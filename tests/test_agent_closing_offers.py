"""LEX-006 (live retest at 8e74373): with something in view, an answer does not close by offering more - "Bạn có
muốn xem thêm các ví dụ … hoặc ôn tập luôn không?". Optional depth is the learner's to ask for. The server drops
such offers; the prompt asks for a short, passage-first answer, and a short reason for a feedback question."""

from __future__ import annotations

import pytest

from tests.test_agent_coaching import _runtime
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.honesty import ClaimGate, offers_more
from writing_coach.agent.prompts import INSTRUCTION
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import FEEDBACK_NUDGE


@pytest.mark.parametrize(("sentence", "support"), [
    ("Bạn có muốn xem thêm các ví dụ sử dụng từ này hoặc ôn tập luôn không?", "vi"),
    ("Em có muốn luyện thêm vài câu không?", "vi"),
    ("Nếu bạn muốn, mình có thể giải thích thêm về cách dùng.", "vi"),
    ("Would you like more examples or a quick review?", "en"),
    ("Do you want me to explain the grammar too?", "en"),
    ("If you'd like, I can give you more sentences.", "en"),
    ("Let me know if you want more examples.", "en"),
    ("你想再看几个例句吗？", "zh-CN"),
    ("要不要复习一下？", "zh-CN"),
    ("如果你想，我可以再举几个例子。", "zh-CN"),
])  # fmt: skip
def test_an_offer_of_more_is_recognised(sentence, support):
    assert offers_more(sentence, support)


@pytest.mark.parametrize(("sentence", "support"), [
    ("Bạn muốn hỏi nghĩa hay cách dùng?", "vi"),  # asks what the learner meant: an answer, not an offer
    ("Trong câu này, 花生 là hạt lạc.", "vi"),
    ("Do you know this word?", "en"),
    ("这个词在这里是“花生”的意思。", "zh-CN"),
])  # fmt: skip
def test_what_is_not_an_offer_of_more_is_kept(sentence, support):
    assert not offers_more(sentence, support)


def _gate(focused):
    gate = ClaimGate(interface="en", support="vi")
    gate.drop_more_offers = focused
    return gate


def test_with_something_in_view_the_closing_offer_is_dropped():
    gate = _gate(True)
    out = gate.feed("**花生** ở đây là hạt lạc.\nBạn có muốn xem thêm ví dụ hoặc ôn tập luôn không?")
    out += gate.finish(None)
    assert "".join(out) == "**花生** ở đây là hạt lạc.\n"


def test_an_answer_that_was_only_an_offer_says_nothing_untrue():
    gate = _gate(True)
    out = gate.feed("Bạn có muốn xem thêm ví dụ không?") + gate.finish(None)
    assert "".join(out) == ""  # never "nothing was changed": nothing was claimed


def test_with_nothing_in_view_the_offer_stays():
    gate = _gate(False)
    out = gate.feed("Hôm nay bạn có 3 từ đến hạn.\nBạn có muốn ôn luôn không?") + gate.finish(None)
    assert "Bạn có muốn ôn luôn không?" in "".join(out)


def test_a_whole_turn_on_a_selected_word_drops_the_closing_offer():
    request = TurnRequest.model_validate({
        "contract_version": 5, "trigger": "message", "message": "What does this word mean here?",
        "client": {"ui_version": "t", "supported_actions": [], "supported_intents": []},
        "context": {"surface": "reading.workspace", "locale": {"interface": "en", "support": "vi", "target": "zh-CN"},
                    "selected_item": {"type": "word", "text": "花生", "lang": "zh-CN"}},
    })  # fmt: skip
    rt, _ = _runtime([reply("Ở đây **花生** là hạt lạc.\nBạn có muốn xem thêm các ví dụ hoặc ôn tập luôn không?")])
    events = list(rt.run(request, LearnerScope(user_key="learner-1", language="zh", interface="en")))
    end = next(e for e in events if e.name == "segment_end")
    assert "có muốn" not in end.text and end.text.startswith("Ở đây **花生** là hạt lạc.")
    assert end.text == "".join(e.text_delta for e in events if e.name == "segment_delta")


def test_the_prompt_keeps_a_focused_answer_short_and_the_reason_short():
    rules = INSTRUCTION.casefold()
    assert "etymology" in rules and "closing offer" in rules and "at most three" in rules
    assert "at most one example" in FEEDBACK_NUDGE
