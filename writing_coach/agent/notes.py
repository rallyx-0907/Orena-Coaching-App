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

# The verbs that also mean "I forget" (#346: "Mình hay quên ngữ pháp này quá", 我总是忘掉这个语法, "I always forget this
# grammar rule"). They ask something of a note only as an imperative - at the start of a sentence, "quên giùm/giúp",
# "quên ... đi" closing the message, 忘记...吧, 把...忘了 - or beside a note noun; never after a subject or a habit word.
_FORGETTING = re.compile(r"(?i)\bquên\b|\bforget\b|忘")
_SELF_FORGETS = re.compile(
    r"(?i)\b(?:mình|tôi|em|tớ|anh|chị|hay|thường|cứ|dễ|bị|vẫn|lại)\s+quên\b"
    r"|\bquên\s+(?:mất|rồi|béng|tiệt)\b"  # "quên mất", "quên rồi": I forgot, never "forget it"
    r"|\b(?:i|we|always|often|keep|usually|sometimes|never|tend to)\s+(?:\w+\s+)?forget"
    # a subject or habit word anywhere earlier in the clause: 我把这个语法忘了, 我又把单词忘了
    r"|(?:我|总是|老是|经常|容易|常常|又|还是)[^，。！？,.!?;]{0,12}忘"
)
_FORGET_IMPERATIVE = re.compile(
    r"(?i)(?:^|[.!?;:\n]\s*)(?:(?:thôi|à|ừ|vậy|ok|okay|please)[,\s]+)?(?:quên|forget)\b"
    r"|\bquên\s+(?:giùm|giúp|hộ)\b"
    r"|\bquên\b[^.?!\n]*\b(?:đi|nhé|nha)\s*[.!?]*\s*$"
    r"|\bđừng nhớ\b|\bkhông cần nhớ\b|\bstop remembering\b"
    r"|\bforget (?:it|that|about (?:it|that)|the note|my note)\b"
    # not a bare 忘了 at the start ("(I) forgot..."), and 把...忘了 only with 吧 after it
    r"|(?:^|[，。！？,.!?;]\s*)请?忘掉|忘了吧|忘了它|别记|不要记|忘记.{0,12}吧|把.{1,12}忘了吧"
)


def _asks_to_forget(text: str) -> bool:
    """A forgetting verb used as "forget it", not "I forget"."""

    return bool(_FORGET_IMPERATIVE.search(text)) and not _SELF_FORGETS.search(text)


def _without_forgetting(text: str) -> str:
    return _FORGETTING.sub(" ", text)


def _asks_about_a_note_by_forgetting_only(text: str) -> bool:
    """The only change word is a forgetting verb, used as "I forget", not "forget it"."""

    return (bool(_FORGETTING.search(text)) and not _CHANGE.search(_without_forgetting(text))
            and not _asks_to_forget(text) and not _NOTE_WORD.search(text))  # fmt: skip


def note_intent(message: str | None) -> str:
    """`forget` only for a request to forget with no new wish ("quên cái đó đi", "forget that", "忘掉吧");
    otherwise `correct` ("Xoá cái cũ đi, từ giờ giải thích bằng tiếng Anh" keeps the note, with new words)."""

    text = unicodedata.normalize("NFC", message or "")
    if _FORGET.search(text) and not _NEW_WISH.search(text):
        # "quên"/"忘" alone is "I forget" (#346): FORGET only as an imperative or beside a note noun.
        if (_FORGETTING.search(text) and not (_asks_to_forget(text) or _NOTE_WORD.search(text))
                and not _FORGET.search(_without_forgetting(text))):  # fmt: skip
            return CORRECT
        return FORGET
    return CORRECT
