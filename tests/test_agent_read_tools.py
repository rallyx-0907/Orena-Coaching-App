"""The Slice 1b read tools: shape, bounds, evidence, and the real services behind them."""

from __future__ import annotations

import pytest

from writing_coach import becoming_library
from writing_coach.agent import learner_copy
from writing_coach.agent.read_tools import MAX_ISSUES
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.tool_plan import PLANNED_TOOLS
from writing_coach.agent.tools import LearnerScope, ToolArgumentsInvalid
from writing_coach.agent.turn import learner_context

EN = LearnerScope(user_key="learner-1", language="en")
ZH = LearnerScope(user_key="learner-1", language="zh")


def registry(review=None):
    return build_tool_registry(writing_review=review or (lambda essay_id: None))


def test_the_registered_tools_are_the_planned_ones_read_only_and_labelled():
    tools = registry()
    assert tools.names() == {
        "get_due_review_summary", "get_due_vocabulary", "get_current_writing_evaluation",
        "get_saved_word_state", "get_word_detail", "get_writing_feedback_items", "get_writing_history_summary",
        "get_grammar_point", "search_grammar_points",
        "get_pronunciation_history", "get_pronunciation_attempt", "get_pronunciation_word_detail",
        "get_current_listening_context", "get_listening_attempt",
        "get_current_reading_context", "get_reading_progress",
        "build_learning_snapshot", "get_learning_weaknesses", "get_recommended_next_activities",
    }  # fmt: skip
    for tool in tools.tools():
        planned = PLANNED_TOOLS[tool.name]
        assert tool.backed_by == planned.backed_by, tool.name
        assert set(tool.languages) == {"en", "zh-CN"}
        assert tool.permission.value == "read_only"
        assert f"result.{tool.name}" in learner_copy.CATALOG


def test_due_review_summary(monkeypatch):
    monkeypatch.setattr(
        becoming_library,
        "library_summary",
        lambda: {"summary": {"due": 12, "due_next_day": 3, "total": 40, "learning": 20, "mastered": 5}, "ladder": []},
    )
    for learner in (EN, ZH):
        result = registry().invoke("get_due_review_summary", learner, {})
        assert result.count == 12 and result.data["due_next_day"] == 3
        assert result.evidence[0].source == "vocabulary.review"


def test_due_vocabulary_asks_for_due_words_and_stays_small(monkeypatch):
    calls = []

    def page(**kwargs):
        calls.append(kwargs)
        row = {"word": "是" * 200, "definition": "to be " * 100, "stage_label": "Learning", "lapse_count": 2}
        return {"items": [row] * kwargs["limit"], "total": 57}

    monkeypatch.setattr(becoming_library, "list_library_vocabulary", page)
    result = registry().invoke("get_due_vocabulary", ZH, {"limit": 10})
    assert calls == [{"limit": 10, "status": "due", "order": "due"}]
    assert result.count == 57 and len(result.data["items"]) == 10
    assert result.size_bytes() <= 8 * 1024
    with pytest.raises(ToolArgumentsInvalid):
        registry().invoke("get_due_vocabulary", ZH, {"limit": 500})


def test_writing_evaluation_reads_one_essay_and_its_issues_are_evidence():
    long = "x" * 5000
    review = {
        "summary": long,
        "issues": [
            {"fragment": f"fragment {i} {long}", "correction": long, "why": long, "rule": long, "kind": "grammar"}
            for i in range(20)
        ],
    }
    seen = []
    tools = registry(lambda essay_id: seen.append(essay_id) or review)
    result = tools.invoke("get_current_writing_evaluation", EN, {"essay_id": "42"})
    assert seen == [42]
    assert result.count == 20 and len(result.evidence) == MAX_ISSUES
    assert {e.source for e in result.evidence} == {"writing.evaluation"}
    assert result.evidence[0].ref == {"essay_id": "42", "path": "issues[0]"}
    assert result.size_bytes() <= 8 * 1024


