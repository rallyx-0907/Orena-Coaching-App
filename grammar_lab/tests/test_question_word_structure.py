from __future__ import annotations

import copy

from grammar_lab.pipeline.generate import (
    assemble_generated_example,
    normalize_generated_question_word_frame,
    normalize_generated_structure,
)


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
