"""`/api/agent/*` behind its server flag (human ruling 2026-09-27)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from writing_coach.agent.api import agent_enabled, configure_agent, router
from writing_coach.agent.contract import CONTRACT_VERSION
from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.fake_provider import FakeAgentTurnProvider, reply
from writing_coach.agent.limits import AgentLimits
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.session import SessionCache
from writing_coach.agent.turn import AgentRuntime
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX


def body(target="zh-CN", **overrides):
    payload = {
        "contract_version": 1,
        "message": "Hôm nay tôi nên học gì?",
        "client": {"ui_version": "next-0"},
        "context": {"surface": "home", "locale": {"interface": "vi", "support": "vi", "target": target}},
    }
    payload.update(overrides)
    return payload


def test_the_flag_is_off_by_default_and_never_on_in_production():
    assert not agent_enabled({}, production=False)
    assert not agent_enabled({"AGENT_ENABLED": "false"}, production=False)
    for on in ("true", "1", "yes", "on", " TRUE "):
        assert agent_enabled({"AGENT_ENABLED": on}, production=False)
        assert not agent_enabled({"AGENT_ENABLED": on}, production=True)


@pytest.fixture()
def client():
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
    yield TestClient(app)
    configure_agent(None)


def enable(rounds=(), limits=None):
    tools = build_tool_registry(writing_review=lambda essay_id: None)
    configure_agent(
        AgentRuntime(
            provider=FakeAgentTurnProvider(list(rounds)),
            tools=tools,
            capabilities=load_capability_registry(registered_tools=tools.names()),
            sessions=SessionCache(),
            **({"limits": limits} if limits else {}),
        )
    )


def test_both_routes_answer_404_while_off(client):
    configure_agent(None)
    assert client.post("/api/agent/turn", json=body()).status_code == 404
    assert client.get("/api/agent/capabilities").status_code == 404
    # a malformed request learns nothing either: 404, not a 422 naming the schema
    assert client.post("/api/agent/turn", json={}).status_code == 404
    assert client.get("/api/agent/capabilities", params={"interface": "x" * 40}).status_code == 404


def test_a_malformed_request_is_422(client):
    enable()
    assert client.post("/api/agent/turn", json=body(message="")).status_code == 422
    assert client.post("/api/agent/turn", json={"contract_version": 1}).status_code == 422


def test_a_target_other_than_the_session_language_is_refused_before_anything_runs(client):
    enable()  # no scripted round: the provider would fail if it were asked
    response = client.post("/api/agent/turn", json=body(target="en"))
    assert response.status_code == 409 and response.json()["detail"] == "target_language_mismatch"


def test_a_turn_streams_contract_events(client):
    # "Nên học gì?" needs the learner's records (gate 3.1): a model that never reads is asked once more.
    enable([reply("Ôn 12 từ đến hạn trước nhé."), reply("Ôn 12 từ đến hạn trước nhé.")])
    response = client.post("/api/agent/turn", json=body())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    frames = [frame for frame in response.text.split("\n\n") if frame]
    assert frames[0].startswith("event: session\ndata: ")
    assert frames[-1].startswith("event: done\ndata: ")


def test_capabilities_follow_the_callers_locale(client):
    enable()
    zh = client.get("/api/agent/capabilities", params={"interface": "vi"}).json()
    assert zh["contract_version"] == CONTRACT_VERSION
    ids = {item["id"] for item in zh["capabilities"]}
    assert "speaking.pronunciation.tone" in ids and "speaking.pronunciation.stress" not in ids
    titles = {item["id"]: item["title"] for item in zh["capabilities"]}
    assert titles["review.due"] == "Từ cần ôn"
    en = client.get("/api/agent/capabilities", params={"interface": "en"}, headers={"x-test-language": "en"}).json()
    ids = {item["id"] for item in en["capabilities"]}
    assert "speaking.pronunciation.stress" in ids and "speaking.pronunciation.tone" not in ids
    assert client.get("/api/agent/capabilities", params={"interface": "fr"}).status_code == 422


def test_the_app_mounts_the_router_once_and_serves_nothing_by_default():
    import app as app_module

    paths = app_module.app.openapi()["paths"]
    assert "post" in paths["/api/agent/turn"] and "get" in paths["/api/agent/capabilities"]

    async def call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            return await http.post("/api/agent/turn", json=body(target="en"))

    assert asyncio.run(call()).status_code == 404


def test_the_app_serves_a_whole_turn_when_enabled(monkeypatch):
    """The real app, middleware, runtime, adapter and legacy routing; only the selected provider is a stand-in."""

    import app as app_module
    from writing_coach.agent.runtime import build_agent_runtime
    from writing_coach.ai import platform
    from writing_coach.ai.base import ChatFinished, ChatTextDelta, ChatToolCall

    rounds = [
        [ChatToolCall("c1", "get_due_review_summary", "{}"), ChatFinished("tool_calls", prompt_tokens=40, completion_tokens=5)],
        [ChatTextDelta("Bạn có từ cần ôn hôm nay."), ChatFinished("stop", prompt_tokens=60, completion_tokens=8)],
    ]

    class Selected:
        id = "gemini"
        name = "Selected"
        kind = "cloud"
        configured = True
        requests: list[dict] = []

        def stream_chat(self, **kwargs):
            self.requests.append(kwargs)
            return iter(rounds.pop(0))

    selected = Selected()
    monkeypatch.setattr(platform, "active_selection", lambda: (selected, "gemini-3.5-flash-lite"))
    monkeypatch.setattr(platform, "_persist_operation_telemetry", lambda telemetry: None)
    usage = app_module._persistence_runtime.product_repository
    configure_agent(build_agent_runtime(writing_review=app_module._agent_writing_review, record_usage=usage.record_usage))
    try:
        before = usage.daily_usage(user_key="legacy", feature="agent.turn")

        async def call() -> httpx.Response:
            transport = httpx.ASGITransport(app=app_module.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
                return await http.post("/api/agent/turn", json=body(target="en"))

        response = asyncio.run(call())
    finally:
        configure_agent(None)
    assert response.status_code == 200, response.text
    names = [frame.split("\n", 1)[0].removeprefix("event: ") for frame in response.text.split("\n\n") if frame]
    assert [n for n in names if n != "segment_delta"] == [
        "session", "tool_call", "tool_result", "evidence", "segment_end", "done",
    ]  # fmt: skip
    assert len(selected.requests) == 2 and selected.requests[0]["tools"][0]["type"] == "function"
    assert usage.daily_usage(user_key="legacy", feature="agent.turn") == before + 1


# --- spec §22: a learner's requests are limited; §35: identity over the wire ------------------


def test_one_turn_too_many_is_429_with_retry_after_and_runs_nothing(client):
    enable(limits=AgentLimits(turns_per_window=2))  # no scripted round: a provider call would fail
    assert client.post("/api/agent/turn", json=body(target="en")).status_code == 409  # counted
    assert client.post("/api/agent/turn", json={"contract_version": 1}).status_code == 422  # counted too
    refused = client.post("/api/agent/turn", json=body())
    assert refused.status_code == 429 and refused.json()["detail"] == "rate_limited"
    assert 1 <= int(refused.headers["retry-after"]) <= 60
    # another learner has a window of their own
    assert client.post("/api/agent/turn", json=body(target="en"), headers={"x-test-user": "learner-2"}).status_code == 409


def test_capability_reads_have_their_own_limit(client):
    enable(limits=AgentLimits(capability_reads_per_window=1))
    assert client.get("/api/agent/capabilities", params={"interface": "vi"}).status_code == 200
    refused = client.get("/api/agent/capabilities", params={"interface": "vi"})
    assert refused.status_code == 429 and "retry-after" in refused.headers
    assert client.post("/api/agent/turn", json=body(target="en")).status_code == 409  # turns are counted apart


def test_while_off_nothing_is_counted_and_everything_is_404(client):
    configure_agent(None)
    for _ in range(30):
        assert client.post("/api/agent/turn", json=body()).status_code == 404


def test_who_orena_is_is_answered_without_a_provider(client):
    enable()  # no scripted round: the provider would fail if it were asked
    response = client.post("/api/agent/turn", json=body(message="Bạn là ai?"))
    assert response.status_code == 200, response.text
    frames = [frame for frame in response.text.split("\n\n") if frame]
    assert [frame.split("\n", 1)[0] for frame in frames] == ["event: session", "event: segment_end", "event: done"]
    assert "Mình là Orena" in frames[1]


def test_the_statuses_answer_as_contract_section_2_1_says(client):
    """404 while off, 409 and 422 counted, 429 with a whole-second Retry-After of at least 1."""

    configure_agent(None)
    off = client.post("/api/agent/turn", json={})
    assert (off.status_code, off.json()) == (404, {"detail": "Not Found"})
    enable(limits=AgentLimits(turns_per_window=2))
    mismatch = client.post("/api/agent/turn", json=body(target="en"))
    assert (mismatch.status_code, mismatch.json()) == (409, {"detail": "target_language_mismatch"})
    assert client.post("/api/agent/turn", json={"contract_version": 1}).status_code == 422
    limited = client.post("/api/agent/turn", json=body())
    assert (limited.status_code, limited.json()) == (429, {"detail": "rate_limited"})
    assert limited.headers["retry-after"].isdigit() and int(limited.headers["retry-after"]) >= 1


def test_a_turn_over_the_daily_spend_cap_is_the_contracts_429_and_reaches_no_provider(client):
    from writing_coach.agent import api as agent_api

    enable([])  # no round scripted: a provider call would fail the test
    agent_api._runtime.spend_guard = lambda: 3600.0
    response = client.post("/api/agent/turn", json=body())
    assert response.status_code == 429 and response.headers["retry-after"] == "3600"


def test_a_turn_refused_by_the_cap_is_not_counted_in_the_learners_window(client):
    from writing_coach.agent import api as agent_api
    from writing_coach.agent.limits import AgentLimits

    enable([reply("Ok.")], limits=AgentLimits(turns_per_window=1))
    agent_api._runtime.spend_guard = lambda: 60.0
    assert client.post("/api/agent/turn", json=body()).status_code == 429
    agent_api._runtime.spend_guard = None  # the cap resets: the one turn the window allows still runs
    assert client.post("/api/agent/turn", json=body()).status_code == 200
