from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import reading_translation_api
from writing_coach.media_translation import TranslationProviderError
from writing_coach.persistence.vocabulary_repository import VocabularyContentUnavailable
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService


class RecordingTranslationProvider:
    engine_id = "fake"
    model_version = "fake-1"

    def __init__(self, *, fail: bool = False, meaning: str = "") -> None:
        self.calls: list[list[str]] = []
        self.fail = fail
        self.meaning = meaning

    def translate_batch(self, source_language, target_language, segments):
        self.calls.append([segment.original_text for segment in segments])
        if self.fail:
            raise TranslationProviderError("provider down")
        return {
            segment.segment_id: self.meaning or f"{target_language}:{segment.original_text}"
            for segment in segments
        }


class FakeVocabularyRepository:
    def __init__(self, entries: dict[tuple[str, str], dict] | None = None, *, unavailable: bool = False) -> None:
        self._entries = entries or {}
        self._unavailable = unavailable
        self.calls: list[tuple[str, str]] = []

    def find_entry(self, language_code: str, normalized_term: str):
        self.calls.append((language_code, normalized_term))
        if self._unavailable:
            raise VocabularyContentUnavailable("no catalog")
        return self._entries.get((language_code, normalized_term))


def _service(
    *,
    vocabulary_repository=None,
    english_dictionary=None,
    translation_provider: RecordingTranslationProvider | None = None,
) -> tuple[ReadingLookupService, RecordingTranslationProvider]:
    provider = translation_provider or RecordingTranslationProvider()
    translation_service = ReadingTranslationService(provider)
    service = ReadingLookupService(
        vocabulary_repository,
        english_dictionary or (lambda word: None),
        translation_service,
    )
    return service, provider


def test_collection_meaning_wins_and_stops_machine_translation() -> None:
    repository = FakeVocabularyRepository(
        {
            ("en", "cloaks"): {
                "term": "cloak",
                "phonetic": "/kləʊk/",
                "part_of_speech": "noun",
                "short_meanings": [{"language": "vi", "text": "áo choàng"}],
            }
        }
    )
    service, provider = _service(vocabulary_repository=repository)

    result = service.lookup("cloaks", "She wore cloaks.", "en", "vi").to_dict()

    assert result["meanings"] == [{"text": "áo choàng", "source": "collection"}]
    assert result["base_form"] == "cloak"
    assert result["part_of_speech"] == "noun"
    assert result["pronunciation"] == "/kləʊk/"
    assert result["available"] is True
    assert result["claim"] == "reading_lookup"
    # The catalog already answered; the translation engine is never reached.
    assert provider.calls == []


def test_catalog_lookup_falls_back_to_the_local_lemma() -> None:
    repository = FakeVocabularyRepository(
        {
            ("en", "book"): {
                "term": "book",
                "phonetic": "",
                "part_of_speech": "noun",
                "short_meanings": [{"language": "vi", "text": "sách"}],
            }
        }
    )
    service, provider = _service(vocabulary_repository=repository)

    result = service.lookup("books", "I have many books.", "en", "vi").to_dict()

    assert result["meanings"] == [{"text": "sách", "source": "collection"}]
    assert repository.calls == [("en", "books"), ("en", "book")]


def test_english_dictionary_definitions_pronunciation_and_audio() -> None:
    def dictionary(word: str):
        assert word == "book"
        return {
            "phonetic": "/bʊk/",
            "audio": "https://example.com/book.mp3",
            "definitions": [
                {"part_of_speech": "noun", "definition": "A written or printed work."},
                {"part_of_speech": "verb", "definition": "To reserve in advance."},
            ],
        }

    service, provider = _service(english_dictionary=dictionary)

    result = service.lookup("book", "I read this book.", "en", "vi").to_dict()

    assert result["definitions"] == [
        {"part_of_speech": "noun", "definition": "A written or printed work."},
        {"part_of_speech": "verb", "definition": "To reserve in advance."},
    ]
    assert result["pronunciation"] == "/bʊk/"
    assert result["audio_url"] == "https://example.com/book.mp3"


