# ruff: noqa: F811
"""Translate ahead when a Reading article opens (D-199): fakes only, no network, no key, no live call."""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_ai_router import GEMMA, STANDBY, config, env, http_error  # noqa: F401 - `env` is a fixture
from writing_coach import reading_articles_api as articles_api
from writing_coach import reading_prefetch
from writing_coach.ai.router import tap
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_prefetch import Prefetcher, plan_words
from writing_coach.reading_translation import ReadingTranslationService
from writing_coach.word_detail import project_word_detail

EN_BODY = (
    "The lantern flickered above the harbour. Fishermen repaired their nets while stormy weather approached. "
    "Nobody expected the lighthouse keeper to announce the evacuation. NASA said 2024 would bring turbulence. "
    "It's a long-standing tradition, and they don't forget it."
)
ZH_BODY = "政府宣布了新的经济政策。企业需要调整战略。北京是首都。"


class _Engine:
    engine_id = "ai"
    model_version = "x"

    def translate_batch(self, *_a, **_k):
        raise AssertionError("the paid reading engine must not be used")


class _Catalogue:
    """A vocabulary repository stub: `entries` maps (language, term) to a short meaning in Vietnamese."""

    def __init__(self, entries=None):
        self.entries = entries or {}

    def find_entry(self, language, term):
        text = self.entries.get((language, term))
        if text is None:
            return None
        return {"term": term, "short_meanings": [{"language": "vi", "text": text}]}


class Inline:
    """An executor that runs the job on submit, on the calling thread."""

    def submit(self, fn, *args):
        fn(*args)
        future: Future = Future()
        future.set_result(None)
        return future


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    tap.reset_state()
    yield
    tap.reset_state()


def lookup_service(catalogue=None, budget=2.0):
    return ReadingLookupService(
        catalogue, lambda _w: {"phonetic": ""}, ReadingTranslationService(_Engine(), cache=DerivedCache()),
        budget_seconds=budget, word_translation=tap.word_translation_seam,
        word_translation_prefetch=tap.word_translation_prefetch,
    )


class Counts(dict):
    def __call__(self, name, amount=1):
        self[name] = self.get(name, 0) + amount


def make_prefetcher(service, counts=None, executor=None, **kw):
    counts = counts if counts is not None else Counts()
    return Prefetcher(
        service.prefetch_meaning, enabled=tap.prefetch_enabled, paused=tap.prefetch_paused, count=counts,
        executor=executor or Inline(), **kw,
    ), counts


def sent_words(env):
    import json

    return [json.loads(call["messages"][-1]["content"])["text"] for call in env.fake.calls]


# --- which words ---------------------------------------------------------------------------------------------------


def test_the_english_plan_skips_names_acronyms_numbers_contractions_compounds_and_common_words() -> None:
    words = plan_words(EN_BODY, "en")
    assert "lantern" in words and "harbour" in words and "lighthouse" in words and "evacuation" in words
    for skipped in ("NASA", "The", "It's", "long-standing", "their", "2024", "they"):
        assert skipped not in words
    assert len(words) == len({word.casefold() for word in words})  # once each
    assert all(len(word) >= reading_prefetch.MIN_EN_LETTERS for word in words)
    # rarer (longer) first, then order of appearance
    assert words.index("evacuation") < words.index("lantern")


def test_the_plan_is_capped_and_word_only() -> None:
    body = " ".join(f"{chr(97 + i % 26)}{chr(97 + i // 26)}word{chr(97 + i % 7)}qq" for i in range(200)) + "."
    assert len(plan_words(body, "en")) == reading_prefetch.MAX_WORDS_PER_ARTICLE
    assert plan_words(body, "en", limit=5).__len__() == 5
    assert plan_words(EN_BODY, "ja") == []


def test_the_chinese_plan_keeps_content_words_of_two_or_more_characters(monkeypatch) -> None:
    tokens = [
        ("政府", "noun"), ("宣布", "verb"), ("了", "particle"), ("新", "adjective"), ("经济", "noun"),
        ("北京", "proper_noun"), ("政策", "noun"), ("政府", "noun"), ("2024", "numeral"), ("的", "particle"),
    ]
    monkeypatch.setattr(
        reading_prefetch, "_zh_tokens", lambda chunk: [{"fragment": f, "pos": p} for f, p in tokens]
    )
    assert plan_words(ZH_BODY, "zh") == ["政府", "宣布", "经济", "政策"]


