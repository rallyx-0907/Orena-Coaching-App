from __future__ import annotations

from writing_coach.languages.chinese.orthography import build_chinese_orthography


def test_builds_generic_chinese_units_from_verified_stroke_owner() -> None:
    result = build_chinese_orthography("学习")

    assert result["script"] == "han"
    assert [unit["surface"] for unit in result["units"]] == ["学", "习"]
    assert result["units"][0]["facts"]["stroke_count"]["value"] == 8
    assert (
        result["units"][0]["facts"]["stroke_count"]["provenance"]["source"]
        == "make-me-a-hanzi"
    )
    assert (
        result["units"][0]["facts"]["stroke_order"]["value"]["representation"]
        == "svg-paths"
    )


def test_preserves_polyphonic_readings_and_context_bindings_without_collapsing_them() -> None:
    result = build_chinese_orthography(
        "银行",
        readings={
            "行": [
                {
                    "value": "xíng",
                    "notation": "pinyin",
                    "bindings": [{"kind": "sense", "id": "bank"}],
                },
                {
                    "value": "háng",
                    "notation": "pinyin",
                    "bindings": [{"kind": "context", "text": "银行"}],
                },
            ]
        },
    )

    readings = result["units"][1]["readings"]
    assert [reading["value"] for reading in readings] == ["xíng", "háng"]
    assert readings[0]["bindings"] != readings[1]["bindings"]


def test_does_not_invent_radical_components_or_etymology() -> None:
    result = build_chinese_orthography("学")
    facts = result["units"][0]["facts"]

    assert "radical" not in facts
    assert "components" not in facts
    assert "etymology" not in facts
