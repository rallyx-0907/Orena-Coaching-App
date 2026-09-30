from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from writing_coach.persistence.config import create_shadow_engine
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import User


class SettingsVersionConflict(Exception):
    """The account settings moved since the writer read them (D-104 H-17).

    Carries the token the writer must re-read against; a client timestamp never resolves it.
    """

    def __init__(self, current_token: str) -> None:
        super().__init__("account settings version conflict")
        self.current_token = current_token


class AccountRowMissing(Exception):
    """There is no account row to hold settings (authentication-disabled local development)."""


# The account-wide scalars that live on the `users` row (migration 0018) and share one version
# token. Everything else on the row is identity and is not written through this path.
ACCOUNT_SETTING_COLUMNS = ("learning_language", "interface_language", "weekly_goal_days")


def _token_of(value: datetime | None) -> str:
    """The opaque `settings_version`: the server's own timestamp text, microseconds included."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _parse_token(token: str) -> tuple[bool, datetime | None]:
    """(valid, value) for a token the server issued; '' is the never-written state.

    Only the server parses its own token. A client echoes it verbatim: a value re-serialised
    through a millisecond clock is a different instant and is refused as stale.
    """
    if not token:
        return True, None
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return False, None
    if parsed.tzinfo is None:
        return False, None
    return True, parsed.astimezone(timezone.utc)


def _settings_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "learning_language": str(row.get("learning_language") or ""),
        "interface_language": str(row.get("interface_language") or ""),
        "weekly_goal_days": row.get("weekly_goal_days"),
        "settings_version": row.get("settings_version") or "",
    }


class AuthRepository(Protocol):
    def initialize(self, admin_emails: set[str]) -> None: ...
    def get_user(self, google_sub: str) -> dict[str, Any] | None: ...
    def upsert_user(self, info: dict[str, Any], admin_emails: set[str]) -> dict[str, Any]: ...
    def get_account_settings(self, user_key: str) -> dict[str, Any] | None: ...
    def update_account_settings(
        self, user_key: str, changes: dict[str, Any], expected_token: str
    ) -> dict[str, Any]: ...


class SQLiteAuthRepository:
    """Current authoritative authentication store behind a repository boundary."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self, admin_emails: set[str]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    google_sub TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL DEFAULT '',
                    picture TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_login TEXT NOT NULL
                )
                """
            )
            cols = {str(r["name"]) for r in conn.execute("PRAGMA table_info(users)").fetchall()}
            if "role" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            # D4 (migration 0018 on PostgreSQL): the account-wide settings and their version token.
            # This SQLite table is the hermetic test backend only.
            for name, ddl in (
                ("learning_language", "TEXT NOT NULL DEFAULT ''"),
                ("interface_language", "TEXT NOT NULL DEFAULT ''"),
                ("weekly_goal_days", "INTEGER"),
                ("settings_updated_at", "TEXT"),
            ):
                if name not in cols:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
            for email in admin_emails:
                conn.execute("UPDATE users SET role='admin' WHERE lower(email)=?", (email,))
            conn.commit()

    def get_user(self, google_sub: str) -> dict[str, Any] | None:
        if not google_sub:
            return None
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
        return dict(row) if row else None

    def upsert_user(self, info: dict[str, Any], admin_emails: set[str]) -> dict[str, Any]:
        sub = str(info.get("sub") or "")
        email = str(info.get("email") or "").strip()
        name = str(info.get("name") or "").strip()
        picture = str(info.get("picture") or "").strip()
        if not sub or not email:
            raise ValueError("Google account did not provide a valid subject/email.")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO users(google_sub,email,name,picture,created_at,last_login)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(google_sub) DO UPDATE SET
                  email=excluded.email,name=excluded.name,picture=excluded.picture,last_login=excluded.last_login
                """,
                (sub, email, name, picture, now, now),
            )
            if email.casefold() in admin_emails:
                conn.execute("UPDATE users SET role='admin' WHERE google_sub=?", (sub,))
            conn.commit()
        return self.get_user(sub) or {}


    def get_account_settings(self, user_key: str) -> dict[str, Any] | None:
        if not user_key:
            return None
        with self.connect() as conn:
            row = conn.execute(
                "SELECT learning_language, interface_language, weekly_goal_days, settings_updated_at "
                "FROM users WHERE google_sub = ?",
                (user_key,),
            ).fetchone()
        if row is None:
            return None
        return _settings_payload({**dict(row), "settings_version": row["settings_updated_at"] or ""})

    def update_account_settings(
        self, user_key: str, changes: dict[str, Any], expected_token: str
    ) -> dict[str, Any]:
        """One conditional UPDATE: the token is compared and replaced by the server in one statement."""
        columns = [name for name in changes if name in ACCOUNT_SETTING_COLUMNS]
        if not columns:
            raise ValueError("No account setting to write")
        current = self.get_account_settings(user_key)
        if current is None:
            raise AccountRowMissing(user_key)
        valid, _ = _parse_token(expected_token)
        if not valid:
            raise SettingsVersionConflict(current["settings_version"])
        new_token = _token_of(datetime.now(timezone.utc))
        assignments = ", ".join(f"{name} = ?" for name in columns)
        with self.connect() as conn:
            cursor = conn.execute(
                f"UPDATE users SET {assignments}, settings_updated_at = ? "
                "WHERE google_sub = ? AND settings_updated_at IS ?",
                (*[changes[name] for name in columns], new_token, user_key, expected_token or None),
            )
            conn.commit()
            written = cursor.rowcount
        if written != 1:
            latest = self.get_account_settings(user_key) or current
            raise SettingsVersionConflict(latest["settings_version"])
        return self.get_account_settings(user_key) or {}


