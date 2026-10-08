"""The conversation kernel, slice 2: one generic pending interaction (architecture target §7, §15, §28 Phase 1).

An offer the learner has not answered stays open across the turns between: an interjected question does not clear
it. The model reads the learner's words in the conversation and, when they accept or decline the offer, says so with
`resolve_pending`; the runtime - not the model - then runs the action exactly once, under the interaction's own id,
or drops it. It clears on confirm, cancel, expiry or when a new offer replaces it, and on nothing else.
"""

from __future__ import annotations

import json

from writing_coach.agent.fake_provider import call_tools, reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.provider import ToolCallRequest, TurnFinished
from writing_coach.agent.schemas import TurnRequest
from tests.test_agent_turn import VI, hermetic, names, run, runtime  # noqa: F401 - fixture

SAVE_ABATE = {"type": "save_word", "payload": {"text": "abate", "lang": "en"}}
SAVE_MITIGATE = {"type": "save_word", "payload": {"text": "mitigate", "lang": "en"}}


def request(message, session_id=None, *, target="en"):
    body = {
        "contract_version": 5,
        "message": message,
        "client": {"ui_version": "t", "supported_actions": ["navigate", "save_word", "unsave_word"],
                   "supported_intents": ["vocabulary.my_language"]},
        "context": {"surface": "orena.home", "locale": {"interface": "vi", "support": "vi", "target": target,
                                                        "content": target}},
    }
    if session_id:
        body["session_id"] = session_id
    return TurnRequest.model_validate(body)


def session_of(events):
    return next(e.session_id for e in events if e.name == "session")


def context_of(req):
    return json.loads(next(m.content for m in req.messages if m.content.startswith("context: "))[len("context: "):])


def offer(proposal=SAVE_ABATE):
    """The model's two rounds when it answers and proposes the button."""

    return [call_tools(("c1", "propose_action", proposal)), reply("abate nghĩa là giảm bớt, dịu đi.")]


def resolve(decision):
    """A round that answers the offer the context names: the learner accepted or declined it."""

    def round_(req):
        pending = context_of(req)["pending_interaction"]
        return (ToolCallRequest("r1", "resolve_pending", {"id": pending["id"], "decision": decision}),
                TurnFinished(0, 4, "tool_calls"))

    return round_


def actions(events):
    return [e for e in events if e.name == "action"]


def talk(rt, session_id, message, **kw):
    events = run(rt, request(message, session_id, **kw))
    return events, session_id or session_of(events)


def test_save_after_an_interjected_example_saves_exactly_abate_once():
    rt, provider = runtime([*offer(), reply("The storm will abate soon."), resolve("confirm"), reply("Ok.")])
    first, sid = talk(rt, None, "abate nghĩa là gì?")
    assert [a.type for a in actions(first)] == ["save_word"] and not actions(first)[0].open  # only offered
    sid = session_of(first)
    second, _ = talk(rt, sid, "cho ví dụ nữa")
    assert not actions(second)  # the interjection ran nothing...
    third, _ = talk(rt, sid, "ừ lưu đi")
    (saved,) = actions(third)  # ...and the pending offer survived it
    assert (saved.type, saved.payload, saved.open) == ("save_word", {"text": "abate", "lang": "en"}, True)
    assert names(third)[-1] == "done"


