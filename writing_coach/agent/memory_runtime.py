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
  such a turn; the model sees the account's notes, with their ids, where it saw the device's - and, after them, the
  device notes the learner has not placed yet (`with_device_notes`), which stay the device's.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
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
    EXPLICIT_TTL,
    RENEW_EVERY,
    MemoryItem,
    MemoryRepository,
    MemoryScope,
    MemorySection,
    MemoryState,
    MemoryUnavailable,
    memory_scope,
    memory_section,
)
from writing_coach.agent.notes import same_note
from writing_coach.agent.retention import _in_background, sweep_enabled
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


MEMORY_SWEEP_SWITCH = "AGENT_MEMORY_RETENTION_SWEEP"


class ExpiredMemorySweep:
    """Expired memory rows are deleted at most once a day per process, off the request thread, in bounded batches
    (`sweep_expired`: expired rows only, `SKIP LOCKED`). The pilot keeps learner data up to 6 months (owner, PRE-005,
    2026-10-18); a kept note expires `EXPLICIT_TTL` after it was last used (kept or read into a turn). Off unless
    AGENT_MEMORY_RETENTION_SWEEP is on: automatic deletion is a destructive lifecycle change, switched on by the
    owner, as the agent.turn sweep (agent/retention.py). A failing sweep is logged and tried the next day."""

    MAX_BATCHES = 20
    BATCH = 500

    def __init__(self, sweep: Callable[[datetime, int], int], *, clock: Callable[[], datetime],
                 run: Callable[[Callable[[], None]], None] = _in_background,
                 enabled: Callable[[], bool] | None = None) -> None:  # fmt: skip
        """`enabled`: the switch read when a sweep is due (the `agent.memory_retention_sweep` policy, BQ); None: on."""
        self._sweep, self._clock, self._run, self._enabled = sweep, clock, run, enabled
        self._lock = threading.Lock()
        self._last: datetime | None = None
        self._removed: int | None = None  # read back only with an inline runner (tests); a thread's count is logged

    def maybe_sweep(self) -> int | None:
        """Start a sweep if one is due. With an inline runner it returns how many rows went (None: none ran)."""

        if self._enabled is not None and self._enabled() is not True:
            return None  # switched off: nothing is deleted, and the day is not claimed
        now = self._clock()
        with self._lock:
            if self._last is not None and now - self._last < timedelta(days=1):
                return None
            self._last = now  # claimed before it runs: one sweep a day, even when it fails
        self._removed = None
        self._run(lambda: self._batches(now))
        return self._removed

    def _batches(self, now: datetime) -> None:
        removed = 0
        try:
            for _ in range(self.MAX_BATCHES):
                gone = self._sweep(now, self.BATCH)
                removed += gone
                if gone < self.BATCH:
                    break
        except Exception:  # noqa: BLE001 - never a learner's turn; tried again the next day
            _log.warning("orena memory sweep failed after %d rows", removed, exc_info=True)
            return
        self._removed = removed
        if removed:
            _log.info("orena memory: %d expired rows removed", removed)


