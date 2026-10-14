"""Derive the Simplified-only / Traditional-only character table from the vendored CC-CEDICT pack.

`writing_coach/languages/chinese/script_detection.py` classifies a Chinese text as Simplified or
Traditional by counting characters that exist in only one script. CC-CEDICT lists, for every
single-character simplified headword, its traditional form(s); this script keeps

* `simplified`: a headword that differs from its traditional form and is never itself a traditional form or
  written identically in both scripts by some entry (so 后, 台, 干, which are also traditional characters, are out);
* `traditional`: a traditional form that is never itself a simplified headword that maps elsewhere.

Characters shared by both scripts carry no evidence and are not listed. Stdlib only, offline, deterministic.

    python scripts/build_chinese_script_table.py          # write script_chars.json
    python scripts/build_chinese_script_table.py --check  # fail when the file is stale
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from writing_coach.languages.chinese import lexicon  # noqa: E402

OUT = ROOT / "writing_coach" / "languages" / "chinese" / "script_chars.json"


def derive() -> dict[str, str]:
    pairs: dict[str, set[str]] = {}
    shared: set[str] = set()  # a headword some entry writes the same in both scripts (后, 台, 干)
    for char in lexicon._index()["offsets"]:
        if len(char) != 1:
            continue
        for entry in lexicon.lookup(char):
            if len(entry.traditional) != 1:
                continue
            if entry.traditional == char:
                shared.add(char)
            else:
                pairs.setdefault(char, set()).add(entry.traditional)
    simplified_heads = set(pairs)
    traditional_forms = {form for forms in pairs.values() for form in forms}
    return {
        "format": "orena.zh-script-chars.v1",
        "source": lexicon.provenance().get("release", ""),
        "simplified": "".join(sorted(simplified_heads - traditional_forms - shared)),
        "traditional": "".join(sorted(traditional_forms - simplified_heads - shared)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    table = derive()
    text = json.dumps(table, ensure_ascii=False, indent=0) + "\n"
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("script_chars.json is stale; run scripts/build_chinese_script_table.py")
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"simplified-only {len(table['simplified'])}, traditional-only {len(table['traditional'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
