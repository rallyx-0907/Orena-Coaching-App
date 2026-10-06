"""Text turns, after the human's test on Orena Home (2026-10-06): the agent offered "Bấm Open the lesson để mở." again
and again, never opened, and "mở giúp tôi" fetched something else. Now an action the learner's own words asked for
carries `open: true` and its sentence says it is happening (§7; R30); "open it" right after an offer opens that
offer, with no model call; and the next turn's model sees what was offered."""

from __future__ import annotations

import json

import pytest

from tests.test_agent_coaching import ZH, _runtime
from writing_coach.agent.events import make_action
from writing_coach.agent.outputs import PROPOSE_ACTION, opens_the_offer
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.schemas import TurnRequest

LESSON = {"type": "navigate", "payload": {"intent": "listening.workspace", "content_id": "media:hawking-01"}}


def _request(message, session_id=None):
    body = {"contract_version": 5, "trigger": "message", "message": message,
            "client": {"ui_version": "t", "supported_actions": ["navigate", "start_review"],
                       "supported_intents": ["listening.workspace", "orena.home"]},
            "context": {"surface": "orena.home", "content_id": "media:hawking-01",
                        "locale": {"interface": "en", "support": "vi", "target": "zh-CN"}}}  # fmt: skip
    if session_id:
        body["session_id"] = session_id
    return TurnRequest.model_validate(body)


def _offering(text="Mình tìm thấy bài về Stephen Hawking."):
    return (TextDelta(text), ToolCallRequest("c1", PROPOSE_ACTION, LESSON), TurnFinished(0, 3, "tool_calls"))


def _shown(events):
    text = next(e.text for e in events if e.name == "segment_end")
    return text, [e.to_wire() for e in events if e.name == "action"]


def test_asked_to_open_it_opens_at_once_and_says_so():
    rt, _ = _runtime([_offering()])
    text, (action,) = _shown(list(rt.run(_request("Mở video của Stephen Hawking"), ZH)))
    assert action["open"] is True and action["payload"] == LESSON["payload"]
    assert text.endswith("Mình mở ngay cho bạn.") and "Bấm" not in text


def test_not_asked_it_is_offered_with_a_tap():
    rt, _ = _runtime([_offering()])
    text, (action,) = _shown(list(rt.run(_request("Có bài nghe nào về Stephen Hawking không?"), ZH)))
    assert "open" not in action and "Bấm" in text


@pytest.mark.parametrize("follow_up", ["mở giúp tôi", "Mở đi", "ok mở giúp mình", "open it", "Open it please", "打开它"])
def test_open_it_right_after_an_offer_opens_that_offer_with_no_model_call(follow_up):
    rt, provider = _runtime([_offering()])
    first = list(rt.run(_request("Có bài nghe nào về Stephen Hawking không?"), ZH))
    session_id = next(e.session_id for e in first if e.name == "session")
    asked = len(provider.requests)
    events = list(rt.run(_request(follow_up, session_id), ZH))
    text, (action,) = _shown(events)
    assert len(provider.requests) == asked  # answered without the model
    assert action["open"] is True and action["payload"] == LESSON["payload"]
    assert text == "Mình mở ngay cho bạn." and not [e for e in events if e.name in ("tool_call", "evidence")]


def test_open_it_with_nothing_offered_is_an_ordinary_turn():
    rt, provider = _runtime([(TextDelta("Bạn muốn mở bài nào?"), TurnFinished(0, 3, "stop"))])
    list(rt.run(_request("mở giúp tôi"), ZH))
    assert len(provider.requests) == 1


def test_the_next_turn_sees_what_was_offered():
    rt, provider = _runtime([_offering(), (TextDelta("Bài đó là về vũ trụ."), TurnFinished(0, 3, "stop"))])
    first = list(rt.run(_request("Có bài nghe nào về Stephen Hawking không?"), ZH))
    session_id = next(e.session_id for e in first if e.name == "session")
    list(rt.run(_request("Bài đó nói về gì?", session_id), ZH))
    context = json.loads(next(m.content for m in provider.requests[-1].messages if m.content.startswith("context: "))[9:])
    assert context["offered_last_turn"] == [{"label": next(e.label for e in first if e.name == "action"),
                                             "payload": LESSON["payload"]}]  # fmt: skip


@pytest.mark.parametrize("message", ["Mở bài nghe của Stephen Hawking", "Open the cosmic calendar video",
                                     "mở bài khác đi", "Có bài nào khác không?", "Mình không muốn mở"])  # fmt: skip
def test_what_names_something_new_is_not_open_it(message):
    assert not opens_the_offer(message)


def test_an_only_offered_action_carries_no_open_on_the_wire():
    action = make_action("a1", "navigate", "Open", {"intent": "orena.home"})
    assert "open" not in action.to_wire()
    assert action.model_copy(update={"open": True}).to_wire()["open"] is True
