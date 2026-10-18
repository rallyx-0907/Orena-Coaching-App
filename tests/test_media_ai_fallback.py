"""A media batch Groq cannot take goes to the platform router; Admin-stored Groq credentials win (D-224, PROPOSED).

Nothing reaches a network: Groq's transport is `requests.post` replaced by a fake, and the router is
`generate_structured` replaced by a fake that returns an `AIResult`. The ledger is the real `SpendLedger` over a temp file."""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from tests.test_media_correction_per_cue import Echo, _english, _world as _correction_world
from tests.test_media_import_pipeline_reasons import _world as _translation_world
from tests.test_media_translation_groq import FakeResponse, segments
from writing_coach import media_ai_router as router
from writing_coach import media_translation as mt
from writing_coach import media_transcript_pipeline as pipeline_module
from writing_coach.ai.base import (
    AICapabilityNotConfigured,
    AIProviderUnavailable,
    AIResult,
)
from writing_coach.media_spend import KIND_AI, SpendCapReached, SpendLedger
from writing_coach.media_translation import TranslationProviderError

SECRET = "sk-test-secret-0123456789"
TARGET = ("openai", "gpt-fallback")


@pytest.fixture(autouse=True)
def _clean_windows():
    mt.reset_output_windows()
    yield
    mt.reset_output_windows()


# -- fakes ---------------------------------------------------------------------------------------------------------

class FakeRouter:
    """`generate_structured` for the two media capabilities: answers like a well-behaved model, or as told."""

    def __init__(self, monkeypatch, *, target=TARGET, usage=None, answer=None, error=None):
        self.calls: list[dict] = []
        self.answer, self.error = answer, error
        self.usage = usage if usage is not None else {"prompt_tokens": 800, "completion_tokens": 200}
        self.target = target
        monkeypatch.setattr(router, "capability_target", lambda key: self.target)
        monkeypatch.setattr("writing_coach.ai.platform.generate_structured", self)

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.answer is not None:
            data = self.answer(kwargs) if callable(self.answer) else self.answer
        else:
            data = self._well_behaved(kwargs)
        return AIResult(data=data, provider=self.target[0], model=self.target[1], runtime=dict(self.usage))

    @staticmethod
    def _well_behaved(kwargs):
        prompt = kwargs["messages"][1]["content"]
        if kwargs["capability_key"] == router.TRANSLATION_CAPABILITY:
            ids = [line.split("\t", 1)[0] for line in prompt.splitlines() if "\t" in line]
            return {"translations": [{"segment_id": i, "translated_meaning": f"vi {i}"} for i in ids]}
        rows = [line.split("\t", 1) for line in prompt.splitlines() if line[:1].isdigit() and "\t" in line]
        return {"lines": [{"index": int(i), "text": t, "reason": "no_change"} for i, t in rows]}


def groq_answers(monkeypatch, response_for_call):
    posts: list[dict] = []

    def post(url, **kwargs):
        posts.append({"url": url, **kwargs})
        return response_for_call(len(posts), kwargs["json"])

    monkeypatch.setattr(mt.requests, "post", post)
    return posts


def refused(status, headers=None, payload=None):
    return lambda _n, _body: FakeResponse(payload if payload is not None else {}, status=status, headers=headers or {})


def admitted(log):
    def admit(provider, model, tokens):
        log.append(("admit", provider, model, tokens))
    return admit


def translate(provider, *texts, scope_log=None, max_wait=60.0, admit=None):
    rows = segments(*texts)
    with mt.fallback_scope(max_wait, admit or admitted(scope_log if scope_log is not None else [])):
        return provider.translate_batch("en", "vi", rows), rows


def wrapper(key="key"):
    return mt.FallbackTranslationProvider(mt.GroqTranslationProvider(key, model="m"), router.PlatformMediaTranslator())


# -- translation: each refusal form falls back; success and short waits do not ----------------------------------------

LONG_WAIT = {"retry-after": "600"}
GROQ_REFUSALS = [
    pytest.param(refused(429, LONG_WAIT), id="rate_limited_longer_than_the_wait_cap"),
    pytest.param(refused(429, {"retry-after": "7200"}, {"error": {"message": "Rate limit reached for model on tokens per day (TPD): Limit 100000, Used 99990, Requested 800", "code": "rate_limit_exceeded"}}), id="daily_quota_exhausted"),
    pytest.param(refused(413), id="request_too_large_that_cannot_shrink"),
    pytest.param(refused(500), id="provider_error_5xx"),
    pytest.param(refused(503), id="provider_unavailable_5xx"),
]


