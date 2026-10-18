"""Zero-cost sense choice for a word tap (owner decision 2026-10-18, refs #194).

A tap shows the neutral first sense. Among several senses on file the sentence picks one by the class and reading the
local tagger gave the word there, with no AI, no network and no word-keyed cache. The `word_translation` seam is asked
only when every deterministic layer missed, and never when a sense was chosen here.
"""

from __future__ import annotations

from typing import Any

import pytest

from writing_coach import reading_lookup, word_detail
from writing_coach.languages.chinese import lexicon as chinese_lexicon
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import LookupDefinition, ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService
from writing_coach.tap_sense import (
    canonical_pos,
    definitions_by_pos,
    pick_catalogue_entry,
    pick_chinese_entry,
)


def _entry(term: str, pos: str, **meanings: str) -> dict[str, Any]:
    return {
        "term": term,
        "part_of_speech": pos,
        "short_meanings": [{"language": language, "text": text} for language, text in meanings.items()],
    }


# --- the pure picks ----------------------------------------------------------------------------------------------

def test_canonical_pos_folds_dictionary_spellings_onto_the_tagger_labels() -> None:
    assert [canonical_pos(v) for v in ("Noun", "v.", "adj", "ADV", "proper noun", "", None, "gizmo")] == [
        "noun", "verb", "adjective", "adverb", "proper_noun", "", "", "",
    ]


def test_definitions_are_reordered_only_when_the_class_is_known_and_listed() -> None:
    noun = LookupDefinition("noun", "a drawing")
    verb = LookupDefinition("verb", "to intend")
    assert definitions_by_pos([noun, verb], "verb") == [verb, noun]
    assert definitions_by_pos([noun, verb], "") == [noun, verb]
    assert definitions_by_pos([noun, verb], "adverb") == [noun, verb]  # nothing matches: the neutral first stays


def test_catalogue_pick_prefers_the_support_language_then_the_class_then_the_first() -> None:
    noun = _entry("plan", "noun", vi="kế hoạch (danh)")
    verb = _entry("plan", "verb", vi="lên kế hoạch")
    assert pick_catalogue_entry([noun, verb], "verb", "vi") is verb
    assert pick_catalogue_entry([noun, verb], "noun", "vi") is noun
    assert pick_catalogue_entry([noun, verb], "", "vi") is noun  # no class: neutral first sense
    assert pick_catalogue_entry([noun, verb], "adverb", "vi") is noun
    no_vi = _entry("plan", "verb", en="to plan")
    assert pick_catalogue_entry([no_vi, noun], "verb", "vi") is noun  # a sense in the learner's language wins
    assert pick_catalogue_entry([], "verb", "vi") is None


def _cedict(pinyin: str, *senses: str) -> chinese_lexicon.LexiconEntry:
    return chinese_lexicon.LexiconEntry("行", "行", pinyin, tuple(senses), False)


def test_chinese_entry_is_chosen_by_the_reading_the_tagger_gave_in_the_sentence() -> None:
    xing, hang = _cedict("xíng", "to walk"), _cedict("háng", "row; line")
    assert pick_chinese_entry([xing, hang], "háng") is hang
    assert pick_chinese_entry([xing, hang], "hang2") is hang  # toneless / numbered spelling still matches the syllable
    assert pick_chinese_entry([xing, hang], "xíng") is xing
    assert pick_chinese_entry([xing, hang], "") is xing  # no reading: neutral first entry
    assert pick_chinese_entry([xing, hang], "zhòng") is xing  # no entry has it: neutral first entry


# --- through the lookup ------------------------------------------------------------------------------------------

class _Engine:
    engine_id = "local_marian"
    model_version = "x-1"
    uses_ai = False
    uses_paid_provider = False

    def translate_batch(self, source_language, target_language, segments):
        return {s.segment_id: "" for s in segments}


