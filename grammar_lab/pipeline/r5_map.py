"""The explicit R5 map of an export package (``GRAMMAR_CONTENT_STORE`` section 9, decisions D-106 2 and 4).

One R5 id has exactly one primary replacement (or is dropped). The R5 id is listed in ``aliases`` of that
primary point and of no other. The other pieces of a split record the relationship as provenance
(``source_refs.r5_split``), never as a second alias. The disposition of every R5 id travels in the manifest as
``r5_map`` rows ``{r5_id, point_id | null, disposition, is_primary}``; the importer reads it and never infers it
from aliases.

Dispositions: ``replaced`` (one R5 id -> one point), ``merged`` (several R5 ids -> one point, one row per id),
``split_primary`` / ``split_secondary`` (one R5 id divided into pieces), ``dropped`` (no replacement).

``build_r5_map`` derives the rows from the runtime catalogue (canonical v1: ``r5`` = every R5 source of a
point, ``aliases`` = the ids it is the primary of); ``validate_r5_map`` checks rows against the point bodies and
is what both the exporter and the package validator run.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

DISPOSITIONS = ("replaced", "merged", "split_primary", "split_secondary", "dropped")


def load_dropped_r5_ids(lang: str, tsv_path: Path) -> list[str]:
    """R5 ids the approved conversion map removes without a replacement (``action == remove``)."""
    with tsv_path.open(encoding="utf-8", newline="") as handle:
        return sorted({row["r5_id"] for row in csv.DictReader(handle, delimiter="\t")
                       if row["lang"] == lang and row["action"] == "remove"})


def build_r5_map(
    records: list[dict[str, Any]], selected: list[str], dropped: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """``(rows, problems)`` for the points ``selected`` out of the whole catalogue ``records``.

    Every R5 id touching a selected point is listed with **all** its pieces, so every piece must be selected too:
    a package cannot carry half of a split (the importer would see a primary without its secondary or the reverse).
    """
    by_id = {record["id"]: record for record in records}
    pieces: dict[str, list[str]] = {}
    primary_of: dict[str, list[str]] = {}
    for record in records:
        for r5_id in record.get("r5", []):
            pieces.setdefault(r5_id, []).append(record["id"])
        for r5_id in record.get("aliases", []):
            primary_of.setdefault(r5_id, []).append(record["id"])
    problems: list[str] = []
    rows: list[dict[str, Any]] = []
    wanted = sorted({r5 for point_id in selected for r5 in by_id[point_id].get("r5", [])})
    for r5_id in wanted:
        owners = primary_of.get(r5_id, [])
        if len(owners) != 1:
            problems.append(f"r5_map.primary: {r5_id} is an alias of {len(owners)} points ({', '.join(owners) or 'none'}); exactly one required")
            continue
        primary = owners[0]
        outside = [point_id for point_id in pieces[r5_id] if point_id not in selected]
        if outside:
            problems.append(f"r5_map.incomplete: {r5_id} also has pieces outside this package ({', '.join(outside)}); export them together")
            continue
        if len(pieces[r5_id]) > 1:
            for point_id in pieces[r5_id]:
                rows.append({"r5_id": r5_id, "point_id": point_id, "is_primary": point_id == primary,
                             "disposition": "split_primary" if point_id == primary else "split_secondary"})
        else:
            merged = len(by_id[primary].get("aliases", [])) > 1
            rows.append({"r5_id": r5_id, "point_id": primary, "is_primary": True,
                         "disposition": "merged" if merged else "replaced"})
    mapped = {row["r5_id"] for row in rows} | set(wanted)
    for r5_id in sorted(set(dropped or [])):
        if r5_id in mapped or r5_id in pieces:
            problems.append(f"r5_map.dropped_and_mapped: {r5_id} is dropped and also has a replacement")
            continue
        rows.append({"r5_id": r5_id, "point_id": None, "is_primary": False, "disposition": "dropped"})
    rows.sort(key=lambda row: (row["r5_id"], not row["is_primary"], row["point_id"] or ""))
    return rows, problems


def validate_r5_map(rows: list[dict[str, Any]], bodies: dict[str, dict[str, Any]]) -> list[str]:
    """Problems of ``rows`` against the point ``bodies`` of the package (empty = valid). Nothing is inferred."""
    problems: list[str] = []
    by_id: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        if set(row) != {"r5_id", "point_id", "is_primary", "disposition"}:
            problems.append(f"r5_map[{index}]: keys must be exactly r5_id, point_id, is_primary, disposition")
            continue
        if row["disposition"] not in DISPOSITIONS:
            problems.append(f"r5_map[{index}]: unknown disposition {row['disposition']!r}")
            continue
        if (row["disposition"] == "dropped") != (row["point_id"] is None):
            problems.append(f"r5_map[{index}] {row['r5_id']}: point_id is null exactly when the disposition is dropped")
        if row["point_id"] is not None and row["point_id"] not in bodies:
            problems.append(f"r5_map[{index}] {row['r5_id']}: point {row['point_id']} is not in the package")
        by_id.setdefault(row["r5_id"], []).append(row)
    aliases: dict[str, list[str]] = {}
    for point_id, body in bodies.items():
        for alias in body.get("aliases", []):
            aliases.setdefault(alias, []).append(point_id)
    for alias, owners in sorted(aliases.items()):
        if len(owners) > 1:
            problems.append(f"aliases.duplicate: {alias} is an alias of {', '.join(sorted(owners))}")
        if alias not in by_id:
            problems.append(f"r5_map.missing: {alias} is an alias of {owners[0]} but has no r5_map row")
    for r5_id, group in sorted(by_id.items()):
        dropped = [row for row in group if row["disposition"] == "dropped"]
        primaries = [row for row in group if row["is_primary"]]
        secondaries = [row for row in group if row["disposition"] == "split_secondary"]
        if dropped and len(group) > 1:
            problems.append(f"r5_map.dropped_and_mapped: {r5_id} is dropped and also mapped")
        if dropped:
            continue
        if len(primaries) != 1:
            problems.append(f"r5_map.primary: {r5_id} has {len(primaries)} primary rows; exactly one required")
            continue
        primary = primaries[0]
        if primary["disposition"] == "split_secondary":
            problems.append(f"r5_map.primary: {r5_id} primary row is marked split_secondary")
        if secondaries and primary["disposition"] != "split_primary":
            problems.append(f"r5_map.split: {r5_id} has secondaries but its primary is {primary['disposition']}")
        if primary["disposition"] == "split_primary" and not secondaries:
            problems.append(f"r5_map.split: {r5_id} is split_primary without a secondary piece")
        if len({row["point_id"] for row in group}) != len(group):
            problems.append(f"r5_map.duplicate_row: {r5_id} lists a point twice")
        if primary["point_id"] in bodies and r5_id not in bodies[primary["point_id"]].get("aliases", []):
            problems.append(f"r5_map.alias: primary point {primary['point_id']} does not list {r5_id} in aliases")
        for row in group:
            if row is primary or row["point_id"] not in bodies:
                continue
            body = bodies[row["point_id"]]
            if r5_id in body.get("aliases", []):
                problems.append(f"r5_map.alias: {r5_id} is also an alias of secondary {row['point_id']} (primary only)")
            if r5_id not in body.get("source_refs", {}).get("r5_split", []):
                problems.append(f"r5_map.provenance: secondary {row['point_id']} does not record {r5_id} in source_refs.r5_split")
    return problems
