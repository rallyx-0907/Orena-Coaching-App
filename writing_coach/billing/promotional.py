"""Promotional allowance grants: the contract only (PR-MON-6 §4, §11; H-8 OFF - no grant is configured).

A grant definition is configuration (`BILLING_PROMOTIONAL_GRANTS_FILE`; none by default): an id, the units per meter,
and how many days a claim lasts. A claim is per person, ever: `promotional_grants` is unique on `(grant_id, users.id)`,
and the `users` row survives delete-and-re-register (the incarnation barrier), so a deleted and re-registered account
cannot claim the same grant again (R-MON-003). Its usage is 0007's quota bucket, one per meter, over the claim's window
`promo:<claim>` - reserved and settled exactly like the plan's. Funding spends promotional buckets before the plan's,
earliest expiry first.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

_GRANT_ID = re.compile(r"^[a-z0-9_-]{1,40}$")


@dataclass(frozen=True)
class GrantDefinition:
    grant_id: str
    meters: dict[str, int] = field(default_factory=dict)
    valid_days: int = 0
    policy_version: str = ""


def load_grant_definitions(env: Mapping[str, str]) -> dict[str, GrantDefinition]:
    """No file, no grants (H-8)."""
    path = str(env.get("BILLING_PROMOTIONAL_GRANTS_FILE", "")).strip()
    if not path:
        return {}
    grants: dict[str, GrantDefinition] = {}
    for item in json.loads(Path(path).read_text(encoding="utf-8")):
        grant = GrantDefinition(grant_id=str(item["grant_id"]), meters=dict(item["meters"]),
                                valid_days=item["valid_days"], policy_version=str(item["policy_version"])[:40])
        if not _GRANT_ID.match(grant.grant_id) or grant.grant_id in grants:
            raise ValueError("a grant id is unique, lower-case letters, digits, '-' or '_' (at most 40)")
        if type(grant.valid_days) is not int or grant.valid_days < 1 or not grant.meters or not grant.policy_version:
            raise ValueError("a grant lasts at least one day, names at least one meter and its policy version")
        for meter, units in grant.meters.items():
            if type(units) is not int or units < 1:
                raise ValueError(f"grant {grant.grant_id}: {meter} needs a positive integer of units")
        grants[grant.grant_id] = grant
    return grants


def claim(engine: Any, definition: GrantDefinition, *, user_id: str, incarnation_id: str,
          now: datetime | None = None) -> str | None:
    """Claim `definition` for this person, once ever, with one bucket per meter in the same transaction. Returns the
    claim id; when this person already claimed the grant (under this or an earlier incarnation), the first claim's id,
    with nothing new written - never a second claim, never more units."""
    claimed_at = (now or datetime.now(UTC)).replace(microsecond=0)
    expires_at = claimed_at + timedelta(days=definition.valid_days)
    claim_id = uuid.uuid4()
    with engine.begin() as connection:
        inserted = connection.execute(text(
            "INSERT INTO promotional_grants (id, grant_id, user_id, incarnation_id, policy_version, claimed_at, "
            "expires_at) VALUES (:id, :grant, :user, :inc, :policy, :claimed, :expires) "
            "ON CONFLICT (grant_id, user_id) DO NOTHING RETURNING id"),
            {"id": claim_id, "grant": definition.grant_id, "user": user_id, "inc": incarnation_id,
             "policy": definition.policy_version, "claimed": claimed_at, "expires": expires_at}).scalar()  # fmt: skip
        if inserted is None:
            existing = connection.execute(text(
                "SELECT id FROM promotional_grants WHERE grant_id = :grant AND user_id = :user"),
                {"grant": definition.grant_id, "user": user_id}).scalar()  # fmt: skip
            return str(existing) if existing is not None else None
        for meter, units in sorted(definition.meters.items()):
            connection.execute(text(
                "INSERT INTO commerce_quota_buckets (id, incarnation_id, meter, window_id, window_start, window_end, "
                "policy_version, unit_limit, consumed, reserved, created_at, updated_at, promotional_grant_id) VALUES "
                "(:id, :inc, :meter, :window, :start, :end, :policy, :limit, 0, 0, :now, :now, :grant)"),
                {"id": uuid.uuid4(), "inc": incarnation_id, "meter": meter, "window": f"promo:{claim_id}",
                 "start": claimed_at, "end": expires_at, "policy": f"grant:{definition.grant_id}:{definition.policy_version}"[:40],
                 "limit": units, "now": claimed_at, "grant": claim_id})  # fmt: skip
    return str(claim_id)


def remaining(engine: Any, incarnation_id: str, meter: str) -> list[dict[str, Any]]:
    """This account's open promotional allowance for `meter`, earliest expiry first (the order funding spends it)."""
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT g.grant_id, b.unit_limit - b.consumed - b.reserved AS remaining, b.window_end AS expires_at "
            "FROM commerce_quota_buckets b JOIN promotional_grants g ON g.id = b.promotional_grant_id "
            "WHERE b.incarnation_id = :inc AND b.meter = :meter AND b.window_start <= now() AND now() < b.window_end "
            "ORDER BY b.window_end, b.window_id"), {"inc": incarnation_id, "meter": meter}).mappings().all()  # fmt: skip
    return [dict(row) for row in rows]