def test_writing_evaluation_without_the_essay_says_so():
    result = registry().invoke("get_current_writing_evaluation", ZH, {"essay_id": "7"})
    assert result.data == {"found": False} and result.count == 0 and result.evidence == ()
    for bad in ("abc", "-1", "1" * 13):
        with pytest.raises(ToolArgumentsInvalid):
            registry().invoke("get_current_writing_evaluation", ZH, {"essay_id": bad})


# --- against the app's real services (sqlite test backend) -------------------------


@pytest.fixture()
def app_module():
    import app as module

    return module


def test_vocabulary_tools_read_the_learners_words_in_each_language(app_module):
    from writing_coach.becoming_library import LibraryVocabularyIn

    words = {"en": "serendipity", "zh": "机会"}
    for language, word in words.items():
        learner = LearnerScope(user_key="legacy", language=language)
        with learner_context(learner):
            app_module.init_db()
            app_module.save_library_vocabulary(LibraryVocabularyIn(word=word, definition="seeded", source_kind="manual"))
    tools = registry()
    for language in words:
        learner = LearnerScope(user_key="legacy", language=language)
        with learner_context(learner):
            summary = tools.invoke("get_due_review_summary", learner, {})
            due = tools.invoke("get_due_vocabulary", learner, {"limit": 10})
        assert summary.data["total"] >= 1, language
        listed = {item["word"] for item in due.data["items"]}
        other = words["zh" if language == "en" else "en"]
        assert other not in listed, f"{language} read the other language's word"


def test_the_writing_tool_reads_through_the_apps_own_review(app_module, monkeypatch, tmp_path):
    import json

    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)
    error = {
        "fragment": "want to telling",
        "suggestion": "want to tell",
        "explanation_vi": "Sau 'want to' dùng động từ nguyên mẫu.",
        "category": "verb_form",
    }
    created = repository.create_essay(
        {
            "created_at": "2026-09-27T08:00:00+00:00",
            "prompt": "Email to a colleague",
            "text": "I want to telling you about my week.",
            "word_count": 8,
            "target_cefr": "B1",
            "grammar": 50.0,
            "vocabulary": 55.0,
            "coherence": 60.0,
            "task_achievement": 58.0,
            "naturalness": 52.0,
            "overall": 55.0,
            "cefr_estimate": "B1",
            "evaluator": "test",
            "summary_vi": "Một lỗi dạng động từ.",
            "strengths_json": "[]",
            "strength_evidence_json": "[]",
            "priorities_json": "[]",
            "errors_json": json.dumps([error], ensure_ascii=False),
        }
    )
    tools = registry(app_module._agent_writing_review)
    found = tools.invoke("get_current_writing_evaluation", EN, {"essay_id": str(created["id"])})
    assert found.data["found"] is True and found.count == 1
    assert found.data["issues"][0]["fragment"] == "want to telling"
    assert found.data["issues"][0]["correction"] == "want to tell"
    assert found.evidence[0].excerpt["fragment"] == "want to telling"
    missing = tools.invoke("get_current_writing_evaluation", EN, {"essay_id": "999999"})
    assert missing.data == {"found": False}


def test_the_writing_reader_turns_only_a_missing_essay_into_none(app_module, monkeypatch):
    from fastapi import HTTPException

    def boom(essay_id):
        raise HTTPException(500, "down")

    monkeypatch.setattr(app_module, "essay_review", lambda essay_id: (_ for _ in ()).throw(HTTPException(404, "x")))
    assert app_module._agent_writing_review(1) is None
    monkeypatch.setattr(app_module, "essay_review", boom)
    with pytest.raises(HTTPException):
        app_module._agent_writing_review(1)


