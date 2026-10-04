from __future__ import annotations

import pytest
from pathlib import Path

from scripts.validate_public_staging_readiness import read_env_file
from writing_coach.core.deployment import CALLBACK_PATH, resolve_deployment_config


def config(**values: str) -> dict[str, str]:
    return {"APP_ENV": "development", **values}


def test_local_callback_derives_from_local_public_origin() -> None:
    resolved = resolve_deployment_config(config(PUBLIC_BASE_URL="http://127.0.0.1:8000"))
    assert resolved.google_redirect_uri == f"http://127.0.0.1:8000{CALLBACK_PATH}"
    assert resolved.cookie_secure is False


def test_production_https_callback_and_secure_cookie() -> None:
    resolved = resolve_deployment_config({
        "APP_ENV": "production",
        "PUBLIC_BASE_URL": "https://becoming.example.com/",
        "GOOGLE_CLIENT_ID": "client-id",
        "GOOGLE_CLIENT_SECRET": "client-secret",
        "SESSION_SECRET": "session-secret",
    })
    assert resolved.public_base_url == "https://becoming.example.com"
    assert resolved.google_redirect_uri == f"https://becoming.example.com{CALLBACK_PATH}"
    assert resolved.cookie_secure is True


def test_same_origin_explicit_callback_override_is_supported() -> None:
    resolved = resolve_deployment_config(config(
        PUBLIC_BASE_URL="https://preview.example.com",
        GOOGLE_REDIRECT_URI="https://preview.example.com/auth/google/callback",
    ))
    assert resolved.google_redirect_uri == "https://preview.example.com/auth/google/callback"


@pytest.mark.parametrize(
    "override",
    [
        "https://login.example.com/auth/google/callback",
        "https://preview.example.com:8443/auth/google/callback",
        "http://preview.example.com/auth/google/callback",
    ],
)
def test_explicit_callback_override_must_use_public_origin(override: str) -> None:
    with pytest.raises(RuntimeError, match="same origin"):
        resolve_deployment_config(config(
            PUBLIC_BASE_URL="https://preview.example.com",
            GOOGLE_REDIRECT_URI=override,
        ))


@pytest.mark.parametrize(
    "public_base_url",
    [
        "https://example.com:abc",
        "https://example.com:70000",
        "https://localhost.",
        "https://sub.localhost",
        "https://127.0.0.2",
        "https://0.0.0.0",
        "https://[::1]",
        "https://[::]",
    ],
)
def test_production_rejects_invalid_ports_and_unsafe_hosts(public_base_url: str) -> None:
    with pytest.raises(RuntimeError):
        resolve_deployment_config({
            "APP_ENV": "production",
            "PUBLIC_BASE_URL": public_base_url,
            "GOOGLE_CLIENT_ID": "client-id",
            "GOOGLE_CLIENT_SECRET": "client-secret",
            "SESSION_SECRET": "session-secret",
        })


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"APP_ENV": "production", "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "secret", "SESSION_SECRET": "x"}, "PUBLIC_BASE_URL"),
        ({"APP_ENV": "production", "PUBLIC_BASE_URL": "http://becoming.example.com", "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "secret", "SESSION_SECRET": "x"}, "HTTPS"),
        ({"APP_ENV": "production", "PUBLIC_BASE_URL": "https://becoming.example.com", "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "secret"}, "SESSION_SECRET"),
        ({"APP_ENV": "production", "PUBLIC_BASE_URL": "https://becoming.example.com", "SESSION_SECRET": "x"}, "Google authentication"),
    ],
)
def test_production_rejects_dangerous_auth_configuration(values: dict[str, str], message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        resolve_deployment_config(values)


def test_auth_security_flow_remains_state_nonce_and_pkce_bound() -> None:
    source = (Path(__file__).resolve().parents[1] / "auth_support.py").read_text(encoding="utf-8")
    for token in ["oauth_state", "oauth_nonce", "oauth_code_verifier", "compare_digest", "verify_oauth2_token", "email_verified"]:
        assert token in source


def test_readiness_and_compose_keep_public_deployment_non_sensitive_and_configurable() -> None:
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "app.py").read_text(encoding="utf-8")
    auth_source = (root / "auth_support.py").read_text(encoding="utf-8")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    readiness = app_source.split('@app.get("/api/readiness")', 1)[1].split("TASK_TYPE_GUIDANCE", 1)[0]
    assert '"/api/readiness"' in auth_source
    assert "SESSION_SECRET" not in readiness
    assert "GOOGLE_CLIENT_SECRET" not in readiness
    assert '"${APP_BIND_HOST:-0.0.0.0}:8000:8000"' in compose
    assert "APP_BIND_HOST=0.0.0.0" in (root / ".env.example").read_text(encoding="utf-8")


def test_health_contract_retains_platform_admin_field() -> None:
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    health = app_source.split('@app.get("/api/health")', 1)[1].split('@app.get("/api/readiness")', 1)[0]
    assert '"platform_admin": True' in health


def test_environment_example_remains_a_usable_development_configuration() -> None:
    root = Path(__file__).resolve().parents[1]
    values = read_env_file(root / ".env.example")
    resolved = resolve_deployment_config(values)
    assert resolved.app_env == "development"
    assert resolved.public_base_url == "http://127.0.0.1:8000"
    assert values["APP_BIND_HOST"] == "0.0.0.0"
    assert values["PERSISTENCE_BACKEND"] == "postgresql"
    assert values["POSTGRES_RUNTIME_URL"] == (
        "postgresql+psycopg://becoming:becoming-local-dev@postgres:5432/becoming"
    )
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert "PostgreSQL by default in local development" in example
    assert "SQLite is retained only for explicit tests" in example
    assert "Production-like staging additionally requires APP_BIND_HOST=127.0.0.1" in example
    assert (root / "VERSION").read_text(encoding="utf-8").strip() == "1.4.0"


def test_the_reading_worker_runs_as_its_own_restarting_service_on_the_shared_data_volume():
    root = Path(__file__).resolve().parents[1]
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    block = compose.split("\n  reading-worker:\n", 1)[1].split("\n\n  ", 1)[0]
    assert 'command: ["python", "-m", "writing_coach.reading_worker"]' in block
    assert "restart: unless-stopped" in block
    assert "writing_data:/data" in block and "READING_LIBRARY_ASSET_ROOT: /data/reading_library_assets" in block
    assert "ports:" not in block, "the worker serves nothing"
