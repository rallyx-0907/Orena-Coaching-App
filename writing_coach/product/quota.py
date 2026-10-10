"""Plan quota enforcement: the one entry every metered route goes through (D-160).

    request -> user_key (request context) -> account (stable_uuid("user", user_key))
            -> incarnation (account_incarnations, ensure_active)
            -> effective plan (subscription -> catalogue, STRICT read)
            -> entitlement for the meter (limit, window, unit - catalogue only)
            -> window (the learner's timezone; see `window_for`)
            -> reserve(op, units, limit_policy='current') under the bucket lock
               not admitted: no provider call, 429 / 503
            -> dispatch(op) immediately before the provider call
            -> settle(op, actual) | release(op)
    usage read (Plan & usage, 429 body) = the same bucket rows + the same catalogue limit

Routes never touch the repository or a plan id; they write

    with quota.admit("writing.review", request_digest=...) as ticket:
        ticket.dispatch("...")          # right before the provider call
        ...
        ticket.settle(1)                # or 0 when no AI ran

An exception inside the block settles 0 (dispatched work, the learner got nothing) or releases (not
dispatched). Leaving the block without a settle settles the admitted units.

A meter charged by what the request turns out to be (audio seconds) asks `require_ready()` first, measures the
work locally, then admits exactly that many units (`pronunciation.audio`, D-165).

Work that outlives the call stack that admitted it - a streamed Orena answer is produced in a worker thread after
the route returned - uses `begin()` instead: the same admission, returning the ticket, which the caller then owns
and must settle or release on every path (D-163).

The switch (default OFF everywhere): the environment `ORENA_QUOTA_ENFORCEMENT` (on/off) wins when it is set;
otherwise the platform setting `product.quota_enforcement` (`{"enabled": bool, "meters": [...]}`, editable at
`PUT /api/product/admin/quota`) decides, so QA can switch a running sandbox without recreating it. The meters
enforced are `ORENA_QUOTA_METERS` (comma separated) when set, otherwise the setting's list, and only meters this
build has wired (`WIRED_METERS`). Off, or a meter not listed: `admit()` is a no-op ticket and no bucket is
written. On with no quota store (SQLite test backend, missing tables, account backbone off): every listed meter
answers 503 `quota_unavailable`. Enforcement never treats "unknown" as "unlimited".

Work that outlives the request itself - a media import runs minutes in a background job and survives a restart - keeps
only the operation id (`ticket.operation_id`) with the work. The job dispatches, settles or releases by that id
(`dispatch_operation`, `settle_operation`, `release_operation`), and the meter is listed in `ASYNC_METERS`, so the
reconciler leaves it to its job for `ASYNC_RECONCILE_AFTER`; after that it settles what the owner of the work decided
(`configure_async_decision`), and only a job still in play is settled as admitted (D-16S).

Defaults still waiting for a human answer are named constants here (`ABANDONED_SETTLES`, `RECONCILE_AFTER`) and
in D-160; the refresh route is deliberately not metered.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import math
import os
import threading
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from writing_coach.core.errors import error_detail, orena_http_error
from writing_coach.core.request_context import current_user_key
from writing_coach.product.catalog import (
    METERS,
    CatalogUnavailable,
    Entitlement,
    Plan,
    current_catalog,
    policy_version,
)

_log = logging.getLogger(__name__)

FLAG = "ORENA_QUOTA_ENFORCEMENT"
METERS_FLAG = "ORENA_QUOTA_METERS"
SETTING_KEY = "product.quota_enforcement"
# Meters whose routes this build admits through `admit()`. Listing any other meter enforces nothing, so it is
# refused by the admin setting and ignored (logged) in the environment: a Plan screen must never show a meter as
# counted while nothing counts it.
WIRED_METERS: tuple[str, ...] = ("writing.review", "orena.message", "pronunciation.audio", "media.import")
# Meters whose provider call ends inside the request; only these are reconciled after RECONCILE_AFTER.
SYNC_METERS: tuple[str, ...] = ("writing.review", "orena.message", "pronunciation.audio")
# Meters whose work outlives the request in a background job that settles its own reservation by operation id
# (`settle_operation`, D-16S). The reconciler is only their backstop, after ASYNC_RECONCILE_AFTER.
ASYNC_METERS: tuple[str, ...] = ("media.import",)
SWITCH_CACHE_SECONDS = 5.0

# [HUMAN, pending] What a reservation whose owner died after dispatch costs: "admitted" (default, human
# 2026-10-09) charges what was reserved; "zero" would charge nothing.
ABANDONED_SETTLES = "admitted"
# [HUMAN, pending] How long an open reservation may sit before the reconciler decides it was abandoned: more than
# twice the slowest provider timeout of a wired route (OLLAMA_TIMEOUT 180 s).
RECONCILE_AFTER = timedelta(minutes=15)
# An async meter's job queues behind others and may run for the pipeline's longest audio (MEDIA_ASR_MAX_SECONDS, 90
# minutes) and be re-queued after a restart; its worker, not the reconciler, settles it. A reservation still open
# after this long has lost its job and its entry.
ASYNC_RECONCILE_AFTER = timedelta(hours=6)
RECONCILE_INTERVAL_SECONDS = 600
# How often an admission re-reads the latest bucket when its computed window lost a race (review P1-1).
WINDOW_RETRIES = 4

# A window never shrinks below this when a timezone change moves its boundary (anti-abuse, D-160).
MIN_WINDOW = {"day": timedelta(hours=23), "month": timedelta(days=27)}
DEFAULT_ZONE = "UTC"
UPGRADE_HREF = "#/plan/pricing"

_ON = {"on", "1", "true", "yes"}
_OFF = {"off", "0", "false", "no"}


# --- request context ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RequestFacts:
    idempotency_key: str = ""
    timezone: str = ""


_NO_FACTS = RequestFacts()
_REQUEST: contextvars.ContextVar[RequestFacts | None] = contextvars.ContextVar("orena_quota_request", default=None)


def _facts_now() -> RequestFacts:
    return _REQUEST.get() or _NO_FACTS


class QuotaRequestMiddleware:
    """Pure ASGI: copies `Idempotency-Key` and `X-Orena-Timezone` into the request context, so a route need not
    take the request to be metered."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers") or []}
        key = headers.get("idempotency-key", "").strip()
        zone = headers.get("x-orena-timezone", "").strip()
        token = _REQUEST.set(RequestFacts(
            idempotency_key=key if 0 < len(key) <= 200 and key.isprintable() else "",
            timezone=zone if valid_zone(zone) else "",
        ))
        try:
            return await self.app(scope, receive, send)
        finally:
            _REQUEST.reset(token)


