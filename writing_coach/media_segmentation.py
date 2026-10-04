"""Turning raw transcript cues into lesson lines, and checking them.

Provider captions and speech-recognition segments arrive in whatever size the
provider cut them: auto-captions are two-second fragments that stop mid-sentence,
Whisper segments can run to half a minute. A listening lesson needs lines a
learner can hold in their head (Dictation, Shadowing), so this module re-cuts
them into sentence-sized lines with honest timing, and then runs the
deterministic checks that decide whether the result is a usable transcript
(D-111 item 1: no self-declared AI confidence - only validators).

Everything here is pure: no provider, no storage, no clock. English and Chinese
share one contract; the only differences are the ones the writing systems force
(Chinese has no spaces and its own sentence marks), and they are parameters of
one function, not two implementations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any

MIN_LINE_MS = 400
GAP_BREAK_MS = 1500

_HAN = re.compile(r"[㐀-䶿一-鿿]")
_WORD = re.compile(r"[A-Za-z0-9']+")
_SPLIT_SENTENCES = re.compile(r"(?<=[。！？；])|(?<=[.!?…])\s+")
_TERMINAL = re.compile(r"[.!?…。！？；]['\"”’）)]*$")
_CLAUSE_MARKS = ",，、:：;—"

# Whisper reports a language by name; ISO tags elsewhere. One map, here.
LANGUAGE_NAMES = {
    "english": "en", "en": "en",
    "chinese": "zh", "mandarin": "zh", "zh": "zh", "cantonese": "zh",
}


def primary_language(value: str | None) -> str:
    text = str(value or "").strip().casefold().replace("_", "-")
    if not text:
        return ""
    return LANGUAGE_NAMES.get(text, LANGUAGE_NAMES.get(text.split("-", 1)[0], text.split("-", 1)[0]))


@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str


def _is_zh(language: str) -> bool:
    return primary_language(language) == "zh"


def _limits(language: str) -> dict[str, int]:
    if _is_zh(language):
        return {"min_chars": 6, "soft_chars": 20, "max_chars": 38, "max_ms": 9000}
    return {"min_chars": 24, "soft_chars": 80, "max_chars": 140, "max_ms": 9000}


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _join(left: str, right: str, zh: bool) -> str:
    if not left:
        return right
    if zh and not (left[-1].isascii() and left[-1].isalnum() and right[0].isascii() and right[0].isalnum()):
        return left + right
    return f"{left} {right}"


def _split_long(text: str, max_chars: int, zh: bool) -> list[str]:
    """Cut one over-long run at the clause mark nearest its middle, recursively."""
    if len(text) <= max_chars:
        return [text]
    middle = len(text) // 2
    candidates = [index for index, char in enumerate(text) if char in _CLAUSE_MARKS and 3 <= index < len(text) - 3]
    if not candidates and not zh:
        candidates = [index for index, char in enumerate(text) if char == " " and 3 <= index < len(text) - 3]
    cut = (min(candidates, key=lambda index: abs(index - middle)) + 1) if candidates else middle
    left, right = text[:cut].strip(), text[cut:].strip()
    if not left or not right:
        return [text]
    return _split_long(left, max_chars, zh) + _split_long(right, max_chars, zh)


def _atoms(cues: Sequence[Cue], language: str, max_chars: int) -> list[tuple[int, int, str]]:
    zh = _is_zh(language)
    atoms: list[tuple[int, int, str]] = []
    for cue in cues:
        text = _clean(cue.text)
        if not text or cue.end_ms <= cue.start_ms:
            continue
        pieces: list[str] = []
        for sentence in _SPLIT_SENTENCES.split(text):
            sentence = sentence.strip()
            if sentence:
                pieces.extend(_split_long(sentence, max_chars, zh))
        weight = sum(len(piece) for piece in pieces) or 1
        span = cue.end_ms - cue.start_ms
        cursor = cue.start_ms
        consumed = 0
        for index, piece in enumerate(pieces):
            consumed += len(piece)
            end = cue.end_ms if index == len(pieces) - 1 else cue.start_ms + round(span * consumed / weight)
            end = max(end, cursor + 1)
            atoms.append((cursor, end, piece))
            cursor = end
    return atoms


def segment_lines(cues: Sequence[Cue], language: str) -> list[Cue]:
    """Re-cut raw cues into sentence-sized lines with proportional timing."""
    zh = _is_zh(language)
    limit = _limits(language)
    atoms = _atoms(sorted(cues, key=lambda cue: (cue.start_ms, cue.end_ms)), language, limit["max_chars"])
    lines: list[Cue] = []
    current: Cue | None = None

    def flush() -> None:
        nonlocal current
        if current is not None and any(char.isalnum() for char in current.text):
            lines.append(current)
        current = None

    for start, end, text in atoms:
        if current is not None:
            joined = _join(current.text, text, zh)
            if (
                start - current.end_ms > GAP_BREAK_MS
                or len(joined) > limit["max_chars"]
                or end - current.start_ms > limit["max_ms"]
            ):
                flush()
        current = Cue(start, end, text) if current is None else Cue(current.start_ms, end, _join(current.text, text, zh))
        long_enough = len(current.text) >= limit["min_chars"] and current.end_ms - current.start_ms >= MIN_LINE_MS
        if (_TERMINAL.search(current.text) and long_enough) or len(current.text) >= limit["soft_chars"]:
            flush()
    flush()
    return _monotonic(lines)


def _monotonic(lines: list[Cue]) -> list[Cue]:
    """Ordered, non-overlapping, every line at least MIN_LINE_MS long."""
    fixed: list[Cue] = []
    for line in lines:
        start = max(line.start_ms, fixed[-1].end_ms if fixed else 0)
        end = max(line.end_ms, start + MIN_LINE_MS)
        fixed.append(Cue(start, end, line.text))
    return fixed


# -- validation -------------------------------------------------------------------------


def _letters(text: str) -> tuple[int, int, int]:
    han = len(_HAN.findall(text))
    latin = sum(1 for char in text if char.isalpha() and ord(char) < 0x250)
    other = sum(1 for char in text if char.isalpha()) - han - latin
    return han, latin, other


def _units(text: str, language: str) -> int:
    return len(_HAN.findall(text)) if _is_zh(language) else len(_WORD.findall(text))


def _normal(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def validate_lines(
    lines: Sequence[Cue],
    *,
    language: str,
    duration_ms: int = 0,
    detected_language: str = "",
) -> list[dict[str, Any]]:
    """The deterministic checks. Each is {id, pass, detail}; the first failing one names the reason.

    Order matters: it is the order an operator would want the cause in
    (nothing there, wrong language, does not cover the media, not usable as lines).
    """
    checks: list[dict[str, Any]] = []
    text = " ".join(line.text for line in lines)
    expected = primary_language(language)

    units = _units(text, language)
    checks.append({"id": "non_empty", "pass": bool(lines) and units >= 4, "detail": f"{units} units"})

    han, latin, other = _letters(text)
    total = han + latin + other
    if expected == "zh":
        ratio = han / total if total else 0.0
        script_ok = ratio >= 0.5
    else:
        ratio = latin / total if total else 0.0
        script_ok = ratio >= 0.75
    detected = primary_language(detected_language)
    label_ok = detected in {"", "und", expected}
    checks.append({"id": "language", "pass": bool(total) and script_ok and label_ok, "detail": f"{ratio:.2f}"})

    if duration_ms >= 5000 and lines:
        span = lines[-1].end_ms - lines[0].start_ms
        coverage = span / duration_ms
        checks.append({"id": "coverage", "pass": coverage >= 0.4, "detail": f"{coverage:.2f}"})
    else:
        checks.append({"id": "coverage", "pass": True, "detail": "skipped"})

    limit = 18.0 if expected == "zh" else 35.0
    ordered = all(
        line.end_ms > line.start_ms and (index == 0 or line.start_ms >= lines[index - 1].end_ms)
        for index, line in enumerate(lines)
    )
    fast = sum(1 for line in lines if len(line.text) / max((line.end_ms - line.start_ms) / 1000.0, 0.001) > limit)
    sane = ordered and all(len(line.text) <= 400 for line in lines) and fast <= max(1, len(lines) // 4)
    checks.append({"id": "segments", "pass": sane, "detail": f"{len(lines)} lines"})

    normals = [_normal(line.text) for line in lines]
    run = longest = 0
    for index, value in enumerate(normals):
        run = run + 1 if index and value == normals[index - 1] else 1
        longest = max(longest, run)
    distinct = len(set(normals)) / len(normals) if normals else 1.0
    checks.append({"id": "repetition", "pass": longest < 4 and (len(normals) < 8 or distinct >= 0.3), "detail": f"{longest}"})
    return checks


REASON_BY_CHECK = {
    "non_empty": "empty_transcript",
    "language": "language_mismatch",
    "coverage": "coverage_low",
    "segments": "segments_invalid",
    "repetition": "repetition",
}


def first_failure(checks: Sequence[dict[str, Any]]) -> str:
    """The reason code of the first failing check, or an empty string when all pass."""
    for check in checks:
        if not check.get("pass"):
            return REASON_BY_CHECK.get(str(check.get("id")), "segments_invalid")
    return ""
