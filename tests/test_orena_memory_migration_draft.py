"""The Orena Memory M2 migration is a draft proposal (ORENA_MEMORY.md §9; D-222): reviewable, rehearsable
(`scripts/rehearse_orena_memory_schema.py`), and nowhere a runtime can apply it."""

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


def test_the_draft_is_proposed_only():
    assert (ROOT / "migrations" / "proposed" / NAME).exists()
    assert not (ROOT / "migrations" / "versions" / NAME).exists()
    assert not list((ROOT / "migrations" / "versions").glob("*orena_memory*"))


def test_the_draft_names_its_revision_and_parent():
    tree = ast.parse((ROOT / "migrations" / "proposed" / NAME).read_text(encoding="utf-8"))
    values = _assigned(tree)
    assert values["revision"] == "20261018_0035" and values["down_revision"] == "20261015_0033"
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"upgrade", "downgrade"} <= functions


def test_no_orm_model_or_code_reads_the_tables_yet():
    from writing_coach.persistence import models

    assert not TABLES & set(models.Base.metadata.tables)
