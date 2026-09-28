"""The agent's read tools on PostgreSQL, through the app's own repositories.

Runs when `ORENA_TEST_POSTGRES_URL` names a throwaway database: the Alembic
chain in a fresh schema, then the tools exactly as a turn calls them - inside
`learner_context`, which sets the request context the repositories scope by.
What only PostgreSQL shows: that the session's language (`zh`, never the
contract's `zh-CN`) and the learner reach the repository's (user, language)
scope, so each tool reads that learner's rows in that language and no other.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@127.0.0.1:port/throwaway \\
        python -m pytest tests/test_agent_tools_postgres.py
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")

from sqlalchemy import create_engine, text  # noqa: E402

from writing_coach.agent.tools import LearnerScope  # noqa: E402
from writing_coach.agent.turn import learner_context  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

EN = LearnerScope(user_key="agent-pg-learner", language="en")
ZH = LearnerScope(user_key="agent-pg-learner", language="zh")
OTHER_ZH = LearnerScope(user_key="agent-pg-other", language="zh")


def _schema_url(schema: str) -> str:
    separator = "&" if "?" in URL else "?"
    return f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"


@contextmanager
def _database():
    from alembic import command
    from alembic.config import Config

    admin = create_engine(URL, future=True)
    schema = f"agent_tools_{uuid.uuid4().hex[:10]}"
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", _schema_url(schema).replace("%", "%%"))
        command.upgrade(cfg, "head")
        engine = create_engine(_schema_url(schema), future=True)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture(scope="module")
def engine():
    from writing_coach.persistence.auth_repository import PostgresAuthRepository

    with _database() as built:
        accounts = PostgresAuthRepository(engine=built)
        for learner in (EN, OTHER_ZH):  # the account rows sign-in creates; one per learner, all languages
            accounts.upsert_user({"sub": learner.user_key, "email": f"{learner.user_key}@example.test"}, set())
        yield built


@pytest.fixture(scope="module")
def app_module():
    import app

    return app


@pytest.fixture()
def learning(engine, app_module, monkeypatch):
    from writing_coach.persistence.learning_repository import PostgresLearningRepository

    repository = PostgresLearningRepository(engine=engine)
    monkeypatch.setattr(app_module, "_learning_repository", repository)
    return repository


def _essay(repository, text_: str, category: str, fragment: str) -> dict:
    error = {"fragment": fragment, "suggestion": fragment, "explanation_vi": "…", "category": category}
    return repository.create_essay(
        {
            "created_at": "2026-09-28T08:00:00+00:00", "prompt": "", "text": text_, "word_count": 12,
            "target_cefr": "", "grammar": 60.0, "vocabulary": 60.0, "coherence": 60.0,
            "task_achievement": 60.0, "naturalness": 60.0, "overall": 60.0, "cefr_estimate": "B1",
            "evaluator": "test", "summary_vi": "", "strengths_json": "[]", "strength_evidence_json": "[]",
            "priorities_json": "[]", "errors_json": json.dumps([error], ensure_ascii=False),
        }
    )  # fmt: skip


def _tools(app_module):
    from writing_coach.agent.runtime import build_tool_registry

    return build_tool_registry(
        writing_review=app_module._agent_writing_review, writing_history=lambda: app_module.api_error_memory()
    )


def test_the_writing_history_reads_the_session_language_and_learner(learning, app_module):
    with learner_context(ZH):
        _essay(learning, "我觉得市场比超市更有意思的。", "particle", "更有意思的")
    with learner_context(EN):
        _essay(learning, "Yesterday I go to the market.", "tense", "go")
    tools = _tools(app_module)
    for learner, category in ((ZH, "particle"), (EN, "tense")):
        with learner_context(learner):
            result = tools.invoke("get_writing_history_summary", learner, {})
        assert result.data["revision_count"] == 1, learner.language
        assert [row["category"] for row in result.data["categories"]] == [category], learner.language
    with learner_context(OTHER_ZH):
        other = tools.invoke("get_writing_history_summary", OTHER_ZH, {})
    assert other.data == {"revision_count": 0, "categories": []}


def test_grammar_completion_is_the_learners_own_in_their_language(learning, app_module):
    """R5 completion on PostgreSQL: scoped by learner and language, read through the app's own route."""

    from writing_coach.agent.runtime import AppReads, build_tool_registry

    tools = build_tool_registry(
        writing_review=lambda essay_id: None,
        reads=AppReads(
            grammar_library=lambda: app_module.api_grammar_library(),
            grammar_lesson=lambda grammar_id: app_module._agent_grammar_lesson(grammar_id),
        ),
    )
    point = "zh-hsk1-1-svo-c-b-n"
    with learner_context(ZH):
        before = tools.invoke("get_grammar_point", ZH, {"grammar_id": point})
        app_module.api_complete_grammar(point)  # the learner's own POST, not a tool
        after = tools.invoke("get_grammar_point", ZH, {"grammar_id": point})
        listed = tools.invoke("search_grammar_points", ZH, {"query": "svo", "level": "HSK1"})
    with learner_context(OTHER_ZH):
        other = tools.invoke("get_grammar_point", OTHER_ZH, {"grammar_id": point})
    assert before.data["completed"] is False and after.data["completed"] is True
    assert next(p for p in listed.data["points"] if p["grammar_id"] == point)["completed"] is True
    assert other.data["completed"] is False


