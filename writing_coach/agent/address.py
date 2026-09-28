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
    self_term: str
    user_term: str
    chosen: bool  # False: the language default

    def public(self) -> dict:
        # Not "user": the provider-bound context drops keys that name a learner (agent/redaction.py).
        return {"self_term": self.self_term, "user_term": self.user_term, "set_by": "learner" if self.chosen else "default"}


def valid_term(term: object) -> bool:
    return isinstance(term, str) and 0 < len(term.strip()) <= MAX_TERM_CHARS and bool(_TERM.match(term.strip()))


def note_id(support: str) -> str:
    return f"address-{support}"


def default_address(support: str) -> Address:
    self_term, user_term = DEFAULTS.get(support, DEFAULTS["en"])
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


def capitalised(term: str) -> str:
    """A term at the start of a sentence (`Chị là…`); other scripts are left as they are."""

    return term[:1].upper() + term[1:] if term[:1].isalpha() and term[:1].lower() != term[:1].upper() else term
