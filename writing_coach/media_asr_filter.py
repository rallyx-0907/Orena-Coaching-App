"""Dropping recogniser hallucinations from ASR segments before they become lesson lines (D-206, PROPOSED).

Whisper-family recognisers invent text over silence, music and noise: subtitle credits, "Thank you", "The End",
a literal "foreign" tag, one stray word at the tail. Those lines pass every transcript check, because each is a
well-formed line. This module removes them, English and Chinese by one contract.

Signal first, phrase second. A segment is dropped when

1. it is a subtitle-credit line or a bare sound tag (`media_asr_hallucinations.json`, language-neutral): these are
   never speech;
2. the recogniser itself says it is not speech: `no_speech_prob` high and `avg_logprob` low (the thresholds
   Whisper uses to skip a window), or `compression_ratio` above Whisper's repetition limit;
3. it is a stock sign-off from the per-language list AND the evidence agrees: the segment is long for its few
   words, or it sits next to a long silence, or the same phrase repeats, or the recogniser doubts it;
4. it is a one-unit segment left alone at the tail after a silence.

A long segment holding few words that matches no phrase is kept and counted as `flagged`, so review sees it
without losing speech that may be real. Pure, deterministic, no provider, idempotent. Captions never pass here.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from writing_coach.media_segmentation import primary_language
from writing_coach.speech_asr import SpeechAsrSegment, SpeechAsrWord

DATA_PATH = Path(__file__).resolve().parent / "media_asr_hallucinations.json"

# Whisper skips a window as silence at no_speech_prob > 0.6 with avg_logprob < -1.0, and treats a compression
# ratio above 2.4 as a repetition loop (openai/whisper `transcribe` defaults).
NO_SPEECH_PROB = 0.6
AVG_LOGPROB = -1.0
COMPRESSION_RATIO = 2.4
# A doubted segment: well short of the skip thresholds, still enough to tip a stock phrase.
DOUBT_NO_SPEECH_PROB = 0.3
# Speech is 2-3 words (English) or 3-6 characters (Chinese) a second; under these a segment of at least
# SPARSE_MIN_MS is mostly silence. A 33 s segment with 2 words is the shape seen in the trial.
SPARSE_MIN_MS = 8000
SPARSE_RATE = {"en": 0.25, "zh": 0.8}
# Silence beside a sign-off that makes it a hallucination rather than a speaker saying goodbye.
LONG_SILENCE_MS = 10000
# Tail: a lone word is a stray when it follows this much silence.
TAIL_SILENCE_MS = 2000
TAIL_UNITS = {"en": 1, "zh": 2}

_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_BRACKETED = re.compile(r"^[\[\(（【♪\s]*(.*?)[\]\)）】♪\s]*$")


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=8)
def _credit_patterns(language: str) -> tuple[re.Pattern[str], ...]:
    data = _data()
    sources = [data.get("any", {}).get("credits", []), data.get(language, {}).get("credits", [])]
    return tuple(re.compile(pattern, re.IGNORECASE) for group in sources for pattern in group)


def _tags() -> frozenset[str]:
    return frozenset(str(tag).casefold() for tag in _data().get("any", {}).get("tags", []))


def _stock(language: str) -> frozenset[str]:
    return frozenset(_fold(str(item)) for item in _data().get(language, {}).get("stock", []))


def _fold(text: str) -> str:
    """Casefolded letters and digits only, words kept apart by one space, CJK joined."""
    kept = "".join(char if unicodedata.category(char)[0] in "LN" else " " for char in str(text).casefold())
    kept = re.sub(r"\s+", " ", kept).strip()
    return re.sub(r"(?<=[㐀-鿿])\s+(?=[㐀-鿿])", "", kept)


def _units(text: str, zh: bool) -> int:
    """How much was said: Hanzi for Chinese, words for the rest."""
    if zh:
        return len(_HAN.findall(text))
    return len(_fold(text).split())


@dataclass(frozen=True)
class AsrScreen:
    segments: tuple[SpeechAsrSegment, ...]
    words: tuple[SpeechAsrWord, ...]
    filtered: int = 0
    flagged: int = 0


def _is_tag(text: str) -> bool:
    """A bare sound tag, with or without brackets: [foreign], (Music), ♪, 音乐."""
    inner = _BRACKETED.match(str(text).strip())
    return _fold(inner.group(1) if inner else text) in _tags()


def _doubted(segment: SpeechAsrSegment) -> bool:
    return (segment.no_speech_prob is not None and segment.no_speech_prob >= DOUBT_NO_SPEECH_PROB) or (
        segment.avg_logprob is not None and segment.avg_logprob < AVG_LOGPROB
    )


def _unsupported(segment: SpeechAsrSegment) -> bool:
    """The recogniser's own verdict that the segment is not speech, or is a repetition loop."""
    if segment.compression_ratio is not None and segment.compression_ratio > COMPRESSION_RATIO:
        return True
    return (
        segment.no_speech_prob is not None
        and segment.no_speech_prob > NO_SPEECH_PROB
        and (segment.avg_logprob is None or segment.avg_logprob < AVG_LOGPROB)
    )


