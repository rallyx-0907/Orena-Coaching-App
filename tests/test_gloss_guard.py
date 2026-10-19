"""A headword gloss is shown only where the headword's sense is the sentence's (PRE-202 review, 2026-10-19).

Each case below is a tap the reviewer found with a wrong sense. The tagger is replaced by a table of the classes it gives
in those sentences, so the tests need no model: they pin what the tap does with a class, a neighbour and a list.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from writing_coach import reading_lookup
from writing_coach.gloss_guard import is_function_word, neighbours, pos_disagrees, withhold_reason
from writing_coach.languages.chinese import lexicon as chinese_lexicon
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService


class _Engine:
    engine_id = "local_marian"
    model_version = "x-1"
    uses_ai = False
    uses_paid_provider = False

    def translate_batch(self, source_language, target_language, segments):
        return {s.segment_id: "WORD-ALONE" for s in segments}


class _Catalogue:
    def __init__(self, *entries: dict[str, Any]) -> None:
        self.entries = list(entries)

    def find_entry(self, language_code, normalized_term):
        return self.entries[0] if self.entries else None

    def find_entries(self, language_code, normalized_term, *, limit=8):
        return list(self.entries)


def _entry(term: str, pos: str, vi: str) -> dict[str, Any]:
    return {"term": term, "part_of_speech": pos, "short_meanings": [{"language": "vi", "text": vi}]}


def _tag(monkeypatch, classes: dict[str, str], language: str = "en") -> None:
    """The tagger as a table: a word's class by its lower-case text (default: noun), one token per word or Han char."""

    pattern = re.compile(r"[一-鿿]" if language == "zh" else r"[\w']+")

    def annotate(lang, text, **_kwargs):
        return [
            {
                "fragment": m.group(), "start": m.start(), "end": m.end(),
                "pos": classes.get(m.group().casefold(), "noun"), "pronunciation": "", "lemma": m.group().casefold(),
            }
            for m in pattern.finditer(text)
        ]

    monkeypatch.setattr(reading_lookup, "annotate", annotate)


def _service(catalogue=None, dictionary=lambda word: None, seam_calls: list | None = None) -> ReadingLookupService:
    def seam(*args):
        seam_calls.append(args)
        return "AI MEANING"

    return ReadingLookupService(
        catalogue,
        dictionary,
        ReadingTranslationService(_Engine(), cache=DerivedCache()),
        word_translation=seam if seam_calls is not None else None,
    )


def _dictionary(*definitions: tuple[str, str]):
    return lambda word: {
        "definitions": [{"part_of_speech": pos, "definition": text} for pos, text in definitions],
        "phonetic": "",
    }


def _tap(service, word, sentence, language="en", target="vi"):
    return service.lookup(word, sentence, language, target).to_dict()


def _nothing_shown(result: dict[str, Any]) -> bool:
    return result["meanings"] == [] and result["definitions"] == [] and result["available"] is False


# --- the pure guard ----------------------------------------------------------------------------------------------

def test_function_words_come_from_each_languages_own_list() -> None:
    assert is_function_word("en", "With") and is_function_word("en", "the") and is_function_word("en", "and")
    assert not is_function_word("en", "turn")
    assert all(is_function_word("zh", w) for w in ("的", "了", "和", "在"))
    assert not is_function_word("zh", "学习")
    assert not is_function_word("fr", "le")  # a language without an adapter list has none: nothing is guessed


def test_the_tagged_class_of_a_grammatical_word_is_enough_without_a_list_entry() -> None:
    for pos in ("preposition", "conjunction", "determiner", "auxiliary", "pronoun", "particle"):
        assert withhold_reason("en", "whereas", pos) == "function_word"
    assert withhold_reason("en", "plan", "verb") == ""


def test_neighbours_are_the_tokens_either_side_of_the_selection() -> None:
    tokens = [
        {"fragment": "turn", "start": 0, "end": 4, "pos": "verb"},
        {"fragment": "off", "start": 5, "end": 8, "pos": "other"},
    ]
    assert neighbours(tokens, 0, 4) == (None, tokens[1])
    assert neighbours(tokens, 5, 8) == (tokens[0], None)


def test_pos_disagreement_is_between_lexical_classes_only() -> None:
    assert pos_disagrees("noun", "verb") and pos_disagrees("adj", "adverb")
    assert not pos_disagrees("noun", "noun") and not pos_disagrees("", "verb") and not pos_disagrees("noun", "other")
    assert not pos_disagrees("noun", "preposition")  # a grammatical class is handled as a function word instead


# --- the reviewed taps (EN) --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("word", "sentence", "classes", "definitions", "pack"),
    [
        ("with", "Do you want to come with?", {"with": "preposition"}, [("adverb", "Along, together with others.")], None),
        ("the", "The more you read, the more you know.", {"the": "determiner"}, [("adverb", "By that much.")], None),
        ("and", "Rock and roll.", {"and": "conjunction"}, [("noun", "A music term.")], _entry("and", "noun", "bản nhạc")),
    ],
)
def test_en_function_words_show_no_headword_gloss(monkeypatch, word, sentence, classes, definitions, pack) -> None:
    _tag(monkeypatch, classes)
    calls: list = []
    service = _service(_Catalogue(pack) if pack else None, _dictionary(*definitions), calls)
    assert _nothing_shown(_tap(service, word, sentence))
    assert calls == []  # no word-alone layer, no AI


