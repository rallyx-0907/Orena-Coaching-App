"""Turn the public Core Inventory PDF into ``inventory/raw/core_inventory_en.csv`` (metadata only).

    python grammar_lab/sources/parse_core_inventory.py <EAQUALS_British_Council_Core_Curriculum_April2011.pdf>

Needs ``pypdf`` (not a project dependency). Reads Appendix E, "Exponents for Language Content"
(PDF pages 22-36): every line that is an inventory item number (46-200: discourse markers, verb forms, nouns, determiners...) followed by a short name.
The level of an item is the level section it sits in; the numbering restarts at each level's
"Verb forms", which is how the sections are told apart in the text layer. Names are cut where the PDF
wraps a line, so ``code`` + ``level`` is the key.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pypdf

FIRST_PAGE, LAST_PAGE = 22, 36
LEVELS = ["A1", "A2", "B1", "B2", "C1"]
# an item line: number, then a name that is not a sentence (examples end in . ? !; "e.g." inside is fine)
ITEM = re.compile(r"^(\d{2,3}[a-z]?)\s+([A-Z][^?!]{2,90})$")


def parse(pdf: Path) -> list[tuple[str, str, str, int]]:
    reader = pypdf.PdfReader(str(pdf))
    rows: list[tuple[str, str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    level_index = 0
    previous = 0
    for page_number in range(FIRST_PAGE, LAST_PAGE + 1):
        text = reader.pages[page_number - 1].extract_text() or ""
        for raw in text.splitlines():
            found = ITEM.match(raw.strip())
            if not found:
                continue
            code, name = found.group(1), found.group(2).strip()
            number = int(re.match(r"\d+", code).group())
            if not 46 <= number <= 200 or code.endswith(".") or name.endswith("."):
                continue
            if number < previous - 30 and level_index < len(LEVELS) - 1:
                level_index += 1
            previous = number
            level = LEVELS[level_index]
            if (code, level) not in seen:
                seen.add((code, level))
                rows.append((code, name, level, page_number))
    return rows


def main(argv: list[str]) -> int:
    out = Path(__file__).resolve().parents[1] / "inventory" / "raw" / "core_inventory_en.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["source", "code", "name", "level", "page"])
        for code, name, level, page in parse(Path(argv[0])):
            writer.writerow(["core_inventory", code, name, level, page])
    sys.stdout.write(f"wrote {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
