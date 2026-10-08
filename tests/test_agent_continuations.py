"""The conversation kernel, slice 4: a short continuation is never taken over by the learner's profile or records
(architecture target §8, §12; Definition of Done 7).

"ok lưu" with a word in view used to read as a question about whether the word is saved ("lưu" matches the status
words), and the turn was told to answer that and explain nothing. Whatever the message, an open offer or an action
just sent means the learner is answering the conversation: no status-only instruction, no instruction to read their
records, no review routing. The model reads the conversation.
"""

from __future__ import annotations

import pytest

from writing_coach.agent.fake_provider import reply
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.turn import EVIDENCE_NUDGE, STATUS_ONLY
from tests.test_agent_pending import SAVE_ABATE, actions, context_of, offer, request, resolve, session_of
from tests.test_agent_turn import hermetic, run, runtime  # noqa: F401 - fixture

CONTINUATIONS = ["ok lưu", "ừ lưu đi", "không", "cho ví dụ nữa", "ý trên là sao?", "từ đó có formal không?",
                 "cái đó là gì", "giải thích dễ hơn", "mở nó đi", "ok"]


def with_word_in_view(message, session_id=None):
    body = request(message, session_id).model_dump(mode="json")
    body["context"]["selected_item"] = {"type": "word", "text": "abate", "lang": "en"}
    return TurnRequest.model_validate(body)


def system_text(req):
    return " ".join(m.content for m in req.messages if m.role == "system")


@pytest.mark.parametrize("message", CONTINUATIONS)
def test_a_short_continuation_with_an_open_offer_gets_no_status_only_or_records_instruction(message):
    rt, provider = runtime([*offer(), reply("Ok."), reply("Ok."), reply("Ok.")])
    first = run(rt, with_word_in_view("abate nghĩa là gì?"))
    run(rt, with_word_in_view(message, session_of(first)))
    sent = system_text(provider.requests[2])
    assert STATUS_ONLY not in sent and EVIDENCE_NUDGE not in sent


def test_ok_save_with_a_word_in_view_is_answered_as_accepting_the_offer():
    rt, provider = runtime([*offer(), resolve("confirm"), reply("Ok.")])
    first = run(rt, with_word_in_view("abate nghĩa là gì?"))
    events = run(rt, with_word_in_view("ok lưu", session_of(first)))
    assert STATUS_ONLY not in system_text(provider.requests[2])
    assert [(a.type, a.open) for a in actions(events)] == [("save_word", True)]


def test_a_status_question_with_nothing_open_is_still_status_only():
    rt, provider = runtime([reply("Chưa lưu.")])
    run(rt, with_word_in_view("từ này lưu chưa?"))
    assert STATUS_ONLY in system_text(provider.requests[0])  # unchanged: this is a question about the library


def test_the_offer_is_in_the_context_of_the_continuation():
    rt, provider = runtime([*offer(), reply("Ok.")])
    first = run(rt, with_word_in_view("abate nghĩa là gì?"))
    run(rt, with_word_in_view("ok lưu", session_of(first)))
    assert context_of(provider.requests[2])["pending_interaction"]["payload"] == SAVE_ABATE["payload"]