def test_en_a_function_word_by_list_is_guarded_even_when_the_tagger_gives_a_content_class(monkeypatch) -> None:
    _tag(monkeypatch, {})  # every word defaults to "noun"
    service = _service(_Catalogue(_entry("with", "noun", "cái gì đó")), _dictionary(("noun", "x")))
    assert _nothing_shown(_tap(service, "with", "She came with us."))


def test_en_phrasal_verb_shows_no_headword_gloss(monkeypatch) -> None:
    _tag(monkeypatch, {"alexa": "proper_noun", "turn": "verb", "off": "other", "the": "determiner", "light": "noun"})
    calls: list = []
    service = _service(_Catalogue(_entry("turn", "verb", "rẽ")), _dictionary(("verb", "To rotate.")), calls)
    assert _nothing_shown(_tap(service, "turn", "Alexa, turn off the light.", ))
    assert calls == []


def test_en_the_same_verb_without_a_particle_keeps_its_gloss(monkeypatch) -> None:
    _tag(monkeypatch, {"turn": "verb", "the": "determiner", "page": "noun"})
    service = _service(_Catalogue(_entry("turn", "verb", "rẽ")))
    assert _tap(service, "turn", "Turn the page.")["meanings"] == [{"text": "rẽ", "source": "collection"}]


def test_en_fixed_phrase_in_turn_shows_no_headword_gloss(monkeypatch) -> None:
    _tag(monkeypatch, {"they": "pronoun", "spoke": "verb", "in": "preposition", "turn": "noun"})
    service = _service(_Catalogue(_entry("turn", "verb", "rẽ")), _dictionary(("verb", "To rotate.")))
    assert _nothing_shown(_tap(service, "turn", "They spoke in turn."))


@pytest.mark.parametrize(
    "sentence", ["The leaves fall in late autumn.", "It was built in the late 1800s."],
)
def test_en_late_in_a_period_shows_no_headword_gloss(monkeypatch, sentence) -> None:
    _tag(monkeypatch, {"late": "adjective", "1800s": "numeral", "the": "determiner", "in": "preposition"})
    calls: list = []
    service = _service(_Catalogue(_entry("late", "adjective", "muộn")), _dictionary(("adjective", "After time.")), calls)
    assert _nothing_shown(_tap(service, "late", sentence))
    assert calls == []


def test_en_late_for_a_person_keeps_its_gloss(monkeypatch) -> None:
    _tag(monkeypatch, {"late": "adjective", "he": "pronoun", "was": "verb", "again": "adverb"})
    service = _service(_Catalogue(_entry("late", "adjective", "muộn")))
    assert _tap(service, "late", "He was late again.")["meanings"][0]["text"] == "muộn"


def test_en_a_word_inside_a_proper_name_shows_no_headword_gloss(monkeypatch) -> None:
    _tag(monkeypatch, {"boston": "proper_noun", "morning": "noun", "post": "proper_noun", "said": "verb"})
    service = _service(_Catalogue(_entry("morning", "noun", "buổi sáng")), _dictionary(("noun", "The start of day.")))
    assert _nothing_shown(_tap(service, "Morning", "The Boston Morning Post said so."))


def test_en_the_common_word_keeps_its_gloss_outside_a_name(monkeypatch) -> None:
    _tag(monkeypatch, {"morning": "noun", "good": "adjective"})
    service = _service(_Catalogue(_entry("morning", "noun", "buổi sáng")))
    assert _tap(service, "morning", "Good morning.")["meanings"][0]["text"] == "buổi sáng"


def test_en_a_pack_sense_of_another_class_is_withheld_and_nothing_second_guesses_it(monkeypatch) -> None:
    _tag(monkeypatch, {"we": "pronoun", "turn": "verb", "left": "adverb"})
    calls: list = []
    service = _service(_Catalogue(_entry("left", "noun", "bên trái")), _dictionary(("adverb", "On the left side.")), calls)
    result = _tap(service, "left", "We turn left.")
    assert result["meanings"] == []  # neither the noun gloss nor a word-alone translation or AI answer
    assert result["definitions"] == [{"part_of_speech": "adverb", "definition": "On the left side."}]
    assert calls == []


def test_the_prefetch_never_spends_a_translation_on_a_function_word(monkeypatch) -> None:
    service = _service(_Catalogue())
    assert service.has_local_meaning("with", "en", "vi") is True
    assert service.has_local_meaning("的", "zh", "vi") is True


# --- ZH parity ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("word", "sentence"),
    [("的", "这是我的书。"), ("了", "他吃了饭。"), ("和", "我和你去。"), ("在", "我在家。")],
)
def test_zh_function_words_show_no_headword_gloss(monkeypatch, word, sentence) -> None:
    _tag(monkeypatch, {word: "particle"}, "zh")
    monkeypatch.setattr(
        chinese_lexicon, "lookup", lambda w: (chinese_lexicon.LexiconEntry(w, w, "de", ("of; 's",), False),),
    )
    calls: list = []
    service = _service(_Catalogue({"term": word, "part_of_speech": "particle", "short_meanings": [
        {"language": "vi", "text": "của"}]}), seam_calls=calls)
    assert _nothing_shown(_tap(service, word, sentence, "zh", "en"))
    assert _nothing_shown(_tap(service, word, sentence, "zh", "vi"))
    assert calls == []


def test_zh_a_content_word_keeps_its_gloss(monkeypatch) -> None:
    _tag(monkeypatch, {"书": "noun"}, "zh")
    monkeypatch.setattr(
        chinese_lexicon, "lookup", lambda w: (chinese_lexicon.LexiconEntry(w, w, "shū", ("book",), False),),
    )
    assert _tap(_service(), "书", "这是我的书。", "zh", "en")["meanings"][0]["text"] == "book"
