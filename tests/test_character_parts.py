"""Curated decomposition, with verified data as the referee.

The point of this file is the first test. A radical is a claim about a
character, and the vendored stroke pack already knows which strokes of a
character belong to its radical. So every claim in `character_parts.json` can
be checked against data nobody wrote by hand — and a wrong one fails here
instead of being shown to a learner as fact. It caught three in the first
draft.
"""

import pytest

from writing_coach.languages.chinese import character_parts
from writing_coach.languages.chinese import stroke_order
from writing_coach.orthography import validate_orthography
from writing_coach.languages.chinese.orthography import build_chinese_orthography

pytestmark = pytest.mark.skipif(
    not stroke_order.installed(), reason="the vendored stroke pack is not installed"
)

CHARACTERS = sorted((character_parts._data().get("characters") or {}))


def test_the_file_carries_some_characters():
    assert CHARACTERS, "the curated file is empty or unreadable"


@pytest.mark.parametrize("character", CHARACTERS)
def test_every_declared_radical_matches_the_verified_pack(character):
    """The radical's own stroke count equals how many strokes the pack marks.

    This is the whole safety net: 钅 has five strokes and the pack marks five
    of 钱's as the radical's, so declaring 钧 (nine) fails.
    """

    entry = stroke_order.character_strokes(character)
    assert entry is not None, f"{character} is not in the pack"
    declared = character_parts._data()["characters"][character]["radical"]["surface"]
    radical = stroke_order.character_strokes(declared)
    assert radical is not None, f"the radical {declared} is not in the pack"
    assert len(entry["radical_strokes"]) == radical["stroke_count"], (
        f"{character}: the pack marks {len(entry['radical_strokes'])} radical strokes, "
        f"but {declared} has {radical['stroke_count']}"
    )


@pytest.mark.parametrize("character", CHARACTERS)
def test_a_component_is_never_the_character_itself(character):
    """A character is not a part of itself, and saying so teaches nothing."""

    entry = character_parts._data()["characters"][character]
    for component in entry.get("components") or ():
        assert component["surface"] != character, f"{character} lists itself as a part"


def test_the_claim_is_decomposition_and_says_so():
    where = character_parts.provenance()
    assert where["evidence_type"] == "structural-decomposition"
    # Never etymology: the architecture requires the three to be told apart,
    # and only etymology may claim trusted provenance.
    assert where["evidence_type"] != "etymology"


def test_the_facts_pass_the_shared_orthography_contract():
    """Built into a real unit, these facts validate - which is what proves they
    are the contract's `radical`/`components` and not a private shape."""

    facts = character_parts.facts_for_word("想", support="vi")
    assert "想" in facts
    built = build_chinese_orthography("想", facts=facts)
    validate_orthography(built)
    unit = built["units"][0]
    assert unit["facts"]["radical"]["value"]["surface"] == "心"
    assert unit["facts"]["radical"]["value"]["gloss"] == "tim, ý nghĩ"
    assert unit["facts"]["components"]["value"][0]["surface"] == "相"
    # The stroke provider stays authoritative for its own two facts.
    assert unit["facts"]["stroke_count"]["value"] == 13


def test_a_gloss_not_written_in_the_learners_language_is_absent():
    """Not the English one wearing a Vietnamese label."""

    facts = character_parts.facts_for("钱", support="fr")
    assert "gloss" not in facts["radical"]["value"]
    assert facts["radical"]["value"]["surface"] == "钅"


def test_a_character_with_no_curated_parts_answers_with_nothing():
    assert character_parts.facts_for("一二三"[0:1] + "￿") == {}
    assert character_parts.facts_for_word("hello") == {}


def test_every_character_in_the_file_is_one_character():
    for character in CHARACTERS:
        assert len(character) == 1, f"{character!r} is not a single character"
