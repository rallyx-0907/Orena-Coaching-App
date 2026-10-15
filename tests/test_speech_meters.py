"""PR-MON-7D2: the speech and TTS meters, wired with enforcement off, and the no-double-charge matrix.

    standalone ASR               -> speech.transcribe (seconds)
    pronunciation exercise       -> pronunciation.audio
    remote speaking evaluation   -> speech.evaluate (seconds), only when a remote evaluator exists - none today
    standalone fresh learner TTS -> audio.tts (characters)
    Orena conversational voice   -> orena.message only

The three new meters have no catalogue window and no approved limit (H7-3): they are pending - never enforceable,
always the no-op ticket - so nothing a learner does changes until their limits are approved.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest

from writing_coach.product import quota
from writing_coach.product.quota import NULL_TICKET, PENDING_METERS

NEW = ("speech.transcribe", "speech.evaluate", "audio.tts")


class Recorder:
    """Stands in for `quota.admit`: records every admission and what its ticket did."""

    def __init__(self, *, refuse=None):
        self.admitted: list[dict] = []
        self.refuse = refuse

    @contextmanager
    def __call__(self, meter, *, units=1, request_digest="", idempotency_key=None):
        if self.refuse is not None:
            raise self.refuse
        row = {"meter": meter, "units": units, "digest": request_digest, "dispatched": False, "settled": None}
        self.admitted.append(row)

        class Ticket:
            def dispatch(self, _what):
                row["dispatched"] = True

            def settle(self, units, _why=""):
                row["settled"] = units

        try:
            yield Ticket()
        except BaseException:
            if row["settled"] is None:
                row["settled"] = 0 if row["dispatched"] else "released"
            raise


# ---- the pending meters activate nothing ------------------------------------------------------------------------------

def test_the_new_meters_carry_their_frozen_units_and_are_never_enforceable(monkeypatch):
    from writing_coach.billing.funding import NEW_METER_UNITS

    assert {key: NEW_METER_UNITS[key] for key in NEW} == PENDING_METERS
    for key in NEW:
        assert key not in quota.WIRED_METERS and key not in quota.ENFORCEABLE
    monkeypatch.setenv(quota.FLAG, "on")
    monkeypatch.setenv(quota.METERS_FLAG, ",".join(NEW))
    quota._clear_switch_cache()
    for key in NEW:
        assert quota.enforces(key) is False   # listing one enforces nothing
        assert quota.require_ready(key) is False
        quota.require_feature(key)
        assert quota.begin(key, units=5) is NULL_TICKET
        with quota.admit(key, units=5) as ticket:
            assert ticket is NULL_TICKET


def test_the_new_meters_are_not_plan_entitlements_or_credit_eligible():
    from writing_coach.billing.funding import CREDIT_ELIGIBLE_V1
    from writing_coach.product.catalog import METERS, PLANS

    for key in NEW:
        assert key not in METERS and key not in CREDIT_ELIGIBLE_V1
        assert all(key not in plan.entitlement_map() for plan in PLANS.values())


# ---- standalone ASR -> speech.transcribe; push-to-talk -> orena.message only -----------------------------------------

asr = pytest.importorskip("test_speech_transcribe_guard")


@pytest.fixture()
def room(monkeypatch):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    from writing_coach import speech_api
    from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX

    provider = asr.CountingAsr()
    speech_api.configure_speech_asr(provider)
    speech_api.reset_transcribe_brake()
    app = FastAPI()

    @app.middleware("http")
    async def learner(request: Request, call_next):
        user, language = USER_KEY_CTX.set("learner-1"), LANGUAGE_CODE_CTX.set("en")
        try:
            return await call_next(request)
        finally:
            LANGUAGE_CODE_CTX.reset(language)
            USER_KEY_CTX.reset(user)

    app.include_router(speech_api.router)
    client = TestClient(app)

    def send(audio, *, purpose=None):
        data = {"language": "en", **({"purpose": purpose} if purpose is not None else {})}
        return client.post("/api/speech/transcribe", data=data,
                           files={"file": ("recording.wav", audio, "audio/wav")})

    recorder = Recorder()
    monkeypatch.setattr(quota, "admit", recorder)
    yield provider, send, recorder
    speech_api.configure_speech_asr(None)
    speech_api.reset_transcribe_brake()


@asr.needs_ffmpeg
def test_standalone_transcription_is_admitted_in_seconds_before_the_provider(room):
    provider, send, recorder = room
    answer = send(asr.silent_wav(3.2))
    assert answer.status_code == 200 and len(provider.calls) == 1
    (row,) = recorder.admitted
    assert row["meter"] == "speech.transcribe" and row["units"] == 4 and row["dispatched"] is True
    assert row["settled"] == 4   # the provider reported no duration: what was measured and admitted


@asr.needs_ffmpeg
def test_the_seconds_the_provider_heard_are_settled_never_more_than_admitted(room, monkeypatch):
    from writing_coach.speech_asr import SpeechAsrResult

    provider, send, recorder = room

    def heard(*_args, **_kwargs):
        return SpeechAsrResult(provider="fake-asr", model="fake", language="en", text="hi", segments=(), words=(),
                               duration_seconds=2.4)

    monkeypatch.setattr(provider, "transcribe_bytes", heard)
    assert send(asr.silent_wav(3.2)).status_code == 200
    (row,) = recorder.admitted
    assert row["units"] == 4 and row["settled"] == 3   # what the provider heard, rounded up, never above admitted


@asr.needs_ffmpeg
def test_a_provider_failure_after_dispatch_charges_nothing(room, monkeypatch):
    from writing_coach.speech_asr import SpeechAsrRequestFailed

    provider, send, recorder = room

    def failing(*_a, **_k):
        raise SpeechAsrRequestFailed("down")

    monkeypatch.setattr(provider, "transcribe_bytes", failing)
    assert send(asr.silent_wav(2)).status_code == 502
    (row,) = recorder.admitted
    assert row["dispatched"] is True and row["settled"] == 0


@asr.needs_ffmpeg
def test_a_refusal_at_admission_never_reaches_the_provider(room, monkeypatch):
    from writing_coach.core.errors import orena_http_error

    provider, send, _recorder = room
    monkeypatch.setattr(quota, "admit", Recorder(refuse=orena_http_error(429, "quota_exhausted", "No.")))
    assert send(asr.silent_wav(2)).status_code == 429
    assert provider.calls == []


@asr.needs_ffmpeg
def test_push_to_talk_is_never_charged_as_a_transcription(room):
    provider, send, recorder = room
    assert send(asr.silent_wav(2), purpose="orena_voice").status_code == 200
    assert len(provider.calls) == 1 and recorder.admitted == []   # the agent turn charges the orena.message


# ---- speech.evaluate: contract only (no remote evaluator) -------------------------------------------------------------

def test_speaking_evaluation_calls_no_provider_and_admits_nothing(monkeypatch):
    from writing_coach import speech_api

    recorder = Recorder()
    monkeypatch.setattr(quota, "admit", recorder)
    monkeypatch.setattr(quota, "begin", lambda *a, **k: pytest.fail("speaking evaluation admitted a meter"))
    source = speech_api.evaluate_speaking.__code__.co_names
    assert "admit" not in source and "begin" not in source
    from writing_coach import speaking_evaluator

    assert "provider" not in speaking_evaluator.build_speaking_evaluation.__code__.co_varnames
    assert recorder.admitted == []


# ---- fresh learner TTS -> audio.tts; cached and free audio is never charged -------------------------------------------

tts = pytest.importorskip("test_word_audio_azure")


def test_a_fresh_synthesis_is_admitted_in_billed_characters(monkeypatch):
    from writing_coach.word_audio_azure import billed_characters

    recorder = Recorder()
    monkeypatch.setattr(quota, "admit", recorder)
    spoken = tts.voice().speak(term="花生", language="zh", reading="huā shēng", single_reading=True)
    assert spoken is not None
    (row,) = recorder.admitted
    assert row["meter"] == "audio.tts" and row["units"] == billed_characters("花生") == 4
    assert row["dispatched"] is True and row["settled"] == 4


def test_a_failed_synthesis_charges_nothing(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(quota, "admit", recorder)
    assert tts.voice(wire=tts.Wire(fail=True)).speak(term="word", language="en", reading="", single_reading=True) is None
    (row,) = recorder.admitted
    assert row["settled"] == 0


def test_no_admission_when_the_paid_voice_is_not_asked(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(quota, "admit", recorder)
    assert tts.voice(spent=9.0, cap=5.0).speak(term="word", language="en", reading="", single_reading=True) is None
    assert tts.voice().speak(term="word", language="en", reading="", single_reading=False) is None
    assert recorder.admitted == []   # the cap, or a reading it cannot be told: no synthesis, no charge


def test_cached_audio_is_never_charged(monkeypatch, tmp_path):
    from writing_coach.book_asset_store import FilesystemBookAssetStore
    from writing_coach.word_audio import WordAudioLibrary

    recorder = Recorder()
    monkeypatch.setattr(quota, "admit", recorder)
    library = WordAudioLibrary(FilesystemBookAssetStore(tmp_path), voices=(tts.voice(),))
    first = library.pronounce(term="word", language="en", reading="", identity_key="en:word", single_reading=True)
    again = library.pronounce(term="word", language="en", reading="", identity_key="en:word", single_reading=True)
    assert first is not None and again is not None
    assert len(recorder.admitted) == 1   # the synthesis; the stored audio is served without a charge


# ---- Orena conversational voice -> orena.message only -------------------------------------------------------------------

def test_conversational_voice_is_charged_only_as_orena_messages():
    from writing_coach.agent import voice_session

    assert voice_session.VOICE_METER == "orena.message"
    names = voice_session.VoiceService._mint_chunk.__code__.co_consts
    assert not {"speech.transcribe", "audio.tts"} & set(map(str, names))
