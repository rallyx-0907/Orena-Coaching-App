"""The rank ladder: thirty-two ranks, eight bands, and where a learner stands.

Who owns what:

- **"Orena Rank Frame Master v2"** owns the rank *system* - thirty-two ranks in
  eight bands, and the crystal each one is made of. The crystal is drawn in the
  browser (`static/orena/ui/rank-frame.js`); the names and bands are product
  facts and live here.
- **The Progress frame** states a word count for twenty of those ranks. The
  numbers are kept **by name**, not by position: a number the design states for
  Archivist is Archivist's wherever Archivist sits. Fourteen ranks have no
  stated number and can therefore not be reached by counting; they carry
  ``None`` rather than an invented threshold.
  ``docs/project/UI_BACKEND_GAPS.md`` records both the disagreement between the
  two sources (GAP-R2) and the missing numbers (GAP-R1).

The measure is the learner's mastered words, which the repository counts in
SQL. This module turns that one number into a rank, so Hồ sơ, Tiến độ and any
later surface read the same answer from the same place rather than each
computing their own.
"""
from __future__ import annotations

from typing import Any

RANK_NAMES: tuple[str, ...] = (
    "Initiate", "Apprentice", "Scribe", "Reader", "Cantor", "Artisan", "Adept", "Voyager",
    "Linguist", "Virtuoso", "Luminary", "Oracle", "Sage", "Maestro", "Herald", "Polyglot",
    "Navigator", "Cartographer", "Wayfinder", "Chronicler", "Rhapsode", "Orator", "Vesper", "Ember",
    "Archivist", "Curator", "Lumen", "Aurora", "Celestial", "Empyrean", "Zenith", "Paragon",
)

BAND_NAMES: tuple[str, ...] = (
    "Amethyst", "Sapphire", "Orchid", "Amber", "Aquamarine", "Carnelian", "Moonstone", "Prismatic",
)

# The Progress frame's own tiles, by name.
RANK_THRESHOLDS: dict[str, int] = {
    "Initiate": 50,
    "Apprentice": 150,
    "Scribe": 300,
    "Reader": 500,
    "Cantor": 700,
    "Artisan": 950,
    "Adept": 1200,
    "Voyager": 1450,
    "Linguist": 1600,
    "Luminary": 3000,
    "Oracle": 4500,
    "Sage": 6000,
    "Maestro": 8000,
    "Herald": 10000,
    "Polyglot": 13000,
    "Archivist": 16000,
    "Aurora": 20000,
    "Celestial": 25000,
    "Paragon": 30000,
}

RANK_TOTAL = len(RANK_NAMES)


def band_of(rank: int) -> str:
    """The band a rank belongs to. Four ranks to a band, in order."""

    index = max(1, min(RANK_TOTAL, int(rank or 0))) - 1
    return BAND_NAMES[min(len(BAND_NAMES) - 1, index // 4)]


def ladder() -> list[dict[str, Any]]:
    """Every rank, in order, with the word count it asks for or ``None``."""

    return [
        {
            "tier": index + 1,
            "name": name,
            "band": band_of(index + 1),
            "words": RANK_THRESHOLDS.get(name),
        }
        for index, name in enumerate(RANK_NAMES)
    ]


def tier_of(mastered: int) -> int:
    """The highest rank whose stated threshold the learner has passed.

    A rank with no stated threshold cannot be reached by counting, so it is
    stepped over rather than guessed at. Zero means no rank yet.
    """

    known = max(0, int(mastered or 0))
    tier = 0
    for entry in ladder():
        if entry["words"] is not None and known >= entry["words"]:
            tier = entry["tier"]
    return tier


def next_tier(mastered: int) -> dict[str, Any] | None:
    """The next rank the learner can actually reach, or ``None`` at the top of
    what the design has numbered."""

    known = max(0, int(mastered or 0))
    current = tier_of(known)
    for entry in ladder():
        if entry["tier"] > current and entry["words"] is not None and known < entry["words"]:
            return entry
    return None


def rank_state(mastered: int) -> dict[str, Any]:
    """Everything a surface needs to name a learner's rank, from one number."""

    known = max(0, int(mastered or 0))
    tier = tier_of(known)
    following = next_tier(known)
    entry = ladder()[tier - 1] if tier else None
    return {
        "rank": tier,
        "rank_total": RANK_TOTAL,
        "rank_name": entry["name"] if entry else "",
        "band": entry["band"] if entry else "",
        "next_rank_name": following["name"] if following else "",
        "next_rank_words": following["words"] if following else None,
        "next_rank_remaining": max(0, following["words"] - known) if following else 0,
    }
