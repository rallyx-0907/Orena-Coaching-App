"""What the server writes into an answer, never the model (human direction 2026-09-28, after the Slice 3 live run):

- the one offer of a proposed button, in the interface layer and the learner's address pair; the model's own
  "Bấm…/Tap…/点击…" sentences are dropped, and with no button there is no offer;
- a coach note the learner changes or cancels: asked once more with its id, then said plainly if unchanged;
- the opening greeting: a fact from the snapshot, or one built from it, never a generic line.
"""

from __future__ import annotations

import pytest

from writing_coach.agent.address import Address, address_note
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply
from writing_coach.agent.greeting import built, numbers_in, states_a_fact
from writing_coach.agent.honesty import ClaimGate, offer, offers_a_button
from writing_coach.agent.notes import notes_the_message_changes
from writing_coach.agent.outputs import FORGET_NOTE, PROPOSE_ACTION, REMEMBER_NOTE
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.schemas import CoachNote, TurnRequest
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime

ZH = LearnerScope(user_key="learner-1", language="zh")
SHORT = CoachNote.model_validate(
    {"id": "n-abc1234567", "kind": "preference", "text": "Thích ví dụ thật ngắn", "weight": 0.6,
     "last_reinforced": "2026-09-28T06:14:30+00:00", "expires_at": None}  # fmt: skip
)


def address(self_term: str, user_term: str, support: str = "vi") -> CoachNote:
    """The address note as the device keeps it (§5.6); it travels as context.address, never in coach_notes."""

    return CoachNote.model_validate(address_note(support, self_term, user_term))


def chosen(self_term: str, user_term: str, support: str = "vi") -> Address:
    return Address(self_term, user_term, chosen=True, lang=support)


def request(message, *, interface="vi", support="vi", notes=(), trigger="message", actions=("save_word", "navigate"),
            addressed=None):  # fmt: skip
    body = {
        "contract_version": 5,
        "trigger": trigger,
        "client": {"ui_version": "t", "supported_actions": list(actions), "supported_intents": ["vocabulary.review_due"]},
        "context": {
            "surface": "vocabulary.my_language",
            "locale": {"interface": interface, "support": support, "target": "zh-CN"},
            "selected_item": {"type": "word", "text": "我", "lang": "zh-CN"},
        },
        "coach_notes": [n.model_dump(mode="json") for n in notes if n.kind != "address"],
    }
    if addressed is not None:
        body["context"]["address"] = addressed
    if message is not None:
        body["message"] = message
    return TurnRequest.model_validate(body)


def run(rounds, req):
    tools = build_tool_registry(writing_review=lambda essay_id: None)
    provider = FakeAgentTurnProvider(list(rounds))
    rt = AgentRuntime(provider=provider, tools=tools, capabilities=load_capability_registry(registered_tools=tools.names()),
                      sessions=SessionCache())  # fmt: skip
    return list(rt.run(req, ZH)), provider


def segments(events):
    return [(e.lang, e.text) for e in events if e.name == "segment_end"]


def deltas(events, index=0):
    return "".join(e.text_delta for e in events if e.name == "segment_delta" and e.index == index)


SAVE = (
    ToolCallRequest("c1", PROPOSE_ACTION, {"type": "save_word", "payload": {"text": "我", "lang": "zh-CN"}}),
    TurnFinished(0, 5, "tool_calls"),
)


# --- 1. the offer is the server's -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "support"),
    [
        ("Bấm Ôn tập từ vựng để ôn lại các từ đang đến hạn.", "vi"),
        ("Bấm vào nút bên dưới để lưu từ 我 nhé!", "vi"),
        ("Bạn có thể bấm Lưu từ.", "vi"),
        ("Hãy nhấn nút Lưu.", "vi"),
        ("Tap **Save word** below to add it to your collection!", "en"),
        ("You can tap Save word.", "en"),
        ("你可以点击下方的按钮把它保存到生词本里：", "zh-CN"),
        ("点击“保存单词”。", "zh-CN"),
    ],
)
def test_the_models_own_offer_is_recognised(sentence, support):
    assert offers_a_button(sentence, support)


