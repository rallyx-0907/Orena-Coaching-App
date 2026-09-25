"""The comprehension processor's one bounded retry.

When a provider answer arrives but cannot make a set - no usable questions, or
fewer than `MIN_QUESTIONS` grounded ones - the processor asks once more, with
the same request and the same validation, and records that it did. A provider
that fails (not configured, unauthorized, unavailable, erroring) is never
retried, nothing is invented, and a second unusable answer fails exactly as
before. English and Chinese take the same path.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from writing_coach.ai.base import (
    AICapabilityDisabled,
    AICapabilityNotConfigured,
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
)
from writing_coach.persistence.reading_evidence_repository import ReadingEvidenceError
from writing_coach.reading_comprehension import MIN_QUESTIONS, process_article

BODIES = {
    "en": (
        "Tom missed the early train. He waited forty minutes on a cold platform. "
        "When the next train came, it was full, so he stood all the way to the city."
    ),
    "zh": "小明错过了早班火车。他在寒冷的站台上等了四十分钟。下一班火车来的时候已经满了，所以他一路站到城里。",
}
SPANS = {"en": ("forty minutes", "it was full"), "zh": ("四十分钟", "已经满了")}


def _article(language: str) -> dict:
    return {"title": "The late train", "body": BODIES[language], "language": language, "effective_level": "B1"}


def _valid(language: str) -> dict:
    first, second = SPANS[language]
    return {"questions": [
        {"question_type": "detail", "prompt": "How long?", "options": ["forty", "ten", "sixty", "five"],
         "correct_index": 0, "explanation": "Bốn mươi phút.", "evidence_text": first},
        {"question_type": "inference", "prompt": "Why stand?", "options": ["full", "late", "broken", "cold"],
         "correct_index": 0, "explanation": "Tàu đã đầy.", "evidence_text": second},
        {"question_type": "main_idea", "prompt": "About?", "options": ["a journey", "a meal", "a race", "a game"],
         "correct_index": 0, "explanation": "Một chuyến đi.", "evidence_text": ""},
    ]}


def _ungrounded(language: str) -> dict:
    data = _valid(language)
    for question in data["questions"][:2]:
        question["evidence_text"] = "words the passage never says"
    return data


class Provider:
    """Answers from a script, one entry per call: a dict or anything else is
    returned as the result's data; an exception instance is raised."""

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    def __call__(self, *, messages, schema, max_output_tokens, temperature, capability_key):
        self.calls.append({"messages": messages, "schema": schema})
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return SimpleNamespace(data=answer, model="stub-model")


def _run(provider: Provider, language: str = "en"):
    return process_article(_article(language), support_code="vi", generate=provider)


@pytest.mark.parametrize("language", ["en", "zh"])
@pytest.mark.parametrize("first", [
    {},                                  # the 4-token answer the sandbox saw: an empty object
    {"questions": []},
    {"questions": "none"},
    None,
    "not an object",
    AIProviderResponseInvalid("AI provider returned an invalid response."),
], ids=["empty-object", "empty-list", "questions-not-a-list", "none", "not-an-object", "invalid-envelope"])
def test_an_unusable_first_answer_is_asked_again_and_a_valid_second_succeeds(language, first, caplog, monkeypatch):
    provider = Provider(first, _valid(language))
    # An in-process Alembic run elsewhere in the suite (`fileConfig` in
    # migrations/env.py) disables loggers that already exist; the app process
    # never runs Alembic, so the logger is enabled here as it is there.
    monkeypatch.setattr(logging.getLogger("writing_coach.reading_comprehension"), "disabled", False)
    with caplog.at_level(logging.WARNING, logger="writing_coach.reading_comprehension"):
        processed = _run(provider, language)
    assert len(provider.calls) == 2
    assert provider.calls[0] == provider.calls[1], "the same request, not a different one"
    assert len(processed.questions) == 3 and processed.model == "stub-model"
    retry = processed.validation["retries"]
    assert len(retry) == 1 and retry[0]["attempt"] == 1
    assert retry[0]["reason"] in {"reading_processor_failed", "reading_processor_ungrounded"}
    assert any("asking once more" in record.getMessage() for record in caplog.records), \
        "a retry is visible in the log"


@pytest.mark.parametrize("language", ["en", "zh"])
def test_an_ungrounded_first_answer_is_asked_again_and_a_valid_second_succeeds(language):
    provider = Provider(_ungrounded(language), _valid(language))
    processed = _run(provider, language)
    assert len(provider.calls) == 2
    assert [item["evidence_text"] for item in processed.questions] == [*SPANS[language], None]
    retry = processed.validation["retries"][0]
    assert retry["reason"] == "reading_processor_ungrounded"
    assert "not in the passage" in retry["detail"]


@pytest.mark.parametrize("first,second,code", [
    ({}, {}, "reading_processor_ungrounded"),
    (None, "still not an object", "reading_processor_failed"),
    ("__ungrounded__", "__ungrounded__", "reading_processor_ungrounded"),
    ({}, AIProviderResponseInvalid("invalid"), "reading_processor_failed"),
])
def test_two_unusable_answers_still_fail_with_the_existing_refusal(first, second, code):
    answers = [_ungrounded("en") if answer == "__ungrounded__" else answer for answer in (first, second)]
    provider = Provider(*answers)
    with pytest.raises(ReadingEvidenceError) as refused:
        _run(provider)
    assert refused.value.code == code
    assert len(provider.calls) == 2, "exactly one retry, never more"


def test_a_short_but_grounded_answer_is_not_padded():
    """Two grounded questions are two: the retry asks again rather than
    inventing a third, and a second short answer fails."""
    short = _valid("en")
    short["questions"] = short["questions"][:MIN_QUESTIONS - 1]
    provider = Provider(short, short)
    with pytest.raises(ReadingEvidenceError) as refused:
        _run(provider)
    assert refused.value.code == "reading_processor_ungrounded"
    assert f"Only {MIN_QUESTIONS - 1} grounded" in str(refused.value)


@pytest.mark.parametrize("failure,code", [
    (AICapabilityNotConfigured("Reading has no provider configured."), "reading_processor_unavailable"),
    (AICapabilityDisabled("Reading is disabled."), "reading_processor_unavailable"),
    (AIProviderNotConfigured("No API key."), "reading_processor_failed"),
    (AIProviderUnavailable("Gemini is not reachable."), "reading_processor_failed"),
    (AIProviderError("HTTP 401 unauthorized"), "reading_processor_failed"),
    (RuntimeError("anything else"), "reading_processor_failed"),
], ids=["capability-not-configured", "capability-disabled", "provider-not-configured", "unavailable",
        "unauthorized", "other-error"])
def test_a_provider_that_fails_is_never_retried(failure, code):
    provider = Provider(failure, _valid("en"))
    with pytest.raises(ReadingEvidenceError) as refused:
        _run(provider)
    assert refused.value.code == code
    assert len(provider.calls) == 1


def test_a_usable_first_answer_is_asked_once_and_records_no_retry():
    provider = Provider(_valid("zh"))
    processed = _run(provider, "zh")
    assert len(provider.calls) == 1
    assert "retries" not in processed.validation


def test_no_provider_is_refused_without_asking():
    with pytest.raises(ReadingEvidenceError) as refused:
        process_article(_article("en"), support_code="vi", generate=None)
    assert refused.value.code == "reading_processor_unavailable"
