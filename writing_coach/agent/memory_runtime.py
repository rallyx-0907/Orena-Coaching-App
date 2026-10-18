"""Orena Memory for one server and one turn (ORENA_MEMORY.md rev 4.1 §4.4, §5.2, §6, §8; D-222; contract v9 §5.4,
§10).

`MemoryRuntime` is what a server has: a store (agent/memory_store.py port; PostgreSQL in the app) and the account
backbone's incarnations. It exists only when both do and `AGENT_MEMORY_HMAC_KEYS` is set; otherwise the server has no
Orena Memory and every turn is exactly as before M2.

- **Scope.** A learner's scope is (account, active incarnation). Reads resolve the active incarnation and never create
  one; a learner's own write (a note they asked for, a memory route) may create it the way the other account-scoped
  writes do (`ensure_active`). No incarnation, or a deleted account: no scope, and memory is off for that learner (fail
  closed; no user-only fallback).
- **One turn** (`MemoryTurn`): the learner's switch and version, read once per turn (the cheap probe of §5.2), and
  whether the server applies notes in it - a client that declared v9, memory ON, and a model cleared for
  `full_memory` (§6, §8). With memory OFF nothing from memory reaches a model, device coach notes neither.
- **Server notes** (`ServerNotes`): `remember_note` / `forget_note` applied to `learner_memories` (explicit class) for
  such a turn; the model sees the account's notes, with their ids, where it saw the device's.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from writing_coach.agent.contract import (
    COACH_NOTE_KINDS,
    MAX_COACH_NOTES,
    MAX_COACH_NOTES_BYTES,
    MEMORY_STORED_VERSION,
)
from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_store import (
    EXPLICIT,
    MemoryItem,
    MemoryRepository,
    MemoryScope,
    MemorySection,
    MemoryState,
    MemoryUnavailable,
    memory_scope,
    memory_section,
)
from writing_coach.agent.schemas import CoachNote, coach_notes_bytes
from writing_coach.product import quota

_log = logging.getLogger(__name__)

STORED_SERVER, STORED_DEVICE = "server", "device"
NOTE_WEIGHT = 1.0  # an explicit item does not decay (§3.2): the model reads it at full weight


def account_id(user_key: str) -> str:
    """The account a learner's memory belongs to: `users.id`, as every account-scoped store derives it."""

    return quota.account_id(user_key)


def as_coach_note(item: MemoryItem) -> CoachNote:
    """An explicit item, shown to the model where a device coach note would be: its id is the server item's."""

    return CoachNote(id=item.id, kind=item.kind, text=item.text, weight=NOTE_WEIGHT, last_reinforced=item.created_at)


@dataclass(frozen=True)
class MemoryTurn:
    """What Orena Memory means for one turn (or one voice session)."""

    scope: MemoryScope | None
    state: MemoryState | None  # None: no scope for this learner (no incarnation)
    server: bool = False  # the server applies notes in this turn (v9, ON, full_memory)
    cleared: bool = False  # the model is cleared for full_memory: the pack may carry memory
    failed: bool = False  # the learner's memory state could not be read: treated as OFF (fail closed)

    @property
    def on(self) -> bool:
        return self.scope is not None and self.state is not None and self.state.enabled

    @property
    def off(self) -> bool:
        """The learner switched memory OFF: nothing from memory, and no device note, reaches a model (§6)."""

        return self.failed or (self.state is not None and not self.state.enabled)

    @property
    def marker(self) -> str:
        """What the conversation's frozen pack depends on (§5.2): rebuilt when the version or the mode moves."""

        if not self.on or not self.server:
            return "m-"  # no memory in the pack (only server mode carries it): nothing to rebuild for
        return f"m{self.state.version}s"


@dataclass
class ServerNotes:
    """`remember_note` / `forget_note` on the account (v9): one store call each, in the learner's scope - resolved
    only when a note is actually written (a learner's own write may create the incarnation, as other writes do)."""

    store: MemoryRepository
    resolve: Callable[[], MemoryScope | None]
    language: str  # the turn's target language (internal code): a note is the learner's for that language
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    _scope: MemoryScope | None = field(default=None, init=False)

    def _in_scope(self) -> MemoryScope:
        if self._scope is None:
            self._scope = self.resolve()
        if self._scope is None:
            raise MemoryUnavailable("no active incarnation")
        return self._scope

    def keep(self, *, kind: str, text: str) -> MemoryItem:
        """A new note. Raises `MemoryOff`, `MemoryLimit`, `MemoryUnavailable` (and a store error)."""

        return self.store.add_explicit(self._in_scope(), language=self.language, kind=kind, text=text, slot=None,
                                       source="learner_asked", now=self.clock())  # fmt: skip

    def forget(self, item_id: str) -> bool:
        return self.store.delete_item(self._in_scope(), item_id, self.clock())


