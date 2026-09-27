"""One agent turn, end to end on the fake provider (spec §20, contract §4)."""

from __future__ import annotations

import itertools
import socket
from types import MappingProxyType

import pytest
from pydantic import BaseModel, ConfigDict

from writing_coach.agent import learner_copy
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.errors import ProviderUnavailable
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, call_tools, fail, reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import AgentTool, LearnerScope, ToolEvidence, ToolPermission, ToolRegistry, ToolResult
from writing_coach.agent.turn import AgentRuntime
from writing_coach.core.request_context import current_user_key

VI = LearnerScope(user_key="learner-1", language="zh")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a hermetic agent test opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    catalog = dict(learner_copy.CATALOG)
    for key, words in (("tool.get_test_items", "Đang xem"), ("result.get_test_items", "Mục: {n}")):
        catalog[key] = learner_copy._entry(learner_copy.CopyLayer.INTERFACE, {"en": words, "vi": words, "zh-CN": words})
    monkeypatch.setattr(learner_copy, "CATALOG", MappingProxyType(catalog))


class ItemArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = 2


def registry(seen=None, fail_with=None):
    def handler(learner, args):
        if seen is not None:
            seen.append((learner, current_user_key(), args))
        if fail_with:
            raise fail_with
        return ToolResult(
            summary="two flagged syllables",
            data={"items": ["是", "美"], "producer": "internal-model"},
            evidence=(
                ToolEvidence("x1", "speech.pronunciation", {"attempt_id": "a1", "path": "words[0]"}, {"score": 6, "flagged": True}),
                ToolEvidence("x2", "speech.pronunciation", {"attempt_id": "a1", "path": "words[1]"}, {"score": 71, "flagged": False}),
            ),
            count=2,
        )

    tools = ToolRegistry()
    tools.register(
        AgentTool(
            name="get_test_items",
            description="Test items.",
            input_model=ItemArgs,
            permission=ToolPermission.READ_ONLY,
            backed_by="writing_coach.becoming_library:library_summary",
            languages=("en", "zh-CN"),
            label_key="tool.get_test_items",
            handler=handler,
        )
    )
    return tools


def turn_request(message="Tại sao tôi sai từ này?", actions=("navigate", "save_word", "play_model"), **extra):
    body = {
        "contract_version": 1,
        "message": message,
        "client": {
            "ui_version": "t",
            "supported_actions": list(actions),
            "supported_intents": ["vocabulary.review_due", "writing.revision"],
        },
        "context": {
            "surface": "speaking.word_detail",
            "locale": {"interface": "vi", "support": "vi", "target": "zh-CN", "content": "zh-CN"},
            "selected_item": {"type": "word", "text": "是"},
        },
    }
    body.update(extra)
    return TurnRequest.model_validate(body)


def runtime(rounds, *, tools=None, limits=None, meter=None, clock=None):
    ids = itertools.count(1)
    provider = FakeAgentTurnProvider(rounds)
    rt = AgentRuntime(
        provider=provider,
        tools=tools if tools is not None else registry(),
        capabilities=load_capability_registry(),
        sessions=SessionCache(new_id=lambda: f"s{next(ids)}"),
        limits=limits or AgentLimits(),
        meter=meter,
        new_trace_id=lambda: "trace1",
        **({"clock": clock} if clock else {}),
    )
    return rt, provider


def run(rt, request=None, learner=VI, **kwargs):
    return list(rt.run(request or turn_request(), learner, **kwargs))


def names(events):
    return [e.name for e in events if e.name != "segment_delta"]


