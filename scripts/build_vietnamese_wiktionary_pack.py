"""Build the vendored Vietnamese gloss pack (D-124) - only the entries Orena's word lists need.

Sources (open data, no model):

- open-dsl-dict `en-vi-enwiktionary` (English Wiktionary translation tables; CC BY-SA 3.0 / GFDL),
- Vietnamese Wiktionary via kaikki.org (`vi-extract.jsonl.gz`; CC BY-SA 4.0): English entries'
  Vietnamese glosses, and Vietnamese entries' English translations indexed back.

The full extracts stay outside the repository. The pack keeps only the English keys needed by
the starter collections (their English words, and the English CC-CEDICT senses of their Chinese
words) plus `localization_data/needed_words.txt` (words met elsewhere: imported collections,
saved words). Rebuild it with the saved upstream files whenever that list grows.

    vi_glosses.json.gz  {"format", "sources", "needed", "opendsl": {key: [[pos, sense, gloss], ...]},
                         "viwikt": {key: [[pos, gloss], ...]}, "viwikt_reverse": {key: [[pos, vi], ...]}}

Glosses keep at most two comma items of at most six words; longer text is a definition, not a
card meaning, and is dropped. Stdlib only.

    python scripts/build_vietnamese_wiktionary_pack.py --vi-extract F --opendsl G
    python scripts/build_vietnamese_wiktionary_pack.py --check
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGET = ROOT / "writing_coach" / "localization_data"
PACK = TARGET / "vi_glosses.json.gz"
NEEDED = TARGET / "needed_words.txt"
FORMAT = "orena.vi-glosses.v2"
VI_URL = "https://kaikki.org/dictionary/downloads/vi/vi-extract.jsonl.gz"
VI_RELEASE = "viwiktionary via kaikki.org Wiktextract extraction of 2026-09-28"
DSL_URL = "https://raw.githubusercontent.com/open-dsl-dict/wiktionary-dict/master/dsl/oneway/en-vi-enwiktionary.dsl.dz"
DSL_RELEASE = "open-dsl-dict wiktionary-dict, last updated 2015-04-25"
POS = {"noun": "noun", "verb": "verb", "adj": "adj", "adv": "adv", "name": "name", "phrase": "phrase",
       "intj": "intj", "prep": "prep", "pron": "pron", "num": "num", "conj": "conj"}
DSL_POS = {"n": "noun", "v": "verb", "adj": "adj", "adv": "adv", "prop": "name", "prep": "prep", "pron": "pron",
           "conj": "conj", "interj": "intj", "num": "num", "phrase": "phrase"}
MAX_WORDS = 6
PAREN = re.compile(r"\([^)]*\)")


def short_gloss(raw: str) -> str:
    text = re.sub(r"\s+", " ", PAREN.sub("", raw)).strip().strip(".;:!").strip()
    items = [item.strip() for item in re.split(r"[,;]", text) if item.strip()][:2]
    if not items or any(len(item.split()) > MAX_WORDS for item in items):
        return ""
    gloss = ", ".join(items)
    # Sentence-case a common gloss; a name ("Trung Quốc") keeps its capitals.
    return gloss[:1].lower() + gloss[1:] if not any(ch.isupper() for ch in gloss[1:]) else gloss


def english_keys(text: str) -> set[str]:
    word = " ".join(str(text or "").split())
    if word.startswith("to "):
        word = word[3:].strip()
    return {word, word.casefold()} if word else set()


def needed_keys() -> set[str]:
    """English keys the starter collections and the needed-words list can ask for."""

    from writing_coach.languages.chinese import lexicon

    keys: set[str] = set()
    zh_words: list[str] = []
    for language, folder in (("en", "english"), ("zh", "chinese")):
        data = json.loads((ROOT / "writing_coach" / "languages" / folder / "vocabulary_collections.json").read_text(encoding="utf-8"))
        for collection in data if isinstance(data, list) else data.get("collections", []):
            for entry in collection["entries"]:
                if language == "en":
                    keys |= english_keys(entry["word"])
                else:
                    zh_words.append(entry["word"])
    if NEEDED.exists():
        for line in NEEDED.read_text(encoding="utf-8").splitlines():
            language, _, word = line.strip().partition("|")
            if language == "en":
                keys |= english_keys(word)
            elif language == "zh":
                zh_words.append(word)
    for word in zh_words:
        for entry in lexicon.lookup(word):
            for sense in lexicon.meaning_senses(entry):
                for part in sense.split(";"):
                    keys |= english_keys(part)
    return keys


def build(vi_raw: bytes, dsl_raw: bytes, keys: set[str]) -> dict:
    opendsl: dict[str, list[list[str]]] = {}
    text = gzip.decompress(dsl_raw).decode("utf-16")
    head, pos, sense = None, "", ""
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if not line.startswith(("\t", " ")):
            head, pos, sense = line.strip(), "", ""
            continue
        m = re.search(r"\[p\]<([^>]+)>\[/p\]", line)
        if m:
            pos = DSL_POS.get(m.group(1).strip(), "")
            s = re.search(r"\[i\]\((.*)\)\[/i\]", line)
            sense = s.group(1).strip() if s else ""
        m = re.search(r"\[m1\](.*?)\[/m\]", line)
        if m and head in keys:
            gloss = short_gloss(re.sub(r"\[/?[a-z0-9 ]+\]", "", m.group(1)))
            if gloss:
                opendsl.setdefault(head, []).append([pos, sense, gloss])
    viwikt: dict[str, list[list[str]]] = {}
    reverse: dict[str, list[list[str]]] = {}
    with gzip.open(io.BytesIO(vi_raw), "rt", encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            code = entry.get("lang_code")
            p = POS.get(entry.get("pos") or "", "")
            if code == "en":
                word = str(entry.get("word") or "").strip()
                if word not in keys:
                    continue
                for s in entry.get("senses") or []:
                    glosses = s.get("glosses") or []
                    gloss = short_gloss(glosses[0]) if glosses else ""
                    if gloss and [p, gloss] not in viwikt.get(word, []):
                        viwikt.setdefault(word, []).append([p, gloss])
            elif code == "vi":
                headword = str(entry.get("word") or "").strip()
                for item in entry.get("translations") or []:
                    target = str(item.get("word") or "").strip()
                    if item.get("lang_code") == "en" and target in keys and headword and [p, headword] not in reverse.get(target, []):
                        reverse.setdefault(target, []).append([p, headword])
    return {
        "format": FORMAT,
        "sources": {
            "opendsl": {"url": DSL_URL, "release": DSL_RELEASE, "license": "CC BY-SA 3.0 / GFDL",
                        "sha256": hashlib.sha256(dsl_raw).hexdigest()},
            "viwikt": {"url": VI_URL, "release": VI_RELEASE, "license": "CC BY-SA 4.0 (also GFDL)",
                       "sha256": hashlib.sha256(vi_raw).hexdigest()},
        },
        "needed": len(keys),
        "opendsl": opendsl,
        "viwikt": viwikt,
        "viwikt_reverse": reverse,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vi-extract", type=Path, help="a saved vi-extract.jsonl.gz")
    parser.add_argument("--opendsl", type=Path, help="a saved en-vi-enwiktionary.dsl.dz")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        data = json.loads(gzip.decompress(PACK.read_bytes()))
        if data.get("format") != FORMAT:
            print("Unexpected pack format.", file=sys.stderr)
            return 1
        print(f"OK {data['needed']} needed keys; opendsl {len(data['opendsl'])}, viwikt {len(data['viwikt'])}, reverse {len(data['viwikt_reverse'])}")
        return 0
    if not args.vi_extract or not args.opendsl:
        parser.error("--vi-extract and --opendsl are required to build (the full extracts stay outside the repository)")
    data = build(args.vi_extract.read_bytes(), args.opendsl.read_bytes(), needed_keys())
    TARGET.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    PACK.write_bytes(gzip.compress(blob, compresslevel=9, mtime=0))
    print(f"Wrote {data['needed']} needed keys: opendsl {len(data['opendsl'])}, viwikt {len(data['viwikt'])}, "
          f"reverse {len(data['viwikt_reverse'])}; {PACK.stat().st_size / 1e3:.1f} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
