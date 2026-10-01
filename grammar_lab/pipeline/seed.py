"""Catalogue seeds -> a point's structural metadata (human, 2026-09-29, items 2-3).

``inventory/seeds_<lang>.yaml`` is the catalogue of what to write: for every point its id, level,
function, point_type, names, the R5 lesson(s) it converts, contrasts (both ways), prerequisites, engine
error tags and the reference-framework anchors. ``generate`` starts from it: a point that is not on disk
yet is created from its seed, and a point that is keeps its content but takes the seed's metadata, so the
catalogue -- not whatever an earlier draft said -- decides structure. Only content is generated.
"""

from __future__ import annotations

import re
import time
import threading
from pathlib import Path
from typing import Any

import yaml

from grammar_lab.pipeline.canonical import canonical_dir, catalog_is_current, catalog_path
from grammar_lab.pipeline.jsonio import read_json, read_yaml
from grammar_lab.pipeline.validate import FUNCTIONS_PATH, GRAMMAR_SCHEMA_PATH, LAB_ROOT, LANGS

SEED_KEYS = ("function", "point_type", "prereqs", "contrasts", "error_tags", "sequence")
_FUNCTIONS_WRITE_LOCK = threading.Lock()


def seeds_path(lang: str, root: Path = LAB_ROOT) -> Path:
    return root / "inventory" / f"seeds_{lang}.yaml"


def load_seeds(lang: str, root: Path = LAB_ROOT) -> list[dict[str, Any]]:
    path = seeds_path(lang, root)
    return read_yaml(path) or [] if path.exists() else []


def load_catalog(lang: str, root: Path = LAB_ROOT) -> list[dict[str, Any]]:
    """The runtime catalogue: ``inventory/catalog_<lang>.yaml`` (generated from canonical v1 by
    ``import-canonical``) when it exists, else the hand seeds alone. ``generate`` and ``coverage`` read
    this; ``check_seeds`` and the reviewed-seed tests keep reading ``load_seeds``."""
    path = catalog_path(lang, root)
    return read_yaml(path) or [] if path.exists() else load_seeds(lang, root)


class GenerationBlocked(RuntimeError):
    """Raised before any provider call when the catalogue cannot be trusted for generation."""


def check_generation_gate(
    lang: str, point_ids: list[str], root: Path = LAB_ROOT, *, allow_default_safe: bool = False
) -> None:
    """Fail closed before a provider is touched.

    1. When the lab has a canonical v1 catalogue, the generated runtime catalogue must be current with it
       (a missing or stale ``catalog_<lang>.yaml`` blocks; run ``import-canonical``).
    2. A point whose metadata is ``default_safe`` (never human-reviewed) is not generated unless the caller
       passes the explicit override: its function, point_type, error_tags, contrasts and prereqs are
       placeholders, and generating on them would bake those placeholders into content.
    """
    if (canonical_dir(root) / f"{lang}.yaml").exists() and not catalog_is_current(lang, root):
        raise GenerationBlocked(
            f"inventory/catalog_{lang}.yaml is missing or stale against canonical_v1; run "
            f"`python -m grammar_lab.pipeline.cli import-canonical --lang {lang}` first"
        )
    if allow_default_safe:
        return
    by_id = {record["id"]: record for record in load_catalog(lang, root)}
    unreviewed = [pid for pid in point_ids if by_id.get(pid, {}).get("catalog", {}).get("metadata_origin") == "default_safe"]
    if unreviewed:
        shown = ", ".join(unreviewed[:5]) + (f" (+{len(unreviewed) - 5} more)" if len(unreviewed) > 5 else "")
        raise GenerationBlocked(
            f"{len(unreviewed)} point(s) have default_safe metadata, not reviewed: {shown}. Review their metadata "
            "into seeds_<lang>.yaml, or pass --allow-default-safe-metadata to generate on placeholders knowingly"
        )


def select_ids(lang: str, level: str, root: Path = LAB_ROOT) -> list[str]:
    """Ids of every catalogue point at ``level`` (``A1``, ``HSK2``, ``2``), in catalogue order."""
    wanted = level.removeprefix("HSK") if lang == "zh" else level
    return [seed["id"] for seed in load_catalog(lang, root) if str(seed["level"]) == wanted]


def seed_for(lang: str, point_id: str, root: Path = LAB_ROOT) -> dict[str, Any] | None:
    return next((seed for seed in load_seeds(lang, root) if seed["id"] == point_id), None)


def _level(lang: str, value: str, root: Path) -> dict[str, Any]:
    scale = read_json(root / GRAMMAR_SCHEMA_PATH)["level_scales"][LANGS[lang]]
    return {"framework": scale["framework"], "value": value, "rank": scale["values"].index(value) + 1}


def aliases_for(seeds: list[dict[str, Any]]) -> dict[str, list[str]]:
    """R5 id -> the one point that owns it as an alias. A merge lists every source R5 lesson on the
    surviving point; a split gives the R5 id to the first piece only (an R5 id may be an alias of one
    point), the other pieces keep it in source_refs.r5."""
    owner: dict[str, str] = {}
    out: dict[str, list[str]] = {seed["id"]: [] for seed in seeds}
    for seed in seeds:
        for r5_id in seed.get("r5", []):
            if r5_id not in owner:
                owner[r5_id] = seed["id"]
                out[seed["id"]].append(r5_id)
    return out


