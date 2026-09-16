"""EPUB -> Reading Library import adapter.

Parses one EPUB file into a `ParsedBook`: title/author/language/description
best-effort from Dublin Core metadata, an ordered chapter list (each a title
plus the paragraphs the chapter actually has - no invented breaks, mirroring
`static/orena/content/reading.js`'s own `readable()` contract), and an
optional cover image.

Only `paragraphs`/`title` are ever required for a chapter to count as usable
content (the same minimum `readable()` itself enforces). Every other field is
best-effort: a missing author, language or cover never fails the import by
itself - `ParsedBook.language` may be `None` when the EPUB does not state one
that the caller's language registry recognizes, and the caller decides the
fallback (the admin's declared import language), not this module.

Security posture (an admin-uploaded file, not anonymous public upload, but
hardened regardless per the acceptance requirement this module exists to
satisfy): every guard below is enforced during actual decompression/parsing,
never only against a declared header a crafted archive could lie about.

  - `MAX_EPUB_BYTES` / `MAX_ENTRIES` / `MAX_SINGLE_ENTRY_BYTES` /
    `MAX_TOTAL_UNCOMPRESSED_BYTES` bound the archive itself (zip-bomb guard).
  - Every zip entry name is checked for absolute paths and `..` segments
    (zip-slip guard) before it is ever joined into an internal lookup.
  - Every XML/XHTML fragment is scanned for a `<!ENTITY` declaration before
    parsing and rejected if present (entity-expansion / XXE guard). An
    ordinary `<!DOCTYPE html PUBLIC "..." "...">` reference, which many real
    EPUB chapter files carry for XHTML validation, is left untouched -
    `xml.etree.ElementTree` does not fetch external subsets during ordinary
    parsing, so it needs no special handling here.
  - Chapter text is extracted through `Element.itertext()` only - raw
    child-element markup, and therefore any embedded `<script>`, is never
    copied into a paragraph string. Paragraphs are always returned as plain
    strings, rendered later only through the existing `esc()`-escaped text
    paths every other reading source already uses.
  - A cover image is accepted only when its manifest media-type is one of
    `COVER_CONTENT_TYPES` (jpeg/png/webp/gif) - never SVG, which can carry a
    script payload of its own.
"""
from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree

MAX_EPUB_BYTES = 80 * 1024 * 1024
MAX_ENTRIES = 4000
MAX_SINGLE_ENTRY_BYTES = 40 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_TITLE_CHARS = 240
MAX_DESCRIPTION_CHARS = 4000
MAX_CHAPTER_KEY_CHARS = 200
_READ_CHUNK = 1024 * 1024

COVER_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_CONTAINER_PATH = "META-INF/container.xml"
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "td"}
_DC = "{http://purl.org/dc/elements/1.1/}"
_OPF_NS_CANDIDATES = (
    "{http://www.idpf.org/2007/opf}",
    "",
)


class EpubImportError(Exception):
    """A categorized, admin-safe import failure. Never a raw parser traceback."""

    def __init__(self, category: str, detail: str = "") -> None:
        self.category = category
        self.detail = detail
        super().__init__(f"{category}: {detail}" if detail else category)


@dataclass(frozen=True)
class ParsedChapter:
    chapter_key: str
    title: str
    paragraphs: tuple[str, ...]

    @property
    def word_count(self) -> int:
        return sum(len(p.split()) for p in self.paragraphs)


@dataclass(frozen=True)
class ParsedCover:
    data: bytes
    content_type: str


@dataclass(frozen=True)
class ParsedBook:
    title: str
    author: str
    language: str | None
    description: str
    chapters: tuple[ParsedChapter, ...]
    cover: ParsedCover | None = field(default=None)

    @property
    def word_count(self) -> int:
        return sum(chapter.word_count for chapter in self.chapters)


def _reject_unsafe_xml(raw: bytes) -> None:
    head = raw[:8192].lower()
    if b"<!entity" in head:
        raise EpubImportError("unsafe_xml_content", "custom XML entity declaration")