@pytest.mark.parametrize(
    ("sentence", "support"),
    [
        ("Từ 点击 nghĩa là bấm chuột.", "vi"),  # a target word being explained
        ("Click nghĩa là nhấp chuột.", "vi"),  # an English word, read with the Vietnamese rule
        ("Từ này dùng khi bạn muốn lưu lại điều gì đó.", "vi"),
        ("The word 'tap' also means a faucet.", "en"),
        ("“点击”的意思是用鼠标按。", "zh-CN"),
        # review 2026-09-28: a tapping verb alone is not an offer
        ("Nhấn mạnh vào thanh điệu nhé.", "vi"),
        ("Nhấn giọng ở âm tiết thứ hai.", "vi"),
        ("Chạm vào trái tim người nghe là điều khó.", "vi"),
        ("Bạn đã bấm Lưu từ chưa?", "vi"),  # a question
        ("Tap water is safe here.", "en"),
        ("Press releases are formal.", "en"),
        ("点击率很高。", "zh-CN"),
        # second review: a bare "to"/"để" names no button
        ("Press to continue with the next question.", "en"),
        ("Click to copy the sentence.", "en"),
        ("Tap to hear it again.", "en"),
        ("Nhấn để xem thêm câu tiếp theo.", "vi"),
        ("Chạm để tiếp tục.", "vi"),
        ("Press your tongue against your teeth.", "en"),
        ("Nhấn mạnh chữ 学 nhé.", "vi"),
    ],
)
def test_a_word_being_explained_is_not_an_offer(sentence, support):
    assert not offers_a_button(sentence, support)


def test_an_answer_that_only_emphasises_is_kept_whole():
    gate = ClaimGate(interface="vi", support="vi")
    out = gate.feed("Nhấn mạnh vào thanh điệu nhé. ")
    out += gate.finish(None, pending=False)
    assert "".join(out) == "Nhấn mạnh vào thanh điệu nhé. "  # never "Mình chưa thay đổi gì cả."


@pytest.mark.parametrize(
    ("sentence", "support"),
    [("Em bấm Lưu từ nhé.", "vi"), ("Bấm vào đây để mở.", "vi"), ("Bấm *Ôn từ ngay* để ôn.", "vi"),
     ("Press the button below.", "en"), ("Click here to start.", "en"), ("请点击这里开始。", "zh-CN"),
     # second review: small words between the verb and the button
     ("Tap the Save word button.", "en"), ("Press the Save button.", "en"), ("Click the “Save word” button.", "en"),
     ("Tap a button below.", "en"), ("Tap on the Save button.", "en"), ("Bấm vào cái nút Lưu từ.", "vi"),
     ("Bấm ngay nút Lưu từ.", "vi"), ("Bấm vào để xem thêm nhé.", "vi"), ("点击保存按钮", "zh-CN")],
)  # fmt: skip
def test_an_offer_names_a_button(sentence, support):
    assert offers_a_button(sentence, support)


def test_with_no_button_there_is_no_offer():
    gate = ClaimGate(interface="vi", support="vi")
    out = gate.feed("Hiện tại bạn có 3 từ đến hạn ôn. Bấm Ôn tập từ vựng để ôn lại các từ đang đến hạn.")
    out += gate.finish(None)
    assert "".join(out) == "Hiện tại bạn có 3 từ đến hạn ôn. "


def test_with_a_button_the_servers_offer_replaces_the_models():
    events, _ = run([(TextDelta("Nghĩa là tôi. Bấm vào nút bên dưới để lưu từ 我 nhé!"), *SAVE)],
                    request("Lưu từ này giúp mình."))  # fmt: skip
    assert segments(events)[0] == ("vi", "Nghĩa là tôi. Bấm Lưu từ để thêm 我 vào từ vựng của bạn.")
    assert deltas(events) == segments(events)[0][1]  # what streamed is the segment


def test_the_offer_is_in_the_learners_address_pair():
    lang, text = offer("save_word", "Lưu từ", {"text": "我"}, interface="vi", support="vi", address=chosen("em", "anh"))
    assert (lang, text) == ("vi", "Bấm Lưu từ để thêm 我 vào từ vựng của anh.")
    assert offer("save_word", "保存单词", {"text": "我"}, interface="zh-CN", support="zh-CN",
                 address=chosen("我", "您", "zh-CN"))[1] == (
        "点击“保存单词”，把我加入您的词汇。"
    )
    events, _ = run([(TextDelta("Nghĩa là tôi."), *SAVE)],
                    request("Lưu từ này giúp em.", addressed={"self": "chị", "user": "em", "lang": "vi"}))  # fmt: skip
    assert segments(events)[0][1].endswith("Bấm Lưu từ để thêm 我 vào từ vựng của em.")


