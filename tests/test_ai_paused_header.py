"""One signal on every surface when the system AI ceiling refused something in a request (owner: AI locked "kèm thông báo
rõ ràng cho người học"; UI lane request, 2026-10-19): the response carries `X-Orena-AI-Paused: <resets_at>`, whatever its
route, status or body - a Reading 503, a Listening 200 whose translation is "unavailable", a room's error. A fault (the
ledger cannot be read) refuses too, but is not "paused": no header, so it stays an ordinary retry."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from writing_coach.ai import spend_gate

HEADER = "x-orena-ai-paused"


@pytest.fixture()
def client():
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()
    app = FastAPI()
    spend_gate.install_paused_header(app)

    @app.get("/sync-ai")
    def sync_ai():  # a sync route: run in the threadpool, as most rooms are
        if spend_gate.ceiling_reached():
            raise HTTPException(503, "translation_unavailable")
        return {"ok": True}

    @app.get("/async-ok")
    async def async_ok():
        return {"translation": {"status": "unavailable"}} if spend_gate.ceiling_reached() else {"ok": True}

    @app.get("/fallback")
    def fallback():  # a paid step skipped, but the learner is still answered (word audio's next voice)
        return {"spoken": "local"} if spend_gate.ceiling_reached(mark=False) else {"spoken": "azure"}

    @app.get("/no-ai")
    def no_ai():
        return {"ok": True}

    yield TestClient(app)
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()


def test_no_ceiling_no_header(client):
    assert HEADER not in client.get("/sync-ai").headers


def test_a_refusal_marks_the_response_whatever_its_status(client):
    spend_gate.configure_ceiling(5.0, read=lambda since: (5.0, 0))
    refused = client.get("/sync-ai")
    assert refused.status_code == 503 and refused.headers[HEADER].endswith("+00:00")
    degraded = client.get("/async-ok")
    assert degraded.status_code == 200 and HEADER in degraded.headers
    assert HEADER not in client.get("/no-ai").headers  # a route that asked nothing of AI is not marked


def test_a_fault_is_not_paused(client):
    def broken(since):
        raise RuntimeError("ledger down")

    spend_gate.configure_ceiling(5.0, read=broken)
    answer = client.get("/sync-ai")
    assert answer.status_code == 503 and HEADER not in answer.headers


def test_a_working_fallback_is_not_marked_and_resets_at_is_the_ceilings_own_midnight(client):
    spend_gate.configure_ceiling(5.0, read=lambda since: (5.0, 0))
    assert HEADER not in client.get("/fallback").headers
    assert client.get("/sync-ai").headers[HEADER] == spend_gate.ceiling_status()["resets_at"]
