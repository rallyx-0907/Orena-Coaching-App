"""Derive the Simplified-only / Traditional-only character table from the vendored CC-CEDICT pack.

`writing_coach/languages/chinese/script_detection.py` classifies a Chinese text as Simplified or
Traditional by counting characters that exist in only one script. CC-CEDICT lists, for every
single-character simplified headword, its traditional form(s); this script keeps

* `simplified`: a headword that differs from its traditional form and is never itself a traditional form or
  written identically in both scripts by some entry (so 后, 台, 干, which are also traditional characters, are out);
* `traditional`: a traditional form that is never itself a simplified headword that maps elsewhere.

Characters shared by both scripts carry no evidence and are not listed. Stdlib only, offline, deterministic.

    python scripts/build_chinese_script_table.py          # write script_chars.json and script_map.json
    python scripts/build_chinese_script_table.py --check  # fail when a file is stale or a known survivor is not converted
    python scripts/build_chinese_script_table.py --unihan-zip Unihan.zip  # refresh the vendored Unihan extract first

Where CC-CEDICT is ambiguous in the Traditional to Simplified direction (麼 is the traditional form of 么 and of the
variant 麽; 乾, 著, 徵, 餘, 覆 have several Simplified forms or are still Simplified characters in some words), the
Unicode Unihan `kSimplifiedVariant` field supplies the Simplified candidates and CC-CEDICT supplies the evidence for a
context-dependent choice (D-211; `derive_variant_maps`).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from writing_coach.languages.chinese import lexicon  # noqa: E402

OUT = ROOT / "writing_coach" / "languages" / "chinese" / "script_chars.json"
MAP_OUT = ROOT / "writing_coach" / "languages" / "chinese" / "script_map.json"
VARIANTS_PATH = ROOT / "writing_coach" / "languages" / "chinese" / "lexicon_data" / "unihan_simplified_variants.json"
VARIANTS_FORMAT = "orena.zh-unihan-simplified-variants.v1"
MAP_FORMAT = "orena.zh-script-map.v2"

# A target must be in the original unified-ideograph block (U+4E00 to U+9FA5, Unicode 1.1): every CJK font carries it,
# so a conversion never produces a missing glyph (the 2000s additions U+9FA6 and up are skipped).
BASIC_BLOCK = (0x4E00, 0x9FA5)
# Unihan variants that are not the standard Simplified form (D-211 review): converting them would write a character a
# reader of Simplified does not expect. Left as written.
EXCLUDED = {
    "諮": "Unihan gives 谘; the standard form in 咨询 is 咨",
    "讎": "Unihan gives 雠; the standard form for 仇 is 仇",
}
KEEP_WORD_MAX = 4  # the longest word a context-dependent character is protected inside

# Real survivors of the 2026-10-15 mini trial (VOA) and the words that must stay as written, with the Simplified each
# must become. `--check` fails when one differs.
EXPECTED = {
    "什麼": "什么", "那麼": "那么", "怎麼": "怎么", "鼓勵": "鼓励", "剩餘": "剩余", "乾淨": "干净",
    "徵求": "征求", "特徵": "特征", "看著": "看着", "回覆": "回复",
    "著名": "著名", "顯著": "显著", "乾坤": "乾坤", "乾隆": "乾隆", "覆蓋": "覆盖", "顛覆": "颠覆",
}


def derive(pairs_out: dict[str, set[str]] | None = None) -> dict[str, str]:
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
    if pairs_out is not None:
        pairs_out.update(pairs)
    simplified_heads = set(pairs)
    traditional_forms = {form for forms in pairs.values() for form in forms}
    return {
        "format": "orena.zh-script-chars.v1",
        "source": "CC-CEDICT",
        "release": lexicon.provenance().get("release", ""),
        "licence": "CC BY-SA 4.0",
        "notice": "Derived from CC-CEDICT (MDBG and contributors; CEDICT (c) 1997, 1998 Paul Andrew Denisowski), see lexicon_data/",
        "simplified": "".join(sorted(simplified_heads - traditional_forms - shared)),
        "traditional": "".join(sorted(traditional_forms - simplified_heads - shared)),
    }


def parse_variants(raw: bytes) -> dict[str, object]:
    """The `kSimplifiedVariant` field of `Unihan_Variants.txt` inside `Unihan.zip`, as the vendored extract."""
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        text = archive.read("Unihan_Variants.txt").decode("utf-8")
    variants: dict[str, str] = {}
    date = version = ""
    for line in text.splitlines():
        if line.startswith("# Date:"):
            date = line.split(":", 1)[1].strip().split(" ")[0]
        elif line.startswith("# Unicode Version"):
            version = line.rsplit(" ", 1)[1]
        if line.startswith("#") or "\tkSimplifiedVariant\t" not in line:
            continue
        code, _field, value = line.split("\t")
        variants[chr(int(code[2:], 16))] = "".join(chr(int(item[2:].split("<")[0], 16)) for item in value.split())
    return {
        "format": VARIANTS_FORMAT,
        "source": "Unicode Unihan, Unihan_Variants.txt",
        "field": "kSimplifiedVariant",
        "unicode_version": version,
        "file_date": date,
        "zip_sha256": hashlib.sha256(raw).hexdigest(),
        "licence": "Unicode License v3",
        "notice": "(c) Unicode, Inc. Only the kSimplifiedVariant field is kept; see lexicon_data/UNICODE-LICENSE.txt.",
        "variants": dict(sorted(variants.items())),
    }


def load_variants() -> dict[str, str]:
    data = json.loads(VARIANTS_PATH.read_text(encoding="utf-8"))
    if data.get("format") != VARIANTS_FORMAT:
        raise SystemExit(f"{VARIANTS_PATH.name} is not {VARIANTS_FORMAT}")
    return dict(data["variants"])


# A CC-CEDICT entry that only points at another word ("variant of 借口") is not a standard Simplified word: 藉口 is
# kept as a spelling of 借口 in the dictionary, not as Simplified text, so it must not protect 藉 from conversion.
_VARIANT_SENSE = re.compile(r"^(old |archaic |erhua |Japanese |Korean |\(\w+\) )*variant (Chinese character )?of ", re.IGNORECASE)


def _cedict_evidence(chars: set[str]) -> tuple[set[str], dict[tuple[str, str], int], dict[str, set[str]], set[str]]:
    """From every CC-CEDICT entry: the characters used in Simplified headwords; how often a wanted Traditional
    character is written as a given Simplified one at the same position (equal-length entries only); and, for each
    wanted character, the short Simplified words that contain it."""
    simplified_used: set[str] = set()
    aligned: dict[tuple[str, str], int] = {}
    words: dict[str, set[str]] = {}
    headwords: set[str] = set()
    for first in sorted(lexicon._index()["offsets"]):
        for word, rows in sorted((lexicon._record(first).get("w") or {}).items()):
            standard = any(not all(_VARIANT_SENSE.match(str(sense)) for sense in senses) for _t, _p, senses in rows)
            if standard:
                headwords.add(word)
                simplified_used.update(word)
                if 2 <= len(word) <= KEEP_WORD_MAX:
                    for char in set(word) & chars:
                        words.setdefault(char, set()).add(word)
            for traditional, _pinyin, _senses in rows:
                if len(traditional) != len(word):
                    continue
                for t, s in zip(traditional, word, strict=True):
                    if t != s and t in chars:
                        aligned[(t, s)] = aligned.get((t, s), 0) + 1
    return simplified_used, aligned, words, headwords


def derive_variant_maps(base: dict[str, str]) -> tuple[dict[str, str], dict[str, dict[str, object]], list[str]]:
    """What Unihan adds to the one-to-one CC-CEDICT table, for zh-Hans output.

    `unique`: a Traditional character for which Unihan names exactly one Simplified form (in the basic block, other
    than itself) and that no CC-CEDICT Simplified word uses as written. It is converted everywhere (麼 -> 么).
    `contextual`: Unihan names several Simplified forms, or the character is still a Simplified character in some
    words (著 in 著名, 乾 in 乾坤, 覆 in 覆盖). The default form is the one CC-CEDICT writes most often at that position
    for that Traditional character (a reproducible basis: 餘 is 余 in 3x the entries it is 馀); the Simplified words
    of CC-CEDICT (2 to 4 characters) that contain the character are kept as written. A character with no such
    evidence, or a tie, is `unresolved` and left alone: a wrong character is worse than a script left mixed.
    """
    variants = load_variants()
    wanted = {char for char in variants if char not in base}
    used, aligned, words, headwords = _cedict_evidence(wanted)
    unique: dict[str, str] = {}
    contextual: dict[str, dict[str, object]] = {}
    unresolved: list[str] = []
    for char in sorted(wanted):
        targets = variants[char]
        candidates = [t for t in targets if t != char and BASIC_BLOCK[0] <= ord(t) <= BASIC_BLOCK[1]]
        if not candidates:
            continue
        still_simplified = char in targets or char in used
        if len(candidates) == 1 and not still_simplified:
            unique[char] = candidates[0]
            continue
        evidence = sorted(((aligned.get((char, t), 0), t) for t in candidates), reverse=True)
        top = evidence[0]
        runner_up = evidence[1][0] if len(evidence) > 1 else 0
        if top[0] == 0 or top[0] == runner_up:
            unresolved.append(char)
            continue
        # A word that CC-CEDICT also lists with the default form (回覆 beside 回复, 藉口 beside 借口) is a variant
        # spelling of it, not Simplified as written, so it does not protect the character.
        keep = sorted(w for w in words.get(char, ()) if w.replace(char, top[1]) not in headwords)
        contextual[char] = {"to": top[1], "keep": keep}
    return unique, contextual, unresolved


def derive_map() -> dict[str, object]:
    """Character conversion tables, one character to one character, so a converted text keeps its length.

    `to_simplified`: a Traditional-only character that is the traditional form of exactly one Simplified headword
    (CC-CEDICT), plus the Unihan additions of `derive_variant_maps`.
    `contextual_to_simplified`: characters whose Simplified form depends on the word (`derive_variant_maps`).
    `to_traditional`: a Simplified-only character with exactly one traditional form (发 -> 發 and 髮 is ambiguous,
    so it is left alone: a wrong character is worse than a script left mixed, and the check then flags it).
    """
    pairs: dict[str, set[str]] = {}
    table = derive(pairs)
    simplified_only, traditional_only = set(table["simplified"]), set(table["traditional"])
    sources: dict[str, set[str]] = {}
    for simp, forms in pairs.items():
        for form in forms:
            sources.setdefault(form, set()).add(simp)
    to_simplified = {t: next(iter(s)) for t, s in sorted(sources.items()) if t in traditional_only and len(s) == 1}
    unique, contextual, unresolved = derive_variant_maps(to_simplified)
    for char in EXCLUDED:
        unique.pop(char, None)
    # A conversion is a single step: a target that is itself converted (戱 to 戯, 戯 to ...) would leave a text half done.
    keys = set(to_simplified) | set(unique)
    for char in [c for c, target in unique.items() if target in keys]:
        del unique[char]
    to_simplified.update(unique)
    chained = [c for c, target in to_simplified.items() if target in to_simplified]
    if chained:
        raise SystemExit("conversion chains: " + "".join(chained))
    return {
        "format": MAP_FORMAT,
        "source": "CC-CEDICT, Unicode Unihan (kSimplifiedVariant)",
        "release": table["release"],
        "licence": "CC BY-SA 4.0 (CC-CEDICT); Unicode License v3 (Unihan)",
        "notice": table["notice"] + "; Unihan (c) Unicode, Inc., see lexicon_data/",
        "to_simplified": dict(sorted(to_simplified.items())),
        "contextual_to_simplified": contextual,
        "unresolved": "".join(unresolved),
        "to_traditional": {s: next(iter(f)) for s, f in sorted(pairs.items()) if s in simplified_only and len(f) == 1},
    }


def expected_failures() -> list[str]:
    """Each EXPECTED word, after a Traditional marker, run through the shipped converter (not the freshly derived table)."""
    from writing_coach.languages.chinese.script_conversion import convert_script

    return [
        f"{word} -> {got[1:]} (want {want})".encode("unicode_escape").decode("ascii")
        for word, want in EXPECTED.items()
        # 這 is the Traditional evidence a context-dependent character needs to be judged at all (D-211).
        if (got := convert_script("這" + word, "zh-Hans")) != "这" + want
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--unihan-zip", help="refresh the vendored kSimplifiedVariant extract from Unihan.zip first")
    args = parser.parse_args()
    if args.unihan_zip:
        extract = parse_variants(Path(args.unihan_zip).read_bytes())
        VARIANTS_PATH.write_text(json.dumps(extract, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n")
    table = derive()
    text = json.dumps(table, ensure_ascii=False, indent=0) + "\n"
    map_text = json.dumps(derive_map(), ensure_ascii=False, indent=0) + "\n"
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        current_map = MAP_OUT.read_text(encoding="utf-8") if MAP_OUT.is_file() else ""
        if current != text or current_map != map_text:
            print("script_chars.json or script_map.json is stale; run scripts/build_chinese_script_table.py")
            return 1
        problems = expected_failures()
        if problems:
            print("known words not converted as expected:\n  " + "\n  ".join(problems))
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    MAP_OUT.write_text(map_text, encoding="utf-8", newline="\n")
    derived = json.loads(map_text)
    print(
        f"simplified-only {len(table['simplified'])}, traditional-only {len(table['traditional'])}; "
        f"to_simplified {len(derived['to_simplified'])}, contextual {len(derived['contextual_to_simplified'])}, "
        f"unresolved {len(derived['unresolved'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
