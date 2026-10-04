"""Targeted structural repair for schema-v0.4 assembled grammar points.

The validator checks the assembled point, so repair must operate on that exact
representation too. Keeping repair on the validator-facing object avoids a
raw-vs-assembled mismatch (sanitized/recovered spans and reordered formulas)
and lets the provider return only the examples/forms implicated by the issues.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from grammar_lab.pipeline.llm_client import LLMClient, LLMResult

FORMS = ("affirmative", "negative", "question")
ROLES = (
    "subject", "verb", "aux", "object", "complement", "classifier",
    "time", "place", "marker", "particle", "connector", "other",
)
MAX_RULE_SLOTS = 4
MAX_ANY_OF = 8
TARGETED_REPAIR_MAX_TOKENS = 1800
# One precise patch per full candidate. If it fails, let the existing full
# semantic retry produce a fresh candidate rather than stacking repair spend.
TARGETED_REPAIR_ATTEMPTS = 1

_REPAIRABLE_CODES = {
    "example.formula_role_missing",
    "example.span_role_not_in_formula",
    "example.span_slot_mismatch",
    "personal_production.rule_invalid",
    "personal_production.rule_role_not_in_formula",
    "personal_production.rule_rejects_sample",
    "personal_production.rule_rejects_example",
}
_EXAMPLE_PATH = re.compile(r"^examples\[(\d+)\]")


def can_target_repair(issues: list[Any]) -> bool:
    """True only when every failure belongs to the bounded structural surface."""
    return bool(issues) and all(getattr(issue, "code", "") in _REPAIRABLE_CODES for issue in issues)


def _formula_slots(point: dict[str, Any], form: str) -> list[dict[str, Any]]:
    if form == "affirmative":
        return point["pattern"]["formula"]
    return point["pattern"].get("variants", {}).get(form, [])


def _slot_view(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": slot.get("text", ""),
        "role": slot.get("role"),
        "optional": bool(slot.get("optional")),
        "options": [option.get("text", "") for option in slot.get("options") or []],
    }


def _affected_example_indexes(issues: list[Any]) -> list[int]:
    """Examples whose own span/form annotations need repair.

    Some personal-production diagnostics deliberately point at an example text
    that the rule failed to match (for example
    personal_production.rule_rejects_example at examples[0].text). That path
    is evidence for the rule failure, not a request to rewrite the example's
    spans, so only example.* diagnostics select example patches here.
    """
    indexes: set[int] = set()
    for issue in issues:
        if not str(getattr(issue, "code", "")).startswith("example."):
            continue
        match = _EXAMPLE_PATH.match(getattr(issue, "path", ""))
        if match:
            indexes.add(int(match.group(1)))
    return sorted(indexes)


def _example_view(example: dict[str, Any], index: int) -> dict[str, Any]:
    text = example["text"]
    return {
        "index": index,
        "text": text,
        "form": example["form"],
        "spans": [
            {"text": text[span["start"]:span["end"]], "role": span["role"]}
            for span in example.get("spans", [])
        ],
    }


def _context(point: dict[str, Any], issues: list[Any], point_id: str) -> dict[str, Any]:
    affected = _affected_example_indexes(issues)
    production = point["personal_production"]
    target_form = production["target_form"]
    return {
        "point_id": point_id,
        "issues": [
            {"code": issue.code, "path": issue.path, "message": issue.message}
            for issue in issues[:12]
        ],
        "formulas": {
            form: [_slot_view(slot) for slot in _formula_slots(point, form)]
            for form in FORMS
        },
        "affected_examples": [
            _example_view(point["examples"][index], index)
            for index in affected
        ],
        "personal_production": {
            "target_form": target_form,
            "sample": production["sample"]["text"],
            "pattern_rule": production["pattern_rule"],
            "target_examples": [
                example["text"] for example in point["examples"]
                if example["form"] == target_form
            ],
        },
    }


def _permutation_schema(length: int) -> dict[str, Any]:
    if length == 0:
        return {"type": "array", "maxItems": 0}
    return {
        "type": "array",
        "minItems": length,
        "maxItems": length,
        "uniqueItems": True,
        "items": {"type": "integer", "minimum": 0, "maximum": length - 1},
    }


def patch_schema(point: dict[str, Any], issues: list[Any]) -> dict[str, Any]:
    affected = _affected_example_indexes(issues)
    span = {
        "type": "object",
        "additionalProperties": False,
        "required": ["text", "role"],
        "properties": {
            "text": {"type": "string", "minLength": 1},
            "role": {"enum": list(ROLES)},
        },
    }
    formula_order = {
        "type": "object",
        "additionalProperties": False,
        "required": ["form", "order"],
        "properties": {
            "form": {"enum": list(FORMS)},
            "order": {"type": "array", "items": {"type": "integer", "minimum": 0}},
        },
    }
    optional = {
        "type": "object",
        "additionalProperties": False,
        "required": ["form", "slot_index"],
        "properties": {
            "form": {"enum": list(FORMS)},
            "slot_index": {"type": "integer", "minimum": 0},
        },
    }
    example_patch = {
        "type": "object",
        "additionalProperties": False,
        "required": ["index", "spans"],
        "properties": {
            "index": {"enum": affected} if affected else {"type": "integer"},
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
    pattern_rule = {
        "type": ["object", "null"],
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
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["formula_orders", "make_optional", "example_spans", "pattern_rule"],
        "properties": {
            "formula_orders": {
                "type": "array",
                "maxItems": len(FORMS),
                "items": formula_order,
            },
            "make_optional": {
                "type": "array",
                "items": optional,
            },
            "example_spans": {
                "type": "array",
                "minItems": len(affected),
                "maxItems": len(affected),
                "items": example_patch,
            },
            "pattern_rule": pattern_rule,
        },
    }


def _resolve_exact_spans(text: str, raw_spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve patch substrings left-to-right; text itself is never rewritten."""
    position = 0
    spans: list[dict[str, Any]] = []
    for raw in raw_spans:
        needle = raw["text"]
        start = text.find(needle, position)
        if start < 0:
            # Allow an earlier occurrence only when it does not overlap already
            # resolved spans; this handles repeated words without guessing.
            start = text.find(needle)
        if start < 0:
            raise ValueError(f"span {needle!r} is not an exact substring")
        end = start + len(needle)
        if any(not (end <= item["start"] or start >= item["end"]) for item in spans):
            raise ValueError(f"overlapping span {needle!r}")
        spans.append({"start": start, "end": end, "role": raw["role"]})
        position = end
    return spans