@pytest.mark.parametrize("groq", GROQ_REFUSALS)
def test_each_capacity_refusal_sends_that_batch_to_the_router(monkeypatch, groq):
    posts = groq_answers(monkeypatch, groq)
    fake = FakeRouter(monkeypatch)
    out, rows = translate(wrapper(), "One line.")
    assert posts, "Groq was asked first"
    assert [call["capability_key"] for call in fake.calls] == ["media_translation"]
    assert out == {rows[0].segment_id: f"vi {rows[0].segment_id}"}


def test_groq_not_configured_goes_straight_to_the_router_without_a_groq_request(monkeypatch):
    posts = groq_answers(monkeypatch, refused(500))
    fake = FakeRouter(monkeypatch)
    out, rows = translate(wrapper(key=""), "One line.")
    assert posts == [] and len(fake.calls) == 1
    assert set(out) == {rows[0].segment_id}


def test_the_router_call_selects_the_capability_configuration_whatever_the_runtime_mode(monkeypatch):
    groq_answers(monkeypatch, refused(500))
    fake = FakeRouter(monkeypatch)
    translate(wrapper(), "One line.")
    call = fake.calls[0]
    assert call["capability_mode"] is True and call["capability_key"] == "media_translation"
    assert call["temperature"] == 0.0


def test_a_short_rate_limit_is_waited_out_not_routed_around(monkeypatch):
    groq_answers(monkeypatch, refused(429, {"retry-after": "5"}))
    fake = FakeRouter(monkeypatch)
    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(), "One line.")
    assert stopped.value.reason == "rate_limited" and stopped.value.retry_after == 5
    assert fake.calls == []


def test_a_wait_longer_than_what_the_pacing_allowance_has_left_falls_back(monkeypatch):
    groq_answers(monkeypatch, refused(429, {"retry-after": "30"}))
    fake = FakeRouter(monkeypatch)
    with mt.translation_pacing(0.0):
        out, rows = translate(wrapper(), "One line.")
    assert len(fake.calls) == 1 and set(out) == {rows[0].segment_id}


def test_a_provider_auth_refusal_does_not_fall_back(monkeypatch):
    groq_answers(monkeypatch, refused(401))
    fake = FakeRouter(monkeypatch)
    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(), "One line.")
    assert stopped.value.reason == "provider_auth" and fake.calls == []


def test_no_fallback_on_success(monkeypatch):
    def ok(_n, body):
        ids = [line.split("\t", 1)[0] for line in body["messages"][1]["content"].splitlines() if "\t" in line]
        return FakeResponse({"choices": [{"message": {"content": json.dumps(
            {"translations": [{"segment_id": i, "translated_meaning": "groq"} for i in ids]})}, "finish_reason": "stop"}]})
    groq_answers(monkeypatch, ok)
    fake = FakeRouter(monkeypatch)
    out, rows = translate(wrapper(), "One line.")
    assert out == {rows[0].segment_id: "groq"} and fake.calls == []


def test_outside_a_spend_scope_there_is_no_fallback(monkeypatch):
    """The on-demand paths have no spend ledger: they keep Groq's refusal exactly."""
    groq_answers(monkeypatch, refused(500))
    fake = FakeRouter(monkeypatch)
    with pytest.raises(TranslationProviderError) as stopped:
        wrapper().translate_batch("en", "vi", segments("One line."))
    assert stopped.value.reason == "provider_error" and fake.calls == []


def test_no_router_capability_configured_is_groq_alone(monkeypatch):
    groq_answers(monkeypatch, refused(429, LONG_WAIT))
    fake = FakeRouter(monkeypatch, target=None)
    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(), "One line.")
    assert (stopped.value.reason, stopped.value.retry_after) == ("rate_limited", 600) and fake.calls == []


# -- the spend check runs before the router, and a refusal of it stops the batch ---------------------------------------

def test_the_spend_check_runs_before_the_router_call(monkeypatch):
    groq_answers(monkeypatch, refused(500))
    order: list[str] = []
    fake = FakeRouter(monkeypatch)
    original = fake.__call__

    def traced(**kwargs):
        order.append("router")
        return original(**kwargs)

    monkeypatch.setattr("writing_coach.ai.platform.generate_structured", traced)
    translate(wrapper(), "One line.", admit=lambda provider, model, tokens: order.append(f"check:{provider}/{model}"))
    assert order == ["check:openai/gpt-fallback", "router"]


def test_a_refused_spend_check_means_no_router_call_and_a_terminal_reason(monkeypatch):
    groq_answers(monkeypatch, refused(500))
    fake = FakeRouter(monkeypatch)

    def refuse(provider, model, tokens):
        raise TranslationProviderError("spend cap", reason="spend_cap")

    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(), "One line.", admit=refuse)
    assert stopped.value.reason == "spend_cap" and fake.calls == []


