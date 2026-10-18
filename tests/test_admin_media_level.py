"""An administrator can set or clear the reviewed level of a shared-library media item."""
from dataclasses import replace

from sqlalchemy.orm import Session

from tests.test_admin_console_routes import call, setup  # noqa: F401,F811 -`setup` is a fixture
from writing_coach.listening_api import stored_media_metadata
from writing_coach.persistence.models import AuditLog

MEDIA_ID = "youtube-abcdefghijk"
PATH = f"/api/admin/console/content/media/{MEDIA_ID}/level"


def _post(setup, level, **kwargs):  # noqa: F811
    return call(setup["app"], "POST", PATH, json={"level": level}, **kwargs)


def _make_english(setup):  # noqa: F811
    entry = setup["store"].get(MEDIA_ID)
    setup["store"].upsert(replace(entry, language="en"))


def test_english_level_is_set_and_shown_to_learners(setup):  # noqa: F811
    _make_english(setup)
    before = setup["store"].get(MEDIA_ID)
    result = _post(setup, "b1")
    assert result.status_code == 200
    assert result.json()["record"]["level"] == "B1"
    after = setup["store"].get(MEDIA_ID)
    assert after.level == "B1"
    assert stored_media_metadata(after)["reviewed_level"] == "B1"
    assert (after.status, after.source, after.lesson, after.processing) == (
        before.status, before.source, before.lesson, before.processing)


def test_chinese_level_is_set_then_cleared(setup):  # noqa: F811
    assert _post(setup, "HSK3").status_code == 200
    assert setup["store"].get(MEDIA_ID).level == "HSK3"
    assert _post(setup, "").status_code == 200
    cleared = setup["store"].get(MEDIA_ID)
    assert cleared.level == ""
    assert stored_media_metadata(cleared)["reviewed_level"] is None


def test_invalid_level_and_language_mismatch_are_refused(setup):  # noqa: F811
    assert _post(setup, "Z9").status_code == 422
    assert _post(setup, "B1").status_code == 422  # the item is Chinese
    _make_english(setup)
    response = _post(setup, "HSK3")
    assert response.status_code == 422
    assert "media_level_invalid" in response.text
    assert setup["store"].get(MEDIA_ID).level == ""


def test_access_rules_match_the_sibling_routes(setup):  # noqa: F811
    assert _post(setup, "HSK3", admin=False).status_code == 403
    assert _post(setup, "HSK3", origin=None).status_code == 403
    assert call(setup["app"], "POST", "/api/admin/console/content/media/nope/level",
                json={"level": "HSK3"}).status_code == 404
    entry = setup["store"].get(MEDIA_ID)
    setup["store"].upsert(replace(entry, library="personal"))
    assert _post(setup, "HSK3").status_code == 404
    assert setup["store"].get(MEDIA_ID).level == ""


def test_level_is_refused_while_processing_is_active(setup):  # noqa: F811
    entry = setup["store"].get(MEDIA_ID)
    setup["store"].upsert(replace(entry, status="processing", processing={"state": "running"}))
    assert _post(setup, "HSK3").status_code == 409
    assert setup["store"].get(MEDIA_ID).level == ""


def test_each_change_is_audited(setup):  # noqa: F811
    assert _post(setup, "HSK3").status_code == 200
    assert _post(setup, "HSK3").status_code == 200
    with Session(setup["engine"]) as session:
        rows = session.query(AuditLog).filter(AuditLog.action == "admin.content.level").order_by(AuditLog.created_at).all()
        assert len(rows) == 2
        assert all(row.entity_id == MEDIA_ID for row in rows)
        assert [row.payload["outcome"] for row in rows] == ["ok", "unchanged"]
        assert rows[0].payload["from"] == "" and rows[0].payload["to"] == "HSK3"
