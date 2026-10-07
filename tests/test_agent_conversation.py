"""The conversation kernel, slice 1: the model sees the turns before this one (architecture target §4-5, §28 Phase 1).

A turn used to reach the model as one message with no history, so "cho ví dụ khác" had nothing to refer to. The
session now keeps recent turns (in this process, TTL like the rest of the session - never a table) and the model is
given them as real user/assistant messages before the learner's new one.
"""

from __future__ import annotations

from writing_coach.agent.fake_provider import reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.session import ConversationTurn
from tests.test_agent_turn import VI, hermetic, names, run, runtime, turn_request  # noqa: F401 - fixture


def session_of(events):
    return next(e for e in events if e.name == "session").session_id


def conversation(rt, *messages, learner=VI, **extra):
    """Run `messages` one after the other in one session; the events of each."""

    session_id, out = None, []
    for message in messages:
        request = turn_request(message, **extra, **({"session_id": session_id} if session_id else {}))
        events = run(rt, request, learner=learner)
        session_id = session_of(events)
        out.append(events)
    return out


def roles(request):
    return [(m.role, m.content) for m in request.messages if m.role in ("user", "assistant")]


def test_the_second_turn_shows_the_model_the_first():
    rt, provider = runtime([reply("mitigate là làm giảm nhẹ."), reply("The controller helps mitigate spikes.")])
    first, second = conversation(rt, "mitigate nghĩa là gì?", "cho ví dụ khác")
    assert names(second)[-1] == "done"
    assert roles(provider.requests[1]) == [
        ("user", "mitigate nghĩa là gì?"),
        ("assistant", "mitigate là làm giảm nhẹ."),
        ("user", "cho ví dụ khác"),
    ]  # the new message is last, and the first turn is the history before it
    assert roles(provider.requests[0]) == [("user", "mitigate nghĩa là gì?")]


def test_history_is_bounded_and_drops_the_oldest_first():
    limits = AgentLimits(max_recent_turns=4)
    rt, provider = runtime([reply(f"a{i}") for i in range(1, 5)], limits=limits)
    conversation(rt, "q1", "q2", "q3", "q4")
    sent = [text for role, text in roles(provider.requests[3]) if role == "user"]
    assert sent == ["q2", "q3", "q4"]  # four kept turns: q2 a2 q3 a3, then the new q4


def test_a_long_pasted_message_is_kept_whole_for_the_next_question():
    article = "Artificial intelligence has fundamentally changed work. " * 300  # ~16,500 characters
    rt, provider = runtime([reply("Tác giả phản đối việc bỏ qua tác động."), reply("Đoạn đó lập luận khá mạnh.")])
    conversation(rt, article + "\nTác giả phản đối điều gì?", "đoạn thứ 3 lập luận có yếu không?")
    kept = [text for role, text in roles(provider.requests[1]) if role == "user"][0]
    assert kept.startswith(article[:200]) and kept.endswith("Tác giả phản đối điều gì?")


def test_history_of_one_learner_never_reaches_another():
    rt, provider = runtime([reply("one"), reply("two")])
    (first,) = conversation(rt, "bí mật của tôi")
    request = turn_request("hỏi tiếp", session_id=session_of(first))
    other = type(VI)(user_key="learner-2", language="zh")
    run(rt, request, learner=other)
    assert roles(provider.requests[1]) == [("user", "hỏi tiếp")]


def test_a_failed_turn_leaves_no_half_conversation():
    from writing_coach.agent.errors import ProviderUnavailable
    from writing_coach.agent.fake_provider import fail

    rt, provider = runtime([fail(ProviderUnavailable("down")), reply("ok")])
    first, second = conversation(rt, "câu hỏi bị lỗi", "hỏi lại")
    assert names(first)[-1] == "error"
    assert roles(provider.requests[1]) == [("user", "hỏi lại")]


def test_a_session_state_keeps_turns_as_plain_data():
    turn = ConversationTurn(role="user", text="hi")
    assert (turn.role, turn.text) == ("user", "hi")