# -- the router's answer is validated exactly as Groq's is ---------------------------------------------------------------

@pytest.mark.parametrize("answer", [
    pytest.param(lambda kw: {"translations": []}, id="missing_ids"),
    pytest.param(lambda kw: {"translations": [{"segment_id": "not-asked", "translated_meaning": "x"}]}, id="unknown_id"),
    pytest.param(lambda kw: {"translations": "nope"}, id="not_a_list"),
    pytest.param(lambda kw: {"nothing": 1}, id="wrong_shape"),
])
def test_an_invalid_router_answer_keeps_groqs_refusal(monkeypatch, answer):
    groq_answers(monkeypatch, refused(429, LONG_WAIT))
    FakeRouter(monkeypatch, answer=answer)
    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(), "One line.")
    assert (stopped.value.reason, stopped.value.retry_after) == ("rate_limited", 600)


def test_blank_and_duplicate_meanings_are_refused_like_groqs():
    ids = {"a", "b"}
    assert mt.parse_translation_rows({"translations": [{"segment_id": "a", "translated_meaning": " "},
                                                       {"segment_id": "b", "translated_meaning": "x"}]}, ids) is None
    assert mt.parse_translation_rows({"translations": [{"segment_id": "a", "translated_meaning": "x"},
                                                       {"segment_id": "a", "translated_meaning": "y"}]}, ids) is None
    assert mt.parse_translation_rows({"translations": [{"segment_id": "a", "translated_meaning": "x"},
                                                       {"segment_id": "b", "translated_meaning": "y"}]}, ids) == {"a": "x", "b": "y"}


def test_a_router_failure_keeps_groqs_refusal_and_its_wait(monkeypatch):
    groq_answers(monkeypatch, refused(429, LONG_WAIT))
    FakeRouter(monkeypatch, error=AIProviderUnavailable(f"upstream said {SECRET}"))
    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(), "One line.")
    assert (stopped.value.reason, stopped.value.retry_after) == ("rate_limited", 600)


def test_lines_groq_already_translated_are_not_asked_of_the_router_again(monkeypatch):
    rows = segments("First.", "Second.")
    provider = wrapper()
    provider.primary._salvage_put("en", "vi", rows, {rows[0].segment_id: "salvaged"})
    groq_answers(monkeypatch, refused(500))
    fake = FakeRouter(monkeypatch)
    with mt.fallback_scope(60.0, admitted([])):
        out = provider.translate_batch("en", "vi", rows)
    asked = fake.calls[0]["messages"][1]["content"]
    assert rows[1].segment_id in asked and rows[0].segment_id not in asked
    assert out[rows[0].segment_id] == "salvaged" and out[rows[1].segment_id] == f"vi {rows[1].segment_id}"
    assert provider.primary.salvaged_for("en", "vi", rows) == {}, "served: nothing stays salvaged"


def test_provider_identity_stays_groqs_so_no_cache_key_changes():
    provider = wrapper()
    assert provider.engine_id == "groq" and provider.model_version == "m" and provider.primary.engine_id == "groq"


# -- the router-only mode ------------------------------------------------------------------------------------------------

def test_router_only_mode_never_asks_groq(monkeypatch):
    posts = groq_answers(monkeypatch, refused(500))
    fake = FakeRouter(monkeypatch)
    out, rows = translate(router.PlatformMediaTranslator(), "One line.")
    assert posts == [] and len(fake.calls) == 1 and set(out) == {rows[0].segment_id}


def test_router_only_mode_without_a_capability_is_not_configured(monkeypatch):
    FakeRouter(monkeypatch, target=None)
    with pytest.raises(TranslationProviderError) as stopped:
        router.PlatformMediaTranslator().translate_batch("en", "vi", segments("One line."))
    assert stopped.value.reason == "not_configured"
    assert router.PlatformMediaTranslator().configured is False


def test_the_provider_id_accepts_ai_without_a_groq_key_and_keeps_todays_resolution():
    assert mt.resolve_translation_provider_id("ai", groq_key="") == "ai"
    assert mt.resolve_translation_provider_id("AI", groq_key="k") == "ai"
    assert mt.resolve_translation_provider_id("", groq_key="k") == "groq"
    assert mt.resolve_translation_provider_id("", groq_key="") == "local"
    assert mt.resolve_translation_provider_id("local", groq_key="k") == "local"
    with pytest.raises(ValueError):
        mt.resolve_translation_provider_id("groq", groq_key="")
    with pytest.raises(ValueError):
        mt.resolve_translation_provider_id("gemini", groq_key="k")