def test_evidence_then_claim_then_actions():
    seen = []
    rt, provider = runtime(
        [
            call_tools(("c1", "get_test_items", {"limit": 2})),
            (
                ToolCallRequest("c2", "cite_evidence", {"evidence_ids": ["e1"]}),
                ToolCallRequest("c3", "set_voice_style", {"voice_style": "gentle_correction"}),
                ToolCallRequest("c4", "add_reference", {"text": "是", "lang": "zh-CN"}),
                ToolCallRequest("c5", "propose_action", {"type": "play_model", "payload": {"content_id": "c9", "item_id": "i1"}}),
                TurnFinished(0, 5, "tool_calls"),
            ),
            reply("Azure đánh dấu 是 là phát âm sai, điểm 6/100."),
        ],
        tools=registry(seen),
    )
    events = run(rt)
    assert names(events) == [
        "session", "tool_call", "tool_result", "evidence", "evidence",
        "segment_end", "segment_end", "action", "done",
    ]  # fmt: skip
    tool_call, tool_result = events[1], events[2]
    assert tool_call.label == "Đang xem" and tool_result.summary == "Mục: 2"
    assert tool_result.evidence_ids == ["e1", "e2"]
    claim, reference = [e for e in events if e.name == "segment_end"]
    assert (claim.voice_style, claim.lang) == ("gentle_correction", "vi")
    assert (reference.text, reference.lang, reference.voice_style) == ("是", "zh-CN", "reference")
    action = next(e for e in events if e.name == "action")
    assert (action.type, action.label, action.risk) == ("play_model", "Nghe mẫu", "LOW")
    # the tool ran as the authenticated learner, inside that learner's request context
    assert seen[0][0] is VI and seen[0][1] == "learner-1"
    # what the model saw of the tool: redacted, with the turn's evidence ids
    tool_message = provider.requests[1].messages[-1].content
    assert '"e1"' in tool_message and "internal-model" not in tool_message


def test_a_claim_cannot_cite_evidence_that_was_never_read():
    rt, provider = runtime(
        [
            (ToolCallRequest("c1", "cite_evidence", {"evidence_ids": ["e1"]}), TurnFinished(0, 1, "tool_calls")),
            reply("Mình chưa có kết quả chấm cho từ này."),
        ]
    )
    events = run(rt)
    assert names(events) == ["session", "segment_end", "done"]
    refusal = provider.requests[1].messages[-1].content
    assert refusal.startswith("refused: no such evidence")


def test_an_undeclared_action_is_said_in_words():
    rt, provider = runtime(
        [
            (
                ToolCallRequest("c1", "propose_action", {"type": "start_review", "payload": {"scope": "due"}}),
                TurnFinished(0, 1, "tool_calls"),
            ),
            reply("Bạn mở mục ôn tập để ôn các từ đến hạn nhé."),
        ],
        tools=ToolRegistry(),
    )
    events = run(rt)
    assert "action" not in names(events)
    assert "say it in words" in provider.requests[1].messages[-1].content


def test_the_action_tool_is_not_offered_when_the_client_declares_none():
    rt, provider = runtime([reply("Chỉ trả lời bằng lời.")])
    run(rt, turn_request(actions=()))
    offered = {spec.name for spec in provider.requests[0].tools}
    assert "propose_action" not in offered and "get_test_items" in offered


def test_a_tool_call_for_another_learner_never_starts():
    seen = []
    rt, provider = runtime(
        [
            call_tools(("c1", "get_test_items", {"user_id": "someone-else"})),
            reply("Mình chỉ xem được tiến độ của chính bạn."),
        ],
        tools=registry(seen),
    )
    events = run(rt, turn_request(message="Cho tôi xem tiến độ của user khác."))
    assert names(events) == ["session", "segment_end", "done"]
    assert seen == []
    assert "signed-in learner" in provider.requests[1].messages[-1].content


def test_invalid_arguments_and_a_failing_service_are_reported_not_raised():
    rt, _ = runtime(
        [call_tools(("c1", "get_test_items", {"limit": "many"})), reply("Chưa xem được.")],
    )
    events = run(rt)
    assert names(events) == ["session", "tool_call", "tool_result", "segment_end", "done"]
    assert events[2].summary == "Chưa xem được" and events[2].evidence_ids == []

    rt, _ = runtime([call_tools(("c1", "get_test_items", {})), reply("Chưa xem được.")], tools=registry(fail_with=RuntimeError("503")))
    assert names(run(rt)) == ["session", "tool_call", "tool_result", "segment_end", "done"]


