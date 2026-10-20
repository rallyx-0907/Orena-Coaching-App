"""The band estimator (Monetisation v2, MONETIZATION_V2_SPEC §3; Intelligence lead): for a piece of the learner's
writing, an estimated IELTS Writing band - or, for Chinese, the HSK level it shows - criterion by criterion, with the
reason for each score, the learner's own words behind it, and the fixes most likely to lift it by half a band.

What makes it trustworthy enough to show, before the pilot calibration proves it:

- **Always an estimate.** Every answer says `estimate: true`; it is never an IELTS or HSK result (the legal copy and
  `becoming_memory` already say so).
- **The overall is the server's.** The model scores each criterion in whole bands; the overall follows the official
  rounding (IELTS: the mean of the criteria, .25 up to the half band, .75 up to the whole band; HSK: the mean, rounded
  down - a level is shown only when every criterion carries it on average).
- **Only the learner's words.** A quoted piece of evidence that is not in the text is dropped, and a fix about words the
  learner did not write is not shown.
- **Too little writing is not scored.** Under half the exam's minimum length the answer is `insufficient_evidence`,
  without a model call; the model may say so too.
- **Calibration before learners.** `agreement` gives the pilot's measures against real scores; until they meet the
  owner's threshold the route is administrators-only and the answer says `experimental: true`.

It is learner text, so it runs on the writing evaluator's capability: its route, its D-104 guard and its spend cap.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CAPABILITY = "writing_evaluator"
EXAMS = ("ielts", "hsk")

# Each criterion: what the model judges, in our own words (never the exam board's descriptors).
CRITERIA: dict[str, dict[str, str]] = {
    "ielts": {
        "task_response": "How fully and relevantly the writing answers the task: a clear position or overview, "
                         "ideas extended and supported.",
        "coherence_cohesion": "How logically the ideas are organised and linked: paragraphing, progression, "
                              "referencing and linking words used accurately and not mechanically.",
        "lexical_resource": "Range and precision of vocabulary: less common words and collocations used "
                            "appropriately; spelling and word formation.",
        "grammatical_range_accuracy": "Range of structures (complex sentences included) and how many sentences "
                                      "are free of errors; punctuation.",
    },
    "hsk": {
        "task_completion": "Whether the writing does what was asked, with relevant, developed content.",
        "vocabulary": "Range and accuracy of words and measure words for the level; characters written correctly.",
        "grammar": "Range and accuracy of sentence patterns (把, 被, complements, 了/过/着, connectives).",
        "coherence": "Order and linking of ideas: connectives, reference, paragraph flow.",
    },
}
SCALE = {"ielts": (0, 9), "hsk": (1, 9)}
# Half the exam's minimum length: below it a band is guessed, not estimated (IELTS words; HSK characters).
MIN_SAMPLE = {("ielts", "task1"): 75, ("ielts", "task2"): 125, ("ielts", "free"): 125,
              ("hsk", "task1"): 40, ("hsk", "task2"): 40, ("hsk", "free"): 40}  # fmt: skip
MAX_FIXES = 3
MAX_EVIDENCE = 2
SUPPORT = {"vi": "Vietnamese", "en": "English", "zh-CN": "Simplified Chinese"}


# Who may ask (spec §3): `admin` (the default) until the pilot calibration agrees with real scores; `off` removes the
# route. Learners get it only through a later, separate change with its plan entitlement.
MODE_ENV = "BAND_ESTIMATOR"
_generate: Callable[..., Any] | None = None  # tests; None: the platform's generate_structured


def mode() -> str:
    import os

    return "off" if os.environ.get(MODE_ENV, "").strip().casefold() == "off" else "admin"


class BandUnavailable(RuntimeError):
    """The model's answer is not a usable estimate (out of range, a criterion missing)."""


class BandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam: Literal["ielts", "hsk"]
    task: Literal["task1", "task2", "free"] = "task2"
    prompt: str = Field(default="", max_length=2000)
    text: str = Field(min_length=1, max_length=8000)
    support: Literal["vi", "en", "zh-CN"] = "vi"


def exam_for_language(language: str) -> str | None:
    """The exam a learner's target language is measured against: English is IELTS, Chinese is HSK; None for any other
    (the route answers 409, never a 500)."""

    return {"en": "ielts", "zh": "hsk"}.get(language)


def ielts_overall(scores: Sequence[int]) -> float:
    """The mean of the criteria, to the nearest half band with .25 and .75 rounded up (the published IELTS rule)."""

    return math.floor(sum(scores) / len(scores) * 2 + 0.5) / 2


def hsk_overall(levels: Sequence[int]) -> int:
    return math.floor(sum(levels) / len(levels))


def hsk_label(level: int) -> str:
    return "HSK 7-9" if level >= 7 else f"HSK {level}"


def sample_size(exam: str, text: str) -> int:
    if exam == "hsk":
        return len(re.findall(r"[㐀-鿿]", text))
    return len(re.findall(r"[A-Za-z][A-Za-z'’-]*", text))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip().casefold()


def _in_text(text: str, quote: Any) -> bool:
    return isinstance(quote, str) and bool(_norm(quote)) and _norm(quote) in _norm(text)


