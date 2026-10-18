"""M2-prep (ORENA_MEMORY.md rev 4.1, D-222): the memory key, the closed-code matchers and grounding, and the
summariser's output validation. Pure code: no schema, no storage, nothing wired into a turn yet."""

from __future__ import annotations

import pytest

from writing_coach.agent.memory_keys import MemoryKeys, normalise
from writing_coach.agent.memory_slots import (
    SLOTS,
    explanation_language_request,
    grounded,
    statements,
)
from writing_coach.agent.memory_summary import (
    EVENTS,
    SCENARIOS,
    SUMMARY_KEYS,
    SummaryContext,
    stored_size,
    validate_summary,
    without_deleted_item,
)

OLD = "a" * 40
NEW = "b" * 40


# --- the memory key ---------------------------------------------------------------------------------------------------


def test_no_key_means_memory_is_off():
    assert MemoryKeys.from_env({}) is None and MemoryKeys.parse("  ") is None


@pytest.mark.parametrize("text", ["secret", "v0:" + OLD, "v1:short", f"v1:{OLD},v1:{NEW}", f"1:{OLD}", f"v1:{OLD} x"])
def test_a_malformed_key_refuses_to_start(text):
    with pytest.raises(ValueError):
        MemoryKeys.parse(text)


def test_the_key_is_stable_keyed_and_never_printed():
    keys = MemoryKeys.parse(f"v1:{OLD}")
    assert keys.stamp("occupation", "engineering") == (1, keys.value_key("occupation", "engineering"))
    assert keys.value_key("interest", " Sport ") == keys.value_key("INTEREST", "sport")  # normalised
    assert keys.value_key("interest", "sport") != keys.value_key("example_domain", "sport")  # the slot is keyed
    assert keys.value_key("a", "b\x1fc") != keys.value_key("a\x1fb", "c")  # no two pairs share a message
    assert keys.value_key("interest", "sport") != MemoryKeys.parse(f"v1:{NEW}").value_key("interest", "sport")
    assert OLD not in repr(keys) and OLD not in str(keys)


def test_after_a_rotation_old_rows_still_match_and_new_rows_use_the_new_version():
    before = MemoryKeys.parse(f"v1:{OLD}")
    version, stored = before.stamp("interest", "sport")  # a row (or a suppression key) written before the rotation
    after = MemoryKeys.parse(f"v1:{OLD},v2:{NEW}")
    assert after.current == 2 and after.stamp("interest", "sport")[0] == 2
    assert after.matches("interest", "sport", version, stored)
    assert after.candidates("interest", "sport")[1] == stored
    assert not after.matches("interest", "music", version, stored)


def test_dropping_a_version_still_in_use_refuses_to_start():
    keys = MemoryKeys.parse(f"v2:{NEW}")
    keys.check_in_use([2])
    with pytest.raises(ValueError):
        keys.check_in_use([1, 2])
    assert not keys.matches("interest", "sport", 1, "0" * 64)  # an unconfigured version never matches


def test_normalise():
    assert normalise("  Kỹ  Sư\t") == normalise("kỹ sư") == "kỹ sư"


# --- statements and grounding -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("message", "expected"), [
    ("Tôi là kỹ sư automation, muốn ví dụ về PLC", {("occupation", "engineering")}),
    ("I am a software engineer", {("occupation", "engineering")}),
    ("我是一名工程师", {("occupation", "engineering")}),
    ("Tôi học tiếng Trung để phỏng vấn", {("learning_purpose", "job_interview")}),
    ("I'm learning Chinese for my job", {("learning_purpose", "work")}),
    ("我学中文是为了考试", {("learning_purpose", "exam")}),
    ("My goal is to pass HSK4", {("learning_purpose", "exam")}),
    ("Mình thích bóng đá", {("interest", "sport")}),
    ("I like music and film", {("interest", "music"), ("interest", "film")}),
    ("我喜欢足球", {("interest", "sport")}),
    ("cho mình ví dụ về du lịch", {("example_domain", "travel")}),
    ("examples about travel please", {("example_domain", "travel")}),
    ("用足球的例子解释", {("example_domain", "sport")}),
])
def test_a_learner_statement_yields_closed_codes(message, expected):
    assert statements(message) == expected