# --- the prefetch itself -------------------------------------------------------------------------------------------


def test_opening_an_article_prefetches_only_the_deterministic_misses_and_the_first_tap_is_a_cache_hit(env) -> None:
    env.fake.default[GEMMA] = {"meaning": "đèn lồng"}
    service = lookup_service(_Catalogue({("en", "harbour"): "bến cảng"}))
    prefetcher, counts = make_prefetcher(service)
    assert prefetcher.schedule("a1", 3, EN_BODY, "en", "vi") == "scheduled"
    asked = sent_words(env)
    assert "harbour" not in asked and "lantern" in asked  # the catalogue answers harbour: AI never sees it
    assert counts["prefetch_skipped"] >= 1 and counts["prefetch_served"] == len(asked)
    assert counts["prefetch_requested"] == len(asked) and counts["prefetch_articles"] == 1
    # The first tap on a prefetched word: served from the cache, labelled word_translation, no new call.
    before = len(env.fake.calls)
    result = service.lookup("lantern", "The lantern flickered above the harbour.", "en", "vi")
    assert [(m.text, m.source) for m in result.meanings] == [("đèn lồng", "word_translation")]
    assert len(env.fake.calls) == before
    detail = project_word_detail(
        selection="lantern", context="The lantern flickered.", language="en", lookup=result.to_dict(),
        explanation=None, saved=False,
    )
    assert detail["meaningSource"] == "word_translation" and detail["contextMeaning"] == "đèn lồng"
    assert detail["meaningLanguage"] == "vi"


def test_the_prefetch_sends_the_word_only_and_charges_no_learner_brake(env, monkeypatch) -> None:
    monkeypatch.setattr(tap, "BRAKE_LIMIT", 1)
    service = lookup_service()
    prefetcher, _ = make_prefetcher(service)
    prefetcher.schedule("a1", 1, EN_BODY, "en", "vi")
    assert len(env.fake.calls) > 1  # more than one call, and the learner's brake (limit 1) was never touched
    import json

    for call in env.fake.calls:
        body = json.loads(call["messages"][-1]["content"])
        assert set(body) == {"text", "source_language", "target_language"} and " " not in body["text"]
    assert tap.word_translation_seam("zzyzx", "", [], "en", "vi") == "đèn"  # the learner's own allowance is intact


def test_at_most_forty_words_are_asked_per_article(env) -> None:
    body = " ".join(f"{chr(97 + i % 26)}{chr(97 + i // 26)}word{chr(97 + i % 7)}qq" for i in range(90)) + "."
    env.fake.default[GEMMA] = {"meaning": "từ"}
    service = lookup_service()
    prefetcher, counts = make_prefetcher(service)
    prefetcher.schedule("a2", 1, body, "en", "vi")
    assert len(env.fake.calls) == reading_prefetch.MAX_WORDS_PER_ARTICLE == counts["prefetch_requested"]


def test_a_provider_outage_stops_the_batch_and_pauses_every_article(env) -> None:
    env.fake.script = {GEMMA: [http_error(429)] * 50, STANDBY: [http_error(429)] * 50}
    service = lookup_service()
    prefetcher, counts = make_prefetcher(service)
    assert prefetcher.schedule("a3", 1, EN_BODY, "en", "vi") == "scheduled"
    calls = len(env.fake.calls)
    assert 1 <= calls <= 4  # the pool's attempts for the first word only, then nothing more (the batch has ~10 words)
    assert counts["prefetch_failed"] == 1 and counts["prefetch_skipped"] >= 1
    assert tap.prefetch_paused()
    assert prefetcher.schedule("a4", 1, EN_BODY, "en", "vi") == "paused"
    assert prefetcher.schedule("a3", 1, EN_BODY, "en", "vi") == "paused"  # the stopped batch left no marker
    assert len(env.fake.calls) == calls
    env.clock.now += tap.PREFETCH_PAUSE_SECONDS + 1
    assert not tap.prefetch_paused()


def test_one_word_nobody_can_answer_validly_does_not_pause_the_batch(env) -> None:
    bad = {"meaning": "灯笼"}  # the wrong script for Vietnamese: refused by the validator on every pool entry
    env.fake.script = {GEMMA: [bad] * 2, STANDBY: [bad] * 2}
    prefetcher, counts = make_prefetcher(lookup_service())
    prefetcher.schedule("a3b", 1, EN_BODY, "en", "vi")
    assert not tap.prefetch_paused()
    assert counts["prefetch_failed"] == 1 and counts["prefetch_served"] >= 3


