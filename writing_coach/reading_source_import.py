"""Where a Reading text comes in - and the last place the engine cares.

Three adapters (a paste, a URL, an uploaded file) produce one
`NormalizedSourceItem`. Everything behind this boundary - dedupe, processing,
review, publication - works on that one shape and never learns which adapter
produced it, which is what lets a recurring RSS source arrive later as a
fourth adapter rather than a second engine.

Two deliberate reuses rather than reimplementations:

- A URL is fetched through `writing_coach.media_safe_fetch.fetch_bounded`,
  the same guard Media already uses: public-address validation including the
  peer address actually connected to, re-validated redirects, a byte budget
  enforced during the read, and a timeout. Reading does not get a friendlier
  fetcher, because "friendlier" here means an SSRF hole.
- Cleaning, canonicalization and the content fingerprint come from
  `writing_coach.reading_processing`, so a pasted text and a fetched page are
  hashed by exactly the same rule and dedupe cannot be fooled by the route
  a text took to get here.

Rights travel with the item from the moment it arrives. An admin who supplies
nothing gets `rights_known: False` in the snapshot, never a default that says
the content may be republished - an unanswered rights question is a review
decision downstream, not something this module resolves.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Protocol

from writing_coach.media_safe_fetch import UnsafeMediaFetch, fetch_bounded
from writing_coach.reading_processing import (
    clean_source_text,
    content_fingerprint,
    detect_language,
    normalize_url,
)

# A Reading article is a short text, not a book: the Book Library already owns
# whole works, and these limits are what keep the two catalogs from blurring.
MAX_TEXT_CHARS = 200_000
MAX_FETCH_BYTES = 2 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 15.0
MAX_FILE_BYTES = MAX_TEXT_CHARS * 4  # UTF-8 worst case for the same text budget

ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "application/xhtml+xml"})
ALLOWED_FILE_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".html", ".htm"})

_META_DATE_FORMATS = ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class ReadingSourceError(Exception):
    """A refusal an admin can act on, carried as a code the UI translates."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SubmittedInput:
    """Exactly what the admin sent, before anything is fetched or parsed."""

    kind: str
    text: str = ""
    url: str = ""
    filename: str = ""
    payload: bytes = b""
    title: str = ""
    author: str = ""
    language: str = ""
    published_at: str = ""
    source_name: str = ""
    rights: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawPayload:
    """One fetched or supplied text, before normalization."""

    body: str
    content_type: str
    canonical_url: str
    submitted: SubmittedInput
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedSourceItem:
    """The one shape everything behind the adapter boundary works on."""

    source_native_id: str
    canonical_url: str
    title: str
    author: str
    published_at: datetime | None
    language: str
    body: str
    content_hash: str
    metadata: dict[str, Any]
    rights: dict[str, Any]


class ReadingSourceAdapter(Protocol):
    """`discover` is for recurring sources; manual inputs answer with nothing."""

    kind: str

    def discover(self, *, cursor: str = "") -> list[dict[str, Any]]: ...

    def fetch(self, submitted: SubmittedInput) -> RawPayload: ...

    def normalize(self, raw: RawPayload) -> NormalizedSourceItem: ...


