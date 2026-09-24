"""The proposed Adaptive Reading schema, proved on both dialects.

`migrations/proposed/20260924_0014_adaptive_reading.py` is not in the applied
chain. This file applies it anyway - to a throwaway database - and writes the
rows each constraint and trigger must refuse, because a constraint is proved
only by watching it refuse. The same scenario list runs on:

- **SQLite**, always, including in CI: the current ORM schema is built the way
  the hermetic suite builds it (`Base.metadata.create_all`, foreign keys on),
  and the proposed `upgrade()` is applied on top through Alembic's own
  operations - batch rebuild, SQLite triggers, `sqlite_where` and all.
- **PostgreSQL**, when `ORENA_TEST_POSTGRES_URL` names a throwaway database:
  the real chain `20260811_0001 -> 20260923_0013` and then the proposal, in a
  fresh schema of its own, so a run leaves nothing behind and can be repeated.

One outcome per scenario on both is the parity claim: the review round-1
blocker was a constraint that held on one dialect and not the other.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/throwaway \\
        python -m pytest tests/test_adaptive_reading_schema_proposed.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")
import sqlalchemy as sa  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "migrations" / "proposed" / "20260924_0014_adaptive_reading.py"
URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
REFUSALS = (IntegrityError, DBAPIError, RuntimeError)
DIALECTS = ["sqlite", "postgresql"]


def _proposal():
    spec = importlib.util.spec_from_file_location("adaptive_reading_proposal", PROPOSAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- building a database at the proposed head --------------------------------

def _sqlite_engine(path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _run_proposal(engine, step: str) -> None:
    """Apply the proposal's `upgrade()`/`downgrade()` through Alembic's own
    operations, exactly as `alembic upgrade` would call it."""
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    module = _proposal()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def _sqlite_at_head(path: Path):
    from writing_coach.persistence.models import Base

    engine = _sqlite_engine(path)
    Base.metadata.create_all(engine)
    _run_proposal(engine, "upgrade")
    return engine


def _pg_schema_url(schema: str) -> str:
    separator = "&" if "?" in URL else "?"
    return f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"


def _alembic(schema: str):
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option(
        "version_locations",
        os.pathsep.join([str(ROOT / "migrations" / "versions"), str(ROOT / "migrations" / "proposed")]),
    )
    cfg.set_main_option("sqlalchemy.url", _pg_schema_url(schema).replace("%", "%%"))
    return cfg


@contextmanager
def _pg_schema():
    """A fresh schema per use, dropped afterwards: the chain runs from nothing."""
    admin = create_engine(URL, future=True)
    schema = f"adaptive_proof_{uuid.uuid4().hex[:10]}"
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield schema
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture(scope="module", params=DIALECTS)
def db(request, tmp_path_factory):
    if request.param == "sqlite":
        engine = _sqlite_at_head(tmp_path_factory.mktemp("adaptive") / "proof.db")
        yield engine
        engine.dispose()
        return
    if not URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
    from alembic import command

    with _pg_schema() as schema:
        command.upgrade(_alembic(schema), "20260924_0014")
        engine = create_engine(_pg_schema_url(schema), future=True)
        yield engine
        engine.dispose()


# ---- rows ---------------------------------------------------------------------

_TYPES = {
    "uuid": sa.Uuid(),
    "json": sa.JSON(),
    "bool": sa.Boolean(),
    "time": sa.DateTime(timezone=True),
    "float": sa.Float(),
}
_COLUMN_TYPES = {
    **dict.fromkeys(
        ["id", "user_id", "session_id", "set_id", "article_id", "source_id", "source_item_id"], "uuid"
    ),
    **dict.fromkeys(
        [
            "answers", "options_json", "validation_json", "by_question_type_json", "questions",
            "recycled_words", "languages", "topic_hints", "polling_policy", "metadata_json",
            "rights_snapshot_json", "adaptation_json", "analysis_json",
        ],
        "json",
    ),
    **dict.fromkeys(
        [
            "machine_suggested", "admin_approved", "admin_rejected", "automation_allowed",
            "can_republish", "can_adapt", "attribution_required", "polling_enabled", "is_adapted",
        ],
        "bool",
    ),
    **dict.fromkeys(
        [
            "created_at", "updated_at", "reviewed_at", "fetched_at", "published_at", "last_login",
        ],
        "time",
    ),
    **dict.fromkeys(["ability", "ability_before", "ability_after", "passage_difficulty"], "float"),
}


def _table(name: str, columns):
    return sa.table(
        name,
        *(
            sa.column(column, _TYPES[_COLUMN_TYPES[column]]) if column in _COLUMN_TYPES else sa.column(column)
            for column in columns
        ),
    )


def _insert(engine, name: str, /, **values) -> None:
    with engine.begin() as connection:
        connection.execute(sa.insert(_table(name, values)).values(**values))


def _update(engine, name: str, row_id, /, **values) -> None:
    table = _table(name, ["id", *values])
    with engine.begin() as connection:
        connection.execute(sa.update(table).where(table.c.id == row_id).values(**values))


def _delete(engine, name: str, row_id) -> None:
    table = _table(name, ["id"])
    with engine.begin() as connection:
        connection.execute(sa.delete(table).where(table.c.id == row_id))


def _count(engine, name: str, where: str = "1 = 1", **params) -> int:
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT count(*) FROM {name} WHERE {where}"), params).scalar_one()


def _now() -> datetime:
    return datetime.now(UTC)


def _sha(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _user(engine) -> uuid.UUID:
    user_id = uuid.uuid4()
    _insert(engine, "users", id=user_id, user_key=f"proof-{user_id.hex}", email="", name="", picture="",
            role="user", created_at=_now(), last_login=None)
    return user_id


BODY = "Tom missed the early train. He waited forty minutes on a cold platform."


def _article(engine, *, language="en", body=BODY) -> uuid.UUID:
    source_id, item_id, article_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = _now()
    _insert(engine, "reading_sources", id=source_id, slug=f"proof-{source_id.hex}", name="Proof",
            source_type="manual", base_url="", state="active", languages=[language], topic_hints=[],
            automation_allowed=False, can_republish=False, can_adapt=False, attribution_required=True,
            license_note="", polling_enabled=False, polling_policy={}, polling_cursor="", last_error="",
            approved_by="", created_by="proof", created_at=now, updated_at=now)
    _insert(engine, "reading_source_items", id=item_id, source_id=source_id, source_native_id="",
            canonical_url="", original_title="T", original_author="", original_language=language,
            original_content=body, content_hash=_sha(body + item_id.hex), metadata_json={},
            rights_snapshot_json={}, revision=1, fetched_at=now, created_at=now)
    _insert(engine, "reading_articles", id=article_id, source_item_id=item_id, title="T", body=body,
            excerpt="", language=language, topic="", subtopic="", estimated_level="B1",
            estimated_level_confidence=0.5, effective_level="B1", word_count=12,
            reading_time_seconds=30, is_adapted=False, adaptation_json={}, analysis_json={},
            status="published", rejection_reason="", content_revision=1, created_at=now,
            updated_at=now, published_at=now)
    return article_id


def _set(engine, article_id, *, language="en", support="vi", status="draft", body=BODY, **extra) -> uuid.UUID:
    set_id = uuid.uuid4()
    now = _now()
    _insert(engine, "reading_comprehension_sets", id=set_id, article_id=article_id, language_code=language,
            support_language=support, article_body_sha256=_sha(body), status=status,
            generator_version="reading-questions/1", model="proof", validation_json={},
            reviewed_by=extra.pop("reviewed_by", ""), reviewed_at=extra.pop("reviewed_at", None), review_reason="",
            created_at=now, updated_at=now, **extra)
    return set_id


def _question(engine, set_id, *, question_type="detail", options=("forty", "ten", "five"),
              correct_index=0, evidence="forty minutes", start=None, end=None, approved=False,
              rejected=False, rank=0) -> uuid.UUID:
    question_id = uuid.uuid4()
    if evidence is not None and start is None:
        start = BODY.index(evidence)
        end = start + len(evidence)
    now = _now()
    _insert(engine, "reading_comprehension_questions", id=question_id, set_id=set_id, rank=rank,
            question_type=question_type, prompt="How long did Tom wait?", options_json=list(options),
            correct_index=correct_index, explanation="Anh ấy đợi bốn mươi phút.", evidence_text=evidence,
            evidence_start=start, evidence_end=end, machine_suggested=True, admin_approved=approved,
            admin_rejected=rejected, created_at=now, updated_at=now)
    return question_id


def _approve(engine, set_id) -> None:
    _update(engine, "reading_comprehension_sets", set_id, status="needs_review")
    _update(engine, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(),
            reviewed_by="admin")


def _approved_set(engine, article_id=None, **kwargs):
    article_id = article_id or _article(engine, language=kwargs.get("language", "en"))
    set_id = _set(engine, article_id, **kwargs)
    _question(engine, set_id, approved=True)
    _approve(engine, set_id)
    return article_id, set_id


def _attempt_values(user_id, set_id, *, language="en", ordinal=1, **overrides) -> dict:
    attempt_id = uuid.uuid4()
    values = dict(
        id=attempt_id, subject_kind="comprehension_set", user_id=user_id, language_code=language,
        set_id=set_id, ordinal=ordinal, operation_id=f"op-{attempt_id.hex}",
        request_digest=_sha(attempt_id.hex), evaluator_version="reading-eval/1",
        ability_policy_version="reading-ability/1", passage_level="B1", passage_difficulty=0.0,
        ability_before=0.0, ability_after=0.25, created_at=_now(),
        answers=[{"question_id": "q", "selected_index": 0, "correct": True}], correct_count=1, total=1,
    )
    values.update(overrides)
    return values


def _attempt(engine, user_id, set_id, **kwargs) -> uuid.UUID:
    values = _attempt_values(user_id, set_id, **kwargs)
    _insert(engine, "reading_attempts", **values)
    return values["id"]


def _replace(engine, name: str, conflict: list[str], /, **values) -> None:
    """Each dialect's own way to overwrite a row that already exists: SQLite's
    `INSERT OR REPLACE`, PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE`."""
    table = _table(name, values)
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        statement = insert(table).values(**values).on_conflict_do_update(
            index_elements=conflict,
            set_={key: value for key, value in values.items() if key not in conflict},
        )
    else:
        statement = sa.insert(table).values(**values).prefix_with("OR REPLACE")
    with engine.begin() as connection:
        connection.execute(statement)


def _legacy_attempt(engine, user_id, *, language="en") -> tuple[uuid.UUID, uuid.UUID]:
    """A generated-session attempt written with exactly the columns today's
    writer and importer name - no `subject_kind`, no new column at all."""
    session_id, attempt_id = uuid.uuid4(), uuid.uuid4()
    now = _now()
    legacy = uuid.uuid4().int % 1_000_000
    _insert(engine, "reading_sessions", id=session_id, user_id=user_id, language_code=language,
            legacy_id=legacy, created_at=now, target_level="B1", topic="work", learner_goal="",
            title="T", passage="P", questions=[], recycled_words=[], generation_mode="practice")
    _insert(engine, "reading_attempts", id=attempt_id, session_id=session_id, legacy_id=1,
            created_at=now, answers=[0], correct_count=1, total=1)
    return session_id, attempt_id


def _refused(action) -> None:
    with pytest.raises(REFUSALS):
        action()


# ---- blocker 1: history never blocks a replacement ----------------------------

def test_a_rejected_set_and_its_replacement_coexist_and_only_one_is_approved(db):
    article = _article(db)
    rejected = _set(db, article)
    _question(db, rejected, rejected=True)
    _update(db, "reading_comprehension_sets", rejected, status="needs_review")
    _update(db, "reading_comprehension_sets", rejected, status="rejected", reviewed_at=_now(), reviewed_by="admin")
    # The replacement is prepared and approved beside the rejection - nothing
    # had to be archived to make room.
    _, first = _approved_set(db, article)
    assert _count(db, "reading_comprehension_sets", "article_id = :a", a=_bind(db, article)) == 2
    # A second approved set for the same article and support language is refused...
    second = _set(db, article)
    _question(db, second, approved=True)
    _update(db, "reading_comprehension_sets", second, status="needs_review")
    _refused(lambda: _update(db, "reading_comprehension_sets", second, status="approved", reviewed_at=_now(), reviewed_by="admin"))
    # ...until the first stops being approved, and a stale set blocks nothing.
    _update(db, "reading_comprehension_sets", first, status="stale")
    _update(db, "reading_comprehension_sets", second, status="approved", reviewed_at=_now(), reviewed_by="admin")
    # Another support language is another set.
    _approved_set(db, article, support="en")


# ---- blocker 2: no path from a content delete to learner evidence --------------

def test_an_article_with_learner_evidence_cannot_be_purged_and_nothing_is_taken(db):
    learner = _user(db)
    article, set_id = _approved_set(db)
    attempt = _attempt(db, learner, set_id)
    _refused(lambda: _delete(db, "reading_articles", article))
    _refused(lambda: _delete(db, "reading_comprehension_sets", set_id))
    assert _count(db, "reading_attempts", "id = :i", i=_bind(db, attempt)) == 1
    assert _count(db, "reading_comprehension_sets", "id = :i", i=_bind(db, set_id)) == 1


def test_a_set_that_reached_learners_is_never_deleted_even_without_attempts(db):
    _, set_id = _approved_set(db)
    _refused(lambda: _delete(db, "reading_comprehension_sets", set_id))
    _update(db, "reading_comprehension_sets", set_id, status="archived")
    _refused(lambda: _delete(db, "reading_comprehension_sets", set_id))


def test_the_purge_path_deletes_undecided_and_rejected_sets_explicitly_then_the_article(db):
    article = _article(db)
    draft = _set(db, article)
    _question(db, draft)
    rejected = _set(db, article)
    _question(db, rejected, rejected=True)
    _update(db, "reading_comprehension_sets", rejected, status="needs_review")
    _update(db, "reading_comprehension_sets", rejected, status="rejected", reviewed_at=_now(), reviewed_by="admin")
    # RESTRICT: the article does not take its sets with it...
    _refused(lambda: _delete(db, "reading_articles", article))
    # ...the purge deletes them first (their questions cascade), then the article.
    _delete(db, "reading_comprehension_sets", draft)
    _delete(db, "reading_comprehension_sets", rejected)
    _delete(db, "reading_articles", article)
    assert _count(db, "reading_comprehension_questions", "set_id IN (:a, :b)",
                  a=_bind(db, draft), b=_bind(db, rejected)) == 0


# ---- blocker 3: the account-data contract --------------------------------------

def test_a_retried_submit_cannot_create_a_second_attempt(db):
    learner = _user(db)
    _, set_id = _approved_set(db)
    _attempt(db, learner, set_id, ordinal=1, operation_id="submit-1")
    # Same operation: the unique constraint is what serializes a raced duplicate.
    _refused(lambda: _attempt(db, learner, set_id, ordinal=2, operation_id="submit-1"))
    # Same ordinal under a new operation: two attempts cannot claim one checkpoint slot.
    _refused(lambda: _attempt(db, learner, set_id, ordinal=1, operation_id="submit-2"))
    # Operation ids are scoped to the account: another learner's "submit-1" is theirs.
    _attempt(db, _user(db), set_id, ordinal=1, operation_id="submit-1")
    # Legacy rows carry NULL in both keys and never collide with each other.
    _legacy_attempt(db, learner)
    _legacy_attempt(db, learner)


def test_a_set_attempt_carries_every_fact_the_evidence_contract_requires(db):
    learner = _user(db)
    _, set_id = _approved_set(db)
    for missing in ("evaluator_version", "ability_policy_version", "operation_id", "request_digest",
                    "passage_level", "passage_difficulty", "ability_before", "ability_after", "ordinal"):
        _refused(lambda missing=missing: _attempt(db, learner, set_id, **{missing: None}))
    _refused(lambda: _attempt(db, learner, set_id, request_digest="ABC"))
    _refused(lambda: _attempt(db, learner, set_id, request_digest=_sha("x").upper()))
    _refused(lambda: _attempt(db, learner, set_id, ordinal=0))
    _refused(lambda: _attempt(db, learner, set_id, total=0, correct_count=0, answers=[]))
    _refused(lambda: _attempt(db, learner, set_id, correct_count=2))
    _refused(lambda: _attempt(db, learner, set_id, total=2, answers=[{"question_id": "q"}]))
    _refused(lambda: _attempt(db, learner, set_id, ability_after=float("nan")))
    _refused(lambda: _attempt(db, learner, set_id, ability_after=float("inf")))
    # The two shapes are exclusive: a set attempt has no session.
    session_id, _ = _legacy_attempt(db, learner)
    _refused(lambda: _attempt(db, learner, set_id, session_id=session_id))
    _refused(lambda: _attempt(db, learner, set_id, subject_kind="generated_session"))
    _refused(lambda: _attempt(db, learner, set_id, subject_kind="something_else"))
    # The range chooses no algorithm: a logit, a theta and an Elo rating all fit.
    _attempt(db, learner, set_id, ordinal=1, ability_before=-3.2, ability_after=-2.9)
    _attempt(db, learner, set_id, ordinal=2, ability_before=1480.0, ability_after=1496.5)


def test_a_legacy_write_is_exactly_what_it_was_and_cannot_borrow_the_new_shape(db):
    learner = _user(db)
    _, attempt = _legacy_attempt(db, learner)
    with db.connect() as connection:
        kind = connection.execute(
            text("SELECT subject_kind FROM reading_attempts WHERE id = :i"), {"i": _bind(db, attempt)}
        ).scalar_one()
    assert kind == "generated_session"
    _, set_id = _approved_set(db)
    session_id, _ = _legacy_attempt(db, learner)
    _refused(lambda: _insert(db, "reading_attempts", id=uuid.uuid4(), session_id=session_id, legacy_id=2,
                             created_at=_now(), answers=[0], correct_count=1, total=1, set_id=set_id))
    # The importer's upsert of a legacy row still works: only set attempts are immutable.
    _update(db, "reading_attempts", attempt, correct_count=0)


def test_the_current_orm_model_still_reads_and_writes_after_the_upgrade(db):
    """Code rollback without schema rollback is the real rollback path, so the
    model in `models.py` today - which knows none of the new columns - must
    keep working against the upgraded schema."""
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import ReadingAttempt, ReadingSession

    learner = _user(db)
    session_id, _ = _legacy_attempt(db, learner)
    with Session(db) as session, session.begin():
        session.add(ReadingAttempt(id=uuid.uuid4(), session_id=session_id, legacy_id=7, created_at=_now(),
                                   answers=[1, 0], correct_count=1, total=2))
    with Session(db) as session:
        rows = session.scalars(sa.select(ReadingAttempt).where(ReadingAttempt.session_id == session_id)).all()
        assert sorted(row.legacy_id for row in rows) == [1, 7]
        assert session.get(ReadingSession, session_id) is not None


def test_a_learner_attempt_cannot_attach_to_a_set_in_another_language(db):
    learner = _user(db)
    _, set_id = _approved_set(db)  # an English set
    _refused(lambda: _attempt(db, learner, set_id, language="zh"))


def test_a_learner_meets_only_an_approved_set(db):
    learner = _user(db)
    article = _article(db)
    pending = _set(db, article)
    _question(db, pending, approved=True)
    _update(db, "reading_comprehension_sets", pending, status="needs_review")
    _refused(lambda: _attempt(db, learner, pending))
    _update(db, "reading_comprehension_sets", pending, status="approved", reviewed_at=_now(), reviewed_by="admin")
    _attempt(db, learner, pending, ordinal=1)
    _update(db, "reading_comprehension_sets", pending, status="stale")
    _refused(lambda: _attempt(db, learner, pending, ordinal=2))


def test_a_set_attempt_is_immutable_evidence(db):
    learner = _user(db)
    _, set_id = _approved_set(db)
    attempt = _attempt(db, learner, set_id)
    _refused(lambda: _update(db, "reading_attempts", attempt, ability_after=9.0))
    _refused(lambda: _update(db, "reading_attempts", attempt, correct_count=0))


def test_the_projection_is_one_row_per_account_language_and_policy_and_discardable(db):
    learner = _user(db)
    _, set_id = _approved_set(db)
    _attempt(db, learner, set_id)

    def projection(policy="reading-ability/1", **overrides):
        values = dict(id=uuid.uuid4(), user_id=learner, language_code="en", policy_version=policy,
                      ability=0.25, consumed_through_ordinal=1, by_question_type_json={"detail": [1, 1]},
                      updated_at=_now())
        values.update(overrides)
        _insert(db, "reading_ability_projections", **values)
        return values["id"]

    first = projection()
    _refused(projection)
    projection(policy="reading-ability/2")  # a new policy builds beside the old one
    _refused(lambda: projection(policy="reading-ability/3", ability=float("nan")))
    _refused(lambda: projection(policy="reading-ability/4", consumed_through_ordinal=-1))
    # Discarding it costs a rebuild, never evidence.
    _delete(db, "reading_ability_projections", first)
    assert _count(db, "reading_attempts", "user_id = :u", u=_bind(db, learner)) == 1


def test_account_deletion_through_the_enumeration_removes_one_learner_and_nothing_else(db):
    module = _proposal()
    leaving, staying = _user(db), _user(db)
    _, set_id = _approved_set(db)
    for learner in (leaving, staying):
        _legacy_attempt(db, learner)
        _attempt(db, learner, set_id)
        _insert(db, "reading_ability_projections", id=uuid.uuid4(), user_id=learner, language_code="en",
                policy_version="reading-ability/1", ability=0.25, consumed_through_ordinal=1,
                by_question_type_json={}, updated_at=_now())
    with db.begin() as connection:
        for table, predicate in module.ACCOUNT_OWNED:
            connection.execute(text(f"DELETE FROM {table} WHERE {predicate}"), {"user_id": _bind(db, leaving)})
    assert _owned(db, leaving) == (0, 0, 0, 0)
    assert _owned(db, staying) == (1, 1, 1, 1)
    # Platform content is untouched by a learner leaving.
    assert _count(db, "reading_comprehension_sets", "id = :i", i=_bind(db, set_id)) == 1


def test_the_owner_foreign_keys_cascade_from_the_account_row_too(db):
    learner = _user(db)
    _, set_id = _approved_set(db)
    _legacy_attempt(db, learner)
    _attempt(db, learner, set_id)
    _insert(db, "reading_ability_projections", id=uuid.uuid4(), user_id=learner, language_code="en",
            policy_version="reading-ability/1", ability=0.0, consumed_through_ordinal=1,
            by_question_type_json={}, updated_at=_now())
    _delete(db, "users", learner)
    assert _owned(db, learner) == (0, 0, 0, 0)


def _owned(db, learner) -> tuple[int, int, int, int]:
    bound = _bind(db, learner)
    return (
        _count(db, "reading_attempts", "user_id = :u", u=bound),
        _count(db, "reading_attempts",
               "session_id IN (SELECT id FROM reading_sessions WHERE user_id = :u)", u=bound),
        _count(db, "reading_sessions", "user_id = :u", u=bound),
        _count(db, "reading_ability_projections", "user_id = :u", u=bound),
    )


# ---- blocker 4 and the question rules -------------------------------------------

def test_question_shape_is_bounded_and_evidence_spans_are_structurally_real(db):
    set_id = _set(db, _article(db))
    _refused(lambda: _question(db, set_id, options=("only one",)))
    _refused(lambda: _question(db, set_id, options=tuple("abcdefg")))
    _refused(lambda: _question(db, set_id, correct_index=3))
    _refused(lambda: _question(db, set_id, correct_index=-1))
    _refused(lambda: _question(db, set_id, rank=-1))
    _refused(lambda: _question(db, set_id, approved=True, rejected=True))
    # Evidence is all or nothing, non-empty, and as long as its span.
    _refused(lambda: _question(db, set_id, evidence="forty minutes", start=0, end=None))
    _refused(lambda: _question(db, set_id, evidence="", start=0, end=0))
    _refused(lambda: _question(db, set_id, evidence="forty minutes", start=5, end=6))
    _refused(lambda: _question(db, set_id, evidence="forty minutes", start=-1, end=12))
    # A detail question must cite; a main-idea question may rest on the whole passage.
    _refused(lambda: _question(db, set_id, question_type="detail", evidence=None))
    _question(db, set_id, question_type="main_idea", evidence=None)
    _question(db, set_id, question_type="authors_purpose", evidence=None)
    _refused(lambda: _question(db, set_id, question_type="opinion"))
    # A span in Chinese is counted in characters, the same on both dialects.
    _question(db, set_id, evidence="汉字", start=3, end=5)
    _refused(lambda: _question(db, set_id, evidence="汉字", start=3, end=9))


def test_a_non_array_options_value_is_refused(db):
    set_id = _set(db, _article(db))
    question_id = uuid.uuid4()
    now = _now()
    _refused(lambda: _insert(db, "reading_comprehension_questions", id=question_id, set_id=set_id, rank=0,
                             question_type="main_idea", prompt="p", options_json={"a": 1}, correct_index=0,
                             explanation="e", evidence_text=None, evidence_start=None, evidence_end=None,
                             machine_suggested=True, admin_approved=False, admin_rejected=False,
                             created_at=now, updated_at=now))


def test_a_set_is_grounded_in_one_body_and_that_anchor_is_frozen_once_decided(db):
    article = _article(db)
    _refused(lambda: _insert(
        db, "reading_comprehension_sets", id=uuid.uuid4(), article_id=article, language_code="en",
        support_language="vi", article_body_sha256="not-a-hash", status="draft",
        generator_version="g", model="", validation_json={}, reviewed_by="", review_reason="",
        created_at=_now(), updated_at=_now()))
    draft = _set(db, article)
    # While undecided, the set may be rebuilt against a corrected body.
    _update(db, "reading_comprehension_sets", draft, article_body_sha256=_sha(BODY + " edited"))
    _, approved = _approved_set(db)
    _refused(lambda: _update(db, "reading_comprehension_sets", approved, article_body_sha256=_sha("other")))
    _refused(lambda: _update(db, "reading_comprehension_sets", approved, support_language="en"))
    # An article edit makes the set stale; the admin can re-approve it once the
    # service has re-validated the anchor, or archive it.
    _update(db, "reading_comprehension_sets", approved, status="stale")
    _update(db, "reading_comprehension_sets", approved, status="approved")
    _update(db, "reading_comprehension_sets", approved, status="archived")


# ---- set lifecycle ---------------------------------------------------------------

def test_a_set_reaches_approval_only_through_review_with_every_question_decided(db):
    article = _article(db)
    _refused(lambda: _set(db, article, status="approved", reviewed_at=_now(), reviewed_by="admin"))
    set_id = _set(db, article)
    undecided = _question(db, set_id)
    _update(db, "reading_comprehension_sets", set_id, status="needs_review")
    # An undecided question blocks approval...
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(), reviewed_by="admin"))
    # ...and so does a set whose every question was rejected.
    _update(db, "reading_comprehension_questions", undecided, admin_rejected=True)
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(), reviewed_by="admin"))
    kept = _question(db, set_id, approved=True, rank=1)
    # A decision has a moment.
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="approved"))
    _update(db, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(), reviewed_by="admin")
    # Frozen: no question is added, edited or removed after the decision.
    _refused(lambda: _question(db, set_id, approved=True))
    _refused(lambda: _update(db, "reading_comprehension_questions", kept, prompt="changed"))
    _refused(lambda: _delete(db, "reading_comprehension_questions", kept))
    # Only review transitions.
    for illegal in ("draft", "needs_review", "rejected"):
        _refused(lambda illegal=illegal: _update(db, "reading_comprehension_sets", set_id, status=illegal))
    _update(db, "reading_comprehension_sets", set_id, status="archived")
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="approved"))


def test_a_rejected_set_is_history_and_frozen(db):
    set_id = _set(db, _article(db))
    question = _question(db, set_id, rejected=True)
    _update(db, "reading_comprehension_sets", set_id, status="needs_review")
    _update(db, "reading_comprehension_sets", set_id, status="rejected", reviewed_at=_now(), reviewed_by="admin")
    _refused(lambda: _update(db, "reading_comprehension_questions", question, prompt="rewritten"))
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="needs_review"))


def test_content_kind_is_one_vocabulary_and_defaults_to_what_every_row_already_is(db):
    article = _article(db)
    with db.connect() as connection:
        assert connection.execute(
            text("SELECT content_kind FROM reading_articles WHERE id = :i"), {"i": _bind(db, article)}
        ).scalar_one() == "article"
    _update(db, "reading_articles", article, content_kind="news")
    for other in ("book", "book_excerpt", "story", "essay", "quote", ""):
        _refused(lambda other=other: _update(db, "reading_articles", article, content_kind=other))


# ---- blocker 5: the catalogue says what the rows proved ---------------------------

def test_the_partial_index_keeps_its_predicate_and_every_upward_key_restricts(db):
    with db.connect() as connection:
        if db.dialect.name == "postgresql":
            definition = connection.execute(text(
                "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_reading_comprehension_set_approved'"
                " AND schemaname = current_schema()"
            )).scalar_one()
            assert "UNIQUE" in definition and "WHERE" in definition and "'approved'" in definition
            actions = dict(connection.execute(text(
                "SELECT conname, confdeltype FROM pg_constraint WHERE contype = 'f'"
                " AND connamespace = current_schema()::regnamespace"
                " AND conrelid IN ('reading_comprehension_sets'::regclass,"
                " 'reading_comprehension_questions'::regclass, 'reading_attempts'::regclass,"
                " 'reading_ability_projections'::regclass)"
            )).all())
            by_target = {
                "fk_reading_comprehension_set_article_scope": "r",
                "reading_comprehension_questions_set_id_fkey": "c",
                "fk_reading_attempt_set_scope": "r",
                "fk_reading_attempt_user": "c",
                "reading_ability_projections_user_id_fkey": "c",
            }
            for name, action in by_target.items():
                assert actions[name] == action, name
        else:
            definition = connection.execute(text(
                "SELECT sql FROM sqlite_master WHERE name = 'uq_reading_comprehension_set_approved'"
            )).scalar_one()
            assert "UNIQUE" in definition and "WHERE" in definition and "'approved'" in definition
            sets = {row[2]: row[6] for row in connection.execute(text("PRAGMA foreign_key_list(reading_comprehension_sets)"))}
            attempts = {row[2]: row[6] for row in connection.execute(text("PRAGMA foreign_key_list(reading_attempts)"))}
            questions = {row[2]: row[6] for row in connection.execute(text("PRAGMA foreign_key_list(reading_comprehension_questions)"))}
            projections = {row[2]: row[6] for row in connection.execute(text("PRAGMA foreign_key_list(reading_ability_projections)"))}
            assert sets["reading_articles"] == "RESTRICT"
            assert attempts["reading_comprehension_sets"] == "RESTRICT"
            assert attempts["users"] == "CASCADE"
            assert attempts["reading_sessions"] == "CASCADE"
            assert questions["reading_comprehension_sets"] == "CASCADE"
            assert projections["users"] == "CASCADE"


def test_question_writes_and_set_approval_serialize(db):
    """PostgreSQL only - SQLite serializes every writer on the whole database.
    While one transaction is adding a question, approval of that set must wait
    for it rather than count a snapshot that is about to be wrong."""
    if db.dialect.name != "postgresql":
        pytest.skip("SQLite has one writer at a time by construction")
    set_id = _set(db, _article(db))
    _question(db, set_id, approved=True)
    _update(db, "reading_comprehension_sets", set_id, status="needs_review")
    writer = db.connect()
    transaction = writer.begin()
    try:
        writer.execute(sa.insert(_table("reading_comprehension_questions", [
            "id", "set_id", "rank", "question_type", "prompt", "options_json", "correct_index",
            "explanation", "machine_suggested", "admin_approved", "admin_rejected", "created_at", "updated_at",
        ])).values(id=uuid.uuid4(), set_id=set_id, rank=2, question_type="main_idea", prompt="p",
                   options_json=["a", "b"], correct_index=0, explanation="e", machine_suggested=True,
                   admin_approved=False, admin_rejected=False, created_at=_now(), updated_at=_now()))
        with db.connect() as approver:
            approver.execute(text("SET lock_timeout = '300ms'"))
            with pytest.raises(DBAPIError, match="lock timeout"):
                approver.execute(text(
                    "UPDATE reading_comprehension_sets SET status = 'approved', reviewed_at = now()"
                    " WHERE id = :i"), {"i": set_id})
    finally:
        transaction.commit()
        writer.close()
    # With the undecided question now committed, the approval's count sees it.
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(), reviewed_by="admin"))


def _bind(db, value: uuid.UUID):
    """How `sa.Uuid()` stores a UUID: native on PostgreSQL, 32 hex characters on SQLite."""
    return value if db.dialect.name == "postgresql" else value.hex


# ---- migration and downgrade ----------------------------------------------------

@pytest.mark.parametrize("dialect", DIALECTS)
def test_downgrade_keeps_legacy_evidence_and_refuses_when_the_feature_has_data(dialect, tmp_path):
    if dialect == "postgresql" and not URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
    with _fresh(dialect, tmp_path) as (engine, upgrade, downgrade):
        learner = _user(engine)
        _, legacy = _legacy_attempt(engine, learner)
        # 1. Nothing written by the feature: the downgrade runs and the legacy
        #    evidence is intact, NOT NULL restored.
        downgrade()
        assert _columns(engine, "reading_attempts") == {
            "id", "session_id", "legacy_id", "created_at", "answers", "correct_count", "total",
        }
        assert not _has_table(engine, "reading_comprehension_sets")
        assert "content_kind" not in _columns(engine, "reading_articles")
        assert _count(engine, "reading_attempts", "id = :i", i=_bind(engine, legacy)) == 1
        _refused(lambda: _insert(engine, "reading_attempts", id=uuid.uuid4(), session_id=None, legacy_id=1,
                                 created_at=_now(), answers=[], correct_count=0, total=0))
        # 2. Up again, and the feature writes one learner attempt: the downgrade
        #    refuses and changes nothing.
        upgrade()
        _, set_id = _approved_set(engine)
        attempt = _attempt(engine, learner, set_id)
        _refused(downgrade)
        assert _has_table(engine, "reading_comprehension_sets")
        assert _count(engine, "reading_attempts", "id = :i", i=_bind(engine, attempt)) == 1
        assert _count(engine, "reading_attempts", "id = :i", i=_bind(engine, legacy)) == 1


def test_the_downgrade_refusal_is_in_the_offline_script_too():
    """`alembic downgrade --sql` is how a human reads a downgrade before running
    it; the refusal must be in what they read, not only in Python."""
    from alembic import command

    cfg = _alembic("public")
    cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://invalid:invalid@localhost/invalid")
    buffer = io.StringIO()
    cfg.output_buffer = buffer
    command.upgrade(cfg, "20260923_0013:20260924_0014", sql=True)
    command.downgrade(cfg, "20260924_0014:20260923_0013", sql=True)
    rendered = buffer.getvalue()
    assert "CREATE UNIQUE INDEX uq_reading_comprehension_set_approved" in rendered
    assert "WHERE status = 'approved'" in rendered
    assert "downgrade refused" in rendered
    assert rendered.index("downgrade refused") < rendered.index("DROP TABLE reading_ability_projections")
    assert rendered.index("IN SHARE ROW EXCLUSIVE MODE") < rendered.index("downgrade refused")


@contextmanager
def _fresh(dialect: str, tmp_path: Path):
    if dialect == "sqlite":
        engine = _sqlite_at_head(tmp_path / "rehearsal.db")
        try:
            yield engine, lambda: _run_proposal(engine, "upgrade"), lambda: _run_proposal(engine, "downgrade")
        finally:
            engine.dispose()
        return
    from alembic import command

    with _pg_schema() as schema:
        cfg = _alembic(schema)
        command.upgrade(cfg, "20260924_0014")
        engine = create_engine(_pg_schema_url(schema), future=True)
        try:
            yield (
                engine,
                lambda: command.upgrade(cfg, "20260924_0014"),
                lambda: command.downgrade(cfg, "20260923_0013"),
            )
        finally:
            engine.dispose()


def _columns(engine, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(engine).get_columns(table)}


def _has_table(engine, table: str) -> bool:
    return sa.inspect(engine).has_table(table)


# ---- round 2 findings -------------------------------------------------------------

def test_evidence_commits_when_the_projection_cannot_measure_it(db):
    """B1: the answers are the evidence. A policy that cannot measure them - no
    mapping for this level, a failed replay - leaves the four ability facts
    NULL together, and the attempt still commits with no projection at all."""
    learner = _user(db)
    _, set_id = _approved_set(db)
    unmeasured = dict(ability_policy_version=None, passage_difficulty=None, ability_before=None,
                      ability_after=None)
    _attempt(db, learner, set_id, ordinal=1, **unmeasured)
    assert _count(db, "reading_ability_projections", "user_id = :u", u=_bind(db, learner)) == 0
    # All four or none: half a measurement is refused.
    for present in unmeasured:
        partial = {**unmeasured, present: 0.5 if present != "ability_policy_version" else "p/1"}
        _refused(lambda partial=partial: _attempt(db, learner, set_id, ordinal=2, **partial))
    # The facts that make it evidence are never optional.
    for required in ("evaluator_version", "passage_level", "operation_id", "request_digest", "ordinal"):
        _refused(lambda required=required: _attempt(db, learner, set_id,
                                                    **{**unmeasured, "ordinal": 3, required: None}))


def test_an_operation_id_is_scoped_to_the_account_not_the_language(db):
    learner = _user(db)
    _, english = _approved_set(db)
    _, chinese = _approved_set(db, language="zh")
    _attempt(db, learner, english, operation_id="submit-7")
    _refused(lambda: _attempt(db, learner, chinese, language="zh", operation_id="submit-7"))
    _attempt(db, learner, chinese, language="zh", operation_id="submit-8")


def test_hashes_and_digests_are_hex_not_merely_lowercase(db):
    article = _article(db)
    learner = _user(db)
    _, set_id = _approved_set(db)
    for bad in ("g" * 64, "0" * 63 + " ", "a" * 65):
        _refused(lambda bad=bad: _insert(db, "reading_comprehension_sets", id=uuid.uuid4(), article_id=article,
                                       language_code="en", support_language="vi", article_body_sha256=bad,
                                       status="draft", generator_version="g", model="",
                                       validation_json={}, reviewed_by="", review_reason="",
                                       created_at=_now(), updated_at=_now()))
        _refused(lambda bad=bad: _attempt(db, learner, set_id, request_digest=bad))


def test_a_decision_names_its_reviewer_and_is_not_rewritten_afterwards(db):
    set_id = _set(db, _article(db))
    _question(db, set_id, approved=True)
    _update(db, "reading_comprehension_sets", set_id, status="needs_review")
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="approved",
                             reviewed_at=_now(), reviewed_by=""))
    _update(db, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(),
            reviewed_by="admin-a", review_reason="clear")
    for field, value in (("reviewed_by", "admin-b"), ("review_reason", "rewritten"),
                         ("reviewed_at", _now())):
        _refused(lambda field=field, value=value: _update(db, "reading_comprehension_sets", set_id,
                                                          **{field: value}))
    # A transition that is not a decision keeps the decision's reviewer.
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="stale",
                             reviewed_by="someone-else"))
    _refused(lambda: _update(db, "reading_comprehension_sets", set_id, status="archived",
                             review_reason="rewritten"))
    # A new decision is a transition into approved, and may name its own reviewer.
    _update(db, "reading_comprehension_sets", set_id, status="stale")
    _update(db, "reading_comprehension_sets", set_id, status="approved", reviewed_at=_now(),
            reviewed_by="admin-b", review_reason="body reverted")


def test_a_set_is_in_its_articles_language(db):
    english = _article(db)
    _refused(lambda: _set(db, english, language="zh"))
    chinese = _article(db, language="zh")
    _set(db, chinese, language="zh")


def test_no_write_replaces_protected_rows_on_either_dialect(db):
    """SQLite's REPLACE deletes the conflicting row without a DELETE trigger;
    PostgreSQL's ON CONFLICT DO UPDATE goes through the UPDATE guards. Either
    way a set attempt is not forged and an approved set is not reset."""
    learner = _user(db)
    article, set_id = _approved_set(db)
    original = _attempt_values(learner, set_id, ordinal=1)
    _insert(db, "reading_attempts", **original)
    forged = {**original, "correct_count": 0, "ability_after": 9.0,
              "answers": [{"question_id": "q", "selected_index": 1, "correct": False}]}
    _refused(lambda: _replace(db, "reading_attempts", ["id"], **forged))
    # A new id claiming the same checkpoint slot or the same operation.
    same_slot = _attempt_values(learner, set_id, ordinal=1)
    _refused(lambda: _replace(db, "reading_attempts", ["user_id", "language_code", "ordinal"], **same_slot))
    same_operation = _attempt_values(learner, set_id, ordinal=2, operation_id=original["operation_id"])
    _refused(lambda: _replace(db, "reading_attempts", ["user_id", "operation_id"], **same_operation))
    with db.connect() as connection:
        row = connection.execute(text("SELECT correct_count, ability_after FROM reading_attempts WHERE id = :i"),
                                 {"i": _bind(db, original["id"])}).one()
    assert (row.correct_count, row.ability_after) == (1, 0.25)
    # An approved set is not reset to a draft with a new anchor.
    reset = dict(id=set_id, article_id=article, language_code="en", support_language="vi",
                 article_body_sha256=_sha("forged"), status="draft", generator_version="g", model="",
                 validation_json={}, reviewed_by="", review_reason="", created_at=_now(), updated_at=_now())
    _refused(lambda: _replace(db, "reading_comprehension_sets", ["id"], **reset))
    assert _count(db, "reading_comprehension_questions", "set_id = :s", s=_bind(db, set_id)) == 1
    # Approving a rival set cannot displace the approved one.
    rival = _set(db, article)
    _question(db, rival, approved=True)
    _update(db, "reading_comprehension_sets", rival, status="needs_review")
    with db.begin() as connection:
        verb = "UPDATE OR REPLACE" if db.dialect.name == "sqlite" else "UPDATE"
        with pytest.raises(REFUSALS):
            connection.execute(text(
                f"{verb} reading_comprehension_sets SET status = 'approved', reviewed_at = :t,"
                " reviewed_by = 'admin' WHERE id = :i"), {"t": _now(), "i": _bind(db, rival)})
    assert _count(db, "reading_comprehension_sets", "id = :i AND status = 'approved'", i=_bind(db, set_id)) == 1


def test_truncate_cannot_take_reviewed_content_or_evidence(db):
    if db.dialect.name != "postgresql":
        pytest.skip("SQLite has no TRUNCATE")
    learner = _user(db)
    _, set_id = _approved_set(db)
    _attempt(db, learner, set_id)
    for statement in ("TRUNCATE reading_articles CASCADE", "TRUNCATE reading_comprehension_sets CASCADE",
                      "TRUNCATE reading_comprehension_questions", "TRUNCATE users CASCADE"):
        with pytest.raises(REFUSALS):
            with db.begin() as connection:
                connection.execute(text(statement))
    assert _count(db, "reading_attempts", "user_id = :u", u=learner) == 1


def test_a_downgrade_racing_a_writer_sees_the_write_instead_of_dropping_it(tmp_path):
    """R1: the downgrade locks before it looks. A draft set committed while the
    downgrade waits is seen by the guard - which refuses - not dropped."""
    if not URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
    import threading
    import time

    with _fresh("postgresql", tmp_path) as (engine, _upgrade, downgrade):
        article = _article(engine)
        writer = engine.connect()
        transaction = writer.begin()
        writer.execute(sa.insert(_table("reading_comprehension_sets", [
            "id", "article_id", "language_code", "support_language", "article_body_sha256", "status",
            "generator_version", "model", "validation_json", "reviewed_by", "review_reason",
            "created_at", "updated_at",
        ])).values(id=uuid.uuid4(), article_id=article, language_code="en", support_language="vi",
                   article_body_sha256=_sha(BODY), status="draft", generator_version="g", model="",
                   validation_json={}, reviewed_by="", review_reason="", created_at=_now(),
                   updated_at=_now()))
        outcome: dict = {}

        def run():
            try:
                downgrade()
                outcome["result"] = "dropped"
            except Exception as error:  # noqa: BLE001 - the refusal is the expected outcome
                outcome["result"] = error

        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(1.5)  # the downgrade is now waiting on the writer's lock
        transaction.commit()
        writer.close()
        thread.join(timeout=60)
        assert isinstance(outcome.get("result"), Exception), outcome
        assert "downgrade refused" in str(outcome["result"])
        assert _has_table(engine, "reading_comprehension_sets")
        assert _count(engine, "reading_comprehension_sets") == 1


def test_a_sqlite_downgrade_holds_the_write_lock_before_its_guard_looks(tmp_path):
    """RC1 (round 3): a SELECT opens no transaction under pysqlite's defaults,
    so without a write lock taken first a writer could commit between the
    guard and the DDL and be dropped unseen. Pause the downgrade right after
    its guard and try to write from another connection: it must be locked out."""
    import sqlite3

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    path = tmp_path / "race.db"
    engine = _sqlite_at_head(path)
    module = _proposal()
    original = module._guard_downgrade
    seen: dict = {}

    def guard_then_race():
        original()
        other = sqlite3.connect(path, timeout=0.1)
        try:
            other.execute("UPDATE reading_articles SET content_kind = 'news' WHERE 1 = 0")
            other.commit()
            seen["writer"] = "committed"
        except sqlite3.OperationalError as error:
            seen["writer"] = str(error)
        finally:
            other.close()

    module._guard_downgrade = guard_then_race
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.downgrade()
    finally:
        engine.dispose()
    assert "locked" in seen["writer"], seen