def _anchors(seed: dict[str, Any]) -> dict[str, Any]:
    items = [{"source": a["source"], "code": str(a["code"]), "level": a["level"]} for a in seed.get("anchors", [])]
    return {"status": "anchored" if items else "unanchored", "items": items}


def apply_seed(existing: dict[str, Any] | None, lang: str, point_id: str, root: Path = LAB_ROOT) -> dict[str, Any] | None:
    """The point as the seed says it should be, keeping ``existing`` content; ``None`` when there is
    neither an existing point nor a seed."""
    seeds = load_catalog(lang, root)
    seed = next((s for s in seeds if s["id"] == point_id), None)
    if seed is None:
        return existing
    # a canonical catalogue record names its aliases; bare seeds derive them (first piece of a split)
    aliases = seed["aliases"] if "aliases" in seed else aliases_for(seeds)[point_id]
    point: dict[str, Any] = dict(existing) if existing else {
        "schema_version": "0.4", "id": point_id, "version": 1, "target_lang": LANGS[lang], "status": "draft_ai",
        "flags": [],
        "provenance": {
            "model": "seed", "prompt_version": "seed.v1", "run_id": "seed", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "review": None,
    }
    point["schema_version"] = "0.4"
    point["level"] = _level(lang, str(seed["level"]), root)
    for key in SEED_KEYS:
        point[key] = seed[key]
    point["aliases"] = aliases
    point["source_refs"] = {key: list(seed[key]) for key in ("r5", "gf0025") if seed.get(key)}
    point["source_anchors"] = _anchors(seed)
    header = dict(point.get("header") or {})
    header.update(
        title=dict(seed["title"]), native_title=seed["native_title"], level=dict(point["level"]),
    )
    header.setdefault("summary", dict(seed["title"]))
    point["header"] = header
    return point


def register_realization(point: dict[str, Any], root: Path = LAB_ROOT) -> bool:
    """Move a generated point into its function realization list safely.

    Parallel corpus generation can finish several points at once. The registry
    is one shared YAML file, so serialize the full read/modify/write transaction
    to prevent one worker from overwriting another worker's update.
    """
    with _FUNCTIONS_WRITE_LOCK:
        path = root / FUNCTIONS_PATH
        data = read_yaml(path)
        function = next((f for f in data["functions"] if f["id"] == point["function"]), None)
        if function is None:
            return False
        lang_key = point["target_lang"]
        realized = function.setdefault("realizations", {}).setdefault(lang_key, [])
        changed = False
        if point["id"] not in realized:
            realized.append(point["id"])
            changed = True
        planned = function.get("planned", {}).get(lang_key, [])
        if point["id"] in planned:
            planned.remove(point["id"])
            changed = True
        if changed:
            path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
                encoding="utf-8",
                newline="\n",
            )
        return changed

_HAN_TITLE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_LOWER_WORD = re.compile(r"[a-zà-ỹ]{3,}")


def audit_seed_semantics(lang: str, root: Path = LAB_ROOT) -> list[dict[str, str]]:
    """Obvious semantic-review debt that structural seed checks cannot prove.

    This intentionally reports rather than auto-fixes: function assignment and
    native teaching titles are curriculum decisions. The audit catches the
    heuristic placeholders that must not be mistaken for reviewed production
    metadata merely because their ids/counts/prerequisites are structurally valid.
    """
    issues: list[dict[str, str]] = []
    for seed in load_seeds(lang, root):
        point_id = seed["id"]
        function = str(seed.get("function", ""))
        native = str(seed.get("native_title", "")).strip()
        if function == "fn.catalog_unclassified":
            issues.append({"id": point_id, "code": "function.unclassified", "value": function})
        if not native:
            issues.append({"id": point_id, "code": "native_title.missing", "value": native})
            continue
        if "_" in native:
            issues.append({"id": point_id, "code": "native_title.placeholder", "value": native})
        if lang == "zh":
            if not _HAN_TITLE.search(native):
                issues.append({"id": point_id, "code": "native_title.non_zh", "value": native})
            elif _LOWER_WORD.search(native):
                issues.append({"id": point_id, "code": "native_title.mixed_language", "value": native})
    return issues

def check_seeds(lang: str, root: Path = LAB_ROOT) -> list[str]:
    """Consistency of the whole seed file; returns the problems (empty = fine)."""
    seeds = load_seeds(lang, root)
    problems: list[str] = []
    ids = [s["id"] for s in seeds]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate id {duplicate}")
    known = set(ids)
    by_id = {s["id"]: s for s in seeds}
    for seed in seeds:
        for other in seed["contrasts"]:
            if other not in known:
                problems.append(f"{seed['id']}: contrast {other} is not a seed")
            elif seed["id"] not in by_id[other]["contrasts"]:
                problems.append(f"{seed['id']}: contrast {other} is not listed both ways")
        for prereq in seed["prereqs"]:
            if prereq not in known:
                problems.append(f"{seed['id']}: prereq {prereq} is not a seed")
    return problems
