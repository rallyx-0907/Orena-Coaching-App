"""Speech recognition and pronunciation scoring are priced and recorded in the shared AI ledger."""

from __future__ import annotations

from typing import Any

import pytest

from writing_coach.ai import platform as ai_platform
from writing_coach.ai.base import sanitize_telemetry
from writing_coach.ai.pricing import estimate_audio_cost
from writing_coach.speech_asr import GroqSpeechAsrProvider
from writing_coach.speech_pronunciation import AzureSpeechPronunciationProvider, SpeechPronunciationNoSpeech


@pytest.fixture()
def recorded(monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr(ai_platform, "_persist_operation_telemetry", lambda event: rows.append(sanitize_telemetry(event)))
    return rows


def test_groq_bills_ten_seconds_at_least_and_whole_seconds_after():
    short = estimate_audio_cost("groq", "whisper-large-v3-turbo", 4.0)
    assert short["state"] == "estimated" and short["amount"] == round(10 * 0.04 / 3600, 8)
    assert estimate_audio_cost("groq", "whisper-large-v3-turbo", 30.2)["amount"] == round(31 * 0.04 / 3600, 8)


def test_azure_bills_each_second():
    assert estimate_audio_cost("azure-speech", "pronunciation-assessment", 8.0)["amount"] == round(8 * 1.32 / 3600, 8)


def test_an_unknown_length_or_model_is_never_priced_as_zero():
    assert estimate_audio_cost("groq", "whisper-large-v3-turbo", None)["state"] == "unknown"
    unpriced = estimate_audio_cost("groq", "some-new-model", 5.0)
    assert unpriced["state"] == "unpriced" and unpriced["amount"] is None


class _GroqResponse:
    status_code = 200

    @staticmethod
    def json() -> dict[str, Any]:
        return {"language": "en", "text": "Hello", "duration": 12.5,
                "segments": [{"text": "Hello", "start": 0.0, "end": 1.0}]}  # fmt: skip


class _GroqSession:
    def post(self, url: str, **kwargs: Any) -> _GroqResponse:
        return _GroqResponse()


def test_a_groq_transcription_records_its_seconds_and_cost(recorded):
    provider = GroqSpeechAsrProvider("test-key", session=_GroqSession())  # type: ignore[arg-type]
    result = provider.transcribe_bytes(b"audio", filename="take.webm", content_type="audio/webm", language="en")
    assert result.duration_seconds == 12.5
    row = recorded[0]
    assert (row["capability"], row["provider"], row["model"], row["outcome"]) == (
        "speech_asr", "groq", "whisper-large-v3-turbo", "success")
    assert row["usage"]["audio_seconds"] == 12.5
    assert row["cost"]["state"] == "estimated" and row["cost"]["amount"] == round(13 * 0.04 / 3600, 8)
    assert "Hello" not in repr(row), "no transcript in the ledger"


class _AzureResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _AzureSession:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def post(self, url: str, **kwargs: Any) -> _AzureResponse:
        return _AzureResponse(self.payload)


def _azure(payload):
    # 44-byte header plus 2 s of 16 kHz mono 16-bit PCM.
    return AzureSpeechPronunciationProvider("secret", "eastus", session=_AzureSession(payload),
                                            normalizer=lambda data, **_: b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 32 + b"\0" * 64000)  # fmt: skip


SCORED = {"DisplayText": "Good morning.", "NBest": [{"Display": "Good morning.", "AccuracyScore": 91, "FluencyScore": 82,
          "CompletenessScore": 100, "PronScore": 90, "Words": [{"Word": "morning", "AccuracyScore": 58,
          "ErrorType": "None", "Phonemes": []}]}]}  # fmt: skip


def test_an_azure_assessment_records_the_seconds_it_sent(recorded):
    _azure(SCORED).assess_bytes(b"webm", filename="t.webm", content_type="audio/webm", language="en",
                                reference_text="Good morning.")  # fmt: skip
    row = recorded[0]
    assert (row["capability"], row["provider"], row["outcome"]) == ("pronunciation_evaluator", "azure-speech", "success")
    assert row["usage"]["audio_seconds"] == 2.0
    assert row["cost"]["amount"] == round(2 * 1.32 / 3600, 8)


def test_a_silent_take_azure_answered_is_still_billed(recorded):
    silent = {"NBest": [{"PronScore": 0, "AccuracyScore": 0, "FluencyScore": 0, "CompletenessScore": 0,
              "Words": [{"Word": "good", "AccuracyScore": 0, "ErrorType": "Omission"}]}]}  # fmt: skip
    with pytest.raises(SpeechPronunciationNoSpeech):
        _azure(silent).assess_bytes(b"webm", filename="t.webm", content_type="audio/webm", language="en",
                                    reference_text="Good.")  # fmt: skip
    assert recorded[0]["cost"]["state"] == "estimated" and recorded[0]["usage"]["audio_seconds"] == 2.0


# --- the cost report (GET /api/admin/ai/costs) -----------------------------------------------------------


def test_the_cost_report_gives_a_unit_cost_per_call_and_per_audio_minute():
    from datetime import UTC, datetime

    from writing_coach.ai.platform import cost_report

    rows = [
        {"day": "2026-10-04", "capability": "writing_evaluator", "provider": "gemini", "model": "m", "calls": 4,
         "failures": 0, "priced_calls": 4, "unpriced_calls": 0, "usd": 0.008, "prompt_tokens": 1, "completion_tokens": 1,
         "audio_seconds": 0.0},
        {"day": "2026-10-03", "capability": "speech_asr", "provider": "groq", "model": "w", "calls": 3, "failures": 1,
         "priced_calls": 2, "unpriced_calls": 0, "usd": 0.0004, "prompt_tokens": 0, "completion_tokens": 0,
         "audio_seconds": 120.0},
        {"day": "2026-10-04", "capability": "learner_dictionary", "provider": None, "model": None, "calls": 2,
         "failures": 2, "priced_calls": 0, "unpriced_calls": 0, "usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0,
         "audio_seconds": 0.0},
    ]  # fmt: skip
    report = cost_report(rows, days=7, since=datetime(2026, 9, 28, tzinfo=UTC))
    features = {f["capability"]: f for f in report["by_feature"]}
    assert features["writing_evaluator"]["unit"] == "call" and features["writing_evaluator"]["usd_per_unit"] == 0.002
    assert features["speech_asr"]["unit"] == "audio_minute" and features["speech_asr"]["usd_per_unit"] == 0.0002
    assert features["learner_dictionary"]["usd_per_unit"] is None, "an average over nothing is null, never 0"
    assert [d["day"] for d in report["by_day"]] == ["2026-10-04", "2026-10-03"]
    assert report["gaps"] and all(gap["code"] and gap["text"] for gap in report["gaps"]), "the report says what it cannot measure"
