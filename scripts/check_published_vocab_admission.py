"""Read-only check: published vocabulary collections whose admission is not valid.

Before the status route applied the admission gate, a collection could be moved
to `published` without a valid admission record. This lists every collection
that is `published` today but whose `provenance.admission` fails
`_publication_admission` (the same function the publish path uses), with its
id, language, entry count and the reason. It writes nothing: the session is
read-only, no row is changed, and the database URL is never printed.

Run it inside the application container, against the database named by
`POSTGRES_RUNTIME_URL` (or `--url`):

    python scripts/check_published_vocab_admission.py

Exit status: 0 nothing to repair, 1 at least one collection needs a decision,
2 no usable database. What to do about a listed collection (re-publish through
`/publish` with a real attestation, or unpublish) is a human decision.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import Engine, create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from writing_coach.persistence.models import (  # noqa: E402
    VocabularyCollection,
    VocabularyCollectionMembership,
)
from writing_coach.persistence.vocabulary_repository import (  # noqa: E402
    _VOCABULARY_PUBLISHABLE_RIGHTS,
    _publication_admission,
    _text,
)


def _reason(provenance: Any) -> str:
    """Why the admission fails. Descriptive only: the verdict is `_publication_admission`'s."""

    admission = provenance.get("admission") if isinstance(provenance, Mapping) else None
    if not isinstance(admission, Mapping):
        return "no admission record"
    reasons: list[str] = []
    if _text(admission.get("review_status")).casefold() != "approved":
        reasons.append("review_status is not approved")
    if admission.get("publication_attested") is not True:
        reasons.append("publication is not attested")
    rights = _text(admission.get("rights_status")).casefold()
    if rights not in _VOCABULARY_PUBLISHABLE_RIGHTS:
        reasons.append(f"rights_status '{rights or 'missing'}' is not publishable")
    if _text(admission.get("completeness")).casefold() != "complete":
        reasons.append("completeness is not complete")
    if not _text(admission.get("attested_by")):
        reasons.append("attested_by is empty")
    return "; ".join(reasons) or "admission invalid"


def find_unadmitted_published(engine: Engine) -> list[dict[str, Any]]:
    """Every published collection whose admission `_publication_admission` refuses."""

    found: list[dict[str, Any]] = []
    with Session(engine) as session:
        if engine.dialect.name == "postgresql":
            session.execute(text("SET TRANSACTION READ ONLY"))
        rows = session.execute(
            select(VocabularyCollection).where(VocabularyCollection.catalog_status == "published")
            .order_by(VocabularyCollection.language_code, VocabularyCollection.id)
        ).scalars().all()
        for collection in rows:
            provenance = collection.provenance if isinstance(collection.provenance, Mapping) else {}
            try:
                _publication_admission(provenance)
            except ValueError:
                count = session.scalar(
                    select(func.count()).select_from(VocabularyCollectionMembership)
                    .where(VocabularyCollectionMembership.collection_id == collection.id)
                )
                found.append({
                    "id": collection.id,
                    "language_code": collection.language_code,
                    "entries": int(count or 0),
                    "reason": _reason(provenance),
                })
        session.rollback()
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        engine = create_engine(url)
        found = find_unadmitted_published(engine)
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not read the vocabulary collections ({type(exc).__name__})")
        return 2
    if not found:
        print("OK: every published vocabulary collection has a valid admission.")
        return 0
    print(f"{len(found)} published vocabulary collection(s) without a valid admission:")
    for item in found:
        print(f"- {item['id']}  language={item['language_code']}  entries={item['entries']}  reason: {item['reason']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
