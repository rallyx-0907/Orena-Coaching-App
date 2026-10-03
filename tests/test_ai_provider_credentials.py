from __future__ import annotations

import json
import secrets
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import Request, Response

from writing_coach.ai.credentials import (
    MASTER_KEY_ENV,
    ProviderCredentialStoreError,
    decrypt_credentials,
    encrypt_credentials,
)
from writing_coach.persistence.platform_repository import SQLitePlatformRepository

import writing_coach.ai.platform as platform_module


@pytest.mark.parametrize("mode,uses_config", [("legacy", False), ("capability", True)])
def test_admin_config_reports_actual_runtime_routing(monkeypatch, mode, uses_config):
    monkeypatch.setenv("AI_RUNTIME_MODE", mode)
    monkeypatch.setattr(platform_module, "_require_admin", lambda request: {"google_sub": "admin"})
    monkeypatch.setattr(platform_module, "_installed_platform_repository", lambda: object())
    monkeypatch.setattr(platform_module, "AIControlPlane", lambda repository: SimpleNamespace(
        inspect=lambda: {"policy": {"learner_runtime_uses_capability_config": False}},
    ))
    data = platform_module.admin_ai_config(Request({"type": "http", "headers": []}))
    assert data["learner_runtime"]["mode"] == mode
    assert data["policy"]["learner_runtime_uses_capability_config"] is uses_config


def test_provider_credential_round_trip_is_encrypted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MASTER_KEY_ENV, Fernet.generate_key().decode("ascii"))
    secret = "token-" + secrets.token_urlsafe(12)

    envelope = encrypt_credentials(
        "gemini",
        {"api_key": secret, "base_url": "https://provider.example/v1"},
    )

    assert envelope["provider"] == "gemini"
    assert secret not in json.dumps(envelope)
    assert decrypt_credentials("gemini", envelope)["api_key"] == secret


def test_provider_credential_requires_the_bootstrap_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MASTER_KEY_ENV, raising=False)

    with pytest.raises(ProviderCredentialStoreError):
        encrypt_credentials("gemini", {"api_key": "token-" + secrets.token_urlsafe(12)})


def test_sqlite_repository_persists_only_the_encrypted_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(MASTER_KEY_ENV, Fernet.generate_key().decode("ascii"))
    secret = "token-" + secrets.token_urlsafe(12)
    repository = SQLitePlatformRepository(tmp_path / "platform.db")
    repository.initialize()
    envelope = encrypt_credentials("gemini", {"api_key": secret, "models": ["gemini-2.5-flash"]})

    repository.set_provider_credential("gemini", envelope, updated_by="qa-admin")

    stored = repository.get_provider_credential("gemini")
    assert stored == envelope
    assert secret not in json.dumps(stored)
    assert decrypt_credentials("gemini", stored)["api_key"] == secret

    with repository.connect() as connection:
        row = connection.execute(
            "SELECT value_json FROM platform_settings WHERE key = ?",
            ("ai.provider_credential.gemini",),
        ).fetchone()
    assert row is not None
    assert secret not in str(row["value_json"])


def test_save_route_never_returns_the_submitted_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MASTER_KEY_ENV, Fernet.generate_key().decode("ascii"))
    secret = "token-" + secrets.token_urlsafe(12)

    class Repository:
        def __init__(self) -> None:
            self.value = None

        def get_provider_credential(self, _provider_id):
            return self.value

        def set_provider_credential(self, _provider_id, value, *, updated_by=""):
            self.value = value

    repository = Repository()
    provider = SimpleNamespace(
        id="gemini",
        name="Gemini API",
        kind="cloud",
        secret_mode="server-managed",
        configured=True,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.5-flash",
        list_models=lambda: ["gemini-2.5-flash"],
    )
    monkeypatch.setattr(platform_module, "_platform_repository", repository)
    monkeypatch.setattr(platform_module, "_admin_guard", lambda _request: {"google_sub": "qa-admin"})
    monkeypatch.setattr(platform_module, "providers", lambda: {"gemini": provider})
    monkeypatch.setattr(platform_module, "_credential_test", lambda _provider_id, _values: ["gemini-2.5-flash"])
    request = Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/api/admin/ai/credentials/gemini",
            "headers": [(b"host", b"testserver"), (b"origin", b"http://testserver")],
        }
    )

    result = platform_module.admin_ai_provider_credential_save(
        "gemini",
        platform_module.ProviderCredentialIn(
            api_key=secret,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            models=["gemini-2.5-flash"],
            default_model="gemini-2.5-flash",
        ),
        request,
        Response(),
    )

    assert secret not in json.dumps(result)
    assert result["secret_saved"] is True
    assert result["secret_exposed"] is False
    assert secret not in json.dumps(repository.value)


