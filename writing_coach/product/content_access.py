"""Content access (Monetisation v2, D-248 §4-§6, MV2-1): the one place that decides `access_tier(item)` and whether a
learner may have it.

**The tier is computed, not stored.** Every rule below is deterministic, so every worker gives the same answer with no
table and no cron. Only exceptions are stored: a bounded list of per-item overrides in one `platform_settings` document
(`OVERRIDES_KEY`), edited through the admin API with an audit row. A stored per-item tier column is a human schema gate
(D-248 §4) and does not exist.

Rules, per kind:

* **Reading article** (`reading`). In each (language, level) pool of published articles:
  - Free = a *floor* (the earliest `ceil(s x n)` published) UNION a *stable bucket* (`int(sha256(id)[:8], 16) % 100 <
    s x 100`), with `s = 1 - sqrt(1 - free_percent)` so the union is about `free_percent` of the pool. Both parts only
    grow as articles are published, so a publish never takes a Free article away (review of #466, P1);
  - a *weekly rotation*: from the Plus pool as it stood at the start of the ISO week (UTC, Monday 00:00), the
    `rotation_per_week` articles with the smallest `sha256("<ISO week>:<id>")` are Free that week; a publish during
    the week never reshuffles them;
  - everything else is Plus.
* **Media** (`media`, YouTube or other). Watching is **always** Free, at every plan, after any weekly cap: YouTube API
  Services Developer Policies III.F.3.a ("API Clients must not charge users to watch content in an embedded YouTube
  player"). The channel's own captions are never paid. Only Orena's learning tools around the player are tiered
  (`MEDIA_TOOLS`): tap-to-look-up is Free on `media.tools_weekly` videos a week (the plan catalogue's weekly meter; one
  video counts once a week); full bilingual translation, scored shadowing, dictation and save-to-review are Plus.
* **Own sets** (`vocab_set`, `grammar`, `mock_test`): the first `set_free_items` items of each set (by position) are
  Free, the rest Plus. A learner's own decks are never gated (they are not a set this module is asked about).
* **Overrides**: `<kind>:<id>` -> `free` | `plus` | `pro` wins over every rule. A media item can only be forced Free
  (its tools); it can never be made paid, since watching is never sold.

Every number is a policy (`writing_coach.policies`, group `access`), editable in Admin, except the weekly video count,
which is the `media.tools_weekly` limit of each plan in the plan catalogue (Admin › Plans), because it differs per plan.

**Entitlement.** `learner_tier` is the account's effective plan (`product.entitlement`: a billing grant - including a
`trialing` one - then an administrator's grant, D-154), read strictly: a plan that cannot be read is 503
`quota_unavailable`, never an upgrade prompt over an outage (D-248 §6). A server with no plan system at all (tests, a
bare development server) lets everything through, as `plan_features` does.

**Enforcement.** The routes call `require_reading` / `require_media_tool` / `gate_media_payload`. They refuse only while
the `access.enforced` policy is on (default off until the learner UI's locked state, MV2-3, can show the refusal); the
tiering and the cache rule (`cache_control`) apply either way. A refusal is **403 `plan_required`** in the contract's
error envelope with `{required_tier, kind, item_id, plan, upgrade, trial_available, preview}`; the same values are
also carried under D-248 §6's names (`content_kind`, `content_id`, `required_plan`).

**Analytics.** `locked_view`, `upgrade_sheet_open` and `trial_start` are counted through the existing usage counter
(`usage_events`, `record_usage`) as `access.<event>:<detail>`, where the detail is a content kind or a source token -
never a title, an id or any learner content.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from writing_coach import policies
from writing_coach.core.errors import orena_http_error

_log = logging.getLogger(__name__)

TIERS: tuple[str, ...] = ("free", "plus", "pro")
RANK: dict[str, int] = {tier: rank for rank, tier in enumerate(TIERS)}
KINDS: tuple[str, ...] = ("reading", "media", "vocab_set", "grammar", "mock_test")
SET_KINDS: frozenset[str] = frozenset({"vocab_set", "grammar", "mock_test"})

# Orena's learning tools around a media player, and the tier each needs. `lookup` is Free but metered weekly.
MEDIA_TOOLS: dict[str, str] = {
    "lookup": "free",
    "translation": "plus",
    "shadowing_score": "plus",
    "dictation": "plus",
    "save_to_review": "plus",
}
MEDIA_TOOLS_METER = "media.tools_weekly"
UPGRADE_HREF = "#/plan/pricing"

OVERRIDES_KEY = "product.content_access"
OVERRIDES_VERSION = 1
MAX_OVERRIDES = 2000
CACHE_SECONDS = 5.0
POOL_CACHE_SECONDS = 60.0

EVENTS: tuple[str, ...] = ("locked_view", "upgrade_sheet_open", "trial_start")
_DETAIL = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ITEM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")


class OverridesInvalid(ValueError):
    """An administrator's override change that cannot be applied (HTTP 422)."""


