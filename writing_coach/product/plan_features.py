"""A plan feature that is on or off, not counted: voice chat with Orena (`orena.voice`).

Owner, 2026-10-19: voice chat with Orena is for Plus and Pro only; Free chats in text. Speaking practice is a different
feature and is not touched. The catalogue's `orena.voice` entitlement (Free off, Plus and Pro on by the code's defaults)
decides, read from the strict catalogue and the account's effective plan - a plan an administrator granted (D-154)
counts. It is a product rule, so it holds whether or not usage limits are enforced. A plan or catalogue that cannot be
read refuses (503 `quota_unavailable`, fail closed). A server with no plan system at all (no `plan_for`: tests, a bare
development server) has no plans to tell apart, and lets the feature through.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from writing_coach.core.errors import orena_http_error
from writing_coach.product import quota
from writing_coach.product.catalog import METERS, CatalogUnavailable, current_catalog

VOICE = "orena.voice"
# The voice seconds the server records per learner when a voice chunk is minted (agent/voice_session.py): the minutes
# used against the plan's daily `orena.voice` limit.
VOICE_USAGE = "agent.voice_seconds"

_daily_usage: Callable[[str, str], int] | None = None  # (user_key, feature) -> today's (UTC) total
_monthly_usage: Callable[[str, str], int] | None = None  # (user_key, feature) -> this UTC calendar month's total
_clock: Callable[[], datetime] = lambda: datetime.now(UTC)


def configure(*, daily_usage: Callable[[str, str], int] | None,
              monthly_usage: Callable[[str, str], int] | None = None,
              clock: Callable[[], datetime] | None = None) -> None:  # fmt: skip
    """app.py: the usage store's daily and monthly totals. None (a bare server, tests): voice minutes are not counted
    in that window. Which one is read is the `orena.voice` meter's window (code-owned, catalog.METERS)."""

    global _daily_usage, _monthly_usage, _clock
    _daily_usage = daily_usage
    _monthly_usage = monthly_usage
    _clock = clock or (lambda: datetime.now(UTC))


def _period_end(now: datetime, window: str | None) -> datetime:
    """When the window that holds `now` ends (UTC): the next midnight, or the first of next month."""

    if window == "month":
        return datetime(now.year + (now.month == 12), now.month % 12 + 1, 1, tzinfo=UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)


def _resets_at(now: datetime, window: str | None) -> str:
    return _period_end(now, window).isoformat().replace("+00:00", "Z")


def _usage_reader() -> Callable[[str, str], int] | None:
    """The total for the voice meter's window; None when that window is not counted here (never a day read as a
    month)."""

    return {"day": _daily_usage, "month": _monthly_usage}.get(METERS[VOICE].window)


def _plan(user_key: str):
    """The account's effective plan from the strict catalogue; None when this server has no plan system."""

    runtime = quota.runtime()
    if runtime.plan_for is None:
        return None
    try:
        plans, _revision = current_catalog(strict=True)
        plan = plans.get(runtime.plan_for(user_key, strict=True).id)
    except CatalogUnavailable as error:
        raise quota._unavailable("catalogue") from error
    except Exception as error:  # noqa: BLE001 - the subscription store or the plan read failed: fail closed
        raise quota._unavailable("subscription") from error
    if plan is None:
        raise quota._unavailable("catalogue")
    return plan


def require(user_key: str, feature: str) -> None:
    """403 `feature_not_in_plan` when the account's plan does not include `feature`; 503 when it cannot be read."""

    plan = _plan(user_key)
    if plan is None:
        return
    entitlement = plan.entitlement_map().get(feature)
    if entitlement is None or not entitlement.enabled:
        raise orena_http_error(403, "feature_not_in_plan", "This feature is not part of your plan.", retryable=False,
                               context={"feature": feature, "plan": plan.id, "upgrade": quota.UPGRADE_HREF})


def entitled(user_key: str, feature: str) -> bool | None:
    """Whether the account's plan includes `feature`; None when the plan cannot be read right now - not "no", so a
    paying learner is never shown an upgrade over a moment's outage (`require` still refuses it with a 503)."""

    from fastapi import HTTPException

    try:
        require(user_key, feature)
    except HTTPException as refused:
        return None if refused.status_code == 503 else False
    return True


def _voice_limit(plan) -> int | None:
    """The plan's voice seconds per window (a day or a month: the meter's). A stored limit under a minute is the on/off
    placeholder (1) an editor saved under D-236, before the limit counted seconds: it reads as the code's default, never
    as one second."""

    from writing_coach.product.catalog import PLANS

    limit = plan.entitlement_map()[VOICE].limit
    if limit is not None and limit < 60:
        default = PLANS.get(plan.id)
        limit = default.entitlement_map()[VOICE].limit if default is not None else None
    return limit


def _voice_used(user_key: str) -> int:
    read = _usage_reader()
    try:
        return int(read(user_key, VOICE_USAGE)) if read is not None else 0
    except Exception as error:  # noqa: BLE001 - the usage store is down: fail closed
        raise quota._unavailable("usage") from error


