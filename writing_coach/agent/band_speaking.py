"""The speaking band estimator (Monetisation v2, MONETIZATION_V2_SPEC §3; Intelligence lead): for something the learner
said, an estimated IELTS Speaking band - or the HSK level the speech shows - criterion by criterion, from the transcript
(what was said) and the pronunciation assessment's scores (how it sounded), with the reason for each score, the
learner's own words behind it, and the fixes most likely to lift it.

It follows the writing estimator (agent/band.py) in everything that makes it trustworthy: always an estimate, the
overall is the server's (the same rounding), only the learner's own words are quoted, too little is not scored and costs
nothing, a malformed answer is refused, and it is for administrators until the pilot calibration agrees.

What is particular to speech:

- **The rate is measured, not guessed.** Words (or characters) per minute come from the transcript and the duration and
  are handed to the model as a fact.
- **Pronunciation needs its evidence.** Without the pronunciation assessment's scores the pronunciation criterion is not
  asked for and there is no overall (`missing: ["pronunciation"]`) - never a band from text alone.
- **The transcript is machine-heard.** Speech recognition can drop or invent words (it invents words from trailing
  silence); the model is told so and must not mark the learner down for what looks like a recognition error.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from writing_coach.agent import band

CRITERIA: dict[str, dict[str, str]] = {
    "ielts": {
        "fluency_coherence": "Speaking at length without noticeable effort or long pauses; ideas in a logical order "
                             "with linking that is natural, not mechanical; little self-correction or repetition.",
        "lexical_resource": "Range and precision of vocabulary for the topic: idiomatic and less common words used "
                            "appropriately; paraphrasing when a word is missing.",
        "grammatical_range_accuracy": "Range of structures, complex sentences included, and how many sentences are "
                                      "free of errors.",
        "pronunciation": "How easily the speech is understood: individual sounds, word and sentence stress, rhythm and "
                         "intonation. Judge from the pronunciation assessment's scores.",
    },
    "hsk": {
        "task_completion": "Whether the answer does what was asked, with relevant, developed content.",
        "vocabulary": "Range and accuracy of words and measure words for the level.",
        "grammar": "Range and accuracy of sentence patterns (把, 被, complements, 了/过/着, connectives).",
        "fluency_pronunciation": "Fluency, tones and sounds: judge from the pronunciation assessment's scores and the "
                                 "speech rate.",
    },
}
PRONUNCIATION_CRITERION = {"ielts": "pronunciation", "hsk": "fluency_pronunciation"}
MIN_WORDS = {"ielts": 50, "hsk": 30}  # words for English, characters for Chinese
MIN_SECONDS = 30
PRONUNCIATION_KEYS = ("pron_score", "accuracy_score", "fluency_score", "prosody_score", "completeness_score")


class Pronunciation(BaseModel):
    """The pronunciation assessment's 0-100 scores for the take (POST /api/speech/pronunciation)."""

    model_config = ConfigDict(extra="ignore")

    pron_score: float | None = Field(default=None, ge=0, le=100)
    accuracy_score: float | None = Field(default=None, ge=0, le=100)
    fluency_score: float | None = Field(default=None, ge=0, le=100)
    prosody_score: float | None = Field(default=None, ge=0, le=100)
    completeness_score: float | None = Field(default=None, ge=0, le=100)


class SpeakingBandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam: Literal["ielts", "hsk"]
    part: Literal["part1", "part2", "part3", "free"] = "free"
    prompt: str = Field(default="", max_length=2000)
    transcript: str = Field(min_length=1, max_length=8000)
    duration_seconds: float = Field(gt=0, le=1800)
    pronunciation: Pronunciation | None = None
    support: Literal["vi", "en", "zh-CN"] = "vi"


def _assessed(request: SpeakingBandRequest) -> dict[str, float]:
    if request.pronunciation is None:
        return {}
    scores = request.pronunciation.model_dump()
    return {key: scores[key] for key in PRONUNCIATION_KEYS if scores.get(key) is not None}


def _criteria(request: SpeakingBandRequest) -> list[str]:
    keys = list(CRITERIA[request.exam])
    return keys if _assessed(request).get("pron_score") is not None else [
        key for key in keys if key != PRONUNCIATION_CRITERION[request.exam]]


def measures(request: SpeakingBandRequest) -> dict[str, Any]:
    """`words` and `rate_per_minute` count words for English and characters for Chinese (`unit`)."""

    words = band.sample_size(request.exam, request.transcript)
    return {"words": words, "unit": "word" if request.exam == "ielts" else "character",
            "seconds": round(request.duration_seconds, 1),
            "rate_per_minute": round(words * 60 / request.duration_seconds)}  # fmt: skip


