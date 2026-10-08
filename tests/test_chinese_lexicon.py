"""The vendored CC-CEDICT + Unihan pack: deterministic Chinese word facts, no AI."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from writing_coach.languages.chinese import lexicon

ROOT = Path(__file__).resolve().parents[1]


def test_the_committed_pack_matches_its_index_and_names_its_sources() -> None:
    index = json.loads(lexicon.INDEX_PATH.read_text(encoding="utf-8"))
    assert index["format"] == lexicon.EXPECTED_FORMAT
    assert hashlib.sha256(lexicon.PACK_PATH.read_bytes()).hexdigest() == index["pack_sha256"]
    assert index["sources"]["cc_cedict"]["license"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert index["headwords"] > 100_000
    for name in ("README.md", "CC-BY-SA-4.0.txt", "UNICODE-LICENSE.txt"):
        assert (lexicon.DATA_DIR / name).is_file(), name


def test_the_build_script_verifies_the_committed_pack() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_chinese_lexicon_pack.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("numbered", "marked"),
    [
        ("xue2 xi2", "xué xí"),
        ("lu:4", "lǜ"),
        ("nu:3 er2", "nǚ ér"),
        ("gou3", "gǒu"),
        ("liu2", "liú"),
        ("gui4", "guì"),
        ("zi5", "zi"),
        ("Bei3 jing1", "Běi jīng"),
        ("r5", "r"),
    ],
)
def test_numbered_pinyin_becomes_tone_marks(numbered: str, marked: str) -> None:
    assert lexicon.tone_marked(numbered) == marked


def test_a_common_word_has_its_reading_and_senses() -> None:
    assert lexicon.reading("学习") == "xué xí"
    assert lexicon.short_meaning("学习") == "to learn; to study"
    assert lexicon.short_meaning("松树") == "pine; pine tree"


def test_bookkeeping_and_register_marked_senses_do_not_lead_a_short_meaning() -> None:
    meaning = lexicon.short_meaning("绿")
    assert meaning == "green"
    for entry in lexicon.lookup("书"):
        for sense in lexicon.meaning_senses(entry):
            assert not sense.startswith("CL:")


def test_names_come_after_common_words() -> None:
    entries = lexicon.lookup("方")
    assert entries and not entries[0].proper_noun


def test_an_unknown_word_is_absent_not_guessed() -> None:
    assert lexicon.lookup("xyz") == ()
    assert lexicon.short_meaning("") == ""
    assert lexicon.reading("𠀀𠀀") == ""


def test_unihan_vietnamese_is_exposed_as_published_not_as_han_viet() -> None:
    facts = lexicon.character("森")
    assert facts["mandarin"] == "sēn"
    assert "vietnamese" in facts and "han_viet" not in facts


def test_provenance_names_release_and_licence() -> None:
    provenance = lexicon.provenance()
    assert provenance["source"] == "cc-cedict"
    assert provenance["license"] == "CC BY-SA 4.0"
    assert provenance["release"].startswith("2026-")
