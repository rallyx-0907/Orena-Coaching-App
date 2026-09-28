"""A learner's message that changes or cancels a coach note (human direction 2026-09-28).

The live run showed the model ignoring "À không, ví dụ dài hơn…" and "Quên ghi
chú về ví dụ đó đi" while the note was on its list, and once answering that no
such note existed. So the server reads the message by rule: a word of change or
forgetting, and the note itself named (a note word, or a phrase of its text). When
both are there and the model changed no note, it is asked once more, with the
notes' ids; if it still does not, the answer says plainly that nothing changed.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from writing_coach.agent.schemas import CoachNote

_CHANGE = re.compile(
    r"(?i)\b(?:quên|xoá|xóa|bỏ|đừng nhớ|không cần nhớ|à không|thôi|đổi|sửa|không phải|thay vì|ngược lại)\b"
    r"|\b(?:forget|delete|remove|actually|no longer|instead|change|not anymore|scratch that)\b"
    r"|忘|删|不要记|别记|其实|不是|改|换"
)
_NOTE_WORD = re.compile(r"(?i)\b(?:ghi chú|lưu ý|note|notes)\b|笔记|那条|记录")
_EN_STOP = frozenset({"that", "this", "with", "have", "from", "they", "them", "more", "less", "like", "want"})


def _phrases(text: str) -> set[str]:
    """What names a note in a message: two syllables in a row (Vietnamese), two characters (Chinese), or a
    word of four letters or more (English)."""

    lowered = unicodedata.normalize("NFC", text).casefold()
    words = re.findall(r"[^\W\d_]+", lowered)
    phrases = {f"{a} {b}" for a, b in zip(words, words[1:], strict=False)}
    phrases |= {w for w in words if w.isascii() and len(w) >= 4 and w not in _EN_STOP}
    for run in re.findall(r"[一-鿿]+", lowered):
        phrases |= {run[i : i + 2] for i in range(len(run) - 1)}
    return phrases


def notes_the_message_changes(message: str | None, notes: Iterable[CoachNote]) -> tuple[CoachNote, ...]:
    """The learner's coach notes (never the address note) this message changes or cancels, by rule."""

    if not message or not _CHANGE.search(unicodedata.normalize("NFC", message)):
        return ()
    own = tuple(note for note in notes if not note.id.startswith("address-"))
    if not own:
        return ()
    if _NOTE_WORD.search(message):
        return own
    said = _phrases(message)
    return tuple(note for note in own if _phrases(note.text) & said)


def nudge(notes: Iterable[CoachNote]) -> str:
    listed = "; ".join(f"{note.id}: {note.text}" for note in notes)
    return (
        "Your answer changed no coach note, but the learner's message changes or cancels one of these: "
        f"{listed}. Call remember_note with replaces set to its id (a correction, in their words) or "
        "forget_note with its id (to forget it) now, then answer in one or two sentences."
    )
