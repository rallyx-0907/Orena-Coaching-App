"""Curated meaning: resolution order, caching, and provider spend.

The rule these protect is a cost rule as much as a product rule. Calling a paid
translation provider every time a learner opens a lesson would be indefensible,
so the second learner in a given support language must cost nothing, and a
reviewed human translation must never be replaced by machine output.
"""

from __future__ import annotations

from dataclasses import dataclass

from writing_coach.media_meaning import (
    PROVENANCE_CACHED_GENERATED,
    PROVENANCE_EDITORIAL,
    PROVENANCE_GENERATED,
    cache_key,
    pinyin_for_segments,
    resolve_segment_meanings,
)


@dataclass(frozen=True)
class Segment:
    segment_id: str
    original_text: str


@dataclass(frozen=True)
class Preauthored:
    segment_id: str
    target_language: str
    translated_meaning: str


class MemoryCache:
    """The persisted cache's contract, without a database in the test."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, str]] = {}
        self.reads = 0
        self.writes = 0

    def get_media_translation(self, key: str):
        self.reads += 1
        return self.rows.get(key)

    def put_media_translation(self, key, translated_text, provenance, generated_at):
        self.writes += 1
        self.rows[key] = {"translated_text": translated_text, "provenance": provenance}


class CountingTranslator:
    def __init__(self, answer: str = "translated", fail: bool = False) -> None:
        self.calls = 0
        self.segments_seen: list[str] = []
        self.answer = answer
        self.fail = fail

    def __call__(self, segments, target_language):
        self.calls += 1
        self.segments_seen.extend(s.segment_id for s in segments)
        if self.fail:
            return {}
        return {s.segment_id: f"{self.answer}:{target_language}:{s.segment_id}" for s in segments}


SEGMENTS = (Segment("a:000", "Where are you going?"), Segment("a:001", "I am going home."))


def _resolve(**over):
    base = dict(
        asset_id="asset-1", segments=SEGMENTS, support_language="ja",
        source_language="en", preauthored=(), cache=None, translate=None,
        provider_model="Groq:model-1",
    )
    base.update(over)
    return resolve_segment_meanings(**base)


# --- A: a reviewed translation is used and never overridden ------------------

def test_preauthored_translation_wins_and_costs_nothing() -> None:
    translator = CountingTranslator()
    outcome = _resolve(
        support_language="vi",
        preauthored=(
            Preauthored("a:000", "vi", "Bạn đi đâu vậy?"),
            Preauthored("a:001", "vi", "Tôi đang về nhà."),
        ),
        translate=translator,
    )
    assert outcome.status == "ready"
    assert outcome.provider_calls == 0, "a human translation must not be re-generated"
    assert translator.calls == 0
    assert {m.provenance for m in outcome.meanings} == {PROVENANCE_EDITORIAL}
    assert outcome.meanings[0].translated_meaning == "Bạn đi đâu vậy?"


# --- B and C: generate once, then reuse --------------------------------------

def test_missing_language_translates_once_then_reuses_the_cache() -> None:
    cache = MemoryCache()
    translator = CountingTranslator()

    first = _resolve(cache=cache, translate=translator)
    assert first.status == "ready"
    assert first.provider_calls == 1, "the first learner pays for translation"
    assert translator.calls == 1
    assert cache.writes == len(SEGMENTS)
    assert {m.provenance for m in first.meanings} == {PROVENANCE_GENERATED}

    second = _resolve(cache=cache, translate=translator)
    assert second.provider_calls == 0, "the second learner must cost no quota"
    assert translator.calls == 1, "the provider must not be called again"
    assert {m.provenance for m in second.meanings} == {PROVENANCE_CACHED_GENERATED}
    assert [m.translated_meaning for m in second.meanings] == \
           [m.translated_meaning for m in first.meanings]


def test_a_second_language_is_cached_separately() -> None:
    """D: ja and es are different answers, neither evicting the other."""

    cache = MemoryCache()
    translator = CountingTranslator()

    _resolve(cache=cache, translate=translator, support_language="ja")
    _resolve(cache=cache, translate=translator, support_language="es")
    assert translator.calls == 2

    # Both remain served from cache afterwards.
    ja = _resolve(cache=cache, translate=translator, support_language="ja")
    es = _resolve(cache=cache, translate=translator, support_language="es")
    assert translator.calls == 2, "neither language re-translated"
    assert ja.meanings[0].translated_meaning != es.meanings[0].translated_meaning
    assert ja.meanings[0].target_language == "ja"
    assert es.meanings[0].target_language == "es"


def test_only_the_missing_segments_are_sent_to_the_provider() -> None:
    """Bounded batching: a partly cached lesson does not re-translate whole."""

    cache = MemoryCache()
    translator = CountingTranslator()
    _resolve(cache=cache, translate=translator, segments=SEGMENTS[:1])
    translator.segments_seen.clear()

    _resolve(cache=cache, translate=translator, segments=SEGMENTS)
    assert translator.segments_seen == ["a:001"], "the cached segment must not be resent"


# --- E: a canonical text change must not serve a stale meaning ---------------

def test_changed_source_text_invalidates_its_meaning() -> None:
    cache = MemoryCache()
    translator = CountingTranslator()
    _resolve(cache=cache, translate=translator)
    assert translator.calls == 1

    edited = (Segment("a:000", "Where are you going now?"), SEGMENTS[1])
    outcome = _resolve(cache=cache, translate=translator, segments=edited)
    assert translator.calls == 2, "edited canonical text must miss the cache"
    assert outcome.meanings[0].provenance == PROVENANCE_GENERATED

    # And the identity really is what changed.
    before = cache_key("asset-1", "a:000", "Where are you going?", "ja", "Groq:model-1")
    after = cache_key("asset-1", "a:000", "Where are you going now?", "ja", "Groq:model-1")
    assert before != after
    # A provider or model change also misses rather than serving another engine's text.
    assert cache_key("asset-1", "a:000", "x", "ja", "Groq:model-1") != \
           cache_key("asset-1", "a:000", "x", "ja", "Groq:model-2")


# --- F: a translation failure must not cost the learner the transcript -------

def test_translation_failure_leaves_the_transcript_usable() -> None:
    cache = MemoryCache()
    failing = CountingTranslator(fail=True)
    outcome = _resolve(cache=cache, translate=failing)

    assert outcome.status == "unavailable"
    assert outcome.failure_kind == "translation_failed"
    assert cache.writes == 0, "a failure must not be cached as if it were an answer"
    # Nothing was fabricated to fill the gap.
    assert outcome.meanings == ()


def test_meaning_is_not_required_when_support_matches_the_source() -> None:
    outcome = _resolve(support_language="en", source_language="en")
    assert outcome.status == "not_required"
    assert outcome.provider_calls == 0


def test_no_provider_means_truthful_unavailable_not_a_guess() -> None:
    outcome = _resolve(cache=MemoryCache(), translate=None)
    assert outcome.status == "unavailable"
    assert outcome.meanings == ()


def test_partial_translation_is_preserved_and_only_missing_lines_are_retried() -> None:
    cache = MemoryCache()
    first = _resolve(cache=cache, translate=lambda segments, target: {segments[0].segment_id: "first meaning"})
    assert first.status == "unavailable"
    assert first.failure_kind == "translation_incomplete"
    assert len(first.meanings) == 1
    seen = []

    def finish(segments, target):
        seen.extend(segment.segment_id for segment in segments)
        return {segment.segment_id: "remaining meaning" for segment in segments}

    second = _resolve(cache=cache, translate=finish)
    assert second.status == "ready"
    assert seen == [SEGMENTS[1].segment_id]
    assert second.meanings[0].translated_meaning == "first meaning"


# --- L: Chinese Pinyin -------------------------------------------------------

def test_pinyin_is_a_reading_of_the_hanzi_not_a_translation() -> None:
    segments = (Segment("z:000", "我今天有点累。"), Segment("z:001", "你去哪儿？"))
    readings = pinyin_for_segments(segments)

    assert readings["z:000"].startswith("wǒ jīn tiān") or "jīn" in readings["z:000"]
    assert "lèi" in readings["z:000"]
    assert "nǎ" in readings["z:001"] or "qù" in readings["z:001"]

    # It does not vary with the support language: the same Hanzi, the same reading.
    assert pinyin_for_segments(segments) == readings

    # Non-Chinese text yields nothing rather than echoing the line back as if
    # it were a reading.
    assert pinyin_for_segments((Segment("e:000", "Hello there"),)) == {}
