# ruff: noqa: F811
"""The word tap's last layer: the router behind the `word_translation` seam (D-195).

AI is reached from a word tap only through `word_translation`, only on a deterministic miss, only when the capability
is enabled; it is sent the word and never the sentence; a slow answer is finished in the background; a learner over
the per-account brake gets the deterministic answer, never an error.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from tests.test_ai_router import GEMMA, STANDBY, Fake, Repository, config, env, http_error  # noqa: F401 - `env` is a fixture
from writing_coach.ai.router import tap
from writing_coach.core.request_context import USER_KEY_CTX
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService

SENTENCE = "The lamp ran out of oil, so we sat in the dark for hours."


@pytest.fixture(autouse=True)
def fresh_tap(monkeypatch):
    tap.reset_state()
    yield
    tap.reset_state()


def test_a_miss_is_answered_with_the_meaning_and_the_word_only(env) -> None:
    answer = tap.word_translation_seam("lamp", SENTENCE, ["a device that gives light"], "en", "vi")
    assert answer == "đèn"
    sent = json.dumps(env.fake.calls, ensure_ascii=False, default=str)
    assert "lamp" in sent
    for leaked in ("ran out of oil", "dark for hours", "a device that gives light", "sat in the"):
        assert leaked not in sent, leaked
    assert json.loads(env.fake.calls[0]["messages"][-1]["content"]) == {
        "text": "lamp", "source_language": "en", "target_language": "vi",
    }


def test_a_disabled_capability_changes_nothing_and_asks_nobody(env) -> None:
    env.repo.config = config(enabled=False)
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") is None
    env.repo.config = None
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") is None
    assert env.fake.calls == []


def test_the_second_tap_is_a_cache_hit_and_costs_no_call_and_no_brake(env, monkeypatch) -> None:
    monkeypatch.setattr(tap, "BRAKE_LIMIT", 1)
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") == "đèn"
    for _ in range(5):
        assert tap.word_translation_seam("lamp", "Another sentence.", [], "en", "vi") == "đèn"
    assert len(env.fake.calls) == 1


@pytest.mark.parametrize("text", ["the quick brown fox", "x" * 41, "", "Hello, world"])
def test_a_selection_that_is_not_a_word_or_short_phrase_is_not_sent(env, text) -> None:
    assert tap.word_translation_seam(text, SENTENCE, [], "en", "vi") is None
    assert env.fake.calls == []


def test_an_unsupported_pair_is_not_sent(env) -> None:
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "en") is None
    assert tap.word_translation_seam("lamp", SENTENCE, [], "ja", "vi") is None
    assert env.fake.calls == []


def test_a_failing_pool_is_a_miss_not_an_error(env) -> None:
    env.fake.script = {GEMMA: [http_error(503)], STANDBY: [http_error(503)]}
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") is None


def test_a_slow_answer_is_a_miss_now_and_the_background_call_fills_the_cache(env, monkeypatch) -> None:
    """Through the lookup service: the tap does not wait past its budget, the call is not abandoned."""

    from writing_coach import reading_lookup

    monkeypatch.setattr(reading_lookup, "SEAM_MIN_WAIT_SECONDS", 0.25)  # the floor has its own test

    entered, release = threading.Event(), threading.Event()

    def slow(_kwargs):
        entered.set()
        release.wait(5)

    env.fake.on_call = slow
    service = ReadingLookupService(
        None, lambda _w: {"phonetic": ""}, ReadingTranslationService(_Engine(), cache=DerivedCache()),
        budget_seconds=0.3, word_translation=tap.word_translation_seam,
    )
    started = time.monotonic()
    assert service.lookup("lamp", SENTENCE, "en", "vi").to_dict()["meanings"] == []
    assert time.monotonic() - started < 1.5 and entered.is_set()
    release.set()
    for _ in range(100):  # the router call finished on the seam's worker and filled the cache
        if tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") == "đèn":
            break
        time.sleep(0.05)
    else:
        pytest.fail("the background completion never filled the cache")
    assert len(env.fake.calls) == 1


def test_over_the_brake_the_learner_gets_the_deterministic_answer_and_no_call(env, monkeypatch) -> None:
    monkeypatch.setattr(tap, "BRAKE_LIMIT", 2)
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") == "đèn"
    env.fake.default[GEMMA] = {"meaning": "quyển sách"}
    assert tap.word_translation_seam("book", SENTENCE, [], "en", "vi") == "quyển sách"
    assert tap.word_translation_seam("door", SENTENCE, [], "en", "vi") is None  # braked: a miss, never a 429
    assert len(env.fake.calls) == 2
    token = USER_KEY_CTX.set("another-account")
    try:
        env.fake.default[GEMMA] = {"meaning": "cửa"}
        assert tap.word_translation_seam("door", SENTENCE, [], "en", "vi") == "cửa"  # its own allowance
    finally:
        USER_KEY_CTX.reset(token)


def test_the_brake_opens_again_after_its_window(env, monkeypatch) -> None:
    monkeypatch.setattr(tap, "BRAKE_LIMIT", 1)
    assert tap.word_translation_seam("lamp", SENTENCE, [], "en", "vi") == "đèn"
    env.fake.default[GEMMA] = {"meaning": "cửa"}
    assert tap.word_translation_seam("door", SENTENCE, [], "en", "vi") is None
    env.clock.now += tap.BRAKE_WINDOW_SECONDS + 1
    assert tap.word_translation_seam("door", SENTENCE, [], "en", "vi") == "cửa"


# --- through the lookup service ----------------------------------------------------------------------------------


class _Engine:
    engine_id = "ai"
    model_version = "x"

    def translate_batch(self, *_a, **_k):
        raise AssertionError("the paid reading engine must not be used by a tap")


def _service(seam=tap.word_translation_seam):
    return ReadingLookupService(
        None, lambda _word: {"phonetic": ""}, ReadingTranslationService(_Engine(), cache=DerivedCache()),
        word_translation=seam,
    )


@pytest.mark.parametrize(
    ("text", "context", "source", "target", "answer"),
    [
        ("lamp", SENTENCE, "en", "vi", "đèn"),
        ("语言", "我喜欢学习语言。", "zh", "vi", "ngôn ngữ"),
        ("ran out", SENTENCE, "en", "zh", "用完"),
    ],
)
def test_the_lookup_ends_with_the_router_after_every_deterministic_layer_missed(env, text, context, source, target, answer) -> None:
    env.fake.script = {GEMMA: [{"meaning": answer}]}
    result = _service().lookup(text, context, source, target).to_dict()
    assert result["meanings"] == [{"text": answer, "source": "word_translation"}]
    assert "ran out of oil" not in json.dumps(env.fake.calls, ensure_ascii=False, default=str)


def test_the_lookup_is_unchanged_when_the_capability_is_not_enabled(env) -> None:
    env.repo.config = config(enabled=False)
    result = _service().lookup("lamp", SENTENCE, "en", "vi").to_dict()
    assert result["meanings"] == [] and result["available"] is False
    assert env.fake.calls == []


def test_the_brake_table_evicts_the_oldest_account_not_everyone(env, monkeypatch) -> None:
    """P2-5: past the table size only the least recently used account loses its count."""

    monkeypatch.setattr(tap, "BRAKE_LIMIT", 1)
    monkeypatch.setattr(tap, "_BRAKE_ACCOUNTS_MAX", 2)
    for account in ("a", "b"):
        assert tap._braked(account) is False
        assert tap._braked(account) is True  # at its limit
    assert tap._braked("c") is False  # a third account: the oldest ("a") is evicted
    assert tap._braked("b") is True  # "b" kept its count
    assert tap._braked("a") is False  # "a" starts over


def test_openrouters_own_rate_limit_headers_are_read_counts_only() -> None:
    from writing_coach.ai.providers import _normalized_rate_limit_headers

    read = _normalized_rate_limit_headers({"X-RateLimit-Limit": "50", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1760400000000"})
    assert read["requests_limit"] == 50 and read["requests_remaining"] == 0 and read["tokens_limit"] is None
