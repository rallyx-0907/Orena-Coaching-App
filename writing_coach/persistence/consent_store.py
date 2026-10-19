"""Consent evidence and voice consent on the account row (migration 20261019_0036, D-233).

Five columns on `users`: `consent_version`, `consent_accepted_at`, `consent_language`, `voice_consent`,
`voice_consent_at`. They are PROPOSED (`migrations/proposed/`), so a runtime may not have them yet, and no ORM column
maps them: this module reads and writes them with raw statements behind a column-presence check, and with the columns
absent every call answers "no record" - `get` returns None, a write returns False - and raises nothing. Merging the
code is therefore safe before the revision is applied; once it is, the same calls start to record.

The presence answer "yes" is remembered for the life of the process (columns are never dropped under a running
server); "no" is remembered for `ABSENT_RECHECK_SECONDS` only, so a runtime that applies the revision starts recording
without a restart. Any database error while reading or writing is treated as "no record" and logged, so a consent
problem can never take a sign-in or a settings read down.

Two backends, one shape: `PostgresConsentStore` (the authoritative runtime) and `SQLiteConsentStore` (the hermetic
test backend and frozen archive, whose `users` table `SQLiteAuthRepository.initialize` extends).
"""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)

CONSENT_COLUMNS = ("consent_version", "consent_accepted_at", "consent_language", "voice_consent", "voice_consent_at")
ABSENT_RECHECK_SECONDS = 30.0


class ConsentUnreadable(Exception):
    """The columns are known present and a read failed: the answer is unknown, which is not "no record"."""


def _warn_once(owner: Any, what: str, *, error: bool) -> None:
    """The first failure of a kind logs its traceback; later ones log one line (a persistent fault is not a flood)."""
    seen = owner.__dict__.setdefault("_warned", set())
    if what in seen:
        log.warning("%s (repeated)", what)
        return
    seen.add(what)
    log.warning(what, exc_info=error)


class _Presence:
    """Whether every consent column exists: a positive answer is kept, a negative one is re-asked after a while."""

    def __init__(self, probe, clock=time.monotonic) -> None:
        self._probe = probe
        self._clock = clock
        self._present = False
        self._checked_at: float | None = None
        self._warned = set()

    def __call__(self) -> bool:
        if self._present:
            return True
        now = self._clock()
        if self._checked_at is not None and now - self._checked_at < ABSENT_RECHECK_SECONDS:
            return False
        self._checked_at = now
        try:
            self._present = bool(self._probe())
        except Exception:  # noqa: BLE001 - an unanswerable probe is "absent", never an error
            _warn_once(self, "consent column probe failed; treating consent as unavailable", error=True)
            self._present = False
        return self._present


def _shape(version, accepted_at, language, voice, voice_at) -> dict[str, Any]:
    return {
        "consent_version": str(version or ""),
        "consent_accepted_at": _iso(accepted_at),
        "consent_language": str(language or ""),
        "voice_consent": bool(voice),
        "voice_consent_at": _iso(voice_at),
    }


def _iso(value: Any) -> str:
    if value is None or value == "":
        return ""
    return value.isoformat() if isinstance(value, datetime) else str(value)


class PostgresConsentStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.available = _Presence(self._probe)

    def _probe(self) -> bool:
        with self.engine.connect() as conn:
            found = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns WHERE table_schema = current_schema() "
                    "AND table_name = 'users' AND column_name = ANY(:names)"
                ),
                {"names": list(CONSENT_COLUMNS)},
            ).scalar()
        return int(found or 0) == len(CONSENT_COLUMNS)

    def get(self, user_key: str) -> dict[str, Any] | None:
        if not user_key or not self.available():
            return None
        try:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT consent_version, consent_accepted_at, consent_language, voice_consent, "
                        "voice_consent_at FROM users WHERE user_key = :k"
                    ),
                    {"k": user_key},
                ).fetchone()
        except Exception as exc:  # noqa: BLE001
            _warn_once(self, "consent read failed", error=True)
            raise ConsentUnreadable from exc
        return _shape(*row) if row else None

    def _execute(self, sql: str, params: dict[str, Any]) -> bool:
        if not self.available():
            return False
        try:
            with self.engine.begin() as conn:
                return conn.execute(text(sql), params).rowcount == 1
        except Exception:  # noqa: BLE001
            _warn_once(self, "consent write failed; nothing recorded", error=True)
            return False

    def accept(self, user_key: str, version: str, language: str, *, only_if_unset: bool) -> bool:
        guard = " AND consent_accepted_at IS NULL" if only_if_unset else ""
        return self._execute(
            "UPDATE users SET consent_version = :v, consent_accepted_at = now(), consent_language = :l "
            f"WHERE user_key = :k{guard}",
            {"k": user_key, "v": version, "l": language},
        )

    def set_voice(self, user_key: str, granted: bool) -> bool:
        return self._execute(
            "UPDATE users SET voice_consent = :g, voice_consent_at = now() WHERE user_key = :k",
            {"k": user_key, "g": bool(granted)},
        )

    def reset(self, user_key: str) -> bool:
        return self._execute(
            "UPDATE users SET consent_version = NULL, consent_accepted_at = NULL, consent_language = NULL, "
            "voice_consent = false, voice_consent_at = NULL WHERE user_key = :k",
            {"k": user_key},
        )


class SQLiteConsentStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.available = _Presence(self._probe)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _probe(self) -> bool:
        conn = self._connect()
        try:
            cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        finally:
            conn.close()
        return set(CONSENT_COLUMNS) <= cols

    def get(self, user_key: str) -> dict[str, Any] | None:
        if not user_key or not self.available():
            return None
        try:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT consent_version, consent_accepted_at, consent_language, voice_consent, voice_consent_at "
                    "FROM users WHERE google_sub = ?",
                    (user_key,),
                ).fetchone()
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            _warn_once(self, "consent read failed", error=True)
            raise ConsentUnreadable from exc
        return _shape(*tuple(row)) if row else None

    def _execute(self, sql: str, params: tuple) -> bool:
        if not self.available():
            return False
        try:
            conn = self._connect()
            try:
                cursor = conn.execute(sql, params)
                conn.commit()
                return cursor.rowcount == 1
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            _warn_once(self, "consent write failed; nothing recorded", error=True)
            return False

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def accept(self, user_key: str, version: str, language: str, *, only_if_unset: bool) -> bool:
        guard = " AND consent_accepted_at IS NULL" if only_if_unset else ""
        return self._execute(
            "UPDATE users SET consent_version = ?, consent_accepted_at = ?, consent_language = ? "
            f"WHERE google_sub = ?{guard}",
            (version, self._now(), language, user_key),
        )

    def set_voice(self, user_key: str, granted: bool) -> bool:
        return self._execute(
            "UPDATE users SET voice_consent = ?, voice_consent_at = ? WHERE google_sub = ?",
            (1 if granted else 0, self._now(), user_key),
        )

    def reset(self, user_key: str) -> bool:
        return self._execute(
            "UPDATE users SET consent_version = NULL, consent_accepted_at = NULL, consent_language = NULL, "
            "voice_consent = 0, voice_consent_at = NULL WHERE google_sub = ?",
            (user_key,),
        )
