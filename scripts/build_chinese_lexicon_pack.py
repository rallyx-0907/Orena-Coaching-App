"""Build the vendored Chinese lexicon pack from CC-CEDICT and Unihan.

AI cost reduction plan P1 (`docs/ORENA_AI_COST_REDUCTION_PLAN.md`): word senses,
pinyin and character readings are dataset facts, so they are looked up, never
generated. This script converts the two upstream datasets into the container
format the stroke pack already uses:

    zh_lexicon.pack        concatenated zlib records, one per leading character
    zh_lexicon.index.json  character -> [offset, length] plus provenance

A record holds every CC-CEDICT entry whose simplified headword starts with that
character, plus that character's Unihan reading fields. Entry text is copied
through unchanged; only the container format differs (see lexicon_data/README.md
for the CC BY-SA 4.0 notice this conversion is published under).

Stdlib only: the operator Python has no project dependencies.

    python scripts/build_chinese_lexicon_pack.py                       # download + build
    python scripts/build_chinese_lexicon_pack.py --cedict F --unihan Z # build from files
    python scripts/build_chinese_lexicon_pack.py --check               # verify, write nothing
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "writing_coach" / "languages" / "chinese" / "lexicon_data"
INDEX_NAME = "zh_lexicon.index.json"
PACK_NAME = "zh_lexicon.pack"
FORMAT = "orena.zh-lexicon.v1"

# CC-CEDICT is published only as a rolling "latest" export; the build records
# the release date and digest it was made from, and --cedict rebuilds from a
# saved copy of exactly that release.
CEDICT_URL = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
UNIHAN_VERSION = "18.0.0"
UNIHAN_URL = f"https://www.unicode.org/Public/{UNIHAN_VERSION}/ucd/Unihan.zip"
UNIHAN_FIELDS = {"kMandarin": "m", "kVietnamese": "v", "kDefinition": "d"}

HAN = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF))
LINE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/\s*$")


def is_han(char: str) -> bool:
    point = ord(char)
    return any(low <= point <= high for low, high in HAN)


def fetch(url: str) -> bytes:
    print(f"Downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "orena-lexicon-build/1"})
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        return response.read()


def parse_cedict(raw: bytes) -> tuple[dict[str, str], dict[str, list[list]]]:
    text = gzip.decompress(raw).decode("utf-8") if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8")
    meta: dict[str, str] = {}
    words: dict[str, list[list]] = {}
    for line in text.splitlines():
        if line.startswith("#!"):
            key, _, value = line[2:].strip().partition("=")
            meta[key.strip()] = value.strip()
            continue
        if not line or line.startswith("#"):
            continue
        match = LINE.match(line)
        if not match:
            continue
        traditional, simplified, pinyin, senses = match.groups()
        if not is_han(simplified[0]):
            continue
        entry = [traditional, pinyin, [sense for sense in senses.split("/") if sense]]
        words.setdefault(simplified, []).append(entry)
    return meta, words


def parse_unihan(raw: bytes) -> dict[str, dict[str, str]]:
    chars: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = archive.read("Unihan_Readings.txt").decode("utf-8")
    for line in text.splitlines():
        if not line.startswith("U+"):
            continue
        code, field, value = line.split("\t", 2)
        short = UNIHAN_FIELDS.get(field)
        if short is None:
            continue
        char = chr(int(code[2:], 16))
        if is_han(char):
            chars.setdefault(char, {})[short] = value
    return chars


def build(cedict_raw: bytes, unihan_raw: bytes) -> tuple[dict, bytes]:
    meta, words = parse_cedict(cedict_raw)
    unihan = parse_unihan(unihan_raw)
    buckets: dict[str, dict] = {}
    for headword, entries in words.items():
        buckets.setdefault(headword[0], {"w": {}})["w"][headword] = entries
    # Character readings only for characters a headword uses: the long tail of
    # Unihan is characters no learner text contains.
    used = {char for headword in words for char in headword if is_han(char)}
    for char in sorted(used):
        if char in unihan:
            buckets.setdefault(char, {"w": {}})["c"] = unihan[char]

    pack = bytearray()
    offsets: dict[str, list[int]] = {}
    for char in sorted(buckets):
        blob = zlib.compress(
            json.dumps(buckets[char], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"),
            9,
        )
        offsets[char] = [len(pack), len(blob)]
        pack.extend(blob)
    index = {
        "format": FORMAT,
        "sources": {
            "cc_cedict": {
                "url": CEDICT_URL,
                "release_date": meta.get("date", ""),
                "declared_entries": meta.get("entries", ""),
                "license": meta.get("license", ""),
                "sha256": hashlib.sha256(cedict_raw).hexdigest(),
            },
            "unihan": {
                "url": UNIHAN_URL,
                "unicode_version": UNIHAN_VERSION,
                "fields": sorted(UNIHAN_FIELDS),
                "license": "https://www.unicode.org/license.txt",
                "sha256": hashlib.sha256(unihan_raw).hexdigest(),
            },
        },
        "headwords": len(words),
        "entries": sum(len(entries) for entries in words.values()),
        "characters_with_readings": sum(1 for bucket in buckets.values() if "c" in bucket),
        "pack_sha256": hashlib.sha256(bytes(pack)).hexdigest(),
        "offsets": offsets,
    }
    return index, bytes(pack)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cedict", type=Path, help="a saved cedict_1_0_ts_utf-8_mdbg.txt(.gz)")
    parser.add_argument("--unihan", type=Path, help="a saved Unihan.zip")
    parser.add_argument("--check", action="store_true", help="verify the committed pack against its index")
    args = parser.parse_args()

    index_path, pack_path = TARGET / INDEX_NAME, TARGET / PACK_NAME
    if args.check:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(pack_path.read_bytes()).hexdigest()
        if index.get("format") != FORMAT or digest != index.get("pack_sha256"):
            print("Lexicon pack does not match its index.", file=sys.stderr)
            return 1
        print(f"OK {index['headwords']} headwords, {len(index['offsets'])} records, {digest[:12]}")
        return 0

    cedict_raw = args.cedict.read_bytes() if args.cedict else fetch(CEDICT_URL)
    unihan_raw = args.unihan.read_bytes() if args.unihan else fetch(UNIHAN_URL)
    index, pack = build(cedict_raw, unihan_raw)
    TARGET.mkdir(parents=True, exist_ok=True)
    pack_path.write_bytes(pack)
    index_path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(
        f"Wrote {index['headwords']} headwords / {index['entries']} entries, "
        f"{index['characters_with_readings']} character readings, pack {len(pack) / 1e6:.2f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
