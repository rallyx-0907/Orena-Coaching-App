"""The comprehension-set processor: AI that works on a passage, never writes one.

D-082: "AI is a processor that runs *after* the source exists". Given a
published corpus article, this asks the configured provider for 3-6
comprehension questions - type, prompt, options, answer, an explanation in the
learner's support language, and the words of the passage that settle it - and
keeps only what is grounded in the article's exact body. The result is a
**draft**: nothing here reaches a learner until an Admin reviews and approves
it.

There is no deterministic fallback. A set of invented questions is worse than
no set, so when no provider can answer, the request fails with a clear reason
and the article stays Free Reading.

One bounded retry: when a result arrives but cannot make a set - no usable
questions, or fewer than `MIN_QUESTIONS` grounded ones - the same request is
made once more and validated the same way. It is logged, and kept in the set's
`validation.retries` when the second answer succeeds; a second unusable answer
fails as before. A provider that fails (not configured, unauthorized,
unavailable, erroring) is never retried.

The capability key is `reading_generator` - the key the admin AI settings
already store for Reading - now doing this job only.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from writing_coach.ai.base import AICapabilityError, AIProviderResponseInvalid
from writing_coach.core.support_languages import support_language
from writing_coach.persistence.reading_evidence_repository import (
    QUESTION_TYPES,
    SPANLESS_TYPES,
    ReadingEvidenceError,
    locate_evidence,
)

_logger = logging.getLogger(__name__)

READING_COMPREHENSION_CAPABILITY = "reading_generator"
GENERATOR_VERSION = "reading-comprehension/1"
MIN_QUESTIONS, MAX_QUESTIONS = 3, 6
# One more request when a result arrives but cannot make a set (no questions,
# or too few grounded ones). Never for a provider that failed.
RETRIES_ON_UNUSABLE_RESULT = 1
_MAX_BODY_CHARS = 12000


class UnusableResult(ReadingEvidenceError):
    """A provider answer that arrived but cannot make a set. The only refusal
    that is retried; callers see its ordinary reason code."""


@dataclass
class Processed:
    questions: list[dict[str, Any]]
    model: str
    validation: dict[str, Any] = field(default_factory=dict)


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": MIN_QUESTIONS,
                "maxItems": MAX_QUESTIONS,
                "items": {
                    "type": "object",
                    "properties": {
                        "question_type": {"type": "string", "enum": sorted(QUESTION_TYPES)},
                        "prompt": {"type": "string"},
                        "options": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "string"}},
                        "correct_index": {"type": "integer", "minimum": 0, "maximum": 3},
                        "explanation": {"type": "string"},
                        "evidence_text": {"type": "string"},
                    },
                    "required": ["question_type", "prompt", "options", "correct_index", "explanation",
                                 "evidence_text"],
                },
            },
        },
        "required": ["questions"],
    }


def _messages(*, title: str, body: str, language: str, level: str, support_code: str) -> list[dict[str, str]]:
    definition = support_language(support_code)
    support_name = definition.translation_label if definition else support_code
    passage_language = "Chinese" if language == "zh" else "English"
    system = (
        "You write reading-comprehension questions for a published passage a language learner will read. "
        "You never rewrite, summarize into, or extend the passage: it is fixed. "
        f"Write {MIN_QUESTIONS} to {MAX_QUESTIONS} multiple-choice questions in {passage_language}, "
        "each with exactly four distinct options and one correct answer. "
        "Use a mix of these types: " + ", ".join(sorted(QUESTION_TYPES)) + ". "
        "For every type except main_idea and authors_purpose, evidence_text must be words copied exactly, "
        "character for character, from the passage - the shortest span that settles the answer. "
        "For main_idea and authors_purpose, evidence_text may be an empty string. "
        f"Write each explanation in {support_name}, briefly, saying why the answer is right."
    )
    user = (
        f"Level of the passage: {level or 'unknown'}\n"
        f"Title: {title}\n\n"
        f"Passage:\n{body[:_MAX_BODY_CHARS]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class _Malformed(ValueError):
    """A question whose structure is not the schema's."""


def _text(item: Mapping[str, Any], key: str, label: str) -> str:
    value = item.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _Malformed(f"{label}: {key} is not text")
    return value.strip()


def _options(item: Mapping[str, Any], label: str) -> list[str]:
    value = item.get("options")
    if not isinstance(value, list):
        raise _Malformed(f"{label}: options is not a list")
    options = []
    for option in value:
        # Text, or a plain number a model wrote without quotes (a year, a
        # count); never an object, a list, a boolean or null.
        if isinstance(option, bool) or not isinstance(option, (str, int, float)):
            raise _Malformed(f"{label}: an option is not text")
        options.append(str(option).strip())
    return options


def _answer_index(item: Mapping[str, Any], label: str) -> int:
    value = item.get("correct_index")
    # An integer, however a model spelled it (1, 1.0, "1"); never a fraction,
    # a boolean, infinity or anything else.
    if isinstance(value, bool):
        raise _Malformed(f"{label}: no answer index")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        return int(value.strip())
    raise _Malformed(f"{label}: no answer index")


def question_list(raw: Mapping[str, Any]) -> list[Any] | None:
    """The questions as a list: an absent or null value is no questions; any
    other non-list is not a question list at all (None)."""
    value = raw.get("questions")
    if value is None:
        return []
    return value if isinstance(value, list) else None


