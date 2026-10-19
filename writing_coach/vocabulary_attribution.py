"""Dataset licences and attribution carried by a vocabulary collection's own record.

A collection built from a third-party dataset states, in its `provenance`, the licence it is
shared under and the attribution the source requires. A collection's `data_sources` names the
datasets it was built from; each recognised name maps to an entry of the licences registry
(`writing_coach.licences`), which mirrors the notice shipped with the vendored data, so no
wording is typed twice: CC-CEDICT (CC BY-SA statement), the CEFR-J Vocabulary Profile (citation)
and CMUdict (BSD notice).
Only the `provenance.licences` list is written (one object per matched dataset, in registry
order); every other provenance key is preserved, and applying it twice changes nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from writing_coach.licences import DATASETS
from writing_coach.persistence.models import VocabularyCollection

# Registry dataset id -> the spellings of it that a collection's `data_sources` may use (casefolded).
SOURCE_TOKENS: dict[str, tuple[str, ...]] = {
    "cc-cedict": ("cc-cedict", "cedict"),
    "cefrj-vocabulary": ("cefr-j", "cefrj"),
    "cmudict": ("cmudict",),
}


def licence_object(dataset_id: str) -> dict[str, str]:
    dataset = next(item for item in DATASETS if item.id == dataset_id)
    statement = f"Derived from {dataset.name} ({dataset.attribution}), licensed {dataset.licence}."
    if "BY-SA" in dataset.licence:
        statement += f" This collection is shared under {dataset.licence}."
    return {
        "id": dataset.id,
        "licence": dataset.licence,
        "licence_url": dataset.licence_url,
        "source": dataset.name,
        "source_url": dataset.source_url,
        "attribution": dataset.attribution,
        "statement": statement,
    }


def cedict_licence() -> dict[str, str]:
    return licence_object("cc-cedict")


def matched_datasets(provenance: Any) -> list[str]:
    """Registry ids named by `data_sources`, in registry order."""

    sources = provenance.get("data_sources") if isinstance(provenance, Mapping) else None
    names = [str(item).casefold() for item in (sources or [])]
    return [dataset.id for dataset in DATASETS
            if any(token in name for name in names for token in SOURCE_TOKENS.get(dataset.id, ()))]


def licences_for(provenance: Any) -> list[dict[str, str]]:
    return [licence_object(dataset_id) for dataset_id in matched_datasets(provenance)]


def uses_cedict(provenance: Any) -> bool:
    return "cc-cedict" in matched_datasets(provenance)


def plan(engine: Engine, collection_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """What would change: explicit ids, else every collection whose data_sources name a known dataset.

    An explicit id whose `data_sources` match nothing is never written (`change` False, with a
    `warning`), and an id that does not exist is reported with `status` None and a warning.
    """

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with Session(engine) as session:
        for collection in session.query(VocabularyCollection).order_by(VocabularyCollection.id):
            if collection_ids is not None and collection.id not in collection_ids:
                continue
            seen.add(collection.id)
            provenance = collection.provenance if isinstance(collection.provenance, Mapping) else {}
            wanted = licences_for(provenance)
            if not wanted:
                if collection_ids is not None:
                    rows.append({"id": collection.id, "status": collection.catalog_status, "change": False,
                                 "datasets": [], "warning": "no matching data source in provenance.data_sources"})
                continue
            rows.append({"id": collection.id, "status": collection.catalog_status,
                         "change": provenance.get("licences") != wanted,
                         "datasets": [item["id"] for item in wanted]})
    for missing in sorted(set(collection_ids or []) - seen):
        rows.append({"id": missing, "status": None, "change": False, "datasets": [], "warning": "collection not found"})
    return rows


def apply(engine: Engine, collection_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Write the licence list into the planned collections. Idempotent; leaves other keys alone."""

    changed = plan(engine, collection_ids)
    with Session(engine) as session, session.begin():
        for row in changed:
            if not row["change"]:
                continue
            collection = session.get(VocabularyCollection, row["id"])
            current = dict(collection.provenance) if isinstance(collection.provenance, Mapping) else {}
            collection.provenance = {**current, "licences": licences_for(current)}
    return changed
