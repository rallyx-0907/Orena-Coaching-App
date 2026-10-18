"""Typed AI capability configuration and offline/static validation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping

from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AICapabilityUnsupported,
    AIProviderUnsupportedOperation,
)
from writing_coach.ai.capabilities import (
    AICapabilityDefinition,
    AIFallbackPolicy,
    NO_BACKUP_CAPABILITIES,
    require_capability,
)
from writing_coach.ai.pricing import is_free_model, resolve_token_pricing
from writing_coach.ai.providers import ProviderDefinition, check_model_allowed, get_provider_definition
from writing_coach.ai.routing import provider_tier


CONFIG_VERSION = 1
CAPABILITY_SETTING_PREFIX = "ai.capability."
_CONFIG_FIELDS = frozenset(
    {
        "config_version",
        "enabled",
        "provider",
        "model",
        "backup_provider",
        "backup_model",
        "timeout_seconds",
        "temperature",
        "fallback_policy",
    }
)
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_MODEL_ID = re.compile(r"^[^\s\x00-\x1f\x7f]{1,160}$")


def _invalid(message: str) -> AICapabilityConfigInvalid:
    return AICapabilityConfigInvalid(message)


@dataclass(frozen=True)
class CapabilityConfig:
    """Secret-free operator configuration stored in platform_settings JSON."""

    enabled: bool
    provider: str
    model: str
    backup_provider: str | None = None
    backup_model: str | None = None
    timeout_seconds: int | None = None
    temperature: float | None = None
    fallback_policy: AIFallbackPolicy = AIFallbackPolicy.NONE
    config_version: int = CONFIG_VERSION

    def __post_init__(self) -> None:
        if type(self.config_version) is not int or self.config_version != CONFIG_VERSION:
            raise _invalid(f"Unsupported capability config_version: {self.config_version!r}.")
        if type(self.enabled) is not bool:
            raise _invalid("Capability enabled must be a boolean.")

        provider = str(self.provider or "").strip().casefold()
        model = str(self.model or "").strip()
        if not _PROVIDER_ID.fullmatch(provider):
            raise _invalid("Capability provider is not a valid provider identifier.")
        if not _MODEL_ID.fullmatch(model):
            raise _invalid("Capability model must be a non-empty sanitized identifier.")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)

        backup_provider = str(self.backup_provider or "").strip().casefold() or None
        backup_model = str(self.backup_model or "").strip() or None
        if (backup_provider is None) != (backup_model is None):
            raise _invalid("Capability backup provider and model must be supplied together.")
        if backup_provider is not None and not _PROVIDER_ID.fullmatch(backup_provider):
            raise _invalid("Capability backup provider is not a valid provider identifier.")
        if backup_model is not None and not _MODEL_ID.fullmatch(backup_model):
            raise _invalid("Capability backup model must be a non-empty sanitized identifier.")
        object.__setattr__(self, "backup_provider", backup_provider)
        object.__setattr__(self, "backup_model", backup_model)

        if self.timeout_seconds is not None:
            if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 600:
                raise _invalid("Capability timeout_seconds must be an integer from 1 to 600.")
        if self.temperature is not None:
            if type(self.temperature) not in {int, float}:
                raise _invalid("Capability temperature must be numeric.")
            temperature = float(self.temperature)
            if not math.isfinite(temperature) or not 0.0 <= temperature <= 2.0:
                raise _invalid("Capability temperature must be from 0.0 to 2.0.")
            object.__setattr__(self, "temperature", temperature)

        try:
            fallback = AIFallbackPolicy(self.fallback_policy)
        except (TypeError, ValueError) as exc:
            raise _invalid("Capability fallback_policy is unknown.") from exc
        object.__setattr__(self, "fallback_policy", fallback)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_version": self.config_version,
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "backup_provider": self.backup_provider,
            "backup_model": self.backup_model,
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "fallback_policy": self.fallback_policy.value,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | object) -> "CapabilityConfig":
        if not isinstance(raw, Mapping):
            raise _invalid("Capability config must be a JSON object.")
        unknown = set(raw) - _CONFIG_FIELDS
        missing = {"config_version", "enabled", "provider", "model", "fallback_policy"} - set(raw)
        if unknown:
            raise _invalid(f"Capability config contains unknown fields: {sorted(unknown)!r}.")
        if missing:
            raise _invalid(f"Capability config is missing fields: {sorted(missing)!r}.")
        return cls(
            config_version=raw["config_version"],
            enabled=raw["enabled"],
            provider=raw["provider"],
            model=raw["model"],
            backup_provider=raw.get("backup_provider"),
            backup_model=raw.get("backup_model"),
            timeout_seconds=raw.get("timeout_seconds"),
            temperature=raw.get("temperature"),
            fallback_policy=raw["fallback_policy"],
        )


def capability_setting_key(capability_key: str) -> str:
    return CAPABILITY_SETTING_PREFIX + require_capability(capability_key).key


def capability_key_from_setting(setting_key: str) -> str | None:
    if not str(setting_key).startswith(CAPABILITY_SETTING_PREFIX):
        return None
    return str(setting_key)[len(CAPABILITY_SETTING_PREFIX) :]


def _check_tiers(definition: AICapabilityDefinition, config: CapabilityConfig, *, enforce_cap: bool) -> None:
    """The tier rule (D-195 amendment 2026-10-14): the primary is free or local; the standby is too, or a priced paid
    model when the capability has a daily spend cap policy and that cap is above zero. Escalation and premium tiers
    are not part of the v1 document and stay refused."""

    if provider_tier(config.provider, config.model) == "paid":
        raise AICapabilityConfigInvalid(
            f"{definition.key!r} needs a free or local primary: {config.provider!r} / {config.model!r} is paid."
        )
    if config.backup_provider is None or provider_tier(config.backup_provider, config.backup_model or "") != "paid":
        return
    label = f"{config.backup_provider!r} / {config.backup_model!r}"
    cap_key = definition.paid_standby_cap_policy
    if not cap_key:
        raise AICapabilityConfigInvalid(f"{definition.key!r} accepts free or local models only: {label} is paid.")
    if (config.backup_provider, config.backup_model) not in definition.paid_standby_models or (
        resolve_token_pricing(config.backup_provider, config.backup_model) is None
    ):
        raise AICapabilityConfigInvalid(
            f"{definition.key!r} accepts only a reviewed, priced paid standby: {label} is not one."
        )
    if enforce_cap:
        # Save time only. At run time a cap of zero is the budget gate skipping the paid standby, not an invalid config.
        from writing_coach import policies

        try:
            cap = float(policies.value_strict(cap_key) or 0)
        except Exception as exc:  # noqa: BLE001 - an unreadable cap is not a cap: refuse to save a paid standby
            raise AICapabilityConfigInvalid(
                f"{definition.key!r} cannot save a paid standby: its daily spend cap ({cap_key}) is unreadable."
            ) from exc
        if not cap > 0:
            raise AICapabilityConfigInvalid(
                f"{definition.key!r} accepts a paid standby only with a daily spend cap above zero ({cap_key}): "
                f"{label} is paid."
            )


# PR-MON-7A-first: the only capabilities `ORENA_CAPABILITY_ROUTING` may list. Each has an account-scoped stored result
# (or none) and an existing learner meter (`writing.review`, `orena.message`). Every other capability stays on the
# legacy selection until its own slice (7A-follow-up after cache isolation, 7B, 7C).
ROUTABLE_CAPABILITIES = frozenset({"writing_evaluator", "writing_improver", "text_discussion"})
ROUTING_SWITCH = "ORENA_CAPABILITY_ROUTING"


def routed_capabilities() -> frozenset[str]:
    """PR-MON-7A-first: the capabilities taken off the legacy selection onto their reviewed chain (`ORENA_CAPABILITY_
    ROUTING`, empty by default). Only `ROUTABLE_CAPABILITIES` may be listed; anything else is ignored and logged."""
    import logging
    import os

    listed = {item.strip() for item in os.getenv(ROUTING_SWITCH, "").split(",") if item.strip()}
    ignored = listed - ROUTABLE_CAPABILITIES
    if ignored:
        logging.getLogger(__name__).warning("%s lists capabilities this build does not route: %s", ROUTING_SWITCH,
                                            sorted(ignored))
    return frozenset(listed & ROUTABLE_CAPABILITIES)


# The daily cap of each routed capability's reviewed paid backup (a `writing_coach.policies` key; default 0 = no paid
# backup, H7-8). It applies only while the capability is routed: on the legacy path nothing changes.
ROUTED_BACKUP_CAP_POLICY = {
    "writing_evaluator": "writing_evaluator.daily_spend_cap_usd",
    "writing_improver": "writing_improver.daily_spend_cap_usd",
    "text_discussion": "text_discussion.daily_spend_cap_usd",
}
assert set(ROUTED_BACKUP_CAP_POLICY) == ROUTABLE_CAPABILITIES


def routed_definition(capability_key: str) -> AICapabilityDefinition:
    """The capability's definition as a routed call sees it: with its routed backup cap policy."""
    import dataclasses

    definition = require_capability(capability_key)
    cap = ROUTED_BACKUP_CAP_POLICY.get(definition.key)
    return dataclasses.replace(definition, paid_standby_cap_policy=cap) if cap else definition


