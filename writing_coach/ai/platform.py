from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from time import perf_counter
from enum import Enum
from pathlib import Path
from collections.abc import Iterator, Sequence
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
    AIOutputInvalid,
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
    AIResult,
    ChatFinished,
    ChatStreamEvent,
    normalized_latency,
    normalized_rate_limit,
    http_status_class,
    normalized_usage,
    sanitize_telemetry,
    telemetry_error_class,
)
from writing_coach.ai import routing as _routing
from writing_coach.ai import learner_cost as _learner_cost
from writing_coach.ai import spend_gate
from writing_coach.ai.capabilities import AIOperation, require_capability
from writing_coach.ai.config import (
    ROUTING_SWITCH,  # noqa: F401 - re-exported for the routing switch's readers
    CapabilityConfig,
    learner_text_refused,
    routed_capabilities,
    routed_definition,
    validate_capability_config,
    validate_routed_policy,
)
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
from writing_coach.ai.health_signal import failure_class_of
from writing_coach.ai.pricing import estimate_token_cost
from writing_coach.ai.routing import (
    AllProvidersUnavailable,
    Attempt,
    ProviderTarget,
    build_chain,
    fallback_reason,
    provider_tier,
    run_chain,
)
from writing_coach.ai.providers import (
    OpenAICompatibleProvider,
    build_providers,
    check_model_allowed,
    get_provider_definition,
    normalize_openai_base_url,
    provider_definitions,
)
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


# PR-MON-7: providers whose bill may currently be covered by provider credits. Their calls keep their real estimated
# cost; whether credits covered a call is only an estimate, `unknown` until an allowance is defined (H7-7).
COVERED_CREDIT_PROVIDERS = frozenset({"ollama-cloud"})


def _legacy_privacy_guard(capability_key: str | None, item: Any, model: str) -> None:
    """The D-195/D-104 privacy rule on the legacy single selection (PR-MON-7 F-1): learner text never reaches a free
    tier, a provider that may log prompts, or a model without its required privacy review. An unknown or missing key is
    treated as learner text. Refused before anything is sent."""

    from writing_coach.ai.capabilities import get_capability
    from writing_coach.ai.pricing import is_free_model
    from writing_coach.ai.providers import get_provider_definition

    definition = get_capability(capability_key) if capability_key else None
    if definition is not None and definition.input_class != "learner_text":
        return
    provider_id = str(getattr(item, "id", "") or "")
    provider = get_provider_definition(provider_id)
    refused = provider is not None and (
        provider.may_log_prompts
        or is_free_model(provider_id, model)
        or (provider.learner_text_models is not None and model not in provider.learner_text_models)
    )
    if refused:
        raise AIProviderUnavailable(
            "The selected AI provider cannot receive learner text (a free tier, a provider that may log prompts, or "
            "a model without a privacy review)."
        )


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


def _control_plane() -> AIControlPlane:
    """The control plane every admin route uses: providers come from the
    credential-aware `providers()` (environment plus the D-037 encrypted
    store), exactly as the runtime builds them."""
    return AIControlPlane(_installed_platform_repository(), provider_factory=providers)


