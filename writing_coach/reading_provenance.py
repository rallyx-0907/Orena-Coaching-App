"""Provenance of a Reading article: where it came from and under what terms (D-189).

One pure module, no persistence. It derives the learner-visible credit from what
Orena already stores - the source's name, the source item's canonical URL and
author, and the effective rights (the immutable snapshot with the recorded
answers folded over it, `overlay_rights`). It invents no new field.

The same function feeds three places, so that none can drift from the others:
the learner list and detail payloads, the admin publication gate, and the
deterministic automatic admission. A text whose source terms require attribution
(`attribution_required` is true) is missing parts of its credit when the publisher,
the original address or the licence is absent. That is a warning an administrator
must knowingly override to publish (D-189 amends D-105's hard rights gate); only
the automatic admission treats it as a refusal.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_EDGE = " \t\r\n-–—:;,.|/()[]"
_NAME_EDGE = " \t\r\n-–—:;,|/·"

# The fields a credit is made of, in the order a reviewer is told about them.
REQUIRED_FIELDS = ("publisher", "url", "license")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


_CC = re.compile(r"\bCC[ -]?BY(?:[ -](NC-SA|NC-ND|SA|NC|ND))?(?:[ -]?v?(\d\.\d))?(?!\w)", re.IGNORECASE)
_CC0 = re.compile(r"\bCC0(?:[ -]?(1\.0))?(?!\w)", re.IGNORECASE)
_PUBLIC_DOMAIN = re.compile(r"\bpublic[ -]domain\b", re.IGNORECASE)
_CC_HOST = re.compile(r"https?://(?:www\.)?creativecommons\.org/[A-Za-z0-9/._-]{1,160}", re.IGNORECASE)
MAX_LICENSE_URL = 200
MAX_NAME = 200
MAX_URL = 600


def recognise_license(note: Any, explicit_url: Any = "") -> dict[str, Any]:
    """The licence a learner is shown: a recognised name and address, never the note.

    `license_note` is administrator free text (up to 2000 characters) and may hold
    anything, so it never reaches a learner payload or a cache as written. Only a
    Creative Commons licence or a public-domain statement found in it is named, in a
    fixed spelling, with a Creative Commons address (the note's own, else derived).
    `recorded` says only that the administrator recorded some licence statement, which
    is what the publication gate needs; it carries none of its words.
    """
    raw = _text(note)
    explicit = _text(explicit_url)
    name, url = "", ""
    cc0 = _CC0.search(raw)
    cc = None if cc0 else _CC.search(raw)
    if cc0:
        name, url = "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"
    elif cc:
        kind = (cc.group(1) or "").upper()
        version = cc.group(2) or ""
        name = " ".join(part for part in ("CC BY" + (f"-{kind}" if kind else ""), version) if part)
        slug = "by" + (f"-{kind.lower()}" if kind else "")
        url = f"https://creativecommons.org/licenses/{slug}/" + (f"{version}/" if version else "")
    elif _PUBLIC_DOMAIN.search(raw):
        name = "Public domain"
    embedded = _CC_HOST.search(raw)
    for candidate in (explicit, embedded.group(0) if embedded else ""):
        if candidate and _CC_HOST.fullmatch(candidate) and len(candidate) <= MAX_LICENSE_URL:
            url = candidate
            break
    return {"name": name, "url": url, "recorded": bool(raw or explicit)}


def attribution_state(rights: Mapping[str, Any] | None) -> str:
    """required / not_required / unknown - the same three answers `rights_state` gives."""
    answered = rights if isinstance(rights, Mapping) else {}
    if "attribution_required" not in answered or answered["attribution_required"] is None:
        return "unknown"
    return "required" if answered["attribution_required"] else "not_required"


# The names of the built-in input paths. They are admin bookkeeping, never a publisher.
INTERNAL_SOURCE_NAMES = frozenset({"direct url", "manual paste", "file upload"})
MAX_PUBLISHER = 120
PUBLIC_NAME_KEY = "public_name"


def _name(value: Any) -> str:
    """A name safe to show: one line, bounded, no address, and not a built-in label."""
    # Only whitespace and separators that cannot close a pair are trimmed: "Global Voices (English)",
    # "Acme Inc." and "美国之音（VOA）" keep their brackets and full stops.
    cleaned = " ".join(_text(value).split()).strip(_NAME_EDGE)[:MAX_PUBLISHER].strip()
    if not cleaned or _URL.search(cleaned) or cleaned.casefold() in INTERNAL_SOURCE_NAMES:
        return ""
    return cleaned


def public_name_of(policy: Any) -> str:
    """The source's configured learner-facing name, kept in its `polling_policy` JSON
    (that column holds no other key today, so no migration is needed)."""
    return _name(policy.get(PUBLIC_NAME_KEY)) if isinstance(policy, Mapping) else ""


def host_name(url: Any) -> str:
    """A cleaned host for an address with nothing better: `voachinese.com`, never the path."""
    host = (urlsplit(_text(url)).hostname or "").lower()
    for prefix in ("www.", "m.", "amp."):
        host = host.removeprefix(prefix)
    return host if "." in host else ""


def original_publisher_of(extraction: Any) -> str:
    """The publisher a republication names ("originally published by ..."), from the
    extraction provenance kept with the item (reading_source_cleanup)."""
    entries = extraction.get("provenance") if isinstance(extraction, Mapping) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, Mapping) and entry.get("kind") == "republication":
            name = _name(entry.get("original_publisher"))
            if name:
                return name
    return ""


def resolve_publisher(
    *,
    extraction: Any = None,
    public_name: Any = "",
    entered_name: Any = "",
    built_in: bool = False,
    url: Any = "",
) -> tuple[str, str]:
    """The publisher a learner sees, and the site it came through (D-18X, proposed).

    The internal source name (what an administrator calls the source: "QA NASA news
    releases (RSS)", "Direct URL") is never an input. The site the text came from is, in order:

    1. the source's configured public name;
    2. for a built-in path (manual, URL, file) only, the name the administrator typed for this text;
    3. the page's `og:site_name`;
    4. the cleaned host of the item's address.

    When the page is a republication that names its original publisher, that publisher is the
    credit and the site is returned second (`via`): "originally published by X, via Global Voices".
    Otherwise `via` is empty. Both are empty when nothing is known: a missing credit is reported
    by the publication gate, never papered over with an internal label.
    """
    facts = extraction.get("page_facts") if isinstance(extraction, Mapping) else None
    site = (
        _name(public_name)
        or (_name(entered_name) if built_in else "")
        or _name(facts.get("site_name") if isinstance(facts, Mapping) else "")
        or host_name(url)
    )
    original = original_publisher_of(extraction)
    if original:
        return original, "" if original.casefold() == site.casefold() else site
    return site, ""


def build_provenance(
    *,
    publisher: Any,
    url: Any,
    author: Any,
    rights: Mapping[str, Any] | None,
    via: Any = "",
) -> dict[str, Any]:
    """The credit a learner sees, from the source record and the effective rights."""
    answered = rights if isinstance(rights, Mapping) else {}
    publisher_name = _text(publisher)[:MAX_NAME]
    via_name = _text(via)[:MAX_NAME]
    original_url = _text(url)[:MAX_URL]
    author_name = _text(author)[:MAX_NAME]
    licence = recognise_license(answered.get("license_note"), answered.get("license_url"))
    text = ""
    if publisher_name:
        text = f"Originally published by {publisher_name}"
        if via_name:
            text += f" via {via_name}"
        if author_name and author_name.casefold() != publisher_name.casefold():
            text += f" (by {author_name})"
        if licence["name"]:
            text += f", {licence['name']}"
        text += "."
    return {
        "publisher": publisher_name,
        "via": via_name,
        "url": original_url,
        "author": author_name,
        "license": licence,
        "attribution_required": attribution_state(answered),
        "text": text,
    }


def missing_fields(provenance: Mapping[str, Any]) -> list[str]:
    """What the credit lacks, when the terms require one. Empty when attribution
    is not required or unanswered (an unanswered question is advice elsewhere)."""
    if provenance.get("attribution_required") != "required":
        return []
    missing: list[str] = []
    if not _text(provenance.get("publisher")):
        missing.append("publisher")
    if not _text(provenance.get("url")):
        missing.append("url")
    licence = provenance.get("license") or {}
    if not (licence.get("recorded") or _text(licence.get("name")) or _text(licence.get("url"))):
        missing.append("license")
    return missing


def provenance_blockers(provenance: Mapping[str, Any]) -> list[dict[str, str]]:
    """One entry per missing part of a required credit (a warning for the admin route,
    a refusal for automatic admission)."""
    return [
        {"code": "provenance_missing", "question": "attribution_required", "field": field}
        for field in missing_fields(provenance)
    ]
