"""Poll approved RSS/Atom sources and feed their article URLs into the engine.

The poller only *discovers*. Every discovered URL goes through the same
`ReadingContentEngine.submit` path an admin's Address form uses, so fetching
(SSRF-guarded `fetch_bounded`), extraction, language, level, targets, hashing
and the review queue are the existing ones and are not repeated here. Polling
creates candidates; publication stays a review decision (or the existing
D-111 admission rule - nothing here changes it).

Eligibility is the repository's own rule for turning polling on: state ==
active, automation_allowed and polling_enabled. Anything else costs zero
network calls. Run `python -m writing_coach.reading_source_poller --once` to
poll every eligible source now, regardless of the interval.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

from writing_coach.core.access_log import quiet_http_client_loggers, scrub_text, scrub_url
from writing_coach.media_safe_fetch import UnsafeMediaFetch, fetch_bounded
from writing_coach.reading_processing import normalize_url
from writing_coach.reading_source_import import ReadingSourceError, SubmittedInput, request_digest

_logger = logging.getLogger(__name__)

FEED_SOURCE_TYPES = frozenset({"rss", "feed"})
MAX_FEED_BYTES = 2 * 1024 * 1024
FEED_TIMEOUT_SECONDS = 15.0
MAX_ENTRIES = 50
DEFAULT_INTERVAL_SECONDS = 900
BACKOFF = (timedelta(minutes=5), timedelta(minutes=15), timedelta(hours=1), timedelta(hours=6))
ACTOR = "orena:reading-poller"
_FORBIDDEN = re.compile(rb"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


class FeedError(Exception):
    """The feed itself could not be fetched or read - a source-level failure."""


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(raw).isoformat()
    except (TypeError, ValueError):
        return ""


def parse_feed(payload: bytes, *, base_url: str = "") -> list[dict[str, str]]:
    """RSS 2.0 or Atom -> [{url, source_native_id, title, published_at}].

    A DOCTYPE or ENTITY declaration is refused before parsing (entity expansion
    and external entities have no place in a feed), so the stdlib parser is
    safe here without a new dependency.
    """
    if _FORBIDDEN.search(payload):
        raise FeedError("feed contains a DOCTYPE or ENTITY declaration")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise FeedError(f"feed is not valid XML: {exc}") from exc
    kind = _local(root.tag)
    if kind not in {"rss", "feed", "RDF"}:
        raise FeedError("not an RSS or Atom feed")
    entries: list[dict[str, str]] = []
    for node in root.iter():
        name = _local(node.tag)
        if name not in {"item", "entry"}:
            continue
        children = {}
        alternate = ""
        for child in node:
            key = _local(child.tag)
            if key == "link" and (child.get("href") is not None):
                if child.get("rel", "alternate") == "alternate" and not alternate:
                    alternate = child.get("href", "")
            else:
                children.setdefault(key, child)
        link = alternate or _text(children.get("link"))
        guid = _text(children.get("guid")) or _text(children.get("id"))
        if not link and guid.startswith(("http://", "https://")):
            link = guid
        url = normalize_url(urljoin(base_url, link.strip())) if link.strip() else ""
        if not url:
            continue
        entries.append({
            "url": url,
            "source_native_id": guid,
            "title": _text(children.get("title")),
            "published_at": _date(
                _text(children.get("pubDate")) or _text(children.get("published"))
                or _text(children.get("updated")) or _text(children.get("date"))
            ),
        })
    return entries


INTERVAL_POLICY = "reading.source_poll_interval_seconds"


def configured_interval() -> int:
    """The polling interval now: READING_SOURCE_POLL_INTERVAL_SECONDS when it is set, else Admin's
    `reading.source_poll_interval_seconds` (BQ, D-172), else 900. 0 means polling is off. Read at every tick."""
    from writing_coach import policies

    try:
        return max(0, int(policies.value(INTERVAL_POLICY)))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS


class ReadingSourcePoller:
    def __init__(
        self, *, content: Any, jobs: Any, engine: Any,
        fetcher: Callable[..., tuple[bytes, str]] = fetch_bounded,
        interval_seconds: int | Callable[[], int] | None = None, max_entries: int = MAX_ENTRIES,
    ) -> None:
        """`interval_seconds`: a number, or a callable read at every tick (`configured_interval`, so an Admin change
        applies without restarting the worker); None: the default."""
        self.content, self.jobs, self.engine, self._fetch = content, jobs, engine, fetcher
        self._interval = DEFAULT_INTERVAL_SECONDS if interval_seconds is None else interval_seconds
        self.max_entries = max_entries

    def interval_seconds(self) -> int:
        source = self._interval
        if not callable(source):
            return int(source)
        try:
            return max(0, int(source()))
        except Exception:  # noqa: BLE001 - an unreadable setting keeps the default cadence
            _logger.warning("reading poller: interval unreadable; using the default", exc_info=True)
            return DEFAULT_INTERVAL_SECONDS

    @property
    def interval(self) -> timedelta:
        return timedelta(seconds=self.interval_seconds())

    @staticmethod
    def eligible(source: dict[str, Any]) -> bool:
        return (source["state"] == "active" and bool(source["rights"]["automation_allowed"])
                and bool(source["polling_enabled"]) and source["source_type"] in FEED_SOURCE_TYPES)

    @staticmethod
    def _state(source: dict[str, Any]) -> dict[str, Any]:
        try:
            return dict(json.loads(source.get("polling_cursor") or "{}"))
        except (TypeError, ValueError):
            return {}

    def due(self, source: dict[str, Any], now: datetime) -> bool:
        retry = self._state(source).get("next_retry_at")
        if retry:
            return now >= datetime.fromisoformat(retry)
        last = source.get("last_checked_at")
        return not last or now >= datetime.fromisoformat(last) + self.interval

    def poll_due(self, *, now: datetime | None = None, force: bool = False) -> list[dict[str, Any]]:
        moment = now or datetime.now(UTC)
        results = []
        for source in self.content.list_sources():
            if self.eligible(source) and (force or self.due(source, moment)):
                results.append(self.poll_source(source, now=moment))
        return results

    def poll_source(self, source: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        moment = now or datetime.now(UTC)
        counts = {"source": source["slug"], "queued": 0, "skipped": 0, "refused": 0}
        try:
            entries = self._discover(source)
        except Exception as exc:  # noqa: BLE001 - a bad feed never crashes the worker
            failures = int(self._state(source).get("failures", 0)) + 1
            retry = moment + BACKOFF[min(failures, len(BACKOFF)) - 1]
            message = scrub_text(f"feed: {exc}")[:500]
            self.content.record_poll(source["id"], error=message, now=moment,
                                     state={"failures": failures, "next_retry_at": retry.isoformat()})
            _logger.warning("reading poller: %s failed: %s", source["slug"], message)
            return {**counts, "error": message}
        known_urls = self.content.known_source_urls(source["id"], [e["url"] for e in entries])
        submissions = [
            (entry, SubmittedInput(kind="url", url=entry["url"], title=entry["title"],
                                   published_at=entry["published_at"], source_id=source["id"],
                                   source_name=source["name"]))
            for entry in entries if entry["url"] not in known_urls
        ]
        counts["skipped"] = len(entries) - len(submissions)
        hashes = {request_digest(sub, source_id=source["id"]) for _, sub in submissions}
        seen_jobs = self.jobs.known_request_hashes(source["id"], sorted(hashes))
        for _, sub in submissions:
            if request_digest(sub, source_id=source["id"]) in seen_jobs:
                counts["skipped"] += 1
                continue
            try:
                job = self.engine.submit(sub, actor=ACTOR, now=moment)
                counts["skipped" if job.get("duplicate") else "queued"] += 1
            except ReadingSourceError as exc:
                counts["refused"] += 1
                _logger.info("reading poller: %s refused %s: %s", source["slug"], scrub_url(sub.url), exc.code)
            except Exception:  # noqa: BLE001 - one bad entry never fails the source
                counts["refused"] += 1
                _logger.exception("reading poller: entry failed: %s", scrub_url(sub.url))
        self.content.record_poll(source["id"], error="", now=moment, state={"failures": 0})
        _logger.info("reading poller: %s", counts)
        return counts

    def _discover(self, source: dict[str, Any]) -> list[dict[str, str]]:
        url = (source.get("base_url") or "").strip()
        try:
            payload, _ = self._fetch(url, max_bytes=MAX_FEED_BYTES, timeout=FEED_TIMEOUT_SECONDS)
        except UnsafeMediaFetch as exc:
            raise FeedError(str(exc)) from exc
        return parse_feed(payload, base_url=url)[: self.max_entries]

    def run_forever(self, should_run: Callable[[], bool] = lambda: True, tick: float = 30.0) -> None:
        while should_run():
            try:
                if self.interval_seconds() > 0:  # 0: polling is switched off for now; asked again next tick
                    self.poll_due()
            except Exception:  # noqa: BLE001
                _logger.exception("reading poller: iteration failed")
            time.sleep(tick)


def build_poller() -> ReadingSourcePoller:  # pragma: no cover - process wiring
    from pathlib import Path

    from writing_coach.book_asset_store import FilesystemBookAssetStore
    from writing_coach.persistence.config import create_runtime_engine
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.persistence.reading_job_repository import ReadingJobRepository
    from writing_coach.reading_content_engine import ReadingContentEngine

    database = create_runtime_engine()
    from writing_coach.thumbnails import require_reading_thumbnails

    store = FilesystemBookAssetStore(Path(os.getenv("READING_LIBRARY_ASSET_ROOT", "data/reading_library_assets")))
    content, jobs = require_reading_thumbnails(ReadingContentRepository(database), store), ReadingJobRepository(database)
    engine = ReadingContentEngine(content=content, jobs=jobs, asset_store=store)
    return ReadingSourcePoller(content=content, jobs=jobs, engine=engine, interval_seconds=configured_interval)


def main() -> int:  # pragma: no cover - one-shot: poll every eligible source now
    logging.basicConfig(level=logging.INFO)
    quiet_http_client_loggers()
    for result in build_poller().poll_due(force=True):
        _logger.info(json.dumps(result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
