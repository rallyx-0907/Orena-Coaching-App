"""Traditional to Simplified conversion is complete for the words that survived D-208 (D-211, PROPOSED).

The words are the survivors of the 2026-10-15 mini trial (VOA). The expected Simplified is the standard PRC form."""
from __future__ import annotations

import importlib.util
import json
import unicodedata
from pathlib import Path

import pytest

from writing_coach.languages.chinese.script_conversion import _compatibility, convert_script, convert_sequence, MAP_PATH
from writing_coach.languages.chinese.script_detection import SIMPLIFIED, TRADITIONAL, script_counts
from writing_coach.media_zh_cleanup import normalise_words
from writing_coach.speech_asr import SpeechAsrWord

ROOT = Path(__file__).resolve().parents[1]


def _simplified(text: str) -> str:
    """The word inside a Traditional sentence: 這 is the Traditional evidence a context-dependent character needs."""
    return convert_script("這" + text, SIMPLIFIED)[1:]


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
    words = [SpeechAsrWord(w, i * 100, i * 100 + 100) for i, w in enumerate(["這", "著", "名", "看", "著"])]
    out = normalise_words(words, "zh")
    assert [word.word for word in out] == ["这", "著", "名", "看", "着"]
    assert [(word.start_ms, word.end_ms) for word in out] == [(i * 100, i * 100 + 100) for i in range(5)]
    assert convert_sequence(["這", "著", "名"], SIMPLIFIED) == ["这", "著", "名"]


# -- Simplified input is never altered (review of #224, P1-1) ---------------------------------------------------

SIMPLIFIED_TEXTS = [
    "鲁迅著《阿Q正传》",
    "他著有多部小说",
    "乾卦与坤卦",
    "宫商角徵羽",
    "覆水难收",
    "这是一个很好的计划，他说着话看着我，什么都不用鼓励。",
    "回复了那封信，借口很多，了解情况，干净的饼干。",
]


@pytest.mark.parametrize("text", SIMPLIFIED_TEXTS)
def test_simplified_text_is_byte_identical(text):
    assert convert_script(text, SIMPLIFIED) == text
    words = [SpeechAsrWord(char, i * 10, i * 10 + 10) for i, char in enumerate(text)]
    assert "".join(word.word for word in normalise_words(words, "zh")) == text


def test_the_context_layer_acts_only_near_traditional_evidence():
    # The Simplified clause after a stop is left alone though the Traditional one before it is converted.
    assert convert_script("他說著話。鲁迅著《阿Q正传》", SIMPLIFIED) == "他说着话。鲁迅著《阿Q正传》"
    # No Traditional-only character anywhere: nothing to judge by, so nothing changes.
    assert convert_script("看著我", SIMPLIFIED) == "看著我"


# -- compatibility ideographs and chains (review P2-3, P2-4) ------------------------------------------------------

def test_compatibility_ideographs_are_converted_and_keep_their_length():
    text = chr(0xF900) + chr(0xF907) + "們"  # 豈 and 龜 as compatibility forms
    out = convert_script(text, SIMPLIFIED)
    assert len(out) == len(text) and out == "岂龟们"
    assert all(len(unicodedata.normalize("NFC", chr(code))) == 1 for code in _compatibility())


def test_no_conversion_chains_and_the_doubtful_ones_are_dropped():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    table = data["to_simplified"]
    assert not [key for key, target in table.items() if target in table]
    for doubtful in ("諮", "讎", "戱"):
        assert doubtful not in table


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
