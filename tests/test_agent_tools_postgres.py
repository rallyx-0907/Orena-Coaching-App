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
