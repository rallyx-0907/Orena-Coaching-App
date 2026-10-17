"""M0 of Orena Memory (docs/project/proposals/ORENA_MEMORY.md §5.4, §7.2, §9): a cache-stable request, a tool list that
can be held fixed, a model pinned per conversation, and the telemetry the before/after benchmark reads.

The layout is judged by what a provider's prefix cache can reuse: the bytes a request shares, from its start, with the
requests before it. Nothing here calls a provider (hermetic fixture).
"""

from __future__ import annotations

import pytest

from writing_coach.agent.fake_provider import call_tools, reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.prompts import INSTRUCTION, TURN_CONTEXT_HEAD, PromptLayout
from writing_coach.agent.provider import ModelRoute, ToolCallRequest, TurnFinished, tools_digest
from writing_coach.agent.summary import INSTRUCTION as SUMMARY_INSTRUCTION
from tests.test_agent_turn import VI, hermetic, run, runtime, turn_request  # noqa: F401 - fixture


def session_of(events):
    return next(e for e in events if e.name == "session").session_id


def conversation(rt, *messages, **extra):
    session_id, out = None, []
    for message in messages:
        request = turn_request(message, **extra, **({"session_id": session_id} if session_id else {}))
        events = run(rt, request)
        session_id = session_of(events)
        out.append(events)
    return out


def context_at(request) -> int:
    """Where this turn's part of the context is (the setting part is right after the instruction)."""

    return next(i for i, m in enumerate(request.messages) if m.content.startswith(TURN_CONTEXT_HEAD))


def shared_prefix(a, b) -> int:
    """How many leading messages two requests have in common, exactly."""

    n = 0
    for x, y in zip(a.messages, b.messages, strict=False):
        if (x.role, x.content, x.tool_calls, x.tool_call_id) != (y.role, y.content, y.tool_calls, y.tool_call_id):
            break
        n += 1
    return n


# --- layout ---------------------------------------------------------------------------------------


def test_the_context_follows_the_conversation_so_the_turns_before_it_are_a_stable_prefix():
    rt, provider = runtime([reply("a1"), reply("a2"), reply("a3")])
    conversation(rt, "q1", "q2", "q3")
    first, second, third = provider.requests
    assert first.messages[0].content == INSTRUCTION
    # Each request is: the instruction, the setting, the turns already said, this turn's context, the tail, the words.
    assert third.messages[1].content.startswith("context: ")
    assert [m.content for m in third.messages[2: context_at(third)]] == ["q1", "a1", "q2", "a2"]
    assert third.messages[-1].content == "q3"
    # Turn 3 reuses everything turn 2 sent before its context, plus turn 2's own exchange.
    assert shared_prefix(second, third) == context_at(second)
    assert shared_prefix(second, third) == 4  # instruction, setting, q1, a1


def test_the_legacy_layout_keeps_the_whole_context_second():
    rt, provider = runtime([reply("a1"), reply("a2")])
    rt.prompt = PromptLayout(cache_stable=False)
    conversation(rt, "q1", "q2")
    second = provider.requests[1]
    assert second.messages[1].content.startswith("context: ") and '"selection"' in second.messages[1].content
    assert not any(m.content.startswith(TURN_CONTEXT_HEAD) for m in second.messages)


def test_a_change_in_this_turns_context_keeps_the_conversation_reusable():
    # A new selection changes this turn's part only: the setting and the turns said before stay the same bytes.
    rt, provider = runtime([reply("a1"), reply("a2")])
    (first,) = conversation(rt, "q1")
    request = turn_request("q2", session_id=session_of(first))
    request = request.model_copy(update={"context": request.context.model_copy(
        update={"selected_item": request.context.selected_item.model_copy(update={"text": "我"})})})
    run(rt, request)
    second = provider.requests[1]
    assert shared_prefix(provider.requests[0], second) == 2  # instruction and setting, then the first turn
    assert [m.content for m in second.messages[2:4]] == ["q1", "a1"]