@pytest.mark.parametrize("message", [
    "tôi không thích bóng đá", "I don't like football", "我不喜欢足球",  # negation is not a statement
    "I'm learning engineering vocabulary", "Tôi đang học từ kỹ sư",  # learning a word says nothing about the learner
    "Tôi học để thiết kế",  # "thi" is not in "thiết"
    "kỹ sư nghĩa là gì?", "What does engineer mean?", "工程师是什么意思？",  # no self-reference
    "Tôi sắp phẫu thuật tuần sau", "I have surgery next week", "我下周要做手术",  # health: no slot holds it
    "Tôi theo đạo Phật", "I'm a Buddhist", "Tôi đang nợ ngân hàng",  # religion, finances
])
def test_what_is_not_a_closed_statement_yields_nothing(message):
    assert statements(message) == set()


@pytest.mark.parametrize("message", [
    "I'm not an engineer", "I am not a student", "I am no longer a teacher", "I'm not really a developer",
    "My goal is not work", "I'm learning Chinese not for work", "I'm not learning Chinese for my job",
    "Mục tiêu của tôi không phải đi làm", "Tôi không phải là kỹ sư", "Tôi là kỹ sư đâu",
    "Mình học tiếng Trung không phải để phỏng vấn", "Mình chưa là sinh viên",
    "我是不是工程师", "我的目标是不考试", "我学中文不是为了工作", "我没有喜欢足球", "我是非工程师",
])
def test_a_negation_never_becomes_the_opposite_fact(message):
    assert statements(message) == set()  # review of PR #266, P1-1


def test_a_single_valued_slot_yields_one_code():
    assert statements("I'm a software engineer") == {("occupation", "engineering")}


def test_every_slot_lists_only_learning_codes():
    excluded = ("health", "religion", "politic", "finance", "money", "salary", "location", "address", "sex")
    for codes in SLOTS.values():
        assert not [code for code in codes if any(word in code for word in excluded)]


def test_grounding_reads_only_the_learner_messages_given():
    learner = ["Mình là kỹ sư", "giải thích lại đi"]
    assert grounded("occupation", "engineering", learner)
    assert not grounded("occupation", "it", learner)
    assert not grounded("interest", "sport", learner)  # a pasted text or Orena's reply is never passed in
    assert not grounded("upcoming_event", "anything", learner)  # not a slot (rev 4.1)
    assert not grounded("occupation", "astronaut", ["I'm an astronaut"])  # not a code


@pytest.mark.parametrize(("message", "language"), [
    ("giải thích bằng tiếng Việt nhé", "vi"), ("Explain it again in English", "en"), ("用中文解释一下", "zh"),
    ("giải thích lại sang tiếng Anh", "en"), ("explain in Mandarin", "zh"),
])
def test_an_explicit_explanation_language_request(message, language):
    assert explanation_language_request(message) == language


@pytest.mark.parametrize("message", ["我想练习写汉字", "Tôi viết bằng tiếng Trung", "I write in English", "",
                                     "giải thích từ này"])
def test_writing_in_a_language_is_never_a_request(message):
    assert explanation_language_request(message) is None


# --- the summariser's output ------------------------------------------------------------------------------------------


def ctx(**extra):
    base = dict(
        learner_messages=("Mình là kỹ sư, đang luyện phỏng vấn", "Tôi học tiếng Trung để phỏng vấn"),
        known_words=frozenset({"面试", "加班", "了"}),
        is_grammar_point=lambda item: item in {"了/过", "aspect"},
        essay_ids=frozenset({"essay-1"}),
        reading_titles={"r-1": "Một ngày ở Bắc Kinh"},
        listening_titles={"l-1": "Podcast 1"},
    )
    base.update(extra)
    return SummaryContext(**base)


def test_a_valid_summary_stores_exactly_three_keys_and_returns_grounded_context():
    out = validate_summary({
        "practised": [{"event": "grammar_point", "item": "了/过"}, {"event": "vocabulary_set", "item": "面试, 加班"},
                      {"event": "reading_text", "item": "r-1"}, {"event": "interview_answer", "item": "why_this_company"}],
        "focus": {"event": "pronunciation_word", "item": "面试"},
        "open_task": {"event": "interview_answer", "item": "self_introduction"},
        "useful_context": [{"slot": "occupation", "code": "engineering"},
                           {"slot": "learning_purpose", "code": "job_interview"}],
    }, ctx())
    assert tuple(out.summary) == SUMMARY_KEYS
    assert out.summary["practised"][1]["item"] == "面试、加班"
    assert out.summary["practised"][2]["item"] == "Một ngày ở Bắc Kinh"  # the record's title, not the model's
    assert out.useful_context == (("occupation", "engineering"), ("learning_purpose", "job_interview"))
    assert out.dropped == 0


