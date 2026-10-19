"""A body edit recounts the article; the recount script finds and fixes stale rows (Refs #361)."""
# ruff: noqa: F811
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import event, insert, update  # noqa: E402

from writing_coach.persistence.models import ReadingArticle, ReadingArticleTarget  # noqa: E402

from tests.test_reading_content_repository import _article, _snapshot, repository as repository  # noqa: E402,F401,F811
from writing_coach.reading_processing import analyze_article  # noqa: E402

ZH_BODY = "温州是浙江南部的一座城市。这里的人们很早就走向了海外。" * 4


def _zh_article(repository):
    return _zh_article_n(repository, 0)


def _zh_article_n(repository, n):
    body = ZH_BODY + "了" * n  # a distinct body per article: source snapshots are keyed by content
    snapshot = _snapshot(repository, body=body, native_id=f"zh-{n + 1}")
    return repository.create_article(
        source_item_id=snapshot["id"], title=f"温州的踪迹{n}", body=body, excerpt=body[:60],
        language="zh", topic="", estimated_level="HSK3", estimated_confidence=0.5,
        word_count=3460, reading_time_seconds=9999, analysis={"sentence_count": 99}, targets=[],
    )


def test_a_body_edit_recounts_english_and_bumps_the_revision(repository):
    article = _article(repository)
    short = "The river rose overnight."
    edited = repository.update_article(article["id"], actor="admin", body=short)
    expected = analyze_article(short, "en")
    assert edited["word_count"] == expected.word_count == 4
    assert edited["reading_time_seconds"] == expected.reading_time_seconds
    assert edited["content_revision"] == article["content_revision"] + 1


def test_a_body_edit_recounts_chinese_characters(repository):
    article = _zh_article(repository)
    half = ZH_BODY[: len(ZH_BODY) // 2]
    edited = repository.update_article(article["id"], actor="admin", body=half)
    expected = analyze_article(half, "zh")
    assert edited["word_count"] == expected.word_count != 3460
    assert edited["reading_time_seconds"] == expected.reading_time_seconds


def test_the_recount_dry_run_writes_nothing_and_apply_is_idempotent(repository):
    article = _zh_article(repository)
    found = repository.recount_articles()
    assert [item["id"] for item in found] == [article["id"]]
    assert repository.get_article(article["id"])["word_count"] == 3460
    assert len(repository.recount_articles(apply=True, article_id=article["id"])) == 1
    fixed = repository.get_article(article["id"])
    assert fixed["word_count"] == analyze_article(ZH_BODY, "zh").word_count
    assert fixed["content_revision"] == article["content_revision"] + 1
    assert repository.recount_articles(apply=True) == []


def test_a_title_only_edit_bumps_the_revision_once_and_recounts_nothing(repository):
    article = _article(repository)
    edited = repository.update_article(article["id"], actor="admin", title="A different title")
    assert edited["content_revision"] == article["content_revision"] + 1
    assert edited["word_count"] == article["word_count"]
    assert edited["analysis"] == article["analysis"]


def test_recount_keeps_unrelated_analysis_keys_and_reports_stale_issues_and_orphans(repository):
    article = _zh_article(repository)
    with repository.engine.begin() as connection:
        connection.execute(update(ReadingArticle).where(ReadingArticle.id == uuid.UUID(article["id"])).values(
            analysis_json={"sentence_count": 99, "custom_key": "kept", "quality_issues": ["too_short"]}))
        connection.execute(insert(ReadingArticleTarget).values(
            id=uuid.uuid4(), article_id=uuid.UUID(article["id"]), text="不存在的短语", canonical_form="x",
            target_type="phrase", context="", meaning="", estimated_level="", rank=1,
            machine_suggested=True, admin_approved=False, admin_rejected=False,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    found = repository.recount_articles(apply=True, article_id=article["id"])
    assert found[0]["orphan_targets"] == ["不存在的短语"]
    assert found[0]["stale_quality_issues"] == {"stored": ["too_short"], "now": []}
    analysis = repository.get_article(article["id"])["analysis"]
    assert analysis["custom_key"] == "kept"
    assert analysis["quality_issues"] == ["too_short"]  # reported, never auto-cleared


def test_recount_commits_once_per_row_in_batches(repository):
    ids = [_zh_article_n(repository, n)["id"] for n in range(3)]
    commits: list[int] = []
    event.listen(repository.engine, "commit", lambda connection: commits.append(1))
    found = repository.recount_articles(apply=True, batch_size=2)
    assert sorted(item["id"] for item in found) == sorted(ids)
    assert len(commits) == 3
    assert repository.recount_articles(apply=True, batch_size=2) == []
