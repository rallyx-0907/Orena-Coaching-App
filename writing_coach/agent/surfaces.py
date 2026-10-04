"""Each place's name and purpose, as the UI publishes them (contract v5 §6.2, D-096).

The UI owns its places: it writes their names and one-line purposes in its copy
layer and publishes them as generated data, `static/orena/copy/surfaces.json`,
which reaches this lane with `codex/work` merged forward. The server reads that
file - for "what is this screen for?" and for naming a place - and keeps no copy of
its own. A surface without a `purpose` gets its name only; the server never writes a
purpose of its own. Both are interface layer.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

SURFACES_FILE = Path(__file__).resolve().parents[2] / "static" / "orena" / "copy" / "surfaces.json"
FALLBACK_LANGUAGE = "en"


@lru_cache(maxsize=1)
def published() -> MappingProxyType:
    """The file's `surfaces` table; empty when the file is missing or unreadable (the answer then names no place)."""

    try:
        data = json.loads(SURFACES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MappingProxyType({})
    table = data.get("surfaces") if isinstance(data, dict) else None
    return MappingProxyType(table if isinstance(table, dict) else {})


def _text(surface: str | None, field: str, interface: str) -> str | None:
    entry: Any = published().get(surface or "")
    texts = entry.get(field) if isinstance(entry, dict) else None
    if not isinstance(texts, dict):
        return None
    value = texts.get(interface) or texts.get(FALLBACK_LANGUAGE)
    return value if isinstance(value, str) and value.strip() else None


def name(surface: str | None, interface: str) -> str | None:
    return _text(surface, "name", interface)


def purpose(surface: str | None, interface: str) -> str | None:
    """Absent until the UI writes it (§6.2: purposes come once the screens exist as drawn)."""

    return _text(surface, "purpose", interface)
