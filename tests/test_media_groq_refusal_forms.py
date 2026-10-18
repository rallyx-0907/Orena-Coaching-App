"""Groq answers an output-allowance refusal in two forms; both teach the limit, only one is a wait (live, 2026-10-17/18).

The two sentences below keep the exact structure of the `error.message` of the 429 answers recorded on :8021
(`qwen/qwen3.8-27b`); only the organisation id is a synthetic stand-in, because it identifies a third party's account and
the parser does not need it (`media_translation._ORG_ID` redacts it from logs for the same reason). The first
carries a `Used` count (the minute is full: wait). The second has none: one request alone expects more output than the whole
minute allows (the request is too big: ask for less, do not wait). The provider used to understand only the first, so after the
second it never learned its limit, kept asking for 24 cues and every attempt was refused. No network: `requests.post` is replaced."""
from __future__ import annotations

from pathlib import Path

from tests.test_media_translation_groq import FakeResponse
from writing_coach import media_translation as mt

MODEL = "qwen/qwen3.8-27b"
ORG = "org_test_account"
WINDOW_FULL = (f"Rate limit reached for model `{MODEL}` in organization `{ORG}` service tier `on_demand` on output tokens per "
               "minute (OTPM): Limit 1000, Used 829, Requested 444. Please try again in 16.38s. Need more tokens? Upgrade "
               "to Dev Tier today at https://console.groq.com/settings/billing")
REQUEST_TOO_LARGE = (f"Request too large for model `{MODEL}` in organization `{ORG}` service tier `on_demand` on output "
                     "tokens per minute (OTPM): Limit 1000, Requested 1816. The request's expected output tokens exceed the "
                     "enforced limit; reduce max_tokens (or the request's expected output) and try again. Need more tokens? "
                     "Upgrade to Dev Tier today at https://console.groq.com/settings/billing")


def refusal(message: str, headers: dict | None = None) -> FakeResponse:
    return FakeResponse({"error": {"message": message, "type": "tokens", "code": "rate_limit_exceeded"}}, status=429,
                        headers=headers or {"x-ratelimit-limit-tokens": "8000", "x-ratelimit-reset-tokens": "7.38s"})


def test_the_recorded_sentences_carry_no_real_organisation_id_and_the_log_still_redacts_one():
    """A real organisation id is account identification of a third party: it must not be committed in a fixture. The
    synthetic id keeps the `org_` form, so the log redaction is exercised on it too."""
    assert ORG == "org_test_account"
    assert "org_test_account" in WINDOW_FULL and "org_test_account" in REQUEST_TOO_LARGE
    logged = mt._error_detail(refusal(REQUEST_TOO_LARGE))
    assert "org_test_account" not in logged and "org_<redacted>" in logged
    source = Path(__file__).read_text(encoding="utf-8")
    import re
    # `org_` followed by a long machine-generated token is the shape of a real id; the only `org_` ids here are synthetic.
    assert not re.search(r"org_[0-9a-z]{16,}", source)


def test_both_recorded_sentences_are_read_and_do_not_confuse_each_other():
    assert mt._otpm_refusal(refusal(WINDOW_FULL)) == (1000, 829)
    assert mt._otpm_request_too_large(refusal(WINDOW_FULL)) is None             # it has a `Used`: that is the wait form
    assert mt._otpm_refusal(refusal(REQUEST_TOO_LARGE)) is None                   # no `Used`: the old reading found nothing
    assert mt._otpm_request_too_large(refusal(REQUEST_TOO_LARGE)) == (1000, 1816)
    assert mt._otpm_request_too_large(refusal("some other refusal")) is None


def test_the_too_large_form_teaches_the_limit_but_not_a_wait():
    mt.reset_output_windows()
    provider = mt.GroqTranslationProvider("k", model="refusal-forms-a")
    assert provider.batch_output_ceiling() is None and provider.correction_output_ceiling() == 2048
    reserved = provider._otpm.reserve(2048, mt._monotonic())
    asked = provider._learn_from_refusal(refusal(REQUEST_TOO_LARGE), reserved, 0.0)
    assert provider.batch_output_ceiling() == 500 and provider.correction_output_ceiling() == 500
    assert asked == 0.0                                                            # no 62 s window to wait out
    assert provider._otpm.wait_for(100, mt._monotonic()) == 0.0                   # nothing blocked, nothing counted as used
    mt.reset_output_windows()


def test_the_window_full_form_still_waits_and_syncs_as_before():
    mt.reset_output_windows()
    provider = mt.GroqTranslationProvider("k", model="refusal-forms-b")
    reserved = provider._otpm.reserve(2048, mt._monotonic())
    asked = provider._learn_from_refusal(refusal(WINDOW_FULL), reserved, 16.38)
    assert provider.batch_output_ceiling() == 500 and asked >= 60.0
    assert provider._otpm.wait_for(100, mt._monotonic()) > 0.0                    # the window is held, as the D-218 tests expect
    mt.reset_output_windows()


def test_the_too_large_form_is_learned_by_the_shared_path_translation_uses_too():
    """`_learn_from_refusal` serves translation as well: it learns the limit there too, and still returns the asked wait."""
    mt.reset_output_windows()
    provider = mt.GroqTranslationProvider("k", model="refusal-forms-f")
    reserved = provider._otpm.reserve(2048, mt._monotonic())
    assert provider._learn_from_refusal(refusal(REQUEST_TOO_LARGE), reserved, 7.0) == 7.0
    assert provider.batch_output_ceiling() == 500
    mt.reset_output_windows()


