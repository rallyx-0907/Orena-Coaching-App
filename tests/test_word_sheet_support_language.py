"""The word sheet always carries the base meaning in the learner's support language (owner decision 2026-10-18).

Order: catalogue -> an open bilingual pack for the pair -> the free local translation -> `word_translation` (the word
only). A Vietnamese learner never reads an English definition unless it is labelled as the fallback it is, and a
missing contextual meaning never takes the base meaning away.
"""

from __future__ import annotations

import pytest

from writing_coach import bilingual_dictionary, reading_lookup, word_detail
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService

SENTENCE = "Its heat shields protect the capsule during re-entry."


class _Paid:
    engine_id = "ai"
    model_version = "x"
    uses_ai = True
    uses_paid_provider = True

    def translate_batch(self, *_a, **_k):
        raise AssertionError("the paid reading engine must not be used by a tap")


def _english(defs: dict[str, str]):
    asked: list[str] = []

    def lookup(word: str):
        asked.append(word)
        text = defs.get(word)
        if not text:
            return {"phonetic": ""}
        return {"definitions": [{"part_of_speech": "noun", "definition": text}], "phonetic": f"/{word}/"}

    lookup.asked = asked  # type: ignore[attr-defined]
    return lookup


def _service(*, dictionary=None, pack=None, seam=None):
    return ReadingLookupService(
        None, dictionary or _english({}), ReadingTranslationService(_Paid(), cache=DerivedCache()),
        word_translation=seam, bilingual_dictionary=pack,
    )


@pytest.fixture(autouse=True)
def _fresh():
    reading_lookup.reset_seam_gate()
    bilingual_dictionary.reset_packs()
    yield
    bilingual_dictionary.reset_packs()


@pytest.fixture
def lemma(monkeypatch):
    """The tagger's facts for "shields" (its lemma), independent of the tagger installed."""

    monkeypatch.setattr(
        reading_lookup, "_local_token_facts",
        lambda _l, _c, _s: {"part_of_speech": "noun", "pronunciation": "", "base_form": "", "lemma": "shield"},
    )


def test_the_bilingual_pack_answers_before_any_translation_and_the_seam_is_not_asked(lemma) -> None:
    asked: list[tuple] = []
    service = _service(
        dictionary=_english({"shields": "Anything that protects or defends"}),
        pack=lambda word, source, target, **_k: {"shield": "tấm chắn; cái khiên"}.get(word),
        seam=lambda *args: asked.append(args) or "never",
    )
    result = service.lookup("shields", SENTENCE, "en", "vi").to_dict()
    assert result["meanings"] == [{"text": "tấm chắn; cái khiên", "source": "bilingual_dictionary"}]
    assert asked == [], "a word the pack holds costs no AI call"
    assert service.has_local_meaning("shield", "en", "vi") is True, "translate-ahead skips a word the pack holds"


def test_a_pack_miss_reaches_word_translation_with_the_word_only(lemma) -> None:
    asked: list[tuple] = []

    def seam(selection, sentence, definitions, source, target):
        asked.append((selection, source, target))
        return "tấm chắn"

    service = _service(pack=lambda *_a, **_k: None, seam=seam)
    result = service.lookup("shields", SENTENCE, "en", "vi").to_dict()
    assert result["meanings"] == [{"text": "tấm chắn", "source": "word_translation"}]
    assert asked == [("shields", "en", "vi")]


def test_a_failing_pack_is_a_miss_never_a_blank_sheet(lemma) -> None:
    def broken(*_a, **_k):
        raise RuntimeError("pack corrupt")

    service = _service(dictionary=_english({"shields": "Anything that protects"}), pack=broken)
    result = service.lookup("shields", SENTENCE, "en", "vi").to_dict()
    assert result["available"] is True
    assert result["definitions"][0]["definition"] == "Anything that protects"


def test_an_inflected_form_without_an_entry_is_looked_up_by_its_lemma(lemma) -> None:
    dictionary = _english({"shield": "A broad piece of armour"})
    result = _service(dictionary=dictionary).lookup("shields", SENTENCE, "en", "vi").to_dict()
    assert dictionary.asked == ["shields", "shield"]
    assert result["definitions"][0]["definition"] == "A broad piece of armour"
    assert result["pronunciation"] != "/shield/", "the lemma's reading is not the inflected form's"


def test_the_file_pack_plugs_in_by_dropping_a_file(tmp_path, monkeypatch) -> None:
    (tmp_path / "en-vi.tsv").write_text("# an open EN->VI pack\nShield\ttấm chắn\nshield\tlater entry ignored\n", encoding="utf-8")
    monkeypatch.setattr(bilingual_dictionary, "PACK_DIR", tmp_path)
    assert bilingual_dictionary.has_pack("en", "vi") is True
    assert bilingual_dictionary.lookup("SHIELD", "en", "vi") == "tấm chắn"
    assert bilingual_dictionary.lookup("lamp", "en", "vi") is None
    assert bilingual_dictionary.has_pack("en", "zh") is False
    assert bilingual_dictionary.lookup("shield", "en", "en") is None


def test_only_the_vendored_en_vi_pack_is_installed_by_default() -> None:
    # D-246: EN->VI ships vendored (English Wiktionary via kaikki.org); no other pair has a pack.
    assert bilingual_dictionary.lookup("shield", "en", "vi")
    assert bilingual_dictionary.lookup("shield", "en", "zh") is None
    assert bilingual_dictionary.has_pack("en", "zh") is False


# --- the sheet's projection -------------------------------------------------------------------------------------


def test_a_vietnamese_learner_never_reads_an_unlabelled_english_definition() -> None:
    detail = word_detail.project_word_detail(
        selection="shields", context=SENTENCE, language="en",
        lookup={"target_language": "vi", "definitions": [{"part_of_speech": "noun", "definition": "Anything that protects"}]},
        explanation=None, saved=False,
    )  # fmt: skip
    assert detail["contextMeaning"] == "Anything that protects"
    assert detail["meaningLanguage"] == "en", "the English definition is labelled as the fallback it is"
    localized = word_detail.project_word_detail(
        selection="shields", context=SENTENCE, language="en",
        lookup={
            "target_language": "vi",
            "meanings": [{"text": "tấm chắn", "source": "bilingual_dictionary"}],
            "definitions": [{"part_of_speech": "noun", "definition": "Anything that protects"}],
        },
        explanation=None, saved=False,
    )  # fmt: skip
    assert localized["contextMeaning"] == "tấm chắn" and localized["meaningLanguage"] == "vi"
    assert localized["originalDefinition"]["language"] == "en"


def test_a_missing_contextual_meaning_still_shows_the_base_meaning(monkeypatch, lemma) -> None:
    service = _service(pack=lambda word, *_a, **_k: {"shield": "tấm chắn"}.get(word))
    monkeypatch.setattr(word_detail, "_gloss", lambda *_a: None)  # the contextual ask answered nothing
    monkeypatch.setattr(word_detail, "_cache", None)
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_lookup", service.lookup)
    body = word_detail.word_detail(
        word_detail.WordDetailIn(
            depth="sheet", contextual=True, text="shields", context=SENTENCE, source_language="en", target_language="vi",
        )
    )
    assert body["contextStatus"] == "empty"
    assert body["available"] is True and body["meaningSource"] == "dictionary"
    assert body["contextMeaning"] == "tấm chắn" and body["meaningLanguage"] == "vi"