class _Catalogue:
    def __init__(self, senses: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
        self.senses = senses
        self.asked: list[tuple[str, str]] = []

    def find_entry(self, language_code, normalized_term):  # the protocol every repository has
        found = self.senses.get((language_code, normalized_term)) or []
        return found[0] if found else None

    def find_entries(self, language_code, normalized_term, *, limit=8):
        self.asked.append((language_code, normalized_term))
        return list(self.senses.get((language_code, normalized_term)) or [])


class _FirstOnly:
    """A repository that predates `find_entries`: the tap must still work, with the first sense."""

    def __init__(self, entry: dict[str, Any]) -> None:
        self.entry = entry

    def find_entry(self, language_code, normalized_term):
        return self.entry


@pytest.fixture(autouse=True)
def _reset_word_detail():
    yield
    word_detail.configure_word_detail(lookup=None, saved_terms=None, cache=None)


@pytest.fixture
def seam_calls() -> list[tuple]:
    return []


def _service(catalogue=None, dictionary=lambda word: None, seam_calls=None) -> ReadingLookupService:
    def seam(*args):
        seam_calls.append(args)
        return "AI MEANING"

    return ReadingLookupService(
        catalogue,
        dictionary,
        ReadingTranslationService(_Engine(), cache=DerivedCache()),
        word_translation=seam if seam_calls is not None else None,
    )


def _tagger(monkeypatch, *, pos: str = "", reading: str = "") -> None:
    monkeypatch.setattr(
        reading_lookup,
        "_local_token_facts",
        lambda language, context, selection: {
            "part_of_speech": pos, "pronunciation": reading, "base_form": "", "lemma": selection,
        },
    )


def test_en_polysemous_word_takes_the_sense_of_its_class_in_the_sentence(monkeypatch, seam_calls) -> None:
    catalogue = _Catalogue({("en", "plan"): [
        _entry("plan", "noun", vi="bản vẽ, sơ đồ"),
        _entry("plan", "verb", vi="lên kế hoạch"),
    ]})
    service = _service(catalogue, seam_calls=seam_calls)

    _tagger(monkeypatch, pos="verb")
    verb = service.lookup("plan", "We plan to leave early.", "en", "vi").to_dict()
    _tagger(monkeypatch, pos="noun")
    noun = service.lookup("plan", "The plan was ready.", "en", "vi").to_dict()
    _tagger(monkeypatch, pos="")
    neutral = service.lookup("plan", "plan", "en", "vi").to_dict()

    assert verb["meanings"] == [{"text": "lên kế hoạch", "source": "collection"}]
    assert noun["meanings"] == [{"text": "bản vẽ, sơ đồ", "source": "collection"}]
    # The same word twice, two sentences, two senses: nothing here is cached by the word alone.
    assert neutral["meanings"][0]["text"] == "bản vẽ, sơ đồ"  # no usable class: the neutral first sense
    assert seam_calls == []  # zero cost: the AI seam was never reached


def test_a_repository_without_find_entries_still_gives_its_first_sense(monkeypatch, seam_calls) -> None:
    _tagger(monkeypatch, pos="verb")
    service = _service(_FirstOnly(_entry("plan", "noun", vi="kế hoạch")), seam_calls=seam_calls)
    assert service.lookup("plan", "We plan.", "en", "vi").to_dict()["meanings"][0]["text"] == "kế hoạch"


def test_en_dictionary_sense_of_the_sentence_class_is_the_main_line_when_nothing_is_localised(monkeypatch, seam_calls) -> None:
    """D14: "plan" as a verb was shown as the architectural drawing, the dictionary's first (noun) sense."""

    dictionary = lambda word: {  # noqa: E731
        "definitions": [
            {"part_of_speech": "noun", "definition": "a detailed drawing of a building"},
            {"part_of_speech": "verb", "definition": "to decide on and arrange in advance"},
        ],
        "phonetic": "",
    }
    service = _service(None, dictionary=dictionary)
    word_detail.configure_word_detail(lookup=service.lookup, saved_terms=None, cache=DerivedCache())

    def sheet(sentence: str):
        return word_detail.word_detail(
            word_detail.WordDetailIn(
                text="plan", context=sentence, source_language="en", target_language="vi", depth="sheet",
                contextual=False,
            )
        )

    _tagger(monkeypatch, pos="verb")
    assert sheet("We plan to leave early.")["contextMeaning"] == "to decide on and arrange in advance"
    _tagger(monkeypatch, pos="noun")
    assert sheet("The plan was ready.")["contextMeaning"] == "a detailed drawing of a building"
    assert seam_calls == []


def test_zh_homograph_takes_the_cedict_entry_with_the_reading_of_the_sentence(monkeypatch, seam_calls) -> None:
    entries = (_cedict("xíng", "to walk; to go"), _cedict("háng", "row; line; profession"))
    monkeypatch.setattr(chinese_lexicon, "lookup", lambda word: entries)

    _tagger(monkeypatch, reading="háng")
    row = _service(seam_calls=seam_calls).lookup("行", "银行", "zh", "en").to_dict()
    _tagger(monkeypatch, reading="xíng")
    walk = _service(seam_calls=seam_calls).lookup("行", "你不行", "zh", "en").to_dict()

    assert row["meanings"][0]["text"] == "row; line; profession"
    assert walk["meanings"][0]["text"] == "to walk; to go"
    assert seam_calls == []


def test_zh_word_with_a_vietnamese_pack_sense_shows_it_instead_of_the_english_gloss(monkeypatch, seam_calls) -> None:
    """D18: 字典 / 钢笔 showed the English CC-CEDICT gloss first while the pack carried a Vietnamese meaning."""

    catalogue = _Catalogue({("zh", "字典"): [
        _entry("字典", "noun", en="dictionary"),
        _entry("字典", "noun", vi="từ điển chữ"),
    ]})
    _tagger(monkeypatch, pos="noun")
    out = _service(catalogue, seam_calls=seam_calls).lookup("字典", "这本字典很厚。", "zh", "vi").to_dict()

    assert out["meanings"] == [{"text": "từ điển chữ", "source": "collection"}]
    assert seam_calls == []


def test_the_vendored_pack_still_answers_a_plain_chinese_word_without_ai(seam_calls) -> None:
    out = _service(seam_calls=seam_calls).lookup("字典", "这本字典很厚。", "zh", "en").to_dict()
    assert out["meanings"] and "dictionary" in out["meanings"][0]["text"].lower()
    assert seam_calls == []
