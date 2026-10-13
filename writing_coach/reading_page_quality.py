"""Quality admission: the one place that says a page is not a publishable article (D-18X, PROPOSED).

The trial (docs/content/READ_SOURCE_TRIAL_2026-10-13.md, D10) found pages that are
not articles reaching the review queue: video and audio pages, index pages,
feed stubs and bot-challenge pages, with nothing to stop a publish.

Two layers, kept apart on purpose:

* `page_facts` reads what only the raw page can say (player markup, challenge
  text, a Special: address, an index title, the site name). The extractor stores
  them with the extraction evidence.
* `quality_flags` turns those facts, the cleaned body and the extraction
  confidence into stable issue codes. Every threshold lives in this file.

HARD codes are facts that make the page not an article. Publishing one is
refused by `publication_blockers` unless an administrator gives an explicit,
reasoned override. SOFT codes leave the item reviewable; they still hold back
D-111 automatic admission (any issue means review).
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote, urlsplit

QUALITY_VERSION = "reading-quality/1"

# ---- thresholds (per language: English words, Chinese Hanzi) -----------------
# Set from the 2026-10-13 trial: the shortest genuine article was 248 English
# words (NASA release) and 983 Hanzi (VOA 中文 report); the non-articles were 0-7
# words, 216-245 Hanzi (video / audio pages) and 119-186 Hanzi (feed stubs).
# The soft minimum sits just above the engine's own `too_short` floor (60) and
# below every authored paste the engine already accepts; the page-shape signals
# below (media, index, special page), not this number, catch the trial's stubs.
MIN_BODY_UNITS = {"en": 80, "zh": 120}  # below: soft `body_below_minimum`
MEDIA_PAGE_MAX_UNITS = {"en": 60, "zh": 400}  # player markup and a body this short: hard `media_page`

# ---- stable codes ------------------------------------------------------------
HARD_ISSUES = frozenset({"empty_body", "media_page", "index_page", "bot_challenge", "special_page"})
SOFT_ISSUES = frozenset({"body_below_minimum", "extraction_medium_confidence", "generic_title"})

_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)

_MEDIA_RE = re.compile(
    r"<(?:video|audio)\b"
    r"|<iframe\b[^>]*\b(?:youtube|youtu\.be|vimeo|player|embed)"
    r"|class\s*=\s*[\"'][^\"']*\b(?:jw-?player|video-js|vjs-|media-?player|mejs)"
    r"|<meta\b[^>]*(?:property|name)\s*=\s*[\"']og:(?:video|audio)",
    re.IGNORECASE,
)
_CHALLENGE_RE = re.compile(
    r"client challenge|just a moment|access denied|attention required|verify you are (?:a )?human"
    r"|checking your browser|enable javascript and cookies|403 forbidden|are you a robot"
    r"|请稍候|请稍後|访问被拒绝|存取被拒|安全验证|安全驗證|验证您是人类|驗證您是人類",
    re.IGNORECASE,
)
_CHALLENGE_MAX_PAGE_UNITS = 300  # a real article that merely quotes "access denied" is longer than this
_INDEX_TITLE_RE = re.compile(
    r"^(?:所有内容|所有內容|全部内容|全部內容|所有文章|全部文章|所有报道|所有報導|最新内容|最新內容"
    r"|all content|all stories|all articles|all posts|archives?|latest news|latest stories|site map|sitemap)$",
    re.IGNORECASE,
)
_GENERIC_TITLES = frozenset(
    {
        "home", "homepage", "home page", "index", "untitled", "news", "latest", "welcome", "default",
        "首页", "首頁", "无标题", "無標題", "新闻", "新聞", "主页", "主頁",
    }
)
_TITLE_SPLIT_RE = re.compile(r"\s*[|/–—·:]\s*|\s+-\s+")
_DATE_RE = re.compile(
    r"\b(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b|(?:19|20)\d{2}\s*年\s*\d{1,2}\s*月"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?。！？…][\"'”’)\]」』）]*$")


def units(text: str) -> int:
    """Words, with every CJK character counted as one."""
    return len(_CJK_RE.findall(text)) + len(_WORD_RE.findall(_CJK_RE.sub(" ", text)))


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def _first(pattern: str, html: str) -> str:
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return " ".join(re.sub(r"<[^>]+>", " ", match.group(1)).split()) if match else ""


def _meta(html: str, name: str) -> str:
    for tag in re.findall(r"<meta\b[^>]*>", html, re.IGNORECASE):
        if re.search(rf"(?:property|name)\s*=\s*[\"']{re.escape(name)}[\"']", tag, re.IGNORECASE):
            content = re.search(r"content\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", tag, re.IGNORECASE)
            if content:
                return " ".join((content.group(1) or content.group(2) or "").split())
    return ""


def page_facts(html: str, *, url: str = "", title: str = "") -> dict[str, Any]:
    """What only the raw page can tell: facts, never verdicts."""
    html = html or ""
    page_title = title or _first(r"<title[^>]*>(.*?)</title>", html)
    h1 = _first(r"<h1\b[^>]*>(.*?)</h1>", html)
    visible = re.sub(r"<(script|style|head|noscript|svg|template)\b.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    visible = " ".join(re.sub(r"<[^>]+>", " ", visible).split())
    page_units = units(visible)
    # A challenge page titles itself in a few words; a headline that merely quotes one is longer.
    challenge = any(
        units(text) <= 8 and bool(_CHALLENGE_RE.search(text)) for text in (page_title, h1)
    ) or (
        page_units < _CHALLENGE_MAX_PAGE_UNITS and bool(_CHALLENGE_RE.search(visible[:600]))
    )
    path = unquote(urlsplit(url).path).casefold() if url else ""
    segments = [part for part in _TITLE_SPLIT_RE.split(page_title) if part] + [h1]
    return {
        "media_player": bool(_MEDIA_RE.search(html)),
        "bot_challenge": challenge,
        "special_page": "/special:" in path or "/特殊:" in path,
        "index_title": any(_INDEX_TITLE_RE.match(part.strip()) for part in segments if part.strip()),
        "site_name": _meta(html, "og:site_name"),
        "page_units": page_units,
    }


def _looks_like_listing(body: str) -> bool:
    """Many short dated lines, or lines that each open with a date: a list of links, not prose."""
    lines = [line.strip() for line in body.split("\n") if line.strip()]
    if len(lines) < 8:
        return False
    short = sum(1 for line in lines if units(line) <= 18 and not _SENTENCE_END_RE.search(line))
    dated = sum(1 for line in lines if _DATE_RE.search(line))
    # A section page lists "date, headline, teaser" per entry (VOA 中文 /z/ pages): every line opens with a date.
    leading = sum(1 for line in lines if (m := _DATE_RE.search(line)) and m.start() <= 1)
    return (short / len(lines) >= 0.7 and dated >= 3) or leading / len(lines) >= 0.7


def _generic_title(title: str, site_name: str) -> bool:
    cleaned = _norm(title)
    if not cleaned:  # no title at all is not a generic one: the engine falls back to the excerpt
        return False
    if cleaned in _GENERIC_TITLES:
        return True
    parts = {_norm(part) for part in _TITLE_SPLIT_RE.split(title) if part.strip()}
    return bool(site_name) and parts <= {_norm(site_name)} | {""}


def quality_flags(
    *, body: str, language: str, title: str = "", confidence: str = "",
    facts: Mapping[str, Any] | None = None,
) -> list[str]:
    """Stable issue codes, hard first. Empty means nothing here doubts the page."""
    facts = facts or {}
    lang = "zh" if language == "zh" else "en"
    size = units(body or "")
    flags: list[str] = []
    if size == 0:
        flags.append("empty_body")
    if facts.get("bot_challenge"):
        flags.append("bot_challenge")
    if facts.get("special_page"):
        flags.append("special_page")
    if facts.get("media_player") and size < MEDIA_PAGE_MAX_UNITS[lang]:
        flags.append("media_page")
    if facts.get("index_title") or _looks_like_listing(body or ""):
        flags.append("index_page")
    if 0 < size < MIN_BODY_UNITS[lang]:
        flags.append("body_below_minimum")
    if confidence == "medium":
        flags.append("extraction_medium_confidence")
    if _generic_title(title, str(facts.get("site_name") or "")):
        flags.append("generic_title")
    return flags


def hard_issues(issues: Any) -> list[str]:
    """The hard codes among stored quality issues, in stored order."""
    return [code for code in (issues if isinstance(issues, list) else []) if code in HARD_ISSUES]
