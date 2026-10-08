"""Slice 3: the snapshot, weaknesses and next activities (deterministic, measured only), and coach notes."""

from __future__ import annotations

import json

import pytest

from writing_coach import becoming_library
from writing_coach.agent.coaching import recommendations, snapshot, weaknesses
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply
from writing_coach.agent.notes import asks_to_remember, asks_to_remember_unaccented, confirmed_note
from writing_coach.agent.outputs import FORGET_NOTE, REMEMBER_NOTE, ReplyOutputs, reply_tool_specs
from writing_coach.agent.provider import TextDelta, ToolCallRequest, TurnFinished
from writing_coach.agent.runtime import AppReads, build_tool_registry
from writing_coach.agent.schemas import ClientInfo, TurnRequest
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime

ZH = LearnerScope(user_key="learner-1", language="zh", interface="vi")

SUMMARY = {
    "domains": {
        "writing": {"status": "current", "activity": {"label": "submitted_versions", "count": 2, "countKind": "exact",
                    "lastObservedAt": "2026-09-27T08:00:00+00:00"},
                    "observations": [
                        {"measure": "overall", "value": 64.0, "synthetic": False, "assisted": None,
                         "observedAt": "2026-09-27T08:00:00+00:00", "producer": "gemini"},
                        {"measure": "overall", "value": 99.0, "synthetic": True, "assisted": None,
                         "observedAt": "2026-09-26T08:00:00+00:00", "producer": "fallback-demo"},
                    ]},
        "reading": {"status": "empty", "activity": {"label": "checks_answered", "count": 0, "countKind": "exact",
                    "lastObservedAt": None}, "observations": []},
        "listening": {"status": "unavailable"},
        "speaking": {"status": "current", "activity": {"label": "takes", "count": 50, "countKind": "at_least",
                     "lastObservedAt": "2026-09-28T08:00:00+00:00"},
                     "observations": [{"measure": "speaking_dimensions", "value": {"pronunciation": 72.0},
                                       "synthetic": False, "assisted": None, "observedAt": "2026-09-28T08:00:00+00:00"}]},
        "grammar": {"status": "empty", "activity": {"label": "patterns_marked_complete", "count": 0,
                    "countKind": "exact", "lastObservedAt": None}, "observations": []},
        "language": {"status": "current", "activity": {"label": "phrases_kept", "count": 3, "countKind": "exact",
                     "lastObservedAt": None}, "observations": []},
    }
}  # fmt: skip


# --- the snapshot ----------------------------------------------------------------------------


def test_the_snapshot_holds_only_measured_numbers_named_in_the_interface_language():
    data = snapshot(SUMMARY, 12, "zh-CN", "vi")
    skills = data["skill_summary"]
    assert set(skills) == {"reading", "listening", "speaking", "writing", "vocabulary", "grammar"}  # §24, language -> vocabulary
    assert "current_level" not in data and data["review_due"] == 12 and data["target"] == "zh-CN"
    assert skills["listening"] == {"name": "Nghe", "state": "hiện không đọc được", "activity": None, "latest": None}
    assert skills["reading"]["activity"]["count"] == 0 and skills["reading"]["latest"] == []  # read and empty: 0 is true
    assert skills["writing"]["activity"]["what"] == "bản bài đã nộp"
    assert [m["value"] for m in skills["writing"]["latest"]] == [64.0]  # the demo evaluator's 99 is not a measurement
    assert skills["speaking"]["activity"]["at_least"] is True
    assert skills["speaking"]["latest"][0]["value"] == {"phát âm": 72.0}
    assert data["recent_sessions"][0]["skill"] == "Nói"
    assert "producer" not in json.dumps(data)


def test_an_unreadable_review_queue_is_null_not_zero():
    assert snapshot(SUMMARY, None, "zh-CN", "vi")["review_due"] is None


def test_the_snapshot_tool_reads_the_apps_summary_route(monkeypatch):
    monkeypatch.setattr(becoming_library, "library_summary", lambda: {"summary": {"due": 3}})
    windows = []
    tools = build_tool_registry(
        writing_review=lambda i: None, reads=AppReads(learner_summary=lambda window: windows.append(window) or SUMMARY)
    )
    result = tools.invoke("build_learning_snapshot", ZH, {})
    assert windows == ["30d"] and result.data["review_due"] == 3
    assert {e.ref["domain"] for e in result.evidence} == {"writing", "speaking"}  # skills with measurements