def test_the_daily_budget_is_a_global_cap_on_router_calls(env, monkeypatch) -> None:
    monkeypatch.setattr(tap, "PREFETCH_DAILY_CALLS", 3)
    service = lookup_service()
    prefetcher, counts = make_prefetcher(service)
    prefetcher.schedule("a5", 1, EN_BODY, "en", "vi")
    assert len(env.fake.calls) == 3
    assert counts["prefetch_failed"] == 1  # the refusal that stopped the batch


def test_a_second_open_of_the_same_article_is_a_no_op_until_the_marker_expires(env) -> None:
    clock = [0.0]
    service = lookup_service()
    prefetcher, _ = make_prefetcher(service, clock=lambda: clock[0])
    assert prefetcher.schedule("a6", 1, EN_BODY, "en", "vi") == "scheduled"
    calls = len(env.fake.calls)
    assert prefetcher.schedule("a6", 1, EN_BODY, "en", "vi") == "already"
    assert prefetcher.schedule("a6", 2, EN_BODY, "en", "vi") == "scheduled"  # a new revision is new work (all cached)
    assert len(env.fake.calls) == calls  # the second run found every answer in the router's cache
    clock[0] += reading_prefetch.MARKER_TTL_SECONDS + 1
    assert prefetcher.schedule("a6", 1, EN_BODY, "en", "vi") == "scheduled"


def test_a_disabled_or_unconfigured_capability_calls_nobody(env) -> None:
    service = lookup_service()
    prefetcher, counts = make_prefetcher(service)
    env.repo.config = config(enabled=False)
    assert prefetcher.schedule("a7", 1, EN_BODY, "en", "vi") == "disabled"
    env.repo.config = None
    assert prefetcher.schedule("a7", 1, EN_BODY, "en", "vi") == "disabled"
    assert env.fake.calls == [] and counts == {}


def test_a_capability_turned_off_mid_batch_stops_the_batch(env) -> None:
    service = lookup_service()

    def switch_off(_kwargs):
        env.repo.config = config(enabled=False)

    env.fake.on_call = switch_off
    prefetcher, _ = make_prefetcher(service)
    prefetcher.schedule("a8", 1, EN_BODY, "en", "vi")
    assert len(env.fake.calls) == 1


def test_unsupported_languages_and_equal_languages_are_not_scheduled(env) -> None:
    prefetcher, _ = make_prefetcher(lookup_service())
    assert prefetcher.schedule("a9", 1, EN_BODY, "ja", "vi") == "unsupported"
    assert prefetcher.schedule("a9", 1, EN_BODY, "en", "en") == "unsupported"
    assert prefetcher.schedule("a9", 1, "", "en", "vi") == "unsupported"
    assert env.fake.calls == []


def test_the_waiting_queue_is_bounded(env) -> None:
    release = threading.Event()
    blocker = lambda *a: release.wait(5)  # noqa: E731
    pool = ThreadPoolExecutor(max_workers=1)
    pool.submit(blocker)  # the pool's only worker is busy: every job queues
    prefetcher, _ = make_prefetcher(lookup_service(), executor=pool)
    outcomes = [prefetcher.schedule(f"q{i}", 1, EN_BODY, "en", "vi") for i in range(reading_prefetch.MAX_QUEUED_ARTICLES + 3)]
    assert outcomes.count("scheduled") == reading_prefetch.MAX_QUEUED_ARTICLES and outcomes[-1] == "queue_full"
    release.set()
    pool.shutdown(wait=True, cancel_futures=True)


# --- a tap that meets a prefetch in flight --------------------------------------------------------------------------


def test_a_tap_during_the_prefetch_of_its_word_joins_it_and_asks_nobody_again(env) -> None:
    entered, release = threading.Event(), threading.Event()

    def slow(_kwargs):
        entered.set()
        release.wait(5)

    env.fake.on_call = slow
    service = lookup_service(budget=3.0)
    runner = threading.Thread(target=lambda: service.prefetch_meaning("lantern", "en", "vi"))
    runner.start()
    assert entered.wait(5)
    tapped: list = []
    tapper = threading.Thread(target=lambda: tapped.append(service.lookup("lantern", "A lantern.", "en", "vi")))
    tapper.start()
    time.sleep(0.2)
    release.set()
    runner.join(5)
    tapper.join(5)
    assert [(m.text, m.source) for m in tapped[0].meanings] == [("đèn", "word_translation")]
    assert len(env.fake.calls) == 1


