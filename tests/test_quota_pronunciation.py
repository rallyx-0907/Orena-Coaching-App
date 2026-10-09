"""D-16Z `pronunciation.audio` enforcement, hermetic (CI, SQLite): `POST /api/speech/pronunciation`.

The meter is the take's real length in seconds. The quota store is the in-memory TEST DOUBLE of
`tests/test_quota_gate.py` (never a runtime store); the provider is either a scripted fake (so "the provider was not
called" is counted, not inferred) or the real Azure adapter over a fake HTTP session and a fake decoder (so the
chain prepare -> reserve -> request -> settle, and the AI cost ledger row, are the production code). The same
behaviour against real PostgreSQL is proved in `tests/test_quota_pronunciation_postgres.py`.
"""
from __future__ import annotations

import concurrent.futures
import shutil
import struct
import subprocess
import threading
import time
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from test_quota_gate import FakeQuotaRepository, enforced_runtime  # noqa: E402

from writing_coach import speech_api  # noqa: E402
from writing_coach.ai import platform as ai_platform  # noqa: E402
from writing_coach.ai.base import sanitize_telemetry  # noqa: E402
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store  # noqa: E402
from writing_coach.speech_pronunciation import (  # noqa: E402
    MAX_ASSESSED_SECONDS,
    AzureSpeechPronunciationProvider,
    PreparedAudio,
    SpeechPronunciationConversionFailed,
    SpeechPronunciationMalformed,
    SpeechPronunciationNoSpeech,
    SpeechPronunciationRequestFailed,
    SpeechPronunciationResult,
    SpeechPronunciationTimedOut,
    wav_seconds,
)

