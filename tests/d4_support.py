"""Shared fixtures for the D4 tests: the REAL repositories on both backends.

`backend` is parametrised over the hermetic SQLite repositories and, when `ORENA_TEST_POSTGRES_URL`
names a throwaway database at the migration head, the PostgreSQL ones. Nothing here fakes a store;
only network providers may be faked by the tests that use it.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

import pytest

from writing_coach import account_settings, becoming_memory
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.persistence.auth_repository import PostgresAuthRepository, SQLiteAuthRepository
from writing_coach.persistence.learning_repository import PostgresLearningRepository, SQLiteLearningRepository
from writing_coach.persistence.specialized_repository import (
    PostgresSpecializedLearningRepository,
    SQLiteSpecializedLearningRepository,
)

PG_URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")


@dataclass
class Backend:
    name: str
    auth: Any
    _profile_for: Callable[[str, str], Any]
    engine: Any = None
    _learning_for: Callable[[str, str], Any] | None = None

    def profile_repo(self, user: str, language: str):
        return self._profile_for(user, language)

    def use(self, user: str, language: str):
        """Act as this account in this learning language, the way a request would."""
        USER_KEY_CTX.set(user)
        LANGUAGE_CODE_CTX.set(language)
        repository = self.profile_repo(user, language)
        becoming_memory.configure_becoming_memory(repository)
        account_settings.configure_account_settings(self.auth)
        return repository

    def learning_repo(self, user: str, language: str):
        """The core learning repository (essays, grammar) over the same store as `profile_repo`."""
        return self._learning_for(user, language)

    def new_user(self) -> str:
        key = f"sub-{uuid.uuid4().hex[:12]}"
        self.auth.upsert_user({"sub": key, "email": f"{key}@example.test", "name": key}, set())
        return key


@pytest.fixture(scope="session")
def pg_engine():
    if not PG_URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
    from alembic import command
    from sqlalchemy import create_engine

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", PG_URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = create_engine(PG_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(params=["sqlite", "postgres"])
def backend(request, tmp_path):
    if request.param == "sqlite":
        auth = SQLiteAuthRepository(tmp_path / "auth.db")
        auth.initialize(set())
        repos: dict[tuple[str, str], SQLiteSpecializedLearningRepository] = {}
        learnings: dict[tuple[str, str], SQLiteLearningRepository] = {}

        def profile_for(user: str, language: str):
            key = (user, language)
            if key not in repos:
                database = tmp_path / f"{user}-{language}.db"

                def connect(path=database):
                    connection = sqlite3.connect(path)
                    connection.row_factory = sqlite3.Row
                    return connection

                learning = SQLiteLearningRepository(lambda path=database: path)
                learning.initialize()
                repo = SQLiteSpecializedLearningRepository(connect)
                repo.initialize()
                repos[key] = repo
                learnings[key] = learning
            return repos[key]

        def learning_for(user: str, language: str):
            profile_for(user, language)
            return learnings[(user, language)]

        yield Backend("sqlite", auth, profile_for, None, learning_for)
        return

    engine = request.getfixturevalue("pg_engine")
    auth = PostgresAuthRepository(engine)
    specialized = PostgresSpecializedLearningRepository(engine)
    learning = PostgresLearningRepository(engine)
    yield Backend("postgres", auth, lambda user, language: specialized, engine, lambda user, language: learning)
