"""Agent sessions: a TTL cache in this process, never a table (spec §11, D7).

A session holds what the next turn needs to resolve "this word" or "the line
before": the last context, the last selection, a goal the learner stated, a
bounded list of recent tool results, the last turns as said (bounded, so the
model sees the conversation: ORENA_INTELLIGENCE_ARCHITECTURE §4-5), a
voice-session reference and a turn count. It holds no chain of thought. The
turns live in this process for the session's life and are not stored anywhere:
the durable transcript stays device memory (AGENTS.md §7, contract §10).

A session belongs to the learner who opened it. Asking for it as anyone else
answers exactly as for an id that never existed, so the cache cannot be used to
learn whether another learner's session is alive. Expiry slides with use; when
a session is gone the client starts a new one and loses nothing durable.

The cache lives in one worker process. Behind several workers a session may be
missing on another worker; that is the same as expiry, by design.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from writing_coach.agent.limits import DEFAULT_LIMITS, AgentLimits
from writing_coach.agent.pending import SETTLED_KEPT, PendingInteraction
from writing_coach.agent.schemas import AppContextSnapshot, SelectedItem


@dataclass(frozen=True)
class ToolResultRecord:
    """What a turn keeps of a tool it ran: a name, a summary, evidence ids."""

    tool: str
    summary: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversationTurn:
    """One side of one exchange, as said: what the learner wrote (or said, once voice joins) or Orena answered."""

    role: str  # "user" | "assistant"
    text: str


@dataclass(frozen=True)
class AgentSessionState:
    agent_session_id: str
    user_key: str
    created_at: float
    updated_at: float
    current_app_context: AppContextSnapshot | None = None
    last_selected_entity: SelectedItem | None = None
    active_learning_goal: str | None = None
    recent_tool_results: tuple[ToolResultRecord, ...] = ()
    voice_session_ref: str | None = field(default=None, repr=False)
    turn_count: int = 0
    address_asked: bool = False  # the learner was asked once, this session, about an address pair
    target_language: str | None = None  # the contract target the kept context belongs to
    # The offer the learner has not answered (agent/pending.py): one generic record for any action, kept until it is
    # completed, cancelled, expired or replaced - a question in between does not clear it. `settled` is the last few
    # that ended, as (id, status), so an answer that arrives twice finds nothing left to run twice.
    pending: PendingInteraction | None = None
    settled: tuple[tuple[str, str], ...] = ()
    # The turns just before this one, verbatim and bounded (architecture target §4-5): the model sees them, so a
    # follow-up ("cho ví dụ khác", "đoạn thứ 3") has something to refer to. In this process only, like the rest.
    recent_turns: tuple[ConversationTurn, ...] = ()

    def for_target(self, target: str | None) -> AgentSessionState:
        """The session as a turn in `target` may see it (dogfood gate 3.3).

        What was kept about the screen belongs to the language it was learned in: a selection, the
        tools' results, the app context, a goal and a voice session are dropped when
        the learner's target language changes, so nothing of an English context
        reaches a Chinese turn. The conversation is not that: a language change is not a new
        conversation, so the recent turns and the unanswered offer (a word names its own language)
        stay, as do who the session belongs to, its turn count and whether an address was asked.
        """

        if target is None or self.target_language == target:
            return self
        if self.target_language is None and not self.turn_count:
            return replace(self, target_language=target)
        return replace(self, target_language=target, current_app_context=None, last_selected_entity=None,
                       active_learning_goal=None, recent_tool_results=(), voice_session_ref=None)

    def with_context(self, context: AppContextSnapshot) -> AgentSessionState:
        selected = context.selected_item or self.last_selected_entity
        # The address may carry the learner's name: used for its turn, never kept (contract v5 §5.6, §10).
        kept = context.model_copy(update={"address": None}) if context.address is not None else context
        return replace(self, current_app_context=kept, last_selected_entity=selected)

    def with_tool_result(self, record: ToolResultRecord, *, limit: int) -> AgentSessionState:
        kept = (*self.recent_tool_results, record)[-limit:]
        return replace(self, recent_tool_results=kept)

    def with_address_asked(self) -> AgentSessionState:
        return replace(self, address_asked=True)

    def with_turn(self) -> AgentSessionState:
        return replace(self, turn_count=self.turn_count + 1)

    def with_exchange(self, user: str, assistant: str, limits: AgentLimits) -> AgentSessionState:
        """The learner's words and Orena's answer, appended; the oldest whole exchanges go first when the history
        holds more than `max_recent_turns` turns or `max_history_chars` characters. The newest exchange stays."""

        cap = limits.max_turn_chars
        added = (ConversationTurn("user", user[:cap]), ConversationTurn("assistant", assistant[:cap]))
        turns = (*self.recent_turns, *added)
        while len(turns) > 2 and (
            len(turns) > limits.max_recent_turns or sum(len(t.text) for t in turns) > limits.max_history_chars
        ):
            turns = turns[2:]
        return replace(self, recent_turns=turns)

    def live_pending(self) -> PendingInteraction | None:
        """The unanswered offer, unless it has been open past its turns."""

        pending = self.pending
        return pending if pending is not None and pending.live_at(self.turn_count) else None

    def with_offer(self, pending: PendingInteraction) -> AgentSessionState:
        """A new offer takes the place of the old one."""

        state = self.with_settled(self.pending, "replaced") if self.pending is not None else self
        return replace(state, pending=pending)

    def with_settled(self, pending: PendingInteraction | None, status: str) -> AgentSessionState:
        """`pending` ended as `status`: it is no longer open, and its id is remembered."""

        if pending is None:
            return self
        kept = (*self.settled, (pending.id, status))[-SETTLED_KEPT:]
        return replace(self, pending=None if self.pending is not None and self.pending.id == pending.id else self.pending,
                       settled=kept)

    def without_expired(self) -> AgentSessionState:
        if self.pending is not None and self.live_pending() is None:
            return self.with_settled(self.pending, "expired")
        return self


class SessionCache:
    def __init__(
        self,
        *,
        limits: AgentLimits = DEFAULT_LIMITS,
        clock: Callable[[], float] = time.monotonic,
        new_id: Callable[[], str] = lambda: secrets.token_urlsafe(24),
    ) -> None:
        self._ttl = limits.session_ttl_seconds
        self._max = limits.max_sessions
        self._tool_limit = limits.max_recent_tool_results
        self._clock = clock
        self._new_id = new_id
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, AgentSessionState] = OrderedDict()

    def __len__(self) -> int:
        with self._lock:
            self._purge(self._clock())
            return len(self._sessions)

    def open(self, session_id: str | None, user_key: str) -> tuple[AgentSessionState, bool]:
        """The learner's live session for `session_id`, or a new one.

        Returns `(state, created)`. A missing, expired or foreign id gives a new
        session with a new id; the foreign session is left untouched.
        """

        if not user_key:
            raise ValueError("a session needs the authenticated learner")
        with self._lock:
            now = self._clock()
            self._purge(now)
            if session_id is not None:
                existing = self._sessions.get(session_id)
                if existing is not None and existing.user_key == user_key:
                    touched = replace(existing, updated_at=now)
                    self._store(touched)
                    return touched, False
            state = AgentSessionState(
                agent_session_id=self._fresh_id(), user_key=user_key, created_at=now, updated_at=now
            )
            self._store(state)
            return state, True

    def get(self, session_id: str, user_key: str) -> AgentSessionState | None:
        with self._lock:
            self._purge(self._clock())
            state = self._sessions.get(session_id)
            if state is None or state.user_key != user_key:
                return None
            return state

    def save(self, state: AgentSessionState) -> AgentSessionState:
        """Store a changed state; its owner must be the one who opened it."""

        with self._lock:
            now = self._clock()
            self._purge(now)
            current = self._sessions.get(state.agent_session_id)
            if current is None or current.user_key != state.user_key:
                raise KeyError("session expired or not this learner's")
            bounded = state
            if len(state.recent_tool_results) > self._tool_limit:
                bounded = replace(state, recent_tool_results=state.recent_tool_results[-self._tool_limit :])
            stored = replace(bounded, updated_at=now)
            self._store(stored)
            return stored

    def update(
        self, session_id: str, user_key: str, change: Callable[[AgentSessionState], AgentSessionState]
    ) -> AgentSessionState | None:
        """Apply `change` to the stored state under the lock (read-modify-write).

        Two turns of one session finishing together each add to what the other
        stored, instead of the later one overwriting the earlier. None when the
        session is gone or not this learner's.
        """

        with self._lock:
            now = self._clock()
            self._purge(now)
            current = self._sessions.get(session_id)
            if current is None or current.user_key != user_key:
                return None
            changed = change(current)
            if changed.agent_session_id != session_id or changed.user_key != user_key:
                raise ValueError("a session change may not move the session")
            kept = changed.recent_tool_results[-self._tool_limit :]
            stored = replace(changed, recent_tool_results=kept, updated_at=now)
            self._store(stored)
            return stored

    def record_tool_result(self, state: AgentSessionState, record: ToolResultRecord) -> AgentSessionState:
        return self.save(state.with_tool_result(record, limit=self._tool_limit))

    def close(self, session_id: str, user_key: str) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or state.user_key != user_key:
                return False
            del self._sessions[session_id]
            return True

    # --- internals (lock held) ---------------------------------------------

    def _fresh_id(self) -> str:
        while True:
            candidate = self._new_id()
            if candidate not in self._sessions:
                return candidate

    def _store(self, state: AgentSessionState) -> None:
        self._sessions[state.agent_session_id] = state
        self._sessions.move_to_end(state.agent_session_id)
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)

    def _purge(self, now: float) -> None:
        # Every store moves its session to the end with the current time, so
        # the order is oldest-touched first and expiry stops at the first live one.
        while self._sessions:
            key, state = next(iter(self._sessions.items()))
            if now - state.updated_at < self._ttl:
                return
            del self._sessions[key]


def describe(state: AgentSessionState) -> dict[str, Any]:
    """A log-safe description: counts and ids of kinds, never learner content."""

    return {
        "agent_session_id": state.agent_session_id,
        "turn_count": state.turn_count,
        "recent_tool_results": len(state.recent_tool_results),
        "has_context": state.current_app_context is not None,
        "has_voice_session": state.voice_session_ref is not None,
    }
