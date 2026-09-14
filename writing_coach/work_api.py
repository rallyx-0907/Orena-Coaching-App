"""Account work over HTTP - the first I2 write path (drafts, responses,
conversations), served only while the account backbone is `active`.

`GET /api/account-backbone` says which of the three states the deployment is
in, so a surface can tell the truth: `disabled` means "this device keeps your
drafts" by decision, `unavailable` means something is wrong and it must not
claim anything is saved, `active` means work is kept with the account.

The work routes refuse with the state's own reason unless `active`; nothing
here falls back to device memory on the server's behalf - the client decides,
knowing the state. When active:

  * `GET  /api/works/{id}` - one work in the request's account and learning
    language; another account's or another language's is not found.
  * `PUT  /api/works/{id}` - one mutation through `commit_mutation`: a
    client-chosen operation id, the version it edited from, and the whole new
    payload. `committed` and `replay` (a lost acknowledgment retried) answer
    200 with the same body; `conflict` answers 409 with the server's text and
    version, nothing merged; `rejected` answers 422 with its reason.
  * `GET  /api/works/changes?after=` - the account's change stream, every
    language, in sequence order; the client filters, the server never skips.

Identity: the account is the request's user key (`stable_uuid('user', key)`,
the same id every PostgreSQL owner uses) and the incarnation is resolved on
each request with `ensure_active` - the sign-in path, which meets the deletion
barrier (403 `account_deleted`) instead of resurrecting a deleted account. The
request's claim is never evidence: `commit_mutation` re-resolves the account
from the incarnation row.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from writing_coach.account_backbone import DISABLED, AccountBackbone
from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.work_repository import semantic_digest
from writing_coach.reference_backbone import Scope
from writing_coach.work_contract import LIFECYCLE, WORK_KINDS

router = APIRouter(prefix='/api', tags=['work'])

_backbone: AccountBackbone = AccountBackbone(DISABLED)
_user_key: Callable[[], str] = current_user_key
_language: Callable[[], str] = current_language_code

# A payload is a learner's own text plus a little structure; the bound keeps
# one request from becoming a storage channel.
MAX_PAYLOAD_CHARS = 200_000
CHANGES_LIMIT = 200


def configure_work(backbone: AccountBackbone, *, user_key: Callable[[], str] | None = None,
                   language: Callable[[], str] | None = None) -> None:
    global _backbone, _user_key, _language
    _backbone = backbone
    _user_key = user_key or current_user_key
    _language = language or current_language_code


class SourceRef(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    id: str = Field(min_length=1, max_length=200)
    revision: str = Field(default='', max_length=120)


class WorkMutation(BaseModel):
    operationId: str = Field(min_length=8, max_length=120)
    expectedVersion: int = Field(ge=0)
    kind: str = 'draft'
    lifecycle: str = 'active'
    payload: dict[str, Any] = Field(default_factory=dict)
    source: SourceRef | None = None


@router.get('/account-backbone')
def account_backbone_state() -> dict[str, str]:
    return {'state': _backbone.state}


def _scope() -> Scope:
    if not _backbone.is_active:
        # `disabled` is a decision, `unavailable` a fault; both are said as
        # they are, never as "saved".
        raise orena_http_error(
            503, f'account_backbone_{_backbone.state}',
            'Work is not kept with the account on this deployment.',
            retryable=False, context={'state': _backbone.state},
        )
    from writing_coach.persistence.incarnation_repository import DeletionBarrier

    account = str(stable_uuid('user', _user_key()))
    try:
        incarnation = _backbone.incarnations.ensure_active(account)
    except DeletionBarrier:
        raise orena_http_error(403, 'account_deleted', 'This account was deleted.', retryable=False) from None
    except ValueError:
        raise orena_http_error(409, 'account_not_ready', 'This account is not set up yet.', retryable=True) from None
    return Scope(account, incarnation, _language().casefold())


def _work_id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise orena_http_error(422, 'work_id_invalid', 'A work id is a UUID.', retryable=False) from None


def _shape(row: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': str(row['id']),
        'version': int(row['version']),
        'lifecycle': row['lifecycle'],
        'language': row['language_code'],
        'payload': row['payload'] or {},
        'sequence': int(row['updated_sequence']),
    }


@router.get('/works/changes')
def work_changes(after: int = Query(0, ge=0), limit: int = Query(CHANGES_LIMIT, ge=1, le=CHANGES_LIMIT)) -> dict[str, Any]:
    scope = _scope()
    rows = _backbone.work.changes_after(scope, after, limit)
    changes = [
        {
            'sequence': int(row['sequence']), 'language': row['language_code'],
            'domain': row['object_domain'], 'id': str(row['object_id']),
            'version': int(row['object_version']), 'change': row['change_kind'],
        }
        for row in rows
    ]
    return {
        'changes': changes,
        'after': changes[-1]['sequence'] if changes else after,
        # A full page may have more behind it; a short one is the end for now.
        'more': len(changes) == limit,
    }


@router.get('/works/{work_id}')
def get_work(work_id: str) -> dict[str, Any]:
    scope = _scope()
    row = _backbone.work.get_work(scope, _work_id(work_id))
    if row is None:
        raise orena_http_error(404, 'work_not_found', 'No such work here.', retryable=False)
    return {'work': _shape(row)}


@router.put('/works/{work_id}')
def put_work(work_id: str, body: WorkMutation) -> dict[str, Any]:
    ident = _work_id(work_id)
    if body.kind not in WORK_KINDS:
        raise orena_http_error(422, 'work_kind_invalid', 'Unknown kind of work.', retryable=False)
    if body.lifecycle not in LIFECYCLE:
        raise orena_http_error(422, 'lifecycle_invalid', 'Unknown lifecycle.', retryable=False)
    if len(json.dumps(body.payload, ensure_ascii=False)) > MAX_PAYLOAD_CHARS:
        raise orena_http_error(413, 'work_too_large', 'This work is too large to keep.', retryable=False)
    scope = _scope()
    source = body.source.model_dump() if body.source else {}
    references = {'work': ident, 'kind': body.kind, 'lifecycle': body.lifecycle, 'source': source}
    outcome = _backbone.work.commit_mutation(
        scope=scope, domain=body.kind, operation_id=body.operationId,
        digest=semantic_digest(body.kind, references, body.payload),
        expected_version=body.expectedVersion, work_id=ident, kind=body.kind,
        payload=body.payload, lifecycle=body.lifecycle, source=source,
    )
    status = outcome.get('status')
    if status in {'committed', 'replay'}:
        return {'status': status, 'version': outcome.get('version'), 'sequence': outcome.get('sequence')}
    if status == 'conflict':
        raise orena_http_error(
            409, 'work_conflict', 'This work changed since you opened it.', retryable=False,
            context={'serverVersion': outcome.get('current_version'),
                     'serverPayload': outcome.get('server_payload') or {}},
        )
    reason = str(outcome.get('reason') or 'rejected')
    if reason == 'scope_denied':
        # Another account's or another language's work: not found here, the
        # same answer a read gives, rather than a hint that it exists.
        raise orena_http_error(404, 'work_not_found', 'No such work here.', retryable=False)
    raise orena_http_error(422, reason, 'This change was not accepted.', retryable=False)


# --- Drafts by the item they belong to ---------------------------------------
#
# The Writing room knows a piece by its item key (`essay:6`, `story:…`,
# `expression:free`), not by a work UUID. The work id is derived on the server
# from the account's incarnation, the learning language and the key, so the
# same piece meets the same draft on every device; two accounts writing about
# the same item never touch each other's row; and an explicit re-registration
# (a new incarnation) starts with no draft at all - `works.id` is globally
# unique, and an id without the incarnation would name the old one's row.

DRAFT_TEXT_LIMIT = 12_000
DRAFT_TASK_LIMIT = 240


class DraftSave(BaseModel):
    operationId: str = Field(min_length=8, max_length=120)
    expectedVersion: int = Field(ge=0)
    text: str = Field(default='', max_length=DRAFT_TEXT_LIMIT)
    task: str = Field(default='', max_length=DRAFT_TASK_LIMIT)


def _draft_key(key: str) -> str:
    if not key or len(key) > 200 or any(ord(ch) < 32 for ch in key):
        raise orena_http_error(422, 'draft_key_invalid', 'Not a piece this room knows.', retryable=False)
    return key


def _draft_work_id(scope: Scope, key: str) -> str:
    return str(stable_uuid('work', scope.account, scope.incarnation, scope.language, 'draft', key))


@router.get('/drafts/{key}')
def get_draft(key: str) -> dict[str, Any]:
    key = _draft_key(key)
    scope = _scope()
    row = _backbone.work.get_work(scope, _draft_work_id(scope, key))
    if row is None or row['lifecycle'] == 'deleted':
        raise orena_http_error(404, 'draft_not_found', 'No draft kept for this piece.', retryable=False)
    payload = row['payload'] or {}
    return {'draft': {'text': str(payload.get('text', '')), 'task': str(payload.get('task', '')),
                      'version': int(row['version'])}}


@router.put('/drafts/{key}')
def put_draft(key: str, body: DraftSave) -> dict[str, Any]:
    key = _draft_key(key)
    scope = _scope()
    ident = _draft_work_id(scope, key)
    payload = {'text': body.text, 'task': body.task}
    source = {'kind': 'item', 'id': key, 'revision': ''}
    references = {'work': ident, 'kind': 'draft', 'lifecycle': 'active', 'source': source}
    outcome = _backbone.work.commit_mutation(
        scope=scope, domain='draft', operation_id=body.operationId,
        digest=semantic_digest('draft', references, payload),
        expected_version=body.expectedVersion, work_id=ident, kind='draft',
        payload=payload, lifecycle='active', source=source,
    )
    status = outcome.get('status')
    if status in {'committed', 'replay'}:
        return {'status': status, 'version': outcome.get('version')}
    if status == 'conflict':
        server = outcome.get('server_payload') or {}
        raise orena_http_error(
            409, 'draft_conflict', 'This draft changed on another device.', retryable=False,
            context={'serverVersion': outcome.get('current_version'),
                     'serverText': str(server.get('text', '')), 'serverTask': str(server.get('task', ''))},
        )
    raise orena_http_error(422, str(outcome.get('reason') or 'rejected'), 'This draft was not kept.',
                           retryable=False)