# --- the rules (pure) ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    """One piece of content to decide for. `position` is the 0-based place of a set's item in its set."""

    kind: str
    id: str
    language: str = ""
    level: str = ""
    position: int | None = None

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id}"


@dataclass(frozen=True)
class Decision:
    tier: str
    reason: str  # bucket | floor | rotation | rule | override | first_item | viewing
    rotation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"tier": self.tier, "reason": self.reason, "rotation": self.rotation}


def bucket(item_id: str) -> int:
    """The stable 0-99 bucket of one id: the same id always lands in the same bucket."""
    return int(hashlib.sha256(str(item_id).encode("utf-8")).hexdigest()[:8], 16) % 100


def iso_week(moment: datetime | None = None) -> str:
    """`2026-W43`: the ISO week of `moment` in UTC (Monday 00:00 UTC starts it)."""
    moment = (moment or datetime.now(UTC)).astimezone(UTC)
    year, week, _day = moment.isocalendar()
    return f"{year}-W{week:02d}"


def _rotation_rank(week: str, item_id: str) -> str:
    return hashlib.sha256(f"{week}:{item_id}".encode()).hexdigest()


def reading_free_ids(pool: Iterable[tuple[str, Any]], *, free_percent: int, rotation_per_week: int,
                     week: str) -> tuple[frozenset[str], frozenset[str]]:
    """(the Free ids of one (language, level) pool, the week's rotation picks).

    Free = the earliest `ceil(s x n)` published articles (the floor) UNION the articles whose stable bucket is under
    `s`, where `s = 1 - sqrt(1 - free_percent)` so the union is about `free_percent` of the pool. Both parts only grow
    when a newer article is published (the prefix keeps its members, a bucket never moves), so **publishing never
    takes a Free article away** - and a level of one article has it Free.

    The rotation is drawn from the Plus pool **as it stood at the start of the ISO week** (articles published before
    Monday 00:00 UTC), so a publish during the week never reshuffles that week's picks.

    `pool` is `(id, published_at)` for every published article of the pool. Pure: the same pool, numbers and week give
    the same answer everywhere."""
    items = _ordered(pool)
    if not items:
        return frozenset(), frozenset()
    share = split_share(free_percent)
    free = _free_set(items, share)
    start = week_start(week)
    before = [(item_id, published) for item_id, published in items
              if isinstance(published, datetime) and _aware(published) < start]
    plus_at_start = [item_id for item_id in (pair[0] for pair in before) if item_id not in _free_set(before, share)]
    count = max(0, int(rotation_per_week))
    rotation = sorted(plus_at_start, key=lambda item_id: _rotation_rank(week, item_id))[:count]
    return frozenset(free), frozenset(rotation) - free


def split_share(free_percent: int) -> float:
    """The share each part of the Free set uses, so floor and bucket together are about `free_percent`."""
    p = max(0, min(100, int(free_percent))) / 100
    return 1.0 if p >= 1 else 1 - math.sqrt(1 - p)


def _ordered(pool: Iterable[tuple[str, Any]]) -> list[tuple[str, Any]]:
    return sorted({str(item_id): published for item_id, published in pool}.items(),
                  key=lambda pair: (_sortable(pair[1]), pair[0]))


def _free_set(items: list[tuple[str, Any]], share: float) -> set[str]:
    floor = math.ceil(share * len(items) - 1e-9)
    earliest = {item_id for item_id, _published in items[:floor]}
    return earliest | {item_id for item_id, _published in items if bucket(item_id) < share * 100}


def week_start(week: str) -> datetime:
    """Monday 00:00 UTC of an ISO week named `2026-W43`."""
    year, _sep, number = week.partition("-W")
    day = date.fromisocalendar(int(year), int(number), 1)
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _aware(moment: datetime) -> datetime:
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)


