"""A translation round that made no progress costs nothing, and a request asks only for the room it needs (D-216, PROPOSED).

Trial evidence (2026-10-15, :8021, `youtube-4HGNqFdaD34`, 49 cues): translation stuck at 24/49 for nine rounds, each one
booked at the pre-call estimate ($0.003326) although Groq had answered 429 every time. The sandbox log carried the
headers of those refusals: 5.5k to 8k of the 8000-token minute bucket and 992+ of the 1000 requests were left, while
`retry-after` asked for 6 to 680 s, so it was not the minute bucket that refused. Groq admits a request against the room
left in an allowance for `prompt + max_completion_tokens`, and this provider always asked for 2048 completion tokens
whatever the batch held. Issue #228: a call the provider refused (401/403/429), or an answer without `usage`, books 0.

Providers here are fakes; nothing reaches a network."""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from tests.test_media_import_pipeline_reasons import _world
from tests.test_media_translation_groq import FakeResponse, install, segments
from writing_coach import media_translation as mt
from writing_coach.media_learning import TranscriptSegment
from writing_coach.media_spend import KIND_AI, SpendLedger


def _ok(segment_ids, *, usage=None):
    body = {"choices": [{"message": {"content": json.dumps(
        {"translations": [{"segment_id": sid, "translated_meaning": f"vi {sid}"} for sid in segment_ids]})},
        "finish_reason": "stop"}]}
    if usage is not None:
        body["usage"] = usage
    return body


def _ids(request_json):
    prompt = request_json["messages"][1]["content"]
    return [line.split("\t", 1)[0] for line in prompt.splitlines() if "\t" in line]


class _World:
    """A pipeline whose meanings come from the real Groq provider over a fake transport, and a real ledger."""

    def __init__(self, tmp_path, monkeypatch, response_for_call):
        monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
        monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
        self.provider = mt.GroqTranslationProvider("key", model="openai/gpt-oss-120b")
        self.calls = 0

        def post(url, **kwargs):
            self.calls += 1
            return response_for_call(self.calls, kwargs["json"])

        monkeypatch.setattr(mt.requests, "post", post)

        def meanings(entry, target):
            rows = segments("One line.", "Another line.")
            try:
                self.provider.translate_batch("en", target, rows)
            except mt.TranslationProviderError as refused:
                return SimpleNamespace(status="partial", meanings=[], provider_calls=1,
                                       reason=refused.reason, retry_after=refused.retry_after)
            return SimpleNamespace(status="ready", meanings=[object()] * 5, provider_calls=1, reason="", retry_after=0.0)

        self.store, self.entry, self.pipeline = _world(tmp_path, meanings=meanings)
        self.ledger = SpendLedger(tmp_path / "spend.json")
        self.pipeline._ledger = self.ledger
        self.pipeline._sleep = lambda _seconds: None

    def run(self):
        return self.pipeline._translate(self.store, self.entry, "batch-1", False, stop={})

    def booked(self):
        events = [e for e in self.ledger._read() if e.get("kind") == KIND_AI]
        return len(events), sum(float(e["usd"]) for e in events)


# -- #228: a refused call books nothing ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_refused_call_books_zero_however_many_rounds_it_is_asked(tmp_path, monkeypatch, status):
    world = _World(tmp_path, monkeypatch, lambda _n, _body: FakeResponse({}, status=status, headers={"retry-after": "1"}))
    outcome, _counts = world.run()
    assert outcome == "failed"
    assert world.calls >= 1, "the provider was asked"
    assert world.booked() == (0, 0.0)


def test_nine_rounds_without_progress_still_book_nothing(tmp_path, monkeypatch):
    """The trial's NatGeo item: 24 lines, then 429 on every round."""
    world = _World(tmp_path, monkeypatch, lambda _n, _body: FakeResponse({}, status=429, headers={"retry-after": "30"}))
    for _round in range(9):
        world.run()
    assert world.booked() == (0, 0.0)


def test_an_answer_without_usage_books_zero(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch, lambda _n, body: FakeResponse(_ok(_ids(body))))
    outcome, _counts = world.run()
    assert outcome == "ready"
    assert world.booked() == (0, 0.0)


def test_an_answer_with_usage_books_what_the_provider_reported(tmp_path, monkeypatch):
    usage = {"prompt_tokens": 900, "completion_tokens": 300, "total_tokens": 1200}
    world = _World(tmp_path, monkeypatch, lambda _n, body: FakeResponse(_ok(_ids(body), usage=usage)))
    outcome, _counts = world.run()
    assert outcome == "ready"
    count, spent = world.booked()
    assert count == 1
    assert spent == pytest.approx(world.pipeline._ai_cost("openai/gpt-oss-120b", usage))
    assert spent > 0


