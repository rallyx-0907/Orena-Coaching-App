"""Remove what a model provider must not receive (spec §36).

Service read models were written for the learner's own screen, where some
fields are fine: a writing observation's `producer` names the evaluator and
model that produced it (for example an internal model id). Sent to a different
provider as agent context, that leaks internal vendor identity, and personal
identifiers never belong in a prompt at all. Every tool result and snapshot
passes through `redact_for_provider` before it is put in a provider request.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

REDACTED_KEYS = frozenset(
    {
        # who or what produced an evaluation
        "producer",
        "provider",
        "provider_id",
        "model",
        "model_id",
        # who the learner is (a superset of the names a tool argument may not use)
        "user",
        "user_id",
        "uid",
        "learner",
        "learner_id",
        "owner",
        "account",
        "user_key",
        "user_sub",
        "account_id",
        "owner_id",
        "email",
        "display_name",
        "full_name",
        "given_name",
        "family_name",
        "picture",
        "avatar_url",
        "ip_address",
    }
)


def redact_for_provider(value: Any) -> Any:
    """A copy of `value` without redacted keys, at any depth."""

    if isinstance(value, Mapping):
        return {
            key: redact_for_provider(item)
            for key, item in value.items()
            if str(key).casefold() not in REDACTED_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [redact_for_provider(item) for item in value]
    return value
