"""An action is offered, never reported as done (agent/honesty.py)."""

from __future__ import annotations

import pytest

from writing_coach.agent.honesty import claims_done, offer_instead


@pytest.mark.parametrize(
    "text",
    [
        "Từ 我 đã được lưu vào danh sách của bạn.",
        "Mình đã lưu từ này rồi.",
        "Đã thêm vào bộ sưu tập.",
        "Lưu xong rồi nhé!",
        "The word has been saved.",
        "I've added it to your deck.",
        "It is now saved.",
        "我已经帮你保存了这个词。",
        "已添加到词库。",
        "收藏好了！",
    ],
)
def test_a_completion_is_a_claim(text):
    assert claims_done(text)


@pytest.mark.parametrize(
    "text",
    [
        "Bấm Lưu từ để lưu 我.",
        "Mình lưu 我 cho bạn nhé.",
        "Tap Save word to keep it.",
        "点击“保存”即可。",
        "Bộ chấm chưa đánh dấu lỗi nào trong bài này.",
        "Màn này giữ các từ bạn đã lưu.",  # the learner's own past, not Orena's claim
        "Bạn đã lưu 12 từ tuần này.",
    ],
)
def test_an_offer_is_not(text):
    assert not claims_done(text)


def test_only_the_claiming_sentences_are_replaced():
    text = "Từ 我 nghĩa là tôi. Nó đã được lưu vào danh sách. Hãy ôn lại mỗi ngày."
    assert offer_instead(text, "Lưu từ", interface="vi", support="vi") == (
        "Từ 我 nghĩa là tôi. Hãy ôn lại mỗi ngày. Bấm “Lưu từ” nếu bạn muốn."
    )
    assert offer_instead("Saved!", "Save word", interface="en", support="en") == "Tap “Save word” if you want to."
    assert offer_instead("It has been saved.", "Save word", interface="en", support="en") == "Tap “Save word” if you want to."
    assert offer_instead("已保存。", "保存单词", interface="zh-CN", support="zh-CN") == "需要的话，点击“保存单词”。"


# --- adversarial review ---------------------------------------------------------------------

from writing_coach.agent.honesty import ClaimGate, claims_acted  # noqa: E402


@pytest.mark.parametrize(
    "text",
    ["Mình lưu 是 cho bạn rồi nhé!", "Mình vừa lưu 是 cho bạn.", "Orena thêm 是 vào bộ sưu tập rồi nhé.",
     "Saved!", "Done, saved.", "我帮你保存了这个词。"],
)  # fmt: skip
def test_the_common_ways_of_saying_it_acted_are_claims(text):
    assert claims_acted(text) and claims_done(text)


def test_a_question_is_never_a_claim():
    assert not claims_done("Đã mở phần Ngữ pháp chưa?") and not claims_done("Has it been saved?")
    text = "Ngữ pháp này khá quan trọng đó. Đã mở phần Ngữ pháp chưa? Bấm vào để xem thêm nhé."
    assert offer_instead(text, "Mở Ngữ pháp", interface="vi", support="vi") == text


def gated(text, offer):
    gate = ClaimGate(interface="vi", support="vi")
    streamed = []
    for piece in (text[i : i + 7] for i in range(0, len(text), 7)):
        streamed += gate.feed(piece)
    streamed += gate.finish(offer)
    assert "".join(streamed) == gate.text  # what was streamed is the segment
    return gate.text


def test_without_a_button_orena_saying_it_acted_is_dropped_and_a_read_state_kept():
    assert gated("Từ này nghĩa là cơ hội. Mình đã lưu nó cho bạn rồi.", None) == "Từ này nghĩa là cơ hội. "
    kept = "Từ serendipity đã được lưu vào danh sách của bạn rồi."  # a state a tool read, no pending button
    assert gated(kept, None) == kept
    assert gated("Mình đã lưu từ này rồi.", None) == "Mình chưa thay đổi gì cả."


def test_with_a_button_both_kinds_are_dropped_and_the_button_offered():
    text = gated("Từ 我 đã được lưu. Mình đã thêm nó vào sổ.", "Bấm “Lưu từ” nếu bạn muốn.")
    assert text == "Bấm “Lưu từ” nếu bạn muốn."
