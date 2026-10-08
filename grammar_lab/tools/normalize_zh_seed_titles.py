from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "inventory" / "seeds_zh.yaml"
NATIVE_TITLE_LINE = re.compile(r"^(\s*native_title:\s*)(.*)$")


def normalize_native_title_lines(text: str) -> tuple[str, int]:
    changed = 0
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        match = NATIVE_TITLE_LINE.match(body)
        if match is None:
            out.append(line)
            continue
        value = match.group(2)
        normalized = value.replace(" ", "")
        if normalized != value:
            changed += 1
        out.append(f"{match.group(1)}{normalized}{ending}")
    return "".join(out), changed


def main() -> None:
    before = SEEDS.read_text(encoding="utf-8")
    after, changed = normalize_native_title_lines(before)
    if after != before:
        SEEDS.write_text(after, encoding="utf-8", newline="\n")
    print(f"normalized {changed} zh native_title line(s)")


if __name__ == "__main__":
    main()
