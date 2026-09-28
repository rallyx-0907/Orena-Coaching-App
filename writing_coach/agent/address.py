"""How Orena says "I" and "you" to this learner, in their support language (human direction 2026-09-28).

The default is the support language's own: Vietnamese `mình` / `bạn`, Chinese
`我` / `你`, English `I` / `you`. It changes only from the learner's own words:
they ask for another pair, or they keep using one and say yes when asked once.
Nothing is inferred from gender, age, a name or anything else, and the words
change without the respect changing.

The choice is a coach note the learner stated directly (contract §5.4): the
agent proposes it with `memory_update`, the device keeps it and sends it back
in `coach_notes`, and each turn reads it here. One note per support language,
with a fixed id (`address-vi`, `address-zh-CN`, `address-en`), so a change of
mind replaces it and the privacy list shows it in the learner's own language.

The server's fixed copy (identity, refusals, errors) keeps the default until
the contract carries the address (proposed v5); only the model applies it now.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType

from writing_coach.agent.schemas import CoachNote

DEFAULTS = MappingProxyType({"vi": ("mình", "bạn"), "zh-CN": ("我", "你"), "en": ("I", "you")})

# 1-24 letters of any script, with their marks, and spaces, hyphens or apostrophes between them.
_TERM = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ '\-])*$")
MAX_TERM_CHARS = 24

# Readable in the learner's privacy list, and read back here.
_NOTE_TEXT = MappingProxyType(
    {
        "vi": 'Xưng hô: Orena xưng "{self}", gọi người học là "{user}".',
        "zh-CN": '称呼：Orena 自称"{self}"，称学习者为"{user}"。',
        "en": 'Address: Orena calls itself "{self}" and the learner "{user}".',
    }
)
_NOTE_TERMS = re.compile(r'"([^"]{1,24})"[^"]*"([^"]{1,24})"')


@dataclass(frozen=True)
class Address:
    self_term: str | None  # None: the support language's ordinary first person
    user_term: str | None
    chosen: bool  # False: the language default

    def public(self) -> dict:
        # Not "user": the provider-bound context drops keys that name a learner (agent/redaction.py).
        return {"self_term": self.self_term, "user_term": self.user_term, "set_by": "learner" if self.chosen else "default"}


MAX_TERM_WORDS = 3  # "chị", "cô giáo", "anh Minh": a way of calling, never a sentence


def valid_term(term: object) -> bool:
    if not isinstance(term, str):
        return False
    stripped = term.strip()
    return (
        0 < len(stripped) <= MAX_TERM_CHARS
        and len(stripped.split()) <= MAX_TERM_WORDS
        and bool(_TERM.match(stripped))
    )


def note_id(support: str) -> str:
    return f"address-{support}"


def default_address(support: str) -> Address:
    """The support language's own pair; for a language with none written here, its ordinary first and second
    person, left to the model rather than an English "I"/"you" (adversarial review)."""

    self_term, user_term = DEFAULTS.get(support, (None, None))
    return Address(self_term, user_term, chosen=False)


def address_for(notes: Iterable[CoachNote], support: str) -> Address:
    """The pair the learner chose for this support language, or its default."""

    for note in notes:
        if note.id != note_id(support):
            continue
        found = _NOTE_TERMS.search(note.text)
        if found and valid_term(found.group(1)) and valid_term(found.group(2)):
            return Address(found.group(1).strip(), found.group(2).strip(), chosen=True)
    return default_address(support)


def address_note(support: str, self_term: str, user_term: str, *, now: datetime | None = None) -> dict:
    """The coach note that keeps the pair: stated by the learner, so full weight and no expiry."""

    template = _NOTE_TEXT.get(support, _NOTE_TEXT["en"])
    note = {
        "id": note_id(support),
        "kind": "preference",
        "text": template.format(self=self_term.strip(), user=user_term.strip()),
        "weight": 1.0,
        "last_reinforced": (now or datetime.now(UTC)).isoformat(),
        "expires_at": None,
    }
    CoachNote.model_validate(note)
    return note


# --- Vietnamese kinship address, mirrored at once (human direction 2026-09-28) ---------------------
#
# A learner who calls themselves anh/chị is answered by an Orena that is "em"; cô/chú/bác, by "cháu". A
# learner who is "em" (or "cháu") to an Orena they call anh/chị (or cô/chú/bác) is answered with exactly those
# words. Only clear first- and second-person uses count: "anh tôi", "chị của mình", "anh ấy", "anh trai",
# "anh Minh" or "chị em" are someone else, and anything unclear keeps the current pair. tao/mày and other
# casual pairs are never mirrored: they change only on an explicit request (set_address).

ELDER_SELF = {"anh": "em", "chị": "em", "cô": "cháu", "chú": "cháu", "bác": "cháu"}  # learner's word -> Orena's
YOUNGER_SELF = {"em": ("anh", "chị"), "cháu": ("cô", "chú", "bác")}  # learner's word -> Orena words it goes with
GENDERED = frozenset({"anh", "chị", "cô", "chú", "bác", "ông", "bà"})  # never used unless the learner used them
CASUAL = frozenset({"tao", "mày"})  # only on an explicit request

# After a kinship word, these make it someone else, a name, a pair of siblings, or part of another word
# ("cô giáo", "bác sĩ", "chú ý", "chú thích", "Anh ngữ", "em bé").
_NOT_A_PERSON_IN_THE_CHAT = (
    r"(?:tôi|mình|tao|của|ấy|ta|trai|gái|họ|kia|này|nọ|rể|dâu|cả|hai|ba|út|em|chị|anh|nhà|"
    r"giáo|sĩ|ý|thích|ngữ|văn|quốc|hùng|bé|ruột|[A-ZĐ]\w*)"
)
# Before a kinship word, these make it a language, a country or part of another word ("tiếng Anh", "nước Anh",
# "ghi chú"): never the learner or Orena. Each pattern below also fixes the word before (sentence start, "cho",
# "để", a verb), so these are a second guard.
_NOT_AFTER = r"(?i:(?<!tiếng )(?<!nước )(?<!ghi )(?<!người )(?<!dân ))"
# The learner as the subject of an act of their own, or the one helped: clear first person.
_SELF_ACTS = r"(?:muốn|cần|hỏi|cảm ơn|không hiểu|chưa hiểu|đang học|vừa học|thắc mắc|quên|nhớ)"


def _self_elder(text: str) -> str | None:
    """The kinship word the learner calls themselves by, when it is clearly first person."""

    for word in ELDER_SELF:
        w = re.escape(word)
        blocked = rf"(?!\s+{_NOT_A_PERSON_IN_THE_CHAT}\b)"
        patterns = (
            rf"(?:^|[.!?,]\s*)(?i:{w}){blocked}\s+(?i:{_SELF_ACTS})\b",  # "Anh muốn hỏi…", "Chị cảm ơn em"
            rf"(?i:\b(?:cho|để|giúp|giùm|bảo|chỉ)\s+){w}\b{blocked}(?:\s+(?i:hỏi|xin|biết|với|nhé|nha|ạ)\b|\s*[.!?,]|\s*$)",
        )
        if any(re.search(_NOT_AFTER + p, text) for p in patterns):
            return word
    return None


def _orena_elder(text: str) -> tuple[str, str] | None:
    """(Orena's word, the learner's word) when the learner is em/cháu to an Orena they call anh/chị/cô/chú/bác."""

    lowered = text.casefold()
    for younger, elders in YOUNGER_SELF.items():
        if not re.search(rf"\b{younger}\b", lowered):
            continue
        for elder in elders:
            e, y = re.escape(elder), re.escape(younger)
            blocked = rf"(?!\s+{_NOT_A_PERSON_IN_THE_CHAT}\b)"
            patterns = (
                rf"\b{y}\s+(?:hỏi|cảm ơn|chào|nhờ|xin|muốn hỏi)\s+{_NOT_AFTER}{e}\b{blocked}",  # "em hỏi chị"
                rf"(?:^|[.!?,:;]\s*){e}\s+ơi\b",  # "Chị ơi, em…": calling, so first in its clause
                rf"{_NOT_AFTER}\b{e}\b{blocked}\s+(?:cho|giúp|giải thích cho|chỉ cho|dạy)\s+{y}\b",  # "chị cho em hỏi"
            )
            if any(re.search(p, lowered) for p in patterns):
                return elder, younger
    return None


def mirrored_address(message: str | None) -> tuple[str, str] | None:
    """(Orena's term, the learner's term) the learner's own Vietnamese kinship address calls for, or None."""

    if not message:
        return None
    text = unicodedata.normalize("NFC", message)
    orena = _orena_elder(text)
    self_word = _self_elder(text)
    if orena and self_word:
        return None  # both readings at once: unclear, keep the current pair
    if orena:
        return orena
    if self_word:
        return ELDER_SELF[self_word], self_word
    return None


def used_by_learner(term: str, words: str | None) -> bool:
    return bool(words) and bool(re.search(rf"(?i)(?<!\w){re.escape(term)}(?!\w)", words or ""))


def explicit_request(term: str, words: str | None) -> bool:
    """A casual term the learner asked for in so many words: "xưng tao gọi mày đi"."""

    return used_by_learner(term, words) and bool(re.search(r"(?i)\b(?:xưng|gọi|đổi)\b", words or ""))


def capitalised(term: str) -> str:
    """A term at the start of a sentence (`Chị là…`); other scripts are left as they are."""

    return term[:1].upper() + term[1:] if term[:1].isalpha() and term[:1].lower() != term[:1].upper() else term
