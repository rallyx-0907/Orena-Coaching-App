"""Orena Memory's store: the repository port and an in-memory fake (ORENA_MEMORY.md rev 4.1 §4, §6; D-222).

The port is what M2/M3 build on. The PostgreSQL repository comes with the migration (§9), behind its own review and
the owner's authorisation; until then nothing in the app constructs a store, and `InMemoryMemoryStore` exists so the
semantics the proposal fixes can be tested now and the PostgreSQL repository can later be run against the same tests:

- **scope** - every read and write is by (`user_id`, `incarnation_id`); with no active incarnation there is no scope,
  and memory is off (fail closed; `memory_scope`);
- **version** - every write, delete, pin, switch change and materialisation bumps the learner's version in the same
  operation, so a pack built at another version is rebuilt on any worker or device (§4.4, §5.2);
- **switch** - OFF: no new item, summary or materialisation; deleting and the switch itself still work (§6);
- **suppression** - deleting a continuity or inferred item leaves an HMAC key of its slot and value, no text, until
  its former expiry; a later materialisation of that (slot, value) writes nothing; bulk delete keeps the keys (§4.1);
- **tombstones** - deleting a session's summary leaves a tombstone for every language part of it, and a checkpoint
  never writes over a tombstone, a finalised row, or a higher `turns_covered` (§4.2);
- **expiry** - reads filter `expires_at`; nothing is swept here (a bounded sweep belongs to the repository);
- **snapshot** - a pack reads state, items and summaries in one operation, so its contents are exactly those of the
  version it carries: a delete committed on another worker either is in it or bumps the version past it (§5.2);
- **finalisation** - an open summary idle 30 minutes (so, too, one 24 hours after its last checkpoint) becomes
  final as a stored transition (a later checkpoint is a no-op); nothing is finalised while memory is OFF.

Pinning (continuity to explicit) is not in this port yet: rev 4.1 §3.4 makes the explicit item the learner's own words
with the slot and code kept, which needs the M3 representation; it comes with it.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any, Protocol

from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_slots import SINGLE_VALUED, SLOTS
from writing_coach.agent.memory_summary import without_deleted_item

EXPLICIT, INFERRED, CONTINUITY = "explicit", "inferred", "continuity"
ANY_LANGUAGE = "*"
CONTINUITY_TTL = timedelta(days=14)  # G10
INFERRED_SUPPRESSION = timedelta(days=30)
SUMMARY_TTL = timedelta(days=60)
TOMBSTONE_TTL = timedelta(days=2)
IDLE_FINAL = timedelta(minutes=30)  # an open summary idle this long becomes final (the session cache TTL)
RENDER_AGE = timedelta(days=14)
LIMITS = {EXPLICIT: 30, INFERRED: 10, CONTINUITY: 20}
MIN_TURNS = 2  # a session with fewer learner turns writes no summary
# Slots holding one value per learner and language (§4.1): a new value replaces the old one.
SINGLE_VALUED_SLOTS = SINGLE_VALUED | {"explanation_length", "support_language", "correction_timing"}


class MemoryOff(Exception):
    """Memory is switched off for this learner: nothing new is written."""


class MemoryLimit(Exception):
    """The learner already keeps the most explicit items allowed; they delete one first."""


@dataclass(frozen=True)
class MemoryScope:
    user_id: str
    incarnation_id: str


def memory_scope(user_id: str | None, incarnation_id: str | None) -> MemoryScope | None:
    """The scope, or None - memory off - when no active incarnation resolves (no fallback to user-only scope)."""

    return MemoryScope(str(user_id), str(incarnation_id)) if user_id and incarnation_id else None


@dataclass(frozen=True)
class MemoryState:
    enabled: bool = True
    version: int = 0


@dataclass(frozen=True)
class MemoryItem:
    id: str
    language_code: str
    cls: str
    kind: str
    slot: str | None
    text: str  # explicit: the learner's words; continuity: the slot's code; inferred: the rule's template
    source: str
    key_version: int
    value_key: str
    created_at: datetime
    expires_at: datetime | None = None
    provenance: tuple[str, ...] = ()  # distinct session ids, as a set


@dataclass(frozen=True)
class SessionSummary:
    agent_session_id: str
    language_code: str
    state: str  # open | final | deleted
    turns_covered: int
    summary: Mapping[str, Any] | None
    last_checkpoint_at: datetime
    finalised_at: datetime | None
    expires_at: datetime


@dataclass(frozen=True)
class MemorySnapshot:
    """One consistent read: everything in it belongs to `state.version`."""

    state: MemoryState
    items: tuple[MemoryItem, ...]
    summaries: tuple[SessionSummary, ...]


@dataclass(frozen=True)
class _Suppression:
    language_code: str
    cls: str
    slot: str | None
    key_version: int
    value_key: str
    expires_at: datetime


class MemoryRepository(Protocol):
    def state(self, scope: MemoryScope) -> MemoryState: ...

    def items(self, scope: MemoryScope, language: str, now: datetime) -> list[MemoryItem]: ...

    def summaries(self, scope: MemoryScope, language: str, now: datetime, limit: int) -> list[SessionSummary]: ...

    def set_enabled(self, scope: MemoryScope, enabled: bool) -> MemoryState: ...

    def add_explicit(self, scope: MemoryScope, *, language: str, kind: str, text: str, slot: str | None,
                     source: str, now: datetime) -> MemoryItem: ...  # fmt: skip

    def delete_item(self, scope: MemoryScope, item_id: str, now: datetime) -> bool: ...

    def snapshot(self, scope: MemoryScope, language: str, now: datetime, sessions: int) -> MemorySnapshot: ...

    def delete_all(self, scope: MemoryScope, what: str, now: datetime) -> int: ...

    def checkpoint(self, scope: MemoryScope, *, agent_session_id: str, language: str, turns_covered: int,
                   summary: Mapping[str, Any], context: Sequence[tuple[str, str]], now: datetime) -> bool: ...  # fmt: skip

    def finalise(self, scope: MemoryScope, agent_session_id: str, now: datetime) -> int: ...

    def delete_summary(self, scope: MemoryScope, agent_session_id: str, now: datetime) -> int: ...


@dataclass
class _Learner:
    state: MemoryState = field(default_factory=MemoryState)
    items: dict[str, MemoryItem] = field(default_factory=dict)
    suppressions: list[_Suppression] = field(default_factory=list)
    summaries: dict[tuple[str, str], SessionSummary] = field(default_factory=dict)  # (session, language)


def _live(expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is None or expires_at > now


class InMemoryMemoryStore:
    """The fake: one lock stands in for the repository's transaction, so each method is one atomic operation."""

    def __init__(self, keys: MemoryKeys) -> None:
        self._keys = keys
        self._lock = threading.Lock()
        self._learners: dict[MemoryScope, _Learner] = {}

    # --- helpers (called with the lock held) ---------------------------------------------------------------------

    def _learner(self, scope: MemoryScope) -> _Learner:
        return self._learners.setdefault(scope, _Learner())

    @staticmethod
    def _bump(learner: _Learner) -> None:
        learner.state = replace(learner.state, version=learner.state.version + 1)

    def _suppressed(self, learner: _Learner, language: str, cls: str, slot: str | None, value: str,
                    now: datetime) -> bool:  # fmt: skip
        return any(
            s.language_code == language and s.cls == cls and s.slot == slot and _live(s.expires_at, now)
            and self._keys.matches(slot or "", value, s.key_version, s.value_key)
            for s in learner.suppressions
        )

    def _same_value(self, item: MemoryItem, slot: str | None, value: str) -> bool:
        return item.slot == slot and self._keys.matches(slot or "", value, item.key_version, item.value_key)

    def _holder(self, learner: _Learner, language: str, cls: str, slot: str | None, value: str,
                now: datetime) -> MemoryItem | None:  # fmt: skip
        """The live item this (slot, value) dedupes to: the slot's item for a single-valued slot, else the same value."""

        for item in learner.items.values():
            if item.language_code != language or item.cls != cls or not _live(item.expires_at, now):
                continue
            if slot in SINGLE_VALUED_SLOTS and item.slot == slot:
                return item
            if self._same_value(item, slot, value):
                return item
        return None

    def _count(self, learner: _Learner, language: str, cls: str, now: datetime) -> list[MemoryItem]:
        return [i for i in learner.items.values()
                if i.language_code == language and i.cls == cls and _live(i.expires_at, now)]  # fmt: skip

    def _new(self, *, language: str, cls: str, kind: str, slot: str | None, text: str, source: str,
             now: datetime, expires_at: datetime | None, provenance: tuple[str, ...] = ()) -> MemoryItem:  # fmt: skip
        version, value_key = self._keys.stamp(slot or "", text)
        return MemoryItem(id=str(uuid.uuid4()), language_code=language, cls=cls, kind=kind, slot=slot, text=text,
                          source=source, key_version=version, value_key=value_key, created_at=now,
                          expires_at=expires_at, provenance=provenance)  # fmt: skip

    def _remove(self, learner: _Learner, item: MemoryItem, now: datetime) -> None:
        """Delete an item; continuity and inferred leave a suppression key, and a continuity item's code leaves
        the summaries that carry it - in the same operation, while the (slot, code) is in hand (§3.4)."""

        del learner.items[item.id]
        if item.cls in (CONTINUITY, INFERRED):
            until = item.expires_at if item.cls == CONTINUITY and item.expires_at else now + INFERRED_SUPPRESSION
            learner.suppressions.append(_Suppression(item.language_code, item.cls, item.slot, item.key_version,
                                                     item.value_key, until))  # fmt: skip
        if item.cls == CONTINUITY and item.slot:
            for key, row in learner.summaries.items():
                if row.summary is not None and item.language_code in (row.language_code, ANY_LANGUAGE):
                    learner.summaries[key] = replace(row, summary=without_deleted_item(row.summary, item.slot,
                                                                                       item.text))  # fmt: skip

    # --- reads ---------------------------------------------------------------------------------------------------

    def state(self, scope: MemoryScope) -> MemoryState:
        with self._lock:
            return self._learner(scope).state

    def _items(self, learner: _Learner, language: str, now: datetime) -> list[MemoryItem]:
        found = [i for i in learner.items.values()
                 if i.language_code in (language, ANY_LANGUAGE) and _live(i.expires_at, now)]  # fmt: skip
        return sorted(found, key=lambda i: (i.cls, i.kind, i.created_at, i.id))

    @staticmethod
    def _settle(learner: _Learner, now: datetime) -> None:
        """Open summaries idle 30 minutes since their last checkpoint become final - stored, so a later
        checkpoint is a no-op. Not while memory is OFF: stored memory stays untouched (§6). The version is not
        bumped: what a pack renders does not change (an idle summary already read as final)."""

        if not learner.state.enabled:
            return
        for key, row in learner.summaries.items():
            if row.state == "open" and now - row.last_checkpoint_at >= IDLE_FINAL:
                ended = row.last_checkpoint_at + IDLE_FINAL
                learner.summaries[key] = replace(row, state="final", finalised_at=ended, expires_at=ended + SUMMARY_TTL)

    def _summaries(self, learner: _Learner, language: str, now: datetime, limit: int) -> list[SessionSummary]:
        shown = [row for row in learner.summaries.values()
                 if row.language_code == language and row.state == "final" and row.summary
                 and _live(row.expires_at, now) and row.finalised_at and now - row.finalised_at <= RENDER_AGE]
        return sorted(shown, key=lambda row: row.finalised_at, reverse=True)[:limit]  # fmt: skip

    def items(self, scope: MemoryScope, language: str, now: datetime) -> list[MemoryItem]:
        with self._lock:
            return self._items(self._learner(scope), language, now)

    def summaries(self, scope: MemoryScope, language: str, now: datetime, limit: int) -> list[SessionSummary]:
        """Finalised summaries of the language, newest first (idle ones finalised first). Never a tombstone, never
        one older than the render age."""

        with self._lock:
            learner = self._learner(scope)
            self._settle(learner, now)
            return self._summaries(learner, language, now, limit)

    def snapshot(self, scope: MemoryScope, language: str, now: datetime, sessions: int) -> MemorySnapshot:
        with self._lock:
            learner = self._learner(scope)
            self._settle(learner, now)
            return MemorySnapshot(state=learner.state, items=tuple(self._items(learner, language, now)),
                                  summaries=tuple(self._summaries(learner, language, now, sessions)))  # fmt: skip

    # --- writes --------------------------------------------------------------------------------------------------

    def set_enabled(self, scope: MemoryScope, enabled: bool) -> MemoryState:
        with self._lock:
            learner = self._learner(scope)
            learner.state = MemoryState(enabled=bool(enabled), version=learner.state.version + 1)
            return learner.state

    def add_explicit(self, scope: MemoryScope, *, language: str, kind: str, text: str, slot: str | None,
                     source: str, now: datetime) -> MemoryItem:  # fmt: skip
        with self._lock:
            learner = self._learner(scope)
            if not learner.state.enabled:
                raise MemoryOff
            held = self._holder(learner, language, EXPLICIT, slot, text, now)
            if held is not None and self._same_value(held, slot, text):
                return held  # a retried remember_note (same words) does not duplicate
            if held is None and len(self._count(learner, language, EXPLICIT, now)) >= LIMITS[EXPLICIT]:
                raise MemoryLimit
            if held is not None:
                del learner.items[held.id]  # a single-valued slot: the learner's latest choice wins
            item = self._new(language=language, cls=EXPLICIT, kind=kind, slot=slot, text=text, source=source,
                             now=now, expires_at=None)  # fmt: skip
            learner.items[item.id] = item
            self._bump(learner)
            return item

    def delete_item(self, scope: MemoryScope, item_id: str, now: datetime) -> bool:
        with self._lock:  # allowed while memory is OFF (§6)
            learner = self._learner(scope)
            item = learner.items.get(item_id)
            if item is None:
                return False
            self._remove(learner, item, now)
            self._bump(learner)
            return True

    def pin(self, scope: MemoryScope, item_id: str, now: datetime) -> MemoryItem | None:
        with self._lock:
            learner = self._learner(scope)
            if not learner.state.enabled:
                raise MemoryOff
            item = learner.items.get(item_id)
            if item is None or item.cls != CONTINUITY:
                return None
            held = self._holder(learner, item.language_code, EXPLICIT, item.slot, item.text, now)
            if held is not None:
                del learner.items[held.id]
            del learner.items[item.id]
            pinned = replace(item, cls=EXPLICIT, source="learner_pinned", expires_at=None)
            learner.items[pinned.id] = pinned
            self._bump(learner)
            return pinned

    def delete_all(self, scope: MemoryScope, what: str, now: datetime) -> int:
        """`items`, `sessions` or `all`. Suppression keys are kept; summaries become tombstones."""

        if what not in ("items", "sessions", "all"):
            raise ValueError(what)
        with self._lock:
            learner = self._learner(scope)
            removed = 0
            if what in ("items", "all"):
                for item in list(learner.items.values()):
                    self._remove(learner, item, now)
                    removed += 1
            if what in ("sessions", "all"):
                for key, row in list(learner.summaries.items()):
                    if row.state != "deleted":
                        learner.summaries[key] = self._tombstone(row, now)
                        self._session_tombstone(learner, key[0], now)
                        removed += 1
            self._bump(learner)
            return removed

    @staticmethod
    def _tombstone(row: SessionSummary, now: datetime) -> SessionSummary:
        return replace(row, state="deleted", summary=None, expires_at=now + TOMBSTONE_TTL)

    def checkpoint(self, scope: MemoryScope, *, agent_session_id: str, language: str, turns_covered: int,
                   summary: Mapping[str, Any], context: Sequence[tuple[str, str]], now: datetime) -> bool:  # fmt: skip
        """One session's language part, as one operation: nothing when memory is OFF, when the row is a tombstone or
        final, or when it already covers as many turns; else the summary, then the grounded context items that no
        suppression key blocks, then the version."""

        if turns_covered < MIN_TURNS:
            return False
        with self._lock:
            learner = self._learner(scope)
            if not learner.state.enabled:
                return False
            self._settle(learner, now)  # an idle part is final before this checkpoint is weighed
            whole = learner.summaries.get((agent_session_id, ANY_LANGUAGE))
            if whole is not None and _live(whole.expires_at, now):
                return False  # the learner deleted this session: no language part of it is written again
            key = (agent_session_id, language)
            row = learner.summaries.get(key)
            if row is not None and (row.state != "open" or row.turns_covered >= turns_covered):
                return False
            learner.summaries[key] = SessionSummary(
                agent_session_id=agent_session_id, language_code=language, state="open", turns_covered=turns_covered,
                summary=dict(summary), last_checkpoint_at=now, finalised_at=None, expires_at=now + SUMMARY_TTL)
            for slot, code in context:
                self._materialise(learner, agent_session_id, language, slot, code, now)
            self._bump(learner)
            return True

    def _materialise(self, learner: _Learner, session: str, language: str, slot: str, code: str,
                     now: datetime) -> None:  # fmt: skip
        if code not in SLOTS.get(slot, ()) or self._suppressed(learner, language, CONTINUITY, slot, code, now):
            return
        until = now + CONTINUITY_TTL
        held = self._holder(learner, language, CONTINUITY, slot, code, now)
        if held is not None and self._same_value(held, slot, code):
            if session not in held.provenance:  # another session said it again: extend, never shorten
                learner.items[held.id] = replace(held, provenance=held.provenance + (session,),
                                                 expires_at=max(held.expires_at or until, until))  # fmt: skip
            return
        if held is not None:
            del learner.items[held.id]  # a single-valued slot changed value
        live = sorted(self._count(learner, language, CONTINUITY, now), key=lambda i: (i.expires_at or until, i.id))
        while len(live) >= LIMITS[CONTINUITY]:
            del learner.items[live.pop(0).id]  # the one expiring soonest gives way
        item = self._new(language=language, cls=CONTINUITY, kind="context", slot=slot, text=code, source="summary",
                         now=now, expires_at=until, provenance=(session,))  # fmt: skip
        learner.items[item.id] = item

    def finalise(self, scope: MemoryScope, agent_session_id: str, now: datetime) -> int:
        with self._lock:
            learner = self._learner(scope)
            if not learner.state.enabled:
                return 0  # memory OFF: stored memory stays untouched
            done = 0
            for key, row in learner.summaries.items():
                if key[0] == agent_session_id and row.state == "open":
                    learner.summaries[key] = replace(row, state="final", finalised_at=now,
                                                     expires_at=now + SUMMARY_TTL)  # fmt: skip
                    done += 1
            if done:
                self._bump(learner)
            return done

    def delete_summary(self, scope: MemoryScope, agent_session_id: str, now: datetime) -> int:
        """Every language part of the session becomes a tombstone (allowed while memory is OFF)."""

        with self._lock:
            learner = self._learner(scope)
            parts = [key for key in learner.summaries if key[0] == agent_session_id]
            for key in parts:
                learner.summaries[key] = self._tombstone(learner.summaries[key], now)
            self._session_tombstone(learner, agent_session_id, now)
            self._bump(learner)
            return len(parts)

    @staticmethod
    def _session_tombstone(learner: _Learner, agent_session_id: str, now: datetime) -> None:
        """A tombstone for the whole session, so a checkpoint in any language - including one not written yet, or
        one already in flight - writes nothing."""

        learner.summaries[(agent_session_id, ANY_LANGUAGE)] = SessionSummary(
            agent_session_id=agent_session_id, language_code=ANY_LANGUAGE, state="deleted", turns_covered=0,
            summary=None, last_checkpoint_at=now, finalised_at=None, expires_at=now + TOMBSTONE_TTL)

    def versions_in_use(self) -> set[int]:
        """Key versions any row or suppression key still uses (for `MemoryKeys.check_in_use`)."""

        with self._lock:
            used = set()
            for learner in self._learners.values():
                used |= {i.key_version for i in learner.items.values()}
                used |= {s.key_version for s in learner.suppressions}
            return used


