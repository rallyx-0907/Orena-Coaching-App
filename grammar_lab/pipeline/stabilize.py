"""Corpus-wide Grammar Lab stabilization.

This module deliberately does not repair individual lessons.  It turns the
whole corpus into one inventory: current corpus state, deterministic validator
issues, objective learner-content quality blockers, cache-only generation
outcomes, and deferred points.  That inventory is the input to later grouped
repairs/regeneration and the final acceptance gate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from grammar_lab.pipeline.content_store import load_points
from grammar_lab.pipeline.corpus import plan_corpus
from grammar_lab.pipeline.jsonio import write_json
from grammar_lab.pipeline.validate import LAB_ROOT, validate_lang

_OUTCOME_RE = re.compile(
    r"(?m)^(written|error|blocked_metadata)\s+((?:en|zh)\.[a-z0-9_.-]+)\s+(\S+)(?:\s+(.*))?$"
)


def classify_generation_reason(reason: str) -> str:
    """Map unstable generator prose onto stable corpus-level failure classes."""
    text = reason.lower()
    if "cache-only mode" in text and "no cached completion" in text:
        return "cache_miss"
    if "formula" in text and ("order" in text or "incompatible" in text):
        return "formula_order"
    if "question" in text and "formula" in text:
        return "variant_formula"
    if "blank" in text and ("mapping" in text or "option" in text):
        return "practice_mapping"
    if "binding" in text and any(word in text for word in ("locat", "order", "overlap", "span")):
        return "slot_binding"
    if "pinyin" in text:
        return "pinyin"
    if "schema" in text or "json" in text:
        return "schema"
    return "semantic_other"


def parse_generation_log(text: str) -> list[dict[str, str]]:
    """Extract every point outcome from one generate-corpus invocation."""
    outcomes: list[dict[str, str]] = []
    for match in _OUTCOME_RE.finditer(text):
        status, point_id, detail, reason = match.groups()
        reason = (reason or "").strip()
        if status == "written":
            category = "written"
        elif status == "blocked_metadata":
            category = "blocked_metadata"
        else:
            category = classify_generation_reason(reason)
        outcomes.append({
            "status": status,
            "point_id": point_id,
            "detail": detail,
            "reason": reason,
            "category": category,
        })
    return outcomes


def _issue(point: dict[str, Any], code: str, path: str, message: str) -> dict[str, str]:
    return {"point_id": str(point.get("id", "")), "code": code, "path": path, "message": message}


def _generated_v04(point: dict[str, Any]) -> bool:
    return (
        point.get("schema_version") == "0.4"
        and isinstance(point.get("provenance"), dict)
        and isinstance(point.get("examples"), list)
    )


def quality_issues(point: dict[str, Any]) -> list[dict[str, str]]:
    """Objective learner-content blockers not covered by JSON shape alone.

    No subjective language scoring lives here.  These checks only reject
    objectively incomplete or duplicated learning material so the gate is
    deterministic and cannot invent grammatical truth.
    """
    if not _generated_v04(point):
        return []

    issues: list[dict[str, str]] = []
    examples = point.get("examples") if isinstance(point.get("examples"), list) else []
    practice = point.get("quick_practice") if isinstance(point.get("quick_practice"), list) else []
    mistakes = point.get("common_mistakes") if isinstance(point.get("common_mistakes"), list) else []

    if len(examples) != 3:
        issues.append(_issue(point, "quality.example_count", "examples", "v0.4 generated lessons require exactly 3 examples"))
    example_texts = [str(item.get("text", "")).strip() for item in examples if isinstance(item, dict)]
    if len(example_texts) != len(set(example_texts)):
        issues.append(_issue(point, "quality.example_duplicate", "examples", "example texts must be distinct"))

    if len(practice) != 3:
        issues.append(_issue(point, "quality.practice_count", "quick_practice", "v0.4 generated lessons require exactly 3 quick-practice items"))
    practice_questions = [str(item.get("q", "")).strip() for item in practice if isinstance(item, dict)]
    if len(practice_questions) != len(set(practice_questions)):
        issues.append(_issue(point, "quality.practice_duplicate", "quick_practice", "quick-practice prompts must be distinct"))

    if not mistakes:
        issues.append(_issue(point, "quality.mistake_missing", "common_mistakes", "at least one real learner mistake is required"))
    mistake_pairs = [
        (str(item.get("wrong", "")).strip(), str(item.get("right", "")).strip())
        for item in mistakes if isinstance(item, dict)
    ]
    if len(mistake_pairs) != len(set(mistake_pairs)):
        issues.append(_issue(point, "quality.mistake_duplicate", "common_mistakes", "common-mistake pairs must be distinct"))

    production = point.get("personal_production")
    has_production = isinstance(production, dict) and bool(production.get("prompt")) and bool(production.get("sample"))
    if not has_production:
        issues.append(_issue(
            point,
            "quality.personal_production_missing",
            "personal_production",
            "generated lessons require a learner production prompt and sample",
        ))

    return issues


def acceptance_blockers(
    *,
    canonical_total: int,
    generated: int,
    ready: int,
    blocked_metadata: int,
    validator_issues: int,
    quality_issues_count: int,
    deferred: int,
    unresolved_cache_errors: int,
) -> list[str]:
    blockers: list[str] = []
    if generated != canonical_total:
        blockers.append("corpus_incomplete")
    if ready:
        blockers.append("ready_points")
    if blocked_metadata:
        blockers.append("blocked_metadata")
    if validator_issues:
        blockers.append("validator_issues")
    if quality_issues_count:
        blockers.append("quality_issues")
    if deferred:
        blockers.append("deferred_points")
    if unresolved_cache_errors:
        blockers.append("unresolved_cache_errors")
    return blockers


def deferred_state_path(root: Path = LAB_ROOT) -> Path:
    return root / ".cache" / "grammar_completion_deferred.txt"


def read_deferred_ids(root: Path = LAB_ROOT) -> list[str]:
    path = deferred_state_path(root)
    if not path.exists():
        return []
    return list(dict.fromkeys(line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()))


def _group_counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def build_stabilization_report(
    lang: str,
    root: Path = LAB_ROOT,
    probe_outcomes: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build the post-salvage corpus report used as the single source of truth."""
    plan = plan_corpus([lang], root)
    language_report = plan["languages"][lang]
    counts = dict(language_report["counts"])
    canonical_total = int(language_report["canonical_total"])
    ready_ids = {item["id"] for item in language_report["items"] if item["status"] == "ready"}

    validation = validate_lang(lang, root)
    validator_by_point: dict[str, list[dict[str, str]]] = defaultdict(list)
    validator_unmapped: list[dict[str, str]] = []
    for issue in validation.issues:
        payload = issue.to_dict()
        point_id = validation.point_files.get(issue.file)
        if point_id:
            validator_by_point[point_id].append(payload)
        else:
            validator_unmapped.append(payload)

    quality: list[dict[str, str]] = []
    for point in load_points(lang, root).values():
        quality.extend(quality_issues(point))
    quality_by_point: dict[str, list[dict[str, str]]] = defaultdict(list)
    for issue in quality:
        quality_by_point[issue["point_id"]].append(issue)

    deferred_ids = [point_id for point_id in read_deferred_ids(root) if point_id in ready_ids]
    outcomes = probe_outcomes or []
    unresolved = [
        item for item in outcomes
        if item.get("status") == "error" and item.get("point_id") in ready_ids
    ]

    point_ids = sorted(
        set(validator_by_point)
        | set(quality_by_point)
        | {item["point_id"] for item in unresolved}
        | set(deferred_ids)
    )
    unresolved_by_point = {item["point_id"]: item for item in unresolved}
    per_point = {
        point_id: {
            "validator": validator_by_point.get(point_id, []),
            "quality": quality_by_point.get(point_id, []),
            "cache_probe": unresolved_by_point.get(point_id),
            "deferred": point_id in deferred_ids,
        }
        for point_id in point_ids
    }

    blockers = acceptance_blockers(
        canonical_total=canonical_total,
        generated=int(counts.get("generated", 0)),
        ready=int(counts.get("ready", 0)),
        blocked_metadata=int(counts.get("blocked_metadata", 0)),
        validator_issues=len(validation.issues),
        quality_issues_count=len(quality),
        deferred=len(deferred_ids),
        unresolved_cache_errors=len(unresolved),
    )

    return {
        "lang": lang,
        "canonical_total": canonical_total,
        "counts": counts,
        "accepted": not blockers,
        "acceptance_blockers": blockers,
        "validator": {
            "issue_count": len(validation.issues),
            "by_code": _group_counts(issue.code for issue in validation.issues),
            "unmapped": validator_unmapped,
        },
        "quality": {
            "issue_count": len(quality),
            "by_code": _group_counts(issue["code"] for issue in quality),
        },
        "cache_probe": {
            "outcome_count": len(outcomes),
            "unresolved_count": len(unresolved),
            "by_category": _group_counts(item["category"] for item in unresolved),
        },
        "deferred": deferred_ids,
        "points": per_point,
    }


