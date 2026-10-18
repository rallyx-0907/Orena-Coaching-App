"""Light consent, server side (D-229 clause 5, D-233): the consent evidence and the voice consent of an account.

What is kept, on the account row (`persistence/consent_store.py`, migration 20261019_0036, proposed): the version of the
Terms and Privacy Policy the learner accepted, when, and in which interface language; and whether the learner allows
their voice to be recorded and sent to an AI service, and when that last changed.

Every function degrades to "no record" when the columns are absent (the runtime has not applied the migration yet) or
unreadable, and none raises for that: `consent_state` answers `available: False`, a write answers False, the bootstrap
flag stays off and the voice gate lets requests through. Nothing is enforced or recorded until the columns exist.

The current version is the deploy-stamped effective date of the public legal pages (`build_public_pages.mjs --release
--effective-date YYYY-MM-DD`; the repository keeps it null, D-229 clause 3). The same date is given to the server as the
environment variable `LEGAL_EFFECTIVE_DATE`; unset or malformed, the version recorded is `unstamped`, which says
honestly that the deploy did not state one.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from writing_coach.core.errors import orena_http_error

log = logging.getLogger(__name__)

UNSTAMPED = "unstamped"
CONSENT_LANGUAGES = ("en", "vi", "zh")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def current_legal_version(environ: Any = None) -> str:
    """The Terms / Privacy effective version a sign-in accepts: `LEGAL_EFFECTIVE_DATE` (YYYY-MM-DD) or `unstamped`."""
    value = str((environ if environ is not None else os.environ).get("LEGAL_EFFECTIVE_DATE") or "").strip()
    return value if _DATE.match(value) else UNSTAMPED


def normalize_language(value: Any, default: str = "en") -> str:
    """`en`, `vi` or `zh` from an interface language or an Accept-Language value (its first tag); else the default."""
    head = str(value or "").split(",")[0].split(";")[0].strip().casefold().replace("_", "-")
    code = head.split("-")[0]
    return code if code in CONSENT_LANGUAGES else default


def _store(repository: Any):
    return getattr(repository, "consent", None) if repository is not None else None


def consent_state(repository: Any, user_key: str) -> dict[str, Any]:
    """`{available, accepted, version, accepted_at, language, voice, voice_at}` for the account.

    `available` is False when there is no store, no columns, no account row or the read failed; every other field is
    then its empty value (`voice` is None: unknown, not refused)."""
    store = _store(repository)
    row = store.get(user_key) if store is not None else None
    if row is None:
        return {
            "available": False, "accepted": False, "version": "", "accepted_at": "", "language": "",
            "voice": None, "voice_at": "",
        }
    return {
        "available": True,
        "accepted": bool(row["consent_accepted_at"]),
        "version": row["consent_version"],
        "accepted_at": row["consent_accepted_at"],
        "language": row["consent_language"],
        "voice": bool(row["voice_consent"]),
        "voice_at": row["voice_consent_at"],
    }


def consent_required(repository: Any, user_key: str) -> bool:
    """True for an account that exists, can hold a record, and has none: the client shows its one-time sheet."""
    state = consent_state(repository, user_key)
    return state["available"] and not state["accepted"]


def public_shape(repository: Any, user_key: str) -> dict[str, Any]:
    """The response of the consent endpoints and the bootstrap: what the client needs and nothing more."""
    state = consent_state(repository, user_key)
    return {
        "stored": state["available"],
        "consent_required": state["available"] and not state["accepted"],
        "consent_version": state["version"],
        "voice_consent": state["voice"],
    }


def record_sign_up_consent(repository: Any, user_key: str, language: str) -> bool:
    """First sign-in of a NEW account: the clickwrap line was shown on the Account step (D-229 clause 1). Never raises."""
    store = _store(repository)
    if store is None or not user_key:
        return False
    try:
        return store.accept(user_key, current_legal_version(), normalize_language(language), only_if_unset=True)
    except Exception:  # noqa: BLE001 - a consent problem must not fail a sign-in
        log.warning("sign-up consent not recorded", exc_info=True)
        return False


def accept_consent(repository: Any, user_key: str, language: str) -> bool:
    """The learner pressed "I agree" on the one-time sheet: record the current version; a later press renews it."""
    store = _store(repository)
    if store is None or not user_key:
        return False
    return store.accept(user_key, current_legal_version(), normalize_language(language), only_if_unset=False)


def set_voice_consent(repository: Any, user_key: str, granted: bool) -> bool:
    store = _store(repository)
    if store is None or not user_key:
        return False
    return store.set_voice(user_key, granted)


def reset_consent(repository: Any, user_key: str) -> bool:
    """The account-deletion workflow's reset of the five columns (`deletion_enumeration.USER_COLUMNS_TO_RESET`)."""
    store = _store(repository)
    if store is None or not user_key:
        return False
    return store.reset(user_key)


def voice_consent_blocks(repository: Any, user_key: str, *, auth_enabled: bool) -> bool:
    """Whether a voice request must be refused: sign-in is on, the account has a record to read, and it says no.

    Absent columns, no account row, no sign-in (local development) and an unreadable record all let the request through:
    the gate enforces a stored refusal, never a missing store."""
    if not auth_enabled:
        return False
    state = consent_state(repository, user_key)
    return state["available"] and state["voice"] is False


def require_voice_consent() -> None:
    """Raise the 403 `voice_consent_required` for a speech request when the learner has not allowed recording.

    The `/api/speech/*` routes that carry audio to a provider call this first. `/api/agent/voice/*` belongs to the
    Orena Intelligence lane: this module only supplies the flag (`GET /api/account-settings/consent`) and that lane
    decides whether to read it."""
    from writing_coach import account_settings

    if voice_consent_blocks(
        account_settings._repository, account_settings._user_key(), auth_enabled=account_settings._auth_enabled()
    ):
        raise orena_http_error(
            403,
            "voice_consent_required",
            "Recording your voice needs your permission. Turn it on in Settings, Privacy.",
            retryable=False,
        )