METER = "pronunciation.audio"
ENV = {quota.FLAG: "on", quota.METERS_FLAG: METER}
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
FREE_LIMIT = 300  # seconds: 5 minutes a month


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    previous = quota.runtime()
    configure_plan_store(None)
    monkeypatch.delenv(quota.FLAG, raising=False)
    monkeypatch.delenv(quota.METERS_FLAG, raising=False)
    yield
    speech_api.configure_speech_pronunciation(None)
    configure_plan_store(None)
    quota.configure_quota(**{field: getattr(previous, field) for field in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def wav(seconds: float) -> bytes:
    """A real 16 kHz mono 16-bit WAV with a LIST chunk before `data`, as ffmpeg writes it."""
    data = b"\0\0" * int(round(seconds * 16000))
    fmt = struct.pack("<HHIIHH", 1, 1, 16000, 32000, 2, 16)
    info = b"INFOISFT" + struct.pack("<I", 14) + b"Lavf60.16.100\0"
    body = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"LIST" + struct.pack("<I", len(info)) + info
            + b"data" + struct.pack("<I", len(data)) + data)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def take(seconds: float, tag: str = "") -> bytes:
    """What the learner uploads: the fake decoder reads the length out of it."""
    return f"take:{seconds}:{tag}".encode()


def decode(data: bytes, **_: Any) -> bytes:
    if data == b"bad":
        raise SpeechPronunciationConversionFailed()
    return wav(float(data.split(b":")[1]))


SCORED = {"DisplayText": "Good morning.", "NBest": [{"Display": "Good morning.", "AccuracyScore": 91, "FluencyScore": 82,
          "CompletenessScore": 100, "PronScore": 90, "Words": [{"Word": "morning", "AccuracyScore": 58,
          "ErrorType": "None", "Phonemes": []}]}]}  # fmt: skip
SILENT = {"NBest": [{"PronScore": 0, "AccuracyScore": 0, "FluencyScore": 0, "CompletenessScore": 0,
          "Words": [{"Word": "good", "AccuracyScore": 0, "ErrorType": "Omission"}]}]}  # fmt: skip


class _Response:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class AzureSession:
    """The HTTP session under the real Azure adapter; counts what reached 'Azure'."""

    def __init__(self, status: int = 200, payload: Any = SCORED) -> None:
        self.status, self.payload, self.posts = status, payload, 0
        self._lock = threading.Lock()

    def post(self, url: str, **kwargs: Any) -> _Response:
        with self._lock:
            self.posts += 1
        return _Response(self.status, self.payload)


def azure(session: AzureSession) -> AzureSpeechPronunciationProvider:
    return AzureSpeechPronunciationProvider("secret", "eastus", session=session, normalizer=decode)  # type: ignore[arg-type]


def measured(seconds: float | None) -> SpeechPronunciationResult:
    return SpeechPronunciationResult(
        provider="scripted", score_kind="measured", locale="en-US", recognized_text="Good morning.", pron_score=70.0,
        accuracy_score=72.0, fluency_score=80.0, completeness_score=100.0, prosody_score=None, words=(),
        audio_seconds=seconds)


class ScriptedProvider:
    """A provider that measures ahead (`prepare_audio`) and records every paid call."""

    provider_id = "scripted"
    max_bytes = 8 * 1024 * 1024
    max_reference_chars = 1200

    def __init__(self, outcome: Any = None) -> None:
        self.outcome = outcome
        self.prepared = 0
        self.calls = 0
        self._lock = threading.Lock()

    def prepare_audio(self, audio_bytes: bytes) -> PreparedAudio:
        self.prepared += 1
        return PreparedAudio(data=audio_bytes, seconds=float(audio_bytes.split(b":")[1]))

    def assess_bytes(self, audio_bytes: bytes, *, prepared: PreparedAudio | None = None, **kwargs: Any):
        with self._lock:
            self.calls += 1
        assert prepared is not None and prepared.data == audio_bytes, "the take is decoded once, before reserving"
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome or measured(prepared.seconds)


class UnmeasuringProvider:
    """No `prepare_audio`: the length is unknown before the call."""

    provider_id = "unmeasuring"
    max_bytes = 8 * 1024 * 1024
    max_reference_chars = 1200

    def __init__(self, result: SpeechPronunciationResult) -> None:
        self.result, self.calls = result, 0

    def assess_bytes(self, audio_bytes: bytes, **kwargs: Any):
        self.calls += 1
        return self.result


def build_client() -> TestClient:
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
    return TestClient(app)


def assess(client: TestClient, audio: bytes, *, key: str | None = None, reference: str = "Good morning.",
           mode: str = "scripted", headers: dict[str, str] | None = None):
    headers = {**(headers or {}), **({"Idempotency-Key": key} if key else {})}
    return client.post(
        "/api/speech/pronunciation", headers=headers,
        files={"file": ("take.webm", audio, "audio/webm")},
        data={"language": "en", "reference_text": reference, "mode": mode},
    )


def bucket(repo: FakeQuotaRepository) -> dict[str, Any] | None:
    found = [b for (_inc, meter, _w), b in repo.buckets.items() if meter == METER]
    return found[0] if found else None


def used(repo: FakeQuotaRepository) -> int:
    row = bucket(repo)
    return 0 if row is None else row["consumed"] + row["reserved"]


def spend(seconds: int, *, prefix: str = "spend") -> None:
    """Earlier use of this month's allowance (the learner-1 account)."""
    token = USER_KEY_CTX.set("learner-1")
    try:
        with quota.admit(METER, units=seconds, request_digest=prefix) as ticket:
            ticket.dispatch("p")
            ticket.settle(seconds)
    finally:
        USER_KEY_CTX.reset(token)


@pytest.fixture()
def recorded(monkeypatch):
    rows: list[dict[str, Any]] = []
    monkeypatch.setattr(ai_platform, "_persist_operation_telemetry", lambda event: rows.append(sanitize_telemetry(event)))
    return rows


# --------------------------------------------------------------- units --

def test_a_started_second_is_a_used_second_and_a_float_sliver_is_not():
    to_units = speech_api._seconds_to_units
    assert [to_units(x) for x in (0, 0.2, 7.0, 7.0004, 7.4, 7.9996, 59.2, 60.0)] == [0, 1, 7, 7, 8, 8, 60, 60]


def test_the_decoded_take_is_measured_from_its_data_chunk_with_or_without_a_header():
    assert wav_seconds(wav(7.4)) == pytest.approx(7.4)
    assert wav_seconds(b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 32 + b"\0" * 64000) == 2.0, "a bare 44-byte header"
    assert wav_seconds(b"") == 0.0


# ------------------------------------------------------- not enforced --

def test_not_enforced_is_exactly_the_unmetered_path_and_writes_nothing():
    repo = enforced_runtime(env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(7.4))
    assert answer.status_code == 200 and session.posts == 1
    assert repo.calls == [] and bucket(repo) is None, "no bucket, no read, no reservation"


def test_the_switch_off_changes_nothing_even_with_the_store_down():
    quota.configure_quota(env={quota.FLAG: "off"}, reason="no_postgresql")
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    assert assess(build_client(), take(3)).status_code == 200 and session.posts == 1


# ---------------------------------------------------------- the meter --

def test_the_charge_is_the_real_audio_seconds_not_the_click():
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    assert assess(client, take(7.4)).status_code == 200
    assert used(repo) == 8, "7.4 s of audio is 8 s"
    assert assess(client, take(0.5, "b")).status_code == 200
    assert used(repo) == 9, "a half second is one"
    assert assess(client, take(44.0, "c")).status_code == 200
    assert used(repo) == 53, "a long take costs its length, a short one its own"
    assert session.posts == 3
    assert repo.calls.count("reserve") == 3 and [c for c in repo.calls if c.startswith("settle")] == [
        "settle:8", "settle:1", "settle:44"]
    row = bucket(repo)
    assert (row["consumed"], row["reserved"], row["unit_limit"]) == (53, 0, FREE_LIMIT)


def test_the_settled_seconds_are_what_the_provider_reports_and_the_rest_is_released():
    repo = enforced_runtime(env=ENV)
    provider = ScriptedProvider(measured(5.2))  # reserved 8 (an 7.4 s decode), the provider processed 5.2
    speech_api.configure_speech_pronunciation(provider)
    assert assess(build_client(), take(7.4)).status_code == 200
    assert used(repo) == 6 and bucket(repo)["reserved"] == 0
    assert "settle:6" in repo.calls


def test_a_take_longer_than_the_limit_reserves_and_settles_at_most_the_limit():
    repo = enforced_runtime(env=ENV)
    provider = ScriptedProvider(measured(75.0))
    speech_api.configure_speech_pronunciation(provider)
    assert assess(build_client(), take(75.0)).status_code == 200
    assert used(repo) == MAX_ASSESSED_SECONDS == 60


def test_an_empty_decode_is_refused_before_any_reservation_or_provider_call():
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(0.0))
    assert answer.status_code == 422 and answer.json()["detail"]["category"] == "pronunciation_audio_empty"
    assert session.posts == 0 and "reserve" not in repo.calls


