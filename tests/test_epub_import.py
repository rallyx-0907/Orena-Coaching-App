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
    assert book.chapters[0].paragraphs == ("First paragraph.", "Second paragraph.")
    assert book.chapters[1].paragraphs == ("Another paragraph here.",)
    assert book.chapters[0].blocks == (
        {"type": "heading", "level": 1, "text": "Chapter One"},
        {"type": "paragraph", "text": "First paragraph."},
        {"type": "paragraph", "text": "Second paragraph."},
    )
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


def test_blocks_preserve_breaks_nested_blocks_and_drop_empty_content():
    chapter = _xhtml(
        "<hr/><h2>CHAPTER I.<br/>Down the Rabbit-Hole</h2>"
        "<p>One<br/>two <em>three</em>.</p>"
        "<blockquote><p>Quoted once.</p></blockquote>"
        "<li><p>Listed once.</p></li>"
        "<hr/><hr/>"
        "<p><br/></p><p>&#160;</p>"
        "<div>Direct <span>text</span>.</div><hr/>"
    )
    book = parse_epub(_build_epub(chap1=chapter, chap2=_xhtml("")))
    assert book.chapters[0].blocks == (
        {"type": "heading", "level": 2, "text": "CHAPTER I.\nDown the Rabbit-Hole"},
        {"type": "paragraph", "text": "One\ntwo three."},
        {"type": "paragraph", "text": "Quoted once."},
        {"type": "paragraph", "text": "Listed once."},
        {"type": "break"},
        {"type": "paragraph", "text": "Direct text."},
    )


def test_navigation_classifies_title_contents_and_cover_and_extracts_provenance():
    opf = (
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title>Alice</dc:title><dc:creator>Lewis Carroll</dc:creator>'
        '<dc:publisher>https://onemorelibrary.com</dc:publisher>'
        '<dc:rights>Public domain</dc:rights><dc:date>1865</dc:date></metadata>'
        '<manifest>'
        '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="toc" href="toc.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="c2" href="c2.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        '</manifest><spine toc="ncx">'
        '<itemref idref="cover"/><itemref idref="title"/><itemref idref="toc"/>'
        '<itemref idref="c1"/><itemref idref="c2"/></spine>'
        '<guide><reference type="cover" href="cover.xhtml"/><reference type="toc" href="toc.xhtml"/></guide>'
        '</package>'
    )
    files = {
        "OEBPS/cover.xhtml": _xhtml("<svg><image/></svg>"),
        "OEBPS/title.xhtml": _xhtml(
            "<p>https://onemorelibrary.com</p><h1>Alice</h1><p>by</p><p>Lewis Carroll</p>"
        ),
        "OEBPS/toc.xhtml": _xhtml(
            '<h2>Contents</h2><table><tr><td><a href="c1.xhtml">CHAPTER I. Down the Rabbit-Hole</a></td></tr>'
            '<tr><td><a href="c2.xhtml">CHAPTER II. The Pool of Tears</a></td></tr></table>'
        ),
        "OEBPS/c1.xhtml": _xhtml("<h2>CHAPTER I.<br/>Down the Rabbit-Hole</h2><p>First.</p>"),
        "OEBPS/c2.xhtml": _xhtml("<h2>CHAPTER II.<br/>The Pool of Tears</h2><p>Second.</p>"),
        "OEBPS/toc.ncx": (
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx"><navMap>'
            '<navPoint><navLabel><text>Contents</text></navLabel><content src="toc.xhtml"/></navPoint>'
            '<navPoint><navLabel><text>CHAPTER I. Down the Rabbit-Hole</text></navLabel><content src="c1.xhtml#x"/></navPoint>'
            '<navPoint><navLabel><text>CHAPTER II. The Pool of Tears</text></navLabel><content src="c2.xhtml"/></navPoint>'
            '</navMap></ncx>'
        ),
    }
    book = parse_epub(_build_epub(
        opf=opf,
        chap1=files["OEBPS/cover.xhtml"],
        chap2=files["OEBPS/title.xhtml"],
        extra_files=files,
    ))
    assert [chapter.title for chapter in book.chapters] == [
        "CHAPTER I. Down the Rabbit-Hole", "CHAPTER II. The Pool of Tears"
    ]
    assert book.chapters[0].blocks[0] == {
        "type": "heading", "level": 2, "text": "CHAPTER I.\nDown the Rabbit-Hole"
    }
    assert all("onemorelibrary" not in block.get("text", "") for chapter in book.chapters for block in chapter.blocks)
    assert book.provenance == {
        "source_url": "https://onemorelibrary.com", "publisher": "", "rights": "Public domain", "date": "1865"
    }


