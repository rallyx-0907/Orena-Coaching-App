"""A real streak and the week's active days, derived from server records (D4 I14; D-104 H-5, D-103.4).

No table: a streak is a read over records that already exist. A DAY is a calendar day in the learner's
own timezone (a validated per-request `tz`, never stored, and never the server's clock for the boundary)
on which at least one meaningful, timestamped, server-written learning record exists. A page visit is not
one. The week is the ISO week, Monday first.

Each skill contributes one activity SOURCE: the instants of its completed records. A source counts only
while its record is completed, server-written and keeps a per-event timestamp that survives, because a
"last updated" time can be overwritten and would let a later write erase a day and break a streak
falsely. At D4 the sources are essay submissions (each revision is its own record, so a revision on
another day is another active day), speaking attempts and Reading attempts. Dictation, Shadowing and
vocabulary review keep only a last-update time today, so they are NOT counted until their domain records
keep an event time - `PENDING_SOURCES` says which and why, and a surface may say so.

Unmeasured is absent, never zero: nothing here reports minutes, a daily goal, achievements, trends, a
skill percentage or a level. The pure functions take instants and a timezone; the route reads the records.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime, timedelta, UTC
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Query

from writing_coach import account_settings
from writing_coach.core.errors import orena_http_error

ACTIVITY_SOURCES = ("essays", "speaking_attempts", "reading_attempts")

# Skills whose records cannot yet prove a PAST day, and what each needs to start counting.
PENDING_SOURCES = {
    "listening_dictation": "no_per_event_timestamp",
    "shadowing": "no_per_event_timestamp",
    "vocabulary_review": "no_per_event_timestamp",
    "grammar_completion": "no_producer_yet",
    "reading_responses": "no_producer_yet",
}

MAX_WINDOW_DAYS = 90
DEFAULT_WINDOW_DAYS = 28

router = APIRouter()
_provider: Callable[[datetime], Mapping[str, Iterable[datetime]]] | None = None


def configure_learner_activity(provider: Callable[[datetime], Mapping[str, Iterable[datetime]]] | None) -> None:
    """`provider(since)` -> {source name: instants} for the request's account and learning language."""
    global _provider
    _provider = provider


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError, OSError):
        raise ValueError(name) from None


def active_days(instants: Iterable[datetime], zone: ZoneInfo) -> set[date]:
    """The local calendar days on which at least one instant falls."""
    days: set[date] = set()
    for instant in instants:
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        days.add(instant.astimezone(zone).date())
    return days


def streak_length(days: set[date], today: date) -> int:
    """Consecutive active days ending today, or yesterday when today has none yet."""
    cursor = today if today in days else today - timedelta(days=1)
    length = 0
    while cursor in days:
        length += 1
        cursor -= timedelta(days=1)
    return length


def week_of(today: date) -> list[date]:
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=offset) for offset in range(7)]


def compute_activity(
    sources: Mapping[str, Iterable[datetime]],
    *,
    now: datetime,
    tz: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    weekly_goal_days: int | None = None,
) -> dict[str, Any]:
    """The streak, this week and the recent active days, from the instants of the counted sources."""
    zone = resolve_timezone(tz)
    today = now.astimezone(zone).date()
    counted = {name: list(sources.get(name, ())) for name in ACTIVITY_SOURCES}
    days = active_days([instant for instants in counted.values() for instant in instants], zone)
    week = week_of(today)
    recent = sorted(day for day in days if today - timedelta(days=window_days - 1) <= day <= today)
    return {
        "timezone": tz,
        "today": today.isoformat(),
        "streak": {"days": streak_length(days, today), "active_today": today in days},
        "week": {
            "start": week[0].isoformat(),
            "days": [{"date": day.isoformat(), "active": day in days, "future": day > today} for day in week],
            "done_days": sum(1 for day in week if day in days),
            # The persisted target, or absent: an unset goal is not drawn as a number.
            **({"goal_days": weekly_goal_days} if weekly_goal_days else {}),
        },
        "recent_days": [day.isoformat() for day in recent],
        "sources": {"counted": list(ACTIVITY_SOURCES), "pending": dict(PENDING_SOURCES)},
    }


@router.get("/api/learner-activity")
def learner_activity(
    tz: str = Query("UTC", max_length=64),
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=7, le=MAX_WINDOW_DAYS),
) -> dict[str, Any]:
    if _provider is None:
        raise orena_http_error(503, "learner_activity_unavailable", "Activity is not available on this deployment.")
    try:
        resolve_timezone(tz)
    except ValueError:
        raise orena_http_error(422, "timezone_invalid", "That is not a timezone this server knows.") from None
    now = datetime.now(UTC)
    # Wide enough for the streak to run on: a streak can be longer than the window the caller draws.
    since = now - timedelta(days=366)
    try:
        instants = _provider(since)
    except RuntimeError as exc:
        raise orena_http_error(503, "learner_activity_unavailable", str(exc)) from exc
    settings = account_settings.read_account_settings() or {}
    return compute_activity(
        instants, now=now, tz=tz, window_days=days, weekly_goal_days=settings.get("weekly_goal_days")
    )
