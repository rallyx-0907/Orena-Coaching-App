"""The work aggregate: drafts, responses and conversations.

LIVE ON THE SANDBOX ONLY — the tables this reads and writes are in
migration `20260908_0005`. The sandbox runtime runs with
`ORENA_ACCOUNT_BACKBONE=on`, and `work_api` serves the Writing room's drafts
through this; production and preview do not run it.

The transaction, the sequence, the receipt and the change record are
`mutation_commit.commit_mutation`, shared with every other account mutation.
What is here is only what is specific to work: reading a work row under lock,
what a lifecycle change means, and refusing a domain this owner does not own.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.persistence.mutation_commit import (
    MutationOutcome,
    MutationRefused,
    ResourceState,
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
        create_guard: Any = None,
    ) -> MutationOutcome:
        """`create_guard(connection)` runs only when the work does not exist yet, inside the transaction and after
        the account's stream lock is held, so a per-account bound is checked where no other creation can interleave.
        It refuses by raising `MutationRefused`."""
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
            # By id alone, and joined to the incarnation so the row can say
            # which account it belongs to. Scoping the lookup instead - id AND
            # incarnation AND language - made another incarnation's work look
            # absent, so a creation went ahead and failed on the primary key
            # rather than being denied for what it was.
            row = connection.execute(
                text(
                    'SELECT w.incarnation_id, w.language_code, w.version, w.lifecycle, '
                    'w.payload, i.user_id FROM works w '
                    'JOIN account_incarnations i ON i.id = w.incarnation_id '
                    'WHERE w.id = :id FOR UPDATE OF w'
                ),
                {'id': work_id},
            ).mappings().first()
            if row is None:
                # Nothing there: creating one in the requester's own scope is
                # exactly what they are allowed to do.
                if create_guard is not None:
                    create_guard(connection)
                return ResourceState(0, False, scope, None)
            owner = Scope(
                str(row['user_id']),
                str(row['incarnation_id']),
                str(row['language_code']),
            )
            if owner != scope:
                # Someone else's work, or this account's work in another
                # language. Report it as it is and let the decision deny it;
                # no lifecycle rule applies to a resource that is not ours.
                return ResourceState(int(row['version']), False, owner, None)
            current_lifecycle = str(row['lifecycle'])
            if current_lifecycle != lifecycle and lifecycle_change(
                current_lifecycle, lifecycle
            ) == 'refused':
                raise MutationRefused('lifecycle_refused')
            return ResourceState(
                int(row['version']),
                current_lifecycle == 'deleted' and lifecycle != 'deleted',
                owner,
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
            # Version 1 is creation and nothing else: the new version is the
            # loaded one plus a step, so only an absent resource reaches 1.
            # Reading it off `state` was ambiguous once a cross-scope resource
            # also reported no state.
            if version == 1:
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


# --- D4: bounded lists, and conversation turns (proposal 2.3 and I6) ----------------------------------

class TurnRefused(Exception):
    """A turn the conversation rules refuse; raised inside the transaction so nothing is written."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


MAX_CONVERSATION_TURNS = 24
MAX_TURN_CHARS = 2400
WORKS_LIST_LIMIT = 50


def _turn_of(row: dict[str, Any]) -> dict[str, Any]:
    """A stored turn as the client's own: `content` holds the turn as JSON, the columns hold order and role."""
    try:
        body = json.loads(row['content'])
    except (TypeError, ValueError):
        body = {}
    body = body if isinstance(body, dict) else {}
    return {
        'ordinal': int(row['ordinal']), 'role': row['author_role'], 'id': str(body.get('id') or ''),
        'text': str(body.get('text') or ''), 'origin': str(body.get('origin') or ''),
        'reply_to': body.get('reply_to'), 'meaning': str(body.get('meaning') or ''),
        'support': str(body.get('support') or ''),
    }


def _list_works(self, scope: Scope, *, kind: str = '', source_kind: str = '', limit: int = 20,
                deleted: bool = False) -> list[dict[str, Any]]:
    """The newest works of an account and language, by change sequence, never deleted ones (`deleted=True` lists
    only the tombstones: their ids, which carry no content, so a device can learn what was removed).

    `ix_works_scope_sequence (incarnation_id, language_code, updated_sequence, id)` serves the range; `kind`
    narrows after it, which is fine at a learner's scale.
    """
    bound = max(1, min(int(limit), WORKS_LIST_LIMIT))
    clauses = ['incarnation_id = :inc', 'language_code = :lang', "lifecycle = 'deleted'" if deleted else "lifecycle <> 'deleted'"]
    params: dict[str, Any] = {'inc': scope.incarnation, 'lang': scope.language, 'limit': bound}
    if kind:
        clauses.append('kind = :kind')
        params['kind'] = kind
    if source_kind:
        clauses.append('source_kind = :source_kind')
        params['source_kind'] = source_kind
    with self._engine.connect() as connection:
        rows = connection.execute(
            text(
                'SELECT id, kind, version, lifecycle, payload, language_code, updated_sequence, '
                'source_kind, source_id, source_revision FROM works WHERE ' + ' AND '.join(clauses)
                + ' ORDER BY updated_sequence DESC, id LIMIT :limit'
            ),
            params,
        ).mappings().all()
    return [dict(row) for row in rows]


def _list_turns(self, scope: Scope, work_id: str) -> list[dict[str, Any]]:
    with self._engine.connect() as connection:
        rows = connection.execute(
            text(
                'SELECT t.ordinal, t.author_role, t.content FROM work_turns t '
                'WHERE t.work_id = :id AND t.incarnation_id = :inc AND t.language_code = :lang '
                'ORDER BY t.ordinal'
            ),
            {'id': work_id, 'inc': scope.incarnation, 'lang': scope.language},
        ).mappings().all()
    return [_turn_of(dict(row)) for row in rows]


