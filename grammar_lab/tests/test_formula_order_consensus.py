from __future__ import annotations

import copy

from grammar_lab.pipeline.generate import normalize_generated_formula_order


def _slot(text: str, role: str) -> dict:
    return {"text": text, "role": role}


def test_formula_order_reorders_when_complete_unique_examples_agree() -> None:
    data = {
        "formula": [
            _slot("S", "subject"),
            _slot("V", "verb"),
            _slot("了/过", "particle"),
            _slot("number", "other"),
            _slot("次/遍/趟", "classifier"),
            _slot("O", "object"),
        ],
        "negative": [],
        "question": [],
        "examples": [
            {
                "text": "我这本书看了三遍。",
                "form": "affirmative",
                "bindings": [
                    {"slot_index": 0, "text": "我"},
                    {"slot_index": 1, "text": "看"},
                    {"slot_index": 2, "text": "了"},
                    {"slot_index": 3, "text": "三"},
                    {"slot_index": 4, "text": "遍"},
                    {"slot_index": 5, "text": "这本书"},
                ],
            },
            {
                "text": "他那部电影看过两次。",
                "form": "affirmative",
                "bindings": [
                    {"slot_index": 0, "text": "他"},
                    {"slot_index": 1, "text": "看"},
                    {"slot_index": 2, "text": "过"},
                    {"slot_index": 3, "text": "两"},
                    {"slot_index": 4, "text": "次"},
                    {"slot_index": 5, "text": "那部电影"},
                ],
            },
        ],
        "personal_production": {
            "target_form": "affirmative",
            "pattern_rule": {"ordered": True, "slots": []},
        },
    }

    out = normalize_generated_formula_order(copy.deepcopy(data), True)

    assert [slot["text"] for slot in out["formula"]] == [
        "S", "O", "V", "了/过", "number", "次/遍/趟",
    ]


def test_formula_order_does_not_merge_partial_examples_into_a_reorder() -> None:
    data = {
        "formula": [_slot("A", "subject"), _slot("B", "verb"), _slot("C", "object")],
        "negative": [],
        "question": [],
        "examples": [
            {
                "text": "c a",
                "form": "affirmative",
                "bindings": [
                    {"slot_index": 0, "text": "a"},
                    {"slot_index": 2, "text": "c"},
                ],
            },
            {
                "text": "a b",
                "form": "affirmative",
                "bindings": [
                    {"slot_index": 0, "text": "a"},
                    {"slot_index": 1, "text": "b"},
                ],
            },
        ],
        "personal_production": {
            "target_form": "affirmative",
            "pattern_rule": {"ordered": True, "slots": []},
        },
    }

    out = normalize_generated_formula_order(copy.deepcopy(data), False)

    assert out == data


def test_formula_order_stays_fail_closed_when_repeated_surfaces_allow_multiple_orders() -> None:
    data = {
        "formula": [_slot("first x", "subject"), _slot("second x", "object"), _slot("Y", "verb")],
        "negative": [],
        "question": [],
        "examples": [
            {
                "text": "x y x",
                "form": "affirmative",
                "bindings": [
                    {"slot_index": 0, "text": "x"},
                    {"slot_index": 1, "text": "x"},
                    {"slot_index": 2, "text": "y"},
                ],
            }
        ],
        "personal_production": {
            "target_form": "affirmative",
            "pattern_rule": {"ordered": True, "slots": []},
        },
    }

    out = normalize_generated_formula_order(copy.deepcopy(data), False)

    assert out == data
