"""How Orena says "I" and "you" to this learner, in their support language (contract v5 §5.6, D-096).

The learner's choice arrives as `context.address` - `{self, user, register, lang}` -
and is applied only when its `lang` is the support language; omitted, or with any
invalid term, the language's default applies to the whole object: Vietnamese
`mình` / `bạn`, Chinese `我` / `你` (`plain`; `您` only for `polite`), English
`I` / `you` (where `user` is a name to call the learner by, never a replacement for
"you"). A support language without a row uses its own ordinary first and second
person, left to the model.

It is kept as a coach note of kind `address`, one per support language
(`address-<lang>`), which the device stores and sends back as `context.address`,
never in `coach_notes`. The server proposes it with `memory_update` - when the
learner asks for a pair, when their own Vietnamese kinship address is answered in
kind (below), or when they say yes to the one question about a pair they keep
using - and reads the `address` object, never the note's text. Nothing is inferred
from gender, age, a name or anything else; the words change, the respect does not.

The terms may carry the learner's name: they are used for the turn only - never
logged, stored or written raw into an instruction (the model reads them as JSON
data in its context).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from writing_coach.agent.schemas import CoachNote

ADDRESS_VERSION = 5  # the contract version that carries context.address (§5.6)

# §5.6's table: the fields each support language takes, and its default.
ADDRESS_FIELDS = MappingProxyType({"en": ("user",), "vi": ("self", "user"), "zh-CN": ("self", "user", "register")})
DEFAULTS = MappingProxyType({"vi": ("mình", "bạn"), "zh-CN": ("我", "你"), "en": ("I", "you")})
REGISTERS = ("plain", "polite")

MAX_TERM_CHARS = 24
MAX_TERM_WORDS = 3  # "chị", "cô giáo", "anh Minh": a way of calling, never a sentence

# Readable in the learner's privacy list; never read back (the server reads the `address` object).
_NOTE_TEXT = MappingProxyType(
    {
        "vi": 'Xưng hô: Orena xưng "{self}", gọi người học là "{user}".',
        "zh-CN": '称呼：Orena 自称"{self}"，称学习者为"{user}"。',
        "en": 'Address: Orena calls the learner "{user}".',
    }
)


@dataclass(frozen=True)
class Address:
    self_term: str | None  # None: the support language's ordinary first person
    user_term: str | None
    chosen: bool  # False: the language default
    register: str | None = None  # zh-CN only: plain | polite
    lang: str | None = None  # the support language it is for: copy in another language takes that one's default

    def public(self) -> dict:
        # Not "user": the provider-bound context drops keys that name a learner (agent/redaction.py).
        out = {"self_term": self.self_term, "user_term": self.user_term, "set_by": "learner" if self.chosen else "default"}
        if self.register is not None:
            out["register"] = self.register
        return out

    @property
    def pair(self) -> tuple[str | None, str | None]:
        return self.self_term, self.user_term


def valid_term(term: object) -> bool:
    """§5.6: 1-24 characters, at most 3 words, only Unicode letters with their combining marks, single spaces
    between words; a word starts with a letter. The same rule as the UI's (static/orena/agent/contract.js)."""

    if not isinstance(term, str) or not 1 <= len(term) <= MAX_TERM_CHARS:
        return False
    words = term.split(" ")
    if len(words) > MAX_TERM_WORDS:
        return False
    for word in words:
        if not word or not unicodedata.category(word[0]).startswith("L"):
            return False
        if any(unicodedata.category(ch)[0] not in "LM" for ch in word):
            return False
    return True


def note_id(support: str) -> str:
    return f"address-{support}"


def default_address(support: str) -> Address:
    """The support language's own pair; for a language with none written here, its ordinary first and second
    person, left to the model rather than an English "I"/"you" (adversarial review)."""

    self_term, user_term = DEFAULTS.get(support, (None, None))
    return Address(self_term, user_term, chosen=False, register="plain" if support == "zh-CN" else None, lang=support)


def normalize(raw: object, support: str) -> dict | None:
    """The §5.6 object for this support language, or None: the fields the language ignores dropped, zh-CN's
    register resolved (plain unless polite), and None for any invalid term, a language with no row, or an object
    that carries nothing (the UI's normalizeAddress)."""

    fields = ADDRESS_FIELDS.get(support)
    if not fields or not isinstance(raw, Mapping):
        return None
    out: dict[str, Any] = {"lang": support}
    for name in fields:
        if name == "register":
            out["register"] = "polite" if raw.get("register") == "polite" else "plain"
            continue
        value = raw.get(name)
        if value is None:
            continue
        if not valid_term(value):
            return None
        out[name] = value
    return out if len(out) > 1 else None


def resolve(raw: object, support: str, version: int = ADDRESS_VERSION) -> Address:
    """`context.address` as this turn applies it: only when its lang is the support language, only for a v5+
    client, and the whole object's default when anything in it is invalid."""

    if version < ADDRESS_VERSION or not isinstance(raw, Mapping) or raw.get("lang") != support:
        return default_address(support)
    chosen = normalize(raw, support)
    if chosen is None:
        return default_address(support)
    base = default_address(support)
    register = chosen.get("register") if support == "zh-CN" else None
    user = chosen.get("user")
    if support == "zh-CN" and user is None:
        user = "您" if register == "polite" else "你"
    elif support == "en":
        user = user or base.user_term
    return Address(
        chosen.get("self", base.self_term),
        user or base.user_term,
        chosen=True,
        register=register,
        lang=support,
    )


def address_note(
    support: str, self_term: str | None, user_term: str | None, *, register: str | None = None, now: datetime | None = None
) -> dict:
    """The note that keeps the choice (§5.6): kind `address`, full weight, no expiry, one per support language."""

    raw: dict[str, Any] = {"self": self_term, "user": user_term}
    if support == "zh-CN":
        raw["register"] = register or "plain"
    address = normalize({k: v for k, v in raw.items() if v is not None}, support)
    if address is None:
        raise ValueError("an address note needs valid terms for a support language §5.6 names")
    default_self, default_user = DEFAULTS[support]
    template = _NOTE_TEXT[support]
    note = {
        "id": note_id(support),
        "kind": "address",
        "address": address,
        "text": template.format(self=address.get("self", default_self), user=address.get("user", default_user)),
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
