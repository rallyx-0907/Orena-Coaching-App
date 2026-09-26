"""Detect traditional Chinese characters in content that must be simplified (zh-Hans).

Uses OpenCC's traditional→simplified character table (Apache-2.0, shipped in
the ``opencc-python-reimplemented`` package). A character counts as
traditional only when *every* simplified candidate differs from it, so
characters that are also valid simplified forms (乾, 於, 瞭, ...) are not
reported.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files


@cache
def traditional_only_chars() -> frozenset[str]:
    table = files("opencc").joinpath("dictionary", "TSCharacters.txt").read_text(encoding="utf-8")
    result = set()
    for line in table.splitlines():
        if not line.strip():
            continue
        source, _, targets = line.partition("\t")
        if source not in targets.split():
            result.add(source)
    return frozenset(result)


def traditional_chars(text: str) -> list[str]:
    """Distinct traditional-only characters in ``text``, in order of first appearance."""
    known = traditional_only_chars()
    return list(dict.fromkeys(ch for ch in text if ch in known))