class _HtmlMetadata(HTMLParser):
    """`<title>`, author and publication date - nothing that can execute."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.author = ""
        self.published = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if tag != "meta":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        name = (values.get("name") or values.get("property") or "").lower()
        content = values.get("content", "").strip()
        if not content:
            return
        if name in {"author", "article:author", "dc.creator", "byl"} and not self.author:
            self.author = content
        elif name in {
            "article:published_time",
            "datepublished",
            "dc.date",
            "pubdate",
        } and not self.published:
            self.published = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _parse_published(raw: str) -> datetime | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for pattern in _META_DATE_FORMATS:
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def _looks_like_text(payload: bytes) -> bool:
    """A NUL byte or a binary signature means this is not a text file.

    Checked as well as the extension, because an extension is a claim the
    uploader makes and the bytes are the fact.
    """
    if not payload:
        return False
    if b"\x00" in payload[:4096]:
        return False
    return not payload.startswith((b"%PDF", b"PK\x03\x04", b"\x89PNG", b"\xff\xd8\xff", b"\x1f\x8b"))


def _normalized_body(text: str) -> str:
    return _CONTROL_CHARS.sub("", clean_source_text(text))


def _finish(
    raw: RawPayload,
    *,
    title: str,
    author: str,
    published: datetime | None,
    extra: dict[str, Any] | None = None,
) -> NormalizedSourceItem:
    """The one place a normalized item is built, whatever produced the text."""
    submitted = raw.submitted
    body = _normalized_body(raw.body)
    detected, confidence = detect_language(body)
    declared = (submitted.language or "").strip().casefold()
    language = declared or detected
    metadata: dict[str, Any] = {
        "input_kind": submitted.kind,
        "content_type": raw.content_type,
        "detected_language": detected,
        "detected_language_confidence": confidence,
        "declared_language": declared,
        "language_mismatch": bool(declared and detected and declared != detected),
        "source_name": submitted.source_name,
        "rights_known": bool(submitted.rights),
    }
    metadata.update(raw.metadata)
    metadata.update(extra or {})
    return NormalizedSourceItem(
        source_native_id=raw.canonical_url,
        canonical_url=raw.canonical_url,
        title=(submitted.title or title).strip(),
        author=(submitted.author or author).strip(),
        published_at=_parse_published(submitted.published_at) or published,
        language=language,
        body=body,
        content_hash=content_fingerprint(body),
        metadata=metadata,
        rights=dict(submitted.rights),
    )


def _require_text(body: str) -> str:
    if len(body) > MAX_TEXT_CHARS:
        raise ReadingSourceError("source_too_large", "This text is longer than the engine accepts.")
    if not _normalized_body(body):
        raise ReadingSourceError("empty_source", "There is no readable text in this source.")
    return body


class ManualTextAdapter:
    """What the admin pasted. No fetch, no parse beyond cleaning."""

    kind = "manual"

    def discover(self, *, cursor: str = "") -> list[dict[str, Any]]:
        return []

    def fetch(self, submitted: SubmittedInput) -> RawPayload:
        body = _require_text(submitted.text or "")
        return RawPayload(
            body=body,
            content_type="text/plain",
            canonical_url=normalize_url(submitted.url),
            submitted=submitted,
        )

    def normalize(self, raw: RawPayload) -> NormalizedSourceItem:
        return _finish(raw, title="", author="", published=None)


class DirectUrlAdapter:
    """One admin-supplied URL, fetched under the existing SSRF guard.

    `fetcher` is injectable so the contract can be tested without a network,
    and defaults to `media_safe_fetch.fetch_bounded` - the default is the
    guard, so forgetting to pass anything is the safe case rather than the
    unsafe one.
    """

    kind = "direct_url"

    def __init__(self, fetcher: Any = None) -> None:
        self._fetch = fetcher or fetch_bounded

    def discover(self, *, cursor: str = "") -> list[dict[str, Any]]:
        return []

    def fetch(self, submitted: SubmittedInput) -> RawPayload:
        canonical = normalize_url(submitted.url)
        if not canonical:
            raise ReadingSourceError("unsafe_url", "This address cannot be fetched.")
        try:
            payload, content_type = self._fetch(
                submitted.url.strip(),
                max_bytes=MAX_FETCH_BYTES,
                timeout=FETCH_TIMEOUT_SECONDS,
                content_types=ALLOWED_CONTENT_TYPES,
            )
        except UnsafeMediaFetch as exc:
            message = str(exc)
            if "not allowed" in message or "valid public" in message:
                raise ReadingSourceError("unsafe_url", message) from exc
            if "not supported" in message:
                raise ReadingSourceError("unsupported_content_type", message) from exc
            raise ReadingSourceError("fetch_failed", message) from exc
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise ReadingSourceError(
                "unsupported_content_type", "This address does not serve a readable page."
            )
        try:
            body = payload.decode("utf-8", errors="replace")
        except (UnicodeError, AttributeError) as exc:  # pragma: no cover - decode with replace
            raise ReadingSourceError("undecodable_source", "This page could not be read as text.") from exc
        _require_text(body)
        return RawPayload(
            body=body,
            content_type=content_type or "text/html",
            canonical_url=canonical,
            submitted=submitted,
            metadata={"fetched_url": submitted.url.strip()},
        )

    def normalize(self, raw: RawPayload) -> NormalizedSourceItem:
        metadata = _HtmlMetadata()
        metadata.feed(raw.body)
        metadata.close()
        return _finish(
            raw,
            title=" ".join(metadata.title.split()),
            author=metadata.author,
            published=_parse_published(metadata.published),
        )


class FileAdapter:
    """An uploaded `.txt`, `.md` or `.html`. Not an EPUB - Books owns those."""

    kind = "file"

    def discover(self, *, cursor: str = "") -> list[dict[str, Any]]:
        return []

    def fetch(self, submitted: SubmittedInput) -> RawPayload:
        # A filename is a label, never a path: only the base name survives, so
        # nothing an uploader writes can reach outside where it is recorded.
        filename = posixpath.basename((submitted.filename or "").replace("\\", "/")).strip()
        suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        if suffix not in ALLOWED_FILE_SUFFIXES:
            raise ReadingSourceError(
                "unsupported_file_type", "This phase reads .txt, .md and .html files."
            )
        payload = submitted.payload or b""
        if len(payload) > MAX_FILE_BYTES:
            raise ReadingSourceError("source_too_large", "This file is larger than the engine accepts.")
        if not _looks_like_text(payload):
            raise ReadingSourceError(
                "unsupported_file_type", "This file is not the text format its name claims."
            )
        try:
            body = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReadingSourceError("undecodable_source", "This file is not valid UTF-8 text.") from exc
        _require_text(body)
        return RawPayload(
            body=body,
            content_type="text/html" if suffix in {".html", ".htm"} else "text/plain",
            canonical_url=normalize_url(submitted.url),
            submitted=submitted,
            metadata={"filename": filename},
        )

    def normalize(self, raw: RawPayload) -> NormalizedSourceItem:
        title = ""
        if raw.content_type == "text/html":
            metadata = _HtmlMetadata()
            metadata.feed(raw.body)
            metadata.close()
            title = " ".join(metadata.title.split())
        return _finish(raw, title=title, author="", published=None)


_ADAPTERS: dict[str, Any] = {
    "text": ManualTextAdapter,
    "manual": ManualTextAdapter,
    "url": DirectUrlAdapter,
    "direct_url": DirectUrlAdapter,
    "file": FileAdapter,
}


def adapter_for(kind: str) -> ReadingSourceAdapter:
    factory = _ADAPTERS.get((kind or "").strip().casefold())
    if factory is None:
        raise ReadingSourceError("unsupported_input", "This kind of source is not supported.")
    return factory()


def request_digest(submitted: SubmittedInput) -> str:
    """The idempotency key a queued job is unique on.

    Built from the canonical form of the submission, so the same URL typed
    with different tracking parameters, or the same text submitted twice by a
    double-clicked button, is one job - decided here and enforced by a unique
    constraint in the database, never by a disabled button in a browser.
    """
    canonical = {
        "kind": (submitted.kind or "").strip().casefold(),
        "url": normalize_url(submitted.url),
        "text": content_fingerprint(submitted.text) if submitted.text else "",
        "file": hashlib.sha256(submitted.payload).hexdigest() if submitted.payload else "",
        "language": (submitted.language or "").strip().casefold(),
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
