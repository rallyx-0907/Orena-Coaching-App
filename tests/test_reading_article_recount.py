"""A body edit recounts the article; the recount script finds and fixes stale rows (Refs #361)."""
# ruff: noqa: F811
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from tests.test_reading_content_repository import _article, _snapshot, repository as repository  # noqa: E402,F401,F811
from writing_coach.reading_processing import analyze_article  # noqa: E402

ZH_BODY = "温州是浙江南部的一座城市。这里的人们很早就走向了海外。" * 4


def _zh_article(repository):
    snapshot = _snapshot(repository, body=ZH_BODY, native_id="zh-1")
    return repository.create_article(
        source_item_id=snapshot["id"], title="温州的踪迹", body=ZH_BODY, excerpt=ZH_BODY[:60],
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
