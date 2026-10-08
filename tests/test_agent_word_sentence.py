"""LEX-006 (readiness check at 1151c83): "What does this word mean here?" must answer from the sentence the word
was selected in (contract §3: selected_item.sentence, ≤ 500 characters), keep saved/due/review status out of an
answer about what is in view unless asked, and give a heading when one is asked for."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from tests.test_agent_coaching import _runtime
from writing_coach.agent.fake_provider import reply
from writing_coach.agent.honesty import ClaimGate, states_status
from writing_coach.agent.prompts import INSTRUCTION
from writing_coach.agent.schemas import SelectedItem, TurnRequest
from writing_coach.agent.tools import LearnerScope

SENTENCE = "母亲说：“让他荒芜着怪可惜，既然你们那么爱吃花生，就辟来做花生园罢。”"
WORD = {"type": "word", "text": "花生", "lang": "zh-CN", "sentence": SENTENCE}
LEARNER = LearnerScope(user_key="learner-1", language="zh", interface="en")


def _turn(message, selected=WORD, *, interface="en", support="vi"):
    return TurnRequest.model_validate({
        "contract_version": 5, "trigger": "message", "message": message,
        "client": {"ui_version": "t", "supported_actions": [], "supported_intents": []},
        "context": {"surface": "reading.workspace", "content_id": "article:7",
                    "locale": {"interface": interface, "support": support, "target": "zh-CN"},
                    "selected_item": selected},
    })  # fmt: skip


def test_a_word_carries_the_sentence_it_was_selected_in():
    assert SelectedItem.model_validate(WORD).sentence == SENTENCE
    with pytest.raises(ValidationError):
        SelectedItem.model_validate({**WORD, "sentence": "花" * 501})


def test_the_model_is_told_which_sentence_here_means():
    rt, provider = _runtime([reply("Ok.")])
    list(rt.run(_turn("What does this word mean here?"), LEARNER))
    system = [m.content for m in provider.requests[0].messages if m.role == "system"]
    line = next(s for s in system if s.startswith("The learner has selected the word"))
    assert json.dumps(SENTENCE, ensure_ascii=False) in line and "meaning in that sentence first" in line
    context = json.loads(next(m.content for m in provider.requests[0].messages if m.content.startswith("context: "))[9:])
    assert context["selection"]["sentence"] == SENTENCE


@pytest.mark.parametrize(("sentence", "support"), [
    ("Từ này hiện đang có trong danh sách từ vựng đã lưu của bạn và đến hạn ôn tập đấy!", "vi"),
    ("This word is already saved in your words and due for review.", "en"),
    ("这个词已经在你的生词本里，今天到期复习。", "zh-CN"),
])  # fmt: skip
def test_a_status_statement_about_the_learner_is_recognised(sentence, support):
    assert states_status(sentence, support)


@pytest.mark.parametrize(("sentence", "support"), [
    ("复习 nghĩa là ôn tập.", "vi"),  # the word's own meaning, not the learner's status
    ("Here 花生 means peanuts, the crop the mother wants to plant.", "en"),
    ("这里的“花生”指孩子们爱吃的花生。", "zh-CN"),
    ("Màn này giữ các từ bạn đã lưu.", "vi"),  # a screen described, not this word's status
])  # fmt: skip
def test_a_meaning_is_not_a_status_statement(sentence, support):
    assert not states_status(sentence, support, "花生")


def test_the_word_as_selected_names_it_too():
    assert states_status("花生 đã có trong danh sách từ vựng đã lưu của bạn.", "vi", "花生")


def test_the_status_line_is_dropped_from_an_answer_about_the_word():
    rt, _ = _runtime([reply("Ở câu này, **花生** là lạc, thứ các con thích ăn.\n"
                            "Từ này hiện đang có trong danh sách từ vựng đã lưu của bạn và đến hạn ôn tập đấy!")])  # fmt: skip
    events = list(rt.run(_turn("What does this word mean here?"), LEARNER))
    end = next(e for e in events if e.name == "segment_end")
    assert end.text.strip() == "Ở câu này, **花生** là lạc, thứ các con thích ăn."


def test_the_status_is_given_when_the_learner_asks_for_it():
    rt, _ = _runtime([reply("Từ này đã có trong danh sách từ vựng đã lưu của bạn.")])
    events = list(rt.run(_turn("Mình đã lưu từ này chưa?", interface="vi"), LEARNER))
    assert "đã lưu của bạn" in next(e for e in events if e.name == "segment_end").text


@pytest.mark.parametrize("message", ["Giải thích từ này, có tiêu đề và in đậm nghĩa chính", "Explain it with a heading",
                                     "请加一个标题解释这个词"])  # fmt: skip
def test_a_requested_heading_written_as_bold_becomes_a_heading(message):
    gate = ClaimGate(interface="vi", support="vi")
    gate.heading_asked = True
    out = gate.feed("**花生 trong câu này**\n**Nghĩa:** lạc.\n") + gate.finish(None)
    assert "".join(out) == "### 花生 trong câu này\n**Nghĩa:** lạc.\n"
    from writing_coach.agent.honesty import asks_for_heading

    assert asks_for_heading(message)


def test_without_a_request_bold_stays_bold():
    gate = ClaimGate(interface="vi", support="vi")
    out = gate.feed("**花生 trong câu này**\n") + gate.finish(None)
    assert "".join(out) == "**花生 trong câu này**\n"


def test_the_prompt_keeps_status_out_unless_asked():
    assert "saved" in INSTRUCTION and "selected_item.sentence" in INSTRUCTION
