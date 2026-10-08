"""One word, opened all the way: what the deep frames are given.

The projection is pure, so these hold the contract without a database, a
provider or an asset store. What they are really protecting is the rule that
an empty section is *absent* rather than invented - the deep frames have eight
sections and a thin catalogue entry fills two of them, and the honest screen is
the one with two.
"""

from writing_coach import word_deep


def test_senses_take_the_entry_part_of_speech_when_a_sense_has_none():
    entry = {
        "part_of_speech": "verb",
        "detailed_definitions": [{"text": "to want"}, {"text": "to think"}],
        "examples": [{"text": "I want to go."}, {"text": "Let me think."}],
    }
    assert word_deep.senses_of(entry) == [
        {"pos": "verb", "meaning": "to want", "example": "I want to go."},
        {"pos": "verb", "meaning": "to think", "example": "Let me think."},
    ]


def test_a_sense_keeps_its_own_part_of_speech_over_the_entry_one():
    entry = {
        "part_of_speech": "verb",
        "detailed_definitions": [{"text": "want", "part_of_speech": "auxiliary"}],
    }
    assert word_deep.senses_of(entry)[0]["pos"] == "auxiliary"


def test_short_meanings_are_the_senses_when_there_are_no_detailed_ones():
    entry = {"part_of_speech": "noun", "short_meanings": [{"text": "harbour"}]}
    assert word_deep.senses_of(entry) == [
        {"pos": "noun", "meaning": "harbour", "example": ""}
    ]


def test_an_entryless_word_still_answers_with_the_word():
    payload = word_deep.project_word_deep(
        word="unknowable",
        entry=None,
        saved=None,
        neighbours=(),
        layer={},
        sentences=(),
        readings=(),
        reading="",
    )
    assert payload["headword"] == "unknowable"
    # Every section is empty rather than filled with something plausible.
    assert payload["senses"] == []
    assert payload["combinations"] == []
    assert payload["related"] == []
    assert payload["contrast"] == []
    assert payload["commonMistake"] == ""
    assert payload["sources"] == []
    assert payload["learnerSentences"] == []


def test_combinations_come_from_the_catalogue_and_keep_their_reading():
    payload = word_deep.project_word_deep(
        word="想",
        entry={"term": "想", "language_code": "zh"},
        saved=None,
        neighbours=[
            {"term": "想要", "reading": "xiǎng yào", "note": "to want"},
            {"term": "想到", "reading": "xiǎng dào", "note": ""},
        ],
        layer={},
        sentences=(),
        readings=("xiǎng",),
        reading="xiǎng",
    )
    assert payload["combinations"] == [
        {"term": "想要", "reading": "xiǎng yào"},
        {"term": "想到", "reading": "xiǎng dào"},
    ]
    # A neighbour with no meaning is a chip, never a related row: the related
    # section draws a note beside the term, and a blank one says nothing.
    assert payload["related"] == [{"term": "想要", "reading": "xiǎng yào", "note": "to want"}]
    assert payload["script"] == "hanzi"


def test_the_catalogue_usage_note_outranks_the_explained_mistake():
    payload = word_deep.project_word_deep(
        word="想",
        entry={"term": "想", "usage_notes": [{"text": "Not directly with a noun."}]},
        saved=None,
        neighbours=(),
        layer={"commonMistake": "Something a model said."},
        sentences=(),
        readings=(),
        reading="",
    )
    assert payload["commonMistake"] == "Not directly with a noun."


def test_where_it_was_met_is_only_said_when_something_was_recorded():
    kept = {"source_kind": "manual", "source_fragment": ""}
    assert word_deep._sources_of(kept) == []
    met = {"source_kind": "listening", "source_fragment": "在餐厅点菜"}
    assert word_deep._sources_of(met) == [
        {"kind": "listening", "title": "在餐厅点菜", "at": "", "id": ""}
    ]


def test_the_explanation_cache_key_separates_two_readings_of_one_word():
    one = word_deep.cache_key("zh:xing", "xíng", "vi")
    other = word_deep.cache_key("zh:xing", "háng", "vi")
    assert one != other
    assert one.startswith("word-deep/") and one.endswith(".json")
    # And it is stable, or a cache would never hit.
    assert one == word_deep.cache_key("zh:xing", "xíng", "vi")


def test_the_support_language_is_part_of_the_key():
    assert word_deep.cache_key("zh:xiang", "xiǎng", "vi") != word_deep.cache_key(
        "zh:xiang", "xiǎng", "en"
    )


def test_explained_keeps_only_the_sections_the_frames_draw():
    layer = word_deep.explained(
        {
            "mental_model": "A thought in the head.",
            "common_mistake": "Not with a bare noun.",
            "contrast": [{"term": "要", "note": "more decided"}, {"term": "", "note": "x"}],
            "summary": "ignored",
            "grammar_notes": ["ignored"],
        }
    )
    assert layer == {
        "mentalModel": "A thought in the head.",
        "commonMistake": "Not with a bare noun.",
        "contrast": [{"term": "要", "note": "more decided"}],
    }


def test_the_core_idea_stands_in_when_there_is_no_mental_model():
    assert word_deep.explained({"core_idea": "wanting"})["mentalModel"] == "wanting"
