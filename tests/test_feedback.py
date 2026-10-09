"""D-156: learner feedback is stored and Platform Admin reads it."""

from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.feedback import DAILY_LIMIT, FeedbackInvalid, submit, summarize, validate_review


class Store:
    def __init__(self):
        self.rows = []

    def record_feedback(self, user_key, review):
        row = {"id": str(len(self.rows) + 1), "created_at": datetime.now(UTC), "user_key": user_key, **review,
               "account_id": "acc-" + user_key, "name": user_key.title(), "email": f"{user_key}@example.test"}
        self.rows.append(row)
        return row

    def count_feedback_since(self, user_key, since):
        return sum(1 for row in self.rows if row["user_key"] == user_key and row["created_at"] >= since)

    def _filtered(self, user_key=None, stars=0, area=""):
        return [row for row in reversed(self.rows) if (user_key is None or row["user_key"] == user_key)
                and (not stars or row["stars"] == stars) and (not area or area in row["areas"])]

    def list_feedback(self, *, user_key=None, stars=0, area="", limit=50, offset=0):
        return self._filtered(user_key, stars, area)[offset:offset + limit]

    def count_feedback(self, *, stars=0, area=""):
        return len(self._filtered(None, stars, area))

    def feedback_summary(self):
        return summarize(self.rows)


def test_a_review_is_validated_and_normalized():
    review = validate_review({"stars": 4, "areas": ["writing", "listening"], "text": "  Great  ", "interface": "vi"})
    assert review == {"stars": 4, "areas": ["listening", "writing"], "text": "Great", "language": "", "interface": "vi"}


@pytest.mark.parametrize("body, message", [
    ({"stars": 0}, "1 to 5"), ({"stars": 6}, "1 to 5"), ({"stars": True}, "1 to 5"), ({}, "1 to 5"),
    ({"stars": 3, "areas": ["design"]}, "Unknown area"), ({"stars": 3, "text": "x" * 601}, "longer"),
    ("nope", "object"),
])
def test_invalid_reviews_are_refused(body, message):
    with pytest.raises(FeedbackInvalid, match=message):
        validate_review(body)


def test_a_learner_has_a_daily_limit():
    store = Store()
    for _ in range(DAILY_LIMIT):
        submit(store, "ana", {"stars": 5})
    with pytest.raises(OverflowError):
        submit(store, "ana", {"stars": 5})
    assert submit(store, "ben", {"stars": 2}), "another learner is not limited by Ana's reviews"
    assert submit(store, "ana", {"stars": 5}, now=datetime.now(UTC) + timedelta(days=2))


def test_summary():
    rows = [{"stars": 5, "areas": ["writing"], "created_at": datetime.now(UTC)},
            {"stars": 3, "areas": ["writing", "bugs"], "created_at": datetime.now(UTC) - timedelta(days=30)}]
    summary = summarize(rows)
    assert summary["total"] == 2 and summary["average"] == 4.0
    assert summary["by_stars"]["5"] == 1 and summary["by_area"]["writing"] == 2
    assert summary["last_7_days"] == 1
    assert summarize([])["average"] is None


def test_routes(monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    import writing_coach.feedback_api as api

    store = Store()
    who = {"key": "ana"}
    monkeypatch.setattr(api, "_store", lambda: store)
    monkeypatch.setattr(api, "current_user_key", lambda request: who["key"])
    monkeypatch.setattr(api, "require_admin", lambda request: {"google_sub": "admin"})
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)

    sent = client.post("/api/feedback", json={"stars": 4, "areas": ["reading"], "text": "Nice"})
    assert sent.status_code == 201 and sent.json()["review"]["stars"] == 4
    assert "email" not in sent.json()["review"], "a learner's own read carries no account fields"
    assert client.post("/api/feedback", json={"stars": 9}).status_code == 422
    who["key"] = "ben"
    client.post("/api/feedback", json={"stars": 1, "areas": ["bugs"], "text": "Crash"})
    assert [item["text"] for item in client.get("/api/feedback/mine").json()["items"]] == ["Crash"], "only one's own reviews"

    admin = client.get("/api/admin/feedback").json()
    assert admin["summary"]["total"] == 2 and admin["summary"]["average"] == 2.5
    assert admin["items"][0]["email"] == "ben@example.test"
    assert "account_key" in admin["items"][0]
    assert client.get("/api/admin/feedback?stars=4").json()["total"] == 1
    assert client.get("/api/admin/feedback?area=bugs").json()["items"][0]["text"] == "Crash"
    assert client.get("/api/admin/feedback?area=design").status_code == 422

    def deny(request):
        raise HTTPException(403, "Platform administrator access required")

    monkeypatch.setattr(api, "require_admin", deny)
    assert client.get("/api/admin/feedback").status_code == 403


# --- Review of #113: the real SQL, over more than 5,000 reviews, and the retention policy (D-159) ---------------
def _sql_repository(tmp_path):
    import sqlalchemy as sa
    from writing_coach.persistence.models import AuditLog, Base, User
    from writing_coach.persistence.platform_repository import PostgresPlatformRepository

    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'feedback.db'}", future=True)
    Base.metadata.create_all(engine, tables=[User.__table__, AuditLog.__table__])
    return engine, PostgresPlatformRepository(engine=engine)