@dataclass
class MemoryRuntime:
    store: MemoryRepository
    incarnations: Any  # resolve(account) -> str | None; ensure_active(account) -> str (account_backbone)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    sweep: ExpiredMemorySweep | None = None  # the daily deletion of expired rows; None while it is switched off

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

        if self.sweep is not None:
            try:
                self.sweep.maybe_sweep()  # at most once a day, off the request thread
            except Exception:  # noqa: BLE001 - the sweep never costs a turn
                _log.warning("orena memory sweep not started", exc_info=True)
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

    def erase_account(self, user_id: str) -> int | None:
        """Every memory item and session summary of one account's CURRENT incarnation, deleted on request (an
        administrator acting on a learner's email, the PRE-005 channel; D-226) - "delete my notes", not account erasure:
        older incarnations' rows are the deletion runtime's (D-055), the switch row stays, and device-side notes are on
        the learner's device. How many went; None only when the account has no active incarnation here. A store that
        cannot be read RAISES (`MemoryUnavailable`): never "nothing to erase" while the notes may still be there."""

        try:
            incarnation = self.incarnations.resolve(user_id)
        except Exception as error:  # noqa: BLE001 - the store failed: unknown, not empty
            raise MemoryUnavailable("the account's incarnation could not be read") from error
        scope = memory_scope(user_id, incarnation)
        if scope is None:
            return None
        return int(self.store.delete_all(scope, "all", self.clock()))

    def server_notes(self, user_key: str, language: str) -> ServerNotes:
        return ServerNotes(self.store, lambda: self.scope(user_key, create=True), language, self.clock)

    def notes(self, turn: MemoryTurn, language: str) -> tuple[CoachNote, ...]:
        """The account's explicit notes for the language, as the model's coach notes (server mode): newest first,
        within the caps a request's `coach_notes` has (§3). A store that cannot be read gives none. They go into the
        model's context now, so each is renewed (`renew`): kept 6 months from this use. A caller that sends them only
        later (a voice open, after its admission) takes `notes_and_due` and renews once they are sent."""

        notes, due = self.notes_and_due(turn, language)
        self.renew(turn, due)
        return notes

    def notes_and_due(self, turn: MemoryTurn, language: str) -> tuple[tuple[CoachNote, ...], tuple[str, ...]]:
        """`notes`, and the ids of those due for renewal (at most once a day each, `RENEW_EVERY`), renewed by no one."""

        if not turn.on:
            return (), ()
        now = self.clock()
        try:
            items = self.store.items(turn.scope, language, now)
        except Exception:  # noqa: BLE001 - the turn goes on without the notes, never fails on them
            _log.warning("orena memory notes not read", exc_info=True)
            return (), ()
        chosen: list[CoachNote] = []
        due: list[str] = []
        for item in sorted(items, key=lambda i: (i.created_at, i.id), reverse=True):
            if item.cls != EXPLICIT or item.kind not in COACH_NOTE_KINDS:
                continue
            note = as_coach_note(item)
            if len(chosen) >= MAX_COACH_NOTES or coach_notes_bytes([*chosen, note]) > MAX_COACH_NOTES_BYTES:
                break
            chosen.append(note)
            due.extend([item.id] if self._due(item, now) else [])
        return tuple(chosen), tuple(due)

    def renew(self, turn: MemoryTurn, due: tuple[str, ...]) -> None:
        """These notes went into the model's context: each is kept 6 months from this use (PRE-005 v2; the owner,
        2026-10-18 21:44). Server mode only - then they are the model's coach notes; memory OFF renews nothing."""

        if not due or not turn.server:
            return
        try:
            self.store.renew(turn.scope, list(due), self.clock())
        except Exception:  # noqa: BLE001 - a renewal never costs the turn; the next day's use tries again
            _log.warning("orena memory notes not renewed", exc_info=True)

    @staticmethod
    def _due(item: MemoryItem, now: datetime) -> bool:
        """Renewed at most once a day: only when its date is a day or more behind a use now (RENEW_EVERY)."""
        return item.expires_at is not None and item.expires_at <= now + EXPLICIT_TTL - RENEW_EVERY

    def pack_reader(self) -> Callable[[str, datetime], MemorySection | None]:
        """For `PackBuilder.memory`: the current learner's memory section (read inside their request context)."""

        def read(target: str, now: datetime) -> MemorySection | None:
            from writing_coach.agent.tools import LearnerScope

            return memory_section(self.store, self.scope(LearnerScope.from_request_context().user_key), target, now)

        return read

    @classmethod
    def from_env(cls, environ: Mapping[str, Any], backbone: Any,
                 store: Callable[[MemoryKeys], MemoryRepository],
                 enabled: Callable[[], bool] | None = None) -> MemoryRuntime | None:  # fmt: skip
        """The server's memory, or None: no keys (`AGENT_MEMORY_HMAC_KEYS`), or no active account backbone. `store` makes
        the repository for the keys (app.py: PostgreSQL; this package reaches no database itself). Unreadable
        keys refuse to start. Nothing is read from the database here (D-002): versions in use are checked by an
        operator before a rotation (`MemoryKeys.check_in_use`), and a row under an unconfigured version never
        matches, so it can neither dedupe nor suppress wrongly."""

        keys = MemoryKeys.from_env(environ)
        sweeping = sweep_enabled(environ, MEMORY_SWEEP_SWITCH)  # an unclear value refuses to start, memory or not
        if keys is None or backbone is None or not getattr(backbone, "is_active", False):
            return None
        repository = store(keys)
        runtime = cls(store=repository, incarnations=backbone.incarnations)
        can_sweep = callable(getattr(repository, "sweep_expired", None))
        if sweeping and not can_sweep:
            raise ValueError(f"{MEMORY_SWEEP_SWITCH} is on but this memory store cannot sweep")
        if enabled is not None and can_sweep:
            # BQ: a live switch (Admin's policy, the variable pinning it): the sweep exists and asks it when one is due.
            runtime.sweep = ExpiredMemorySweep(repository.sweep_expired, clock=runtime.clock, enabled=enabled)
        elif sweeping:
            runtime.sweep = ExpiredMemorySweep(repository.sweep_expired, clock=runtime.clock)
        return runtime


def with_device_notes(account: tuple[CoachNote, ...],
                      device: tuple[CoachNote, ...]) -> tuple[tuple[CoachNote, ...], frozenset[str]]:  # fmt: skip
    """Server mode (contract v9 §3/§10, UI-lane ruling (b) on #278): the account's notes first, then the device notes
    the learner has not placed yet - highest weight first, as the client orders them - in the room the account's
    leave under the request caps. A device note the account already holds (`notes.same_note`) is sent once, as the
    account's. Returns the notes and the ids that are the device's (read-only on the server: a change to one is
    applied by the device, `stored: "device"`)."""

    chosen = list(account)
    held = {note.id for note in account}
    taken: set[str] = set()
    for note in sorted(device, key=lambda n: -n.weight):  # a stable sort: the client's order among equal weights
        if note.id in held or any(same_note(note.text, kept.text) for kept in chosen):
            continue  # the account's (by id or words), or a repeat of a device note already sent
        if len(chosen) >= MAX_COACH_NOTES:
            break
        if coach_notes_bytes([*chosen, note]) > MAX_COACH_NOTES_BYTES:
            continue  # too large for the room left; a smaller one after it may still fit
        chosen.append(note)
        held.add(note.id)
        taken.add(note.id)
    return tuple(chosen), frozenset(taken)


def carries_memory(pack: Any) -> bool:
    """The built pack holds Orena Memory (explicit, inferred or continuity data), not only its version stamp."""

    return any(key in pack.data for key in ("explicit", "inferred", "continuity"))


def without_explicit(section: MemorySection | None) -> MemorySection | None:
    """A section whose explicit items reach the model as coach notes instead (server mode): not sent twice."""

    if section is None:
        return None
    return replace(section, explicit=(),
                   provenance=tuple(e for e in section.provenance if not str(e.get("line", "")).startswith("explicit.")))