def run_cache_sweep(lang: str, root: Path = LAB_ROOT, *, workers: int = 4) -> tuple[int, str, list[dict[str, str]]]:
    """Replay every eligible cached candidate in one child process, never paid."""
    command = [
        sys.executable,
        "-m", "grammar_lab.pipeline.cli", "generate-corpus",
        "--lang", lang,
        "--provider", "deepseek",
        "--model", "deepseek-flash",
        "--workers", str(workers),
        "--max-points", "0",
        "--max-full-attempts", "1",
        "--no-paid-repairs",
        "--one-shot",
        "--cache-only",
        "--root", str(root),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        check=False,
    )
    text = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode, text, parse_generation_log(text)


def write_stabilization_report(report: dict[str, Any], path: Path) -> Path:
    write_json(path, report)
    return path


def render_stabilization_report(report: dict[str, Any]) -> str:
    counts = report["counts"]
    lines = [
        f"stabilize {report['lang']}: canonical {report['canonical_total']}, "
        f"generated {counts.get('generated', 0)}, ready {counts.get('ready', 0)}, "
        f"blocked {counts.get('blocked_metadata', 0)}",
        f"validator issues: {report['validator']['issue_count']}",
        f"quality blockers: {report['quality']['issue_count']}",
        f"unresolved cache outcomes: {report['cache_probe']['unresolved_count']}",
        f"deferred: {len(report['deferred'])}",
        f"accepted: {'YES' if report['accepted'] else 'NO'}",
    ]
    if report["cache_probe"]["by_category"]:
        lines.append("cache failure classes: " + ", ".join(
            f"{code}={count}" for code, count in report["cache_probe"]["by_category"].items()
        ))
    if report["acceptance_blockers"]:
        lines.append("acceptance blockers: " + ", ".join(report["acceptance_blockers"]))
    return "\n".join(lines)
