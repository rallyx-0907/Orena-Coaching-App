from __future__ import annotations

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
