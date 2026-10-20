"""The weekly recurring-mistake report (Monetisation v2, MONETIZATION_V2_SPEC §3; from Orena Memory's evidence): what
the learner's own records show this week against the four weeks before - which mistakes keep coming back, which are
new, which have stopped - each with the learner's own words and its fix. Counts only; nothing estimated."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from writing_coach.agent import weekly_report as report

NOW = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)  # a Wednesday: this ISO week starts Monday 2026-10-19


def error(category, day, essay, fragment="he go", suggestion="he goes", rule="Ngôi thứ ba số ít thêm -s."):
    return {"category": category, "created_at": f"2026-{day}T10:00:00+00:00", "essay_id": essay,
            "fragment": fragment, "suggestion": suggestion, "mini_rule_vi": rule}  # fmt: skip


def attempt(day, *words):
    return {"created_at": f"2026-{day}T10:00:00+00:00",
            "evidence": {"pronunciation": {"words": [{"word": w, "error_type": "Mispronunciation"} for w in words]}}}


def build(writing=(), speaking=(), tz="UTC", interface="vi"):
    return report.weekly_report(writing=list(writing), speaking=list(speaking), now=NOW, tz=tz, interface=interface)


def test_the_week_is_the_iso_week_in_the_learners_time_zone():
    answer = build()
    assert (answer["week"], answer["week_start"], answer["compared_with_weeks"]) == ("2026-W43", "2026-10-19", 4)
    # 06:00 Monday in Ho Chi Minh is still Sunday 23:00 UTC: the learner's week, not the server's
    late = report.weekly_report(writing=[], speaking=[], now=datetime(2026, 10, 18, 23, 0, tzinfo=UTC),
                                tz="Asia/Ho_Chi_Minh", interface="vi")  # fmt: skip
    assert late["week_start"] == "2026-10-19"


def test_a_mistake_this_week_and_before_is_recurring_with_the_learners_own_words():
    answer = build([error("grammar", "10-08", 1), error("grammar", "10-14", 2),
                    error("grammar", "10-20", 3, fragment="she like", suggestion="she likes")])
    (item,) = answer["writing"]
    assert item["status"] == "recurring" and (item["this_week"], item["before"]) == (1, 2)
    assert item["example"] == {"fragment": "she like", "suggestion": "she likes", "rule": "Ngôi thứ ba số ít thêm -s."}
    assert item["category"] == "grammar" and item["label"]  # named in the interface language


def test_a_mistake_seen_only_this_week_twice_is_new():
    answer = build([error("vocabulary", "10-19", 3), error("vocabulary", "10-20", 4, fragment="make homework")])
    assert answer["writing"][0]["status"] == "new"


def test_a_mistake_that_stopped_this_week_is_improving():
    answer = build([error("spelling", "10-06", 1), error("spelling", "10-13", 2, fragment="becuase")])
    (item,) = answer["writing"]
    assert item["status"] == "improving" and item["this_week"] == 0 and item["example"]["fragment"] == "becuase"


def test_a_single_old_mistake_is_not_reported_and_older_than_five_weeks_is_out():
    answer = build([error("grammar", "10-13", 1), error("spelling", "09-01", 1), error("spelling", "09-02", 2)])
    assert answer["writing"] == []


def test_the_order_is_this_weeks_count_then_the_total():
    answer = build([error("a", "10-19", 1), error("a", "10-20", 2), error("b", "10-19", 1), error("b", "10-10", 3),
                    error("b", "10-11", 4)])
    assert [item["category"] for item in answer["writing"]] == ["a", "b"]


def test_speaking_words_flagged_again_and_again():
    # "think" was flagged five weeks ago: outside the four weeks compared, so once is not a pattern
    answer = build(speaking=[attempt("10-20", "three", "think"), attempt("10-12", "three"), attempt("09-10", "think")])
    assert answer["speaking"] == [{"word": "three", "this_week": 1, "before": 1, "status": "recurring"}]


def test_what_was_practised_this_week_is_counted():
    answer = build([error("grammar", "10-20", 7), error("spelling", "10-20", 7), error("grammar", "10-12", 5)],
                   [attempt("10-21", "three"), attempt("10-02", "x")])
    assert answer["practised"] == {"writing_reviews": 1, "speaking_attempts": 1}


def test_an_unreadable_source_is_unknown_never_no_mistakes():
    answer = report.weekly_report(writing=None, speaking=None, now=NOW, tz="UTC", interface="vi")
    assert answer["writing"] is None and answer["speaking"] is None and answer["practised"] is None


def test_an_unknown_time_zone_is_refused():
    with pytest.raises(ValueError):
        build(tz="Mars/Olympus")


# --- the route ----------------------------------------------------------------------------------------------------

from tests.test_agent_api import client  # noqa: E402,F401 - the agent router's test client fixture


@pytest.fixture()
def sources(monkeypatch):
    from tests.test_agent_api import enable
    from writing_coach.agent import api as agent_api
    from writing_coach.agent.memory_pack import PackBuilder, PackSources

    enable([])
    rows = {"writing": [error("grammar", "10-12", 1), error("grammar", "10-20", 2)], "speaking": []}
    agent_api._runtime.pack = PackBuilder(enabled=False, sources=PackSources(
        writing_events=lambda: rows["writing"], speaking_attempts=lambda limit: rows["speaking"]))
    return rows


def test_the_route_reports_the_learners_week(client, sources):  # noqa: F811
    answered = client.get("/api/agent/progress/weekly", params={"tz": "Asia/Ho_Chi_Minh", "interface": "vi"})
    assert answered.status_code == 200 and answered.headers["Cache-Control"] == "private, no-store"
    body = answered.json()
    assert body["time_zone"] == "Asia/Ho_Chi_Minh" and isinstance(body["writing"], list)


def test_the_route_takes_the_time_zone_header(client, sources):  # noqa: F811
    answered = client.get("/api/agent/progress/weekly", headers={"X-Orena-Timezone": "Asia/Shanghai"})
    assert answered.json()["time_zone"] == "Asia/Shanghai"


def test_an_unknown_time_zone_or_interface_is_422(client, sources):  # noqa: F811
    assert client.get("/api/agent/progress/weekly", params={"tz": "Mars/Olympus"}).status_code == 422
    assert client.get("/api/agent/progress/weekly", params={"interface": "xx"}).status_code == 422


def test_a_source_that_cannot_be_read_is_unknown(client, sources):  # noqa: F811
    from writing_coach.agent import api as agent_api
    from writing_coach.agent.memory_pack import PackBuilder, PackSources

    def broken():
        raise RuntimeError("database down")

    agent_api._runtime.pack = PackBuilder(enabled=False, sources=PackSources(writing_events=broken))
    body = client.get("/api/agent/progress/weekly").json()
    assert body["writing"] is None


def test_a_bad_time_zone_header_falls_back_to_utc(client, sources):  # noqa: F811
    answered = client.get("/api/agent/progress/weekly", headers={"X-Orena-Timezone": "Mars/Olympus"})
    assert answered.status_code == 200 and answered.json()["time_zone"] == "UTC"


def test_the_route_reports_statuses_and_counts(client, sources):  # noqa: F811
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    sources["writing"] = [{"category": "grammar", "created_at": (now - timedelta(weeks=w)).isoformat(), "essay_id": w,
                           "fragment": "he go", "suggestion": "he goes", "mini_rule_vi": "-s"} for w in (0, 1)]
    (item,) = client.get("/api/agent/progress/weekly").json()["writing"]
    assert (item["status"], item["this_week"], item["before"]) == ("recurring", 1, 1)
    assert item["example"]["fragment"] == "he go"


# --- the plan gate (MV2-6a): Plus and Pro; Free is told, before anything is read -----------------------------------


@pytest.fixture()
def plan(monkeypatch):
    from writing_coach.product import quota
    from writing_coach.product.catalog import FREE

    state = {"plan": FREE}
    monkeypatch.setattr(quota.runtime(), "plan_for", lambda user_key, strict=True: state["plan"])
    return state


def test_a_free_learner_is_told_the_report_is_not_in_their_plan(client, sources, plan):  # noqa: F811
    refused = client.get("/api/agent/progress/weekly")
    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert detail["category"] == "feature_not_in_plan" and detail["context"]["feature"] == "progress.weekly_report"


def test_plus_and_pro_get_the_report(client, sources, plan):  # noqa: F811
    from writing_coach.product.catalog import PLUS, PRO

    for paid in (PLUS, PRO):
        plan["plan"] = paid
        assert client.get("/api/agent/progress/weekly").status_code == 200


def test_an_unreadable_plan_fails_closed(client, sources, monkeypatch):  # noqa: F811
    from writing_coach.product import quota

    def broken(user_key, strict=True):
        raise RuntimeError("subscription store down")

    monkeypatch.setattr(quota.runtime(), "plan_for", broken)
    assert client.get("/api/agent/progress/weekly").status_code == 503
