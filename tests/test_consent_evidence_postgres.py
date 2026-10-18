"""The proposed 0036 on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, a throwaway database at the migration head only).

CI does not set the URL, so this is run by hand like the other `*_postgres.py` proofs: the head carries no consent columns,
so the first half is the dormancy proof on the real repository; the second applies the proposed revision with Alembic's
operations (as `test_credit_ledger_postgres` applies its proposals) and proves recording, the voice answer, the reset and
the exact downgrade.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest

from tests.d4_support import PG_URL, pg_engine  # noqa: F401 - the session fixture

pytestmark = pytest.mark.skipif(not PG_URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

PROPOSED = Path(__file__).resolve().parents[1] / "migrations" / "proposed" / "20261019_0036_consent_evidence.py"
COLUMNS = ("consent_version", "consent_accepted_at", "consent_language", "voice_consent", "voice_consent_at")


def _migrate(engine, direction):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    spec = importlib.util.spec_from_file_location("consent_0036", PROPOSED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        getattr(module, direction)()


def _present(engine):
    from sqlalchemy import inspect

    return set(COLUMNS) <= {c["name"] for c in inspect(engine).get_columns("users")}


def test_the_code_is_dormant_before_the_migration_and_records_after_it_and_the_downgrade_is_exact(pg_engine):  # noqa: F811
    from writing_coach import consent
    from writing_coach.persistence.auth_repository import PostgresAuthRepository

    assert not _present(pg_engine), "run on a database at the head: the proposal is not applied"
    repo = PostgresAuthRepository(pg_engine)
    sub = f"sub-{uuid.uuid4().hex[:12]}"
    assert repo.upsert_user({"sub": sub, "email": f"{sub}@example.test", "name": sub}, set())["created_now"] is True
    assert consent.public_shape(repo, sub)["stored"] is False
    assert consent.record_sign_up_consent(repo, sub, "vi") is False
    assert consent.set_voice_consent(repo, sub, True) is False

    _migrate(pg_engine, "upgrade")
    try:
        repo = PostgresAuthRepository(pg_engine)  # a fresh presence cache
        assert consent.consent_required(repo, sub) is True, "an account that existed before has no record"
        assert consent.record_sign_up_consent(repo, sub, "zh-CN") is True
        state = consent.consent_state(repo, sub)
        assert state["language"] == "zh" and state["accepted_at"] and state["voice"] is False
        assert consent.set_voice_consent(repo, sub, True) is True
        assert consent.voice_consent_blocks(repo, sub, auth_enabled=True) is False
        assert consent.reset_consent(repo, sub) is True
        after = consent.consent_state(repo, sub)
        assert after["accepted"] is False and after["voice"] is False
    finally:
        _migrate(pg_engine, "downgrade")
    assert not _present(pg_engine)