def test_an_opening_turn_also_ends_with_its_context_before_the_trigger():
    rt, provider = runtime([reply("Chào bạn.")])
    run(rt, _open_request())
    (sent,) = provider.requests
    assert sent.messages[0].content == INSTRUCTION and sent.messages[1].content.startswith("context: ")
    assert context_at(sent) == len(sent.messages) - 2 and sent.messages[-1].role == "user"


def _open_request():
    """An opening on no selection (one on a selection is answered from copy, with no model)."""

    request = turn_request("x")
    context = request.context.model_copy(update={"selected_item": None})
    return request.model_copy(update={"message": None, "trigger": "open", "context": context})


def test_rounds_of_one_turn_extend_the_same_request():
    rt, provider = runtime([call_tools(("c1", "get_test_items", {"limit": 1})), reply("xong")])
    run(rt)
    first, second = provider.requests
    assert shared_prefix(first, second) == len(first.messages)  # the second round only appends


# --- the tool list ----------------------------------------------------------------------------------


def test_by_default_the_tools_are_those_the_round_allows():
    rt, provider = runtime([reply("a1")])
    run(rt)
    names = [t.name for t in provider.requests[0].tools]
    assert "resolve_pending" not in names  # no offer is open
    assert provider.requests[0].tool_choice is None


def test_stable_tools_list_the_same_tools_every_round_and_every_turn():
    limits = AgentLimits(max_tool_iterations_per_turn=1)
    rounds = [call_tools(("c1", "get_test_items", {"limit": 1})), reply("xong"), reply("a2")]
    rt, provider = runtime(rounds, limits=limits)
    rt.prompt = PromptLayout(stable_tools=True)
    conversation(rt, "q1", "q2")
    digests = {tools_digest(r.tools) for r in provider.requests}
    assert len(digests) == 1 and None not in digests
    names = [t.name for t in provider.requests[0].tools]
    assert "resolve_pending" in names and "get_test_items" in names  # listed though no offer is open
    # The last round of a turn only answers: the tools stay listed and none may be called.
    assert provider.requests[1].tool_choice == "none"
    assert provider.requests[0].tool_choice is None


def test_stable_tools_still_refuse_what_the_turn_does_not_allow():
    # An opening turn reads nothing (§3.2): a read the model asks for is answered "unavailable" and never runs.
    seen = []
    rounds = [
        (ToolCallRequest("c1", "get_test_items", {"limit": 1}), TurnFinished(0, 5, "tool_calls")),
        reply("Chào bạn."),
    ]
    rt, provider = runtime(rounds)
    rt.prompt = PromptLayout(stable_tools=True)
    original = rt.tools.invoke
    rt.tools.invoke = lambda *a, **k: seen.append(a) or original(*a, **k)  # type: ignore[method-assign]
    run(rt, _open_request())
    assert seen == []
    answered = [m.content for m in provider.requests[1].messages if m.role == "tool"]
    assert answered == ["unavailable: not offered in this turn"]


def test_layout_from_the_environment_refuses_to_guess():
    assert PromptLayout.from_env({}) == PromptLayout(cache_stable=True, stable_tools=False)
    assert PromptLayout.from_env({"AGENT_PROMPT_LAYOUT": "legacy", "AGENT_STABLE_TOOLS": "on"}) == PromptLayout(
        cache_stable=False, stable_tools=True)
    with pytest.raises(ValueError):
        PromptLayout.from_env({"AGENT_PROMPT_LAYOUT": "fast"})
    with pytest.raises(ValueError):
        PromptLayout.from_env({"AGENT_STABLE_TOOLS": "maybe"})


# --- the model pinned per conversation ----------------------------------------------------------------


class Router:
    def __init__(self, current, usable=lambda route: True):
        self.selection = current
        self.is_usable = usable

    def current(self):
        return self.selection

    def usable(self, route):
        return self.is_usable(route)