def _sortable(published: Any) -> str:
    if isinstance(published, datetime):
        return (published if published.tzinfo else published.replace(tzinfo=UTC)).astimezone(UTC).isoformat()
    return str(published or "9999")


def set_tier(position: int | None, *, free_items: int) -> Decision:
    """A set's item: the first `free_items` (by position) are Free, the rest Plus. No position is the first item."""
    index = 0 if position is None else max(0, int(position))
    return Decision("free", "first_item") if index < max(0, int(free_items)) else Decision("plus", "rule")


# --- configuration ---------------------------------------------------------------------------------------------------

ReadingPool = Callable[[str, str], list[tuple[str, Any]]]


@dataclass
class _Runtime:
    store: Any | None = None                                   # get_setting / set_setting (platform_settings)
    reading_pool: ReadingPool | None = None                     # (language, level) -> [(id, published_at)]
    record_usage: Callable[..., None] | None = None             # product repository record_usage (usage_events)
    # Billing's seam (D-248 §1): whether this learner may still start the 7-day trial. None until Billing installs it,
    # and the refusal then says `trial_available: null` (not known), never a guess.
    trial_available: Callable[[str], bool | None] | None = None
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)


_runtime = _Runtime()
_lock = threading.Lock()
_overrides_cache: tuple[float, dict[str, Any]] | None = None
_overrides_last_good: dict[str, Any] | None = None
_pool_cache: dict[tuple[str, str], tuple[float, list[tuple[str, Any]]]] = {}


def configure(*, store: Any | None = None, reading_pool: ReadingPool | None = None,
              record_usage: Callable[..., None] | None = None,
              trial_available: Callable[[str], bool | None] | None = None,
              clock: Callable[[], datetime] | None = None) -> None:
    """app.py installs the platform settings store, the Reading pool read, the usage counter and Billing's trial seam."""
    global _runtime, _overrides_cache, _overrides_last_good
    with _lock:
        _runtime = _Runtime(store=store, reading_pool=reading_pool, record_usage=record_usage,
                            trial_available=trial_available, clock=clock or (lambda: datetime.now(UTC)))
        _overrides_cache = None
        _overrides_last_good = None
        _pool_cache.clear()


def configure_trial(trial_available: Callable[[str], bool | None] | None) -> None:
    """Billing's seam: install (or remove) the read of whether a learner may still start the trial."""
    _runtime.trial_available = trial_available


def enforced() -> bool:
    """Whether the routes refuse gated content now (`access.enforced`, Admin › Policies)."""
    return policies.value("access.enforced") is True


# --- overrides (platform_settings) ---------------------------------------------------------------------------------

def _parse_overrides(record: Mapping[str, Any] | None) -> dict[str, Any]:
    document = (record or {}).get("value") if record else None
    raw = document.get("overrides") if isinstance(document, Mapping) else None
    clean: dict[str, str] = {}
    for key, tier in (raw or {}).items() if isinstance(raw, Mapping) else ():
        try:
            clean[_override_key(key)] = _override_tier(key, tier)
        except OverridesInvalid:
            _log.warning("content access: ignoring a stored override that is not valid now: %r", key)
    return {"overrides": clean, "updated_at": (record or {}).get("updated_at"),
            "updated_by": (record or {}).get("updated_by")}


def _overrides_document() -> dict[str, Any]:
    global _overrides_cache, _overrides_last_good
    now = time.monotonic()
    with _lock:
        if _overrides_cache is not None and _overrides_cache[0] > now:
            return _overrides_cache[1]
        store = _runtime.store
    if store is None:
        loaded = {"overrides": {}, "updated_at": None, "updated_by": None}
    else:
        try:
            loaded = _parse_overrides(store.get_setting(OVERRIDES_KEY))
        except Exception:  # noqa: BLE001 - an unreadable document keeps the last one read; the rules still decide
            _log.warning("content access overrides unreadable; keeping the last ones read", exc_info=True)
            loaded = _overrides_last_good or {"overrides": {}, "updated_at": None, "updated_by": None}
            with _lock:
                _overrides_cache = (now + CACHE_SECONDS, loaded)
            return loaded
    with _lock:
        _overrides_cache = (now + CACHE_SECONDS, loaded)
        _overrides_last_good = loaded
    return loaded


def overrides() -> dict[str, str]:
    return dict(_overrides_document()["overrides"])


