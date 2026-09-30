"""coverage step (SPEC §5.5) over the canonical catalogue.

A point being in the catalogue is not the same as its content being written, checked or approved, and
this report never conflates them. Per point it keeps four separate facts:

1. ``canonical``  -- the point is in ``catalog_<lang>.yaml`` (always true for a row of the report);
2. ``generated``  -- ``content/<lang>/<id>.json`` exists;
3. ``validated``  -- generated and it passes the deterministic checks of ``validate`` (SPEC §5.2);
4. ``approved``   -- generated and ``status == approved`` (``auto_ok`` is counted apart).

Chinese also reports the catalogue-layer GF0025 source coverage (572/572 for catalog v1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from grammar_lab.pipeline.canonical import zh_source_coverage
from grammar_lab.pipeline.content_store import load_points
from grammar_lab.pipeline.seed import load_catalog
from grammar_lab.pipeline.validate import LAB_ROOT, validate_lang


def coverage_report(lang: str, root: Path = LAB_ROOT) -> dict[str, Any]:
    records = load_catalog(lang, root)
    points = load_points(lang, root)
    validation = validate_lang(lang, root)
    invalid = {validation.point_files[issue.file] for issue in validation.issues if issue.file in validation.point_files}
    catalog_ids = {record["id"] for record in records}

    def state(record: dict[str, Any]) -> dict[str, bool]:
        point = points.get(record["id"])
        generated = point is not None
        return {
            "generated": generated,
            "validated": generated and record["id"] not in invalid,
            "auto_ok": generated and point.get("status") == "auto_ok",
            "approved": generated and point.get("status") == "approved",
        }

    states = {record["id"]: state(record) for record in records}
    per_level: dict[str, dict[str, int]] = {}
    for record in records:
        label = record.get("catalog", {}).get("canonical_level") or str(record["level"])
        row = per_level.setdefault(label, {"canonical": 0, "generated": 0, "validated": 0, "auto_ok": 0, "approved": 0})
        row["canonical"] += 1
        for key, flag in states[record["id"]].items():
            row[key] += int(flag)
    totals = {key: sum(int(s[key]) for s in states.values()) for key in ("generated", "validated", "auto_ok", "approved")}
    report: dict[str, Any] = {
        "lang": lang,
        "canonical_total": len(records),
        "generated_total": totals["generated"],
        "validated_total": totals["validated"],
        "auto_ok_total": totals["auto_ok"],
        "approved_total": totals["approved"],
        "missing_content_total": len(records) - totals["generated"],
        "per_level": per_level,
        "missing_content": [record["id"] for record in records if not states[record["id"]]["generated"]],
        "content_outside_catalog": sorted(set(points) - catalog_ids),
        "metadata_origin": _count(record.get("catalog", {}).get("metadata_origin", "seed") for record in records),
    }
    if lang == "zh":
        report["gf0025"] = zh_source_coverage(root)
    return report


def _count(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def render_text(report: dict[str, Any]) -> str:
    lines = [
        f"coverage --lang {report['lang']}: canonical {report['canonical_total']}, "
        f"generated {report['generated_total']}, validated {report['validated_total']}, "
        f"auto_ok {report['auto_ok_total']}, approved {report['approved_total']}, "
        f"missing content {report['missing_content_total']}",
        "level      canonical generated validated auto_ok approved",
    ]
    for label, row in report["per_level"].items():
        lines.append(
            f"{label:10} {row['canonical']:9} {row['generated']:9} {row['validated']:9} {row['auto_ok']:7} {row['approved']:8}"
        )
    if "gf0025" in report:
        gf = report["gf0025"]
        lines.append(f"GF0025 source coverage: {gf['covered']}/{gf['total']} (missing {len(gf['missing'])})")
    if report["content_outside_catalog"]:
        lines.append("content outside the catalogue: " + ", ".join(report["content_outside_catalog"]))
    return "\n".join(lines)
