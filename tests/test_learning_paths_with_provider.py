"""Deterministic provider-injected coverage for the rich learning paths.

The register comparison, spoken-response coaching and generated reading
passages all reach a provider, and everything that protects the learner from
that provider lives in the normalisation around it: a quotation the learner
never wrote, a register outside the vocabulary, a comprehension question whose
evidence is not in the passage.

Those rules were only ever exercised by hand against injected browser
responses. Here they run against the real functions with a fake provider, so a
change that loosens one fails rather than reaching a learner.
"""

from __future__ import annotations

from typing import Any

import pytest

from writing_coach import becoming_reading, media_interaction


@pytest.fixture(autouse=True)
def english_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")


def _provider(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Install a provider that always answers `payload`, recording its requests."""
    seen: list[dict[str, Any]] = []

    def fake_run(capability_key: str, *, messages, schema, max_output_tokens):
        seen.append(
            {
                "capability_key": capability_key,
                "system": messages[0]["content"],
                "user": messages[1]["content"],
                "schema": schema,
            }
        )
        return payload

    monkeypatch.setattr(media_interaction, "_run_structured", fake_run)
    return seen


# --------------------------------------------------------------------------
# Register comparison
# --------------------------------------------------------------------------


def _register_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "meaning": "You went to the shop and bought bread.",
        "what_changes": "Sentence length and how much is spelled out.",
        "versions": [
            {
                "register": "conversational",
                "text": "Popped to the shop and grabbed some bread.",
                "why": "Short verbs, dropped subject.",
                "signals": ["phrasal verb", "dropped subject"],
                "use_when": "Texting a friend.",
                "avoid_when": "Writing to someone you do not know.",
            },
            {
                "register": "formal",
                "text": "I visited the shop and purchased bread.",
                "why": "Full clauses and a plainer verb.",
                "signals": ["full subject"],
                "use_when": "A letter.",
                "avoid_when": "Everyday conversation.",
            },
        ],
    }
    payload.update(overrides)
    return payload


def _explore(text: str = "I went to the shop and got bread.", situation: str = "") -> dict[str, Any]:
    return media_interaction.explore_registers(
        media_interaction.RegisterExploreIn(
            text=text,
            source_language="en",
            target_language="vi",
            situation=situation,
        )
    )


def test_register_comparison_returns_each_version_with_its_signals(monkeypatch) -> None:
    seen = _provider(monkeypatch, _register_payload())

    result = _explore(situation="A message to my landlord")

    assert result["available"] is True
    assert result["claim"] == "register_comparison"
    assert [item["register"] for item in result["versions"]] == ["conversational", "formal"]
    first = result["versions"][0]
    # A version without the signals that place it, and without when it is the
    # wrong choice, is a rewrite rather than a comparison.
    assert first["signals"] == ["phrasal verb", "dropped subject"]
    assert first["use_when"] and first["avoid_when"]
    assert result["what_changes"]
    # The situation the learner gave steers the request rather than being dropped.
    assert "A message to my landlord" in seen[0]["user"]


def test_register_comparison_drops_versions_outside_the_shared_vocabulary(monkeypatch) -> None:
    payload = _register_payload()
    payload["versions"].append(
        {"register": "playful", "text": "Bread! Got it!", "why": "x", "signals": [], "use_when": "", "avoid_when": ""}
    )
    payload["versions"].append(
        {"register": "academic", "text": "   ", "why": "x", "signals": [], "use_when": "", "avoid_when": ""}
    )
    _provider(monkeypatch, payload)

    result = _explore()

    registers = [item["register"] for item in result["versions"]]
    assert "playful" not in registers, "a register the product cannot label must not be shown"
    assert "academic" not in registers, "a version with no text is not a version"
    assert registers == ["conversational", "formal"]


def test_register_comparison_says_so_when_nothing_usable_came_back(monkeypatch) -> None:
    _provider(monkeypatch, _register_payload(versions=[]))

    result = _explore()

    assert result["available"] is False
    assert result["claim"] == "register_comparison_unavailable"
    assert result["versions"] == []
    # Nothing is rewritten in place of an answer that did not arrive.
    assert result["text"] == "I went to the shop and got bread."


def test_register_prompt_forbids_a_correct_version_and_invented_authority(monkeypatch) -> None:
    seen = _provider(monkeypatch, _register_payload())

    _explore()

    system = seen[0]["system"]
    assert "one version as correct and the others as mistakes" in system
    assert "Never cite a style guide, standard or corpus you were not given." in system


# --------------------------------------------------------------------------
# Spoken-response coaching
# --------------------------------------------------------------------------

TRANSCRIPT = "I would take you to the old market near the river, because it is very interesting for me."


def _coach(transcript: str = TRANSCRIPT, situation: str = "") -> dict[str, Any]:
    return media_interaction.coach_spoken_response(
        media_interaction.SpokenResponseIn(
            transcript=transcript,
            source_language="en",
            target_language="vi",
            situation=situation,
        )
    )


def test_spoken_coaching_keeps_only_quotations_the_learner_actually_said(monkeypatch) -> None:
    _provider(
        monkeypatch,
        {
            "carried": [
                {"quote": "the old market near the river", "why": "A specific place."},
                {"quote": "a sentence they never said", "why": "invented"},
            ],
            "landed_differently": [
                {
                    "quote": "it is very interesting for me",
                    "why": "Describes your reaction rather than giving a reason.",
                    "instead": "you would love how noisy it gets",
                    "judgement": "possible_but_unnatural",
                },
                {
                    "quote": "words from another take",
                    "why": "invented",
                    "instead": "x",
                    "judgement": "natural",
                },
            ],
            "another_way": "I think you would really like it there.",
            "next_attempt": "Say one thing you would do together.",
        },
    )

    result = _coach(situation="A friend has just moved to your city.")

    assert [item["quote"] for item in result["carried"]] == ["the old market near the river"]
    assert [item["quote"] for item in result["landed_differently"]] == ["it is very interesting for me"]
    assert result["available"] is True
    assert result["claim"] == "spoken_response_coaching_from_transcript"
    assert result["another_way"] and result["next_attempt"]


def test_spoken_coaching_uses_the_shared_judgement_vocabulary(monkeypatch) -> None:
    _provider(
        monkeypatch,
        {
            "carried": [],
            "landed_differently": [
                {
                    "quote": "very interesting for me",
                    "why": "reason",
                    "instead": "alternative",
                    "judgement": "not_a_real_judgement",
                }
            ],
            "another_way": "",
            "next_attempt": "",
        },
    )

    result = _coach()

    assert result["landed_differently"][0]["judgement"] in media_interaction.USAGE_JUDGEMENTS


def test_spoken_coaching_never_scores_and_never_claims_to_have_heard(monkeypatch) -> None:
    seen = _provider(
        monkeypatch,
        {"carried": [], "landed_differently": [], "another_way": "", "next_attempt": ""},
    )

    result = _coach()

    # Nothing survived, and the surface is told so rather than shown a shell.
    assert result["available"] is False
    # Coaching is not measurement: no score reaches the payload under any name.
    assert not {"score", "overall", "level", "cefr", "rating"} & set(result)
    system = seen[0]["system"]
    assert "You did NOT hear the audio" in system
    assert "never comment on pronunciation" in system
    assert "score, grade or estimate a level" in system


def test_spoken_coaching_carries_the_situation_it_was_answering(monkeypatch) -> None:
    seen = _provider(
        monkeypatch,
        {"carried": [], "landed_differently": [], "another_way": "", "next_attempt": ""},
    )

    _coach(situation="Invite a friend somewhere you love.")

    assert "Invite a friend somewhere you love." in seen[0]["user"]
    assert TRANSCRIPT in seen[0]["user"]


# --------------------------------------------------------------------------
# Generated reading passages
# --------------------------------------------------------------------------

PASSAGE = (
    "Maya used to open several tabs before she had decided what to finish. "
    "Last month she wrote one task on a card and worked on it for twenty-five "
    "minutes without changing activities. The routine did not make hard work "
    "easy, but it made distraction easier to notice."
)


def _question(index: int, evidence: str) -> dict[str, Any]:
    return {
        "question": f"Question {index}?",
        "options": [f"a{index}", f"b{index}", f"c{index}", f"d{index}"],
        "correct_index": 0,
        "explanation_vi": "Giai thich.",
        "evidence_fragment": evidence,
    }


def test_generated_reading_keeps_a_passage_whose_questions_are_answerable(monkeypatch) -> None:
    generated = becoming_reading._validate_generated(
        {
            "title": "One Task Before Many Tabs",
            "passage": PASSAGE,
            "questions": [_question(i, "she wrote one task on a card") for i in range(1, 5)],
        }
    )

    assert generated is not None
    assert generated["title"] == "One Task Before Many Tabs"
    assert [item["id"] for item in generated["questions"]] == [1, 2, 3, 4]
    assert all(item["evidence_fragment"] in generated["passage"] for item in generated["questions"])


def test_generated_reading_is_rejected_when_evidence_is_not_in_the_passage(monkeypatch) -> None:
    """A question the passage cannot answer is worse than no question at all.

    The learner is told the answer is in the text; if the evidence was never
    there, they will look for something that does not exist.
    """
    questions = [_question(i, "she wrote one task on a card") for i in range(1, 5)]
    questions[2]["evidence_fragment"] = "a sentence the passage does not contain"

    assert becoming_reading._validate_generated(
        {"title": "T", "passage": PASSAGE, "questions": questions}
    ) is None


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda q: q.__setitem__("options", ["a", "b", "c"]), "three options is not four"),
        (lambda q: q.__setitem__("options", ["same", "same", "c", "d"]), "duplicate options"),
        (lambda q: q.__setitem__("correct_index", 9), "an answer outside the options"),
        (lambda q: q.__setitem__("correct_index", None), "no answer at all"),
        (lambda q: q.__setitem__("explanation_vi", "  "), "no explanation"),
        (lambda q: q.__setitem__("question", ""), "no question"),
    ],
)
def test_generated_reading_rejects_unusable_questions(mutate, reason) -> None:
    questions = [_question(i, "she wrote one task on a card") for i in range(1, 5)]
    mutate(questions[1])

    assert becoming_reading._validate_generated(
        {"title": "T", "passage": PASSAGE, "questions": questions}
    ) is None, reason


def test_generated_reading_rejects_a_passage_too_short_to_read() -> None:
    assert becoming_reading._validate_generated(
        {
            "title": "T",
            "passage": "Too short.",
            "questions": [_question(i, "Too short.") for i in range(1, 5)],
        }
    ) is None


def test_built_in_reading_answers_every_language_with_answerable_questions() -> None:
    """The provider-free passage is what most runtimes actually serve."""
    for language in ("en", "zh"):
        fallback = becoming_reading._fallback(language, "B1", "daily_life")
        assert fallback["title"] and len(fallback["passage"]) >= 120
        assert len(fallback["questions"]) == 4
        for question in fallback["questions"]:
            assert question["evidence_fragment"] in fallback["passage"], language
            assert len(question["options"]) == 4
            assert question["correct_index"] in range(4)


# --------------------------------------------------------------------------
# Contextual understanding, the rich case
# --------------------------------------------------------------------------

RICH_EXPLANATION = {
    "summary": "A habitual action, said the way people usually say it.",
    "natural_translation": "Tôi thường đi bộ đến trường.",
    "grammar_notes": ["Adverbs of frequency sit before the main verb.", "  "],
    "vocabulary": [
        {"fragment": "usually", "meaning": "most of the time", "pos": "adverb", "pronunciation": "ˈjuːʒuəli"},
        {"fragment": "", "meaning": "dropped", "pos": "noun", "pronunciation": ""},
    ],
    "usage_note": "Common in everyday speech.",
    "judgement": "natural",
    "judgement_reason": "This is how the frequency adverb is normally placed.",
    "register": "neutral",
    "examples": [{"text": "I usually walk to school.", "note": "Frequency before the verb."}],
    "counter_examples": [
        {
            "text": "I walk usually to school.",
            "note": "Understandable, but not where the adverb normally goes.",
            "judgement": "possible_but_unnatural",
        },
        {
            "text": "Usually I to school walk.",
            "note": "The verb cannot go last in English.",
            "judgement": "grammatically_impossible",
        },
    ],
    "follow_ups": ["When does the adverb go at the end?", ""],
}


def _explain(question: str = "") -> dict[str, Any]:
    return media_interaction.contextual_dictionary(
        media_interaction.ContextualDictionaryIn(
            text="usually",
            context="I usually walk to school.",
            source_language="en",
            target_language="vi",
            question=question,
        )
    )


def test_rich_explanation_keeps_examples_counter_examples_and_their_judgements(monkeypatch) -> None:
    _provider(monkeypatch, dict(RICH_EXPLANATION))

    result = _explain()

    assert result["available"] is True
    # The contextual route restates the claim as its own: an explanation
    # grounded in visible context is a different promise from a free lookup.
    assert result["claim"] == "contextual_dictionary"
    assert result["examples"][0]["text"] == "I usually walk to school."
    # "Wrong" is six different things, and a counter-example is only useful if
    # the learner is told which one it is.
    judgements = [item["judgement"] for item in result["counter_examples"]]
    assert judgements == ["possible_but_unnatural", "grammatically_impossible"]
    assert all(j in media_interaction.USAGE_JUDGEMENTS for j in judgements)
    assert result["judgement"] == "natural"
    assert result["judgement_reason"]


def test_rich_explanation_drops_empty_notes_vocabulary_and_follow_ups(monkeypatch) -> None:
    _provider(monkeypatch, dict(RICH_EXPLANATION))

    result = _explain()

    assert result["grammar_notes"] == ["Adverbs of frequency sit before the main verb."]
    assert [item["fragment"] for item in result["vocabulary"]] == ["usually"]
    assert result["follow_ups"] == ["When does the adverb go at the end?"]


def test_counter_example_judgement_is_normalised_into_the_shared_vocabulary(monkeypatch) -> None:
    payload = dict(RICH_EXPLANATION)
    payload["counter_examples"] = [
        {"text": "I walk usually to school.", "note": "n", "judgement": "sounds_a_bit_odd"}
    ]
    payload["judgement"] = "also_not_real"
    _provider(monkeypatch, payload)

    result = _explain()

    assert result["counter_examples"][0]["judgement"] in media_interaction.USAGE_JUDGEMENTS
    assert result["judgement"] in media_interaction.USAGE_JUDGEMENTS


def test_a_follow_up_question_travels_with_its_selection_and_context(monkeypatch) -> None:
    seen = _provider(monkeypatch, dict(RICH_EXPLANATION))

    result = _explain(question="Why is it said this way?")

    user = seen[0]["user"]
    assert "Why is it said this way?" in user
    assert "usually" in user and "I usually walk to school." in user
    # Going deeper must not cost the learner the thing they were looking at.
    assert result["question"] == "Why is it said this way?"
    assert result["selected_text"] == "usually"


def test_explanation_prompt_refuses_authority_it_was_not_given(monkeypatch) -> None:
    seen = _provider(monkeypatch, dict(RICH_EXPLANATION))

    _explain()

    assert "explain from the language itself instead" in seen[0]["system"]


def _say_again_payload(say_again: str) -> dict[str, Any]:
    return {"carried": [], "landed_differently": [{"quote": "very interesting for me", "why": "x", "instead": "really interesting to me", "judgement": "unnatural"}], "another_way": "Bạn có thể nói ...", "next_attempt": "y", "say_again": say_again}


def test_spoken_coaching_offers_one_line_to_say_again_in_the_learning_language(monkeypatch) -> None:
    # The Speaking design's "say this again" is a line the learner can say, in the language they
    # are learning - not advice in the support language (measured on real Gemini, 2026-09-23).
    seen = _provider(monkeypatch, _say_again_payload("I would take you to the old market by the river."))
    result = _coach()
    assert result["say_again"] == "I would take you to the old market by the river."
    assert "say_again" in seen[0]["schema"]["properties"]
    assert "say_again" in seen[0]["schema"]["required"]


@pytest.mark.parametrize("bad", ["Bạn có thể nói: I would go.", "你可以说：I would go.", "", "x" * 400])
def test_a_line_to_say_again_that_is_not_the_learning_language_is_dropped(monkeypatch, bad) -> None:
    _provider(monkeypatch, _say_again_payload(bad))
    assert _coach()["say_again"] == ""


def test_a_chinese_line_to_say_again_must_be_chinese(monkeypatch) -> None:
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "zh")
    payload = {"carried": [], "landed_differently": [], "another_way": "", "next_attempt": "", "say_again": "其实我是英国人。"}
    _provider(monkeypatch, payload)
    zh = media_interaction.coach_spoken_response(media_interaction.SpokenResponseIn(transcript="不是，我是英国人。", source_language="zh", target_language="vi", situation=""))
    assert zh["say_again"] == "其实我是英国人。"
    _provider(monkeypatch, {**payload, "say_again": "Instead of 不是, say 其实我是英国人."})
    zh = media_interaction.coach_spoken_response(media_interaction.SpokenResponseIn(transcript="不是，我是英国人。", source_language="zh", target_language="vi", situation=""))
    assert zh["say_again"] == ""
