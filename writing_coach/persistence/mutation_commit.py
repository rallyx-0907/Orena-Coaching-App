"""One transactional envelope for every account mutation.

PROPOSAL — the tables this touches are in `migrations/proposed/20260908_0005`,
awaiting re-review and schema authorization. No caller is wired to it.

Work and provenance are different domains that need identical guarantees: one
sequence per account allocated under a held lock, one receipt per scoped
operation, one change record per committed change, and a retry that returns
what its first attempt committed. Writing that twice would let the two drift,
and the half that drifted would be the half nobody was looking at. So the
envelope lives here and each domain supplies only what is domain-specific: how
to read its current state, and how to write its row.

The order inside the transaction, and why:

  1. lock the account's stream head, held to commit, so the sequence is a total
     order per account rather than an approximation of one;
  2. **re-resolve the account from the incarnation** and reject a mismatch -
     the request says who it is, and the request is not evidence;
  3. look up the receipt for this scoped operation *before* comparing versions,
     so a retry whose acknowledgment was lost gets its original result rather
     than a conflict against the version its own first attempt produced;
  4. read the domain's current state, under whatever lock that domain needs;
  5. decide, with `reference_backbone.mutation_decision`;
  6. on commit, allocate from the held head and write the domain row, the
     change record and the receipt together.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import Mutation, Receipt, Scope, mutation_decision
from writing_coach.work_contract import validate_domain


@dataclass(frozen=True)
class ResourceState:
    """What the database says about the resource a command names.

    `scope` is the resource's own scope, read from its row - not the scope the
    request claimed. The envelope used to pass the request's scope in as the
    resource's, which made `mutation_decision`'s first check compare a value
    with itself: a real scope mismatch could not be detected there, and a
    resource owned by another incarnation looked simply absent, so creation
    proceeded and failed on a primary key instead of being denied.

    An absent resource reports the command's own scope, because creating one
    where nothing exists is exactly what the requester is allowed to do.
    """

    version: int
    deleted: bool
    scope: Scope
    state: Any = None


class MutationOutcome(dict):
    """`committed`, `replay`, `conflict` or `rejected`, with what a caller needs."""


class MutationRefused(Exception):
    """A domain-specific refusal raised from `load`; rolls the transaction back."""

    def __init__(self, reason: str, **detail: Any):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def commit_mutation(
    engine: Engine,
    *,
    scope: Scope,
    domain: str,
    operation_id: str,
    digest: str,
    expected_version: int,
    resource_id: str,
    load: Callable[[Any], ResourceState],
    write: Callable[..., str],
) -> MutationOutcome:
    """Run one mutation. `load` reads domain state; `write` writes the row.

    `load(connection) -> ResourceState`, reporting the resource's *persisted*
    version, deletion and scope. Version 0 means the resource does not exist,
    matching the creation convention; a resource that does exist reports the
    scope it actually belongs to, so a command naming another account's or
    another language's resource is denied rather than treated as a creation.
    `load` may raise `MutationRefused` for a domain rule - a parent in another
    account, say - and nothing will have been written.

    `write(connection, version, sequence, now, state) -> change_kind`.
    """
    validate_domain(domain)
    now = datetime.now(UTC)
    with engine.begin() as connection:
        head = connection.execute(
            text(
                'SELECT next_sequence FROM account_streams '
                'WHERE incarnation_id = :inc FOR UPDATE'
            ),
            {'inc': scope.incarnation},
        ).scalar_one_or_none()
        if head is None:
            return MutationOutcome(status='rejected', reason='unknown_account_stream')

        # The account this incarnation actually belongs to, read from the row
        # rather than taken from the request. A request that presents someone
        # else's incarnation with its own account id would otherwise have its
        # own claim used as the account half of every identity below.
        owner = connection.execute(
            text('SELECT user_id, status FROM account_incarnations WHERE id = :inc'),
            {'inc': scope.incarnation},
        ).mappings().first()
        if owner is None:
            return MutationOutcome(status='rejected', reason='unknown_incarnation')
        if str(owner['user_id']) != str(scope.account):
            return MutationOutcome(status='rejected', reason='account_incarnation_mismatch')
        if owner['status'] != 'active':
            return MutationOutcome(status='rejected', reason='account_not_active')
        resolved_account = str(owner['user_id'])

        receipt_row = connection.execute(
            text(
                'SELECT language_code, domain, resource_id, operation_id, '
                'request_digest, expected_version, result_ref, committed_version '
                'FROM mutation_receipts WHERE incarnation_id = :inc '
                'AND domain = :domain AND operation_id = :op'
            ),
            {'inc': scope.incarnation, 'domain': domain, 'op': operation_id},
        ).mappings().first()

        try:
            resource = load(connection)
        except MutationRefused as refusal:
            return MutationOutcome(status='rejected', reason=refusal.reason, **refusal.detail)

        command = Mutation(scope, domain, resource_id, operation_id, digest, expected_version)
        receipt = None
        if receipt_row is not None:
            # Every field from a persisted column, including the account, which
            # comes from the incarnation row above and not from `scope`.
            receipt = Receipt(
                Mutation(
                    Scope(
                        resolved_account,
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

        # The resource's own scope, not the request's. This is the comparison
        # that makes `scope_denied` reachable at all.
        verdict = mutation_decision(
            command, resource.scope, resource.version, receipt, deleted=resource.deleted
        )
        if verdict == 'replay':
            return MutationOutcome(
                status='replay',
                result_ref=receipt.result_ref,
                version=receipt.committed_version,
            )
        if verdict == 'version_conflict':
            return MutationOutcome(
                status='conflict', current_version=resource.version, state=resource.state
            )
        if verdict != 'commit':
            return MutationOutcome(status='rejected', reason=verdict)

        sequence = int(head)
        connection.execute(
            text(
                'UPDATE account_streams SET next_sequence = :next, updated_at = :now '
                'WHERE incarnation_id = :inc'
            ),
            {'next': sequence + 1, 'now': now, 'inc': scope.incarnation},
        )
        new_version = resource.version + 1
        change_kind = write(connection, new_version, sequence, now, resource.state)
        connection.execute(
            text(
                'INSERT INTO change_records (id, incarnation_id, sequence, '
                'language_code, object_domain, object_id, object_version, '
                'change_kind, created_at) VALUES (:id, :inc, :seq, :lang, :domain, '
                ':object_id, :version, :change_kind, :now)'
            ),
            {
                'id': uuid.uuid4(), 'inc': scope.incarnation, 'seq': sequence,
                'lang': scope.language, 'domain': domain, 'object_id': resource_id,
                'version': new_version, 'change_kind': change_kind, 'now': now,
            },
        )
        connection.execute(
            text(
                'INSERT INTO mutation_receipts (id, incarnation_id, language_code, '
                'domain, resource_id, operation_id, request_digest, expected_version, '
                'result_ref, committed_version, sequence, created_at) VALUES '
                '(:id, :inc, :lang, :domain, :resource, :op, :digest, :expected, '
                ':result_ref, :version, :seq, :now)'
            ),
            {
                'id': uuid.uuid4(), 'inc': scope.incarnation, 'lang': scope.language,
                'domain': domain, 'resource': resource_id, 'op': operation_id,
                'digest': digest, 'expected': expected_version,
                'result_ref': resource_id, 'version': new_version,
                'seq': sequence, 'now': now,
            },
        )
        return MutationOutcome(
            status='committed', result_ref=resource_id, version=new_version,
            sequence=sequence,
        )
