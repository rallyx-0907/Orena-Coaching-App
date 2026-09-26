from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def req(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("Learning repository boundary validation FAILED: " + message)


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> None:
    req((ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.4.0", "app version must be v1.4.0")

    app = text("app.py")
    repo = text("writing_coach/persistence/learning_repository.py")

    req("import sqlite3" not in app, "app.py still imports sqlite3")
    req("sqlite3.connect" not in app, "app.py still opens SQLite directly")
    req("conn.execute(" not in app, "app.py still owns learning SQL")
    req("SQLiteLearningRepository" in app, "SQLite learning repository is not selected")
    req("PostgresLearningRepository" not in app, "PostgreSQL learning repository activated before cutover")
    req("create_shadow_engine" not in app, "app.py activated PostgreSQL before cutover")

    for token in [
        "class LearningRepository(Protocol)",
        "class SQLiteLearningRepository",
        "class PostgresLearningRepository",
        "class SQLiteLearningCacheRepository",
    ]:
        req(token in repo, f"learning repository contract missing: {token}")

    # Core API persistence paths must delegate through the selected repository.
    for token in [
        "_learning_repository.create_essay(",
        "_learning_repository.list_essays(",
        "_learning_repository.get_essay(",
        "_learning_repository.delete_series_for_essay(",
        "_learning_repository.completed_grammar_ids()",
        "_learning_repository.set_grammar_completed(",
        "_learning_repository.list_saved_words()",
        "_learning_repository.upsert_saved_word(",
        "_learning_cache.get_dictionary(",
        # get_grammar_lesson was removed by R5: grammar became a static KB with
        # no runtime AI generation, so there is no lesson left to cache. The
        # dictionary cache below is the remaining live delegation.
    ]:
        req(token in app, f"core learning path does not delegate: {token}")

    specialized = [
        "writing_coach/becoming_memory.py",
        "writing_coach/becoming_outcomes.py",
        "writing_coach/becoming_library.py",
        "writing_coach/becoming_linguistics.py",
    ]
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if version == "1.3.2":
        specialized_sql = [rel for rel in specialized if "conn.execute(" in text(rel)]
        req(specialized_sql == specialized, "v1.3.2 specialized SQLite adapter inventory changed unexpectedly")
    else:
        for rel in specialized:
            src = text(rel)
            req("_db_factory" not in src and "def _db()" not in src, f"v1.3.3 specialized service still owns DB factory: {rel}")
        repo = text("writing_coach/persistence/specialized_repository.py")
        req("class SQLiteSpecializedLearningRepository" in repo, "v1.3.3 SQLite specialized repository missing")
        req("class PostgresSpecializedLearningRepository" in repo, "v1.3.3 PostgreSQL specialized repository missing")
        if version == "1.3.4":
            for rel in ["writing_coach/becoming_memory.py", "writing_coach/becoming_library.py"]:
                src = text(rel)
                for forbidden in ["import sqlite3", "sqlite3.Connection", "CREATE TABLE", "ALTER TABLE", "PRAGMA"]:
                    req(forbidden not in src, f"v1.3.4 service schema coupling remains: {rel}: {forbidden}")

    # sqlite3.connect is allowed only in explicit repository/migration/verification
    # adapters. Core app and service orchestration may not open DBs directly.
    actual_connectors: set[str] = set()
    for path in [ROOT / "app.py", *sorted((ROOT / "writing_coach").rglob("*.py"))]:
        if path.name.endswith("_selftest.py") or path.name == "selftest.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "sqlite3" and node.func.attr == "connect":
                actual_connectors.add(path.relative_to(ROOT).as_posix())
    allowed = {
        "writing_coach/product/repository.py",
        "writing_coach/persistence/auth_repository.py",
        "writing_coach/persistence/platform_repository.py",
        "writing_coach/persistence/learning_repository.py",
        "writing_coach/persistence/importer.py",
        "writing_coach/persistence/read_compare.py",
        "writing_coach/persistence/cutover_verification.py",
    }
    req(actual_connectors <= allowed, f"unexpected SQLite connector bypasses: {sorted(actual_connectors - allowed)}")

    for rel in [
        "writing_coach/persistence/learning_repository.py",
        "writing_coach/persistence/learning_repository_selftest.py",
        "docs/LEARNING_REPOSITORY_BOUNDARY.md",
    ]:
        req((ROOT / rel).is_file(), f"missing learning-boundary artifact: {rel}")

    print("BECOMING learning core repository boundary validation OK")
    print("Core app direct SQLite SQL: REMOVED")
    print("Learning runtime selection: SQLiteLearningRepository")
    print("PostgreSQL core implementation: PRESENT / NOT SELECTED")
    print("Specialized BECOMING persistence: CRUD + schema repository-bound on v1.3.4")
    print("Runtime cutover: NOT ENABLED")


if __name__ == "__main__":
    main()