def _validate(raw: Mapping[str, Any], body: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep the questions that are well formed and grounded; say why others
    went. The caller has checked that `questions` is a list; a question whose
    structure is not the schema's is set aside with its reason, never allowed
    to raise."""
    kept: list[dict[str, Any]] = []
    issues: list[str] = []
    for index, item in enumerate(question_list(raw) or []):
        label = f"question {index + 1}"
        if not isinstance(item, Mapping):
            issues.append(f"{label}: not an object")
            continue
        try:
            qtype = _text(item, "question_type", label)
            prompt = _text(item, "prompt", label)
            explanation = _text(item, "explanation", label)
            evidence = _text(item, "evidence_text", label)
            options = _options(item, label)
            correct = _answer_index(item, label)
        except _Malformed as exc:
            issues.append(str(exc))
            continue
        if qtype not in QUESTION_TYPES:
            issues.append(f"{label}: unknown type {qtype!r}")
        elif not prompt or not explanation:
            issues.append(f"{label}: missing prompt or explanation")
        elif not 2 <= len(options) <= 6 or any(not value for value in options) or \
                len({value.casefold() for value in options}) != len(options):
            issues.append(f"{label}: options must be 2-6, non-empty and distinct")
        elif not 0 <= correct < len(options):
            issues.append(f"{label}: the answer is not one of the options")
        elif evidence and locate_evidence(body, evidence) is None:
            issues.append(f"{label}: its evidence is not in the passage")
        elif not evidence and qtype not in SPANLESS_TYPES:
            issues.append(f"{label}: a {qtype} question must cite the passage")
        else:
            kept.append({
                "question_type": qtype, "prompt": prompt, "options": options, "correct_index": correct,
                "explanation": explanation, "evidence_text": evidence or None, "rank": len(kept),
            })
    return kept[:MAX_QUESTIONS], issues


def process_article(
    article: Mapping[str, Any],
    *,
    support_code: str,
    generate: Callable[..., Any] | None,
) -> Processed:
    """Ask the provider for a draft set for this article, grounded in its body."""
    if generate is None:
        raise ReadingEvidenceError("reading_processor_unavailable", "No AI provider is configured for Reading.")
    body = str(article.get("body") or "")
    if not body.strip():
        raise ReadingEvidenceError("reading_article_empty", "The article has no text to ask about.")
    messages = _messages(
        title=str(article.get("title") or ""), body=body, language=str(article.get("language") or ""),
        level=str(article.get("effective_level") or ""), support_code=support_code,
    )
    retries: list[dict[str, Any]] = []
    for attempt in range(1 + RETRIES_ON_UNUSABLE_RESULT):
        # A provider that fails - not configured, unauthorized, unavailable,
        # erroring - raises here and is never retried: asking again would not
        # change the answer, and the administrator has to see it.
        try:
            return _checked(_ask(generate, messages), body, retries)
        except UnusableResult as exc:
            if attempt == RETRIES_ON_UNUSABLE_RESULT:
                raise
            # A result arrived but cannot make a set - no questions, or too few
            # grounded ones. Models do this now and then; one more request, the
            # same one, and the same validation. Nothing is invented and no
            # grounding rule is relaxed.
            retries.append({"attempt": attempt + 1, "reason": exc.code, "detail": str(exc)[:300]})
            _logger.warning(
                "reading comprehension: unusable provider result (%s), asking once more: %s",
                exc.code, str(exc)[:300],
            )
    raise AssertionError("unreachable")  # pragma: no cover


def _ask(generate: Callable[..., Any], messages: list[dict[str, str]]) -> Any:
    try:
        return generate(
            messages=messages,
            schema=_schema(),
            max_output_tokens=2400,
            temperature=0.2,
            capability_key=READING_COMPREHENSION_CAPABILITY,
        )
    except ReadingEvidenceError:
        raise
    except AIProviderResponseInvalid as exc:
        # The provider answered, but not with a usable payload.
        raise UnusableResult("reading_processor_failed", "The AI provider returned no usable questions.") from exc
    except AICapabilityError as exc:
        # Not configured, disabled, misconfigured or unsupported: the
        # administrator's to fix in AI settings, and said in its own words.
        raise ReadingEvidenceError("reading_processor_unavailable", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - any provider failure is one refusal
        raise ReadingEvidenceError(
            "reading_processor_failed", "The AI provider could not write questions for this article."
        ) from exc


def _checked(result: Any, body: str, retries: list[dict[str, Any]]) -> Processed:
    """A usable draft from one provider result, or the refusal saying why not."""
    data = getattr(result, "data", result)
    if not isinstance(data, Mapping):
        raise UnusableResult("reading_processor_failed", "The AI provider returned no questions.")
    returned = question_list(data)
    if returned is None:
        raise UnusableResult("reading_processor_failed", "The AI provider's questions are not a list.")
    try:
        questions, issues = _validate(data, body)
    except Exception as exc:  # noqa: BLE001 - a malformed answer is unusable, never a 500
        _logger.warning("reading comprehension: a provider answer could not be validated", exc_info=True)
        raise UnusableResult("reading_processor_failed", "The AI provider's questions could not be read.") from exc
    if len(questions) < MIN_QUESTIONS:
        raise UnusableResult(
            "reading_processor_ungrounded",
            f"Only {len(questions)} grounded questions came back; a set needs {MIN_QUESTIONS}. "
            + ("; ".join(issues) if issues else ""),
        )
    model = str(getattr(result, "model", "") or "")
    coverage = sorted({item["question_type"] for item in questions})
    validation: dict[str, Any] = {"issues": issues, "coverage": coverage, "kept": len(questions),
                                  "returned": len(returned)}
    if retries:
        # Kept with the set, so the Admin reviewing it - and anyone reading the
        # sets later - sees that the provider's first answer was unusable.
        validation["retries"] = list(retries)
    return Processed(questions=questions, model=model, validation=validation)
