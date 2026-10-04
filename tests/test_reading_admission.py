"""Admission must be grounded in persisted source evidence and visible rights."""
from types import SimpleNamespace

import pytest

from writing_coach.reading_admission import automatic_admission


def decision(*, source_changes=None, snapshot_changes=None, target_changes=None, analysis=None):
    body = "Trees grow beside rivers. Students observe flowers. Families enjoy gardens."
    source = {"state": "active", "languages": ["en", "zh"], "name": "Owned",
              "base_url": "https://owned.example", "rights": {"automation_allowed": True, "can_republish": True}}
    snapshot = {"body": body, "language": "en", "rights": {"can_republish": True, "attribution_required": False}}
    source.update(source_changes or {})
    snapshot.update(snapshot_changes or {})
    targets = [SimpleNamespace(text=word, canonical_form=word, context=context, target_type="word")
               for word, context in [("Trees", "Trees grow beside rivers."),
                                     ("flowers", "Students observe flowers."),
                                     ("gardens", "Families enjoy gardens.")]]
    if target_changes:
        targets[0].__dict__.update(target_changes)
    return automatic_admission(source=source, snapshot=snapshot, language="en", body=body,
                               analysis=analysis if analysis is not None else {"quality_issues": []},
                               targets=targets, min_targets=3, max_targets=8)


def test_cleared_grounded_content_is_admitted():
    assert decision()["decision"] == "published"


@pytest.mark.parametrize("changes,reason", [
    ({"rights": {"can_republish": True, "attribution_required": True}}, "attribution_missing"),
    ({"rights": {"can_republish": True}}, "attribution_unknown"),
    ({"rights": {"can_republish": False}}, "rights_not_cleared"),
    ({"canonical_url": "https://other.example/article"}, "source_origin_mismatch"),
    ({"body": "Different revision"}, "source_snapshot_mismatch"),
    ({"language": "zh"}, "source_snapshot_mismatch"),
    ({"superseded_at": "2026-10-04"}, "source_superseded"),
])
def test_source_evidence_failures_hold_content(changes, reason):
    outcome = decision(snapshot_changes=changes)
    assert outcome["decision"] == "review"
    assert reason in outcome["reasons"]


@pytest.mark.parametrize("changes", [{"text": ""}, {"text": "invented"}, {"context": "Absent sentence"},
                                      {"canonical_form": "flowers"}, {"target_type": "unsupported"}])
def test_invalid_or_ungrounded_targets_never_auto_publish(changes):
    assert "targets_invalid" in decision(target_changes=changes)["reasons"]


def test_attribution_requires_visible_article_evidence_not_registry_name_or_url():
    assert "attribution_missing" in decision(snapshot_changes={
        "rights": {"can_republish": True, "attribution_required": True}})["reasons"]
    assert decision(snapshot_changes={"author": "QA author", "rights": {
        "can_republish": True, "attribution_required": True}})["decision"] == "published"


def test_missing_analysis_is_held():
    assert "analysis_missing" in decision(analysis={})["reasons"]


def test_url_cannot_borrow_a_blank_origin_manual_source_policy():
    outcome = decision(source_changes={"base_url": ""}, snapshot_changes={
        "metadata": {"input_kind": "url"}, "canonical_url": "https://unrelated.example/article"})
    assert outcome["decision"] == "review"
    assert "source_origin_mismatch" in outcome["reasons"]


@pytest.mark.parametrize("origin,url,admitted", [
    ("https://owned.example", "https://owned.example/a", True),
    ("https://owned.example:443", "https://owned.example/a", True),
    ("https://owned.example", "https://other.example/a", False),
    ("https://owned.example", "http://owned.example/a", False),
    ("https://owned.example", "https://owned.example:8443/a", False),
    ("https://[", "https://owned.example/a", False),
])
def test_fetched_url_is_bound_to_its_registered_origin(origin, url, admitted):
    outcome = decision(source_changes={"base_url": origin}, snapshot_changes={
        "metadata": {"input_kind": "url"}, "canonical_url": url})
    assert (outcome["decision"] == "published") is admitted
