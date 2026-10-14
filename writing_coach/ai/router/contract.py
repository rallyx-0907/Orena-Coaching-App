"""A routed capability's contract: what it accepts, how it asks, what counts as a valid answer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from writing_coach.ai.base import AIOutputInvalid
from writing_coach.ai.capabilities import require_capability

InvalidOutput = AIOutputInvalid


class RouterInputInvalid(ValueError):
    """The request does not satisfy the contract's input model. Raised before any provider is asked."""


@dataclass(frozen=True)
class CapabilityContract:
    key: str
    contract_version: str
    prompt_version: str
    input_model: type[BaseModel]
    output_schema: dict[str, Any]
    # The canonical, model-free material the cache key is made of.
    normalize: Callable[[Any], dict[str, Any]]
    # The input travels as JSON data in the user role; it is never spliced into the instructions.
    build_messages: Callable[[Any], list[dict[str, str]]]
    # Semantic checks on top of the schema; returns the cleaned output or raises `InvalidOutput`.
    validate: Callable[[Any, dict[str, Any]], dict[str, Any]]
    sample_input: dict[str, Any]
    cache_ttl_seconds: float
    default_timeout_seconds: float = 2.5
    max_total_latency_seconds: float = 4.0
    max_output_tokens: int = 120
    retry_invalid: int = 1
    temperature: float = 0.0
    # An optional tier 0 that answers without a provider; None when the capability has none.
    deterministic: Callable[[Any], dict[str, Any] | None] | None = None

    @property
    def input_class(self) -> str:
        """Single source: the catalogue definition (D-006)."""

        return require_capability(self.key).input_class


_REGISTRY: dict[str, CapabilityContract] = {}


def register(contract: CapabilityContract) -> CapabilityContract:
    _REGISTRY[contract.key] = contract
    return contract


def get_contract(key: str) -> CapabilityContract:
    from writing_coach.ai.router import contracts  # noqa: F401  (registers the shipped contracts)

    try:
        return _REGISTRY[key]
    except KeyError:
        from writing_coach.ai.base import AICapabilityUnsupported

        raise AICapabilityUnsupported(f"AI capability {key!r} is not routed.") from None