# --- weaknesses ------------------------------------------------------------------------------


def _attempt(*words):
    return {"evidence": {"pronunciation": {"words": [{"word": w, "error_type": e} for w, e in words]}}}


def test_weaknesses_are_counts_of_what_recurs_and_unread_is_null():
    found = weaknesses(
        history={"items": [{"category": "tense", "total": 3, "newer": 1}, {"category": "article", "total": 1}]},
        attempts=[_attempt(("是", "Mispronunciation"), ("我", "None")), _attempt(("是", "Mispronunciation")),
                  _attempt(("学", "Omission"))],
        listening=[{"checked_attempt_count": 2, "best_exact": False, "revealed": True, "score_source": "server"},
                   {"checked_attempt_count": 1, "best_exact": True, "revealed": False, "score_source": "server"},
                   {"checked_attempt_count": 3, "best_exact": False, "revealed": False, "score_source": "client"}],
        reading=None,
        vocabulary=[{"word": "机会", "lapse_count": 3}, {"word": "学习", "lapse_count": 1}],
        interface="vi",
    )  # fmt: skip
    assert found["writing"] == [{"category": "Thì", "times": 3, "recent_times": 1}]  # "article" once is not recurring
    assert found["speaking"] == [{"word": "是", "times_flagged": 2, "most_often": "Phát âm sai"}]
    assert found["listening"] == {"lines_worked_on": 3, "not_yet_exact": 1, "score_not_verified": 1, "answer_revealed": 1}
    assert found["reading"] is None  # not read here: unknown, never "no weakness"
    assert found["vocabulary"] == [{"word": "机会", "times_forgotten": 3}]
    assert found["grammar"] is None  # no mistake store: not measured, not guessed


def test_a_reader_that_fails_makes_its_skill_null(monkeypatch):
    monkeypatch.setattr(becoming_library, "list_library_vocabulary", lambda **k: {"items": []})

    def broken(*args, **kwargs):
        raise RuntimeError("PostgreSQL only")

    tools = build_tool_registry(writing_review=lambda i: None, writing_history=lambda: {"items": []},
                                reads=AppReads(speaking_attempts=broken, listening_recent=broken, reading_evidence=broken))  # fmt: skip
    data = tools.invoke("get_learning_weaknesses", ZH, {}).data["by_skill"]
    assert data["Nói"] is None and data["Nghe"] is None and data["Đọc"] is None
    assert data["Viết"] == [] and data["Từ vựng"] == []  # read, nothing recurs
    assert data["Ngữ pháp"] is None


# --- next activities -------------------------------------------------------------------------


def test_the_order_is_the_backends_and_each_item_carries_ids_a_navigate_may_name():
    cue = {"available": True, "source": "reading", "evidence": "The Early Train",
           "action": {"kind": "reading", "article_id": "a-1"}}  # fmt: skip
    items = recommendations(4, cue, "vi")
    assert [i["rank"] for i in items] == [1, 2]
    assert items[0]["open"] == {"intent": "vocabulary.review_due"} and items[0]["why"] == {"words_due": 4}
    assert items[1]["open"] == {"intent": "reading.workspace", "content_id": "article:a-1"}
    writing = recommendations(0, {"available": True, "evidence": "tense", "action": {"kind": "review", "essay_id": 9}}, "vi")
    assert writing == [{"rank": 1, "activity": "Viết", "why": {"from_your_record": "tense"},
                        "open": {"intent": "writing.review", "essay_id": "9"}}]  # fmt: skip
    listening = recommendations(0, {"available": True, "evidence": "s1", "action": {"kind": "listening", "asset_id": "m"}}, "vi")
    assert listening[0]["open"] is None  # a media asset is not the lesson the UI opens: said in words
    assert recommendations(None, {"available": False}, "vi") == []


