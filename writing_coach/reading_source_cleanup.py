"""Post-extraction cleanup: what a publisher wraps around its article text.

`reading_article_extraction` finds the article. Publishers still put four kinds
of non-article text inside it, and a learner must not be asked to read them:

1. press / media-contact blocks (names, telephone numbers, e-mail addresses) and
   the "To learn more, visit:" lead-in that points at a link list;
2. an editorial preface ("This post was originally published by ... An edited
   version is republished under a partnership"), which is *provenance*: it
   leaves the body and is returned as structured metadata, never discarded;
3. an author biography at the end;
4. media-player, audio and video boilerplate ("No media source currently
   available", "Embed", "Download").

Every rule needs two things at once, so it cannot fire inside prose: a
*position* (leading or trailing blocks only; player boilerplate is a whole-block
match) and a *pattern*. A paragraph that merely mentions "contact", "media" or
"author" matches nothing here. The rules are generic. `SOURCE_RULES` is the
declarative per-host table for what a generic rule cannot do safely; it is kept
small on purpose.

Nothing here rates, rejects or levels an article.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple
from urllib.parse import urljoin, urlsplit

_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)


def _units(text: str) -> int:
    return len(_CJK_RE.findall(text)) + len(_WORD_RE.findall(_CJK_RE.sub(" ", text)))


class Item(NamedTuple):
    text: str
    heading: bool = False
    hrefs: tuple[str, ...] = ()


@dataclass
class CleanupResult:
    removed: dict[int, str] = field(default_factory=dict)  # index -> kind
    provenance: list[dict[str, str]] = field(default_factory=list)


# ---- declarative per-host table (P1-J extends it) ---------------------------
# Keyed by registrable host; a page host matches when it equals the key or ends
# with "." + key.
#   drop_class_tokens: class/id tokens that name the publisher's media player.
#   player_text:       extra whole-block player strings, matched case-insensitively.
SOURCE_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "voanews.com": {"drop_class_tokens": ("mmp",), "player_text": ()},
    "voachinese.com": {"drop_class_tokens": ("mmp",), "player_text": ("没有媒体可用资源",)},
}


def rules_for(host: str) -> dict[str, tuple[str, ...]]:
    host = (host or "").lower().split(":")[0].removeprefix("www.")
    merged: dict[str, tuple[str, ...]] = {"drop_class_tokens": (), "player_text": ()}
    for key, rule in SOURCE_RULES.items():
        if host == key or host.endswith("." + key):
            for name, values in rule.items():
                merged[name] = merged.get(name, ()) + tuple(values)
    return merged


def host_of(url: str) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


# ---- patterns ---------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,2}[\s.-])?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?!\d)")
_CONTACT_LABEL_RE = re.compile(
    r"^(?i:media|press|public|news)\s+(?i:contacts?|inquiries|relations|office)\b[\s:：-]*", re.UNICODE
)
_END_MARK_RE = re.compile(r"^[\s\-–—#*_=]*(?i:end|30)[\s\-–—#*_=]*$")
_PLAYER_RE = re.compile(
    r"^(?:no media source currently available|accessibility links|skip to main content"
    r"|your browser does(?: not|n['’]t) support (?:the )?(?:html5 )?(?:audio|video)[^.]*\.?"
    r"|embed|embed code|download|download (?:audio|video|mp3|mp4)|share|share this|copy(?: link| url)?"
    r"|play|pause|mute|unmute|fullscreen|full screen|captions?|closed captions?|audio|video"
    r"|loading|loading\.\.\.|close|close player)$",
    re.IGNORECASE,
)
_DOWNLOAD_RE = re.compile(
    r"^(?:download\s+)?(?:jpe?g|png|gif|tiff?|webp|pdf|mp3|mp4|mov|wav|zip|svg)\s*\(\s*\d+(?:[.,]\d+)?\s*(?:[kmg]b)\s*\)$",
    re.IGNORECASE,
)
_REPUBLISH = (
    r"originally\s+(?:published|appeared|posted)|(?:was|is|has\s+been|being)\s+(?:re-?published|re-?posted|cross-?posted|adapted)"
    r"|first\s+(?:published|appeared)"
)
_SUBJECT = r"(?:this|the)\s+(?:\w+\s+){0,3}?(?:post|article|story|piece|essay|report|interview|text)\b"
_PREFACE_RE = re.compile(
    rf"^(?:{_SUBJECT}.{{0,250}}?\b(?:{_REPUBLISH})"
    r"|(?:an?\s+(?:\w+\s+){0,2}version\s+of\s+(?:this|the)\s+(?:post|article|story|piece)\b)"
    r"|originally\s+(?:published|appeared|posted)\s+(?:by|on|at|in)\b"
    r"|re-?published\s+(?:with|under|by|from|on|here)\b)",
    re.IGNORECASE,
)
# A series / partnership / grant note: "This post is part of ... Spotlight series",
# "This article was produced by ... through the ... grant scheme".
_EDITORIAL_NOTE_RE = re.compile(
    rf"^{_SUBJECT}.{{0,300}}?\b(?:is\s+part\s+of\b.{{0,120}}?\b(?:series|spotlight|coverage|project|campaign|special)"
    r"|(?:was|is)\s+(?:produced|commissioned|supported|funded)\s+(?:by|through|with)\b"
    r"|(?:is|was|being)\s+published\s+(?:on|by|at|in)\b.{0,120}?\b(?:agreement|partnership))",
    re.IGNORECASE,
)
_INFO_CONTACT_RE = re.compile(
    r"^(?:for|to\s+get|to\s+request)\s+(?:more\s+)?(?:information|details|questions|inquiries|a\s+copy)\b[^.]{0,120}?"
    r"\b(?:contact|e-?mail|call|write)\b",
    re.IGNORECASE,
)
_PUBLISHER_RE = re.compile(
    r"originally\s+(?:published|appeared|posted)\s+(?:by|on|at|in)\s+(?P<name>[^,.;()]+?)(?=\s+(?:on|under|in|as|with)\b|\s*[,.;(]|$)",
    re.IGNORECASE,
)
_ABOUT_HEADING_RE = re.compile(
    r"^(?:about|meet)\s+(?:the\s+)?(?:author|authors|writer|writers|contributor|contributors|reporter|reporters)\b"
    r"|^(?:author|contributor)\s+(?:bio|biography|profile)\b|^关于作者|^作者简介",
    re.IGNORECASE,
)
_ROLES = (
    "journalist|writer|researcher|editor|reporter|author|analyst|lawyer|activist|photographer|blogger|"
    "professor|lecturer|scholar|poet|filmmaker|correspondent|columnist|historian|economist|consultant"
)
_NAME = r"[A-Z][\w.'’-]*"
_BIO_RE = re.compile(
    rf"^{_NAME}(?:\s+(?:{_NAME}|de|da|van|von|bin|al|el)){{0,4}}\s+(?:is|was)\s+(?:an?|the)\s+[^.]{{0,90}}?\b(?:{_ROLES})\b",
)
_BIO_TAIL_RE = re.compile(
    r"\b(?:based in|lives in|work(?:s|ing) (?:at|for|on|as|in|with)|writes?(?: about| on| for)?|writing|contributor"
    r"|has (?:published|written|worked|authored|covered)|follow (?:him|her|them)|(?:his|her|their) (?:work|writing))\b",
    re.IGNORECASE,
)
_CITATION_RE = re.compile(
    r"\bAccessed\s+[A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4}\b|^[A-Z][\w'’-]+,\s+(?:[A-Z]\.\s?){1,3}.{0,200}?\(\d{4}\)"
)
_REFERENCES_HEADING_RE = re.compile(r"^(?:references|further reading|sources|bibliography|works cited)$", re.IGNORECASE)

_MAX_PREFACE_UNITS = 100
_MAX_CONTACT_UNITS = 45
_MAX_BIO_UNITS = 70
_MAX_BIO_SECTION_UNITS = 150


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_contact(text: str) -> bool:
    """An address block: it carries an e-mail or telephone number and is not a sentence."""
    if _units(text) > _MAX_CONTACT_UNITS:
        return False
    has_reach = bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text))
    if _CONTACT_LABEL_RE.match(text) and (has_reach or _units(text) <= 6):
        return True
    if not has_reach:
        return False
    leftover = _PHONE_RE.sub(" ", _EMAIL_RE.sub(" ", text))
    words = _WORD_RE.findall(leftover)
    # Names, places and agencies are capitalised; prose has lowercase words in it.
    lowercase = [w for w in words if w[0].islower() and w.lower() not in {"of", "and", "the", "for", "de", "at"}]
    return len(lowercase) <= 2


def _is_citation(text: str) -> bool:
    return _units(text) <= 120 and bool(_CITATION_RE.search(text))


def _is_preface(text: str) -> bool:
    return _units(text) <= _MAX_PREFACE_UNITS and bool(_PREFACE_RE.match(text) or _EDITORIAL_NOTE_RE.match(text))


def _is_info_contact(text: str) -> bool:
    return _units(text) <= 30 and bool(_INFO_CONTACT_RE.match(text) and (_EMAIL_RE.search(text) or _PHONE_RE.search(text)))


def _is_bio(text: str) -> bool:
    if _units(text) > _MAX_BIO_UNITS or '"' in text or "“" in text or "「" in text:
        return False
    return bool(_BIO_RE.match(text) and _BIO_TAIL_RE.search(text))


def _provenance(text: str, hrefs: tuple[str, ...], page_host: str, base_url: str) -> dict[str, str]:
    republished = bool(re.search(_REPUBLISH + r"|version\s+of", text, re.IGNORECASE))
    entry = {"kind": "republication" if republished else "editorial_note", "text": _norm(text)}
    if not republished:
        return entry
    found = _PUBLISHER_RE.search(text)
    if found:
        entry["original_publisher"] = _norm(found.group("name"))
    for href in hrefs:
        absolute = urljoin(base_url, href) if base_url else href
        host = host_of(absolute)
        if absolute.startswith(("http://", "https://")) and host and host != page_host:
            entry["original_url"] = absolute
            break
    return entry


def cleanup(items: list[Item], page_url: str = "") -> CleanupResult:
    """Decide which blocks are not article text. Indices refer to `items`."""
    result = CleanupResult()
    page_host = host_of(page_url)
    rules = rules_for(page_host)
    extra_player = {_norm(t).casefold() for t in rules["player_text"]}
    removed = result.removed

    # 4. Player and download boilerplate: a whole-block match, wherever it sits.
    for index, item in enumerate(items):
        text = _norm(item.text)
        if item.heading:
            continue
        if _PLAYER_RE.match(text) or text.casefold() in extra_player:
            removed[index] = "player"
        elif _DOWNLOAD_RE.match(text):
            removed[index] = "media_download"

    def live() -> list[int]:
        return [i for i in range(len(items)) if i not in removed]

    # 2. Preface: one of the first blocks, with the pattern. Provenance is kept.
    for index in live()[:3]:
        item = items[index]
        if not item.heading and _is_preface(item.text):
            removed[index] = "preface"
            result.provenance.append(_provenance(item.text, item.hrefs, page_host, page_url))
    for index in live()[:2]:  # "For more information, contact ..." above the text
        if not items[index].heading and _is_info_contact(items[index].text) and len(live()) > 2:
            removed[index] = "contact"

    # 1 + 3 + trailing references: walk in from the end while the tail is not prose.
    changed = True
    while changed:
        changed = False
        tail = live()
        if not tail:
            break
        last = tail[-1]
        item = items[last]
        text = _norm(item.text)

        # An "About the author" section: its heading and everything under it.
        heading_at = next((i for i in reversed(tail) if items[i].heading and _ABOUT_HEADING_RE.match(_norm(items[i].text))), None)
        if heading_at is not None:
            under = [i for i in tail if i > heading_at]
            if (
                not any(items[i].heading for i in under)
                and sum(_units(items[i].text) for i in under) <= _MAX_BIO_SECTION_UNITS
                and len(tail) - len(under) - 1 >= 2
            ):
                for i in [heading_at, *under]:
                    removed[i] = "author_bio"
                changed = True
                continue
        refs_at = next((i for i in reversed(tail) if items[i].heading and _REFERENCES_HEADING_RE.match(_norm(items[i].text))), None)
        if refs_at is not None and not any(items[i].heading for i in tail if i > refs_at) and len(tail) - 1 - len([i for i in tail if i > refs_at]) >= 2:
            for i in [i for i in tail if i >= refs_at]:
                removed[i] = "references"
            changed = True
            continue

        if item.heading:
            continue  # the extractor already pops a trailing orphan heading
        if _END_MARK_RE.match(text) or _is_contact(text) or _is_info_contact(text):
            removed[last] = "contact"
        elif _is_citation(text) and (
            sum(1 for i in tail if _is_citation(items[i].text)) + sum(1 for kind in removed.values() if kind == "references") >= 2
        ):
            removed[last] = "references"
        elif _is_preface(text) and len(tail) > 2:
            removed[last] = "preface"
            result.provenance.append(_provenance(item.text, item.hrefs, page_host, page_url))
        elif _is_bio(text) and len(tail) > 3:
            removed[last] = "author_bio"
        elif text.endswith((":", "：")) and len(tail) > 1:
            # "To learn more, visit:" whose link list was dropped: a lead-in to nothing.
            removed[last] = "dangling_leadin"
        else:
            break
        changed = True

    return result
