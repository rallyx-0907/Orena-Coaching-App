"""Reading thumbnails: which candidate may become a card image, and how its bytes are fetched safely.

A Reading card shows a real picture only when three things are all true (D-192, proposed):

  a. the source's image policy allows it (`image_policy_allowed`; off for every source until the
     owner turns it on),
  b. an administrator approved that specific candidate (a recorded `image_set` review event), and
  c. a credit exists (the approved credit, else the source's publisher).

Otherwise the card is the generated letter tile. The bytes are fetched once, at approval time,
through the existing SSRF guard (`media_safe_fetch`), checked against their magic bytes and size, and
stored in the existing asset store; the learner is only ever served the same-origin copy, never the
third party's address. No function here reaches a learner payload with a candidate URL in it.

Pure helpers (no persistence) plus `fetch_image`, whose fetcher is injectable so the contract is
tested without a network.
"""
from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from writing_coach.media_safe_fetch import UnsafeMediaFetch, fetch_bounded

MAX_IMAGE_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 10.0
MIN_SHORT_SIDE = 400
# Width / height: 1:2 (tall) to 2:1 (wide).
MIN_ASPECT, MAX_ASPECT = 0.5, 2.0
# A URL carried by this many other items of the same source is the source's furniture, not this
# article's picture.
SHARED_URL_THRESHOLD = 2
ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
MAX_CREDIT = 240
MAX_ALT = 240
ASSET_PREFIX = "reading-images"
POLICY_KEY = "image_policy"


class ImageRefused(ValueError):
    """An image that may not be stored. `code` is machine-readable; the text is safe to show an admin."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# -- source policy ------------------------------------------------------------------------------


def image_policy_allowed(policy: Any) -> bool:
    """Whether a source's stored config permits learner thumbnails. Absent or malformed means no."""
    if not isinstance(policy, Mapping):
        return False
    entry = policy.get(POLICY_KEY)
    return isinstance(entry, Mapping) and entry.get("allowed") is True


def with_image_policy(policy: Any, allowed: bool) -> dict[str, Any]:
    merged = dict(policy) if isinstance(policy, Mapping) else {}
    merged[POLICY_KEY] = {"allowed": bool(allowed)}
    return merged


# -- candidate selection ------------------------------------------------------------------------


def candidate_url(entry: Any) -> str:
    url = str(entry.get("url") or "").strip() if isinstance(entry, Mapping) else ""
    return url if urlsplit(url).scheme in {"http", "https"} else ""


def _rank(entry: Mapping[str, Any]) -> int:
    source = str(entry.get("source") or "")
    if source.startswith("meta:og"):
        return 0
    if entry.get("role") == "hero":
        return 1
    if source.startswith("meta:"):
        return 2
    return 3


def assess_candidates(
    media: Sequence[Any],
    *,
    shared_counts: Mapping[str, int] | None = None,
    rejected: frozenset[str] = frozenset(),
    approved_url: str = "",
) -> list[dict[str, Any]]:
    """Every stored candidate, in the order a reviewer should look at them, with why it may not be chosen.

    `index` is the candidate's position in the stored list - the handle the admin routes take, so the
    request never carries a URL. A candidate is `eligible` unless it is rejected, shared across the
    source's other items, or its declared size says it is small or oddly shaped. Sizes the page did not
    declare (an og:image usually has none) are checked from the real bytes at approval.
    """
    counts = shared_counts or {}
    rows: list[dict[str, Any]] = []
    for index, entry in enumerate(media or []):
        url = candidate_url(entry)
        if not url:
            continue
        width, height = int(entry.get("width") or 0), int(entry.get("height") or 0)
        reason = ""
        if url in rejected:
            reason = "rejected"
        elif counts.get(url, 0) >= SHARED_URL_THRESHOLD:
            reason = "shared"
        elif width and height and min(width, height) < MIN_SHORT_SIDE:
            reason = "small"
        elif width and height and not (MIN_ASPECT <= width / height <= MAX_ASPECT):
            reason = "aspect"
        rows.append(
            {
                "index": index,
                "role": str(entry.get("role") or ""),
                "width": width,
                "height": height,
                "alt": str(entry.get("alt") or "")[:MAX_ALT],
                "caption": str(entry.get("caption") or "")[:MAX_CREDIT],
                "credit": str(entry.get("credit") or "")[:MAX_CREDIT],
                "eligible": not reason,
                "reason": reason,
                "approved": bool(approved_url) and url == approved_url,
                "_rank": _rank(entry),
            }
        )
    rows.sort(key=lambda row: (row["_rank"], row["index"]))
    for row in rows:
        del row["_rank"]
    return rows


def shared_url_counts(other_items_media: Sequence[Sequence[Any]]) -> dict[str, int]:
    """How many other items of a source carry each candidate URL."""
    counts: dict[str, int] = {}
    for media in other_items_media:
        for url in {candidate_url(entry) for entry in media or [] if candidate_url(entry)}:
            counts[url] = counts.get(url, 0) + 1
    return counts


