"""Cleaning Chinese speech-recognition cues before they are cut into lesson lines.

Whisper's Chinese output arrives with a space between words (or characters), no sentence punctuation, and a
segment that may begin long before its first spoken word. A learner reads Hanzi without spaces and needs
sentence marks to read, shadow and dictate a line, so this module repairs those three things.

Deterministic only, no provider: spaces between CJK characters are removed; full-width marks are restored from
the recogniser's own word timings (a pause) and from segment boundaries (a question particle or question word in
the final clause decides between the question mark and the full stop); a cue's start moves to its first word's
timestamp. Pure and idempotent, and language-gated: anything that is not Chinese is returned untouched. Only
cues that contain Hanzi are punctuated. The question rule is a heuristic over Simplified and Traditional forms.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from writing_coach.languages.chinese.script_conversion import convert_script, target_script
from writing_coach.media_segmentation import Cue, primary_language
from writing_coach.speech_asr import SpeechAsrWord

# A comma needs a pause that hesitation or timestamp jitter does not make: Whisper word times wobble by a few
# hundred ms and a breath inside a clause is 200-400 ms, while a clause boundary is usually 500 ms or more.
# A sentence ends after a second of silence.
COMMA_PAUSE_MS = 500
SENTENCE_PAUSE_MS = 1000

_CJK = r"㐀-䶿一-鿿豈-﫿　-〿＀-￯"
_HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_SPACE_BETWEEN_CJK = re.compile(rf"(?<=[{_CJK}])\s+(?=[{_CJK}])")
_SPACE_AROUND_MARK = re.compile(r"\s+(?=[，。？！；：、])|(?<=[，。？！；：、])\s+")
_HALF_AFTER_CJK = {",": "，", "?": "？", "!": "！", ";": "；", ":": "：", ".": "。"}
_HALF_MARK = re.compile(rf"(?<=[{_CJK}])([,?!;:.])(?=\s|$|[{_CJK}])")
_TERMINAL = re.compile(r"[。？！…][”’）)」』]*$")
_MARKS = "，。？！；：、…"
_CLAUSE_END = "，。？！；：、"
# Sentence-final particles: a pause never separates one from the word it belongs to.
_PARTICLES = "吗嗎呢吧啊啦呀了的嘛么麼"
_QUESTION_PARTICLE = re.compile(r"(吗|嗎)$")
_NE = re.compile(r"呢$")
_PROGRESSIVE = re.compile(r"(正在|在|正|还在|還在)[^，。？！]*呢$")
_QUESTION_WORD = re.compile(
    r"(什么|什麼|甚麼|谁|誰|哪里|哪裡|哪儿|哪兒|哪个|哪個|哪些|怎么|怎麼|怎样|怎樣|为什么|為什麼|為甚麼|几个|幾個|几点|幾點|几岁|幾歲"
    r"|多少|是不是|有没有|有沒有|对不对|對不對|好不好|能不能|可不可以|行不行|要不要|会不会|會不會)"
)
_UNIVERSAL = re.compile(r"(什么|什麼|甚麼|谁|誰|哪里|哪裡|哪儿|哪兒|哪个|哪個|怎么|怎麼|几|幾)(都|也)")
_EMBEDDED = re.compile(r"(不知道|不知|知道|不明白|不懂|不清楚|不确定|不確定|告诉|告訴|问|問|想知道)")


def _compact(text: str) -> str:
    text = _SPACE_BETWEEN_CJK.sub("", " ".join(str(text or "").split()))
    text = _HALF_MARK.sub(lambda match: _HALF_AFTER_CJK[match.group(1)], text)
    return _SPACE_AROUND_MARK.sub("", text).strip()


def _last_clause(text: str) -> str:
    clause = text.rstrip(_MARKS + " ")
    cut = max((clause.rfind(mark) for mark in _CLAUSE_END), default=-1)
    return clause[cut + 1:]


def _is_question(text: str) -> bool:
    clause = _last_clause(text)
    if not clause:
        return False
    if _QUESTION_PARTICLE.search(clause):
        return True
    if _NE.search(clause) and not _PROGRESSIVE.search(clause):
        return True
    scrubbed = _UNIVERSAL.sub("", clause)
    found = _QUESTION_WORD.search(scrubbed)
    if not found:
        return False
    # "我不知道他在说什么" is a statement that holds a question.
    return not _EMBEDDED.search(scrubbed[:found.start()])


def _sentence_mark(text: str) -> str:
    return "？" if _is_question(text) else "。"


def _cue_words(cue: Cue, words: Sequence[SpeechAsrWord]) -> list[SpeechAsrWord]:
    """The words spoken inside the cue: a word belongs to the cue its middle falls in, so the previous cue's last
    word (which ends at or before this cue's start) is never taken for this cue's first."""
    return [
        word for word in words
        if word.word.strip() and cue.start_ms <= (word.start_ms + word.end_ms) / 2 < cue.end_ms
    ]


def _align(text: str, spoken: Sequence[SpeechAsrWord]) -> list[int] | None:
    """The text index of each word's last character, or None when the words do not spell the text."""
    letters = [index for index, char in enumerate(text) if char not in _MARKS and not char.isspace()]
    cursor = 0
    ends: list[int] = []
    for word in spoken:
        piece = "".join(char for char in word.word if char not in _MARKS and not char.isspace())
        if not piece:
            ends.append(ends[-1] if ends else -1)
            continue
        window = "".join(text[index] for index in letters[cursor:cursor + len(piece)])
        if window != piece:
            return None
        cursor += len(piece)
        ends.append(letters[cursor - 1])
    return ends


def _gap_after(cue: Cue, following: Cue | None, words: Sequence[SpeechAsrWord]) -> int | None:
    """Silence between this cue's last word and the next cue's first, None for the last cue."""
    if following is None:
        return None
    here = _cue_words(cue, words)
    there = _cue_words(following, words)
    return (there[0].start_ms if there else following.start_ms) - (here[-1].end_ms if here else cue.end_ms)


def _clean_cue(cue: Cue, spoken: Sequence[SpeechAsrWord], gap_after: int | None = None) -> list[Cue]:
    text = _compact(cue.text)
    start = cue.start_ms
    if spoken and cue.start_ms < spoken[0].start_ms < cue.end_ms:
        start = spoken[0].start_ms  # leading silence is not part of the line
    if not text or not _HAN.search(text):
        return [Cue(start, cue.end_ms, text)]
    ends = _align(text, spoken) if spoken else None
    pieces: list[tuple[str, int, int]] = []  # text, start_ms, end_ms
    carried = ""
    piece_from = 0
    piece_start = start
    for position in range(len(spoken) - 1 if ends else 0):
        gap = spoken[position + 1].start_ms - spoken[position].end_ms
        at = ends[position]
        if gap < COMMA_PAUSE_MS or at < 0 or at + 1 >= len(text) or text[at + 1] in _MARKS or text[at + 1] in _PARTICLES:
            continue
        chunk = carried + text[piece_from:at + 1]
        if gap >= SENTENCE_PAUSE_MS:
            # A sentence break is cut at the real pause: the line ends with its last word and the next begins
            # with its first, so no word straddles the cut.
            pieces.append((chunk + _sentence_mark(chunk), piece_start, spoken[position].end_ms))
            carried, piece_from, piece_start = "", at + 1, spoken[position + 1].start_ms
        else:
            carried, piece_from = chunk + "，", at + 1
    tail = carried + text[piece_from:]
    if tail and not _TERMINAL.search(tail):
        if tail[-1] in "，、；：":
            tail = tail[:-1]
        # A recogniser cut with no pause after it is mid-sentence: a full stop there is wrong, so the line is
        # left open (a question particle still closes it, and the last cue always ends).
        if gap_after is not None and gap_after < COMMA_PAUSE_MS and not _is_question(tail):
            pass
        else:
            tail += _sentence_mark(tail)
    pieces.append((tail, piece_start, cue.end_ms))
    return [Cue(a, max(b, a + 1), t) for t, a, b in pieces if t]


def normalise_words(words: Sequence[SpeechAsrWord], language: str) -> list[SpeechAsrWord]:
    """The recogniser's words written in the item's script (one character to one character, so timings and the
    word-to-text alignment are unchanged). Anything that is not Chinese is returned untouched."""
    if primary_language(language) != "zh":
        return list(words)
    target = target_script(language)
    return [SpeechAsrWord(convert_script(word.word, target), word.start_ms, word.end_ms) for word in words]


def clean_asr_cues(cues: Sequence[Cue], words: Sequence[SpeechAsrWord], language: str) -> list[Cue]:
    if primary_language(language) != "zh":
        return list(cues)
    # Whisper picks a script per phrase, so one line can hold both. The item's script is the standard (D-207).
    target = target_script(language)
    cues = [Cue(cue.start_ms, cue.end_ms, convert_script(cue.text, target)) for cue in cues]
    words = normalise_words(words, language)
    cleaned: list[Cue] = []
    for index, cue in enumerate(cues):
        following = cues[index + 1] if index + 1 < len(cues) else None
        cleaned.extend(_clean_cue(cue, _cue_words(cue, words), _gap_after(cue, following, words)))
    return cleaned
