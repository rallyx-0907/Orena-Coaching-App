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

    def list_feedback(self, *, user_key=None, limit=50, offset=0):
        rows = [row for row in reversed(self.rows) if user_key is None or row["user_key"] == user_key]
        return rows[offset:offset + limit]


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