def validate_routed_policy(capability_key: str, config: CapabilityConfig, *, enforce_cap: bool = True) -> None:
    """The static policy of a routed capability (PR-MON-7 design revision 2.1, §4.2), on top of
    `validate_capability_config`. Refused:
    - a capability that is not routable in this build;
    - a primary outside the capability's reviewed primary allowlist;
    - a local provider anywhere in the chain (production has no local-model tier);
    - for learner text: a free tier, a prompt-logging provider, or a model whose provider requires a per-model privacy
      review that has not been given (Ollama Cloud, H7-6);
    - a backup outside the capability's reviewed paid-backup allowlist, an unpriced paid model, or (when saving) a
      paid backup without a readable daily cap above zero."""

    definition = require_capability(capability_key)
    if definition.key not in ROUTABLE_CAPABILITIES:
        raise AICapabilityConfigInvalid(f"{definition.key!r} cannot be routed in this build (PR-MON-7A-first).")
    pool = [("primary", config.provider, config.model)]
    if config.backup_provider is not None:
        pool.append(("backup", config.backup_provider, config.backup_model or ""))
    if (config.provider, config.model) not in definition.reviewed_primary_models:
        raise AICapabilityConfigInvalid(
            f"{definition.key!r} accepts only a reviewed primary: {config.provider!r} / {config.model!r} is not one."
        )
    for role, provider_id, model in pool:
        provider = get_provider_definition(provider_id)
        if provider is None or provider.kind == "local":
            raise AICapabilityConfigInvalid(
                f"{definition.key!r} has no local-model production tier: {role} {provider_id!r} is refused."
            )
        if definition.input_class == "learner_text":
            if provider.may_log_prompts or is_free_model(provider_id, model):
                raise AICapabilityConfigInvalid(
                    f"{definition.key!r} carries learner text: {role} {provider_id!r} / {model!r} is refused."
                )
            if provider.learner_text_models is not None and model not in provider.learner_text_models:
                raise AICapabilityConfigInvalid(
                    f"{definition.key!r} carries learner text: {provider_id!r} / {model!r} has no reviewed privacy "
                    "classification for it."
                )
        if provider_tier(provider_id, model) == "paid" and resolve_token_pricing(provider_id, model) is None:
            raise AICapabilityConfigInvalid(f"{definition.key!r}: {role} {provider_id!r} / {model!r} is unpriced.")
    if config.backup_provider is not None:
        label = f"{config.backup_provider!r} / {config.backup_model!r}"
        if (config.backup_provider, config.backup_model) not in definition.paid_standby_models:
            raise AICapabilityConfigInvalid(f"{definition.key!r} accepts only a reviewed backup: {label} is not one.")
        if enforce_cap:
            from writing_coach import policies

            cap_key = ROUTED_BACKUP_CAP_POLICY.get(definition.key, "")
            try:
                cap = float(policies.value_strict(cap_key) or 0) if cap_key else 0.0
            except Exception as exc:  # noqa: BLE001 - an unreadable cap is not a cap
                raise AICapabilityConfigInvalid(f"{definition.key!r}: the backup's daily cap is unreadable.") from exc
            if not cap > 0:
                raise AICapabilityConfigInvalid(
                    f"{definition.key!r} accepts a paid backup only with a daily spend cap above zero ({cap_key})."
                )


