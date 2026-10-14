"""Build the graded word tables the Reading level estimate (reading-level/3, D-199) reads.

Sources (downloaded once by a person, read here as untrusted data, never fetched by this script):

* CEFR-J Vocabulary Profile 1.5 (Tono Lab, TUFS): A1-B2. Free for research and commercial use with citation.
* Octanove Vocabulary Profile C1/C2 1.0 (Octanove Labs): C1-C2. CC BY-SA 4.0 - kept in its own file.
* HSK 3.0 word and character lists, as cleaned by ivankra/hsk30 (MIT) from the PRC Ministry of Education standard.

    python scripts/build_reading_level_tables.py --source-dir DIR   # write the three JSON files
    python scripts/build_reading_level_tables.py --check            # offline: validate the committed files
    python scripts/build_reading_level_tables.py --check --source-dir DIR   # also rebuild and compare

DIR holds `cefrj-vocabulary-profile-1.5.csv`, `octanove-vocabulary-profile-c1c2-1.0.csv`,
`hsk30-expanded.csv`, `hsk30-chars.csv`. Stdlib only, deterministic.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_DIR = ROOT / "writing_coach" / "languages" / "english"
ZH_DIR = ROOT / "writing_coach" / "languages" / "chinese"
CEFRJ_OUT = EN_DIR / "level_words_cefrj.json"
OCTANOVE_OUT = EN_DIR / "level_words_octanove_c1c2.json"
HSK_OUT = ZH_DIR / "level_words_hsk30.json"

_WORD = re.compile(r"^[a-z]+$")
_HAN = re.compile(r"^[㐀-鿿]+$")

CEFRJ = {
    "file": "cefrj-vocabulary-profile-1.5.csv",
    "levels": ("A1", "A2", "B1", "B2"),
    "meta": {
        "format": "orena.level-words.en.v1",
        "name": "CEFR-J Vocabulary Profile",
        "version": "1.5",
        "licence": "CEFR-J terms of use: research and commercial use without charge, with citation of the dataset",
        "copyright": "Tono Laboratory, Tokyo University of Foreign Studies (TUFS)",
        "citation": "The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies. http://www.cefr-j.org/download.html",
        "origin": "https://github.com/openlanguageprofiles/olp-en-cefrj (commit d4e45b75b38f27b30dfc5c44d8c571aec7e7092f)",
        "derivation": "single-word headwords, slash variants split, lower-cased; a headword listed at several levels keeps its lowest; phrases and non-ASCII variants dropped",
    },
}
OCTANOVE = {
    "file": "octanove-vocabulary-profile-c1c2-1.0.csv",
    "levels": ("C1", "C2"),
    "meta": {
        "format": "orena.level-words.en.v1",
        "name": "Octanove Vocabulary Profile C1/C2",
        "version": "1.0",
        "licence": "CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/) - ShareAlike applies to this file and to adaptations of it",
        "copyright": "Octanove Labs",
        "citation": "Octanove Vocabulary Profile C1/C2 1.0, Octanove Labs, distributed with the CEFR-J datasets by Open Language Profiles",
        "origin": "https://github.com/openlanguageprofiles/olp-en-cefrj (commit d4e45b75b38f27b30dfc5c44d8c571aec7e7092f)",
        "derivation": "same as the CEFR-J table; this file is a separate data file so the ShareAlike licence does not extend to code or to the CEFR-J table",
    },
}
HSK = {
    "files": ("hsk30-expanded.csv", "hsk30-chars.csv"),
    "meta": {
        "format": "orena.level-words.zh.v1",
        "name": "HSK 3.0 word and character lists (Simplified)",
        "licence": "MIT (ivankra/hsk30, Copyright (c) 2023 Ivan Krasilnikov, (c) 2021 Shawky); the underlying standard is a PRC Ministry of Education publication",
        "copyright": "ivankra/hsk30 data derives from elkmovie/hsk30 and shawkynasr/HSK-official-Query-System (both MIT) and the Ministry of Education of the PRC standard",
        "citation": "ivankra/hsk30, https://github.com/ivankra/hsk30 (commit 4ff9e3915ce87baaecd7ebe263085573a4ea3192)",
        "origin": "https://github.com/ivankra/hsk30; primary source http://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/s5987/202103/t20210329_523304.html",
        "derivation": "simplified headwords with variants expanded, only the level of each word and character is kept; a word listed at several levels keeps its lowest; level 7 is the advanced 7-9 band, beyond Orena's HSK6 scale",
        "note": "The ivankra README states the copyright claim on the data is questionable because the original is a government work; recorded here and in THIRD_PARTY_NOTICES.md.",
    },
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _en_words(spec: dict, source: Path, level_column: str = "CEFR") -> tuple[dict[str, str], str]:
    path = source / spec["file"]
    best: dict[str, int] = {}
    for row in _read(path):
        level = (row.get(level_column) or "").strip().upper()
        if level not in spec["levels"]:
            continue
        for variant in (row.get("headword") or "").split("/"):
            word = variant.strip().lower()
            if _WORD.match(word):
                rank = spec["levels"].index(level)
                best[word] = min(best.get(word, rank), rank)
    grouped = {level: " ".join(sorted(w for w, r in best.items() if r == i)) for i, level in enumerate(spec["levels"])}
    return grouped, _sha(path)


def build_english(source: Path) -> dict[Path, dict]:
    out = {}
    for spec, target in ((CEFRJ, CEFRJ_OUT), (OCTANOVE, OCTANOVE_OUT)):
        words, digest = _en_words(spec, source)
        out[target] = {**spec["meta"], "source_file": spec["file"], "source_sha256": digest, "levels": words}
    return out


def build_chinese(source: Path) -> dict[Path, dict]:
    words: dict[str, int] = {}
    for row in _read(source / "hsk30-expanded.csv"):
        word = (row.get("Simplified") or "").strip()
        level = (row.get("Level") or "").strip()
        if row.get("Example") or not _HAN.match(word):
            continue
        rank = 7 if level.startswith("7") else int(level)
        words[word] = min(words.get(word, rank), rank)
    chars: dict[str, int] = {}
    for row in _read(source / "hsk30-chars.csv"):
        char = (row.get("Hanzi") or "").strip()
        level = (row.get("Level") or "").strip()
        if _HAN.match(char) and len(char) == 1:
            chars[char] = 7 if level.startswith("7") else int(level)
    digests = {name: _sha(source / name) for name in HSK["files"]}
    return {
        HSK_OUT: {
            **HSK["meta"],
            "source_files": list(HSK["files"]),
            "source_sha256": digests,
            "words": {str(n): " ".join(sorted(w for w, r in words.items() if r == n)) for n in range(1, 8)},
            "chars": {str(n): "".join(sorted(c for c, r in chars.items() if r == n)) for n in range(1, 8)},
        }
    }


def build_all(source: Path) -> dict[Path, dict]:
    return {**build_english(source), **build_chinese(source)}


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def validate_committed() -> list[str]:
    problems = []
    for path, levels, min_words in ((CEFRJ_OUT, CEFRJ["levels"], 5000), (OCTANOVE_OUT, OCTANOVE["levels"], 1000)):
        if not path.exists():
            problems.append(f"missing {path.name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if tuple(data.get("levels", {})) != tuple(levels) and set(data.get("levels", {})) != set(levels):
            problems.append(f"{path.name}: levels differ")
        total = sum(len(v.split()) for v in data.get("levels", {}).values())
        if total < min_words:
            problems.append(f"{path.name}: only {total} words")
        for key in ("licence", "copyright", "citation", "origin", "source_sha256"):
            if not data.get(key):
                problems.append(f"{path.name}: missing {key}")
    if "CC BY-SA" not in json.loads(OCTANOVE_OUT.read_text(encoding="utf-8")).get("licence", ""):
        problems.append("octanove file must state its CC BY-SA licence")
    if not HSK_OUT.exists():
        problems.append(f"missing {HSK_OUT.name}")
    else:
        data = json.loads(HSK_OUT.read_text(encoding="utf-8"))
        if sum(len(v.split()) for v in data.get("words", {}).values()) < 10000:
            problems.append("hsk30 words: fewer than 10000")
        if sum(len(v) for v in data.get("chars", {}).values()) < 2900:
            problems.append("hsk30 chars: fewer than 2900")
        for key in ("licence", "citation", "origin", "source_sha256"):
            if not data.get(key):
                problems.append(f"{HSK_OUT.name}: missing {key}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    built = build_all(args.source_dir) if args.source_dir else {}
    if args.check:
        problems = validate_committed()
        for path, data in built.items():
            if not path.exists() or path.read_text(encoding="utf-8") != render(data):
                problems.append(f"{path.name} is stale against {args.source_dir}")
        if problems:
            print("\n".join(problems))
            return 1
        print("OK: level tables are valid" + (" and current against the source" if built else ""))
        return 0
    if not built:
        parser.error("--source-dir is required to write")
    for path, data in built.items():
        path.write_text(render(data), encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
