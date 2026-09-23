"""The pronunciation route: one provider-neutral answer, honest failures, no secrets."""
from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import speech_api
from writing_coach.speech_pronunciation import (
    PronunciationPhoneme,
    PronunciationSyllable,
    PronunciationWord,
    SpeechPronunciationMalformed,
    SpeechPronunciationNoSpeech,
    SpeechPronunciationRequestFailed,
    SpeechPronunciationResult,
    SpeechPronunciationTimedOut,
)

SECRET = "not-a-real-key-but-treat-it-as-one"


class StubProvider:
    provider_id = "stub-provider"
    max_bytes = 1024
    max_reference_chars = 200

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []
        self._api_key = SECRET

    def assess_bytes(self, audio_bytes, **kwargs):
        self.calls.append((audio_bytes, kwargs))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def measured_result() -> SpeechPronunciationResult:
    return SpeechPronunciationResult(
        provider="stub-provider",
        score_kind="measured",
        locale="en-US",
        recognized_text="Two cats slept.",
        pron_score=70.0,
        accuracy_score=72.0,
        fluency_score=80.0,
        completeness_score=67.0,
        prosody_score=None,
        words=(
            PronunciationWord(
                word="cats", accuracy_score=61.0, error_type="None",
                phonemes=(PronunciationPhoneme("s", 4.0),),
                syllables=(PronunciationSyllable("kaets", 61.0),),
                offset_ms=420, duration_ms=380,
            ),
        ),
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(speech_api.router)
    yield TestClient(app)
    speech_api.configure_speech_pronunciation(None)


def post(client, *, language="en", reference="Two cats slept.", audio=b"audio-bytes"):
    return client.post(
        "/api/speech/pronunciation",
        files={"file": ("take.webm", audio, "audio/webm")},
        data={"language": language, "reference_text": reference},
    )


def test_success_is_the_normalized_contract_and_nothing_of_the_provider(client):
    provider = StubProvider(measured_result())
    speech_api.configure_speech_pronunciation(provider)
    response = post(client)
    assert response.status_code == 200
    body = response.json()
    assert body["score_kind"] == "measured"
    assert body["language"] == "en"
    assert body["reference_text"] == "Two cats slept."
    word = body["words"][0]
    assert word == {
        "word": "cats", "accuracy_score": 61.0, "error_type": "None",
        "offset_ms": 420, "duration_ms": 380,
        "syllables": [{"syllable": "kaets", "accuracy_score": 61.0}],
        "phonemes": [{"phoneme": "s", "accuracy_score": 4.0}],
    }
    assert isinstance(body["latency_ms"], int)
    assert "NBest" not in response.text and SECRET not in response.text


def test_status_says_whether_pronunciation_is_configured(client):
    assert client.get("/api/speech/status").json()["pronunciation"] == {"configured": False}
    speech_api.configure_speech_pronunciation(StubProvider(measured_result()))
    assert client.get("/api/speech/status").json()["pronunciation"] == {"configured": True}


@pytest.mark.parametrize(
    "outcome,status,category",
    [
        (SpeechPronunciationNoSpeech(), 422, "pronunciation_no_speech"),
        (SpeechPronunciationTimedOut(), 504, "pronunciation_timeout"),
        (SpeechPronunciationMalformed(), 502, "pronunciation_provider_malformed"),
        (SpeechPronunciationRequestFailed(401, f"key {SECRET} rejected"), 502, "pronunciation_auth"),
        (SpeechPronunciationRequestFailed(429), 502, "pronunciation_rate_limited"),
    ],
)
def test_failures_have_their_own_category_and_leak_nothing(client, caplog, outcome, status, category):
    speech_api.configure_speech_pronunciation(StubProvider(outcome))
    with caplog.at_level(logging.INFO):
        response = post(client)
    assert response.status_code == status
    assert response.json()["detail"]["category"] == category
    assert SECRET not in response.text
    assert SECRET not in caplog.text


def test_unconfigured_provider_is_a_plain_503(client):
    response = post(client)
    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "pronunciation_unconfigured"


@pytest.mark.parametrize(
    "kwargs,category",
    [
        ({"language": "fr"}, "pronunciation_invalid_language"),
        ({"reference": ""}, "pronunciation_reference_invalid"),
        ({"reference": "x" * 201}, "pronunciation_reference_invalid"),
        ({"audio": b""}, "pronunciation_audio_empty"),
    ],
)
def test_invalid_requests_are_refused_before_the_provider_is_called(client, kwargs, category):
    provider = StubProvider(measured_result())
    speech_api.configure_speech_pronunciation(provider)
    response = post(client, **kwargs)
    assert response.status_code == 422
    assert response.json()["detail"]["category"] == category
    assert provider.calls == []


def test_oversized_audio_is_refused_with_its_measurement(client):
    provider = StubProvider(measured_result())
    speech_api.configure_speech_pronunciation(provider)
    response = post(client, audio=b"x" * 2048)
    assert response.status_code == 413
    assert provider.calls == []


def test_the_log_line_carries_operations_not_content(client, caplog):
    speech_api.configure_speech_pronunciation(StubProvider(measured_result()))
    with caplog.at_level(logging.INFO, logger="writing_coach.speech_api"):
        post(client, reference="Two cats slept.")
    line = " ".join(record.getMessage() for record in caplog.records)
    assert "pronunciation" in line and "stub-provider" in line
    assert "Two cats slept" not in line
    assert "audio-bytes" not in line
