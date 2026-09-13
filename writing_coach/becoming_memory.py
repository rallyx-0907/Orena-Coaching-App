from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from writing_coach.languages.runtime import active_profile
from writing_coach.persistence.specialized_repository import SpecializedLearningRepository
from writing_coach.core.support_languages import resolve_support_language
from writing_coach.account_profile import (
    LANGUAGE_SETTINGS,
    PatchRejected,
    STORED_SETTINGS,
    effective_settings,
    patch_profile,
)


_repository: SpecializedLearningRepository | None = None


class LearnerProfileIn(BaseModel):
    goal: str = Field(default="everyday", pattern=r"^(everyday|work|exam|voice)$")
    style: str = Field(default="guided", pattern=r"^(guided|examples|concise|deep)$")
    pinyin: str = Field(default="auto", pattern=r"^(auto|on|off)$")
    # The learner's SUPPORT language: what meanings and explanations arrive in.
    # Widened from ^(vi|en|zh)$ to a BCP-47 shape so the stored preference is a
    # language identity rather than an enum of the three Orena happened to
    # support first. Availability is enforced on resolution, not on storage.
    native_language: str = Field(default="", pattern=r"^$|^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    theme_preset: str = Field(
        default="editorial",
        pattern=r"^(editorial|sage|clay|blueprint)$",
    )


def configure_becoming_memory(repository: SpecializedLearningRepository) -> None:
    global _repository
    _repository = repository


def _repo() -> SpecializedLearningRepository:
    if _repository is None:
        raise RuntimeError("BECOMING memory repository is not installed")
    return _repository

