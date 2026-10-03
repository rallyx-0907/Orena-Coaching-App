"""Targeted repair for schema-v0.4 grammar candidates.

Full point generation is expensive and mostly correct by the time deterministic
validation finds a formula/span or personal-production mismatch. This module
asks the provider for a small patch instead of rewriting translations,
explanations, comparisons, mistakes, and practice items that already passed.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from grammar_lab.pipeline.llm_client import LLMClient, LLMResult

FORMS = ("affirmative", "negative", "question")
ROLES = (
    "subject", "verb", "aux", "object", "complement", "classifier",
    "time", "place", "marker", "particle", "connector", "other",
)
MAX_RULE_SLOTS = 4
MAX_ANY_OF = 8
TARGETED_REPAIR_MAX_TOKENS = 2600
TARGETED_REPAIR_ATTEMPTS = 2

_REPAIRABLE_CODES = {
    "example.formula_role_missing",
    "example.span_role_not_in_formula",
    "example.span_slot_mismatch",
    "personal_production.rule_invalid",
    "personal_production.rule_role_not_in_formula",
    "personal_production.rule_rejects_sample",
    "personal_production.rule_rejects_example",
}


def can_target_repair(issues: list[Any]) -> bool:
    """True only when every failure belongs to the small patch surface."""
    return bool(issues) and all(getattr(issue, "code", "") in _REPAIRABLE_CODES for issue in issues)


def _formula_key(form: str) -> str:
    return "formula" if form == "affirmative" else form


def _formula_slots(data: dict[str, Any], form: str) -> list[dict[str, Any]]:
    return data.get(_formula_key(form)) or []


def _slot_view(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": slot.get("text", ""),
        "role": slot.get("role"),
        "optional": bool(slot.get("optional")),
        "options": [option.get("text", "") for option in slot.get("options") or []],
    }


def _context(data: dict[str, Any], issues: list[Any], point_id: str) -> dict[str, Any]:
    return {
        "point_id": point_id,
        "issues": [
            {"code": issue.code, "path": issue.path, "message": issue.message}
            for issue in issues[:12]
        ],
        "formulas": {
            form: [_slot_view(slot) for slot in _formula_slots(data, form)]
            for form in FORMS
        },
        "examples": [
            {
                "index": index,
                "text": example["text"],
                "form": example["form"],
                "spans": example.get("spans", []),
            }
            for index, example in enumerate(data["examples"])
        ],
        "personal_production": {
            "target_form": data["personal_production"]["target_form"],
            "sample": data["personal_production"]["sample"],
            "pattern_rule": data["personal_production"]["pattern_rule"],
        },
    }


def _index_array_schema(length: int) -> dict[str, Any]:
    if length == 0:
        return {"type": "array", "maxItems": 0}
    return {
        "type": "array",
        "minItems": length,
        "maxItems": length,
        "uniqueItems": True,
        "items": {"type": "integer", "minimum": 0, "maximum": length - 1},
    }


def _optional_index_schema(length: int) -> dict[str, Any]:
    if length == 0:
        return {"type": "array", "maxItems": 0}
    return {
        "type": "array",
        "maxItems": length,
        "uniqueItems": True,
        "items": {"type": "integer", "minimum": 0, "maximum": length - 1},
    }


def patch_schema(data: dict[str, Any]) -> dict[str, Any]:
    span = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "role"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "role": {"enum": list(ROLES)},
        },
    }
    example_patch = {
        "type": "object",
        "additionalProperties": False,
        "required": ["index", "spans"],
        "properties": {
            "index": {
                "type": "integer",
                "minimum": 0,
                "maximum": max(0, len(data["examples"]) - 1),
            },
            "spans": {"type": "array", "minItems": 1, "items": span},
        },
    }
    rule_slot = {
        "type": "object",
        "additionalProperties": False,
        "required": ["role", "any_of", "regex"],
        "properties": {
            "role": {"enum": list(ROLES)},
            "any_of": {
                "type": "array",
                "maxItems": MAX_ANY_OF,
                "items": {"type": "string", "minLength": 1},
            },
            "regex": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["formula_order", "make_optional", "examples", "pattern_rule"],
        "properties": {
            "formula_order": {
                "type": "object",
                "additionalProperties": False,
                "required": list(FORMS),
                "properties": {
                    form: _index_array_schema(len(_formula_slots(data, form)))
                    for form in FORMS
                },
            },
            "make_optional": {
                "type": "object",
                "additionalProperties": False,
                "required": list(FORMS),
                "properties": {
                    form: _optional_index_schema(len(_formula_slots(data, form)))
                    for form in FORMS
                },
            },
            "examples": {
                "type": "array",
                "minItems": len(data["examples"]),
                "maxItems": len(data["examples"]),
                "items": example_patch,
            },
            "pattern_rule": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ordered", "slots"],
                "properties": {
                    "ordered": {"type": "boolean"},
                    "slots": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_RULE_SLOTS,
                        "items": rule_slot,
                    },
                },
            },
        },
    }


def apply_patch(data: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply only bounded structural edits; reject a patch that changes text."""
    out = copy.deepcopy(data)

    for form in FORMS:
        slots = _formula_slots(out, form)
        order = patch["formula_order"][form]
        if sorted(order) != list(range(len(slots))):
            raise ValueError(f"{form} formula_order is not a permutation")
        for index in patch["make_optional"][form]:
            if not 0 <= index < len(slots):
                raise ValueError(f"{form} optional index out of range")
            slots[index]["optional"] = True

        reordered = [slots[index] for index in order]
        key = _formula_key(form)
        if key in out:
            out[key] = reordered
        elif reordered:
            raise ValueError(f"{form} formula does not exist")

    seen_indexes: set[int] = set()
    for example_patch in patch["examples"]:
        index = example_patch["index"]
        if index in seen_indexes or not 0 <= index < len(out["examples"]):
            raise ValueError("example indexes must be unique and in range")
        seen_indexes.add(index)
        text = out["examples"][index]["text"]
        occupied: list[tuple[int, int]] = []
        spans: list[dict[str, str]] = []
        cursor: dict[str, int] = {}
        for span in example_patch["spans"]:
            needle = span["text"]
            start = text.find(needle, cursor.get(needle, 0))
            if start < 0:
                raise ValueError(f"span {needle!r} is not an exact substring of example {index}")
            end = start + len(needle)
            cursor[needle] = end
            if any(not (end <= left or start >= right) for left, right in occupied):
                raise ValueError(f"overlapping span {needle!r} in example {index}")
            occupied.append((start, end))
            spans.append({"text": needle, "role": span["role"]})
        out["examples"][index]["spans"] = spans

    if seen_indexes != set(range(len(out["examples"]))):
        raise ValueError("patch must return spans for every example")

    out["personal_production"]["pattern_rule"] = patch["pattern_rule"]
    return out


