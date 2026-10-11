"""Test doubles for the operational policies (writing_coach/policies.py, D-172).

`MemoryPolicyStore` is an in-memory `platform_settings`: the same `get_setting` / `set_setting` contract as the
platform repository (compare-and-set on `expected_updated_at`, the audit row recorded with the write, a
`SettingConflict` on a stale version). `installed()` puts one in place for the length of a test and puts back what
was there, so a test never leaks a policy into another.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from writing_coach import policies
from writing_coach.persistence.platform_repository import SettingConflict


class MemoryPolicyStore:
    def __init__(self, values: dict[str, Any] | None = None, *, fail_reads: bool = False) -> None:
        self.rows: dict[str, dict] = {}
        self.audits: list[dict] = []
        self.fail_reads = fail_reads
        self.reads = 0
        self._tick = 0
        if values is not None:
            self.rows[policies.SETTING_KEY] = self._row({"version": policies.VERSION, "values": dict(values)}, "seed")

    def _row(self, value: dict, by: str) -> dict:
        self._tick += 1
        stamp = datetime(2026, 10, 11, 12, 0, self._tick % 60, tzinfo=UTC).isoformat()
        return {"value": value, "updated_at": stamp, "updated_by": by}

    def get_setting(self, key: str) -> dict | None:
        self.reads += 1
        if self.fail_reads:
            raise RuntimeError("settings store down")
        row = self.rows.get(key)
        return dict(row) if row else None

    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict:
        row = self.rows.get(key)
        if expected_updated_at is not ... and (row["updated_at"] if row else None) != expected_updated_at:
            raise SettingConflict(key)
        saved = self._row(value, updated_by)
        self.rows[key] = saved
        if audit is not None:
            self.audits.append(audit)
        return dict(saved)


@contextmanager
def installed(store: MemoryPolicyStore | None = None, *, env: dict[str, str] | None = None):
    """Policies read `store` (and `env`, an empty environment unless given) inside the block."""
    previous = (policies._store, policies._env)
    store = store if store is not None else MemoryPolicyStore()
    policies.configure(store, env={} if env is None else env)
    try:
        yield store
    finally:
        policies.configure(previous[0], env=previous[1])
