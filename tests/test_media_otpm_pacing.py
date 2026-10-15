"""Translation respects an output-tokens-per-minute (OTPM) allowance (D-218, PROPOSED).

Trial evidence (2026-10-15 sitting 2, :8021, `qwen/qwen3.8-27b`): after the first 24 lines every continuation round was
refused with `output tokens per minute (OTPM): Limit 1000, Used 867-922, Requested 640`, and retries about every 35 s kept the
one-minute window full, so an item of more than about 35 cues never finished (Vox 24/49, Lauris 48/76).

Everything here is a fake: a virtual clock and a provider that admits a request only while `used + max_completion_tokens`
fits the limit inside a sliding 60 s window. Nothing reaches a network and nothing sleeps."""
from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from tests.test_media_import_pipeline_reasons import _Ledger, _entry
from tests.test_media_translation_continuation import _drain, _first_run
from tests.test_media_translation_groq import FakeResponse, segments
from writing_coach import listening_api
from writing_coach import media_translation as mt
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.media_meaning import resolve_segment_meanings

MODEL = "qwen/qwen3.8-27b"
LIMIT = 1000


class Clock:
    def __init__(self) -> None:
        self.now = 10_000.0

    def advance(self, seconds: float) -> None:
        self.now += max(0.0, seconds)


class FakeGroqOtpm:
    """Groq's output-token allowance: `used + requested` must fit `limit` over the last 60 s. A request that is refused
    optionally still fills the window (`refusals_consume`), the worst reading of the trial's 'Used stays near 900'."""

    def __init__(self, clock: Clock, *, limit: int = LIMIT, refusals_consume: bool = False) -> None:
        self.clock, self.limit, self.refusals_consume = clock, limit, refusals_consume
        self.events: list[tuple[float, int]] = []
        self.sent: list[tuple[float, list[str]]] = []   # (time, source texts) of every request that reached the provider
        self.refused: list[float] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        body = kwargs["json"]
        requested = int(body["max_completion_tokens"])
        now = self.clock.now
        used = sum(tokens for at, tokens in self.events if at > now - 60.0)
        lines = [row.split("\t", 1) for row in body["messages"][1]["content"].split("\n\n", 1)[1].split("\n")]
        self.sent.append((now, [text for _id, text in lines]))
        if used + requested > self.limit:
            self.refused.append(now)
            if self.refusals_consume:
                self.events.append((now, requested))
            message = (f"Rate limit reached for model `{MODEL}` in organization `org_01abc` service tier `on_demand` on output "
                       f"tokens per minute (OTPM): Limit {self.limit}, Used {used}, Requested {requested}. Please try again in 35s.")
            return FakeResponse({"error": {"message": message, "type": "tokens", "code": "rate_limit_exceeded"}}, status=429,
                                headers={"retry-after": "35", "x-ratelimit-limit-tokens": "8000"})
        content = json.dumps({"translations": [{"segment_id": ident, "translated_meaning": f"VI {text}"} for ident, text in lines]})
        completion = math.ceil(len(content) / 3)
        self.events.append((now, requested))
        finish = "length" if completion > requested else "stop"
        return FakeResponse({"choices": [{"finish_reason": finish, "message": {"content": content}}],
                             "usage": {"prompt_tokens": 400, "completion_tokens": min(completion, requested), "total_tokens": 400 + completion}})


