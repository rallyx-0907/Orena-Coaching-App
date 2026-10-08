from __future__ import annotations

import pytest
from pathlib import Path

import scripts.validate_public_staging_readiness as staging_validator
from scripts.validate_public_staging_readiness import (
    read_env_file,
    render_report,
    validate_public_staging_readiness,
)
from writing_coach.core.deployment import CALLBACK_PATH, resolve_deployment_config


SECRETS = {
    "GOOGLE_CLIENT_SECRET": "google-secret-value",
    "SESSION_SECRET": "session-secret-value-for-tests-0123456789",
    "POSTGRES_RUNTIME_URL": (
        "postgresql+psycopg://staging-user:database-secret-value@postgres:5432/becoming"
    ),
    "POSTGRES_SHADOW_URL": (
        "postgresql+psycopg://shadow-user:shadow-secret-value@postgres:5432/shadow"
    ),
    "CLOUDFLARE_TUNNEL_TOKEN": "cloudflare-secret-value",
}


def valid_env(**updates: str) -> dict[str, str]:
    values = {
        "APP_ENV": "production",
        "APP_BIND_HOST": "127.0.0.1",
        "PUBLIC_BASE_URL": "https://staging.example.com",
        "GOOGLE_CLIENT_ID": "google-client-id",
        "PERSISTENCE_BACKEND": "postgresql",
        **SECRETS,
    }
    values.update(updates)
    return values


def assert_failed(values: dict[str, str], message: str) -> None:
    report = validate_public_staging_readiness(values)
    assert report.ok is False
    assert message in " ".join(report.errors)


def test_valid_production_postgresql_tunnel_staging_passes() -> None:
    report = validate_public_staging_readiness(valid_env())
    assert report.ok is True
    assert not report.errors
    assert "POSTGRES_SHADOW_URL excluded from runtime selection" in report.passed


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"APP_ENV": "development"}, "production"),
        ({"PUBLIC_BASE_URL": "http://staging.example.com"}, "HTTPS"),
        ({"PUBLIC_BASE_URL": "https://localhost"}, "non-local"),
        ({"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": ""}, "Google"),
        ({"SESSION_SECRET": ""}, "SESSION_SECRET"),
        ({"PERSISTENCE_BACKEND": "sqlite"}, "postgresql"),
        ({"POSTGRES_RUNTIME_URL": ""}, "POSTGRES_RUNTIME_URL"),
        ({"POSTGRES_RUNTIME_URL": "postgresql+psycopg://"}, "POSTGRES_RUNTIME_URL"),
        ({"APP_BIND_HOST": "0.0.0.0"}, "APP_BIND_HOST"),
        ({"CLOUDFLARE_TUNNEL_TOKEN": ""}, "CLOUDFLARE_TUNNEL_TOKEN"),
    ],
)
def test_unsafe_public_staging_configuration_fails(
    updates: dict[str, str], message: str
) -> None:
    assert_failed(valid_env(**updates), message)


def test_shadow_url_alone_cannot_satisfy_runtime() -> None:
    values = valid_env(POSTGRES_RUNTIME_URL="")
    assert values["POSTGRES_SHADOW_URL"]
    assert_failed(values, "POSTGRES_RUNTIME_URL")


def test_canonical_callback_comes_from_public_base_url() -> None:
    resolved = resolve_deployment_config(valid_env())
    assert resolved.google_redirect_uri == resolved.public_base_url + CALLBACK_PATH


def test_report_never_contains_injected_secret_values() -> None:
    values = valid_env(APP_BIND_HOST="unsafe-secret-host")
    output = render_report(validate_public_staging_readiness(values))
    for secret in SECRETS.values():
        assert secret not in output
    assert "google-secret-value" not in output
    assert "database-secret-value" not in output
    assert "shadow-secret-value" not in output
    assert "cloudflare-secret-value" not in output


def test_env_file_accepts_comments_blanks_and_last_assignment_wins(tmp_path: Path) -> None:
    fixture = tmp_path / "staging.env"
    fixture.write_text(
        "# ignored\n\nAPP_ENV=development\nAPP_ENV=production\n"
        "APP_BIND_HOST=127.0.0.1\nPUBLIC_BASE_URL=https://staging.example.com\n"
        "GOOGLE_CLIENT_ID=google-client-id\n"
        f"GOOGLE_CLIENT_SECRET={SECRETS['GOOGLE_CLIENT_SECRET']}\n"
        f"SESSION_SECRET={SECRETS['SESSION_SECRET']}\n"
        "PERSISTENCE_BACKEND=postgresql\n"
        f"POSTGRES_RUNTIME_URL={SECRETS['POSTGRES_RUNTIME_URL']}\n"
        f"POSTGRES_SHADOW_URL={SECRETS['POSTGRES_SHADOW_URL']}\n"
        f"CLOUDFLARE_TUNNEL_TOKEN={SECRETS['CLOUDFLARE_TUNNEL_TOKEN']}\n",
        encoding="utf-8",
    )
    values = read_env_file(fixture)
    assert values["APP_ENV"] == "production"
    assert validate_public_staging_readiness(values).ok is True


def test_env_file_cli_is_explicit_source_and_redacts_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = tmp_path / "staging.env"
    fixture.write_text("\n".join(f"{key}={value}" for key, value in valid_env().items()), encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr("sys.argv", ["validate_public_staging_readiness.py", "--env-file", str(fixture)])
    assert staging_validator.main() == 0
    output = capsys.readouterr().out
    assert "PUBLIC STAGING READINESS PASS" in output
    for secret in SECRETS.values():
        assert secret not in output


def test_missing_env_file_fails_without_leaking_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "secretly-named-missing.env"
    monkeypatch.setattr("sys.argv", ["validate_public_staging_readiness.py", "--env-file", str(missing)])
    assert staging_validator.main() == 1
    output = capsys.readouterr().out
    assert "Unable to read the requested environment file." in output
    assert str(missing) not in output
