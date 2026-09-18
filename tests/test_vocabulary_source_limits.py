"""A vocabulary source is read and parsed within its limits, not after them.

The parser refused a source over MAX_SOURCE_BYTES or MAX_SOURCE_ROWS, but only
after the route had read the whole upload into memory and the parser had built
a row for every line - so an oversized file cost the memory the limit exists
to protect. These tests hold the limits small and count what is actually read.
"""
from __future__ import annotations

import asyncio
import csv
import json

import pytest

from writing_coach import vocabulary_source_import as source_import
from writing_coach.vocabulary_source_import import VocabularySourceError, parse_vocabulary_source


class _Upload:
    def __init__(self, size: int) -> None:
        self.remaining = size
        self.served = 0

    async def read(self, size: int = -1) -> bytes:
        take = self.remaining if size is None or size < 0 else min(size, self.remaining)
        self.remaining -= take
        self.served += take
        return b"a" * take


def test_an_upload_is_read_one_byte_past_the_limit_and_no_further(monkeypatch):
    monkeypatch.setattr(source_import, "MAX_SOURCE_BYTES", 1000)
    upload = _Upload(50_000)
    raw = asyncio.run(source_import.read_source_upload(upload))
    assert upload.served == 1001
    with pytest.raises(VocabularySourceError, match="too large"):
        parse_vocabulary_source("words.txt", raw)


def test_a_small_upload_is_read_whole(monkeypatch):
    upload = _Upload(300)
    assert len(asyncio.run(source_import.read_source_upload(upload))) == 300


def test_csv_rows_stop_being_read_at_the_limit(monkeypatch):
    monkeypatch.setattr(source_import, "MAX_SOURCE_ROWS", 10)
    yielded = []
    original = csv.DictReader

    class CountingReader(original):
        def __next__(self):
            row = super().__next__()
            yielded.append(row)
            return row

    monkeypatch.setattr(source_import.csv, "DictReader", CountingReader)
    text = "term,meaning\n" + "".join(f"w{index},m{index}\n" for index in range(5000))
    with pytest.raises(VocabularySourceError, match="too many rows"):
        parse_vocabulary_source("words.csv", text.encode())
    assert len(yielded) <= 11


def test_json_rows_are_refused_before_they_are_built(monkeypatch):
    monkeypatch.setattr(source_import, "MAX_SOURCE_ROWS", 10)

    class CountingList(list):
        visited = 0

        def __iter__(self):
            for item in super().__iter__():
                CountingList.visited += 1
                yield item

    with pytest.raises(VocabularySourceError, match="too many rows"):
        source_import._rows_from_json(CountingList(range(5000)))
    assert CountingList.visited <= 11


@pytest.mark.parametrize("name, body", [
    ("words.txt", lambda count: "".join(f"w{index}\n" for index in range(count))),
    ("words.csv", lambda count: "term\n" + "".join(f"w{index}\n" for index in range(count))),
    ("words.json", lambda count: json.dumps([f"w{index}" for index in range(count)])),
])
def test_exactly_the_limit_is_accepted_and_one_more_is_refused(monkeypatch, name, body):
    monkeypatch.setattr(source_import, "MAX_SOURCE_ROWS", 25)
    assert len(parse_vocabulary_source(name, body(25).encode()).rows) == 25
    with pytest.raises(VocabularySourceError, match="too many rows"):
        parse_vocabulary_source(name, body(26).encode())


def test_text_lines_split_as_before():
    # Every separator str.splitlines() honours still ends a term.
    text = "alpha\r\nbeta\rgamma\x0bdelta\x0cepsilon\x1czeta\x85eta\u2028theta\u2029iota\n\n  \nkappa"
    parsed = parse_vocabulary_source("words.txt", text.encode("utf-8"))
    assert [row["term"] for row in parsed.rows] == [
        "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    ]


def test_the_admin_routes_read_through_the_limited_reader():
    import inspect

    import app as app_module

    for route in (app_module._parse_uploaded_vocabulary_source, app_module.admin_vocabulary_source_import):
        source = inspect.getsource(route)
        assert "read_source_upload(" in source
        assert ".read()" not in source, "an unbounded read would hold the whole upload in memory"


def test_csv_io_is_still_utf8_only():
    with pytest.raises(VocabularySourceError):
        parse_vocabulary_source("words.csv", "term\ncafé\n".encode("latin-1"))
    assert parse_vocabulary_source("words.csv", "term\ncafé\n".encode("utf-8")).rows[0]["term"] == "café"
