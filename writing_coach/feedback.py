"""Learner feedback: what a learner sends from the Feedback screen, and what Platform Admin reads (human, 2026-10-09,
D-156).

A review is a rating (1-5 stars), any of the screen's areas, and up to TEXT_LIMIT characters of text. It is stored as
an `audit_logs` row (action `learner.feedback`, linked to the account) - the existing table, no new schema - and read
back for the learner's own history and for Platform Admin (totals, average, by stars, by area, the reviews themselves).
A learner can send at most DAILY_LIMIT reviews a day.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, Protocol

FEEDBACK_ACTION = "learner.feedback"
AREAS: tuple[str, ...] = ("listening", "speaking", "reading", "writing", "vocabulary", "orena", "bugs")
TEXT_LIMIT = 600
DAILY_LIMIT = 10
MAX_PAGE = 100

# Retention (human decision 2026-10-09, D-159): a review is deleted with its account, and every review after 24 months.
# The periodic sweep (feedback_retention.py) is a destructive lifecycle job: it runs only once its switch is on.
FEEDBACK_RETENTION_DAYS = 730
RETENTION_SWITCH = "FEEDBACK_RETENTION_SWEEP"
_ON = frozenset({"1", "true", "on", "yes"})
_OFF = frozenset({"", "0", "false", "off", "no"})


def retention_enabled(env: Mapping[str, str]) -> bool:
    value = str(env.get(RETENTION_SWITCH, "")).strip().casefold()
    if value in _ON:
        return True
    if value in _OFF:
        return False
    raise ValueError(f"{RETENTION_SWITCH} must be one of {sorted(_ON | _OFF - {''})}")


class FeedbackInvalid(ValueError):
    """A review that cannot be stored (HTTP 422)."""


class FeedbackStore(Protocol):
    def record_feedback(self, user_key: str, review: dict) -> dict: ...
    def count_feedback_since(self, user_key: str, since: datetime) -> int: ...
    def list_feedback(self, *, user_key: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]: ...
    def feedback_summary(self) -> dict: ...


def validate_review(body: object) -> dict:
    if not isinstance(body, Mapping):
        raise FeedbackInvalid("The review must be an object.")
    stars = body.get("stars")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        raise FeedbackInvalid("A rating of 1 to 5 stars is required.")
    areas = body.get("areas") or []
    if not isinstance(areas, list) or any(area not in AREAS for area in areas):
        raise FeedbackInvalid("Unknown area.")
    text = body.get("text") or ""
    if not isinstance(text, str):
        raise FeedbackInvalid("The text must be a string.")
    text = text.strip()
    if len(text) > TEXT_LIMIT:
        raise FeedbackInvalid(f"The text is longer than {TEXT_LIMIT} characters.")
    language = str(body.get("language") or "")[:8]
    interface = str(body.get("interface") or "")[:8]
    return {
        "stars": stars,
        "areas": [area for area in AREAS if area in areas],
        "text": text,
        "language": language,
        "interface": interface,
    }


def submit(store: FeedbackStore, user_key: str, body: object, *, now: datetime | None = None) -> dict:
    review = validate_review(body)
    moment = now or datetime.now(UTC)
    if store.count_feedback_since(user_key, moment - timedelta(days=1)) >= DAILY_LIMIT:
        raise OverflowError("Too many reviews today.")
    return store.record_feedback(user_key, review)


def page_bounds(limit: object, offset: object) -> tuple[int, int]:
    try:
        bounded = max(1, min(int(limit or 50), MAX_PAGE))
    except (TypeError, ValueError):
        bounded = 50
    try:
        start = max(0, int(offset or 0))
    except (TypeError, ValueError):
        start = 0
    return bounded, start


def summarize(rows: list[dict]) -> dict:
    """Totals over stored reviews: count, average, by stars, by area, the last seven days."""
    total = len(rows)
    by_stars = {str(n): 0 for n in range(1, 6)}
    by_area = {area: 0 for area in AREAS}
    recent = 0
    week_ago = datetime.now(UTC) - timedelta(days=7)
    star_sum = 0
    for row in rows:
        stars = int(row.get("stars") or 0)
        if 1 <= stars <= 5:
            by_stars[str(stars)] += 1
            star_sum += stars
        for area in row.get("areas") or []:
            if area in by_area:
                by_area[area] += 1
        created = row.get("created_at")
        if isinstance(created, datetime) and created >= week_ago:
            recent += 1
    return {
        "total": total,
        "average": round(star_sum / total, 2) if total else None,
        "by_stars": by_stars,
        "by_area": by_area,
        "last_7_days": recent,
    }
