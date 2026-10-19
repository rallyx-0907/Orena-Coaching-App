"""Every learner-visible content item has a thumbnail (D-240).

One module for the rule, so Reading, vocabulary collections, books, media and content packs do not each grow
their own copy:

  * the three kinds of thumbnail and the provenance each must carry (`normalize_provenance`),
  * the typographic cover - a deterministic, $0, no-AI SVG built from the title and the design tokens only
    (`typographic_cover_svg`),
  * the allow-listed attach-from-URL path (`fetch_licensed_image`), whose fetcher is injectable so no test
    touches a network,
  * `ThumbnailRequired`, the hard fail a publish raises when an item has no thumbnail.

Source order (D-240): 1. a source image with clear rights, 2. a free library image with its licence, 3. a
typographic cover. No AI image generation without a cost decision from the owner.

Provenance is kept in fields that already exist (a Reading image event's answers, a vocabulary collection's
`provenance` JSON, a media entry's `source` mapping, a book's sidecar object in the asset store); there is no
schema change. A typographic cover is Orena's own work and needs no credit.
"""
from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Callable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

KIND_SOURCE_IMAGE = "source_image"
KIND_LIBRARY_IMAGE = "library_image"
KIND_TYPOGRAPHIC = "typographic"
THUMBNAIL_KINDS = (KIND_SOURCE_IMAGE, KIND_LIBRARY_IMAGE, KIND_TYPOGRAPHIC)
EXTERNAL_KINDS = (KIND_SOURCE_IMAGE, KIND_LIBRARY_IMAGE)

# The licences a downloaded picture may carry, by their canonical name, and the spellings an admin may type.
LICENCES = ("PD", "CC0", "CC BY", "CC BY-SA", "Unsplash", "Pexels")
_LICENCE_ALIASES = {
    "pd": "PD", "public domain": "PD", "publicdomain": "PD", "pdm": "PD", "us government": "PD",
    "cc0": "CC0", "cc0 1.0": "CC0", "cc-0": "CC0",
    "cc by": "CC BY", "cc-by": "CC BY", "cc by 4.0": "CC BY", "cc by 3.0": "CC BY", "cc by 2.0": "CC BY",
    "cc-by-4.0": "CC BY", "cc-by-3.0": "CC BY", "cc-by-2.0": "CC BY",
    "cc by-sa": "CC BY-SA", "cc by-sa 4.0": "CC BY-SA", "cc by-sa 3.0": "CC BY-SA", "cc-by-sa": "CC BY-SA",
    "cc-by-sa-4.0": "CC BY-SA", "cc-by-sa-3.0": "CC BY-SA", "cc by sa": "CC BY-SA",
    "unsplash": "Unsplash", "unsplash licence": "Unsplash", "unsplash license": "Unsplash",
    "pexels": "Pexels", "pexels licence": "Pexels", "pexels license": "Pexels",
}

# Exact hosts, or a registered domain whose sub-domains are also allowed (a leading dot).
ALLOWED_HOSTS = (
    ".nasa.gov", ".noaa.gov", ".nih.gov", ".gutenberg.org",
    "upload.wikimedia.org", "images.unsplash.com", "images.pexels.com",
)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FIELD = 300
ASSET_PREFIX = "thumbnails"
SVG_TYPE = "image/svg+xml"

PROVENANCE_FIELDS = ("source_url", "author", "licence", "licence_url")


class ThumbnailRequired(ValueError):
    """A publish was refused because the item has no thumbnail. `kind` names the content kind."""

    def __init__(self, kind: str, message: str = "") -> None:
        super().__init__(message or f"A {kind} needs a thumbnail before it can be published.")
        self.kind = kind


