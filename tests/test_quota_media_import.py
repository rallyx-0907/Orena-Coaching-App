"""D-16S `media.import` enforcement, hermetic (CI, SQLite): a learner's link or file, through the real routes, the real
importer, the real pipeline and the real quota core over the in-memory TEST DOUBLE repository of
`tests/test_quota_gate.py` (never a runtime store).

The meter is the minutes of SOURCE media a learner imports in their month, stored in seconds. Only the audio layer
(ffprobe / ffmpeg), the ASR provider, YouTube and the clock are scripted, so "the provider was not called" and "this
many seconds were reserved" are counted, not inferred. The same behaviour against real PostgreSQL is proved in
`tests/test_quota_media_import_postgres.py`.

The fake media is `MEDIA|<declared seconds>|<decoded seconds>|<tag>`: the container's declared length (what ffprobe
reports, the length a learner is charged by) and the length the decoder really finds.
"""
from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from test_quota_gate import FakeQuotaRepository, enforced_runtime  # noqa: E402

from writing_coach import media_api, media_library_api, media_quota, media_source_import, media_thumbnail  # noqa: E402
from writing_coach import media_transcript_pipeline as pipeline_mod  # noqa: E402
from writing_coach.book_asset_store import FilesystemBookAssetStore  # noqa: E402
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX  # noqa: E402
from writing_coach.media_ingestion import MediaAcquisition, MediaPlayback  # noqa: E402
from writing_coach.media_learning import (  # noqa: E402
    MediaLearningAsset,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)
from writing_coach.media_library_store import FileMediaLibraryStore, owner_token  # noqa: E402
from writing_coach.media_providers.youtube import youtube_embed_url  # noqa: E402
from writing_coach.media_source_import import MediaSourceImporter  # noqa: E402
from writing_coach.media_spend import SpendLedger  # noqa: E402
from writing_coach.media_thumbnail import MediaProbe  # noqa: E402
from writing_coach.media_transcript_pipeline import MediaPipeline  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store  # noqa: E402
from writing_coach.speech_asr import SpeechAsrRequestFailed, SpeechAsrResult, SpeechAsrSegment  # noqa: E402

