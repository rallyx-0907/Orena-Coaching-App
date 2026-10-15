"""Traditional to Simplified conversion is complete for the words that survived D-208 (D-211, PROPOSED).

The words are the survivors of the 2026-10-15 mini trial (VOA). The expected Simplified is the standard PRC form."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from writing_coach.languages.chinese.script_conversion import convert_script, convert_sequence, MAP_PATH
from writing_coach.languages.chinese.script_detection import SIMPLIFIED, TRADITIONAL, script_counts
from writing_coach.media_zh_cleanup import normalise_words
from writing_coach.speech_asr import SpeechAsrWord

ROOT = Path(__file__).resolve().parents[1]


def _simplified(text: str) -> str:
    return convert_script(text, SIMPLIFIED)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("什麼", "什么"),  # CC-CEDICT lists both 么 and the variant 麽, so only Unihan decides
        ("那麼", "那么"),
        ("怎麼樣", "怎么样"),
        ("鼓勵", "鼓励"),
        ("剩餘", "剩余"),  # 余, not the variant 馀
        ("乾淨", "干净"),
        ("餅乾", "饼干"),
        ("徵求", "征求"),
        ("特徵", "特征"),
        ("看著", "看着"),
        ("著急", "着急"),
        ("回覆", "回复"),
        ("答覆", "答复"),
        ("瞭解", "了解"),
        ("藉口", "借口"),
    ],
)
def test_survivors_become_the_standard_simplified_form(source, expected):
    assert _simplified(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("著名", "著名"),
        ("顯著", "显著"),
        ("卓著", "卓著"),
        ("乾坤", "乾坤"),
        ("乾隆", "乾隆"),
        ("覆蓋", "覆盖"),
        ("顛覆", "颠覆"),
        ("狼藉", "狼藉"),
        ("瞭望", "瞭望"),
    ],
)
def test_a_character_that_is_simplified_inside_a_word_stays(source, expected):
    assert _simplified(source) == expected


def test_a_sentence_mixes_both_cases_and_keeps_its_length():
    text = "他說著名的乾隆皇帝看著我們，什麼都不用鼓勵，特徵很顯著。"
    out = _simplified(text)
    assert out == "他说著名的乾隆皇帝看着我们，什么都不用鼓励，特征很显著。"
    assert len(out) == len(text)
    assert script_counts(out)[1] == 0


def test_survivors_leave_no_traditional_only_character():
    text = "什麼那麼怎麼鼓勵剩餘乾淨徵求特徵看著回覆瞭解藉口"
    assert script_counts(text)[1] > 0
    assert script_counts(_simplified(text))[1] == 0


def test_traditional_target_is_unchanged_by_the_context_table():
    assert convert_script("著名乾坤", TRADITIONAL) == "著名乾坤"


def test_a_word_split_across_recogniser_words_is_judged_whole():
    words = [SpeechAsrWord("著", 0, 100), SpeechAsrWord("名", 100, 200), SpeechAsrWord("看", 200, 300), SpeechAsrWord("著", 300, 400)]
    out = normalise_words(words, "zh")
    assert [word.word for word in out] == ["著", "名", "看", "着"]
    assert [(word.start_ms, word.end_ms) for word in out] == [(0, 100), (100, 200), (200, 300), (300, 400)]
    # Word by word the same split would have been 着 + 名.
    assert [convert_script(word.word, SIMPLIFIED) for word in words][0] == "着"
    assert convert_sequence(["著", "名"], SIMPLIFIED) == ["著", "名"]


def test_conversion_is_one_character_to_one_character_in_the_whole_table():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    assert data["format"] == "orena.zh-script-map.v2"
    for source, target in data["to_simplified"].items():
        assert len(source) == 1 and len(target) == 1
    for source, item in data["contextual_to_simplified"].items():
        assert len(source) == 1 and len(item["to"]) == 1
        assert 0x4E00 <= ord(item["to"]) <= 0x9FA5  # a character every font has
        assert all(2 <= len(word) <= 4 and source in word for word in item["keep"])
    assert data["to_simplified"]["麼"] == "么"
    assert data["contextual_to_simplified"]["著"]["to"] == "着"
    assert data["contextual_to_simplified"]["餘"]["to"] == "余"


def test_build_script_check_passes_and_names_the_expected_words():
    spec = importlib.util.spec_from_file_location("build_chinese_script_table", ROOT / "scripts" / "build_chinese_script_table.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.expected_failures() == []
    assert {"什麼", "鼓勵", "著名", "乾坤"} <= set(module.EXPECTED)
    # The vendored table is exactly what the script derives from the vendored sources.
    derived = module.derive_map()
    assert json.loads(MAP_PATH.read_text(encoding="utf-8")) == derived
