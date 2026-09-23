"""The EPUB importer's own limits, exercised where a hostile file would push them.

Entity declarations are refused wherever the prolog puts them (a long comment
or processing instruction cannot push one out of view), and text that only
mentions "<!ENTITY" is content, not a declaration. Archive limits are enforced
against bytes actually decompressed, per entry and in total, and an upload is
read no further than the maximum EPUB size.
"""
from __future__ import annotations

import asyncio
import io
import zipfile

import pytest

from writing_coach import epub_import
from writing_coach.epub_import import EpubImportError, parse_epub

_CONTAINER = (
    '<?xml version="1.0"?>'
    '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
    '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>'
    "</container>"
)


def _opf(prolog: str = '<?xml version="1.0"?>') -> str:
    return (
        f"{prolog}"
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>A Book</dc:title></metadata>'
        '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="c1"/></spine></package>'
    )


def _epub(*, opf: str | None = None, chapter: str | None = None, extra: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("META-INF/container.xml", _CONTAINER)
        archive.writestr("OEBPS/content.opf", opf or _opf())
        archive.writestr(
            "OEBPS/c1.xhtml",
            chapter
            or '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>One</h1><p>A paragraph of text.</p></body></html>',
        )
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_an_entity_declared_after_a_long_prolog_comment_is_refused():
    padded = '<?xml version="1.0"?><!--' + "x" * 9000 + '--><!DOCTYPE package [<!ENTITY e "boom">]>'
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(_epub(opf=_opf(padded)))
    assert excinfo.value.category == "unsafe_xml_content"


def test_an_entity_declared_after_a_comment_that_looks_like_markup_is_refused():
    tricky = '<?xml version="1.0"?><!-- <package> --><!DOCTYPE package [<!ENTITY e "boom">]>'
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(_epub(opf=_opf(tricky)))
    assert excinfo.value.category == "unsafe_xml_content"


def test_a_parameter_entity_is_refused_too():
    parameter = '<?xml version="1.0"?><!DOCTYPE package [<!ENTITY % p "x">]>'
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(_epub(opf=_opf(parameter)))
    assert excinfo.value.category == "unsafe_xml_content"


def test_text_that_mentions_an_entity_declaration_is_content():
    chapter = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Markup</h1>'
        "<p>Write &lt;!ENTITY name \"value\"&gt; inside a DOCTYPE.</p>"
        '<pre><![CDATA[<!ENTITY example "value">]]></pre></body></html>'
    )
    book = parse_epub(_epub(chapter=chapter))
    assert any("<!ENTITY name" in paragraph for paragraph in book.chapters[0].paragraphs)


def test_an_entry_is_limited_by_the_bytes_it_expands_to(monkeypatch):
    monkeypatch.setattr(epub_import, "MAX_SINGLE_ENTRY_BYTES", 4096)
    bomb = _epub(extra={"OEBPS/images/pad.bin": b"\0" * 20000})
    assert len(bomb) < 4096, "the archive is small; only its expansion is large"
    # Nothing references the padding, so the manifest, not the limit, would
    # skip it: make the oversized entry one the parser must read.
    chapter = "<html xmlns=\"http://www.w3.org/1999/xhtml\"><body><p>" + "a " * 5000 + "</p></body></html>"
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(_epub(chapter=chapter))
    assert excinfo.value.category == "archive_too_large"


def test_the_archive_is_limited_by_the_total_it_expands_to(monkeypatch):
    monkeypatch.setattr(epub_import, "MAX_TOTAL_UNCOMPRESSED_BYTES", 3000)
    chapter = "<html xmlns=\"http://www.w3.org/1999/xhtml\"><body><p>" + "b " * 1500 + "</p></body></html>"
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(_epub(chapter=chapter))
    assert excinfo.value.category == "archive_too_large"


def test_an_upload_is_read_no_further_than_the_maximum_size(monkeypatch):
    from writing_coach import reading_library_api

    class _Upload:
        def __init__(self) -> None:
            self.served = 0

        async def read(self, size: int = -1) -> bytes:
            self.served += size
            return b"z" * size

    upload = _Upload()
    with pytest.raises(EpubImportError) as excinfo:
        asyncio.run(reading_library_api._read_upload_limited(upload, max_bytes=3 * 1024 * 1024))
    assert excinfo.value.category == "archive_too_large"
    assert upload.served <= 4 * 1024 * 1024, "reading stops at the limit, not at the end of the upload"
