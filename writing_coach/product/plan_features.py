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
_clock: Callable[[], datetime] = lambda: datetime.now(UTC)


def configure(*, daily_usage: Callable[[str, str], int] | None,
              clock: Callable[[], datetime] | None = None) -> None:  # fmt: skip
    """app.py: the usage store's daily total. None (a bare server, tests): voice minutes are not counted."""

    global _daily_usage, _clock
    _daily_usage = daily_usage
    _clock = clock or (lambda: datetime.now(UTC))


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


def require_voice_time(user_key: str) -> None:
    """The plan has voice (403 otherwise) and today's voice minutes are not used up: 429 `quota_exhausted` with
    `feature: "orena.voice"` at the plan's daily limit - this learner only, nothing else is locked. Checked before a
    voice chunk is minted; a chunk already minted plays out, so the cap can be passed by at most one chunk. Usage
    that cannot be read refuses (503, fail closed)."""

    plan = _plan(user_key)
    if plan is None:
        return
    require(user_key, VOICE)
    limit = plan.entitlement_map()[VOICE].limit
    if limit is None or _daily_usage is None:
        return
    try:
        used = int(_daily_usage(user_key, VOICE_USAGE))
    except Exception as error:  # noqa: BLE001 - the usage store is down: fail closed
        raise quota._unavailable("usage") from error
    if used < limit:
        return
    now = _clock()
    resets = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
    meter = METERS[VOICE]
    raise quota.exhausted_error({
        "feature": VOICE, "used": used, "limit": limit, "unit": meter.unit, "display_unit": meter.display_unit,
        "scale": meter.scale, "window": meter.window, "resets_at": resets.isoformat().replace("+00:00", "Z"),
        "plan": plan.id, "upgrade": quota.UPGRADE_HREF}, now=now)  # fmt: skip
