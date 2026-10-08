"""Groq translation: token reservation, language naming, oversized requests.

Two defects these lock down. The provider reserved `max_tokens: 8000` against an
organisation ceiling of 8000, so a single request claimed the whole per-minute
budget and returned HTTP 413 whenever the bucket was not already full - which
made it look intermittent. And it carried a private three-language name map, so
any language outside vi/en/zh reached the prompt as a bare code.
"""

from __future__ import annotations

import json
import pytest

from writing_coach.media_translation import (
    DEFAULT_GROQ_MAX_COMPLETION_TOKENS,
    GROQ_MAX_COMPLETION_TOKENS_ENV,
    MAX_TRANSLATION_BATCH_SEGMENTS,
    GroqTranslationProvider,
    TranslationProviderError,
    resolve_max_completion_tokens,
)
from writing_coach.media_learning import TranscriptSegment


def segments(count: int) -> tuple[TranscriptSegment, ...]:
    return tuple(
        TranscriptSegment(f"s:{i:03d}", i, i * 1000, (i + 1) * 1000, f"Line number {i}.")
        for i in range(count)
    )


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None) -> None:
        self.status_code = status
        self._payload = payload or {}
        self.headers = {"x-ratelimit-limit-tokens": "8000"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


def completion(segment_ids) -> FakeResponse:
    body = {"translations": [
        {"segment_id": sid, "translated_meaning": f"meaning-{sid}"} for sid in segment_ids
    ]}
    return FakeResponse(200, {"choices": [{"message": {"content": json.dumps(body)}}]})


class Recorder:
    """Captures each outgoing request body, and answers as instructed."""

    def __init__(self, too_large_over: int | None = None) -> None:
        self.bodies: list[dict] = []
        self.too_large_over = too_large_over

    def __call__(self, url, json=None, headers=None, timeout=None):  # noqa: A002
        self.bodies.append(json)
        ids = [line.split("\t")[0] for line in json["messages"][1]["content"].splitlines()
               if "\t" in line]
        if self.too_large_over is not None and len(ids) > self.too_large_over:
            return FakeResponse(413, {"error": {
                "code": "rate_limit_exceeded",
                "message": "Request too large for model `openai/gpt-oss-120b`",
            }})
        return completion(ids)


def provider(monkeypatch, recorder: Recorder, **kwargs) -> GroqTranslationProvider:
    import writing_coach.media_translation as module
    monkeypatch.setattr(module.requests, "post", recorder)
    return GroqTranslationProvider("test-key", **kwargs)


# --- the token reservation is bounded and configured ------------------------

def test_a_normal_batch_does_not_request_eight_thousand_output_tokens(monkeypatch) -> None:
    recorder = Recorder()
    engine = provider(monkeypatch, recorder)
    engine.translate_batch("en", "ja", segments(MAX_TRANSLATION_BATCH_SEGMENTS))

    body = recorder.bodies[0]
    assert "max_tokens" not in body, "the deprecated field must be gone"
    reserved = body["max_completion_tokens"]
    assert reserved == DEFAULT_GROQ_MAX_COMPLETION_TOKENS == 2048
    assert reserved < 8000, "a request must not reserve the whole organisation ceiling"


def test_the_reservation_is_configurable_and_validated() -> None:
    assert resolve_max_completion_tokens(env={}) == DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    assert resolve_max_completion_tokens(env={GROQ_MAX_COMPLETION_TOKENS_ENV: "1024"}) == 1024

    # Absurd, negative, zero, non-numeric and boolean values fall back rather
    # than silently reserving something unreasonable.
    for bad in ("0", "-5", "999999", "abc", "", "  "):
        assert resolve_max_completion_tokens(
            env={GROQ_MAX_COMPLETION_TOKENS_ENV: bad}
        ) == DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    assert resolve_max_completion_tokens(True) == DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    assert resolve_max_completion_tokens(100) == DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    assert resolve_max_completion_tokens(4096) == 4096


def test_an_explicit_reservation_reaches_the_request(monkeypatch) -> None:
    recorder = Recorder()
    engine = provider(monkeypatch, recorder, max_completion_tokens=1024)
    engine.translate_batch("en", "es", segments(2))
    assert recorder.bodies[0]["max_completion_tokens"] == 1024


# --- an oversized request is split, never blindly retried -------------------

def test_an_oversized_request_is_split_without_losing_segments(monkeypatch) -> None:
    # The provider refuses anything over 4 segments as too large.
    recorder = Recorder(too_large_over=4)
    engine = provider(monkeypatch, recorder)

    wanted = segments(8)
    result = engine.translate_batch("en", "ja", wanted)

    assert set(result) == {s.segment_id for s in wanted}, "no segment id may be lost"
    assert len(result) == 8
    # The first attempt was the full batch; it then halved rather than retrying
    # the identical oversized request.
    sizes = [len([line for line in b["messages"][1]["content"].splitlines() if "\t" in line])
             for b in recorder.bodies]
    assert sizes[0] == 8
    assert 8 not in sizes[1:], "the identical oversized request must not be repeated"
    assert sum(s for s in sizes[1:]) >= 8


def test_splitting_gives_up_truthfully_rather_than_looping(monkeypatch) -> None:
    # Nothing is ever small enough: it must fail, not recurse forever.
    recorder = Recorder(too_large_over=0)
    engine = provider(monkeypatch, recorder)

    try:
        engine.translate_batch("en", "ja", segments(8))
    except TranslationProviderError as exc:
        assert "token ceiling" in str(exc)
    else:
        raise AssertionError("an unsplittable oversized request must fail truthfully")
    assert len(recorder.bodies) < 40, "splitting must be bounded"


@pytest.mark.parametrize("source,target", [("en", "vi"), ("zh", "en")])
def test_json_generation_failure_splits_without_losing_lines(monkeypatch, source, target):
    recorder = Recorder()
    real = recorder.__call__

    def post(url, **kwargs):
        ids = [line.split("\t")[0] for line in kwargs["json"]["messages"][1]["content"].splitlines() if "\t" in line]
        if len(ids) > 2:
            recorder.bodies.append(kwargs["json"])
            return FakeResponse(400, {"error": {"code": "json_validate_failed"}})
        return real(url, **kwargs)

    import writing_coach.media_translation as module
    monkeypatch.setattr(module.requests, "post", post)
    wanted = segments(8)
    result = GroqTranslationProvider("test-key").translate_batch(source, target, wanted)
    assert set(result) == {s.segment_id for s in wanted}
    assert len(recorder.bodies) == 7


def test_long_provenance_ids_return_to_the_correct_canonical_lines(monkeypatch):
    from dataclasses import replace
    recorder = Recorder()
    engine = provider(monkeypatch, recorder)
    wanted = tuple(replace(s, segment_id=f"source:segment:{'a' * 96}:{i}") for i, s in enumerate(segments(6)))
    result = engine.translate_batch("en", "vi", wanted)
    assert set(result) == {s.segment_id for s in wanted}
    assert all(len(line.split("\t")[0]) < 64 for b in recorder.bodies
               for line in b["messages"][1]["content"].splitlines() if "\t" in line)


# --- the prompt names languages from the canonical registry -----------------

def test_the_prompt_names_the_language_not_its_code(monkeypatch) -> None:
    recorder = Recorder()
    engine = provider(monkeypatch, recorder)

    for code, expected in (("ja", "Japanese"), ("es", "Spanish"), ("ko", "Korean"),
                           ("fr", "French"), ("vi", "Vietnamese")):
        recorder.bodies.clear()
        engine.translate_batch("en", code, segments(1))
        prompt = recorder.bodies[0]["messages"][1]["content"]
        assert f"into natural {expected}" in prompt, f"{code} must be named {expected}"
        assert f"into natural {code} " not in prompt, "a bare code must not reach the prompt"


def test_the_source_language_is_named_too(monkeypatch) -> None:
    recorder = Recorder()
    engine = provider(monkeypatch, recorder)
    engine.translate_batch("zh", "ja", segments(1))
    prompt = recorder.bodies[0]["messages"][1]["content"]
    assert "Simplified Chinese line" in prompt


def test_the_provider_keeps_no_language_map_of_its_own() -> None:
    """One registry for the product, not one per AI provider."""

    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "writing_coach/media_translation.py").read_text(encoding="utf-8")
    assert "_LANGUAGE_NAMES" not in source
    assert "core.support_languages import" in source