def _add_user(engine, key):
    import uuid
    from sqlalchemy.orm import Session
    from writing_coach.persistence.models import User

    with Session(engine) as session, session.begin():
        user = User(id=uuid.uuid4(), user_key=key, email=f"{key}@example.test", name=key, picture="", role="user",
                    created_at=datetime.now(UTC), last_login=None)
        session.add(user)
        return user.id


def test_admin_totals_are_over_every_review_not_a_truncated_page(tmp_path):
    import uuid
    from sqlalchemy.orm import Session
    from writing_coach.persistence.models import AuditLog

    engine, repo = _sql_repository(tmp_path)
    old = datetime.now(UTC) - timedelta(days=30)
    with Session(engine) as session, session.begin():
        for i in range(5005):
            session.add(AuditLog(id=uuid.uuid4(), user_id=None, action="learner.feedback", entity_type="feedback",
                                 entity_id=str(i), created_at=old if i < 5000 else datetime.now(UTC),
                                 payload={"stars": 5 if i % 5 == 0 else 3, "areas": ["reading", "bugs"] if i % 2 else ["listening"],
                                          "text": f"r{i}", "account": f"local-{i % 7}"}))
    summary = repo.feedback_summary()
    assert summary["total"] == 5005, "every stored review counts, past 5,000"
    assert summary["by_stars"]["5"] == 1001 and summary["by_stars"]["3"] == 4004
    assert summary["average"] == round((1001 * 5 + 4004 * 3) / 5005, 2)
    assert summary["by_area"]["reading"] == 2502 and summary["by_area"]["listening"] == 2503 and summary["by_area"]["bugs"] == 2502
    assert summary["last_7_days"] == 5
    assert repo.count_feedback(stars=5) == 1001
    assert repo.count_feedback(area="listening") == 2503
    assert repo.count_feedback(stars=5, area="listening") == 501
    page = repo.list_feedback(area="bugs", limit=25, offset=2475)
    assert len(page) == 25 and all("bugs" in row["areas"] for row in page)
    assert len(repo.list_feedback(area="bugs", limit=25, offset=2500)) == 2, "the last page of the filtered set"


def test_retention_deletes_an_accounts_reviews_and_reviews_past_24_months(tmp_path):
    from sqlalchemy.orm import Session
    from writing_coach.persistence.models import AuditLog, User

    engine, repo = _sql_repository(tmp_path)
    ana = _add_user(engine, "ana")
    _add_user(engine, "ben")
    repo.record_feedback("ana", {"stars": 4, "areas": [], "text": "a"})
    repo.record_feedback("ben", {"stars": 2, "areas": [], "text": "b"})
    repo.record_feedback("local-development", {"stars": 5, "areas": [], "text": "local"})
    assert repo.delete_feedback_for_account("ana") == 1
    assert [row["text"] for row in repo.list_feedback(limit=10)] == ["local", "b"]

    # A review older than 24 months goes; an account row deleted after its review leaves an orphan, which goes too.
    with Session(engine) as session, session.begin():
        log = session.query(AuditLog).filter(AuditLog.payload["text"].as_string() == "local").one()
        log.created_at = datetime.now(UTC) - timedelta(days=731)
        session.query(AuditLog).filter(AuditLog.payload["text"].as_string() == "b").update({AuditLog.user_id: None})
    repo.record_feedback("local-other", {"stars": 3, "areas": [], "text": "keep"})
    removed = repo.delete_feedback_before(datetime.now(UTC) - timedelta(days=730), limit=100)
    assert removed == 2
    assert [row["text"] for row in repo.list_feedback(limit=10)] == ["keep"]


def test_retention_switch_is_off_unless_turned_on():
    from writing_coach.feedback import FEEDBACK_RETENTION_DAYS, retention_enabled

    assert FEEDBACK_RETENTION_DAYS == 730
    assert retention_enabled({}) is False
    assert retention_enabled({"FEEDBACK_RETENTION_SWEEP": "on"}) is True
    with pytest.raises(ValueError):
        retention_enabled({"FEEDBACK_RETENTION_SWEEP": "maybe"})


def test_retention_is_a_periodic_job_independent_of_sends():
    import time

    from writing_coach.feedback_retention import FeedbackRetentionSchedule, sweep_once

    cutoffs = []

    def deleter(before, limit):
        cutoffs.append(before)
        return 0

    schedule = FeedbackRetentionSchedule(deleter, interval=0.05)
    schedule.start()
    deadline = time.monotonic() + 3
    while schedule.sweeps < 3 and time.monotonic() < deadline:
        time.sleep(0.02)
    schedule.stop()
    assert schedule.sweeps >= 3, "it sweeps on a clock, with no feedback sent"
    age = datetime.now(UTC) - cutoffs[0]
    assert timedelta(days=729) < age < timedelta(days=731), "the cutoff is 24 months"

    # A backlog goes in bounded batches; a failing sweep is retried at the next tick, never raised.
    batches = iter([1000, 1000, 7])
    assert sweep_once(lambda before, limit: next(batches)) == 2007

    def broken(before, limit):
        raise RuntimeError("db down")

    failing = FeedbackRetentionSchedule(broken)
    assert failing.tick() is None and failing.sweeps == 1


def test_the_app_starts_the_schedule_only_when_switched_on():
    source = open("app.py", encoding="utf-8").read()
    assert "_feedback_retention.start()" in source and "if _feedback_retention_enabled(os.environ):" in source
