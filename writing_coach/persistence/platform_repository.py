from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from writing_coach.ai.config import (
    CAPABILITY_SETTING_PREFIX,
    CapabilityConfig,
    capability_key_from_setting,
    capability_setting_key,
    validate_capability_config,
)
from writing_coach.ai.base import AICapabilityConfigInvalid
from writing_coach.persistence.config import create_shadow_engine
from writing_coach.persistence.models import AuditLog, PlatformSetting, User


@dataclass(frozen=True)
class AISelectionRecord:
    provider: str
    model: str
    updated_at: str = ""
    updated_by: str = ""


@dataclass(frozen=True)
class CapabilityConfigRecord:
    capability_key: str
    config: CapabilityConfig
    updated_at: str = ""
    updated_by: str = ""


def _sqlite_capability_config(raw: object) -> CapabilityConfig:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError) as exc:
        raise AICapabilityConfigInvalid(
            "Persisted capability config is not valid JSON."
        ) from exc
    return CapabilityConfig.from_dict(value)


class PlatformRepository(Protocol):
    def initialize(self) -> None: ...
    def get_ai_selection(self) -> AISelectionRecord | None: ...
    def set_ai_selection(self, *, provider: str, model: str, updated_by: str = "") -> None: ...
    def get_capability_config(self, capability_key: str) -> CapabilityConfigRecord | None: ...
    def list_capability_configs(self) -> list[CapabilityConfigRecord]: ...
    def set_capability_config(
        self,
        capability_key: str,
        config: CapabilityConfig,
        *,
        updated_by: str = "",
    ) -> None: ...
    def get_provider_credential(self, provider_id: str) -> dict | None: ...
    def set_provider_credential(
        self,
        provider_id: str,
        value: dict,
        *,
        updated_by: str = "",
    ) -> None: ...
    def delete_provider_credential(self, provider_id: str) -> None: ...
    def record_ai_operation(self, telemetry: dict) -> None: ...
    def list_ai_operation_events(self, limit: int = 100) -> list[dict]: ...
    def record_admin_event(
        self,
        action: str,
        *,
        actor: str,
        entity_type: str = "",
        entity_id: str = "",
        payload: dict | None = None,
    ) -> None: ...


