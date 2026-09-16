"""EPUB -> Reading Library parsing, including the security guards §4 of the
Shared Reading Library task requires: zip-slip, zip-bomb, malformed archive/
XML/XHTML, and unsafe XML content (entity expansion / XXE)."""
from __future__ import annotations

import io
import zipfile

import pytest

from writing_coach.epub_import import (
    MAX_ENTRIES,
    EpubImportError,
    parse_epub,
)

_CONTAINER_XML = (
    '<?xml version="1.0"?>'
    '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/></rootfiles></container>'
)


def _opf(*, title="A Book", creator="An Author", language="en", extra_meta="", manifest_extra="", cover_meta=""):
    return (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{title}</dc:title>"
        f"<dc:creator>{creator}</dc:creator>"
        f"<dc:language>{language}</dc:language>"
        f"{cover_meta}{extra_meta}"
        "</metadata>"
        '<manifest>'
        '<item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="chap2" href="chap2.xhtml" media-type="application/xhtml+xml"/>'
        f"{manifest_extra}"
        '</manifest>'
        '<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>'
        '</package>'
    )


def _xhtml(body, *, doctype='<!DOCTYPE html>'):
    return (
        f"{doctype}"
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter</title></head>'
        f"<body>{body}</body></html>"
    )


def _build_epub(*, opf=None, container=_CONTAINER_XML, chap1=None, chap2=None, extra_files=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf if opf is not None else _opf())
        zf.writestr(
            "OEBPS/chap1.xhtml",
            chap1 if chap1 is not None else _xhtml("<h1>Chapter One</h1><p>First paragraph.</p><p>Second paragraph.</p>"),
        )
        zf.writestr(
            "OEBPS/chap2.xhtml",
            chap2 if chap2 is not None else _xhtml("<h1>Chapter Two</h1><p>Another paragraph here.</p>"),
        )
        for name, data in (extra_files or {}).items():
            zf.writestr(name, data)
    return buffer.getvalue()


def test_valid_epub_parses_title_author_language_and_chapters():
    book = parse_epub(_build_epub())
    assert book.title == "A Book"
    assert book.author == "An Author"
    assert book.language == "en"
    assert len(book.chapters) == 2
    # Block-level heading text counts as content the chapter actually has,
    # same as any other block tag - nothing is filtered out as "just a title".
    assert book.chapters[0].paragraphs == ("Chapter One", "First paragraph.", "Second paragraph.")
    assert book.chapters[1].paragraphs == ("Chapter Two", "Another paragraph here.")
    assert book.cover is None


def test_cover_image_is_extracted_when_manifest_declares_one():
    cover_bytes = b"\xff\xd8\xff\xe0fakejpegbytes"
    opf = _opf(
        cover_meta='<meta name="cover" content="cover-img"/>',
        manifest_extra='<item id="cover-img" href="cover.jpg" media-type="image/jpeg"/>',
    )
    data = _build_epub(opf=opf, extra_files={"OEBPS/cover.jpg": cover_bytes})
    book = parse_epub(data)
    assert book.cover is not None
    assert book.cover.data == cover_bytes
    assert book.cover.content_type == "image/jpeg"


def test_svg_cover_is_never_accepted_even_if_declared():
    opf = _opf(
        cover_meta='<meta name="cover" content="cover-img"/>',
        manifest_extra='<item id="cover-img" href="cover.svg" media-type="image/svg+xml"/>',
    )
    data = _build_epub(opf=opf, extra_files={"OEBPS/cover.svg": b"<svg><script>evil()</script></svg>"})
    book = parse_epub(data)
    assert book.cover is None


def test_ordinary_xhtml_doctype_does_not_trip_the_entity_guard():
    chap1 = _xhtml(
        "<p>Fine paragraph.</p>",
        doctype=(
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
            '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
        ),
    )
    book = parse_epub(_build_epub(chap1=chap1))
    assert book.chapters[0].paragraphs == ("Fine paragraph.",)