def current_facts() -> RequestFacts:
    """The request's quota facts (idempotency key, timezone) as set by the middleware. A route that admits work from
    another thread (a streamed turn) captures them here, in the request's own context, and replays them there."""
    return _facts_now()


@contextmanager
def request_facts(**facts: str) -> Iterator[None]:
    """For tests and in-process callers: the facts a request's headers would have set."""
    token = _REQUEST.set(RequestFacts(**facts))
    try:
        yield
    finally:
        _REQUEST.reset(token)


def valid_zone(name: str) -> bool:
    if not name or len(name) > 47 or not all(ch.isalnum() or ch in "/_+-" for ch in name):
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


# --- runtime -------------------------------------------------------------------------------------------------

@dataclass
class QuotaRuntime:
    repository: Any | None = None       # PostgresQuotaRepository
    incarnations: Any | None = None     # PostgresIncarnationRepository (ensure_active / resolve)
    plan_for: Callable[..., Plan] | None = None   # (user_key, strict=True) -> Plan
    settings: Any | None = None         # get_setting / set_setting (platform_settings)
    reason: str = ""                    # why the store is missing, for the admin read
    env: Any = None
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)


_runtime = QuotaRuntime()
_switch_cache: tuple[float, dict | None] | None = None
_switch_last_good: dict | None = None
_switch_lock = threading.Lock()


def configure_quota(**fields: Any) -> QuotaRuntime:
    global _runtime, _switch_cache, _switch_last_good, _switch_ever_read
    _runtime = QuotaRuntime(**fields)
    _switch_cache = None
    _switch_last_good = None
    _switch_ever_read = False
    return _runtime


def runtime() -> QuotaRuntime:
    return _runtime


def _env() -> Any:
    return os.environ if _runtime.env is None else _runtime.env


_UNREAD = object()


