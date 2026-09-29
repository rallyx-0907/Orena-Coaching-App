"""N-36 point 1 (docs/project/UI_BACKEND_GAPS.md): Progress's Evidence rows draw a
short excerpt of each essay next to its score, but `GET /api/essays` (the list
route) used to drop `text` entirely - `app.py` `row_to_dict()`'s non-detail
branch popped it with nothing put in its place, so the row carried a title
only. These tests hold the fix: the list item now carries a short, bounded
`excerpt` derived from the stored text at serialization time - never the full
text, and the detail route (which already carries the full `text`) is
unchanged.

Before the fix, `test_list_item_carries_a_bounded_excerpt` and
`test_excerpt_is_never_the_full_text` both failed: `rows[0]["excerpt"]` raised
`KeyError`, because no such key existed on a list row.
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402

SHORT_TEXT = "Hi Anna, I want to tell you about my last week."

# Long enough to exceed ESSAY_LIST_EXCERPT_MAX_CHARS on its own, with irregular
# whitespace (a blank line, a tab, doubled spaces) so the excerpt's whitespace
# normalisation is also exercised.
LONG_TEXT = (
    "Hi Anna,\n\nI want to  tell you about my last week.\tI go to the Da Nang "
    "office for a meeting with a customer and I dont finished the report. "
    "The meeting was long and the customer had many question about our "
    "product, so we talked for almost two hours before we agree on the next "
    "step and I promise to send the report tomorrow morning without fail."
)

# A Vietnamese sentence (precomposed diacritics) and a Chinese sentence, each
# repeated past ESSAY_LIST_EXCERPT_MAX_CHARS, so the cut point lands inside a
# run of non-ASCII characters rather than at a convenient ASCII boundary.
VIETNAMESE_TEXT = "Tuần trước tôi đã đi làm và gặp khách hàng ở Đà Nẵng. " * 6
CHINESE_TEXT = "这是我上周写的一篇关于学习中文的短文，内容很长。" * 8


def _review_payload(index: int) -> dict[str, Any]:
    return {
        "grammar": 50.0,
        "vocabulary": 55.0,
        "coherence": 60.0,
        "task_achievement": 58.0,
        "naturalness": 52.0,
        "cefr_estimate": "B1",
        "summary_vi": f"Review #{index}",
        "strengths_vi": ["Clear enough."],
        "strength_evidence": [],
        "priorities_vi": ["Watch the past tense."],
        "errors": [],
        "schema_version": "writing-evaluation-v2",
    }


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    test_client = TestClient(app_module.app)
    test_client.__enter__()

    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)

    calls: list[str] = []

    def _evaluator(payload: Any) -> dict[str, Any]:
        calls.append(payload.text)
        return _review_payload(len(calls))

    monkeypatch.setattr(app_module, "evaluate_with_ai", _evaluator)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", False)
    monkeypatch.setattr(
        app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"}
    )
    app_module._review_in_flight.clear()
    try:
        yield test_client
    finally:
        test_client.__exit__(None, None, None)


def _write(client: TestClient, text: str) -> int:
    response = client.post(
        "/api/evaluate",
        json={"prompt": "Email to a colleague", "text": text, "learning_language": "en"},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


# --- The list item carries an excerpt -----------------------------------


def test_list_item_carries_a_bounded_excerpt(client: TestClient) -> None:
    _write(client, LONG_TEXT)
    rows = client.get("/api/essays").json()
    assert len(rows) == 1
    excerpt = rows[0]["excerpt"]
    assert isinstance(excerpt, str) and excerpt
    assert len(excerpt) <= app_module.ESSAY_LIST_EXCERPT_MAX_CHARS + 1  # +1 for the ellipsis


def test_excerpt_is_never_the_full_text(client: TestClient) -> None:
    _write(client, LONG_TEXT)
    rows = client.get("/api/essays").json()
    assert rows[0]["excerpt"] != LONG_TEXT
    assert "text" not in rows[0]


def test_short_essay_excerpt_is_not_truncated(client: TestClient) -> None:
    _write(client, SHORT_TEXT)
    rows = client.get("/api/essays").json()
    assert rows[0]["excerpt"] == SHORT_TEXT
    assert "…" not in rows[0]["excerpt"]


def test_excerpt_ellipsis_appears_only_when_cut(client: TestClient) -> None:
    _write(client, LONG_TEXT)
    rows = client.get("/api/essays").json()
    assert rows[0]["excerpt"].endswith("…")


def test_excerpt_normalises_whitespace(client: TestClient) -> None:
    _write(client, LONG_TEXT)
    rows = client.get("/api/essays").json()
    excerpt = rows[0]["excerpt"]
    assert "\n" not in excerpt
    assert "\t" not in excerpt
    assert "  " not in excerpt


def test_excerpt_cuts_on_a_character_boundary_for_vietnamese(client: TestClient) -> None:
    _write(client, VIETNAMESE_TEXT)
    rows = client.get("/api/essays").json()
    excerpt = rows[0]["excerpt"]
    # A mis-cut combining/precomposed character would not round-trip through
    # encode/decode identically; a clean code-point boundary always does.
    assert excerpt.encode("utf-8").decode("utf-8") == excerpt
    assert excerpt.endswith("…")
    assert len(excerpt) <= app_module.ESSAY_LIST_EXCERPT_MAX_CHARS + 1


def test_excerpt_cuts_on_a_character_boundary_for_chinese(client: TestClient) -> None:
    _write(client, CHINESE_TEXT)
    rows = client.get("/api/essays").json()
    excerpt = rows[0]["excerpt"]
    assert excerpt.encode("utf-8").decode("utf-8") == excerpt
    assert excerpt.endswith("…")
    assert len(excerpt) <= app_module.ESSAY_LIST_EXCERPT_MAX_CHARS + 1


# --- The detail route is unchanged ---------------------------------------


def test_detail_route_still_carries_the_full_text(client: TestClient) -> None:
    essay_id = _write(client, LONG_TEXT)
    detail = client.get(f"/api/essays/{essay_id}").json()
    assert detail["text"] == LONG_TEXT
    assert "excerpt" not in detail
