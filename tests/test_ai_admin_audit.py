"""Who changed the AI platform, and how, is recorded - and never with a secret.

The capability routes, the legacy learner model and provider credentials are
stored as the latest value with only the last updater. These are the changes
that decide which provider every learner request reaches and which key it
carries, so each attempt - changed, refused or failed - now leaves an
`audit_logs` row naming the administrator, the target, the time and the
outcome. A submitted API key never appears in that row, in a response, in
the application log or in storage as plaintext.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import writing_coach.ai.platform as platform
from writing_coach.ai.credentials import MASTER_KEY_ENV
from writing_coach.persistence.models import AuditLog, Base, PlatformSetting, User
from writing_coach.persistence.platform_repository import PostgresPlatformRepository, SQLitePlatformRepository

ADMIN = {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}
ORIGIN = {"origin": "http://testserver"}


@pytest.fixture()
def world(monkeypatch):
    monkeypatch.setenv(MASTER_KEY_ENV, Fernet.generate_key().decode("ascii"))
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    admin_id = uuid.uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=admin_id, user_key="sub-admin", email="admin@example.com", name="Admin", role="admin",
                         created_at=datetime.now(UTC)))
    repository = PostgresPlatformRepository(engine)
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "_admin_guard", lambda request: ADMIN)
    app = FastAPI()
    app.include_router(platform.router)
    return {"app": app, "engine": engine, "admin_id": admin_id}


def call(app, method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(run())


def events(engine, action=None):
    with Session(engine) as session:
        statement = select(AuditLog).where(AuditLog.action.like("admin.ai.%")).order_by(AuditLog.created_at)
        rows = session.scalars(statement).all()
        return [
            {"action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id,
             "payload": dict(row.payload), "user_id": row.user_id, "created_at": row.created_at}
            for row in rows if action is None or row.action == action
        ]


def test_a_route_change_is_recorded_with_actor_target_time_and_outcome(world):
    body = {"enabled": True, "provider": "ollama", "model": "qwen3:8b"}
    assert call(world["app"], "PUT", "/api/admin/ai/config/learner_dictionary", json=body).status_code == 200
    (event,) = events(world["engine"], "admin.ai.route.update")
    assert event["entity_type"] == "ai_capability" and event["entity_id"] == "learner_dictionary"
    assert event["user_id"] == world["admin_id"]
    assert event["created_at"] is not None
    assert event["payload"]["outcome"] == "ok"
    assert event["payload"]["provider"] == "ollama" and event["payload"]["model"] == "qwen3:8b"


def test_a_refused_route_change_is_recorded_as_refused(world):
    body = {"enabled": True, "provider": "no-such-provider", "model": "x"}
    assert call(world["app"], "PUT", "/api/admin/ai/config/learner_dictionary", json=body).status_code == 400
    (event,) = events(world["engine"], "admin.ai.route.update")
    assert event["payload"]["outcome"] == "refused"


def test_a_route_test_is_recorded_with_its_outcome(world):
    response = call(world["app"], "POST", "/api/admin/ai/test/learner_dictionary")
    assert response.status_code == 404  # no saved route to test
    (event,) = events(world["engine"], "admin.ai.route.test")
    assert event["payload"] == {"standby": False, "outcome": "failed", "error_class": "capability_not_configured"}


def test_a_credential_change_is_recorded_and_the_key_is_nowhere(world, monkeypatch, caplog):
    secret = "sk-" + secrets.token_urlsafe(24)
    monkeypatch.setattr(platform, "_credential_test", lambda provider_id, values: ["model-a", "model-b"])
    caplog.set_level(logging.DEBUG)
    body = {"api_key": secret, "models": ["model-a"], "default_model": "model-a"}
    saved = call(world["app"], "PUT", "/api/admin/ai/credentials/groq", json=body, headers=ORIGIN)
    assert saved.status_code == 200
    (event,) = events(world["engine"], "admin.ai.credential.update")
    assert event["entity_type"] == "ai_provider" and event["entity_id"] == "groq"
    assert event["user_id"] == world["admin_id"]
    assert event["payload"]["credential_updated"] is True and event["payload"]["outcome"] == "ok"

    reads = [
        saved,
        call(world["app"], "GET", "/api/admin/ai/credentials"),
        call(world["app"], "GET", "/api/admin/ai/config"),
        call(world["app"], "GET", "/api/admin/ai/catalog"),
    ]
    for response in reads:
        assert secret not in response.text
    assert secret not in json.dumps([item["payload"] for item in events(world["engine"])], default=str)
    assert secret not in caplog.text
    with Session(world["engine"]) as session:
        stored = [json.dumps(row.value) for row in session.scalars(select(PlatformSetting)).all()]
    assert stored and all(secret not in value for value in stored), "the key is stored only encrypted"


def test_a_failed_credential_change_is_recorded_without_the_key(world, monkeypatch, caplog):
    secret = "sk-" + secrets.token_urlsafe(24)

    def refuse(provider_id, values):
        raise HTTPException(502, "Provider connection validation failed: Groq API returned HTTP 401.")

    monkeypatch.setattr(platform, "_credential_test", refuse)
    caplog.set_level(logging.DEBUG)
    body = {"api_key": secret, "models": ["model-a"], "default_model": "model-a"}
    response = call(world["app"], "PUT", "/api/admin/ai/credentials/groq", json=body, headers=ORIGIN)
    assert response.status_code == 502
    assert secret not in response.text
    (event,) = events(world["engine"], "admin.ai.credential.update")
    assert event["payload"] == {"credential_updated": False, "outcome": "failed", "status": 502}
    assert secret not in caplog.text


def test_a_provider_test_and_a_credential_removal_are_recorded(world, monkeypatch):
    secret = "sk-" + secrets.token_urlsafe(24)
    monkeypatch.setattr(platform, "_credential_test", lambda provider_id, values: ["model-a"])
    tested = call(world["app"], "POST", "/api/admin/ai/credentials/groq/test", json={"api_key": secret}, headers=ORIGIN)
    assert tested.status_code == 200
    assert call(world["app"], "DELETE", "/api/admin/ai/credentials/groq", headers=ORIGIN).status_code == 200
    test_event = events(world["engine"], "admin.ai.provider.test")[0]
    assert test_event["payload"] == {"outcome": "ok", "models": 1}
    removal = events(world["engine"], "admin.ai.credential.delete")[0]
    assert removal["payload"] == {"credential_deleted": True, "outcome": "ok"}
    assert secret not in json.dumps([item["payload"] for item in events(world["engine"])], default=str)


def test_the_legacy_learner_model_change_is_recorded(world, monkeypatch):
    refused = call(world["app"], "PUT", "/api/admin/ai/config", json={"provider": "no-such", "model": "m"})
    assert refused.status_code == 400
    (event,) = events(world["engine"], "admin.ai.selection.update")
    assert event["entity_id"] == "learner_default"
    assert event["payload"]["outcome"] == "refused"


def test_an_unaudited_store_is_not_an_error(tmp_path, monkeypatch):
    # The frozen SQLite store keeps no audit (as it keeps no telemetry); the
    # change still succeeds rather than failing on a record it cannot write.
    repository = SQLitePlatformRepository(tmp_path / "platform.db")
    repository.initialize()
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "_admin_guard", lambda request: ADMIN)
    app = FastAPI()
    app.include_router(platform.router)
    body = {"enabled": True, "provider": "ollama", "model": "qwen3:8b"}
    assert call(app, "PUT", "/api/admin/ai/config/learner_dictionary", json=body).status_code == 200
    assert repository.record_admin_event("admin.ai.route.update", actor="sub-admin") is None