METER = "media.import"
ENV = {quota.FLAG: "on", quota.METERS_FLAG: METER}
FREE_LIMIT = 900  # seconds: 15 minutes a month


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    previous = quota.runtime()
    decision = quota._async_decision  # the application wires one (app.py); a test decides for itself
    quota.configure_async_decision(None)
    configure_plan_store(None)
    monkeypatch.delenv(quota.FLAG, raising=False)
    monkeypatch.delenv(quota.METERS_FLAG, raising=False)
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_MODEL_CLIPS", "0")
    monkeypatch.setattr(media_quota.time, "sleep", lambda _seconds: None)
    yield
    quota.configure_async_decision(decision)
    configure_plan_store(None)
    quota.configure_quota(**{field: getattr(previous, field) for field in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


class Spy(FakeQuotaRepository):
    """The quota double, recording the settlements (with their outcome reference) and able to fail on demand."""

    def __init__(self) -> None:
        super().__init__()
        self.settled: list[tuple[str, int, str | None]] = []
        self.fail_settle = 0
        self.fail_dispatch = False

    def settle(self, *, operation_id, actual_units, outcome_ref=None):
        if self.fail_settle:
            self.fail_settle -= 1
            raise RuntimeError("quota store down")
        self.settled.append((operation_id, actual_units, outcome_ref))
        return super().settle(operation_id=operation_id, actual_units=actual_units, outcome_ref=outcome_ref)

    def dispatch(self, *, operation_id, dispatch_ref=None):
        if self.fail_dispatch:
            raise RuntimeError("quota store down")
        return super().dispatch(operation_id=operation_id, dispatch_ref=dispatch_ref)


def media(declared: float, decoded: float | None = None, tag: str = "a") -> bytes:
    return f"MEDIA|{declared}|{declared if decoded is None else decoded}|{tag}".encode()


def _lengths(data: bytes) -> tuple[float, float]:
    parts = data.split(b"|")
    return float(parts[1]), float(parts[2])


class FakeAsr:
    provider_id = "fake"

    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None
        self._lock = threading.Lock()

    def transcribe_bytes(self, body: bytes, *, filename: str, content_type: str, language: str | None):
        with self._lock:
            self.calls += 1
        if self.error is not None:
            raise self.error
        _declared, decoded = _lengths(body)
        segments = tuple(SpeechAsrSegment(f"This is the sentence number {index} about the market today.",
                                          index * 5000, index * 5000 + 4800) for index in range(int(decoded // 5)))
        return SpeechAsrResult("fake", "fake", "en", " ".join(item.text for item in segments), segments, (), decoded)


def video_id(n: int) -> str:
    return f"vid{n:08d}"


def video_url(n: int, host: str = "https://www.youtube.com/watch?v=") -> str:
    return f"{host}{video_id(n)}"


class FakeIngestion:
    """YouTube's public page and captions: free, and counted."""

    def __init__(self) -> None:
        self.calls = 0
        self.captions_seconds: int | None = 300

    def import_media(self, url: str, source_language: str, language: str) -> MediaAcquisition:
        from writing_coach.media_providers.youtube import parse_youtube_video_id

        self.calls += 1
        vid = parse_youtube_video_id(url)
        asset_id = f"youtube:{vid}"
        captions = self.captions_seconds
        transcript = MediaTranscript(asset_id, "en", tuple(
            TranscriptSegment(f"{asset_id}:segment:{index:04d}", index, index * 5000, index * 5000 + 4800,
                              f"This is the sentence number {index} about the market today.")
            for index in range(int(captions // 5)))) if captions else None
        asset = MediaLearningAsset(
            asset_id=asset_id, source_url=f"https://www.youtube.com/watch?v={vid}", source_provider="youtube",
            source_type="external-video", title="A walk to the market", source_language="en" if transcript else "und",
            processing_state=MediaProcessingState.READY, duration_ms=None, transcript_available=transcript is not None,
            translation_available=False)
        return MediaAcquisition(MediaLearningObject(asset, transcript),
                                MediaPlayback("youtube", "embed", youtube_embed_url(vid)))


class World:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repository: Spy | None = None) -> None:
        self.tmp = tmp_path
        self.repo = enforced_runtime(repository=repository or Spy(), env=ENV)
        self.store = FileMediaLibraryStore(tmp_path / "index")
        self.assets = FilesystemBookAssetStore(tmp_path / "assets")
        self.asr = FakeAsr()
        self.ingestion = FakeIngestion()
        self.youtube_seconds: float | None = 600.0
        self.youtube_decoded: float | None = None
        self.probed_files = 0
        self.probed_urls: list[str] = []
        self.pipeline = self.new_pipeline()
        self.importer = MediaSourceImporter(self.ingestion, self.store, self.assets, pipeline=self.pipeline,
                                            duration_probe=self._probe_youtube)
        monkeypatch.setattr(media_library_api, "_store", self.store)
        monkeypatch.setattr(media_library_api, "_asset_store", self.assets)
        monkeypatch.setattr(media_library_api, "_importer", self.importer)
        monkeypatch.setattr(media_library_api, "_learner_payload", self._payload)
        monkeypatch.setattr(media_library_api, "_language_supported", lambda code: code in {"en", "zh"})
        monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path / "media_temp")
        monkeypatch.setattr(media_source_import, "probe_media", self._probe_media)
        monkeypatch.setattr(MediaSourceImporter, "_persist_thumbnail", lambda *_a, **_k: "")
        monkeypatch.setattr(pipeline_mod, "audio_chunks", self._audio_chunks)
        monkeypatch.setattr(pipeline_mod, "_probe_seconds", lambda path: _lengths(Path(path).read_bytes())[1])
        self.client = self._client()

    def new_pipeline(self) -> MediaPipeline:
        return MediaPipeline(ledger=SpendLedger(self.tmp / "spend.json"), asr=self.asr, ingestion=self.ingestion,
                             youtube_audio=self._youtube_audio, workers=1)

    # -- the scripted outside world ---------------------------------------------------------------
    @staticmethod
    def _payload(media_id: str, _target: str) -> dict[str, Any] | None:
        """What the learner's room reads: whether the import is still going, failed, or ready."""
        entry = media_library_api.find_entry(media_id)
        if entry is None:
            return None
        state = (entry.processing or {}).get("state")
        shown = "failed" if state == "failed" else "processing" if state in ("queued", "running") else "ready"
        return {"media_id": entry.media_id, "asset": {"processing_state": shown}}

    def _probe_media(self, path: Path) -> MediaProbe:
        self.probed_files += 1
        data = Path(path).read_bytes()
        if not data.startswith(b"MEDIA|"):
            raise ValueError("The file is not audio or video media.")
        declared, _ = _lengths(data)
        return MediaProbe(duration_ms=round(declared * 1000), media_type="audio", width=None, height=None,
                          has_video=False, has_audio=True)

    def _probe_youtube(self, url: str) -> float | None:
        self.probed_urls.append(url)
        return self.youtube_seconds

    def _youtube_audio(self, url: str, work: Path, *, max_seconds: int) -> Path:
        decoded = self.youtube_decoded if self.youtube_decoded is not None else (self.youtube_seconds or 60.0)
        destination = Path(work) / "source.bin"
        destination.write_bytes(media(decoded, decoded, "yt"))
        return destination

    def _audio_chunks(self, source: Path, work: Path, chunk_seconds: int = 600):
        chunk = Path(work) / "chunk-000.mp3"
        chunk.write_bytes(Path(source).read_bytes())
        return [(chunk, 0.0)]

    # -- HTTP -------------------------------------------------------------------------------------
    def _client(self) -> TestClient:
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
        app.include_router(media_library_api.router)
        app.include_router(media_library_api.media_learning_router)
        app.include_router(media_api.router)
        return TestClient(app)

    def upload(self, data: bytes, *, user: str = "learner-1", extra: dict[str, str] | None = None, headers=None):
        return self.client.post(
            "/api/media-learning/upload", files={"file": ("lecture.mp3", data, "audio/mpeg")},
            data={"language": "en", **(extra or {})}, headers={"x-test-user": user, **(headers or {})})

    def source(self, url: str, *, user: str = "learner-1"):
        return self.client.post("/api/media-learning/source", json={"source_url": url, "target_language": "vi"},
                                headers={"x-test-user": user})

    # -- the books --------------------------------------------------------------------------------
    def bucket(self) -> dict[str, Any] | None:
        found = [b for (_inc, meter, _w), b in self.repo.buckets.items() if meter == METER]
        return found[0] if found else None

    def entries(self):
        return self.store.list(library="personal", status=None)

    def stored_files(self) -> list[Path]:
        return [item for item in (self.tmp / "assets").rglob("*") if item.is_file()] if (self.tmp / "assets").exists() else []

    def spend(self, seconds: int, user: str = "learner-1") -> None:
        from writing_coach.core.request_context import USER_KEY_CTX as ctx

        token = ctx.set(user)
        try:
            with quota.admit(METER, units=seconds, request_digest=f"spend-{seconds}") as ticket:
                ticket.dispatch("p")
                ticket.settle(seconds)
        finally:
            ctx.reset(token)


@pytest.fixture()
def world(tmp_path, monkeypatch) -> World:
    return World(tmp_path, monkeypatch)


# ===================================================================== refusal before work (all or nothing) ==

def test_an_upload_that_does_not_fit_is_refused_before_anything_is_stored_or_heard(world: World):
    world.spend(FREE_LIMIT - 10)
    answer = world.upload(media(20))
    assert answer.status_code == 429
    detail = answer.json()["detail"]
    assert detail["category"] == "quota_exhausted"
    assert (detail["context"]["feature"], detail["context"]["used"], detail["context"]["limit"]) == (METER, 890, FREE_LIMIT)
    assert (detail["context"]["unit"], detail["context"]["display_unit"], detail["context"]["scale"]) == ("second", "minute", 60)
    assert detail["context"]["upgrade"] == "#/plan/pricing" and "resets_at" in detail["context"]
    assert world.asr.calls == 0 and world.stored_files() == [] and world.entries() == []
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (890, 0), "all or nothing: nothing was reserved"


def test_a_link_that_does_not_fit_is_refused_before_its_page_or_captions_are_read(world: World):
    world.spend(FREE_LIMIT - 10)
    answer = world.source(video_url(1))
    assert answer.status_code == 429 and answer.json()["detail"]["category"] == "quota_exhausted"
    assert world.probed_urls == [video_url(1)], "only YouTube's length was asked"
    assert world.ingestion.calls == 0 and world.asr.calls == 0 and world.entries() == []
    assert world.bucket()["reserved"] == 0


def test_a_source_longer_than_the_allowance_can_ever_hold_is_refused_outright(world: World):
    world.youtube_seconds = 20 * 60
    answer = world.source(video_url(2))
    assert answer.status_code == 429 and answer.json()["detail"]["context"]["used"] == 0
    assert world.ingestion.calls == 0


# ============================================================ the length is the server's, never the client's ==

def test_the_reservation_is_the_stored_files_declared_length_whatever_the_client_says(world: World):
    answer = world.upload(media(61.2, 58.2), extra={"duration_ms": "1000", "duration": "1"},
                          headers={"X-Duration-Seconds": "1"})
    assert answer.status_code == 200, answer.text
    (operation, units), = [(op, row["units"]) for op, row in world.repo.reservations.items()]
    assert units == 62, "ceil(61.2)"
    assert world.repo.settled == [(operation, 59, "completed:generated_asr")], "settles the 58.2 s heard, rounded up"
    assert world.bucket()["consumed"] == 59 and world.bucket()["reserved"] == 0


def test_a_youtube_link_is_charged_by_youtubes_length_not_by_its_captions(world: World):
    world.youtube_seconds = 600.4
    assert world.source(video_url(3)).status_code == 200
    (row,) = world.repo.reservations.values()
    assert row["units"] == 601
    assert world.asr.calls == 0, "captions were free"


def test_captions_still_cost_the_learner_the_source_minutes(world: World):
    world.youtube_seconds = 600
    assert world.source(video_url(4)).status_code == 200
    (_op, actual, ref), = world.repo.settled
    assert (actual, ref) == (600, "completed:provider_caption")
    assert world.bucket()["consumed"] == 600 and world.asr.calls == 0


def test_when_youtubes_metadata_cannot_be_read_the_captions_length_is_used(world: World):
    world.youtube_seconds = None
    world.ingestion.captions_seconds = 300
    assert world.source(video_url(5)).status_code == 200
    (row,) = world.repo.reservations.values()
    assert row["units"] == 300, "the last caption ends at 299.8 s"


def test_an_unreadable_length_is_never_free(world: World):
    world.youtube_seconds = None
    world.ingestion.captions_seconds = None
    answer = world.source(video_url(6))
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "media_duration_unavailable"
    assert world.repo.reservations == {} and world.entries() == []


def test_a_file_with_no_readable_length_is_refused_as_invalid(world: World):
    answer = world.upload(media(0))
    assert answer.status_code == 422 and answer.json()["detail"]["category"] == "media_upload_invalid"
    assert world.repo.reservations == {} and world.stored_files() == []


def test_a_file_longer_than_the_pipeline_can_transcribe_is_refused_not_charged(world: World):
    answer = world.upload(media(5401))
    assert answer.status_code == 422 and answer.json()["detail"]["category"] == "media_upload_invalid"
    assert world.repo.reservations == {} and world.stored_files() == []


def test_a_long_youtube_video_reserves_at_most_what_the_pipeline_processes(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    quota.runtime().plan_for = lambda user_key, strict=False: catalog.plan_by_id("pro", strict=strict)
    world.youtube_seconds = 7200
    assert world.source(video_url(7)).status_code == 200
    (row,) = world.repo.reservations.values()
    assert row["units"] == 5400 == media_quota.max_import_seconds()


def test_units_round_up_to_a_whole_second_and_never_below_one():
    assert [media_quota.units_for(value) for value in (0.2, 59.0004, 59.0006, 60, 61.2)] == [1, 59, 60, 60, 62]
    for bad in (0, -3, float("nan"), float("inf"), None, True, "60"):
        with pytest.raises(Exception) as refused:
            media_quota.units_for(bad)
        assert refused.value.status_code == 503


# ============================================================================= settle: success, failure, 0 ==

def test_a_failed_import_settles_zero_and_the_learner_can_try_again(world: World):
    world.asr.error = SpeechAsrRequestFailed(500)
    first = world.upload(media(60))
    assert first.status_code == 200 and first.json()["asset"]["processing_state"] == "failed"
    assert world.asr.calls == 1
    (_op, actual, ref), = world.repo.settled
    assert (actual, ref) == (0, "failed:asr_failed")
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (0, 0), "a failure never charges"
    world.asr.error = None
    again = world.upload(media(60))
    assert again.status_code == 200 and again.json()["asset"]["processing_state"] != "failed"
    assert again.json()["media_id"] != first.json()["media_id"], "a failed import is not 'already imported'"
    assert world.bucket()["consumed"] == 60, "charged once, for the import that worked"


def test_an_unusable_transcript_settles_zero(world: World):
    answer = world.upload(media(100, 20))
    assert answer.json()["asset"]["processing_state"] == "failed"
    (_op, actual, ref), = world.repo.settled
    assert actual == 0 and ref == "failed:coverage_low"
    assert world.bucket()["consumed"] == 0


def test_audio_longer_than_the_reservation_is_stopped_before_it_is_heard(world: World):
    answer = world.upload(media(30, 90))
    assert answer.json()["asset"]["processing_state"] == "failed"
    assert world.asr.calls == 0, "no paid call for audio that is not the source that was admitted"
    (_op, actual, ref), = world.repo.settled
    assert (actual, ref) == (0, "failed:duration_mismatch")


def test_a_youtube_video_without_captions_is_heard_and_charged_for_what_was_decoded(world: World):
    world.ingestion.captions_seconds = None
    world.youtube_seconds = 100
    world.youtube_decoded = 99.2
    answer = world.source(video_url(8))
    assert answer.status_code == 200, answer.text
    assert world.asr.calls == 1
    (_op, actual, ref), = world.repo.settled
    assert (actual, ref) == (100, "completed:generated_asr"), "ceil(99.2)"
    assert world.bucket()["consumed"] == 100


def test_the_worker_starts_paid_work_only_against_a_live_reservation(world: World):
    world.repo.fail_dispatch = True
    answer = world.upload(media(60))
    assert answer.json()["asset"]["processing_state"] == "failed"
    assert world.asr.calls == 0
    (entry,) = world.entries()
    assert entry.processing["reason"] == "quota_unavailable"
    assert world.repo.settled[-1][1:] == (0, "failed:quota_unavailable")
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (0, 0)


# ============================================================================ restart: settle by operation id ==

def test_a_restart_before_the_job_ran_still_settles_by_operation_id(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    monkeypatch.setattr(world.pipeline, "_pool", type("Idle", (), {"submit": lambda *_a, **_k: None})())
    monkeypatch.delenv("MEDIA_PIPELINE_INLINE")
    answer = world.upload(media(120, 118.5))
    assert answer.status_code == 200 and answer.json()["asset"]["processing_state"] == "processing"
    (entry,) = world.entries()
    operation = entry.source[media_quota.SOURCE_OP]
    assert world.repo.reservations[operation]["state"] == "reserved" and world.bucket()["reserved"] == 120
    assert world.asr.calls == 0
    # "The process died": a new pipeline, a new process, the same index and the same quota store.
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    restarted = world.new_pipeline()
    assert restarted.recover(world.store, world.assets) == 1
    assert world.asr.calls == 1
    assert world.repo.reservations[operation]["state"] == "settled"
    assert world.repo.settled == [(operation, 119, "completed:generated_asr")]
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (119, 0)
    assert world.store.get(entry.media_id).source[media_quota.SOURCE_SETTLE] == media_quota.SETTLED


def test_a_settlement_the_store_could_not_take_is_written_by_the_next_restart(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    world.repo.fail_settle = 99
    answer = world.upload(media(60))
    assert answer.status_code == 200 and answer.json()["asset"]["processing_state"] != "failed"
    (entry,) = world.entries()
    operation = entry.source[media_quota.SOURCE_OP]
    assert media_quota.decode_intent(entry.source[media_quota.SOURCE_SETTLE]) == (60, "completed:generated_asr")
    assert world.repo.reservations[operation]["state"] == "dispatched" and world.bucket()["reserved"] == 60
    world.repo.fail_settle = 0
    assert world.new_pipeline().recover(world.store, world.assets) == 0, "nothing to re-run"
    assert world.repo.reservations[operation]["state"] == "settled"
    assert world.repo.settled == [(operation, 60, "completed:generated_asr")], "the amount decided when the job ended"
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (60, 0)
    assert world.new_pipeline().recover(world.store, world.assets) == 0
    assert len(world.repo.settled) == 1, "a settled import is never settled again"


def test_an_import_interrupted_too_often_settles_zero(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    monkeypatch.setattr(world.pipeline, "_pool", type("Idle", (), {"submit": lambda *_a, **_k: None})())
    monkeypatch.delenv("MEDIA_PIPELINE_INLINE")
    world.upload(media(60))
    (entry,) = world.entries()
    world.store.update_if_present(entry.media_id, lambda e: dataclasses.replace(
        e, processing={**e.processing, "attempts": pipeline_mod.MAX_ATTEMPTS}))
    assert world.new_pipeline().recover(world.store, world.assets) == 0
    assert world.store.get(entry.media_id).processing["reason"] == "pipeline_interrupted"
    assert world.repo.settled[-1][1:] == (0, "failed:pipeline_interrupted")
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (0, 0)


def test_removing_an_unfinished_import_costs_nothing(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    monkeypatch.setattr(world.pipeline, "_pool", type("Idle", (), {"submit": lambda *_a, **_k: None})())
    monkeypatch.delenv("MEDIA_PIPELINE_INLINE")
    world.upload(media(60))
    (entry,) = world.entries()
    assert world.bucket()["reserved"] == 60
    assert media_library_api.delete_owned_media(entry.media_id, user_key="learner-1", language="en") is True
    assert world.repo.settled[-1][1:] == (0, "cancelled")
    assert (world.bucket()["consumed"], world.bucket()["reserved"]) == (0, 0)


# ================================================================== the same source is never charged twice ==

def test_the_same_file_imported_again_is_the_same_import_and_is_charged_once(world: World):
    first = world.upload(media(60, tag="same"))
    second = world.upload(media(60, tag="same"))
    assert first.status_code == second.status_code == 200
    assert second.json()["media_id"] == first.json()["media_id"]
    assert world.asr.calls == 1 and len(world.entries()) == 1
    assert world.bucket()["consumed"] == 60 and len(world.repo.reservations) == 1


def test_the_same_file_from_another_learner_is_that_learners_own_import(world: World):
    one = world.upload(media(60, tag="same"), user="learner-1")
    two = world.upload(media(60, tag="same"), user="learner-2")
    assert one.json()["media_id"] != two.json()["media_id"]
    assert world.asr.calls == 2 and len(world.repo.reservations) == 2


def test_the_same_video_by_any_link_form_is_charged_once(world: World):
    first = world.source(video_url(9))
    second = world.source(video_url(9, "https://youtu.be/"))
    third = world.source(video_url(9) + "&t=30s")
    assert first.status_code == second.status_code == third.status_code == 200
    assert first.json()["media_id"] == second.json()["media_id"] == third.json()["media_id"]
    assert len(world.repo.reservations) == 1 and world.bucket()["consumed"] == 600
    assert len(world.probed_urls) == 1 and world.ingestion.calls == 1, "the second request fetched nothing at all"


def test_simultaneous_requests_for_one_source_make_one_import(world: World):
    barrier = threading.Barrier(5)

    def one(_n):
        barrier.wait(timeout=20)
        return world.upload(media(60, tag="race"))

    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(one, range(5)))
    assert [a.status_code for a in answers] == [200] * 5
    assert len({a.json()["media_id"] for a in answers}) == 1
    assert len(world.repo.reservations) == 1 and world.bucket()["consumed"] == 60 and world.asr.calls == 1


# ================================================================================= switch off / store down ==

def test_with_the_switch_off_an_import_is_exactly_what_it_was(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    enforced_runtime(repository=world.repo, env={quota.FLAG: "off"})
    first = world.upload(media(60, tag="same"))
    second = world.upload(media(60, tag="same"))
    assert first.json()["media_id"] != second.json()["media_id"], "no duplicate handling when nothing is metered"
    assert world.asr.calls == 2 and world.repo.calls == [], "no bucket was read or written"
    assert all(media_quota.SOURCE_OP not in entry.source and media_quota.SOURCE_KEY not in entry.source
               for entry in world.entries())
    assert world.source(video_url(10)).status_code == 200
    assert world.probed_urls == [], "YouTube's length is not even asked"
    assert world.repo.calls == []


def test_a_meter_that_is_not_listed_is_not_metered(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    enforced_runtime(repository=world.repo, env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    assert world.upload(media(60)).status_code == 200 and world.repo.calls == []


def test_when_the_quota_store_cannot_be_asked_nothing_is_read_stored_or_fetched(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    quota.configure_quota(repository=None, incarnations=None, plan_for=None, settings=None, env=ENV,
                          reason="no_postgresql")
    upload = world.upload(media(60))
    assert upload.status_code == 503 and upload.json()["detail"]["category"] == "quota_unavailable"
    link = world.source(video_url(11))
    assert link.status_code == 503 and link.json()["detail"]["category"] == "quota_unavailable"
    assert world.probed_files == 0 and world.probed_urls == [] and world.ingestion.calls == 0
    assert world.asr.calls == 0 and world.stored_files() == [] and world.entries() == []


def test_a_quota_store_that_fails_mid_request_is_a_503_and_leaves_nothing_reserved(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    monkeypatch.setattr(world.repo, "reserve", lambda **_k: (_ for _ in ()).throw(RuntimeError("down")))
    answer = world.upload(media(60))
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert world.stored_files() == [] and world.asr.calls == 0 and world.bucket() is None


def test_the_older_import_route_is_refused_where_it_cannot_be_metered(world: World, monkeypatch):
    monkeypatch.setattr(media_api, "_media_ingestion_service", None)
    answer = world.client.post("/api/media-learning/import", json={"source_url": video_url(12), "target_language": "vi"})
    assert answer.status_code == 503
    detail = answer.json()["detail"]
    assert detail["category"] == "quota_media_import_not_metered" and detail["context"]["feature"] == METER
    enforced_runtime(repository=world.repo, env={quota.FLAG: "off"})
    off = world.client.post("/api/media-learning/import", json={"source_url": video_url(12), "target_language": "vi"})
    assert "quota_media_import_not_metered" not in off.text, "unchanged when not enforced"


# ============================================================================ the book the learner reads ==

def test_plan_and_usage_reads_the_same_bucket_the_import_wrote(world: World):
    world.upload(media(61.2, 58.2))
    usage = quota.usage_for("learner-1", catalog.FREE)[METER]
    assert usage["state"] == "known" and usage["used"] == 59 == world.bucket()["consumed"]
    assert quota.usage_for("learner-2", catalog.FREE)[METER]["used"] == 0, "another learner's month is their own"


def test_the_limit_is_the_plans_and_the_used_minutes_are_kept_when_it_changes(world: World):
    assert world.upload(media(60, tag="a")).status_code == 200
    quota.runtime().plan_for = lambda user_key, strict=False: catalog.plan_by_id("plus", strict=strict)
    world.spend(FREE_LIMIT)  # 960 s in the month: past the Free allowance, well inside Plus's 7200
    assert world.upload(media(60, tag="b")).status_code == 200
    assert world.bucket()["consumed"] == 1020, "the minutes already used are kept when the plan changes"
    quota.runtime().plan_for = lambda user_key, strict=False: catalog.plan_by_id("free", strict=strict)
    refused = world.upload(media(60, tag="c"))
    context = refused.json()["detail"]["context"]
    assert (refused.status_code, context["used"], context["limit"], context["plan"]) == (429, 1020, FREE_LIMIT, "free")
    assert world.asr.calls == 2


# ================================================================================================ reconciler ==

def test_the_reconciler_leaves_an_import_to_its_worker_for_hours(world: World):
    enforced_runtime(repository=world.repo, env={quota.FLAG: "on", quota.METERS_FLAG: f"{METER},pronunciation.audio"})
    take = quota.begin("pronunciation.audio", units=5, request_digest="p")
    take.dispatch("p")
    running = quota.begin(METER, units=60, request_digest="long import")
    quota.dispatch_operation(running.operation_id, "media-import")
    stale = datetime.now(UTC)
    for row in world.repo.reservations.values():
        row["updated_at"] = stale - timedelta(minutes=30)
    assert quota.reconcile_once(world.repo, now=stale) == {"settled": 1, "released": 0},         "the 30-minute-old pronunciation take is swept; the import is its worker's"
    assert world.repo.reservations[running.operation_id]["state"] == "dispatched"
    assert world.repo.reservations[take.operation_id]["state"] == "settled"
    assert quota.reconcile_once(world.repo, now=stale + quota.ASYNC_RECONCILE_AFTER) == {"settled": 1, "released": 0}
    assert world.repo.reservations[running.operation_id]["state"] == "settled"
    assert world.bucket()["consumed"] == 60 and world.bucket()["reserved"] == 0, "abandoned work is settled as admitted"


def test_an_import_that_never_reached_a_worker_is_released_by_the_backstop(world: World):
    ticket = quota.begin(METER, units=60, request_digest="orphan")
    row = world.repo.reservations[ticket.operation_id]
    row["updated_at"] = datetime.now(UTC) - quota.ASYNC_RECONCILE_AFTER - timedelta(minutes=1)
    assert quota.reconcile_once(world.repo)["released"] == 1
    assert world.repo.reservations[ticket.operation_id]["state"] == "released" and world.bucket()["reserved"] == 0


def test_the_meter_is_wired_and_async():
    assert METER in quota.WIRED_METERS and METER in quota.ASYNC_METERS and METER not in quota.SYNC_METERS
    assert quota.validate_switch_setting({"enabled": True, "meters": [METER]}) == {"enabled": True, "meters": [METER]}
    assert set(quota.ASYNC_METERS).isdisjoint(quota.SYNC_METERS)


def test_the_operation_id_is_kept_with_the_entry_and_never_shown_to_the_learner(world: World):
    from writing_coach import listening_api

    world.upload(media(60))
    (entry,) = world.entries()
    assert entry.source["owner"] == owner_token("learner-1") and "learner-1" not in str(entry.source)
    assert entry.source[media_quota.SOURCE_OP].startswith("q1:") and entry.source[media_quota.SOURCE_UNITS] == "60"
    shown = json.dumps([listening_api._stored_asset(entry), listening_api.stored_media_metadata(entry)], default=str)
    assert "q1:" not in shown and media_quota.SOURCE_OP not in shown