def test_undecodable_audio_is_the_learners_422_and_costs_nothing():
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), b"bad")
    assert answer.status_code == 422 and answer.json()["detail"]["category"] == "pronunciation_audio_unsupported"
    assert session.posts == 0 and "reserve" not in repo.calls and used(repo) == 0


# ---------------------------------------------------------- exhausted --

def test_exhausted_is_429_before_the_provider_with_the_bucket_truth():
    repo = enforced_runtime(env=ENV)
    spend(FREE_LIMIT)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(3.0))
    assert answer.status_code == 429
    detail = answer.json()["detail"]
    assert detail["category"] == "quota_exhausted"
    context = detail["context"]
    assert (context["feature"], context["used"], context["limit"]) == (METER, FREE_LIMIT, FREE_LIMIT)
    assert (context["unit"], context["display_unit"], context["scale"], context["window"]) == ("second", "minute", 60, "month")
    assert context["upgrade"] == "#/plan/pricing" and context["resets_at"] == "2026-11-01T00:00:00Z"
    assert int(answer.headers["Retry-After"]) > 0
    assert session.posts == 0, "the paid provider was not called"
    assert used(repo) == FREE_LIMIT


def test_a_take_needing_more_than_remains_is_refused_not_partially_assessed():
    repo = enforced_runtime(env=ENV)
    spend(FREE_LIMIT - 5)  # 5 s left
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    refused = assess(client, take(7.4))
    assert refused.status_code == 429 and session.posts == 0
    assert refused.json()["detail"]["context"]["used"] == FREE_LIMIT - 5
    assert used(repo) == FREE_LIMIT - 5, "nothing was taken from the allowance"
    fits = assess(client, take(4.2, "b"))
    assert fits.status_code == 200 and session.posts == 1 and used(repo) == FREE_LIMIT, "5 s left, a 4.2 s take fits"


