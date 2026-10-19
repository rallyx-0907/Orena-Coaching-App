"""Retention sweeps for usage counts and administrators' audit records (PRE-502 R8; owner, 2026-10-19 16:26).

The owner set two periods, which the public Privacy Policy states:
- **Plan and usage counts:** `usage_events` and the quota ledgers (`commerce_quota_reservations`,
  `commerce_quota_buckets`) are kept 12 months (`USAGE_RETENTION_DAYS`).
- **Records of administrators' actions:** `audit_logs` rows `admin.*`, `product.*` and `platform.*` are kept 24 months
  (`ADMIN_AUDIT_RETENTION_DAYS`).

Billing and credit records are kept as accounting law requires and are never swept here.

Each sweep is deletion, so each is off until its switch is on (`USAGE_RETENTION_SWEEP`, `ADMIN_AUDIT_RETENTION_SWEEP`;
`agent.retention.sweep_enabled`: an unclear value refuses to start). They run on the same daily schedule as the
feedback sweep (`feedback_retention.FeedbackRetentionSchedule`), in bounded batches, idempotently. PostgreSQL only:
the archive backend has no such rows to keep.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

USAGE_RETENTION_DAYS = 365
ADMIN_AUDIT_RETENTION_DAYS = 730
USAGE_SWEEP_SWITCH = "USAGE_RETENTION_SWEEP"
ADMIN_AUDIT_SWEEP_SWITCH = "ADMIN_AUDIT_RETENTION_SWEEP"
ADMIN_ACTION_PATTERNS = ("admin.%", "product.%", "platform.%")  # who changed what; the learner's own rows have their own


def delete_usage_before(engine: Any, before: datetime, limit: int) -> int:
    """Up to `limit` usage rows of each kind older than `before`: usage events, then quota reservations, then quota
    buckets whose window began before it and that no reservation still references (RESTRICT). Returns how many."""
    n = max(1, int(limit))
    with engine.begin() as conn:
        events = conn.execute(text(
            "DELETE FROM usage_events WHERE id IN (SELECT id FROM usage_events WHERE occurred_at < :before"
            " ORDER BY occurred_at LIMIT :n FOR UPDATE SKIP LOCKED)"), {"before": before, "n": n}).rowcount  # fmt: skip
        reservations = conn.execute(text(
            "DELETE FROM commerce_quota_reservations WHERE id IN (SELECT id FROM commerce_quota_reservations"
            " WHERE created_at < :before ORDER BY created_at LIMIT :n FOR UPDATE SKIP LOCKED)"),
            {"before": before, "n": n}).rowcount  # fmt: skip
        buckets = conn.execute(text(
            "DELETE FROM commerce_quota_buckets WHERE id IN (SELECT b.id FROM commerce_quota_buckets b"
            " WHERE b.window_start < :before AND NOT EXISTS (SELECT 1 FROM commerce_quota_reservations r"
            " WHERE r.bucket_id = b.id) ORDER BY b.window_start LIMIT :n FOR UPDATE SKIP LOCKED)"),
            {"before": before, "n": n}).rowcount  # fmt: skip
    return int(events or 0) + int(reservations or 0) + int(buckets or 0)


def delete_admin_audit_before(engine: Any, before: datetime, limit: int) -> int:
    """Up to `limit` administrator-action audit rows older than `before`. Returns how many."""
    likes = " OR ".join(f"action LIKE :p{i}" for i in range(len(ADMIN_ACTION_PATTERNS)))
    with engine.begin() as conn:
        gone = conn.execute(text(
            f"DELETE FROM audit_logs WHERE id IN (SELECT id FROM audit_logs WHERE created_at < :before AND ({likes})"
            " ORDER BY created_at LIMIT :n FOR UPDATE SKIP LOCKED)"),
            {"before": before, "n": max(1, int(limit)),
             **{f"p{i}": p for i, p in enumerate(ADMIN_ACTION_PATTERNS)}}).rowcount  # fmt: skip
    return int(gone or 0)
