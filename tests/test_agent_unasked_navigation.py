"""LEX-006 (retest at 87b223e): asked what a selected word means here, the learner got a "My Library" button and
its offer. With something in view a navigate button is unasked routing, like a review offer: refused unless the
learner asks to open or go somewhere. And with a heading asked for, a later bold-only short line is a sub-heading."""

from __future__ import annotations

import pytest

from writing_coach.agent.honesty import ClaimGate
from writing_coach.agent.outputs import PROPOSE_ACTION, ClientInfo, ReplyOutputs


def _outputs(message, *, focused=True):
    client = ClientInfo.model_validate({"ui_version": "t", "supported_actions": ["navigate", "save_word"],
                                        "supported_intents": ["vocabulary.my_language", "orena.home"]})  # fmt: skip
    return ReplyOutputs(client=client, interface="en", support="vi", target="zh-CN", focused=focused,
                        text_in_view=focused, learner_words=message)  # fmt: skip


NAVIGATE = {"type": "navigate", "payload": {"intent": "vocabulary.my_language"}}


def test_a_meaning_question_in_view_gets_no_navigation():
    out = _outputs("Từ này nghĩa là gì ở đây?")
    answer = out.handle(PROPOSE_ACTION, NAVIGATE, known_evidence=frozenset())
    assert answer.startswith("refused: the learner asks about what is in view") and out.actions == []


@pytest.mark.parametrize("message", ["Mở danh sách từ vựng của mình", "Take me to my library", "Open My Library",
                                     "打开我的词汇", "Đưa mình tới thư viện"])  # fmt: skip
def test_navigation_is_offered_when_the_learner_asks_to_go(message):
    out = _outputs(message)
    assert out.handle(PROPOSE_ACTION, NAVIGATE, known_evidence=frozenset()).startswith("accepted")


def test_without_anything_in_view_navigation_may_be_offered():
    out = _outputs("Hôm nay mình nên làm gì?", focused=False)
    assert out.handle(PROPOSE_ACTION, NAVIGATE, known_evidence=frozenset()).startswith("accepted")


def test_saving_the_selected_word_is_still_offered():
    out = _outputs("Từ này nghĩa là gì ở đây?")
    action = {"type": "save_word", "payload": {"text": "花生", "lang": "zh-CN"}}
    out.learn_ids("text", ("花生",))
    answer = out.handle(PROPOSE_ACTION, action, known_evidence=frozenset())
    assert not answer.startswith("refused: the learner asks about what is in view")


def test_with_a_heading_asked_a_later_bold_line_is_a_sub_heading():
    gate = ClaimGate(interface="vi", support="vi")
    gate.heading_asked = True
    out = gate.feed("### Từ vựng: 花生\n**Nghĩa chính:** hạt lạc.\n**Ví dụ minh họa**\n1. 我爱吃花生。\n")
    out += gate.finish(None)
    assert "".join(out) == "### Từ vựng: 花生\n**Nghĩa chính:** hạt lạc.\n#### Ví dụ minh họa\n1. 我爱吃花生。\n"


def test_without_a_heading_asked_bold_lines_stay():
    gate = ClaimGate(interface="vi", support="vi")
    out = gate.feed("Nghĩa: hạt lạc.\n**Ví dụ minh họa**\n") + gate.finish(None)
    assert "".join(out) == "Nghĩa: hạt lạc.\n**Ví dụ minh họa**\n"