def test_english_dictionary_gives_at_most_three_definitions() -> None:
    def dictionary(word: str):
        return {
            "definitions": [
                {"part_of_speech": "noun", "definition": f"Sense {index}."}
                for index in range(5)
            ]
        }

    service, provider = _service(english_dictionary=dictionary)

    result = service.lookup("run", "I went for a run.", "en", "vi").to_dict()

    assert len(result["definitions"]) == 3


def test_dictionary_is_never_consulted_for_a_phrase() -> None:
    called = []

    def dictionary(word: str):
        called.append(word)
        return {"definitions": [{"part_of_speech": "noun", "definition": "x"}]}

    service, provider = _service(english_dictionary=dictionary)

    service.lookup("really like", "I really like this book.", "en", "vi")

    assert called == []


def test_machine_translation_fallback_labelled_machine_translation() -> None:
    provider = RecordingTranslationProvider(meaning="con mèo")
    service, provider = _service(translation_provider=provider)

    result = service.lookup("cat", "I have a cat.", "en", "vi").to_dict()

    assert result["meanings"] == [{"text": "con mèo", "source": "machine_translation"}]
    assert provider.calls == [["cat"]]


def test_chinese_pinyin_and_base_form_from_local_tagger() -> None:
    service, provider = _service()

    result = service.lookup("学校", "我今天在学校学习中文。", "zh", "vi").to_dict()

    assert result["pronunciation"] == "xué xiào"
    assert result["base_form"] == "学校"
    assert result["part_of_speech"] == "noun"


def test_a_character_inside_a_longer_word_reads_only_itself() -> None:
    """LEX-030: 科 tapped inside 维基百科 is kē, never the whole word's wéi jī bǎi kē."""
    service, provider = _service()

    context = "打开维基百科的首页"
    assert service.lookup("科", context, "zh", "vi").to_dict()["pronunciation"] == "kē"
    assert service.lookup("基百", context, "zh", "vi").to_dict()["pronunciation"] == "jī bǎi"
    assert service.lookup("维基百科", context, "zh", "vi").to_dict()["pronunciation"] == "wéi jī bǎi kē"


def test_chinese_word_gets_cc_cedict_senses_without_a_provider() -> None:
    provider = RecordingTranslationProvider(fail=True)
    service, provider = _service(translation_provider=provider)

    result = service.lookup("松树", "山上有很多松树。", "zh", "vi").to_dict()

    assert result["definitions"] == [
        {"part_of_speech": "", "definition": "pine"},
        {"part_of_speech": "", "definition": "pine tree"},
    ]
    # Vietnamese is not English: the dictionary senses are on the sheet and the
    # meaning still goes to the translation engine (here down), not to a model.
    assert result["meanings"] == []
    assert result["available"] is True


def test_chinese_word_for_an_english_support_language_is_the_dictionary_meaning() -> None:
    service, provider = _service()

    result = service.lookup("学习", "我每天学习中文。", "zh", "en").to_dict()

    assert result["meanings"] == [{"text": "to learn; to study", "source": "dictionary"}]
    assert provider.calls == []


@pytest.mark.parametrize(
    "selection,context",
    [
        ("底", "我们底主人"),
        ("底", "花生底好处很多"),
        ("底", "父亲底话"),
        ("底", "这是我们底"),
    ],
)
def test_di_written_for_the_particle_de_is_the_particle_not_bottom(selection: str, context: str) -> None:
    """PRE-105 / D23: the same rule as the annotation, so the lookup and the reading agree."""
    service, provider = _service()

    result = service.lookup(selection, context, "zh", "en").to_dict()

    assert result["pronunciation"] == "de"
    assert result["part_of_speech"] == "particle"
    assert result["meanings"] == [{"text": "the particle 的 (possessive / attributive)", "source": "dictionary"}]
    assert {"part_of_speech": "", "definition": "old written form of 的"} in result["definitions"]
    assert "bottom" not in str(result)
    assert provider.calls == []


@pytest.mark.parametrize("context", ["到底怎么回事", "桌子底下很暗", "海底世界", "彻底改变", "年底到了"])
def test_di_in_a_lexical_word_is_still_bottom(context: str) -> None:
    service, _ = _service()

    result = service.lookup("底", context, "zh", "en").to_dict()

    assert result["pronunciation"] in ("dǐ", "")
    assert "old written form" not in str(result)


