"""Open bilingual dictionary packs: a word's base meaning in the learner's support language, at no cost.

The word tap's lookup order (owner decision 2026-10-18, "neutral base meaning, cost $0 or the lowest possible"):

    catalogue (curated)  ->  bilingual pack for the pair  ->  free local machine translation  ->  `word_translation`

A pack is a deterministic, offline word list for one (source language, support language) pair - the EN->VI
counterpart of what the vendored CC-CEDICT is for ZH->EN (CC-CEDICT stays in the Chinese layer, `reading_lookup`).
No pack ships with this module: an open pack (for example a FreeDict or Wiktionary-derived EN->VI list) plugs in by
dropping a file into `PACK_DIR`, or by `register_pack` at start-up. Choosing and vendoring a pack is a licence
decision per pack, not an implementation detail; until one is installed every lookup here is a miss and the layers
after it answer exactly as before.

File format: UTF-8, one entry per line, `headword<TAB>gloss`; a line starting with "#" is a comment. The headword is
matched case-insensitively after collapsing whitespace; the first entry for a headword wins. The file is
`<source>-<target>.tsv`, e.g. `en-vi.tsv`.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

_log = logging.getLogger("orena.lookup")

PACK_DIR = Path(__file__).resolve().parent / "data" / "bilingual_packs"
MAX_GLOSS_CHARS = 120

# (word, source language, support language) -> a short gloss, or None.
PackLookup = Callable[[str, str, str], "str | None"]

_lock = threading.Lock()
_registered: dict[tuple[str, str], PackLookup] = {}
_loaded: dict[tuple[str, str], dict[str, str] | None] = {}


def _key(word: str) -> str:
    return " ".join(str(word or "").casefold().split())


def _pair(source: str, target: str) -> tuple[str, str]:
    return (str(source or "").strip().casefold(), str(target or "").strip().casefold())


def register_pack(source: str, target: str, lookup: PackLookup) -> None:
    """Install a pack for one pair (start-up wiring, tests). It replaces any file pack for that pair."""

    with _lock:
        _registered[_pair(source, target)] = lookup


def reset_packs() -> None:
    """Forget registered and loaded packs (tests)."""

    with _lock:
        _registered.clear()
        _loaded.clear()


def _read_file(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.lstrip().startswith("#") or "\t" not in line:
                continue
            word, gloss = line.rstrip("\n").split("\t", 1)
            key, gloss = _key(word), " ".join(gloss.split())
            if key and gloss and key not in entries:
                entries[key] = gloss[:MAX_GLOSS_CHARS]
    return entries


def _file_pack(pair: tuple[str, str]) -> dict[str, str] | None:
    with _lock:
        if pair in _loaded:
            return _loaded[pair]
    path = PACK_DIR / f"{pair[0]}-{pair[1]}.tsv"
    table: dict[str, str] | None = None
    if path.is_file():
        try:
            table = _read_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("bilingual pack %s-%s unreadable (%s); treated as absent", pair[0], pair[1], type(exc).__name__)
    with _lock:
        _loaded[pair] = table
    return table


def has_pack(source: str, target: str) -> bool:
    pair = _pair(source, target)
    with _lock:
        if pair in _registered:
            return True
    return bool(_file_pack(pair))


def lookup(word: str, source: str, target: str) -> str | None:
    """The pack's gloss for `word` in `target`, or None (no pack for the pair, no entry, or a failing pack)."""

    pair = _pair(source, target)
    if not word or pair[0] == pair[1]:
        return None
    with _lock:
        registered = _registered.get(pair)
    if registered is not None:
        try:
            found = registered(word, pair[0], pair[1])
        except Exception as exc:  # noqa: BLE001 - a pack is an aid; its failure is a miss
            _log.warning("bilingual pack %s-%s failed (%s); treated as a miss", pair[0], pair[1], type(exc).__name__)
            return None
        found = " ".join(str(found or "").split())
        return found[:MAX_GLOSS_CHARS] or None
    table = _file_pack(pair)
    if not table:
        return None
    return table.get(_key(word))
