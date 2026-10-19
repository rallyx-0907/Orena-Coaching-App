"""The promoted 0036 on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, a throwaway database only: this test downgrades it).

CI does not set the URL, so this is run by hand like the other `*_postgres.py` proofs. The session fixture upgrades to
head (0036); the test steps the database back to 0035, which carries no consent columns, for the dormancy proof on the
real repository, then upgrades to 0036 with Alembic itself and proves recording, the voice answer, the reset and the
exact downgrade, and leaves the database at head.
"""
from __future__ import annotations

import uuid

import pytest

from tests.d4_support import PG_URL, pg_engine  # noqa: F401 - the session fixture

pytestmark = pytest.mark.skipif(not PG_URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

COLUMNS = ("consent_version", "consent_accepted_at", "consent_language", "voice_consent", "voice_consent_at")


def _migrate(engine, direction):
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    if direction == "upgrade":
        command.upgrade(cfg, "20261019_0036")
    else:
        command.downgrade(cfg, "20261018_0035")


def _present(engine):
    from sqlalchemy import inspect

    return set(COLUMNS) <= {c["name"] for c in inspect(engine).get_columns("users")}


def test_the_code_is_dormant_before_the_migration_and_records_after_it_and_the_downgrade_is_exact(pg_engine):  # noqa: F811
    from writing_coach import consent
    from writing_coach.persistence.auth_repository import PostgresAuthRepository

    _migrate(pg_engine, "downgrade")
    assert not _present(pg_engine), "at 0035 the consent columns do not exist"
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
        downgraded = not _present(pg_engine)
        _migrate(pg_engine, "upgrade")  # leave the shared throwaway database at head
    assert downgraded and _present(pg_engine)