def test_a_recommended_item_can_be_opened_by_navigate(monkeypatch):
    monkeypatch.setattr(becoming_library, "library_summary", lambda: {"summary": {"due": 0}})
    cue = {"available": True, "evidence": "tense", "action": {"kind": "review", "essay_id": 9}}
    result = build_tool_registry(writing_review=lambda i: None, reads=AppReads(cross_skill_cue=lambda: cue)).invoke(
        "get_recommended_next_activities", ZH, {}
    )
    client = ClientInfo.model_validate({"ui_version": "t", "supported_actions": ["navigate"], "supported_intents": ["writing.review"]})
    outputs = ReplyOutputs(client=client, interface="vi", support="vi", target="zh-CN", version=4)
    outputs.learn_from(result.data)
    payload = {"intent": "writing.review", "essay_id": "9"}
    assert outputs.handle("propose_action", {"type": "navigate", "payload": payload}, known_evidence=frozenset()).startswith("accepted")


# --- coach notes (layer 3, device memory) ------------------------------------------------------


def outputs(notes=None, opening=False, **asked):
    client = ClientInfo.model_validate({"ui_version": "t"})
    return ReplyOutputs(client=client, interface="vi", support="vi", target="zh-CN", version=4, opening=opening,
                        notes=notes or {}, **asked)  # fmt: skip


def test_a_note_the_learner_stated_is_kept_and_a_correction_replaces_it():
    out = outputs({"n-old": 0.6, "address-vi": 1.0}, learner_words="Nhớ giúp mình: thi HSK4 vào tháng 12.")
    assert out.handle(REMEMBER_NOTE, {"kind": "goal", "text": "Thi HSK4 vào tháng 12"}, known_evidence=frozenset()).startswith("accepted")
    new = out.memory_updates[0]
    assert new.op == "upsert" and new.note["id"].startswith("n-") and new.note["weight"] == 0.6
    assert new.note["expires_at"] is None and new.note["kind"] == "goal"
    out.correcting = out.asked = ("n-old",)  # the learner's next words correct that note: "À không, kỹ hơn"
    out.handle(REMEMBER_NOTE, {"kind": "preference", "text": "Giải thích kỹ hơn", "replaces": "n-old"}, known_evidence=frozenset())
    replaced = out.memory_updates[1]
    assert replaced.note["id"] == "n-old" and replaced.note["weight"] == 0.8  # reinforced
    assert out.handle(REMEMBER_NOTE, {"kind": "plan", "text": "x"}, known_evidence=frozenset()).startswith("refused: at most 2")


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        (REMEMBER_NOTE, {"kind": "feeling", "text": "buồn"}),
        (REMEMBER_NOTE, {"kind": "goal", "text": "x" * 201}),
        (REMEMBER_NOTE, {"kind": "goal", "text": "x", "replaces": "n-none"}),
        (REMEMBER_NOTE, {"kind": "goal", "text": "x", "replaces": "address-vi"}),
        (FORGET_NOTE, {"id": "n-none"}),
        (FORGET_NOTE, {"id": "address-vi"}),
    ],
)
def test_what_is_not_a_learner_stated_note_is_refused(tool, args):
    out = outputs({"address-vi": 1.0})
    assert out.handle(tool, args, known_evidence=frozenset()).startswith("refused") and out.memory_updates == []


def test_a_note_is_forgotten_on_request_and_nothing_is_kept_in_an_opening_turn():
    out = outputs({"n-1": 0.6}, learner_words="Quên ghi chú đó đi", asked=("n-1",), notes_intent="forget")
    out.handle(FORGET_NOTE, {"id": "n-1"}, known_evidence=frozenset())
    assert out.memory_updates[0].op == "remove" and out.memory_updates[0].note == {"id": "n-1"}
    assert outputs(opening=True).handle(REMEMBER_NOTE, {"kind": "goal", "text": "x"}, known_evidence=frozenset()).startswith("refused")
    names = {s.name for s in reply_tool_specs(ClientInfo.model_validate({"ui_version": "t"}), "zh-CN", version=4, opening=True)}
    assert REMEMBER_NOTE not in names and FORGET_NOTE not in names