def _skill_tools(app_module, engine):
    from writing_coach.agent.runtime import AppReads, build_tool_registry
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.persistence.reading_evidence_repository import ReadingEvidenceRepository
    from writing_coach.persistence.specialized_repository import PostgresSpecializedLearningRepository

    specialized = PostgresSpecializedLearningRepository(engine)
    evidence = ReadingEvidenceRepository(engine)
    return specialized, evidence, build_tool_registry(
        writing_review=lambda essay_id: None,
        reads=AppReads(
            speaking_attempts=lambda limit, *, asset_id=None, segment_id=None: specialized.list_speaking_attempt_records(
                limit, asset_id=asset_id, segment_id=segment_id
            ),
            speaking_progress=specialized.speaking_progress,
            listening_lesson=app_module._agent_listening_lesson,
            listening_progress=specialized.list_listening_progress_records,
            reading_article=ReadingContentRepository(engine).get_published_article,
            reading_evidence=evidence.list_evidence,
        ),
    )


def test_speaking_attempts_are_the_learners_own_in_their_language(engine, app_module):
    specialized, _, tools = _skill_tools(app_module, engine)
    words = [{"word": "是", "accuracy_score": 40.0, "error_type": "Mispronunciation", "phonemes": []}]
    with learner_context(ZH):
        stored = specialized.create_speaking_attempt_record(
            {
                "created_at": "2026-09-28T08:00:00+00:00", "language": "zh", "take_id": f"s1:1:{uuid.uuid4().hex}",
                "asset_id": "lesson-9", "segment_id": "s1", "reference_text": "我是学生", "transcript_text": "我是学生",
                "dimensions": {"pronunciation": 70.0}, "provenance": {},
                "evidence": {"pronunciation": {"words": words}},
            }
        )  # fmt: skip
        attempt = tools.invoke(
            "get_pronunciation_attempt", ZH, {"attempt_id": stored["id"], "content_id": "lesson-9", "item_id": "s1"}
        )
        history = tools.invoke("get_pronunciation_history", ZH, {})
    assert attempt.data["found"] and attempt.data["flagged_count"] == 1
    assert history.count == 1 and history.data["attempts"][0]["attempt_id"] == stored["id"]
    for learner in (EN, OTHER_ZH):  # the other language, the other learner: nothing
        with learner_context(learner):
            assert tools.invoke("get_pronunciation_history", learner, {}).count == 0
            assert tools.invoke("get_pronunciation_attempt", learner, {"attempt_id": stored["id"]}).data == {"found": False}


