"""Account-wide learner settings on the account row (D4 I2, I3, I3b; D-104 H-17, H-18).

Three scalars follow the person, not the language being learned: the learning language, the
interface language and the weekly goal in days. They live on `users` and share ONE version token,
`settings_updated_at`, set only by the server and served to clients as the opaque string
`settings_version`. A write carries the token it read; a stale token is a 409 carrying the current
one. A client timestamp never resolves a conflict and there is no blind last write.

No decision here is about a request or a database: the repository owns the conditional statement,
this module owns validation and the HTTP shape.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from writing_coach.account_profile import ACCOUNT_SETTINGS
from writing_coach.core.language_registry import is_enabled
from writing_coach.core.request_context import current_user_key
from writing_coach.persistence.auth_repository import (
    AccountRowMissing,
    SettingsVersionConflict,
)

router = APIRouter()

WEEKLY_GOAL_DAYS = (1, 7)
# The one account of authentication-disabled local development (auth_support keys the request by it).
LOCAL_ACCOUNT_KEY = "legacy"

_repository: Any = None
_user_key = current_user_key


def _auth_enabled() -> bool:
    """Whether this deployment signs learners in. The local account is created only when it does not."""
    from writing_coach.core.deployment import resolve_deployment_config

    return bool(resolve_deployment_config().auth_enabled)


def configure_account_settings(repository: Any, user_key=current_user_key) -> None:
    global _repository, _user_key
    _repository = repository
    _user_key = user_key


def _shape(row: dict[str, Any] | None) -> dict[str, Any]:
    """The response: `stored` says whether an account row exists to hold these at all."""
    if row is None:
        return {
            "stored": False,
            "learning_language": "",
            "interface_language": "",
            "weekly_goal_days": None,
            "settings_version": "",
        }
    return {
        "stored": True,
        "learning_language": row["learning_language"],
        "interface_language": row["interface_language"],
        "weekly_goal_days": row["weekly_goal_days"],
        "settings_version": row["settings_version"],
    }


def read_account_settings() -> dict[str, Any] | None:
    """The stored settings for the request's account, or None when there is no account row."""
    if _repository is None:
        return None
    return _repository.get_account_settings(_user_key())


def stored_learning_language(user_key: str) -> str:
    """The language the account last chose, or '' (never chosen, or no account row)."""
    if _repository is None:
        return ""
    row = _repository.get_account_settings(user_key)
    value = str((row or {}).get("learning_language") or "")
    return value if value and is_enabled(value) else ""


class AccountSettingsPatchIn(BaseModel):
    # The token this writer read, echoed verbatim. '' is the never-written state.
    expected_settings_version: str = Field(default="", max_length=64)
    learning_language: str | None = Field(default=None, max_length=20)
    interface_language: str | None = Field(default=None, max_length=8)
    # Present and null clears the goal; absent leaves it.
    weekly_goal_days: int | None = None


def _conflict(token: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"reason": "version_conflict", "current_settings_version": token},
    )


def validated_changes(payload: AccountSettingsPatchIn) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    sent = payload.model_fields_set
    if payload.learning_language is not None:
        code = payload.learning_language.strip().casefold()
        if not is_enabled(code):
            raise HTTPException(400, detail={"reason": "invalid_value", "field": "learning_language"})
        changes["learning_language"] = code
    if payload.interface_language is not None:
        if not ACCOUNT_SETTINGS["interface_language"].allows(payload.interface_language):
            raise HTTPException(400, detail={"reason": "invalid_value", "field": "interface_language"})
        changes["interface_language"] = payload.interface_language
    if "weekly_goal_days" in sent:
        goal = payload.weekly_goal_days
        if goal is not None and not WEEKLY_GOAL_DAYS[0] <= goal <= WEEKLY_GOAL_DAYS[1]:
            raise HTTPException(400, detail={"reason": "invalid_value", "field": "weekly_goal_days"})
        changes["weekly_goal_days"] = goal
    if not changes:
        raise HTTPException(400, detail={"reason": "empty_patch"})
    return changes


def language_adoption(changes: dict[str, Any]):
    """The target-language entitlement's adoption for a write that sets the learning language (D-16R), or None.

    None when the write does not touch the learning language, or the entitlement is not enforced. Raises the 503 of
    the gate when enforcement is on but cannot run. The repository calls `adoption.guard` inside the write's
    transaction."""
    code = changes.get("learning_language")
    if not code:
        return None
    from writing_coach.product import language_limit

    return language_limit.adoption(str(code), _user_key())


def _guard_of(adoption: Any):
    return adoption.guard if adoption is not None else None


def write_account_settings(changes: dict[str, Any], expected_token: str | None, *, guard: Any = None) -> dict[str, Any]:
    """The conditional write; raises the HTTP errors the routes share.

    `guard` (from `adoption_guard`) judges the write inside its transaction. `expected_token=None` writes against the
    token the server reads under that lock, for a caller that holds none."""
    if _repository is None:
        raise HTTPException(503, detail={"reason": "account_settings_unavailable"})
    key = _user_key()
    options = {"guard": guard} if guard is not None else {}
    try:
        try:
            row = _repository.update_account_settings(key, changes, expected_token, **options)
        except AccountRowMissing:
            # Authentication-disabled local development has one account, "legacy", whose row a PostgreSQL
            # runtime seeds at start and a test backend never had. Create exactly that row (idempotent, so two
            # first writers both find it) and write once more; any other missing account stays unavailable.
            if _auth_enabled() or key != LOCAL_ACCOUNT_KEY:
                raise
            _repository.upsert_user(
                {"sub": LOCAL_ACCOUNT_KEY, "email": "local@localhost.invalid", "name": "Local developer"}, set()
            )
            row = _repository.update_account_settings(key, changes, expected_token, **options)
    except SettingsVersionConflict as conflict:
        raise _conflict(conflict.current_token) from conflict
    except AccountRowMissing as missing:
        raise HTTPException(503, detail={"reason": "account_settings_unavailable"}) from missing
    return _shape(row)


@router.get("/api/account-settings")
def get_account_settings() -> dict[str, Any]:
    return _shape(read_account_settings())


@router.patch("/api/account-settings")
def patch_account_settings(payload: AccountSettingsPatchIn) -> dict[str, Any]:
    changes = validated_changes(payload)
    return write_account_settings(
        changes, payload.expected_settings_version, guard=_guard_of(language_adoption(changes))
    )
