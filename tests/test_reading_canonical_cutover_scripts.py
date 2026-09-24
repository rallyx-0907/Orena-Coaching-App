"""The cutover tooling refuses everything but the admin sandbox (D-076), and
never prints a secret."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cutover = _load("reading_canonical_cutover")
e2e = _load("reading_canonical_e2e")
backup = _load("runtime_backup")
SANDBOX_DB = "postgresql+psycopg://orena:s3cret@db:5432/orena"


def _refusal(url=SANDBOX_DB, app_url="", environ=None, confirmed="orena"):
    environ = {"APP_ENV": "development", "PUBLIC_BASE_URL": "http://localhost:8012"} if environ is None else environ
    return cutover.refusal(url=url, app_url=app_url, environ=environ, confirmed=confirmed)


def test_production_and_preview_are_refused():
    assert _refusal() is None
    assert "production" in _refusal(environ={"APP_ENV": "production"})
    for port in (8000, 8010):
        assert _refusal(environ={"PUBLIC_BASE_URL": f"http://host:{port}"})
        assert _refusal(app_url=f"http://host:{port}")
        assert e2e._refused(f"http://localhost:{port}")
    assert _refusal(url="")
    assert _refusal(url="sqlite:///x.db")
    assert e2e._refused("http://localhost:8012") is None
    assert e2e._refused("http://127.0.0.1:8012") is None
    assert e2e._refused("localhost:8012")


def test_the_production_database_is_refused_by_name_even_from_a_clean_environment():
    """A pasted production URL, run from a shell whose environment says
    nothing, must still be refused - and the names refused are the ones the
    production compose file actually defaults to."""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    default = re.search(r"POSTGRES_RUNTIME_URL: \$\{POSTGRES_RUNTIME_URL:-([^}]+)\}", compose).group(1)
    parsed = urlparse(default)
    assert (parsed.hostname, parsed.path.lstrip("/")) == (cutover.PRODUCTION_HOST, cutover.PRODUCTION_DATABASE)
    for url in (default, "postgresql+psycopg://u:p@localhost:5432/becoming",
                "postgresql+psycopg://u:p@postgres:5432/orena_admin_sandbox"):
        reason = _refusal(url=url, environ={}, confirmed=urlparse(url).path.lstrip("/"))
        assert reason and "production" in reason, url


def test_the_sandbox_must_be_named_and_the_server_must_agree():
    assert "--confirm-sandbox" in _refusal(confirmed="")
    assert "nothing was touched" in _refusal(confirmed="orena_admin_sandbox")
    ok = {"database": "orena", "cluster": "7412345678901234567"}
    assert cutover.identity_refusal(ok, confirmed="orena", expect_cluster=None) is None
    assert cutover.identity_refusal(ok, confirmed="orena", expect_cluster="7412345678901234567") is None
    assert "not the confirmed" in cutover.identity_refusal({**ok, "database": "becoming"}, confirmed="orena",
                                                           expect_cluster=None)
    assert "nothing was touched" in cutover.identity_refusal(ok, confirmed="orena", expect_cluster="999")
    assert "cannot be pinned" in cutover.identity_refusal({**ok, "cluster": ""}, confirmed="orena",
                                                          expect_cluster="7412345678901234567")


def test_reset_needs_the_cluster_before_anything_is_connected(monkeypatch, capsys):
    monkeypatch.setattr(cutover, "identity", lambda url: (_ for _ in ()).throw(AssertionError("connected")))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8012")
    code =cutover.main(["reset-legacy", "--url", SANDBOX_DB, "--confirm-sandbox", "orena",
                         "--expect-sessions", "1", "--expect-attempts", "1"])
    assert code == 2 and "--expect-cluster" in capsys.readouterr().out


def test_the_e2e_refuses_a_public_host_and_a_server_that_says_production():
    assert "not this machine" in e2e._refused("https://orena.example.com")
    assert "not this machine" in e2e._refused("http://192.168.1.20:8012")

    class Answer:
        def __init__(self, environment):
            self.environment = environment

        def call(self, method, path, expect=200):
            assert (method, path) == ("GET", "/api/readiness")
            return {"environment": self.environment}

    assert "production" in e2e._server_refused(Answer("production"))
    assert e2e._server_refused(Answer("development")) is None


def test_nothing_prints_a_password():
    assert "s3cret" not in cutover.redacted(SANDBOX_DB)
    assert backup._redact("postgresql://orena:s3cret@db/orena") == "postgresql://orena:***@db/orena"
    assert backup._redact("--format=custom") == "--format=custom"


def test_the_inventory_masks_identity_and_only_hints():
    assert cutover.mask_email("ana.learner@gmail.com") == "a•••@gmail.com"
    assert cutover.mask_email("") == ""
    assert cutover.looks_like_test("legacy", "local@localhost.invalid")
    assert cutover.looks_like_test("sub-1", "qa@example.com")
    assert not cutover.looks_like_test("google-sub-1", "ana.learner@gmail.com")