def test_router_errors_map_to_stable_codes_without_their_message():
    for error, reason in [(AICapabilityNotConfigured(f"{SECRET}"), "not_configured"),
                          (AIProviderUnavailable(SECRET), "provider_error")]:
        mapped = router.map_router_error(error)
        assert mapped.reason == reason and SECRET not in str(mapped)


# -- the pipeline: translation ------------------------------------------------------------------------------------------

class TranslationWorld:
    """A pipeline whose meanings come from the real wrapper over a fake Groq transport and the fake router."""

    def __init__(self, tmp_path, monkeypatch, groq, *, library="shared", fake=None, key="key"):
        monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
        monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
        self.posts = groq_answers(monkeypatch, groq)
        self.fake = fake or FakeRouter(monkeypatch)
        self.provider = wrapper(key)

        def meanings(entry, target):
            rows = segments("One line.", "Another line.")
            try:
                self.provider.translate_batch("en", target, rows)
            except TranslationProviderError as stopped:
                return SimpleNamespace(status="partial", meanings=[], provider_calls=1, reason=stopped.reason,
                                       retry_after=stopped.retry_after)
            return SimpleNamespace(status="ready", meanings=[object()] * 5, provider_calls=1, reason="", retry_after=0.0)

        self.store, self.entry, self.pipeline = _translation_world(tmp_path, meanings=meanings)
        if library != "shared":
            from dataclasses import replace
            self.entry = replace(self.entry, library=library)
            self.store.upsert(self.entry)
        self.ledger = SpendLedger(tmp_path / "spend.json")
        self.pipeline._ledger = self.ledger
        self.pipeline._sleep = lambda _seconds: None

    def run(self):
        return self.pipeline._translate(self.store, self.entry, "batch-1", self.entry.library == "personal", stop={})

    def events(self):
        return [event for event in self.ledger._read() if event.get("kind") == KIND_AI]


@pytest.mark.parametrize("library", ["shared", "personal"])
def test_translation_through_the_router_is_booked_once_with_the_routers_provider(tmp_path, monkeypatch, library):
    world = TranslationWorld(tmp_path, monkeypatch, refused(429, LONG_WAIT), library=library)
    outcome, counts = world.run()
    assert outcome == "ready" and counts == {"vi": {"done": 5, "total": 5}}
    assert len(world.fake.calls) == 1
    events = world.events()
    assert len(events) == 1, "one router answer is one ledger row"
    assert events[0]["provider"] == "openai" and events[0]["units"] == 1 and events[0]["usd"] > 0
    assert events[0]["free_tier"] is False and events[0]["environment"]
    # which provider and model served the batch is on the item, for the Admin item view and the cost page
    served = world.store.get(world.entry.media_id).processing["translation_served"]
    assert served == [{"provider": "openai", "model": "gpt-fallback", "requests": 1}]


def test_groq_answers_are_booked_as_groq_and_no_router_row_appears(tmp_path, monkeypatch):
    usage = {"prompt_tokens": 900, "completion_tokens": 300, "total_tokens": 1200}

    def ok(_n, body):
        ids = [line.split("\t", 1)[0] for line in body["messages"][1]["content"].splitlines() if "\t" in line]
        return FakeResponse({"choices": [{"message": {"content": json.dumps(
            {"translations": [{"segment_id": i, "translated_meaning": "g"} for i in ids]})}, "finish_reason": "stop"}],
            "usage": usage})
    world = TranslationWorld(tmp_path, monkeypatch, ok)
    outcome, _ = world.run()
    assert outcome == "ready" and world.fake.calls == []
    assert [event["provider"] for event in world.events()] == ["groq"]
    assert world.store.get(world.entry.media_id).processing["translation_served"][0]["provider"] == "groq"


def test_the_router_call_is_not_recorded_a_second_time_by_the_media_layer(tmp_path, monkeypatch):
    """The router writes `ai_cost_records` and telemetry for its own call; this layer writes only Groq's attempt."""
    recorded = []
    monkeypatch.setattr("writing_coach.ai.audio_telemetry.record_token_operation",
                        lambda capability, **kwargs: recorded.append((capability, kwargs["provider"], kwargs["outcome"])))
    world = TranslationWorld(tmp_path, monkeypatch, refused(500))
    world.run()
    assert recorded == [("media_translation", "groq", "failure")], "Groq's refused attempt only; the router's call is its own"


