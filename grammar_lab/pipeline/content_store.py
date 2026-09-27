"""Shared read/write of ``content/<lang>/`` used by generate, verify and route.

``validate.py`` keeps its own private loader (it must also accept and report
on malformed input). This module is for steps that only ever operate on
points that already exist as well-formed JSON on disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from grammar_lab.pipeline.jsonio import read_json, read_yaml, write_json
from grammar_lab.pipeline.validate import FUNCTIONS_PATH, LANGS, MANIFEST_NAME, LAB_ROOT

__all__ = [
    "LAB_ROOT",
    "content_dir",
    "point_path",
    "load_manifest",
    "load_functions",
    "load_points",
    "load_point",
    "save_point",
    "next_draft_version",
]


def content_dir(lang: str, root: Path = LAB_ROOT) -> Path:
    return root / "content" / lang


def point_path(lang: str, point_id: str, root: Path = LAB_ROOT) -> Path:
    return content_dir(lang, root) / f"{point_id}.json"


def load_manifest(lang: str, root: Path = LAB_ROOT) -> dict[str, Any]:
    return read_json(content_dir(lang, root) / MANIFEST_NAME)


def load_functions(root: Path = LAB_ROOT) -> dict[str, Any]:
    return read_yaml(root / FUNCTIONS_PATH)


def load_points(lang: str, root: Path = LAB_ROOT) -> dict[str, dict[str, Any]]:
    """Every well-formed point file for ``lang``, keyed by id. Skips files that
    are not valid JSON objects rather than raising: callers that need strict
    validation should run ``validate`` first."""
    directory = content_dir(lang, root)
    points: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return points
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = read_json(path)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("id"), str):
            points[data["id"]] = data
    return points


def load_point(lang: str, point_id: str, root: Path = LAB_ROOT) -> dict[str, Any] | None:
    path = point_path(lang, point_id, root)
    if not path.exists():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


def save_point(lang: str, point: dict[str, Any], root: Path = LAB_ROOT) -> Path:
    path = point_path(lang, point["id"], root)
    write_json(path, point)
    return path


def next_draft_version(existing: dict[str, Any] | None) -> int:
    """SPEC §5.1: generate never overwrites an approved point silently.

    Callers decide *whether* to regenerate (skip when ``existing`` is
    approved unless the caller explicitly asked for a regenerate); this only
    computes the version number once that decision is made.
    """
    if existing is None:
        return 1
    return int(existing.get("version", 1)) + 1


def lang_dir_code(target_lang: str) -> str:
    """BCP-47 target_lang -> short content-dir/id-prefix code (inverse of LANGS)."""
    for short, full in LANGS.items():
        if full == target_lang:
            return short
    raise ValueError(f"unknown target_lang {target_lang!r}")
