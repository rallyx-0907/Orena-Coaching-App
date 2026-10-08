from __future__ import annotations

from writing_coach.job_contract import (
    Lease,
    cancellation_decision,
    job_commit_decision,
    lease_acquire_decision,
    reconciliation_decision,
    recovery_decision,
    reservation_outcome_decision,
    retry_decision,
    source_revision_decision,
)
from writing_coach.reference_backbone import (
    Evidence,
    Scope,
    growth_comparable,
    job_may_publish,
    projection_evidence,
)


def test_i5_worker_cannot_publish_for_a_different_scope_or_lease() -> None:
    owner = Scope("owner-a", "incarnation-1", "en")
    other = Scope("owner-b", "incarnation-1", "en")

    assert job_may_publish(owner, owner, "running", 3, 3, True)
    assert not job_may_publish(other, owner, "running", 3, 3, True)
    assert not job_may_publish(owner, owner, "running", 2, 3, True)


def test_i5_worker_must_not_publish_unknown_or_inactive_outcomes() -> None:
    scope = Scope("owner-a", "incarnation-1", "zh")

    assert not job_may_publish(scope, scope, "outcome_unknown", 1, 1, True)
    assert not job_may_publish(scope, scope, "running", 1, 1, False)


def test_i5_a_live_lease_is_exclusive_and_an_expired_one_is_recovery() -> None:
    live = Lease(2, "worker-a", False)

    assert lease_acquire_decision(state="queued", requester="worker-a") == "acquire"
    # The same holder asking twice must not run the work twice.
    assert lease_acquire_decision(state="queued", requester="worker-a", current_lease=live) == "already_held"
    assert lease_acquire_decision(state="queued", requester="worker-b", current_lease=live) == "busy"
    # A running job whose lease expired is a crashed worker, not a fresh job.
    assert lease_acquire_decision(
        state="running", requester="worker-b", current_lease=Lease(2, "worker-a", True)
    ) == "recover"
    assert lease_acquire_decision(state="outcome_unknown", requester="worker-b") == "reconcile_required"


def test_i5_a_source_revision_that_moved_under_the_job_cannot_publish() -> None:
    scope = Scope("owner-a", "incarnation-1", "en")
    common = dict(
        job_scope=scope, current_scope=scope, state="running",
        lease_generation=3, current_lease=3, account_active=True,
    )

    assert job_commit_decision(captured_source_revision="rev-1", current_source_revision="rev-1", **common) == "publish"
    assert job_commit_decision(
        captured_source_revision="rev-1", current_source_revision="rev-2", **common
    ) == "source_revision_changed"
    assert job_commit_decision(
        captured_source_revision="rev-1", current_source_revision=None, **common
    ) == "source_revision_unknown"
    assert source_revision_decision("", "rev-1") == "unknown"


def test_i5_cancellation_suppresses_publication_without_erasing_the_bill() -> None:
    scope = Scope("owner-a", "incarnation-1", "zh")

    assert cancellation_decision(state="running", dispatched=False) == "cancel_released"
    assert cancellation_decision(state="running", dispatched=True) == "cancel_retained"
    assert cancellation_decision(state="outcome_unknown", dispatched=True) == "reconcile_before_terminal"
    assert job_commit_decision(
        job_scope=scope, current_scope=scope, state="running", lease_generation=1, current_lease=1,
        account_active=True, cancelled=True, captured_source_revision="rev-1",
        current_source_revision="rev-1",
    ) == "cancelled"
    assert reservation_outcome_decision(dispatched=True, actual_units_known=True) == "settle"


def test_i5_unknown_outcome_reconciles_and_unknown_cost_is_retained() -> None:
    assert recovery_decision(
        state="running", dispatched=True, provider_handle_known=False, provider_queryable=False
    ) == "outcome_unknown"
    assert reconciliation_decision(
        state="outcome_unknown", provider_outcome="absent", handle_verified=True
    ) == "not_started"
    assert reconciliation_decision(
        state="outcome_unknown", provider_outcome="ok", handle_verified=True
    ) == "unknown"
    assert reservation_outcome_decision(dispatched=True, actual_units_known=False) == "retain_unknown_cost"
    assert reservation_outcome_decision(dispatched=False, actual_units_known=False) == "release"


def test_i5_failure_classes_decide_retry_and_a_timeout_reconciles() -> None:
    common = dict(attempts=1, max_attempts=3, deadline_remaining=True, budget_remaining=True)

    assert retry_decision(failure_class="rate_limited", **common) == "retry"
    assert retry_decision(failure_class="invalid_input", **common) == "permanent_failure"
    assert retry_decision(failure_class="timeout_after_dispatch", **common) == "reconcile"
    assert retry_decision(
        failure_class="transient", attempts=3, max_attempts=3,
        deadline_remaining=True, budget_remaining=True,
    ) == "permanent_failure"


def test_i6_projection_uses_latest_acknowledged_version_and_filters_invalidated() -> None:
    scope = Scope("owner-a", "incarnation-1", "en")
    rows = [
        Evidence(scope, "writing", "essay-1", 1, True),
        Evidence(scope, "writing", "essay-1", 2, True, invalidated=True),
        Evidence(scope, "reading", "session-1", 1, True),
    ]

    projected = projection_evidence(scope, rows)

    assert [(row.domain, row.id) for row in projected] == [("reading", "session-1")]


def test_i6_growth_requires_same_scope_and_complete_matching_metadata() -> None:
    scope = Scope("owner-a", "incarnation-1", "en")
    metric = ("writing", "evaluator-v1", "unaided", "message")

    assert growth_comparable(scope, scope, metric, metric)
    assert not growth_comparable(
        scope,
        Scope("owner-a", "incarnation-1", "zh"),
        metric,
        metric,
    )
    assert not growth_comparable(scope, scope, metric, ("writing", "", "unaided", "message"))
