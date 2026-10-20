"""The weekly recurring-mistake report (Monetisation v2, MONETIZATION_V2_SPEC §3): what the learner's own records show
this ISO week, in the learner's time zone, against the four weeks before.

- **writing**: per error category of the stored reviews, `this_week` and `before` counts and a status - `recurring`
  (this week and before), `new` (at least twice this week, never before), `improving` (at least twice before, not this
  week) - with the learner's latest own words, the fix and the rule. A single mistake is not a pattern.
- **speaking**: words the pronunciation provider flagged, with the same counts and statuses (over the newest
  attempts the route reads, `SPEAKING_ATTEMPTS_READ`).
- **practised**: the reviews and attempts of this week.

Counts only, from the same rows Orena Memory reads (`PackSources`); nothing is estimated or asked of a model, so it
costs nothing. A source that cannot be read is `None` - unknown, never "no mistakes".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from writing_coach.agent.labels import category_label
from writing_coach.agent.skill_tools import flagged

WEEKS_BEFORE = 4
RECURRING = 2
MAX_ITEMS = 5
FRAGMENT_CHARS = 120


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"unknown time zone {tz!r}") from error


def known_zone(tz: str) -> bool:
    try:
        _zone(tz)
    except ValueError:
        return False
    return True


def _instant(value: Any) -> datetime | None:
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _status(this_week: int, before: int) -> str | None:
    if this_week and before:
        return "recurring"
    if this_week >= RECURRING:
        return "new"
    if not this_week and before >= RECURRING:
        return "improving"
    return None


def _clip(value: Any) -> str:
    return " ".join(str(value or "").split())[:FRAGMENT_CHARS]


class _Window:
    def __init__(self, now: datetime, zone: ZoneInfo) -> None:
        local = now.astimezone(zone)
        monday = (local - timedelta(days=local.weekday())).date()
        self.start = datetime(monday.year, monday.month, monday.day, tzinfo=zone)
        self.end = self.start + timedelta(days=7)
        self.earliest = self.start - timedelta(weeks=WEEKS_BEFORE)
        year, week, _ = monday.isocalendar()
        self.week = f"{year}-W{week:02d}"

    def place(self, value: Any) -> str | None:
        moment = _instant(value)
        if moment is None or not self.earliest <= moment < self.end:
            return None
        return "this_week" if moment >= self.start else "before"


def _ranked(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (-item["this_week"], -(item["this_week"] + item["before"])))[:MAX_ITEMS]


def _writing(rows: Sequence[Mapping[str, Any]], window: _Window, interface: str) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = {}
    latest: dict[str, tuple[datetime, Mapping[str, Any]]] = {}
    for row in rows:
        category, where = row.get("category"), window.place(row.get("created_at"))
        if not category or where is None:
            continue
        counts.setdefault(category, {"this_week": 0, "before": 0})[where] += 1
        moment = _instant(row.get("created_at"))
        if category not in latest or moment >= latest[category][0]:
            latest[category] = (moment, row)
    out = []
    for category, seen in counts.items():
        status = _status(seen["this_week"], seen["before"])
        if status is None:
            continue
        row = latest[category][1]
        out.append({"category": category, "label": category_label(category, interface), **seen, "status": status,
                    "example": {"fragment": _clip(row.get("fragment")), "suggestion": _clip(row.get("suggestion")),
                                "rule": _clip(row.get("mini_rule_vi"))}})  # fmt: skip
    return _ranked(out)


def _speaking(attempts: Sequence[Mapping[str, Any]], window: _Window) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = {}
    for attempt in attempts:
        where = window.place(attempt.get("created_at"))
        evidence = attempt.get("evidence") if isinstance(attempt.get("evidence"), Mapping) else {}
        pronunciation = evidence.get("pronunciation") if isinstance(evidence.get("pronunciation"), Mapping) else {}
        if where is None:
            continue
        for word in {str(w["word"]) for w in pronunciation.get("words") or ()
                     if isinstance(w, Mapping) and w.get("word") and flagged(w)}:  # fmt: skip
            counts.setdefault(word, {"this_week": 0, "before": 0})[where] += 1
    return _ranked({"word": word, **seen, "status": status} for word, seen in counts.items()
                   if (status := _status(seen["this_week"], seen["before"])) is not None)  # fmt: skip


def weekly_report(*, writing: Sequence[Mapping[str, Any]] | None, speaking: Sequence[Mapping[str, Any]] | None,
                  now: datetime, tz: str, interface: str) -> dict[str, Any]:  # fmt: skip
    window = _Window(now, _zone(tz))
    practised = None
    if writing is not None or speaking is not None:
        practised = {
            "writing_reviews": None if writing is None else len(
                {row.get("essay_id") for row in writing if window.place(row.get("created_at")) == "this_week"}),
            "speaking_attempts": None if speaking is None else sum(
                1 for row in speaking if window.place(row.get("created_at")) == "this_week"),
        }  # fmt: skip
    return {
        "week": window.week,
        "week_start": window.start.date().isoformat(),
        "time_zone": tz,
        "compared_with_weeks": WEEKS_BEFORE,
        "writing": None if writing is None else _writing(writing, window, interface),
        "speaking": None if speaking is None else _speaking(speaking, window),
        "practised": practised,
    }
