"""The free-tier cost flag (D-219, PROPOSED): which spend is real money and which is free-plan value.

Owner decision, 2026-10-16: an administrator can say, per provider, that the account is on a free plan
(`cost.free_tier.<provider>`, an ordinary policy, `writing_coach/policies.py`). Every cost event is STAMPED with the
tier in force when it is recorded - `free_tier: true|false` plus the provider - and a later change of the flag never
rewrites a past event. When the account moves to a paid plan the administrator turns the flag off; events from then on
are real spend, and the free-tier events before it stay free-tier value.

What the flag does NOT do: it never zeroes a cost or a cap. An amount is always computed at the public price (the
"list price"), so a spend cap keeps protecting the provider's quota whatever the tier. The flag only decides which
bucket a computed amount is reported in:

* `real`     - the event was stamped `free_tier: false`; this is what is actually spent;
* `free`     - stamped `free_tier: true`; the estimated value of what the free plan covered;
* `unknown`  - no stamp (an event written before D-219) AND no way to tell from the flag's history (D-220, PROPOSED:
               an unstamped event is otherwise placed by the history, see `FlagTimeline.tier_at`). Reported apart,
               never added to real spend or to free value.

Where a stamp lives: the media spend ledger (a JSON file) and the `ai.operation` telemetry payload (JSON) carry it.
`ai_cost_records` has no free-form column and its schema is a human gate, so its tier is DERIVED from the flag's
change history in the audit log (`FlagTimeline`), at the instant of each record.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from writing_coach import policies

# The providers that have a flag. An unknown provider has none: its spend is real.
_FLAG_KEYS: dict[str, str] = {
    "groq": "cost.free_tier.groq",
    "supadata": "cost.free_tier.supadata",
    "gemini": "cost.free_tier.gemini",
}
PROVIDERS: tuple[str, ...] = tuple(_FLAG_KEYS)
KEY_PREFIX = "cost.free_tier."

TIER_REAL = "real"
TIER_FREE = "free"
TIER_UNKNOWN = "unknown"


def _provider(provider: object) -> str:
    return str(provider or "").strip().casefold()


def flag_key(provider: object) -> str | None:
    return _FLAG_KEYS.get(_provider(provider))


def is_free_tier(provider: object, env: Mapping[str, str] | None = None) -> bool:
    """Whether this provider's flag is on now. A provider with no flag is not on a free plan."""
    key = flag_key(provider)
    return bool(policies.value(key, env=env)) if key else False


def stamp(provider: object, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """What a cost event records about its tier, at the moment it is recorded."""
    return {"provider": _provider(provider)[:40], "free_tier": is_free_tier(provider, env)}


def _event_time(event: Mapping[str, Any]) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(event.get("at") or ""))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def tier_of(event: Mapping[str, Any], tier_at: Callable[[object, datetime], str] | None = None) -> str:
    """`free`, `real` or `unknown` for one stamped (or unstamped) event.

    A stamp always wins. An event with no stamp (written before D-219) is `unknown` unless `tier_at` is given
    (D-220, PROPOSED): then it takes the tier the flag's history gives for its provider at its time, which is `real`
    for a provider whose flag was never on (or that has no flag) and `free` for one whose flag was always on."""
    flag = event.get("free_tier")
    if flag is True:
        return TIER_FREE
    if flag is False:
        return TIER_REAL
    when = _event_time(event)
    if tier_at is None or when is None:
        return TIER_UNKNOWN
    return tier_at(event.get("provider"), when)


def split(events: list[Mapping[str, Any]], amount: str = "usd",
          tier_at: Callable[[object, datetime], str] | None = None) -> dict[str, float]:
    """Sum `amount` of events into the three buckets."""
    totals = {TIER_REAL: 0.0, TIER_FREE: 0.0, TIER_UNKNOWN: 0.0}
    for event in events:
        totals[tier_of(event, tier_at)] += float(event.get(amount) or 0)
    return {name: round(value, 8) for name, value in totals.items()}