def messages(request: SpeakingBandRequest) -> list[dict[str, str]]:
    exam = request.exam
    low, high = band.SCALE[exam]
    scale = "IELTS Speaking band" if exam == "ielts" else "HSK (3.0) level"
    keys = _criteria(request)
    criteria = "\n".join(f"- {key}: {CRITERIA[exam][key]}" for key in keys)
    rate = measures(request)
    unit = "words" if exam == "ielts" else "characters"
    assessed = _assessed(request)
    pronunciation = ", ".join(f"{key} {value:g}" for key, value in assessed.items()) or "(not assessed)"
    system = (
        f"You are an experienced examiner estimating the {scale} a learner's spoken answer shows. Score each criterion "
        f"listed separately with a whole number from {low} to {high}, judging only what the evidence shows. Be strict "
        "and consistent. The transcript was produced by automatic speech recognition: it can drop words, mishear them, "
        "or invent short phrases from silence (such as 'thank you' at the end). Do not mark the learner down for what "
        "looks like a recognition error, and never quote such a phrase as evidence. If the answer is too short, "
        "off-task or not in the target language to judge, set insufficient_evidence to true and return no criteria. "
        f"Write every reason, fix and why in {band.SUPPORT[request.support]}. Evidence and `before` are short exact "
        "quotes copied from the transcript. Give at most three fixes, most important first; `after` is a better way "
        "to say it."
    )
    user = (f"Criteria:\n{criteria}\n\nPart: {request.part}\nQuestion: {request.prompt or '(none given)'}\n"
            f"Measured: {rate['words']} {unit} in {rate['seconds']} s, {rate['rate_per_minute']} {unit} per minute.\n"
            f"Pronunciation assessment (0-100): {pronunciation}\n\nTranscript:\n<<<\n{request.transcript}\n>>>")  # fmt: skip
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _empty(request: SpeakingBandRequest, **extra: Any) -> dict[str, Any]:
    return {"skill": "speaking", "exam": request.exam, "part": request.part, "estimate": True, "experimental": True,
            "insufficient_evidence": True, "overall": None, "label": None, "criteria": [], "fixes": [],
            "missing": [], "measures": measures(request), **extra}  # fmt: skip


def estimate(request: SpeakingBandRequest, *, generate: Callable[..., Any] | None = None) -> dict[str, Any]:
    """One estimate. Too little speech: answered without a model call. A model answer out of range or missing a
    criterion raises `band.BandUnavailable`."""

    rate = measures(request)
    if rate["words"] < MIN_WORDS[request.exam] or request.duration_seconds < MIN_SECONDS:
        return _empty(request)
    generate = generate or band._generate
    if generate is None:
        from writing_coach.ai.platform import generate_structured as generate
    keys = _criteria(request)
    result = generate(messages=messages(request), schema=band.schema(request.exam, keys), max_output_tokens=1800,
                      temperature=0.0, seed=42, capability_key=band.CAPABILITY)  # fmt: skip
    data = dict(result.data)
    model = {"provider": result.provider, "model": result.model}
    if data.get("insufficient_evidence"):
        return _empty(request, **model)
    low, high = band.SCALE[request.exam]
    by_key = {item.get("criterion"): item for item in data.get("criteria") or () if isinstance(item, dict)}
    criteria = []
    for key in keys:
        item = by_key.get(key)
        score = item.get("score") if item else None
        if not isinstance(score, int) or isinstance(score, bool) or not low <= score <= high:
            raise band.BandUnavailable(f"criterion {key} has no usable score")
        evidence = [q for q in item.get("evidence") or () if band._in_text(request.transcript, q)][:band.MAX_EVIDENCE]
        criteria.append({"criterion": key, "score": score, "reason": str(item.get("reason") or ""),
                         "evidence": evidence})  # fmt: skip
    missing = [key for key in CRITERIA[request.exam] if key not in keys]
    overall: float | int | None = None
    label = None
    if not missing:
        scores = [c["score"] for c in criteria]
        if request.exam == "ielts":
            overall = band.ielts_overall(scores)
            label = f"IELTS {overall:.1f}"
        else:
            overall = band.hsk_overall(scores)
            label = band.hsk_label(overall)
    fixes = [{key: str(fix.get(key) or "") for key in ("fix", "why", "before", "after")}
             for fix in data.get("fixes") or ()
             if isinstance(fix, dict) and band._in_text(request.transcript, fix.get("before"))]  # fmt: skip
    return {"skill": "speaking", "exam": request.exam, "part": request.part, "estimate": True, "experimental": True,
            "insufficient_evidence": False, "overall": overall, "label": label, "criteria": criteria,
            "fixes": fixes[:band.MAX_FIXES], "missing": missing, "measures": rate, **model}  # fmt: skip