def validate_capability_config(
    capability_key: str,
    config: CapabilityConfig,
    *,
    enforce_cap: bool = True,
) -> tuple[AICapabilityDefinition, ProviderDefinition]:
    """Validate using code-owned metadata only; no runtime provider is built."""

    definition = require_capability(capability_key)
    if not definition.implemented or not definition.provider_backed or not definition.configurable:
        raise AICapabilityUnsupported(
            f"AI capability {definition.key!r} is not provider-configurable."
        )

    if definition.key in NO_BACKUP_CAPABILITIES and config.backup_provider is not None:
        raise AICapabilityConfigInvalid(
            f"{definition.key!r} takes no backup provider: the media spend cap is checked at the primary's price only (D-224)."
        )
    provider = get_provider_definition(config.provider)
    if provider is None:
        raise AICapabilityUnsupported(f"Unknown AI provider: {config.provider!r}.")
    if not provider.supports(definition.operation):
        raise AIProviderUnsupportedOperation(
            f"AI provider {provider.id!r} does not support {definition.operation.value!r}."
        )
    if config.backup_provider is not None:
        backup = get_provider_definition(config.backup_provider)
        if backup is None:
            raise AICapabilityUnsupported(f"Unknown backup AI provider: {config.backup_provider!r}.")
        if not backup.supports(definition.operation):
            raise AIProviderUnsupportedOperation(
                f"Backup AI provider {backup.id!r} does not support {definition.operation.value!r}."
            )

    requested_options = {
        key
        for key, value in {
            "timeout_seconds": config.timeout_seconds,
            "temperature": config.temperature,
        }.items()
        if value is not None
    }
    unsupported = requested_options - provider.supported_option_keys
    if unsupported:
        raise AIProviderUnsupportedOperation(
            f"AI provider {provider.id!r} does not support options: {sorted(unsupported)!r}."
        )
    if config.backup_provider is not None:
        backup = get_provider_definition(config.backup_provider)
        backup_unsupported = requested_options - backup.supported_option_keys
        if backup_unsupported:
            raise AIProviderUnsupportedOperation(
                f"Backup AI provider {backup.id!r} does not support options: {sorted(backup_unsupported)!r}."
            )
    check_model_allowed(provider.id, config.model)
    if config.backup_provider is not None:
        check_model_allowed(config.backup_provider, config.backup_model or "")
    if definition.free_primary_only:
        _check_tiers(definition, config, enforce_cap=enforce_cap)
    pool = [(provider, config.model)]
    if config.backup_provider is not None:
        pool.append((get_provider_definition(config.backup_provider), config.backup_model or ""))
    if definition.input_class == "learner_text":
        # A free tier, or any endpoint that may log prompts, never receives learner-authored text (D-195, D-104).
        for entry, model in pool:
            if entry.may_log_prompts or is_free_model(entry.id, model):
                raise AICapabilityConfigInvalid(
                    f"{definition.key!r} carries learner text: provider {entry.id!r} / model {model!r} "
                    "(a free tier or a provider that may log prompts) is refused."
                )
            # PR-MON-7: a provider that requires a per-model privacy review (Ollama Cloud) sends learner text only to
            # a reviewed model - on every capability-mode path, routed or not (H7-6).
            if entry.learner_text_models is not None and model not in entry.learner_text_models:
                raise AICapabilityConfigInvalid(
                    f"{definition.key!r} carries learner text: {entry.id!r} / {model!r} has no reviewed privacy "
                    "classification for it."
                )
    if definition.key in ROUTABLE_CAPABILITIES:
        # PR-MON-7A-first: these capabilities never run on a local production model, in any capability mode.
        for entry, _model in pool:
            if entry.kind == "local":
                raise AICapabilityConfigInvalid(
                    f"{definition.key!r} has no local-model production tier: {entry.id!r} is refused."
                )
        if definition.key in routed_capabilities():
            # Activated for routing: its whole reviewed policy holds when the config is saved (with the cap check),
            # loaded and called - an invalid routed config is never accepted and never runs.
            validate_routed_policy(definition.key, config, enforce_cap=enforce_cap)
    if config.fallback_policy not in definition.allowed_fallback_policies:
        raise AICapabilityConfigInvalid(
            f"Fallback policy {config.fallback_policy.value!r} is not allowed for {definition.key!r}."
        )
    return definition, provider