def reclassify_unstamped(rows: list[dict[str, Any]], pieces: list[tuple[datetime, list[dict[str, Any]]]],
                         tier_at: Callable[[object, datetime], str], *, last_unknown: bool = False) -> list[dict[str, Any]]:
    """Move the unstamped amount of report rows out of `usd_unknown` by the flag's history (D-220, PROPOSED).

    `rows` are `ai_cost_rows` rows (by day, capability, provider, model); `pieces` are `(start, unstamped rows)` for each
    stretch of time between two flag changes, the rows having the same keys and a `usd` that is the unstamped amount.
    Each piece is classified by `tier_at(provider, start)`. Nothing is added or removed from `usd`, so no cap moves."""
    keyed = {(r["day"], r["capability"], r["provider"], r["model"]): r for r in rows}
    names = {TIER_REAL: "usd_real", TIER_FREE: "usd_free", TIER_UNKNOWN: "usd_unknown"}
    for index, (start, unstamped) in enumerate(pieces):
        ambiguous = last_unknown and index == len(pieces) - 1
        for item in unstamped:
            target = keyed.get((item["day"], item["capability"], item["provider"], item["model"]))
            if target is None:
                continue
            amount = float(item.get("usd") or 0)
            tier = TIER_UNKNOWN if ambiguous else tier_at(item["provider"], start)
            if tier == TIER_UNKNOWN:
                continue
            target["usd_unknown"] = round(target["usd_unknown"] - amount, 8)
            target[names[tier]] = round(target[names[tier]] + amount, 8)
    return rows


# --- the flag's history, for a record that carries no stamp -------------------------------------------------------

class FlagTimeline:
    """Whether each provider's flag was on at a given instant, from the audit rows of policy saves.

    The state before the first recorded change of a provider is that change's `from`; a provider never changed has
    always had its present value. A flag pinned by the environment has no history to consult: it is its present value
    throughout."""

    def __init__(self, current: Mapping[str, bool], changes: list[tuple[datetime, str, bool, bool]],
                 pinned: frozenset[str] = frozenset(), stored: frozenset[str] = frozenset()) -> None:
        # changes: (when, provider, from, to), oldest first
        self._current = dict(current)
        self._pinned = pinned
        self._stored = stored
        self._changes: dict[str, list[tuple[datetime, bool, bool]]] = {}
        for when, provider, before, after in sorted(changes, key=lambda item: item[0]):
            if provider in pinned or provider not in PROVIDERS:
                continue
            self._changes.setdefault(provider, []).append((when, before, after))

    def is_free(self, provider: object, at: datetime) -> bool:
        name = _provider(provider)
        if name not in PROVIDERS:
            return False
        history = self._changes.get(name)
        if not history:
            return bool(self._current.get(name, False))
        state = history[0][1]
        for when, _before, after in history:
            if when <= at:
                state = after
            else:
                break
        return state

    def tier_at(self, provider: object, at: datetime) -> str:
        """`free`, `real` or `unknown` for a record without a stamp. `unknown` when the flag is ON by an administrator's
        stored value yet no retained audit row explains it: the history is missing, and calling it free could hide real
        spend. A flag that is OFF, or that is its untouched default, needs no history."""
        name = _provider(provider)
        if not name:
            return TIER_UNKNOWN  # an event that names no provider cannot be placed on any plan
        if name in PROVIDERS and name not in self._changes and name in self._stored and self._current.get(name) and name not in self._pinned:
            return TIER_UNKNOWN
        return TIER_FREE if self.is_free(provider, at) else TIER_REAL

    def boundaries(self, since: datetime, until: datetime) -> list[datetime]:
        """The instants inside (since, until) at which some flag changed, oldest first."""
        points = {when for history in self._changes.values() for when, _b, _a in history if since < when < until}
        return sorted(points)


def timeline_from_audit(rows: list[Mapping[str, Any]], *, current: Mapping[str, bool] | None = None,
                        pinned: frozenset[str] = frozenset(), stored: frozenset[str] = frozenset()) -> FlagTimeline:
    """`rows` are `platform.policies.update` audit rows: `{"created_at": datetime, "payload": {"changes": {...}}}`."""
    present = dict(current) if current is not None else {name: is_free_tier(name) for name in PROVIDERS}
    changes: list[tuple[datetime, str, bool, bool]] = []
    for row in rows:
        payload = row.get("payload")
        edits = payload.get("changes") if isinstance(payload, Mapping) else None
        when = row.get("created_at")
        if not isinstance(edits, Mapping) or not isinstance(when, datetime):
            continue
        when = when if when.tzinfo else when.replace(tzinfo=UTC)
        for key, edit in edits.items():
            if not str(key).startswith(KEY_PREFIX) or not isinstance(edit, Mapping):
                continue
            provider = str(key)[len(KEY_PREFIX):]
            before, after = edit.get("from"), edit.get("to")
            if isinstance(before, bool) and isinstance(after, bool):
                changes.append((when, provider, before, after))
    return FlagTimeline(present, changes, pinned, stored)
