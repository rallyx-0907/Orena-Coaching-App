from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import reading_translation_api
from writing_coach.media_translation import (
    MAX_TRANSLATION_BATCH_CHARS,
    TranslationProviderError,
)
from writing_coach.reading_translation import (
    ReadingTranslationService,
    ReadingTranslationStatus,
    TextSegment,
)


class RecordingProvider:
    engine_id = "fake"
    model_version = "fake-1"

    def __init__(self, *, fail: bool = False, drop: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail
        self.drop = drop

    def translate_batch(self, source_language, target_language, segments):
        self.calls.append([segment.original_text for segment in segments])
        if self.fail:
            raise TranslationProviderError("provider down")
        return {
            segment.segment_id: f"{target_language}:{segment.original_text}"
            for segment in segments
            if segment.segment_id != self.drop
        }


def _segments(*texts: str) -> list[TextSegment]:
    return [TextSegment(f"p{index}", text) for index, text in enumerate(texts)]


def test_paragraphs_are_translated_in_request_order() -> None:
    provider = RecordingProvider()
    result = ReadingTranslationService(provider).translate("en", "vi", _segments("One.", "Two."))

    assert result.status is ReadingTranslationStatus.READY
    assert result.translations == (("p0", "vi:One."), ("p1", "vi:Two."))
    assert provider.calls == [["One.", "Two."]]


def test_a_paragraph_already_translated_is_not_sent_again() -> None:
    provider = RecordingProvider()
    service = ReadingTranslationService(provider)
    service.translate("en", "vi", _segments("One."))

    result = service.translate("en", "vi", _segments("One.", "Two."))

    assert result.status is ReadingTranslationStatus.READY
    assert result.translations == (("p0", "vi:One."), ("p1", "vi:Two."))
    assert provider.calls == [["One."], ["Two."]]


def test_the_cache_is_kept_per_target_language() -> None:
    provider = RecordingProvider()
    service = ReadingTranslationService(provider)
    service.translate("en", "vi", _segments("One."))

    result = service.translate("en", "es", _segments("One."))

    assert result.translations == (("p0", "es:One."),)
    assert provider.calls == [["One."], ["One."]]


def test_the_cache_is_bounded() -> None:
    provider = RecordingProvider()
    service = ReadingTranslationService(provider, cache_entries=2)
    for text in ("One.", "Two.", "Three."):
        service.translate("en", "vi", _segments(text))

    service.translate("en", "vi", _segments("One."))

    assert provider.calls[-1] == ["One."]


def test_reading_in_the_support_language_needs_no_translation() -> None:
    provider = RecordingProvider()
    result = ReadingTranslationService(provider).translate("en", "en", _segments("One."))

    assert result.status is ReadingTranslationStatus.NOT_REQUIRED
    assert result.translations == ()
    assert provider.calls == []


def test_a_provider_failure_is_reported_rather_than_raised() -> None:
    result = ReadingTranslationService(RecordingProvider(fail=True)).translate(
        "en", "vi", _segments("One.")
    )

    assert result.status is ReadingTranslationStatus.UNAVAILABLE
    assert result.translations == ()


def test_an_answer_missing_a_paragraph_is_not_passed_off_as_complete() -> None:
    provider = RecordingProvider(drop="p1")
    service = ReadingTranslationService(provider)

    result = service.translate("en", "vi", _segments("One.", "Two."))

    assert result.status is ReadingTranslationStatus.UNAVAILABLE
    assert result.translations == ()
    # Nothing from a malformed answer is kept to be served later as if it were sound.
    service.translate("en", "vi", _segments("One."))
    assert provider.calls[-1] == ["One."]


def test_a_paragraph_too_long_for_one_batch_is_too_large() -> None:
    provider = RecordingProvider()
    result = ReadingTranslationService(provider).translate(
        "en", "vi", _segments("x" * (MAX_TRANSLATION_BATCH_CHARS + 1))
    )

    assert result.status is ReadingTranslationStatus.TOO_LARGE
    assert provider.calls == []


@pytest.fixture
def client(monkeypatch):
    provider = RecordingProvider()
    reading_translation_api.configure_reading_translation(ReadingTranslationService(provider))
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    app = FastAPI()
    app.include_router(reading_translation_api.router)
    yield TestClient(app), provider
    reading_translation_api.configure_reading_translation(None)


def _body(**overrides):
    body = {
        "source_language": "en",
        "target_language": "vi",
        "segments": [
            {"segment_id": "p0", "text": "One."},
            {"segment_id": "p1", "text": "Two."},
        ],
    }
    body.update(overrides)
    return body


def test_translate_endpoint_returns_each_paragraph_meaning(client) -> None:
    http, _ = client
    response = http.post("/api/reading/translate", json=_body())

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "source_language": "en",
        "target_language": "vi",
        "translations": [
            {"segment_id": "p0", "translated_meaning": "vi:One."},
            {"segment_id": "p1", "translated_meaning": "vi:Two."},
        ],
    }


def test_translate_endpoint_reports_an_unavailable_engine_as_a_state(client, monkeypatch) -> None:
    http, _ = client
    reading_translation_api.configure_reading_translation(
        ReadingTranslationService(RecordingProvider(fail=True))
    )
    response = http.post("/api/reading/translate", json=_body())

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["translations"] == []


def test_translate_endpoint_refuses_text_in_another_learning_language(client) -> None:
    http, provider = client
    response = http.post("/api/reading/translate", json=_body(source_language="zh"))

    assert response.status_code == 409
    assert response.json()["detail"]["category"] == "reading_language_mismatch"
    assert provider.calls == []


def test_translate_endpoint_refuses_an_unknown_support_language(client) -> None:
    http, provider = client
    response = http.post("/api/reading/translate", json=_body(target_language="xx"))

    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "invalid_support_language"
    assert provider.calls == []


def test_translate_endpoint_refuses_repeated_paragraph_ids(client) -> None:
    http, provider = client
    response = http.post(
        "/api/reading/translate",
        json=_body(
            segments=[
                {"segment_id": "p0", "text": "One."},
                {"segment_id": "p0", "text": "Two."},
            ]
        ),
    )

    assert response.status_code == 422
    assert provider.calls == []


def test_translate_endpoint_bounds_how_much_one_request_may_ask_for(client) -> None:
    http, provider = client
    too_many = [
        {"segment_id": f"p{index}", "text": "One."}
        for index in range(reading_translation_api.MAX_READING_TRANSLATION_SEGMENTS + 1)
    ]
    response = http.post("/api/reading/translate", json=_body(segments=too_many))

    assert response.status_code == 422
    assert provider.calls == []


def test_translate_endpoint_is_unavailable_until_configured(monkeypatch) -> None:
    reading_translation_api.configure_reading_translation(None)
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    app = FastAPI()
    app.include_router(reading_translation_api.router)

    response = TestClient(app).post("/api/reading/translate", json=_body())

    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "reading_translation_unavailable"
