from __future__ import annotations

import copy

from grammar_lab.pipeline.generate import (
    assemble_generated_example,
    assemble_generated_personal_production,
    normalize_generated_question_word_frame,
    normalize_generated_structure,
)
from grammar_lab.pipeline.validate import LAB_ROOT, _Validation, pattern_rule_matches


def _slot(text: str, role: str, label: str) -> dict:
    return {"text": text, "role": role, "label": {"vi": label}, "optional": False, "options": []}


def _example(text: str, bindings: list[dict]) -> dict:
    return {
        "form": "question",
        "text": text,
        "bindings": bindings,
        "annotation": {"vi": "Từ để hỏi giữ nguyên vị trí của phần cần hỏi."},
        "translation": {"vi": "Câu hỏi mẫu."},
    }


def _candidate() -> dict:
    question = [
        _slot("S", "subject", "chủ ngữ"),
        _slot("V", "verb", "động từ"),
        _slot("O", "object", "phần được hỏi"),
    ]
    return {
        "formula": copy.deepcopy(question),
        "negative": [],
        "question": copy.deepcopy(question),
        "examples": [
            _example("你喜欢什么？", [
                {"slot_index": 0, "text": "你"},
                {"slot_index": 1, "text": "喜欢"},
                {"slot_index": 2, "text": "什么"},
            ]),
            _example("他找谁？", [
                {"slot_index": 0, "text": "他"},
                {"slot_index": 1, "text": "找"},
                {"slot_index": 2, "text": "谁"},
            ]),
            _example("你在哪儿工作？", [
                {"slot_index": 0, "text": "你"},
                {"slot_index": 1, "text": "在哪儿工作"},
                {"slot_index": 2, "text": "哪儿"},
            ]),
        ],
        "personal_production": {
            "target_form": "question",
            "pattern_rule": {
                "ordered": True,
                "slots": [{"slot_index": 2, "any_of": ["什么", "谁", "哪儿"], "regex": ""}],
            },
        },
    }


def test_question_word_frame_repairs_locative_overlap_without_reinterpreting_as_object() -> None:
    data = _candidate()
    original = copy.deepcopy(data)
    out = normalize_generated_question_word_frame(data, True)

    assert data == original
    assert [slot["text"] for slot in out["question"]] == ["…", "疑问词", "…"]
    assert [slot["role"] for slot in out["question"]] == ["other", "other", "other"]
    assert [slot["optional"] for slot in out["question"]] == [True, False, True]
    assert out["examples"][0]["bindings"] == [
        {"slot_index": 0, "text": "你喜欢"},
        {"slot_index": 1, "text": "什么"},
    ]
    assert out["examples"][1]["bindings"] == [
        {"slot_index": 0, "text": "他找"},
        {"slot_index": 1, "text": "谁"},
    ]
    assert out["examples"][2]["bindings"] == [
        {"slot_index": 0, "text": "你在"},
        {"slot_index": 1, "text": "哪儿"},
        {"slot_index": 2, "text": "工作"},
    ]
    assert out["personal_production"]["pattern_rule"]["slots"] == [
        {"slot_index": 1, "any_of": ["什么", "谁", "哪儿"], "regex": ""}
    ]

    normalized = normalize_generated_structure(out, True)
    pattern = {"formula": normalized["formula"], "variants": {"question": normalized["question"]}}
    for index, example in enumerate(normalized["examples"]):
        _assembled, problems = assemble_generated_example(
            example, pattern, True, lambda value: value, index,
        )
        assert problems == []


def test_question_word_frame_is_fail_closed_without_overlap_witness() -> None:
    data = _candidate()
    data["examples"][2]["bindings"][1]["text"] = "工作"
    assert normalize_generated_question_word_frame(data, True) == data


def test_question_word_frame_is_fail_closed_for_non_question_production_rules() -> None:
    data = _candidate()
    data["personal_production"]["pattern_rule"]["slots"] = [
        {"slot_index": 1, "any_of": ["喜欢", "找", "工作"], "regex": ""},
    ]
    assert normalize_generated_question_word_frame(data, True) == data


