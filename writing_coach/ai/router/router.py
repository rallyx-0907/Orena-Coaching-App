"""`route()`: the one entry point to every routed AI capability (D-18X).

    route(capability_key, input, deadline=None) -> RouteResult

The order is fixed and never random: validate the input, read the operator's configuration (a disabled or
unconfigured capability answers nothing, and serves nothing from the cache), try the deterministic tier, then the
result cache, then the pool in the operator's order. The pool runs through the existing capability runtime
(`platform.generate_structured`), which owns the chain, the cooldown, the per-attempt timeout, the validator and the
telemetry; this module adds the cache, the single flight, the negative cache and the rollup counters around it.

Nothing here names a model. Nothing here puts a word, a prompt or an answer in telemetry.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

import writing_coach.ai.platform as platform
from writing_coach.ai.base import (
    AICapabilityDisabled,
    AICapabilityError,
    AICapabilityNotConfigured,
    AIProviderError,
)
from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.router.cache import NEGATIVE_SECONDS, ResultCache
from writing_coach.ai.router.contract import CapabilityContract, RouterInputInvalid, get_contract
from writing_coach.ai.router.policy import policy_from_v1
from writing_coach.ai.router.stats import RouterStats
from writing_coach.ai.routing import AllProvidersUnavailable, provider_tier

ROUTER_VERSION = "1"
# The operator's configuration is re-read at most this often per worker, so a tap does not read the database; a
# disable takes effect within it.
CONFIG_TTL_SECONDS = 5.0

_clock = time.monotonic
_cache = ResultCache(lambda: _clock())
_stats = RouterStats(lambda: _clock(), ROUTER_VERSION)
_config_held: dict[str, tuple[float, CapabilityConfig | None]] = {}


@dataclass(frozen=True)
class RouteResult:
    output: dict[str, Any]
    # "model" (a provider answered), "cache" (this or a joined request already had), "deterministic" (tier 0).
    source: str
    # Visible to the operator only: provider, model, tier, prompt version, when.
    provenance: dict[str, Any] | None = None


def reset_state() -> None:
    """Forget the cache, the counters and the held configuration (tests, and an operator purge)."""

    global _cache, _stats
    _cache = ResultCache(lambda: _clock())
    _stats = RouterStats(lambda: _clock(), ROUTER_VERSION)
    _config_held.clear()


def flush_rollup(*, force: bool = False) -> int:
    recorder = getattr(platform._platform_repository, "record_admin_event", None)
    return _stats.flush(recorder if callable(recorder) else None, force=force)


def load_config(capability_key: str) -> CapabilityConfig:
    """The enabled configuration, or the typed reason the capability answers nothing."""

    held = _config_held.get(capability_key)
    if held is None or held[0] <= _clock():
        row = platform._installed_platform_repository().get_capability_config(capability_key)
        held = (_clock() + CONFIG_TTL_SECONDS, row.config if row is not None else None)
        _config_held[capability_key] = held
    config = held[1]
    if config is None:
        raise AICapabilityNotConfigured(f"AI capability {capability_key!r} has no explicit configuration.")
    if not config.enabled:
        raise AICapabilityDisabled(f"AI capability {capability_key!r} is disabled.")
    return config


def _cache_key(contract: CapabilityContract, normalized: dict[str, Any]) -> str:
    material = json.dumps(
        [contract.key, contract.contract_version, contract.prompt_version, normalized],
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _cached(value: dict[str, Any]) -> RouteResult:
    return RouteResult(output=dict(value["output"]), source="cache", provenance=value.get("provenance"))


def route(capability_key: str, raw_input: Any, *, deadline: float | None = None) -> RouteResult:
    """Answer one request of a routed capability.

    `deadline` is an absolute `time.monotonic()` time; the whole request also never exceeds the contract's maximum
    total latency. Raises `RouterInputInvalid` (before anything is asked), `AICapabilityDisabled` /
    `AICapabilityNotConfigured`, or the provider error / `AllProvidersUnavailable` when no pool entry could answer.
    """

    contract = get_contract(capability_key)
    try:
        inp = contract.input_model(**raw_input) if isinstance(raw_input, dict) else contract.input_model.model_validate(raw_input)
    except (ValidationError, TypeError):
        raise RouterInputInvalid(f"The input does not satisfy the {contract.key!r} contract.") from None
    capability = contract.key
    _stats.count(capability, "requests")
    try:
        return _route_validated(contract, inp, deadline)
    finally:
        flush_rollup()


def _route_validated(contract: CapabilityContract, inp: Any, deadline: float | None) -> RouteResult:
    capability = contract.key
    try:
        config = load_config(capability)
    except AICapabilityError:
        _stats.count(capability, "not_available")
        raise
    policy = policy_from_v1(contract, config)

    if contract.deterministic is not None:
        found = contract.deterministic(inp)
        if found is not None:
            _stats.count(capability, "deterministic_hits")
            return RouteResult(output=found, source="deterministic")

    key = _cache_key(contract, contract.normalize(inp))
    held = _cache.get(key)
    if held is not None:
        _stats.count(capability, "cache_hits")
        return _cached(held)
    if _cache.is_unavailable(key):
        _stats.count(capability, "negative_hits")
        raise AllProvidersUnavailable("This request failed moments ago; not asked again yet.", [])

    total = _clock() + policy.max_total_latency_seconds
    limit = total if deadline is None else min(deadline, total)

    flight, leader = _cache.join(key)
    if not leader:
        _stats.count(capability, "coalesced")
        if not flight.done.wait(max(0.0, limit - _clock())):
            raise AllProvidersUnavailable("The request already in flight did not finish in time.", [])
        if flight.error is not None:
            raise flight.error
        return RouteResult(output=dict(flight.result.output), source="cache", provenance=flight.result.provenance)

    try:
        result = _ask_pool(contract, inp, policy, limit, key)
    except BaseException as exc:
        flight.set_error(exc)
        raise
    else:
        flight.set_result(result)
        return result
    finally:
        _cache.leave(key, flight)


def _ask_pool(contract: CapabilityContract, inp: Any, policy: Any, limit: float, key: str) -> RouteResult:
    capability = contract.key
    started = _clock()

    def check(data: dict[str, Any]) -> None:
        contract.validate(inp, data)

    try:
        answered = platform.generate_structured(
            messages=contract.build_messages(inp),
            schema=contract.output_schema,
            max_output_tokens=policy.max_output_tokens,
            temperature=policy.temperature,
            capability_key=capability,
            validate=check,
            deadline=limit,
            invalid_retries=policy.retry_invalid,
            attempt_timeout=policy.timeout_seconds,
            router_version=ROUTER_VERSION,
            capability_mode=True,
        )
    except AIProviderError as exc:
        attempts = list(getattr(exc, "attempts", ()))
        _stats.count(capability, "model_calls", getattr(exc, "router_calls", 0))
        _stats.count(capability, "failures")
        failed = [a for a in attempts if a.outcome == "failure"]
        for attempt in failed:
            if attempt.reason == "invalid_output":
                _stats.count(capability, "invalid_outputs")
        if getattr(exc, "reason", None) == "deadline":
            _stats.count(capability, "deadline_exceeded")
        if failed:
            _cache.mark_unavailable(key, NEGATIVE_SECONDS)  # nothing answered: do not ask again for about a minute
        raise
    except AICapabilityError:
        _stats.count(capability, "terminal_errors")
        raise

    output = contract.validate(inp, answered.data)
    router = answered.runtime.get("router", {})
    attempts = router.get("attempts", [])
    _stats.count(capability, "model_calls", router.get("calls", 1))
    if any(a.outcome == "failure" for a in attempts):
        _stats.count(capability, "fallbacks")
    for attempt in attempts:
        if attempt.reason == "invalid_output":
            _stats.count(capability, "invalid_outputs")
    telemetry = answered.runtime.get("telemetry", {})
    usage = telemetry.get("usage") or {}
    _stats.count(capability, "prompt_tokens", usage.get("prompt_tokens") or 0)
    _stats.count(capability, "completion_tokens", usage.get("completion_tokens") or 0)
    cost = ((telemetry.get("cost") or {}).get("amount")) or 0.0
    _stats.count(capability, "cost_usd", float(cost))
    _stats.count(capability, "latency_ms", int((_clock() - started) * 1000))
    _stats.model_answered(capability, answered.provider, answered.model)

    provenance = {
        "provider": answered.provider,
        "model": answered.model,
        "tier": provider_tier(answered.provider, answered.model),
        "prompt_version": contract.prompt_version,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _cache.put(key, {"output": output, "provenance": provenance}, contract.cache_ttl_seconds)
    return RouteResult(output=output, source="model", provenance=provenance)
