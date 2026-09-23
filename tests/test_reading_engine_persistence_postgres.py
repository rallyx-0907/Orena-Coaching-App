"""The Reading engine's constraints, proved on real PostgreSQL.

`READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md` §11.4 promised this file,
and the reason it exists is worth restating where it runs: **CI exercises none
of these.** The hermetic suite runs on SQLite, where the CHECK constraints are
never created, the trigger cannot exist at all, and a `postgresql_where`
partial index silently becomes a full one. Every "the database enforces it"
claim in that proposal is therefore only as true as this file.

So each constraint is proved the only way a constraint can be: by writing the
row it must refuse and watching it refuse. The partial indexes are proved by
reading `pg_indexes.indexdef` back, because an index that lost its predicate
still exists, still has the right name, and enforces something different.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/orena_engine_test \\
        python -m pytest tests/test_reading_engine_persistence_postgres.py
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(
    not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run"
)

MANUAL = uuid.UUID("0a52e5d0-0000-4000-8000-000000000001")
FILE_SOURCE = uuid.UUID("0a52e5d0-0000-4000-8000-000000000003")
REFUSALS = (IntegrityError, DBAPIError)


@pytest.fixture(scope="module")
def engine():
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _require_schema(engine):
    with engine.connect() as connection:
        present = connection.execute(
            text("SELECT to_regclass('reading_articles') IS NOT NULL")
        ).scalar_one()
    if not present:
        pytest.skip(
            "the Reading engine tables are not in the applied chain yet - "
            "20260923_0013_reading_content_engine.py has not been moved into "
            "migrations/versions/."
        )


def _hash(seed: str) -> str:
    """A 64-character lowercase hex value, which is what the CHECK demands."""
    return f"{abs(hash(seed)):064x}"[:64].replace("-", "0")


def _item(engine, *, source=MANUAL, native="", body="A text.", digest=None, revision=1,
          supersedes=None, url="") -> uuid.UUID:
    item_id = uuid.uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reading_source_items (id, source_id, source_native_id, canonical_url,"
                " original_title, original_author, original_language, original_content, content_hash,"
                " metadata_json, rights_snapshot_json, revision, supersedes_id, fetched_at, created_at)"
                " VALUES (:id, :source, :native, :url, 'A title', '', 'en', :body, :hash,"
                " '{}', '{}', :revision, :supersedes, :now, :now)"
            ),
            {"id": item_id, "source": source, "native": native, "url": url, "body": body,
             "hash": digest or _hash(body), "revision": revision, "supersedes": supersedes,
             "now": now},
        )
    return item_id


def _article(engine, item_id, *, status="needs_review", published=None, estimated="B1",
             reviewed=None, effective="B1") -> uuid.UUID:
    article_id = uuid.uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reading_articles (id, source_item_id, title, body, excerpt, language,"
                " topic, subtopic, estimated_level, estimated_level_confidence, reviewed_level,"
                " effective_level, word_count, reading_time_seconds, is_adapted, adaptation_json,"
                " analysis_json, status, rejection_reason, content_revision, created_at, updated_at,"
                " published_at) VALUES (:id, :item, 'A title', 'A body', '', 'en', '', '',"
                " :estimated, 0.5, :reviewed, :effective, 10, 30, false, '{}', '{}', :status, '', 1,"
                " :now, :now, :published)"
            ),
            {"id": article_id, "item": item_id, "estimated": estimated, "reviewed": reviewed,
             "effective": effective, "status": status, "now": now, "published": published},
        )
    return article_id


def _job(engine, *, request_hash, status="queued", attempt=0, max_attempts=3) -> uuid.UUID:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reading_ingestion_jobs (id, job_type, source_id, input_json,"
                " request_hash, status, stage, attempt, max_attempts, next_retry_at, heartbeat_at,"
                " created_at) VALUES (:id, 'ingest_text', :source, '{}', :hash, :status, 'queued',"
                " :attempt, :max_attempts, :now, :now, :now)"
            ),
            {"id": job_id, "source": MANUAL, "hash": request_hash, "status": status,
             "attempt": attempt, "max_attempts": max_attempts, "now": now},
        )
    return job_id


# ---- the seeded sources ------------------------------------------------------

def test_the_three_built_in_sources_are_there_with_the_ids_the_code_expects(engine):
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, slug, state, automation_allowed, polling_enabled FROM reading_sources"
                 " WHERE created_by LIKE 'migration%' ORDER BY slug")
        ).all()
    assert [str(row.id) for row in rows] == [
        "0a52e5d0-0000-4000-8000-000000000002",
        "0a52e5d0-0000-4000-8000-000000000003",
        "0a52e5d0-0000-4000-8000-000000000001",
    ]
    assert all(row.state == "active" for row in rows)
    assert all(not row.automation_allowed and not row.polling_enabled for row in rows)


# ---- CHECK constraints -------------------------------------------------------

def test_polling_cannot_be_turned_on_without_approval_and_rights(engine):
    with pytest.raises(REFUSALS) as refusal, engine.begin() as connection:
        connection.execute(
            text("UPDATE reading_sources SET polling_enabled = true WHERE id = :id"), {"id": MANUAL}
        )
    assert "ck_reading_source_polling_requires_approval" in str(refusal.value)


def test_a_published_article_must_carry_the_time_the_learner_list_orders_by(engine):
    item = _item(engine, body="published without a timestamp")
    with pytest.raises(REFUSALS) as refusal:
        _article(engine, item, status="published", published=None)
    assert "ck_reading_article_published_at" in str(refusal.value)


def test_the_effective_level_cannot_drift_from_the_two_it_is_derived_from(engine):
    item = _item(engine, body="drifting level")
    with pytest.raises(REFUSALS) as refusal:
        _article(engine, item, estimated="B1", reviewed=None, effective="C2")
    assert "ck_reading_article_effective_level" in str(refusal.value)


def test_an_unset_reviewed_level_is_null_and_never_the_empty_string(engine):
    # `effective` matches `COALESCE(reviewed, estimated)` here on purpose, so
    # the row is refused by the constraint under test rather than by the
    # effective-level one firing first.
    item = _item(engine, body="empty reviewed level")
    with pytest.raises(REFUSALS) as refusal:
        _article(engine, item, reviewed="", effective="")
    assert "ck_reading_article_reviewed_level" in str(refusal.value)


def test_a_target_cannot_be_approved_and_rejected_at_once(engine):
    article = _article(engine, _item(engine, body="target decision"))
    now = datetime.now(UTC)
    with pytest.raises(REFUSALS) as refusal, engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reading_article_targets (id, article_id, text, canonical_form,"
                " target_type, rank, machine_suggested, admin_approved, admin_rejected, created_at,"
                " updated_at) VALUES (:id, :article, 'both', 'both', 'word', 0, true, true, true,"
                " :now, :now)"
            ),
            {"id": uuid.uuid4(), "article": article, "now": now},
        )
    assert "ck_reading_target_decision" in str(refusal.value)


def test_a_job_cannot_be_claimed_more_times_than_it_is_allowed(engine):
    with pytest.raises(REFUSALS) as refusal:
        _job(engine, request_hash=_hash("over-attempted"), attempt=4, max_attempts=3)
    assert "ck_reading_job_attempt_bound" in str(refusal.value)


def test_a_content_hash_must_be_lowercase_hex_of_the_right_length(engine):
    with pytest.raises(REFUSALS) as refusal:
        _item(engine, body="uppercase hash", digest="A" * 64)
    assert "ck_reading_source_item_hash" in str(refusal.value)
    with pytest.raises(REFUSALS) as short:
        _item(engine, body="short hash", digest="abc")
    assert "ck_reading_source_item_hash" in str(short.value)


def test_a_later_revision_must_say_what_it_was_created_after(engine):
    with pytest.raises(REFUSALS) as refusal:
        _item(engine, body="orphan revision", revision=3, supersedes=None)
    assert "ck_reading_source_item_chain" in str(refusal.value)


# ---- uniqueness --------------------------------------------------------------

def test_the_same_bytes_from_one_source_are_one_snapshot(engine):
    digest = _hash("identical bytes")
    _item(engine, body="identical bytes", digest=digest)
    with pytest.raises(REFUSALS) as refusal:
        _item(engine, body="identical bytes again", digest=digest)
    assert "uq_reading_source_items_hash" in str(refusal.value)


def test_one_current_snapshot_per_native_id_and_a_superseded_one_does_not_count(engine):
    native = f"native-{uuid.uuid4()}"
    first = _item(engine, native=native, body=f"first {native}")
    with pytest.raises(REFUSALS) as refusal:
        _item(engine, native=native, body=f"second {native}", revision=2, supersedes=first)
    assert "uq_reading_source_items_native" in str(refusal.value)

    # Stamp the first superseded, and the second becomes possible - which is
    # the whole point of the index being partial.
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE reading_source_items SET superseded_at = :now WHERE id = :id"),
            {"id": first, "now": datetime.now(UTC)},
        )
    _item(engine, native=native, body=f"second {native}", revision=2, supersedes=first)


def test_one_article_per_snapshot(engine):
    item = _item(engine, body="one article only")
    _article(engine, item)
    with pytest.raises(REFUSALS) as refusal:
        _article(engine, item)
    assert "uq_reading_article_source_item" in str(refusal.value)


def test_two_live_jobs_cannot_share_a_request_hash_but_a_finished_one_frees_it(engine):
    digest = _hash(f"request-{uuid.uuid4()}")
    live = _job(engine, request_hash=digest)
    with pytest.raises(REFUSALS) as refusal:
        _job(engine, request_hash=digest)
    assert "uq_reading_job_request_hash" in str(refusal.value)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE reading_ingestion_jobs SET status = 'failed' WHERE id = :id"), {"id": live}
        )
    _job(engine, request_hash=digest)


# ---- the immutability trigger ------------------------------------------------

@pytest.mark.parametrize(
    "column, value",
    [
        ("original_content", "'rewritten'"),
        ("content_hash", "'" + "b" * 64 + "'"),
        ("rights_snapshot_json", "'{\"can_republish\": true}'"),
        ("source_native_id", "'moved'"),
        ("canonical_url", "'https://example.com/moved'"),
        ("source_id", f"'{FILE_SOURCE}'"),
        ("revision", "9"),
    ],
)
def test_the_snapshot_refuses_every_rewrite_of_what_it_is_evidence_for(engine, column, value):
    item = _item(engine, body=f"immutable {column}")
    with pytest.raises(REFUSALS) as refusal, engine.begin() as connection:
        connection.execute(
            text(f"UPDATE reading_source_items SET {column} = {value} WHERE id = :id"), {"id": item}
        )
    assert "immutable snapshot" in str(refusal.value)


def test_the_snapshot_permits_the_one_update_the_engine_needs(engine):
    item = _item(engine, body="supersede me")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE reading_source_items SET superseded_at = :now WHERE id = :id"),
            {"id": item, "now": datetime.now(UTC)},
        )
        connection.execute(
            text("UPDATE reading_source_items SET original_title = 'Corrected' WHERE id = :id"),
            {"id": item},
        )
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT original_title, superseded_at FROM reading_source_items WHERE id = :id"),
            {"id": item},
        ).one()
    assert row.original_title == "Corrected" and row.superseded_at is not None


# ---- the partial indexes actually carry their predicates ---------------------

PARTIAL = {
    "uq_reading_source_items_native": "source_native_id <> '' AND superseded_at IS NULL",
    "ix_reading_source_items_canonical": "canonical_url <> ''",
    "ix_reading_articles_published": "status = 'published'",
    "ix_reading_articles_published_level": "status = 'published'",
    "ix_reading_articles_published_topic": "status = 'published'",
    "uq_reading_target_form": "canonical_form <> ''",
    "uq_reading_job_request_hash": "status = ANY",
    "ix_reading_jobs_claim": "status = 'queued'",
    "ix_reading_jobs_stale": "status = 'running'",
}


def _readable(definition: str) -> str:
    """PostgreSQL's own rendering, with its casts and parentheses removed.

    `pg_indexes` reports `((status)::text = 'published'::text)`, which says the
    same thing as `status = 'published'` and matches no literal a human would
    write. Normalizing here keeps the assertion about the predicate rather
    than about how the server spells it.
    """
    import re

    text_form = definition.split(" WHERE ", 1)[-1]
    text_form = re.sub(r"::(?:character varying|text|\w+)(?:\[\])?", "", text_form)
    text_form = text_form.replace("(", " ").replace(")", " ")
    return " ".join(text_form.split())


@pytest.mark.parametrize("index_name, predicate", sorted(PARTIAL.items()))
def test_each_partial_index_kept_its_predicate_on_the_applied_schema(engine, index_name, predicate):
    """An index that lost its `WHERE` still exists, still has the right name,
    and enforces something else entirely - which is exactly what would happen
    if this DDL were ever created from `models.py` on a backend that ignores
    the dialect keyword. Reading the definition back is the only way to know."""
    with engine.connect() as connection:
        definition = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"), {"name": index_name}
        ).scalar_one()
    assert " WHERE " in definition, definition
    assert predicate in _readable(definition), definition


def test_the_claim_index_is_ordered_the_way_the_claim_walks(engine):
    with engine.connect() as connection:
        definition = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_reading_jobs_claim'")
        ).scalar_one()
    assert "(created_at, id)" in definition.replace("USING btree ", "").replace("btree ", "")


def test_the_published_indexes_end_in_the_keyset_tiebreak(engine):
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes"
                " WHERE indexname LIKE 'ix_reading_articles_published%'"
            )
        ).all()
    assert len(rows) == 3
    for row in rows:
        columns = row.indexdef.split("(", 1)[1].split(")", 1)[0]
        assert columns.strip().endswith("id"), row.indexdef
