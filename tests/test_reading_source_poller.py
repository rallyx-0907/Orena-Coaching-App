"""RSS/Atom polling feeds the existing ingestion path; no real network."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.pool import StaticPool

from writing_coach.media_safe_fetch import fetch_bounded
from writing_coach.persistence.models import Base, ReadingIngestionJob, ReadingSource
from writing_coach.persistence.reading_content_repository import ReadingContentRepository
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_content_engine import ReadingContentEngine
from writing_coach.reading_source_poller import ReadingSourcePoller, parse_feed

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>One</title><link>https://news.example.org/a/1</link><guid>g1</guid><pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Two</title><link>https://news.example.org/a/2?utm_source=x</link></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A</title>
<id>tag:x,1</id><link rel="self" href="https://news.example.org/self"/>
<link rel="alternate" href="/a/3"/><updated>2026-10-05T10:00:00Z</updated></entry></feed>"""


class Net:
    def __init__(self, payload=RSS, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def __call__(self, url, **kwargs):
        self.calls.append(url)
        if self.error:
            raise self.error
        return self.payload, "application/xml"


@pytest.fixture()
def world():
    db = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(db)
    content, jobs = ReadingContentRepository(db), ReadingJobRepository(db)
    content.ensure_built_in_sources()
    engine = ReadingContentEngine(content=content, jobs=jobs)
    source = content.create_source(
        slug="news", name="News", source_type="rss", base_url="https://news.example.org/feed.xml",
        languages=["en"], rights={"automation_allowed": True, "can_republish": True}, created_by="t")
    content.set_source_state(source["id"], "active", actor="t")
    content.set_polling(source["id"], enabled=True, actor="t")

    def poller(net):
        return ReadingSourcePoller(content=content, jobs=jobs, engine=engine, fetcher=net)

    def job_count():
        with db.connect() as c:
            return c.execute(select(func.count()).select_from(ReadingIngestionJob)).scalar()

    return {"db": db, "content": content, "poller": poller, "source": source["id"], "jobs": job_count}


def test_rss_two_new_articles_become_url_jobs_and_repeat_is_idempotent(world):
    p = world["poller"](Net())
    first = p.poll_due(force=True)[0]
    assert (first["queued"], world["jobs"]()) == (2, 2)
    second = p.poll_due(force=True)[0]
    assert (second["queued"], second["skipped"], world["jobs"]()) == (0, 2, 2)
    source = world["content"].get_source(world["source"])
    assert source["last_success_at"] and source["last_error"] == ""


def test_atom_alternate_link_resolved(world):
    urls = [e["url"] for e in parse_feed(ATOM, base_url="https://news.example.org/feed")]
    assert urls == ["https://news.example.org/a/3"]
    assert world["poller"](Net(ATOM)).poll_due(force=True)[0]["queued"] == 1


@pytest.mark.parametrize("paused", [True, False])
def test_ineligible_source_makes_no_network_call(world, paused):
    if paused:
        world["content"].set_source_state(world["source"], "paused", actor="t")
    else:
        world["content"].set_polling(world["source"], enabled=False, actor="t")
    net = Net()
    assert world["poller"](net).poll_due(force=True) == [] and net.calls == []


def test_automation_not_allowed_makes_no_network_call(world):
    with world["db"].begin() as c:
        c.execute(update(ReadingSource).values(automation_allowed=False))
    net = Net()
    assert world["poller"](net).poll_due(force=True) == [] and net.calls == []


def test_one_bad_entry_does_not_fail_the_source(world):
    p = world["poller"](Net())
    real = p.engine.submit

    def submit(sub, **kw):
        if sub.url.endswith("/1"):
            raise RuntimeError("boom")
        return real(sub, **kw)

    p.engine.submit = submit
    result = p.poll_due(force=True)[0]
    assert (result["queued"], result["refused"], "error" in result) == (1, 1, False)
    assert world["content"].get_source(world["source"])["last_error"] == ""


@pytest.mark.parametrize("net", [
    Net(payload=b"<rss><channel>"),
    Net(payload=b"<!DOCTYPE x [<!ENTITY a 'b'>]><rss/>"),
    Net(payload=b"<html/>"),
    Net(error=TimeoutError("timed out")),
])
def test_unreadable_feed_records_error_and_backs_off(world, net):
    result = world["poller"](net).poll_due(force=True)[0]
    assert "error" in result and world["jobs"]() == 0
    source = world["content"].get_source(world["source"])
    assert source["last_error"] and "next_retry_at" in source["polling_cursor"]
    again = Net()
    assert world["poller"](again).poll_due() == [] and again.calls == []  # waits for next_retry_at


def test_private_feed_url_refused_by_safe_fetch_boundary(world):
    with world["db"].begin() as c:
        c.execute(update(ReadingSource).values(base_url="http://127.0.0.1/feed.xml"))
    p = world["poller"](fetch_bounded)
    result = p.poll_due(force=True)[0]
    assert "error" in result and world["jobs"]() == 0


def test_failed_feed_log_line_never_carries_a_query_string_or_token(world, caplog):
    net = Net(error=TimeoutError("GET https://news.example.org/feed.xml?token=SECRET123 timed out"))
    with caplog.at_level("WARNING", logger="writing_coach.reading_source_poller"):
        world["poller"](net).poll_due(force=True)
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "news.example.org/feed.xml" in logged and "SECRET123" not in logged and "token=" not in logged