def _sparse(segment: SpeechAsrSegment, units: int, language: str) -> bool:
    length = segment.end_ms - segment.start_ms
    return length >= SPARSE_MIN_MS and units / (length / 1000) < SPARSE_RATE.get(language, SPARSE_RATE["en"])


def screen_segments(
    segments: tuple[SpeechAsrSegment, ...] | list[SpeechAsrSegment],
    words: tuple[SpeechAsrWord, ...] | list[SpeechAsrWord],
    language: str,
) -> AsrScreen:
    """The segments that are speech, the words inside them, and how many segments were dropped or flagged."""
    lang = primary_language(language) or "en"
    zh = lang == "zh"
    ordered = sorted(segments, key=lambda item: (item.start_ms, item.end_ms))
    stock = _stock(lang)
    credits = _credit_patterns(lang)
    flagged = 0
    drop = [False] * len(ordered)
    folded = [_fold(item.text) for item in ordered]
    for index, segment in enumerate(ordered):
        if any(pattern.search(segment.text) for pattern in credits) or _is_tag(segment.text) or _unsupported(segment):
            drop[index] = True
            continue
        units = _units(segment.text, zh)
        before = segment.start_ms - ordered[index - 1].end_ms if index else segment.start_ms
        after = ordered[index + 1].start_ms - segment.end_ms if index + 1 < len(ordered) else None
        sparse = _sparse(segment, units, lang)
        if folded[index] in stock:
            repeated = any(
                0 <= other < len(ordered) and folded[other] == folded[index] for other in (index - 1, index + 1)
            )
            silent = before >= LONG_SILENCE_MS or (after is not None and after >= LONG_SILENCE_MS)
            if sparse or silent or repeated or _doubted(segment):
                drop[index] = True
            continue
        if sparse:
            flagged += 1
    # Tail: a run of lone words after silence is the recogniser talking to itself.
    limit = TAIL_UNITS.get(lang, 1)
    end = len(ordered)
    while end > 0 and (drop[end - 1] or _units(ordered[end - 1].text, zh) <= limit):
        end -= 1
    run = [i for i in range(end, len(ordered)) if not drop[i]]
    if run:
        kept_before = [i for i in range(end) if not drop[i]]
        previous_end = ordered[kept_before[-1]].end_ms if kept_before else 0
        if ordered[run[0]].start_ms - previous_end >= TAIL_SILENCE_MS:
            for i in run:
                drop[i] = True
    kept = tuple(item for item, gone in zip(ordered, drop, strict=True) if not gone)
    gone_spans = [(item.start_ms, item.end_ms) for item, gone in zip(ordered, drop, strict=True) if gone]
    if not gone_spans:
        return AsrScreen(tuple(ordered), tuple(words), 0, flagged)
    kept_words = tuple(
        word for word in words
        if not any(start <= (word.start_ms + word.end_ms) / 2 < end_ for start, end_ in gone_spans)
    )
    return AsrScreen(kept, kept_words, len(gone_spans), flagged)

