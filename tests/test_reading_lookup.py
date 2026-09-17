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


def test_reading_lookup_never_calls_an_ai_capability(monkeypatch) -> None:
    from writing_coach.ai import platform as ai_platform

    def boom(*args, **kwargs):
        raise AssertionError("reading lookup must never call an AI capability")

    monkeypatch.setattr(ai_platform, "generate_structured", boom)

    service, provider = _service()
    result = service.lookup("book", "I have a book.", "en", "vi").to_dict()

    assert result["available"] is True


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
