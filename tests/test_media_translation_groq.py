"""Groq as the default shared-media translation provider (plan P2).

Nothing here reaches the network. What is worth pinning is the shape of the
request, the strictness of the response check, and the one rule the AI Platform
invariants care about: a failure stops, it never quietly becomes a different
provider's answer.
"""

from __future__ import annotations

import json

import pytest
import requests

from writing_coach import media_translation as mt
from writing_coach.media_learning import TranscriptSegment


def segments(*texts: str) -> tuple[TranscriptSegment, ...]:
    return tuple(
        TranscriptSegment(
            segment_id=f"{index:016x}",
            order=index,
            start_ms=index * 2000,
            end_ms=(index + 1) * 2000,
            original_text=text,
        )
        for index, text in enumerate(texts)
    )


class FakeResponse:
    def __init__(self, payload: object, *, status: int = 200, headers: dict[str, str] | None = None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> object:
        return self._payload


def envelope(body: object) -> dict[str, object]:
    return {"choices": [{"message": {"content": json.dumps(body)}}]}


def install(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> list[dict]:
    calls: list[dict] = []

    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        calls.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(mt.requests, "post", fake_post)
    return calls


def test_translates_a_batch_and_returns_every_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = segments("清晨。", "我学习中文。")
    install(
        monkeypatch,
        FakeResponse(
            envelope(
                {
                    "translations": [
                        {"segment_id": batch[0].segment_id, "translated_meaning": "Sáng sớm."},
                        {"segment_id": batch[1].segment_id, "translated_meaning": "Tôi học tiếng Trung."},
                    ]
                }
            )
        ),
    )

    provider = mt.GroqTranslationProvider("test-key")
    assert provider.translate_batch("zh", "vi", batch) == {
        batch[0].segment_id: "Sáng sớm.",
        batch[1].segment_id: "Tôi học tiếng Trung.",
    }


def test_transcript_correction_uses_one_bounded_structured_configured_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    cues = (SimpleNamespace(text="Hello world"), SimpleNamespace(text="we are ready"))
    calls = install(monkeypatch, FakeResponse({
        **envelope({"lines": [
            {"index": 0, "text": "Hello, world.", "reason": "punctuation"},
            {"index": 1, "text": "We are ready.", "reason": "Restored sentence capitalization."},
        ]}),
        "usage": {"prompt_tokens": 90, "completion_tokens": 20},
    }))
    provider = mt.GroqTranslationProvider("test-key", model="configured-model")
    captured: list[tuple[str, dict]] = []
    with mt.usage_sink(lambda model, usage: captured.append((model, usage))):
        result = provider.correct(language="en", cues=cues, title="A title", description="A description")

    assert result["texts"] == ["Hello, world.", "We are ready."]
    # A code from the closed list is kept; a sentence (in any language) is stored as the neutral `other`, never as free text.
    assert result["reasons"] == ["punctuation", "other"]
    prompt = calls[0]["json"]["messages"][1]["content"]
    assert "exactly one code" in prompt and "homophone" in prompt and "No change." not in prompt
    assert result["model"] == "configured-model"
    assert len(calls) == 1
    body = calls[0]["json"]
    assert body["model"] == "configured-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_completion_tokens"] <= provider._reservation_cap()
    assert "punctuation" in body["messages"][0]["content"]
    assert captured == [("configured-model", {"prompt_tokens": 90, "completion_tokens": 20})]


def test_transcript_correction_rejects_malformed_result_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    cues = (SimpleNamespace(text="Hello world"),)
    calls = install(monkeypatch, FakeResponse(envelope({"lines": [{"index": 0, "text": "Hello."}, {"index": 0, "text": "Hello!"}]})))
    provider = mt.GroqTranslationProvider("test-key", model="configured-model")

    with pytest.raises(mt.TranslationProviderError, match="malformed"):
        provider.correct(language="en", cues=cues)
    assert len(calls) == 1


def test_transcript_correction_requires_truthful_per_line_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    cues = (SimpleNamespace(text="Hello world"),)
    calls = install(monkeypatch, FakeResponse(envelope({"lines": [{"index": 0, "text": "Hello, world."}]})))
    provider = mt.GroqTranslationProvider("test-key", model="configured-model")

    with pytest.raises(mt.TranslationProviderError, match="malformed"):
        provider.correct(language="en", cues=cues)
    assert len(calls) == 1


def test_transcript_correction_rate_limit_is_one_failed_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    calls = install(monkeypatch, FakeResponse({}, status=429, headers={"retry-after": "1"}))
    provider = mt.GroqTranslationProvider("test-key", model="configured-model")
    with pytest.raises(mt.TranslationProviderError) as caught:
        provider.correct(language="zh", cues=(SimpleNamespace(text="守株待兔"),))
    assert caught.value.reason == "rate_limited"
    assert len(calls) == 1


def test_the_request_asks_for_json_and_does_not_send_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both halves were learned by measurement.

    `response_format: json_object` is what stops a reasoning model spending its
    whole budget thinking and returning an empty string. `reasoning_effort` is
    unnecessary in that mode and is rejected outright by the other Groq models
    (`qwen3.6` accepts only none/default, `groq/compound` refuses it), so sending
    it would break the moment the model is changed.
    """
    batch = segments("好。")
    calls = install(
        monkeypatch,
        FakeResponse(
            envelope({"translations": [{"segment_id": batch[0].segment_id, "translated_meaning": "Tốt."}]})
        ),
    )

    mt.GroqTranslationProvider("test-key").translate_batch("zh", "vi", batch)

    body = calls[0]["json"]
    assert body["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in body
    assert body["temperature"] == 0.0
    assert body["model"] == "openai/gpt-oss-120b"
    assert calls[0]["url"].endswith("/chat/completions")
    # Every segment id has to reach the model, or it cannot return them.
    assert batch[0].segment_id in body["messages"][-1]["content"]


def test_quota_headers_are_captured_for_the_admin_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = segments("好。")
    install(
        monkeypatch,
        FakeResponse(
            envelope({"translations": [{"segment_id": batch[0].segment_id, "translated_meaning": "Tốt."}]}),
            headers={
                "x-ratelimit-limit-requests": "1000",
                "x-ratelimit-remaining-requests": "997",
                "content-type": "application/json",
            },
        ),
    )

    provider = mt.GroqTranslationProvider("test-key")
    provider.translate_batch("zh", "vi", batch)

    assert provider.last_quota == {
        "x-ratelimit-limit-requests": "1000",
        "x-ratelimit-remaining-requests": "997",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"translations": "not a list"},
        {"translations": [{"segment_id": "unknown-id", "translated_meaning": "x"}]},
        {"translations": [{"segment_id": "0000000000000000", "translated_meaning": "   "}]},
        {"translations": [{"segment_id": "0000000000000000"}]},
        {"nothing": True},
    ],
)
def test_a_malformed_answer_is_refused_rather_than_half_used(
    monkeypatch: pytest.MonkeyPatch, payload: dict
) -> None:
    batch = segments("好。")
    install(monkeypatch, FakeResponse(envelope(payload)))

    with pytest.raises(mt.TranslationProviderError):
        mt.GroqTranslationProvider("test-key").translate_batch("zh", "vi", batch)


def test_a_duplicate_segment_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    batch = segments("好。")
    same = {"segment_id": batch[0].segment_id, "translated_meaning": "Tốt."}
    install(monkeypatch, FakeResponse(envelope({"translations": [same, same]})))

    with pytest.raises(mt.TranslationProviderError):
        mt.GroqTranslationProvider("test-key").translate_batch("zh", "vi", batch)


def test_a_transport_failure_stops_there(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> FakeResponse:
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(mt.requests, "post", fake_post)

    with pytest.raises(mt.TranslationProviderError):
        mt.GroqTranslationProvider("test-key").translate_batch("zh", "vi", segments("好。"))


def test_an_unconfigured_provider_refuses_instead_of_calling(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install(monkeypatch, FakeResponse(envelope({"translations": []})))
    provider = mt.GroqTranslationProvider("")

    assert provider.configured is False
    with pytest.raises(mt.TranslationProviderError):
        provider.translate_batch("zh", "vi", segments("好。"))
    assert calls == []


def test_it_never_falls_back_to_another_provider() -> None:
    """`ARCHITECTURE_INVARIANTS.md`: no provider-to-provider fallback.

    Choosing the local service instead is an operator decision made once at
    startup, not something this class may do when a request fails.
    """
    source = mt.GroqTranslationProvider.__doc__ or ""
    assert "fallback" in source.lower()
    module = __import__("pathlib").Path(mt.__file__).read_text(encoding="utf-8")
    groq_body = module[module.index("class GroqTranslationProvider") : module.index("class MediaTranslationService")]
    assert "LocalHttpTranslationProvider" not in groq_body


def test_both_providers_satisfy_the_same_boundary() -> None:
    for provider in (mt.GroqTranslationProvider("k"), mt.LocalHttpTranslationProvider("http://x")):
        assert isinstance(provider.engine_id, str) and provider.engine_id
        assert isinstance(provider.model_version, str)
        assert callable(provider.translate_batch)


# ------------------------------------------------- which engine is chosen ---


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_an_empty_setting_means_unset_not_invalid(blank) -> None:
    """The trap this helper exists for.

    compose passes every optional variable through as an empty string, and
    `os.getenv(name, default)` only falls back when the name is absent. Reading
    "" as an invalid value stopped the application from importing at all.
    """
    assert mt.resolve_translation_provider_id(blank, groq_key="k") == "groq"
    assert mt.resolve_translation_provider_id(blank, groq_key="") == "local"


@pytest.mark.parametrize(("value", "expected"), [("groq", "groq"), ("LOCAL", "local"), (" Groq ", "groq")])
def test_an_explicit_setting_wins_and_is_normalised(value: str, expected: str) -> None:
    assert mt.resolve_translation_provider_id(value, groq_key="k") == expected


def test_an_unknown_engine_is_refused() -> None:
    with pytest.raises(ValueError, match="MEDIA_TRANSLATION_PROVIDER"):
        mt.resolve_translation_provider_id("openai", groq_key="k")


def test_groq_without_a_key_fails_closed_rather_than_silently_using_local() -> None:
    # Falling back here would be exactly the silent failover the AI Platform
    # invariants forbid: the operator asked for Groq and must be told it cannot
    # run, not quietly given a different engine.
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        mt.resolve_translation_provider_id("groq", groq_key="")