class SQLitePlatformRepository:
    """Current authoritative platform-config store behind a repository boundary."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_ai_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by_sub TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def get_ai_selection(self) -> AISelectionRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT provider, model, updated_at, updated_by_sub FROM platform_ai_config WHERE id = 1"
            ).fetchone()
        if not row:
            return None
        return AISelectionRecord(
            provider=str(row["provider"]),
            model=str(row["model"]),
            updated_at=str(row["updated_at"]),
            updated_by=str(row["updated_by_sub"]),
        )

    def set_ai_selection(self, *, provider: str, model: str, updated_by: str = "") -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO platform_ai_config(id, provider, model, updated_at, updated_by_sub)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  provider = excluded.provider,
                  model = excluded.model,
                  updated_at = excluded.updated_at,
                  updated_by_sub = excluded.updated_by_sub
                """,
                (provider, model, now, updated_by),
            )
            conn.commit()

    @staticmethod
    def _has_platform_settings(conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'platform_settings'"
        ).fetchone()
        return row is not None

    def get_capability_config(self, capability_key: str) -> CapabilityConfigRecord | None:
        setting_key = capability_setting_key(capability_key)
        with self.connect() as conn:
            if not self._has_platform_settings(conn):
                return None
            row = conn.execute(
                "SELECT key, value_json, updated_at, updated_by FROM platform_settings WHERE key = ?",
                (setting_key,),
            ).fetchone()
        if row is None:
            return None
        return CapabilityConfigRecord(
            capability_key=capability_key_from_setting(str(row["key"])) or "",
            config=_sqlite_capability_config(row["value_json"]),
            updated_at=str(row["updated_at"]),
            updated_by=str(row["updated_by"]),
        )

    def list_capability_configs(self) -> list[CapabilityConfigRecord]:
        with self.connect() as conn:
            if not self._has_platform_settings(conn):
                return []
            rows = conn.execute(
                """
                SELECT key, value_json, updated_at, updated_by
                FROM platform_settings
                WHERE key LIKE ?
                ORDER BY key
                """,
                (CAPABILITY_SETTING_PREFIX + "%",),
            ).fetchall()
        return [
            CapabilityConfigRecord(
                capability_key=capability_key_from_setting(str(row["key"])) or "",
                config=_sqlite_capability_config(row["value_json"]),
                updated_at=str(row["updated_at"]),
                updated_by=str(row["updated_by"]),
            )
            for row in rows
        ]

    def set_capability_config(
        self,
        capability_key: str,
        config: CapabilityConfig,
        *,
        updated_by: str = "",
    ) -> None:
        validate_capability_config(capability_key, config)
        setting_key = capability_setting_key(capability_key)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO platform_settings(key, value_json, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value_json = excluded.value_json,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (setting_key, json.dumps(config.to_dict(), sort_keys=True), now, updated_by),
            )
            conn.commit()

    @staticmethod
    def _provider_setting_key(provider_id: str) -> str:
        from writing_coach.ai.credentials import credential_setting_key

        return credential_setting_key(provider_id)

    def get_provider_credential(self, provider_id: str) -> dict | None:
        key = self._provider_setting_key(provider_id)
        with self.connect() as conn:
            if not self._has_platform_settings(conn):
                return None
            row = conn.execute(
                "SELECT value_json FROM platform_settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(str(row["value_json"]))
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def set_provider_credential(
        self, provider_id: str, value: dict, *, updated_by: str = ""
    ) -> None:
        key = self._provider_setting_key(provider_id)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                INSERT INTO platform_settings(key, value_json, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value_json = excluded.value_json,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (key, json.dumps(value, sort_keys=True), now, updated_by),
            )
            conn.commit()

    def delete_provider_credential(self, provider_id: str) -> None:
        key = self._provider_setting_key(provider_id)
        with self.connect() as conn:
            if self._has_platform_settings(conn):
                conn.execute("DELETE FROM platform_settings WHERE key = ?", (key,))
                conn.commit()

    def record_ai_operation(self, telemetry: dict) -> None:
        # SQLite is frozen archive/rollback storage; telemetry is PostgreSQL-only.
        return None

    def record_admin_event(
        self,
        action: str,
        *,
        actor: str,
        entity_type: str = "",
        entity_id: str = "",
        payload: dict | None = None,
    ) -> None:
        # Like telemetry, the administrator audit is PostgreSQL-only; the frozen
        # archive store neither gains an audit table nor fails a change for it.
        return None

    def list_ai_operation_events(self, limit: int = 100) -> list[dict]:
        return []


class PostgresPlatformRepository:
    """PostgreSQL platform configuration backed by Alembic-owned storage."""

    KEY = "ai.active_selection"

    def __init__(self, engine: Engine | None = None, *, url: str | None = None) -> None:
        self.engine = engine or create_shadow_engine(url)

    def initialize(self) -> None:
        # Alembic owns schema creation.
        return None

    def get_ai_selection(self) -> AISelectionRecord | None:
        with Session(self.engine) as session:
            row = session.get(PlatformSetting, self.KEY)
            if row is None:
                return None
            value = row.value if isinstance(row.value, dict) else {}
            return AISelectionRecord(
                provider=str(value.get("provider") or ""),
                model=str(value.get("model") or ""),
                updated_at=row.updated_at.isoformat(),
                updated_by=row.updated_by,
            )

    def set_ai_selection(self, *, provider: str, model: str, updated_by: str = "") -> None:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            row = session.get(PlatformSetting, self.KEY)
            value = {"provider": provider, "model": model}
            if row is None:
                session.add(
                    PlatformSetting(
                        key=self.KEY,
                        value=value,
                        updated_at=now,
                        updated_by=updated_by,
                    )
                )
            else:
                row.value = value
                row.updated_at = now
                row.updated_by = updated_by

    def get_capability_config(self, capability_key: str) -> CapabilityConfigRecord | None:
        setting_key = capability_setting_key(capability_key)
        with Session(self.engine) as session:
            row = session.get(PlatformSetting, setting_key)
            if row is None:
                return None
            return CapabilityConfigRecord(
                capability_key=capability_key_from_setting(row.key) or "",
                config=CapabilityConfig.from_dict(row.value),
                updated_at=row.updated_at.isoformat(),
                updated_by=row.updated_by,
            )

    def list_capability_configs(self) -> list[CapabilityConfigRecord]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(PlatformSetting)
                .where(PlatformSetting.key.startswith(CAPABILITY_SETTING_PREFIX))
                .order_by(PlatformSetting.key)
            ).all()
            return [
                CapabilityConfigRecord(
                    capability_key=capability_key_from_setting(row.key) or "",
                    config=CapabilityConfig.from_dict(row.value),
                    updated_at=row.updated_at.isoformat(),
                    updated_by=row.updated_by,
                )
                for row in rows
            ]

    def set_capability_config(
        self,
        capability_key: str,
        config: CapabilityConfig,
        *,
        updated_by: str = "",
    ) -> None:
        validate_capability_config(capability_key, config)
        setting_key = capability_setting_key(capability_key)
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            row = session.get(PlatformSetting, setting_key)
            if row is None:
                session.add(
                    PlatformSetting(
                        key=setting_key,
                        value=config.to_dict(),
                        updated_at=now,
                        updated_by=updated_by,
                    )
                )
            else:
                row.value = config.to_dict()
                row.updated_at = now
                row.updated_by = updated_by

    @staticmethod
    def _provider_setting_key(provider_id: str) -> str:
        from writing_coach.ai.credentials import credential_setting_key

        return credential_setting_key(provider_id)

    def get_provider_credential(self, provider_id: str) -> dict | None:
        row_key = self._provider_setting_key(provider_id)
        with Session(self.engine) as session:
            row = session.get(PlatformSetting, row_key)
            if row is None or not isinstance(row.value, dict):
                return None
            return dict(row.value)

    def set_provider_credential(
        self, provider_id: str, value: dict, *, updated_by: str = ""
    ) -> None:
        row_key = self._provider_setting_key(provider_id)
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            row = session.get(PlatformSetting, row_key)
            if row is None:
                session.add(
                    PlatformSetting(
                        key=row_key,
                        value=value,
                        updated_at=now,
                        updated_by=updated_by,
                    )
                )
            else:
                row.value = value
                row.updated_at = now
                row.updated_by = updated_by

    def delete_provider_credential(self, provider_id: str) -> None:
        row_key = self._provider_setting_key(provider_id)
        with Session(self.engine) as session, session.begin():
            row = session.get(PlatformSetting, row_key)
            if row is not None:
                session.delete(row)

    def record_ai_operation(self, telemetry: dict) -> None:
        from writing_coach.ai.base import sanitize_telemetry

        safe = sanitize_telemetry(telemetry)
        if safe is None:
            return None
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            session.add(
                AuditLog(
                    id=uuid.uuid4(),
                    user_id=None,
                    action="ai.operation",
                    entity_type="ai_capability",
                    entity_id=str(safe["capability"]),
                    payload=safe,
                    created_at=now,
                )
            )

    def record_admin_event(
        self,
        action: str,
        *,
        actor: str,
        entity_type: str = "",
        entity_id: str = "",
        payload: dict | None = None,
    ) -> None:
        """Record one administrator change to the AI platform in `audit_logs`.

        The same table AI operation telemetry uses. The actor is linked to its
        account row when there is one; a development administrator without one
        is named in the payload instead. Callers pass only non-secret facts.
        """
        body = dict(payload or {})
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            user_id = session.scalar(select(User.id).where(User.user_key == actor)) if actor else None
            if user_id is None:
                body["actor"] = str(actor or "unknown")
            session.add(
                AuditLog(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    action=str(action)[:160],
                    entity_type=str(entity_type)[:120],
                    entity_id=str(entity_id)[:255],
                    payload=body,
                    created_at=now,
                )
            )

    def list_ai_operation_events(self, limit: int = 100) -> list[dict]:
        bounded = max(1, min(int(limit), 500))
        with Session(self.engine) as session:
            rows = session.scalars(
                select(AuditLog)
                .where(AuditLog.action == "ai.operation")
                .order_by(AuditLog.created_at.desc())
                .limit(bounded)
            ).all()
        from writing_coach.ai.base import sanitize_telemetry

        events: list[dict] = []
        for row in rows:
            safe = sanitize_telemetry(row.payload)
            if safe is None:
                continue
            safe["created_at"] = row.created_at.isoformat()
            events.append(safe)
        return events
