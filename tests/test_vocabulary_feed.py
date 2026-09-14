"""Task C: the Daily Feed candidate/selection foundation.

Covers exclusion, count, same-context/date determinism, different learner
keys being allowed to differ, level/framework narrowing with non-starvation
fallback, EN/ZH candidate production, and the candidate-card absence of
``memory``/``source_encounters``.
"""

from __future__ import annotations

from datetime import date

from writing_coach.vocabulary_feed import (
    LearnerFeedContext,
    daily_feed_candidates,
    vocabulary_card_from_feed_candidate,
)
from writing_coach.vocabulary_library import all_vocabulary_entries, normalize_vocabulary_word

_ON_DATE = date(2026, 9, 14)


def _context(**overrides: object) -> LearnerFeedContext:
    fields: dict[str, object] = {"learner_key": "sandbox-learner-1"}
    fields.update(overrides)
    return LearnerFeedContext(**fields)


# --- Exclusion ---------------------------------------------------------------


def test_excludes_normalized_words_already_saved() -> None:
    pool = all_vocabulary_entries("en")
    excluded_word = pool[0]["normalized_word"]
    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(),
        exclude_normalized={excluded_word},
        count=len(pool),
        on_date=_ON_DATE,
    )
    assert excluded_word not in {entry["normalized_word"] for entry in candidates}
    assert len(candidates) == len(pool) - 1


def test_exclude_normalized_is_itself_normalized_before_matching() -> None:
    candidates = daily_feed_candidates(
        "zh",
        learner_context=_context(),
        exclude_normalized={"  你好 "},
        count=100,
        on_date=_ON_DATE,
    )
    assert "你好" not in {entry["normalized_word"] for entry in candidates}


# --- Count -------------------------------------------------------------------


def test_returns_at_most_count_candidates() -> None:
    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(),
        exclude_normalized=set(),
        count=5,
        on_date=_ON_DATE,
    )
    assert len(candidates) == 5


def test_count_larger_than_pool_returns_whole_pool_without_error() -> None:
    pool = all_vocabulary_entries("zh")
    candidates = daily_feed_candidates(
        "zh",
        learner_context=_context(),
        exclude_normalized=set(),
        count=len(pool) + 50,
        on_date=_ON_DATE,
    )
    assert len(candidates) == len(pool)


# --- Determinism ---------------------------------------------------------


def test_same_learner_language_and_date_returns_identical_order() -> None:
    kwargs = dict(
        learner_context=_context(),
        exclude_normalized=set(),
        count=10,
        on_date=_ON_DATE,
    )
    first = daily_feed_candidates("en", **kwargs)
    second = daily_feed_candidates("en", **kwargs)
    assert [entry["normalized_word"] for entry in first] == [
        entry["normalized_word"] for entry in second
    ]


def test_different_date_may_change_order_but_stays_deterministic_per_date() -> None:
    kwargs = dict(learner_context=_context(), exclude_normalized=set(), count=10)
    day_one = daily_feed_candidates("en", on_date=_ON_DATE, **kwargs)
    day_one_again = daily_feed_candidates("en", on_date=_ON_DATE, **kwargs)
    day_two = daily_feed_candidates("en", on_date=date(2026, 9, 15), **kwargs)
    assert [e["normalized_word"] for e in day_one] == [e["normalized_word"] for e in day_one_again]
    assert [e["normalized_word"] for e in day_one] != [e["normalized_word"] for e in day_two]


def test_different_learner_keys_are_allowed_to_produce_a_different_order() -> None:
    kwargs = dict(exclude_normalized=set(), count=10, on_date=_ON_DATE)
    learner_a = daily_feed_candidates(
        "en", learner_context=_context(learner_key="learner-a"), **kwargs
    )
    learner_b = daily_feed_candidates(
        "en", learner_context=_context(learner_key="learner-b"), **kwargs
    )
    assert [e["normalized_word"] for e in learner_a] != [
        e["normalized_word"] for e in learner_b
    ]


def test_selector_is_not_secretly_keyed_on_date_alone() -> None:
    # Same date, same language, same everything else except learner_key: if
    # the selector silently ignored learner_key, these two calls would always
    # match. They must not, proving learner_key genuinely participates in the
    # ordering hash rather than being accepted and discarded.
    kwargs = dict(exclude_normalized=set(), count=len(all_vocabulary_entries("zh")), on_date=_ON_DATE)
    learner_a = daily_feed_candidates(
        "zh", learner_context=_context(learner_key="alpha-learner"), **kwargs
    )
    learner_b = daily_feed_candidates(
        "zh", learner_context=_context(learner_key="zzz-different-learner"), **kwargs
    )
    assert [e["normalized_word"] for e in learner_a] != [
        e["normalized_word"] for e in learner_b
    ]


