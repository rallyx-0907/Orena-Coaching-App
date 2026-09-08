"""The transactional seam for the work aggregate.

PROPOSAL — the tables this reads and writes are in migration `20260908_0005`,
which is awaiting Codex review and explicit schema authorization. Nothing here
runs until that migration is applied by the operator command; no caller is
wired to it yet.

Everything that decides is elsewhere and reused, not restated:
`reference_backbone.mutation_decision` for scope, receipt, version and
deletion, and `work_contract` for lifecycle, conversation heads and paging.
What lives here is the one thing those cannot do - hold a transaction.

The shape of a commit, in this order, inside one transaction:

  1. lock the account's stream head and hold it until commit;
  2. recheck the incarnation is still active - a request authorized a moment
     ago can arrive after a deletion;
  3. look up the receipt for this scoped operation, before comparing versions,
     so a retry whose acknowledgment was lost returns its original result
     rather than a version conflict;
  4. lock the work row and read its version and lifecycle;
  5. decide;
  6. on commit, allocate the next sequence from the locked head and write the
     domain row, the change record and the receipt together.

A sequence allocated outside commit order - a database sequence, say - is not
sufficient: it can be consumed by a transaction that later rolls back, leaving
a gap that a reader cannot distinguish from a write it has not seen yet.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import Mutation, Receipt, Scope, mutation_decision
from writing_coach.work_contract import lifecycle_change, validate_domain, validate_kind


def semantic_digest(command_type: str, references: dict[str, Any], payload: Any) -> str:
    """A stable hash of validated semantic input, including type and references.

    Two distinct attempts that happen to carry equal text are different
    operations, so this never becomes the operation's identity - it is only the
    guard that catches one operation id being reused with different input.
    """
    material = json.dumps(
        {'type': command_type, 'refs': references, 'payload': payload},
        sort_keys=True,
        ensure_ascii=False,
        separators=(',', ':'),
    )
    return hashlib.sha256(material.encode('utf-8')).hexdigest()


class WorkCommitted(dict):
    """`committed`, `replay`, `conflict` or `rejected`, with what the caller needs."""


class PostgresWorkRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # -- reads ---------------------------------------------------------------

    def get_work(self, scope: Scope, work_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT id, version, lifecycle, payload, language_code, updated_sequence "
                    "FROM works WHERE id = :id AND incarnation_id = :inc "
                    "AND language_code = :lang"
                ),
                {'id': work_id, 'inc': scope.incarnation, 'lang': scope.language},
            ).mappings().first()
        return dict(row) if row else None

    def changes_after(self, scope: Scope, after: int, limit: int = 200) -> list[dict[str, Any]]:
        """The account's whole change stream, not a per-language slice.

        A language filter cannot skip changes in another language, so the pull
        reads every change for the incarnation and the caller decides what to
        show. Filtering here is how a cursor silently loses rows.
        """
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT sequence, language_code, object_domain, object_id, "
                    "object_version, change_kind FROM change_records "
                    "WHERE incarnation_id = :inc AND sequence > :after "
                    "ORDER BY sequence LIMIT :limit"
                ),
                {'inc': scope.incarnation, 'after': after, 'limit': limit},
            ).mappings().all()
        return [dict(row) for row in rows]

    # -- the commit ----------------------------------------------------------

    def commit_mutation(
        self,
        *,
        scope: Scope,
        domain: str,
        operation_id: str,
        digest: str,
        expected_version: int,
        work_id: str,
        kind: str = 'draft',
        payload: dict[str, Any] | None = None,
        lifecycle: str = 'active',
        source: dict[str, str] | None = None,
    ) -> WorkCommitted:
        source = source or {}
        # Finding 9: kind and domain stay strings in PostgreSQL, so the
        # strictness has to be here and has to run before anything is written.
        validate_kind(kind)
        validate_domain(domain)
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            # 1. The stream head, held until this transaction ends. Every
            #    producer - including deletion and workers - takes this lock,
            #    which is what makes the sequence a total order per account.
            head = connection.execute(
                text(
                    "SELECT next_sequence FROM account_streams "
                    "WHERE incarnation_id = :inc FOR UPDATE"
                ),
                {'inc': scope.incarnation},
            ).scalar_one_or_none()
            if head is None:
                return WorkCommitted(status='rejected', reason='unknown_account_stream')

            # 2. The account may have been deleted since this request was
            #    authorized.
            status = connection.execute(
                text("SELECT status FROM account_incarnations WHERE id = :inc"),
                {'inc': scope.incarnation},
            ).scalar_one_or_none()
            if status != 'active':
                return WorkCommitted(status='rejected', reason='account_not_active')

            # 3. Receipt before version. A lost acknowledgment retried the same
            #    operation; it must get its original result, not a conflict
            #    against the version its own first attempt produced.
            receipt_row = connection.execute(
                text(
                    "SELECT language_code, domain, resource_id, operation_id, "
                    "request_digest, expected_version, result_ref, committed_version "
                    "FROM mutation_receipts WHERE incarnation_id = :inc "
                    "AND domain = :domain AND operation_id = :op"
                ),
                {'inc': scope.incarnation, 'domain': domain, 'op': operation_id},
            ).mappings().first()

            # 4. The work row, locked.
            work = connection.execute(
                text(
                    "SELECT version, lifecycle, payload FROM works "
                    "WHERE id = :id AND incarnation_id = :inc AND language_code = :lang "
                    "FOR UPDATE"
                ),
                {'id': work_id, 'inc': scope.incarnation, 'lang': scope.language},
            ).mappings().first()
            current_version = int(work['version']) if work else 0
            current_lifecycle = str(work['lifecycle']) if work else 'active'

            command = Mutation(scope, domain, work_id, operation_id, digest, expected_version)
            receipt = None
            if receipt_row is not None:
                # Rebuilt entirely from persisted columns. Nothing here comes
                # from the request that is retrying: a historical command
                # reconstructed out of current input compares a field against
                # itself, so a changed one passes as a match.
                receipt = Receipt(
                    Mutation(
                        Scope(
                            scope.account,
                            scope.incarnation,
                            str(receipt_row['language_code']),
                        ),
                        str(receipt_row['domain']),
                        str(receipt_row['resource_id']),
                        str(receipt_row['operation_id']),
                        str(receipt_row['request_digest']),
                        int(receipt_row['expected_version']),
                    ),
                    str(receipt_row['result_ref']),
                    int(receipt_row['committed_version']),
                )

            # 5. Decide. Scope, deletion, replay and version, in that order.
            verdict = mutation_decision(
                command, scope, current_version, receipt,
                deleted=current_lifecycle == 'deleted' and lifecycle != 'deleted',
            )
            if verdict == 'replay':
                return WorkCommitted(
                    status='replay',
                    result_ref=receipt.result_ref,
                    version=receipt.committed_version,
                )
            if verdict == 'version_conflict':
                return WorkCommitted(
                    status='conflict',
                    current_version=current_version,
                    server_payload=dict(work['payload']) if work else {},
                )
            if verdict != 'commit':
                return WorkCommitted(status='rejected', reason=verdict)
            if work is not None and lifecycle != current_lifecycle:
                if lifecycle_change(current_lifecycle, lifecycle) == 'refused':
                    return WorkCommitted(status='rejected', reason='lifecycle_refused')

            # 6. Allocate from the held head, then write all three rows.
            sequence = int(head)
            connection.execute(
                text(
                    "UPDATE account_streams SET next_sequence = :next, updated_at = :now "
                    "WHERE incarnation_id = :inc"
                ),
                {'next': sequence + 1, 'now': now, 'inc': scope.incarnation},
            )
            new_version = current_version + 1
            params = {
                'id': work_id, 'inc': scope.incarnation, 'lang': scope.language,
                'kind': kind, 'version': new_version, 'lifecycle': lifecycle,
                'payload': json.dumps(payload or {}, ensure_ascii=False),
                'seq': sequence, 'now': now,
                'source_kind': source.get('kind', ''),
                'source_id': source.get('id', ''),
                'source_revision': source.get('revision', ''),
            }
            if work is None:
                connection.execute(
                    text(
                        "INSERT INTO works (id, incarnation_id, language_code, kind, "
                        "source_kind, source_id, source_revision, version, lifecycle, "
                        "payload, updated_sequence, created_at, updated_at) VALUES "
                        "(:id, :inc, :lang, :kind, :source_kind, :source_id, "
                        ":source_revision, :version, :lifecycle, CAST(:payload AS JSON), "
                        ":seq, :now, :now)"
                    ),
                    params,
                )
            else:
                connection.execute(
                    text(
                        "UPDATE works SET version = :version, lifecycle = :lifecycle, "
                        "payload = CAST(:payload AS JSON), updated_sequence = :seq, "
                        "updated_at = :now WHERE id = :id AND incarnation_id = :inc "
                        "AND language_code = :lang"
                    ),
                    params,
                )
            connection.execute(
                text(
                    "INSERT INTO change_records (id, incarnation_id, sequence, "
                    "language_code, object_domain, object_id, object_version, "
                    "change_kind, created_at) VALUES (:id, :inc, :seq, :lang, :domain, "
                    ":object_id, :version, :change_kind, :now)"
                ),
                {
                    'id': uuid.uuid4(), 'inc': scope.incarnation, 'seq': sequence,
                    'lang': scope.language, 'domain': domain, 'object_id': work_id,
                    'version': new_version,
                    'change_kind': 'delete' if lifecycle == 'deleted' else 'upsert',
                    'now': now,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO mutation_receipts (id, incarnation_id, language_code, "
                    "domain, resource_id, operation_id, request_digest, expected_version, "
                    "result_ref, committed_version, sequence, created_at) VALUES "
                    "(:id, :inc, :lang, :domain, :resource, :op, :digest, :expected, "
                    ":result_ref, :version, :seq, :now)"
                ),
                {
                    'id': uuid.uuid4(), 'inc': scope.incarnation,
                    'lang': scope.language, 'domain': domain, 'resource': work_id,
                    'op': operation_id, 'digest': digest,
                    'expected': expected_version, 'result_ref': work_id,
                    'version': new_version, 'seq': sequence, 'now': now,
                },
            )
            return WorkCommitted(
                status='committed', result_ref=work_id, version=new_version, sequence=sequence
            )
