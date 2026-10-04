from __future__ import annotations

import copy
import json

import httpx
import pytest

from grammar_lab.pipeline.semantic_repair import (
    apply_patch,
    can_target_repair,
    patch_schema,
)
from grammar_lab.tests.test_generate import (
    CANNED_V04,
    _answer,
    _v04_lab,
    make_generator,
)


class _Issue:
    def __init__(self, code: str, path: str = "x", message: str = "bad") -> None:
        self.code = code
        self.path = path
        self.message = message


def _assembled_point() -> dict:
    return {
        "pattern": {
            "formula": [
                {"text": "He / She / It", "role": "subject", "optional": False, "options": []},
                {"text": "V-s", "role": "verb", "optional": False, "options": []},
            ],
            "variants": {
                "negative": [
                    {"text": "He / She / It", "role": "subject", "optional": False, "options": []},
                    {"text": "doesn't", "role": "aux", "optional": False, "options": []},
                    {"text": "V", "role": "verb", "optional": False, "options": []},
                ],
            },
        },
        "examples": [
            {
                "text": "She works in a bank.",
                "form": "affirmative",
                "spans": [
                    {"start": 0, "end": 3, "role": "subject"},
                    {"start": 4, "end": 9, "role": "verb"},
                ],
            },
            {
                "text": "He studies every day.",
                "form": "affirmative",
                "spans": [
                    {"start": 0, "end": 2, "role": "subject"},
                    {"start": 3, "end": 10, "role": "verb"},
                ],
            },
            {
                "text": "He doesn't like tea.",
                "form": "negative",
                "spans": [
                    {"start": 0, "end": 2, "role": "subject"},
                    {"start": 3, "end": 10, "role": "aux"},
                    {"start": 11, "end": 15, "role": "verb"},
                ],
            },
        ],
        "personal_production": {
            "target_form": "affirmative",
            "sample": {"text": "She reads a book."},
            "pattern_rule": {
                "ordered": True,
                "slots": [{"role": "verb", "regex": r"\b\w+(?:s|es)\b"}],
            },
        },
    }


def test_can_target_repair_only_accepts_the_small_structural_failure_surface() -> None:
    assert can_target_repair([
        _Issue("example.formula_role_missing"),
        _Issue("personal_production.rule_rejects_sample"),
    ])
    assert not can_target_repair([_Issue("quick_practice.blank_invalid")])
    assert not can_target_repair([])


def test_patch_schema_does_not_mistake_rule_rejects_example_for_span_repair() -> None:
    point = _assembled_point()
    issues = [
        _Issue(
            "personal_production.rule_rejects_example",
            "examples[0].text",
            "pattern rule did not match",
        )
    ]
    schema = patch_schema(point, issues)
    examples = schema["properties"]["example_spans"]

    assert examples["minItems"] == examples["maxItems"] == 0


def test_patch_schema_only_requires_affected_examples() -> None:
    point = _assembled_point()
    issues = [_Issue("example.formula_role_missing", "examples[1].spans")]
    schema = patch_schema(point, issues)
    examples = schema["properties"]["example_spans"]

    assert examples["minItems"] == examples["maxItems"] == 1
    assert examples["items"]["properties"]["index"]["enum"] == [1]
    assert schema["properties"]["formula_orders"]["maxItems"] == 3


def test_apply_patch_reorders_formula_and_replaces_only_affected_spans() -> None:
    point = _assembled_point()
    original = copy.deepcopy(point)
    issues = [_Issue("example.span_slot_mismatch", "examples[0].spans")]
    patch = {
        "formula_orders": [{"form": "affirmative", "order": [1, 0]}],
        "make_optional": [{"form": "affirmative", "slot_index": 1}],
        "example_spans": [{
            "index": 0,
            "spans": [
                {"text": "works", "role": "verb"},
                {"text": "She", "role": "subject"},
            ],
        }],
        "pattern_rule": None,
    }

    repaired = apply_patch(point, patch, issues)

    assert point == original
    assert [slot["role"] for slot in repaired["pattern"]["formula"]] == ["verb", "subject"]
    assert repaired["pattern"]["formula"][1]["optional"] is True
    assert repaired["examples"][1] == original["examples"][1]
    assert repaired["examples"][0]["spans"] == [
        {"start": 4, "end": 9, "role": "verb"},
        {"start": 0, "end": 3, "role": "subject"},
    ]


def test_apply_patch_rejects_span_text_not_present_in_unchanged_example() -> None:
    point = _assembled_point()
    issues = [_Issue("example.formula_role_missing", "examples[0].spans")]
    patch = {
        "formula_orders": [],
        "make_optional": [],
        "example_spans": [{
            "index": 0,
            "spans": [{"text": "NOT IN SENTENCE", "role": "subject"}],
        }],
        "pattern_rule": None,
    }
    with pytest.raises(ValueError, match="exact substring"):
        apply_patch(point, patch, issues)


def test_generate_v04_uses_issue_local_patch_on_assembled_candidate(tmp_path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    bad = copy.deepcopy(CANNED_V04)
    # v13 makes example/formula alignment structural. Keep those bindings
    # valid and force a remaining semantic failure in personal production.
    bad["personal_production"]["pattern_rule"]["slots"][0]["regex"] = r"\bNEVER\b"
    calls: list[str] = []

    patch = {
        "formula_orders": [],
        "make_optional": [],
        "example_spans": [],
        "pattern_rule": copy.deepcopy(CANNED_V04["personal_production"]["pattern_rule"]),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        tool_name = sent["tool_choice"]["name"]
        calls.append(tool_name)
        if tool_name == "emit_grammar_point_v04":
            payload = _answer(bad)
        elif tool_name == "emit_grammar_point_v04_semantic_patch":
            payload = patch
        else:
            raise AssertionError(tool_name)
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": tool_name, "input": payload}],
            "usage": {"input_tokens": 100, "output_tokens": 100},
        })

    outcome = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")

    assert outcome.status == "written", outcome.reason
    assert calls == ["emit_grammar_point_v04", "emit_grammar_point_v04_semantic_patch"]
