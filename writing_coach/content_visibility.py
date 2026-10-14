"""Which code-owned built-in content learners may see (D-203).

Some learner content ships in the repository (the Listening catalogue's lessons are the first). The owner's
decision of 2026-10-14: that content is test material and the Admin must be able to take it off the shelf
without a code change. This module is the one server-side switch.

One settings document, `content.visibility` (a `platform_settings` row, exactly like `platform.policies` and
`product.plan_catalog`): `{"version": 1, "hidden": {<kind>: [<built-in id>, ...]}}`. It holds only what an
administrator hid; an item that is not named is visible, so an empty or missing document changes nothing and no
migration is needed. Nothing is deleted - the lesson, its transcript and its provenance stay in the repository and
in the Admin list, and showing it again is one click.

The learner paths do not read this module themselves. They already resolve a built-in item through one place
(`listening_catalog.catalog_lesson` / `catalog_lessons`), and that place filters here, so a hidden item is absent
from lists, search, recommendations, progress cards, prefetch and model-line routes alike, and a direct open
answers 404. The Admin lists the whole catalogue (`listening_catalog.CATALOG`) so it can show a hidden item again.

Reads never raise. A store that cannot be read keeps the last value read in this process (nothing hidden if none was
ever read) and is logged. A saved change applies at once in the worker that saved it and within `CACHE_SECONDS` in
the others. A save is a compare-and-set on the stored version with the audit row in the same transaction.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Mapping
from typing import Any, Protocol

_log = logging.getLogger(__name__)

SETTING_KEY = "content.visibility"
VERSION = 1
CACHE_SECONDS = 5.0
# The kinds of built-in content that can be hidden. A kind is added here when its learner paths filter on it.
KINDS: tuple[str, ...] = ("listening",)
_MAX_ID = 200


class VisibilityInvalid(ValueError):
    """A change that cannot be applied (HTTP 422)."""


class SettingStore(Protocol):
    def get_setting(self, key: str) -> dict | None: ...
    def set_setting(self, key: str, value: dict, *, updated_by: str = "", expected_updated_at: object = ...,
                    audit: dict | None = None) -> dict: ...


_store: SettingStore | None = None
_lock = threading.Lock()
_cache: tuple[float, dict[str, frozenset[str]]] | None = None
_last_good: dict[str, frozenset[str]] | None = None


def configure(store: SettingStore | None) -> None:
    """Install the settings store (the platform repository)."""
    global _store, _cache, _last_good
    with _lock:
        _store, _cache, _last_good = store, None, None


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def _parse(record: Mapping[str, Any] | None) -> dict[str, frozenset[str]]:
    """The hidden ids by kind. A malformed document hides nothing it cannot read; it never raises."""
    document = (record or {}).get("value")
    hidden = document.get("hidden") if isinstance(document, Mapping) else None
    result: dict[str, frozenset[str]] = {}
    if isinstance(hidden, Mapping):
        for kind in KINDS:
            ids = hidden.get(kind)
            if isinstance(ids, list):
                result[kind] = frozenset(str(item) for item in ids if isinstance(item, str) and item)
    return result


def _loaded() -> dict[str, frozenset[str]]:
    global _cache, _last_good
    now = time.monotonic()
    with _lock:
        if _cache is not None and _cache[0] > now:
            return _cache[1]
        store, previous = _store, _last_good
    if store is None:
        return {}
    try:
        loaded = _parse(store.get_setting(SETTING_KEY))
    except Exception:  # noqa: BLE001 - a store that cannot be read must not take the learner's library down
        _log.warning("content visibility unreadable; keeping the last value read", exc_info=True)
        return previous or {}
    with _lock:
        _cache = (now + CACHE_SECONDS, loaded)
        _last_good = loaded
    return loaded


def hidden_ids(kind: str) -> frozenset[str]:
    """The ids of this kind an administrator has hidden from learners."""
    return _loaded().get(kind, frozenset())


def is_hidden(kind: str, item_id: str) -> bool:
    return str(item_id) in hidden_ids(kind)


def stored_meta() -> dict[str, Any]:
    """When and by whom the visibility document was last saved (None when nothing is stored)."""
    if _store is None:
        return {"updated_at": None, "updated_by": None}
    try:
        record = _store.get_setting(SETTING_KEY) or {}
    except Exception:  # noqa: BLE001
        return {"updated_at": None, "updated_by": None}
    return {"updated_at": record.get("updated_at") or None, "updated_by": record.get("updated_by") or None}


def set_hidden(kind: str, item_id: str, hidden: bool, *, updated_by: str = "", actor: str = "",
               audit_extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Hide or show one built-in item; returns `{"from": bool, "to": bool, "changed": bool}`.

    The caller has checked that `item_id` names a real built-in item of `kind`. Setting the state an item already
    has writes nothing. A change is a compare-and-set against the version just read (a concurrent change by another
    administrator raises `SettingConflict`, HTTP 409), and the audit row commits with it.
    """
    if kind not in KINDS:
        raise VisibilityInvalid(f"Unknown content kind {kind!r}.")
    item_id = str(item_id or "").strip()
    if not item_id or len(item_id) > _MAX_ID:
        raise VisibilityInvalid("An item id is required.")
    if _store is None:
        raise RuntimeError("The content visibility store has not been installed by the persistence runtime.")
    try:
        record = _store.get_setting(SETTING_KEY)
    except Exception as error:
        raise RuntimeError("The content visibility store could not be read.") from error
    current = _parse(record)
    before = item_id in current.get(kind, frozenset())
    if before == bool(hidden):
        return {"from": before, "to": before, "changed": False}
    document_hidden = {name: sorted(current.get(name, frozenset())) for name in KINDS}
    ids = set(document_hidden[kind])
    if hidden:
        ids.add(item_id)
    else:
        ids.discard(item_id)
    document_hidden[kind] = sorted(ids)
    document = {"version": VERSION, "hidden": {name: values for name, values in document_hidden.items() if values}}
    payload = {"kind": kind, "item": item_id, "from": "hidden" if before else "visible",
               "to": "hidden" if hidden else "visible", **dict(audit_extra or {})}
    audit = {"action": "admin.content.visibility", "actor": actor, "entity_type": f"{kind}_builtin",
             "entity_id": item_id, "payload": payload}
    _store.set_setting(SETTING_KEY, document, updated_by=updated_by,
                       expected_updated_at=record.get("updated_at") if record else None, audit=audit)
    clear_cache()
    return {"from": before, "to": bool(hidden), "changed": True}