def _override_key(key: object) -> str:
    text = str(key or "").strip()
    kind, _sep, item_id = text.partition(":")
    if kind not in KINDS or not _ITEM_ID.match(item_id):
        raise OverridesInvalid(f"Unknown content {text!r}: use <kind>:<id> with a kind in {', '.join(KINDS)}.")
    return f"{kind}:{item_id}"


def _override_tier(key: object, tier: object) -> str:
    value = str(tier or "").strip().casefold()
    if value not in TIERS:
        raise OverridesInvalid(f"{key}: the tier must be free, plus or pro.")
    if str(key).startswith("media:") and value != "free":
        # YouTube API Services Developer Policies III.F.3.a: watching is never sold, so a video is never made paid.
        raise OverridesInvalid(f"{key}: a video can only be made free; watching is never sold.")
    return value


def admin_snapshot() -> dict[str, Any]:
    document = _overrides_document()
    return {
        "version": OVERRIDES_VERSION,
        "overrides": dict(document["overrides"]),
        "updated_at": document["updated_at"],
        "updated_by": document["updated_by"],
        "max_overrides": MAX_OVERRIDES,
        "kinds": list(KINDS),
        "tiers": list(TIERS),
        "enforced": enforced(),
        "policies": {key: policies.value(key) for key in ACCESS_POLICIES},
        "media_tools": dict(MEDIA_TOOLS),
    }


ACCESS_POLICIES: tuple[str, ...] = ("access.enforced", "access.reading_free_percent", "access.reading_rotation_per_week",
                                    "access.set_free_items")


def save_overrides(change: object, *, updated_by: str = "", actor: str = "") -> dict[str, Any]:
    """Apply `{"set": {"<kind>:<id>": tier}, "remove": ["<kind>:<id>"], "expected_updated_at": ...}`.

    A compare-and-set on the stored version (absent: the version just read), with the audit row written in the same
    transaction (the policies' contract). Raises `OverridesInvalid` (422) and the store's `SettingConflict` (409)."""
    global _overrides_cache
    store = _runtime.store
    if store is None:
        raise RuntimeError("The content access store has not been installed by the persistence runtime.")
    if not isinstance(change, Mapping):
        raise OverridesInvalid("The change must be an object.")
    unknown = set(change) - {"set", "remove", "expected_updated_at"}
    if unknown:
        raise OverridesInvalid(f"Unknown field {sorted(unknown)[0]!r}.")
    to_set = change.get("set") or {}
    to_remove = change.get("remove") or []
    if not isinstance(to_set, Mapping) or not isinstance(to_remove, list):
        raise OverridesInvalid("`set` must be an object and `remove` a list.")
    clean = {_override_key(key): _override_tier(key, tier) for key, tier in to_set.items()}
    removed = [_override_key(key) for key in to_remove]
    try:
        record = store.get_setting(OVERRIDES_KEY)
    except Exception as error:
        raise RuntimeError("The content access store could not be read.") from error
    base = _parse_overrides(record)["overrides"]
    expected = change["expected_updated_at"] if "expected_updated_at" in change else (
        record.get("updated_at") if record else None)
    after = {**base, **clean}
    for key in removed:
        after.pop(key, None)
    if len(after) > MAX_OVERRIDES:
        raise OverridesInvalid(f"At most {MAX_OVERRIDES} overrides can be kept.")
    changes = {key: {"from": base.get(key), "to": after.get(key)}
               for key in sorted(set(clean) | set(removed)) if base.get(key) != after.get(key)}
    if not changes:
        return admin_snapshot()
    document = {"version": OVERRIDES_VERSION, "overrides": {key: after[key] for key in sorted(after)}}
    audit = {"action": "product.content_access.update", "actor": actor, "entity_type": "platform_setting",
             "entity_id": OVERRIDES_KEY, "payload": {"changes": changes}}
    store.set_setting(OVERRIDES_KEY, document, updated_by=updated_by, expected_updated_at=expected, audit=audit)
    with _lock:
        _overrides_cache = None
    return admin_snapshot()


# --- deciding a tier -------------------------------------------------------------------------------------------------

def _reading_pool(language: str, level: str) -> list[tuple[str, Any]]:
    reader = _runtime.reading_pool
    if reader is None:
        return []
    cache_key = (language, level)
    now = time.monotonic()
    with _lock:
        cached = _pool_cache.get(cache_key)
        if cached is not None and cached[0] > now:
            return cached[1]
    try:
        pool = list(reader(language, level))
    except Exception:  # noqa: BLE001 - not cached: the item is decided alone (its bucket and the floor) until it reads
        _log.warning("content access: the Reading pool could not be read", exc_info=True)
        return []
    with _lock:
        _pool_cache[cache_key] = (now + POOL_CACHE_SECONDS, pool)
    return pool


