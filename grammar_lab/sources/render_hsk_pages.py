"""Render the grammar-outline pages of the scanned HSK 3.0 standard to PNG (no OCR, no text recognition).

    python grammar_lab/sources/render_hsk_pages.py <gf0025.pdf> <out_dir> [first_page last_page] [dpi]

GF 0025-2021 (gov.cn, 260 pages, scanned, no text layer): appendix 4 "语法等级大纲" is PDF pages 176-260.
The images go to a vision model (a different one from the engine's, under the gemini-text lock) that
returns the item codes, names and levels as JSON -- see ``inventory/raw/README.md``. Needs ``pymupdf``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


def main(argv: list[str]) -> int:
    pdf, out_dir = Path(argv[0]), Path(argv[1])
    first = int(argv[2]) if len(argv) > 2 else 176
    last = int(argv[3]) if len(argv) > 3 else 260
    dpi = int(argv[4]) if len(argv) > 4 else 130
    out_dir.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(str(pdf))
    for number in range(first, last + 1):
        document[number - 1].get_pixmap(dpi=dpi).save(str(out_dir / f"p{number:03d}.png"))
    sys.stdout.write(f"rendered pages {first}-{last} to {out_dir}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
