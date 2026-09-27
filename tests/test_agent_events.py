"""Server events (contract §4-§7) and the order the stream allows."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from writing_coach.agent.contract import ACTIONS, CONTRACT_VERSION, SURFACES
from writing_coach.agent.events import (
    ActionNotSupported,
    AudioChunkEvent,
    ContractViolation,
    Display,
    DoneEvent,
    ErrorEvent,
    EvidenceEvent,
    MemoryUpdateEvent,
    MeteredEvent,
    SegmentDelta,
    SegmentEnd,
    SessionEvent,
    SuggestionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStream,
    Usage,
    VoiceStateEvent,
    error_event,
    make_action,
    sse_frame,
)
from writing_coach.agent.schemas import ClientInfo

ALL_ACTIONS = sorted(ACTIONS)
ALL_INTENTS = sorted(SURFACES)


def client(actions=ALL_ACTIONS, intents=ALL_INTENTS):
    return ClientInfo(ui_version="t", supported_actions=list(actions), supported_intents=list(intents))


def stream(version=CONTRACT_VERSION, **kwargs):
    s = TurnStream(version=version, client=kwargs.pop("client", client()), **kwargs)
    s.emit(SessionEvent(session_id="s1", contract_version=version))
    return s


def done():
    return DoneEvent(usage=Usage(input_tokens=10, output_tokens=5), trace_id="t1")


def names(s):
    return [event.name for event in s.events]


# --- framing -----------------------------------------------------------------


def test_sse_framing_and_wire_names():
    frame = sse_frame(ToolCallEvent(name="get_current_writing_evaluation", label="Đang xem bài viết"))
    assert frame.startswith("event: tool_call\ndata: ") and frame.endswith("\n\n")
    assert json.loads(frame.split("data: ", 1)[1]) == {
        "name": "get_current_writing_evaluation",
        "label": "Đang xem bài viết",
    }
    error = sse_frame(error_event("provider_unavailable", interface="vi", support="vi"))
    assert json.loads(error.split("data: ", 1)[1]) == {
        "class": "provider_unavailable",
        "message": "Orena đang bận, thử lại sau nhé.",
        "fallback": "retry",
    }


def test_text_is_sent_as_written():
    frame = sse_frame(SegmentEnd(index=0, lang="zh-CN", text="是", voice_style="reference"))
    assert '"text":"是"' in frame


# --- the canonical streams, built through the stream (contract §12) ----------


def test_s1_app_help():
    s = stream()
    s.emit(SegmentDelta(index=0, lang="vi", text_delta="Màn này "))
    s.emit(SegmentDelta(index=0, lang="vi", text_delta="giữ các từ của bạn."))
    s.emit(SegmentEnd(index=0, lang="vi", text="Màn này giữ các từ của bạn.", voice_style="neutral_explain"))
    s.emit(SuggestionEvent(label="Ôn từ đến hạn", intent="review_due"))
    s.emit(done())
    assert names(s) == ["session", "segment_delta", "segment_delta", "segment_end", "suggestion", "done"]


def test_s5_save_word():
    s = stream()
    s.emit(SegmentEnd(index=0, lang="vi", text="Mình lưu 我 cho bạn nhé.", voice_style="brief_ack"))
    action = s.emit(make_action("a1", "save_word", "Lưu từ", {"text": "我", "lang": "zh-CN"}))
    s.emit(done())
    assert action.risk == "LOW"
    assert names(s) == ["session", "segment_end", "action", "done"]


def test_s8_authorization_has_no_tool_and_no_action():
    s = stream()
    s.emit(SegmentEnd(index=0, lang="vi", text="Mình chỉ xem được tiến độ của chính bạn.", voice_style="neutral_explain"))
    s.emit(done())
    assert names(s) == ["session", "segment_end", "done"]


def test_s9_writing_evidence_then_claim_then_navigate():
    s = stream()
    s.emit(ToolCallEvent(name="get_current_writing_evaluation", label="Đang xem bài viết"))
    s.emit(ToolResultEvent(name="get_current_writing_evaluation", summary="2 lỗi", evidence_ids=["e1", "e2"]))
    for evidence_id in ("e1", "e2"):
        s.emit(EvidenceEvent(id=evidence_id, source="writing.evaluation", ref={"essay_id": "9"}, excerpt={"k": 1}))
    s.emit(
        SegmentEnd(index=0, lang="vi", text="Bạn hay sai trật tự từ.", voice_style="neutral_explain"),
        cites=["e1", "e2"],
    )
    s.emit(make_action("a1", "navigate", "Sửa bài", {"intent": "writing.revision", "essay_id": "9"}))
    s.emit(done())
    assert names(s) == [
        "session", "tool_call", "tool_result", "evidence", "evidence", "segment_end", "action", "done",
    ]


def test_s2_pronunciation_claim_rests_on_flagged_evidence():
    s = stream()
    s.emit(ToolCallEvent(name="get_pronunciation_attempt", label="Đang xem lần nói gần nhất"))
    s.emit(ToolResultEvent(name="get_pronunciation_attempt", summary="1 âm", evidence_ids=["e1"]))
    s.emit(
        EvidenceEvent(
            id="e1",
            source="speech.pronunciation",
            ref={"attempt_id": "att-1", "path": "words[2].phonemes[0]"},
            excerpt={"pinyin": "shi", "tone": 4, "score": 6, "flagged": True},
        )
    )
    s.emit(SegmentEnd(index=0, lang="vi", text="Azure đánh dấu 是 …", voice_style="gentle_correction"), cites=["e1"])
    s.emit(SegmentEnd(index=1, lang="zh-CN", text="是", voice_style="reference"))
    s.emit(make_action("a1", "play_model", "Nghe mẫu", {"content_id": "c1", "item_id": "i1"}))
    s.emit(make_action("a2", "say_again", "Nói lại", {"content_id": "c1", "item_id": "i1"}))
    s.emit(done())
    assert names(s)[-4:] == ["segment_end", "action", "action", "done"]


def test_s12_metered_then_short_answer():
    s = stream()
    s.emit(MeteredEvent(turn_ordinal=301, budget_state="soft_limited"))
    s.emit(SegmentEnd(index=0, lang="vi", text="Ngắn thôi nhé.", voice_style="brief_ack"))
    s.emit(done())
    assert names(s) == ["session", "metered", "segment_end", "done"]


def test_se_provider_failure_ends_with_error():
    s = stream()
    s.emit(error_event("provider_unavailable", interface="vi", support="vi"))
    assert s.finished and names(s) == ["session", "error"]


# --- ordering ------------------------------------------------------------------


def test_session_comes_first_and_once():
    s = TurnStream(version=CONTRACT_VERSION, client=client())
    with pytest.raises(ContractViolation):
        s.emit(done())
    s.emit(SessionEvent(session_id="s1", contract_version=CONTRACT_VERSION))
    with pytest.raises(ContractViolation):
        s.emit(SessionEvent(session_id="s2", contract_version=1))


def test_session_carries_the_negotiated_version():
    s = TurnStream(version=CONTRACT_VERSION, client=client())
    with pytest.raises(ContractViolation):
        s.emit(SessionEvent(session_id="s1", contract_version=1))


def test_nothing_after_done_or_error():
    for terminal in (done(), error_event("internal_error", interface="en", support="en")):
        s = stream()
        s.emit(terminal)
        with pytest.raises(ContractViolation):
            s.emit(SegmentEnd(index=0, lang="en", text="late", voice_style="brief_ack"))


def test_delta_after_end_and_text_mismatch_are_refused():
    s = stream()
    s.emit(SegmentDelta(index=0, lang="en", text_delta="Hello"))
    with pytest.raises(ContractViolation, match="differs"):
        s.emit(SegmentEnd(index=0, lang="en", text="Hello there", voice_style="neutral_explain"))
    s.emit(SegmentEnd(index=0, lang="en", text="Hello", voice_style="neutral_explain"))
    with pytest.raises(ContractViolation):
        s.emit(SegmentDelta(index=0, lang="en", text_delta="again"))


def test_segments_open_in_order_and_keep_their_language():
    s = stream()
    with pytest.raises(ContractViolation):
        s.emit(SegmentEnd(index=1, lang="en", text="skip", voice_style="brief_ack"))
    s.emit(SegmentDelta(index=0, lang="en", text_delta="a"))
    with pytest.raises(ContractViolation):
        s.emit(SegmentDelta(index=0, lang="zh-CN", text_delta="是"))


def test_done_needs_every_segment_ended_and_every_named_evidence_sent():
    s = stream()
    s.emit(SegmentDelta(index=0, lang="en", text_delta="open"))
    with pytest.raises(ContractViolation, match="never ended"):
        s.emit(done())
    s = stream()
    s.emit(ToolResultEvent(name="get_due_vocabulary", summary="3 due", evidence_ids=["e9"]))
    with pytest.raises(ContractViolation, match="never sent"):
        s.emit(done())


def test_a_claim_cannot_cite_evidence_not_yet_sent():
    s = stream()
    with pytest.raises(ContractViolation, match="not yet sent"):
        s.emit(SegmentEnd(index=0, lang="vi", text="Bạn sai.", voice_style="gentle_correction"), cites=["e1"])
    with pytest.raises(ContractViolation):
        s.emit(SuggestionEvent(label="x", intent="y"), cites=["e1"])


def test_evidence_and_action_ids_are_unique():
    s = stream()
    s.emit(EvidenceEvent(id="e1", source="learner_summary", ref={}, excerpt={}))
    with pytest.raises(ContractViolation):
        s.emit(EvidenceEvent(id="e1", source="learner_summary", ref={}, excerpt={}))
    s.emit(make_action("a1", "start_review", "Ôn ngay", {"scope": "due"}))
    with pytest.raises(ContractViolation):
        s.emit(make_action("a1", "start_review", "Ôn ngay", {"scope": "due"}))


def test_voice_events_only_in_a_voice_stream():
    s = stream()
    with pytest.raises(ContractViolation):
        s.emit(VoiceStateEvent(state="speaking"))
    v = stream(mode="voice")
    v.emit(VoiceStateEvent(state="speaking"))
    v.emit(AudioChunkEvent(index=0, format="pcm16_24k", data_base64="AAAA"))


# --- actions (contract §3.1, §7) ---------------------------------------------


def test_the_client_decides_which_actions_exist():
    s = stream(client=client(actions=["navigate"], intents=["vocabulary.review_due"]))
    assert not s.allows_action("save_word")
    assert s.allows_action("navigate", "vocabulary.review_due")
    assert not s.allows_action("navigate", "writing.revision")
    with pytest.raises(ActionNotSupported):
        s.emit(make_action("a1", "save_word", "Lưu từ", {"text": "我", "lang": "zh-CN"}))
    with pytest.raises(ActionNotSupported):
        s.emit(make_action("a2", "navigate", "Sửa bài", {"intent": "writing.revision", "essay_id": "9"}))
    s.emit(make_action("a3", "navigate", "Ôn từ", {"intent": "vocabulary.review_due"}))


def test_blocked_and_unknown_actions_cannot_be_built():
    for blocked in ("delete_collection", "reset_progress", "clear_history", "bulk_remove", "open_admin"):
        with pytest.raises(ContractViolation):
            make_action("a1", blocked, "x", {})


def test_risk_comes_from_the_table_never_from_the_caller():
    assert make_action("a1", "unsave_word", "Bỏ lưu", {"text": "我", "lang": "zh-CN"}).risk == "CONFIRM"
    with pytest.raises(ValidationError):
        from writing_coach.agent.events import ActionEvent

        ActionEvent(id="a1", type="unsave_word", label="Bỏ lưu", payload={"text": "我", "lang": "zh-CN"}, risk="LOW")


@pytest.mark.parametrize(
    "action_type, payload",
    [
        ("navigate", {"intent": "writing.revision"}),  # missing essay_id
        ("navigate", {"intent": "writing.workspace", "essay_id": "9"}),  # extra param
        ("navigate", {"intent": "admin.users"}),
        ("save_word", {"word_id": "w1", "text": "我"}),
        ("save_word", {"text": "我", "lang": "zh"}),
        ("compare_with_model", {"attempt_id": "a"}),
        ("start_review", {"scope": "week"}),
        ("start_review", {"scope": "word"}),
        ("start_targeted_drill", {"focus": "tone", "item_ids": []}),
        ("start_review", {"scope": "due", "text": "我", "lang": "zh-CN"}),
        ("add_word_to_collection", {"text": "我", "lang": "zh-CN", "target": {"system": "shelf", "id": "d1"}}),
        ("add_word_to_collection", {"text": "我", "lang": "zh-CN", "target": "d1"}),
        ("play_user", {"attempt_id": "a1"}),
        ("navigate", {"intent": "vocabulary.word", "word_id": "w1"}),
        ("start_targeted_drill", {"focus": "rhythm", "item_ids": ["i1"]}),
        ("play_model", {"content_id": 7}),
    ],
)
def test_payloads_follow_the_table(action_type, payload):
    with pytest.raises(ValidationError):
        make_action("a1", action_type, "x", payload)


@pytest.mark.parametrize(
    "action_type, payload",
    [
        ("save_word", {"text": "我", "lang": "zh-CN"}),
        ("say_again", {"content_id": "c1"}),
        ("add_word_to_collection", {"text": "我", "lang": "zh-CN"}),
        ("add_word_to_collection", {"text": "我", "lang": "zh-CN", "target": {"system": "library", "id": "c1"}}),
        ("start_review", {"scope": "word", "text": "我", "lang": "zh-CN"}),
        ("start_review", {"scope": "due"}),
        ("start_targeted_drill", {"focus": "tone", "item_ids": ["i1", "i2"]}),
        ("play_user", {"take_ref": "t1", "item_id": "i1"}),
        ("navigate", {"intent": "speaking.word_detail", "take_ref": "t1", "item_id": "i"}),
        ("navigate", {"intent": "vocabulary.word", "text": "我", "lang": "zh-CN"}),
        ("navigate", {"intent": "orena.home"}),
    ],
)
def test_valid_payloads(action_type, payload):
    assert make_action("a1", action_type, "Nút", payload).type == action_type


def test_action_label_is_at_most_24_characters():
    make_action("a1", "start_review", "x" * 24, {"scope": "due"})
    with pytest.raises(ValidationError):
        make_action("a1", "start_review", "x" * 25, {"scope": "due"})


# --- other payloads ------------------------------------------------------------


def test_closed_values_on_events():
    with pytest.raises(ValidationError):
        SegmentEnd(index=0, lang="vi", text="x", voice_style="shouting")
    with pytest.raises(ValidationError):
        SegmentEnd(index=0, lang="zh", text="x", voice_style="neutral_explain")
    with pytest.raises(ValidationError):
        EvidenceEvent(id="e1", source="speech.guess", ref={}, excerpt={})
    with pytest.raises(ValidationError):
        MeteredEvent(turn_ordinal=1, budget_state="blocked")
    with pytest.raises(ValidationError):
        ErrorEvent(error_class="provider_unavailable", message="m", fallback="switch_provider")
    with pytest.raises(ValidationError):
        ErrorEvent(error_class="made_up", message="m", fallback="retry")


def test_an_error_falls_back_the_way_its_kind_does():
    with pytest.raises(ValidationError, match="text_only"):
        ErrorEvent(error_class="voice_unavailable", message="m", fallback="retry")
    with pytest.raises(ValidationError):
        ErrorEvent(error_class="provider_unavailable", message="m", fallback="none")
    assert ErrorEvent(error_class="voice_unavailable", message="m", fallback="text_only").fallback == "text_only"
    with pytest.raises(ValidationError):
        AudioChunkEvent(index=0, format="mp3", data_base64="AA")


def test_memory_update_shapes():
    note = {
        "id": "n1",
        "kind": "goal",
        "text": "HSK3 vào tháng 12",
        "weight": 0.6,
        "last_reinforced": "2026-09-27T08:00:00Z",
        "expires_at": None,
    }
    MemoryUpdateEvent(op="upsert", note=note)
    MemoryUpdateEvent(op="remove", note={"id": "n1"})
    with pytest.raises(ValidationError):
        MemoryUpdateEvent(op="remove", note=note)
    with pytest.raises(ValidationError):
        MemoryUpdateEvent(op="upsert", note={**note, "kind": "mood"})
    with pytest.raises(ValidationError):
        MemoryUpdateEvent(op="replace_all", note={"id": "n1"})


# --- version 2 and the clients that declared version 1 (contract §0, D-092) ---------------


def test_a_version_one_client_gets_none_of_the_changed_actions_or_intents():
    s = stream(version=1)
    for changed in ("save_word", "unsave_word", "add_word_to_collection", "start_review", "say_again", "play_user"):
        assert not s.allows_action(changed)
    assert s.allows_action("play_model") and s.allows_action("navigate", "vocabulary.review_due")
    assert not s.allows_action("navigate", "orena.home")
    assert not s.allows_action("navigate", "vocabulary.word")
    with pytest.raises(ActionNotSupported):
        s.emit(make_action("a1", "save_word", "Lưu từ", {"text": "我", "lang": "zh-CN"}))


def test_display_reaches_only_a_version_two_client():
    display = Display(kind="writing", reason="Hai lỗi động từ lặp lại.")
    for version, expected in ((2, {"kind": "writing", "reason": "Hai lỗi động từ lặp lại."}), (1, None)):
        s = stream(version=version)
        action = s.emit(make_action("a1", "navigate", "Sửa bài", {"intent": "writing.revision", "essay_id": "9"}, display=display))
        wire = json.loads(sse_frame(action).split("data: ", 1)[1])
        assert wire.get("display") == expected
        assert ("display" in wire) is (expected is not None)


def test_display_is_bounded():
    with pytest.raises(ValidationError):
        Display(kind="games")
    with pytest.raises(ValidationError):
        Display(reason="x" * 91)