def test_five_concurrent_takes_on_the_last_seconds_never_overspend():
    repo = enforced_runtime(env=ENV)
    spend(FREE_LIMIT - 10)  # 10 s left; each take is 6 s, so exactly one fits
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    barrier = threading.Barrier(5)

    def one(n: int):
        barrier.wait(timeout=10)
        return assess(client, take(5.5, str(n)), key=f"take-{n}")

    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(one, range(5)))
    assert sorted(a.status_code for a in answers) == [200, 429, 429, 429, 429]
    assert session.posts == 1
    row = bucket(repo)
    assert (row["consumed"], row["reserved"]) == (FREE_LIMIT - 10 + 6, 0) and row["consumed"] <= FREE_LIMIT


# ---------------------------------------------------------- failures --

@pytest.mark.parametrize("session,category", [
    (AzureSession(500, {"error": "boom"}), "pronunciation_provider_failure"),
    (AzureSession(401, {"error": "no"}), "pronunciation_auth"),
    (AzureSession(200, ValueError("not json")), "pronunciation_provider_malformed"),
    (AzureSession(200, {"NBest": []}), "pronunciation_provider_malformed"),
])
def test_a_provider_failure_or_an_unusable_result_costs_the_learner_nothing(session, category, recorded):
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(9.0))
    assert answer.status_code == 502 and answer.json()["detail"]["category"] == category
    assert session.posts == 1
    assert used(repo) == 0, "nothing was charged"
    assert bucket(repo)["consumed"] == 0 and bucket(repo)["reserved"] == 0
    assert "settle:0" in repo.calls
    if session.status == 200:  # Azure answered, so it billed: that spend is in the cost ledger, not the allowance
        assert recorded[-1]["outcome"] == "success" and recorded[-1]["usage"]["audio_seconds"] == 9.0


def test_a_timeout_costs_nothing():
    repo = enforced_runtime(env=ENV)
    provider = ScriptedProvider(SpeechPronunciationTimedOut())
    speech_api.configure_speech_pronunciation(provider)
    answer = assess(build_client(), take(9.0))
    assert answer.status_code == 504 and used(repo) == 0 and provider.calls == 1


def test_a_silent_take_azure_processed_is_charged_its_seconds(monkeypatch, recorded):
    repo = enforced_runtime(env=ENV)
    session = AzureSession(200, SILENT)
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(3.2))
    assert answer.status_code == 422 and answer.json()["detail"]["category"] == "pronunciation_no_speech"
    assert used(repo) == 4, "Azure processed and billed 3.2 s of silence"
    assert recorded[-1]["usage"]["audio_seconds"] == 3.2 and recorded[-1]["cost"]["state"] == "estimated"


def test_a_silent_take_is_free_when_the_human_decides_so(monkeypatch):
    repo = enforced_runtime(env=ENV)
    monkeypatch.setattr(speech_api, "NO_SPEECH_CHARGED", False)
    speech_api.configure_speech_pronunciation(azure(AzureSession(200, SILENT)))
    assert assess(build_client(), take(3.2)).status_code == 422
    assert used(repo) == 0


def test_a_silent_take_of_a_provider_that_cannot_say_how_long_is_not_guessed():
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(ScriptedProvider(SpeechPronunciationNoSpeech()))
    assert assess(build_client(), take(3.2)).status_code == 422
    assert used(repo) == 4, "the decode measured it"
    repo2 = enforced_runtime(env=ENV)
    stub = UnmeasuringProvider(measured(None))

    def silent(*_a, **_k):
        raise SpeechPronunciationNoSpeech()

    stub.assess_bytes = silent  # type: ignore[method-assign]
    speech_api.configure_speech_pronunciation(stub)
    assert assess(build_client(), take(3.2, "x")).status_code == 422
    assert used(repo2) == 0


