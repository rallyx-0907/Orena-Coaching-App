"""Task G: the `orthography` Vocabulary Card projection seam.

This module tests only the projection from the existing, already-tested
Chinese stroke-order capability (`tests/test_chinese_stroke_order.py`) into
the card `orthography` shape. It never re-verifies stroke-data correctness
itself.
"""

from __future__ import annotations

from writing_coach import orthography
from writing_coach.languages.chinese import stroke_order


def test_known_multi_character_zh_word_returns_han_script_with_stroke_data() -> None:
    result = orthography.orthography_for_word("学习", "zh")

    assert result is not None
    assert result["script"] == "han"
    assert [entry["character"] for entry in result["characters"]] == ["学", "习"]
    for entry in result["characters"]:
        assert entry["stroke_count"] > 0
        assert entry["stroke_paths"]


def test_en_word_returns_none() -> None:
    assert orthography.orthography_for_word("curious", "en") is None


def test_fully_unavailable_zh_word_returns_none() -> None:
    # U+4DBF is inside the accepted Han range but has no glyph in the pack
    # (see tests/test_chinese_stroke_order.py::test_a_character_outside_the_pack_is_named_not_invented).
    assert orthography.orthography_for_word("䶿", "zh") is None


def test_source_and_source_version_match_the_stroke_order_capability() -> None:
    result = orthography.orthography_for_word("学习", "zh")
    direct = stroke_order.stroke_order_for("学习")

    assert result is not None
    assert result["source"] == direct["source"]
    assert result["source_version"] == direct["source_version"]
    assert result["source"] == "make-me-a-hanzi"
    assert result["source_version"] == stroke_order.SOURCE_VERSION


def test_projection_calls_the_existing_capability_rather_than_reading_files(monkeypatch) -> None:
    calls: list[str] = []
    fabricated = {
        "word": "学习",
        "glyph_size": stroke_order.GLYPH_SIZE,
        "characters": [
            {
                "character": "学",
                "stroke_count": 1,
                "stroke_paths": ["M 0 0"],
                "medians": [[[0, 0], [1, 1]]],
                "radical_strokes": [],
            }
        ],
        "unavailable": [],
        "source": "make-me-a-hanzi",
        "source_version": stroke_order.SOURCE_VERSION,
    }

    def fake_stroke_order_for(word: str) -> dict:
        calls.append(word)
        return fabricated

    monkeypatch.setattr(stroke_order, "stroke_order_for", fake_stroke_order_for)

    result = orthography.orthography_for_word("学习", "zh")

    assert calls == ["学习"]
    assert result is not None
    assert result["characters"] == fabricated["characters"]