def request_patch(
    llm: LLMClient,
    *,
    point_id: str,
    target_lang: str,
    data: dict[str, Any],
    issues: list[Any],
) -> LLMResult:
    system = """You repair only structural grammar annotations in an existing lesson candidate.
Do not rewrite lesson prose or sentence text.

Return one JSON patch matching the supplied schema.

Rules:
- formula_order is a permutation of the existing slot indexes for each form. Reorder only when needed.
- make_optional lists existing slot indexes that are legitimately omissible in that form (for example a zero article). Do not use optional merely to silence a missing span.
- examples must return spans for every example. Each span text must be an exact substring of that unchanged sentence and use only roles from that example's selected formula.
- Cover every non-optional formula role. Keep spans in natural sentence order.
- pattern_rule must match the unchanged personal-production sample and at least one unchanged example of its target form.
- Use at most four pattern-rule slots and at most eight any_of literals per slot. Never enumerate open-class vocabulary.
- Fix the reported validator issues and preserve everything outside this patch surface."""
    user = (
        f"Repair grammar point {point_id} ({target_lang}).\n"
        + json.dumps(_context(data, issues, point_id), ensure_ascii=False, separators=(",", ":"))
    )
    return llm.complete(
        system=system,
        user=user,
        json_schema=patch_schema(data),
        schema_name="grammar_point_v04_semantic_patch",
        max_tokens=TARGETED_REPAIR_MAX_TOKENS,
    )
