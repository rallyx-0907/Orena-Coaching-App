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
    offer = "Bấm Lưu từ để thêm 我 vào từ vựng của bạn."
    assert offer_instead(text, offer, interface="vi", support="vi") == (
        "Từ 我 nghĩa là tôi. Hãy ôn lại mỗi ngày. Bấm Lưu từ để thêm 我 vào từ vựng của bạn."
    )
    assert offer_instead("Saved!", "Tap Save word.", interface="en", support="en") == "Tap Save word."
    assert offer_instead("It has been saved.", "Tap Save word.", interface="en", support="en") == "Tap Save word."
    assert offer_instead("已保存。", "点击“保存”。", interface="zh-CN", support="zh-CN") == "点击“保存”。"


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
    assert offer_instead(text, "Bấm Mở Ngữ pháp để mở.", interface="vi", support="vi") == text


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


# --- the offer is built from the action in hand (human direction 2026-09-28) ------------------

from writing_coach.agent.honesty import offer_for  # noqa: E402


def test_the_offer_is_built_from_the_action():
    word = {"text": "我", "lang": "zh-CN"}
    assert offer_for("save_word", "Lưu từ", word, interface="vi", support="vi") == "Bấm Lưu từ để thêm 我 vào từ vựng của bạn."
    assert offer_for("save_word", "Save word", {"text": "apple", "lang": "en"}, interface="en", support="en") == (
        "Tap Save word to add apple to your words."
    )
    assert offer_for("save_word", "保存单词", word, interface="zh-CN", support="zh-CN") == "点击“保存单词”，把我加入你的词汇。"
    assert offer_for("start_review", "Ôn ngay", {"scope": "due"}, interface="vi", support="vi") == "Bấm Ôn ngay để bắt đầu ôn."
    assert offer_for("navigate", "Sửa bài", {"intent": "writing.revision"}, interface="vi", support="vi") == "Bấm Sửa bài để mở."
    # an action with no sentence of its own falls back to the plain offer
    assert offer_for("play_model", "Nghe mẫu", {"content_id": "c1"}, interface="vi", support="vi") == "Bấm Nghe mẫu nếu bạn muốn."


def test_a_claim_is_held_before_it_is_streamed():
    """The filter runs on the way out, a sentence at a time: a claim never reaches the client, even briefly."""

    gate = ClaimGate(interface="vi", support="vi")
    out = []
    for piece in ["Từ này nghĩa là tôi. Mình đ", "ã lưu nó rồi", ". Ôn nó mỗi ngày nhé."]:
        out.append(gate.feed(piece))
    assert out == [["Từ này nghĩa là tôi. "], [], []]  # the claim and everything after it are held
    assert gate.finish("Bấm Lưu từ để thêm 我 vào từ vựng của bạn.") == [
        "Ôn nó mỗi ngày nhé. Bấm Lưu từ để thêm 我 vào từ vựng của bạn."
    ]


@pytest.mark.parametrize("text", ["Mình đã ghi nhớ từ 我 giúp bạn rồi nhé!", "我已经帮你记录下了这个词。"])
def test_the_live_runs_other_verbs_are_claims_too(text):
    assert claims_acted(text)