def test_the_pipeline_spend_check_precedes_the_router_and_a_cap_stops_it(tmp_path, monkeypatch):
    world = TranslationWorld(tmp_path, monkeypatch, refused(429, LONG_WAIT))
    seen: list[str] = []
    real = world.ledger.check

    def check(kind, batch_id, usd):
        seen.append(f"check:{usd > 0}:calls={len(world.fake.calls)}")
        if len(seen) > 1:
            raise SpendCapReached("spend_cap_batch_ai", limit=0.0, spent=0.0, scope="batch")
        return real(kind, batch_id, usd)

    world.ledger.check = check
    outcome, _counts = world.run()
    assert seen[0].endswith("calls=0") and seen[1].endswith("calls=0"), "the second check (the router's) ran before any router call"
    assert world.fake.calls == [] and outcome in {"failed", "spend_cap"}
    assert world.events() == []


# -- the pipeline: correction -------------------------------------------------------------------------------------------

class Refusing:
    """A primary corrector that refuses every batch with the given reason."""
    model = "groq-model"
    model_version = "groq-model"

    def __init__(self, reason, retry_after=0.0, configured=True):
        self.reason, self.retry_after, self.configured, self.calls = reason, retry_after, configured, 0

    def correct(self, **_kwargs):
        self.calls += 1
        raise TranslationProviderError("refused", reason=self.reason, retry_after=self.retry_after)


class RouterCorrector:
    """What `PlatformMediaCorrector` is to the pipeline, with the router's answer chosen by a callable."""
    engine_id = "ai"

    def __init__(self, edit=lambda text: (text, "no_change"), target=TARGET, usage=None):
        self.edit, self._target, self.calls = edit, target, []
        self.usage = usage if usage is not None else {"prompt_tokens": 700, "completion_tokens": 150}

    def target(self):
        return self._target

    def correct(self, *, cues, **_kwargs):
        self.calls.append(tuple(cue.text for cue in cues))
        answers = [self.edit(cue.text) for cue in cues]
        mt.report_usage(self._target[1], self.usage, provider=self._target[0])
        return {"texts": [a[0] for a in answers], "reasons": [a[1] for a in answers], "provider": self._target[0],
                "model": self._target[1]}


def correction_world(tmp_path, primary, fallback, *, language="en", name="c"):
    store, entry, pipeline, slept = _correction_world(tmp_path, primary, language=language, name=name)
    pipeline._fallback_corrector = fallback
    return store, entry, pipeline, slept


def run_correction(pipeline, store, entry, count=3):
    return pipeline._correct_transcript(store, entry, "b", _english(count), origin=pipeline_module.ORIGIN_CAPTION)


CORRECTION_REFUSALS = [
    pytest.param("rate_limited", 600.0, id="rate_limited_longer_than_the_wait_cap"),
    pytest.param("rate_limited", 0.0, id="rate_limited_with_no_retry_left"),
    pytest.param("provider_error", 0.0, id="provider_error"),
    pytest.param("request_too_large", 0.0, id="request_too_large_that_cannot_shrink"),
    pytest.param("not_configured", 0.0, id="not_configured_error"),
]


@pytest.mark.parametrize(("reason", "wait"), CORRECTION_REFUSALS)
def test_each_capacity_refusal_sends_the_correction_batch_to_the_router(tmp_path, reason, wait):
    primary, fallback = Refusing(reason, wait), RouterCorrector(lambda text: (text.capitalize() + ".", "punctuation"))
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    lines, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "applied"
    assert [line.text for line in lines][0] == "Cue number 0 has some plain words."
    assert len(fallback.calls) == 1 and primary.calls >= 1
    assert {row["provider"] for row in meta["transcript_corrections"]} == {"openai"}
    assert {row["model"] for row in meta["transcript_corrections"]} == {"gpt-fallback"}


def test_a_short_rate_limit_is_waited_out_and_groq_retries_before_any_fallback(tmp_path):
    class RateLimitedOnce(Echo):
        def __init__(self):
            super().__init__()
            self.asked = 0

        def correct(self, **kwargs):
            self.asked += 1
            if self.asked == 1:
                raise TranslationProviderError("slow down", reason="rate_limited", retry_after=5.0)
            return super().correct(**kwargs)

    primary, fallback = RateLimitedOnce(), RouterCorrector()
    store, entry, pipeline, slept = correction_world(tmp_path, primary, fallback)
    _, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "applied" and slept == [5.0]
    assert fallback.calls == []


def test_no_fallback_when_groq_answers(tmp_path):
    primary, fallback = Echo(), RouterCorrector()
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    _, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "applied" and fallback.calls == []
    assert {row["provider"] for row in meta["transcript_corrections"]} <= {"groq", ""}


def test_a_provider_auth_refusal_is_not_routed_around(tmp_path):
    primary, fallback = Refusing("provider_auth"), RouterCorrector()
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    _, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "failed" and fallback.calls == []


