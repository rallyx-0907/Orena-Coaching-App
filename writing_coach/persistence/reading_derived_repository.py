"""The persistent layer of the Reading on-demand cache (`writing_coach/reading_derived.py`).

One table, `reading_derived_texts` (proposed migration 20261005_0028). Reads and writes are short and bounded; an
error (the table not there yet, a timeout) is the caller's to absorb - `DerivedCache` pauses persistence for five
minutes and carries on in process.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from writing_coach.persistence.models import ReadingDerivedText


class ReadingDerivedRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get_many(self, kind: str, target_language: str, keys: Sequence[str]) -> dict[str, dict[str, Any]]:
        if not keys:
            return {}
        statement = select(ReadingDerivedText.content_hash, ReadingDerivedText.payload).where(
            ReadingDerivedText.kind == kind,
            ReadingDerivedText.target_language == target_language,
            ReadingDerivedText.content_hash.in_(list(keys)),
        )
        with self.engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = 500"))
            return {
                row.content_hash: row.payload
                for row in connection.execute(statement)
                if isinstance(row.payload, dict)
            }

    def put_many(
        self,
        kind: str,
        target_language: str,
        source_language: str,
        rows: Sequence[tuple[str, dict[str, Any]]],
        *,
        provider: str,
        model: str,
    ) -> None:
        now = datetime.now(UTC)
        values = [
            {
                "kind": kind,
                "content_hash": key,
                "target_language": target_language,
                "source_language": source_language,
                "payload": payload,
                "provider": provider,
                "model": model,
                "created_at": now,
            }
            for key, payload in rows
        ]
        if not values:
            return
        # First writer wins: two learners asking at once store one answer, and a stored answer is never replaced.
        statement = pg_insert(ReadingDerivedText).values(values).on_conflict_do_nothing()
        with self.engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = 500"))
            connection.execute(text("SET LOCAL lock_timeout = 200"))
            connection.execute(statement)