def clear_caches() -> None:
    global _overrides_cache
    with _lock:
        _overrides_cache = None
        _pool_cache.clear()


def decide(item: Item, *, now: datetime | None = None) -> Decision:
    """The tier of one item now, with the rule that decided it."""
    if item.kind not in KINDS:
        raise ValueError(f"Unknown content kind {item.kind!r}")
    if item.kind == "media":
        return Decision("free", "viewing")  # watching is never gated (III.F.3.a)
    forced = overrides().get(item.key)
    if forced is not None:
        return Decision(forced, "override")
    if item.kind in SET_KINDS:
        return set_tier(item.position, free_items=policies.value("access.set_free_items"))
    # reading
    pool = _reading_pool(item.language, item.level)
    ids = {str(item_id) for item_id, _published in pool}
    if item.id not in ids:
        # Not in the pool this worker read (published a moment ago): decided on its own bucket until the pool refreshes.
        pool = [*pool, (item.id, None)]
    free, rotation = reading_free_ids(pool, free_percent=policies.value("access.reading_free_percent"),
                                      rotation_per_week=policies.value("access.reading_rotation_per_week"),
                                      week=iso_week(now or _runtime.clock()))
    if item.id in free:
        in_bucket = bucket(item.id) < split_share(policies.value("access.reading_free_percent")) * 100
        return Decision("free", "bucket" if in_bucket else "floor")
    if item.id in rotation:
        return Decision("free", "rotation", rotation=True)
    return Decision("plus", "rule")


def access_tier(item: Item, *, now: datetime | None = None) -> str:
    """`free`, `plus` or `pro`: what plan a learner needs for this item."""
    return decide(item, now=now).tier


def reading_item(article: Mapping[str, Any]) -> Item:
    return Item("reading", str(article.get("id") or ""), language=str(article.get("language") or ""),
                level=str(article.get("level") or ""))


# --- the learner ---------------------------------------------------------------------------------------------------

def _user(user_key: str | None) -> str:
    if user_key is not None:
        return user_key
    from writing_coach.core.request_context import current_user_key

    return current_user_key()


def learner_tier(user_key: str | None = None) -> str | None:
    """The tier the learner's effective plan gives (a trial or an administrator's grant counts); None on a server with no
    plan system. 503 `quota_unavailable` when the plan cannot be read (fail closed)."""
    from writing_coach.product import plan_features

    plan = plan_features._plan(_user(user_key))
    if plan is None:
        return None
    if plan.id in RANK:
        return plan.id
    return TIERS[max(0, min(len(TIERS) - 1, int(getattr(plan, "rank", 0))))]


def can_access(user_key: str | None, item: Item, *, now: datetime | None = None) -> bool:
    """Whether this learner's plan reaches the item's tier. Raises 503 when the plan cannot be read."""
    tier = access_tier(item, now=now)
    if tier == "free":
        return True
    have = learner_tier(user_key)
    return have is None or RANK[have] >= RANK[tier]


def _trial(user_key: str) -> bool | None:
    reader = _runtime.trial_available
    if reader is None:
        return None
    try:
        answer = reader(user_key)
    except Exception:  # noqa: BLE001 - the trial read never turns a refusal into an error
        _log.warning("content access: the trial read failed", exc_info=True)
        return None
    return None if answer is None else bool(answer)


def learner_access(user_key: str | None = None) -> dict[str, Any]:
    """What the learner UI needs to draw badges and locks (MV2-3), read with the commerce state: whether enforcement is
    on, the tier the learner's effective plan gives, and whether the trial may still be started (None: not known). A
    plan that cannot be read is `tier: None`, which the client never reads as locked - no upgrade prompt over an
    outage; the routes still fail closed on their own."""
    user = _user(user_key)
    try:
        tier = learner_tier(user)
    except Exception:  # noqa: BLE001 - a read for drawing; the gated routes refuse on their own
        tier = None
    return {"enforced": enforced(), "tier": tier, "trial_available": _trial(user)}