def test_listening_progress_is_read_by_the_lessons_media_asset(engine, app_module):
    from writing_coach.listening_catalog import catalog_lessons, lesson_metadata

    specialized, _, tools = _skill_tools(app_module, engine)
    lesson = next((item for item in catalog_lessons() if str(lesson_metadata(item)["language"]).startswith("zh")), None)
    if lesson is None:
        pytest.skip("no published Chinese listening lesson in the catalogue")
    metadata = app_module._agent_listening_lesson(lesson.lesson_id)
    with learner_context(ZH):
        specialized.save_listening_progress_record(
            {
                "asset_id": metadata["media_object_id"], "segment_id": "s1", "presentation": "checked",
                "revealed": False, "checked_attempt_count": 2, "best_accuracy_percent": 100.0, "best_exact": True,
                "last_answer": "", "updated_at": "2026-09-28T08:00:00+00:00",
            }
        )  # fmt: skip
        context = tools.invoke("get_current_listening_context", ZH, {"content_id": lesson.lesson_id})
        attempt = tools.invoke("get_listening_attempt", ZH, {"content_id": lesson.lesson_id})
    assert context.data["found"] and context.data["title"]
    assert attempt.count == 1 and attempt.data["exact_count"] == 1
    with learner_context(OTHER_ZH):
        assert tools.invoke("get_listening_attempt", OTHER_ZH, {"content_id": lesson.lesson_id}).count == 0


def test_reading_context_and_progress(engine, app_module):
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.persistence.reading_evidence_repository import QuestionInput, body_sha256

    _, evidence, tools = _skill_tools(app_module, engine)
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    body = "Tom missed the early train. He waited forty minutes on a cold platform. The next one was full."
    snapshot = content.record_source_item(
        source_id=content.built_in_source_id("manual"), source_native_id="", canonical_url="", title="T",
        author="", published_at=None, language="en", body=body, content_hash=uuid.uuid4().hex * 2,
        metadata={}, rights={"can_republish": True},
    )  # fmt: skip
    article = content.create_article(
        source_item_id=snapshot["id"], title="The Early Train", body=body, excerpt="", language="en", topic="travel",
        estimated_level="B1", estimated_confidence=0.7, word_count=20, reading_time_seconds=60, analysis={}, targets=[],
    )  # fmt: skip
    content.set_status(article["id"], "published", actor="admin")
    built = evidence.create_set(
        article["id"], expected_body_sha256=body_sha256(content.get_article(article["id"])["body"]),
        support_language="vi", generator_version="test/1", model="stub",
        questions=[QuestionInput("detail", "How long?", ["forty", "ten"], 0, "x", "forty minutes")],
        validation={}, actor="admin",
    )  # fmt: skip
    evidence.transition(built["id"], "needs_review", actor="admin")
    for question in built["questions"]:
        evidence.decide_question(built["id"], question["id"], decision="approve", actor="admin")
    evidence.transition(built["id"], "approved", actor="admin")
    content_id = f"article:{article['id']}"
    with learner_context(EN):
        evidence.submit_attempt(
            set_id=built["id"], operation_id=uuid.uuid4().hex,
            answers={q["id"]: 0 for q in built["questions"]}, support_language="vi",
        )  # fmt: skip
        in_view = tools.invoke("get_current_reading_context", EN, {"content_id": content_id})
        progress = tools.invoke("get_reading_progress", EN, {})
    assert in_view.data["found"] and in_view.data["title"] == "The Early Train"
    assert progress.count >= 1 and progress.data["attempts"][0]["content_id"] == content_id
    assert progress.data["attempts"][0]["correct"] == 1
    with learner_context(ZH):  # shared content, but in the learner's language only
        assert tools.invoke("get_current_reading_context", ZH, {"content_id": content_id}).data == {"found": False}
