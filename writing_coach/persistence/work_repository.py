"""The work aggregate: drafts, responses and conversations.

PROPOSAL — the tables this reads and writes are in migration `20260908_0005`,
awaiting re-review and schema authorization. No caller is wired to it.

The transaction, the sequence, the receipt and the change record are
`mutation_commit.commit_mutation`, shared with every other account mutation.
What is here is only what is specific to work: reading a work row under lock,
what a lifecycle change means, and refusing a domain this owner does not own.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.persistence.mutation_commit import (
    MutationOutcome,
    MutationRefused,
    commit_mutation,
)
from writing_coach.reference_backbone import Scope
from writing_coach.work_contract import lifecycle_change, validate_kind, validate_work_domain


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


class PostgresWorkRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # -- reads ---------------------------------------------------------------

    def get_work(self, scope: Scope, work_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT id, version, lifecycle, payload, language_code, updated_sequence '
                    'FROM works WHERE id = :id AND incarnation_id = :inc '
                    'AND language_code = :lang'
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
                    'SELECT sequence, language_code, object_domain, object_id, '
                    'object_version, change_kind FROM change_records '
                    'WHERE incarnation_id = :inc AND sequence > :after '
                    'ORDER BY sequence LIMIT :limit'
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
    ) -> MutationOutcome:
        source = source or {}
        validate_kind(kind)
        # Not every mutation domain is a work domain. `provenance` takes a
        # sequence, a receipt and a change record like anything else, and it is
        # still not something this owner writes a `works` row for.
        validate_work_domain(domain)
        if bool(source.get('kind')) != bool(source.get('id')):
            raise ValueError('A source reference is both kind and id, or neither')
        if source.get('revision') and not source.get('id'):
            # A revision of nothing. The database refuses this too; refusing it
            # here as well means the caller is told which field is wrong rather
            # than reading a constraint name out of a driver error.
            raise ValueError('A source revision needs a source to be a revision of')

        def load(connection):
            row = connection.execute(
                text(
                    'SELECT version, lifecycle, payload FROM works '
                    'WHERE id = :id AND incarnation_id = :inc AND language_code = :lang '
                    'FOR UPDATE'
                ),
                {'id': work_id, 'inc': scope.incarnation, 'lang': scope.language},
            ).mappings().first()
            if row is None:
                return 0, False, None
            current_lifecycle = str(row['lifecycle'])
            if current_lifecycle != lifecycle and lifecycle_change(
                current_lifecycle, lifecycle
            ) == 'refused':
                raise MutationRefused('lifecycle_refused')
            return (
                int(row['version']),
                current_lifecycle == 'deleted' and lifecycle != 'deleted',
                dict(row['payload']) if row['payload'] else {},
            )

        def write(connection, version, sequence, now, state):
            params = {
                'id': work_id, 'inc': scope.incarnation, 'lang': scope.language,
                'kind': kind, 'version': version, 'lifecycle': lifecycle,
                'payload': json.dumps(payload or {}, ensure_ascii=False),
                'seq': sequence, 'now': now,
                'source_kind': source.get('kind', ''),
                'source_id': source.get('id', ''),
                'source_revision': source.get('revision', ''),
            }
            if state is None:
                connection.execute(
                    text(
                        'INSERT INTO works (id, incarnation_id, language_code, kind, '
                        'source_kind, source_id, source_revision, version, lifecycle, '
                        'payload, updated_sequence, created_at, updated_at) VALUES '
                        '(:id, :inc, :lang, :kind, :source_kind, :source_id, '
                        ':source_revision, :version, :lifecycle, CAST(:payload AS JSON), '
                        ':seq, :now, :now)'
                    ),
                    params,
                )
            else:
                connection.execute(
                    text(
                        'UPDATE works SET version = :version, lifecycle = :lifecycle, '
                        'payload = CAST(:payload AS JSON), updated_sequence = :seq, '
                        'updated_at = :now WHERE id = :id AND incarnation_id = :inc '
                        'AND language_code = :lang'
                    ),
                    params,
                )
            return 'delete' if lifecycle == 'deleted' else 'upsert'

        outcome = commit_mutation(
            self._engine,
            scope=scope,
            domain=domain,
            operation_id=operation_id,
            digest=digest,
            expected_version=expected_version,
            resource_id=work_id,
            load=load,
            write=write,
        )
        # A conflict hands back the server's text so the learner can reconcile;
        # the client still holds its own. Nothing is merged and nobody wins.
        if outcome.get('status') == 'conflict':
            outcome['server_payload'] = outcome.pop('state', None) or {}
        return outcome
