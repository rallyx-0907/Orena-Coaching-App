"""CC-CEDICT attribution carried by a vocabulary collection's own record (CC BY-SA 4.0).

A collection whose senses or readings come from CC-CEDICT states, in its `provenance`, the
licence it is shared under and the attribution the source requires. The wording is read from
the licences registry (`writing_coach.licences`), which mirrors the notice shipped with the
vendored data (`languages/chinese/lexicon_data/README.md`); nothing is typed twice.
Only the `provenance.licence` object is written; every other provenance key is preserved,
and applying it twice changes nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from writing_coach.licences import DATASETS
from writing_coach.persistence.models import VocabularyCollection

DATASET_ID = "cc-cedict"


def cedict_licence() -> dict[str, str]:
    dataset = next(item for item in DATASETS if item.id == DATASET_ID)
    return {
        "id": dataset.id,
        "licence": dataset.licence,
        "licence_url": dataset.licence_url,
        "source": dataset.name,
        "source_url": dataset.source_url,
        "attribution": dataset.attribution,
        "statement": (
            f"Derived from {dataset.name} ({dataset.attribution}), "
            f"licensed {dataset.licence}. This collection is shared under {dataset.licence}."
        ),
    }


def uses_cedict(provenance: Any) -> bool:
    sources = provenance.get("data_sources") if isinstance(provenance, Mapping) else None
    return any("cc-cedict" in str(item).casefold() for item in (sources or []))


def plan(engine: Engine, collection_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """What would change: explicit ids, else every collection whose data_sources name CC-CEDICT."""

    wanted = cedict_licence()
    rows: list[dict[str, Any]] = []
    with Session(engine) as session:
        for collection in session.query(VocabularyCollection).order_by(VocabularyCollection.id):
            if collection_ids is not None and collection.id not in collection_ids:
                continue
            provenance = collection.provenance if isinstance(collection.provenance, Mapping) else {}
            if collection_ids is None and not uses_cedict(provenance):
                continue
            rows.append({"id": collection.id, "status": collection.catalog_status,
                         "change": provenance.get("licence") != wanted})
    return rows


def apply(engine: Engine, collection_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Write the licence object into the planned collections. Idempotent; leaves other keys alone."""

    wanted = cedict_licence()
    changed = plan(engine, collection_ids)
    with Session(engine) as session, session.begin():
        for row in changed:
            if not row["change"]:
                continue
            collection = session.get(VocabularyCollection, row["id"])
            current = dict(collection.provenance) if isinstance(collection.provenance, Mapping) else {}
            collection.provenance = {**current, "licence": wanted}
    return changed