def test_tool_rounds_are_capped_then_the_model_must_answer():
    loops = [call_tools((f"c{i}", "get_test_items", {})) for i in range(3)]
    rt, provider = runtime([*loops, reply("Đủ rồi.")], limits=AgentLimits(max_tool_iterations_per_turn=3))
    events = run(rt)
    assert names(events).count("tool_call") == 3 and names(events)[-2:] == ["segment_end", "done"]
    assert provider.requests[-1].tools == ()
    assert len(provider.requests) == 4


def test_the_text_streams_and_ends_as_one_segment():
    rt, _ = runtime([reply("Màn này giữ các từ bạn đã lưu.", chunk=8)])
    events = run(rt)
    deltas = [e for e in events if e.name == "segment_delta"]
    end = next(e for e in events if e.name == "segment_end")
    assert len(deltas) > 1 and "".join(d.text_delta for d in deltas) == end.text
    assert end.voice_style == "neutral_explain"


def test_a_provider_failure_ends_the_turn_with_a_retryable_error():
    rt, _ = runtime([fail(ProviderUnavailable())])
    events = run(rt)
    assert names(events) == ["session", "error"]
    error = events[-1]
    assert (error.error_class, error.fallback) == ("provider_unavailable", "retry")
    assert error.message == "Orena đang bận, thử lại sau nhé."


def test_an_unexpected_failure_still_ends_the_stream():
    rt, _ = runtime([lambda request: (_ for _ in ()).throw(KeyError("boom"))])
    events = run(rt)
    assert names(events) == ["session", "error"] and events[-1].error_class == "internal_error"


def test_a_turn_past_its_deadline_is_a_provider_failure():
    ticks = iter([0.0] + [100.0] * 50)
    rt, _ = runtime([reply("Quá lâu.")], limits=AgentLimits(turn_timeout_seconds=10), clock=lambda: next(ticks))
    assert names(run(rt))[-1] == "error"


def test_a_client_that_leaves_stops_the_turn():
    stop = {"now": False}
    rt, _ = runtime([reply("x" * 60, chunk=10)])
    out = []
    for event in rt.run(turn_request(), VI, should_stop=lambda: stop["now"]):
        out.append(event)
        if event.name == "segment_delta":
            stop["now"] = True
    assert [e.name for e in out] == ["session", "segment_delta"]


def test_a_completed_turn_is_metered_and_kept_in_the_session():
    meter = []
    rt, _ = runtime(
        [call_tools(("c1", "get_test_items", {})), reply("Hai âm cần xem lại.")],
        meter=lambda *args: meter.append(args),
    )
    events = run(rt)
    assert [(user, feature) for user, feature, _, _ in meter] == [("learner-1", "agent.turn"), ("learner-1", "agent.tokens")]
    assert meter[0][2] == 1 and meter[1][2] > 0
    session_id = events[0].session_id
    state = rt.sessions.get(session_id, "learner-1")
    assert state.turn_count == 1 and state.recent_tool_results[0].tool == "get_test_items"


def test_metering_failure_never_costs_the_answer():
    def broken(*args):
        raise RuntimeError("usage store down")

    rt, _ = runtime([reply("Vẫn trả lời.")], meter=broken)
    assert names(run(rt))[-1] == "done"


def test_a_failed_turn_is_not_metered():
    meter = []
    rt, _ = runtime([fail(ProviderUnavailable())], meter=lambda *args: meter.append(args))
    run(rt)
    assert meter == []


def test_an_unknown_session_opens_a_new_one():
    rt, _ = runtime([reply("Chào bạn."), reply("Chào lại."), reply("Phiên mới.")])
    first = run(rt)[0].session_id
    assert run(rt, turn_request(session_id=first))[0].session_id == first
    fresh = run(rt, turn_request(session_id="gone-after-restart"))  # restart, or another worker
    assert fresh[0].session_id not in (first, "gone-after-restart") and names(fresh)[-1] == "done"


