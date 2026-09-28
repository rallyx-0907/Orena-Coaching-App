"""Speaking, Listening and Reading read tools (Slice 2), on readers shaped as the app's are."""

from __future__ import annotations

import pytest

from writing_coach.agent.runtime import AppReads, build_tool_registry
from writing_coach.agent.skill_tools import flagged
from writing_coach.agent.tools import LearnerScope, ToolArgumentsInvalid

EN = LearnerScope(user_key="learner-1", language="en")
ZH = LearnerScope(user_key="learner-1", language="zh")

ATTEMPT = {
    "id": "a-1", "created_at": "2026-09-28T08:00:00+00:00", "language": "zh", "take_id": "s1:1:1",
    "asset_id": "lesson-9", "segment_id": "s1", "reference_text": "我是学生", "transcript_text": "我是学生",
    "dimensions": {"pronunciation": 72.5, "fluency": 80.0, "content_match": 100.0},
    "evidence": {"recognized_text": "我是学生", "pronunciation": {"words": [
        {"word": "我", "accuracy_score": 95.0, "error_type": "None", "phonemes": []},
        {"word": "是", "accuracy_score": 40.0, "error_type": "Mispronunciation",
         "phonemes": [{"phoneme": "sh", "accuracy_score": 30.0}, {"phoneme": "i", "accuracy_score": 50.0}]},
        {"word": "学生", "accuracy_score": 61.0, "error_type": "None", "phonemes": []},
    ]}},
}  # fmt: skip


def tools(**reads):
    return build_tool_registry(writing_review=lambda essay_id: None, reads=AppReads(**reads))


def attempts_reader(rows, seen=None):
    def read(limit, *, asset_id=None, segment_id=None):
        if seen is not None:
            seen.append((limit, asset_id, segment_id))
        return [r for r in rows if (asset_id is None or r["asset_id"] == asset_id)
                and (segment_id is None or r["segment_id"] == segment_id)][:limit]  # fmt: skip
    return read


def test_flagged_is_the_providers_mark_never_a_threshold():
    assert flagged({"error_type": "Mispronunciation"}) and flagged({"error_type": "Omission"})
    assert not flagged({"error_type": "None"}) and not flagged({"error_type": ""}) and not flagged({})
    assert not flagged({"error_type": "None", "accuracy_score": 12.0})  # a low score it did not flag is not an error


def test_an_attempt_cites_only_what_the_provider_flagged():
    seen = []
    result = tools(speaking_attempts=attempts_reader([ATTEMPT], seen)).invoke(
        "get_pronunciation_attempt", ZH, {"attempt_id": "a-1", "content_id": "lesson-9", "item_id": "s1"}
    )
    assert seen == [(100, "lesson-9", "s1")]  # no read-by-id (N-9): the list the client's ids filter
    assert result.data["found"] and result.data["flagged_count"] == 1 and result.count == 1
    assert [e.ref for e in result.evidence] == [{"attempt_id": "a-1", "path": "words[1]"}]
    assert result.evidence[0].excerpt["error_type"] == "Mispronunciation"
    assert [w["flagged"] for w in result.data["words"]] == [False, True, False]
    assert result.data["content_id"] == "lesson-9" and result.data["item_id"] == "s1"
    missing = tools(speaking_attempts=attempts_reader([ATTEMPT])).invoke("get_pronunciation_attempt", ZH, {"attempt_id": "nope"})
    assert missing.data == {"found": False}


def test_a_word_of_an_attempt_with_its_phonemes():
    reads = {"speaking_attempts": attempts_reader([ATTEMPT])}
    word = tools(**reads).invoke("get_pronunciation_word_detail", ZH, {"attempt_id": "a-1", "word": "是"})
    assert word.data["flagged"] and word.data["path"] == "words[1]"
    assert word.data["phonemes"] == [{"phoneme": "sh", "accuracy": 30.0}, {"phoneme": "i", "accuracy": 50.0}]
    other = tools(**reads).invoke("get_pronunciation_word_detail", ZH, {"attempt_id": "a-1", "word": "老师"})
    assert other.data == {"found": False}


def test_history_lists_recent_attempts_and_the_apps_averages():
    progress = {"attempt_count": 1, "average_pronunciation": 72.5, "average_fluency": 80.0, "average_content_match": 100.0}
    result = tools(speaking_attempts=attempts_reader([ATTEMPT]), speaking_progress=lambda: progress).invoke(
        "get_pronunciation_history", ZH, {"limit": 3}
    )
    assert result.count == 1 and result.data["attempts"][0]["attempt_id"] == "a-1"
    assert result.data["averages_over_recent"]["average_pronunciation"] == 72.5
    with pytest.raises(ToolArgumentsInvalid):
        tools().invoke("get_pronunciation_history", ZH, {"limit": 50})