def test_a_tap_timing_out_never_cancels_the_prefetch_it_joined(env) -> None:
    entered, release = threading.Event(), threading.Event()

    def slow(_kwargs):
        entered.set()
        release.wait(5)

    env.fake.on_call = slow
    service = lookup_service(budget=0.3)
    runner = threading.Thread(target=lambda: service.prefetch_meaning("lantern", "en", "vi"))
    runner.start()
    assert entered.wait(5)
    assert service.lookup("lantern", "A lantern.", "en", "vi").meanings == ()  # a miss within its budget
    release.set()
    runner.join(5)
    assert service.lookup("lantern", "A lantern.", "en", "vi").meanings[0].source == "word_translation"
    assert len(env.fake.calls) == 1


# --- EN / ZH parity --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "language", "target", "word", "answer"),
    [
        (EN_BODY, "en", "vi", "lantern", "đèn lồng"),
        (EN_BODY, "en", "zh", "lantern", "灯笼"),
        (ZH_BODY, "zh", "vi", "政府", "chính phủ"),
    ],
)
def test_english_and_chinese_articles_are_translated_ahead_the_same_way(env, monkeypatch, body, language, target, word, answer) -> None:
    monkeypatch.setattr(reading_prefetch, "_zh_tokens", lambda chunk: [{"fragment": "政府", "pos": "noun"}])
    env.fake.default[GEMMA] = {"meaning": answer}
    service = lookup_service()
    monkeypatch.setattr(service, "has_local_meaning", lambda *_a: False)  # CC-CEDICT is not what this test is about
    prefetcher, counts = make_prefetcher(service)
    assert prefetcher.schedule("p1", 1, body, language, target) == "scheduled"
    assert counts["prefetch_served"] >= 1
    before = len(env.fake.calls)
    result = service.lookup(word, "", language, target)
    assert [(m.text, m.source) for m in result.meanings] == [(answer, "word_translation")]
    assert len(env.fake.calls) == before


def test_chinese_words_cc_cedict_answers_for_an_english_support_language_are_skipped(env, monkeypatch) -> None:
    monkeypatch.setattr(reading_prefetch, "_zh_tokens", lambda chunk: [{"fragment": "政府", "pos": "noun"}])
    from writing_coach import reading_lookup

    monkeypatch.setattr(reading_lookup, "_safe_chinese_senses", lambda word: ("government",))
    prefetcher, counts = make_prefetcher(lookup_service())
    prefetcher.schedule("p2", 1, ZH_BODY, "zh", "en")
    assert env.fake.calls == [] and counts["prefetch_skipped"] == 1


# --- the open hook ---------------------------------------------------------------------------------------------------


class _Repo:
    def get_published_article(self, article_id):
        return {"id": article_id, "body": EN_BODY, "language": "en", "content_revision": 7, "image": None}


def _client(on_open):
    articles_api.configure_reading_articles(_Repo(), on_open=on_open)
    app = FastAPI()
    app.include_router(articles_api.router)
    return TestClient(app)


def test_opening_an_article_hands_it_to_the_hook_and_a_failing_hook_never_breaks_the_response() -> None:
    seen: list = []
    try:
        client = _client(seen.append)
        first = client.get("/api/reading/articles/abc")
        assert first.status_code == 200 and seen[0]["id"] == "abc" and seen[0]["content_revision"] == 7
        again = client.get("/api/reading/articles/abc", headers={"if-none-match": first.headers["etag"]})
        assert again.status_code == 304 and len(seen) == 2  # a revalidation is an open too

        def broken(_article):
            raise RuntimeError("boom")

        assert _client(broken).get("/api/reading/articles/abc").status_code == 200
    finally:
        articles_api.configure_reading_articles(None)


def test_the_hook_does_not_wait_for_the_prefetch(env) -> None:
    release = threading.Event()
    env.fake.on_call = lambda _k: release.wait(5)
    service = lookup_service()
    prefetcher, _ = make_prefetcher(service, executor=ThreadPoolExecutor(max_workers=1))
    started = time.monotonic()
    assert prefetcher.schedule("h1", 1, EN_BODY, "en", "vi") == "scheduled"
    assert time.monotonic() - started < 1.0
    release.set()
