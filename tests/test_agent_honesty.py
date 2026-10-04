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
    ["Mình lưu 是 cho bạn rồi nhé!", "Mình vừa lưu 是 cho bạn.", "Mình lưu 我 cho bạn nhé.", "Mình sẽ lưu nó cho bạn.", "Orena thêm 是 vào bộ sưu tập rồi nhé.",
     "Saved!", "Done, saved.", "我帮你保存了这个词。"],
)  # fmt: skip
def test_the_common_ways_of_saying_it_acted_are_claims(text):
    assert claims_acted(text) and claims_done(text)


def test_a_question_is_never_a_claim():
    assert not claims_done("Đã mở phần Ngữ pháp chưa?") and not claims_done("Has it been saved?")
    text = "Ngữ pháp này khá quan trọng đó. Đã mở phần Ngữ pháp chưa? Bấm vào để xem thêm nhé."
    assert offer_instead(text, "Bấm Mở Ngữ pháp để mở.", interface="vi", support="vi") == (
        "Ngữ pháp này khá quan trọng đó. Đã mở phần Ngữ pháp chưa? Bấm Mở Ngữ pháp để mở."
    )  # the question stays; the model's own offer gives way to the server's


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


# Live run 2026-09-28: beside "Ôn từ đến hạn", "Từ 朋友 đã được lưu…" was dropped as a claim and the offer
# came twice. A completion without an actor is a claim only when it is what the pending button would do.
@pytest.mark.parametrize(
    ("sentence", "action"),
    [
        ("Từ 朋友 đã được lưu trong thư viện của bạn.", "start_review"),
        ("Từ 朋友 đã được lưu trong thư viện của bạn.", "navigate"),
        ("This word has been saved to your library.", "start_review"),
        ("这个词已经保存在你的词库里。", "navigate"),
    ],
)
def test_a_state_a_tool_read_is_not_a_claim_beside_another_button(sentence, action):
    assert not claims_done(sentence, action=action)


@pytest.mark.parametrize(
    ("sentence", "action"),
    [
        ("Từ 我 đã được lưu.", "save_word"),
        ("It has been saved.", "add_word_to_collection"),
        ("已保存。", "save_word"),
        ("Phần ôn tập đã được bắt đầu.", "start_review"),
        ("Từ này đã được xoá.", "unsave_word"),
        ("Mình đã lưu từ này rồi.", "start_review"),  # Orena acting is a claim beside any button
    ],
)
def test_the_pending_buttons_own_completion_is_still_a_claim(sentence, action):
    assert claims_done(sentence, action=action)


def test_the_offer_comes_once_and_is_the_servers():
    gate = ClaimGate(interface="vi", support="vi")
    streamed = gate.feed("Bấm Ôn từ đến hạn để bắt đầu ôn tập. Ôn tập đã được bắt đầu.")
    streamed += gate.finish("Bấm Ôn từ đến hạn để mở.", action="start_review")
    assert "".join(streamed) == "Bấm Ôn từ đến hạn để mở."
    text = "Bấm Ôn từ đến hạn để ôn. Đã bắt đầu ôn."
    assert offer_instead(text, "Bấm Ôn từ đến hạn để mở.", interface="vi", support="vi", action="start_review") == (
        "Bấm Ôn từ đến hạn để mở."
    )


def test_a_true_state_stays_and_the_offer_comes_once():
    gate = ClaimGate(interface="vi", support="vi")
    streamed = gate.feed("Từ 朋友 đã được lưu trong thư viện của bạn và đang đến hạn ôn.")
    streamed += gate.finish("Bấm Ôn từ đến hạn để mở.", action="start_review")
    assert "".join(streamed) == "Từ 朋友 đã được lưu trong thư viện của bạn và đang đến hạn ôn. Bấm Ôn từ đến hạn để mở."


# Contract v5 (D-096) §7: a reply that comes with an action offers it. The old S5 line "Mình lưu 我 cho bạn nhé."
# is a claim, and so is the same line in the learner's own address (§5.6).
from writing_coach.agent.address import resolve  # noqa: E402

CHI_EM = resolve({"self": "chị", "user": "em", "lang": "vi"}, "vi")
NIN = resolve({"register": "polite", "lang": "zh-CN"}, "zh-CN")
XIAOMING = resolve({"user": "小明", "lang": "zh-CN"}, "zh-CN")