def _normalize_pattern_rule(raw: dict[str, Any]) -> dict[str, Any]:
    slots: list[dict[str, Any]] = []
    for raw_slot in raw["slots"]:
        values = list(raw_slot.get("any_of") or [])
        regex = str(raw_slot.get("regex") or "")
        if bool(values) == bool(regex):
            raise ValueError("pattern rule slot needs exactly one matcher")
        if len(values) > MAX_ANY_OF:
            raise ValueError("pattern rule any_of exceeds bound")
        slot = {"role": raw_slot["role"]}
        if values:
            slot["any_of"] = values
        else:
            try:
                re.compile(regex)
            except re.error as exc:
                raise ValueError(f"invalid pattern regex: {exc}") from exc
            slot["regex"] = regex
        slots.append(slot)
    return {"ordered": bool(raw["ordered"]), "slots": slots}


def apply_patch(point: dict[str, Any], patch: dict[str, Any], issues: list[Any]) -> dict[str, Any]:
    """Apply a bounded patch directly to the validator-facing assembled point."""
    out = copy.deepcopy(point)
    affected = set(_affected_example_indexes(issues))

    seen_forms: set[str] = set()
    for operation in patch["formula_orders"]:
        form = operation["form"]
        if form in seen_forms:
            raise ValueError(f"duplicate formula order for {form}")
        seen_forms.add(form)
        slots = _formula_slots(out, form)
        order = operation["order"]
        if sorted(order) != list(range(len(slots))):
            raise ValueError(f"{form} formula_order is not a permutation")
        reordered = [slots[index] for index in order]
        if form == "affirmative":
            out["pattern"]["formula"] = reordered
        else:
            out["pattern"].setdefault("variants", {})[form] = reordered

    for operation in patch["make_optional"]:
        slots = _formula_slots(out, operation["form"])
        index = operation["slot_index"]
        if not 0 <= index < len(slots):
            raise ValueError("optional slot index out of range")
        slots[index]["optional"] = True

    seen_examples: set[int] = set()
    for example_patch in patch["example_spans"]:
        index = example_patch["index"]
        if index not in affected or index in seen_examples:
            raise ValueError("example patch index is not an affected unique example")
        seen_examples.add(index)
        text = out["examples"][index]["text"]
        out["examples"][index]["spans"] = _resolve_exact_spans(text, example_patch["spans"])

    if seen_examples != affected:
        raise ValueError("patch must return spans for every affected example")

    if patch["pattern_rule"] is not None:
        out["personal_production"]["pattern_rule"] = _normalize_pattern_rule(patch["pattern_rule"])
    return out


def request_patch(
    llm: LLMClient,
    *,
    point_id: str,
    target_lang: str,
    point: dict[str, Any],
    issues: list[Any],
) -> LLMResult:
    affected = _affected_example_indexes(issues)
    has_rule_issue = any(getattr(issue, "code", "").startswith("personal_production.") for issue in issues)
    system = """You repair structural annotations on an already assembled grammar lesson.
The validator errors below refer to exactly the formulas and spans you see here.
Do not rewrite any sentence, explanation, translation, title, or practice item.

Return one minimal JSON patch matching the schema.

- example_spans: return spans only for the affected example indexes requested. Each span text must be an exact substring of the unchanged sentence. Cover every non-optional formula role and use no role absent from that form.
- formula_orders: normally []. Use it only when the existing slots are correct but in the wrong order. order is a permutation of existing zero-based slot indexes.
- make_optional: normally []. Use only when the grammar genuinely permits that existing slot to be absent, never merely to silence a validator.
- pattern_rule: return null unless a personal_production error is listed. If needed, it must match the unchanged sample and at least one target-form example; use 1-4 grammar-bearing slots, max 8 closed-set any_of literals, and never enumerate open-class vocabulary.
- Preserve all content outside these structural annotations."""
    user = (
        f"Repair grammar point {point_id} ({target_lang}). "
        f"Affected example indexes: {affected}. "
        f"Personal-production repair required: {has_rule_issue}.\n"
        + json.dumps(_context(point, issues, point_id), ensure_ascii=False, separators=(",", ":"))
    )
    return llm.complete(
        system=system,
        user=user,
        json_schema=patch_schema(point, issues),
        schema_name="grammar_point_v04_semantic_patch",
        max_tokens=TARGETED_REPAIR_MAX_TOKENS,
    )
