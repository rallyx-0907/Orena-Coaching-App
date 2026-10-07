"""Human approval gate for reviewed Grammar Lab points.

Approval is intentionally separate from generation and ``apply-feedback``.  It
is the explicit human transition from a reviewed draft/route result to
``approved`` and records the schema's ``review`` audit fields.

The operation is fail-closed and batch-atomic at the application level: every
selected point is preflighted first, including rules that only become active
when ``status == 'approved'``.  Nothing is written when any selected point
fails a gate.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from grammar_lab.pipeline.content_store import load_points, save_point
from grammar_lab.pipeline.validate import LAB_ROOT, LANGS, validate_generated_point, validate_lang

APPROVABLE_STATUSES = frozenset({"draft_ai", "auto_ok", "flagged"})


class ApprovalError(ValueError):
    """One or more gates blocked a requested human approval batch."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class ApprovalResult:
    approved: list[str]
    already_approved: list[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def approve_points(
    lang: str,
    point_ids: list[str],
    *,
    reviewer: str,
    seconds: float = 0.0,
    note: str | None = None,
    reviewed_at: str | None = None,
    root: Path = LAB_ROOT,
) -> ApprovalResult:
    """Approve selected reviewed points and record human review metadata.

    The selected batch is all-or-nothing: all current and approved-state
    validation gates are evaluated before any point is saved.  Existing
    approvals are idempotent no-ops and their original review record is never
    overwritten.
    """
    problems: list[str] = []
    reviewer = reviewer.strip()
    unique_ids = list(dict.fromkeys(point_id.strip() for point_id in point_ids if point_id.strip()))

    if lang not in LANGS:
        raise ApprovalError([f"unknown lang {lang!r}; expected one of {', '.join(LANGS)}"])
    if not unique_ids:
        problems.append("no grammar point ids selected")
    if not reviewer:
        problems.append("reviewer must be a non-empty human reviewer name")
    if seconds < 0:
        problems.append("seconds must be >= 0")

    points = load_points(lang, root)
    full_report = validate_lang(lang, root)
    issues_by_id: dict[str, list] = {}
    for issue in full_report.issues:
        point_id = full_report.point_files.get(issue.file)
        if point_id:
            issues_by_id.setdefault(point_id, []).append(issue)

    timestamp = reviewed_at or _now_iso()
    review_note = note.strip() if isinstance(note, str) and note.strip() else None
    candidates: dict[str, dict] = {}
    already_approved: list[str] = []

    for point_id in unique_ids:
        point = points.get(point_id)
        if point is None:
            problems.append(f"{point_id}: point not found in content/{lang}")
            continue

        status = point.get("status")
        if status == "approved":
            already_approved.append(point_id)
            continue
        if status not in APPROVABLE_STATUSES:
            problems.append(f"{point_id}: status {status!r} cannot be approved")
            continue

        current_issues = issues_by_id.get(point_id, [])
        if current_issues:
            for issue in current_issues:
                problems.append(
                    f"{point_id}: {issue.reason} at {issue.path}: {issue.message}"
                )
            continue

        candidate = copy.deepcopy(point)
        candidate["status"] = "approved"
        candidate["review"] = {
            "reviewer": reviewer,
            "reviewed_at": timestamp,
            "seconds": float(seconds),
            "note": review_note,
        }
        approved_issues = validate_generated_point(lang, candidate, root)
        if approved_issues:
            for issue in approved_issues:
                problems.append(
                    f"{point_id}: {issue.reason} at {issue.path}: {issue.message}"
                )
            continue
        candidates[point_id] = candidate

    if problems:
        raise ApprovalError(problems)

    approved: list[str] = []
    for point_id in unique_ids:
        candidate = candidates.get(point_id)
        if candidate is None:
            continue
        save_point(lang, candidate, root)
        approved.append(point_id)

    return ApprovalResult(approved=approved, already_approved=already_approved)
