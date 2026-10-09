from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine, String, cast, delete, func, select, text
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


class SettingConflict(Exception):
    """A compare-and-set write whose expected version is no longer the stored one (HTTP 409)."""


def _moment(value: object) -> datetime | None:
    """A stored or expected timestamp as an aware UTC datetime (None for "no row yet")."""
    if value in (None, ""):
        return None
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _add_audit(session: Session, audit: dict, now: datetime) -> None:
    """One `audit_logs` row inside the caller's transaction; the actor is linked to their account row when there is one."""
    actor = str(audit.get("actor") or "")
    body = dict(audit.get("payload") or {})
    user_id = session.scalar(select(User.id).where(User.user_key == actor)) if actor else None
    if user_id is None:
        body["actor"] = actor or "unknown"
    session.add(AuditLog(id=uuid.uuid4(), user_id=user_id, action=str(audit["action"])[:160],
                         entity_type=str(audit.get("entity_type") or "")[:120],
                         entity_id=str(audit.get("entity_id") or "")[:255], payload=body, created_at=now))


def _version_matches(stored: object, expected: object) -> bool:
    """`expected` is `...` (no check), None (the row must not exist yet), or the version the caller read."""
    if expected is ...:
        return True
    try:
        return _moment(stored) == _moment(expected)
    except ValueError:
        return False


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
    def get_setting(self, key: str) -> dict | None: ...
    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict: ...
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
    def delete_agent_turns_before(self, before: datetime, *, limit: int) -> int: ...


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

    def get_setting(self, key: str) -> dict | None:
        """One platform_settings document as {value, updated_at, updated_by}, or None."""
        with self.connect() as conn:
            if not self._has_platform_settings(conn):
                return None
            row = conn.execute(
                "SELECT value_json, updated_at, updated_by FROM platform_settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row["value_json"])
        except (TypeError, ValueError):
            return None
        return {"value": value, "updated_at": str(row["updated_at"]), "updated_by": str(row["updated_by"])}

    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict:
        """Write one document. With `expected_updated_at`, only if the stored version is still that one - checked and
        written in one IMMEDIATE transaction, so two writers from the same version cannot both pass. The frozen archive
        has no audit store; `audit` is recorded by the PostgreSQL runtime only."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self.connect()
        conn.isolation_level = None  # explicit transaction control below
        try:
            conn.execute("BEGIN IMMEDIATE")
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
            row = conn.execute("SELECT updated_at FROM platform_settings WHERE key = ?", (key,)).fetchone()
            if not _version_matches(row["updated_at"] if row else None, expected_updated_at):
                conn.execute("ROLLBACK")
                raise SettingConflict(key)
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
            conn.execute("COMMIT")
        finally:
            conn.close()
        return {"value": value, "updated_at": now, "updated_by": updated_by}

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

    def delete_agent_turns_before(self, before: datetime, *, limit: int) -> int:
        # No audit table in the frozen archive store: nothing was recorded, so nothing is swept.
        return 0

    def ai_spend_since(self, since: datetime) -> tuple[float, int]:
        # No AI ledger here (telemetry is PostgreSQL-only): a spend cap must refuse, not read zero.
        raise NotImplementedError("the AI spend ledger is PostgreSQL-only")

    def ai_cost_rows(self, since: datetime) -> list[dict]:
        # Telemetry is PostgreSQL-only: nothing to report from the archive store.
        return []

    def ai_spend_for_capability(self, capability: str) -> float:
        # No ledger here: a spend cap must refuse, not read zero.
        raise NotImplementedError("the AI spend ledger is PostgreSQL-only")

    def record_ai_cost(self, user_key: str, event: dict) -> bool:
        return False

    def delete_ai_costs_before(self, before: datetime, *, limit: int) -> int:
        return 0

    def ai_costs_by_account(self, since: datetime, *, limit: int = 100) -> list[dict] | None:
        return None


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

    def get_setting(self, key: str) -> dict | None:
        """One platform_settings document as {value, updated_at, updated_by}, or None."""
        with Session(self.engine) as session:
            row = session.get(PlatformSetting, key)
            if row is None:
                return None
            return {"value": row.value, "updated_at": row.updated_at.isoformat(), "updated_by": row.updated_by}

    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict:
        """Write one document. With `expected_updated_at`, only if the stored version is still that one: the row is
        locked (`SELECT ... FOR UPDATE`), compared and written in one transaction, so two writers from the same version
        cannot both pass (review of #112). `audit` ({action, actor, entity_type, entity_id, payload}) is written in the
        same transaction: the change and its audit row commit together or not at all."""
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            row = session.scalar(select(PlatformSetting).where(PlatformSetting.key == key).with_for_update())
            if not _version_matches(row.updated_at if row else None, expected_updated_at):
                raise SettingConflict(key)
            if row is None:
                session.add(PlatformSetting(key=key, value=value, updated_at=now, updated_by=updated_by))
            else:
                row.value = value
                row.updated_at = now
                row.updated_by = updated_by
            if audit:
                _add_audit(session, audit, now)
        return {"value": value, "updated_at": now.isoformat(), "updated_by": updated_by}

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
        now = datetime.now(UTC)
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

    def delete_agent_turns_before(self, before: datetime, *, limit: int) -> int:
        """The agent.turn retention sweep (agent/retention.py): delete at most `limit` `agent.turn` rows created
        before `before`, the oldest first, and say how many went. Only that action: no other audit row - an
        administrator's change, AI operation telemetry - is ever touched by it."""

        bounded = max(1, min(int(limit), 50_000))
        oldest = (
            select(AuditLog.id)
            .where(AuditLog.action == "agent.turn", AuditLog.created_at < before)
            .order_by(AuditLog.created_at)
            .limit(bounded)
            .scalar_subquery()
        )
        with Session(self.engine) as session, session.begin():
            result = session.execute(
                delete(AuditLog)
                .where(AuditLog.action == "agent.turn", AuditLog.id.in_(oldest))
                .execution_options(synchronize_session=False)
            )
            return int(result.rowcount or 0)
    def ai_spend_since(self, since: datetime) -> tuple[float, int]:
        """Today's shared AI ledger (agent/budget.py): the estimated USD of priced calls since `since`, and how many
        provider calls succeeded without a price."""

        query = text(
            "SELECT COALESCE(SUM((payload::jsonb -> 'cost' ->> 'amount')::numeric), 0), "
            "COUNT(*) FILTER (WHERE payload::jsonb ->> 'outcome' = 'success' "
            "AND payload::jsonb ->> 'provider' IS NOT NULL "
            "AND COALESCE(payload::jsonb -> 'cost' ->> 'state', '') <> 'estimated') "
            "FROM audit_logs WHERE action = 'ai.operation' AND created_at >= :since"
        )
        with self.engine.connect() as connection:
            usd, unpriced = connection.execute(query, {"since": since}).one()
        return float(usd or 0), int(unpriced or 0)

    def ai_spend_for_capability(self, capability: str) -> float:
        """All the estimated USD one capability has spent, ever (a lifetime cap, e.g. word TTS's 5 USD)."""

        query = text(
            "SELECT COALESCE(SUM((payload::jsonb -> 'cost' ->> 'amount')::numeric), 0) FROM audit_logs "
            "WHERE action = 'ai.operation' AND payload::jsonb ->> 'capability' = :capability"
        )
        with self.engine.connect() as connection:
            return float(connection.execute(query, {"capability": str(capability)}).scalar_one() or 0)

    # --- D-156: learner feedback, kept as `learner.feedback` audit rows ----------------------------------------
    def record_feedback(self, user_key: str, review: dict) -> dict:
        from writing_coach.feedback import FEEDBACK_ACTION

        now = datetime.now(UTC)
        row_id = uuid.uuid4()
        with Session(self.engine) as session, session.begin():
            user_id = session.scalar(select(User.id).where(User.user_key == user_key)) if user_key else None
            body = dict(review)
            if user_id is None:
                body["account"] = str(user_key or "unknown")
            session.add(AuditLog(id=row_id, user_id=user_id, action=FEEDBACK_ACTION, entity_type="feedback",
                                 entity_id=str(row_id), payload=body, created_at=now))
        return {"id": str(row_id), "created_at": now.isoformat(), **review}

    def count_feedback_since(self, user_key: str, since: datetime) -> int:
        from writing_coach.feedback import FEEDBACK_ACTION

        with Session(self.engine) as session:
            user_id = session.scalar(select(User.id).where(User.user_key == user_key)) if user_key else None
            query = select(func.count()).select_from(AuditLog).where(AuditLog.action == FEEDBACK_ACTION, AuditLog.created_at >= since)
            query = query.where(AuditLog.user_id == user_id) if user_id is not None else query.where(AuditLog.payload["account"].as_string() == str(user_key))
            return int(session.scalar(query) or 0)

    # Totals, filters and paging run in SQL over every stored review - never over a truncated page (review of #113).
    @staticmethod
    def _feedback_filters(query, *, stars: int = 0, area: str = ""):
        from writing_coach.feedback import FEEDBACK_ACTION

        query = query.where(AuditLog.action == FEEDBACK_ACTION)
        if stars:
            query = query.where(AuditLog.payload["stars"].as_integer() == int(stars))
        if area:
            # `areas` is a JSON list of fixed tokens; a quoted token matches one whole entry, on every dialect.
            query = query.where(cast(AuditLog.payload["areas"], String).like(f'%"{area}"%'))
        return query

    def _feedback_user_filter(self, session, query, user_key: str):
        user_id = session.scalar(select(User.id).where(User.user_key == user_key))
        if user_id is not None:
            return query.where(AuditLog.user_id == user_id)
        return query.where(AuditLog.payload["account"].as_string() == str(user_key))

    def list_feedback(self, *, user_key: str | None = None, stars: int = 0, area: str = "", limit: int = 50,
                      offset: int = 0) -> list[dict]:
        with Session(self.engine) as session:
            query = select(AuditLog, User).outerjoin(User, User.id == AuditLog.user_id)
            query = self._feedback_filters(query, stars=stars, area=area).order_by(AuditLog.created_at.desc())
            if user_key is not None:
                query = self._feedback_user_filter(session, query, user_key)
            rows = session.execute(query.offset(max(0, int(offset))).limit(max(1, min(int(limit), 100)))).all()
            return [{
                "id": str(log.id),
                "created_at": log.created_at,
                "stars": (log.payload or {}).get("stars"),
                "areas": (log.payload or {}).get("areas") or [],
                "text": (log.payload or {}).get("text") or "",
                "language": (log.payload or {}).get("language") or "",
                "interface": (log.payload or {}).get("interface") or "",
                "account_id": str(user.id) if user else None,
                # An account with no users row (local mode) keeps the key it was sent under.
                "account_key": "" if user else str((log.payload or {}).get("account") or ""),
                "name": user.name if user else "",
                "email": user.email if user else "",
            } for log, user in rows]

    def count_feedback(self, *, stars: int = 0, area: str = "") -> int:
        with Session(self.engine) as session:
            query = self._feedback_filters(select(func.count()).select_from(AuditLog), stars=stars, area=area)
            return int(session.scalar(query) or 0)

    def feedback_summary(self, *, now: datetime | None = None) -> dict:
        """Count, average, by stars, by area and the last seven days over every stored review, in SQL."""
        from writing_coach.feedback import AREAS

        moment = now or datetime.now(UTC)
        stars_value = AuditLog.payload["stars"].as_integer()
        with Session(self.engine) as session:
            base = self._feedback_filters(select(func.count()).select_from(AuditLog))
            total = int(session.scalar(base) or 0)
            average = session.scalar(self._feedback_filters(select(func.avg(stars_value)).select_from(AuditLog)))
            by_stars = {str(n): 0 for n in range(1, 6)}
            for value, count in session.execute(
                self._feedback_filters(select(stars_value, func.count()).select_from(AuditLog)).group_by(stars_value)
            ).all():
                if value is not None and str(int(value)) in by_stars:
                    by_stars[str(int(value))] = int(count)
            by_area = {area: int(session.scalar(self._feedback_filters(select(func.count()).select_from(AuditLog), area=area)) or 0)
                       for area in AREAS}
            recent = int(session.scalar(base.where(AuditLog.created_at >= moment - timedelta(days=7))) or 0)
        return {
            "total": total,
            "average": round(float(average), 2) if total and average is not None else None,
            "by_stars": by_stars,
            "by_area": by_area,
            "last_7_days": recent,
        }

    # --- Retention (human decision 2026-10-09, D-159): reviews go with their account, and after 24 months. --------
    def delete_feedback_for_account(self, user_key: str) -> int:
        """Every review an account sent - for the account-deletion runtime to call when it deletes the account."""
        from writing_coach.feedback import FEEDBACK_ACTION

        with Session(self.engine) as session, session.begin():
            user_id = session.scalar(select(User.id).where(User.user_key == user_key)) if user_key else None
            query = delete(AuditLog).where(AuditLog.action == FEEDBACK_ACTION)
            query = query.where(AuditLog.user_id == user_id) if user_id is not None else query.where(
                AuditLog.payload["account"].as_string() == str(user_key))
            return int(session.execute(query).rowcount or 0)

    def delete_feedback_before(self, before: datetime, *, limit: int) -> int:
        """The retention sweep: reviews older than `before`, and reviews whose account row is gone (an account row
        deleted after the review leaves `user_id` empty and no account key, the shape no live review has). Bounded
        batches; `learner.feedback` rows only."""
        from writing_coach.feedback import FEEDBACK_ACTION

        with Session(self.engine) as session, session.begin():
            orphan = (AuditLog.user_id.is_(None)) & (AuditLog.payload["account"].as_string().is_(None))
            ids = session.scalars(
                select(AuditLog.id).where(AuditLog.action == FEEDBACK_ACTION)
                .where((AuditLog.created_at < before) | orphan)
                .order_by(AuditLog.created_at).limit(max(1, int(limit)))
            ).all()
            if not ids:
                return 0
            return int(session.execute(delete(AuditLog).where(AuditLog.id.in_(ids))).rowcount or 0)

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

    def ai_cost_rows(self, since: datetime) -> list[dict]:
        """The AI ledger grouped by UTC day, capability, provider and model (cost report, 2026-10-04).

        Sums only what the rows recorded: estimated USD, priced and unpriced calls, tokens and audio seconds.
        No learner is named: the operation telemetry is anonymous by design.
        """

        query = text(
            "WITH ops AS (SELECT created_at, payload::jsonb AS p FROM audit_logs "
            "WHERE action = 'ai.operation' AND created_at >= :since) "
            "SELECT to_char(date_trunc('day', created_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS day, "
            "p ->> 'capability' AS capability, p ->> 'provider' AS provider, p ->> 'model' AS model, "
            "COUNT(*) AS calls, COUNT(*) FILTER (WHERE p ->> 'outcome' = 'failure') AS failures, "
            "COUNT(*) FILTER (WHERE p -> 'cost' ->> 'state' = 'estimated') AS priced_calls, "
            "COUNT(*) FILTER (WHERE p ->> 'outcome' = 'success' AND p ->> 'provider' IS NOT NULL "
            "AND COALESCE(p -> 'cost' ->> 'state', '') <> 'estimated') AS unpriced_calls, "
            "COALESCE(SUM((p -> 'cost' ->> 'amount')::numeric), 0) AS usd, "
            "COALESCE(SUM((p -> 'usage' ->> 'prompt_tokens')::bigint), 0) AS prompt_tokens, "
            "COALESCE(SUM((p -> 'usage' ->> 'completion_tokens')::bigint), 0) AS completion_tokens, "
            "COALESCE(SUM((p -> 'usage' ->> 'audio_seconds')::numeric), 0) AS audio_seconds, "
            "AVG((p ->> 'latency_ms')::numeric) AS avg_latency_ms "
            "FROM ops GROUP BY 1, 2, 3, 4 ORDER BY 1 DESC, usd DESC"
        )
        with self.engine.connect() as connection:
            rows = connection.execute(query, {"since": since}).mappings().all()
        return [
            {
                "day": row["day"], "capability": row["capability"], "provider": row["provider"], "model": row["model"],
                "calls": int(row["calls"]), "failures": int(row["failures"]), "priced_calls": int(row["priced_calls"]),
                "unpriced_calls": int(row["unpriced_calls"]), "usd": round(float(row["usd"]), 8),
                "prompt_tokens": int(row["prompt_tokens"]), "completion_tokens": int(row["completion_tokens"]),
                "audio_seconds": round(float(row["audio_seconds"]), 3),
                "avg_latency_ms": round(float(row["avg_latency_ms"])) if row["avg_latency_ms"] is not None else None,
            }
            for row in rows
        ]

    # ---- AI cost per account (AC-2; proposed migration 20261005_0026) -------------------------------------

    def record_ai_cost(self, user_key: str, event: dict) -> bool:
        """One priced call for a signed-in account: account, feature, provider, model, cost and units - no learner
        words. One statement in the learner's request, bounded by short timeouts so a slow database delays a learner
        by at most a fraction of a second. False (nothing written) for a key with no account row; an error (the
        table not there yet, a timeout) is the caller's to absorb."""

        cost = event.get("cost") if isinstance(event.get("cost"), dict) else {}
        usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        values = {
            "id": uuid.uuid4(), "user_key": user_key, "occurred_at": datetime.now(UTC),
            "feature": str(event.get("capability") or "")[:80], "provider": str(event.get("provider") or "")[:40],
            "model": str(event.get("model") or "")[:160], "cost_state": str(cost.get("state") or "unknown"),
            "cost_usd": cost.get("amount"), "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"), "audio_seconds": usage.get("audio_seconds"),
        }  # fmt: skip
        statement = text(
            "INSERT INTO ai_cost_records (id, account_id, occurred_at, feature, provider, model, cost_state, cost_usd, "
            "input_tokens, output_tokens, audio_seconds) "
            "SELECT :id, users.id, :occurred_at, :feature, :provider, :model, :cost_state, :cost_usd, :input_tokens, "
            ":output_tokens, :audio_seconds FROM users WHERE users.user_key = :user_key"
        )
        with self.engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = 500"))
            connection.execute(text("SET LOCAL lock_timeout = 200"))
            return int(connection.execute(statement, values).rowcount or 0) == 1

    def delete_ai_costs_before(self, before: datetime, *, limit: int) -> int:
        """The 13-month sweep (ai/account_costs.py): at most `limit` cost records older than `before`, oldest first.
        Only that table."""

        from writing_coach.persistence.models import AICostRecord

        bounded = max(1, min(int(limit), 50_000))
        oldest = (select(AICostRecord.id).where(AICostRecord.occurred_at < before)
                  .order_by(AICostRecord.occurred_at).limit(bounded).scalar_subquery())  # fmt: skip
        with Session(self.engine) as session, session.begin():
            result = session.execute(delete(AICostRecord).where(AICostRecord.id.in_(oldest))
                                     .execution_options(synchronize_session=False))  # fmt: skip
            return int(result.rowcount or 0)

    def ai_costs_by_account(self, since: datetime, *, limit: int = 100) -> list[dict] | None:
        """Cost per account since `since`, the most expensive first, at most `limit` accounts, for an
        administrator. None before the table."""

        from sqlalchemy import func
        from sqlalchemy.exc import ProgrammingError

        from writing_coach.persistence.models import AICostRecord

        query = (
            select(User.email, User.name, func.count(AICostRecord.id), func.coalesce(func.sum(AICostRecord.cost_usd), 0))
            .join(User, User.id == AICostRecord.account_id)
            .where(AICostRecord.occurred_at >= since)
            .group_by(User.id, User.email, User.name)
            .order_by(func.coalesce(func.sum(AICostRecord.cost_usd), 0).desc())
            .limit(max(1, min(int(limit), 1000)))
        )
        try:
            with Session(self.engine) as session:
                rows = session.execute(query).all()
        except ProgrammingError:
            return None
        return [{"email": email, "name": name, "calls": int(calls), "usd": round(float(usd or 0), 8)}
                for email, name, calls, usd in rows]