def test_a_malformed_provider_answer_without_measurement_costs_nothing():
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(ScriptedProvider(SpeechPronunciationMalformed()))
    assert assess(build_client(), take(6.0)).status_code == 502 and used(repo) == 0
    speech_api.configure_speech_pronunciation(ScriptedProvider(SpeechPronunciationRequestFailed(429)))
    assert assess(build_client(), take(6.0, "b")).status_code == 502 and used(repo) == 0


# ---------------------------------------------------------- idempotency --

def test_a_retry_of_the_same_take_is_never_charged_twice():
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    first = assess(client, take(7.4), key="take-1")
    assert first.status_code == 200
    again = assess(client, take(7.4), key="take-1")
    assert again.status_code == 409 and again.json()["detail"]["category"] == "operation_finished"
    assert session.posts == 1 and used(repo) == 8


def test_the_same_key_for_other_audio_or_another_line_is_another_operation_not_a_retry():
    """The operation is (account, meter, key, digest of the audio, language, line, mode): only the same take is a retry."""
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    assert assess(client, take(7.4), key="take-1").status_code == 200
    assert assess(client, take(7.4, "other"), key="take-1").status_code == 200
    assert assess(client, take(7.4), key="take-1", reference="Another line.").status_code == 200
    assert session.posts == 3 and used(repo) == 24
    assert assess(client, take(7.4), key="take-1").status_code == 409, "the first take, again, is the retry"
    assert session.posts == 3 and used(repo) == 24


def test_a_retry_that_arrives_while_the_first_is_in_flight_is_refused_and_not_charged():
    repo = enforced_runtime(env=ENV)
    gate, entered = threading.Event(), threading.Event()

    class Slow(AzureSession):
        def post(self, url: str, **kwargs: Any):
            entered.set()
            gate.wait(10)
            return super().post(url, **kwargs)

    session = Slow()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        first = pool.submit(assess, client, take(7.4), key="take-1")
        assert entered.wait(10)
        retry = assess(client, take(7.4), key="take-1")
        gate.set()
        assert first.result(10).status_code == 200
    assert retry.status_code == 409 and retry.json()["detail"]["category"] == "operation_in_progress"
    assert session.posts == 1 and used(repo) == 8


def test_a_failed_take_may_be_sent_again_under_a_new_key_and_is_charged_once():
    repo = enforced_runtime(env=ENV)
    session = AzureSession(500, {"error": "boom"})
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    assert assess(client, take(7.4), key="attempt-1").status_code == 502 and used(repo) == 0
    session.status, session.payload = 200, SCORED
    assert assess(client, take(7.4), key="attempt-2").status_code == 200
    assert used(repo) == 8 and session.posts == 2


# ---------------------------------------------------- fail closed (503) --

def test_enforcement_without_a_store_is_503_before_decoding_or_calling_anything():
    quota.configure_quota(env=ENV, reason="no_postgresql")
    session = AzureSession()
    decoded = []
    provider = AzureSpeechPronunciationProvider(
        "secret", "eastus", session=session,  # type: ignore[arg-type]
        normalizer=lambda data, **_: decoded.append(1) or decode(data))
    speech_api.configure_speech_pronunciation(provider)
    answer = assess(build_client(), take(3.0))
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert session.posts == 0 and decoded == []


def test_an_unreadable_catalogue_is_503_and_the_provider_is_not_called():
    from test_quota_gate import MemorySettings

    enforced_runtime(env=ENV)
    configure_plan_store(MemorySettings(fail=True))
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(3.0))
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert session.posts == 0


def test_a_failed_dispatch_is_503_and_the_provider_is_not_called():
    repo = enforced_runtime(env=ENV)
    repo.dispatch = lambda **_k: (_ for _ in ()).throw(RuntimeError("store down"))  # type: ignore[method-assign]
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(3.0))
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert session.posts == 0 and used(repo) == 0, "the reservation was released"


