"""Wikimedia Commons as a media source: a File: page (or a direct upload.wikimedia.org file) resolved through the
Commons API to the media URL, a readable title, the author and the licence.

Read-only and bounded: one JSON request through `media_safe_fetch` (SSRF-guarded, byte- and time-limited) to the
fixed Commons API host. Nothing here decides rights; the licence is recorded as provenance and the item still goes
through the normal rights step (unknown rights are held for a person).
"""
from __future__ import annotations

import html
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlsplit

from writing_coach.media_safe_fetch import UnsafeMediaFetch, fetch_bounded

COMMONS_PAGE_HOST = "commons.wikimedia.org"
COMMONS_UPLOAD_HOST = "upload.wikimedia.org"
COMMONS_API = f"https://{COMMONS_PAGE_HOST}/w/api.php"
PLATFORM = "Wikimedia Commons"
_API_MAX_BYTES = 1024 * 1024
# Wikimedia's User-Agent policy asks scripted clients to identify themselves with a way to reach the operator; a
# generic agent gets 403/429. The project URL is that contact (no personal address).
USER_AGENT = "OrenaMediaImport/1.0 (https://github.com/rallyx-0907/Orena-Coaching-App; media import for a language-learning library)"
API_HOSTS = frozenset({COMMONS_PAGE_HOST})
UPLOAD_HOSTS = frozenset({COMMONS_UPLOAD_HOST})


def refusal(exc: BaseException) -> CommonsRejected:
    """A fetch that Wikimedia refused or did not answer, as the stable code that says which."""
    status = getattr(exc, "status_code", None)
    if status in {403, 429}:
        return CommonsRejected(
            "commons_rate_limited",
            "Wikimedia Commons is limiting requests from this server right now. Try again in a few minutes.",
        )
    return CommonsRejected(
        "commons_unavailable",
        "Wikimedia Commons did not answer, so this file could not be checked. Try again later.",
    )


