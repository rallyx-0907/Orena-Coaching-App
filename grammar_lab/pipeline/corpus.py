"""Whole-corpus planning helpers for Grammar Lab.

The canonical catalog is larger than the currently reviewed seed metadata. This
module keeps those facts separate so a corpus run can safely resume without
silently generating content from default_safe placeholders.

A point is classified as one of:

* ready: reviewed metadata, no content file yet;
* generated: reviewed metadata and content already exists;
* blocked_metadata: no content yet, but metadata is still default_safe;
* generated_unreviewed_metadata: content exists even though catalog metadata
  is still default_safe and therefore needs metadata review before the point
  can be considered corpus-complete.

The planner never mutates content and never bypasses check_generation_gate.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from grammar_lab.pipeline.content_store import load_points
from grammar_lab.pipeline.seed import load_catalog
from grammar_lab.pipeline.validate import LAB_ROOT

CORPUS_LANGS = ("en", "zh")
READY = "ready"
GENERATED = "generated"
BLOCKED_METADATA = "blocked_metadata"
GENERATED_UNREVIEWED_METADATA = "generated_unreviewed_metadata"


def normalize_langs(lang: str) -> tuple[str, ...]:
    """CLI-facing language selector: all or one corpus language."""
    if lang == "all":
        return CORPUS_LANGS
    if lang not in CORPUS_LANGS:
        raise ValueError(f"expected all, {', '.join(CORPUS_LANGS)}")
    return (lang,)


def _level_label(record: dict[str, Any]) -> str:
    return str(record.get("catalog", {}).get("canonical_level") or record["level"])


def _status(record: dict[str, Any], generated_ids: set[str]) -> str:
    generated = record["id"] in generated_ids
    metadata_origin = record.get("catalog", {}).get("metadata_origin", "default_safe")
    reviewed = metadata_origin != "default_safe"
    if generated and reviewed:
        return GENERATED
    if generated:
        return GENERATED_UNREVIEWED_METADATA
    if reviewed:
        return READY
    return BLOCKED_METADATA


def plan_corpus(
    langs: Iterable[str] = CORPUS_LANGS,
    root: Path = LAB_ROOT,
) -> dict[str, Any]:
    """Return a deterministic, canonical-order plan for the selected languages."""
    language_reports: dict[str, Any] = {}
    total_counts: Counter[str] = Counter()
    total = 0

    for lang in langs:
        if lang not in CORPUS_LANGS:
            raise ValueError(f"unsupported corpus language: {lang}")
        records = load_catalog(lang, root)
        generated_ids = set(load_points(lang, root))
        items: list[dict[str, str]] = []
        counts: Counter[str] = Counter()
        per_level: dict[str, Counter[str]] = {}

        for record in records:
            status = _status(record, generated_ids)
            level = _level_label(record)
            item = {
                "id": record["id"],
                "level": level,
                "status": status,
                "metadata_origin": record.get("catalog", {}).get("metadata_origin", "default_safe"),
            }
            items.append(item)
            counts[status] += 1
            per_level.setdefault(level, Counter())[status] += 1

        language_reports[lang] = {
            "canonical_total": len(records),
            "counts": dict(counts),
            "per_level": {level: dict(row) for level, row in per_level.items()},
            "items": items,
        }
        total += len(records)
        total_counts.update(counts)

    return {
        "canonical_total": total,
        "counts": dict(total_counts),
        "languages": language_reports,
    }


def matches_generation_provenance(
    point: dict[str, Any], *, provider: str, model: str, prompt_version: str,
) -> bool:
    """Whether an existing v0.4 draft already came from this exact corpus recipe.

    Used by final-corpus normalization so a resumed run does not pay to
    regenerate points that were already written by the same provider/model
    and prompt version.
    """
    provenance = point.get("provenance") or {}
    return (
        point.get("schema_version") == "0.4"
        and provenance.get("model") == f"{provider}:{model}"
        and provenance.get("prompt_version") == prompt_version
        and not provenance.get("metadata_stale", False)
    )


def generation_items(
    plan: dict[str, Any], *, include_generated: bool = False,
) -> list[tuple[str, str, str]]:
    """Return (lang, level, id) in canonical order for a corpus generation run.

    The default keeps the historical resumable behavior: only missing ready
    points are selected. include_generated=True also selects points that
    already have reviewed content so a final corpus pass can regenerate every
    draft through the same prompt/schema pipeline. Blocked/default-safe points
    are never selected here.
    """
    statuses = {READY}
    if include_generated:
        statuses.add(GENERATED)
    out: list[tuple[str, str, str]] = []
    for lang, report in plan["languages"].items():
        for item in report["items"]:
            if item["status"] in statuses:
                out.append((lang, item["level"], item["id"]))
    return out


def stratified_items(
    items: list[tuple[str, str, str]], per_level: int,
) -> list[tuple[str, str, str]]:
    """Take the first N candidates from every (language, level) group.

    Unlike --max-points on canonical order, this gives a smoke run real
    coverage across A1-C2 and HSK1-HSK9 instead of over-sampling A1 English.
    Input order is preserved.
    """
    if per_level <= 0:
        return list(items)
    counts: Counter[tuple[str, str]] = Counter()
    out: list[tuple[str, str, str]] = []
    for item in items:
        key = (item[0], item[1])
        if counts[key] >= per_level:
            continue
        counts[key] += 1
        out.append(item)
    return out

def ready_items(plan: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Backward-compatible selector for missing reviewed points only."""
    return generation_items(plan)


def render_text(plan: dict[str, Any]) -> str:
    counts = plan["counts"]
    lines = [
        (
            f"corpus: canonical {plan['canonical_total']}, "
            f"ready {counts.get(READY, 0)}, "
            f"generated {counts.get(GENERATED, 0)}, "
            f"blocked metadata {counts.get(BLOCKED_METADATA, 0)}, "
            f"generated with unreviewed metadata {counts.get(GENERATED_UNREVIEWED_METADATA, 0)}"
        )
    ]
    for lang, report in plan["languages"].items():
        c = report["counts"]
        lines.append(
            f"{lang}: canonical {report['canonical_total']}, ready {c.get(READY, 0)}, "
            f"generated {c.get(GENERATED, 0)}, blocked metadata {c.get(BLOCKED_METADATA, 0)}, "
            f"generated/unreviewed {c.get(GENERATED_UNREVIEWED_METADATA, 0)}"
        )
        for level, row in report["per_level"].items():
            lines.append(
                f"  {level:6} ready {row.get(READY, 0):3}  generated {row.get(GENERATED, 0):3}  "
                f"blocked {row.get(BLOCKED_METADATA, 0):3}  generated/unreviewed "
                f"{row.get(GENERATED_UNREVIEWED_METADATA, 0):3}"
            )
    return "\n".join(lines)