def test_no_router_capability_is_groq_alone_and_the_item_is_held_as_today(tmp_path):
    primary, fallback = Refusing("rate_limited", 600.0), RouterCorrector(target=None)
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    lines, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "rate_limited"
    assert fallback.calls == [] and [line.text for line in lines] == [cue.text for cue in _english(3)]


def test_no_fallback_object_is_groq_alone(tmp_path):
    primary = Refusing("provider_error")
    store, entry, pipeline, _ = correction_world(tmp_path, primary, None)
    _, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "provider_error"


def test_groq_unconfigured_uses_the_router_without_a_groq_call(tmp_path):
    primary, fallback = Refusing("provider_error", configured=False), RouterCorrector()
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    _, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "applied" and primary.calls == 0 and len(fallback.calls) == 1


def test_groq_unconfigured_and_no_router_stays_unavailable(tmp_path):
    primary = Refusing("provider_error", configured=False)
    store, entry, pipeline, _ = correction_world(tmp_path, primary, RouterCorrector(target=None))
    _, meta = run_correction(pipeline, store, entry)
    assert (meta["transcript_correction_state"], meta["transcript_correction_detail"]) == ("unavailable", "corrector_unconfigured")


def test_the_spend_check_runs_before_the_correction_fallback_and_a_cap_holds_the_item(tmp_path):
    primary, fallback = Refusing("rate_limited", 600.0), RouterCorrector()
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    order: list[str] = []
    real = pipeline._ledger.check

    def check(kind, batch_id, usd):
        order.append(f"check{len(fallback.calls)}")
        if len(order) >= 2:
            raise SpendCapReached("spend_cap_batch_ai", limit=0.0, spent=0.0, scope="batch")
        return real(kind, batch_id, usd)

    pipeline._ledger.check = check
    _, meta = run_correction(pipeline, store, entry)
    assert order[:2] == ["check0", "check0"], "Groq's check, then the router's, both before any router call"
    assert fallback.calls == []
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "spend_cap"


def test_correction_usage_is_booked_once_per_call_with_the_routers_provider(tmp_path):
    primary, fallback = Refusing("provider_error"), RouterCorrector()
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    run_correction(pipeline, store, entry)
    events = [event for event in pipeline._ledger._read() if event.get("kind") == KIND_AI]
    assert len(events) == 1
    assert events[0]["provider"] == "openai" and events[0]["units"] == 1 and events[0]["usd"] > 0
    assert events[0]["free_tier"] is False and events[0]["environment"]


def test_the_per_cue_rules_apply_to_the_routers_correction_as_to_groqs(tmp_path):
    def edit(text):
        if text.startswith("cue number 1 "):
            return "Cue number 1 has plain words.", "capitalization"      # drops "some": refused
        return text.capitalize() + ".", "punctuation"
    primary, fallback = Refusing("provider_error"), RouterCorrector(edit)
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    lines, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "partial" and meta["transcript_correction_detail"] == "lexemes_changed"
    assert lines[1].text == "cue number 1 has some plain words", "the offending cue keeps its raw text"
    assert lines[0].text.endswith("words.") and lines[2].text.endswith("words.")
    assert [(row["index"], row["code"]) for row in meta["transcript_correction_rejected"]] == [(1, "lexemes_changed")]


def test_chinese_edit_allowance_applies_to_the_routers_correction(tmp_path):
    raw = "我们渡舰过河去"
    rewrite = "今天天气真好我们出去玩吧"
    primary, fallback = Refusing("provider_error"), RouterCorrector(lambda text: (rewrite, "homophone"))
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback, language="zh")
    lines, meta = pipeline._correct_transcript(
        store, entry, "b", [pipeline_module.Cue(0, 2500, raw)], origin=pipeline_module.ORIGIN_ASR)
    assert lines[0].text == raw
    assert [row["code"] for row in meta["transcript_correction_rejected"]] == ["edit_ratio_exceeded"]


def test_a_malformed_router_correction_holds_the_batch_like_groqs(tmp_path):
    class Bad(RouterCorrector):
        def correct(self, **kwargs):
            raise TranslationProviderError("bad", reason="malformed_result")
    primary, fallback = Refusing("provider_error"), Bad()
    store, entry, pipeline, _ = correction_world(tmp_path, primary, fallback)
    _, meta = run_correction(pipeline, store, entry)
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "provider_error"