def _runtime(rounds, **reads):
    tools = build_tool_registry(writing_review=lambda i: None, reads=AppReads(**reads))
    provider = FakeAgentTurnProvider(list(rounds))
    return AgentRuntime(provider=provider, tools=tools, sessions=SessionCache(),
                        capabilities=load_capability_registry(registered_tools=tools.names())), provider  # fmt: skip


def _request(message="Mình muốn thi HSK4 vào tháng 12.", *, trigger="message", notes=()):
    body = {
        "contract_version": 4, "trigger": trigger,
        "client": {"ui_version": "t", "supported_actions": ["start_review"], "supported_intents": []},
        "context": {"surface": "orena.home", "locale": {"interface": "vi", "support": "vi", "target": "zh-CN"}},
        "coach_notes": list(notes),
    }  # fmt: skip
    if message is not None:
        body["message"] = message
    return TurnRequest.model_validate(body)


def test_saying_a_note_is_kept_is_true_when_the_turn_keeps_it():
    rounds = [
        (TextDelta("Mình đã ghi nhớ mục tiêu HSK4 của bạn."),
         ToolCallRequest("c1", REMEMBER_NOTE, {"kind": "goal", "text": "Thi HSK4 vào tháng 12"}),
         TurnFinished(0, 3, "tool_calls")),
    ]  # fmt: skip
    rt, _ = _runtime(rounds)
    events = list(rt.run(_request("Nhớ giúp mình là mình muốn thi HSK4 vào tháng 12."), ZH))
    assert next(e for e in events if e.name == "segment_end").text == "Mình đã ghi nhớ mục tiêu HSK4 của bạn."
    # S14: a memory_update comes before the words that say it is applied
    assert [e.name for e in events][-3:] == ["memory_update", "segment_end", "done"]
    rt2, _ = _runtime([reply("Mình đã ghi nhớ từ 我 giúp bạn rồi.")])
    events2 = list(rt2.run(_request("Lưu 我 giúp mình."), ZH))  # nothing kept: remembering is a false claim
    assert "ghi nhớ" not in next(e for e in events2 if e.name == "segment_end").text


def test_the_notes_reach_the_model_with_their_ids_and_not_the_address():
    notes = [
        {"id": "n-1", "kind": "preference", "text": "Giải thích ngắn", "weight": 0.6, "last_reinforced": "2026-09-28T08:00:00+00:00"},
        {"id": "address-vi", "kind": "preference", "text": 'Xưng hô: Orena xưng "chị", gọi người học là "em".',
         "weight": 1.0, "last_reinforced": "2026-09-28T08:00:00+00:00"},
    ]  # fmt: skip
    rt, provider = _runtime([reply("Ok.")])
    list(rt.run(_request("Chào.", notes=notes), ZH))
    context = json.loads(next(m.content for m in provider.requests[0].messages if m.content.startswith("context: "))[9:])
    assert context["coach_notes"] == [{"id": "n-1", "kind": "preference", "text": "Giải thích ngắn"}]


# --- the opening turn is built on the snapshot (S13) ------------------------------------------


def test_the_opening_turn_is_built_on_the_snapshot_and_reads_nothing_itself(monkeypatch):
    monkeypatch.setattr(becoming_library, "library_summary", lambda: {"summary": {"due": 3}})
    rt, provider = _runtime([reply("Chào bạn, hôm nay có 3 từ đến hạn ôn.")], learner_summary=lambda window: SUMMARY)
    events = list(rt.run(_request(None, trigger="open"), ZH))
    assert [e.name for e in events if e.name not in ("segment_delta",)][:2] == ["session", "segment_end"]
    request = provider.requests[0]
    snap = next(m.content for m in request.messages if m.content.startswith("snapshot: "))
    assert json.loads(snap[len("snapshot: "):])["review_due"] == 3
    assert not {t.name for t in request.tools} & {"build_learning_snapshot", "get_due_review_summary"}  # no read tools
    assert "Never state a\n  number the snapshot does not hold" in next(m.content for m in request.messages if "opening turn" in m.content)



# --- dogfood gate 3.2: the server, not the model, authorises a note ---------------------------------------


