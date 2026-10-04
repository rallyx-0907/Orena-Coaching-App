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
    r"(?i)\b(?:quên|xoá|xóa|bỏ|đừng|không cần nhớ|à không|thôi|đổi|sửa|không phải|thay vì|ngược lại)\b"
    r"|\b(?:forget|delete|remove|actually|no longer|instead|change|not anymore|scratch that|don't|do not)\b"
    r"|忘|删|不要|别|其实|不是|改|换"
)

# Forgetting deletes: only a request to forget that states no new wish (human direction 2026-09-28). A message
# that says what the learner wants now is a correction, even with "xoá"/"đừng" in it; anything unclear is a
# correction too - the note is replaced (same id), never lost.
_FORGET = re.compile(
    r"(?i)\b(?:quên|xoá|xóa|bỏ ghi chú|đừng nhớ|đừng ghi nhớ|không cần nhớ)\b"
    r"|\b(?:forget|delete|remove|stop remembering|don't remember)\b"
    r"|忘|删|不要记|别记"
)
_NEW_WISH = re.compile(
    r"(?i)\b(?:lấy|giải thích|dùng|hãy|nên|muốn|thích|từ giờ|từ nay|thay vì|thay bằng|hơn|bằng tiếng|cho mình|nói)\b"
    r"|\b(?:instead|from now|use|explain|prefer|want|give me|make|longer|shorter|more|less|in english|in vietnamese"
    r"|in chinese|rather)\b"
    r"|改|换|用|以后|从现在|要|更|请|喜欢"
)
CORRECT, FORGET = "correct", "forget"


def note_intent(message: str | None) -> str:
    """`forget` only for a request to forget with no new wish ("quên cái đó đi", "forget that", "忘掉吧");
    otherwise `correct` ("Xoá cái cũ đi, từ giờ giải thích bằng tiếng Anh" keeps the note, with new words)."""

    text = unicodedata.normalize("NFC", message or "")
    if _FORGET.search(text) and not _NEW_WISH.search(text):
        return FORGET
    return CORRECT
# A request to keep something (dogfood gate 3.2): the learner asks, in so many words, or states a standing wish
# ("từ giờ", "from now on", "以后"). Telling a fact ("Mình đang luyện HSK4") is not a request, and neither is
# not remembering something ("mình không nhớ là…", "I don't remember", "我不记得").
_REMEMBER = re.compile(
    r"(?i)(?<!không )(?<!chẳng )(?<!chưa )(?<!đừng )\bnhớ (?:giúp|giùm|hộ|là|rằng|cho|nhé|giúp mình|điều này|cái này)\b"
    r"|\b(?:ghi nhớ|ghi lại|ghi chú lại|lưu lại điều|từ giờ|từ nay|lần sau|sau này|về sau)\b"
    r"|(?<!\bi )(?<!n't )(?<!not )\bremember (?:that|this|to|i|i'm|my|me)\b"
    r"|\b(?:keep in mind|note that|make a note|take note|from now on|next time|going forward|in future|in the future)\b"
    r"|(?<!不)记住|帮我记|记一下|请记得|你要记得|以后|从现在起|从今以后|今后|下次"
)


def asks_to_remember(message: str | None) -> bool:
    """The learner asks Orena to keep something, or states a wish for the turns to come."""

    return bool(message) and bool(_REMEMBER.search(unicodedata.normalize("NFC", message)))


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


def nudge(notes: Iterable[CoachNote], intent: str = CORRECT) -> str:
    listed = "; ".join(f"{note.id}: {note.text}" for note in notes)
    if intent == FORGET:
        what = "The learner asks you to forget it: call forget_note with its id now"
    else:
        what = ("The learner corrects it with a new wish: call remember_note with replaces set to its id and the new "
                "wish in their words now - do not forget it")  # fmt: skip
    return f"Your answer changed no coach note, but the learner's message is about this one: {listed}. {what}, then answer in one or two sentences."
