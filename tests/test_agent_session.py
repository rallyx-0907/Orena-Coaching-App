"""Agent sessions: an owner-bound TTL cache, never a table (spec §11, D7)."""

from __future__ import annotations

import itertools
import threading

import pytest

from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.schemas import AppContextSnapshot, SelectedItem
from writing_coach.agent.session import SessionCache, ToolResultRecord, describe


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def cache(clock=None, **limits):
    counter = itertools.count(1)
    return SessionCache(
        limits=AgentLimits(**{"session_ttl_seconds": 60, **limits}),
        clock=clock or Clock(),
        new_id=lambda: f"s{next(counter)}",
    )


def context(text="我"):
    return AppContextSnapshot.model_validate(
        {
            "surface": "speaking.workspace",
            "locale": {"interface": "vi", "support": "vi", "target": "zh-CN"},
            "selected_item": {"type": "word", "text": text},
        }
    )


def test_open_creates_then_resumes():
    sessions = cache()
    state, created = sessions.open(None, "u1")
    assert created and state.agent_session_id == "s1" and state.turn_count == 0
    again, created = sessions.open("s1", "u1")
    assert not created and again.agent_session_id == "s1"


def test_a_session_belongs_to_its_learner():
    sessions = cache()
    mine, _ = sessions.open(None, "u1")
    theirs, created = sessions.open(mine.agent_session_id, "u2")
    assert created and theirs.agent_session_id != mine.agent_session_id
    assert sessions.get(mine.agent_session_id, "u2") is None
    assert sessions.get(mine.agent_session_id, "u1") is not None  # untouched by the attempt
    assert not sessions.close(mine.agent_session_id, "u2")
    with pytest.raises(KeyError):
        sessions.save(type(mine)(**{**mine.__dict__, "user_key": "u2"}))


def test_expiry_slides_with_use():
    clock = Clock()
    sessions = cache(clock)
    state, _ = sessions.open(None, "u1")
    clock.now += 50
    sessions.open(state.agent_session_id, "u1")
    clock.now += 50
    assert sessions.get(state.agent_session_id, "u1") is not None
    clock.now += 61
    assert sessions.get(state.agent_session_id, "u1") is None
    fresh, created = sessions.open(state.agent_session_id, "u1")
    assert created and fresh.agent_session_id != state.agent_session_id


def test_the_oldest_session_is_evicted_at_capacity():
    clock = Clock()
    sessions = cache(clock, max_sessions=2)
    first, _ = sessions.open(None, "u1")
    clock.now += 1
    second, _ = sessions.open(None, "u2")
    clock.now += 1
    sessions.open(first.agent_session_id, "u1")  # touched: now the newest
    clock.now += 1
    sessions.open(None, "u3")
    assert sessions.get(second.agent_session_id, "u2") is None
    assert sessions.get(first.agent_session_id, "u1") is not None
    assert len(sessions) == 2


def test_context_keeps_the_last_selection():
    sessions = cache()
    state, _ = sessions.open(None, "u1")
    state = sessions.save(state.with_context(context("我")).with_turn())
    without = AppContextSnapshot.model_validate(
        {"surface": "speaking.workspace", "locale": {"interface": "vi", "support": "vi", "target": "zh-CN"}}
    )
    state = sessions.save(state.with_context(without).with_turn())
    assert state.last_selected_entity == SelectedItem(type="word", text="我")
    assert state.turn_count == 2


def test_recent_tool_results_are_bounded():
    sessions = cache(max_recent_tool_results=3)
    state, _ = sessions.open(None, "u1")
    for i in range(5):
        state = sessions.record_tool_result(state, ToolResultRecord(tool=f"t{i}", summary="s", evidence_ids=(f"e{i}",)))
    assert [r.tool for r in state.recent_tool_results] == ["t2", "t3", "t4"]
    oversized = state.__class__(**{**state.__dict__, "recent_tool_results": state.recent_tool_results * 3})
    assert len(sessions.save(oversized).recent_tool_results) == 3


def test_a_session_needs_a_learner():
    with pytest.raises(ValueError):
        cache().open(None, "")


def test_ids_are_unguessable_by_default():
    sessions = SessionCache()
    a, _ = sessions.open(None, "u1")
    b, _ = sessions.open(None, "u1")
    assert a.agent_session_id != b.agent_session_id and len(a.agent_session_id) >= 32


def test_description_carries_no_learner_content():
    sessions = cache()
    state, _ = sessions.open(None, "u1")
    state = sessions.save(state.with_context(context("秘密")))
    described = describe(state)
    assert "秘密" not in repr(described) and "u1" not in repr(described)
    assert "voice_session_ref" not in repr(state)


def test_concurrent_opens_are_safe():
    sessions = SessionCache(limits=AgentLimits(max_sessions=10_000))
    errors = []

    def worker(user):
        try:
            for _ in range(200):
                state, _ = sessions.open(None, user)
                sessions.save(state.with_turn())
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(f"u{i}",)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors and len(sessions) == 1600
