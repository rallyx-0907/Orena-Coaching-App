

def test_content_states_put_every_kind_in_the_five_states_and_say_when_reading_is_unreadable():
    from writing_coach.admin_metrics import content_states

    reading = {"articles": {"published": 52, "needs_review": 3}, "review": {"rights": 1, "invalid": 2, "unscreened": 0},
               "jobs": {"queued": 1, "running": 1, "failed": 2, "completed": 56}, "sets": {"approved": 8, "draft": 1, "stale": 1}}
    records = [{"kind": "media", "status": "published"}, {"kind": "media", "status": "review"},
               {"kind": "media", "status": "processing"}, {"kind": "book", "status": "published"},
               {"kind": "vocabulary", "status": "draft"}]
    result = content_states(reading=reading, records=records, transcript_missing=1)
    assert result["kinds"]["reading"] == {"live": 52, "review": 1, "invalid": 2, "failed": 2, "processing": 2}
    assert result["kinds"]["comprehension"] == {"live": 8, "review": 1, "invalid": 1, "failed": 0, "processing": 0}
    assert result["kinds"]["media"] == {"live": 1, "review": 1, "invalid": 1, "failed": 0, "processing": 1}
    assert result["totals"]["live"] == 52 + 8 + 1 + 1
    unreadable = content_states(reading=None, records=records)
    assert unreadable["kinds"]["reading"] is None, "an unreadable owner is said as such, never zeros"


def test_failed_reading_jobs_need_attention():
    from writing_coach.admin_metrics import needs_attention

    items = needs_attention(capabilities=[], provider_state={}, operations={}, runtime_mode="legacy", reading_jobs_failed=2)
    assert {"kind": "reading_jobs_failed", "severity": "warning", "section": "reading", "count": 2} in items