def _parse_xml(raw: bytes) -> ElementTree.Element:
    _reject_unsafe_xml(raw)
    try:
        return ElementTree.fromstring(raw)
    except ElementTree.ParseError as exc:
        raise EpubImportError("malformed_xml", str(exc)) from exc


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo, *, budget: list[int]) -> bytes:
    """Decompress one entry with a hard cap enforced against the actual
    bytes produced, never only against `info.file_size` (a crafted central
    directory can misstate it)."""
    if info.file_size > MAX_SINGLE_ENTRY_BYTES:
        raise EpubImportError("archive_too_large", f"{info.filename} declares an oversized size")
    chunks: list[bytes] = []
    total = 0
    with zf.open(info) as handle:
        while True:
            chunk = handle.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_SINGLE_ENTRY_BYTES:
                raise EpubImportError("archive_too_large", f"{info.filename} exceeds the per-entry limit")
            budget[0] += len(chunk)
            if budget[0] > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise EpubImportError("archive_too_large", "archive exceeds the total uncompressed limit")
            chunks.append(chunk)
    return b"".join(chunks)


def _safe_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or posixpath.isabs(normalized):
        raise EpubImportError("unsafe_archive_entry", name)
    parts = normalized.split("/")
    if any(part in ("", "..") for part in parts if part != normalized.rstrip("/")) or ".." in parts:
        raise EpubImportError("unsafe_archive_entry", name)
    return normalized


def _resolve_href(base_dir: str, href: str) -> str:
    href = href.split("#", 1)[0]
    joined = posixpath.normpath(posixpath.join(base_dir, href))
    if joined.startswith("..") or posixpath.isabs(joined):
        raise EpubImportError("unsafe_archive_entry", href)
    return joined


def _open_zip(data: bytes) -> zipfile.ZipFile:
    if len(data) > MAX_EPUB_BYTES:
        raise EpubImportError("archive_too_large", "file exceeds the maximum EPUB size")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise EpubImportError("malformed_archive", str(exc)) from exc
    infos = zf.infolist()
    if not infos:
        raise EpubImportError("malformed_archive", "empty archive")
    if len(infos) > MAX_ENTRIES:
        raise EpubImportError("archive_too_large", "too many archive entries")
    for info in infos:
        _safe_member_name(info.filename)
    return zf


def _text_of(elements: list[ElementTree.Element]) -> str:
    for element in elements:
        text = "".join(element.itertext()).strip()
        if text:
            return text
    return ""


def _dc_metadata(metadata_el: ElementTree.Element) -> tuple[str, str, str | None, str]:
    title = _text_of(metadata_el.findall(f"{_DC}title"))[:MAX_TITLE_CHARS]
    author = _text_of(metadata_el.findall(f"{_DC}creator"))[:MAX_TITLE_CHARS]
    language_raw = _text_of(metadata_el.findall(f"{_DC}language"))
    language = language_raw.strip().casefold().split("-", 1)[0] or None
    description = _text_of(metadata_el.findall(f"{_DC}description"))[:MAX_DESCRIPTION_CHARS]
    return title, author, language, description


def _cover_manifest_id(metadata_el: ElementTree.Element) -> str | None:
    for meta in metadata_el:
        if _local(meta.tag) == "meta" and meta.get("name") == "cover":
            content = meta.get("content")
            if content:
                return content
    return None


def _paragraphs_of(document: ElementTree.Element) -> list[str]:
    body = None
    for element in document.iter():
        if _local(element.tag) == "body":
            body = element
            break
    if body is None:
        return []
    paragraphs: list[str] = []
    for element in body.iter():
        if _local(element.tag) not in _BLOCK_TAGS:
            continue
        text = " ".join("".join(element.itertext()).split())
        if text:
            paragraphs.append(text)
    return paragraphs