A = ModelRoute("gemini", "gemini-3.5-flash-lite")
B = ModelRoute("groq", "openai/gpt-oss-120b")


def test_a_conversation_keeps_the_model_it_opened_on_when_admin_changes_the_selection():
    rt, provider = runtime([reply("a1"), reply("a2")])
    rt.router = Router(A)
    first, = conversation(rt, "q1")
    rt.router.selection = B  # Admin picks another model
    run(rt, turn_request("q2", session_id=session_of(first)))
    assert [r.route for r in provider.requests] == [A, A]


def test_a_new_conversation_takes_the_current_selection():
    rt, provider = runtime([reply("a1"), reply("a2")])
    rt.router = Router(A)
    conversation(rt, "q1")
    rt.router.selection = B
    conversation(rt, "q1 again")
    assert [r.route for r in provider.requests] == [A, B]


def test_a_pinned_model_that_can_no_longer_stream_is_pinned_again():
    rt, provider = runtime([reply("a1"), reply("a2")])
    rt.router = Router(A)
    first, = conversation(rt, "q1")
    rt.router.selection, rt.router.is_usable = B, (lambda route: route != A)
    records = []
    rt.record_turn = lambda user, record: records.append(record)
    run(rt, turn_request("q2", session_id=session_of(first)))
    assert provider.requests[1].route == B
    assert records[-1]["model_route"] == {"provider": "groq", "model": "openai/gpt-oss-120b", "pinned": "repinned"}


def test_without_a_router_nothing_is_pinned():
    rt, provider = runtime([reply("a1")])
    run(rt)
    assert provider.requests[0].route is None


def test_the_rolling_summary_runs_on_the_conversation_model():
    limits = AgentLimits(compact_after_turns=2, keep_verbatim_turns=2)
    rt, provider = runtime([reply("a1"), reply("a2"), reply("tóm tắt"), reply("a3"), reply("tóm tắt 2")], limits=limits)
    rt.router = Router(A)
    conversation(rt, "q1", "q2", "q3")
    summaries = [r for r in provider.requests if r.messages[0].content.startswith(SUMMARY_INSTRUCTION[:40])]
    assert summaries and all(r.route == A for r in summaries)


# --- telemetry ----------------------------------------------------------------------------------------


def test_the_turn_record_carries_what_the_benchmark_reads():
    rt, provider = runtime([
        (*call_tools(("c1", "get_test_items", {"limit": 1}))[:-1], TurnFinished(4000, 20, "tool_calls", 3500)),
        (*reply("xong")[:-1], TurnFinished(4100, 80, "stop", 4000)),
    ])
    rt.router = Router(A)
    rt.price_summary = lambda i, o, route=None: {"provider": route.provider, "model": route.model, "cost": 0.0026}
    records = []
    rt.record_turn = lambda user, record: records.append(record)
    run(rt)
    (record,) = records
    assert record["prompt_layout"] == "orena-prompt/2"
    assert record["tools_digest"] and len(record["tools_digest"]) == 16
    assert record["model_route"] == {"provider": "gemini", "model": "gemini-3.5-flash-lite", "pinned": "new"}
    # The fake counts the input itself; the cached part is what the provider reported.
    assert record["input_tokens"] == sum(r["input_tokens"] for r in record["rounds"])
    assert record["cached_input_tokens"] == 7500
    assert record["uncached_input_tokens"] == max(record["input_tokens"] - 7500, 0) and record["output_tokens"] == 100
    assert record["provider_rounds"] == 2 and record["tool_calls"] == 1
    assert record["cost_upper_bound"] == 0.0026
    assert [r["cached_input_tokens"] for r in record["rounds"]] == [3500, 4000]
    assert all(r["first_event_ms"] is not None and r["end_ms"] is not None for r in record["rounds"])
