"""Build the local English IPA table from CMUdict (D-202, PROPOSED).

Source: the official CMUdict (https://github.com/cmusphinx/cmudict, `cmudict.dict`, BSD-style licence, text in
`writing_coach/languages/english/CMUDICT-LICENSE.txt`). Download it into a scratch directory outside the repository
and pass it with --source; its SHA-256 must equal the pinned one. The first pronunciation of each word is kept,
keys are lowercase, entries whose key has a digit or a character other than a-z, apostrophe and hyphen are dropped.

    python scripts/build_english_ipa_table.py --source <dir>/cmudict.dict            # write cmudict_ipa.json.gz
    python scripts/build_english_ipa_table.py --source <dir>/cmudict.dict --check    # rebuild and compare
    python scripts/build_english_ipa_table.py --check                                # no source: verify metadata

Without --source, --check verifies the shipped table's metadata (pinned source hash and commit, converter
version); with --source it rebuilds and requires an identical table. Stdlib only, offline.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from writing_coach.languages.english import ipa  # noqa: E402

SOURCE_COMMIT = "74790861f652b15e4ac49015a90074ad62a27690"
SOURCE_COMMIT_DATE = "2025-10-24"
SOURCE_SHA256 = "81917843c7f44ce2b094ac63873c2c7a4cf802040792c455ba3ca406891c3d22"
OUT = ipa.TABLE_PATH
_KEY = re.compile(r"^[a-z][a-z'\-]*$")
_VARIANT = re.compile(r"\(\d+\)$")


def derive(source: Path) -> dict:
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"cmudict.dict hash {digest} does not match the pinned {SOURCE_SHA256}")
    table: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        head, _, rest = line.partition(" ")
        if _VARIANT.search(head):
            continue  # alternates: the first pronunciation wins
        key = head.lower()
        if not _KEY.match(key) or key in table:
            continue
        table[key] = ipa.arpabet_to_ipa(rest.split())
    return {
        "format": "orena.en-ipa.v1",
        "source": "CMUdict",
        "sourceUrl": "https://github.com/cmusphinx/cmudict",
        "sourceCommit": SOURCE_COMMIT,
        "sourceCommitDate": SOURCE_COMMIT_DATE,
        "sourceSha256": SOURCE_SHA256,
        "converter": ipa.CONVERTER_VERSION,
        "licence": "BSD-style (Carnegie Mellon University)",
        "notice": "Copyright (C) 1993-2015 Carnegie Mellon University. All rights reserved. See CMUDICT-LICENSE.txt",
        "entries": len(table),
        "ipa": dict(sorted(table.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check and not args.source:
        meta = ipa.metadata() if OUT.is_file() else {}
        if not (meta.get("sourceSha256") == SOURCE_SHA256 and meta.get("sourceCommit") == SOURCE_COMMIT
                and meta.get("converter") == ipa.CONVERTER_VERSION):
            print("cmudict_ipa.json.gz is stale or missing; run scripts/build_english_ipa_table.py --source ...")
            return 1
        return 0
    if not args.source:
        parser.error("--source is required to write the table")
    table = derive(args.source)
    data = json.dumps(table, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if args.check:
        current = gzip.decompress(OUT.read_bytes()) if OUT.is_file() else b""
        if current != data:
            print("cmudict_ipa.json.gz is stale; run scripts/build_english_ipa_table.py --source ...")
            return 1
        return 0
    OUT.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    print(f"{table['entries']} entries, {OUT.stat().st_size} bytes gzipped, {len(data)} bytes raw")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
