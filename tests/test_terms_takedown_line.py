"""D-239: the English Terms carry the content-owner removal line, with a contact the Terms already list."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERMS = ROOT / "docs" / "legal" / "public" / "terms.en.json"
BUILT = ROOT / "templates" / "orena" / "public" / "terms.en.html"
LINE = "Content owners can request removal at "


def _contacts(node) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for value in node.values():
            found |= _contacts(value)
    elif isinstance(node, list):
        for value in node:
            found |= _contacts(value)
    elif isinstance(node, str):
        found |= set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", node))
    return found


def test_terms_say_content_owners_can_request_removal_at_a_listed_contact() -> None:
    data = json.loads(TERMS.read_text(encoding="utf-8"))
    text = json.dumps(data, ensure_ascii=False)
    assert LINE in text
    address = re.search(re.escape(LINE) + r"([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", text).group(1)
    assert address.endswith("@chillpickle.org")
    contact_block = [b for s in data["sections"] for b in s["blocks"] if "contact" in b]
    assert address in _contacts(contact_block), "the removal address must be one the Terms already list as a contact"


def test_the_built_terms_page_carries_the_line() -> None:
    assert LINE in BUILT.read_text(encoding="utf-8")