# A request to keep something (dogfood gate 3.2): the learner asks, in so many words, or states a standing wish
# ("từ giờ", "from now on", "以后"). Telling a fact ("Mình đang luyện HSK4") is not a request, and neither is
# not remembering something ("mình không nhớ là…", "I don't remember", "我不记得").
_REMEMBER = re.compile(
    # "mình nhớ là bài trước…" is the learner remembering, not a request (review P2-6).
    r"(?i)(?<!không )(?<!chẳng )(?<!chưa )(?<!đừng )(?<!mình )(?<!tôi )(?<!em )(?<!tớ )"
    r"\bnhớ (?:giúp|giùm|hộ|là|rằng|cho|nhé|giúp mình|điều này|cái này)\b"
    # "ghi nhớ từ này" is memorising a word; only "ghi nhớ" of a statement is a request.
    r"|\b(?:ghi nhớ|ghi lại|ghi chú lại) (?:là|rằng|giúp|giùm|hộ|điều này|nhé)\b"
    r"|\b(?:từ giờ|từ nay|từ bây giờ)\b|\blần sau (?:hãy|nhớ|đừng|cứ)\b"
    r"|(?<!\bi )(?<!n't )(?<!not )(?<!you )\bremember (?:that|this|to|i|i'm|my|me)\b"
    r"|\b(?:keep in mind|note that|make a note|take note|from now on|going forward)\b"
    r"|\bnext time,? (?:please|always|don't|do not|use|explain|give|answer)\b"
    r"|(?<!不)记住|帮我记|记一下|请记得|你要记得|从现在起|从今以后"
    r"|(?:以后|今后|下次)(?:请|你|都|要|用|给我|别|不要)"
)


def asks_to_remember(message: str | None) -> bool:
    """The learner asks Orena to keep something, or states a wish for the turns to come - or taps the button
    that confirms one (`confirmed_note`)."""

    if not message:
        return False
    return bool(_REMEMBER.search(unicodedata.normalize("NFC", message))) or confirmed_note(message) is not None


# The button that confirms a note proposed from a request typed without diacritics (human direction 2026-10-04):
# a suggestion whose label is the learner's next message (contract §4), in the interface language's words of
# `notes.keep_label` (agent/learner_copy.py). Typed by hand it is the same explicit request.
_CONFIRMED = re.compile(r"(?i)^\s*(?:ghi nhớ|remember|记住)\s*[:：]\s*(?P<text>\S.*?)\s*$", re.DOTALL)


def confirmed_note(message: str | None) -> str | None:
    """The note a message confirms ("Ghi nhớ: …", "Remember: …", "记住：…"), else None."""

    found = _CONFIRMED.match(unicodedata.normalize("NFC", message or ""))
    return found.group("text") if found else None


def same_note(a: str, b: str) -> bool:
    """The same words, give or take case, spacing and the closing punctuation."""

    def plain(text: str) -> str:
        return " ".join(unicodedata.normalize("NFC", text).casefold().split()).rstrip(".!。！ ")

    return plain(a) == plain(b)


# The same requests typed without Vietnamese diacritics ("nho giup minh la…", "tu gio…"). Without the marks the
# words are ambiguous ("nho" is nhớ, nhỏ or nhọ), so nothing is kept on them: Orena asks back, and keeps the note
# only when the learner taps to confirm it (human direction 2026-10-04) - never a silent refusal.
_REMEMBER_PLAIN = re.compile(
    r"(?i)(?<!khong )(?<!chang )(?<!chua )(?<!dung )(?<!minh )(?<!toi )(?<!em )(?<!to )"
    r"\bnho (?:giup|gium|ho|la|rang|cho|nhe|dieu nay|cai nay)\b"
    r"|\b(?:ghi nho|ghi lai|ghi chu lai) (?:la|rang|giup|gium|ho|dieu nay|nhe)\b"
    # Not "tu nay": without its marks it is "từ này" (this word) as often as "từ nay" (from now on).
    r"|\b(?:tu gio|tu bay gio)\b|\blan sau (?:hay|nho|dung|cu)\b"
)
# What opens the request rather than says the wish: "(mình) là / rằng", "giúp mình", a colon.
_REQUEST_LEAD = re.compile(r"(?i)^(?:[\s:,.-]|(?:minh|toi|em|to|giup|gium|ho|voi|nhe)\s+(?=la\b|rang\b)|(?:la|rang)\b)+")


def _unaccented(text: str) -> bool:
    """No Vietnamese mark at all: no combining diacritic and no đ."""

    decomposed = unicodedata.normalize("NFD", text)
    return not any(unicodedata.combining(c) for c in decomposed) and not set(decomposed) & {"đ", "Đ"}


