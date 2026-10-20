"""The vendored EN->VI dictionary pack (D-246): English Wiktionary's Vietnamese translations via kaikki.org.

Loader, provenance and attribution, the word tap's lookup order (a pack hit costs no AI call, a miss reaches the
`word_translation` seam), the sense choice, and the deterministic build script on a tiny fixture.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import unicodedata
import zlib
from pathlib import Path

import pytest

from writing_coach import bilingual_dictionary, reading_lookup
from writing_coach.languages.english import vi_lexicon
from writing_coach.licences import DATASETS
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService

ROOT = Path(__file__).resolve().parents[1]
SENTENCE = "Its heat shield protects the capsule during re-entry."


def _build_script():
    spec = importlib.util.spec_from_file_location("build_en_vi_pack", ROOT / "scripts" / "build_en_vi_pack.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --- the loader ---------------------------------------------------------------------------------------------------


def test_the_pack_is_installed_and_matches_its_index() -> None:
    assert vi_lexicon.installed() is True
    index = json.loads(vi_lexicon.INDEX_PATH.read_text(encoding="utf-8"))
    assert index["format"] == vi_lexicon.EXPECTED_FORMAT == "orena.en-vi-lexicon.v1"
    assert hashlib.sha256(vi_lexicon.PACK_PATH.read_bytes()).hexdigest() == index["pack_sha256"]
    assert index["headwords"] > 15000, "the full set of headwords, not a subset by level"
    assert _build_script().check(vi_lexicon.DATA_DIR) == 0


def test_shield_has_a_vietnamese_gloss_with_its_english_sense_label() -> None:
    senses = vi_lexicon.lookup("shield")
    assert senses and senses[0].part_of_speech == "noun"
    assert senses[0].sense, "each pair keeps its English sense label"
    assert "khiên" in senses[0].glosses
    assert vi_lexicon.gloss("shield") == senses[0].gloss
    # The headword as written, then lower case; an infinitive "to " is dropped.
    assert vi_lexicon.lookup("Shield") == senses
    assert vi_lexicon.lookup("to protect") == vi_lexicon.lookup("protect") != ()


def test_every_gloss_is_nfc_vietnamese_and_deduplicated() -> None:
    for word in ("shield", "protect", "temperature", "battery", "crew", "mission", "record"):
        for sense in vi_lexicon.lookup(word):
            assert sense.glosses and len(set(sense.glosses)) == len(sense.glosses)
            for text in sense.glosses:
                assert text == unicodedata.normalize("NFC", text) == text.strip() and text
                assert _build_script().is_vietnamese(text), text


def test_an_absent_word_is_reported_absent_never_guessed() -> None:
    assert vi_lexicon.lookup("launch") == ()
    assert vi_lexicon.gloss("launch") is None
    assert vi_lexicon.lookup("") == ()


def test_a_missing_pack_is_unavailable_not_an_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(vi_lexicon, "INDEX_PATH", tmp_path / "absent.json")
    vi_lexicon._index.cache_clear()
    vi_lexicon._record.cache_clear()
    try:
        assert vi_lexicon.installed() is False
        assert bilingual_dictionary.lookup("shield", "en", "vi") is None, "a missing pack is a miss"
    finally:
        vi_lexicon._index.cache_clear()
        vi_lexicon._record.cache_clear()


# --- the sense choice ---------------------------------------------------------------------------------------------


def test_the_sense_follows_the_part_of_speech_then_the_sentence() -> None:
    noun = vi_lexicon.choose("heat", "noun")
    verb = vi_lexicon.choose("heat", "verb")
    assert noun is not None and noun.part_of_speech == "noun"
    assert verb is not None and verb.part_of_speech == "verb" and verb.gloss != noun.gloss
    # The sense label's words in the sentence pick the sense; otherwise the common sense (first).
    river = vi_lexicon.choose("bank", "noun", "They sat on the bank of the river.")
    assert river is not None and "river" in river.sense
    assert vi_lexicon.choose("bank", "noun", "She opened an account.") == vi_lexicon.lookup("bank")[0]
    # A class the pack has no sense of is a miss, never another class's gloss.
    assert vi_lexicon.choose("shield", "adverb") is None


# --- the word tap's lookup order ----------------------------------------------------------------------------------


class _Paid:
    engine_id = "ai"
    model_version = "x"
    uses_ai = True
    uses_paid_provider = True

    def translate_batch(self, *_a, **_k):
        raise AssertionError("the paid reading engine must not be used by a tap")


@pytest.fixture
def tap(monkeypatch):
    reading_lookup.reset_seam_gate()
    bilingual_dictionary.reset_packs()
    monkeypatch.setattr(
        reading_lookup, "_local_token_facts",
        lambda _l, _c, selection: {"part_of_speech": "noun", "pronunciation": "", "base_form": "", "lemma": selection},
    )
    asked: list[tuple] = []

    def seam(selection, sentence, definitions, source, target):
        asked.append((selection, source, target))
        return "từ AI"

    service = ReadingLookupService(
        None, lambda _w: {"phonetic": ""}, ReadingTranslationService(_Paid(), cache=DerivedCache()),
        word_translation=seam, bilingual_dictionary=bilingual_dictionary.lookup,
    )
    yield service, asked
    bilingual_dictionary.reset_packs()


def test_a_pack_hit_gives_the_vietnamese_gloss_and_no_ai_call(tap) -> None:
    service, asked = tap
    result = service.lookup("shield", SENTENCE, "en", "vi").to_dict()
    assert result["meanings"][0]["source"] == "bilingual_dictionary"
    assert "khiên" in result["meanings"][0]["text"]
    assert asked == [], "a word the pack holds costs no AI call"
    assert service.has_local_meaning("shield", "en", "vi") is True


def test_a_word_the_pack_lacks_falls_through_to_the_ai_seam(tap) -> None:
    service, asked = tap
    result = service.lookup("launch", "They watched the launch.", "en", "vi").to_dict()
    assert result["meanings"] == [{"text": "từ AI", "source": "word_translation"}]
    assert asked == [("launch", "en", "vi")]


def test_the_vendored_pack_answers_only_its_pair() -> None:
    assert bilingual_dictionary.has_pack("en", "vi") is True
    assert bilingual_dictionary.lookup("shield", "en", "zh") is None
    assert bilingual_dictionary.lookup("shield", "en", "en") is None


# --- attribution --------------------------------------------------------------------------------------------------


def test_the_attribution_is_where_cc_cedicts_is() -> None:
    dataset = next(item for item in DATASETS if item.id == "wiktionary-en-vi")
    assert dataset.licence == "CC BY-SA 4.0" and "by-sa/4.0" in dataset.licence_url
    assert "Wiktionary contributors" in dataset.attribution and "Wiktextract" in dataset.attribution
    assert "`wiktionary-en-vi`" in (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    readme = (vi_lexicon.DATA_DIR / "README.md").read_text(encoding="utf-8")
    assert "Modification notice" in readme and "Share-alike" in readme and "CC-BY-SA-4.0.txt" in readme
    assert "Attribution-ShareAlike 4.0" in (vi_lexicon.DATA_DIR / "CC-BY-SA-4.0.txt").read_text(encoding="utf-8")
    source = json.loads(vi_lexicon.INDEX_PATH.read_text(encoding="utf-8"))["sources"]["wiktionary_en"]
    assert source["license"] == "CC BY-SA 4.0" and "Wiktionary contributors" in source["attribution"]
    assert source["release"] and len(source["sha256"]) == 64
    assert vi_lexicon.provenance()["license"] == "CC BY-SA 4.0"


# --- the build script ---------------------------------------------------------------------------------------------


def _fixture_lines() -> list[dict]:
    decomposed = unicodedata.normalize("NFD", "lá chắn")
    return [
        {"word": "shield", "pos": "noun", "lang_code": "en", "translations": [
            {"lang_code": "vi", "sense": "armor", "word": "khiên"},
            {"lang_code": "vi", "sense": "armor", "word": f"  {decomposed} "},
            {"lang_code": "vi", "sense": "armor", "word": "khiên"},          # duplicate
            {"lang_code": "vi", "sense": "armor", "word": "盾"},             # Han: not Vietnamese orthography
            {"lang_code": "vi", "sense": "armor", "word": ""},               # empty
            {"lang_code": "fr", "sense": "armor", "word": "bouclier"},       # another language
            {"lang_code": "de", "sense": "armor", "word": "Schild"},
            {"lang_code": "vi", "sense": "heraldry", "word": "huy hiệu"},
        ], "senses": [{"glosses": ["armor"], "translations": [{"lang_code": "vi", "sense": "armor", "word": "khiên"}]}]},
        {"word": "shield", "pos": "verb", "lang_code": "en", "translations": [
            {"code": "vi", "sense": "to protect", "word": "che chắn"},       # the older "code" key
        ]},
        {"word": "lamp", "pos": "noun", "lang_code": "en", "translations": [
            {"lang_code": "vi", "sense": "device", "word": "đèn", "tags": ["obsolete"]},
            {"lang_code": "vi", "sense": "device", "word": "cây đèn"},
        ]},
        {"word": "nothing", "pos": "noun", "lang_code": "en", "translations": [{"lang_code": "fr", "word": "rien"}]},
        {"word": "chien", "pos": "noun", "lang_code": "fr", "translations": [{"lang_code": "vi", "word": "chó"}]},
    ]


def test_the_build_script_on_a_tiny_fixture_is_deterministic(tmp_path) -> None:
    script = _build_script()
    source = tmp_path / "raw" / "kaikki.org-dictionary-English.jsonl.gz"
    source.parent.mkdir()
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write("not json\n")
        for line in _fixture_lines():
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    first, second = tmp_path / "a", tmp_path / "b"
    assert script.main(["--kaikki", str(source), "--release", "2026-10-03", "--out", str(first)]) == 0
    assert script.main(["--kaikki", str(source), "--release", "2026-10-03", "--out", str(second)]) == 0
    assert (first / script.PACK_NAME).read_bytes() == (second / script.PACK_NAME).read_bytes()
    assert (first / script.INDEX_NAME).read_bytes() == (second / script.INDEX_NAME).read_bytes()
    assert script.check(first) == 0

    index = json.loads((first / script.INDEX_NAME).read_text(encoding="utf-8"))
    assert index["format"] == script.FORMAT and index["headwords"] == 2
    assert index["sources"]["wiktionary_en"]["release"] == "2026-10-03"
    pack = (first / script.PACK_NAME).read_bytes()
    records: dict = {}
    for offset, length in index["offsets"].values():
        records.update(json.loads(zlib.decompress(pack[offset:offset + length])))
    # Armor first (three languages translate it), its Vietnamese trimmed, NFC, de-duplicated; Han and empty dropped.
    assert records["shield"] == [
        ["noun", "armor", ["khiên", "lá chắn"]],
        ["noun", "heraldry", ["huy hiệu"]],
        ["verb", "to protect", ["che chắn"]],
    ]
    assert records["lamp"] == [["noun", "device", ["cây đèn", "đèn"]]], "an obsolete translation comes last"
    assert "nothing" not in records and "chien" not in records
