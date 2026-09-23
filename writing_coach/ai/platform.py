from __future__ import annotations

import logging
import os
from time import perf_counter
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr

from writing_coach.ai.base import (
    AICapabilityError,
    AICapabilityConfigInvalid,
    AICapabilityDisabled,
    AICapabilityNotConfigured,
    AICapabilityUnsupported,
    AIModelCatalogEmpty,
    AIModelUnavailable,
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
    AIResult,
    normalized_latency,
    normalized_rate_limit,
    normalized_usage,
    sanitize_telemetry,
    telemetry_error_class,
)
from writing_coach.ai.capabilities import require_capability
from writing_coach.ai.config import CapabilityConfig, validate_capability_config
from writing_coach.ai.control_plane import (
    AIControlPlane,
    safe_capability_display,
    safe_model_display,
)
from writing_coach.ai.credentials import (
    ProviderCredentialStoreError,
    decrypt_credentials,
    encrypt_credentials,
)
from writing_coach.ai.pricing import estimate_token_cost
from writing_coach.ai.routing import (
    Attempt,
    ProviderTarget,
    build_chain,
    run_chain,
)
from writing_coach.ai.providers import build_providers, provider_definitions
from writing_coach.persistence.platform_repository import PlatformRepository

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DB_PATH = Path(os.getenv("PLATFORM_DB", ROOT / "data" / "platform.db"))
_admin_guard: Callable[[Request], dict[str, Any]] | None = None
_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ai", tags=["platform-admin"])


class AIRuntimeMode(str, Enum):
    LEGACY = "legacy"
    CAPABILITY = "capability"


def runtime_mode() -> AIRuntimeMode:
    """Return the single learner-routing mode; legacy remains the default."""

    value = os.getenv("AI_RUNTIME_MODE", AIRuntimeMode.LEGACY).strip().casefold()
    try:
        return AIRuntimeMode(value)
    except ValueError as exc:
        raise AICapabilityConfigInvalid(f"Unsupported AI runtime mode: {value!r}.") from exc


class AIConfigIn(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    model: str = Field(min_length=1, max_length=160)


class CapabilityConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=160)
    backup_provider: str | None = Field(default=None, min_length=1, max_length=40)
    backup_model: str | None = Field(default=None, min_length=1, max_length=160)
    timeout_seconds: int | None = None
    temperature: float | None = None
    fallback_policy: str = "none"


class ProviderCredentialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr | None = Field(default=None, max_length=4096)
    base_url: AnyHttpUrl | None = None
    models: list[str] = Field(default_factory=list, max_length=100)
    default_model: str = Field(default="", max_length=160)


_platform_repository: PlatformRepository | None = None

def _installed_platform_repository() -> PlatformRepository:
    if _platform_repository is None:
        raise RuntimeError("Platform repository has not been installed by the persistence runtime.")
    return _platform_repository

def configure_platform_repository(repository: PlatformRepository) -> None:
    global _platform_repository
    _platform_repository = repository


def init_platform_ai_db() -> None:
    _installed_platform_repository().initialize()


def providers() -> dict[str, Any]:
    stored: dict[str, dict[str, Any]] = {}
    if _platform_repository is not None:
        for definition in provider_definitions():
            envelope = _platform_repository.get_provider_credential(definition.id)
            if not envelope:
                continue
            try:
                stored[definition.id] = decrypt_credentials(definition.id, envelope)
            except ProviderCredentialStoreError:
                # A broken/missing encryption key fails closed for UI-managed
                # credentials; environment-managed credentials remain usable.
                continue
    return build_providers(stored)


_PROVIDER_CONFIG_META: dict[str, dict[str, str | None]] = {
    "ollama": {
        "endpoint_env": "OLLAMA_URL",
        "credential_env": None,
        "model_env": "OLLAMA_MODEL",
        "models_env": None,
    },
    "openai": {
        "endpoint_env": "OPENAI_BASE_URL",
        "credential_env": "OPENAI_API_KEY",
        "model_env": None,
        "models_env": "OPENAI_MODELS",
    },
    "deepseek": {
        "endpoint_env": "DEEPSEEK_BASE_URL",
        "credential_env": "DEEPSEEK_API_KEY",
        "model_env": None,
        "models_env": "DEEPSEEK_MODELS",
    },
    "groq": {
        "endpoint_env": "GROQ_BASE_URL",
        "credential_env": "GROQ_API_KEY",
        "model_env": None,
        "models_env": "GROQ_MODELS",
    },
    "gemini": {
        "endpoint_env": "GEMINI_BASE_URL",
        "credential_env": "GEMINI_API_KEY",
        "model_env": None,
        "models_env": "GEMINI_MODELS",
    },
}


