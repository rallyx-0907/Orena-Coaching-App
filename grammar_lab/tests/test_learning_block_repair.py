from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import httpx

from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.generate import (
    apply_generation_learning_patch,
    can_repair_generation_learning_blocks,
    can_repair_generation_structure,
    generation_learning_block_repair_issues,
    generation_structure_repair_issues,
)
from grammar_lab.pipeline.validate import validate_lang
from grammar_lab.tests.test_generate import CANNED_V04, _answer, _v04_lab, make_generator


def _issue(code: str, path: str = "x") -> SimpleNamespace:
    return SimpleNamespace(code=code, path=path, message=code)


def test_formula_joiner_is_routed_to_structure_repair() -> None:
    issues = [_issue("formula.slot_has_joiner", "pattern.formula[1].text")]
    assert can_repair_generation_structure(issues)
    assert generation_structure_repair_issues(issues) == issues


def test_learning_block_repair_selects_only_bounded_content_codes() -> None:
    issues = [
        _issue("common_mistake.same_wrong_right", "common_mistakes[0]"),
        _issue("quick_practice.blank_invalid", "quick_practice[0].q"),
        _issue("generation.binding_text_order", "examples[0].bindings"),
    ]
    selected = generation_learning_block_repair_issues(issues)
    assert [issue.code for issue in selected] == [
        "common_mistake.same_wrong_right",
        "quick_practice.blank_invalid",
    ]
    assert can_repair_generation_learning_blocks(issues)


def test_apply_learning_patch_changes_only_requested_blocks() -> None:
    data = _answer(copy.deepcopy(CANNED_V04))
    before = copy.deepcopy(data)
    replacement = copy.deepcopy(CANNED_V04["quick_practice"])
    replacement[0]["q"] = "She ___ every day."

    out = apply_generation_learning_patch(data, {"quick_practice": replacement})

    assert data == before
    assert out["quick_practice"] == replacement
    assert out["formula"] == before["formula"]
    assert out["examples"] == before["examples"]
    assert out["common_mistakes"] == before["common_mistakes"]
    assert out["personal_production"] == before["personal_production"]


def test_generate_repairs_common_mistake_and_quick_practice_without_rewriting_lesson(tmp_path) -> None:
    lab = _v04_lab(tmp_path)
    lab.write()

    bad = copy.deepcopy(CANNED_V04)
    bad["common_mistakes"][0]["wrong"] = bad["common_mistakes"][0]["right"]
    bad["quick_practice"][0]["q"] = "He goes to school."

    good_answer = _answer(copy.deepcopy(CANNED_V04))
    patch = {
        "common_mistakes": copy.deepcopy(good_answer["common_mistakes"]),
        "quick_practice": copy.deepcopy(good_answer["quick_practice"]),
    }
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent = json.loads(request.content)
        tool_name = sent["tool_choice"]["name"]
        calls.append(tool_name)
        if tool_name == "emit_grammar_point_v04":
            payload = _answer(bad)
        elif tool_name == "emit_grammar_point_v04_learning_patch":
            payload = patch
        else:
            raise AssertionError(tool_name)
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": tool_name, "input": payload}],
            "usage": {"input_tokens": 100, "output_tokens": 100},
        })

    outcome = make_generator(lab.root, httpx.MockTransport(handler)).generate("en.alpha")

    assert outcome.status == "written", outcome.reason
    assert calls == ["emit_grammar_point_v04", "emit_grammar_point_v04_learning_patch"]
    point = load_point("en", "en.alpha", lab.root)
    assert point["header"]["summary"] == CANNED_V04["summary"]
    assert [example["text"] for example in point["examples"]] == [
        example["text"] for example in CANNED_V04["examples"]
    ]
    assert validate_lang("en", lab.root).ok
