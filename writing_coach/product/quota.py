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

The switch (default OFF everywhere): the environment `ORENA_QUOTA_ENFORCEMENT` (on/off) wins when it is set;
otherwise the platform setting `product.quota_enforcement` (`{"enabled": bool, "meters": [...]}`, editable at
`PUT /api/product/admin/quota`) decides, so QA can switch a running sandbox without recreating it. The meters
enforced are `ORENA_QUOTA_METERS` (comma separated) when set, otherwise the setting's list, and only meters this
build has wired (`WIRED_METERS`). Off, or a meter not listed: `admit()` is a no-op ticket and no bucket is
written. On with no quota store (SQLite test backend, missing tables, account backbone off): every listed meter
answers 503 `quota_unavailable`. Enforcement never treats "unknown" as "unlimited".

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
WIRED_METERS: tuple[str, ...] = ("writing.review",)
SWITCH_CACHE_SECONDS = 5.0

# [HUMAN, pending] What a reservation whose owner died after dispatch costs: "admitted" (default, human
# 2026-10-09) charges what was reserved; "zero" would charge nothing.
ABANDONED_SETTLES = "admitted"
# [HUMAN, pending] How long an open reservation may sit before the reconciler decides it was abandoned: more than
# twice the slowest provider timeout of a wired route (OLLAMA_TIMEOUT 180 s).
RECONCILE_AFTER = timedelta(minutes=15)
RECONCILE_INTERVAL_SECONDS = 600

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
    global _runtime, _switch_cache
    _runtime = QuotaRuntime(**fields)
    _switch_cache = None
    return _runtime


def runtime() -> QuotaRuntime:
    return _runtime


def _env() -> Any:
    return os.environ if _runtime.env is None else _runtime.env


def _setting() -> dict | None:
    """The stored switch, cached a few seconds. A read failure keeps the last good value (logged)."""
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
        _log.warning("quota switch setting unreadable; keeping the last value read", exc_info=True)
        return _switch_last_good
    with _switch_lock:
        _switch_cache = (now + SWITCH_CACHE_SECONDS, value)
        _switch_last_good = value
    return value


def _clear_switch_cache() -> None:
    global _switch_cache
    _switch_cache = None


def switch() -> dict[str, Any]:
    """{enabled, meters, source, state, store}. `state`: off | enforced | unavailable."""
    env = _env()
    raw = str(env.get(FLAG, "") or "").strip().casefold()
    setting = _setting() or {}
    if raw in _ON | _OFF:
        enabled, source = raw in _ON, "environment"
    else:
        enabled, source = setting.get("enabled") is True, "setting" if setting else "default"
    raw_meters = env.get(METERS_FLAG)
    listed = (
        [item.strip() for item in str(raw_meters).split(",") if item.strip()]
        if raw_meters is not None and str(raw_meters).strip() != ""
        else [str(item) for item in setting.get("meters") or []]
    )
    ignored = [item for item in listed if item not in WIRED_METERS]
    if ignored:
        _log.warning("quota meters not wired in this build are ignored: %s", ", ".join(ignored))
    meters = [item for item in WIRED_METERS if item in listed]
    store = _runtime.repository is not None and _runtime.incarnations is not None and _runtime.plan_for is not None
    state = "off" if not enabled or not meters else ("enforced" if store else "unavailable")
    return {"enabled": enabled, "meters": meters if enabled else [], "source": source, "state": state,
            "store": "ready" if store else (_runtime.reason or "missing"), "wired_meters": list(WIRED_METERS)}


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


def _reserve(meter: str, units: int, digest: str) -> Ticket:
    from writing_coach.persistence.quota_repository import BucketWindow

    repository = _runtime.repository
    if repository is None or _runtime.incarnations is None or _runtime.plan_for is None:
        raise _unavailable(_runtime.reason or "store")
    user_key = current_user_key()
    incarnation = incarnation_for(user_key)
    try:
        plan = _runtime.plan_for(user_key, strict=True)
        _plans, revision = current_catalog(strict=True)
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
    key = _facts_now().idempotency_key or str(uuid.uuid4())
    op = operation_id(incarnation=incarnation, meter=meter, key=key, request_digest=digest)
    for _attempt in range(2):
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
        if status == "window_closed":
            continue  # the window ended between the read and the lock: decide again in the next one
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


@contextmanager
def admit(meter: str, *, units: int = 1, request_digest: str = "") -> Iterator[Any]:
    """Reserve `units` of `meter` for this request, or refuse it before any provider is called (429/403/409/503).

    A no-op (`NullTicket`) unless the switch is on and lists the meter."""
    if meter not in METERS:
        raise ValueError(f"Unknown meter {meter!r}")
    state = switch()
    if meter not in state["meters"]:
        token = _TICKET.set(NULL_TICKET)
        try:
            yield NULL_TICKET
        finally:
            _TICKET.reset(token)
        return
    ticket = _reserve(meter, units, request_digest)
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
    meters = [key for key in enforced_meters() if key in plan.entitlement_map()]
    if not meters:
        return {}
    repository = _runtime.repository
    if repository is None or _runtime.incarnations is None:
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
    """Open reservations older than RECONCILE_AFTER: a dispatched one is settled (ABANDONED_SETTLES), a reserved
    one (never handed to a provider) is released. Idempotent; several processes may run it."""
    now = now or datetime.now(UTC)
    done = {"settled": 0, "released": 0}
    for row in repository.stale_dispatched(now - RECONCILE_AFTER, limit, states=("reserved", "dispatched")):
        if row["state"] == "dispatched":
            actual = int(row["admitted_units"]) if ABANDONED_SETTLES == "admitted" else 0
            outcome = repository.settle(operation_id=row["operation_id"], actual_units=actual,
                                        outcome_ref="reconciled:abandoned")
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