def test_phrase_gets_no_part_of_speech() -> None:
    service, provider = _service()

    result = service.lookup("really like", "I really like this book.", "en", "vi").to_dict()

    assert result["part_of_speech"] == ""


def test_unavailable_catalog_degrades_without_error() -> None:
    repository = FakeVocabularyRepository(unavailable=True)
    provider = RecordingTranslationProvider(fail=True)
    service, provider = _service(vocabulary_repository=repository, translation_provider=provider)

    result = service.lookup("xyzzy", "I read xyzzy today.", "en", "vi").to_dict()

    assert result["available"] is False
    assert result["claim"] == "reading_lookup_unavailable"
    assert result["meanings"] == []


def test_unavailable_dictionary_degrades_without_error() -> None:
    def broken_dictionary(word: str):
        raise RuntimeError("dictionary down")

    provider = RecordingTranslationProvider(fail=True)
    service, provider = _service(english_dictionary=broken_dictionary, translation_provider=provider)

    result = service.lookup("gizmo", "I bought a gizmo.", "en", "vi").to_dict()

    assert result["available"] is False
    assert result["definitions"] == []


def test_unavailable_engine_degrades_without_error() -> None:
    provider = RecordingTranslationProvider(fail=True)
    service, provider = _service(translation_provider=provider)

    result = service.lookup("gizmo", "I bought a gizmo.", "en", "vi").to_dict()

    assert result["available"] is False
    assert result["meanings"] == []


def test_available_is_true_when_only_the_engine_answers() -> None:
    repository = FakeVocabularyRepository(unavailable=True)

    def broken_dictionary(word: str):
        raise RuntimeError("dictionary down")

    provider = RecordingTranslationProvider(meaning="dụng cụ")
    service, provider = _service(
        vocabulary_repository=repository,
        english_dictionary=broken_dictionary,
        translation_provider=provider,
    )

    result = service.lookup("gizmo", "I bought a gizmo.", "en", "vi").to_dict()

    assert result["available"] is True
    assert result["meanings"] == [{"text": "dụng cụ", "source": "machine_translation"}]


def test_reading_lookup_reaches_ai_only_through_word_translation_on_a_miss_when_enabled(monkeypatch) -> None:
    """D-195 replaced "never AI": AI only via `word_translation`, only on a deterministic miss, only when enabled."""

    from writing_coach.ai import platform as ai_platform
    from writing_coach.ai.router import router as ai_router, tap

    asked: list[str | None] = []

    def spy(*args, **kwargs):
        asked.append(kwargs.get("capability_key"))
        raise AssertionError("no AI call was expected on this path")

    monkeypatch.setattr(ai_platform, "generate_structured", spy)
    tap.reset_state()
    ai_router.reset_state()

    # No seam wired: the lookup never reaches AI, and a deterministic answer is untouched.
    service, provider = _service()
    result = service.lookup("book", "I have a book.", "en", "vi").to_dict()
    assert result["available"] is True and asked == []

    # The real seam, capability not configured (the shipped state): a deterministic hit and a miss both make no call.
    class _NoConfig:
        def get_capability_config(self, _key):
            return None

    monkeypatch.setattr(ai_platform, "_platform_repository", _NoConfig())
    wired = ReadingLookupService(None, lambda word: None, ReadingTranslationService(RecordingTranslationProvider()),
                                 word_translation=tap.word_translation_seam)
    wired.lookup("book", "I have a book.", "en", "vi")
    wired.lookup("zzyzx", "A zzyzx.", "en", "vi")
    assert asked == []


@pytest.fixture
def lookup_client(monkeypatch):
    provider = RecordingTranslationProvider()
    translation_service = ReadingTranslationService(provider)
    service = ReadingLookupService(None, lambda word: None, translation_service)
    reading_translation_api.configure_reading_lookup(service)
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    app = FastAPI()
    app.include_router(reading_translation_api.router)
    yield TestClient(app), provider
    reading_translation_api.configure_reading_lookup(None)