def plan_required(*, user_key: str, kind: str, item_id: str, required_tier: str, plan: str | None,
                  preview: Mapping[str, Any] | None = None, tool: str | None = None) -> Exception:
    """The 403 `plan_required` refusal, in the contract's error envelope."""
    context: dict[str, Any] = {
        "required_tier": required_tier, "kind": kind, "item_id": item_id,
        # D-248 §6 names the same three values so; both are carried.
        "content_kind": kind, "content_id": item_id, "required_plan": required_tier,
        "plan": plan, "upgrade": UPGRADE_HREF, "trial_available": _trial(user_key), "preview": dict(preview or {}),
    }
    if tool:
        context["tool"] = tool
    return orena_http_error(403, "plan_required", "This is part of a paid plan.", retryable=False, context=context)


def require(item: Item, *, user_key: str | None = None, preview: Mapping[str, Any] | None = None,
            now: datetime | None = None) -> Decision:
    """The item's decision when the learner may have it; 403 `plan_required` when not (only while enforcement is on);
    503 when the plan cannot be read."""
    decision = decide(item, now=now)
    if decision.tier == "free" or not enforced():
        return decision
    user = _user(user_key)
    have = learner_tier(user)
    if have is None or RANK[have] >= RANK[decision.tier]:
        return decision
    record_event("locked_view", item.kind, user_key=user)
    raise plan_required(user_key=user, kind=item.kind, item_id=item.id, required_tier=decision.tier, plan=have,
                        preview=preview)


# --- Reading -------------------------------------------------------------------------------------------------------