def test_router_correction_answers_are_parsed_by_the_same_checks_as_groqs():
    texts = ("one", "two")
    good = {"lines": [{"index": 0, "text": "One.", "reason": "punctuation"}, {"index": 1, "text": "Two.", "reason": "A sentence"}]}
    out = mt.parse_correction_rows(good, texts, provider="openai", model="m")
    assert out["texts"] == ["One.", "Two."] and out["reasons"] == ["punctuation", "other"] and out["provider"] == "openai"
    for bad in ({"lines": []}, {"lines": [good["lines"][0], good["lines"][0]]}, {"nope": 1},
                {"lines": [good["lines"][0], {"index": 1, "text": "", "reason": "x"}]},
                {"lines": [good["lines"][0], {"index": 5, "text": "x", "reason": "x"}]}):
        with pytest.raises(TranslationProviderError) as stopped:
            mt.parse_correction_rows(bad, texts, provider="openai", model="m")
        assert stopped.value.reason == "malformed_result"


def test_the_platform_corrector_calls_its_own_capability_and_reports_usage(monkeypatch):
    fake = FakeRouter(monkeypatch)
    seen = []
    with mt.usage_sink(lambda model, usage, provider="groq": seen.append((model, usage, provider))):
        out = router.PlatformMediaCorrector().correct(language="en", cues=_english(2), title="T")
    assert fake.calls[0]["capability_key"] == "media_transcript_correction" and fake.calls[0]["capability_mode"] is True
    assert out["provider"] == "openai" and out["model"] == "gpt-fallback" and len(out["texts"]) == 2
    assert seen == [("gpt-fallback", {"prompt_tokens": 800, "completion_tokens": 200}, "openai")]