def _setting() -> Any:
    """The stored switch, cached a few seconds: a dict, None (nothing stored / no store), or `_UNREAD` when the
    store failed and no value was ever read in this process. A failure after a good read keeps that value."""
    global _switch_cache, _switch_last_good
    import time

    if _runtime.settings is None:
        return None
    now = time.monotonic()
    with _switch_lock:
        if _switch_cache is not None and _switch_cache[0] > now:
            return _switch_cache[1]
    try:
        record = _runtime.settings.get_setting(SETTING_KEY)
        value = record.get("value") if record else None
        value = value if isinstance(value, dict) else None
    except Exception:
        if not _switch_ever_read:
            _log.error("quota switch setting unreadable and never read: enforcement fails closed", exc_info=True)
            return _UNREAD
        _log.warning("quota switch setting unreadable; keeping the last value read", exc_info=True)
        return _switch_last_good
    with _switch_lock:
        _switch_cache = (now + SWITCH_CACHE_SECONDS, value)
        _switch_last_good = value
        _mark_read()
    return value


_switch_ever_read = False


def _mark_read() -> None:
    global _switch_ever_read
    _switch_ever_read = True


def _clear_switch_cache() -> None:
    global _switch_cache
    _switch_cache = None


def switch() -> dict[str, Any]:
    """{enabled, meters, source, state, reason, store}. `state`: off | enforced | unavailable.

    Fails closed (review of #116, P2-1):
      * `ORENA_QUOTA_ENFORCEMENT=off` -> off, whatever the setting says;
      * `=on` -> on; if no wired meter resolves (ORENA_QUOTA_METERS empty and the setting lists none or cannot
        be read) every wired meter answers 503 (`reason=no_meters`) - never a silent off;
      * unset -> the admin setting decides; a setting that cannot be read, in a process that never read it, makes
        every wired meter answer 503 (`reason=switch_unreadable`); nothing stored -> off.
    :8000 must pin both environment variables so the setting is never the authority there.
    `meters` lists the meters that are refused or metered (both go through `admit()`'s store path)."""
    env = _env()
    raw = str(env.get(FLAG, "") or "").strip().casefold()
    raw_meters = env.get(METERS_FLAG)
    env_meters = (
        [item.strip() for item in str(raw_meters).split(",") if item.strip()]
        if raw_meters is not None and str(raw_meters).strip() != "" else None
    )
    store = _runtime.repository is not None and _runtime.incarnations is not None and _runtime.plan_for is not None
    base = {"store": "ready" if store else (_runtime.reason or "missing"), "wired_meters": list(WIRED_METERS)}
    if raw in _OFF:
        return {**base, "enabled": False, "meters": [], "source": "environment", "state": "off", "reason": ""}
    setting = _setting() if (raw not in _ON or env_meters is None) else None
    unreadable = setting is _UNREAD
    setting = {} if unreadable or setting is None else setting
    if raw in _ON:
        enabled, source = True, "environment"
    elif unreadable:
        return {**base, "enabled": True, "meters": list(WIRED_METERS), "source": "setting",
                "state": "unavailable", "reason": "switch_unreadable"}
    else:
        enabled, source = setting.get("enabled") is True, "setting" if setting else "default"
    listed = env_meters if env_meters is not None else [str(item) for item in setting.get("meters") or []]
    ignored = [item for item in listed if item not in WIRED_METERS]
    if ignored:
        _log.warning("quota meters not wired in this build are ignored: %s", ", ".join(ignored))
    meters = [item for item in WIRED_METERS if item in listed]
    if not enabled:
        return {**base, "enabled": False, "meters": [], "source": source, "state": "off", "reason": ""}
    if not meters:
        if source == "environment":
            _log.error("ORENA_QUOTA_ENFORCEMENT=on but no wired meter is listed: every wired meter answers 503")
            return {**base, "enabled": True, "meters": list(WIRED_METERS), "source": source,
                    "state": "unavailable", "reason": "switch_unreadable" if unreadable else "no_meters"}
        return {**base, "enabled": True, "meters": [], "source": source, "state": "off", "reason": ""}
    return {**base, "enabled": True, "meters": meters, "source": source,
            "state": "enforced" if store else "unavailable", "reason": "" if store else (_runtime.reason or "store")}


def enforced_meters() -> list[str]:
    return list(switch()["meters"])


def validate_switch_setting(document: object) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ValueError("The quota switch must be an object.")
    enabled = document.get("enabled")
    if type(enabled) is not bool:
        raise ValueError("enabled must be true or false.")
    meters = document.get("meters", [])
    if not isinstance(meters, list) or not all(isinstance(item, str) for item in meters):
        raise ValueError("meters must be a list of meter keys.")
    unwired = [item for item in meters if item not in WIRED_METERS]
    if unwired:
        raise ValueError(f"Not enforceable in this build: {', '.join(unwired)}.")
    return {"enabled": enabled, "meters": [item for item in WIRED_METERS if item in meters]}