def test_custom_entity_declaration_is_rejected():
    chap1 = (
        '<!DOCTYPE html [<!ENTITY boom "big">]>'
        '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>&boom;</p></body></html>'
    )
    data = _build_epub(chap1=chap1)
    # The chapter itself is skipped rather than failing the whole book, but
    # with only one chapter left it must still succeed - assert indirectly by
    # making it the ONLY chapter and expecting no_readable_content.
    single_chapter_opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>A Book</dc:title></metadata>"
        '<manifest><item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="chap1"/></spine></package>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr("OEBPS/content.opf", single_chapter_opf)
        zf.writestr("OEBPS/chap1.xhtml", chap1)
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(buffer.getvalue())
    assert excinfo.value.category == "no_readable_content"


def test_missing_container_xml_is_malformed_epub():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("OEBPS/content.opf", _opf())
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(buffer.getvalue())
    assert excinfo.value.category == "malformed_epub"


def test_not_a_zip_file_is_malformed_archive():
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(b"this is not a zip file at all")
    assert excinfo.value.category == "malformed_archive"


def test_zip_slip_entry_name_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../../etc/passwd", "nope")
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(buffer.getvalue())
    assert excinfo.value.category == "unsafe_archive_entry"


def test_absolute_path_entry_name_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("/etc/passwd", "nope")
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(buffer.getvalue())
    assert excinfo.value.category == "unsafe_archive_entry"


def test_too_many_entries_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for index in range(MAX_ENTRIES + 1):
            zf.writestr(f"filler/{index}.txt", "x")
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(buffer.getvalue())
    assert excinfo.value.category == "archive_too_large"


def test_oversized_declared_entry_is_rejected_without_decompressing():
    # A ZipInfo whose declared file_size alone exceeds the per-entry cap must
    # be rejected before the entry is read at all.
    from writing_coach.epub_import import MAX_SINGLE_ENTRY_BYTES

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        info = zipfile.ZipInfo("OEBPS/content.opf")
        zf.writestr(info, _opf())
    data = bytearray(buffer.getvalue())
    with zipfile.ZipFile(io.BytesIO(bytes(data))) as probe:
        assert probe.getinfo("OEBPS/content.opf").file_size < MAX_SINGLE_ENTRY_BYTES

    # A direct unit check of the guard, independent of crafting a real
    # oversized zip (which would make this test itself slow/huge):
    from writing_coach.epub_import import EpubImportError as _Err
    from writing_coach.epub_import import _read_entry

    class _FakeInfo:
        filename = "huge.bin"
        file_size = MAX_SINGLE_ENTRY_BYTES + 1

    class _FakeZip:
        def open(self, info):
            raise AssertionError("must reject before opening an oversized declared entry")

    with pytest.raises(_Err) as excinfo:
        _read_entry(_FakeZip(), _FakeInfo(), budget=[0])
    assert excinfo.value.category == "archive_too_large"


def test_epub_with_no_readable_paragraphs_is_rejected():
    empty_chapter = _xhtml("")
    data = _build_epub(chap1=empty_chapter, chap2=_xhtml(""))
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(data)
    assert excinfo.value.category == "no_readable_content"


def test_epub_missing_title_is_rejected():
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"></metadata>'
        '<manifest><item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="chap1"/></spine></package>'
    )
    data = _build_epub(opf=opf)
    with pytest.raises(EpubImportError) as excinfo:
        parse_epub(data)
    assert excinfo.value.category == "missing_title"


def test_one_broken_chapter_does_not_fail_the_whole_book():
    data = _build_epub(chap1="not xml at all <<<", chap2=_xhtml("<p>Still here.</p>"))
    book = parse_epub(data)
    assert len(book.chapters) == 1
    assert book.chapters[0].paragraphs == ("Still here.",)


def test_missing_optional_metadata_never_fails_the_import():
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Bare Title</dc:title></metadata>"
        '<manifest><item id="chap1" href="chap1.xhtml" media-type="application/xhtml+xml"/></manifest>'
        '<spine><itemref idref="chap1"/></spine></package>'
    )
    book = parse_epub(_build_epub(opf=opf))
    assert book.title == "Bare Title"
    assert book.author == ""
    assert book.language is None
    assert book.description == ""
    assert book.cover is None