def test_pure_link_list_without_navigation_is_toc_and_classification_falls_back_to_text_documents():
    opf = _opf(
        manifest_extra='<item id="toc" href="toc.xhtml" media-type="application/xhtml+xml"/>',
    ).replace('<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>',
              '<spine><itemref idref="toc"/><itemref idref="chap1"/><itemref idref="chap2"/></spine>')
    toc = _xhtml('<p><a href="chap1.xhtml">One</a></p><p><a href="chap2.xhtml">Two</a></p>')
    book = parse_epub(_build_epub(
        opf=opf,
        chap1=_xhtml("<h1>One</h1><p>Only chapter one.</p>"),
        chap2=_xhtml("<h1>Two</h1><p>Only chapter two.</p>"),
        extra_files={"OEBPS/toc.xhtml": toc},
    ))
    assert len(book.chapters) == 2
    assert {"Only chapter one.", "Only chapter two."} == {
        paragraph for chapter in book.chapters for paragraph in chapter.paragraphs
    }


def test_epub3_nav_landmarks_keep_only_body_chapters():
    opf = _opf().replace(
        '<manifest>',
        '<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="titlepage" href="titlepage.xhtml" media-type="application/xhtml+xml"/>'
        '<item id="toc" href="toc.xhtml" media-type="application/xhtml+xml"/>',
    ).replace(
        '<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>',
        '<spine><itemref idref="titlepage"/><itemref idref="toc"/>'
        '<itemref idref="chap1"/><itemref idref="chap2"/></spine>',
    )
    nav = (
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>'
        '<nav epub:type="toc"><ol><li><a href="chap1.xhtml">First</a></li>'
        '<li><a href="chap2.xhtml">Second</a></li></ol></nav>'
        '<nav epub:type="landmarks"><ol><li><a epub:type="titlepage" href="titlepage.xhtml">Title</a></li>'
        '<li><a epub:type="toc" href="toc.xhtml">Contents</a></li>'
        '<li><a epub:type="bodymatter" href="chap1.xhtml">Start</a></li></ol></nav>'
        '</body></html>'
    )
    book = parse_epub(_build_epub(
        opf=opf,
        chap1=_xhtml("<h1>First body</h1><p>Body one.</p>"),
        chap2=_xhtml("<h1>Second body</h1><p>Body two.</p>"),
        extra_files={
            "OEBPS/nav.xhtml": nav,
            "OEBPS/titlepage.xhtml": _xhtml("<h1>Title</h1><p>Front.</p>"),
            "OEBPS/toc.xhtml": _xhtml("<h1>Contents</h1><p>Links.</p>"),
        },
    ))
    assert [chapter.title for chapter in book.chapters] == ["First", "Second"]


def test_classification_safety_net_keeps_text_when_every_document_is_excluded():
    opf = _opf().replace(
        '<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>',
        '<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>',
    )
    front = '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body epub:type="frontmatter"><p>Readable.</p></body></html>'
    book = parse_epub(_build_epub(opf=opf, chap1=front, chap2=front))
    assert len(book.chapters) == 2


def test_epub_without_navigation_keeps_text_documents_if_all_are_classified_away():
    chapter = _xhtml("<p>Readable.</p>")
    opf = _opf().replace('<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>',
                         '<spine><itemref idref="chap1"/><itemref idref="chap2"/></spine>')
    book = parse_epub(_build_epub(opf=opf, chap1=chapter, chap2=chapter))
    assert len(book.chapters) == 2


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
