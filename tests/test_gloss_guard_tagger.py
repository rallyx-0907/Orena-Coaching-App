"""The PRE-202 reviewed sentences through the real shared tagger (no stubs): the guard holds end to end."""

from __future__ import annotations

from typing import Any

import pytest

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
    def __init__(self, entry: dict[str, Any]) -> None:
        self.entry = entry

    def find_entry(self, language_code, normalized_term):
        return self.entry

    def find_entries(self, language_code, normalized_term, *, limit=8):
        return [self.entry]


def _service(catalogue=None, dictionary=lambda word: None, calls: list | None = None) -> ReadingLookupService:
    def seam(*args):
        calls.append(args)
        return "AI MEANING"

    return ReadingLookupService(
        catalogue, dictionary, ReadingTranslationService(_Engine(), cache=DerivedCache()),
        word_translation=seam if calls is not None else None,
    )


def _nothing_shown(result: dict[str, Any]) -> bool:
    return result["meanings"] == [] and result["definitions"] == [] and result["available"] is False


@pytest.mark.parametrize(
    ("word", "sentence", "pack_pos", "pack_vi"),
    [
        ("with", "Do you want to come with?", "noun", "cùng"),
        ("the", "The more you read, the more you know.", "noun", "cái"),
        ("and", "We sang and danced.", "noun", "bản nhạc"),
        ("turn", "Alexa, turn off the living room light.", "verb", "rẽ"),
        ("turn", "They spoke in turn.", "verb", "rẽ"),
        ("late", "The leaves fall in late autumn.", "adjective", "muộn"),
        ("late", "It was built in the late 1800s.", "adjective", "muộn"),
        ("Morning", "The Boston Morning Post said so.", "noun", "buổi sáng"),
    ],
)
def test_en_reviewed_sentences_with_the_real_tagger(word, sentence, pack_pos, pack_vi) -> None:
    pack = {"term": word.casefold(), "part_of_speech": pack_pos, "short_meanings": [{"language": "vi", "text": pack_vi}]}
    calls: list = []
    dictionary = lambda w: {"definitions": [{"part_of_speech": pack_pos, "definition": "x"}], "phonetic": ""}  # noqa: E731
    result = _service(_Catalogue(pack), dictionary, calls).lookup(word, sentence, "en", "vi").to_dict()
    assert _nothing_shown(result)
    assert calls == []


@pytest.mark.parametrize(
    ("word", "sentence"),
    [("的", "这是我的书。"), ("了", "我吃了。"), ("和", "我和你去学校。"), ("在", "他在学校学习。")],
)
def test_zh_reviewed_function_words_with_the_real_tagger(monkeypatch, word, sentence) -> None:
    monkeypatch.setattr(
        chinese_lexicon, "lookup", lambda w: (chinese_lexicon.LexiconEntry(w, w, "x", ("sense",), False),),
    )
    assert _nothing_shown(_service().lookup(word, sentence, "zh", "en").to_dict())


@pytest.mark.parametrize(
    ("word", "sentence"),
    [
        ("sat", "She sat on the chair."),
        ("walked", "He walked through the door."),
        ("came", "They came back."),
        ("sit", "Please sit down."),
    ],
)
def test_en_verbs_with_an_unlisted_particle_keep_their_gloss_with_the_real_tagger(word, sentence) -> None:
    pack = {"term": word, "part_of_speech": "verb", "short_meanings": [{"language": "vi", "text": "nghĩa"}]}
    result = _service(_Catalogue(pack)).lookup(word, sentence, "en", "vi").to_dict()
    assert result["meanings"] == [{"text": "nghĩa", "source": "collection"}]
