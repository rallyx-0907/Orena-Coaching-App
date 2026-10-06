from __future__ import annotations

import copy

from grammar_lab.pipeline.generate import (
    assemble_generated_example,
    normalize_generated_structure,
)


def _slot(text: str, role: str, *, options: list[str] | None = None) -> dict:
    return {
        "text": text,
        "role": role,
        "label": {"vi": text},
        "optional": False,
        "options": [{"text": value} for value in (options or [])],
    }


def _candidate(*, proven_optional_suffix: bool = True) -> dict:
    negator = _slot(
        "没(有)" if proven_optional_suffix else "没有",
        "marker",
        options=["没", "没有"] if proven_optional_suffix else ["没有"],
    )
    negative = [
        _slot("S", "subject"),
        negator,
        _slot("V", "verb"),
        _slot("O", "object"),
    ]
    return {
        "formula": [_slot("S", "subject"), _slot("V", "verb"), _slot("O", "object")],
        "negative": negative,
        "question": [],
        "examples": [
            {
                "text": "她没有妹妹。",
                "form": "negative",
                "bindings": [
                    {"slot_index": 0, "text": "她"},
                    {"slot_index": 1, "text": "没有"},
                    {"slot_index": 2, "text": "有"},
                    {"slot_index": 3, "text": "妹妹"},
                ],
                "annotation": {"vi": "Cô ấy không có em gái."},
                "translation": {"vi": "Cô ấy không có em gái."},
            }
        ],
        "personal_production": {
            "target_form": "negative",
            "pattern_rule": {"ordered": True, "slots": []},
        },
    }


def test_zh_optional_suffix_binding_uses_short_form_when_next_slot_realizes_suffix() -> None:
    data = _candidate()
    original = copy.deepcopy(data)

    out = normalize_generated_structure(data, True)

    assert data == original
    assert out["examples"][0]["bindings"] == [
        {"slot_index": 0, "text": "她"},
        {"slot_index": 1, "text": "没"},
        {"slot_index": 2, "text": "有"},
        {"slot_index": 3, "text": "妹妹"},
    ]

    pattern = {"formula": out["formula"], "variants": {"negative": out["negative"]}}
    _assembled, problems = assemble_generated_example(
        out["examples"][0], pattern, True, lambda value: value, 0,
    )
    assert problems == []


def test_zh_optional_suffix_binding_stays_fail_closed_without_formula_proof() -> None:
    data = _candidate(proven_optional_suffix=False)
    assert normalize_generated_structure(data, True) == data
