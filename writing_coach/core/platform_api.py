from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from writing_coach import account_settings
from writing_coach.core.language_registry import (
    DEFAULT_LANGUAGE,
    all_languages,
    enabled_language,
    is_enabled,
)
from writing_coach.core.request_context import current_language_code
from writing_coach.core.skill_registry import all_skills
from writing_coach.core.support_languages import all_support_languages

router = APIRouter()


class LanguageSelectIn(BaseModel):
    language: str = Field(min_length=2, max_length=12)
    # The opaque token the client read from /api/account-settings (D-104 H-17). Absent: the session
    # still switches, and the stored choice is written only if the account never chose one.
    settings_version: str | None = Field(default=None, max_length=64)


@router.get("/api/platform/languages")
def api_platform_languages(request: Request) -> dict[str, object]:
    active = enabled_language(
        request.session.get("language") or current_language_code() or DEFAULT_LANGUAGE
    ).code
    return {
        "api_version": 1,
        "active": active,
        "data_isolation": "user+language",
        "support_languages": [{"code": item.code, "label": item.translation_label} for item in all_support_languages()],
        "languages": [item.public_dict() for item in all_languages()],
    }


@router.post("/api/platform/language")
def api_platform_language(payload: LanguageSelectIn, request: Request) -> dict[str, object]:
    code = payload.language.strip().casefold()
    if not is_enabled(code):
        raise HTTPException(409, f"Language module '{code}' is not enabled yet.")
    stored, token = False, ""
    # D-16R: where the target-language count is enforced (None when it is not), taking a language the account does
    # not hold yet is judged inside the write's own transaction - so it must be stored; a language it holds switches
    # exactly as it always did. A refusal is raised before the session is touched.
    adoption = account_settings.language_adoption({"learning_language": code})
    guard = adoption.guard if adoption is not None else None
    row = account_settings.read_account_settings()
    if row is not None:
        token = row["settings_version"]
        if payload.settings_version is not None:
            # A stale token is a 409 and the session is left as it was: the client re-reads and
            # re-applies once. The stored value and the session change together or not at all.
            written = account_settings.write_account_settings(
                {"learning_language": code}, payload.settings_version, guard=guard
            )
            stored, token = True, written["settings_version"]
        elif not row["learning_language"] and not token:
            if adoption is not None:
                # Enforced: the first choice is an adoption like any other. It is written against the token the server
                # reads under the lock, so the guard ALWAYS judges it - a rival first choice that committed meanwhile
                # cannot turn this write into a skipped check and a swallowed 409 (review F1).
                written = account_settings.write_account_settings({"learning_language": code}, None, guard=guard)
                stored, token = True, written["settings_version"]
            else:
                try:
                    written = account_settings.write_account_settings({"learning_language": code}, "")
                    stored, token = True, written["settings_version"]
                except HTTPException:
                    stored = False
        elif adoption is not None and not adoption.holds():
            # A token-less switch to a language the account does not hold would otherwise change this session only
            # and leave no trace of the adoption: record it, against the token the server reads under the lock.
            written = account_settings.write_account_settings({"learning_language": code}, None, guard=guard)
            stored, token = True, written["settings_version"]
    elif adoption is not None:
        # An enforced adoption must be recorded on the account. With no account row the write creates the local
        # account's (authentication off) or answers 503 `account_settings_unavailable` (nowhere to record it).
        written = account_settings.write_account_settings({"learning_language": code}, "", guard=guard)
        stored, token = True, written["settings_version"]
    request.session["language"] = code
    return {"ok": True, "active": code, "stored": stored, "settings_version": token}


@router.get("/api/platform/skills")
def api_platform_skills() -> dict[str, object]:
    """Return the single language-wide learner skill release contract."""
    return {
        "api_version": 1,
        "policy": "language-wide",
        "language_scope": [item.code for item in all_languages() if item.enabled],
        "skills": [item.public_dict() for item in all_skills()],
    }
