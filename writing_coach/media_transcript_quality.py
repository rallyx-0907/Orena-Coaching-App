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
# Bounded sound-tag rule (English captions). Only what caption convention reserves for non-speech is removed:
# * a square-bracket group whose words are all in the closed sound vocabulary ([music], [crying], [door creaks]) or that
#   is a speaker label (one or two capitalised words of the closed label vocabulary: [MAN], [Narrator], [Male Voice]);
#   any other bracket ([sic], [the president], [1]) is left alone;
# * a parenthesised group only when its words are all in the closed sound vocabulary, whether it is the whole cue or
#   inside it ((music) yes, (yes), (Paris) no), because parentheses can hold real speech.
_EN_SQUARE_TAG = re.compile(r"\[\s*[^\W\d_]+(?:[ '’-]+[^\W\d_]+){0,3}\s*\]")
_EN_PAREN_TAG = re.compile(r"\(\s*[^\W\d_]+(?:[ '’-]+[^\W\d_]+){0,3}\s*\)")
_EN_SPEAKER_LABEL = frozenset({
    "narrator", "man", "woman", "boy", "girl", "child", "speaker", "host", "interviewer", "reporter", "announcer",
    "voice", "male", "female", "crowd", "audience", "all", "both",
})
_EN_SOUND_WORDS = frozenset({
    "music", "applause", "laughter", "laughs", "laughing", "cheering", "cheers", "crying", "cries", "gasps", "gasping",
    "sighs", "snorts", "coughs", "coughing", "sniffles", "screams", "screaming", "whispers", "silence", "inaudible",
    "singing", "humming", "clapping", "chuckles", "groans", "sobbing", "beeping", "ringing", "noise",
    "door", "creaks", "creaking", "knocks", "knocking", "slams", "footsteps", "thunder", "rain", "wind", "bell", "bells",
    "phone", "buzzing", "explosion", "gunshot", "gunshots", "sirens", "siren", "barking", "barks", "birds", "chirping",
    "engine", "car", "starts", "applauds", "applauding", "murmurs", "murmuring", "yells", "shouts", "shouting",
    "sneezes", "yawns", "sighing", "grunts", "static", "echo", "echoing", "continues", "playing", "plays", "fading",
})
_SPEAKER_MARK = re.compile(r">{2,}")
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


def _words(group: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", group.casefold())


def _is_sound_group(group: str) -> bool:
    words = _words(group)
    return bool(words) and all(word in _EN_SOUND_WORDS for word in words)


def _is_speaker_label(group: str) -> bool:
    """`[MAN]`, `[Narrator]`, `[Male Voice]`: one or two words from the closed speaker-label vocabulary, written with
    initial capitals as a label is. `[the president]`, `[sic]` and `[man]` (lower case) are speech or an editor's note."""
    words = re.findall(r"[^\W\d_]+", group)
    if not words or len(words) > 2 or not all(word.casefold() in _EN_SPEAKER_LABEL for word in words):
        return False
    return all(word[0].isupper() for word in words)


def _square_is_noise(match: re.Match[str]) -> str:
    group = match.group(0)
    return " " if _is_sound_group(group) or _is_speaker_label(group) else group


def _paren_is_sound(match: re.Match[str]) -> str:
    return " " if _is_sound_group(match.group(0)) else match.group(0)


def repair_english_caption_text(value: object) -> str:
    """Remove English auto-caption noise without guessing sentence edges.

    Strips speaker marks (`>>`), bracketed sound tags by the bounded rule above and spacing. Casing and every lexical
    token of real speech are preserved; punctuation and case restoration belong to the context-aware corrector. Only
    English text is passed here: Chinese bracketed text is never stripped by this function.
    """
    text = _SPEAKER_MARK.sub(" ", str(value or ""))
    text = _EN_SQUARE_TAG.sub(_square_is_noise, text)
    text = _EN_PAREN_TAG.sub(_paren_is_sound, text)
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