def test_a_plan_without_the_feature_is_403_not_unlimited():
    from test_quota_gate import MemorySettings

    stored = {"version": 2, "plans": [
        {"id": plan_id, "prices": {}, "entitlements": [{"key": METER, "enabled": plan_id != "free", "limit": 300}]}
        for plan_id in ("free", "plus", "pro")]}
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {"value": stored, "updated_at": "t"}}))
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(3.0))
    assert answer.status_code == 403 and answer.json()["detail"]["category"] == "feature_not_in_plan"
    assert session.posts == 0 and used(repo) == 0


# ------------------------------------------- providers that cannot measure --

def test_a_provider_that_cannot_measure_ahead_reserves_the_longest_take_and_settles_on_its_report():
    repo = enforced_runtime(env=ENV)
    stub = UnmeasuringProvider(measured(7.4))
    speech_api.configure_speech_pronunciation(stub)  # type: ignore[arg-type]
    assert assess(build_client(), b"anything").status_code == 200
    assert used(repo) == 8 and "settle:8" in repo.calls


def test_a_provider_that_cannot_measure_needs_the_longest_take_to_fit():
    repo = enforced_runtime(env=ENV)
    spend(FREE_LIMIT - 30)
    stub = UnmeasuringProvider(measured(7.4))
    speech_api.configure_speech_pronunciation(stub)  # type: ignore[arg-type]
    assert assess(build_client(), b"anything").status_code == 429
    assert stub.calls == 0 and used(repo) == FREE_LIMIT - 30


def test_a_measured_result_without_a_length_costs_the_reserved_bound_and_a_stand_in_costs_nothing():
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(UnmeasuringProvider(measured(None)))  # type: ignore[arg-type]
    assert assess(build_client(), b"anything").status_code == 200 and used(repo) == MAX_ASSESSED_SECONDS
    demo = measured(None)
    demo = SpeechPronunciationResult(**{**demo.__dict__, "score_kind": "synthetic_demo"})
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(UnmeasuringProvider(demo))  # type: ignore[arg-type]
    assert assess(build_client(), b"anything").status_code == 200 and used(repo) == 0


# --------------------------------------------- usage, telemetry, scope --

def test_plan_and_usage_reads_the_same_bucket_in_seconds_and_the_screen_shows_minutes():
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(azure(AzureSession()))
    client = build_client()
    assert assess(client, take(7.4)).status_code == 200
    assert assess(client, take(60.0, "b")).status_code == 200
    reading = quota.usage_for("learner-1", catalog.FREE)[METER]
    assert reading["state"] == "known" and reading["used"] == used(repo) == 68
    assert reading["resets_at"] == "2026-11-01T00:00:00Z" and reading["window_id"] == "M:2026-10@UTC"


def test_the_ai_ledger_gets_provider_model_seconds_and_usd_separately_from_the_allowance(recorded):
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(azure(AzureSession()))
    assert assess(build_client(), take(7.4)).status_code == 200
    row = recorded[-1]
    assert (row["capability"], row["provider"], row["model"], row["outcome"]) == (
        "pronunciation_evaluator", "azure-speech", "pronunciation-assessment", "success")
    assert row["usage"]["audio_seconds"] == 7.4, "the exact seconds Azure bills; the learner is charged 8"
    assert row["cost"]["state"] == "estimated" and row["cost"]["amount"] == round(8 * 1.32 / 3600, 8)  # Azure bills whole seconds
    assert used(repo) == 8


def test_a_local_decode_failure_is_still_a_ledger_row(recorded):
    enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(azure(AzureSession()))
    assert assess(build_client(), b"bad").status_code == 422
    assert recorded[-1]["outcome"] == "failure" and recorded[-1]["provider"] == "azure-speech"


def test_accounts_are_metered_apart_and_the_month_follows_the_learners_zone():
    repo = enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(azure(AzureSession()))
    client = build_client()
    assert assess(client, take(7.4), headers={"X-Orena-Timezone": "Asia/Ho_Chi_Minh"}).status_code == 200
    assert assess(client, take(7.4, "b"), headers={"x-test-user": "learner-2"}).status_code == 200
    windows = sorted(b["window_id"] for b in repo.buckets.values())
    assert windows == ["M:2026-10@Asia/Ho_Chi_Minh", "M:2026-10@UTC"]
    assert sorted(b["consumed"] for b in repo.buckets.values()) == [8, 8]


