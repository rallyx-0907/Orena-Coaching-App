"""R5 (the app's current grammar lessons) as raw material for conversion (human, 2026-09-28).

Grammar Lab restructures, corrects and completes R5 into schema v0.4 rather than discarding
it: a point whose ``source_refs.r5`` lists R5 lesson ids is generated *from* those lessons
(generate.py), its provenance records them (the redirect table for old links is built from
that), and verify has the other-family model confirm each correction the generator says it
made to R5 (verify.py), so the human learns where R5 itself was wrong.

This reads the app's grammar **data files** read-only -- the same kind of access as
export_error_tags.py; no app code is imported (SPEC principle 1). Review and checkpoint items
are practice sessions made of other lessons, not grammar points, and are left out.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.validate import LAB_ROOT

DEFAULT_R5_ROOT = LAB_ROOT.parent / "writing_coach" / "languages"
_LANG_DIRS = {"en": "english", "zh": "chinese"}
_CURRICULUM = "grammar_curriculum.json"
_KNOWLEDGE = "grammar_knowledge.json"

# What the model gets from each lesson: everything that carries grammar content. Scheduling,
# practice blueprints and authoring metadata are left out.
_CURRICULUM_FIELDS = ("level", "title", "objective_vi", "scope", "contrasts", "restrictions", "common_traps")
_LESSON_FIELDS = ("explanation_vi", "rules", "contrasts", "exceptions", "examples", "mistakes", "guided_practice")


class R5SourceError(RuntimeError):
    """The R5 files are missing or do not have the expected shape."""


def _read_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise R5SourceError(f"R5 file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = list(data.values())
    if not isinstance(data, list):
        raise R5SourceError(f"{path}: expected a list of lessons")
    return data


def load_r5(lang: str, root: Path = DEFAULT_R5_ROOT) -> dict[str, dict[str, Any]]:
    """R5 lessons of one language by id: curriculum row + knowledge record, lessons only."""
    lang_dir = root / _LANG_DIRS[lang]
    curriculum = _read_list(lang_dir / _CURRICULUM)
    knowledge = {item["id"]: item for item in _read_list(lang_dir / _KNOWLEDGE)}
    records: dict[str, dict[str, Any]] = {}
    for row in curriculum:
        if row.get("kind") != "lesson":
            continue
        known = knowledge.get(row["id"], {})
        lesson = known.get("lesson", {})
        records[row["id"]] = {
            "id": row["id"],
            **{key: row.get(key) for key in _CURRICULUM_FIELDS},
            "content_version": int(row.get("content_version") or known.get("content_version") or 1),
            "summary_vi": (known.get("quick_reference") or {}).get("summary_vi"),
            **{key: lesson.get(key) for key in _LESSON_FIELDS},
        }
    return records


def r5_source_text(records: list[dict[str, Any]]) -> str:
    """The R5 lesson(s) as compact JSON for the generation prompt (empty fields dropped)."""
    trimmed = [
        {key: value for key, value in record.items() if value not in (None, "", [], {}) and key != "content_version"}
        for record in records
    ]
    return json.dumps(trimmed, ensure_ascii=False, indent=1)
