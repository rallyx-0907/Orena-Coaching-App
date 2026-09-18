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
"""

from __future__ import annotations

from dataclasses import dataclass

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
