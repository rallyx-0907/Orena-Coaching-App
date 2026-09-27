"""Deterministic JSON/YAML file I/O shared by every pipeline step.

Content lives in git, so one canonical formatting keeps AI and admin edits
readable as diffs: containers are inlined when they fit in ``WIDTH`` columns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

WIDTH = 100


def format_json(value: Any) -> str:
    return _format(value, 0) + "\n"


def _format(value: Any, indent: int) -> str:
    compact = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    if not isinstance(value, dict | list) or not value or indent + len(compact) <= WIDTH:
        return compact
    pad = " " * (indent + 2)
    if isinstance(value, list):
        inner = [pad + _format(item, indent + 2) for item in value]
        return "[\n" + ",\n".join(inner) + "\n" + " " * indent + "]"
    inner = [
        pad + json.dumps(key, ensure_ascii=False) + ": " + _format(item, indent + 2).lstrip()
        for key, item in value.items()
    ]
    return "{\n" + ",\n".join(inner) + "\n" + " " * indent + "}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_json(value), encoding="utf-8", newline="\n")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
