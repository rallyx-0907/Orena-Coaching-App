from __future__ import annotations

from typing import Any

import pytest

from writing_coach.speech_asr import GroqSpeechAsrProvider, SpeechAsrMalformed


class FakeResponse:
    status_code = 200

    @staticmethod
    def json() -> dict[str, Any]:
        return {
            "language": "en",
            "text": "Hello world",
            "segments": [{"text": "Hello world", "start": 0.0, "end": 1.2}],
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "world", "start": 0.55, "end": 1.2},
            ],
        }


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse()


def test_groq_can_transcribe_one_https_media_url_with_real_word_timestamps() -> None:
    session = FakeSession()
    provider = GroqSpeechAsrProvider("test-key", session=session)  # type: ignore[arg-type]

    result = provider.transcribe_url(
        "https://media.example.test/audio.m4a?token=signed",
        language="en",
        prompt="A public media lesson: honey bees.",
    )

    assert result.provider == "groq"
    assert result.language == "en"
    assert [(word.word, word.start_ms, word.end_ms) for word in result.words] == [
        ("Hello", 0, 500),
        ("world", 550, 1200),
    ]
    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert call["files"] == {
        "url": (None, "https://media.example.test/audio.m4a?token=signed")
    }
    assert ("timestamp_granularities[]", "segment") in call["data"]
    assert ("timestamp_granularities[]", "word") in call["data"]
    assert ("prompt", "A public media lesson: honey bees.") in call["data"]


@pytest.mark.parametrize(
    "audio_url",
    (
        "http://media.example.test/audio.m4a",
        "file:///tmp/audio.m4a",
        "https://user:secret@media.example.test/audio.m4a",
        "not-a-url",
    ),
)
def test_groq_url_boundary_rejects_non_https_or_credentialed_urls(
    audio_url: str,
) -> None:
    session = FakeSession()
    provider = GroqSpeechAsrProvider("test-key", session=session)  # type: ignore[arg-type]

    with pytest.raises(SpeechAsrMalformed):
        provider.transcribe_url(audio_url, language="en")

    assert session.calls == []


@pytest.mark.parametrize("timestamp", (float("nan"), float("inf"), float("-inf")))
def test_groq_rejects_non_finite_timestamps(timestamp: float) -> None:
    class InvalidTimestampResponse(FakeResponse):
        @staticmethod
        def json() -> dict[str, Any]:
            payload = FakeResponse.json()
            payload["segments"][0]["start"] = timestamp
            return payload

    session = FakeSession()
    session.post = lambda *_args, **_kwargs: InvalidTimestampResponse()  # type: ignore[method-assign]
    provider = GroqSpeechAsrProvider("test-key", session=session)  # type: ignore[arg-type]

    with pytest.raises(SpeechAsrMalformed):
        provider.transcribe_url("https://media.example.test/audio.m4a", language="en")