def test_the_offer_is_visible_to_the_model_with_a_stable_id_until_it_is_answered():
    rt, provider = runtime([*offer(), reply("The storm will abate soon.")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    talk(rt, sid, "cho ví dụ nữa")
    request_two = provider.requests[-1]
    pending = context_of(request_two)["pending_interaction"]
    assert (pending["action"], pending["payload"]) == ("save_word", {"text": "abate", "lang": "en"})
    assert "resolve_pending" in [t.name for t in request_two.tools]
    assert "resolve_pending" not in [t.name for t in provider.requests[0].tools]  # nothing was pending yet


def test_confirming_runs_the_action_under_the_interactions_own_id_and_clears_it():
    rt, provider = runtime([*offer(), resolve("confirm"), reply("Ok."), reply("Bạn cần gì nữa?")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    third, _ = talk(rt, sid, "lưu đi")
    pending_id = context_of(provider.requests[2])["pending_interaction"]["id"]
    assert actions(third)[0].id == pending_id
    talk(rt, sid, "ok lưu")  # said again by accident
    after = provider.requests[-1]
    assert "pending_interaction" not in context_of(after)
    assert "resolve_pending" not in [t.name for t in after.tools]  # nothing left to confirm twice


def test_confirming_twice_in_one_turn_runs_it_once():
    def twice(req):
        pid = context_of(req)["pending_interaction"]["id"]
        return (ToolCallRequest("r1", "resolve_pending", {"id": pid, "decision": "confirm"}),
                ToolCallRequest("r2", "resolve_pending", {"id": pid, "decision": "confirm"}),
                TurnFinished(0, 4, "tool_calls"))

    rt, _ = runtime([*offer(), twice, reply("Ok.")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    events, _ = talk(rt, session_of(first), "ừ lưu đi")
    assert len(actions(events)) == 1


def test_declining_cancels_without_running_anything():
    rt, provider = runtime([*offer(), resolve("cancel"), reply("Ok, mình không lưu."), reply("Còn gì nữa?")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    second, _ = talk(rt, sid, "không")
    assert not actions(second) and names(second)[-1] == "done"
    talk(rt, sid, "từ khác nhé")
    assert "pending_interaction" not in context_of(provider.requests[-1])


def test_a_question_in_between_leaves_the_offer_open_for_later():
    rt, provider = runtime([*offer(), reply("Formal vừa phải."), reply("Đúng, abate hơi trang trọng."), resolve("confirm"),
                            reply("Ok.")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    talk(rt, sid, "nó có formal không?")
    talk(rt, sid, "vậy hả")
    events, _ = talk(rt, sid, "thôi lưu đi")
    assert actions(events)[0].payload == {"text": "abate", "lang": "en"}


def test_a_new_offer_replaces_the_old_one():
    rt, provider = runtime([*offer(), *offer(SAVE_MITIGATE), resolve("confirm"), reply("Ok.")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    talk(rt, sid, "còn mitigate?")
    events, _ = talk(rt, sid, "lưu đi")
    assert [a.payload["text"] for a in actions(events)] == ["mitigate"]


def test_a_stale_or_unknown_id_runs_nothing():
    def wrong(req):
        return (ToolCallRequest("r1", "resolve_pending", {"id": "p0-deadbeef", "decision": "confirm"}),
                TurnFinished(0, 4, "tool_calls"))

    rt, _ = runtime([*offer(), wrong, reply("Bạn muốn lưu từ nào?")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    events, _ = talk(rt, session_of(first), "lưu đi")
    assert not actions(events)


def test_an_unanswered_offer_expires_after_a_few_turns():
    rt, provider = runtime([*offer(), *[reply(f"a{i}") for i in range(1, 8)]], limits=AgentLimits(compact_after_turns=100))  # no fold in this talk
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    for i in range(7):
        talk(rt, sid, f"câu {i}")
    assert "pending_interaction" not in context_of(provider.requests[-1])


def test_changing_the_learning_language_keeps_the_conversation_and_the_offer():
    rt, provider = runtime([*offer(), reply("你好是 hello.")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    talk(rt, sid, "đổi sang tiếng Trung", target="zh-CN")
    sent = provider.requests[-1]
    assert ("user", "abate nghĩa là gì?") in [(m.role, m.content) for m in sent.messages]
    assert context_of(sent)["pending_interaction"]["action"] == "save_word"


def test_the_instruction_has_the_model_offer_saving_as_a_button_not_in_words():
    from writing_coach.agent.prompts import INSTRUCTION

    assert "call propose_action save_word for that word" in INSTRUCTION
    assert "Never offer saving in words" in INSTRUCTION


def ask_to_run(proposal=SAVE_ABATE):
    return [call_tools(("c1", "propose_action", {**proposal, "requested": True})), reply("Ok.")]


def test_words_that_ask_for_an_action_run_it_even_with_no_earlier_offer():
    rt, _ = runtime([*ask_to_run()])
    events, _ = talk(rt, None, "lưu abate đi")
    (saved,) = actions(events)
    assert (saved.type, saved.payload, saved.open) == ("save_word", {"text": "abate", "lang": "en"}, True)


def test_the_same_words_said_twice_run_the_action_once():
    rt, _ = runtime([*ask_to_run(), *ask_to_run()])
    first, _ = talk(rt, None, "ok lưu abate")
    again, _ = talk(rt, session_of(first), "ok lưu")
    assert len(actions(first)) == 1 and not [a for a in actions(again) if a.open]


def test_proposing_the_open_offer_at_the_learners_word_accepts_it_under_its_own_id():
    rt, provider = runtime([*offer(), *ask_to_run(), reply("x")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    events, _ = talk(rt, sid, "ừ lưu đi")
    pending_id = context_of(provider.requests[2])["pending_interaction"]["id"]
    assert [(a.id, a.open) for a in actions(events)] == [(pending_id, True)]
    talk(rt, sid, "còn gì nữa")
    assert "pending_interaction" not in context_of(provider.requests[-1])


def test_an_action_not_asked_for_is_only_offered():
    rt, _ = runtime([*offer()])
    events, _ = talk(rt, None, "abate nghĩa là gì?")
    assert [a.open for a in actions(events)] == [None]


def test_offering_the_same_button_again_keeps_the_same_offer():
    rt, provider = runtime([*offer(), *offer(), reply("x")])
    first, _ = talk(rt, None, "abate nghĩa là gì?")
    sid = session_of(first)
    talk(rt, sid, "cho ví dụ nữa")
    talk(rt, sid, "ừ")
    pending = context_of(provider.requests[-1])["pending_interaction"]
    assert pending["id"].startswith("p1-")  # the offer of the first turn, not a new one each time


def test_after_an_action_ran_the_model_is_told_it_was_sent_not_that_it_worked():
    rt, provider = runtime([*ask_to_run(), reply("Đã gửi rồi.")])
    first, _ = talk(rt, None, "lưu abate đi")
    talk(rt, session_of(first), "ok lưu")
    sent = provider.requests[-1]
    assert context_of(sent)["sent_to_app_just_now"] == [{"action": "save_word", "payload": {"text": "abate", "lang": "en"}}]
    assert any("never say it is saved or done" in " ".join(m.content.split()) for m in sent.messages if m.role == "system")
