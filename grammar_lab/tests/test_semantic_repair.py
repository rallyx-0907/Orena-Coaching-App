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


def _raw() -> dict:
    return _answer(copy.deepcopy(CANNED_V04))


def test_can_target_repair_only_accepts_the_small_structural_failure_surface() -> None:
    assert can_target_repair([
        _Issue("example.formula_role_missing"),
        _Issue("personal_production.rule_rejects_sample"),
    ])
    assert not can_target_repair([_Issue("quick_practice.blank_invalid")])
    assert not can_target_repair([])


def test_patch_schema_fixes_formula_order_lengths_to_the_candidate() -> None:
    schema = patch_schema(_raw())
    order = schema["properties"]["formula_order"]["properties"]
    assert order["affirmative"]["minItems"] == order["affirmative"]["maxItems"] == 2
    assert order["negative"]["minItems"] == order["negative"]["maxItems"] == 3
    assert order["question"]["maxItems"] == 0


def test_apply_patch_reorders_existing_slots_marks_original_slot_optional_and_replaces_spans() -> None:
    data = _raw()
    original = copy.deepcopy(data)
    patch = {
        "formula_order": {
            "affirmative": [1, 0],
            "negative": [0, 1, 2],
            "question": [],
        },
        "make_optional": {
            "affirmative": [0],
            "negative": [],
            "question": [],
        },
        "examples": [
            {"index": i, "spans": example["spans"]}
            for i, example in enumerate(data["examples"])
        ],
        "pattern_rule": data["personal_production"]["pattern_rule"],
    }

    repaired = apply_patch(data, patch)

    assert data == original
    assert [slot["role"] for slot in repaired["formula"]] == ["verb", "subject"]
    # optional index refers to the original formula, so subject stays optional after reordering.
    assert repaired["formula"][1]["role"] == "subject"
    assert repaired["formula"][1]["optional"] is True


def test_apply_patch_rejects_span_text_not_present_in_the_unchanged_example() -> None:
    data = _raw()
    patch = {
        "formula_order": {
            "affirmative": [0, 1],
            "negative": [0, 1, 2],
            "question": [],
        },
        "make_optional": {"affirmative": [], "negative": [], "question": []},
        "examples": [
            {"index": 0, "spans": [{"text": "NOT IN SENTENCE", "role": "subject"}]},
            {"index": 1, "spans": data["examples"][1]["spans"]},
            {"index": 2, "spans": data["examples"][2]["spans"]},
        ],
        "pattern_rule": data["personal_production"]["pattern_rule"],
    }
    with pytest.raises(ValueError, match="exact substring"):
        apply_patch(data, patch)


def test_generate_v04_uses_targeted_patch_before_regenerating_the_full_lesson(tmp_path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()
    bad = copy.deepcopy(CANNED_V04)
    bad["examples"][0]["spans"] = [
        span for span in bad["examples"][0]["spans"] if span["role"] != "subject"
    ]
    calls: list[str] = []

    patch = {
        "formula_order": {
            "affirmative": [0, 1],
            "negative": [0, 1, 2],
            "question": [],
        },
        "make_optional": {"affirmative": [], "negative": [], "question": []},
        "examples": [
            {"index": i, "spans": copy.deepcopy(example["spans"])}
            for i, example in enumerate(CANNED_V04["examples"])
        ],
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