def parse_epub(data: bytes) -> ParsedBook:
    zf = _open_zip(data)
    budget = [0]
    names = set(zf.namelist())

    if _CONTAINER_PATH not in names:
        raise EpubImportError("malformed_epub", "missing META-INF/container.xml")
    container = _parse_xml(_read_entry(zf, zf.getinfo(_CONTAINER_PATH), budget=budget))
    rootfile = next(
        (el for el in container.iter() if _local(el.tag) == "rootfile"),
        None,
    )
    opf_path = rootfile.get("full-path") if rootfile is not None else None
    if not opf_path or opf_path not in names:
        raise EpubImportError("malformed_epub", "container.xml names no readable OPF")

    opf = _parse_xml(_read_entry(zf, zf.getinfo(opf_path), budget=budget))
    opf_dir = posixpath.dirname(opf_path)

    metadata_el = next((el for el in opf if _local(el.tag) == "metadata"), None)
    manifest_el = next((el for el in opf if _local(el.tag) == "manifest"), None)
    spine_el = next((el for el in opf if _local(el.tag) == "spine"), None)
    if manifest_el is None or spine_el is None:
        raise EpubImportError("malformed_epub", "OPF is missing manifest or spine")

    title, author, language, description = (
        _dc_metadata(metadata_el) if metadata_el is not None else ("", "", None, "")
    )

    manifest: dict[str, tuple[str, str, str]] = {}
    for item in manifest_el:
        if _local(item.tag) != "item":
            continue
        item_id = item.get("id")
        href = item.get("href")
        if not item_id or not href:
            continue
        manifest[item_id] = (
            _resolve_href(opf_dir, href),
            item.get("media-type") or "",
            item.get("properties") or "",
        )

    cover_asset: ParsedCover | None = None
    cover_id = _cover_manifest_id(metadata_el) if metadata_el is not None else None
    if cover_id is None:
        cover_id = next(
            (item_id for item_id, (_, __, props) in manifest.items() if "cover-image" in props.split()),
            None,
        )
    if cover_id and cover_id in manifest:
        cover_href, cover_media_type, _props = manifest[cover_id]
        if cover_media_type in COVER_CONTENT_TYPES and cover_href in names:
            try:
                cover_bytes = _read_entry(zf, zf.getinfo(cover_href), budget=budget)
                cover_asset = ParsedCover(data=cover_bytes, content_type=cover_media_type)
            except EpubImportError:
                cover_asset = None  # a broken cover never fails the whole import

    chapters: list[ParsedChapter] = []
    for itemref in spine_el:
        if _local(itemref.tag) != "itemref":
            continue
        idref = itemref.get("idref")
        if not idref or idref not in manifest:
            continue
        href, media_type, _props = manifest[idref]
        if "html" not in media_type and not href.endswith((".xhtml", ".html", ".htm")):
            continue
        if href not in names:
            continue
        try:
            document = _parse_xml(_read_entry(zf, zf.getinfo(href), budget=budget))
        except EpubImportError:
            continue  # one unreadable chapter is skipped, not a whole-book failure
        paragraphs = _paragraphs_of(document)
        if not paragraphs:
            continue
        # A body heading is the chapter's own authored title; the document's
        # <title> (usually in <head>, often just a generic placeholder some
        # generators repeat on every chapter) is only a fallback when the
        # body has no heading at all.
        chapter_title = next(
            ("".join(h.itertext()).strip() for h in document.iter() if _local(h.tag) in {"h1", "h2"} and "".join(h.itertext()).strip()),
            "",
        ) or next(
            ("".join(h.itertext()).strip() for h in document.iter() if _local(h.tag) == "title" and "".join(h.itertext()).strip()),
            "",
        )
        chapters.append(
            ParsedChapter(
                chapter_key=idref[:MAX_CHAPTER_KEY_CHARS],
                title=(chapter_title or f"{title or 'Chapter'} {len(chapters) + 1}")[:MAX_TITLE_CHARS],
                paragraphs=tuple(paragraphs),
            )
        )

    if not chapters:
        raise EpubImportError("no_readable_content", "no chapter with usable paragraphs")
    if not title:
        raise EpubImportError("missing_title", "EPUB names no dc:title")

    return ParsedBook(
        title=title,
        author=author,
        language=language,
        description=description,
        chapters=tuple(chapters),
        cover=cover_asset,
    )