def _safe_json(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except Exception:
        return fallback
    return parsed


def _normalized_category(value: Any) -> str:
    raw = str(value or "other").strip().lower()
    raw = "_".join(part for part in raw.replace("-", " ").split() if part)
    return raw[:80] or "other"


# The profile record predates the settings registry, so one name differs: the
# column is `native_language`, the setting is `support_language`. Mapping it in
# one place keeps the column where it is - renaming it is a migration - while
# the contract says what the setting actually means.
_RECORD_NAMES = {"support_language": "native_language"}


def _saved_settings(row: dict[str, Any] | None) -> dict[str, Any]:
    """The stored answers, addressed by setting name rather than column name."""
    if not row:
        return {}
    saved: dict[str, Any] = {}
    for name in STORED_SETTINGS:
        value = row.get(_RECORD_NAMES.get(name, name))
        if value not in (None, ""):
            saved[name] = str(value)
    return saved


def _profile_version(row: dict[str, Any] | None) -> str:
    """The token a writer must present to change the profile.

    There is no version column and none is authorized yet, so the record's own
    last-updated stamp serves: it changes on every write, which is all an
    expected-version check needs. An absent profile has the empty token, which
    is the creation case.
    """
    return str((row or {}).get("updated_at") or "")


def _profile_payload(row: dict[str, Any] | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    version = _profile_version(row)
    settings = effective_settings(_saved_settings(row), version=version, overrides=overrides)
    flat = {name: settings[name]["value"] for name in LANGUAGE_SETTINGS}
    return {
        "exists": bool(row),
        "language": active_profile().code,
        **flat,
        "native_language": str((row or {}).get("native_language") or ""),
        # The resolved SUPPORT language, so every client reads one answer
        # instead of re-implementing the rule and drifting apart.
        "support_language": resolve_support_language((row or {}).get("native_language")),
        # Presentation is the theme registry's, not this domain's. It is read
        # and written back untouched.
        "theme_preset": str((row or {}).get("theme_preset") or "editorial"),
        "updated_at": version,
        # Each setting with where its current value came from, so a surface can
        # tell a saved choice from a product default without guessing.
        "settings": settings,
        "version": version,
    }


def get_learner_profile(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    return _profile_payload(_repo().get_profile_record(), overrides)


class ProfilePatchIn(BaseModel):
    """Named settings to change, and the version the client believes is current.

    Every field is optional and absent means absent: the whole-profile PUT this
    replaces defaulted each field, so a client sending only the setting it
    meant to change reset the others to the product defaults.
    """

    expected_version: str = ""
    goal: str | None = None
    style: str | None = None
    pinyin: str | None = None
    support_language: str | None = None
    declared_level: str | None = None
    interface_language: str | None = None
    theme_preset: str | None = None


_PATCH_STATUS = {"version_conflict": 409, "not_yet_stored": 501}


def patch_learner_profile(payload: ProfilePatchIn) -> dict[str, Any]:
    """Change the named settings, or change nothing and say why."""
    from fastapi import HTTPException

    row = _repo().get_profile_record()
    patch = {
        name: value
        for name, value in payload.model_dump(exclude={"expected_version"}).items()
        if value is not None
    }
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        merged, version = patch_profile(
            _saved_settings(row),
            patch,
            expected_version=payload.expected_version,
            current_version=_profile_version(row),
            next_version=now,
        )
    except PatchRejected as rejected:
        raise HTTPException(
            status_code=_PATCH_STATUS.get(rejected.reason, 400),
            detail={
                "reason": rejected.reason,
                "field": rejected.field,
                "current_version": rejected.current_version,
            },
        ) from rejected
    _repo().upsert_profile_record({
        "goal": merged.get("goal", LANGUAGE_SETTINGS["goal"].default),
        "style": merged.get("style", LANGUAGE_SETTINGS["style"].default),
        "pinyin": merged.get("pinyin", LANGUAGE_SETTINGS["pinyin"].default),
        "native_language": merged.get("support_language", ""),
        # Untouched: presentation belongs to the theme registry.
        "theme_preset": str((row or {}).get("theme_preset") or "editorial"),
        "created_at": str((row or {}).get("created_at") or now),
        "updated_at": version,
    })
    return get_learner_profile()

def put_learner_profile(payload: LearnerProfileIn) -> dict[str, Any]:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    existing = _repo().get_profile_record()
    created_at = str(existing.get("created_at")) if existing else now
    _repo().upsert_profile_record({
        "goal": payload.goal, "style": payload.style, "pinyin": payload.pinyin,
        "native_language": payload.native_language, "theme_preset": payload.theme_preset,
        "created_at": created_at, "updated_at": now,
    })
    return {
        "exists": True, "language": active_profile().code, "goal": payload.goal,
        "style": payload.style, "pinyin": payload.pinyin,
        "native_language": payload.native_language,
        "support_language": resolve_support_language(payload.native_language),
        "theme_preset": payload.theme_preset,
        "updated_at": now,
    }

def _essay_rows() -> list[dict[str, Any]]:
    return _repo().memory_essay_rows()

def _error_patterns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    by_cat: dict[str, dict[str, Any]] = {}
    midpoint = max(1, len(rows) // 2)
    newer_ids = {int(row["id"]) for row in rows[midpoint:]}
    older_ids = {int(row["id"]) for row in rows[:midpoint]}

    for row in rows:
        rid = int(row["id"])
        for err in _safe_json(row["errors_json"], []):
            if not isinstance(err, dict):
                continue
            cat = _normalized_category(err.get("category"))
            item = by_cat.setdefault(
                cat,
                {
                    "category": cat,
                    "total": 0,
                    "older": 0,
                    "newer": 0,
                    "series": set(),
                    "last_seen": "",
                    "latest_essay_id": None,
                    "example_essay_id": None,
                    "example": "",
                    "suggestion": "",
                },
            )
            item["total"] += 1
            item["series"].add(int(row["series_id"] or row["id"]))
            item["last_seen"] = str(row["created_at"])
            item["latest_essay_id"] = rid
            if rid in older_ids:
                item["older"] += 1
            if rid in newer_ids:
                item["newer"] += 1
            if not item["example"] and err.get("fragment"):
                item["example"] = str(err.get("fragment"))[:240]
                item["example_essay_id"] = rid
            if not item["suggestion"] and err.get("suggestion"):
                item["suggestion"] = str(err.get("suggestion"))[:320]

    output: list[dict[str, Any]] = []
    for item in by_cat.values():
        if item["newer"] == 0 and item["older"] > 0:
            status = "historical"
        elif item["older"] > 0 and item["newer"] < item["older"]:
            status = "improving"
        elif item["older"] == 0 and item["newer"] > 0:
            status = "new"
        elif item["total"] >= 3:
            status = "recurring"
        else:
            status = "watch"

        output.append(
            {
                "category": item["category"],
                "status": status,
                "total": item["total"],
                "older": item["older"],
                "newer": item["newer"],
                "series_count": len(item["series"]),
                "last_seen": item["last_seen"],
                "latest_essay_id": item["latest_essay_id"],
                "example_essay_id": item["example_essay_id"],
                "example": item["example"],
                "suggestion": item["suggestion"],
            }
        )

    priority = {"recurring": 0, "new": 1, "watch": 2, "improving": 3, "historical": 4}
    output.sort(key=lambda x: (priority.get(x["status"], 9), -int(x["total"])))
    return output


_REVIEW_CUE_OUTCOME_STATUSES = {"still_working", "needs_attention"}
_REVIEW_CUE_PATTERN_STATUSES = {"recurring", "new", "watch"}


def _review_cue_from_outcome(outcome: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(outcome, dict):
        return None
    status = str(outcome.get("status") or "").strip().casefold()
    if status not in _REVIEW_CUE_OUTCOME_STATUSES:
        return None
    raw_evidence = outcome.get("error_evidence")
    if not isinstance(raw_evidence, list):
        return None
    evidence = next(
        (
            str(item).strip()[:260]
            for item in raw_evidence
            if isinstance(item, str) and item.strip()
        ),
        "",
    )
    essay_id = outcome.get("essay_id")
    if isinstance(essay_id, bool) or not isinstance(essay_id, int) or essay_id <= 0 or not evidence:
        return None
    return {
        "available": True,
        "state": "unresolved",
        "source": "practice_outcome",
        "status": status,
        "category": str(outcome.get("focus_category") or "expression")[:80],
        "focus_family": str(outcome.get("focus_family") or "expression")[:40],
        "evidence": evidence,
        "suggestion": "",
        "essay_id": essay_id,
        "grammar_id": str(outcome.get("grammar_id") or "")[:160],
        "total": None,
    }


def _review_cue_from_pattern(pattern: dict[str, Any], *, essay_id: int | None = None) -> dict[str, Any] | None:
    if not isinstance(pattern, dict):
        return None
    status = str(pattern.get("status") or "").strip().casefold()
    evidence = str(pattern.get("example") or "").strip()[:260]
    latest_id = pattern.get("latest_essay_id")
    evidence_id = pattern.get("example_essay_id")
    if status not in _REVIEW_CUE_PATTERN_STATUSES or not evidence:
        return None
    if isinstance(latest_id, bool) or not isinstance(latest_id, int) or latest_id <= 0:
        return None
    if isinstance(evidence_id, bool) or not isinstance(evidence_id, int) or evidence_id <= 0:
        return None
    if essay_id is not None and evidence_id != essay_id:
        return None
    return {
        "available": True,
        "state": "recurring" if status == "recurring" else "unresolved",
        "source": "error_memory",
        "status": status,
        "category": str(pattern.get("category") or "expression")[:80],
        "focus_family": "",
        "evidence": evidence,
        "suggestion": str(pattern.get("suggestion") or "").strip()[:320],
        "essay_id": evidence_id,
        "grammar_id": "",
        "total": int(pattern.get("total") or 0),
    }


def _review_cue(
    rows: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    *,
    essay_id: int | None = None,
) -> dict[str, Any]:
    """Select one literal, language-scoped cue without inferring mastery."""
    if essay_id is not None:
        target = next(
            (row for row in rows if int(row["id"] or 0) == essay_id),
            None,
        )
        if target:
            try:
                from writing_coach.becoming_outcomes import derive_practice_outcome

                outcome = _review_cue_from_outcome(derive_practice_outcome(rows, target))
            except Exception:
                outcome = None
            if outcome:
                return outcome
        for pattern in patterns:
            cue = _review_cue_from_pattern(pattern, essay_id=essay_id)
            if cue:
                return cue

        # An essay-scoped request must never receive a cue from another essay.
        return {
            "available": False,
            "state": "none",
            "source": "none",
            "status": "",
            "category": "",
            "focus_family": "",
            "evidence": "",
            "suggestion": "",
            "essay_id": None,
            "grammar_id": "",
            "total": 0,
        }

    for pattern in patterns:
        cue = _review_cue_from_pattern(pattern)
        if cue:
            return cue

    # A practice outcome can carry a more recent unresolved literal than the
    # aggregate pattern list. Only use the repository's own rows and statuses.
    try:
        from writing_coach.becoming_outcomes import derive_practice_outcome

        for row in reversed(rows):
            cue = _review_cue_from_outcome(derive_practice_outcome(rows, row))
            if cue:
                return cue
    except Exception:
        pass

    return {
        "available": False,
        "state": "none",
        "source": "none",
        "status": "",
        "category": "",
        "focus_family": "",
        "evidence": "",
        "suggestion": "",
        "essay_id": None,
        "grammar_id": "",
        "total": 0,
    }


def _strength_patterns(rows: list[dict[str, Any]], error_patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_cat: dict[str, dict[str, Any]] = {}
    recent_rows = rows[-5:]
    recent_ids = {int(row["id"]) for row in recent_rows}
    recent_error_categories = {
        item["category"]
        for item in error_patterns
        if item["status"] in {"recurring", "new", "watch"}
    }

    for row in rows:
        rid = int(row["id"])
        series_id = int(row["series_id"] or row["id"])
        evidence = _safe_json(row["strength_evidence_json"], [])
        for item in evidence:
            if not isinstance(item, dict):
                continue
            cat = _normalized_category(item.get("category"))
            fragment = str(item.get("fragment") or "").strip()
            if not fragment:
                continue

            record = by_cat.setdefault(
                cat,
                {
                    "category": cat,
                    "evidence_count": 0,
                    "recent_count": 0,
                    "series": set(),
                    "last_seen": "",
                    "example": "",
                    "explanation": "",
                },
            )
            record["evidence_count"] += 1
            record["series"].add(series_id)
            record["last_seen"] = str(row["created_at"])
            if rid in recent_ids:
                record["recent_count"] += 1
            if not record["example"]:
                record["example"] = fragment[:240]
            if not record["explanation"] and item.get("explanation_vi"):
                record["explanation"] = str(item.get("explanation_vi"))[:500]

    output: list[dict[str, Any]] = []
    for record in by_cat.values():
        count = int(record["evidence_count"])
        series_count = len(record["series"])

        if count >= 5 and series_count >= 4 and record["recent_count"] >= 1:
            stage = "Mastered"
        elif count >= 3 and series_count >= 2:
            stage = "Stable"
        elif count >= 2:
            stage = "Developing"
        else:
            stage = "Emerging"

        # Exact-category negative evidence caps automatic mastery. This is deliberately
        # conservative: absence of errors alone never creates mastery.
        if record["category"] in recent_error_categories and stage in {"Stable", "Mastered"}:
            stage = "Developing"

        output.append(
            {
                "category": record["category"],
                "stage": stage,
                "evidence_count": count,
                "series_count": series_count,
                "recent_count": int(record["recent_count"]),
                "last_seen": record["last_seen"],
                "example": record["example"],
                "explanation": record["explanation"],
            }
        )

    stage_rank = {"Mastered": 0, "Stable": 1, "Developing": 2, "Emerging": 3}
    output.sort(
        key=lambda x: (
            stage_rank.get(x["stage"], 9),
            -int(x["evidence_count"]),
        )
    )
    return output


def _revision_wins(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_series: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_series[int(row["series_id"] or row["id"])].append(row)

    wins: list[dict[str, Any]] = []
    for series_id, series_rows in by_series.items():
        ordered = sorted(series_rows, key=lambda row: int(row["revision_no"] or 1))
        if len(ordered) < 2:
            continue
        first = ordered[0]
        latest = ordered[-1]
        delta = round(float(latest["overall"]) - float(first["overall"]), 1)

        first_errors = len(_safe_json(first["errors_json"], []))
        latest_errors = len(_safe_json(latest["errors_json"], []))
        error_delta = latest_errors - first_errors

        if delta <= 0 and error_delta >= 0:
            continue

        wins.append(
            {
                "series_id": series_id,
                "revisions": len(ordered),
                "overall_delta": delta,
                "error_delta": error_delta,
                "latest_id": int(latest["id"]),
                "latest_date": str(latest["created_at"]),
            }
        )

    wins.sort(
        key=lambda item: (
            item["latest_date"],
            item["overall_delta"],
            -item["error_delta"],
        ),
        reverse=True,
    )
    return wins


def get_learning_memory() -> dict[str, Any]:
    rows = _essay_rows()

    patterns = _error_patterns(rows)
    strengths = _strength_patterns(rows, patterns)
    wins = _revision_wins(rows)
    review_cue = _review_cue(rows, patterns)

    active_focus = next(
        (item for item in patterns if item["status"] in {"recurring", "new", "watch", "improving"}),
        None,
    )

    return {
        "language": active_profile().code,
        "essay_count": len({int(row["series_id"] or row["id"]) for row in rows}),
        "revision_count": len(rows),
        "focus": active_focus,
        "patterns": patterns[:12],
        "strengths": strengths[:12],
        "revision_wins": wins[:8],
        "review_cue": review_cue,
        "mastery_vocabulary": ["Emerging", "Developing", "Stable", "Mastered"],
        "mastery_note": (
            "Internal practice stability derived from repeated evidence. "
            "It is not a CEFR, TOEIC, IELTS or HSK equivalence."
        ),
    }


def get_review_cue(essay_id: int | None = None) -> dict[str, Any]:
    rows = _essay_rows()
    patterns = _error_patterns(rows)
    return _review_cue(rows, patterns, essay_id=essay_id)
