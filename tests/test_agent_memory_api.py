"""`/api/agent/memory` (contract v9 §10; ORENA_MEMORY.md rev 4.1 §6): what the learner sees, deletes and switches off.

The store is the in-memory fake (the PostgreSQL repository passes the same contract). Every route is the learner's own,
behind `AGENT_ENABLED` (404 while off) and the account's active incarnation (503 `memory_unavailable` without one);
state-changing ones pass the app-wide origin check like every `/api/` write (core/http_security.py)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from writing_coach.agent.api import configure_agent, router
from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_runtime import MemoryRuntime, account_id
from writing_coach.agent.memory_store import CONTINUITY, InMemoryMemoryStore, MemoryScope
from writing_coach.core.http_security import origin_refusal
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from tests.test_agent_api import enable

T0 = datetime(2026, 10, 18, 9, 0, tzinfo=UTC)


class Incarnations:
    def __init__(self):
        self.active = {account_id("learner-1"): "inc-1", account_id("learner-2"): "inc-2"}

    def resolve(self, account):
        return self.active.get(account)

    def ensure_active(self, account):
        if account not in self.active:
            raise ValueError("not set up")
        return self.active[account]


@pytest.fixture()
def api():
    app = FastAPI()

    @app.middleware("http")
    async def learner(request: Request, call_next):
        user = USER_KEY_CTX.set(request.headers.get("x-test-user", "learner-1"))
        language = LANGUAGE_CODE_CTX.set(request.headers.get("x-test-language", "zh"))
        try:
            return await call_next(request)
        finally:
            LANGUAGE_CODE_CTX.reset(language)
            USER_KEY_CTX.reset(user)

    app.include_router(router)
    enable()
    from writing_coach.agent import api as agent_api

    store = InMemoryMemoryStore(MemoryKeys.parse("v1:" + "k" * 40))
    incarnations = Incarnations()
    agent_api.configure_memory(MemoryRuntime(store=store, incarnations=incarnations))
    yield TestClient(app), store, incarnations
    configure_agent(None)


def scope(user="learner-1", inc="inc-1"):
    return MemoryScope(account_id(user), inc)


def keep(store, text="Mình học để phỏng vấn", user="learner-1", inc="inc-1", language="zh"):
    return store.add_explicit(scope(user, inc), language=language, kind="goal", text=text, slot=None,
                              source="learner_asked", now=T0)  # fmt: skip


def test_the_listing_is_by_class_with_reason_codes_and_the_switch(api):
    client, store, _ = api
    item = keep(store)
    store.checkpoint(scope(), agent_session_id="s1", language="zh", turns_covered=4,
                     summary={"practised": [], "focus": None, "open_task": None},
                     context=[("interest", "sport")], now=T0)  # fmt: skip
    answer = client.get("/api/agent/memory", params={"language": "zh-CN"})
    assert answer.status_code == 200
    data = answer.json()
    assert data["enabled"] is True and data["language"] == "zh-CN" and data["sessions"] == []
    [explicit] = data["items"]["explicit"]
    assert explicit["id"] == item.id and explicit["text"] == "Mình học để phỏng vấn"
    assert explicit["reason"] == {"source": "learner_asked", "evidence_count": None, "confidence": None,
                                  "expires_at": None}  # fmt: skip
    [continuity] = data["items"]["continuity"]
    assert continuity["slot"] == "interest" and continuity["code"] == "sport" and continuity["reason"]["expires_at"]
    assert data["items"]["inferred"] == []
    assert all(isinstance(v, (str, int, float, bool, type(None), dict, list)) for v in explicit.values())


def test_a_learner_sees_and_deletes_only_their_own(api):
    client, store, _ = api
    theirs = keep(store, text="của người khác", user="learner-2", inc="inc-2")
    assert client.get("/api/agent/memory").json()["items"]["explicit"] == []
    assert client.delete(f"/api/agent/memory/items/{theirs.id}").status_code == 404
    assert [i.id for i in store.items(scope("learner-2", "inc-2"), "zh", T0)] == [theirs.id]


def test_delete_one_and_the_switch_work_while_off(api):
    client, store, _ = api
    item = keep(store)
    off = client.put("/api/agent/memory/settings", json={"enabled": False})
    assert off.status_code == 200 and off.json()["enabled"] is False
    assert client.delete(f"/api/agent/memory/items/{item.id}").status_code == 204
    assert store.items(scope(), "zh", T0) == []
    on = client.put("/api/agent/memory/settings", json={"enabled": True})
    assert on.json()["enabled"] is True and on.json()["version"] > off.json()["version"]


def test_bulk_delete_keeps_suppression_and_counts(api):
    client, store, _ = api
    keep(store)
    store.checkpoint(scope(), agent_session_id="s1", language="zh", turns_covered=4,
                     summary={"practised": [], "focus": None, "open_task": None},
                     context=[("interest", "sport")], now=T0)  # fmt: skip
    answer = client.delete("/api/agent/memory", params={"scope": "items"})
    assert answer.status_code == 200 and answer.json()["removed"] == 2
    assert store.items(scope(), "zh", T0) == []
    assert store.suppressed(scope(), "zh", CONTINUITY, "interest", "sport", T0)
    assert client.delete("/api/agent/memory", params={"scope": "everything"}).status_code == 422


def test_without_an_incarnation_memory_is_unavailable(api):
    client, _, incarnations = api
    incarnations.active.clear()
    for answer in (client.get("/api/agent/memory"), client.put("/api/agent/memory/settings", json={"enabled": False}),
                   client.delete("/api/agent/memory", params={"scope": "all"})):  # fmt: skip
        assert answer.status_code == 503 and answer.json()["detail"] == "memory_unavailable"


def test_without_memory_on_this_server_the_routes_are_unavailable(api):
    client, _, _ = api
    from writing_coach.agent import api as agent_api

    agent_api.configure_memory(None)
    assert client.get("/api/agent/memory").status_code == 503


def test_off_with_the_agent_every_route_is_404(api):
    client, _, _ = api
    configure_agent(None)
    assert client.get("/api/agent/memory").status_code == 404
    assert client.put("/api/agent/memory/settings", json={"enabled": False}).status_code == 404
    assert client.delete("/api/agent/memory/items/x").status_code == 404


def test_a_cross_site_write_is_refused_like_every_api_write():
    for method in ("PUT", "DELETE"):
        assert origin_refusal(method, "/api/agent/memory/settings", {"origin": "https://evil.example",
                                                                     "host": "orena.app"}) == "origin_mismatch"