@dataclass(frozen=True)
class MemorySection:
    """What a pack carries from Orena Memory (§5.1, §5.3), read at one version of the learner's memory."""

    explicit: tuple[Mapping[str, Any], ...] = ()
    inferred: tuple[Mapping[str, Any], ...] = ()
    continuity_items: tuple[Mapping[str, Any], ...] = ()
    sessions: tuple[Mapping[str, Any], ...] = ()
    provenance: tuple[Mapping[str, Any], ...] = ()  # one entry per rendered item: its row, kept on the server
    version: int = 0


def memory_section(store: MemoryRepository, scope: MemoryScope | None, language: str, now: datetime, *,
                   sessions: int = 2) -> MemorySection | None:  # fmt: skip
    """The learner's memory for a pack, or None when there is none to send: no scope (fail closed) or memory OFF."""

    if scope is None:
        return None
    read = store.snapshot(scope, language, now, sessions)  # one consistent read at one version
    state = read.state
    if not state.enabled:
        return None
    by_class: dict[str, list[MemoryItem]] = {EXPLICIT: [], INFERRED: [], CONTINUITY: []}
    for item in read.items:
        by_class[item.cls].append(item)
    by_class[EXPLICIT].sort(key=lambda i: (i.created_at, i.id))
    ordered = [*reversed(by_class[EXPLICIT]), *by_class[INFERRED], *by_class[CONTINUITY]]  # as rendered
    proof = [{"line": f"{item.cls}.{item.id}", "source": "learner_memories", "id": item.id, "via": item.source}
             for item in ordered]
    rows = read.summaries
    proof += [{"line": f"session.{row.agent_session_id}", "source": "orena_session_summaries",
               "id": row.agent_session_id} for row in rows]  # fmt: skip
    return MemorySection(
        explicit=tuple({"kind": i.kind, "text": i.text} for i in reversed(by_class[EXPLICIT])),  # oldest trimmed first
        inferred=tuple({"kind": i.kind, "text": i.text} for i in by_class[INFERRED]),
        continuity_items=tuple({"slot": i.slot, "code": i.text} for i in by_class[CONTINUITY]),
        sessions=tuple({"day": (row.finalised_at or row.last_checkpoint_at).date().isoformat(),
                        **{key: row.summary.get(key) for key in ("practised", "focus", "open_task")}}
                       for row in rows if row.summary),  # fmt: skip
        provenance=tuple(proof),
        version=state.version,
    )

