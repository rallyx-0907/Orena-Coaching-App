"""Build the vendored English -> Vietnamese dictionary pack from English Wiktionary translation tables.

Source (D-246): the English Wiktionary's Vietnamese translations (`lang_code`/`code` == "vi") of its English entries,
as extracted by Wiktextract and published by kaikki.org - the per-language "English" dictionary file
(`kaikki.org-dictionary-English.jsonl[.gz]`), never the all-languages raw dump. Licence: CC BY-SA 4.0, the same
licence and attribution model as the vendored CC-CEDICT; the share-alike reaches this pack only, not Orena's code.
Vietnamese Wiktionary data and the Ho Ngoc Duc / FVDP dictionary are deliberately not used.

The input is streamed line by line (gzip or plain JSONL); it is never loaded whole. Output, in the container format
the Chinese lexicon pack uses:

    en_vi_lexicon.pack        concatenated zlib records, one per key prefix (first two characters, casefolded)
    en_vi_lexicon.index.json  prefix -> [offset, length], plus provenance, counts and the pack digest

A record decompresses to `{headword: [[pos, english_sense_label, [vietnamese, ...]], ...]}`. Within an entry, senses are
ordered common first (by how many languages its translation table translates that sense; ties keep the source order);
Vietnamese strings are trimmed, NFC-normalised (diacritics
kept), de-duplicated, and dropped when empty or not written in Vietnamese orthography. Nothing else is changed.

Deterministic: the same input file gives the same bytes (sorted keys, no timestamps), so this script is also the
update script. Stdlib only.

    python -I scripts/build_en_vi_pack.py --kaikki <kaikki.org-dictionary-English.jsonl.gz> --release 2026-10-03
    python -I scripts/build_en_vi_pack.py --check            # verify the committed pack, write nothing
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import unicodedata
import zlib
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import IO, Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "writing_coach" / "languages" / "english" / "vi_lexicon_data"
INDEX_NAME = "en_vi_lexicon.index.json"
PACK_NAME = "en_vi_lexicon.pack"
FORMAT = "orena.en-vi-lexicon.v1"
SOURCE_URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz"
PREFIX_LENGTH = 2
MAX_GLOSS_CHARS = 60
MAX_SENSE_CHARS = 120

# Vietnamese orthography (Quoc ngu) plus f, j, w, z for loanwords: a translation written with any other letter is
# another language's word in the wrong table, or a Han / Nom form, and is dropped.
_VI_LETTERS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
)
_VI_PUNCTUATION = set(" -'’.,0123456789")
# Translations so tagged are kept, after the current ones.
_DATED_TAGS = {"archaic", "obsolete", "dated", "historical", "rare"}
_ENGLISH_OR = re.compile(r"\s+or\s+")


def is_vietnamese(text: str) -> bool:
    """True when every character is Vietnamese orthography (or a space, hyphen, apostrophe, digit) and one is a letter."""

    letters = 0
    for char in text.casefold():
        if char in _VI_LETTERS:
            letters += 1
        elif char not in _VI_PUNCTUATION:
            return False
    return letters > 0


def clean_text(value: Any, limit: int) -> str:
    text = " ".join(unicodedata.normalize("NFC", str(value or "")).split()).strip(" ,;")
    return text if len(text) <= limit else ""


def headword_key(word: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(word or "")).split())


def prefix_of(word: str) -> str:
    return headword_key(word).casefold()[:PREFIX_LENGTH]


def open_input(path: Path) -> IO[str]:
    with path.open("rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _translations(entry: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Every translation item of an entry: the entry-level table and any per-sense tables (both shapes exist)."""

    for item in entry.get("translations") or []:
        if isinstance(item, dict):
            yield item
    for sense in entry.get("senses") or []:
        if isinstance(sense, dict):
            for item in sense.get("translations") or []:
                if isinstance(item, dict):
                    yield item


