"""Pure aggregation rules behind the Platform Admin control center.

Every number the console shows is computed here from stored facts, and every
number that cannot be computed truthfully says so instead of being guessed.
"""
from datetime import UTC, date, datetime, timedelta

from writing_coach import admin_metrics as metrics

NOW = datetime(2026, 9, 18, 15, 30, tzinfo=UTC)


def test_day_keys_end_today_oldest_first():
    keys = metrics.day_keys(3, now=NOW)
    assert keys == ["2026-09-16", "2026-09-17", "2026-09-18"]


def test_daily_series_zero_fills_days_without_rows_and_ignores_days_outside_the_window():
    series = metrics.daily_series({"2026-09-17": 4, "2026-08-01": 99}, 3, now=NOW)
    assert series == [
        {"date": "2026-09-16", "count": 0},
        {"date": "2026-09-17", "count": 4},
        {"date": "2026-09-18", "count": 0},
    ]


def test_mask_email_keeps_domain_and_two_leading_characters_only():
    assert metrics.mask_email("buinguyen@gmail.com") == "bu•••@gmail.com"
    assert metrics.mask_email("a@b.io") == "a•••@b.io"
    assert metrics.mask_email("") == ""
    assert metrics.mask_email("no-at-sign") == "no•••"


def test_learner_segments_split_active_learners_by_first_ever_activity():
    window_start = NOW - timedelta(days=7)
    first = {
        "old": NOW - timedelta(days=40),
        "fresh": NOW - timedelta(days=2),
        "idle": NOW - timedelta(days=90),
    }
    result = metrics.learner_segments(first, {"old", "fresh"}, window_start)
    assert result == {"active": 2, "new": 1, "returning": 1}


def test_retention_is_insufficient_below_the_minimum_sample_and_never_reports_a_rate():
    today = NOW.date()
    first = {f"u{i}": today - timedelta(days=10) for i in range(5)}
    days = {user: {first[user], first[user] + timedelta(days=1)} for user in first}
    windows = metrics.retention_windows(first, days, today=today, offsets=(1, 7))
    assert [w["days"] for w in windows] == [1, 7]
    assert windows[0]["eligible_learners"] == 5
    assert windows[0]["returned_learners"] == 5
    assert windows[0]["state"] == "insufficient"
    assert windows[0]["rate_percent"] is None


def test_retention_rate_is_reported_once_the_sample_is_large_enough():
    today = NOW.date()
    first = {f"u{i}": today - timedelta(days=20) for i in range(20)}
    days = {
        user: ({first[user], first[user] + timedelta(days=8)} if index < 5 else {first[user]})
        for index, user in enumerate(first)
    }
    seven = metrics.retention_windows(first, days, today=today, offsets=(7,), min_sample=20)[0]
    assert seven["eligible_learners"] == 20
    assert seven["returned_learners"] == 5
    assert seven["state"] == "ready"
    assert seven["rate_percent"] == 25.0


def test_retention_excludes_learners_who_have_not_had_the_full_window_yet():
    today = NOW.date()
    first = {"recent": today - timedelta(days=3), "older": today - timedelta(days=9)}
    days = {"recent": {first["recent"]}, "older": {first["older"], today}}
    seven = metrics.retention_windows(first, days, today=today, offsets=(7,), min_sample=1)[0]
    assert seven["eligible_learners"] == 1
    assert seven["returned_learners"] == 1


def test_retention_cohort_is_bounded_to_recent_first_activity():
    today = NOW.date()
    first = {"ancient": today - timedelta(days=400)}
    days = {"ancient": {first["ancient"], today}}
    one = metrics.retention_windows(first, days, today=today, offsets=(1,), cohort_days=90, min_sample=1)[0]
    assert one["eligible_learners"] == 0
    assert one["state"] == "insufficient"


def _capability(key, *, configured=True, enabled=True, provider="ollama"):
    return {
        "key": key,
        "implemented": True,
        "provider_backed": True,
        "configurable": True,
        "explicit_config_exists": configured,
        "config": {"enabled": enabled, "provider": provider} if configured else None,
    }


def test_attention_flags_an_enabled_route_whose_provider_is_not_configured():
    items = metrics.needs_attention(
        capabilities=[_capability("writing_evaluator", provider="groq")],
        provider_state={"groq": {"configured": False, "credential_unreadable": False}},
        operations={"available": True, "by_capability": []},
        runtime_mode="legacy",
    )
    assert items == [
        {"kind": "provider_unavailable", "severity": "critical", "section": "ai", "subject": "writing_evaluator", "provider": "groq"}
    ]