# -- through the real HTTP path of the provider and the pipeline, answered from the recorded sentences ---------------

import json  # noqa: E402

from tests.test_media_correction_per_cue import _hsk_cues, _world  # noqa: E402
from writing_coach import media_transcript_pipeline as pipeline_module  # noqa: E402
from writing_coach.media_segmentation import Cue  # noqa: E402


class Scripted:
    """`requests.post` answering from a script; every request body is kept so a test can read what was really asked."""

    def __init__(self, answers):
        self.answers, self.bodies = list(answers), []

    def post(self, url, **kwargs):
        body = kwargs["json"]
        self.bodies.append(body)
        answer = self.answers.pop(0) if self.answers else "echo"
        if answer != "echo":
            return answer
        lines = body["messages"][1]["content"].split("\n\n", 1)[1].split("\n")
        rows = [{"index": int(row.split("\t", 1)[0]), "text": row.split("\t", 1)[1], "reason": "no_change"} for row in lines]
        return FakeResponse({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"lines": rows})}}],
                             "usage": {"prompt_tokens": 100, "completion_tokens": 100}})


def real_pipeline(tmp_path, monkeypatch, answers, model):
    """The real provider and pipeline over a scripted HTTP answer, on a virtual clock: the provider's own pacing sleeps for the
    output-token window (`_pause`), which on the real clock would hold a test for a minute (it did, once)."""
    script = Scripted(answers)
    clock = [10_000.0]
    script.waits = []

    def pause(seconds):
        script.waits.append(seconds)
        clock[0] += max(0.0, seconds)

    monkeypatch.setattr(mt, "_monotonic", lambda: clock[0])
    monkeypatch.setattr(mt, "_pause", pause)
    monkeypatch.setattr(mt.requests, "post", script.post)
    mt.reset_output_windows()
    provider = mt.GroqTranslationProvider("k", model=model)
    store, entry, pipeline, slept = _world(tmp_path, provider, "zh")
    return script, provider, store, entry, pipeline, slept


def _sizes(script):
    return [len(body["messages"][1]["content"].split("\n\n", 1)[1].split("\n")) for body in script.bodies]


def test_a_request_too_large_refusal_is_retried_at_once_with_a_smaller_batch(tmp_path, monkeypatch):
    """The live sequence: the first request is refused as too large, no wait, then a smaller batch fits."""
    script, _, store, entry, pipeline, slept = real_pipeline(tmp_path, monkeypatch, [refusal(REQUEST_TOO_LARGE)], "refusal-forms-c")
    cues = _hsk_cues(24)
    lines, meta = pipeline._correct_transcript(store, entry, "b", cues, origin=pipeline_module.ORIGIN_ASR)
    sizes = _sizes(script)
    assert sizes[0] == 24 and sizes[1] < 24                                        # the retry is a smaller batch
    assert slept == []                                                             # and it did not wait
    assert script.bodies[1]["max_completion_tokens"] <= 500
    assert meta["transcript_correction_state"] == "applied" and [line.text for line in lines] == [cue.text for cue in cues]
    assert sum(sizes[1:]) == 24                                                    # every cue was asked once more, none lost
    # Later batches queue behind the minute's allowance inside the provider; each such wait stays within the per-wait cap.
    assert all(wait <= pipeline_module.CORRECTION_MAX_WAIT for wait in script.waits)
    assert sum(script.waits) <= pipeline_module.CORRECTION_MAX_TOTAL_WAIT
    mt.reset_output_windows()


def test_a_request_too_large_refusal_that_cannot_be_narrowed_is_not_retried(tmp_path, monkeypatch):
    """A single cue refused as too large: asking for the same thing again would be refused the same way."""
    script, _, store, entry, pipeline, slept = real_pipeline(
        tmp_path, monkeypatch, [refusal(REQUEST_TOO_LARGE), refusal(REQUEST_TOO_LARGE)], "refusal-forms-d")
    lines, meta = pipeline._correct_transcript(store, entry, "b", [Cue(0, 1000, "你好吗我很好")], origin=pipeline_module.ORIGIN_ASR)
    assert len(script.bodies) == 1 and slept == []
    assert meta["transcript_correction_state"] == "failed" and meta["transcript_correction_detail"] == "request_too_large"
    assert [line.text for line in lines] == ["你好吗我很好"]
    mt.reset_output_windows()


def test_the_window_full_refusal_keeps_its_named_wait_and_single_retry(tmp_path, monkeypatch):
    script, _, store, entry, pipeline, slept = real_pipeline(
        tmp_path, monkeypatch, [refusal(WINDOW_FULL, {"retry-after": "16"})], "refusal-forms-e")
    lines, meta = pipeline._correct_transcript(store, entry, "b", _hsk_cues(6), origin=pipeline_module.ORIGIN_ASR)
    assert len(slept) == 1 and slept[0] >= 16.0                                    # it waited, as D-218 requires
    assert meta["transcript_correction_state"] == "applied" and len(script.bodies) == 2
    mt.reset_output_windows()