@pytest.mark.parametrize(("event", "item"), [
    ("grammar_point", "Bạn ấy sắp phẫu thuật"),  # free personal text: no validator accepts it
    ("vocabulary_set", "đang chuẩn bị phỏng vấn ở công ty X"),
    ("vocabulary_set", "手术"),  # a word not in the learner's records or this session
    ("writing_revision", "essay-of-someone-else"),
    ("reading_text", "Some title the model wrote"),
    ("interview_answer", "Why did you leave your last job because of your illness?"),
    ("roleplay_scenario", "negotiating_salary"),
])
def test_an_item_no_validator_accepts_is_dropped_and_the_event_kept(event, item):
    out = validate_summary({"practised": [{"event": event, "item": item}]}, ctx())
    assert out.summary["practised"] == [{"event": event, "item": None}] and out.dropped == 1


def test_a_resolved_title_over_the_bound_is_dropped_not_cut():
    long_title = "Một câu chuyện rất dài " * 5  # > 60 characters, from the record
    out = validate_summary({"practised": [{"event": "reading_text", "item": "r-2"},
                                          {"event": "listening_text", "item": "l-2"},
                                          {"event": "reading_text", "item": "r-1"}]},
                           ctx(reading_titles={"r-1": "Một ngày ở Bắc Kinh", "r-2": long_title},
                               listening_titles={"l-2": long_title}))
    assert out.summary["practised"] == [{"event": "reading_text", "item": None},
                                        {"event": "listening_text", "item": None},
                                        {"event": "reading_text", "item": "Một ngày ở Bắc Kinh"}]  # unchanged
    assert out.dropped == 2


def test_a_summary_over_1200_utf8_bytes_is_rejected_whole():
    words = ["词" * 18 + chr(0x4E00 + i) for i in range(18)]  # 3 bytes a character
    known = frozenset(words)

    def entry(start):
        return {"event": "vocabulary_set", "item": "、".join(words[start:start + 3])}

    raw = {"practised": [entry(0), entry(3), entry(6), entry(9)], "focus": entry(12), "open_task": entry(15)}
    assert all(len(e["item"]) <= 60 for e in [*raw["practised"], raw["focus"], raw["open_task"]])
    assert validate_summary(raw, ctx(known_words=known)) is None
    smaller = {"practised": [entry(0)], "focus": entry(3)}
    out = validate_summary(smaller, ctx(known_words=known))
    assert out is not None and stored_size(out.summary) <= 1200


def test_context_not_said_by_the_learner_or_off_the_lists_is_dropped():
    out = validate_summary({"useful_context": [
        {"slot": "interest", "code": "sport"},  # the learner never said it (pasted text, Orena's reply)
        {"slot": "upcoming_event", "code": "surgery"},  # removed slot
        {"slot": "occupation", "code": "doctor"},  # not a code
        {"slot": "occupation", "code": "engineering"},
    ]}, ctx())
    assert out.useful_context == (("occupation", "engineering"),) and out.dropped == 3
    assert out.summary == {"practised": [], "focus": None, "open_task": None}


@pytest.mark.parametrize("raw", [
    None, [], "text",
    {"practised": [], "temporary_preferences": []},  # a key outside the schema
    {"practised": [{"event": "grammar_point", "item": "了"}] * 5},  # over the bound
    {"practised": [{"event": "diary", "item": None}]},  # not an event
    {"practised": [{"event": "grammar_point", "item": "x" * 61}]},
    {"practised": [{"event": "grammar_point", "item": "了", "note": "x"}]},
    {"focus": "free text"},
    {"useful_context": [{"slot": "occupation", "value": "kỹ sư automation"}]},  # free text instead of a code
    {"useful_context": [{"slot": "interest", "code": "sport"}] * 7},
])
def test_output_that_breaks_the_schema_is_rejected_whole(raw):
    assert validate_summary(raw, ctx()) is None


def test_deleting_an_item_removes_the_summary_entries_that_carry_its_code():
    summary = {"practised": [{"event": "interview_answer", "item": "why_this_company"},
                             {"event": "grammar_point", "item": "了/过"}],
               "focus": None, "open_task": {"event": "interview_answer", "item": "self_introduction"}}
    kept = without_deleted_item(summary, "learning_purpose", "job_interview")
    assert kept == {"practised": [{"event": "grammar_point", "item": "了/过"}], "focus": None, "open_task": None}
    assert without_deleted_item(summary, "interest", "sport") == summary


def test_the_closed_lists_hold_no_excluded_scenario():
    excluded = ("salary", "health", "doctor", "religio", "money", "bank", "address")
    assert not [code for code in SCENARIOS if any(word in code for word in excluded)]
    assert len(set(EVENTS)) == len(EVENTS)
