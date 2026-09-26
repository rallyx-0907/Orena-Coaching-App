"""The cutover tooling refuses everything but the admin sandbox (D-083), and
never prints a secret."""
from __future__ import annotations

import importlib.util
import os
import re
import uuid
from pathlib import Path
from urllib.parse import quote, urlparse

import pytest

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


def test_apply_needs_the_cluster_and_the_revision_before_anything_is_connected(monkeypatch, capsys):
    monkeypatch.setattr(cutover, "identity", lambda url: (_ for _ in ()).throw(AssertionError("connected")))
    monkeypatch.setattr(cutover, "apply", lambda *a, **k: (_ for _ in ()).throw(AssertionError("applied")))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8012")
    base = ["apply", "--url", SANDBOX_DB, "--confirm-sandbox", "orena"]
    assert cutover.main(base + ["--from", "20260924_0015"]) == 2
    assert "--expect-cluster" in capsys.readouterr().out
    assert cutover.main(base + ["--expect-cluster", "1"]) == 2
    assert "--from" in capsys.readouterr().out
    # The production database is refused before either.
    assert cutover.main(["apply", "--url", "postgresql+psycopg://u:p@postgres:5432/becoming",
                         "--confirm-sandbox", "becoming", "--expect-cluster", "1", "--from", "x"]) == 2
    assert "production" in capsys.readouterr().out


def test_bootstrap_never_crosses_the_cutover_revision():
    bootstrap = _load("bootstrap_runtime_schema")
    assert bootstrap.gated_revision_between("20260924_0015", "20260924_0016") == "20260924_0016"
    assert bootstrap.gated_revision_between("20260924_0016", "20260924_0016") is None
    assert cutover.CUTOVER_REVISION in bootstrap.GATED_REVISIONS
    assert "reading_canonical_cutover.py apply" in bootstrap.GATED_REVISIONS[cutover.CUTOVER_REVISION]


PG_URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")


@pytest.mark.skipif(not PG_URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
def test_apply_checks_and_migrates_on_one_connection_or_changes_nothing(capsys):
    """Against a real server: a wrong cluster, a wrong revision and a wrong
    database all leave the database at 20260924_0015; the confirmed one in
    the pinned cluster is migrated to 20260924_0016 by the same command."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    schema = f"cutover_apply_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in PG_URL else "?"
    url = f"{PG_URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(PG_URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(config, "20260924_0015")

        def revision() -> str:
            engine = create_engine(url, future=True)
            try:
                with engine.connect() as connection:
                    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            finally:
                engine.dispose()

        found = cutover.identity(url)
        assert found["database"] and found["cluster"]
        database, cluster = found["database"], found["cluster"]
        for kwargs in (
            {"confirmed": database, "expect_cluster": "1", "from_revision": "20260924_0015"},
            {"confirmed": database, "expect_cluster": cluster, "from_revision": "20260922_0012"},
            {"confirmed": "some_other_database", "expect_cluster": cluster, "from_revision": "20260924_0015"},
        ):
            assert cutover.apply(url, **kwargs) == 2, kwargs
            assert revision() == "20260924_0015", kwargs
        assert cutover.apply(url, confirmed=database, expect_cluster=cluster, from_revision="20260924_0015") == 0
        assert revision() == "20260924_0016"
        out = capsys.readouterr().out
        assert f"cluster {cluster}" in out and "applied" in out
        # Applied once: a second run finds the database past --from and refuses.
        assert cutover.apply(url, confirmed=database, expect_cluster=cluster, from_revision="20260924_0015") == 2
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_apply_takes_only_the_cutover_step_and_refuses_any_other_from_before_connecting(monkeypatch, capsys):
    """`apply` is 20260924_0015 -> 20260924_0016 and nothing else: a --from that
    matched some other database's revision would carry it across revisions this
    command was never meant to apply."""
    monkeypatch.setattr(cutover, "_engine", lambda url: (_ for _ in ()).throw(AssertionError("connected")))
    for other in ("20260922_0012", "20260924_0016", "", "head"):
        assert cutover.apply(SANDBOX_DB, confirmed="orena", expect_cluster="1", from_revision=other) == 2, other
        assert "refused" in capsys.readouterr().out
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8012")
    assert cutover.main(["apply", "--url", SANDBOX_DB, "--confirm-sandbox", "orena", "--expect-cluster", "1",
                         "--from", "20260922_0012"]) == 2
    assert "only 20260924_0015 -> 20260924_0016" in capsys.readouterr().out


@pytest.mark.skipif(not PG_URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
def test_a_database_at_an_earlier_revision_cannot_be_migrated_by_the_cutover_command(capsys):
    """A real database at 20260922_0012, with --from 20260922_0012 that matches
    it, the right database and the right cluster: still refused, still at
    20260922_0012."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    schema = f"cutover_early_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in PG_URL else "?"
    url = f"{PG_URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(PG_URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "migrations"))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(config, "20260922_0012")
        found = cutover.identity(url)
        assert cutover.apply(url, confirmed=found["database"], expect_cluster=found["cluster"],
                             from_revision="20260922_0012") == 2
        assert "only 20260924_0015 -> 20260924_0016" in capsys.readouterr().out
        engine = create_engine(url, future=True)
        try:
            with engine.connect() as connection:
                assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() \
                    == "20260922_0012"
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