@dataclass
class MemoryRuntime:
    store: MemoryRepository
    incarnations: Any  # resolve(account) -> str | None; ensure_active(account) -> str (account_backbone)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def scope(self, user_key: str, *, create: bool = False) -> MemoryScope | None:
        account = account_id(user_key)
        try:
            incarnation = self.incarnations.ensure_active(account) if create else self.incarnations.resolve(account)
        except Exception:  # noqa: BLE001 - a deleted account (DeletionBarrier), one not set up, or the store down
            return None
        return memory_scope(account, incarnation)

    def turn(self, user_key: str, *, version: int, cleared: bool) -> MemoryTurn:
        """One turn's view: the probe (§5.2) and whether the server applies notes. A store that cannot be read
        gives no scope - memory is off for the turn, never guessed."""

        scope = self.scope(user_key)
        if scope is None:
            return MemoryTurn(None, None)
        try:
            state = self.store.probe(scope, self.clock())
        except Exception:  # noqa: BLE001 - memory that cannot be read is not used; the turn goes on without it
            _log.warning("orena memory probe failed", exc_info=True)
            return MemoryTurn(None, None, failed=True)  # the switch is unknown: as OFF, so no device note goes either
        server = state.enabled and cleared and version >= MEMORY_STORED_VERSION
        return MemoryTurn(scope, state, server=server, cleared=cleared)

    def server_notes(self, user_key: str, language: str) -> ServerNotes:
        return ServerNotes(self.store, lambda: self.scope(user_key, create=True), language, self.clock)

    def notes(self, turn: MemoryTurn, language: str) -> tuple[CoachNote, ...]:
        """The account's explicit notes for the language, as the model's coach notes (server mode): newest first,
        within the caps a request's `coach_notes` has (§3). A store that cannot be read gives none."""

        if not turn.on:
            return ()
        try:
            items = self.store.items(turn.scope, language, self.clock())
        except Exception:  # noqa: BLE001 - the turn goes on without the notes, never fails on them
            _log.warning("orena memory notes not read", exc_info=True)
            return ()
        chosen: list[CoachNote] = []
        for item in sorted(items, key=lambda i: (i.created_at, i.id), reverse=True):
            if item.cls != EXPLICIT or item.kind not in COACH_NOTE_KINDS:
                continue
            note = as_coach_note(item)
            if len(chosen) >= MAX_COACH_NOTES or coach_notes_bytes([*chosen, note]) > MAX_COACH_NOTES_BYTES:
                break
            chosen.append(note)
        return tuple(chosen)

    def pack_reader(self) -> Callable[[str, datetime], MemorySection | None]:
        """For `PackBuilder.memory`: the current learner's memory section (read inside their request context)."""

        def read(target: str, now: datetime) -> MemorySection | None:
            from writing_coach.agent.tools import LearnerScope

            return memory_section(self.store, self.scope(LearnerScope.from_request_context().user_key), target, now)

        return read

    @classmethod
    def from_env(cls, environ: Mapping[str, Any], backbone: Any,
                 store: Callable[[MemoryKeys], MemoryRepository]) -> MemoryRuntime | None:  # fmt: skip
        """The server's memory, or None: no keys (`AGENT_MEMORY_HMAC_KEYS`), or no active account backbone. `store` makes
        the repository for the keys (app.py: PostgreSQL; this package reaches no database itself). Unreadable
        keys refuse to start. Nothing is read from the database here (D-002): versions in use are checked by an
        operator before a rotation (`MemoryKeys.check_in_use`), and a row under an unconfigured version never
        matches, so it can neither dedupe nor suppress wrongly."""

        keys = MemoryKeys.from_env(environ)
        if keys is None or backbone is None or not getattr(backbone, "is_active", False):
            return None
        return cls(store=store(keys), incarnations=backbone.incarnations)


def carries_memory(pack: Any) -> bool:
    """The built pack holds Orena Memory (explicit, inferred or continuity data), not only its version stamp."""

    return any(key in pack.data for key in ("explicit", "inferred", "continuity"))


def without_explicit(section: MemorySection | None) -> MemorySection | None:
    """A section whose explicit items reach the model as coach notes instead (server mode): not sent twice."""

    if section is None:
        return None
    return replace(section, explicit=(),
                   provenance=tuple(e for e in section.provenance if not str(e.get("line", "")).startswith("explicit.")))