def test_a_chinese_review_fits_the_byte_budget_by_dropping_issues_not_failing():
    review = {
        "summary": "总结" * 200,
        "issues": [
            {"fragment": "我" * 300, "correction": "是" * 300, "why": "因为" * 150, "rule": "规则" * 100, "kind": "grammar"}
            for _ in range(10)
        ],
    }
    result = registry(lambda essay_id: review).invoke("get_current_writing_evaluation", ZH, {"essay_id": "5"})
    assert result.size_bytes() <= 7 * 1024
    assert result.count == 10 and 0 < len(result.evidence) <= MAX_ISSUES
    assert len(result.data["issues"]) == len(result.evidence)


def test_chinese_due_words_fit_the_byte_budget(monkeypatch):
    row = {"word": "机会" * 30, "short_meanings": ["机会" * 60], "stage_label": "学习中" * 10, "lapse_count": 1}
    monkeypatch.setattr(becoming_library, "list_library_vocabulary", lambda **kwargs: {"items": [row] * 10, "total": 10})
    result = registry().invoke("get_due_vocabulary", ZH, {"limit": 10})
    assert result.size_bytes() <= 7 * 1024 and result.count == 10


# --- Slice 1c tools --------------------------------------------------------------------


def test_saved_word_state_answers_word_by_word(monkeypatch):
    seen = []

    def state(candidates):
        seen.append(candidates)
        return {"机会": {"word": "机会", "stage_label": "Learning", "review_stage": 1, "due": True, "lapse_count": 2,
                        "next_review_at": "2026-09-28"}}  # fmt: skip

    monkeypatch.setattr(becoming_library, "saved_vocabulary_state", state)
    result = registry().invoke("get_saved_word_state", ZH, {"words": ["机会", "学习"]})
    assert seen == [("机会", "学习")]
    assert result.data["words"] == [
        {"word": "机会", "saved": True, "status": "Learning", "status_meaning": "reviewed a few times, not yet secure",
         "due": True, "due_label": "Due for review", "lapses": 2, "next_review_at": "2026-09-28"},  # fmt: skip
        {"word": "学习", "saved": False},
    ]
    assert result.count == 1 and [e.ref for e in result.evidence] == [{"text": "机会"}]
    with pytest.raises(ToolArgumentsInvalid):
        registry().invoke("get_saved_word_state", ZH, {"words": [f"w{i}" for i in range(11)]})


def test_word_detail_reads_the_catalogue_and_the_saved_state(monkeypatch):
    entry = {
        "word": "serendipity",
        "part_of_speech": "noun",
        "level": "C1",
        "definition": "luck in finding good things by chance",
        "support_translations": {"vi": "sự tình cờ may mắn", "zh": "意外之喜"},
        "examples": [{"text": "It was pure serendipity."}, "Another.", "A third."],
    }
    monkeypatch.setattr(becoming_library, "catalog_entry_for", lambda term: entry if term == "serendipity" else None)
    monkeypatch.setattr(becoming_library, "saved_vocabulary_state", lambda candidates: {})
    result = registry().invoke("get_word_detail", EN, {"text": "serendipity"})
    assert result.data["in_catalog"] and not result.data["saved"] and result.count == 1
    assert result.data["examples"] == ["It was pure serendipity.", "Another."]
    unknown = registry().invoke("get_word_detail", EN, {"text": "zzz"})
    assert unknown.data["in_catalog"] is False and unknown.count == 0


def test_feedback_items_filter_by_kind():
    review = {
        "strengths": "Clear opening.",
        "issues": [
            {"fragment": "a", "correction": "b", "why": "w", "kind": "grammar"},
            {"fragment": "c", "correction": "d", "why": "w", "kind": "vocabulary"},
            {"fragment": "e", "correction": "f", "why": "w", "kind": "grammar"},
        ],
    }
    tools = registry(lambda essay_id: review)
    grammar = tools.invoke("get_writing_feedback_items", EN, {"essay_id": "3", "kind": "grammar"})
    assert grammar.count == 2 and [i["evidence"] for i in grammar.data["issues"]] == ["issues[0]", "issues[2]"]
    assert [e.ref["path"] for e in grammar.evidence] == ["issues[0]", "issues[2]"]
    everything = tools.invoke("get_writing_feedback_items", ZH, {"essay_id": "3"})
    assert everything.count == 3 and everything.data["strengths"] == "Clear opening."