_PROVIDER_CONFIG_META: dict[str, dict[str, str | None]] = {
    'azure-openai': {'endpoint_env': 'AZURE_OPENAI_BASE_URL', 'credential_env': 'AZURE_OPENAI_API_KEY', 'model_env': None, 'models_env': 'AZURE_OPENAI_DEPLOYMENTS'},
    'azure-speech': {'endpoint_env': 'AZURE_SPEECH_REGION', 'credential_env': 'AZURE_SPEECH_KEY', 'model_env': None, 'models_env': None},
    "ollama": {
        "endpoint_env": "OLLAMA_URL",
        "credential_env": None,
        "model_env": "OLLAMA_MODEL",
        "models_env": None,
    },
    "ollama-cloud": {
        "endpoint_env": "OLLAMA_CLOUD_BASE_URL",
        "credential_env": "OLLAMA_CLOUD_API_KEY",
        "model_env": None,
        "models_env": "OLLAMA_CLOUD_MODELS",
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
    "openrouter": {
        "endpoint_env": "OPENROUTER_BASE_URL",
        "credential_env": "OPENROUTER_API_KEY",
        "model_env": None,
        "models_env": "OPENROUTER_MODELS",
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


def _offline_models(item: Any) -> list[str]:
    """Models for a health answer: never a network call (a provider's catalogue is not asked on every /api/health)."""

    try:
        return item.list_models(offline=True)
    except TypeError:  # a provider without the keyword (a local model lists itself cheaply)
        return item.list_models()


def active_ai_status() -> dict[str, Any]:
    item, model = active_selection()
    models = item.list_models() if item.id == "ollama" else _offline_models(item)
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

    if isinstance(telemetry, dict) and telemetry.get("provider") in COVERED_CREDIT_PROVIDERS:
        # PR-MON-7 §4.4: the economic cost stays the catalogue estimate; coverage is an estimate, `unknown` until H7-7.
        telemetry = {**telemetry, "cost_coverage": "unknown"}
    if isinstance(telemetry, dict) and telemetry.get("provider"):
        # D-219: stamp the tier in force now. For a provider that has a flag, the flag decides: a model billed at 0 on a
        # free plan (qwen) becomes real spend when the owner turns the flag off. Only a provider without a flag falls
        # back to the model being free by id (an OpenRouter ":free" id; its amount is 0 either way).
        from writing_coach import cost_tier
        from writing_coach.ai.pricing import is_free_model

        provider = telemetry.get("provider")
        free = (cost_tier.is_free_tier(provider) if cost_tier.flag_key(provider)
                else is_free_model(provider, telemetry.get("model")))
        telemetry = {**telemetry, "free_tier": free}
    if isinstance(telemetry, dict):
        # D-221: the environment that wrote this event; the provider key is shared by every environment.
        from writing_coach import cost_env

        telemetry = {**telemetry, "environment": cost_env.label()}
    safe = sanitize_telemetry(telemetry)
    recorder = getattr(_platform_repository, "record_ai_operation", None)
    if safe is None or not callable(recorder):
        return
    try:
        from writing_coach.ai.account_costs import record_for_current_account

        record_for_current_account(safe)  # AC-2: the same call, once more, for the signed-in account
    except Exception:  # noqa: BLE001 - never changes the operation
        pass
    try:
        recorder(safe)
    except Exception:
        # Telemetry must never change learner/provider operation semantics.
        return


def _router_fields(router_version: str | None, provider: str | None, model: str | None, *, attempt: int | None,
                   reason: str | None = None, status_class: str | None = None) -> dict[str, Any]:
    """The AI Cost Router's telemetry fields (D-195); empty for every non-routed call."""

    if router_version is None:
        return {}
    return {
        "tier": provider_tier(provider or "", model or ""),
        "phase": "pool",
        "attempt": attempt,
        "fallback_reason": reason,
        "http_status_class": status_class,
        "router_version": router_version,
    }


def _budget_gate(definition: Any, *, paid_ok: bool = True) -> Callable[[ProviderTarget], str | None] | None:
    """The chain's admission check for the paid rungs of a capability with a daily spend cap (None: nothing to gate).

    A paid rung is skipped (`"budget"`) when the caller is background work, the cap is zero or unreadable, today's spend
    has reached it, or the ledger cannot be read: it fails closed. Free and local rungs are never gated."""

    if not definition.paid_standby_cap_policy:
        return None

    def admit(target: ProviderTarget) -> str | None:
        if provider_tier(target.provider, target.model) != "paid":
            return None
        if not paid_ok:
            return "budget"
        return "budget" if spend_gate.paid_refused(definition.key, definition.paid_standby_cap_policy) else None

    return admit


def _funded_gate(capability_key: str, budget: Callable[[ProviderTarget], str | None] | None,
                 timeout_for: Callable[[ProviderTarget], float | None]) -> Callable[[ProviderTarget], str | None]:
    """The budget gate, then I-1's backstop for a paid rung (PR-MON-6 §2): a paid rung without live funding is skipped
    (`unfunded`) when FUNDING_ENFORCEMENT is `enforce`, logged in `log`, untouched when `off`. Free and local rungs
    need no paid funding."""

    from writing_coach.billing import funding_context

    def admit(target: ProviderTarget) -> str | None:
        # The system's daily spend is a monitor since D-251 (ai/spend_gate.py): ticked for every paid rung, never a refusal.
        if provider_tier(target.provider, target.model) == "paid":
            spend_gate.observe()
        refused = budget(target) if budget is not None else None
        if refused is not None:
            return refused
        if provider_tier(target.provider, target.model) != "paid":
            return None
        allowed = funding_context.paid_allowed(capability=capability_key, provider=target.provider,
                                               timeout_seconds=timeout_for(target) or 0.0)
        return None if allowed else "unfunded"

    return admit


def _provider_timeout(provider_id: str) -> float | None:
    """The provider client's own request timeout (its default when a call names none)."""
    item = providers().get(provider_id)
    value = getattr(item, "timeout", None)
    return float(value) if isinstance(value, (int, float)) and value > 0 else None


def _effective_timeout(requested: float | None, default: float | None) -> float | None:
    """The upper bound the outbound request will really use: the per-call timeout when one is given (capped by the
    client's own), else the client's default. None when neither is known - the backstop then refuses."""
    values = [float(v) for v in (requested, default) if isinstance(v, (int, float)) and v > 0]
    if not values:
        return None
    return min(values) if requested else values[0]


def _require_paid_funding(capability: str, provider: str | None, model: str | None, timeout: float | None) -> None:
    """The backstop for a single paid request with no other rung (legacy selection, agent rounds)."""
    from writing_coach.billing import funding_context

    if provider and provider_tier(provider, model or "") == "paid":
        spend_gate.observe()  # the system's daily spend monitor (ai/spend_gate.py, D-251): it alerts, it never refuses
        funding_context.require_paid(capability=capability, provider=provider, timeout_seconds=timeout or 0.0)


def _record_attempt(capability_key: str | None, router_version: str | None = None,
                    sent: Callable[[], bool] | None = None) -> Callable[[Attempt], None]:
    """Every rung is logged, not only the one that answered.

    Without this a fallback is invisible: the operator sees one success and
    never learns that the primary provider is down. The successful attempt is
    logged by `finish()` with its usage and cost, so only the ones that did not
    answer are recorded here.
    """

    counter = {"n": 0}

    def record(attempt: Attempt) -> None:
        counter["n"] += 1
        # PR-MON-6 §8: did this rung's request leave Orena? A skipped rung never did; a failed one did only if the
        # attempt reached the provider call (`sent`), not when it failed before (an unconfigured provider).
        was_sent = attempt.outcome == "failure" and (sent() if sent is not None else False)
        if attempt.outcome == "success":
            return
        model_display, model_redacted = safe_model_display(attempt.model)
        # The telemetry vocabulary is success/failure; a provider skipped
        # because it is cooling down did not succeed, and the error class says
        # why it was never asked.
        error_class = (
            "ProviderCoolingDown" if attempt.outcome == "skipped_unhealthy"
            else "privacy_refused" if attempt.outcome == "skipped_budget" and attempt.reason == "privacy"
            else "budget_skipped" if attempt.outcome == "skipped_budget"
            else attempt.error_class
        )
        # PR BZ: a skipped rung is not a provider failure; a failed one carries its health class.
        failure_class = "not_counted" if attempt.outcome != "failure" else (attempt.failure_class or "other")
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
                "billable_attempt": was_sent,
                "failure_class": failure_class,
                **_router_fields(router_version, attempt.provider, model_display, attempt=counter["n"],
                                 reason=attempt.reason, status_class=attempt.status_class),
            }
        )

    return record


# A chain with a deadline does not retry an invalid answer with less than this left.
MIN_RETRY_SECONDS = 0.5
# What a rung with a backup after it leaves of the deadline for that backup: a primary that times out must not take
# the whole time, or the configured backup is never asked (P0 QA: Groq timing out, word lookups got no answer).
BACKUP_RESERVE_SECONDS = 1.5


def _backup_can_answer(target: ProviderTarget, health: Any = None) -> bool:
    """Whether a later rung could be asked at all: its provider is configured and its breaker is not holding it down.
    Time is reserved only for such a rung; an unconfigured or stood-down backup leaves the primary the whole deadline."""

    item = providers().get(target.provider)
    if item is None or not getattr(item, "configured", False):
        return False
    tracker = health or _routing.provider_health
    try:
        return bool(tracker.is_available(target.provider, target.model))
    except Exception:  # noqa: BLE001 - a tracker that cannot answer reserves nothing
        return False


# PR CA: an answer that is not a complete JSON object (empty, cut off) is asked again once on the same rung. DeepSeek's
# JSON mode (`response_format: json_object`, sent by every OpenAI-compatible adapter) may still return empty content
# now and then, and a rerun answers; the retry is another paid call, admitted again by the spend gate and charged.
MALFORMED_JSON_RETRIES = 1


def _record_invalid_output(capability_key: str | None, target: ProviderTarget, result: AIResult | None,
                           router_version: str | None, *, attempt: int, runtime: dict[str, Any] | None = None,
                           error_class: str = "output_invalid") -> None:
    """An answer that parsed but failed the contract - or (PR CA) that was not a complete JSON object and is asked
    again - is a failed generation that may still have cost tokens: recorded with its usage, so the ledger prices it."""

    model_display, model_redacted = safe_model_display(target.model)
    usage = normalized_usage(result.runtime if result is not None else runtime)
    _persist_operation_telemetry(
        {
            "capability": safe_capability_display(capability_key) if capability_key else "legacy",
            "origin": "learner",
            "provider": target.provider,
            "model": model_display or None,
            "model_redacted": model_redacted,
            "outcome": "failure",
            "error_class": error_class,
            "latency_ms": None,
            "usage": usage,
            "rate_limit": normalized_rate_limit(None),
            "cost": estimate_token_cost(target.provider, model_display, usage),
            "quota_available": "unknown",
            "billable_attempt": True,   # the provider answered: the call was made and may have cost tokens
            "failure_class": "not_counted",  # the validator refused one answer: not a provider failure (PR BZ)
            **_router_fields(router_version, target.provider, model_display, attempt=attempt, reason="invalid_output"),
        }
    )


def _privacy_gate(definition: Any, gate: Callable[[ProviderTarget], str | None] | None
                  ) -> Callable[[ProviderTarget], str | None]:
    """D-104 at switch time (PR BZ): before any rung is asked - the primary, or a backup reached because the primary is
    down - a capability carrying learner text refuses a free tier or a prompt-logging provider (`"privacy"`), then the
    spend and funding gate decides as before. With every rung refused the chain ends in the caller's gentle error or
    its deterministic answer; nothing is sent."""

    def admit(target: ProviderTarget) -> str | None:
        if learner_text_refused(definition, target.provider, target.model):
            return "privacy"
        return gate(target) if gate is not None else None

    return admit


# The trigger of a switch, from what the first rung did.
_SWITCH_TRIGGERS = {"skipped_unhealthy": "down", "failure": "failed"}


def provider_switch(attempts: Sequence[Attempt] | None, answered_by: str | None) -> dict[str, Any] | None:
    """The `provider_switch` telemetry field (PR BZ): the configured first rung did not answer and the chain moved on.
    `from` is that rung, `to` the provider that answered (None: nobody did), `reason` a closed failure class (the
    breaker's for a provider that is down; `privacy` / `budget` / `unfunded` for a rung a gate refused) and `trigger`
    down / failed / refused. Provider ids and closed words only, never a prompt."""

    rungs = list(attempts or ())
    if len(rungs) < 2 or rungs[0].outcome == "success":
        return None
    first = rungs[0]
    trigger = _SWITCH_TRIGGERS.get(first.outcome, "refused")
    if trigger == "refused":
        reason = first.reason if first.reason in {"privacy", "budget", "unfunded"} else "budget"
    else:
        reason = first.failure_class or "other"
    return {"from": first.provider, "to": answered_by or None, "reason": reason, "trigger": trigger}


AGENT_TURN_CAPABILITY = "agent_turn_fast"


def _route_item(route: tuple[str, str]) -> Any:
    item = providers().get(route[0])
    if item is None:
        raise AIProviderUnavailable("The agent's pinned provider is not known on this server.")
    return item


def agent_route_usable(route: tuple[str, str]) -> bool:
    """Whether a pinned agent route can still stream here: a managed provider, configured, that streams agent turns.
    False when Admin removed or unconfigured it; the conversation is then pinned again to the current selection."""

    item = providers().get(route[0])
    if item is None or getattr(item, "kind", "") != "cloud" or not item.configured or not route[1]:
        return False
    try:
        check_model_allowed(item.id, route[1])  # e.g. an OpenRouter free model since dropped from the catalogue
    except (AICapabilityError, AIProviderError):
        return False
    definition = get_provider_definition(item.id)
    return bool(definition is not None and definition.supports(AIOperation.AGENT_TURN)
                and callable(getattr(item, "stream_chat", None)))


def agent_current_route() -> tuple[str, str] | None:
    """The route a new agent conversation is pinned to: the active selection, when it can stream agent turns."""

    try:
        item, model = active_selection()
    except Exception:  # noqa: BLE001 - no route: the round reads the selection itself and fails as before
        return None
    route = (str(getattr(item, "id", "") or ""), str(model or ""))
    return route if route[0] and agent_route_usable(route) else None


AGENT_FALLBACK_SETTING = "agent.fallback_route"  # platform setting {"provider", "model"} (D-247)
AGENT_FALLBACK_ENV = "AGENT_FALLBACK_ROUTE"  # "provider:model", while no Admin record exists


def agent_fallback_route() -> tuple[str, str] | None:
    """The agent's second rung (D-247): the Admin record `agent.fallback_route`, else `AGENT_FALLBACK_ROUTE`; None when
    neither names one, or the one named cannot take agent turns here (not configured, cannot stream them) or may not
    receive learner text (D-104: a free tier, a provider that may log prompts). Read at each turn, so a change in Admin
    applies at the next one."""

    raw: Any = None
    if _platform_repository is not None:
        try:
            row = _platform_repository.get_setting(AGENT_FALLBACK_SETTING)
        except Exception:  # noqa: BLE001 - an unreadable record names no fallback (the first rung is unaffected)
            row = None
        if row:
            value = row.get("value") or {}
            raw = (str(value.get("provider") or ""), str(value.get("model") or ""))
    if raw is None:
        provider, _, model = str(os.environ.get(AGENT_FALLBACK_ENV, "") or "").strip().partition(":")
        raw = (provider.strip(), model.strip())
    if not raw[0] or not raw[1] or not agent_route_usable(raw):
        return None
    try:
        _legacy_privacy_guard(None, _route_item(raw), raw[1])
    except AIProviderUnavailable:
        _logger.warning("agent fallback %s refused: it may not receive learner text (D-104)", raw[0])
        return None
    return raw


def stream_agent_turn(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_output_tokens: int,
    temperature: float | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    timeout_seconds: float | None = None,
    route: tuple[str, str] | None = None,
    tool_choice: str | None = None,
    fallback: tuple[str, str] | None = None,
) -> Iterator[ChatStreamEvent]:
    """Stream one Orena Intelligence round on `route` (the conversation's pinned model) or the legacy active selection,
    and on `fallback` when that first rung cannot answer (D-247, owner 2026-10-20: automatic fallback, never silent).

    The fallback is taken only BEFORE the first rung yields anything - a provider error at the start, or the shared
    breaker already holding that provider (or model) down - so the learner never sees half an answer from one model and
    the rest from another. Once the first rung has produced its first event, its errors are the round's, as before.
    `fallback` is chosen by the caller (the agent, which applies the G8 data classes) and has passed the D-104 learner-
    text rule (`agent_fallback_route`). Each attempt is recorded in the AI operation telemetry under `agent_turn_fast`,
    the one that answered after a switch with `provider_switch`; each counts toward the spend gates as any round."""

    kwargs = dict(messages=messages, tools=tools, max_output_tokens=max_output_tokens, temperature=temperature,
                  should_stop=should_stop, timeout_seconds=timeout_seconds, tool_choice=tool_choice)
    first = route
    if fallback is None or tuple(fallback) == tuple(first or ()):
        return _agent_round(route=first, **kwargs)
    first_id = (first[0], first[1]) if first is not None else _selection_route()
    if first_id is not None and not _routing.provider_health.is_available(*first_id):
        reason = _routing.provider_health.down_reason(*first_id) or "other"
        return _agent_round(route=fallback, switch={"from": first_id[0], "to": fallback[0], "reason": reason,
                                                    "trigger": "down"}, **kwargs)  # fmt: skip
    return _with_fallback(first, first_id, fallback, kwargs)


def _selection_route() -> tuple[str, str] | None:
    try:
        item, model = active_selection()
    except Exception:  # noqa: BLE001 - no selection: the first rung fails as before
        return None
    provider = str(getattr(item, "id", "") or "")
    return (provider, str(model or "")) if provider else None


def _with_fallback(first: tuple[str, str] | None, first_id: tuple[str, str] | None, fallback: tuple[str, str],
                   kwargs: dict[str, Any]) -> Iterator[ChatStreamEvent]:  # fmt: skip
    """The first rung, falling back to `fallback` only if it fails before yielding anything."""

    try:
        events = _agent_round(route=first, **kwargs)
        head = next(events)
    except StopIteration:
        return iter(())
    except (AICapabilityError, AIProviderError) as exc:
        if isinstance(exc, AICapabilityError) and not isinstance(exc, AIProviderUnavailable):
            raise  # a configuration refusal is not fixed by asking someone else
        if isinstance(exc, spend_gate.SpendCeilingReached):
            raise  # the system's own daily ceiling: every paid rung is refused alike
        _logger.warning("agent first rung failed before answering (%s); falling back to %s", type(exc).__name__,
                     fallback[0])  # fmt: skip
        switch = {"from": first_id[0] if first_id else None, "to": fallback[0],
                  "reason": failure_class_of(exc) or "other", "trigger": "failed"}  # fmt: skip
        return _agent_round(route=fallback, switch=switch, **kwargs)

    def chained() -> Iterator[ChatStreamEvent]:
        try:
            yield head
            yield from events
        finally:
            events.close()

    return chained()


def _agent_round(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_output_tokens: int,
    temperature: float | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    timeout_seconds: float | None = None,
    route: tuple[str, str] | None = None,
    tool_choice: str | None = None,
    switch: dict[str, Any] | None = None,
) -> Iterator[ChatStreamEvent]:
    """One provider attempt of an agent round (the body `stream_agent_turn` had before D-247)."""

    started = perf_counter()
    provider_id: str | None = None
    model: str | None = None
    sent = {"request": False}   # PR-MON-6 §8: the round's request left Orena

    def record(
        outcome: str,
        *,
        error: BaseException | None = None,
        finished: ChatFinished | None = None,
        error_class: str | None = None,
    ) -> None:
        model_display, model_redacted = safe_model_display(model)
        runtime = {
            "prompt_tokens": finished.prompt_tokens if finished else None,
            "completion_tokens": finished.completion_tokens if finished else None,
        }
        usage = normalized_usage(runtime) if finished else normalized_usage(None)
        rate_limit = finished.rate_limit if finished else getattr(error, "rate_limit", None)
        _persist_operation_telemetry(
            {
                "capability": AGENT_TURN_CAPABILITY,
                "origin": "learner",
                "provider": provider_id,
                "model": model_display or None,
                "model_redacted": model_redacted,
                "outcome": outcome,
                "error_class": error_class or (telemetry_error_class(error) if error is not None else None),
                "failure_class": failure_class_of(error, error_class=error_class) if outcome == "failure" else None,
                "latency_ms": normalized_latency((perf_counter() - started) * 1000),
                "usage": usage,
                "rate_limit": normalized_rate_limit(rate_limit),
                "cost": estimate_token_cost(provider_id, model_display, usage if finished else None),
                "quota_available": "unknown",
                "billable_attempt": sent["request"],
                **({"provider_switch": switch} if switch else {}),
            }
        )
        # The shared breaker (PR BZ): a provider that failed is skipped by the next rounds while it cools down.
        if provider_id:
            if outcome == "success":
                _routing.provider_health.record_success(provider_id, model)
            elif (error is not None and _routing.classify(error) == "availability"
                  and not isinstance(error, spend_gate.SpendCeilingReached)):  # our ceiling, not the provider's fault
                _routing.provider_health.record_failure(provider_id, failure_class_of(error), model)

    try:
        if route is not None:
            item, model = _route_item(route), route[1]
        else:
            item, model = active_selection()
        # D-104: the agent carries learner text, so it never runs on a free tier or a provider that may log prompts.
        _legacy_privacy_guard(None, item, model)
        provider_id = str(getattr(item, "id", "") or "") or None
        if getattr(item, "kind", "") != "cloud":
            raise AIProviderUnavailable("The agent needs a managed provider selected in Admin > AI.")
        if not item.configured:
            raise AIProviderUnavailable(f"{item.name} is not configured.")
        definition = get_provider_definition(item.id)
        stream_chat = getattr(item, "stream_chat", None)
        if definition is None or not definition.supports(AIOperation.AGENT_TURN) or not callable(stream_chat):
            raise AIProviderUnavailable(f"{item.name} cannot stream agent turns.")
        # I-1's backstop, per model round: a stream whose funding closed (TTL, settlement) stops at its next round.
        # The effective bound is the provider's own read timeout, capped by the turn's remaining time.
        _require_paid_funding(AGENT_TURN_CAPABILITY, provider_id, model,
                              _effective_timeout(timeout_seconds, getattr(item, "timeout", None)))
        sent["request"] = True
        events = stream_chat(
            messages=messages,
            tools=tools,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            should_stop=should_stop,
            read_timeout=timeout_seconds,
            **({"tool_choice": tool_choice} if tool_choice is not None else {}),
        )
    except (AICapabilityError, AIProviderError) as exc:
        record("failure", error=exc)
        raise

    def recorded() -> Iterator[ChatStreamEvent]:
        finished: ChatFinished | None = None
        try:
            for event in events:
                if isinstance(event, ChatFinished):
                    finished = event
                yield event
        except (AICapabilityError, AIProviderError) as exc:
            record("failure", error=exc)
            raise
        except GeneratorExit:
            # The learner left mid-round: the provider may already have been
            # paid, so the round is recorded rather than lost.
            if finished is not None:
                record("success", finished=finished)
            else:
                record("failure", error_class="client_abandoned")
            raise
        if finished is not None:
            # A round that did not end normally is a failure in the telemetry too, with its usage kept (it may be paid).
            if finished.finish_reason in ("stop", "tool_calls"):
                record("success", finished=finished)
            else:
                record("failure", finished=finished, error_class="abnormal_finish")

    return recorded()


def enforce_pool_rule(capability_key: str | None, pool: Sequence[ProviderTarget] | None) -> None:
    """D-228: a caller-built pool is honoured only for `POOL_CAPABILITIES`, and those never fall back to the stored chain."""

    from writing_coach.ai.capabilities import POOL_CAPABILITIES

    if capability_key in POOL_CAPABILITIES:
        if not pool:
            raise AICapabilityUnsupported(f"AI capability {capability_key!r} runs only on a caller-built pool.")
    elif pool is not None:
        raise AICapabilityUnsupported(f"AI capability {capability_key!r} does not take a caller-built pool.")


def generate_structured(
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    max_output_tokens: int = 1200,
    temperature: float = 0.1,
    seed: int | None = None,
    capability_key: str | None = None,
    validate: Callable[[dict[str, Any]], None] | None = None,
    deadline: float | None = None,
    invalid_retries: int = 0,
    attempt_timeout: float | None = None,
    router_version: str | None = None,
    capability_mode: bool = False,
    health: Any = None,
    paid_standby: bool = True,
    routable: bool = True,
    pool: Sequence[ProviderTarget] | None = None,
) -> AIResult:
    """One structured request through the learner runtime.

    The AI Cost Router (D-195) adds keyword-only inputs, all inert by default: `validate` is the contract's semantic
    check, run inside the chain so an invalid answer retries (`invalid_retries`) and then moves on to the standby
    like any availability failure; `deadline` is an absolute `monotonic()` time for the whole chain, and each
    attempt's HTTP timeout is the configured one (else `attempt_timeout`) capped by what remains; `router_version`
    adds the router's fields to telemetry; `capability_mode` selects the explicit capability configuration whatever
    `AI_RUNTIME_MODE` is (a routed capability has no legacy selection); `health` is a private `ProviderHealth` for a
    background caller (D-200), so its failures never cool a provider down for the learner's own requests.
    `paid_standby=False` (the translate-ahead prefetch) never asks a paid pool entry: background work does not spend.
    `pool` (D-228) replaces the stored primary/backup chain with a caller-built ordered chain, for the one capability
    whose pool is chosen per request (`word_sense_choice`); the capability must still be saved and enabled, and every
    rung still goes through the budget, funding and health gates.
    """

    started = perf_counter()
    provider_id: str | None = None
    model: str | None = None
    attempts_made = {"calls": 0}
    # PR-MON-6 §8: a request that left Orena and got no accounted answer (finish / invalid output record their own).
    unaccounted = {"legacy": False, "rung": False}

    def finish(result: AIResult, attempts: list[Attempt] | None = None) -> AIResult:
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
            "billable_attempt": True,
            **_router_fields(router_version, provider_id, model_display, attempt=len(attempts or ()) or 1),
        }
        switch = provider_switch(attempts, provider_id)
        if switch is not None:
            runtime["telemetry"]["provider_switch"] = switch
        if router_version is not None:
            runtime["router"] = {"attempts": list(attempts or ()), "calls": attempts_made["calls"]}
        _persist_operation_telemetry(runtime["telemetry"])
        result.runtime = runtime
        return result

    try:
        enforce_pool_rule(capability_key, pool)
        # `routable=False`: a caller that shares a capability key but is not part of the routed slice (the reading
        # summary reuses `text_discussion`; its shared cache blocks it until 7A-follow-up) stays on the legacy path.
        routed = routable and capability_key is not None and capability_key in routed_capabilities()
        capability_mode = capability_mode or routed
        if runtime_mode() is AIRuntimeMode.LEGACY and not capability_mode:
            item, model = active_selection()
            provider_id = str(getattr(item, "id", "") or "") or None
            if not item.configured:
                raise AIProviderUnavailable(f"{item.name} is not configured.")
            _legacy_privacy_guard(capability_key, item, model)
            if provider_tier(provider_id or "", model or "") == "paid":
                # D-251: one selected model has no economy rung to give way to; at the hard ceiling it is refused.
                learner = _learner_cost.learner_cost_state()
                if learner.state == _learner_cost.REFUSE:
                    raise _learner_cost.LearnerCostCapReached(learner)

            # Do not silently fail over to a paid provider.
            _require_paid_funding(capability_key or "legacy", provider_id, model,
                                  _effective_timeout(attempt_timeout, getattr(item, "timeout", None)))
            unaccounted["legacy"] = True
            # D-251 review: the single selected model reserves its estimate too, atomically with the state check.
            legacy_usd = _learner_cost.estimate_call_usd(
                provider_id or "", model or "", output_tokens=max_output_tokens,
                input_tokens=max(1, sum(len(str(m.get("content") or "")) for m in messages if isinstance(m, dict)) // 3))
            with _learner_cost.admit_paid(_learner_cost.current_account(),
                                          ProviderTarget(provider_id or "", model or ""), legacy_usd,
                                          single_model=True):
                answer = item.generate_json(
                    messages=messages,
                    schema=schema,
                    model=model,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                    seed=seed,
                )
            unaccounted["legacy"] = False
            return finish(answer)

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
        validate_capability_config(definition.key, config, enforce_cap=False)  # a zero cap is the gate below
        if routed:
            # PR-MON-7: a routed capability runs only on its reviewed primary and reviewed backup (§4.2), and its paid
            # backup is gated by the routed daily cap (0 by default: no paid backup).
            validate_routed_policy(definition.key, config, enforce_cap=False)
            definition = routed_definition(definition.key)

        # The operator configured a backup pair; until now nothing used it, so
        # one rate-limited provider stopped the capability. The chain asks each
        # rung once - never twice, so a learner turn cannot be answered twice -
        # and a malformed request still fails on the first rung, unchanged.
        chain = list(pool) if pool is not None else build_chain(
            provider=config.provider,
            model=config.model,
            backup_provider=config.backup_provider,
            backup_model=config.backup_model,
            timeout_seconds=config.timeout_seconds,
        )

        def _timeout_for(target: ProviderTarget) -> float | None:
            """This attempt's HTTP timeout: the configured one (else the caller's), capped by what remains."""

            limit = float(target.timeout_seconds) if target.timeout_seconds is not None else attempt_timeout
            if deadline is not None:
                remaining = max(0.05, deadline - _routing.monotonic())
                # A rung with a backup after it never spends the whole deadline: a primary that times out (a
                # configured timeout longer than the capability's deadline) still leaves the backup its time.
                if target in chain and any(_backup_can_answer(later, health) for later in chain[chain.index(target) + 1:]):
                    remaining = max(_routing.MIN_ATTEMPT_SECONDS, remaining - min(BACKUP_RESERVE_SECONDS, remaining / 2))
                limit = remaining if limit is None else min(limit, remaining)
            return limit

        budget = _budget_gate(definition, paid_ok=paid_standby)
        if routed and budget is not None:
            # PR-MON-7: the routed daily cap belongs to the reviewed paid BACKUP and measures only that backup's own
            # spend (provider and model), never the primary's. The reviewed primary - Ollama Cloud, priced as paid -
            # is never skipped by it; the funding gate still applies to every paid rung.
            primary, cap_policy = chain[0], definition.paid_standby_cap_policy

            def budget(target: ProviderTarget) -> str | None:
                if target == primary or provider_tier(target.provider, target.model) != "paid":
                    return None
                if not paid_standby:
                    return "budget"
                refused = spend_gate.paid_refused(definition.key, cap_policy, provider=target.provider,
                                                  model=target.model)
                return "budget" if refused else None

        # D-251: the learner's own daily cost cap, by plan. At the cap the paid rungs give way to the economy model; at
        # the hard ceiling only free and local rungs run, and a chain of paid rungs alone is refused (429 quota_exhausted).
        learner = _learner_cost.learner_cost_state()
        if learner.state != _learner_cost.OK:
            chain = _learner_cost.admitted_chain(chain, learner)
            if not chain:
                raise _learner_cost.LearnerCostCapReached(learner)
            economy = learner.economy if learner.state == _learner_cost.DEGRADE else None
            if economy is not None and budget is not None:
                capability_budget = budget

                def budget(target: ProviderTarget) -> str | None:
                    # The learner's economy model answers under the learner's own cap, not the capability's backup cap
                    # (a routed backup's 0 means "no reviewed backup", not "no economy model"); privacy and funding
                    # still gate it.
                    if (target.provider, target.model) == (economy.provider, economy.model):
                        return None
                    return capability_budget(target)

        gate = _funded_gate(definition.key, budget,
                            lambda target: _effective_timeout(_timeout_for(target), _provider_timeout(target.provider)))
        admit = _privacy_gate(definition, gate)

        def _ask(target: ProviderTarget) -> AIResult:
            nonlocal provider_id, model
            provider_id, model = target.provider, target.model
            item = providers().get(target.provider)
            if item is None:
                raise AIProviderUnavailable(f"Unknown AI provider: {target.provider!r}.")
            if not item.configured:
                raise AIProviderUnavailable(f"{item.name} is not configured.")
            generate_once = getattr(item, "generate_json_once", None) or item.generate_json

            def _retry_admitted() -> bool:
                if deadline is not None and deadline - _routing.monotonic() < MIN_RETRY_SECONDS:
                    return False  # no time for a second try: the standby gets what is left
                # a retry is another paid call: it is admitted again, never assumed from the first
                return gate is None or gate(target) is None

            def _generate() -> AIResult:
                """One answer from this rung; an answer that is not a complete JSON object is asked again once (PR CA)."""

                for malformed_try in range(MALFORMED_JSON_RETRIES + 1):
                    options: dict[str, Any] = {}
                    timeout = _timeout_for(target)
                    if timeout is not None:
                        options["timeout"] = timeout
                    attempts_made["calls"] += 1
                    unaccounted["rung"] = True
                    try:
                        return generate_once(
                            messages=messages,
                            schema=schema,
                            model=target.model,
                            max_output_tokens=max_output_tokens,
                            temperature=config.temperature if config.temperature is not None else temperature,
                            seed=seed,
                            **options,
                        )
                    except AIProviderResponseInvalid as exc:
                        if isinstance(exc, AIOutputInvalid) or malformed_try >= MALFORMED_JSON_RETRIES:
                            raise
                        # This answer was billed: recorded first with its usage, so the ledger prices it before the
                        # spend gate decides on the retry. The rung's outcome is the retry's; only a second malformed
                        # answer (or a refused retry) fails the rung, recorded once by the chain.
                        unaccounted["rung"] = False
                        _record_invalid_output(capability_key, target, None, router_version,
                                               attempt=chain.index(target) + 1,
                                               runtime=getattr(exc, "runtime", None),
                                               error_class=telemetry_error_class(exc))
                        if not _retry_admitted():
                            raise
                raise AssertionError("unreachable")  # pragma: no cover

            invalid: AIOutputInvalid | None = None
            for _try in range(max(0, int(invalid_retries)) + 1):
                if _try and not _retry_admitted():
                    break
                result = _generate()
                unaccounted["rung"] = False   # answered: its cost is recorded by finish() or as invalid output
                if validate is None:
                    return result
                try:
                    validate(result.data)
                    return result
                except AIOutputInvalid as exc:
                    invalid = exc
                    _record_invalid_output(capability_key, target, result, router_version, attempt=chain.index(target) + 1)
            assert invalid is not None
            raise invalid

        # D-251 review: before each paid rung the learner's state is read and the call's estimate reserved under that
        # learner's lock (atomic), held until the call returns, so concurrent calls cannot all pass a cap.
        learner_account = learner.account
        input_estimate = max(1, sum(len(str(item.get("content") or "")) for item in messages
                                    if isinstance(item, dict)) // 3)

        def _ask_reserved(target: ProviderTarget) -> AIResult:
            usd = _learner_cost.estimate_call_usd(target.provider, target.model, input_tokens=input_estimate,
                                                  output_tokens=max_output_tokens)
            with _learner_cost.admit_paid(learner_account, target, usd):
                return _ask(target)

        try:
            outcome = run_chain(
                chain, _ask_reserved, on_attempt=_record_attempt(capability_key, router_version,
                                                        sent=lambda: unaccounted.pop("rung", False)),
                deadline=deadline,
                health=health, admit=admit,
            )
        except AllProvidersUnavailable as error:
            skipped = [a for a in getattr(error, "attempts", []) or []]
            if skipped and all(getattr(a, "reason", None) == "unfunded" for a in skipped):
                from writing_coach.billing.funding_context import FundingRequired

                raise FundingRequired("no_unpaid_rung", capability=definition.key) from error
            raise
        provider_id, model = outcome.target.provider, outcome.target.model
        return finish(outcome.value, outcome.attempts)
    except (AICapabilityError, AIProviderError) as exc:
        model_display, model_redacted = safe_model_display(model)
        if router_version is not None:
            exc.router_calls = attempts_made["calls"]  # type: ignore[attr-defined]
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
            # the legacy call that raised was sent; a chain's rungs were each recorded already (never twice)
            "billable_attempt": unaccounted["legacy"],
            "failure_class": failure_class_of(exc),
            # PR BZ: a chain's rungs were each recorded already; this closing row is not counted again by health.
            **({"chain_summary": True} if getattr(exc, "attempts", None) else {}),
            **({"provider_switch": switch} if (switch := provider_switch(getattr(exc, "attempts", None), None)) else {}),
            **_router_fields(router_version, provider_id, model_display, attempt=len(getattr(exc, "attempts", ())) or 1,
                             reason=fallback_reason(exc) if isinstance(exc, AIProviderError) else None,
                             status_class=http_status_class(getattr(exc, "status_code", None))),
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
    result = _control_plane().inspect()
    mode = runtime_mode()
    result["learner_runtime"] = {"mode": mode.value}
    result["policy"]["learner_runtime_uses_capability_config"] = mode is AIRuntimeMode.CAPABILITY
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
    test_current: bool = False,
) -> dict[str, Any]:
    item = providers().get(provider_id)
    if item is None:
        raise HTTPException(404, "Unknown AI provider.")
    existing = _stored_provider_credentials(provider_id)
    supplied_key = payload.api_key.get_secret_value().strip() if payload.api_key is not None else ""
    api_key = supplied_key or str(existing.get("api_key") or "").strip()
    # Test the current environment credential without returning or copying it
    # into the store. A changed endpoint must never receive that credential.
    if test_current and not api_key and not payload.base_url:
        api_key = str(getattr(item, 'api_key', '') or '').strip()
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
    if isinstance(item, OpenAICompatibleProvider):
        base_url = normalize_openai_base_url(base_url)  # a pasted ".../chat/completions" is stored as the base
    from urllib.parse import urlsplit

    parsed = urlsplit(base_url)
    if parsed.username or parsed.password or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Provider endpoint must be a valid URL without embedded credentials.")
    if (item.secret_mode == "server-managed" or api_key) and parsed.scheme != "https":
        raise HTTPException(400, "Provider credentials require an HTTPS endpoint.")
    if provider_id == 'azure-speech':
        from writing_coach.ai.azure import speech_region
        try:
            speech_region(base_url)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    if provider_id == 'azure-openai' and (not parsed.hostname or not parsed.hostname.endswith(('.openai.azure.com', '.services.ai.azure.com')) or parsed.path.rstrip('/') != '/openai/v1' or parsed.query or parsed.fragment or parsed.port):
        raise HTTPException(400, 'Use the Azure resource HTTPS /openai/v1 endpoint.')
    models = sorted({str(model).strip() for model in payload.models if str(model).strip()})
    if any(len(model) > 160 or any(ord(char) < 32 for char in model) for model in models):
        raise HTTPException(400, "Model names must be readable values of 160 characters or fewer.")
    if len(models) > 100:
        raise HTTPException(400, "A provider can have at most 100 configured models.")
    default_model = payload.default_model.strip() or (str(getattr(item, 'default_model', '') or '') if test_current else '')
    if provider_id == 'azure-speech':
        models = ['pronunciation-assessment']
        default_model = models[0]
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
        if provider_id == 'azure-openai':
            deployment = values.get('default_model')
            if not deployment:
                raise HTTPException(400, 'Enter your Azure OpenAI deployment name.')
            result = item.generate_json_once(messages=[{'role': 'user', 'content': 'Return {"ok":true}.'}],
                schema={'type': 'object'}, model=deployment, max_output_tokens=64, temperature=0)
            if result.data.get('ok') is not True:
                raise AIProviderResponseInvalid('Azure deployment test returned an invalid result.')
            return [deployment]
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
        values = _provider_credential_values(provider_id, payload, require_models=False, test_current=True)
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
    return _control_plane().operations(limit=limit)


def ai_health_report() -> dict[str, Any]:
    """Provider health (PR BZ): the recorded operations of the last minutes per provider and capability, the router's
    breaker in this process, the recent provider switches and the providers that are down. Counts and closed words
    only (ai/health_signal.py)."""

    from writing_coach.ai.health_signal import report_from_repository, unavailable_report

    breaker = _routing.provider_health.snapshot()
    try:
        repository = _installed_platform_repository()
    except RuntimeError:
        report = unavailable_report()
        report.update({"switches": [], "down": []})
    else:
        report = report_from_repository(repository, breaker=breaker)
    report["breaker"] = [{"provider": key, "model": None, **state} for key, state in sorted(breaker.items())]
    # Each provider's display name, so a page that loads no provider list (the Overview) still says "OpenRouter".
    from writing_coach.ai.providers import provider_definitions

    report["provider_names"] = {definition.id: definition.name for definition in provider_definitions()}
    return report


@router.get("/health")
def admin_ai_health(request: Request, response: Response) -> dict[str, Any]:
    _require_admin(request)
    response.headers["Cache-Control"] = "no-store"
    return ai_health_report()


# Audio capabilities are reported per minute of audio; every other one per call.
_PER_MINUTE = frozenset({"speech_asr"})
# (code, English text): the Admin page words each code in the interface language.
COST_REPORT_GAPS = (
    ("per_learner", "Per learner: the operation telemetry is anonymous by design. Cost per account is recorded "
     "separately once migration 20261005_0026 is applied (AC-2); before that, only Orena agent turns carry an "
     "account."),
    ("per_turn", "Per Orena turn: a turn is one to four agent_turn_fast rounds; the per-turn cost is in the "
     "agent.turn timeline report, not here."),
    ("infrastructure", "Infrastructure (hosting, database, storage, bandwidth) is not measured: unknown."),
    ("audio_list_price", "Audio rates are provider list prices (ai/pricing.py); the Azure pronunciation rate is to "
     "be checked against the Azure bill."),
    ("audio_before", "Calls before 2026-10-04 for speech recognition and pronunciation scoring were never recorded."),
    ("free_tier_tier", "Free tier: an amount on a free plan is shown at its list price, apart from real spend. Calls "
     "recorded before the tier was stamped (2026-10-16) are counted as unknown tier, in neither."),
    ("environment_shared", "Environment: this page reads one environment's database and media ledger. The same "
     "provider key is spent from every other environment (staging, preview, sandboxes, other lanes, scripts), which "
     "record elsewhere, so the provider's own console total is larger than this page by design."),
    ("voice_ceiling", "Orena voice (Gemini Live) is recorded as the session's token life at a ceiling rate: the "
     "vendor reports its real audio and text usage only to the browser, which the server never sees."),
    ("account_tier", "Cost by account has no tier column (its schema is a human gate): the tier is read from the "
     "flag's change history in the audit log, at the time of each record."),
)


# D-219: an amount split by the tier stamped on the event.
_TIER_FIELDS = ("usd_real", "usd_free", "usd_unknown")


def cost_report(rows: list[dict[str, Any]], *, days: int, since: datetime) -> dict[str, Any]:
    """The ledger rows as the cost report reads them: by day, and by feature x provider x model with a unit
    cost - per priced call, or per audio minute for speech recognition. An average over nothing is null."""

    by_day: dict[str, dict[str, Any]] = {}
    by_feature: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        day = by_day.setdefault(row["day"], {"day": row["day"], "calls": 0, "usd": 0.0, "unpriced_calls": 0,
                                             **dict.fromkeys(_TIER_FIELDS, 0.0)})
        day["calls"] += row["calls"]
        day["usd"] += row["usd"]
        day["unpriced_calls"] += row["unpriced_calls"]
        for name in _TIER_FIELDS:
            day[name] += row.get(name, 0.0)
        key = (row["capability"] or "", row["provider"] or "", row["model"] or "")
        item = by_feature.setdefault(key, {"capability": key[0], "provider": key[1] or None, "model": key[2] or None,
                                           "calls": 0, "failures": 0, "priced_calls": 0, "unpriced_calls": 0,
                                           "usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0,
                                           "audio_seconds": 0.0, **dict.fromkeys(_TIER_FIELDS, 0.0)})  # fmt: skip
        for name in ("calls", "failures", "priced_calls", "unpriced_calls", "usd", "prompt_tokens",
                     "completion_tokens", "audio_seconds"):  # fmt: skip
            item[name] += row[name]
        for name in _TIER_FIELDS:
            item[name] += row.get(name, 0.0)
    features = []
    for item in by_feature.values():
        item["usd"] = round(item["usd"], 8)
        for name in _TIER_FIELDS:
            item[name] = round(item[name], 8)
        if item["capability"] in _PER_MINUTE:
            minutes = item["audio_seconds"] / 60
            item["unit"], item["usd_per_unit"] = "audio_minute", round(item["usd"] / minutes, 6) if minutes else None
        else:
            item["unit"] = "call"
            item["usd_per_unit"] = round(item["usd"] / item["priced_calls"], 6) if item["priced_calls"] else None
        features.append(item)
    features.sort(key=lambda entry: -entry["usd"])
    return {
        "since": since.isoformat(), "days": days, "currency": "USD",
        "by_day": [dict(day, usd=round(day["usd"], 8), **{name: round(day[name], 8) for name in _TIER_FIELDS})
                   for day in sorted(by_day.values(), key=lambda d: d["day"], reverse=True)],
        "by_feature": features,
        # D-219: `usd` is every computed amount (list price); `usd_real` only events stamped free_tier=false; `usd_free`
        # the list-price value of free-plan events; `usd_unknown` events written before the stamp existed.
        "totals": {name: round(sum(day[name] for day in by_day.values()), 8) for name in ("usd", *_TIER_FIELDS)},
        "gaps": [{"code": code, "text": text} for code, text in COST_REPORT_GAPS],
    }


def environment_report(rows: list[dict[str, Any]], *, current: str) -> dict[str, Any]:
    """D-221: the events of this database by the environment that wrote them, with this process's own marked. An
    environment of None wrote before the tag existed. Other environments record into other databases and never appear."""

    return {"current": current,
            "by_environment": [{**row, "current": row.get("environment") == current} for row in rows]}


@router.get("/costs")
def admin_ai_costs(request: Request, days: int = 30) -> dict[str, Any]:
    """AI cost by day and by feature, provider and model, from the shared ledger (no UI yet: UI_BACKEND_GAPS)."""

    _require_admin(request)
    bounded = max(1, min(int(days), 90))
    now = datetime.now(UTC)
    since = datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=bounded - 1)
    repository = _installed_platform_repository()
    reader = getattr(repository, "ai_cost_rows", None)
    rows = reader(since) if callable(reader) else []
    timeline = _flag_timeline(repository)
    if timeline is not None:
        rows = _place_unstamped_rows(repository, rows, timeline, since, now)
    report = cost_report(rows, days=bounded, since=since)
    report["media"] = _media_spend_totals(bounded, timeline.tier_at if timeline is not None else None)
    from writing_coach import cost_env

    environments = getattr(repository, "ai_cost_environments", None)
    try:
        env_rows = environments(since) if callable(environments) else []
    except Exception:  # noqa: BLE001 - the environment block never fails the cost report
        env_rows = []
    report["environments"] = environment_report(env_rows, current=cost_env.label())
    return report


def _flag_timeline(repository: Any) -> Any:
    """The free-tier flags' history from the audit log, or None where it cannot be read (the archive store)."""

    history = getattr(repository, "policy_change_history", None)
    if not callable(history):
        return None
    from writing_coach import cost_tier
    from writing_coach import policies as _policies

    # The whole history is read (the table is a handful of rows): a flag stored ON that no audit row explains is
    # "unknown" for the window, never silently free.
    return cost_tier.timeline_from_audit(
        history(datetime(2000, 1, 1, tzinfo=UTC)),
        pinned=frozenset(name for name in cost_tier.PROVIDERS if _policies.is_pinned(cost_tier.flag_key(name))),
        stored=frozenset(name for name in cost_tier.PROVIDERS if _policies.has_admin_value(cost_tier.flag_key(name))))


def _place_unstamped_rows(repository: Any, rows: list[dict[str, Any]], timeline: Any, since: datetime,
                          now: datetime) -> list[dict[str, Any]]:
    """D-220 (PROPOSED): events written before D-219 carry no stamp. Place them by the flag's history instead of leaving
    them "unknown": a paid provider's past spend is real, a free plan's is free; a history that cannot say stays unknown.
    The total `usd` (and so every cap) is untouched."""

    from writing_coach import cost_tier

    reader = getattr(repository, "ai_unstamped_cost_rows", None)
    if not callable(reader) or not any(row.get("usd_unknown") for row in rows):
        return rows
    boundaries = timeline.boundaries(since, now)
    edges = [since, *boundaries[:200], now + timedelta(seconds=1)]
    pieces = [(start, reader(start, end)) for start, end in zip(edges, edges[1:], strict=False)]
    return cost_tier.reclassify_unstamped(rows, pieces, timeline.tier_at, last_unknown=len(boundaries) > 200)


# The media processing spend lives in its own ledger (media_spend.py); app.py registers its reader here so the one cost
# page can show both stores without this module importing the media pipeline.
_media_spend_reader: Callable[..., dict[str, Any]] | None = None


def register_media_spend_reader(reader: Callable[..., dict[str, Any]] | None) -> None:
    global _media_spend_reader
    _media_spend_reader = reader


def _media_spend_totals(days: int, tier_at: Any = None) -> dict[str, Any] | None:
    if _media_spend_reader is None:
        return None
    try:
        return _media_spend_reader(days, tier_at)
    except Exception:  # noqa: BLE001 - an unreadable ledger leaves the block out; it never fails the report
        return None


@router.get("/costs/accounts")
def admin_ai_costs_by_account(request: Request, days: int = 30) -> dict[str, Any]:
    """AI cost per account (AC-2), an administrator's view only; each look is itself recorded. The window is at
    most 90 days, like the totals, though records are kept 13 months."""

    admin = _require_admin(request)
    bounded = max(1, min(int(days), 90))
    now = datetime.now(UTC)
    since = datetime(now.year, now.month, now.day, tzinfo=UTC) - timedelta(days=bounded - 1)
    reader = getattr(_installed_platform_repository(), "ai_costs_by_account", None)
    limit = 100
    # One more than shown, to say whether the list was cut (the page shows the most expensive accounts only).
    accounts = None
    tiered = getattr(_installed_platform_repository(), "ai_costs_by_account_tiered", None)
    history = getattr(_installed_platform_repository(), "policy_change_history", None)
    if callable(tiered) and callable(history):
        # D-219: split each account's cost into real and free-tier by the flag's state at the time of each record.
        from writing_coach import cost_tier
        from writing_coach import policies as _policies

        # The whole history is read (the table is a handful of rows): a flag stored ON that no audit row explains is
        # "unknown" for the window, never silently free.
        timeline = cost_tier.timeline_from_audit(
            history(datetime(2000, 1, 1, tzinfo=UTC)),
            pinned=frozenset(name for name in cost_tier.PROVIDERS if _policies.is_pinned(cost_tier.flag_key(name))),
            stored=frozenset(name for name in cost_tier.PROVIDERS if _policies.has_admin_value(cost_tier.flag_key(name))))
        accounts = tiered(since, now + timedelta(seconds=1), timeline.boundaries(since, now), timeline.tier_at,
                          limit=limit + 1)
    if accounts is None and callable(reader):
        accounts = reader(since, limit=limit + 1)
    _record_admin_event(admin, "admin.ai.costs.accounts.view", entity_type="ai_costs", entity_id="accounts",
                        payload={"days": bounded, "available": accounts is not None})
    return {"since": since.isoformat(), "days": bounded, "currency": "USD", "available": accounts is not None,
            "accounts": (accounts or [])[:limit], "truncated": len(accounts or []) > limit}


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
        if provider_id == 'azure-speech':
            raise HTTPException(400, 'Azure Speech cannot be selected as a text model.')

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
    if provider_id == 'azure-speech':
        started = perf_counter()
        try:
            item.discover_models_live()
        except (AIProviderNotConfigured, AIProviderUnavailable, AIProviderError, AIProviderResponseInvalid) as exc:
            raise HTTPException(502, f"Provider connection validation failed: {exc}") from exc
        return {'ok': True, 'provider': provider_id, 'model': item.default_model, 'latency_ms': int((perf_counter() - started) * 1000)}

    schema = {
        "type": "object",
        "properties": {
            "ok": {"type": "boolean"},
            "message": {"type": "string"},
        },
        "required": ["ok", "message"],
    }

    test_started = perf_counter()
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
    # D-221: the connection test is a real, billed completion. It was the one Gemini call path with no cost row; it is
    # recorded as an operator test (never an account's spend, still in the provider's total).
    from writing_coach.ai.audio_telemetry import record_token_operation, telemetry_origin

    with telemetry_origin("operator_test"):
        record_token_operation("ai_connection_test", provider=provider_id, model=model, outcome="success",
                               latency_ms=int((perf_counter() - test_started) * 1000), usage=result.runtime,
                               billable_attempt=True)

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
        result = _control_plane().set_config(
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
        **{key: telemetry[key] for key in ("http_status_class", "fallback_reason") if key in telemetry},
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
    control_plane = _control_plane()
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
