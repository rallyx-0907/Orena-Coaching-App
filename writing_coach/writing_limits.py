"""How much writing Orena accepts, in one place.

A database TEXT column will hold a megabyte, a JSON body parser will read ten,
and a provider will charge for every token of it. None of those is a product
decision. This module is the product decision, and every layer that touches
learner writing asks it rather than carrying a number of its own: the browser
before it inserts a paste, the request model, the route before it spends
anything, the repository before it writes, and the evaluator before it builds a
prompt.

The numbers come from what learners actually write. A long piece in this
product is an essay, an email or a report - a few thousand words. 12,000 code
points is generous for all of those and is already what the writing box
accepts; the byte and line bounds exist only to catch input that is not
writing at all: a file pasted by accident, a generator, one enormous line.

Three bounds, because one does not catch the others:

  characters  what a learner perceives, and what the box counts
  bytes       what storage and transport actually pay for, and what a
              character bound cannot bound on its own - 12,000 Han characters
              or emoji are three to four times their count in UTF-8
  lines       a character bound says nothing about a million empty lines,
              which cost little to store and a great deal to lay out

Nothing here truncates. Learner writing is the learner's; an over-long piece is
refused with its measurement so the learner knows by how much, and what they
wrote is still theirs.

The other end of the range is here too, and it is a different kind of bound:
the request minimum. It answers "is this an attempt at writing at all?" - not
"is this enough to grade?", which is the evaluator's own question
(`band_status: insufficient_evidence`) and is left there. It refuses only what
is not writing: nothing, whitespace, punctuation, a stray character. A minimum
of code points cannot say that fairly, because a code point is a different
amount of writing in every script - `我是学生。` is a complete HSK 1 sentence and
five of them - so the minimum is a count of what each learning language writes
in, one row per language, and a language without a row is counted by the
stated default rather than refused a review.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

# The contract the whole product shares. `static/orena/capabilities/writing-limits.js`
# carries the same numbers for the browser, and a gate fails if the two drift.
MAX_CHARACTERS = 12_000
MAX_BYTES = 60_000
MAX_LINES = 1_000

# What the piece is *for*: a short line, not a second essay.
MAX_INTENTION_CHARACTERS = 240

# A prompt is built from the title and the learner's intention. It is bounded
# for the same reason the text is: it reaches the provider.
MAX_PROMPT_CHARACTERS = 2_000

# A provider answers with structured feedback, not with a document. This bounds
# what may be persisted and rendered from one answer, whatever the provider
# actually returned.
MAX_REVIEW_BYTES = 256_000
MAX_REVIEW_ITEMS = 60


@dataclass(frozen=True)
class Measurement:
    """What a piece of writing measures, and whether it fits.

    Measured, never modified: `characters` counts code points as a learner
    counts them, `bytes` is the UTF-8 length, and `lines` counts line
    separators in either convention. A caller that needs to report a breach has
    everything it needs here without looking at the text again.
    """

    characters: int
    bytes: int
    lines: int
    limit_exceeded: str = ""

    @property
    def within_limits(self) -> bool:
        return not self.limit_exceeded

    def as_context(self) -> dict[str, int | str]:
        """Operational metadata for an error or a log line - never the text.

        An oversized request must not put a learner's writing into a log, so
        this is deliberately the only thing a refusal carries out of here.
        """
        return {
            "limit": self.limit_exceeded,
            "characters": self.characters,
            "bytes": self.bytes,
            "lines": self.lines,
            "max_characters": MAX_CHARACTERS,
            "max_bytes": MAX_BYTES,
            "max_lines": MAX_LINES,
        }


def measure_writing(text: str) -> Measurement:
    """Measure a piece of learner writing against the shared contract.

    Counting is done on the string, never on a slice of its bytes: a UTF-8
    sequence cut in half is corruption, and a learner's Vietnamese or Chinese
    would be the first to suffer it. `len()` on a Python string is already code
    points, and combining marks count as the separate code points they are -
    which is the honest answer for a storage and token bound, even though a
    reader would see fewer glyphs.
    """
    value = text if isinstance(text, str) else str(text or "")
    characters = len(value)
    size = len(value.encode("utf-8"))
    # \r\n is one separator, not two, so CRLF text is not penalised for being
    # written on Windows.
    lines = value.replace("\r\n", "\n").count("\n") + 1 if value else 0
    breach = ""
    if characters > MAX_CHARACTERS:
        breach = "characters"
    elif size > MAX_BYTES:
        breach = "bytes"
    elif lines > MAX_LINES:
        breach = "lines"
    return Measurement(characters=characters, bytes=size, lines=lines, limit_exceeded=breach)


def fits(text: str) -> bool:
    return measure_writing(text).within_limits


# --- The request minimum -------------------------------------------------
#
# Not "is this enough to grade" - the evaluator answers that itself, with
# `band_status: insufficient_evidence`, and a short attempt still earns its
# review. Only "is this writing at all". Counted in what the learning language
# is written in, so the same number means the same amount of writing.
#
#   han    Han characters. Ideographic punctuation such as 。 is not one, so
#          `你好。` is two. The ranges are stated, not read from a Unicode
#          property, so the browser can state the same ones: CJK Unified
#          Ideographs and Extension A, the compatibility ideographs, and the
#          supplementary-plane Extensions B onward. Radicals are not a
#          character anyone writes and are left out.
#   words  Runs of letters and digits, joined by an apostrophe or a hyphen
#          inside a word, that hold at least one letter. A number alone is not
#          a word of writing, and punctuation, whitespace and emoji are not
#          words. The text is normalised first, so a Vietnamese or accented
#          word typed with combining marks is one word, not two.
#
# `words` counts spaced text. A language written without spaces must have a row
# of its own before the product teaches it - the default would count a whole
# sentence as one word - and `tests/test_writing_minimum.py` fails until a
# language the product teaches has one.
#
# These are not the numbers a learner is shown, and are not meant to be. The
# count under a draft (`Intl.Segmenter` in the browser) and the stored
# `word_count` (`languages.runtime.writing_unit_count`) answer "how long is this
# piece?"; this answers "is it writing at all?". They part where a token is not
# a word of writing: a bare number is a word to both of those and not to this
# (`3 cats` shows 2 words and counts 1 here), a hyphenated compound is one word
# here and two to the Segmenter, and for Chinese the shown count is Segmenter
# words while this counts Han characters. Neither can be reused as it stands -
# `writing_unit_count` reads the request's language from a context variable,
# and this is pure and is handed the language - so the difference is stated
# rather than hidden, and the shared fixture pins it.
#
# The browser carries the same table in `static/orena/capabilities/writing-limits.js`.
# `tests/fixtures/writing_minimum_cases.json` states the table and the counts
# once, and both sides are tested against it.

_HAN = re.compile(
    "[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f\U00030000-\U000323af]"
)
_WORD = re.compile(r"[^\W_]+(?:['\u2019-][^\W_]+)*")


def count_han(text: str) -> int:
    """Han characters in the text: what a Chinese learner has written."""
    return len(_HAN.findall(text if isinstance(text, str) else str(text or "")))


def count_words(text: str) -> int:
    """Words in the text: what an English learner has written."""
    value = unicodedata.normalize("NFC", text if isinstance(text, str) else str(text or ""))
    return sum(
        1 for match in _WORD.finditer(value) if any(char.isalpha() for char in match.group())
    )


_COUNTERS = MappingProxyType({"han": count_han, "words": count_words})
_UNIT_NOUNS = MappingProxyType(
    {"han": ("Chinese character", "Chinese characters"), "words": ("word", "words")}
)


@dataclass(frozen=True)
class MinimumRule:
    """The least writing that is an attempt, and the unit it is counted in."""

    unit: str
    minimum: int

    def __post_init__(self) -> None:
        if self.unit not in _COUNTERS:
            raise ValueError(f"unknown Writing minimum unit: {self.unit!r}")
        if self.minimum < 1:
            raise ValueError("a Writing minimum of nothing is no minimum")


# One row per language the product teaches to write in, keyed the way the rest
# of Writing keys a language. English is counted in words, Chinese in Han
# characters; the values are the smallest that still refuse a stray character
# and admit a real greeting: `你好。` and `Hi Bob.` are both attempts.
MINIMUM_BY_LANGUAGE: Mapping[str, MinimumRule] = MappingProxyType(
    {
        "en": MinimumRule(unit="words", minimum=2),
        "zh": MinimumRule(unit="han", minimum=2),
    }
)

# What a language with no row of its own is held to.
DEFAULT_MINIMUM = MinimumRule(unit="words", minimum=2)


def language_key(code: str | None) -> str:
    """The language a code names, without its region: `zh-CN` and `zh_TW` are `zh`."""
    return str(code or "").strip().casefold().replace("_", "-").split("-", 1)[0]


def minimum_rule(language: str | None) -> MinimumRule:
    return MINIMUM_BY_LANGUAGE.get(language_key(language), DEFAULT_MINIMUM)


@dataclass(frozen=True)
class MinimumCheck:
    """What a piece of writing counts to, against the minimum of its language.

    Like `Measurement`: measured, never modified, and it carries everything a
    refusal needs without the text.
    """

    language: str
    unit: str
    minimum: int
    count: int

    @property
    def met(self) -> bool:
        return self.count >= self.minimum

    def as_context(self) -> dict[str, int | str]:
        """Operational metadata for an error or a log line - never the text."""
        return {
            "limit": "minimum",
            "language": self.language,
            "unit": self.unit,
            "minimum": self.minimum,
            "count": self.count,
        }


def check_minimum(text: str, language: str | None) -> MinimumCheck:
    """Count the text in its language's unit. Pure: the caller names the language."""
    rule = minimum_rule(language)
    return MinimumCheck(
        language=language_key(language),
        unit=rule.unit,
        minimum=rule.minimum,
        count=_COUNTERS[rule.unit](text),
    )


def meets_minimum(text: str, language: str | None) -> bool:
    return check_minimum(text, language).met


def minimum_message(check: MinimumCheck) -> str:
    """The refusal in plain English, saying what would be enough."""
    singular, plural = _UNIT_NOUNS[check.unit]
    noun = singular if check.minimum == 1 else plural
    return f"This is too short to review. Write at least {check.minimum} {noun}."
