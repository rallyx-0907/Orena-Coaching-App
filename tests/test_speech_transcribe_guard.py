"""D-16T: the guard on `POST /api/speech/transcribe` - a take is at most five minutes (measured on the server), an account
sends at most an hour of audio a day, and Orena's push-to-talk is refused before transcribing when no Orena message is left.
No plan meter is added or used for the transcription itself.

The provider is a counting fake, so "Groq was not called" is asserted. The audio is real (silent WAV made here, decoded
by ffmpeg like any recording), so the server really measures it.
"""
from __future__ import annotations

import io
import shutil
import wave

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from test_quota_gate import enforced_runtime  # noqa: E402
from test_quota_orena_message import _isolated, spend, totals  # noqa: E402,F401  (fixture)

from writing_coach import speech_api  # noqa: E402
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX  # noqa: E402
from writing_coach.product import quota  # noqa: E402
from writing_coach.speech_asr import SpeechAsrResult  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed here")
pytestmark = needs_ffmpeg
ENV = {quota.FLAG: "on", quota.METERS_FLAG: "orena.message"}


def silent_wav(seconds: float, rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\x00\x00" * int(seconds * rate))
    return buffer.getvalue()


class CountingAsr:
    provider_id = "fake-asr"
    model = "fake"
    max_bytes = 24 * 1024 * 1024

    def __init__(self):
        self.calls = []

    def transcribe_bytes(self, audio_bytes, *, filename, content_type, language):
        self.calls.append(len(audio_bytes))
        return SpeechAsrResult(provider="fake-asr", model="fake", language=language or "en", text="hello there",
                               segments=(), words=())


@pytest.fixture()
def room():
    provider = CountingAsr()
    speech_api.configure_speech_asr(provider)
    speech_api.reset_transcribe_brake()
    app = FastAPI()

    @app.middleware("http")
    async def learner(request: Request, call_next):
        user = USER_KEY_CTX.set(request.headers.get("x-test-user", "learner-1"))
        language = LANGUAGE_CODE_CTX.set("en")
        try:
            return await call_next(request)
        finally:
            LANGUAGE_CODE_CTX.reset(language)
            USER_KEY_CTX.reset(user)

    app.add_middleware(quota.QuotaRequestMiddleware)
    app.include_router(speech_api.router)
    client = TestClient(app)

    def send(audio, *, purpose=None, user="learner-1", language="en"):
        data = {"language": language, **({"purpose": purpose} if purpose is not None else {})}
        return client.post("/api/speech/transcribe", data=data, headers={"x-test-user": user},
                           files={"file": ("recording.wav", audio, "audio/wav")})

    yield provider, send
    speech_api.configure_speech_asr(None)
    speech_api.reset_transcribe_brake()


# ------------------------------------------------------------------------------------------ one take --

def test_a_normal_take_is_transcribed(room):
    provider, send = room
    answer = send(silent_wav(3))
    assert answer.status_code == 200 and answer.json()["text"] == "hello there"
    assert len(provider.calls) == 1


def test_the_server_measures_the_take_and_refuses_more_than_five_minutes(room):
    provider, send = room
    assert send(silent_wav(299)).status_code == 200
    long = send(silent_wav(305))
    assert long.status_code == 413 and long.json()["detail"]["category"] == "speech_asr_take_too_long"
    assert len(provider.calls) == 1, "the provider never saw the long take"


def test_a_take_is_measured_by_decoding_it_not_by_trusting_its_container():
    assert speech_api.take_seconds(silent_wav(2.5)) == pytest.approx(2.5, abs=0.05)
    assert speech_api.take_seconds(silent_wav(400)) == pytest.approx(speech_api.TRANSCRIBE_MAX_SECONDS + 1, abs=0.1), \
        "decoding stops a second past the limit, so a long file costs no more than a short one"
    with pytest.raises(speech_api.TakeUnreadable):
        speech_api.take_seconds(b"this is not audio")
    with pytest.raises(speech_api.TakeUnreadable):
        speech_api.take_seconds(b"")


def moov_at_end_mp4(seconds: float = 3.0) -> bytes:
    """An MP4 as a phone writes one: the `moov` index after the media data, so it cannot be read from a pipe."""
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "take.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={seconds}", "-c:a", "aac", "-f", "mp4", str(target)], check=True)
        data = target.read_bytes()
    assert data.index(b"moov") > data.index(b"mdat"), "the fixture must have its index at the end"
    return data


def test_an_mp4_with_its_index_at_the_end_is_measured_and_transcribed(room):
    """A recording from a device that writes the moov atom last (iPhone Safari) must not be refused as unreadable."""
    provider, send = room
    take = moov_at_end_mp4(3.0)
    assert speech_api.take_seconds(take) == pytest.approx(3.0, abs=0.2)
    answer = send(take, purpose=None)
    assert answer.status_code == 200 and answer.json()["text"] == "hello there"
    assert len(provider.calls) == 1
    # and the too-long case is still caught for the same container
    assert send(moov_at_end_mp4(310.0)).status_code == 413


