"""The comprehension-set processor: AI that works on a passage, never writes one.

D-075: "AI is a processor that runs *after* the source exists". Given a
published corpus article, this asks the configured provider for 3-6
comprehension questions - type, prompt, options, answer, an explanation in the
learner's support language, and the words of the passage that settle it - and
keeps only what is grounded in the article's exact body. The result is a
**draft**: nothing here reaches a learner until an Admin reviews and approves
it.

There is no deterministic fallback. A set of invented questions is worse than
no set, so when no provider can answer, the request fails with a clear reason
and the article stays Free Reading.

The capability key is `reading_generator` - the key the admin AI settings
already store for Reading - now doing this job only.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from writing_coach.ai.base import AICapabilityError
from writing_coach.core.support_languages import support_language
from writing_coach.persistence.reading_evidence_repository import (
    QUESTION_TYPES,
    SPANLESS_TYPES,
    ReadingEvidenceError,
    locate_evidence,
)

READING_COMPREHENSION_CAPABILITY = "reading_generator"
GENERATOR_VERSION = "reading-comprehension/1"
MIN_QUESTIONS, MAX_QUESTIONS = 3, 6
_MAX_BODY_CHARS = 12000


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


def _validate(raw: Mapping[str, Any], body: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep the questions that are well formed and grounded; say why others went."""
    kept: list[dict[str, Any]] = []
    issues: list[str] = []
    for index, item in enumerate(raw.get("questions") or []):
        label = f"question {index + 1}"
        if not isinstance(item, Mapping):
            issues.append(f"{label}: not an object")
            continue
        qtype = str(item.get("question_type") or "").strip()
        prompt = str(item.get("prompt") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        options = [str(value).strip() for value in (item.get("options") or [])]
        evidence = str(item.get("evidence_text") or "").strip()
        try:
            correct = int(item.get("correct_index"))
        except (TypeError, ValueError):
            issues.append(f"{label}: no answer index")
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
    try:
        result = generate(
            messages=_messages(
                title=str(article.get("title") or ""), body=body, language=str(article.get("language") or ""),
                level=str(article.get("effective_level") or ""), support_code=support_code,
            ),
            schema=_schema(),
            max_output_tokens=2400,
            temperature=0.2,
            capability_key=READING_COMPREHENSION_CAPABILITY,
        )
    except ReadingEvidenceError:
        raise
    except AICapabilityError as exc:
        # Not configured, disabled, misconfigured or unsupported: the
        # administrator's to fix in AI settings, and said in its own words.
        raise ReadingEvidenceError("reading_processor_unavailable", str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - any provider failure is one refusal
        raise ReadingEvidenceError(
            "reading_processor_failed", "The AI provider could not write questions for this article."
        ) from exc
    data = getattr(result, "data", result)
    if not isinstance(data, Mapping):
        raise ReadingEvidenceError("reading_processor_failed", "The AI provider returned no questions.")
    questions, issues = _validate(data, body)
    if len(questions) < MIN_QUESTIONS:
        raise ReadingEvidenceError(
            "reading_processor_ungrounded",
            f"Only {len(questions)} grounded questions came back; a set needs {MIN_QUESTIONS}. "
            + ("; ".join(issues) if issues else ""),
        )
    model = str(getattr(result, "model", "") or "")
    coverage = sorted({item["question_type"] for item in questions})
    return Processed(
        questions=questions,
        model=model,
        validation={"issues": issues, "coverage": coverage, "kept": len(questions),
                    "returned": len(data.get("questions") or [])},
    )
