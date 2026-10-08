from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "pipeline" / "seed.py"
OLD = '''    header.setdefault("summary", dict(seed["title"]))
    point["header"] = header
    return point
'''
NEW = '''    header.setdefault("summary", dict(seed["title"]))
    # native_title is authoritative seed metadata. Its per-character pinyin is
    # deterministic display data, so every apply_seed consumer (including the
    # production exporter) must keep the pair in lockstep, not only sync-metadata.
    if lang == "zh":
        from grammar_lab.pipeline.generate import pinyin_from_pairs
        header["native_title_pinyin"] = pinyin_from_pairs(header["native_title"])
    point["header"] = header
    return point
'''


def main() -> None:
    before = TARGET.read_text(encoding="utf-8")
    if NEW in before:
        print("apply_seed title/pinyin patch already present")
        return
    if before.count(OLD) != 1:
        raise SystemExit("expected apply_seed return block exactly once")
    TARGET.write_text(before.replace(OLD, NEW), encoding="utf-8", newline="\n")
    print("patched apply_seed to realign zh native_title_pinyin")


if __name__ == "__main__":
    main()
