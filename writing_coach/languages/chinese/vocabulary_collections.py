from __future__ import annotations
import json
from pathlib import Path

_PATH = Path(__file__).with_name("vocabulary_collections.json")
VOCABULARY_COLLECTIONS = json.loads(_PATH.read_text(encoding="utf-8"))