def _main_formula_candidate() -> dict:
    data = _candidate()
    data["question"] = []
    for example in data["examples"]:
        example["form"] = "affirmative"
    data["examples"][0]["text"] = "你买什么？"
    data["examples"][0]["bindings"][1]["text"] = "买"
    data["examples"][1]["text"] = "谁是老师？"
    data["examples"][1]["bindings"] = [
        {"slot_index": 0, "text": "谁"},
        {"slot_index": 1, "text": "是"},
        {"slot_index": 2, "text": "老师"},
    ]
    data["personal_production"] = {
        "target_form": "affirmative",
        "sample": "你买什么？",
        "pattern_rule": {"ordered": True, "slots": [
            {"slot_index": 1, "any_of": ["买", "吃", "喝", "看", "要"], "regex": ""},
            {"slot_index": 2, "any_of": ["什么"], "regex": ""},
        ]},
    }
    return data


def test_main_formula_question_frame_preserves_lexical_production_constraints() -> None:
    data = _main_formula_candidate()
    original = copy.deepcopy(data)
    out = normalize_generated_question_word_frame(data, True)
    assert data == original
    assert out["question"] == []
    assert [slot["role"] for slot in out["formula"]] == ["other"] * 3
    assert out["examples"][1]["bindings"] == [
        {"slot_index": 1, "text": "谁"},
        {"slot_index": 2, "text": "是老师"},
    ]
    rules = out["personal_production"]["pattern_rule"]["slots"]
    assert [rule["slot_index"] for rule in rules] == [0, 1]
    assert [rule["any_of"] for rule in rules] == [
        rule["any_of"] for rule in original["personal_production"]["pattern_rule"]["slots"]
    ]
    normalized = normalize_generated_structure(out, True)
    assembled = []
    for index, example in enumerate(normalized["examples"]):
        result, problems = assemble_generated_example(example, {"formula": normalized["formula"]}, True, lambda value: value, index)
        assert problems == []
        assembled.append(result)
    production_raw = {**out["personal_production"], "prompt": "test", "placeholder": "你买……"}
    production, problems = assemble_generated_personal_production(
        production_raw, {"formula": out["formula"]}, True, lambda value: value,
    )
    assert problems == []
    matchers = [rule["any_of"] for rule in production["pattern_rule"]["slots"]]
    assert pattern_rule_matches(True, matchers, "你买什么？", True)
    assert not pattern_rule_matches(True, matchers, "你买茶？", True)
    assert not pattern_rule_matches(True, matchers, "你找什么？", True)
    validation = _Validation("zh", LAB_ROOT)
    point = {"pattern": {"formula": out["formula"]}, "examples": assembled, "personal_production": production}
    validation.check_examples_v04("test.json", point)
    validation.check_personal_production_v04("test.json", point)
    assert validation.report.ok, validation.report.issues
    assert normalize_generated_question_word_frame(out, True) == out


def test_main_formula_question_frame_fails_closed_without_exact_sample_witness() -> None:
    data = _main_formula_candidate()
    data["personal_production"]["sample"] = "你吃什么？"
    assert normalize_generated_question_word_frame(data, True) == data


def test_main_formula_question_frame_fails_closed_for_overlapping_production_constraint() -> None:
    data = _main_formula_candidate()
    data["personal_production"]["sample"] = "你在哪儿工作？"
    data["personal_production"]["pattern_rule"]["slots"][0]["any_of"] = ["在哪儿工作"]
    assert normalize_generated_question_word_frame(data, True) == data


def test_main_formula_question_frame_fails_closed_for_repeated_interrogative() -> None:
    data = _main_formula_candidate()
    data["examples"][0]["text"] = "你买什么，吃什么？"
    assert normalize_generated_question_word_frame(data, True) == data


def test_main_formula_question_frame_fails_closed_when_rules_collapse_to_same_slot() -> None:
    data = _main_formula_candidate()
    data["personal_production"]["pattern_rule"]["slots"].insert(
        0, {"slot_index": 0, "any_of": ["你"], "regex": ""},
    )
    assert normalize_generated_question_word_frame(data, True) == data