def _lookup_body(**overrides):
    body = {
        "text": "cat",
        "context": "I have a cat.",
        "source_language": "en",
        "target_language": "vi",
    }
    body.update(overrides)
    return body


def test_lookup_endpoint_returns_a_meaning(lookup_client) -> None:
    http, provider = lookup_client
    response = http.post("/api/reading/lookup", json=_lookup_body())

    assert response.status_code == 200
    body = response.json()
    assert body["selected_text"] == "cat"
    assert body["source_language"] == "en"
    assert body["target_language"] == "vi"
    assert body["available"] is True


def test_lookup_endpoint_refuses_text_not_in_context(lookup_client) -> None:
    http, provider = lookup_client
    response = http.post("/api/reading/lookup", json=_lookup_body(text="dog"))

    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "reading_lookup_text_not_in_context"
    assert provider.calls == []


def test_lookup_endpoint_refuses_text_in_another_learning_language(lookup_client) -> None:
    http, provider = lookup_client
    response = http.post(
        "/api/reading/lookup",
        json=_lookup_body(source_language="zh", text="学校", context="我在学校。"),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["category"] == "reading_language_mismatch"
    assert provider.calls == []


def test_lookup_endpoint_refuses_an_unknown_support_language(lookup_client) -> None:
    http, provider = lookup_client
    response = http.post("/api/reading/lookup", json=_lookup_body(target_language="xx"))

    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "invalid_support_language"


def test_lookup_endpoint_is_unavailable_until_configured(monkeypatch) -> None:
    reading_translation_api.configure_reading_lookup(None)
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    app = FastAPI()
    app.include_router(reading_translation_api.router)

    response = TestClient(app).post("/api/reading/lookup", json=_lookup_body())

    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "reading_lookup_unavailable"


def test_a_class_the_dictionary_never_gives_the_word_is_the_taggers_error() -> None:
    """LEX-026: the tagger reads "lonely" in "I'm lonely" as an adverb; the dictionary knows it only as an
    adjective, so the adjective stands. A class the dictionary does list is the tagger's to choose."""

    def dictionary(word: str):
        senses = {
            "lonely": [{"part_of_speech": "adjective", "definition": "Sad because one has no friends."}],
            "book": [
                {"part_of_speech": "noun", "definition": "A written work."},
                {"part_of_speech": "verb", "definition": "To reserve."},
            ],
        }
        return {"definitions": senses[word]}

    service, _provider = _service(english_dictionary=dictionary)
    assert service.lookup("lonely", "\u201cI'm lonely,\u201d she said.", "en", "en").to_dict()["part_of_speech"] == "adjective"
    # "book" may be a noun or a verb: whichever the tagger read here is kept, never replaced by the dictionary's.
    from writing_coach.reading_lookup import LookupDefinition, _reconciled_part_of_speech

    both = [LookupDefinition("noun", "A written work."), LookupDefinition("verb", "To reserve.")]
    assert _reconciled_part_of_speech("verb", both) == "verb"
    assert _reconciled_part_of_speech("noun", both) == "noun"
    assert _reconciled_part_of_speech("adverb", []) == "adverb"


def test_an_unknown_english_word_has_no_part_of_speech() -> None:
    # The tagger answers "noun" for any unseen string; with no catalogue entry, no dictionary entry and no
    # pronunciation nothing vouches for the word, so no class is shown (PRE D6).
    answered_empty, _provider = _service(english_dictionary=lambda word: {"definitions": []})
    offline, _provider = _service()  # the dictionary gave no answer at all: timed out or offline

    unknown = answered_empty.lookup("zzzqxv", "The zzzqxv was on the table.", "en", "vi").to_dict()
    known = answered_empty.lookup("table", "The cat was on the table.", "en", "vi").to_dict()
    unreachable = offline.lookup("zzzqxv", "The zzzqxv was on the table.", "en", "vi").to_dict()

    assert unknown["part_of_speech"] == ""
    assert known["part_of_speech"] == "noun"
    # No answer from the dictionary says nothing about the word: the tagger's class stays.
    assert unreachable["part_of_speech"] == "noun"