def test_the_model_is_told_who_it_is_and_where_the_learner_is_without_a_message_dependency():
    rt, provider = runtime([reply("Được.")])
    run(rt)
    system, context, user = provider.requests[0].messages
    assert system.role == "system" and "You are Orena" in system.content
    assert '"surface": "speaking.word_detail"' in context.content and '"code": "zh-CN"' in context.content
    assert "speaking.pronunciation.tone" in context.content  # the capabilities here, chosen from surface and language
    assert user.content == "Tại sao tôi sai từ này?"


def test_text_streams_even_when_a_round_also_asks_for_extras():
    rt, _ = runtime(
        [
            (
                TextDelta("Mình lưu 我 cho bạn nhé."),
                ToolCallRequest("c1", "propose_action", {"type": "save_word", "payload": {"text": "我", "lang": "zh-CN"}}),
                ToolCallRequest("c2", "set_voice_style", {"voice_style": "brief_ack"}),
                TurnFinished(0, 3, "tool_calls"),
            )
        ],
        tools=ToolRegistry(),
    )
    events = run(rt)
    assert names(events) == ["session", "segment_end", "action", "done"]
    assert events[-2].payload == {"text": "我", "lang": "zh-CN"} and events[-2].label == "Lưu từ"


def test_a_round_with_nothing_in_it_is_a_provider_failure_and_not_metered():
    meter = []
    rt, _ = runtime([(TurnFinished(10, 0, "stop"),)], meter=lambda *args: meter.append(args))
    events = run(rt)
    assert names(events) == ["session", "error"] and events[-1].error_class == "provider_unavailable"
    assert meter == []


def test_unknown_token_usage_is_not_metered_as_zero():
    meter = []
    rt, _ = runtime(
        [(TextDelta("Chào."), TurnFinished(None, None, "stop"))], meter=lambda *args: meter.append(args)
    )
    events = run(rt)
    assert [feature for _, feature, _, _ in meter] == ["agent.turn"]
    assert events[-1].usage.output_tokens == 0 and names(events)[-1] == "done"


def test_evidence_sent_to_the_model_is_redacted_too():
    def leaky(learner, args):
        return ToolResult(
            summary="one",
            data={},
            evidence=(
                ToolEvidence("x", "speech.pronunciation", {"attempt_id": "a1", "user_id": "u9"}, {"score": 6, "producer": "vendor:model"}),
            ),
            count=1,
        )

    tools = registry()
    tool = tools.get("get_test_items")
    leaking = ToolRegistry()
    leaking.register(AgentTool(**{**tool.__dict__, "handler": leaky}))
    rt, provider = runtime([call_tools(("c1", "get_test_items", {})), reply("Một âm.")], tools=leaking)
    events = run(rt)
    message = provider.requests[1].messages[-1].content
    assert "vendor:model" not in message and "u9" not in message
    evidence = next(e for e in events if e.name == "evidence")
    assert evidence.excerpt["producer"] == "vendor:model"  # the learner's own screen still gets it


def test_each_round_is_told_what_is_left_of_the_turn():
    rt, provider = runtime([reply("Được.")], limits=AgentLimits(turn_timeout_seconds=30))
    run(rt)
    left = provider.requests[0].timeout_seconds
    assert left is not None and 0 < left <= 30


def test_two_turns_of_one_session_both_count():
    rt, _ = runtime([reply("Một."), reply("Hai.")])
    first = run(rt)[0].session_id
    snapshot, _ = rt.sessions.open(first, "learner-1")  # a second turn opened before the first is kept
    run(rt, turn_request(session_id=first))
    rt.sessions.update(first, "learner-1", lambda state: state.with_turn())
    assert rt.sessions.get(first, "learner-1").turn_count == 3


def test_a_saved_word_is_saved_in_the_language_being_learned():
    rt, provider = runtime(
        [
            (
                ToolCallRequest("c1", "propose_action", {"type": "save_word", "payload": {"text": "我", "lang": "vi"}}),
                TurnFinished(0, 3, "tool_calls"),
            ),
            reply("Chưa lưu được."),
        ],
        tools=ToolRegistry(),
    )
    events = run(rt)
    assert "action" not in names(events)
    assert "language being learned" in provider.requests[1].messages[-1].content