def test_the_decode_leaves_no_file_behind():
    import tempfile
    from pathlib import Path

    before = {p.name for p in Path(tempfile.gettempdir()).glob("orena-transcribe-*")}
    speech_api.take_seconds(silent_wav(1))
    with pytest.raises(speech_api.TakeUnreadable):
        speech_api.take_seconds(b"not audio")
    assert {p.name for p in Path(tempfile.gettempdir()).glob("orena-transcribe-*")} == before


def test_audio_the_server_cannot_decode_is_refused(room):
    provider, send = room
    bad = send(b"this is not audio at all, just text")
    assert bad.status_code == 422 and bad.json()["detail"]["category"] == "speech_asr_unprocessable_audio"
    assert provider.calls == []


def test_an_upload_past_the_byte_ceiling_is_refused_before_it_is_decoded(room):
    provider, send = room
    big = send(b"\x00" * (speech_api.TRANSCRIBE_MAX_BYTES + 1024))
    assert big.status_code == 413 and big.json()["detail"]["category"] == "speech_asr_payload_too_large"
    assert provider.calls == []


def test_the_providers_own_larger_limit_is_untouched_for_the_media_pipeline(room):
    provider, _send = room
    assert provider.max_bytes > speech_api.TRANSCRIBE_MAX_BYTES, "the route caps itself; the provider keeps its 24 MiB"


def test_an_unknown_purpose_is_refused(room):
    provider, send = room
    refused = send(silent_wav(2), purpose="free_money")
    assert refused.status_code == 422 and refused.json()["detail"]["category"] == "speech_asr_invalid_purpose"
    assert provider.calls == []


# ---------------------------------------------------------------------------------------- the daily brake --

def test_an_account_can_send_an_hour_of_audio_a_day_and_no_more(room):
    provider, send = room
    speech_api.reset_transcribe_brake(25)  # seconds: two takes of 10 s (the provider's minimum) fit, a third does not
    assert send(silent_wav(3)).status_code == 200  # a 3 s take counts as the 10 s the provider bills
    assert send(silent_wav(10)).status_code == 200
    third = send(silent_wav(3))
    assert third.status_code == 429 and third.json()["detail"]["category"] == "speech_asr_daily_limit"
    assert int(third.headers["Retry-After"]) >= 1
    assert len(provider.calls) == 2, "the third never reached the provider"
    assert send(silent_wav(3), user="learner-2").status_code == 200, "another account has its own hour"


def test_the_default_ceiling_is_an_hour():
    assert speech_api.TRANSCRIBE_DAILY_SECONDS == 3600 and speech_api.TRANSCRIBE_MAX_SECONDS == 300


def test_the_brake_is_a_sliding_day():
    now = [0.0]
    brake = speech_api.DailySecondsBrake(100, window_seconds=1000, clock=lambda: now[0])
    assert brake.take("a", 60) is None
    now[0] = 400
    assert brake.take("a", 60) == pytest.approx(600), "wait until the first take has aged out"
    now[0] = 1001
    assert brake.take("a", 60) is None, "the first take is a day old"
    assert brake.take("b", 100) is None and brake.take("b", 1) is not None


# ----------------------------------------------------------------------------------- push-to-talk check --

def test_push_to_talk_with_no_message_left_is_refused_before_anything_is_transcribed(room):
    provider, send = room
    repository = enforced_runtime(env=ENV)
    spend(20)
    refused = send(silent_wav(3), purpose="orena_voice")
    assert refused.status_code == 429
    assert refused.json()["detail"]["category"] == "quota_exhausted"
    assert refused.json()["detail"]["context"]["feature"] == "orena.message"
    assert provider.calls == [], "no audio was read, decoded or sent to the provider"
    assert totals(repository) == (20, 0)


def test_push_to_talk_with_a_message_left_transcribes_and_reserves_nothing(room):
    provider, send = room
    repository = enforced_runtime(env=ENV)
    spend(19)
    before = list(repository.calls)
    answer = send(silent_wav(3), purpose="orena_voice")
    assert answer.status_code == 200 and len(provider.calls) == 1
    assert "reserve" not in repository.calls[len(before):], "a read-only peek: the message is charged when it is sent as a turn"
    assert totals(repository) == (19, 0)


def test_push_to_talk_cannot_be_checked_when_enforcement_is_unreadable_so_it_is_refused(room):
    provider, send = room
    quota.configure_quota(env=ENV, reason="no_store")
    refused = send(silent_wav(3), purpose="orena_voice")
    assert refused.status_code == 503 and refused.json()["detail"]["category"] == "quota_unavailable"
    assert provider.calls == []


def test_a_speaking_room_take_is_never_checked_against_orena_messages(room):
    provider, send = room
    repository = enforced_runtime(env=ENV)
    spend(20)
    before = list(repository.calls)
    assert send(silent_wav(3)).status_code == 200, "a draft for the learner to read is not an Orena message"
    assert repository.calls == before
    assert len(provider.calls) == 1