DAILY = "daily_seconds"  # the entitlement's parameter: the most of the window's voice seconds one UTC day may use


def _voice_daily_limit(plan) -> int | None:
    """The plan's daily sub-cap under a longer window (Hermes for the owner, 2026-10-21; COST_PRE402_403 §7), or None:
    none set, the window is already a day, or no daily total is counted here (a bare server)."""

    if METERS[VOICE].window == "day" or _daily_usage is None:
        return None
    value = (plan.entitlement_map()[VOICE].params or {}).get(DAILY)
    return int(value) if value else None


def _voice_used_today(user_key: str) -> int:
    try:
        return int(_daily_usage(user_key, VOICE_USAGE))
    except Exception as error:  # noqa: BLE001 - the usage store is down: fail closed
        raise quota._unavailable("usage") from error


def _voice_caps(user_key: str, plan) -> list[tuple[str, int, int]]:
    """Each cap that counts here, as (window, limit, used): the meter's window first, then the daily sub-cap."""

    caps = []
    limit = _voice_limit(plan)
    if limit is not None and _usage_reader() is not None:
        caps.append((METERS[VOICE].window, limit, _voice_used(user_key)))
    daily = _voice_daily_limit(plan)
    if daily is not None:
        caps.append(("day", daily, _voice_used_today(user_key)))
    return caps


def voice_seconds_left(user_key: str) -> int | None:
    """The voice seconds a session may still use now (at least 0): the smaller of what is left in the meter's window
    (today, or this month) and in today's sub-cap. None when nothing is capped (no plan system, no usage store, no
    limit). The voice service clamps every token it mints to it, so no session runs past either cap."""

    plan = _plan(user_key)
    if plan is None:
        return None
    caps = _voice_caps(user_key, plan)
    return max(0, min(limit - used for _window, limit, used in caps)) if caps else None


def require_voice_time(user_key: str) -> None:
    """The plan has voice (403 otherwise) and this window's voice minutes are not used up: 429 `quota_exhausted` with
    `feature: "orena.voice"` at the plan's limit for the window - this learner only, nothing else is locked. Checked before a
    voice session opens or a chunk is renewed; every token minted is clamped to the seconds left
    (`voice_seconds_left`), so the cap is not passed. Usage that cannot be read refuses (503, fail closed)."""

    plan = _plan(user_key)
    if plan is None:
        return
    require(user_key, VOICE)
    # The window first (the longer wait when both are used up), then today's sub-cap.
    spent = next(((window, limit, used) for window, limit, used in _voice_caps(user_key, plan) if used >= limit), None)
    if spent is None:
        return
    window, limit, used = spent
    now = _clock()
    meter = METERS[VOICE]
    # No `upgrade`: Plus and Pro differ only in how many minutes, and the learner is told when they come back.
    raise quota.exhausted_error({
        "feature": VOICE, "used": used, "limit": limit, "unit": meter.unit, "display_unit": meter.display_unit,
        "scale": meter.scale, "window": window, "resets_at": _resets_at(now, window),
        "plan": plan.id}, now=now)  # fmt: skip


def voice_allowance(user_key: str) -> dict:
    """The voice minutes for the energy bar (Monetisation v2): read only, nothing minted or charged.

    `limit`/`used`/`left`/`resets_at` are the meter's window (a day, or a month); `daily` is today's sub-cap under it
    (`{limit, used, left, resets_at}`, None when there is none); `available` is what a new session may use now, the
    smaller of the two. `used` counts every token already minted (a token's seconds count when it is minted). A plan
    without voice is `entitled: false` with nothing available - not a refusal. None where nothing is capped here (no plan
    system, no usage store, no limit). Unreadable: 503, fail closed."""

    meter = METERS[VOICE]
    now = _clock()
    answer = {"feature": VOICE, "entitled": True, "limit": None, "used": 0, "left": None, "unit": meter.unit,
              "display_unit": meter.display_unit, "scale": meter.scale, "window": meter.window,
              "resets_at": _resets_at(now, meter.window), "plan": None, "daily": None,
              "available": None}  # fmt: skip
    plan = _plan(user_key)
    if plan is None:
        return answer
    answer["plan"] = plan.id
    entitlement = plan.entitlement_map().get(VOICE)
    if entitlement is None or not entitlement.enabled:
        return {**answer, "entitled": False, "limit": 0, "left": 0, "available": 0}
    lefts = []
    limit = _voice_limit(plan)
    if limit is not None and _usage_reader() is not None:
        used = min(_voice_used(user_key), limit)
        answer.update(limit=limit, used=used, left=limit - used)
        lefts.append(limit - used)
    daily = _voice_daily_limit(plan)
    if daily is not None:
        today = min(_voice_used_today(user_key), daily)
        answer["daily"] = {"limit": daily, "used": today, "left": daily - today, "resets_at": _resets_at(now, "day")}
        lefts.append(daily - today)
    answer["available"] = min(lefts) if lefts else None
    return answer
