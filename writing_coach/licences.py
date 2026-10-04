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
            "The fonts' authors, via Google Fonts"),
    Dataset("nltk-tagger", "NLTK averaged perceptron tagger", "Apache 2.0",
            "https://www.apache.org/licenses/LICENSE-2.0", "https://www.nltk.org", "NLTK Project"),
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
        licence = _text(source.get("license"))
        if not licence:
            continue
        rows.append({
            "title": _text(getattr(entry, "title", "")),
            "creator": _text(getattr(entry, "creator", "")),
            "licence": licence,
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
    return [
        {
            "title": _text(source.get("name")),
            "creator": "",
            "licence": _text(source.get("license_note")),
            "source_url": _text(source.get("base_url")),
        }
        for source in sources
        if _text(source.get("state")) == "active" and source.get("can_republish") and _text(source.get("license_note"))
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