def _provider_snapshot(item: Any) -> dict[str, Any]:
    raw_models = item.list_models()
    displayed_models = [safe_model_display(model) for model in raw_models]
    raw_default = getattr(item, "default_model", "") or (
        raw_models[0] if raw_models else ""
    )
    default_model, default_model_redacted = safe_model_display(raw_default)
    config_meta = _PROVIDER_CONFIG_META.get(item.id, {})
    credential_env = config_meta.get("credential_env")
    stored_credential = False
    if _platform_repository is not None:
        credential_reader = getattr(_platform_repository, "get_provider_credential", None)
        stored_credential = bool(credential_reader(item.id)) if callable(credential_reader) else False
    return {
        "id": item.id,
        "name": item.name,
        "kind": item.kind,
        "configured": bool(item.configured),
        "available": bool(raw_models),
        "models": [model for model, _redacted in displayed_models],
        "models_redacted": any(redacted for _model, redacted in displayed_models),
        "default_model": default_model,
        "default_model_redacted": default_model_redacted,
        "secret_mode": item.secret_mode,
        "configuration": {
            "endpoint_url": str(getattr(item, "base_url", "") or ""),
            "endpoint_env": config_meta.get("endpoint_env"),
            "credential_env": credential_env,
            "credential_state": (
                "not_required"
                if credential_env is None
                else "configured" if bool(item.configured) else "not_configured"
            ),
            "credential_source": (
                "encrypted_server_store"
                if stored_credential
                else "server_environment" if bool(item.configured) else "not_configured"
            ),
            "model_env": config_meta.get("model_env"),
            "models_env": config_meta.get("models_env"),
            "secrets_server_managed": item.secret_mode == "server-managed",
        },
    }


def _default_selection() -> tuple[str, str]:
    items = providers()
    ollama = items["ollama"]
    models = ollama.list_models()
    model = ollama.default_model
    if models and model not in models:
        model = models[0]
    return "ollama", model


def active_selection() -> tuple[Any, str]:
    init_platform_ai_db()
    items = providers()

    row = _installed_platform_repository().get_ai_selection()

    if row:
        provider_id = row.provider
        model = row.model
        item = items.get(provider_id)
        if item and item.configured and model:
            return item, model

    provider_id, model = _default_selection()
    return items[provider_id], model


def active_ai_label(capability_key: str | None = None) -> str:
    if runtime_mode() is AIRuntimeMode.CAPABILITY:
        if capability_key is None:
            raise AICapabilityUnsupported("Capability mode requires an explicit AI capability.")
        definition = require_capability(capability_key)
        row = _installed_platform_repository().get_capability_config(definition.key)
        if row is None:
            raise AICapabilityNotConfigured(
                f"AI capability {definition.key!r} has no explicit configuration."
            )
        return f"{row.config.provider}:{row.config.model}"
    item, model = active_selection()
    return f"{item.id}:{model}"


def active_ai_status() -> dict[str, Any]:
    item, model = active_selection()
    models = item.list_models()
    if item.id == "ollama":
        ready = bool(item.configured and model and model in models)
    else:
        ready = bool(item.configured and model and (not models or model in models))
    return {
        "ready": ready,
        "provider": item.id,
        "model": model,
        "provider_name": item.name,
        "kind": item.kind,
    }


def _persist_operation_telemetry(telemetry: dict[str, Any]) -> None:
    """Best-effort persistence through the installed platform repository."""

    safe = sanitize_telemetry(telemetry)
    recorder = getattr(_platform_repository, "record_ai_operation", None)
    if safe is None or not callable(recorder):
        return
    try:
        recorder(safe)
    except Exception:
        # Telemetry must never change learner/provider operation semantics.
        return


