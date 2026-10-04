"""The deterministic fake provider every agent test runs on (spec D14)."""

from __future__ import annotations

import socket

import pytest
from pydantic import BaseModel, ConfigDict

from writing_coach.agent.errors import ProviderUnavailable
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, FakeScriptExhausted, call_tools, fail, reply
from writing_coach.agent.provider import (
    ProviderMessage,
    ProviderToolSpec,
    ProviderTurnRequest,
    TextDelta,
    ToolCallRequest,
    TurnFinished,
)
from writing_coach.agent.tools import AgentTool, ToolPermission, ToolResult


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a hermetic agent test opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def request(text="Hôm nay tôi nên học gì?"):
    return ProviderTurnRequest(
        messages=(ProviderMessage(role="system", content="You are Orena."), ProviderMessage(role="user", content=text))
    )


def test_a_reply_streams_in_fixed_deltas_then_finishes():
    provider = FakeAgentTurnProvider([reply("Ôn 12 từ đến hạn trước nhé.", chunk=10)])
    events = list(provider.stream(request()))
    assert [type(e) for e in events] == [TextDelta, TextDelta, TextDelta, TurnFinished]
    assert "".join(e.text for e in events[:-1]) == "Ôn 12 từ đến hạn trước nhé."
    assert events[-1].finish_reason == "stop" and events[-1].input_tokens > 0


def test_same_script_same_output():
    def run():
        provider = FakeAgentTurnProvider([reply("A deterministic answer."), call_tools(("c1", "get_due_vocabulary", {}))])
        return [list(provider.stream(request())), list(provider.stream(request()))]

    assert run() == run()


def test_a_tool_round_then_an_answer_round():
    provider = FakeAgentTurnProvider(
        [
            call_tools(("c1", "get_current_writing_evaluation", {"essay_id": "9"})),
            reply("Bạn hay sai trật tự từ."),
        ]
    )
    first = list(provider.stream(request()))
    assert first[0] == ToolCallRequest(id="c1", name="get_current_writing_evaluation", arguments={"essay_id": "9"})
    assert first[-1].finish_reason == "tool_calls"
    followup = ProviderTurnRequest(
        messages=(
            *request().messages,
            ProviderMessage(role="assistant", tool_calls=(first[0],)),
            ProviderMessage(role="tool", content='{"issues": 2}', tool_call_id="c1"),
        )
    )
    second = list(provider.stream(followup))
    assert second[-1].finish_reason == "stop"
    assert len(provider.requests) == 2 and provider.requests[1] is followup
    assert provider.remaining == 0


def test_a_round_can_see_the_request():
    provider = FakeAgentTurnProvider([lambda req: reply(f"{len(req.messages)} messages")])
    assert "".join(e.text for e in provider.stream(request()) if isinstance(e, TextDelta)) == "2 messages"


def test_failures_are_injected_where_scripted():
    provider = FakeAgentTurnProvider([fail(ProviderUnavailable()), (TextDelta("Hel"), ProviderUnavailable())])
    with pytest.raises(ProviderUnavailable):
        list(provider.stream(request()))
    partial = provider.stream(request())
    assert next(partial) == TextDelta("Hel")
    with pytest.raises(ProviderUnavailable):
        next(partial)


def test_an_unscripted_round_is_a_test_failure():
    provider = FakeAgentTurnProvider([])
    with pytest.raises(FakeScriptExhausted):
        provider.stream(request())


def test_the_client_can_stop_a_round():
    provider = FakeAgentTurnProvider([reply("x" * 100, chunk=10)])
    seen = []
    for event in provider.stream(request(), should_stop=lambda: len(seen) >= 3):
        seen.append(event)
    assert len(seen) == 3 and not any(isinstance(e, TurnFinished) for e in seen)


def test_messages_keep_their_roles_honest():
    with pytest.raises(ValueError):
        ProviderMessage(role="user", tool_calls=(ToolCallRequest(id="c", name="t"),))
    with pytest.raises(ValueError):
        ProviderMessage(role="tool", content="{}")
    with pytest.raises(ValueError):
        ProviderMessage(role="assistant", content="x", tool_call_id="c1")


def test_tool_specs_come_from_registered_tools():
    class Args(BaseModel):
        model_config = ConfigDict(extra="forbid")
        essay_id: str

    tool = AgentTool(
        name="get_current_writing_evaluation",
        description="The stored review of an essay.",
        input_model=Args,
        permission=ToolPermission.READ_ONLY,
        backed_by="writing_coach.writing_contract:project_review",
        languages=("en", "zh-CN"),
        label_key="error.internal",
        handler=lambda learner, args: ToolResult(summary="", data={}),
    )
    spec = ProviderToolSpec.from_tool(tool)
    assert spec.name == tool.name and spec.parameters["required"] == ["essay_id"]