def schema(exam: str) -> dict[str, Any]:
    low, high = SCALE[exam]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["insufficient_evidence", "criteria", "fixes"],
        "properties": {
            "insufficient_evidence": {"type": "boolean"},
            "criteria": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["criterion", "score", "reason", "evidence"],
                "properties": {
                    "criterion": {"type": "string", "enum": list(CRITERIA[exam])},
                    "score": {"type": "integer", "minimum": low, "maximum": high},
                    "reason": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_EVIDENCE},
                }}},
            "fixes": {"type": "array", "maxItems": MAX_FIXES, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["fix", "why", "before", "after"],
                "properties": {"fix": {"type": "string"}, "why": {"type": "string"},
                               "before": {"type": "string"}, "after": {"type": "string"}}}},
        },
    }  # fmt: skip


def messages(request: BandRequest) -> list[dict[str, str]]:
    exam = request.exam
    low, high = SCALE[exam]
    scale = "IELTS Writing band" if exam == "ielts" else "HSK (3.0) level"
    criteria = "\n".join(f"- {key}: {what}" for key, what in CRITERIA[exam].items())
    task = {"task1": "Task 1 (report or letter)", "task2": "Task 2 (essay)", "free": "free writing"}[request.task]
    system = (
        f"You are an experienced examiner estimating the {scale} a piece of writing shows. Score each criterion "
        f"separately with a whole number from {low} to {high}, judging only what the text demonstrates. Be strict and "
        "consistent; do not reward length alone, and do not give the learner the benefit of the doubt. If the text is "
        "too short, off-task or not in the target language to judge, set insufficient_evidence to true and return no "
        f"criteria. Write every reason, fix and why in {SUPPORT[request.support]}. Evidence and `before` are short "
        "exact quotes copied from the learner's text, never paraphrased. Give at most three fixes: the changes most "
        "likely to raise the overall by half a band, most important first; `after` is the corrected version."
    )
    user = (f"Criteria:\n{criteria}\n\nTask type: {task}\nTask prompt: {request.prompt or '(none given)'}\n\n"
            f"Learner's text:\n<<<\n{request.text}\n>>>")  # fmt: skip
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _empty(request: BandRequest, **extra: Any) -> dict[str, Any]:
    return {"exam": request.exam, "task": request.task, "estimate": True, "experimental": True,
            "insufficient_evidence": True, "overall": None, "label": None, "criteria": [], "fixes": [],
            "sample_size": sample_size(request.exam, request.text), **extra}  # fmt: skip


def estimate(request: BandRequest, *, generate: Callable[..., Any] | None = None) -> dict[str, Any]:
    """One estimate. Too short: answered without a model call. A model answer out of range or missing a criterion
    raises `BandUnavailable` - an estimate is never patched up."""

    if sample_size(request.exam, request.text) < MIN_SAMPLE[(request.exam, request.task)]:
        return _empty(request)
    generate = generate or _generate
    if generate is None:
        from writing_coach.ai.platform import generate_structured as generate
    result = generate(messages=messages(request), schema=schema(request.exam), max_output_tokens=1800,
                      temperature=0.0, seed=42, capability_key=CAPABILITY)  # fmt: skip
    data = dict(result.data)
    model = {"provider": result.provider, "model": result.model}
    if data.get("insufficient_evidence"):
        return _empty(request, **model)
    low, high = SCALE[request.exam]
    by_key = {item.get("criterion"): item for item in data.get("criteria") or () if isinstance(item, dict)}
    criteria = []
    for key in CRITERIA[request.exam]:
        item = by_key.get(key)
        score = item.get("score") if item else None
        if not isinstance(score, int) or isinstance(score, bool) or not low <= score <= high:
            raise BandUnavailable(f"criterion {key} has no usable score")
        evidence = [quote for quote in item.get("evidence") or () if _in_text(request.text, quote)][:MAX_EVIDENCE]
        criteria.append({"criterion": key, "score": score, "reason": str(item.get("reason") or ""),
                         "evidence": evidence})  # fmt: skip
    scores = [c["score"] for c in criteria]
    if request.exam == "ielts":
        overall: float | int = ielts_overall(scores)
        label = f"IELTS {overall:.1f}"
    else:
        overall = hsk_overall(scores)
        label = hsk_label(overall)
    fixes = [{key: str(fix.get(key) or "") for key in ("fix", "why", "before", "after")}
             for fix in data.get("fixes") or () if isinstance(fix, dict) and _in_text(request.text, fix.get("before"))]
    return {"exam": request.exam, "task": request.task, "estimate": True, "experimental": True,
            "insufficient_evidence": False, "overall": overall, "label": label, "criteria": criteria,
            "fixes": fixes[:MAX_FIXES], "sample_size": sample_size(request.exam, request.text), **model}  # fmt: skip


def agreement(pairs: Iterable[tuple[float, float]]) -> dict[str, Any]:
    """The pilot's measures (spec §3): Orena's estimate against a real mock or teacher score, per learner sample.
    `within_half_band` is the share no more than half a band away; for HSK levels (whole numbers) it is the exact
    share, a level apart being a different level."""

    rows = [(float(estimate), float(actual)) for estimate, actual in pairs]
    if not rows:
        return {"n": 0, "mean_absolute_error": None, "within_half_band": None, "exact": None}
    gaps = [abs(estimate - actual) for estimate, actual in rows]
    return {"n": len(rows), "mean_absolute_error": round(sum(gaps) / len(gaps), 3),
            "within_half_band": round(sum(gap <= 0.5 for gap in gaps) / len(gaps), 3),
            "exact": round(sum(gap == 0 for gap in gaps) / len(gaps), 3)}  # fmt: skip