def _record_attempt(capability_key: str | None) -> Callable[[Attempt], None]:
    """Every rung is logged, not only the one that answered.

    Without this a fallback is invisible: the operator sees one success and
    never learns that the primary provider is down. The successful attempt is
    logged by `finish()` with its usage and cost, so only the ones that did not
    answer are recorded here.
    """

    def record(attempt: Attempt) -> None:
        if attempt.outcome == "success":
            return
        model_display, model_redacted = safe_model_display(attempt.model)
        # The telemetry vocabulary is success/failure; a provider skipped
        # because it is cooling down did not succeed, and the error class says
        # why it was never asked.
        error_class = (
            "ProviderCoolingDown" if attempt.outcome == "skipped_unhealthy" else attempt.error_class
        )
        _persist_operation_telemetry(
            {
                "capability": safe_capability_display(capability_key)
                if capability_key
                else "legacy",
                "origin": "learner",
                "provider": attempt.provider,
                "model": model_display or None,
                "model_redacted": model_redacted,
                "outcome": "failure",
                "error_class": error_class,
                "latency_ms": normalized_latency(attempt.latency_ms)
                if attempt.latency_ms is not None
                else None,
                "usage": normalized_usage(None),
                "rate_limit": normalized_rate_limit(None),
                "cost": estimate_token_cost(attempt.provider, model_display, None),
                "quota_available": "unknown",
            }
        )

    return record


def generate_structured(
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    max_output_tokens: int = 1200,
    temperature: float = 0.1,
    seed: int | None = None,
    capability_key: str | None = None,
) -> AIResult:
    started = perf_counter()
    provider_id: str | None = None
    model: str | None = None

    def finish(result: AIResult) -> AIResult:
        runtime = dict(result.runtime or {})
        provider_id = str(result.provider or "") or None
        model_display, model_redacted = safe_model_display(result.model)
        runtime["telemetry"] = {
            "capability": safe_capability_display(capability_key) if capability_key else "legacy",
            "origin": "learner",
            "provider": provider_id,
            "model": model_display or None,
            "model_redacted": model_redacted,
            "outcome": "success",
            "error_class": None,
            "latency_ms": normalized_latency((perf_counter() - started) * 1000),
            "usage": normalized_usage(runtime),
            "rate_limit": normalized_rate_limit(runtime.get("rate_limit")),
            "cost": estimate_token_cost(provider_id, model_display, normalized_usage(runtime)),
            "quota_available": "unknown",
        }
        _persist_operation_telemetry(runtime["telemetry"])
        result.runtime = runtime
        return result

    try:
        if runtime_mode() is AIRuntimeMode.LEGACY:
            item, model = active_selection()
            provider_id = str(getattr(item, "id", "") or "") or None
            if not item.configured:
                raise AIProviderUnavailable(f"{item.name} is not configured.")

            # Do not silently fail over to a paid provider.
            return finish(item.generate_json(
                messages=messages,
                schema=schema,
                model=model,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                seed=seed,
            ))

        if capability_key is None:
            raise AICapabilityUnsupported("Capability mode requires an explicit AI capability.")
        definition = require_capability(capability_key)
        if not definition.implemented or not definition.provider_backed or not definition.configurable:
            raise AICapabilityUnsupported(
                f"AI capability {definition.key!r} is not provider-configurable."
            )
        row = _installed_platform_repository().get_capability_config(definition.key)
        if row is None:
            raise AICapabilityNotConfigured(
                f"AI capability {definition.key!r} has no explicit configuration."
            )
        config = row.config
        provider_id = config.provider
        model = config.model
        if not config.enabled:
            raise AICapabilityDisabled(f"AI capability {definition.key!r} is disabled.")
        validate_capability_config(definition.key, config)

        # The operator configured a backup pair; until now nothing used it, so
        # one rate-limited provider stopped the capability. The chain asks each
        # rung once - never twice, so a learner turn cannot be answered twice -
        # and a malformed request still fails on the first rung, unchanged.
        chain = build_chain(
            provider=config.provider,
            model=config.model,
            backup_provider=config.backup_provider,
            backup_model=config.backup_model,
            timeout_seconds=config.timeout_seconds,
        )

        def _ask(target: ProviderTarget) -> AIResult:
            nonlocal provider_id, model
            provider_id, model = target.provider, target.model
            item = providers().get(target.provider)
            if item is None:
                raise AIProviderUnavailable(f"Unknown AI provider: {target.provider!r}.")
            if not item.configured:
                raise AIProviderUnavailable(f"{item.name} is not configured.")
            generate_once = getattr(item, "generate_json_once", None) or item.generate_json
            return generate_once(
                messages=messages,
                schema=schema,
                model=target.model,
                max_output_tokens=max_output_tokens,
                temperature=config.temperature if config.temperature is not None else temperature,
                seed=seed,
            )

        routed = run_chain(chain, _ask, on_attempt=_record_attempt(capability_key))
        provider_id, model = routed.target.provider, routed.target.model
        return finish(routed.value)
    except (AICapabilityError, AIProviderError) as exc:
        model_display, model_redacted = safe_model_display(model)
        exc.telemetry = {
            "capability": safe_capability_display(capability_key) if capability_key else "legacy",
            "origin": "learner",
            "provider": provider_id,
            "model": model_display or None,
            "model_redacted": model_redacted,
            "outcome": "failure",
            "error_class": telemetry_error_class(exc),
            "latency_ms": normalized_latency((perf_counter() - started) * 1000),
            "usage": normalized_usage(None),
            "rate_limit": normalized_rate_limit(getattr(exc, "rate_limit", None)),
            "cost": estimate_token_cost(provider_id, model_display, None),
            "quota_available": "unknown",
        }
        _persist_operation_telemetry(exc.telemetry)
        raise