def test_attention_ignores_a_disabled_route_and_reports_degraded_health():
    items = metrics.needs_attention(
        capabilities=[_capability("writing_evaluator", enabled=False, provider="groq")],
        provider_state={"groq": {"configured": False, "credential_unreadable": False}},
        operations={"available": True, "by_capability": [{"capability": "learner_dictionary", "health_state": "degraded"}]},
        runtime_mode="legacy",
    )
    assert items == [
        {"kind": "capability_degraded", "severity": "warning", "section": "ai", "subject": "learner_dictionary"}
    ]


def test_attention_reports_provider_failure_from_recorded_operations():
    items = metrics.needs_attention(
        capabilities=[],
        provider_state={},
        operations={"available": True, "by_capability": [{"capability": "learner_translation", "health_state": "provider_failure"}]},
        runtime_mode="legacy",
    )
    assert items[0]["kind"] == "provider_failure"
    assert items[0]["severity"] == "critical"


def test_unconfigured_capabilities_matter_only_once_learners_route_through_them():
    capabilities = [_capability("writing_evaluator", configured=False)]
    legacy = metrics.needs_attention(capabilities=capabilities, provider_state={}, operations={}, runtime_mode="legacy")
    live = metrics.needs_attention(capabilities=capabilities, provider_state={}, operations={}, runtime_mode="capability")
    assert legacy == []
    assert live == [
        {"kind": "capability_not_configured", "severity": "critical", "section": "ai", "subject": "writing_evaluator"}
    ]


def test_attention_reports_a_legacy_route_that_silently_falls_back_to_the_local_default():
    fallback = metrics.needs_attention(
        capabilities=[], provider_state={"gemini": {"configured": False}}, operations={}, runtime_mode="legacy",
        legacy_route={"source": "saved", "provider": "gemini", "provider_configured": False},
    )
    assert fallback == [
        {"kind": "legacy_route_fallback", "severity": "warning", "section": "ai", "provider": "gemini"}
    ]
    healthy = metrics.needs_attention(
        capabilities=[], provider_state={}, operations={}, runtime_mode="legacy",
        legacy_route={"source": "saved", "provider": "ollama", "provider_configured": True},
    )
    assert healthy == []
    # Once learners route per capability, the legacy selection no longer decides anything.
    routed = metrics.needs_attention(
        capabilities=[], provider_state={}, operations={}, runtime_mode="capability",
        legacy_route={"source": "saved", "provider": "gemini", "provider_configured": False},
    )
    assert routed == []


def test_attention_counts_content_imports_and_runtime_problems_and_orders_by_severity():
    items = metrics.needs_attention(
        capabilities=[],
        provider_state={"gemini": {"configured": False, "credential_unreadable": True}},
        operations={},
        runtime_mode="legacy",
        import_failures=2,
        transcript_missing=3,
        content_waiting=1,
        runtime={
            "persistence_backend": "postgresql",
            "media_index_issue": "index_corrupt",
            "reading_library": "unavailable",
            "vocabulary": "ok",
            "account_backbone": "unavailable",
            "learner_impact_failures": 4,
        },
    )
    kinds = [(item["kind"], item["severity"]) for item in items]
    assert kinds == [
        ("account_backbone_unavailable", "critical"),
        ("media_index_unreadable", "critical"),
        ("credential_unreadable", "warning"),
        ("import_failed", "warning"),
        ("transcript_missing", "warning"),
        ("learner_impact_failures", "warning"),
        ("reading_library_unavailable", "warning"),
        ("content_waiting", "info"),
    ]
    counts = {item["kind"]: item.get("count") for item in items}
    assert counts["import_failed"] == 2
    assert counts["transcript_missing"] == 3
    assert counts["content_waiting"] == 1
    assert counts["learner_impact_failures"] == 4


def test_attention_treats_a_missing_media_index_as_normal_and_sqlite_as_critical():
    items = metrics.needs_attention(
        capabilities=[], provider_state={}, operations={}, runtime_mode="legacy",
        runtime={"persistence_backend": "sqlite", "media_index_issue": "index_missing"},
    )
    assert items == [
        {"kind": "persistence_not_authoritative", "severity": "critical", "section": "operations"}
    ]


def test_first_activity_days_and_active_days_are_derived_from_day_rows():
    rows = [
        ("u1", "2026-09-10"), ("u1", "2026-09-12"), ("u2", "2026-09-18"), ("u1", "2026-09-10"),
    ]
    first, active = metrics.activity_days(rows)
    assert first == {"u1": date(2026, 9, 10), "u2": date(2026, 9, 18)}
    assert active == {"u1": {date(2026, 9, 10), date(2026, 9, 12)}, "u2": {date(2026, 9, 18)}}
