"""PR-MON-6 through the quota gate, hermetic (CI, SQLite): feature access before bypass, the funding ticket, and the
§9 refusal. The funding service is a test double of `FundingService`'s protocol; its PostgreSQL behaviour is proved in
`tests/test_funding_postgres.py`."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402

from writing_coach.billing import funding_context as fc  # noqa: E402
from writing_coach.persistence.funding_repository import AdmissionOutcome, Refusal  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store  # noqa: E402
from tests.test_quota_gate import MemorySettings, _isolated, enforced_runtime, rooms  # noqa: E402,F401

TEXT = ("Hi Anna, I want to telling you about my last week. I go to the Da Nang office for a meeting with a "
        "customer and I dont finished the report.")


class FakeFunding:
    """The service protocol the gate uses: admit, dispatch, settle, release, repository.get, offers_available."""

    def __init__(self, outcome=None, *, offers=False):
        self.outcome, self.offers, self.calls, self.intents = outcome, offers, [], []
        self.repository = self

    def admit(self, intent, *, plan, policy_label=""):
        self.intents.append(intent)
        if self.outcome is not None:
            return self.outcome
        return AdmissionOutcome("funded", row={"units": intent.units, "source": "allowance",
                                                "operation_id": intent.operation_id})

    def get(self, operation_id):
        return None

    def dispatch(self, operation_id, ref="dispatch"):
        self.calls.append(("dispatch", operation_id))
        return "dispatched"

    def settle(self, operation_id, actual, outcome_ref=None):
        self.calls.append(("settle", operation_id, actual))
        return "settled"

    def release(self, operation_id, reason=""):
        self.calls.append(("release", operation_id))
        return "released"

    def offers_available(self, meter):
        return self.offers


@pytest.fixture(autouse=True)
def _no_funding():
    yield
    quota.configure_funding(None)


def _disable_review_on_free():
    stored = {"version": 2, "plans": [
        {"id": plan_id, "prices": {}, "entitlements": [{"key": "writing.review", "enabled": plan_id != "free", "limit": 2}]}
        for plan_id in ("free", "plus", "pro")]}
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {"value": stored, "updated_at": "t"}}))


def _evaluate(client):
    return client.post("/api/evaluate", json={"prompt": "Email", "text": TEXT, "learning_language": "en"})


# ---- P1-1: feature access first -------------------------------------------------------------------------------------

def test_a_disabled_meter_with_a_stored_review_is_403_and_the_cache_never_answers(rooms):  # noqa: F811
    client, calls, _app = rooms
    enforced_runtime()
    assert _evaluate(client).status_code == 200            # stored now
    _disable_review_on_free()
    refused = _evaluate(client)                            # the cache would answer: access is checked first
    assert refused.status_code == 403 and refused.json()["detail"]["category"] == "feature_not_in_plan"
    assert calls == ["evaluate"]


def test_an_enabled_meter_with_a_stored_review_is_served_and_consumes_no_funding(rooms):  # noqa: F811
    client, calls, _app = rooms
    repository = enforced_runtime()
    funding = FakeFunding()
    quota.configure_funding(funding)
    assert _evaluate(client).status_code == 200
    assert len(funding.intents) == 1
    reused = _evaluate(client)
    assert reused.status_code == 200 and reused.json()["reused"] is True
    assert len(funding.intents) == 1 and calls == ["evaluate"]   # no second admission, no provider call
    assert "reserve" not in repository.calls                   # funding admitted it, not the bare bucket


def test_require_feature_is_a_no_op_while_the_meter_is_not_enforced_and_403_when_disabled():
    _disable_review_on_free()
    quota.require_feature("writing.review")                  # not enforced: no behaviour change
    enforced_runtime()
    with pytest.raises(HTTPException) as refused:
        quota.require_feature("writing.review")
    assert refused.value.status_code == 403 and refused.value.detail["category"] == "feature_not_in_plan"


def test_credits_never_unlock_a_disabled_feature():
    _disable_review_on_free()
    enforced_runtime()
    funding = FakeFunding()                                  # would fund anything it is asked
    quota.configure_funding(funding)
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pass
    assert refused.value.status_code == 403 and funding.intents == []


# ---- the funding ticket ------------------------------------------------------------------------------------------

def test_a_funded_admission_carries_its_context_and_closes_through_funding():
    enforced_runtime()
    funding = FakeFunding()
    quota.configure_funding(funding)
    with quota.admit("writing.review", request_digest="x") as ticket:
        assert isinstance(ticket, quota.FundingTicket)
        context = fc.current()
        assert context.operation_id == ticket.operation_id and context.meter == "writing.review"
        assert context.admission_digest == funding.intents[0].request_digest
        ticket.dispatch("p")
    assert fc.current() is None
    assert funding.calls == [("dispatch", ticket.operation_id), ("settle", ticket.operation_id, 1)]


def test_an_exception_releases_an_undispatched_funded_operation():
    enforced_runtime()
    funding = FakeFunding()
    quota.configure_funding(funding)
    with pytest.raises(RuntimeError):
        with quota.admit("writing.review", request_digest="x") as ticket:
            raise RuntimeError("provider down before dispatch")
    assert funding.calls == [("release", ticket.operation_id)]


# ---- refusals --------------------------------------------------------------------------------------------------------

def test_a_refusal_is_429_quota_exhausted_with_the_reason_and_the_options():
    enforced_runtime()
    refusal = Refusal("insufficient_credits", {"allowance": {"status": "exhausted", "limit": 2, "consumed": 2,
                                                             "reserved": 0},
                                               "credits": {"available": 3, "needed": 5, "price_per_unit": 5}})
    quota.configure_funding(FakeFunding(AdmissionOutcome("refused", refusal=refusal), offers=True))
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pass
    detail = refused.value.detail
    assert refused.value.status_code == 429 and detail["category"] == "quota_exhausted"
    context = detail["context"]
    assert context["reason"] == "insufficient_credits" and context["meter"] == "writing.review"
    assert context["credits"] == {"available": 3, "needed": 5, "price_per_unit": 5}
    assert context["allowance"]["remaining"] == 0 and context["allowance"]["limit"] == 2
    assert "buy_credits" in context["options"] and "upgrade" in context["options"]
    assert context["used"] == 2   # the existing envelope keys stay


@pytest.mark.parametrize(("status", "category"), [("operation_conflict", "operation_conflict"),
                                                  ("operation_completed", "operation_completed"),
                                                  ("operation_closed", "operation_closed")])
def test_a_decided_operation_answers_409(status, category):
    enforced_runtime()
    quota.configure_funding(FakeFunding(AdmissionOutcome(status)))
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pass
    assert refused.value.status_code == 409 and refused.value.detail["category"] == category


def test_without_funding_attached_the_gate_is_unchanged():
    repository = enforced_runtime()
    with quota.admit("writing.review", request_digest="x") as ticket:
        assert isinstance(ticket, quota.Ticket)
    assert "reserve" in repository.calls