class CommonsRejected(Exception):
    """A Commons address that cannot be imported, with a stable code and a sentence an operator can act on."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CommonsFile:
    filename: str          # "Example.ogv", spaces not underscores
    page_url: str          # the File: page
    media_url: str         # the original file on upload.wikimedia.org
    mime: str
    title: str             # readable, never the raw filename stem
    author: str
    author_url: str
    licence: str           # short name, e.g. "CC BY-SA 4.0"
    licence_url: str


def is_commons_address(url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold().rstrip(".")
    return host in {COMMONS_PAGE_HOST, COMMONS_UPLOAD_HOST}


def is_derivative_upload(url: str) -> bool:
    """A transcoded rendition on upload.wikimedia.org (`.../commons/transcoded/<a>/<ab>/<File>/<File>.360p.webm`).

    Its last path segment is a derivative name, not a Commons file title, so the File lookup would answer "missing";
    it is a plain media file and imports as a direct one."""
    parts = urlsplit(url)
    if (parts.hostname or "").casefold().rstrip(".") != COMMONS_UPLOAD_HOST:
        return False
    segments = [unquote(item) for item in parts.path.split("/") if item]
    return len(segments) > 3 and segments[:2] == ["wikipedia", "commons"] and segments[2] == "transcoded"


def _filename_from(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").casefold().rstrip(".")
    if host == COMMONS_PAGE_HOST:
        path = unquote(parts.path)
        title = ""
        if path.startswith("/wiki/"):
            title = path[len("/wiki/"):]
        elif path.rstrip("/").endswith("/index.php"):
            title = (parse_qs(parts.query).get("title") or [""])[0]
        title = title.replace("_", " ").strip()
        if not title.casefold().startswith("file:"):
            raise CommonsRejected(
                "commons_not_a_file",
                "This Wikimedia Commons address is not a File: page. Open the audio or video file's own page and paste that address.",
            )
        name = title[len("file:"):].strip()
        if not name:
            raise CommonsRejected("commons_not_a_file", "This Wikimedia Commons address names no file.")
        return name
    segments = [unquote(item) for item in parts.path.split("/") if item]
    if len(segments) < 2 or segments[0] != "wikipedia" or segments[1] != "commons":
        raise CommonsRejected(
            "commons_not_commons",
            "This upload.wikimedia.org address is not a Wikimedia Commons file.",
        )
    if "thumb" in segments:
        at = segments.index("thumb")
        name = segments[at + 3] if len(segments) > at + 3 else ""
    else:
        name = segments[-1]
    name = name.replace("_", " ").strip()
    if not name:
        raise CommonsRejected("commons_not_a_file", "This Wikimedia Commons address names no file.")
    return name


_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _plain(value: object) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", str(value or ""))).split())


def _meta(extmetadata: Mapping[str, object], key: str) -> str:
    item = extmetadata.get(key)
    return str(item.get("value") or "") if isinstance(item, Mapping) else ""


def _absolute(href: str) -> str:
    href = html.unescape(href).strip()
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = f"https://{COMMONS_PAGE_HOST}{href}"
    parts = urlsplit(href)
    return href if parts.scheme in {"http", "https"} and parts.hostname else ""


def _readable_title(object_name: str, filename: str) -> str:
    title = _plain(object_name)
    stem = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", filename).strip()
    if not title or title.casefold() in {filename.casefold(), stem.casefold()}:
        title = stem
    # The upload filename's own punctuation is not a title: "Foo_bar-baz.ogv" -> "Foo bar baz".
    if title == stem:
        title = " ".join(re.sub(r"[_]+", " ", title).split())
    return title[:240] or "Wikimedia Commons file"


def resolve(url: str, *, fetch: Callable[..., tuple[bytes, str]] = fetch_bounded) -> CommonsFile:
    """The Commons file behind this address, or a CommonsRejected that says why not."""
    filename = _filename_from(url)
    query = (
        f"{COMMONS_API}?action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url%7Cmime%7Cextmetadata"
        f"&redirects=1&titles={quote('File:' + filename)}"
    )
    try:
        body, _type = fetch(
            query, max_bytes=_API_MAX_BYTES, timeout=10.0, total_timeout=15.0, allowed_hosts=API_HOSTS, user_agent=USER_AGENT
        )
        answer = json.loads(body.decode("utf-8"))
    except (UnsafeMediaFetch, ValueError, UnicodeDecodeError) as exc:
        raise refusal(exc) from exc
    pages = (answer.get("query") or {}).get("pages") if isinstance(answer, dict) else None
    page = pages[0] if isinstance(pages, list) and pages and isinstance(pages[0], dict) else None
    if page is None or page.get("missing"):
        raise CommonsRejected("commons_file_missing", "This file does not exist on Wikimedia Commons.")
    resolved = str(page.get("title") or "")
    if resolved.casefold().startswith("file:") and resolved[5:].strip():
        filename = resolved[5:].strip()
    info = (page.get("imageinfo") or [None])[0]
    if not isinstance(info, dict) or not info.get("url"):
        raise CommonsRejected("commons_file_missing", "Wikimedia Commons has no file behind this page.")
    mime = str(info.get("mime") or "").casefold()
    if not (mime.startswith(("audio/", "video/")) or mime == "application/ogg"):
        raise CommonsRejected(
            "commons_not_media",
            f"This Commons file is {mime or 'not audio or video'}, not an audio or video recording.",
        )
    media_url = str(info["url"])
    if (urlsplit(media_url).hostname or "").casefold() != COMMONS_UPLOAD_HOST:
        raise CommonsRejected("commons_unavailable", "Wikimedia Commons returned an unexpected file address.")
    extmetadata = info.get("extmetadata") if isinstance(info.get("extmetadata"), Mapping) else {}
    artist_html = _meta(extmetadata, "Artist")
    link = _HREF.search(artist_html)
    return CommonsFile(
        filename=filename,
        page_url=f"https://{COMMONS_PAGE_HOST}/wiki/File:{quote(filename.replace(' ', '_'))}",
        media_url=media_url,
        mime=mime,
        title=_readable_title(_meta(extmetadata, "ObjectName"), filename),
        author=_plain(artist_html)[:200],
        author_url=_absolute(link.group(1)) if link else "",
        licence=_plain(_meta(extmetadata, "LicenseShortName"))[:120],
        licence_url=_absolute(_meta(extmetadata, "LicenseUrl")),
    )