def test_history_summary_reads_the_apps_error_memory():
    from writing_coach.agent.runtime import build_tool_registry

    memory = {
        "revision_count": 12,
        "items": [
            {"category": "tense", "total": 5, "older": 4, "newer": 1, "first_seen": "2026-09-01", "last_seen": "2026-09-20"},
            {"category": "article", "total": 9, "older": 3, "newer": 6, "first_seen": "2026-09-02", "last_seen": "2026-09-26"},
        ],
    }
    tools = build_tool_registry(writing_review=lambda essay_id: None, writing_history=lambda: memory)
    result = tools.invoke("get_writing_history_summary", EN, {})
    assert [row["category"] for row in result.data["categories"]] == ["Articles", "Tense"]  # named, never the key
    assert [e.ref["category"] for e in result.evidence] == ["article", "tense"]  # the record's key stays in the ref
    assert result.data["revision_count"] == 12 and result.count == 2
    assert result.evidence[0].excerpt == {"total": 9, "older": 3, "newer": 6}


def test_the_app_hands_in_its_error_memory(app_module):
    assert "writing_history=lambda: api_error_memory()" in __import__("pathlib").Path(app_module.__file__).read_text(encoding="utf-8")


def test_word_detail_reads_a_published_entry_too(monkeypatch):
    # The published (DB) catalogue has no `definition`: its meaning is in `detailed_definitions`.
    entry = {
        "id": "91",
        "word": "机会",
        "part_of_speech": "noun",
        "level": "HSK3",
        "short_meanings": [{"language": "vi", "text": "cơ hội"}],
        "detailed_definitions": [{"language": "zh-CN", "text": "恰好的时候；时机"}],
        "support_translations": {"vi": "cơ hội"},
        "readings": [{"text": "jīhuì"}],
        "examples": [],
    }
    monkeypatch.setattr(becoming_library, "catalog_entry_for", lambda term: entry)
    monkeypatch.setattr(becoming_library, "saved_vocabulary_state", lambda candidates: {})
    result = registry().invoke("get_word_detail", ZH, {"text": "机会"})
    assert result.data["definition"] == "恰好的时候；时机"
    assert result.data["translations"] == {"vi": "cơ hội"} and result.data["readings"] == ["jīhuì"]



def test_a_result_with_no_marked_error_says_what_that_means():
    """(b) the evaluator marking nothing is stated for the model, never as praise or as proof."""

    from writing_coach.agent.read_tools import NO_MARKED_ERROR
    from writing_coach.agent.runtime import build_tool_registry

    tools = registry(lambda essay_id: {"summary": "", "strengths": "", "issues": []})
    evaluation = tools.invoke("get_current_writing_evaluation", ZH, {"essay_id": "3"})
    feedback = tools.invoke("get_writing_feedback_items", ZH, {"essay_id": "3"})
    assert evaluation.data["note"] == NO_MARKED_ERROR and feedback.data["note"] == NO_MARKED_ERROR
    history = build_tool_registry(writing_review=lambda i: None, writing_history=lambda: {"revision_count": 1, "items": []})
    summary = history.invoke("get_writing_history_summary", ZH, {})
    assert summary.data == {"revision_count": 1, "categories": [], "note": NO_MARKED_ERROR}
    empty = build_tool_registry(writing_review=lambda i: None, writing_history=lambda: {"revision_count": 0, "items": []})
    assert "note" not in empty.invoke("get_writing_history_summary", ZH, {}).data  # no versions: nothing to qualify
    with_issue = registry(lambda essay_id: {"issues": [{"fragment": "a", "correction": "b", "kind": "grammar"}]})
    assert "note" not in with_issue.invoke("get_current_writing_evaluation", ZH, {"essay_id": "3"}).data
