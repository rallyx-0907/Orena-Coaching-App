"""A vocabulary import is audited by its own receipt table.

The admin vocabulary importer predates the console and records every source it
is given in `vocabulary_source_imports`: who imported it, into which
collection, when, and how it ended - a failure included, with its reason. The
console's import history reads that table, so it is the audit record for this
action; this test holds it to the same four facts as every other admin audit.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app as app_module
from writing_coach.persistence.models import VocabularySourceImport


def _post(files, metadata):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver") as client:
            return await client.post(
                "/api/admin/vocabulary/import", files=files, data={"metadata": json.dumps(metadata)},
                headers={"origin": "http://testserver"},
            )
    return asyncio.run(run())


def test_a_vocabulary_import_records_who_what_when_and_how_it_ended():
    repository = app_module._persistence_runtime.vocabulary_repository
    if repository is None or not repository.available():
        pytest.skip("the vocabulary schema is not active on this backend")
    title = f"Receipt {uuid.uuid4().hex[:10]}"
    metadata = {"language_code": "en", "title": title}
    stored = _post([("files", ("receipt-good.csv", b"term,meaning\nreceipt,a record\n", "text/csv"))], metadata)
    refused = _post([("files", ("receipt-bad.csv", b"\xff\xfe\x00broken", "text/csv"))], metadata)
    assert stored.status_code == 200 and refused.status_code == 200
    collection_id = stored.json()["collection"]["id"]
    with Session(repository.engine) as session:
        receipts = session.scalars(
            select(VocabularySourceImport).where(VocabularySourceImport.filename.in_(["receipt-good.csv", "receipt-bad.csv"]))
            .where(VocabularySourceImport.collection_id == collection_id)
        ).all()
        failed = session.scalars(
            select(VocabularySourceImport).where(VocabularySourceImport.filename == "receipt-bad.csv")
            .order_by(VocabularySourceImport.created_at.desc())
        ).first()
    good = next(row for row in receipts if row.filename == "receipt-good.csv")
    assert good.imported_by == "local-admin"  # the development administrator's identity
    assert good.status == "imported" and good.imported_count == 1
    assert good.created_at is not None
    assert failed is not None and failed.status == "failed"
    assert failed.imported_by == "local-admin" and failed.created_at is not None
    assert failed.errors and failed.errors[0].get("reason")
