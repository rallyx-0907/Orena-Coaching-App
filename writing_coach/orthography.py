"""The general `orthography` Vocabulary Card capability seam.

`ORENA_VOCABULARY_ARCHITECTURE.md` §4 names `orthography` as one general
card capability with script-specific renderers underneath it — this module is
that seam. Today there is exactly one language adapter behind it: Chinese,
which reuses the already-shipped, already-tested stroke-order capability at
`writing_coach/languages/chinese/stroke_order.py`. It is not a second dataset
and not a second adapter; it imports and calls that module's public
`stroke_order_for`, never reimplements stroke lookup or pack decoding.

Structural data only. No mnemonic or etymology content is added here, and
none should be — `ORENA_UNDERSTANDING_ENGINE.md` §4's accuracy rule applies to
this seam exactly as it applies to the capability it projects.
"""

from __future__ import annotations

from typing import Any

from writing_coach.languages.chinese import stroke_order


def orthography_for_word(word: str, language_code: str) -> dict[str, Any] | None:
    """The card `orthography` field for `word` in `language_code`, or `None`.

    `None` for any non-Chinese language, and `None` (never a value with an
    empty `characters` list) when nothing in `word` is covered by the
    vendored stroke data — a card must not invent a value merely to fill an
    unused field. `source`/`source_version` are read from the stroke-order
    capability's own result rather than restated, so the two can never drift.
    """

    language = str(language_code or "").strip().casefold()
    if language != "zh":
        return None

    result = stroke_order.stroke_order_for(word)
    characters = result["characters"]
    if not characters:
        return None

    return {
        "script": "han",
        "characters": characters,
        "source": result["source"],
        "source_version": result["source_version"],
    }