def test_the_offer_is_in_the_interface_layer_apart_when_it_differs():
    events, _ = run([(TextDelta("Nghĩa là tôi."), *SAVE)],
                    request("Lưu từ này giúp mình.", interface="en", support="vi"))  # fmt: skip
    first, second = segments(events)[:2]
    assert first == ("vi", "Nghĩa là tôi.")  # the answer, in the support language
    assert second[0] == "en" and second[1].startswith("Tap ") and second[1].endswith(" to add 我 to your words.")
    assert deltas(events, 1) == segments(events)[1][1]


# --- 2. a coach note changed or cancelled -------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "À không, ví dụ dài hơn một chút thì mình dễ hiểu hơn.",
        "Quên ghi chú về ví dụ đó đi.",
        "Thôi, đừng nhớ chuyện ví dụ ngắn nữa.",
    ],
)
def test_a_change_of_a_note_is_recognised(message):
    assert notes_the_message_changes(message, (SHORT, address("chị", "em"))) == (SHORT,)


@pytest.mark.parametrize(
    "message",
    [
        "Cho mình một ví dụ với 朋友.",  # no change asked
        "Thôi, mình đi ngủ đây.",  # a word of change, no note named
        "Đổi sang từ khác nhé.",
    ],
)
def test_anything_else_is_not(message):
    assert notes_the_message_changes(message, (SHORT,)) == ()


def test_the_address_note_is_never_one_of_them():
    assert notes_the_message_changes("Quên ghi chú đi.", (address("chị", "em"),)) == ()


def test_a_note_ignored_is_asked_once_more_and_then_forgotten():
    forget = (ToolCallRequest("c1", FORGET_NOTE, {"id": SHORT.id}), TurnFinished(0, 3, "tool_calls"))
    events, provider = run(
        [reply("Bạn chưa lưu ghi chú nào về ví dụ đó."), forget, reply("Mình đã quên ghi chú đó rồi.")],
        request("Quên ghi chú về ví dụ đó đi.", notes=(SHORT,)),
    )
    updates = [{"op": e.op, "note": e.note} for e in events if e.name == "memory_update"]
    assert updates == [{"op": "remove", "note": {"id": SHORT.id}}]
    asked = provider.requests[1].messages[-1]
    assert asked.role == "user" and SHORT.id in asked.content  # asked again, with its id
    text = segments(events)[0][1]
    assert "chưa lưu ghi chú" not in text  # the first answer never reached the learner
    assert text == "Mình đã quên ghi chú đó rồi." == deltas(events)


def test_a_note_ignored_twice_is_said_plainly_in_the_learners_address():
    events, provider = run(
        [reply("Mình hiểu rồi."), reply("Để chị lấy ví dụ dài hơn nhé.")],
        request("À không, ví dụ dài hơn một chút thì em dễ hiểu hơn.", notes=(SHORT,),
                addressed={"self": "chị", "user": "em", "lang": "vi"}),
    )
    assert len(provider.requests) == 2  # once more, not more
    assert not [e for e in events if e.name == "memory_update"]
    assert segments(events)[0][1] == "Chị chưa sửa hay xoá ghi chú nào của em. Em nói rõ ghi chú nào cần sửa hoặc xoá nhé?"


def test_a_correction_done_at_once_is_not_asked_again():
    correct = (
        ToolCallRequest("c1", REMEMBER_NOTE, {"kind": "preference", "text": "Thích ví dụ dài hơn", "replaces": SHORT.id}),
        TurnFinished(0, 3, "tool_calls"),
    )
    events, provider = run([correct, reply("Mình ghi nhớ rồi nhé.")],
                           request("À không, ví dụ dài hơn thì dễ hiểu hơn.", notes=(SHORT,)))  # fmt: skip
    assert len(provider.requests) == 2  # the tool round and the answer: no extra ask
    assert [e.note["id"] for e in events if e.name == "memory_update"] == [SHORT.id]


# --- 3. the opening greeting states a fact from the snapshot ---------------------------------------


def snapshot(due=3, counts=None, readable=True):
    skills = {}
    for name, count in (counts or {}).items():
        skills[name] = {"name": name.capitalize(), "state": "x",
                        "activity": {"what": "bài viết", "count": count, "at_least": False} if readable else None}  # fmt: skip
    return {"target": "zh-CN", "window_days": 30, "skill_summary": skills, "review_due": due, "recent_sessions": []}


def test_a_greeting_with_a_fact_of_the_snapshot_is_kept():
    assert states_a_fact("Chào bạn! Hôm nay bạn có 3 từ đến hạn ôn.", snapshot(due=3))
    assert states_a_fact("你好！今天你有三个词需要复习。", snapshot(due=3))
    assert states_a_fact("Hi! You have three words due today.", snapshot(due=3))


