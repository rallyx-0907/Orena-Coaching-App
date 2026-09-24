"""The cutover tooling refuses everything but the admin sandbox (D-076), and
never prints a secret."""
from __future__ import annotations

import importlib.util
from pathlib import Path

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


def test_production_and_preview_are_refused():
    sandbox = {"APP_ENV": "development", "PUBLIC_BASE_URL": "http://localhost:8012"}
    assert cutover.refusal(url=SANDBOX_DB, app_url="", environ=sandbox) is None
    assert "production" in cutover.refusal(url=SANDBOX_DB, app_url="", environ={"APP_ENV": "production"})
    for port in (8000, 8010):
        assert cutover.refusal(url=SANDBOX_DB, app_url="", environ={"PUBLIC_BASE_URL": f"http://host:{port}"})
        assert cutover.refusal(url=SANDBOX_DB, app_url=f"http://host:{port}", environ=sandbox)
        assert e2e._refused(f"http://localhost:{port}")
    assert cutover.refusal(url="", app_url="", environ=sandbox)
    assert cutover.refusal(url="sqlite:///x.db", app_url="", environ=sandbox)
    assert e2e._refused("http://localhost:8012") is None
    assert e2e._refused("localhost:8012")


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