LESSON = {
    "lesson_id": "zh-lesson-1", "media_object_id": "media-77", "title": "在咖啡馆", "language": "zh",
    "level": "HSK2", "topic": "daily life", "duration_ms": 95000, "speech_speed": "natural",
    "available_modes": ["listen", "dictation"], "spoken_text_by_segment": {"s1": "你好", "s2": "我要一杯咖啡"},
}  # fmt: skip


def test_a_listening_lesson_and_the_learners_dictation_on_it():
    seen = []

    def progress(asset_id):
        seen.append(asset_id)
        return [
            {"segment_id": "s1", "checked_attempt_count": 2, "best_accuracy_percent": 100, "best_exact": True,
             "revealed": False, "last_hint_level": 0},
            {"segment_id": "s2", "checked_attempt_count": 3, "best_accuracy_percent": 62.5, "best_exact": False,
             "revealed": True, "last_hint_level": 2},
        ]  # fmt: skip

    reads = {"listening_lesson": lambda i: LESSON if i == "zh-lesson-1" else None, "listening_progress": progress}
    context = tools(**reads).invoke("get_current_listening_context", ZH, {"content_id": "zh-lesson-1"})
    assert context.data["title"] == "在咖啡馆" and context.data["line_count"] == 2 and context.data["duration_s"] == 95
    attempt = tools(**reads).invoke("get_listening_attempt", ZH, {"content_id": "zh-lesson-1"})
    assert seen == ["media-77"]  # progress is keyed by the lesson's media asset
    assert attempt.data["exact_count"] == 1 and attempt.data["revealed_count"] == 1 and attempt.count == 2
    assert attempt.evidence[1].ref == {"content_id": "zh-lesson-1", "item_id": "s2"}
    # a lesson of the other language is not the learner's to read here
    assert tools(**reads).invoke("get_current_listening_context", EN, {"content_id": "zh-lesson-1"}).data == {"found": False}


ARTICLE = {
    "id": "0b6f1c2e-0000-4000-8000-000000000001", "title": "A Morning in the City", "language": "en",
    "level": "B1", "topic": "travel", "reading_time_seconds": 120, "word_count": 240,
    "targets": [{"text": "forty minutes", "meaning": "bốn mươi phút"}],
}  # fmt: skip


def test_the_reading_in_view_by_the_new_uis_content_id():
    reads = {
        "reading_article": lambda i: ARTICLE if i == ARTICLE["id"] else None,
        "reading_chapter": lambda b, c: {"title": "Ch 1", "book_title": "Book", "author": "A", "position": 1,
                                         "learning_language": "en"} if (b, c) == ("b1", "c1") else None,
    }  # fmt: skip
    article = tools(**reads).invoke("get_current_reading_context", EN, {"content_id": f"article:{ARTICLE['id']}"})
    assert article.data["kind"] == "article" and article.data["targets"][0]["text"] == "forty minutes"
    assert article.data["content_id"] == f"article:{ARTICLE['id']}"
    chapter = tools(**reads).invoke("get_current_reading_context", EN, {"content_id": "book:b1:c1"})
    assert chapter.data["kind"] == "chapter" and chapter.data["book_title"] == "Book"
    assert tools(**reads).invoke("get_current_reading_context", ZH, {"content_id": f"article:{ARTICLE['id']}"}).data == {"found": False}
    assert tools(**reads).invoke("get_current_reading_context", EN, {"content_id": "media:x"}).data == {"found": False}


def test_reading_progress_names_articles_as_the_ui_does():
    rows = [{"article_id": ARTICLE["id"], "title": "A Morning", "correct_count": 2, "total": 3,
             "passage_level": "B1", "created_at": "2026-09-28T09:00:00+00:00"}]  # fmt: skip
    result = tools(reading_evidence=lambda limit: rows[:limit]).invoke("get_reading_progress", EN, {})
    assert result.data["attempts"][0]["content_id"] == f"article:{ARTICLE['id']}"
    assert result.evidence[0].excerpt == {"correct": 2, "total": 3}


def test_a_runtime_without_the_records_is_unavailable_not_empty(app_module_sqlite):
    """On the SQLite test backend the specialized repository raises: the turn reports the tool unavailable."""

    registry = build_tool_registry(
        writing_review=lambda i: None,
        reads=AppReads(speaking_attempts=lambda limit, **k: app_module_sqlite._specialized_learning_repository.list_speaking_attempt_records(limit, **k)),
    )
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        registry.invoke("get_pronunciation_history", ZH, {})


@pytest.fixture(scope="module")
def app_module_sqlite():
    import app

    return app
