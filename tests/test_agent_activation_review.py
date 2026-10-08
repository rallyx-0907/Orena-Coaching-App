"""The independent architecture review of 2026-10-04 (dark merge approved; these are required before activation).

P1 evidence before claim: text the model writes in the same round as a read tool call was written before the
evidence came back; it never reaches the learner, and the answer written after the read does.
P1/P2 fail closed: a round that ended for any reason but a normal stop - cut off ("length") or unknown - is an error
for the learner, never a complete answer.
"""

from __future__ import annotations

from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from tests.test_agent_server_copy import reply, request, run, segments


def test_text_beside_a_read_is_never_shown_the_answer_after_it_is():
    claim_before_reading = (
        TextDelta("Bạn đã thuộc hết các từ rồi. "),  # written before anything was read
        ToolCallRequest("c1", "get_due_review_summary", {}),
        TurnFinished(0, 5, "tool_calls"),
    )
    events, provider = run([claim_before_reading, reply("Bạn có 0 từ đến hạn ôn.")], request("Mình còn từ nào phải ôn?"))
    names = [e.name for e in events]
    assert names.index("tool_result") < names.index("segment_delta")  # evidence first, then words
    text = segments(events)[0][1]
    assert "thuộc hết" not in text and text == "Bạn có 0 từ đến hạn ôn."
    assert provider.requests[1].messages[-2].content in ("", None)  # the model's history holds no unread claim


def test_a_reply_tool_beside_text_keeps_the_text():
    with_suggestion = (TextDelta("Từ này nghĩa là tôi."), ToolCallRequest("c1", "suggest_next", {"intent": "prompt.review_due"}),
                       TurnFinished(0, 5, "tool_calls"))  # fmt: skip
    events, _ = run([with_suggestion], request("Từ 我 là gì?"))
    assert segments(events)[0][1] == "Từ này nghĩa là tôi."


def test_a_cut_off_round_is_an_error_not_an_answer():
    events, _ = run([(TextDelta("Câu trả lời bị cắt giữa"), TurnFinished(0, 1024, "length"))], request("Giải thích dài giúp mình."))
    assert events[-1].name == "error" and events[-1].error_class == "provider_unavailable"
    assert "segment_end" not in [e.name for e in events]