class ThumbnailRefused(ValueError):
    """A thumbnail that may not be attached. `code` is machine-readable; the text is safe to show an admin."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _clean(value: Any, limit: int = MAX_FIELD) -> str:
    return " ".join(str(value or "").split())[:limit]


def _https_url(value: Any) -> str:
    text = _clean(value, 1000)
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return text


def canonical_licence(value: Any) -> str:
    """The canonical licence name, or '' when it is not one of the allowed licences."""
    text = _clean(value, 60)
    if text in LICENCES:
        return text
    return _LICENCE_ALIASES.get(text.casefold(), "")


def host_allowed(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").casefold()
        scheme = urlsplit(url).scheme
    except ValueError:
        return False
    if scheme != "https" or not host:
        return False
    for entry in ALLOWED_HOSTS:
        if entry.startswith("."):
            if host == entry[1:] or host.endswith(entry):
                return True
        elif host == entry:
            return True
    return False


def normalize_provenance(raw: Mapping[str, Any] | None, *, kind: str | None = None) -> dict[str, str]:
    """{kind, source_url, author, licence, licence_url} or ThumbnailRefused.

    A typographic cover carries only its kind. A source or library image must carry all four fields, an allowed
    licence and an allowed host; this is the one check every attach path and every pack import goes through.
    """
    data = dict(raw or {})
    chosen = _clean(kind or data.get("kind"), 30)
    if chosen not in THUMBNAIL_KINDS:
        raise ThumbnailRefused("thumbnail_kind_invalid", "A thumbnail is a source image, a library image or a typographic cover.")
    if chosen == KIND_TYPOGRAPHIC:
        return {"kind": KIND_TYPOGRAPHIC, "source_url": "", "author": "", "licence": "", "licence_url": ""}
    source_url, licence_url = _https_url(data.get("source_url")), _https_url(data.get("licence_url"))
    author = _clean(data.get("author"))
    licence = canonical_licence(data.get("licence"))
    if not source_url or not host_allowed(source_url):
        raise ThumbnailRefused("thumbnail_host_not_allowed", "This image address is not on the list of allowed image hosts.")
    if not licence:
        raise ThumbnailRefused("thumbnail_licence_not_allowed", "The licence must be public domain, CC0, CC BY, CC BY-SA, Unsplash or Pexels.")
    if not author:
        raise ThumbnailRefused("thumbnail_author_required", "An image needs its author or credit line.")
    if not licence_url:
        raise ThumbnailRefused("thumbnail_licence_url_required", "An image needs the address of its licence.")
    return {"kind": chosen, "source_url": source_url, "author": author, "licence": licence, "licence_url": licence_url}


def credit_line(provenance: Mapping[str, Any] | None) -> str:
    """The one credit a card or reader shows. A typographic cover has none."""
    data = provenance or {}
    if data.get("kind") not in EXTERNAL_KINDS:
        return ""
    return " · ".join(part for part in (_clean(data.get("author")), _clean(data.get("licence"))) if part)


def asset_key(namespace: str, item_id: str, sha256: str, ext: str) -> str:
    """Content-addressed, ASCII-only: `thumbnails/<namespace>/<item>/<hash24>.<ext>`."""
    safe_item = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(item_id)).strip("-.")[:80]
    if not safe_item or not re.fullmatch(r"[a-z-]{3,20}", namespace) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ThumbnailRefused("thumbnail_bad_key", "This thumbnail cannot be stored.")
    if safe_item != str(item_id):  # two distinct ids must not collapse onto one folder
        safe_item = f"{safe_item[:60]}-{hashlib.sha256(str(item_id).encode()).hexdigest()[:12]}"
    return f"{ASSET_PREFIX}/{namespace}/{safe_item}/{sha256[:24]}.{ext}"


# -- typographic cover -------------------------------------------------------------------------------


_TOKENS = Path(__file__).resolve().parents[1] / "static" / "orena" / "kit" / "tokens.css"
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b")
FONT_STACK = "Outfit, 'Noto Sans SC', 'Noto Sans', system-ui, sans-serif"  # the design's --font-ui, as the server can name it
# What each content kind is tinted by - the same skill hues `cover-visuals.js` uses.
KIND_HUE = {
    "reading": "--skill-read", "article": "--skill-read", "book": "--skill-read",
    "vocabulary": "--skill-vocab", "collection": "--skill-vocab",
    "media": "--skill-listen", "listening": "--skill-listen", "video": "--skill-listen",
    "speaking": "--skill-speak", "writing": "--skill-write", "grammar": "--skill-grammar",
}
# `posterAccent` in components.js: the second hue is picked from this list by the title's hash.
_ACCENTS = ("--skill-listen", "--skill-speak", "--skill-read", "--skill-write", "--skill-vocab", "--skill-grammar", "--accent")
INK_TOKEN = "--accent-ink"
WIDTH, HEIGHT = 640, 400  # 16:10, the ratio the media card and the hero draw


@lru_cache(maxsize=1)
def design_tokens() -> dict[str, str]:
    """name -> hex for the tokens this module may paint with, read from the kit's one colour owner."""
    css = _TOKENS.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for match in re.finditer(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\s*;", css):
        found.setdefault(match.group(1), match.group(2).upper())
    wanted = {*(KIND_HUE.values()), *_ACCENTS, INK_TOKEN}
    missing = wanted - set(found)
    if missing:
        raise RuntimeError(f"tokens.css lacks {sorted(missing)}")
    return {name: found[name] for name in sorted(wanted)}


def token_hexes() -> frozenset[str]:
    """Every hex colour the kit's tokens.css declares (what a cover's colours must come from)."""
    return frozenset(item.upper() for item in _HEX.findall(_TOKENS.read_text(encoding="utf-8")))


def _glyph(title: str) -> str:
    for char in str(title or "").strip():
        if char.isalnum():
            return char.upper()
    return ""


def _is_cjk(char: str) -> bool:
    return "⺀" <= char <= "鿿" or "豈" <= char <= "﫿" or "＀" <= char <= "￯"


def _lines(title: str, language: str) -> list[str]:
    """The title in at most three lines, wrapped by width and never cut mid-word (Chinese by character)."""
    text = " ".join(str(title or "").split())
    cjk = language.casefold().startswith("zh") or any(_is_cjk(c) for c in text)
    limit = 14 if cjk else 26
    if cjk:
        rows = [text[i : i + limit] for i in range(0, len(text), limit)]
    else:
        rows, current = [], ""
        for word in text.split(" "):
            if current and len(current) + 1 + len(word) > limit:
                rows.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        rows.append(current)
    if len(rows) > 3:
        rows = rows[:3]
        rows[2] = rows[2][: max(1, limit - 1)].rstrip() + "…"
    return [row for row in rows if row] or [""]


def typographic_cover_svg(title: str, *, language: str = "", topic: str = "", kind: str = "reading") -> bytes:
    """A 640x400 SVG cover for a title: the kind's hue as a gradient, two light circles, the title's first letter
    large and the title set small at the foot - the same poster the app draws for a coverless card, made once and
    stored. Deterministic (the same input gives the same bytes), no network, no AI, and no colour that is not a
    token of the kit. Text is escaped; there is no script, no external reference and no font file."""
    tokens = design_tokens()
    hue = tokens[KIND_HUE.get(kind, "--skill-read")]
    hash_value = 0
    for char in str(title or ""):
        hash_value = (hash_value * 31 + ord(char)) & 0xFFFFFFFF
    hue2 = tokens[_ACCENTS[hash_value % len(_ACCENTS)]]
    ink = tokens[INK_TOKEN]
    glyph = html.escape(_glyph(title), quote=True)
    lines = _lines(title, language)
    size = 30 if len(lines) < 3 else 26
    start = HEIGHT - 44 - (len(lines) - 1) * (size + 8)
    spans = "".join(
        f'<tspan x="40" y="{start + index * (size + 8)}">{html.escape(line, quote=True)}</tspan>'
        for index, line in enumerate(lines)
    )
    label = html.escape(" · ".join(part for part in (str(topic or "").strip(), str(language or "").strip().upper()) if part), quote=True)
    topic_text = (
        f'<text x="40" y="52" fill="{ink}" fill-opacity="0.82" font-size="20" font-weight="600" letter-spacing="1">{label}</text>'
        if label else ""
    )
    alt = html.escape(str(title or ""), quote=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        f'role="img" aria-label="{alt}" font-family="{html.escape(FONT_STACK, quote=True)}">'
        f"<title>{alt}</title>"
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{hue}"/><stop offset="0.7" stop-color="{hue2}"/></linearGradient></defs>'
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#g)"/>'
        f'<circle cx="{WIDTH - 40}" cy="40" r="210" fill="{ink}" fill-opacity="0.14"/>'
        f'<circle cx="300" cy="{HEIGHT + 120}" r="150" fill="{ink}" fill-opacity="0.10"/>'
        f'<text x="{WIDTH - 54}" y="236" text-anchor="end" fill="{ink}" fill-opacity="0.92" font-size="190" font-weight="700">{glyph}</text>'
        f"{topic_text}"
        f'<text fill="{ink}" font-size="{size}" font-weight="700">{spans}</text>'
        "</svg>"
    )
    return svg.encode("utf-8")


def typographic_record(title: str, *, language: str = "", topic: str = "", kind: str = "reading") -> dict[str, Any]:
    """{data, content_type, ext, sha256, alt} of a typographic cover, ready to store."""
    data = typographic_cover_svg(title, language=language, topic=topic, kind=kind)
    return {"data": data, "content_type": SVG_TYPE, "ext": "svg", "sha256": hashlib.sha256(data).hexdigest(),
            "alt": _clean(title, 240), "width": WIDTH, "height": HEIGHT}


# -- attach from a URL --------------------------------------------------------------------------------


# Tests (and only tests) replace this so no check ever reaches a network; production leaves it None, which uses the
# SSRF-guarded `media_safe_fetch.fetch_bounded`.
FETCHER: Callable[..., tuple[bytes, str]] | None = None


def fetch_licensed_image(
    url: str,
    provenance: Mapping[str, Any],
    *,
    fetcher: Callable[..., tuple[bytes, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Download one allow-listed, licensed picture and prove it is one: (record, normalised provenance).

    Order of checks: provenance (host, licence, author, licence URL), then the SSRF-guarded fetch (public
    addresses only, redirects re-checked, <= 5 MB, image types only), then the picture's own magic bytes. Raises
    ThumbnailRefused. `fetcher` is injectable so a test never reaches a network.
    """
    from writing_coach import reading_images as images

    merged = {**dict(provenance), "source_url": url, "kind": provenance.get("kind") or KIND_LIBRARY_IMAGE}
    clean = normalize_provenance(merged)
    if clean["kind"] == KIND_TYPOGRAPHIC:
        raise ThumbnailRefused("thumbnail_kind_invalid", "A typographic cover is generated, not downloaded.")
    try:
        # The allow-list goes into the fetch itself, so every redirect hop (an open redirect on an allowed host
        # included) is re-checked against it, not only the address the administrator typed.
        fetched = images.fetch_image(clean["source_url"], fetcher=fetcher or FETCHER, allowed_hosts=frozenset(ALLOWED_HOSTS))
    except images.ImageRefused as exc:
        raise ThumbnailRefused(exc.code, str(exc)) from exc
    return fetched, clean


def required_message(kind: str) -> str:
    return f"A {kind} needs a thumbnail before it can be published. Attach an image or give it a typographic cover."


# -- storing -------------------------------------------------------------------------------------------


def store_record(store: Any, key: str, record: Mapping[str, Any]) -> bool:
    """Put a record's bytes under `key` unless the same content-addressed key is already there. Returns whether
    this call wrote it (so a caller whose later step fails removes only what it created)."""
    if store.exists(key):
        return False
    store.put(key, bytes(record["data"]))
    return True


def stored_dict(record: Mapping[str, Any], key: str, provenance: Mapping[str, Any]) -> dict[str, Any]:
    """The description of a stored thumbnail: where it is, what it is and where it came from.

    This one shape is what a Reading `image_set` event carries, what a vocabulary collection keeps in
    `provenance["thumbnail"]` and what a book's sidecar and a media entry's `source` are built from.
    """
    return {
        "candidate_url": str(provenance.get("source_url") or ""), "asset_key": key,
        "content_type": record["content_type"], "width": int(record["width"]), "height": int(record["height"]),
        "sha256": record["sha256"], "credit": "", "alt": _clean(record.get("alt"), 240),
        "kind": provenance["kind"], "source_url": provenance.get("source_url", ""), "author": provenance.get("author", ""),
        "licence": provenance.get("licence", ""), "licence_url": provenance.get("licence_url", ""),
    }


PACK_FIELDS = ("kind", "source_url", "author", "licence", "licence_url", "alt", "content_type", "sha256", "width", "height")


def pack_meta(stored: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """What an exported item records about its thumbnail (`data["thumbnail"]`). `asset_key` is the exporting
    environment's key: it names the pack file (`assets/<key>`) that holds the bytes of a downloaded picture."""
    if not stored or not stored.get("asset_key"):
        return None
    return {**{name: stored.get(name, "") for name in PACK_FIELDS}, "asset_key": stored["asset_key"]}


def read_pack_thumbnail(meta: Any, assets: Mapping[str, bytes]) -> tuple[dict[str, Any], dict[str, str]] | None:
    """The verified (record, provenance) of a pack item's downloaded thumbnail, or None when the item carries none
    or carries a typographic cover (the importer makes that one itself, deterministically, from the item's title -
    pack bytes are never trusted for an SVG). Raises ThumbnailRefused for a thumbnail that does not verify: its
    provenance must pass `normalize_provenance` (allowed host and licence) and its bytes must be the picture the
    manifest hash names."""
    from writing_coach import reading_images as images

    if not isinstance(meta, Mapping) or meta.get("kind") in (None, "", KIND_TYPOGRAPHIC):
        return None
    provenance = normalize_provenance(meta)
    data = assets.get(f"assets/{meta.get('asset_key')}")
    if data is None:
        raise ThumbnailRefused("thumbnail_pack_asset_missing", "The pack names a thumbnail it does not contain.")
    sniffed = images.sniff_image(data)
    if sniffed is None or len(data) > MAX_IMAGE_BYTES:
        raise ThumbnailRefused("thumbnail_pack_asset_invalid", "The pack's thumbnail is not a usable picture.")
    content_type, width, height = sniffed
    digest = hashlib.sha256(data).hexdigest()
    if meta.get("sha256") and meta["sha256"] != digest:
        raise ThumbnailRefused("thumbnail_pack_asset_invalid", "The pack's thumbnail does not match its recorded hash.")
    record = {"data": data, "content_type": content_type, "ext": images.ALLOWED_TYPES[content_type], "sha256": digest,
              "width": width, "height": height, "alt": _clean(meta.get("alt"), 240)}
    return record, provenance


def make_reading_cover(store: Any, *, article_id: str, title: str, language: str, topic: str) -> dict[str, Any]:
    """Generate, store and describe a typographic cover for a Reading article (the `image` of an event)."""
    from writing_coach import reading_images as images

    record = typographic_record(title, language=language, topic=topic, kind="reading")
    key = images.asset_key(article_id, record["sha256"], record["ext"])
    store_record(store, key, record)
    return stored_dict(record, key, normalize_provenance({}, kind=KIND_TYPOGRAPHIC))


def make_cover(store: Any, namespace: str, item_id: str, *, title: str, language: str = "", topic: str = "",
               kind: str = "reading") -> dict[str, Any]:
    """Generate, store and describe a typographic cover for any other item (`thumbnails/<namespace>/<id>/…`)."""
    record = typographic_record(title, language=language, topic=topic, kind=kind)
    key = asset_key(namespace, item_id, record["sha256"], record["ext"])
    store_record(store, key, record)
    return stored_dict(record, key, normalize_provenance({}, kind=KIND_TYPOGRAPHIC))


def store_licensed(store: Any, namespace: str, item_id: str, fetched: Mapping[str, Any], provenance: Mapping[str, Any],
                   *, alt: str) -> dict[str, Any]:
    """Store a fetched, licensed picture and describe it (see `fetch_licensed_image`)."""
    key = asset_key(namespace, item_id, fetched["sha256"], fetched["ext"])
    store_record(store, key, fetched)
    return stored_dict({**fetched, "alt": alt}, key, provenance)


def stored_thumbnail(provenance: Any) -> dict[str, Any] | None:
    """The stored thumbnail kept in a provenance mapping (`provenance["thumbnail"]`), or None."""
    value = provenance.get("thumbnail") if isinstance(provenance, Mapping) else None
    if isinstance(value, Mapping) and value.get("asset_key") and value.get("kind") in THUMBNAIL_KINDS:
        return dict(value)
    return None


def collection_view(collection_id: str, title: str, provenance: Any) -> dict[str, Any]:
    """The `thumbnail` object of a vocabulary collection payload: our own same-origin cover route, alt text, kind and
    credit. Every collection has one: a collection with nothing stored gets the deterministic typographic cover, made
    on request, so no learner-visible collection is ever without a picture (D-240)."""
    from urllib.parse import quote

    stored = stored_thumbnail(provenance)
    if stored:
        version, kind, credit = str(stored.get("sha256") or "")[:12], stored["kind"], credit_line(stored)
        alt = _clean(stored.get("alt"), 240) or _clean(title, 240)
    else:
        version = "t" + hashlib.sha256(str(title).encode()).hexdigest()[:11]
        kind, credit, alt = KIND_TYPOGRAPHIC, "", _clean(title, 240)
    return {
        "url": f"/api/vocabulary/library/collections/{quote(str(collection_id), safe='')}/cover?v={version}",
        "alt": alt, "kind": kind, "credit": credit, "stored": stored is not None,
    }


# -- media ---------------------------------------------------------------------------------------------

MEDIA_SOURCE_KEYS = {
    "kind": "thumbnail_kind", "source_url": "thumbnail_source_url", "author": "thumbnail_author",
    "licence": "thumbnail_licence", "licence_url": "thumbnail_licence_url",
}


def has_media_thumbnail(thumbnail: Any) -> bool:
    """A media entry has a thumbnail when it records a provider-hosted one (kept provider-served for an embed: copying
    a provider's thumbnail may conflict with its terms, an open owner question in D-240) or a stored asset."""
    if not isinstance(thumbnail, Mapping):
        return False
    return thumbnail.get("kind") in {"provider-url", "asset"} and bool(str(thumbnail.get("ref") or "").strip())


def media_thumbnail_provenance(source: Mapping[str, Any] | None) -> dict[str, str] | None:
    """The provenance recorded in a media entry's `source` mapping for its stored thumbnail, if any."""
    data = source or {}
    kind = str(data.get(MEDIA_SOURCE_KEYS["kind"]) or "")
    if kind not in THUMBNAIL_KINDS:
        return None
    return {key: str(data.get(name) or "") for key, name in MEDIA_SOURCE_KEYS.items()}


_OWN_COVER_KEY = re.compile(r"media/[A-Za-z0-9_.-]+/thumb-[0-9a-f]{24}\.svg")
_OWN_COVER_HEAD = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}"'.encode()


def is_own_cover(key: str, payload: bytes) -> bool:
    """Whether stored bytes are one of Orena's typographic covers: a cover key AND the generator's own opening, with
    nothing that could run. The files route serves no other SVG."""
    low = payload.lower()
    return (bool(_OWN_COVER_KEY.fullmatch(key)) and payload.startswith(_OWN_COVER_HEAD) and b"<script" not in low
            and b"onload" not in low and b"<foreignobject" not in low and b"href" not in low)


def media_cover_key(media_id: str, stored: Mapping[str, Any]) -> str:
    """`media/<media id>/thumb-<hash>.<ext>`: under the directory the entry owns, so the files route serves it."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(media_id)).strip("-.")[:100]
    if not safe:
        raise ThumbnailRefused("thumbnail_bad_key", "This thumbnail cannot be stored.")
    return f"media/{safe}/thumb-{str(stored['sha256'])[:24]}.{stored['ext']}"


def media_entry_with_thumbnail(entry: Any, store: Any, record: Mapping[str, Any], provenance: Mapping[str, Any]) -> Any:
    """The entry with a stored thumbnail (bytes written to the asset store) and its provenance in `source`."""
    from dataclasses import replace

    key = media_cover_key(entry.media_id, record)
    store_record(store, key, record)
    source = {**dict(entry.source), **{name: str(provenance.get(field) or "") for field, name in MEDIA_SOURCE_KEYS.items()}}
    return replace(entry, thumbnail={"kind": "asset", "ref": key}, source=source)


def media_entry_with_cover(entry: Any, store: Any) -> Any:
    """The entry with a typographic cover made from its title, language and topic."""
    topic = ""
    if isinstance(entry.lesson, Mapping):
        topic = str(entry.lesson.get("topic") or "")
    record = typographic_record(entry.title, language=entry.language, topic=topic, kind="media")
    return media_entry_with_thumbnail(entry, store, record, normalize_provenance({}, kind=KIND_TYPOGRAPHIC))


def require_reading_thumbnails(repository: Any, store: Any) -> Any:
    """Switch the publish gate on for a Reading repository and give it the cover maker an automatic admission uses.

    Called wherever the runtime builds a repository that can publish: the application, the worker and the poller.
    """
    repository.require_thumbnail = True
    repository.cover_factory = lambda item: make_reading_cover(
        store, article_id=item["article_id"], title=item["title"], language=item["language"], topic=item.get("topic") or "",
    )
    return repository
