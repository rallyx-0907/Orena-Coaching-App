"""Deterministic cleanup for provider captions before canonical transcript creation."""
from __future__ import annotations
from dataclasses import dataclass
import html
import math
import re

_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")
_ONLY_MARKS = re.compile(r"^[\W_]+$", re.UNICODE)
_BRACKETED = re.compile(r"^\s*[\[\(（【]\s*(.*?)\s*[\]\)）】]\s*$")
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_EN_NOISE = re.compile(r"\[\s*(?:music|applause|laughter|laughs|cheering|cheers)\s*\]", re.IGNORECASE)
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_MUSIC = re.compile(r"[♪♫♬♩]+")
_CUE_WORDS = {"music","applause","laughter","laughs","cheering","cheers","音乐","音樂","掌声","掌聲","笑声","笑聲","欢呼","歡呼"}

@dataclass(frozen=True)
class CaptionUnit:
    text: str
    start_seconds: float
    duration_seconds: float
    provider_order: int = 0

def clean_caption_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG.sub(" ", text)
    text = _ZERO_WIDTH.sub("", text)
    text = _MUSIC.sub(" ", text)
    text = _SPACE.sub(" ", text).strip()
    if not text:
        return ""
    match = _BRACKETED.fullmatch(text)
    if match and _SPACE.sub(" ", match.group(1)).strip().casefold() in _CUE_WORDS:
        return ""
    if _ONLY_MARKS.fullmatch(text):
        return ""
    return text


def repair_english_caption_text(value: object) -> str:
    """Remove common English auto-caption noise without guessing sentence edges.

    Caption cues are often sentence fragments; punctuation restoration is left
    to the context-aware corrector. This deterministic pass preserves casing
    and every lexical token.
    """
    text = str(value or "").replace(">>", " ")
    text = _EN_NOISE.sub(" ", text)
    return _SPACE.sub(" ", text).strip()

def _primary(value: str) -> str:
    return (value or "").strip().casefold().replace("_", "-").split("-", 1)[0]

def _score(text: str, source_language: str) -> int:
    lang = _primary(source_language)
    han = len(_HAN.findall(text))
    latin = len(_LATIN.findall(text))
    if lang == "zh":
        if han:
            return 100 + min(han, 40)
        if latin >= 2:
            return -100 - min(latin, 40)
    if lang == "en":
        if latin and not han:
            return 100 + min(latin, 40)
        if latin > han:
            return 50 + min(latin, 40)
        if han:
            return -100 - min(han, 40)
    return 0

def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None

def clean_caption_units(
    units: tuple[CaptionUnit, ...],
    *,
    source_language: str,
    parallel_start_tolerance_seconds: float = 0.35,
) -> tuple[CaptionUnit, ...]:
    prepared: list[CaptionUnit] = []
    for unit in units:
        start = _finite(unit.start_seconds)
        duration = _finite(unit.duration_seconds)
        text = clean_caption_text(unit.text)
        if start is None or duration is None or start < 0 or duration <= 0 or not text:
            continue
        prepared.append(CaptionUnit(text, start, duration, int(unit.provider_order)))
    prepared.sort(key=lambda item: (item.start_seconds, item.provider_order))
    selected: list[CaptionUnit] = []
    index = 0
    while index < len(prepared):
        anchor = prepared[index].start_seconds
        group: list[CaptionUnit] = []
        while index < len(prepared) and prepared[index].start_seconds - anchor <= parallel_start_tolerance_seconds:
            group.append(prepared[index])
            index += 1
        if len(group) == 1:
            selected.extend(group)
            continue
        scores = [_score(item.text, source_language) for item in group]
        has_target = any(score >= 100 for score in scores)
        has_foreign = any(score <= -100 for score in scores)
        if has_target and has_foreign:
            candidates = [item for item, score in zip(group, scores, strict=True) if score >= 100]
            selected.append(max(candidates, key=lambda item: (_score(item.text, source_language), len(item.text), -item.provider_order)))
        else:
            selected.extend(group)
    # Preserve duplicate valid captions. Canonical transcript identity owns
    # duplicate disambiguation via occurrence suffixes; cleanup must not collapse
    # provider segments that can represent separate caption events.
    return tuple(selected)
