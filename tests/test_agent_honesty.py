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
    assert offer_instead("Saved!", "Save word", interface="en", support="en") == "Saved!"  # no claim pattern: left
    assert offer_instead("It has been saved.", "Save word", interface="en", support="en") == "Tap “Save word” if you want to."
    assert offer_instead("已保存。", "保存单词", interface="zh-CN", support="zh-CN") == "需要的话，点击“保存单词”。"