def asks_to_remember_unaccented(message: str | None) -> bool:
    """A Vietnamese request to keep something, typed without diacritics: to be confirmed, never kept as it is."""

    if not message or asks_to_remember(message) or not _unaccented(message):
        return False
    return bool(_REMEMBER_PLAIN.search(message))


def unaccented_wish(message: str) -> str | None:
    """The wish an unaccented request states, in the learner's own words: what follows the request itself."""

    found = _REMEMBER_PLAIN.search(message)
    if found is None:
        return None
    wish = _REQUEST_LEAD.sub("", message[found.end() :]).strip()
    return wish or None


# An explicit note noun (#346: not "lưu ý" or 记录 - an everyday "note that" and "records" named every note at once).
_NOTE_WORD = re.compile(r"(?i)\b(?:ghi chú|note|notes)\b|笔记|备注|那条")
_EN_STOP = frozenset({"that", "this", "with", "have", "from", "they", "them", "more", "less", "like", "want", "what",
                      "does", "word", "mean", "please", "help", "about", "just"})
# Phrases every learner says - who is asked, which thing is meant - name no note (#346): a request to fix a sentence
# "giúp mình" never touches a note that also says "giúp mình".
_STOP_PHRASES = frozenset({
    "giúp mình", "cho mình", "giúp tôi", "cho tôi", "giúp em", "cho em", "giúp với", "mình muốn", "tôi muốn",
    "câu này", "từ này", "cái này", "cái đó", "hôm nay", "bây giờ", "được không",
    "帮我", "给我", "这个", "那个", "一下", "我的", "我们", "你的", "什么", "怎么", "可以", "一点",
})


def _phrases(text: str) -> set[str]:
    """What names a note in a message: two syllables in a row (Vietnamese), two characters (Chinese), or a
    word of four letters or more (English)."""

    lowered = unicodedata.normalize("NFC", text).casefold()
    words = re.findall(r"[^\W\d_]+", lowered)
    phrases = {f"{a} {b}" for a, b in zip(words, words[1:], strict=False)}
    phrases |= {w for w in words if w.isascii() and len(w) >= 4 and w not in _EN_STOP}
    for run in re.findall(r"[一-鿿]+", lowered):
        phrases |= {run[i : i + 2] for i in range(len(run) - 1)}
    return phrases - _STOP_PHRASES


def notes_the_message_changes(message: str | None, notes: Iterable[CoachNote]) -> tuple[CoachNote, ...]:
    """The learner's coach notes (never the address note) this message changes or cancels, by rule."""

    text = unicodedata.normalize("NFC", message or "")
    if not message or not _CHANGE.search(text) or _asks_about_a_note_by_forgetting_only(text):
        return ()
    own = tuple(note for note in notes if not note.id.startswith("address-"))
    if not own:
        return ()
    if _NOTE_WORD.search(text):
        return own
    said = _phrases(message)
    return tuple(note for note in own if _phrases(note.text) & said)


def names_a_note(message: str | None) -> bool:
    """The message names a note outright ("ghi chú", "note", "笔记"): only then may the server order a change."""

    return bool(message) and bool(_NOTE_WORD.search(unicodedata.normalize("NFC", message)))


def nudge(notes: Iterable[CoachNote], intent: str = CORRECT, *, explicit: bool = True) -> str:
    """`explicit`: the message named a note (`names_a_note`). Otherwise the match is by rule and may be wrong, so the
    model is asked to change the note only if that is what the learner asks - never ordered to (#346)."""

    listed = "; ".join(f"{note.id}: {note.text}" for note in notes)
    if not explicit:
        verb = ("call forget_note with its id" if intent == FORGET
                else "call remember_note with replaces set to its id and the new wish in their words")  # fmt: skip
        return (f"Your answer changed no coach note. The learner's message may be about this one: {listed}. "
                f"{verb[0].upper()}{verb[1:]} only if that is what they ask; if it is not, change no note and answer "
                "their message.")  # fmt: skip
    if intent == FORGET:
        what = "The learner asks you to forget it: call forget_note with its id now"
    else:
        what = ("The learner corrects it with a new wish: call remember_note with replaces set to its id and the new "
                "wish in their words now - do not forget it")  # fmt: skip
    return f"Your answer changed no coach note, but the learner's message is about this one: {listed}. {what}, then answer in one or two sentences."
