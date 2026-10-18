"""Deploy blockers B3/B4/B8 (audit 2026-10-18): real readiness, no query strings in logs, CSP Report-Only."""

from __future__ import annotations

import logging
from dataclasses import replace

from fastapi.testclient import TestClient

import app as app_module
from writing_coach.core.access_log import QueryStringScrubFilter, configure_access_log, log_request, scrub_text, scrub_url
from writing_coach.core.http_security import CSP_REPORT_ONLY, hardening_headers, inline_script_hashes


class _DownEngine:
    def connect(self):
        raise RuntimeError("could not connect to server at db.internal.example:5432 password=hunter2")


class _UpEngine:
    def connect(self):
        class _Connection:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, statement):
                assert str(statement) == "SELECT 1"

        return _Connection()


def test_readiness_is_503_with_a_stable_reason_and_no_detail_when_the_database_is_down(monkeypatch):
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, engine=_DownEngine()))
    answer = TestClient(app_module.app).get("/api/readiness")
    assert answer.status_code == 503
    body = answer.json()
    assert body["ready"] is False and body["reason"] == "database_unavailable"
    assert "db.internal" not in answer.text and "hunter2" not in answer.text


def test_readiness_is_200_when_the_database_answers(monkeypatch):
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, engine=_UpEngine()))
    answer = TestClient(app_module.app).get("/api/readiness")
    assert answer.status_code == 200 and answer.json()["ready"] is True


def test_access_log_line_has_method_path_status_duration_and_no_query(caplog):
    configure_access_log()
    logger = logging.getLogger("orena.access")
    logger.propagate = True  # caplog listens on the root logger
    try:
        with caplog.at_level("INFO", logger="orena.access"):
            log_request("GET", "/auth/google/callback?state=abc&code=SECRET", 302, 12.4)
    finally:
        logger.propagate = False
    line = caplog.records[-1].getMessage()
    assert line == "GET /auth/google/callback 302 12ms" and "SECRET" not in line


def test_uvicorn_access_filter_drops_the_query_string():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("1.2.3.4:5", "GET", "/auth/google/callback?code=SECRET", "1.1", 302), None)
    QueryStringScrubFilter().filter(record)
    assert "SECRET" not in record.getMessage() and "/auth/google/callback " in record.getMessage()


def test_url_scrub_keeps_scheme_host_path_only():
    assert scrub_url("https://user:pw@feeds.example.org:8443/a/b.xml?token=T#frag") == "https://feeds.example.org:8443/a/b.xml"
    assert scrub_text("GET https://x.example/f?k=V failed (https://y.example/p?q=W)") == "GET https://x.example/f failed (https://y.example/p)"


def test_html_pages_carry_a_report_only_csp_and_json_does_not():
    client = TestClient(app_module.app)
    page = client.get("/privacy?lang=en")
    policy = page.headers[CSP_REPORT_ONLY.lower()]
    for part in ("default-src 'self'", "frame-ancestors 'none'", "https://www.youtube-nocookie.com", "https://www.youtube.com"):
        assert part in policy
    assert "content-security-policy" not in page.headers
    assert CSP_REPORT_ONLY.lower() not in client.get("/api/health").headers
    assert CSP_REPORT_ONLY in hardening_headers({"content-type": "text/html; charset=utf-8"}, https=False)
    assert inline_script_hashes() and all(policy.count(h) == 1 for h in inline_script_hashes())