# -- bytes --------------------------------------------------------------------------------------


def _png_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    return None


def _gif_size(data: bytes) -> tuple[int, int] | None:
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    return None


def _jpeg_size(data: bytes) -> tuple[int, int] | None:
    if data[:2] != b"\xff\xd8":
        return None
    position, length = 2, len(data)
    while position + 9 < length:
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7 or marker == 0xFF:
            position += 1 if marker == 0xFF else 2
            continue
        segment = struct.unpack(">H", data[position + 2 : position + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return width, height
        position += 2 + segment
    return None


def _webp_size(data: bytes) -> tuple[int, int] | None:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP" or len(data) < 30:
        return None
    kind = data[12:16]
    if kind == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L" and data[20] == 0x2F:
        bits = struct.unpack("<I", data[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X":
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    return None


def sniff_image(data: bytes) -> tuple[str, int, int] | None:
    """(content type, width, height) from the bytes themselves, or None when they are not a supported image.

    The declared Content-Type is never trusted: SVG, HTML and anything else dressed as an image fail here.
    """
    for content_type, reader in (
        ("image/png", _png_size),
        ("image/jpeg", _jpeg_size),
        ("image/gif", _gif_size),
        ("image/webp", _webp_size),
    ):
        try:
            size = reader(data)
        except (struct.error, IndexError):
            size = None
        if size and size[0] > 0 and size[1] > 0:
            return content_type, int(size[0]), int(size[1])
    return None


def fetch_image(url: str, *, fetcher: Callable[..., tuple[bytes, str]] | None = None) -> dict[str, Any]:
    """Fetch one candidate under the existing SSRF guard and prove it is a usable picture.

    Returns {"data", "content_type", "ext", "width", "height", "sha256"}; raises ImageRefused otherwise.
    The guard (http/https only, public addresses only, every redirect re-checked, the connected address
    re-checked, no credentials, byte budget enforced while reading) is `media_safe_fetch`'s; this adds the
    type allowlist, the magic-byte check and the size rules.
    """
    fetch = fetcher or fetch_bounded
    if not candidate_url({"url": url}):
        raise ImageRefused("image_unsafe_url", "This image address cannot be fetched.")
    try:
        data, _declared = fetch(
            url,
            max_bytes=MAX_IMAGE_BYTES,
            timeout=FETCH_TIMEOUT_SECONDS,
            content_types=frozenset(ALLOWED_TYPES),
        )
    except UnsafeMediaFetch as exc:
        message = str(exc)
        if "too large" in message:
            raise ImageRefused("image_too_large", message) from exc
        if "not supported" in message:
            raise ImageRefused("image_unsupported_type", message) from exc
        if "not allowed" in message or "valid public" in message:
            raise ImageRefused("image_unsafe_url", message) from exc
        raise ImageRefused("image_fetch_failed", message) from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRefused("image_too_large", "This image is too large.")
    sniffed = sniff_image(data)
    if sniffed is None:
        raise ImageRefused("image_unsupported_type", "This file is not a supported picture.")
    content_type, width, height = sniffed
    if min(width, height) < MIN_SHORT_SIDE:
        raise ImageRefused("image_too_small", "This picture is too small for a card.")
    if not (MIN_ASPECT <= width / height <= MAX_ASPECT):
        raise ImageRefused("image_bad_aspect", "This picture is too narrow or too wide for a card.")
    return {
        "data": data,
        "content_type": content_type,
        "ext": ALLOWED_TYPES[content_type],
        "width": width,
        "height": height,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def asset_key(article_id: str, sha256: str, ext: str) -> str:
    """Content-addressed, ASCII-only, under the article: a different picture is a different key."""
    if not re.fullmatch(r"[0-9a-f-]{32,40}", article_id) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ImageRefused("image_bad_key", "This image cannot be stored.")
    return f"{ASSET_PREFIX}/{article_id}/{sha256[:24]}.{ext}"


def clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


# -- what a learner may see ---------------------------------------------------------------------


def learner_image(
    *,
    article_id: str,
    revision: int,
    policy_allowed: bool,
    approved: Mapping[str, Any] | None,
    publisher: str,
) -> dict[str, str] | None:
    """The `image` object of a learner payload, or None (the letter tile).

    Never carries the candidate's address: only the same-origin route, a credit and alt text.
    """
    if not policy_allowed or not approved or not approved.get("asset_key"):
        return None
    credit = clean_text(approved.get("credit"), MAX_CREDIT) or clean_text(publisher, MAX_CREDIT)
    if not credit:
        return None
    return {
        "url": f"/api/reading/articles/{article_id}/image?v={int(revision)}",
        "credit": credit,
        "alt": clean_text(approved.get("alt"), MAX_ALT),
    }