def save_switch(document: object, *, updated_by: str = "", audit: dict | None = None) -> dict[str, Any]:
    normalized = validate_switch_setting(document)
    if _runtime.settings is None:
        raise RuntimeError("No settings store on this deployment.")
    _runtime.settings.set_setting(SETTING_KEY, normalized, updated_by=updated_by, audit=audit)
    _clear_switch_cache()
    return switch()


# --- windows: the learner's timezone -------------------------------------------------------------------------

@dataclass(frozen=True)
class Window:
    window_id: str
    start: datetime
    end: datetime
    zone: str


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=zone).astimezone(UTC)


def _first_of_next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def _period(kind: str, local_day: date, zone: ZoneInfo) -> tuple[datetime, datetime, str]:
    if kind == "day":
        return _midnight(local_day, zone), _midnight(local_day + timedelta(days=1), zone), local_day.isoformat()
    first = local_day.replace(day=1)
    return _midnight(first, zone), _midnight(_first_of_next_month(first), zone), first.strftime("%Y-%m")


def zone_of(window_id: str) -> str:
    """The zone a stored window was cut in (`D:2026-10-09@Asia/Ho_Chi_Minh` -> `Asia/Ho_Chi_Minh`)."""
    return window_id.split("@", 1)[1] if "@" in window_id else ""


def window_for(kind: str, *, now: datetime, zone_name: str, previous: dict | None) -> Window:
    """The current window of a `day` or `month` meter, in the learner's timezone, never reopened by a change.

    * The latest bucket, if it is open now, IS the window - whatever zone the request names. A timezone change
      therefore never resets or reopens the window it happens in; it applies from the next one.
    * Otherwise the natural local period containing `now` (local 00:00 to local 00:00; the 1st at 00:00 for a
      month), cut in `zone_name`. If that period would start before the previous window ended (the zone moved
      west, so the new local day began earlier), it starts where the previous window ended instead, and ends at
      the first local boundary at least `MIN_WINDOW` later - a learner hopping zones never gets a short window.
    * window_id = `D:<local date>@<zone>` or `M:<local yyyy-mm>@<zone>`, the local date/month of its start; the
      bucket stores the true UTC start and end, and `resets_at` is that end.
    """
    if previous is not None and previous["window_start"] <= now < previous["window_end"]:
        zone = zone_of(previous["window_id"]) or zone_name
        return Window(previous["window_id"], previous["window_start"], previous["window_end"], zone)
    zone = ZoneInfo(zone_name)
    local_day = now.astimezone(zone).date()
    start, end, label = _period(kind, local_day, zone)
    if previous is not None and start < previous["window_end"]:
        start = previous["window_end"]
        label_day = start.astimezone(zone).date()
        label = label_day.isoformat() if kind == "day" else label_day.strftime("%Y-%m")
        while end < start + MIN_WINDOW[kind]:
            boundary = end.astimezone(zone).date()  # the local date the current end falls on
            nxt = boundary + timedelta(days=1) if kind == "day" else _first_of_next_month(boundary)
            end = _midnight(nxt, zone)
    prefix = "D" if kind == "day" else "M"
    return Window(f"{prefix}:{label}@{zone_name}", start, end, zone_name)


def _zone_for(previous: dict | None) -> str:
    """The stored zone is the request's (the browser's, sent on every call); else the zone of the learner's last
    window ("recorded on the account" - the bucket is where it is recorded); else UTC. No account column holds a
    timezone today (D-160: a schema decision reserved to the human)."""
    requested = _facts_now().timezone
    if requested:
        return requested
    recorded = zone_of(previous["window_id"]) if previous else ""
    return recorded if valid_zone(recorded) else DEFAULT_ZONE


# --- errors -------------------------------------------------------------------------------------------------

def _unavailable(reason: str) -> HTTPException:
    return orena_http_error(503, "quota_unavailable",
                            "Usage limits cannot be checked right now. Please try again in a moment.",
                            retryable=True, context={"reason": reason})


