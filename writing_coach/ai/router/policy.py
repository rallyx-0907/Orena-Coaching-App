"""A routed capability's pool, read from the operator's stored configuration.

Slice 1 reads the v1 document (`CapabilityConfig`): the pool is `[primary, standby?]`. Config v2 (a longer pool) is a
later slice and arrives as another reader here, not as a change to the router.
"""

from __future__ import annotations

from dataclasses import dataclass

from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.router.contract import CapabilityContract


@dataclass(frozen=True)
class PoolEntry:
    provider: str
    model: str


@dataclass(frozen=True)
class Policy:
    pool: tuple[PoolEntry, ...]
    timeout_seconds: float
    max_total_latency_seconds: float
    max_output_tokens: int
    retry_invalid: int
    temperature: float


def policy_from_v1(contract: CapabilityContract, config: CapabilityConfig) -> Policy:
    pool = [PoolEntry(config.provider, config.model)]
    if config.backup_provider and config.backup_model:
        pool.append(PoolEntry(config.backup_provider, config.backup_model))
    return Policy(
        pool=tuple(pool),
        timeout_seconds=(
            float(config.timeout_seconds) if config.timeout_seconds is not None else contract.default_timeout_seconds
        ),
        max_total_latency_seconds=contract.max_total_latency_seconds,
        max_output_tokens=contract.max_output_tokens,
        retry_invalid=contract.retry_invalid,
        temperature=config.temperature if config.temperature is not None else contract.temperature,
    )
