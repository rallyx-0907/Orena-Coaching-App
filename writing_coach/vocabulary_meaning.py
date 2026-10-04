"""A saved word's meaning for the learner's support language, on the server (D-124).

The server-side twin of `static/orena/product/vocabulary-meaning.js`, for the
payloads the server composes itself (Collection retrieval snippets). Order:
the sense's localization for the support language → the learner's own note
(`definition`) → the older Vietnamese copy, for a Vietnamese support language
only → the sense's meaning in another language. Pure; no provider.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _listed(items: Any, language: str) -> str:
    for item in items if isinstance(items, list) else []:
        if isinstance(item, Mapping) and _clean(item.get("language")).casefold() == language and _clean(item.get("text")):
            return _clean(item["text"])
    return ""


def saved_word_meaning(item: Mapping[str, Any], support_language: str) -> str:
    language = _clean(support_language).casefold()
    if language:
        localized = _listed(item.get("short_meanings"), language) or _clean(
            (item.get("support_translations") or {}).get(language)
        )
        if localized:
            return localized
    note = _clean(item.get("definition"))
    if note:
        return note
    if language == "vi" and _clean(item.get("translation_vi")):
        return _clean(item["translation_vi"])
    own = _clean(item.get("language_code")).casefold()
    for meaning in item.get("short_meanings") or []:
        if isinstance(meaning, Mapping):
            other = _clean(meaning.get("language")).casefold()
            if other and other != own and _clean(meaning.get("text")):
                return _clean(meaning["text"])
    return ""


# The request's support language, configured at start-up (app.py) so this module
# does not import the profile store.
_support_language: Callable[[], str] = lambda: ""


def configure_support_language(resolver: Callable[[], str]) -> None:
    global _support_language
    _support_language = resolver


def current_support_language() -> str:
    try:
        return _clean(_support_language()).casefold()
    except Exception:  # noqa: BLE001 - a missing profile costs a snippet, never the page
        return ""