@pytest.mark.parametrize(
    "greeting",
    [
        "Chào bạn, mình là trợ lý tiếng Trung của bạn. Hôm nay chúng ta cùng học nhé!",  # the live run's
        "Chào bạn! Hôm nay bạn có 5 từ đến hạn ôn.",  # a number the snapshot does not hold
        "Chào bạn! Bạn có 3 từ đến hạn và 7 bài viết.",  # one right, one invented
    ],
)
def test_a_generic_or_invented_greeting_is_not(greeting):
    assert not states_a_fact(greeting, snapshot(due=3, counts={"writing": 2}))


def test_the_built_greeting_is_one_fact_in_the_learners_address():
    assert built(snapshot(due=3), interface="vi", support="vi") == "Chào bạn! Hôm nay bạn có 3 từ đến hạn ôn."
    assert built(snapshot(due=3), interface="vi", support="vi", address=chosen("em", "anh")) == (
        "Chào anh! Hôm nay anh có 3 từ đến hạn ôn."
    )
    assert built(snapshot(due=0, counts={"writing": 2, "reading": 5}), interface="vi", support="vi") == (
        "Chào bạn! 30 ngày qua bạn có 5 bài viết ở phần Reading."
    )
    assert built(snapshot(due=0), interface="vi", support="vi") == "Chào bạn! 30 ngày qua chưa có hoạt động nào được ghi lại."
    assert built(None, interface="vi", support="vi") == "Chào bạn! Mình chưa đọc được tiến độ lúc này."
    assert built(snapshot(due=2), interface="zh-CN", support="zh-CN") == "你好！今天你有2个词需要复习。"
    assert built(snapshot(due=2), interface="en", support="en") == "Hi! You have 2 words due for review today."


def test_numbers_are_read_in_digits_and_words():
    assert numbers_in("Bạn có ba từ và 12 bài.") == {3, 12}
    assert numbers_in("今天有两个词") == {2}


def test_an_opening_with_a_generic_greeting_gets_the_built_one(monkeypatch):
    from writing_coach.agent import coaching

    monkeypatch.setattr(coaching, "_due_count", lambda: 3)  # the snapshot the server reads: 3 words due
    events, provider = run([reply("Chào bạn, mình là trợ lý tiếng Trung của bạn. Hôm nay chúng ta cùng học nhé!")],
                           request(None, trigger="open"))  # fmt: skip
    assert any('"review_due": 3' in m.content for m in provider.requests[0].messages)  # the model had the fact
    assert segments(events)[0][1] == "Chào bạn! Hôm nay bạn có 3 từ đến hạn ôn."


def test_an_opening_that_states_the_fact_is_kept(monkeypatch):
    from writing_coach.agent import coaching

    monkeypatch.setattr(coaching, "_due_count", lambda: 3)
    events, _ = run([reply("Chào bạn! Hôm nay có 3 từ đang chờ bạn ôn.")], request(None, trigger="open"))
    assert segments(events)[0][1] == "Chào bạn! Hôm nay có 3 từ đang chờ bạn ôn."


def test_an_opening_with_an_unread_snapshot_says_so(monkeypatch):
    from writing_coach.agent import coaching

    monkeypatch.setattr(coaching, "_due_count", lambda: None)
    events, _ = run([reply("Chào bạn! Hôm nay mình cùng học nhé.")], request(None, trigger="open"))
    assert segments(events)[0][1] == "Chào bạn! Mình chưa đọc được tiến độ lúc này."


def test_a_note_turn_that_fails_after_asking_again_says_so_in_the_log(caplog):
    import logging

    from writing_coach.agent.errors import ProviderUnavailable

    class Failing(FakeAgentTurnProvider):
        def stream(self, request, **kw):
            if len(self.requests) >= 1:  # the second round (after the nudge) is refused
                self.requests.append(request)
                raise ProviderUnavailable("503")
            return super().stream(request, **kw)

    tools = build_tool_registry(writing_review=lambda essay_id: None)
    rt = AgentRuntime(provider=Failing([reply("Bạn chưa lưu ghi chú nào.")]), tools=tools,
                      capabilities=load_capability_registry(registered_tools=tools.names()), sessions=SessionCache())  # fmt: skip
    caplog.set_level(logging.WARNING)
    events = list(rt.run(request("Quên ghi chú về ví dụ đó đi.", notes=(SHORT,)), ZH))
    assert events[-1].name == "error"
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("agent notes:")]
    assert lines == ["agent notes: the model changed no note of 1; asked again", "agent notes: failed before a verdict"]