def test_the_validation_errors_come_before_any_quota_work():
    repo = enforced_runtime(env=ENV)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    empty = assess(client, b"")
    assert empty.status_code == 422 and empty.json()["detail"]["category"] == "pronunciation_audio_empty"
    blank = assess(client, take(3.0), reference="  ")
    assert blank.status_code == 422 and blank.json()["detail"]["category"] == "pronunciation_reference_invalid"
    assert repo.calls == [] and session.posts == 0


def test_the_switch_can_enforce_it_from_the_admin_setting():
    assert quota.validate_switch_setting({"enabled": True, "meters": [METER]}) == {"enabled": True, "meters": [METER]}
    assert METER in quota.SYNC_METERS, "the reconciler backstops an abandoned reservation"


# ------------------------------------------------ workers, real ffmpeg (review of #119) --

def test_assessments_hold_at_most_the_configured_worker_threads(monkeypatch):
    """A burst of assessments queues on its own limiter instead of taking every thread the other routes share."""
    monkeypatch.setenv(speech_api.PRONUNCIATION_WORKERS_ENV, "2")
    repo = enforced_runtime(env=ENV)
    live, peak = [0], [0]
    lock = threading.Lock()

    class Gauge(AzureSession):
        def post(self, url: str, **kwargs: Any):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.15)
            try:
                return super().post(url, **kwargs)
            finally:
                with lock:
                    live[0] -= 1

    session = Gauge()
    speech_api.configure_speech_pronunciation(azure(session))
    with build_client() as client:  # one event loop for every request, as in production
        with concurrent.futures.ThreadPoolExecutor(6) as pool:
            answers = list(pool.map(lambda n: assess(client, take(3.0, str(n)), key=f"w-{n}"), range(6)))
    assert [a.status_code for a in answers] == [200] * 6
    assert peak[0] == 2 and session.posts == 6
    assert used(repo) == 18


def test_a_bad_worker_setting_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv(speech_api.PRONUNCIATION_WORKERS_ENV, "many")
    enforced_runtime(env=ENV)
    speech_api.configure_speech_pronunciation(azure(AzureSession()))
    assert assess(build_client(), take(3.0)).status_code == 200


FFMPEG = shutil.which("ffmpeg")


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is not installed")
def test_real_ffmpeg_output_is_measured_by_its_data_chunk_and_carries_no_client_metadata(tmp_path):
    """The seconds reserved are the seconds of the bytes sent: proven on the real decoder, with a tag-laden input."""
    from writing_coach.speech_pronunciation import normalize_audio_to_pcm16_wav

    source = tmp_path / "client.wav"
    subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=7.4", "-ar", "44100", "-ac", "2",
         "-metadata", "title=CLIENT-CHOSEN-TEXT", "-metadata", "comment=" + "x" * 5000, str(source)],
        check=True,
    )
    sent = normalize_audio_to_pcm16_wav(source.read_bytes())
    assert b"CLIENT-CHOSEN-TEXT" not in sent and b"LIST" not in sent, "audio only goes to the provider"
    assert wav_seconds(sent) == pytest.approx(7.4, abs=0.001)
    assert speech_api._seconds_to_units(wav_seconds(sent)) == 8

    # The same decode WITH tags keeps ffmpeg's LIST chunk before `data`: still measured from the data chunk.
    tagged = tmp_path / "tagged.wav"
    subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(source), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(tagged)],
        check=True,
    )
    raw = tagged.read_bytes()
    assert b"LIST" in raw[:200] and b"CLIENT-CHOSEN-TEXT" in raw
    assert wav_seconds(raw) == pytest.approx(7.4, abs=0.001)
    assert len(raw) - 44 != int(wav_seconds(raw) * 32000), "the old len-44 formula would have been wrong here"

    longer = tmp_path / "long.wav"
    subprocess.run([FFMPEG, "-v", "error", "-f", "lavfi", "-i", "sine=duration=75", "-ar", "8000", "-ac", "1", str(longer)],
                   check=True)
    assert wav_seconds(normalize_audio_to_pcm16_wav(longer.read_bytes())) == pytest.approx(60.0, abs=0.001)
