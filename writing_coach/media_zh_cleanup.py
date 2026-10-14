"""Cleaning Chinese speech-recognition cues before they are cut into lesson lines.

Whisper's Chinese output arrives with a space between words (or characters), no sentence punctuation, and a
segment that may begin long before its first spoken word. A learner reads Hanzi without spaces and needs
sentence marks to read, shadow and dictate a line, so this module repairs those three things.

Deterministic only, no provider: spaces between CJK characters are removed; full-width marks are restored from
the recogniser's own word timings (a pause) and from segment boundaries (a question word or particle decides
between the question mark and the full stop); a cue's start moves to its first word's timestamp. Pure and
idempotent, and language-gated: anything that is not Chinese is returned untouched.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from writing_coach.media_segmentation import Cue, primary_language
from writing_coach.speech_asr import SpeechAsrWord

COMMA_PAUSE_MS = 300
SENTENCE_PAUSE_MS = 1000

_CJK = r"㐀-䶿一-鿿豈-﫿　-〿＀-￯"
_SPACE_BETWEEN_CJK = re.compile(rf"(?<=[{_CJK}])\s+(?=[{_CJK}])")
_SPACE_AROUND_MARK = re.compile(r"\s+(?=[，。？！；：、])|(?<=[，。？！；：、])\s+")
_HALF_AFTER_CJK = {",": "，", "?": "？", "!": "！", ";": "；", ":": "：", ".": "。"}
_HALF_MARK = re.compile(rf"(?<=[{_CJK}])([,?!;:.])(?=\s|$|[{_CJK}])")
_TERMINAL = re.compile(r"[。？！…][”’）)」』]*$")
_MARKS = "，。？！；：、…"
_QUESTION_TAIL = re.compile(r"(吗|呢|么|嘛)$")
_QUESTION_WORD = re.compile(r"(什么|谁|哪里|哪儿|哪个|哪些|怎么|怎样|怎么样|为什么|几个|几点|多少|是不是|有没有|对不对|好不好|能不能|可不可以)")


def _compact(text: str) -> str:
    text = _SPACE_BETWEEN_CJK.sub("", " ".join(str(text or "").split()))
    text = _HALF_MARK.sub(lambda match: _HALF_AFTER_CJK[match.group(1)], text)
    return _SPACE_AROUND_MARK.sub("", text).strip()


def _is_question(clause: str) -> bool:
    clause = clause.rstrip(_MARKS + " ")
    return bool(_QUESTION_TAIL.search(clause) or _QUESTION_WORD.search(clause))


def _sentence_mark(clause: str) -> str:
    return "？" if _is_question(clause) else "。"


def _cue_words(cue: Cue, words: Sequence[SpeechAsrWord]) -> list[SpeechAsrWord]:
    return [word for word in words if cue.start_ms - 50 <= word.start_ms < cue.end_ms and word.word.strip()]


def _pause_marks(text: str, spoken: Sequence[SpeechAsrWord]) -> dict[int, str]:
    """Mark to insert after each text index, from the pauses between consecutive words. Empty when the words
    do not spell the text (then there is nothing trustworthy to align on)."""
    letters = [(index, char) for index, char in enumerate(text) if char not in _MARKS and not char.isspace()]
    cursor = 0
    ends: list[int] = []
    for word in spoken:
        piece = "".join(char for char in word.word if char not in _MARKS and not char.isspace())
        if not piece:
            ends.append(ends[-1] if ends else -1)
            continue
        window = "".join(char for _, char in letters[cursor:cursor + len(piece)])
        if window != piece:
            return {}
        cursor += len(piece)
        ends.append(letters[cursor - 1][0])
    marks: dict[int, str] = {}
    clause_start = 0
    for position in range(len(spoken) - 1):
        gap = spoken[position + 1].start_ms - spoken[position].end_ms
        at = ends[position]
        if gap < COMMA_PAUSE_MS or at < 0 or at + 1 >= len(text) or text[at + 1] in _MARKS:
            continue
        if gap >= SENTENCE_PAUSE_MS:
            marks[at] = _sentence_mark(text[clause_start:at + 1])
            clause_start = at + 1
        else:
            marks[at] = "，"
    return marks


def _punctuate(text: str, spoken: Sequence[SpeechAsrWord]) -> str:
    marks = _pause_marks(text, spoken) if spoken else {}
    if marks:
        text = "".join(char + marks.get(index, "") for index, char in enumerate(text))
    if text and not _TERMINAL.search(text) and text[-1] not in _MARKS:
        clause = re.split(r"[。？！]", text)[-1]
        text = text + _sentence_mark(clause)
    elif text and text[-1] in "，、；：":
        text = text[:-1] + _sentence_mark(re.split(r"[。？！]", text[:-1])[-1])
    return text


def clean_asr_cues(cues: Sequence[Cue], words: Sequence[SpeechAsrWord], language: str) -> list[Cue]:
    if primary_language(language) != "zh":
        return list(cues)
    cleaned: list[Cue] = []
    for cue in cues:
        spoken = _cue_words(cue, words)
        start = cue.start_ms
        if spoken and cue.start_ms < spoken[0].start_ms < cue.end_ms:
            start = spoken[0].start_ms  # leading silence is not part of the line
        text = _compact(cue.text)
        cleaned.append(Cue(start, cue.end_ms, _punctuate(text, spoken) if text else text))
    return cleaned
