"""D-16S cost telemetry of a media import: every paid provider request of an import is one row in the AI cost ledger
(provider, model, audio seconds or tokens, USD), without the media's text. Hermetic: the platform's persistence is a
list, the providers' HTTP is scripted.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from writing_coach import media_translation as mt
from writing_coach.ai import platform as ai_platform
from writing_coach.ai.audio_telemetry import record_audio_operation
from writing_coach.ai.base import sanitize_telemetry
from writing_coach.media_learning import TranscriptSegment
from writing_coach.media_providers.supadata import SupadataTranscriptClient


@pytest.fixture()
def ledger(monkeypatch):
    """The AI cost ledger's rows, as the platform would persist them (after the allow-list)."""
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr(ai_platform, "_persist_operation_telemetry", lambda event: rows.append(sanitize_telemetry(event)))
    return rows


class Reply:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code, self._payload, self.headers = status, payload, {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


SEGMENT = TranscriptSegment("0000000000000000", 0, 0, 2000, "Hello there.")


def test_a_groq_translation_request_is_one_priced_ledger_row(ledger, monkeypatch):
    answer = {"translations": [{"segment_id": "0000000000000000", "translated_meaning": "Xin chao"}]}
    reply = Reply(200, {"choices": [{"message": {"content": json.dumps(answer)}}],
                        "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}})
    monkeypatch.setattr(mt.requests, "post", lambda *_a, **_k: reply)
    assert mt.GroqTranslationProvider("key").translate_batch("en", "vi", (SEGMENT,)) == {"0000000000000000": "Xin chao"}
    (row,) = ledger
    assert (row["capability"], row["provider"], row["model"], row["outcome"]) == (
        "media_translation", "groq", "openai/gpt-oss-120b", "success")
    assert (row["usage"]["prompt_tokens"], row["usage"]["completion_tokens"]) == (1000, 500)
    assert row["cost"]["state"] == "estimated" and row["cost"]["amount"] == pytest.approx(0.00045)
    assert "Hello" not in json.dumps(row), "no text is recorded"


def test_a_failed_groq_translation_request_is_a_failure_row_with_no_amount(ledger, monkeypatch):
    monkeypatch.setattr(mt.requests, "post", lambda *_a, **_k: Reply(500, {}))
    with pytest.raises(mt.TranslationProviderError):
        mt.GroqTranslationProvider("key").translate_batch("en", "vi", (SEGMENT,))
    (row,) = ledger
    assert row["outcome"] == "failure" and row["cost"]["amount"] is None


def test_a_supadata_transcript_request_is_one_unpriced_row_and_a_poll_is_not_counted_again(ledger):
    class Session:
        def get(self, url, **_kwargs):
            if url.endswith("/job-1"):
                return Reply(200, {"status": "queued"})
            return Reply(202, {"jobId": "job-1"})

    client = SupadataTranscriptClient("key", session=Session())  # type: ignore[arg-type]
    client.start("https://www.youtube.com/watch?v=vid00000001", "en")
    client.poll("job-1", "en")
    (row,) = ledger
    assert (row["capability"], row["provider"], row["outcome"]) == ("media_transcript_fallback", "supadata", "success")
    assert row["cost"]["state"] == "unpriced", "no published price is held: never priced as zero"


def test_speech_recognition_of_an_import_is_one_row_per_request_priced_by_its_seconds(ledger):
    record_audio_operation("speech_asr", provider="groq", model="whisper-large-v3-turbo", outcome="success",
                           latency_ms=900, audio_seconds=600.0)
    (row,) = ledger
    assert row["usage"]["audio_seconds"] == 600.0
    assert row["cost"]["amount"] == pytest.approx(600 * 0.04 / 3600, rel=1e-3)