def _append_turn(
    self,
    *,
    scope: Scope,
    work_id: str,
    operation_id: str,
    digest: str,
    expected_head: int,
    role: str,
    turn: dict[str, Any],
    header: dict[str, Any] | None = None,
    ended: bool = False,
) -> MutationOutcome:
    """Append ONE turn to a conversation at the head the writer saw (ADA section 4).

    The head is the number of turns. A retry of the same operation returns the turn it committed; a
    different append at a head that has moved is a conflict; a turn is never inserted behind the head or
    written ahead of it. The role alternates learner, partner from a learner first turn; a partner turn
    answers the learner turn before it; a client turn id is used once; a conversation that has ended or
    reached its turn limit takes no more. Those rules are checked in the writing transaction, under the
    conversation's row lock, so two simultaneous appends cannot both pass.
    """
    header = header or {}

    def load(connection):
        row = connection.execute(
            text(
                'SELECT w.incarnation_id, w.language_code, w.kind, w.lifecycle, w.payload, i.user_id '
                'FROM works w JOIN account_incarnations i ON i.id = w.incarnation_id '
                'WHERE w.id = :id FOR UPDATE OF w'
            ),
            {'id': work_id},
        ).mappings().first()
        if row is None:
            return ResourceState(0, False, scope, None)
        owner = Scope(str(row['user_id']), str(row['incarnation_id']), str(row['language_code']))
        if owner != scope:
            return ResourceState(0, False, owner, None)
        if row['kind'] != 'conversation':
            raise MutationRefused('not_a_conversation')
        head = connection.execute(
            text('SELECT count(*) FROM work_turns WHERE work_id = :id'), {'id': work_id}
        ).scalar_one()
        return ResourceState(int(head), row['lifecycle'] == 'deleted', owner, dict(row['payload'] or {}))

    def write(connection, version, sequence, now, state):
        expected_role = 'learner' if (version - 1) % 2 == 0 else 'partner'
        if version > MAX_CONVERSATION_TURNS:
            raise TurnRefused('turn_limit')
        if (state or {}).get('ended'):
            raise TurnRefused('conversation_ended')
        if role != expected_role:
            raise TurnRefused('role_order')
        text_value = str(turn.get('text') or '')
        if not text_value.strip() or len(text_value) > MAX_TURN_CHARS:
            raise TurnRefused('turn_text_invalid')
        client_id = str(turn.get('id') or '')
        if not client_id:
            raise TurnRefused('turn_id_missing')
        previous = connection.execute(
            text('SELECT content FROM work_turns WHERE work_id = :id ORDER BY ordinal'), {'id': work_id}
        ).scalars().all()
        seen = []
        for content in previous:
            try:
                seen.append(str((json.loads(content) or {}).get('id') or ''))
            except (TypeError, ValueError):
                seen.append('')
        if client_id in seen:
            raise TurnRefused('duplicate_turn_id')
        if role == 'partner' and turn.get('reply_to') != (seen[-1] if seen else None):
            raise TurnRefused('reply_to_mismatch')
        body = {
            'id': client_id, 'text': text_value.strip(), 'origin': str(turn.get('origin') or '')[:40],
            'reply_to': turn.get('reply_to') if role == 'partner' else None,
            'meaning': str(turn.get('meaning') or '')[:MAX_TURN_CHARS], 'support': str(turn.get('support') or '')[:32],
        }
        payload = dict(state or {})
        if version == 1:
            payload = {'title': str(header.get('title') or '')[:240],
                       'situation': str(header.get('situation') or '')[:1200], 'ended': False}
        if ended:
            payload['ended'] = True
        params = {'id': work_id, 'inc': scope.incarnation, 'lang': scope.language, 'seq': sequence, 'now': now,
                  'payload': json.dumps(payload, ensure_ascii=False)}
        if version == 1:
            connection.execute(
                text(
                    'INSERT INTO works (id, incarnation_id, language_code, kind, source_kind, source_id, '
                    "source_revision, version, lifecycle, payload, updated_sequence, created_at, updated_at) VALUES "
                    "(:id, :inc, :lang, 'conversation', '', '', '', 1, 'active', CAST(:payload AS JSON), :seq, :now, :now)"
                ),
                params,
            )
        else:
            connection.execute(
                text(
                    'UPDATE works SET version = version + 1, payload = CAST(:payload AS JSON), '
                    'updated_sequence = :seq, updated_at = :now WHERE id = :id AND incarnation_id = :inc '
                    'AND language_code = :lang'
                ),
                params,
            )
        connection.execute(
            text(
                'INSERT INTO work_turns (id, work_id, incarnation_id, language_code, ordinal, author_role, content, '
                'source_revision, created_at) VALUES (:tid, :id, :inc, :lang, :ordinal, :role, :content, :rev, :now)'
            ),
            {'tid': str(uuid.uuid4()), 'id': work_id, 'inc': scope.incarnation, 'lang': scope.language,
             'ordinal': version, 'role': role, 'content': json.dumps(body, ensure_ascii=False), 'rev': '', 'now': now},
        )
        return 'upsert'

    try:
        outcome = commit_mutation(
            self._engine, scope=scope, domain='conversation', operation_id=operation_id, digest=digest,
            expected_version=expected_head, resource_id=work_id, load=load, write=write,
        )
    except TurnRefused as refused:
        return MutationOutcome(status='rejected', reason=refused.reason)
    if outcome.get('status') == 'conflict':
        outcome['server_head'] = outcome.get('current_version')
        outcome.pop('state', None)
    return outcome


PostgresWorkRepository.list_works = _list_works
PostgresWorkRepository.list_turns = _list_turns
PostgresWorkRepository.append_turn = _append_turn
