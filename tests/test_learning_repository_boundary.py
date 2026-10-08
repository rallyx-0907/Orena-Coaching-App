from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_core_app_has_no_direct_learning_sql():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "import sqlite3" not in app
    assert "sqlite3.connect" not in app
    assert "conn.execute(" not in app
    assert "SQLiteLearningRepository" in app
    assert "PostgresLearningRepository" not in app


def test_learning_repository_contract_and_no_cutover():
    repo = (ROOT / "writing_coach/persistence/learning_repository.py").read_text(encoding="utf-8")
    for token in [
        "class LearningRepository(Protocol)",
        "class SQLiteLearningRepository",
        "class PostgresLearningRepository",
        "class SQLiteLearningCacheRepository",
    ]:
        assert token in repo
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "create_shadow_engine" not in app


def test_specialized_services_are_storage_neutral_on_v134():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    services = [
        "writing_coach/becoming_memory.py",
        "writing_coach/becoming_outcomes.py",
        "writing_coach/becoming_library.py",
        "writing_coach/becoming_linguistics.py",
    ]
    assert version == "1.4.0"
    for rel in services:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "_db_factory" not in src
        assert "def _db()" not in src
        assert "_repository" in src
        for forbidden in ["import sqlite3", "sqlite3.Connection", "CREATE TABLE", "ALTER TABLE", "PRAGMA"]:
            assert forbidden not in src

    repo = (ROOT / "writing_coach/persistence/specialized_repository.py").read_text(encoding="utf-8")
    assert "class SQLiteSpecializedLearningRepository" in repo
    assert "class PostgresSpecializedLearningRepository" in repo
    protocol, remainder = repo.split("class SQLiteSpecializedLearningRepository", 1)
    sqlite_repo, postgres_repo = remainder.split("class PostgresSpecializedLearningRepository", 1)
    assert "def initialize(self)" not in protocol
    assert "def initialize(self)" in sqlite_repo
    assert "def initialize(self)" not in postgres_repo
