"""Deleting one learner's Orena Memory on request (the PRE-005 email channel; owner, D-226: one Settings switch and no
notes list in the learner UI). Admin only: `DELETE /api/admin/accounts/{user_id}/memory` removes every memory item and
session summary of that account's active incarnation, says how many, and never returns a note's text. It is audited,
and the audit is required: no record, no deletion."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from writing_coach.agent.memory_keys import MemoryKeys
from writing_coach.agent.memory_runtime import MemoryRuntime, account_id
from writing_coach.agent.memory_store import InMemoryMemoryStore, MemoryScope

T0 = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LEARNER = account_id("learner-1")


class Incarnations:
    def resolve(self, account):
        return "inc-1" if account == LEARNER else None

    def ensure_active(self, account):
        return self.resolve(account)


@pytest.fixture()
def rig(monkeypatch):
    import app as app_module
    from writing_coach import admin_console_api
    from writing_coach.agent import api as agent_api

    store = InMemoryMemoryStore(MemoryKeys.parse("v1:" + "k" * 40))
    store.add_explicit(MemoryScope(LEARNER, "inc-1"), language="en", kind="goal", text="Phỏng vấn xin việc", slot=None,
                       source="learner_asked", now=T0)  # fmt: skip
    previous = agent_api.current_memory()
    agent_api.configure_memory(MemoryRuntime(store=store, incarnations=Incarnations()))
    audits = []
    monkeypatch.setattr(app_module, "require_admin", lambda request: {"google_sub": "admin-1", "role": "admin"})
    monkeypatch.setattr(admin_console_api, "_audit",
                        lambda admin, action, **kw: audits.append((action, kw)))  # fmt: skip
    yield TestClient(app_module.app), store, audits, app_module
    agent_api.configure_memory(previous)


def test_an_admin_erases_one_learners_memory_and_learns_only_how_much(rig):
    client, store, audits, _ = rig
    answer = client.delete(f"/api/admin/accounts/{LEARNER}/memory")
    assert answer.status_code == 200 and answer.json() == {"removed": 1}
    assert "Phỏng vấn" not in answer.text
    assert store.items(MemoryScope(LEARNER, "inc-1"), "en", T0) == []
    actions = [action for action, _ in audits]
    assert actions == ["admin.memory_erase_requested", "admin.memory_erased"]
    assert audits[1][1]["payload"] == {"removed": 1} and audits[1][1]["entity_id"] == LEARNER


def test_an_account_without_memory_is_404_and_nothing_is_erased(rig):
    client, _store, audits, _ = rig
    assert client.delete(f"/api/admin/accounts/{account_id('nobody')}/memory").status_code == 404


def test_no_audit_no_erase(rig, monkeypatch):
    client, store, _audits, _ = rig
    from writing_coach import admin_console_api

    def refuse(admin, action, **kw):
        raise HTTPException(503, "admin_audit_unavailable")

    monkeypatch.setattr(admin_console_api, "_audit", refuse)
    assert client.delete(f"/api/admin/accounts/{LEARNER}/memory").status_code == 503
    assert [i.text for i in store.items(MemoryScope(LEARNER, "inc-1"), "en", T0)] == ["Phỏng vấn xin việc"]


def test_a_learner_cannot_erase_anyone(rig, monkeypatch):
    client, store, _audits, app_module = rig

    def refuse(request):
        raise HTTPException(403, "admin_required")

    monkeypatch.setattr(app_module, "require_admin", refuse)
    assert client.delete(f"/api/admin/accounts/{LEARNER}/memory").status_code == 403
    assert store.items(MemoryScope(LEARNER, "inc-1"), "en", T0)