def test_connection_test_discovers_models_without_manual_model_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MASTER_KEY_ENV, Fernet.generate_key().decode("ascii"))
    secret = "token-" + secrets.token_urlsafe(12)
    provider = SimpleNamespace(
        id="gemini",
        name="Gemini API",
        kind="cloud",
        secret_mode="server-managed",
        configured=True,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setattr(platform_module, "_platform_repository", None)
    monkeypatch.setattr(platform_module, "_admin_guard", lambda _request: {"google_sub": "qa-admin"})
    monkeypatch.setattr(platform_module, "providers", lambda: {"gemini": provider})
    monkeypatch.setattr(
        platform_module,
        "_credential_test",
        lambda _provider_id, values: ["gemini-2.5-flash"] if not values["models"] else [],
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/ai/credentials/gemini/test",
            "headers": [(b"host", b"testserver"), (b"origin", b"http://testserver")],
        }
    )

    result = platform_module.admin_ai_provider_credential_test(
        "gemini",
        platform_module.ProviderCredentialIn(
            api_key=secret,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            models=[],
            default_model="",
        ),
        request,
        Response(),
    )

    assert result == {
        "ok": True,
        "provider": "gemini",
        "models": ["gemini-2.5-flash"],
        "secret_saved": False,
    }


@pytest.mark.parametrize("endpoint", ["http://provider.example/v1", "http://127.0.0.1:9000/v1"])
def test_cloud_provider_credentials_require_https(monkeypatch, endpoint):
    from fastapi import HTTPException
    provider = SimpleNamespace(id="gemini", secret_mode="server-managed", base_url=endpoint)
    monkeypatch.setattr(platform_module, "_platform_repository", None)
    monkeypatch.setattr(platform_module, "providers", lambda: {"gemini": provider})
    with pytest.raises(HTTPException) as error:
        platform_module._provider_credential_values("gemini", platform_module.ProviderCredentialIn(
            api_key="synthetic-qa-key", base_url=endpoint), require_models=False)
    assert error.value.status_code == 400
    assert "HTTPS" in error.value.detail


def test_local_provider_without_credentials_can_use_http(monkeypatch):
    provider = SimpleNamespace(id="ollama", secret_mode="none", base_url="http://127.0.0.1:11434")
    monkeypatch.setattr(platform_module, "_platform_repository", None)
    monkeypatch.setattr(platform_module, "providers", lambda: {"ollama": provider})
    values = platform_module._provider_credential_values(
        "ollama", platform_module.ProviderCredentialIn(), require_models=False,
    )
    assert values["base_url"] == "http://127.0.0.1:11434"
    assert values["api_key"] == ""


def test_provider_credential_values_normalizes_a_pasted_bearer_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "token-" + secrets.token_urlsafe(12)
    provider = SimpleNamespace(
        id="gemini",
        name="Gemini API",
        secret_mode="server-managed",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setattr(platform_module, "_platform_repository", None)
    monkeypatch.setattr(platform_module, "providers", lambda: {"gemini": provider})

    values = platform_module._provider_credential_values(
        "gemini",
        platform_module.ProviderCredentialIn(
            api_key=f"Bearer {secret}",
            base_url=provider.base_url,
            models=[],
            default_model="",
        ),
        require_models=False,
    )

    assert values["api_key"] == secret