def test_a_batch_the_provider_billed_and_then_split_is_booked_for_the_tokens_it_used(tmp_path, monkeypatch):
    """A 200 whose JSON is unusable is refused by this code, but the provider billed its tokens."""
    usage = {"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000}

    def answer(call, body):
        if call == 1:
            return FakeResponse({"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}], "usage": usage})
        return FakeResponse(_ok(_ids(body), usage=usage))

    world = _World(tmp_path, monkeypatch, answer)
    world.run()
    count, spent = world.booked()
    assert count == 1
    assert spent == pytest.approx(3 * world.pipeline._ai_cost("openai/gpt-oss-120b", usage))


# -- the request asks for the room it needs -----------------------------------------------------------------------

def _long_ids(count, text):
    return tuple(
        TranscriptSegment(segment_id=f"{index:032x}" * 3, order=index, start_ms=index * 2000,
                          end_ms=(index + 1) * 2000, original_text=text)
        for index in range(count)
    )


def test_a_small_batch_reserves_a_small_completion(monkeypatch):
    posted = []

    def post(url, **kwargs):
        posted.append(kwargs["json"])
        return FakeResponse(_ok(_ids(kwargs["json"])))

    monkeypatch.setattr(mt.requests, "post", post)
    mt.GroqTranslationProvider("key", model="m").translate_batch("en", "vi", segments("Hello there.", "How are you?"))
    asked = posted[-1]["max_completion_tokens"]
    assert mt.MIN_GROQ_MAX_COMPLETION_TOKENS <= asked < mt.DEFAULT_GROQ_MAX_COMPLETION_TOKENS


def test_the_reservation_never_exceeds_the_configured_ceiling(monkeypatch):
    posted = []

    def post(url, **kwargs):
        posted.append(kwargs["json"])
        return FakeResponse(_ok(_ids(kwargs["json"])))

    monkeypatch.setattr(mt.requests, "post", post)
    rows = segments(*["A sentence of about eighty characters, spoken by a narrator in the middle of a film." for _ in range(12)])
    mt.GroqTranslationProvider("key", model="m", max_completion_tokens=512).translate_batch("en", "vi", rows)
    assert all(body["max_completion_tokens"] <= 512 for body in posted)


def test_long_canonical_ids_do_not_split_a_batch_that_travels_with_short_handles(monkeypatch):
    """The wire carries `line-000000` handles when ids are long, so the pre-split size is the wire's, not the canonical id's."""
    posted = []

    def post(url, **kwargs):
        posted.append(kwargs["json"])
        return FakeResponse(_ok(_ids(kwargs["json"])))

    monkeypatch.setattr(mt.requests, "post", post)
    rows = _long_ids(24, "A short line of text.")
    result = mt.GroqTranslationProvider("key", model="m").translate_batch("en", "vi", rows)
    assert len(posted) == 1
    assert set(result) == {row.segment_id for row in rows}


def test_a_49_line_item_completes_when_the_allowance_left_fits_the_reservation_it_needs(monkeypatch):
    """Groq admits a request when `prompt + max_completion_tokens` fits the room left in an allowance. With 2300 tokens
    of room, a fixed 2048-token reservation can never fit beside a real prompt (the stuck item); a reservation sized
    to the batch does, so the 49 lines are translated in the batches the translator already sends."""
    room = 2300
    admitted = []

    def post(url, **kwargs):
        body = kwargs["json"]
        prompt_tokens = len(body["messages"][0]["content"] + body["messages"][1]["content"]) // 3
        if prompt_tokens + body["max_completion_tokens"] > room:
            return FakeResponse({"error": {"message": "tokens per day (TPD)", "code": "rate_limit_exceeded"}},
                                status=429, headers={"retry-after": "300"})
        admitted.append(len(_ids(body)))
        return FakeResponse(_ok(_ids(body)))

    monkeypatch.setattr(mt.requests, "post", post)
    texts = [f"(line {i}) " + "This is a caption of about eighty characters, said by a narrator in a film." for i in range(49)]
    rows = segments(*texts)
    provider = mt.GroqTranslationProvider("key", model="m")
    done = {}
    for batch in mt.build_translation_batches(rows):
        done.update(provider.translate_batch("en", "vi", batch))
    assert set(done) == {row.segment_id for row in rows}
    assert sum(admitted) == 49


def test_the_old_fixed_2048_reservation_stalls_in_the_same_world(monkeypatch):
    """The negative case of the test above: with the same 2300 tokens of room, a fixed 2048 reservation is refused for
    every batch, so nothing is translated."""
    room = 2300
    admitted = []

    def post(url, **kwargs):
        body = kwargs["json"]
        prompt_tokens = len(body["messages"][0]["content"] + body["messages"][1]["content"]) // 3
        if prompt_tokens + body["max_completion_tokens"] > room:
            return FakeResponse({"error": {"message": "tokens per day (TPD)"}}, status=429, headers={"retry-after": "300"})
        admitted.append(len(_ids(body)))
        return FakeResponse(_ok(_ids(body)))

    monkeypatch.setattr(mt.requests, "post", post)
    rows = segments(*[f"(line {i}) " + "This is a caption of about eighty characters, said by a narrator in a film." for i in range(49)])
    provider = mt.GroqTranslationProvider("key", model="m")
    monkeypatch.setattr(provider, "_completion_budget", lambda _wire: 2048)
    refused = 0
    for batch in mt.build_translation_batches(rows):
        with pytest.raises(mt.TranslationProviderError) as stalled:
            provider.translate_batch("en", "vi", batch)
        assert stalled.value.reason == "rate_limited"
        refused += 1
    assert refused >= 2 and admitted == []


# -- the usage sink -----------------------------------------------------------------------------------------------

USAGE = {"prompt_tokens": 900, "completion_tokens": 300, "total_tokens": 1200}


def test_usage_captured_before_meanings_raises_is_still_booked(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch, lambda _n, body: FakeResponse(_ok(_ids(body), usage=USAGE)))
    inner = world.pipeline._meanings

    def meanings(entry, target):
        inner(entry, target)
        raise RuntimeError("after the provider billed")

    world.pipeline._meanings = meanings
    world.run()
    count, spent = world.booked()
    assert count == 1 and spent == pytest.approx(world.pipeline._ai_cost("openai/gpt-oss-120b", USAGE))


def test_an_explicit_translation_sink_is_honoured(tmp_path, monkeypatch):
    from contextlib import contextmanager

    world = _World(tmp_path, monkeypatch, lambda _n, body: FakeResponse(_ok(_ids(body), usage=USAGE)))
    opened = []
    held = {}

    @contextmanager
    def sink(callback):
        opened.append(True)
        held["callback"] = callback
        yield

    world.pipeline._translation_sink = sink
    world.pipeline._meanings = lambda entry, target: (
        held["callback"]("openai/gpt-oss-120b", USAGE),
        SimpleNamespace(status="ready", meanings=[object()] * 5, provider_calls=1, reason="", retry_after=0.0))[1]
    world.run()
    assert opened == [True]
    count, spent = world.booked()
    assert count == 1 and spent == pytest.approx(world.pipeline._ai_cost("openai/gpt-oss-120b", USAGE))


def test_the_usage_sink_does_not_leak_into_another_thread_or_past_its_block(monkeypatch):
    import threading

    monkeypatch.setattr(mt.requests, "post", lambda url, **kw: FakeResponse(_ok(_ids(kw["json"]), usage=USAGE)))
    provider = mt.GroqTranslationProvider("key", model="m")
    seen = []

    def call():
        provider.translate_batch("en", "vi", segments("One."))

    with mt.usage_sink(lambda model, usage: seen.append(model)):
        worker = threading.Thread(target=call)
        worker.start()
        worker.join()
        assert seen == [], "a new thread starts with an empty context"
        call()
        assert seen == ["m"]
    call()
    assert seen == ["m"], "nothing is reported after the block"


def test_an_organisation_id_in_a_429_sentence_is_not_logged(monkeypatch, caplog):
    message = "Rate limit reached for model `m` in organization `org_01abcdEFGH23` on tokens per day (TPD): Limit 200000."
    install(monkeypatch, FakeResponse({"error": {"message": message}}, status=429, headers={"retry-after": "5"}))
    with caplog.at_level(logging.WARNING, logger="writing_coach.media_translation"):
        with pytest.raises(mt.TranslationProviderError):
            mt.GroqTranslationProvider("key", model="m").translate_batch("en", "vi", segments("One."))
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "org_01abcdEFGH23" not in text and "tokens per day" in text


# -- the reason is findable ---------------------------------------------------------------------------------------

def test_a_429_log_names_the_allowance_that_refused_and_no_credential(monkeypatch, caplog):
    message = ("Rate limit reached for model `openai/gpt-oss-120b` on tokens per day (TPD): Limit 200000, Used 198900, "
               "Requested 2900. Please try again in 8m30s.")
    install(monkeypatch, FakeResponse({"error": {"message": message, "type": "tokens", "code": "rate_limit_exceeded"}},
                                      status=429, headers={"retry-after": "510", "authorization": "Bearer secret-value"}))
    with caplog.at_level(logging.WARNING, logger="writing_coach.media_translation"):
        with pytest.raises(mt.TranslationProviderError):
            mt.GroqTranslationProvider("secret-key", model="m").translate_batch("en", "vi", segments("One."))
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "tokens per day" in text
    assert "secret" not in text