def _require_admin(request: Request) -> dict[str, Any]:
    if _admin_guard is None:
        raise HTTPException(503, "Platform admin guard is not installed.")
    return _admin_guard(request)


def _record_admin_event(
    admin: dict[str, Any],
    action: str,
    *,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> None:
    """Record who changed or tested the AI platform, and how it went.

    Only non-secret facts are passed in: a credential change records that a
    key was set, never the key. The change has already happened (or been
    refused) when it is recorded, so a record that cannot be written is
    logged by action name alone rather than turning the answer into an error.
    """
    recorder = getattr(_platform_repository, "record_admin_event", None)
    if recorder is None:
        return
    try:
        recorder(
            action,
            actor=str(admin.get("google_sub") or admin.get("email") or "admin"),
            entity_type=entity_type,
            entity_id=str(entity_id)[:120],
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001 - reported, never allowed to undo or fail the change
        _logger.warning("AI admin audit record failed for %s (%s)", action, type(exc).__name__)


def _legacy_config_payload() -> dict[str, Any]:
    item, model = active_selection()
    displayed_model, model_redacted = safe_model_display(model)
    return {
        "active": {
            "provider": item.id,
            "provider_name": item.name,
            "model": displayed_model,
            "model_redacted": model_redacted,
            "kind": item.kind,
        },
        "providers": [_provider_snapshot(value) for value in providers().values()],
        "policy": {
            "scope": "global-platform",
            "automatic_paid_failover": False,
            "secrets": "server-managed",
        },
    }


@router.get("/config")
def admin_ai_config(request: Request) -> dict[str, Any]:
    _require_admin(request)
    result = AIControlPlane(_installed_platform_repository()).inspect()
    result["learner_runtime"] = {"mode": runtime_mode().value}
    return result


@router.get("/catalog")
def admin_ai_catalog(request: Request) -> dict[str, Any]:
    """Return the provider model catalog for the explicit Admin picker.

    Catalog discovery is read-only and intentionally separate from the
    network-free capability inspection endpoint. It never changes the active
    model, capability settings, learner routing, or production state.
    """

    _require_admin(request)
    return {
        "providers": [_provider_snapshot(value) for value in providers().values()],
        "read_only": True,
    }


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(403, "Credential changes require a same-origin browser request.")
    from urllib.parse import urlsplit

    expected_host = request.headers.get("host", "")
    if urlsplit(origin).netloc != expected_host:
        raise HTTPException(403, "Credential changes must originate from the Admin application.")


def _stored_provider_credentials(provider_id: str) -> dict[str, Any]:
    if _platform_repository is None:
        return {}
    envelope = _platform_repository.get_provider_credential(provider_id)
    if not envelope:
        return {}
    try:
        return decrypt_credentials(provider_id, envelope)
    except ProviderCredentialStoreError as exc:
        raise HTTPException(503, "Stored provider credential is unavailable.") from exc


def _provider_credential_values(
    provider_id: str,
    payload: ProviderCredentialIn,
    *,
    require_models: bool = True,
) -> dict[str, Any]:
    item = providers().get(provider_id)
    if item is None:
        raise HTTPException(404, "Unknown AI provider.")
    existing = _stored_provider_credentials(provider_id)
    supplied_key = payload.api_key.get_secret_value().strip() if payload.api_key is not None else ""
    api_key = supplied_key or str(existing.get("api_key") or "").strip()
    # Operators sometimes paste the value copied from an HTTP example as
    # ``Bearer <key>``. The provider adapters add the authentication scheme
    # themselves, so retain only the credential material before sending or
    # encrypting it. No credential value is logged or returned.
    if api_key.casefold().startswith("bearer "):
        api_key = api_key[7:].strip()
    if item.secret_mode == "server-managed" and not api_key:
        raise HTTPException(400, "A provider credential is required.")
    base_url = str(payload.base_url).strip().rstrip("/") if payload.base_url else str(
        existing.get("base_url") or getattr(item, "base_url", "") or ""
    ).strip().rstrip("/")
    from urllib.parse import urlsplit

    parsed = urlsplit(base_url)
    if parsed.username or parsed.password or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Provider endpoint must be a valid URL without embedded credentials.")
    models = sorted({str(model).strip() for model in payload.models if str(model).strip()})
    if any(len(model) > 160 or any(ord(char) < 32 for char in model) for model in models):
        raise HTTPException(400, "Model names must be readable values of 160 characters or fewer.")
    if len(models) > 100:
        raise HTTPException(400, "A provider can have at most 100 configured models.")
    default_model = payload.default_model.strip()
    if any(ord(char) < 32 for char in default_model):
        raise HTTPException(400, "The default model name is invalid.")
    if default_model and default_model not in models and require_models:
        models.append(default_model)
    if require_models and not models:
        raise HTTPException(400, "At least one model name is required.")
    return {
        "api_key": api_key,
        "base_url": base_url,
        "models": sorted(set(models)),
        "default_model": default_model,
    }


def _credential_test(provider_id: str, values: dict[str, Any]) -> list[str]:
    # Force a live catalog request. A manually supplied model allowlist is
    # useful after saving, but it must never make the connection test pass
    # without contacting the provider.
    test_values = dict(values)
    test_values["models"] = []
    item = build_providers({provider_id: test_values}).get(provider_id)
    if item is None:
        raise HTTPException(404, "Unknown AI provider.")
    try:
        return item.discover_models_live()
    except (AIProviderNotConfigured, AIProviderUnavailable, AIProviderError, AIProviderResponseInvalid) as exc:
        # Provider adapters deliberately expose only sanitized failure classes
        # and status codes. Returning that safe detail makes key restrictions,
        # invalid credentials, and network failures distinguishable without
        # leaking provider response bodies or credential material.
        detail = str(exc).strip() or "Provider request failed."
        raise HTTPException(502, f"Provider connection validation failed: {detail}") from exc


@router.get("/credentials")
def admin_ai_credentials(request: Request) -> dict[str, Any]:
    """Return credential status only; secret values never cross this boundary."""

    _require_admin(request)
    safe_providers = []
    for definition in provider_definitions():
        metadata = _PROVIDER_CONFIG_META.get(definition.id, {})
        stored = bool(
            _platform_repository is not None
            and _platform_repository.get_provider_credential(definition.id)
        )
        credential_env = metadata.get("credential_env")
        env_configured = bool(os.getenv(credential_env, "").strip()) if credential_env else False
        safe_providers.append(
            {
                "id": definition.id,
                "name": definition.name,
                "credential_source": (
                    "encrypted_server_store" if stored
                    else "server_environment" if env_configured
                    else "not_configured"
                ),
                "credential_state": (
                    "not_required" if credential_env is None
                    else "configured" if stored or env_configured else "not_configured"
                ),
            }
        )
    return {
        "providers": safe_providers,
        "secrets_exposed": False,
    }


@router.post("/credentials/{provider_id}/test")
def admin_ai_provider_credential_test(
    provider_id: str,
    payload: ProviderCredentialIn,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    admin = _require_admin(request)
    _same_origin(request)
    provider_id = provider_id.strip().casefold()
    try:
        values = _provider_credential_values(provider_id, payload, require_models=False)
        response.headers["Cache-Control"] = "no-store"
        models = _credential_test(provider_id, values)
    except HTTPException as exc:
        _record_admin_event(admin, "admin.ai.provider.test", entity_type="ai_provider", entity_id=provider_id,
                            payload={"outcome": "failed", "status": exc.status_code})
        raise
    _record_admin_event(admin, "admin.ai.provider.test", entity_type="ai_provider", entity_id=provider_id,
                        payload={"outcome": "ok", "models": len(models)})
    return {
        "ok": True,
        "provider": provider_id,
        "models": [safe_model_display(model)[0] for model in models],
        "secret_saved": False,
    }


@router.put("/credentials/{provider_id}")
def admin_ai_provider_credential_save(
    provider_id: str,
    payload: ProviderCredentialIn,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    admin = _require_admin(request)
    _same_origin(request)
    provider_id = provider_id.strip().casefold()
    try:
        values = _provider_credential_values(provider_id, payload)
        live_models = _credential_test(provider_id, values)
        live_model_set = set(live_models)
        if not live_model_set:
            raise HTTPException(502, "Provider returned no usable text models.")
        if values["default_model"] not in live_model_set or not set(values["models"]).issubset(live_model_set):
            raise HTTPException(400, "Choose the default and allowed models from the live provider catalog.")
        try:
            encrypted = encrypt_credentials(provider_id, values)
            _installed_platform_repository().set_provider_credential(
                provider_id,
                encrypted,
                updated_by=str(admin.get("google_sub") or ""),
            )
        except ProviderCredentialStoreError as exc:
            raise HTTPException(503, "Provider credential encryption is not configured on this server.") from exc
    except HTTPException as exc:
        _record_admin_event(admin, "admin.ai.credential.update", entity_type="ai_provider", entity_id=provider_id,
                            payload={"credential_updated": False, "outcome": "failed", "status": exc.status_code})
        raise
    _record_admin_event(admin, "admin.ai.credential.update", entity_type="ai_provider", entity_id=provider_id,
                        payload={
                            "credential_updated": True,
                            "outcome": "ok",
                            "endpoint_set": bool(values["base_url"]),
                            "models": len(values["models"]),
                            "default_model": safe_model_display(values["default_model"])[0],
                        })
    response.headers["Cache-Control"] = "no-store"
    stored = providers().get(provider_id)
    if stored is None:
        raise HTTPException(404, "Unknown AI provider.")
    return {
        "ok": True,
        "provider": _provider_snapshot(stored),
        "secret_saved": True,
        "secret_exposed": False,
    }


@router.delete("/credentials/{provider_id}")
def admin_ai_provider_credential_delete(
    provider_id: str,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    admin = _require_admin(request)
    _same_origin(request)
    provider_id = provider_id.strip().casefold()
    if provider_id not in providers():
        _record_admin_event(admin, "admin.ai.credential.delete", entity_type="ai_provider", entity_id=provider_id,
                            payload={"credential_deleted": False, "outcome": "refused", "status": 404})
        raise HTTPException(404, "Unknown AI provider.")
    _installed_platform_repository().delete_provider_credential(provider_id)
    _record_admin_event(admin, "admin.ai.credential.delete", entity_type="ai_provider", entity_id=provider_id,
                        payload={"credential_deleted": True, "outcome": "ok"})
    response.headers["Cache-Control"] = "no-store"
    return {"ok": True, "provider": provider_id, "secret_deleted": True, "secret_exposed": False}


@router.get("/operations")
def admin_ai_operations(request: Request, limit: int = 100) -> dict[str, Any]:
    _require_admin(request)
    return AIControlPlane(_installed_platform_repository()).operations(limit=limit)


@router.put("/config", deprecated=True)
def admin_ai_config_update(payload: AIConfigIn, request: Request) -> dict[str, Any]:
    admin = _require_admin(request)
    items = providers()
    provider_id = payload.provider.strip().casefold()
    model = payload.model.strip()
    item = items.get(provider_id)
    target = {"provider": provider_id[:40], "model": safe_model_display(model)[0]}

    try:
        if not item:
            raise HTTPException(400, "Unknown AI provider.")
        if not item.configured:
            raise HTTPException(409, f"{item.name} is not configured on the server.")

        models = item.list_models()
        if models and model not in models:
            raise HTTPException(400, "Selected model is not available for this provider.")

        _installed_platform_repository().set_ai_selection(
            provider=provider_id,
            model=model,
            updated_by=str(admin.get("google_sub") or ""),
        )
    except HTTPException as exc:
        _record_admin_event(admin, "admin.ai.selection.update", entity_type="ai_selection", entity_id="learner_default",
                            payload={**target, "outcome": "refused", "status": exc.status_code})
        raise
    _record_admin_event(admin, "admin.ai.selection.update", entity_type="ai_selection", entity_id="learner_default",
                        payload={**target, "outcome": "ok"})

    return _legacy_config_payload()


@router.post("/test", deprecated=True)
def admin_ai_test(payload: AIConfigIn, request: Request) -> dict[str, Any]:
    admin = _require_admin(request)
    items = providers()
    provider_id = payload.provider.strip().casefold()
    model = payload.model.strip()
    item = items.get(provider_id)
    target = {"provider": provider_id[:40], "model": safe_model_display(model)[0]}

    if not item:
        _record_admin_event(admin, "admin.ai.selection.test", entity_type="ai_selection", entity_id="learner_default",
                            payload={**target, "outcome": "refused", "status": 400})
        raise HTTPException(400, "Unknown AI provider.")
    if not item.configured:
        _record_admin_event(admin, "admin.ai.selection.test", entity_type="ai_selection", entity_id="learner_default",
                            payload={**target, "outcome": "refused", "status": 409})
        raise HTTPException(409, f"{item.name} is not configured.")

    schema = {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "message": {"type": "string"},
        },
        "required": ["ok", "message"],
    }

    try:
        result = item.generate_json(
            messages=[
                {"role": "system", "content": "Return a tiny JSON health response for a writing application."},
                {"role": "user", "content": "Return ok=true and a short message."},
            ],
            schema=schema,
            model=model,
            max_output_tokens=80,
            temperature=0.0,
        )
    except AIProviderUnavailable as exc:
        _record_admin_event(admin, "admin.ai.selection.test", entity_type="ai_selection", entity_id="learner_default",
                            payload={**target, "outcome": "failed", "status": 503})
        raise HTTPException(503, "AI provider is unavailable.") from exc
    except AIProviderError as exc:
        _record_admin_event(admin, "admin.ai.selection.test", entity_type="ai_selection", entity_id="learner_default",
                            payload={**target, "outcome": "failed", "status": 502})
        raise HTTPException(502, "AI provider request failed.") from exc
    _record_admin_event(admin, "admin.ai.selection.test", entity_type="ai_selection", entity_id="learner_default",
                        payload={**target, "outcome": "ok"})

    displayed_model, model_redacted = safe_model_display(result.model)

    return {
        "ok": bool(result.data.get("ok", True)),
        "provider": result.provider,
        "model": displayed_model,
        "model_redacted": model_redacted,
        "message": "Connection succeeded.",
    }


def _capability_config(payload: CapabilityConfigIn) -> CapabilityConfig:
    return CapabilityConfig(
        enabled=payload.enabled,
        provider=payload.provider,
        model=payload.model,
        backup_provider=payload.backup_provider,
        backup_model=payload.backup_model,
        timeout_seconds=payload.timeout_seconds,
        temperature=payload.temperature,
        fallback_policy=payload.fallback_policy,
    )


@router.put("/config/{capability_key}")
def admin_ai_capability_config_update(
    capability_key: str,
    payload: CapabilityConfigIn,
    request: Request,
) -> dict[str, Any]:
    admin = _require_admin(request)
    try:
        result = AIControlPlane(_installed_platform_repository()).set_config(
            capability_key,
            _capability_config(payload),
            updated_by=str(admin.get("google_sub") or ""),
        )
    except (AICapabilityConfigInvalid, AICapabilityUnsupported) as exc:
        _record_admin_event(admin, "admin.ai.route.update", entity_type="ai_capability",
                            entity_id=safe_capability_display(capability_key), payload={"outcome": "refused"})
        raise HTTPException(400, str(exc)) from exc
    _record_admin_event(admin, "admin.ai.route.update", entity_type="ai_capability", entity_id=result["capability"],
                        payload={**result["config"], "outcome": "ok"})
    return result


def _live_failure(
    control_plane: AIControlPlane,
    capability_key: str,
    exc: Exception,
    *,
    standby: bool = False,
) -> HTTPException:
    if isinstance(exc, AICapabilityDisabled):
        status, error_class, message = 409, "capability_disabled", "Capability is disabled."
    elif isinstance(exc, AICapabilityNotConfigured):
        status, error_class, message = 404, "capability_not_configured", "Capability has no explicit configuration."
    elif isinstance(exc, AIProviderNotConfigured):
        status, error_class, message = 409, "provider_not_configured", "Provider credentials or server configuration are missing."
    elif isinstance(exc, AIModelCatalogEmpty):
        status, error_class, message = 409, "model_catalog_empty", "Provider model catalog is empty."
    elif isinstance(exc, AIModelUnavailable):
        status, error_class, message = 409, "model_unavailable", "Configured model is not available."
    elif isinstance(exc, AIProviderResponseInvalid):
        status, error_class, message = 502, "provider_response_invalid", "Provider response failed capability validation."
    elif isinstance(exc, AIProviderUnavailable):
        status, error_class, message = 503, "provider_unavailable", "Provider is unavailable."
    elif isinstance(exc, AIProviderError):
        status, error_class, message = 502, "provider_error", "Provider request failed."
    elif isinstance(exc, (AICapabilityConfigInvalid, AICapabilityUnsupported)):
        status, error_class, message = 400, "capability_invalid", "Capability is not available for live testing."
    else:  # Programming errors must remain visible rather than masquerading as provider failures.
        raise exc

    try:
        context = control_plane.diagnostic_context(capability_key, standby=standby)
    except (AICapabilityConfigInvalid, AICapabilityUnsupported):
        context = {
            "capability": "[invalid]",
            "provider": None,
            "model": None,
            "model_redacted": False,
        }
    raw_telemetry = getattr(exc, "telemetry", None)
    telemetry = raw_telemetry if isinstance(raw_telemetry, dict) else {}
    # The control plane attaches this shape before the route translates the
    # typed exception; copy only normalized fields into the HTTP detail.
    safe_telemetry = {
        "capability": safe_capability_display(telemetry.get("capability") or capability_key),
        "origin": "operator_test",
        "provider": str(telemetry.get("provider") or "") or None,
        "model": safe_model_display(telemetry.get("model"))[0] or None,
        "model_redacted": bool(telemetry.get("model_redacted")),
        "outcome": "failure",
        "error_class": error_class,
        "latency_ms": normalized_latency(telemetry.get("latency_ms")),
        "usage": normalized_usage(telemetry.get("usage")),
        "rate_limit": normalized_rate_limit(telemetry.get("rate_limit")),
        "quota_available": "unknown",
    }
    return HTTPException(
        status,
        {
            "ok": False,
            **context,
            "latency_ms": safe_telemetry["latency_ms"],
            "error_class": error_class,
            "error": message,
            "telemetry": safe_telemetry,
        },
    )


@router.post("/test/{capability_key}")
def admin_ai_capability_test(
    capability_key: str,
    request: Request,
    standby: bool = False,
) -> dict[str, Any]:
    admin = _require_admin(request)
    control_plane = AIControlPlane(_installed_platform_repository())
    entity_id = safe_capability_display(capability_key)
    try:
        result = control_plane.live_test(capability_key, standby=standby)
    except (
        AICapabilityConfigInvalid,
        AICapabilityDisabled,
        AICapabilityNotConfigured,
        AICapabilityUnsupported,
        AIProviderError,
    ) as exc:
        failure = _live_failure(control_plane, capability_key, exc, standby=standby)
        _record_admin_event(admin, "admin.ai.route.test", entity_type="ai_capability", entity_id=entity_id,
                            payload={"standby": standby, "outcome": "failed", "error_class": failure.detail["error_class"]})
        raise failure from exc
    _record_admin_event(admin, "admin.ai.route.test", entity_type="ai_capability", entity_id=entity_id,
                        payload={"standby": standby, "outcome": "ok"})
    return result


def install_platform_ai(
    app: FastAPI,
    admin_guard: Callable[[Request], dict[str, Any]],
) -> None:
    global _admin_guard
    _admin_guard = admin_guard
    init_platform_ai_db()
    app.include_router(router)
