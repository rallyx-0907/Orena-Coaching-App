"""Open-public readiness items d (sign-in rate limit) and f (analytics language fields, participant code, no text)."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import app as app_module
from writing_coach.core.http_security import client_address, signin_group
from writing_coach.persistence.specialized_repository import PostgresSpecializedLearningRepository
from writing_coach.product_activity import aggregate_product_activity, participant_code


# ---- d: sign-in rate limit ------------------------------------------------------------------------------------

def test_the_three_sign_in_routes_have_a_group_and_nothing_else_does():
    assert signin_group("GET", "/auth/google")[0] == "signin_start"
    assert signin_group("GET", "/auth/google/callback")[0] == "signin_callback"
    assert signin_group("POST", "/api/auth/native/exchange")[0] == "signin_exchange"
    assert signin_group("GET", "/auth/google")[1:] == (20, 600)
    assert signin_group("GET", "/auth/google/callback")[1:] == (30, 600)
    assert signin_group("POST", "/auth/logout") is None
    assert signin_group("GET", "/api/health") is None


def test_client_address_trusts_the_edge_header_only_behind_a_private_hop():
    # A public peer chooses nothing: its own address is the key, whatever it writes.
    assert client_address("8.8.8.8", {"cf-connecting-ip": "198.51.100.1", "x-forwarded-for": "198.51.100.2"}) == "8.8.8.8"
    # A private hop (tunnel connector, Docker's port proxy) carries the edge's view of the caller.
    assert client_address("172.18.0.1", {"cf-connecting-ip": "198.51.100.1"}) == "198.51.100.1"
    assert client_address("127.0.0.1", {"cf-connecting-ip": "2001:db8::1"}) == "2001:db8::1"
    # X-Forwarded-For is never read; a malformed edge header is ignored; no peer fails closed to one bucket.
    assert client_address("172.18.0.1", {"x-forwarded-for": "198.51.100.2"}) == "172.18.0.1"
    assert client_address("172.18.0.1", {"cf-connecting-ip": "not-an-ip"}) == "172.18.0.1"
    assert client_address(None, {}) == "unknown"


@pytest.fixture
def signin_client(monkeypatch):
    monkeypatch.setattr(app_module, "AUTH_ENABLED", True)
    monkeypatch.setattr(app_module, "_ROUTE_LIMITERS", {})
    return TestClient(app_module.app, client=("203.0.113.7", 50000))


def test_sign_in_start_is_limited_per_address_with_the_sibling_429(signin_client):
    statuses = [signin_client.get("/auth/google", follow_redirects=False).status_code for _ in range(21)]
    assert 429 not in statuses[:20]
    last = signin_client.get("/auth/google", follow_redirects=False)
    assert last.status_code == 429
    body = last.json()["detail"]
    assert body["category"] == "rate_limited" and body["retryable"] is True
    assert int(last.headers["retry-after"]) >= 1
    # The refusal says nothing about any account.
    assert "account" not in json.dumps(body).casefold() and "@" not in json.dumps(body)


def test_another_address_is_not_blocked_by_the_first(signin_client):
    for _ in range(25):
        signin_client.get("/auth/google", follow_redirects=False)
    other = TestClient(app_module.app, client=("203.0.113.8", 50000))
    assert other.get("/auth/google", follow_redirects=False).status_code != 429


def test_callback_and_native_exchange_are_limited_too(signin_client):
    callback = [signin_client.get("/auth/google/callback", follow_redirects=False).status_code for _ in range(31)]
    assert callback[-1] == 429 and 429 not in callback[:30]
    exchange = [signin_client.post("/api/auth/native/exchange", json={"code": "x"}).status_code for _ in range(31)]
    assert exchange[-1] == 429 and 429 not in exchange[:30]


def test_sign_in_is_not_limited_when_sign_in_is_off(monkeypatch):
    monkeypatch.setattr(app_module, "AUTH_ENABLED", False)
    monkeypatch.setattr(app_module, "_ROUTE_LIMITERS", {})
    client = TestClient(app_module.app, client=("203.0.113.7", 50000))
    assert all(client.get("/auth/google", follow_redirects=False).status_code != 429 for _ in range(25))


# ---- f: analytics ----------------------------------------------------------------------------------------------

NOW = datetime(2026, 1, 8, 12, tzinfo=UTC)


def _row(uid, secret, **extra):
    return {"learner_key": uid, "participant_code": participant_code(uid, secret), "skill": "writing",
            "occurred_at": "2026-01-08T10:00:00+00:00", "completed": True, **extra}


def test_participant_code_is_stable_keyed_and_reveals_nothing():
    assert participant_code("user-1", "s1") == participant_code("user-1", "s1")
    assert participant_code("user-1", "s1") != participant_code("user-2", "s1")
    assert participant_code("user-1", "s1") != participant_code("user-1", "s2")
    code = participant_code("user-1", "s1")
    assert code.startswith("P-") and len(code) == 14 and "user-1" not in code


def test_aggregates_carry_target_and_interface_language_separately_by_participant_code():
    rows = [
        _row("a", "k", target_lang="en", interface_lang="vi"),
        _row("a", "k", target_lang="en", interface_lang="vi", skill="reading"),
        _row("b", "k", target_lang="zh", interface_lang="en"),
        _row("c", "k", target_lang="en", interface_lang="vi"),
    ]
    result = aggregate_product_activity(rows, now=NOW)
    pairs = {(p["target_lang"], p["interface_lang"]): p["participants"] for p in result["language_pairs"]}
    assert pairs == {("en", "vi"): 2, ("zh", "en"): 1}
    by_code = {p["participant_code"]: p for p in result["participants"]}
    assert set(by_code) == {participant_code(x, "k") for x in "abc"}
    mine = by_code[participant_code("a", "k")]
    assert (mine["target_lang"], mine["interface_lang"], mine["activities"], mine["skills"]) == ("en", "vi", 2, ["reading", "writing"])
    # Neither the internal learner key nor any identity appears anywhere in the output.
    dumped = json.dumps(result)
    assert "learner_key" not in dumped and '"a"' not in dumped


def test_no_learner_free_text_or_audio_reaches_the_analytics_output():
    secret_values = ["MY PRIVATE ESSAY", "spoken transcript words", "https://media.example/take.webm", "me@example.com", "Real Name"]
    rows = [_row("a", "k", target_lang="en", interface_lang="vi", text=secret_values[0], transcript=secret_values[1],
                 audio_url=secret_values[2], email=secret_values[3], name=secret_values[4], content=secret_values[0])]
    result = aggregate_product_activity(rows, now=NOW)
    dumped = json.dumps(result)
    assert not any(value in dumped for value in secret_values)
    allowed_participant_keys = {"participant_code", "target_lang", "interface_lang", "activities", "completions", "active_days", "skills"}
    assert all(set(p) == allowed_participant_keys for p in result["participants"])
    assert all(set(p) == {"target_lang", "interface_lang", "participants"} for p in result["language_pairs"])


def test_stored_analytics_rows_select_no_text_transcript_or_audio_columns():
    """The rows the repository hands to analytics: only these keys, and the query selects no content column."""
    source = inspect.getsource(PostgresSpecializedLearningRepository.list_product_activity_events).split('"""')[2]
    for forbidden in (".content", ".text", ".body", "transcript", "audio", "email", "display_name", "storage", "url"):
        assert forbidden not in source.casefold().replace("funnel_key", ""), forbidden
    for key in ("participant_code", "target_lang", "interface_lang"):
        assert f'"{key}"' in source