class PostgresAuthRepository:
    """PostgreSQL implementation of the auth contract; not selected at runtime yet."""

    def __init__(self, engine: Engine | None = None, *, url: str | None = None) -> None:
        self.engine = engine or create_shadow_engine(url)

    def _id(self, google_sub: str):
        return stable_uuid("user", google_sub)

    def initialize(self, admin_emails: set[str]) -> None:
        # Alembic owns schema creation. This method only synchronizes configured admin roles.
        if not admin_emails:
            return
        with Session(self.engine) as session, session.begin():
            rows = session.scalars(select(User).where(func.lower(User.email).in_(sorted(admin_emails)))).all()
            for row in rows:
                row.role = "admin"

    @staticmethod
    def _payload(row: User) -> dict[str, Any]:
        return {
            "google_sub": row.user_key,
            "email": row.email,
            "name": row.name,
            "picture": row.picture,
            "created_at": row.created_at.isoformat(),
            "last_login": row.last_login.isoformat() if row.last_login else "",
            "role": row.role,
            "learning_language": row.learning_language or "",
        }

    def get_user(self, google_sub: str) -> dict[str, Any] | None:
        if not google_sub:
            return None
        with Session(self.engine) as session:
            row = session.get(User, self._id(google_sub))
            return self._payload(row) if row else None

    def upsert_user(self, info: dict[str, Any], admin_emails: set[str]) -> dict[str, Any]:
        sub = str(info.get("sub") or "")
        email = str(info.get("email") or "").strip()
        name = str(info.get("name") or "").strip()
        picture = str(info.get("picture") or "").strip()
        if not sub or not email:
            raise ValueError("Google account did not provide a valid subject/email.")
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            uid = self._id(sub)
            row = session.get(User, uid)
            if row is None:
                row = User(
                    id=uid,
                    user_key=sub,
                    email=email,
                    name=name,
                    picture=picture,
                    role="admin" if email.casefold() in admin_emails else "user",
                    created_at=now,
                    last_login=now,
                )
                session.add(row)
            else:
                row.email = email
                row.name = name
                row.picture = picture
                row.last_login = now
                if email.casefold() in admin_emails:
                    row.role = "admin"
            session.flush()
            payload = self._payload(row)
        return payload

    @staticmethod
    def _settings_of(row: Any) -> dict[str, Any]:
        return _settings_payload({
            "learning_language": row.learning_language,
            "interface_language": row.interface_language,
            "weekly_goal_days": row.weekly_goal_days,
            "settings_version": _token_of(row.settings_updated_at),
        })

    def get_account_settings(self, user_key: str) -> dict[str, Any] | None:
        if not user_key:
            return None
        with Session(self.engine) as session:
            row = session.get(User, self._id(user_key))
            return self._settings_of(row) if row else None

    def update_account_settings(
        self, user_key: str, changes: dict[str, Any], expected_token: str
    ) -> dict[str, Any]:
        """`UPDATE ... WHERE id = :id AND settings_updated_at IS NOT DISTINCT FROM :expected`.

        The new token is the database clock in the same statement, so two writers holding one token
        cannot both succeed and a client timestamp never enters (D-104 H-17).
        """
        columns = {name: changes[name] for name in changes if name in ACCOUNT_SETTING_COLUMNS}
        if not columns:
            raise ValueError("No account setting to write")
        uid = self._id(user_key)
        valid, expected = _parse_token(expected_token)
        with Session(self.engine) as session, session.begin():
            current = session.get(User, uid)
            if current is None:
                raise AccountRowMissing(user_key)
            latest = self._settings_of(current)
            if not valid:
                raise SettingsVersionConflict(latest["settings_version"])
            guard = (
                User.settings_updated_at.is_(None)
                if expected is None
                else User.settings_updated_at == expected
            )
            result = session.execute(
                update(User)
                .where(User.id == uid, guard)
                .values(**columns, settings_updated_at=func.clock_timestamp())
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                session.expire_all()
                fresh = session.get(User, uid)
                raise SettingsVersionConflict(_token_of(fresh.settings_updated_at) if fresh else "")
        with Session(self.engine) as session:
            row = session.get(User, uid)
            return self._settings_of(row)
