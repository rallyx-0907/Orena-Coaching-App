"""Licences and data sources: what Orena shows a learner, and under which terms.

One registry for the vendored datasets and bundled assets, shared by the learner-facing
licences page (`GET /api/licences`) and `THIRD_PARTY_NOTICES.md` (a test keeps them in step),
plus the per-item credits that live with content: each stored word recording, each listening
source, each registered reading source and each book. Read-only; no provider.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from writing_coach.reading_provenance import host_name


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    licence: str
    licence_url: str
    source_url: str
    attribution: str


DATASETS: tuple[Dataset, ...] = (
    Dataset("cc-cedict", "CC-CEDICT", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/",
            "https://www.mdbg.net/chinese/dictionary?page=cc-cedict",
            "MDBG and CC-CEDICT contributors; CEDICT © 1997, 1998 Paul Andrew Denisowski"),
    Dataset("unihan", "Unicode Unihan database", "Unicode License v3", "https://www.unicode.org/license.txt",
            "https://www.unicode.org/reports/tr38/", "© Unicode, Inc."),
    Dataset("make-me-a-hanzi", "Make Me a Hanzi (hanzi-writer-data 2.0.1)", "Arphic Public License",
            "https://github.com/skishore/makemeahanzi/blob/master/APL/ARPHICPL.TXT",
            "https://github.com/skishore/makemeahanzi", "Shaunak Kishore; Arphic Technology Co., Ltd."),
    Dataset("open-dsl-dict", "open-dsl-dict en-vi (from English Wiktionary)", "CC BY-SA 3.0 / GFDL",
            "https://creativecommons.org/licenses/by-sa/3.0/", "https://github.com/open-dsl-dict/wiktionary-dict",
            "Wiktionary contributors; Open DSL Dictionary Project"),
    Dataset("wiktionary-vi", "Vietnamese Wiktionary via kaikki.org", "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/", "https://kaikki.org/dictionary/rawdata.html",
            "Wiktionary contributors; extraction by Wiktextract (kaikki.org)"),
    Dataset("lucide", "Lucide icons (lucide-static 0.525.0)", "ISC", "https://lucide.dev/license",
            "https://lucide.dev", "Lucide contributors"),
    Dataset("google-fonts",
            "Fonts: Fredoka, Outfit, Plus Jakarta Sans, Literata, JetBrains Mono, Noto Sans SC, Noto Serif SC",
            "SIL Open Font License 1.1", "https://openfontlicense.org", "https://fonts.google.com",
            "The fonts' authors; served from Orena, not from Google"),
    Dataset("nltk-tagger", "NLTK averaged perceptron tagger", "Apache 2.0",
            "https://www.apache.org/licenses/LICENSE-2.0", "https://www.nltk.org", "NLTK Project"),
    Dataset("cefrj-vocabulary", "CEFR-J Vocabulary Profile 1.5 (English word levels A1-B2)",
            "Free for research and commercial use with citation",
            "https://github.com/openlanguageprofiles/olp-en-cefrj/blob/master/README.md",
            "https://github.com/openlanguageprofiles/olp-en-cefrj",
            "Tono Laboratory, Tokyo University of Foreign Studies (TUFS); The CEFR-J Wordlist Version 1.5, compiled by Yukio Tono"),
    Dataset("octanove-vocabulary", "Octanove Vocabulary Profile C1/C2 1.0 (English word levels C1-C2)", "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/", "https://github.com/openlanguageprofiles/olp-en-cefrj",
            "Octanove Labs, distributed with the CEFR-J datasets by Open Language Profiles"),
    Dataset("hsk30-vocabulary", "HSK 3.0 word and character levels (ivankra/hsk30)", "MIT",
            "https://github.com/ivankra/hsk30/blob/main/LICENSE", "https://github.com/ivankra/hsk30",
            "Ivan Krasilnikov and Shawky; derived from the PRC Ministry of Education HSK 3.0 standard"),
    Dataset("cmudict", "CMUdict (English pronunciations, converted to IPA)", "BSD-style (Carnegie Mellon University)",
            "https://github.com/cmusphinx/cmudict/blob/master/LICENSE", "https://github.com/cmusphinx/cmudict",
            "Copyright (C) 1993-2015 Carnegie Mellon University. All rights reserved."),
)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def word_audio_credits(records: Iterable[Any]) -> list[dict[str, str]]:
    """One row per stored recording: its file, author and licence (Wikimedia Commons et al.)."""

    rows = []
    for record in records:
        rows.append({
            "source": _text(getattr(record, "source", "")),
            "licence": _text(getattr(record, "licence", "")),
            "attribution": _text(getattr(record, "attribution", "")),
            "reading": _text(getattr(record, "reading", "")),
            "voice": _text(getattr(record, "voice", "")),
        })
    return [row for row in rows if row["source"] or row["attribution"]]


def media_credits(entries: Iterable[Any]) -> list[dict[str, str]]:
    rows = []
    for entry in entries:
        source = getattr(entry, "source", None) or {}
        if not isinstance(source, Mapping):
            source = {}
        licence = _text(source.get("license_name") or source.get("license"))
        if not licence:
            continue
        rows.append({
            "title": _text(getattr(entry, "title", "")),
            "creator": _text(getattr(entry, "creator", "")),
            "licence": licence,
            "licence_url": _text(source.get("license_url")),
            "source_url": _text(source.get("provenance_url") or getattr(entry, "canonical_url", "")),
        })
    return rows


def listening_catalog_credits(lessons: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    rows = []
    for lesson in lessons:
        source = lesson.get("source") if isinstance(lesson.get("source"), Mapping) else {}
        if not source or not _text(source.get("license")):
            continue
        rows.append({
            "title": _text(source.get("title") or lesson.get("title")),
            "creator": _text(source.get("creator")),
            "licence": _text(source.get("license")),
            "source_url": _text(source.get("provenance_url") or source.get("source_url")),
        })
    return rows


def reading_source_credits(sources: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """The licence page names a source by its public name, else its host; the internal
    name is administrator bookkeeping and never published. A source with neither is left out of this
    list (its texts are still credited one by one in `reading_text_credits`) (D-192, proposed)."""
    rows = []
    for source in sources:
        # The registry returns the rights nested under `rights`; a flat mapping is accepted too.
        rights = source.get("rights") if isinstance(source.get("rights"), Mapping) else source
        if not (_text(source.get("state")) == "active" and rights.get("can_republish") and _text(rights.get("license_note"))):
            continue
        title = _text(source.get("public_name")) or host_name(source.get("base_url"))
        if title:
            rows.append({"title": title, "creator": "", "licence": _text(rights.get("license_note")),
                         "source_url": _text(source.get("base_url"))})
    return rows


def reading_text_credits(texts: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """One row per published text whose rights carry a licence note: who credits it (the publisher, with the
    author when they differ, D-189), the terms and the original address."""

    def creator(text: Mapping[str, Any]) -> str:
        publisher, author = _text(text.get("source_name")), _text(text.get("author"))
        if publisher and author and publisher.casefold() != author.casefold():
            return f"{publisher} ({author})"
        return publisher or author

    return [
        {
            "title": _text(text.get("title")),
            "creator": creator(text),
            "licence": _text(text.get("license_note")),
            "source_url": _text(text.get("source_url")),
        }
        for text in texts
        if _text(text.get("license_note"))
    ]


def book_credits(books: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {"title": _text(book.get("title")), "creator": _text(book.get("author")),
         "licence": _text(book.get("source_kind")), "source_url": ""}
        for book in books
        if _text(book.get("status")) == "published"
    ]


def licences_payload(
    *,
    word_audio: Callable[[], Iterable[Any]] | None = None,
    media: Callable[[], Iterable[Any]] | None = None,
    listening: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
    reading_sources: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
    reading_texts: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
    books: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """The page's data. A part whose owner is unavailable is an empty list, never an error."""

    def safe(read: Callable[[], Iterable[Any]] | None, shape: Callable[[Iterable[Any]], list]) -> list:
        if read is None:
            return []
        try:
            return shape(read())
        except Exception:  # noqa: BLE001 - a missing owner hides its rows, never the page
            return []

    content = (
        safe(listening, listening_catalog_credits)
        + safe(media, media_credits)
        + safe(reading_sources, reading_source_credits)
        + safe(reading_texts, reading_text_credits)
        + safe(books, book_credits)
    )
    # Two lessons cut from one source are one credit.
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in content:
        unique.setdefault((row["title"], row["source_url"]), row)
    return {
        "datasets": [asdict(dataset) for dataset in DATASETS],
        "content": list(unique.values()),
        "audio": safe(word_audio, word_audio_credits),
    }