@pytest.mark.parametrize("message", ["Mình muốn thi HSK4 vào tháng 12.", "I'm preparing for HSK4.", "我在准备HSK4。",
                                     "Mình không nhớ là từ này nghĩa gì", "hay là thôi", "Sau này mình dùng từ này thế nào?",
                                     "What do I say next time?", "mình nhớ là bài trước có từ này",
                                     "Do you remember my level?", "Ghi nhớ từ này khó quá", "考试以后再说"])
def test_a_fact_told_or_an_unclear_message_writes_no_note(message):
    out = outputs({}, learner_words=message)
    answer = out.handle(REMEMBER_NOTE, {"kind": "goal", "text": "Thi HSK4"}, known_evidence=frozenset())
    assert answer.startswith("refused: the learner did not ask you to remember") and out.memory_updates == []


@pytest.mark.parametrize("message", ["Nhớ giúp mình là mình muốn thi HSK4.", "Please remember that I'm aiming for HSK4.",
                                     "记住我在准备HSK4。", "Từ giờ giải thích ngắn thôi", "From now on, explain in English"])
def test_an_explicit_request_writes_the_note(message):
    out = outputs({}, learner_words=message)
    assert out.handle(REMEMBER_NOTE, {"kind": "goal", "text": "Thi HSK4"}, known_evidence=frozenset()).startswith("accepted")


def test_a_note_the_learner_did_not_name_is_neither_replaced_nor_forgotten():
    notes = {"n-goal": 0.6, "n-style": 0.6}
    out = outputs(notes, learner_words="À không, giải thích kỹ hơn", correcting=("n-style",), asked=("n-style",),
                  notes_intent="correct")  # fmt: skip
    replaced = out.handle(REMEMBER_NOTE, {"kind": "goal", "text": "x", "replaces": "n-goal"}, known_evidence=frozenset())
    assert replaced.startswith("refused: the learner's message does not correct that note")
    forgotten = out.handle(FORGET_NOTE, {"id": "n-goal"}, known_evidence=frozenset())
    assert forgotten.startswith("refused: the learner did not ask to forget") and out.memory_updates == []


@pytest.mark.parametrize("message", ["nho giup minh la minh thich vi du ngan", "Tu gio giai thich ngan thoi nhe",
                                     "ghi nho la minh muon thi HSK4 thang 12", "lan sau hay dung tieng Anh"])
def test_a_request_typed_without_vietnamese_diacritics_is_recognised_as_unconfirmed(message):
    assert asks_to_remember_unaccented(message) and not asks_to_remember(message)


@pytest.mark.parametrize("message", ["Nhớ giúp mình là mình thích ví dụ ngắn", "minh khong nho la tu nay nghia gi",
                                     "minh muon thi HSK4", "From now on, explain in English", "记住我在准备HSK4。"])
def test_what_is_not_an_unaccented_keep_request_is_not_one(message):
    assert not asks_to_remember_unaccented(message)


def test_an_unaccented_request_keeps_nothing_and_proposes_the_note_for_confirmation():
    out = outputs({}, learner_words="nho giup minh la minh thich vi du ngan", unaccented_keep=True)
    answer = out.handle(REMEMBER_NOTE, {"kind": "preference", "text": "Mình thích ví dụ thật ngắn."}, known_evidence=frozenset())
    assert answer.startswith("refused: typed without diacritics") and out.memory_updates == []
    assert out.note_offer == ("preference", "Mình thích ví dụ thật ngắn.")


def _suggestions(events):
    return [(e.label, e.intent) for e in events if e.name == "suggestion"]


def test_orena_asks_back_with_a_button_when_a_keep_request_has_no_diacritics():
    """Human direction 2026-10-04: never refused in silence; asked back, and kept only when the learner taps."""

    rounds = [
        (TextDelta("Mình đã ghi nhớ rồi nhé."),
         ToolCallRequest("c1", REMEMBER_NOTE, {"kind": "preference", "text": "Mình thích ví dụ thật ngắn."}),
         TurnFinished(0, 3, "tool_calls")),
    ]  # fmt: skip
    rt, _ = _runtime(rounds)
    events = list(rt.run(_request("nho giup minh la minh thich vi du ngan"), ZH))
    assert not [e for e in events if e.name == "memory_update"]
    assert next(e for e in events if e.name == "segment_end").text == "Bạn muốn mình ghi nhớ: “Mình thích ví dụ thật ngắn.”?"
    assert _suggestions(events) == [("Ghi nhớ: Mình thích ví dụ thật ngắn.", "prompt.keep_note")]