def test_thinking_tokens_are_counted_with_the_completion(monkeypatch):
    FakeRouter(monkeypatch, usage={"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 400})
    seen = []
    with mt.usage_sink(lambda model, usage, provider="groq": seen.append(usage)):
        router.PlatformMediaCorrector().correct(language="en", cues=_english(1))
    assert seen == [{"prompt_tokens": 100, "completion_tokens": 300}]


# -- Admin-stored Groq credential --------------------------------------------------------------------------------------

def test_the_admin_stored_groq_key_wins_over_the_environment(monkeypatch):
    from writing_coach.ai.providers import build_providers

    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    monkeypatch.setattr("writing_coach.ai.platform.providers", lambda: build_providers({"groq": {"api_key": "stored-key"}}))
    assert router.groq_credentials()[0] == "stored-key"
    monkeypatch.setattr("writing_coach.ai.platform.providers", lambda: build_providers({}))
    assert router.groq_credentials()[0] == "env-key"


def test_a_failing_store_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")

    def broken():
        raise RuntimeError("store down")

    monkeypatch.setattr("writing_coach.ai.platform.providers", broken)
    assert router.groq_credentials()[0] == "env-key"


def test_groq_translation_reads_the_stored_key_at_every_request(monkeypatch):
    keys = ["stored-one", "stored-two"]
    posts = groq_answers(monkeypatch, lambda _n, body: FakeResponse({"choices": [{"message": {"content": json.dumps(
        {"translations": [{"segment_id": line.split("\t", 1)[0], "translated_meaning": "x"}
                          for line in body["messages"][1]["content"].splitlines() if "\t" in line]})}, "finish_reason": "stop"}]}))
    provider = mt.GroqTranslationProvider("env-key", model="m", credentials=lambda: (keys[0], "https://groq.example/openai/v1"))
    assert provider.configured is True
    provider.translate_batch("en", "vi", segments("One."))
    keys[0] = keys[1]                                       # a key saved in Admin applies with no restart
    provider.translate_batch("en", "vi", segments("Two."))
    assert [post["headers"]["Authorization"] for post in posts] == ["Bearer stored-one", "Bearer stored-two"]
    assert posts[0]["url"] == "https://groq.example/openai/v1/chat/completions"


def test_a_stored_key_makes_an_env_keyless_groq_configured(monkeypatch):
    provider = mt.GroqTranslationProvider("", model="m", credentials=lambda: ("stored", "https://api.groq.com/openai/v1"))
    assert provider.configured is True
    assert mt.GroqTranslationProvider("", model="m", credentials=lambda: ("", "")).configured is False
    assert mt.GroqTranslationProvider("env", model="m", credentials=lambda: ("", "")).configured is True


def test_groq_correction_uses_the_stored_key(monkeypatch):
    posts = groq_answers(monkeypatch, lambda _n, _body: FakeResponse({"choices": [{"message": {"content": json.dumps(
        {"lines": [{"index": 0, "text": "One.", "reason": "punctuation"}]})}, "finish_reason": "stop"}]}))
    provider = mt.GroqTranslationProvider("env", model="m", credentials=lambda: ("stored", "https://api.groq.com/openai/v1"))
    provider.correct(language="en", cues=_english(1))
    assert posts[0]["headers"]["Authorization"] == "Bearer stored"


def test_groq_asr_uses_the_stored_key_and_the_environment_otherwise():
    from writing_coach.speech_asr import GroqSpeechAsrProvider

    source = {"key": "stored-asr"}
    provider = GroqSpeechAsrProvider("env-asr", key_source=lambda: source["key"])
    assert provider._bearer() == "stored-asr"
    source["key"] = ""
    assert provider._bearer() == "env-asr"
    source["key"] = "has a space"
    assert provider._bearer() == "env-asr", "a key a header cannot carry is never used"
    assert GroqSpeechAsrProvider("env-asr")._bearer() == "env-asr"


def test_asr_exists_at_start_from_a_stored_key_alone(monkeypatch):
    from writing_coach.speech_asr import GroqSpeechAsrProvider

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert GroqSpeechAsrProvider.from_env() is None
    provider = GroqSpeechAsrProvider.from_env(key_source=lambda: "stored-asr")
    assert provider is not None and provider._bearer() == "stored-asr"


# -- no secret is ever logged -------------------------------------------------------------------------------------------

def test_no_key_reaches_a_log_a_stored_record_or_an_error(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("GROQ_API_KEY", SECRET)
    world = TranslationWorld(tmp_path, monkeypatch, refused(429, LONG_WAIT),
                             fake=FakeRouter(monkeypatch, error=AIProviderUnavailable(f"upstream {SECRET}")), key=SECRET)
    world.run()
    store, entry, pipeline, _ = correction_world(tmp_path, Refusing("provider_error"), RouterCorrector(), name="s")
    run_correction(pipeline, store, entry)
    stored = json.dumps(world.store.get(world.entry.media_id).processing, default=str)
    stored += json.dumps(store.get(entry.media_id).processing, default=str)
    assert SECRET not in caplog.text and SECRET not in stored
    with pytest.raises(TranslationProviderError) as stopped:
        translate(wrapper(SECRET), "One line.")
    assert SECRET not in str(stopped.value)


# -- the capability catalogue -------------------------------------------------------------------------------------------

def test_the_two_media_capabilities_are_declared_opt_in_and_configurable():
    from writing_coach.ai.capabilities import activation_capabilities, configurable_provider_capabilities, require_capability

    for key in ("media_translation", "media_transcript_correction"):
        definition = require_capability(key)
        assert definition.provider_backed and definition.configurable and definition.implemented and definition.opt_in
        assert definition.input_class == "learner_text", "a learner's private import is learner content (D-104)"
        assert key in {item.key for item in configurable_provider_capabilities()}
        assert key not in {item.key for item in activation_capabilities()}, "no row is required to activate the runtime"


def test_an_operator_can_pick_a_paid_provider_model_and_backup_for_each_capability():
    from writing_coach.ai.config import CapabilityConfig, validate_capability_config

    for key in ("media_translation", "media_transcript_correction"):
        config = CapabilityConfig(enabled=True, provider="openai", model="gpt-4.1-mini",
                                  backup_provider="deepseek", backup_model="deepseek-v4-flash")
        validate_capability_config(key, config)
        validate_capability_config(key, CapabilityConfig(enabled=True, provider="gemini", model="gemini-2.5-flash"))


def test_a_prompt_logging_provider_is_refused_for_the_media_capabilities():
    from writing_coach.ai.base import AICapabilityConfigInvalid
    from writing_coach.ai.config import CapabilityConfig, validate_capability_config

    with pytest.raises(AICapabilityConfigInvalid):
        validate_capability_config("media_translation",
                                   CapabilityConfig(enabled=True, provider="openrouter", model="meta/model:free"))


def test_the_capability_target_needs_an_enabled_row_and_a_credentialed_provider(monkeypatch):
    from writing_coach.ai import platform
    from writing_coach.ai.config import CapabilityConfig

    config = CapabilityConfig(enabled=True, provider="openai", model="gpt-4.1-mini")
    holder = {"row": SimpleNamespace(config=config)}
    repository = SimpleNamespace(get_capability_config=lambda key: holder["row"])
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "providers", lambda: {"openai": SimpleNamespace(configured=True)})
    assert router.capability_target("media_translation") == ("openai", "gpt-4.1-mini")
    monkeypatch.setattr(platform, "providers", lambda: {"openai": SimpleNamespace(configured=False)})
    assert router.capability_target("media_translation") is None
    monkeypatch.setattr(platform, "providers", lambda: {"openai": SimpleNamespace(configured=True)})
    holder["row"] = None
    assert router.capability_target("media_translation") is None
    holder["row"] = SimpleNamespace(config=CapabilityConfig(enabled=False, provider="openai", model="gpt-4.1-mini"))
    assert router.capability_target("media_translation") is None
