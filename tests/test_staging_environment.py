"""APP_ENV=staging (D-146): public and product-like.

Staging is the runtime people test the product on (:8000 and the public domain). It keeps every public security
requirement production has, and it is not a feature switch: a learner capability is on where its own flag says so.
Developer tooling stays development-only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from auth_support import _local_admin_allowed
from scripts.validate_public_staging_readiness import validate_public_staging_readiness
from writing_coach.agent.api import agent_enabled, voice_enabled
from writing_coach.core.deployment import (
    environment_name,
    is_public_environment,
    resolve_deployment_config,
)
from writing_coach.listening_catalog import dev_catalog_enabled

ROOT = Path(__file__).resolve().parents[1]
SECRET = "s" * 40
PUBLIC = {
    "PUBLIC_BASE_URL": "https://orena.example",
    "GOOGLE_CLIENT_ID": "id",
    "GOOGLE_CLIENT_SECRET": "secret",
    "SESSION_SECRET": SECRET,
}


def _staging(**updates: str) -> dict[str, str]:
    return {"APP_ENV": "staging", **PUBLIC, **updates}


# ---- the environment itself ----------------------------------------------------------------------------------------


def test_staging_is_a_first_class_public_environment():
    config = resolve_deployment_config(_staging())
    assert config.app_env == "staging"
    assert config.public is True
    assert config.production is False, "staging is not the final product"
    assert config.cookie_secure is True
    assert config.developer_docs is False
    assert config.google_redirect_uri == "https://orena.example/auth/google/callback"
    assert environment_name("stage") == "staging"
    assert is_public_environment("staging") and is_public_environment("production")
    assert not is_public_environment("development") and not is_public_environment("")


def test_development_keeps_its_developer_docs_and_is_not_public():
    config = resolve_deployment_config({})
    assert config.app_env == "development" and config.public is False and config.developer_docs is True


def test_an_unknown_environment_is_refused():
    with pytest.raises(RuntimeError, match="development, staging or production"):
        resolve_deployment_config({"APP_ENV": "qa"})


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"PUBLIC_BASE_URL": ""}, "PUBLIC_BASE_URL is required"),
        ({"PUBLIC_BASE_URL": "http://orena.example"}, "HTTPS"),
        ({"PUBLIC_BASE_URL": "https://localhost"}, "non-local"),
        ({"PUBLIC_BASE_URL": "https://127.0.0.1"}, "non-local"),
        ({"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}, "Google authentication"),
        ({"SESSION_SECRET": ""}, "SESSION_SECRET"),
        ({"SESSION_SECRET": "short"}, "32 characters"),
        ({"GOOGLE_REDIRECT_URI": "https://other.example/auth/google/callback"}, "same origin"),
    ],
)
def test_staging_keeps_every_public_security_requirement(updates, message):
    with pytest.raises(RuntimeError, match=message):
        resolve_deployment_config(_staging(**updates))


def test_the_app_hides_developer_docs_on_a_public_runtime():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "_DEVELOPER_DOCS = DEPLOYMENT.developer_docs" in source
    assert 'docs_url="/docs" if _DEVELOPER_DOCS else None' in source
    assert 'openapi_url="/openapi.json" if _DEVELOPER_DOCS else None' in source
    assert 'APP_ENV == "production"' not in source, "no feature or tooling decision keyed on production alone"


# ---- security that applies to staging ------------------------------------------------------------------------------


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_a_public_runtime_never_has_a_local_admin(environment):
    assert _local_admin_allowed({"APP_ENV": environment, "ALLOW_LOCAL_ADMIN": "1"}) is False
    assert _local_admin_allowed({"APP_ENV": environment, "PUBLIC_BASE_URL": "http://127.0.0.1:8000"}) is False
    assert _local_admin_allowed({"APP_ENV": "development", "PUBLIC_BASE_URL": "http://127.0.0.1:8000"}) is True


def test_staging_serves_no_synthetic_pronunciation_score(monkeypatch):
    from writing_coach.speech_pronunciation import build_speech_pronunciation_provider

    monkeypatch.setenv("PRONUNCIATION_PROVIDER", "demo")
    monkeypatch.setenv("APP_ENV", "staging")
    assert build_speech_pronunciation_provider() is None


def test_staging_never_loads_generated_development_listening_content():
    assert dev_catalog_enabled({"ENABLE_DEV_LISTENING_CATALOG": "1", "APP_ENV": "staging"}) is False
    assert dev_catalog_enabled({"ENABLE_DEV_LISTENING_CATALOG": "1", "APP_ENV": "development"}) is True


def test_the_sandbox_only_reading_scripts_refuse_staging():
    spec = importlib.util.spec_from_file_location("reading_canonical_cutover", ROOT / "scripts" / "reading_canonical_cutover.py")
    cutover = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cutover)
    reason = cutover.refusal(url="postgresql+psycopg://orena:pw@db:5432/orena", app_url="",
                             environ={"APP_ENV": "staging"}, confirmed="orena")
    assert reason and "staging" in reason


def test_the_public_staging_readiness_check_accepts_staging():
    values = {
        **_staging(), "APP_BIND_HOST": "127.0.0.1", "PERSISTENCE_BACKEND": "postgresql",
        "POSTGRES_RUNTIME_URL": "postgresql+psycopg://orena:pw@postgres:5432/orena",
        "CLOUDFLARE_TUNNEL_TOKEN": "t" * 40,
    }
    report = validate_public_staging_readiness(values)
    assert "APP_ENV resolves to a public environment (staging)" in report.passed
    assert not any("APP_ENV" in error for error in report.errors)
    development = validate_public_staging_readiness({**values, "APP_ENV": "development"})
    assert any("public environment" in error for error in development.errors)


# ---- learner capabilities follow their own flags --------------------------------------------------------------------


def test_the_agent_is_on_in_staging_when_its_flag_says_so():
    assert agent_enabled({"APP_ENV": "staging", "AGENT_ENABLED": "true"}) is True
    assert agent_enabled({"APP_ENV": "staging"}) is False, "unset is absent"
    assert agent_enabled({"APP_ENV": "staging", "AGENT_ENABLED": "false"}) is False


def test_voice_stays_its_own_switch():
    assert voice_enabled({"APP_ENV": "staging", "AGENT_ENABLED": "true", "AGENT_VOICE_ENABLED": "false"}) is False
    assert voice_enabled({"APP_ENV": "staging", "AGENT_ENABLED": "true"}) is False
    assert voice_enabled({"APP_ENV": "staging", "AGENT_ENABLED": "true", "AGENT_VOICE_ENABLED": "true"}) is True


def test_no_runtime_branch_turns_a_feature_off_because_the_runtime_is_production():
    """D-146 audit: an APP_ENV comparison in the application is either a public-security rule (staging and production
    alike, through is_public_environment / DeploymentConfig.public) or developer tooling. A bare `== "production"`
    would be a feature switch keyed on the environment."""
    offenders = []
    for path in [ROOT / "app.py", ROOT / "auth_support.py", *(ROOT / "writing_coach").rglob("*.py")]:
        text = path.read_text(encoding="utf-8")
        for needle in ('APP_ENV == "production"', "APP_ENV == 'production'", '== "production":', "production=APP_ENV"):
            if needle in text:
                offenders.append(f"{path.relative_to(ROOT)}: {needle}")
    assert offenders == []