def first_paragraph(body: str) -> str:
    text = str(body or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(parts) <= 1:
        parts = [part.strip() for part in text.splitlines() if part.strip()]
    return parts[0] if parts else ""


def reading_preview(article: Mapping[str, Any]) -> dict[str, Any]:
    """What a locked article still shows everyone (D-248 §4): its title, its cover and its first paragraph."""
    return {
        "title": article.get("title") or "",
        "image": article.get("image"),
        "first_paragraph": first_paragraph(str(article.get("body") or "")),
        "language": article.get("language") or "",
        "level": article.get("level") or "",
        "topic": article.get("topic") or "",
        "reading_time_seconds": article.get("reading_time_seconds"),
        "provenance": article.get("provenance"),
    }


def require_reading(article: Mapping[str, Any], *, user_key: str | None = None) -> Decision:
    return require(reading_item(article), user_key=user_key, preview=reading_preview(article))


def cache_control(decision: Decision, public_value: str) -> dict[str, str]:
    """The cache headers for an article body: never in a shared cache (D-248 §6, plan F6). Every body is private,
    whatever its tier now, because any tier can change (the weekly rotation, an override, a policy edit) and a
    shared copy would outlive that change (review of #466). `decision` and `public_value` are kept for the caller's
    shape; the ETag still revalidates the body cheaply."""
    return {"Cache-Control": "private, max-age=60", "Vary": "Cookie"}


def reading_card_access(items: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """The `access` block of each card: `{tier, rotation}`. The same for every learner (so the list stays cacheable);
    the client compares it with the plan it already reads, it never computes a tier."""
    out = []
    for item in items:
        try:
            decision = decide(reading_item(item), now=now)
            access = {"tier": decision.tier, "rotation": decision.rotation}
        except Exception:  # noqa: BLE001 - a card is never lost to the access read; its detail read decides
            _log.warning("content access: a card's tier could not be read", exc_info=True)
            access = {"tier": None, "rotation": False}
        out.append({**item, "access": access})
    return out


# --- Media tools ---------------------------------------------------------------------------------------------------

def _local_week_key(now: datetime) -> str:
    """The Monday of the learner's current local week (the zone their requests send, else UTC), as the quota window
    is cut, so one video counts once in each of the meter's windows."""
    from writing_coach.product import quota

    zone_name = quota.current_facts().timezone or "UTC"
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    local: date = now.astimezone(zone).date()
    return (local - timedelta(days=local.weekday())).isoformat()


def _count_video(media_id: str) -> None:
    """Count one video in this week's `media.tools_weekly` window, once: a second tool use on the same video in the
    same week is already admitted. 429 `quota_exhausted` past the plan's videos a week; nothing when the meter is not
    enforced (the quota switch)."""
    from fastapi import HTTPException

    from writing_coach.product import quota

    week = _local_week_key(_runtime.clock())
    digest = hashlib.sha256(f"media-tools|{media_id}|{week}".encode()).hexdigest()
    try:
        ticket = quota.begin(MEDIA_TOOLS_METER, units=1, request_digest=digest,
                             idempotency_key=f"media-tools:{media_id}:{week}")
    except HTTPException as refused:
        detail = refused.detail if isinstance(refused.detail, Mapping) else {}
        if refused.status_code == 409 and detail.get("category") in ("operation_finished", "operation_in_progress"):
            return  # this video was already counted this week
        raise
    ticket.dispatch("media-tools")
    ticket.settle(1, "media-tools")


def media_id_of(content_id: str | None) -> str | None:
    """The media id of an Agent Contract Listening content id (`media:<id>`, §6.1), else None."""
    text = str(content_id or "").strip()
    if not text.startswith("media:"):
        return None
    media_id = text[len("media:"):].strip()
    return media_id if _ITEM_ID.match(media_id) else None


def require_media_tool(tool: str, media_id: str, *, user_key: str | None = None) -> None:
    """Orena's learning tool `tool` around video `media_id`. Never called for watching: the player and the channel's
    captions are not a tool. Free tools pass (tap-to-look-up is counted on the weekly meter for a plan without the full
    tools); a Plus tool is 403 `plan_required` for Free. Only while enforcement is on."""
    if tool not in MEDIA_TOOLS:
        raise ValueError(f"Unknown media tool {tool!r}")
    if not enforced():
        return
    user = _user(user_key)
    have = learner_tier(user)
    if have is None or RANK[have] >= RANK["plus"]:
        return  # the full tools: nothing to count, nothing to refuse
    if media_id and overrides().get(f"media:{media_id}") == "free":
        return  # an editor made this video's tools free
    required = MEDIA_TOOLS[tool]
    if required == "free":
        if media_id:  # a look-up that names no video cannot be counted against one
            _count_video(media_id)
        return
    record_event("locked_view", "media_tool", user_key=user)
    raise plan_required(user_key=user, kind="media_tool", item_id=media_id, required_tier=required, plan=have,
                        tool=tool)


def media_tools(media_id: str, *, user_key: str | None = None) -> dict[str, Any]:
    """The `access` block of a media payload: what each tool needs and whether this learner has it. Never about the
    player (always available)."""
    full = not enforced() or overrides().get(f"media:{media_id}") == "free"
    if not full:
        have = learner_tier(_user(user_key))
        full = have is None or RANK[have] >= RANK["plus"]
    return {
        "viewing": "free",
        "tools": {tool: {"tier": tier, "locked": not full and tier != "free"} for tool, tier in MEDIA_TOOLS.items()},
        "lookup_metered": not full,
    }


def gate_media_payload(payload: dict[str, Any], media_id: str, *, user_key: str | None = None) -> dict[str, Any]:
    """A media lesson payload for this learner: everything a player and the channel's own captions need, always; Orena's
    bilingual translation only for a plan with the full tools. While enforcement is off the payload is unchanged."""
    if not enforced():
        return payload
    access = media_tools(media_id, user_key=user_key)
    payload = {**payload, "access": access}
    if access["tools"]["translation"]["locked"]:
        payload.pop("translations", None)
        translation = dict(payload.get("translation") or {})
        translation["locked"] = True
        payload["translation"] = translation
    return payload


# --- analytics -----------------------------------------------------------------------------------------------------

def record_event(event: str, detail: str = "", *, user_key: str | None = None) -> bool:
    """Count one access event in the usage counter (`access.<event>:<detail>`). The detail is a short token (a content
    kind, a sheet source) - never learner content. A failure is logged and never reaches the learner."""
    if event not in EVENTS:
        raise ValueError(f"Unknown access event {event!r}")
    token = str(detail or "").strip().casefold()
    if token and not _DETAIL.match(token):
        raise ValueError("The event detail must be a short token.")
    recorder = _runtime.record_usage
    if recorder is None:
        return False
    try:
        recorder(user_key=_user(user_key), feature=f"access.{event}:{token}" if token else f"access.{event}", amount=1)
    except Exception:  # noqa: BLE001 - analytics never cost a learner a request
        _log.warning("content access: an event could not be recorded", exc_info=True)
        return False
    return True


def trial_started(user_key: str, source: str = "") -> bool:
    """Billing's seam: call when a trial grant is made, so `trial_start` is counted with the other access events."""
    return record_event("trial_start", source, user_key=user_key)