def entry_senses(entry: dict[str, Any]) -> list[list[Any]]:
    """The entry's Vietnamese translations grouped by English sense label, in source order."""

    groups: dict[str, list[tuple[bool, str]]] = {}
    languages: dict[str, set[str]] = {}
    for item in _translations(entry):
        code = str(item.get("lang_code") or item.get("code") or "")
        languages.setdefault(clean_text(item.get("sense"), MAX_SENSE_CHARS), set()).add(code)
        if code != "vi":
            continue
        sense = clean_text(item.get("sense"), MAX_SENSE_CHARS)
        dated = bool(_DATED_TAGS.intersection(str(tag).casefold() for tag in item.get("tags") or []))
        # A cell listing spelling alternatives with an English "or" ("anh or anh trai") is one gloss per alternative.
        for part in _ENGLISH_OR.split(str(item.get("word") or "")):
            vi = clean_text(part, MAX_GLOSS_CHARS)
            if vi and is_vietnamese(vi):
                groups.setdefault(sense, []).append((dated, vi))
    senses: list[list[Any]] = []
    pos = str(entry.get("pos") or "").strip().casefold()
    for sense, items in groups.items():
        ordered = [vi for _dated, vi in sorted(items, key=lambda pair: pair[0])]  # stable: current first
        unique = list(dict.fromkeys(ordered))
        if unique:
            senses.append([pos, sense, unique])
    # The common sense first: Wiktionary's own sense order puts some rare senses first ("provide": "to earn money for
    # necessities"), so senses are ordered by how many languages translate them - a sense every table translates is
    # the one learners meet. Ties keep the source order (a stable sort).
    senses.sort(key=lambda row: -len(languages.get(row[1], ())))
    return senses


def collect(lines: Iterable[str]) -> dict[str, list[list[Any]]]:
    """headword -> senses, merged across the headword's entries (one per part of speech / etymology) in source order."""

    words: dict[str, list[list[Any]]] = {}
    for line in lines:
        if '"vi"' not in line:
            continue  # cheap pre-filter: no Vietnamese translation on this line
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("lang_code") not in (None, "en"):
            continue
        word = headword_key(entry.get("word"))
        if not word:
            continue
        senses = entry_senses(entry)
        if not senses:
            continue
        merged = words.setdefault(word, [])
        for pos, sense, glosses in senses:
            same = next((row for row in merged if row[0] == pos and row[1] == sense), None)
            if same is None:
                merged.append([pos, sense, glosses])
            else:
                same[2] = list(dict.fromkeys(same[2] + glosses))
    return words


def build(words: dict[str, list[list[Any]]], *, sha256: str, release: str, input_name: str) -> tuple[dict, bytes]:
    buckets: dict[str, dict[str, list[list[Any]]]] = {}
    for word in sorted(words):
        buckets.setdefault(prefix_of(word), {})[word] = words[word]
    pack = bytearray()
    offsets: dict[str, list[int]] = {}
    for prefix in sorted(buckets):
        blob = zlib.compress(
            json.dumps(buckets[prefix], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"), 9
        )
        offsets[prefix] = [len(pack), len(blob)]
        pack.extend(blob)
    index = {
        "format": FORMAT,
        "sources": {
            "wiktionary_en": {
                "url": SOURCE_URL,
                "input": input_name,
                "release": release,
                "license": "CC BY-SA 4.0",
                "attribution": "Wiktionary contributors; extraction by Tatu Ylonen's Wiktextract (kaikki.org)",
                "sha256": sha256,
            },
        },
        "headwords": len(words),
        "senses": sum(len(senses) for senses in words.values()),
        "pairs": sum(len(glosses) for senses in words.values() for _p, _s, glosses in senses),
        "pack_sha256": hashlib.sha256(bytes(pack)).hexdigest(),
        "offsets": offsets,
    }
    return index, bytes(pack)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(target: Path, index: dict, pack: bytes) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / PACK_NAME).write_bytes(pack)
    (target / INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8", newline="\n"
    )


def check(target: Path) -> int:
    index = json.loads((target / INDEX_NAME).read_text(encoding="utf-8"))
    digest = hashlib.sha256((target / PACK_NAME).read_bytes()).hexdigest()
    if index.get("format") != FORMAT or digest != index.get("pack_sha256"):
        print("EN->VI pack does not match its index.", file=sys.stderr)
        return 1
    print(f"OK {index['headwords']} headwords, {index['pairs']} pairs, {len(index['offsets'])} records, {digest[:12]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kaikki", type=Path, help="kaikki.org-dictionary-English.jsonl or .jsonl.gz")
    parser.add_argument("--release", default="", help="the kaikki extraction date (from its download page)")
    parser.add_argument("--out", type=Path, default=TARGET, help="output directory (default: the vendored location)")
    parser.add_argument("--check", action="store_true", help="verify the committed pack against its index")
    args = parser.parse_args(argv)

    if args.check:
        return check(args.out)
    if not args.kaikki:
        parser.error("--kaikki is required to build")
    with open_input(args.kaikki) as handle:
        words = collect(handle)
    index, pack = build(words, sha256=file_sha256(args.kaikki), release=args.release, input_name=args.kaikki.name)
    write(args.out, index, pack)
    print(
        f"Wrote {index['headwords']} headwords / {index['senses']} senses / {index['pairs']} pairs, "
        f"{len(index['offsets'])} records, pack {len(pack) / 1e6:.2f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
