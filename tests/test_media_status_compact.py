"""ASGI contract tests for compact, owner-scoped media import status."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json

import httpx
from itsdangerous import TimestampSigner

import app as app_module
import auth_support
import writing_coach.media_api as media_api
from writing_coach.media_fallback import MediaFallbackResult
from writing_coach.media_ingestion import MediaAcquisition, MediaPlayback
from writing_coach.media_learning import MediaLearningAsset, MediaLearningObject, MediaProcessingState


def _session_cookie(*, user_sub: str, language: str) -> str:
    encoded = base64.b64encode(
        json.dumps({"user_sub": user_sub, "language": language}).encode("utf-8")
    )
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


def _acquisition() -> MediaAcquisition:
    return MediaAcquisition(
        media_object=MediaLearningObject(
            asset=MediaLearningAsset(
                asset_id="youtube:fixture-media",
                source_url="https://example.com/media-fixture",
                source_provider="youtube",
                source_type="external-video",
                title="Fixture lesson",
                source_language="en",
                processing_state=MediaProcessingState.READY,
                transcript_available=False,
            )
        ),
        playback=MediaPlayback(
            provider="youtube",
            kind="embed",
            url="https://example.com/embed/fixture-media",
        ),
    )


@dataclass
class FakeStatusService:
    results: dict[tuple[str, str, str], MediaFallbackResult]

    def __post_init__(self) -> None:
        self.poll_calls: list[tuple[str, str, str]] = []

    def poll(self, job_id: str, *, owner_key: str, learning_language: str) -> MediaFallbackResult:
        self.poll_calls.append((job_id, owner_key, learning_language))
        try:
            return self.results[(job_id, owner_key, learning_language)]
        except KeyError as exc:
            raise KeyError("expired or foreign") from exc


def _result(
    status: str,
    *,
    job_id: str | None,
    provider_state: str,
    failure_kind: str | None = None,
) -> MediaFallbackResult:
    return MediaFallbackResult(
        status=status,
        acquisition=_acquisition(),
        job_id=job_id,
        provider_state=provider_state,
        source="supadata",
        failure_kind=failure_kind,
        target_language="vi",
    )


def test_compact_status_shapes_states_without_transcript_payloads(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)
    processing_id = "opaque-processing-handle-12345"
    ready_id = "opaque-ready-handle-12345678"
    failed_id = "opaque-failed-handle-1234567"
    service = FakeStatusService(
        {
            (processing_id, "learner-a", "en"): _result(
                "processing", job_id=processing_id, provider_state="active"
            ),
            (ready_id, "learner-a", "en"): _result(
                "ready", job_id=ready_id, provider_state="completed"
            ),
            (failed_id, "learner-a", "en"): _result(
                "failed",
                job_id=failed_id,
                provider_state="failed",
                failure_kind="provider_timeout",
            ),
        }
    )
    monkeypatch.setattr(media_api, "_media_fallback_service", service)

    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers={"Origin": "http://testserver"}) as client:
            client.cookies.set(
                "writing_coach_session",
                _session_cookie(user_sub="learner-a", language="en"),
            )
            compact = []
            for job_id in (processing_id, ready_id, failed_id):
                response = await client.post(
                    "/api/media-learning/import/status",
                    json={"job_id": job_id, "compact": True},
                )
                compact.append(response)
            full = await client.post(
                "/api/media-learning/import/status",
                json={"job_id": processing_id},
            )
            return compact, full

    compact_responses, full_response = asyncio.run(exercise())
    assert [response.status_code for response in compact_responses] == [200, 200, 200]
    expected = [
        ("processing", "processing", "active", None, True),
        ("ready", "ready", "completed", None, False),
        ("failed", "failed", "failed", "provider_timeout", False),
    ]
    for response, (status, asset_state, job_state, failure, resumable) in zip(
        compact_responses, expected
    ):
        payload = response.json()
        assert payload["status"] == status
        assert payload["asset"] == {
            "asset_id": "youtube:fixture-media",
            "processing_state": asset_state,
        }
        assert payload["import_job"]["state"] == job_state
        assert payload["import_job"]["source"] == "supadata"
        assert payload["import_job"]["failure_kind"] == failure
        assert payload["import_job"]["resumable"] is resumable
        assert set(payload) == {"status", "asset", "import_job"}
        assert all(secret not in response.text for secret in ("Generated transcript", "provider-job"))
        assert "transcript" not in payload
        assert "translations" not in payload
        assert "playback" not in payload

    assert full_response.status_code == 200
    full_payload = full_response.json()
    assert full_payload["import_job"]["job_id"] == processing_id
    assert "transcript" in full_payload
    assert len(service.poll_calls) == 4


def test_compact_status_keeps_owner_and_language_scope_and_expiry_private(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)
    handle = "opaque-processing-handle-scope"
    service = FakeStatusService(
        {
            (handle, "learner-a", "en"): _result(
                "processing", job_id=handle, provider_state="queued"
            )
        }
    )
    monkeypatch.setattr(media_api, "_media_fallback_service", service)

    async def request():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers={"Origin": "http://testserver"}) as client:
            client.cookies.set(
                "writing_coach_session",
                _session_cookie(user_sub="learner-b", language="en"),
            )
            foreign = await client.post(
                "/api/media-learning/import/status",
                json={"job_id": handle, "compact": True},
            )
            client.cookies.set(
                "writing_coach_session",
                _session_cookie(user_sub="learner-a", language="zh"),
            )
            language_mismatch = await client.post(
                "/api/media-learning/import/status",
                json={"job_id": handle, "compact": True},
            )
            monkeypatch.setattr(media_api, "_media_fallback_service", None)
            unavailable = await client.post(
                "/api/media-learning/import/status",
                json={"job_id": handle, "compact": True},
            )
            return foreign, language_mismatch, unavailable

    foreign, language_mismatch, unavailable = asyncio.run(request())
    for response in (foreign, language_mismatch, unavailable):
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert detail["category"] == "media_job_unavailable"
        assert detail["context"] == {"status": "unavailable", "resumable": False}
        assert handle not in response.text
        assert "provider-job" not in response.text
    assert service.poll_calls == [
        (handle, "learner-b", "en"),
        (handle, "learner-a", "zh"),
    ]
