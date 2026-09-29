"""A learner's own file, through the route the new UI's Import > File posts to (D-098).

`POST /api/media-learning/upload` had no test of its own; the human wired the
new learner UI's File option to it "with the types and size limit the endpoint
already has", so those limits are what these hold: audio or video only, never
empty, never over `MAX_UPLOAD_BYTES`, and a stored file opens in Listening
through the same `/api/listening/library/{id}` read a curated lesson uses.

The stores are temporary and the temp root is this test's own, so nothing is
written into the checkout.
"""
from __future__ import annotations

import io
import math
import shutil
import struct
import sys
import wave
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
from writing_coach import listening_api, media_library_api, media_thumbnail  # noqa: E402
from writing_coach.book_asset_store import FilesystemBookAssetStore  # noqa: E402
from writing_coach.media_library_store import FileMediaLibraryStore  # noqa: E402
from writing_coach.media_source_import import MediaSourceImporter  # noqa: E402

needs_ffprobe = pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not installed")


def _tone(seconds: float = 1.0, rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(
            b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(rate * seconds)))
        )
    return buffer.getvalue()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    store = FileMediaLibraryStore(tmp_path / "library")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    importer = MediaSourceImporter(app_module._media_ingestion_service, store, assets)
    monkeypatch.setattr(media_library_api, "_store", store)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(media_library_api, "_importer", importer)
    monkeypatch.setattr(listening_api, "_media_store", store)
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", tmp_path / "media_temp")
    return TestClient(app_module.app)


def _upload(client: TestClient, name: str, body: bytes, language: str = "en"):
    return client.post(
        "/api/media-learning/upload",
        files={"file": (name, body, "application/octet-stream")},
        data={"language": language},
    )


@needs_ffprobe
def test_an_audio_file_is_stored_as_the_learners_own_and_opens_in_listening(client: TestClient) -> None:
    answer = _upload(client, "Lecture 3.wav", _tone())
    assert answer.status_code == 200, answer.text
    payload = answer.json()
    media_id = payload["media_id"]
    assert media_id.startswith("upload-")
    assert payload["asset"]["title"] == "Lecture 3"
    opened = client.get(f"/api/listening/library/{media_id}")
    assert opened.status_code == 200, opened.text
    assert opened.json()["asset"]["title"] == "Lecture 3"


@needs_ffprobe
def test_a_file_that_is_not_audio_or_video_is_refused_as_invalid(client: TestClient) -> None:
    answer = _upload(client, "notes.txt", b"these are notes, not media")
    assert answer.status_code == 422
    assert answer.json()["detail"]["category"] == "media_upload_invalid"


def test_an_empty_file_is_refused_as_invalid(client: TestClient) -> None:
    answer = _upload(client, "empty.wav", b"")
    assert answer.status_code == 422
    assert answer.json()["detail"]["category"] == "media_upload_invalid"


def test_a_file_over_the_routes_own_limit_is_refused_as_invalid(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_library_api, "MAX_UPLOAD_BYTES", 1024)
    answer = _upload(client, "long.wav", b"\0" * 4096)
    assert answer.status_code == 422
    assert answer.json()["detail"]["category"] == "media_upload_invalid"


def test_storage_that_cannot_be_written_is_unavailable_not_invalid(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the temp directory should be")
    monkeypatch.setattr(media_thumbnail, "_TEMP_ROOT", blocked / "media_temp")
    answer = _upload(client, "tone.wav", _tone(0.2))
    assert answer.status_code == 503
    assert answer.json()["detail"]["category"] == "media_upload_unavailable"
