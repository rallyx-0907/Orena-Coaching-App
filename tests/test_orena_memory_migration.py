"""The Orena Memory M2 migration is promoted (ORENA_MEMORY.md §9; D-222; owner authorisation 2026-10-18): it is the
single head of `migrations/versions/`, rehearsable (`scripts/rehearse_orena_memory_schema.py`), and its tables are
not in the ORM, like every incarnation-keyed table of 0005 (raw SQL repository, PostgreSQL only)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "20261018_0035_orena_memory.py"
TABLES = {"learner_memories", "learner_memory_suppressions", "learner_memory_state"}


def _assigned(tree: ast.Module) -> dict[str, object]:
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return out


def test_the_migration_is_in_versions_and_not_proposed():
    assert (ROOT / "migrations" / "versions" / NAME).exists()
    assert not (ROOT / "migrations" / "proposed" / NAME).exists()


def test_the_chain_has_one_head_and_it_is_0035():
    revisions: dict[str, object] = {}
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        values = _assigned(ast.parse(path.read_text(encoding="utf-8")))
        if "revision" in values:
            revisions[str(values["revision"])] = values.get("down_revision")
    parents = {str(p) for p in revisions.values() if isinstance(p, str)}
    parents |= {str(p) for value in revisions.values() if isinstance(value, tuple) for p in value}
    assert set(revisions) - parents == {"20261018_0035"}


def test_the_migration_has_upgrade_and_downgrade():
    tree = ast.parse((ROOT / "migrations" / "versions" / NAME).read_text(encoding="utf-8"))
    assert _assigned(tree)["revision"] == "20261018_0035"
    assert {"upgrade", "downgrade"} <= {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_no_orm_model_maps_the_memory_tables():
    from writing_coach.persistence import models

    assert not TABLES & set(models.Base.metadata.tables)