@pytest.mark.parametrize(
    ("sentence", "address"),
    [
        ("Mình lưu 我 cho bạn nhé.", None),  # the v4 S5 line
        ("Chị lưu 我 cho em nhé.", CHI_EM),
        ("Chị đã lưu từ này rồi.", CHI_EM),
        ("Chị vừa thêm 我 vào từ vựng.", CHI_EM),
        ("Chị sẽ lưu nó cho em.", CHI_EM),
        ("我帮您保存了这个词。", NIN),
        ("我帮小明保存了。", XIAOMING),
    ],
)
def test_the_old_s5_line_and_its_addressed_forms_are_claims(sentence, address):
    assert claims_acted(sentence, address=address) and claims_done(sentence, address=address)


@pytest.mark.parametrize(
    ("sentence", "address"),
    [
        ("Em đã lưu từ này trong thư viện rồi.", CHI_EM),  # the learner (em) did it: a state, not Orena's act
        ("Chị lưu từ này chưa?", CHI_EM),  # a question
        ("Bấm Lưu từ để thêm 我 vào từ vựng của em.", CHI_EM),  # what the button will do
    ],
)
def test_the_learners_own_act_a_question_or_the_offer_is_not(sentence, address):
    assert not claims_acted(sentence, address=address)


def test_through_a_turn_the_addressed_claim_gives_way_to_the_offer():
    from writing_coach.agent.capability_registry import load_capability_registry
    from writing_coach.agent.fake_provider import FakeAgentTurnProvider
    from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
    from writing_coach.agent.runtime import build_tool_registry
    from writing_coach.agent.schemas import TurnRequest
    from writing_coach.agent.session import SessionCache
    from writing_coach.agent.tools import LearnerScope
    from writing_coach.agent.turn import AgentRuntime

    tools = build_tool_registry(writing_review=lambda essay_id: None)
    rounds = [(TextDelta("Chị lưu 我 cho em nhé."),
               ToolCallRequest("c1", "propose_action", {"type": "save_word", "payload": {"text": "我", "lang": "zh-CN"}}),
               TurnFinished(0, 5, "tool_calls"))]  # fmt: skip
    rt = AgentRuntime(provider=FakeAgentTurnProvider(rounds), tools=tools,
                      capabilities=load_capability_registry(registered_tools=tools.names()), sessions=SessionCache())  # fmt: skip
    body = {
        "contract_version": 5, "trigger": "message", "message": "Lưu từ này giúp em.",
        "client": {"ui_version": "t", "supported_actions": ["save_word"], "supported_intents": []},
        "context": {"surface": "vocabulary.word", "locale": {"interface": "vi", "support": "vi", "target": "zh-CN"},
                    "selected_item": {"type": "word", "text": "我", "lang": "zh-CN"},
                    "address": {"self": "chị", "user": "em", "lang": "vi"}},
    }  # fmt: skip
    events = list(rt.run(TurnRequest.model_validate(body), LearnerScope(user_key="u", language="zh")))
    text = next(e.text for e in events if e.name == "segment_end")
    assert text == "Bấm Lưu từ để thêm 我 vào từ vựng của em."  # S5 (v5), in the learner's address


# --- dogfood gate 3.5: forms the audit found getting through -------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Mình đã đưa bạn tới phần Ngữ pháp.",
        "I moved you to Grammar.",
        "I've taken you to your review.",
        "I've gone ahead and saved it.",
        "Opening the review page now.",
        "已为你保存。",
        "已帮你打开复习。",
        "我打开了设置。",
        "我把它加入词库了。",
    ],
)
def test_more_ways_of_saying_it_acted_are_claims(text):
    assert claims_acted(text)


@pytest.mark.parametrize(
    "text",
    [
        "Mình sẽ đưa ra ví dụ cho bạn.",
        "Mình đưa bạn đến phần Ôn tập nhé?",
        "Adding a comma now makes it correct.",
        "我打开了门。",
        "我收藏了很多书。",
        "我删除了文件。",
        "我加入了俱乐部。",
        "我把门打开了。",
        "我开始了解你的学习情况。",
        "Taken together, these words are due tomorrow.",
        "You moved to Grammar yesterday.",
        "Bạn muốn mình mở phần ôn tập không?",
    ],
)
def test_their_harmless_neighbours_are_not(text):
    assert not claims_acted(text)