# --- Level/framework narrowing and non-starvation fallback -------------------


def test_target_level_narrows_the_pool_when_entries_match() -> None:
    full_pool = all_vocabulary_entries("zh")
    hsk1_words = {
        entry["normalized_word"] for entry in full_pool if entry["level"] == "HSK1"
    }
    assert hsk1_words and len(hsk1_words) < len(full_pool)

    candidates = daily_feed_candidates(
        "zh",
        learner_context=_context(target_level="HSK1"),
        exclude_normalized=set(),
        count=len(full_pool),
        on_date=_ON_DATE,
    )
    returned_words = {entry["normalized_word"] for entry in candidates}
    assert returned_words <= hsk1_words
    assert all(entry["level"] == "HSK1" for entry in candidates)
    assert len(candidates) < len(full_pool)


def test_target_level_matching_nothing_falls_back_to_full_pool() -> None:
    full_pool = all_vocabulary_entries("en")
    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(target_level="no-such-level"),
        exclude_normalized=set(),
        count=len(full_pool) + 10,
        on_date=_ON_DATE,
    )
    assert candidates
    assert len(candidates) == len(full_pool)


def test_framework_filter_narrows_independently_of_level() -> None:
    full_pool = all_vocabulary_entries("en")
    toeic_words = {
        entry["normalized_word"] for entry in full_pool if entry["framework"] == "toeic"
    }
    assert toeic_words and len(toeic_words) < len(full_pool)

    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(framework="toeic"),
        exclude_normalized=set(),
        count=len(full_pool),
        on_date=_ON_DATE,
    )
    assert {entry["normalized_word"] for entry in candidates} <= toeic_words
    assert all(entry["framework"] == "toeic" for entry in candidates)


# --- EN/ZH parity --------------------------------------------------------


def test_produces_valid_english_candidates() -> None:
    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(),
        exclude_normalized=set(),
        count=5,
        on_date=_ON_DATE,
    )
    assert len(candidates) == 5
    assert all(entry["language_code"] == "en" for entry in candidates)


def test_produces_valid_chinese_candidates() -> None:
    candidates = daily_feed_candidates(
        "zh",
        learner_context=_context(),
        exclude_normalized=set(),
        count=5,
        on_date=_ON_DATE,
    )
    assert len(candidates) == 5
    assert all(entry["language_code"] == "zh" for entry in candidates)


def test_unknown_language_returns_no_candidates() -> None:
    candidates = daily_feed_candidates(
        "fr",
        learner_context=_context(),
        exclude_normalized=set(),
        count=5,
        on_date=_ON_DATE,
    )
    assert candidates == []


# --- Candidate card shape -----------------------------------------------------


def test_feed_candidate_card_has_no_memory_or_source_encounters_fields() -> None:
    candidates = daily_feed_candidates(
        "zh",
        learner_context=_context(),
        exclude_normalized=set(),
        count=1,
        on_date=_ON_DATE,
    )
    card = vocabulary_card_from_feed_candidate(candidates[0])
    assert "memory" not in card
    assert "source_encounters" not in card


def test_feed_candidate_card_projects_orthography_for_zh_when_available() -> None:
    # Task G: the Daily Feed candidate card projects the same Chinese
    # stroke-order capability the saved-word and catalog-collection cards do,
    # for ZH candidates the vendored pack actually covers.
    candidates = daily_feed_candidates(
        "zh",
        learner_context=_context(),
        exclude_normalized=set(),
        count=1,
        on_date=_ON_DATE,
    )
    card = vocabulary_card_from_feed_candidate(candidates[0])
    assert card["orthography"]["script"] == "han"
    assert card["orthography"]["source"] == "make-me-a-hanzi"
    assert [entry["character"] for entry in card["orthography"]["characters"]] == list(
        candidates[0]["word"]
    )


def test_feed_candidate_card_omits_orthography_key_for_en() -> None:
    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(),
        exclude_normalized=set(),
        count=1,
        on_date=_ON_DATE,
    )
    card = vocabulary_card_from_feed_candidate(candidates[0])
    assert "orthography" not in card


def test_feed_candidate_card_matches_direct_catalog_projection() -> None:
    from writing_coach.vocabulary_cards import vocabulary_card_from_catalog_entry

    candidates = daily_feed_candidates(
        "en",
        learner_context=_context(),
        exclude_normalized=set(),
        count=1,
        on_date=_ON_DATE,
    )
    entry = candidates[0]
    assert vocabulary_card_from_feed_candidate(entry) == vocabulary_card_from_catalog_entry(entry)


def test_normalize_vocabulary_word_helper_used_for_exclusion_matches_library() -> None:
    # Sanity: the exclusion set's normalization must line up with the
    # catalog's own normalization, or exclusion could silently no-op.
    assert normalize_vocabulary_word("  Client ") == "client"
