"""Orena Memory on PostgreSQL: the `MemoryRepository` port over migration 0035 (ORENA_MEMORY.md rev 4.1 §4.1, §4.4,
§6; D-222).

It honours the contract `InMemoryMemoryStore` holds (agent/memory_store.py), and the same tests run against both
(`tests/test_agent_memory_contract.py`). Like every incarnation-keyed table of 0005, the tables have no ORM model: raw
SQL on an `Engine`, PostgreSQL only.

- **One transaction per method.** A write first makes sure the learner's `learner_memory_state` row exists, then holds
  it `FOR UPDATE`: that lock serialises one learner's memory writes, so dedupe, limits and the version bump are
  race-free without relying on a unique violation, and the version moves in the same transaction as the change.
- **Scope.** Every statement filters `incarnation_id` and `user_id`. A write whose incarnation is not active (deleted
  while the request was in flight) raises `MemoryUnavailable` and writes nothing. Resolving the scope from the active
  incarnation is the caller's job (`memory_scope`); there is no user-only fallback.
- **Lock order.** The incarnation row (`FOR SHARE`), then the learner's state row (`FOR UPDATE`), then items. The
  D-055 deletion runtime, when it is built, must lock the incarnation before it touches memory rows; the reverse
  order deadlocks with a writer. The expiry sweep takes no learner lock and skips locked rows.
- **Reads.** `snapshot` reads the state and the items in one `REPEATABLE READ` transaction, so a pack holds exactly
  the items of the version it carries. Expiry is filtered on read; `sweep_expired` deletes in bounded batches and is
  never called at startup (D-002).
- **Keys.** `value_key` is the HMAC of the normalised slot and value (the code when there is one, else the text)
  under the current key version; dedupe and suppression match a row under its own stored version
  (`MemoryKeys.matches`), so rows written before a rotation still dedupe and suppress.
- **Reads fail closed.** Every read also requires the incarnation to be active: after an account deletion a scope
  resolved earlier reads OFF, no items and no suppression.
- **Session summaries are M3** (their own revision): `summaries` is empty, `snapshot` carries none, a bulk delete of
  `sessions` removes nothing, and `checkpoint`, `finalise` and `delete_summary` raise until that table exists.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text as sql
from sqlalchemy.engine import Connection, Engine

from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_store import (
    CONTINUITY,
    EXPLICIT,
    INFERRED,
    INFERRED_SUPPRESSION,
    LIMITS,
    SINGLE_VALUED_SLOTS,
    MemoryItem,
    MemoryLimit,
    MemoryOff,
    MemoryScope,
    MemorySnapshot,
    MemoryState,
    MemoryUnavailable,
    SessionSummary,
)

M3 = "orena_session_summaries is migration M3's: not in this revision"
_COLUMNS = ("id, language_code, class, kind, slot, text, code, source, key_version, value_key, created_at, expires_at,"
            " provenance")  # fmt: skip
_LIVE = "(expires_at IS NULL OR expires_at > :now)"
_SCOPE = "incarnation_id = :i AND user_id = :u"
# Reads fail closed too: a scope resolved before the account was deleted reads nothing after (review of M2.1 P2-2).
_ACTIVE = ("EXISTS (SELECT 1 FROM account_incarnations ai WHERE ai.id = :i AND ai.user_id = :u"
           " AND ai.status = 'active')")


def _params(scope: MemoryScope, **more: Any) -> dict[str, Any]:
    return {"i": scope.incarnation_id, "u": scope.user_id, **more}


def _item(row: Mapping[str, Any]) -> MemoryItem:
    provenance = row["provenance"] or {}
    if isinstance(provenance, str):
        provenance = json.loads(provenance)
    return MemoryItem(
        id=str(row["id"]), language_code=row["language_code"], cls=row["class"], kind=row["kind"], slot=row["slot"],
        text=row["text"], source=row["source"], key_version=int(row["key_version"]), value_key=row["value_key"],
        created_at=row["created_at"], expires_at=row["expires_at"],
        provenance=tuple(provenance.get("sessions") or ()), code=row["code"],
    )


def _uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


class PostgresMemoryRepository:
    def __init__(self, engine: Engine, keys: MemoryKeys) -> None:
        self._engine = engine
        self._keys = keys

    @contextmanager
    def _write(self) -> Iterator[Connection]:
        """A write transaction at READ COMMITTED, pinned rather than left to the engine default: the first-write
        serialisation (ON CONFLICT DO NOTHING, then FOR UPDATE on a fresh snapshot) depends on it (review P2-4)."""

        with self._engine.connect().execution_options(isolation_level="READ COMMITTED") as conn, conn.begin():
            yield conn

    # --- helpers (inside a transaction) --------------------------------------------------------------------------

    @staticmethod
    def _state(conn: Connection, scope: MemoryScope) -> MemoryState:
        """The switch and version; an incarnation that is not active reads as OFF (its version kept, so a pack built
        before the deletion is rebuilt)."""

        row = conn.execute(sql(f"SELECT enabled, version, {_ACTIVE} FROM learner_memory_state WHERE {_SCOPE}"),
                           _params(scope)).first()  # fmt: skip
        if row is None:
            active = conn.execute(sql(f"SELECT {_ACTIVE}"), _params(scope)).scalar()
            return MemoryState() if active else MemoryState(enabled=False)
        return MemoryState(enabled=bool(row[0]) and bool(row[2]), version=int(row[1]))

    @staticmethod
    def _lock(conn: Connection, scope: MemoryScope, now: datetime) -> MemoryState:
        """The learner's state row, created if missing and held for this transaction; the incarnation must be active."""

        active = conn.execute(sql(
            "SELECT 1 FROM account_incarnations WHERE id = :i AND user_id = :u AND status = 'active' FOR SHARE"),
            _params(scope)).first()  # fmt: skip
        if active is None:
            raise MemoryUnavailable("the incarnation is not active")
        conn.execute(sql(
            "INSERT INTO learner_memory_state (incarnation_id, user_id, enabled, version, updated_at)"
            " VALUES (:i, :u, true, 0, :now) ON CONFLICT (incarnation_id) DO NOTHING"), _params(scope, now=now))
        row = conn.execute(sql(f"SELECT enabled, version FROM learner_memory_state WHERE {_SCOPE} FOR UPDATE"),
                           _params(scope)).one()  # fmt: skip
        return MemoryState(enabled=bool(row[0]), version=int(row[1]))

    @staticmethod
    def _bump(conn: Connection, scope: MemoryScope, now: datetime, *, enabled: bool | None = None) -> MemoryState:
        row = conn.execute(sql(
            "UPDATE learner_memory_state SET version = version + 1, updated_at = :now,"
            f" enabled = coalesce(:enabled, enabled) WHERE {_SCOPE} RETURNING enabled, version"),
            _params(scope, now=now, enabled=enabled)).one()  # fmt: skip
        return MemoryState(enabled=bool(row[0]), version=int(row[1]))

    @staticmethod
    def _rows(conn: Connection, scope: MemoryScope, where: str, now: datetime, **more: Any) -> list[MemoryItem]:
        rows = conn.execute(sql(f"SELECT {_COLUMNS} FROM learner_memories WHERE {_SCOPE} AND {_LIVE} AND {_ACTIVE} AND {where}"
                                 " ORDER BY class, kind, created_at, id"), _params(scope, now=now, **more))
        return [_item(row) for row in rows.mappings()]

    def _same_value(self, item: MemoryItem, slot: str | None, value: str) -> bool:
        return item.slot == slot and self._keys.matches(slot or "", value, item.key_version, item.value_key)

    def _remove(self, conn: Connection, scope: MemoryScope, item: MemoryItem, now: datetime) -> None:
        """Delete an item; continuity and inferred leave a suppression key until their former expiry (§4.1)."""

        conn.execute(sql(f"DELETE FROM learner_memories WHERE id = :id AND {_SCOPE}"), _params(scope, id=item.id))
        if item.cls in (CONTINUITY, INFERRED) and item.slot:
            until = item.expires_at if item.cls == CONTINUITY and item.expires_at else now + INFERRED_SUPPRESSION
            conn.execute(sql(
                "INSERT INTO learner_memory_suppressions (id, incarnation_id, user_id, language_code, class, slot,"
                " value_key, key_version, expires_at) VALUES (:id, :i, :u, :lang, :cls, :slot, :vk, :kv, :until)"
                " ON CONFLICT ON CONSTRAINT uq_learner_memory_suppressions_key"
                " DO UPDATE SET expires_at = greatest(learner_memory_suppressions.expires_at, excluded.expires_at)"),
                _params(scope, id=uuid.uuid4(), lang=item.language_code, cls=item.cls, slot=item.slot,
                        vk=item.value_key, kv=item.key_version, until=until))  # fmt: skip

    # --- reads ---------------------------------------------------------------------------------------------------

    def state(self, scope: MemoryScope) -> MemoryState:
        with self._engine.connect() as conn:
            return self._state(conn, scope)

    def probe(self, scope: MemoryScope, now: datetime) -> MemoryState:
        """The cheap per-turn read (§5.2). Nothing comes due by time alone until M3's summaries exist."""

        return self.state(scope)

    def items(self, scope: MemoryScope, language: str, now: datetime) -> list[MemoryItem]:
        with self._engine.connect() as conn:
            return self._rows(conn, scope, "language_code IN (:lang, '*')", now, lang=language)

    def summaries(self, scope: MemoryScope, language: str, now: datetime, limit: int) -> list[SessionSummary]:
        return []

    def snapshot(self, scope: MemoryScope, language: str, now: datetime, sessions: int) -> MemorySnapshot:
        with self._engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                state = self._state(conn, scope)
                items = self._rows(conn, scope, "language_code IN (:lang, '*')", now, lang=language)
        return MemorySnapshot(state=state, items=tuple(items), summaries=())

    def suppressed(self, scope: MemoryScope, language: str, cls: str, slot: str | None, value: str,
                   now: datetime) -> bool:  # fmt: skip
        with self._engine.connect() as conn:
            rows = conn.execute(sql(
                f"SELECT key_version, value_key FROM learner_memory_suppressions WHERE {_SCOPE} AND {_ACTIVE}"
                " AND language_code = :lang AND class = :cls AND slot = :slot AND expires_at > :now"),
                _params(scope, lang=language, cls=cls, slot=slot or "", now=now)).all()  # fmt: skip
        return any(self._keys.matches(slot or "", value, int(kv), vk) for kv, vk in rows)

    def versions_in_use(self) -> set[int]:
        """Key versions any live row or unexpired suppression key still uses (for `MemoryKeys.check_in_use`)."""

        with self._engine.connect() as conn:
            rows = conn.execute(sql(
                "SELECT DISTINCT key_version FROM learner_memories WHERE expires_at IS NULL OR expires_at > now()"
                " UNION SELECT DISTINCT key_version FROM learner_memory_suppressions WHERE expires_at > now()")).all()
        return {int(row[0]) for row in rows}

    # --- writes --------------------------------------------------------------------------------------------------

    def set_enabled(self, scope: MemoryScope, enabled: bool, now: datetime | None = None) -> MemoryState:
        now = now or datetime.now(UTC)
        with self._write() as conn:
            self._lock(conn, scope, now)
            return self._bump(conn, scope, now, enabled=bool(enabled))

    def add_explicit(self, scope: MemoryScope, *, language: str, kind: str, text: str, slot: str | None,
                     source: str, now: datetime) -> MemoryItem:  # fmt: skip
        with self._write() as conn:
            if not self._lock(conn, scope, now).enabled:
                raise MemoryOff
            live = self._rows(conn, scope, "language_code = :lang AND class = :cls", now, lang=language, cls=EXPLICIT)
            held = next((i for i in live if (slot in SINGLE_VALUED_SLOTS and i.slot == slot)
                         or self._same_value(i, slot, text)), None)  # fmt: skip
            if held is not None and self._same_value(held, slot, text):
                return held  # a retried remember_note (same words) does not duplicate
            if held is None and len(live) >= LIMITS[EXPLICIT]:
                raise MemoryLimit
            if held is not None:  # a single-valued slot: the learner's latest choice wins
                conn.execute(sql(f"DELETE FROM learner_memories WHERE id = :id AND {_SCOPE}"),
                             _params(scope, id=held.id))  # fmt: skip
            version, value_key = self._keys.stamp(slot or "", text)
            row = conn.execute(sql(
                "INSERT INTO learner_memories (id, incarnation_id, user_id, language_code, class, kind, slot, text,"
                " value_key, key_version, source, created_at, updated_at)"
                " VALUES (:id, :i, :u, :lang, 'explicit', :kind, :slot, :text, :vk, :kv, :source, :now, :now)"
                f" RETURNING {_COLUMNS}"),
                _params(scope, id=uuid.uuid4(), lang=language, kind=kind, slot=slot, text=text, vk=value_key,
                        kv=version, source=source, now=now)).mappings().one()  # fmt: skip
            self._bump(conn, scope, now)
            return _item(row)

    def delete_item(self, scope: MemoryScope, item_id: str, now: datetime) -> bool:
        ident = _uuid(item_id)
        if ident is None:
            return False
        with self._write() as conn:  # allowed while memory is OFF (§6)
            self._lock(conn, scope, now)
            row = conn.execute(sql(f"SELECT {_COLUMNS} FROM learner_memories WHERE id = :id AND {_SCOPE} FOR UPDATE"),
                               _params(scope, id=ident)).mappings().first()  # fmt: skip
            if row is None:
                return False
            self._remove(conn, scope, _item(row), now)
            self._bump(conn, scope, now)
            return True

    def delete_all(self, scope: MemoryScope, what: str, now: datetime) -> int:
        """`items`, `sessions` or `all`. Suppression keys are kept (and written for continuity and inferred)."""

        if what not in ("items", "sessions", "all"):
            raise ValueError(what)
        with self._write() as conn:
            self._lock(conn, scope, now)
            removed = 0
            if what in ("items", "all"):
                rows = conn.execute(sql(f"SELECT {_COLUMNS} FROM learner_memories WHERE {_SCOPE} FOR UPDATE"),
                                    _params(scope)).mappings().all()  # fmt: skip
                for row in rows:
                    self._remove(conn, scope, _item(row), now)
                removed = len(rows)
            self._bump(conn, scope, now)
            return removed

    def sweep_expired(self, now: datetime, batch: int = 500) -> int:
        """Delete up to `batch` expired items and expired suppression keys. Expired rows are already invisible to
        every read, so the version does not move. Called by an operator job, never at startup."""

        with self._write() as conn:
            items = conn.execute(sql(
                "DELETE FROM learner_memories WHERE id IN (SELECT id FROM learner_memories"
                " WHERE expires_at IS NOT NULL AND expires_at <= :now LIMIT :n FOR UPDATE SKIP LOCKED)"),
                {"now": now, "n": batch}).rowcount  # fmt: skip
            keys = conn.execute(sql(
                "DELETE FROM learner_memory_suppressions WHERE id IN (SELECT id FROM learner_memory_suppressions"
                " WHERE expires_at <= :now LIMIT :n FOR UPDATE SKIP LOCKED)"), {"now": now, "n": batch}).rowcount
        return int(items or 0) + int(keys or 0)

    # --- M3 ------------------------------------------------------------------------------------------------------

    def checkpoint(self, scope: MemoryScope, *, agent_session_id: str, language: str, turns_covered: int,
                   summary: Mapping[str, Any], context: Sequence[tuple[str, str]], now: datetime) -> bool:  # fmt: skip
        raise NotImplementedError(M3)

    def finalise(self, scope: MemoryScope, agent_session_id: str, now: datetime) -> int:
        raise NotImplementedError(M3)

    def delete_summary(self, scope: MemoryScope, agent_session_id: str, now: datetime) -> int:
        raise NotImplementedError(M3)