@pytest.fixture
def world(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(mt, "_monotonic", lambda: clock.now)
    monkeypatch.setattr(mt, "_pause", clock.advance)
    mt.reset_output_windows()
    fake = FakeGroqOtpm(clock)
    monkeypatch.setattr(mt.requests, "post", fake.post)
    yield clock, fake
    mt.reset_output_windows()


def long_texts(count: int) -> list[str]:
    return [f"line {index:03d} " + "the quick brown fox keeps talking about the economy " * 1 + "." for index in range(count)]


# ---- the provider -------------------------------------------------------------------------------------------------------

def test_a_refused_window_is_waited_out_not_hammered(world):
    clock, fake = world
    batch = segments(*long_texts(24))
    provider = mt.GroqTranslationProvider("k", model=MODEL)
    with pytest.raises(mt.TranslationProviderError) as first:
        provider.translate_batch("en", "vi", batch)
    assert first.value.reason == "rate_limited" and len(fake.refused) == 1
    # The provider's own sentence said Limit 1000: it is learned, and the wait covers a whole one-minute window even though
    # the 429 asked for 35 s.
    assert first.value.retry_after >= 60.0
    sent = len(fake.sent)
    for _ in range(3):  # asking again at once must not reach the provider
        with pytest.raises(mt.TranslationProviderError) as again:
            provider.translate_batch("en", "vi", batch)
        assert again.value.reason == "rate_limited" and again.value.retry_after >= 55.0
    assert len(fake.sent) == sent
    clock.advance(first.value.retry_after + 1)
    # Past the window, the lines the first call already had are not asked for twice.
    done = provider.translate_batch("en", "vi", batch[: 4])
    assert len(done) == 4 and len(fake.refused) == 1


def test_batches_are_sized_to_the_limit_and_a_configured_limit_needs_no_refusal(world):
    clock, fake = world
    provider = mt.GroqTranslationProvider("k", model=MODEL, output_tokens_per_minute=LIMIT)
    assert provider.batch_output_ceiling() == LIMIT // 2
    batch = segments(*long_texts(12))
    with mt.translation_pacing(300.0):
        out = provider.translate_batch("en", "vi", batch)
    assert set(out) == {s.segment_id for s in batch}
    assert fake.refused == []
    for _at, texts in fake.sent:
        assert len(texts) < 12  # one request never held the whole batch: each fits half the minute
    assert clock.now > 10_000.0 + 55  # the second half of the minute was waited for, inside the allowed pacing


def test_pacing_that_is_not_allowed_refuses_without_sending_and_keeps_finished_lines(world):
    clock, fake = world
    provider = mt.GroqTranslationProvider("k", model=MODEL, output_tokens_per_minute=LIMIT)
    batch = segments(*long_texts(12))
    with pytest.raises(mt.TranslationProviderError) as stopped:   # no pacing allowance: never sleeps
        provider.translate_batch("en", "vi", batch)
    assert stopped.value.reason == "rate_limited" and 0 < stopped.value.retry_after <= 63
    assert fake.refused == [] and clock.now == 10_000.0
    already = [text for _at, texts in fake.sent for text in texts]
    assert 0 < len(already) < 12
    clock.advance(stopped.value.retry_after)
    fake.sent.clear()
    with mt.translation_pacing(300.0):
        out = provider.translate_batch("en", "vi", batch)
    assert len(out) == 12
    again = [text for _at, texts in fake.sent for text in texts]
    assert not set(again) & set(already)   # the lines that were translated before the stop were kept, not paid for twice


def test_the_limit_comes_from_configuration_or_the_provider_never_from_the_model_name(monkeypatch):
    assert mt.resolve_output_tokens_per_minute(env={mt.GROQ_OTPM_ENV: "1000"}) == 1000
    for bad in ("", "abc", "-5", "0", "99999999"):
        assert mt.resolve_output_tokens_per_minute(env={mt.GROQ_OTPM_ENV: bad}) is None
    mt.reset_output_windows()
    unknown = mt.GroqTranslationProvider("k", model="some/other-model")
    assert unknown.batch_output_ceiling() is None   # nothing is assumed for a model; a refusal teaches it
    assert mt.GroqTranslationProvider("k", model="x", output_tokens_per_minute=600).batch_output_ceiling() == 300


def test_batches_split_by_output_estimate_only_when_asked():
    many = segments(*long_texts(76))
    plain = mt.build_translation_batches(many[:48])
    assert [len(batch) for batch in plain] == [24, 24]
    sized = mt.build_translation_batches(many[:24], max_output_tokens=500)
    assert sized is not None and [segment.segment_id for batch in sized for segment in batch] == [s.segment_id for s in many[:24]]
    assert all(mt.estimate_output_tokens(batch) <= 500 or len(batch) == 1 for batch in sized)
    assert len(sized) > 2
    assert mt.build_translation_batches(many[:48], max_output_tokens=500) is None  # more than one call may hold: the caller takes a window


# ---- the whole pipeline: a 76-line item completes -----------------------------------------------------------------------

class _Cache:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get_media_translation(self, key):
        return self.rows.get(key)

    def put_media_translation(self, key, translated_text, provenance, generated_at):
        self.rows[key] = {"translated_text": translated_text}


def _item(tmp_path, monkeypatch, clock, *, lines):
    from writing_coach.media_segmentation import Cue
    from writing_coach.media_transcript_pipeline import MediaPipeline, build_transcript, lesson_payload

    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    store = FileMediaLibraryStore(tmp_path / "index")
    entry = replace(_entry(), language="en", status="processing", processing={"state": "running"})
    texts = long_texts(lines)
    cues = [Cue(i * 6000, i * 6000 + 5000, text) for i, text in enumerate(texts)]
    payload = lesson_payload(entry, build_transcript(entry.media_id, "en", cues), "fixture", lines * 6000)
    entry = replace(entry, lesson={"lesson_id": entry.media_id, "payload": payload})
    store.upsert(entry)
    provider = mt.GroqTranslationProvider("k", model=MODEL)
    service = mt.MediaTranslationService(provider)
    monkeypatch.setattr(listening_api, "media_translation_service", lambda: service)
    cache = _Cache()

    def meanings(item, target):
        stored = (item.lesson or {}).get("payload") or {}
        media_object = listening_api._media_object_from_stored(stored, item)
        return resolve_segment_meanings(
            asset_id=media_object.asset.asset_id, segments=media_object.transcript.segments, support_language=target,
            source_language=media_object.asset.source_language, preauthored=media_object.translations, cache=cache,
            translate=listening_api._curated_translator(media_object), provider_model=f"{type(provider).__name__}:{MODEL}")

    pipeline = MediaPipeline(ledger=_Ledger(), workers=1, meanings=meanings)
    held = store.update_if_present(entry.media_id, lambda e: replace(
        e, processing={"state": "held", "stage": "ready", "reason": "rights_unknown", "batch_id": "b1", "attempts": 1}))
    scheduled: list = []
    base = 1_000_000.0
    pipeline._schedule = lambda delay, callback: scheduled.append((delay, callback))
    pipeline._clock = lambda: base + (clock.now - 10_000.0)
    pipeline._sleep = clock.advance
    return store, held, pipeline, scheduled


class _Clocked:
    """`_drain` moves a one-element list; this one moves the shared virtual clock."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def __getitem__(self, _index: int) -> float:
        return self.clock.now

    def __setitem__(self, _index: int, value: float) -> None:
        self.clock.now = value


@pytest.mark.parametrize("refusals_consume", [False, True])
def test_a_76_line_item_completes_under_a_1000_token_minute(tmp_path, monkeypatch, world, refusals_consume):
    clock, fake = world
    fake.refusals_consume = refusals_consume
    store, entry, pipeline, scheduled = _item(tmp_path, monkeypatch, clock, lines=76)
    _first_run(store, entry, pipeline)
    _drain(scheduled, _Clocked(clock))
    stored = store.get(entry.media_id).processing
    assert stored["translation_counts"] == {"vi": {"done": 76, "total": 76}}, (stored["translation"], stored["translation_reason"])
    assert stored["translation"] == "ready" and stored["translation_continuation"] == {}
    assert stored["state"] == "held" and stored["reason"] == "rights_unknown"
    # It learned the limit from at most one refusal and then paced: it never hammered the provider.
    assert len(fake.refused) <= 1
    assert all(second - first >= 59 for first, second in zip(fake.refused, fake.refused[1:], strict=False))
    assert all(len(texts) >= 1 for _at, texts in fake.sent)


def test_no_progress_still_costs_nothing(tmp_path, monkeypatch, world):
    clock, fake = world
    fake.limit = 0   # nothing can ever fit: a refusal every time
    store, entry, pipeline, scheduled = _item(tmp_path, monkeypatch, clock, lines=30)
    booked: list[float] = []
    pipeline._ledger.record = lambda kind, usd, **_k: booked.append(usd)
    _first_run(store, entry, pipeline)
    _drain(scheduled, _Clocked(clock))
    assert booked == [] or all(usd == 0 for usd in booked)
    assert all(second - first >= 59 for first, second in zip(fake.refused, fake.refused[1:], strict=False))   # a refusal is waited out, not retried
    assert store.get(entry.media_id).processing["translation"] in {"failed", "partial"}
