"""Each turn leaves one timeline record: where its time went, and nothing the learner wrote."""

from __future__ import annotations

import itertools

from writing_coach.agent.fake_provider import call_tools, reply
from tests.test_agent_turn import VI, hermetic, registry, run, runtime, turn_request  # noqa: F401 - fixture


def _recorded(rounds, request=None, tools=None):
    rt, provider = runtime(rounds, tools=tools)
    ticks = itertools.count()
    rt.clock = lambda: next(ticks) * 0.01  # 10 ms per reading of the clock
    recorded = []
    rt.record_turn = lambda user_key, record: recorded.append((user_key, record))
    events = run(rt, request)
    return events, recorded


def test_a_tool_turn_records_its_rounds_tools_and_first_visible_answer():
    events, recorded = _recorded([call_tools(("c1", "get_test_items", {})), reply("Bạn sai thanh điệu ở 是.")],
                                 tools=registry())
    assert len(recorded) == 1
    user_key, record = recorded[0]
    assert user_key == VI.user_key
    assert record["outcome"] == "success"
    assert record["tools"] == ["get_test_items"]
    assert record["provider_rounds"] == 2 and len(record["rounds"]) == 2
    assert record["rounds"][0]["tool_calls"] == 1
    names = [m["name"] for m in record["marks"]]
    assert names.index("context_built") < names.index("tool_start") < names.index("tool_end") < names.index("final_ready")
    assert record["first_visible_ms"] is not None and record["first_visible_ms"] <= record["total_ms"]
    assert record["context_built_ms"] <= record["rounds"][0]["start_ms"] <= record["rounds"][0]["first_event_ms"]


def test_the_record_holds_no_learner_words():
    message = "Tại sao tôi sai từ này?"
    _, recorded = _recorded([reply("Một câu trả lời riêng tư.")], request=turn_request(message))
    text = repr(recorded)
    assert message not in text and "riêng tư" not in text and "是" not in text


def test_a_failed_recorder_never_costs_the_answer():
    rt, _ = runtime([reply("Ok.")])

    def broken(user_key, record):
        raise RuntimeError("database down")

    rt.record_turn = broken
    events = run(rt)
    assert events[-1].name == "done"
