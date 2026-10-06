from __future__ import annotations

import copy

from grammar_lab.pipeline.generate import assemble_generated_example, normalize_generated_structure


def _pronoun_candidate() -> dict:
    return {
        "formula": [
            {
                "text": "人称代词",
                "role": "subject",
                "label": "personal pronoun",
                "optional": False,
                "options": [{"text": "我"}, {"text": "你"}, {"text": "您"}],
            }
        ],
        "negative": [],
        "question": [],
        "examples": [
            {
                "text": "我是学生。",
                "form": "affirmative",
                "bindings": [{"slot_index": 0, "text": "我"}],
                "annotation": "pronoun subject",
                "translation": "I am a student.",
            },
            {
                "text": "您贵姓？",
                "form": "question",
                "bindings": [{"slot_index": 0, "text": "您"}],
                "annotation": "polite pronoun subject",
                "translation": "May I ask your surname?",
            },
        ],
        "personal_production": {
            "target_form": "affirmative",
            "pattern_rule": {
                "ordered": True,
                "slots": [{"slot_index": 0, "any_of": ["我", "你", "您"], "regex": ""}],
            },
        },
    }


def test_missing_question_variant_reuses_proven_base_formula_for_lexical_slot() -> None:
    data = _pronoun_candidate()
    original = copy.deepcopy(data)

    out = normalize_generated_structure(data, True)

    assert out["question"] == out["formula"]
    pattern = {"formula": out["formula"], "variants": {"question": out["question"]}}
    example, problems = assemble_generated_example(
        out["examples"][1], pattern, True, lambda value: value, 1
    )
    assert problems == []
    assert example["spans"] == [{"start": 0, "end": 1, "role": "subject"}]
    assert data == original


def test_missing_question_variant_stays_fail_closed_when_required_binding_is_missing() -> None:
    data = _pronoun_candidate()
    data["formula"].append(
        {
            "text": "地点",
            "role": "place",
            "label": "place",
            "optional": False,
            "options": [],
        }
    )

    out = normalize_generated_structure(data, True)

    assert out["question"] == []


def test_missing_question_variant_stays_fail_closed_for_form_sensitive_formula() -> None:
    data = _pronoun_candidate()
    data["formula"][0]["role"] = "verb"

    out = normalize_generated_structure(data, True)

    assert out["question"] == []
