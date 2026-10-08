"""Security review fixes, 2026-10-04: cross-site changes, hardening headers, rate groups, local admin, secrets."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app as app_module
from auth_support import _local_admin_allowed
from writing_coach.core.http_security import hardening_headers, origin_refusal, rate_group


@pytest.mark.parametrize(("headers", "refused"), [
    ({"host": "orena.example", "origin": "https://orena.example"}, None),
    ({"host": "orena.example", "origin": "https://evil.example"}, "origin_mismatch"),
    ({"host": "orena.example", "origin": "https://staging.orena.example"}, "origin_mismatch"),
    ({"host": "orena.example", "origin": "null"}, "origin_null"),
    ({"host": "orena.example", "sec-fetch-site": "cross-site"}, "cross_site_request"),
    ({"host": "orena.example", "sec-fetch-site": "same-site"}, "cross_site_request"),
    ({"host": "orena.example", "sec-fetch-site": "same-origin"}, None),
    ({"host": "orena.example"}, None),  # not a browser's cross-site request (a script, the native exchange)
])  # fmt: skip
def test_a_state_change_is_refused_when_a_browser_says_it_came_from_elsewhere(headers, refused):
    assert origin_refusal("POST", "/api/essays/1", headers) == refused


def test_reads_and_unguarded_paths_are_never_refused():
    evil = {"host": "orena.example", "origin": "https://evil.example"}
    assert origin_refusal("GET", "/api/essays", evil) is None
    assert origin_refusal("POST", "/static/x", evil) is None
    assert origin_refusal("POST", "/api/auth/native/exchange", evil) is None


def test_the_app_refuses_a_cross_site_delete_and_hardens_every_answer():
    client = TestClient(app_module.app)
    refused = client.post("/api/vocabulary", json={}, headers={"origin": "https://evil.example"})
    assert refused.status_code == 403 and refused.json()["detail"]["category"] == "origin_refused"
    answer = client.get("/api/health")
    assert answer.headers["x-content-type-options"] == "nosniff"
    assert answer.headers["x-frame-options"] == "DENY"
    assert "referrer-policy" in answer.headers


def test_hsts_only_over_https_and_a_route_keeps_its_own_value():
    assert "Strict-Transport-Security" in hardening_headers({}, https=True)
    assert "Strict-Transport-Security" not in hardening_headers({}, https=False)
    assert "X-Frame-Options" not in hardening_headers({"x-frame-options": "SAMEORIGIN"}, https=False)


def test_paid_and_upload_routes_are_in_a_rate_group_and_polls_are_not():
    assert rate_group("POST", "/api/evaluate")[0] == "writing_ai"
    assert rate_group("POST", "/api/speech/transcribe")[0] == "speech_ai"
    assert rate_group("POST", "/api/reading/translate")[0] == "reading_ai"
    assert rate_group("POST", "/api/reading/summary")[0] == "reading_ai"
    assert rate_group("POST", "/api/media-learning/import")[0] == "media_learning"
    assert rate_group("POST", "/api/media-learning/import/status") is None
    assert rate_group("GET", "/api/evaluate") is None


@pytest.mark.parametrize(("environ", "allowed"), [
    ({}, True),
    ({"PUBLIC_BASE_URL": "http://localhost:8021"}, True),
    ({"PUBLIC_BASE_URL": "http://127.0.0.1:8000"}, True),
    ({"PUBLIC_BASE_URL": "https://orena.example"}, False),
    ({"PUBLIC_BASE_URL": "http://192.168.1.20:8000"}, False),
    ({"PUBLIC_BASE_URL": "https://orena.example", "ALLOW_LOCAL_ADMIN": "1"}, True),
])  # fmt: skip
def test_signed_out_local_admin_exists_only_on_this_machines_own_address(environ, allowed):
    assert _local_admin_allowed(environ) is allowed


def test_a_short_session_secret_is_refused_in_production():
    from writing_coach.core.deployment import resolve_deployment_config

    base = {"APP_ENV": "production", "PUBLIC_BASE_URL": "https://orena.example", "GOOGLE_CLIENT_ID": "id",
            "GOOGLE_CLIENT_SECRET": "secret", "GOOGLE_REDIRECT_URI": "https://orena.example/auth/google/callback"}  # fmt: skip
    with pytest.raises(RuntimeError, match="32 characters"):
        resolve_deployment_config({**base, "SESSION_SECRET": "short"})
    resolve_deployment_config({**base, "SESSION_SECRET": "x" * 40})


def test_a_stored_file_is_never_served_as_a_page():
    from writing_coach.media_library_api import _SERVED_TYPES
    from writing_coach.media_source_import import _safe_suffix

    assert ".html" not in _SERVED_TYPES and ".svg" not in _SERVED_TYPES
    assert _safe_suffix("x.html") == ".bin" and _safe_suffix("talk.MP3") == ".mp3"
