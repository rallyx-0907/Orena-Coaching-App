"""Pure aggregation rules behind the Platform Admin control center.

Everything here works on facts the repositories already read - timestamps,
identifiers, configuration and recorded operations - and returns aggregates.
Nothing here reads a database, and nothing invents a number: a metric that the
stored evidence cannot support comes back as an explicit `insufficient` state
rather than as a guess.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# Below this many eligible learners a return rate says more about chance than
# about the product, so none is reported. Showing "3 of 4" as 75% would be a
# claim the data cannot make.
MIN_RETENTION_SAMPLE = 20
RETENTION_OFFSETS = (1, 7, 30)
RETENTION_COHORT_DAYS = 90

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _utc(now: datetime | None) -> datetime:
    value = now or datetime.now(UTC)
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def day_keys(days: int, *, now: datetime | None = None) -> list[str]:
    """ISO dates of the last `days` UTC days, oldest first, ending today."""
    today = _utc(now).date()
    count = max(1, int(days))
    return [(today - timedelta(days=offset)).isoformat() for offset in range(count - 1, -1, -1)]


def daily_series(counts: Mapping[str, int], days: int, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """A zero-filled daily series. A day with no rows is a real zero, not a gap."""
    return [{"date": key, "count": int(counts.get(key, 0) or 0)} for key in day_keys(days, now=now)]


def mask_email(email: str) -> str:
    """Enough of an address to recognise it, not enough to copy it off a screen."""
    value = str(email or "").strip()
    if not value:
        return ""
    local, at, domain = value.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}•••{at}{domain}" if at else f"{visible}•••"


def activity_days(rows: Iterable[tuple[str, Any]]) -> tuple[dict[str, date], dict[str, set[date]]]:
    """First activity day and the set of active days, per learner.

    `rows` are `(learner_id, day)` pairs where day is a date or an ISO string,
    as the repository's day-grouped activity read returns them.
    """
    first: dict[str, date] = {}
    active: dict[str, set[date]] = {}
    for learner, raw_day in rows:
        day = raw_day if isinstance(raw_day, date) and not isinstance(raw_day, datetime) else _as_date(raw_day)
        if day is None or not learner:
            continue
        key = str(learner)
        active.setdefault(key, set()).add(day)
        if key not in first or day < first[key]:
            first[key] = day
    return first, active


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return _utc(value).date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def learner_segments(
    first_active: Mapping[str, datetime],
    active_in_window: set[str],
    window_start: datetime,
) -> dict[str, int]:
    """Active learners split by whether their first-ever activity is in the window."""
    start = _utc(window_start)
    new = 0
    for learner in active_in_window:
        first = first_active.get(learner)
        if first is not None and _utc(first) >= start:
            new += 1
    return {"active": len(active_in_window), "new": new, "returning": len(active_in_window) - new}


def retention_windows(
    first_day: Mapping[str, date],
    active_days: Mapping[str, set[date]],
    *,
    today: date,
    offsets: Iterable[int] = RETENTION_OFFSETS,
    cohort_days: int = RETENTION_COHORT_DAYS,
    min_sample: int = MIN_RETENTION_SAMPLE,
) -> list[dict[str, Any]]:
    """N-day return for learners whose first activity is recent.

    A learner is eligible for the N-day window once N days have passed since
    their first activity, and counts as returned when they were active again on
    or after that day. Only learners who started within `cohort_days` are
    considered, so the figure describes the product as it is now.
    """
    cohort_floor = today - timedelta(days=int(cohort_days))
    result = []
    for offset in offsets:
        eligible = returned = 0
        for learner, first in first_day.items():
            if first < cohort_floor or first + timedelta(days=offset) > today:
                continue
            eligible += 1
            threshold = first + timedelta(days=offset)
            if any(day >= threshold for day in active_days.get(learner, ())):
                returned += 1
        ready = eligible >= max(1, int(min_sample))
        result.append({
            "days": int(offset),
            "eligible_learners": eligible,
            "returned_learners": returned,
            "state": "ready" if ready else "insufficient",
            "rate_percent": round(returned * 100 / eligible, 1) if ready else None,
            "minimum_sample": int(min_sample),
        })
    return result


def needs_attention(
    *,
    capabilities: Iterable[Mapping[str, Any]] | None,
    provider_state: Mapping[str, Mapping[str, Any]] | None,
    operations: Mapping[str, Any] | None,
    runtime_mode: str,
    import_failures: int = 0,
    transcript_missing: int = 0,
    content_waiting: int = 0,
    runtime: Mapping[str, Any] | None = None,
    legacy_route: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Only problems an operator can act on, most severe first.

    Configuration that learners do not route through yet (the capability
    runtime is still `legacy`) is not reported as a failure: an unconfigured
    capability matters once learners depend on it, and saying otherwise would
    fill the list with work that is not urgent.
    """
    items: list[dict[str, Any]] = []
    providers = provider_state or {}
    reported: set[str] = set()

    for capability in capabilities or []:
        if not isinstance(capability, Mapping):
            continue
        if not (capability.get("implemented") and capability.get("provider_backed") and capability.get("configurable")):
            continue
        key = str(capability.get("key") or "")
        config = capability.get("config") if isinstance(capability.get("config"), Mapping) else None
        if capability.get("explicit_config_exists") is not True or config is None:
            if runtime_mode == "capability":
                items.append({"kind": "capability_not_configured", "severity": "critical", "section": "ai", "subject": key})
                reported.add(key)
            continue
        if config.get("enabled") is False:
            continue
        provider = str(config.get("provider") or "")
        if not providers.get(provider, {}).get("configured"):
            items.append({"kind": "provider_unavailable", "severity": "critical", "section": "ai", "subject": key, "provider": provider})
            reported.add(key)

    for row in (operations or {}).get("by_capability") or []:
        if not isinstance(row, Mapping):
            continue
        key = str(row.get("capability") or "")
        if key in reported:
            continue
        state = row.get("health_state")
        if state == "provider_failure":
            items.append({"kind": "provider_failure", "severity": "critical", "section": "ai", "subject": key})
        elif state == "degraded":
            items.append({"kind": "capability_degraded", "severity": "warning", "section": "ai", "subject": key})

    for provider, state in providers.items():
        if isinstance(state, Mapping) and state.get("credential_unreadable"):
            items.append({"kind": "credential_unreadable", "severity": "warning", "section": "ai", "provider": provider})

    # In the legacy runtime every learner request uses the one saved selection,
    # and a saved provider that is not configured is replaced by the local
    # default without a word (ai/platform.py `active_selection`). That silent
    # substitution is exactly what an operator needs to hear about.
    route = legacy_route or {}
    if runtime_mode == "legacy" and route.get("source") == "saved" and route.get("provider_configured") is False:
        items.append({"kind": "legacy_route_fallback", "severity": "warning", "section": "ai",
                      "provider": str(route.get("provider") or "")})

    facts = runtime or {}
    if facts.get("persistence_backend") and facts.get("persistence_backend") != "postgresql":
        items.append({"kind": "persistence_not_authoritative", "severity": "critical", "section": "operations"})
    if facts.get("account_backbone") == "unavailable":
        items.append({"kind": "account_backbone_unavailable", "severity": "critical", "section": "operations"})
    # A missing index is simply a library nobody has imported into yet; an
    # index that exists but cannot be read is a library learners have lost.
    if facts.get("media_index_issue") in {"index_corrupt", "index_unreadable"}:
        items.append({"kind": "media_index_unreadable", "severity": "critical", "section": "operations"})
    if import_failures:
        items.append({"kind": "import_failed", "severity": "warning", "section": "imports", "count": int(import_failures)})
    if transcript_missing:
        items.append({"kind": "transcript_missing", "severity": "warning", "section": "content", "count": int(transcript_missing)})
    learner_failures = int(facts.get("learner_impact_failures") or 0)
    if learner_failures:
        items.append({"kind": "learner_impact_failures", "severity": "warning", "section": "operations", "count": learner_failures})
    if facts.get("reading_library") == "unavailable":
        items.append({"kind": "reading_library_unavailable", "severity": "warning", "section": "operations"})
    if facts.get("vocabulary") == "unavailable":
        items.append({"kind": "vocabulary_unavailable", "severity": "warning", "section": "operations"})
    if content_waiting:
        items.append({"kind": "content_waiting", "severity": "info", "section": "content", "count": int(content_waiting)})

    return sorted(items, key=lambda item: _SEVERITY_ORDER.get(item["severity"], 3))
