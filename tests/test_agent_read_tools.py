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
    assert tools.names() == {"get_due_review_summary", "get_due_vocabulary", "get_current_writing_evaluation"}
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
