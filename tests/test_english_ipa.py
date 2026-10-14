"""Local English IPA from CMUdict (D-202): conversion, lookup fallback order, table freshness."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from writing_coach.languages.english import ipa
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("word, expected", [
    ("infrastructure", "/ˌɪnfɹəˈstɹʌktʃɚ/"),
    ("rubble", "/ˈɹʌbəl/"),
    ("reconstruction", "/ˌɹikənˈstɹʌkʃən/"),
    ("aid", "/eɪd/"),
    ("propulsion", "/pɹəˈpʌlʃən/"),
    ("oversight", "/ˈoʊvɚˌsaɪt/"),
    ("read", "/ɹɛd/"),  # heteronym: the first CMUdict pronunciation
    ("Apple", "/ˈæpəl/"),  # case-insensitive
    ("the", "/ðə/"),
])
def test_conversion_samples(word: str, expected: str) -> None:
    assert ipa.ipa_for(word) == expected


def test_unknown_phrase_and_empty_have_no_reading() -> None:
    assert ipa.ipa_for("xyzzyqq") == ""
    assert ipa.ipa_for("two words") == ""
    assert ipa.ipa_for("") == ""


def test_stress_goes_before_the_syllable_onset() -> None:
    assert ipa.arpabet_to_ipa("AH0 B AW1 T".split()) == "əˈbaʊt"
    assert ipa.arpabet_to_ipa("AE1 S T R OW0 N AO2 T".split()) == "ˈæstɹoʊˌnɔt"
    assert ipa.arpabet_to_ipa("HH AW1 S".split()) == "haʊs"  # one syllable: no mark


class _Provider:
    def translate(self, *args, **kwargs):  # pragma: no cover - never reached with a meaning in hand
        raise RuntimeError("no translation")


def _service(dictionary, repository=None) -> ReadingLookupService:
    return ReadingLookupService(repository, dictionary, ReadingTranslationService(_Provider()))


def test_local_ipa_fills_in_when_the_online_dictionary_has_none() -> None:
    def timed_out(word: str):
        raise TimeoutError

    result = _service(timed_out).lookup("rubble", "Rubble lay everywhere.", "en", "vi").to_dict()
    assert result["pronunciation"] == "/ˈɹʌbəl/"
    result = _service(lambda word: {"definitions": []}).lookup("aid", "Food aid arrived.", "en", "vi").to_dict()
    assert result["pronunciation"] == "/eɪd/"


def test_online_dictionary_wins_over_local() -> None:
    result = _service(lambda word: {"phonetic": "/ɹʌbl/", "definitions": []}).lookup(
        "rubble", "Rubble lay everywhere.", "en", "vi").to_dict()
    assert result["pronunciation"] == "/ɹʌbl/"


def test_catalogue_wins_over_online_and_local() -> None:
    class Repo:
        def find_entry(self, language_code, normalized_term):
            return {"term": "rubble", "phonetic": "/catalogue/", "part_of_speech": "noun", "short_meanings": []}

    result = _service(lambda word: {"phonetic": "/online/", "definitions": []}, Repo()).lookup(
        "rubble", "Rubble lay everywhere.", "en", "vi").to_dict()
    assert result["pronunciation"] == "/catalogue/"


def test_phrase_gets_no_local_reading() -> None:
    result = _service(lambda word: None).lookup("food aid", "Food aid arrived.", "en", "vi").to_dict()
    assert result["pronunciation"] == ""


def test_table_metadata_and_freshness_check() -> None:
    meta = ipa.metadata()
    assert meta["source"] == "CMUdict" and meta["licence"].startswith("BSD") and meta["entries"] > 100_000
    assert (ROOT / "writing_coach/languages/english/CMUDICT-LICENSE.txt").read_text(encoding="utf-8").startswith(
        "Copyright (C) 1993-2015 Carnegie Mellon University")
    done = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/build_english_ipa_table.py"), "--check"],
                          capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT)})
    assert done.returncode == 0, done.stdout + done.stderr
