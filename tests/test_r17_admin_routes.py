import asyncio
from datetime import datetime, timezone

import httpx

import app as app_module


class FakeControlPlane:
    def __init__(self, _repository, **_kw):
        pass

    def inspect(self):
        return {"capabilities": [], "providers": []}


def test_product_activity_and_readiness_routes_require_admin_and_redact(monkeypatch):
    occurred_at = datetime.now(timezone.utc).isoformat()

    def guard(request):
        from fastapi import HTTPException
        if request.headers.get("x-test-admin") != "1":
            raise HTTPException(403, "admin required")
        return {"is_admin": True}

    class Repo:
        def initialize(self):
            return None

        def list_product_activity_events(self, _since):
            return [{"learner_key": "private-user", "skill": "writing", "occurred_at": occurred_at, "completed": True, "text": "private learner text", "media_url": "https://private.example/media"}]

    operations = {"available": True, "has_data": True, "by_capability": [], "recent": [{"origin": "learner", "outcome": "failure", "error_class": "provider_error", "capability": "writing_evaluator", "created_at": occurred_at, "prompt": "private prompt", "learner_key": "private-user", "url": "https://private.example"}]}

    monkeypatch.setattr(app_module, "require_admin", guard)
    monkeypatch.setattr(app_module, "_specialized_learning_repository", Repo())
    monkeypatch.setattr(app_module, "admin_ai_operations", lambda *_args, **_kwargs: operations)
    monkeypatch.setattr(app_module, "AIControlPlane", FakeControlPlane)

    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            denied = [await client.get(path) for path in ("/api/admin/product-activity", "/api/admin/readiness-summary")]
            allowed = [await client.get(path, headers={"x-test-admin": "1"}) for path in ("/api/admin/product-activity", "/api/admin/readiness-summary")]
            return denied, allowed

    denied, allowed = asyncio.run(exercise())
    assert [response.status_code for response in denied] == [403, 403]
    assert [response.status_code for response in allowed] == [200, 200]
    activity, readiness = [response.json() for response in allowed]
    assert activity["active_learners"] == 1
    assert activity["learner_impact_failures"]["by_capability"][0]["failure_count"] == 1
    assert readiness["available"] is True
    assert readiness["approval_state"] == "not_granted"
    serialized = repr((activity, readiness))
    assert all(secret not in serialized for secret in ("private-user", "private learner text", "private prompt", "private.example", "event_rows"))