def exhausted_error(facts: dict[str, Any], *, now: datetime) -> HTTPException:
    resets_at = facts.get("resets_at")
    headers = {}
    if resets_at:
        wait = (datetime.fromisoformat(resets_at.replace("Z", "+00:00")) - now).total_seconds()
        headers["Retry-After"] = str(max(1, math.ceil(wait)))
    message = f"You have used {facts['used']} of {facts['limit']} for {facts['feature']} in this period."
    return HTTPException(429, detail=error_detail("quota_exhausted", message, retryable=False, context=facts),
                         headers=headers or None)


def _iso(instant: datetime | None) -> str | None:
    if instant is None:
        return None
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


# --- admission ----------------------------------------------------------------------------------------------

class NullTicket:
    """What `admit()` yields when the meter is not enforced: every call is a no-op."""

    enforced = False
    usage: dict[str, Any] = {}

    def dispatch(self, ref: str = "") -> None:
        return None

    def settle(self, actual: int, outcome_ref: str | None = None) -> None:
        return None

    def release(self) -> None:
        return None


NULL_TICKET = NullTicket()
_TICKET: contextvars.ContextVar[Any] = contextvars.ContextVar("orena_quota_ticket", default=NULL_TICKET)


def current_ticket() -> Any:
    """The ticket of the `admit()` block this code runs in, or the no-op ticket."""
    return _TICKET.get()


class Ticket:
    enforced = True

    def __init__(self, repository: Any, operation_id: str, units: int, usage: dict[str, Any]) -> None:
        self._repository = repository
        self.operation_id = operation_id
        self.units = units
        self.usage = usage
        self.dispatched = False
        self.finished = False

    def dispatch(self, ref: str = "") -> None:
        if self.dispatched or self.finished:
            return
        ref = (ref or "dispatch")[:200]
        try:
            outcome = self._repository.dispatch(operation_id=self.operation_id, dispatch_ref=ref)
        except Exception as error:
            self.release()
            raise _unavailable("store") from error
        status = outcome.get("status")
        if status in ("dispatch", "duplicate"):
            self.dispatched = True
            return
        self.release()
        if status == "denied":
            raise orena_http_error(403, "account_deleted", "This account was deleted.", retryable=False)
        raise _unavailable(f"dispatch_{status}")

    def settle(self, actual: int, outcome_ref: str | None = None) -> None:
        if self.finished:
            return
        self.finished = True
        actual = max(0, min(int(actual), self.units))
        try:
            outcome = self._repository.settle(operation_id=self.operation_id, actual_units=actual,
                                              outcome_ref=(outcome_ref or None) and outcome_ref[:200])
            if outcome.get("status") not in ("settle", "duplicate"):
                _log.warning("quota settle %s: %s", self.operation_id, outcome)
        except Exception:
            # Left open; the reconciler settles it (ABANDONED_SETTLES).
            _log.warning("quota settle failed for %s; left to the reconciler", self.operation_id, exc_info=True)

    def release(self) -> None:
        if self.finished:
            return
        self.finished = True
        try:
            self._repository.release(operation_id=self.operation_id)
        except Exception:
            _log.warning("quota release failed for %s; left to the reconciler", self.operation_id, exc_info=True)


def account_id(user_key: str) -> str:
    from writing_coach.persistence.ids import stable_uuid

    return str(stable_uuid("user", user_key))


def incarnation_for(user_key: str) -> str:
    """The request's account incarnation (the work_api / billing_api pattern); errors in the HTTP envelope."""
    from writing_coach.persistence.incarnation_repository import DeletionBarrier

    try:
        return _runtime.incarnations.ensure_active(account_id(user_key))
    except DeletionBarrier:
        raise orena_http_error(403, "account_deleted", "This account was deleted.", retryable=False) from None
    except ValueError:
        raise orena_http_error(409, "account_not_ready", "This account is not set up yet.", retryable=True) from None
    except Exception as error:
        raise _unavailable("incarnation") from error


def operation_id(*, incarnation: str, meter: str, key: str, request_digest: str) -> str:
    """Scoped by incarnation and meter (operation ids are global), sensitive to the request body."""
    material = "|".join((str(incarnation), meter, key, request_digest))
    return "q1:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]