def test_the_learners_own_words_are_proposed_when_the_model_proposes_nothing():
    rt, _ = _runtime([reply("Được thôi.")])
    events = list(rt.run(_request("nho giup minh la minh thich vi du ngan"), ZH))
    assert not [e for e in events if e.name == "memory_update"]
    assert next(e for e in events if e.name == "segment_end").text == "Bạn muốn mình ghi nhớ: “minh thich vi du ngan”?"
    assert _suggestions(events) == [("Ghi nhớ: minh thich vi du ngan", "prompt.keep_note")]


def test_tapping_the_button_keeps_exactly_the_confirmed_note():
    rounds = [
        (TextDelta("Mình đã ghi nhớ: bạn thích ví dụ thật ngắn."),
         ToolCallRequest("c1", REMEMBER_NOTE, {"kind": "preference", "text": "Mình thích ví dụ thật ngắn."}),
         TurnFinished(0, 3, "tool_calls")),
    ]  # fmt: skip
    rt, _ = _runtime(rounds)
    events = list(rt.run(_request("Ghi nhớ: Mình thích ví dụ thật ngắn."), ZH))
    [update] = [e for e in events if e.name == "memory_update"]
    assert update.op == "upsert" and update.note["text"] == "Mình thích ví dụ thật ngắn."
    assert update.note["kind"] == "preference" and not _suggestions(events)


def test_after_the_tap_a_different_note_is_refused_and_the_model_is_asked_once_more():
    rounds = [
        (ToolCallRequest("c1", REMEMBER_NOTE, {"kind": "preference", "text": "Thích ví dụ dài"}),
         TurnFinished(0, 3, "tool_calls")),
        (TextDelta("Mình đã ghi nhớ."),
         ToolCallRequest("c2", REMEMBER_NOTE, {"kind": "preference", "text": "Mình thích ví dụ thật ngắn."}),
         TurnFinished(0, 3, "tool_calls")),
    ]  # fmt: skip
    rt, provider = _runtime(rounds)
    events = list(rt.run(_request("Ghi nhớ: Mình thích ví dụ thật ngắn."), ZH))
    [update] = [e for e in events if e.name == "memory_update"]
    assert update.note["text"] == "Mình thích ví dụ thật ngắn."
    refusal = next(m.content for m in provider.requests[1].messages if m.role == "tool")
    assert refusal.startswith("refused: keep exactly the words the learner confirmed")


def test_the_confirmation_label_follows_the_interface_language():
    out = outputs({}, learner_words="Remember: I like short examples.")
    assert out.handle(REMEMBER_NOTE, {"kind": "preference", "text": "I like short examples."},
                      known_evidence=frozenset()).startswith("accepted")  # fmt: skip
    assert confirmed_note("记住：我喜欢短例子。") == "我喜欢短例子。"
    assert confirmed_note("Ghi nhớ: Mình thích ví dụ thật ngắn.") == "Mình thích ví dụ thật ngắn."
    assert confirmed_note("Ghi nhớ từ này khó quá") is None


def test_a_model_that_offers_to_remember_writes_nothing_until_the_learner_asks():
    """The model offers and keeps in one turn: the learner only told a fact, so nothing is kept or claimed."""

    rounds = [
        (TextDelta("Mình đã ghi nhớ mục tiêu HSK4 của bạn."),
         ToolCallRequest("c1", REMEMBER_NOTE, {"kind": "goal", "text": "Thi HSK4 vào tháng 12"}),
         TurnFinished(0, 3, "tool_calls")),
    ]  # fmt: skip
    rt, _ = _runtime(rounds)
    events = list(rt.run(_request("Mình muốn thi HSK4 vào tháng 12."), ZH))
    assert not [e for e in events if e.name == "memory_update"]
    assert "ghi nhớ" not in next(e for e in events if e.name == "segment_end").text