def request_digest(value: Any) -> str:
    """A stable digest of a request body (a pydantic model, a mapping or a string)."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _entitlement(plan: Plan, meter: str) -> Entitlement:
    entitlement = plan.entitlement_map().get(meter)
    if entitlement is None or not entitlement.enabled:
        raise orena_http_error(403, "feature_not_in_plan", "This feature is not part of your plan.",
                               retryable=False, context={"feature": meter, "plan": plan.id, "upgrade": UPGRADE_HREF})
    return entitlement


def _facts(meter: str, entitlement: Entitlement, plan: Plan, *, used: int, window: Window) -> dict[str, Any]:
    spec = METERS[meter]
    return {
        "feature": meter, "used": int(used), "limit": entitlement.limit, "unit": spec.unit,
        "display_unit": spec.display_unit, "scale": spec.scale, "window": spec.window,
        "resets_at": _iso(window.end), "plan": plan.id, "upgrade": UPGRADE_HREF,
    }


def _reserve(meter: str, units: int, digest: str, idempotency_key: str | None = None) -> Ticket:
    from writing_coach.persistence.quota_repository import BucketWindow

    repository = _runtime.repository
    if repository is None or _runtime.incarnations is None or _runtime.plan_for is None:
        raise _unavailable(_runtime.reason or "store")
    user_key = current_user_key()
    incarnation = incarnation_for(user_key)
    try:
        # One catalogue snapshot for both the limit and the policy label it is recorded under (review P3-2); the
        # subscription read only names the effective plan.
        plans, revision = current_catalog(strict=True)
        plan = plans.get(_runtime.plan_for(user_key, strict=True).id)
        if plan is None:
            raise CatalogUnavailable("the effective plan is not in the catalogue snapshot")
    except CatalogUnavailable as error:
        raise _unavailable("catalogue") from error
    except HTTPException:
        raise
    except Exception as error:
        raise _unavailable("subscription") from error
    entitlement = _entitlement(plan, meter)
    kind = METERS[meter].window
    if kind not in MIN_WINDOW:
        raise ValueError(f"{meter} is a count cap, not a windowed meter")
    key = idempotency_key or _facts_now().idempotency_key or str(uuid.uuid4())
    op = operation_id(incarnation=incarnation, meter=meter, key=key, request_digest=digest)
    for _attempt in range(WINDOW_RETRIES):
        now = _runtime.clock()
        try:
            previous = repository.latest_buckets(incarnation, [meter]).get(meter)
            window = window_for(kind, now=now, zone_name=_zone_for(previous), previous=previous)
            outcome = repository.reserve(
                incarnation_id=incarnation, meter=meter, operation_id=op, requested_units=units,
                window=BucketWindow(window.window_id, window.start, window.end,
                                    policy_version(plan.id, revision), entitlement.limit),
                limit_policy="current",
            )
        except Exception as error:
            raise _unavailable("store") from error
        status = outcome.get("status")
        if status in ("window_closed", "window_superseded"):
            # The window ended between the read and the lock, or another request (in another zone) opened the
            # current window first: read the latest bucket again and decide in the window that now holds.
            continue
        break
    else:
        raise _unavailable("window")
    if status == "admit":
        used = (previous or {}).get("consumed", 0) + (previous or {}).get("reserved", 0) + units \
            if previous and previous["window_id"] == window.window_id else units
        return Ticket(repository, op, units, _facts(meter, entitlement, plan, used=used, window=window))
    if status == "exhausted":
        used = int(outcome.get("consumed", 0)) + int(outcome.get("reserved", 0))
        raise exhausted_error(_facts(meter, entitlement, plan, used=used, window=window), now=now)
    if status == "duplicate":
        if outcome.get("state") in ("reserved", "dispatched"):
            raise orena_http_error(409, "operation_in_progress", "This request is already being processed.",
                                   retryable=True)
        raise orena_http_error(409, "operation_finished",
                               "This request was already processed. Send it again as a new request.",
                               retryable=False)
    if status == "payload_conflict":
        raise orena_http_error(409, "operation_conflict", "This request key was used for another request.",
                               retryable=False)
    if status == "denied":
        raise orena_http_error(403, "account_deleted", "This account was deleted.", retryable=False)
    raise _unavailable(str(status))


# The owner of an async meter's work tells the backstop what a job it finds abandoned actually decided: `fn(operation_id)`
# returns (units, outcome_ref), None when the job is still in play (the backstop then settles as admitted, below), and
# raises when the owner cannot tell (the row is left for the next tick, never guessed).
_async_decision: Callable[[str], tuple[int, str] | None] | None = None


def configure_async_decision(decide: Callable[[str], tuple[int, str] | None] | None) -> None:
    global _async_decision
    _async_decision = decide


# --- work that outlives its request: act on a reservation by operation id ----------------------------------------

def _store_repository() -> Any:
    repository = _runtime.repository
    if repository is None:
        raise _unavailable(_runtime.reason or "store")
    return repository


def dispatch_operation(operation_id: str, ref: str = "") -> str:
    """The background job is about to start paid work: `dispatched` for this reservation, by id.

    Returns the repository's verdict (`dispatch`, `duplicate` for a job re-queued after a restart, `denied` for a
    deleted account, `unknown_operation`, ...). Raises on a store failure. The caller decides what each verdict
    means for its job; paid work starts only on `dispatch` or `duplicate`."""
    outcome = _store_repository().dispatch(operation_id=operation_id, dispatch_ref=(ref or "dispatch")[:200])
    return str(outcome.get("status"))


def settle_operation(operation_id: str, actual: int, outcome_ref: str | None = None) -> str:
    """Settle `actual` units of a reservation by id (idempotent). Returns the verdict; raises on a store failure.

    Used by a background job, which cannot hold the request's `Ticket`: the id was kept with the work, so the
    settlement survives a process restart. `actual` can never exceed what was reserved (`exceeds_admitted`)."""
    outcome = _store_repository().settle(operation_id=operation_id, actual_units=max(0, int(actual)),
                                         outcome_ref=(outcome_ref or None) and outcome_ref[:200])
    return str(outcome.get("status"))


def release_operation(operation_id: str) -> str:
    """Give back a reservation that never reached a provider (by id, idempotent)."""
    return str(_store_repository().release(operation_id=operation_id).get("status"))


def enforces(meter: str) -> bool:
    """True when this meter is listed (metered, or refused because the store is unavailable)."""
    return meter in switch()["meters"]


def begin(meter: str, *, units: int = 1, request_digest: str = "", idempotency_key: str | None = None) -> Any:
    """`admit()` without the context manager: returns the ticket, which the caller settles or releases itself.

    For work that outlives the call stack that admitted it - a streamed answer is produced in a worker thread
    after the route returned - where a `with` block cannot span the lifetime and a contextvar token cannot be
    reset from another thread. The caller owns the ticket: it must `settle` or `release` it on every path (the
    reconciler is only the backstop). The no-op ticket when the meter is not enforced.

    Raises the same 429 / 403 / 409 / 503 as `admit()`, before any provider is called."""
    if meter not in METERS:
        raise ValueError(f"Unknown meter {meter!r}")
    state = switch()
    if meter in state["meters"] and state["state"] == "unavailable":
        raise _unavailable(state["reason"] or "store")
    if meter not in state["meters"]:
        return NULL_TICKET
    return _reserve(meter, units, request_digest, idempotency_key)


def require_ready(meter: str) -> bool:
    """True when `meter` is enforced and enforcement can run; False when it is not enforced; 503 when it is enforced
    but cannot be checked (the switch, the store or the catalogue is unreadable). For a route whose units are known
    only after local work (decoding audio): it asks first, so that work is not done for a request about to be
    refused, and a route that does not enforce the meter does none of it."""
    if meter not in METERS:
        raise ValueError(f"Unknown meter {meter!r}")
    state = switch()
    if meter not in state["meters"]:
        return False
    if state["state"] == "unavailable":
        raise _unavailable(state["reason"] or "store")
    return True


def refuse_unmetered(meter: str, *, category: str, message: str) -> None:
    """Fail closed for a path that cannot be metered yet: 503 `category` when `meter` is enforced (or enforcement
    cannot tell), nothing when it is not. Used by live voice, which is charged by duration in a later change."""
    if enforces(meter):
        raise orena_http_error(503, category, message, retryable=False, context={"feature": meter})


@contextmanager
def admit(meter: str, *, units: int = 1, request_digest: str = "", idempotency_key: str | None = None) -> Iterator[Any]:
    """Reserve `units` of `meter` for this request, or refuse it before any provider is called (429/403/409/503).

    A no-op (`NullTicket`) unless the switch is on and lists the meter. `idempotency_key` overrides the
    `Idempotency-Key` header (a body field the client already uses to make a retry safe)."""
    ticket = begin(meter, units=units, request_digest=request_digest, idempotency_key=idempotency_key)
    if ticket is NULL_TICKET:
        token = _TICKET.set(NULL_TICKET)
        try:
            yield NULL_TICKET
        finally:
            _TICKET.reset(token)
        return
    token = _TICKET.set(ticket)
    try:
        yield ticket
    except BaseException:
        if not ticket.finished:
            if ticket.dispatched:
                ticket.settle(0, "failed")
            else:
                ticket.release()
        raise
    else:
        if not ticket.finished:
            ticket.settle(units, "completed")
    finally:
        _TICKET.reset(token)


# --- usage read (Plan & usage) ------------------------------------------------------------------------------

def usage_for(user_key: str, plan: Plan) -> dict[str, dict[str, Any]]:
    """What the Plan & usage screen shows, read from the buckets enforcement writes.

    Only enforced meters appear (`known` with `used` and `resets_at`, or `unavailable`); the rest are not
    metered and the caller says so. Never "0 used" for a store it could not read."""
    state = switch()
    meters = [key for key in state["meters"] if key in plan.entitlement_map()]
    if not meters:
        return {}
    repository = _runtime.repository
    if state["state"] == "unavailable" or repository is None or _runtime.incarnations is None:
        return {key: {"state": "unavailable"} for key in meters}
    try:
        # The display's limits are known only when enforcement's own (strict) catalogue read works (review P3-4).
        current_catalog(strict=True)
    except CatalogUnavailable:
        return {key: {"state": "unavailable"} for key in meters}
    try:
        now = _runtime.clock()
        incarnation = _runtime.incarnations.resolve(account_id(user_key))
        latest = repository.latest_buckets(incarnation, meters) if incarnation else {}
        out: dict[str, dict[str, Any]] = {}
        for key in meters:
            previous = latest.get(key)
            window = window_for(METERS[key].window, now=now, zone_name=_zone_for(previous), previous=previous)
            used = int(previous["consumed"]) + int(previous["reserved"]) \
                if previous and previous["window_id"] == window.window_id else 0
            out[key] = {"state": "known", "used": used, "resets_at": _iso(window.end), "window_id": window.window_id}
        return out
    except Exception:
        _log.warning("quota usage unreadable", exc_info=True)
        return {key: {"state": "unavailable"} for key in meters}


# --- reconciler -----------------------------------------------------------------------------------------------

def reconcile_once(repository: Any, *, now: datetime | None = None, limit: int = 200) -> dict[str, int]:
    """Open reservations older than their meter's threshold: a dispatched one is settled (ABANDONED_SETTLES), a
    reserved one (never handed to a provider) is released. Idempotent; several processes may run it.

    Scoped by meter (review P3-1): a synchronous meter is swept after RECONCILE_AFTER, an async meter (media import,
    settled by its own worker) only after ASYNC_RECONCILE_AFTER, so a long import is never swept while it runs."""
    now = now or datetime.now(UTC)
    done = {"settled": 0, "released": 0}
    for meters, after in ((SYNC_METERS, RECONCILE_AFTER), (ASYNC_METERS, ASYNC_RECONCILE_AFTER)):
        for row in repository.stale_dispatched(now - after, limit, states=("reserved", "dispatched"), meters=meters):
            if row["state"] == "dispatched":
                actual = int(row["admitted_units"]) if ABANDONED_SETTLES == "admitted" else 0
                ref = "reconciled:abandoned"
                if meters is ASYNC_METERS and _async_decision is not None:
                    try:
                        decided = _async_decision(row["operation_id"])
                    except Exception:  # noqa: BLE001 - the owner cannot tell now: not guessed, retried next tick
                        _log.warning("quota reconciler: no decision for %s yet", row["operation_id"], exc_info=True)
                        continue
                    if decided is not None:
                        actual, ref = min(max(0, int(decided[0])), int(row["admitted_units"])), f"reconciled:{decided[1]}"[:200]
                outcome = repository.settle(operation_id=row["operation_id"], actual_units=actual,
                                            outcome_ref=ref)
                done["settled"] += outcome.get("status") == "settle"
            else:
                outcome = repository.release(operation_id=row["operation_id"])
                done["released"] += outcome.get("status") == "release"
    if any(done.values()):
        _log.info("quota reconciler: %s", done)
    return done


class QuotaReconcileSchedule:
    """At start and then every RECONCILE_INTERVAL_SECONDS, on its own daemon thread (the feedback-retention
    pattern). Started only where a quota store exists."""

    def __init__(self, repository: Any, *, interval: float = RECONCILE_INTERVAL_SECONDS) -> None:
        self._repository = repository
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> dict[str, int] | None:
        try:
            return reconcile_once(self._repository)
        except Exception:
            _log.warning("quota reconciler failed; retried at the next tick", exc_info=True)
            return None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self._interval)

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="quota-reconciler", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
