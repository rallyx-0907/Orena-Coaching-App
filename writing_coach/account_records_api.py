"""The learner's own records kept with the account: notes and highlights, private imports, typed and
Reading Transfer responses, and where a kept word was met (D4 I9, I10, I12; D-104 H-18).

Every route is served only while the account backbone is `active` (`work_api._scope`, 503 with the
state's own reason otherwise), so a client that meets `disabled` keeps the record on the device and never
claims a save. Each kind has a DETERMINISTIC work id derived on the server from the account, its
incarnation, the learning language and the client's key, so a re-open finds the same row on every device,
two accounts never touch each other's, and a re-registration starts empty (like a draft). The generic
`PUT /api/works/{id}` refuses `annotation` and `imported` (proposal 13.3): only these routes write them.

Conflict rule (proposal 2.4): `expectedVersion` on every write; a stale write is a 409 carrying the
server's copy and nothing is merged. Annotations are a set: on a 409 the client unions by id and writes
again - a client action, never a server merge of prose.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from writing_coach.core.errors import orena_http_error
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.work_repository import semantic_digest
from writing_coach.reference_backbone import Scope
from writing_coach import work_api

router = APIRouter(prefix='/api', tags=['account-records'])

# --- bounds (proposal I10: about 104 KB worst case, well under MAX_PAYLOAD_CHARS) -----------------------
MAX_HIGHLIGHTS = 80
MAX_HIGHLIGHT_CHARS = 400
MAX_NOTES = 120
MAX_NOTE_CHARS = 600
NOTE_TYPES = ('factual', 'reflection', 'question')
MAX_IMPORTS = 20
MAX_IMPORT_TEXT_CHARS = 12_000
MAX_IMPORT_URL_CHARS = 2_048
MAX_RESPONSE_ANSWER_CHARS = 4_000


def _backbone():
    return work_api._backbone  # noqa: SLF001 - one backbone, configured once for every account route


def _key(value: str, code: str) -> str:
    if not value or len(value) > 255 or any(ord(ch) < 32 for ch in value):
        raise orena_http_error(422, code, 'That is not a key this room knows.', retryable=False)
    return value


def _work_id(scope: Scope, kind: str, key: str) -> str:
    return str(stable_uuid('work', scope.account, scope.incarnation, scope.language, kind, key))


def _commit(scope: Scope, *, kind: str, ident: str, operation_id: str, expected_version: int,
            payload: dict[str, Any], source: dict[str, str], lifecycle: str = 'active',
            conflict_code: str, create_guard: Any = None) -> dict[str, Any]:
    references = {'work': ident, 'kind': kind, 'lifecycle': lifecycle, 'source': source}
    outcome = _backbone().work.commit_mutation(
        scope=scope, domain=kind, operation_id=operation_id,
        digest=semantic_digest(kind, references, payload), expected_version=expected_version,
        work_id=ident, kind=kind, payload=payload, lifecycle=lifecycle, source=source, create_guard=create_guard,
    )
    status = outcome.get('status')
    if status in {'committed', 'replay'}:
        return {'status': status, 'version': outcome.get('version')}
    if status == 'conflict':
        raise orena_http_error(
            409, conflict_code, 'This changed on another device.', retryable=False,
            context={'serverVersion': outcome.get('current_version'), 'serverPayload': outcome.get('server_payload') or {}},
        )
    reason = str(outcome.get('reason') or 'rejected')
    if reason == 'scope_denied':
        raise orena_http_error(404, 'work_not_found', 'No such record here.', retryable=False)
    raise orena_http_error(422, reason, 'This change was not accepted.', retryable=False)


def _read(scope: Scope, kind: str, key: str) -> dict[str, Any] | None:
    row = _backbone().work.get_work(scope, _work_id(scope, kind, key))
    if row is None or row['lifecycle'] == 'deleted':
        return None
    return row


# --- Notes and highlights (I10) -----------------------------------------------------------------------

class Highlight(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    segment: str = Field(default='', max_length=255)
    sentence: str = Field(default='', max_length=MAX_HIGHLIGHT_CHARS)
    at: str = Field(default='', max_length=40)


class Note(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    key: str = Field(default='', max_length=255)
    type: str = Field(default='reflection', pattern=r'^(factual|reflection|question)$')
    text: str = Field(default='', max_length=MAX_NOTE_CHARS)
    at: str = Field(default='', max_length=40)


class AnnotationSave(BaseModel):
    operationId: str = Field(min_length=8, max_length=120)
    expectedVersion: int = Field(ge=0)
    highlights: list[Highlight] = Field(default_factory=list, max_length=MAX_HIGHLIGHTS)
    notes: list[Note] = Field(default_factory=list, max_length=MAX_NOTES)
    # Clearing is a flag in the payload, never lifecycle `deleted`: a deterministic id cannot be reused.
    cleared: bool = False


def _annotation_shape(row: dict[str, Any]) -> dict[str, Any]:
    payload = row['payload'] or {}
    return {'highlights': list(payload.get('highlights') or []), 'notes': list(payload.get('notes') or []),
            'cleared': bool(payload.get('cleared')), 'version': int(row['version'])}


@router.get('/annotations/{content_id:path}')
def get_annotations(content_id: str) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    row = _read(scope, 'annotation', _key(content_id, 'content_id_invalid'))
    if row is None:
        raise orena_http_error(404, 'annotation_not_found', 'Nothing kept for this text.', retryable=False)
    return {'annotation': _annotation_shape(row)}


@router.put('/annotations/{content_id:path}')
def put_annotations(content_id: str, body: AnnotationSave) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    content_id = _key(content_id, 'content_id_invalid')
    ids = [item.id for item in body.highlights] + [item.id for item in body.notes]
    if len(set(ids)) != len(ids):
        raise orena_http_error(422, 'annotation_duplicate_id', 'Each highlight and note has its own id.', retryable=False)
    payload = ({'cleared': True} if body.cleared else {
        'highlights': [item.model_dump() for item in body.highlights],
        'notes': [item.model_dump() for item in body.notes],
    })
    return _commit(
        scope, kind='annotation', ident=_work_id(scope, 'annotation', content_id), operation_id=body.operationId,
        expected_version=body.expectedVersion, payload=payload,
        source={'kind': 'content', 'id': content_id, 'revision': ''}, conflict_code='annotation_conflict',
    )


# --- Private imports (I12) ----------------------------------------------------------------------------
#
# The public id is `text:<uuid>` or `url:<uuid>`, where <uuid> is the client's own import id; the work id
# is derived from it, so the same import meets the same row on every device. A `url:` import stores the
# reference the app fetches through its safe-fetch path, never the body.

class ImportSave(BaseModel):
    operationId: str = Field(min_length=8, max_length=120)
    expectedVersion: int = Field(ge=0)
    form: str = Field(pattern=r'^(text|url)$')
    title: str = Field(min_length=1, max_length=240)
    text: str = Field(default='', max_length=MAX_IMPORT_TEXT_CHARS)
    url: str = Field(default='', max_length=MAX_IMPORT_URL_CHARS)


def _import_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise orena_http_error(422, 'import_id_invalid', 'An import id is a UUID.', retryable=False) from None


def _import_shape(row: dict[str, Any]) -> dict[str, Any]:
    payload = row['payload'] or {}
    form = str(payload.get('form') or 'text')
    client = str(payload.get('id') or '')
    return {'id': f'{form}:{client}', 'form': form, 'title': str(payload.get('title') or ''),
            'text': str(payload.get('text') or ''), 'url': str(payload.get('url') or ''),
            'version': int(row['version'])}


@router.get('/imports')
def list_imports(limit: int = Query(20, ge=1, le=work_api.LIST_LIMIT)) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    rows = _backbone().work.list_works(scope, kind='imported', source_kind='imported', limit=limit)
    return {'imports': [_import_shape(row) for row in rows]}


@router.get('/imports/{import_id}')
def get_import(import_id: str) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    row = _read(scope, 'imported', _import_uuid(import_id))
    if row is None:
        raise orena_http_error(404, 'import_not_found', 'That import is not kept.', retryable=False)
    return {'import': _import_shape(row)}


@router.put('/imports/{import_id}')
def put_import(import_id: str, body: ImportSave) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    client = _import_uuid(import_id)
    if body.form == 'text' and not body.text.strip():
        raise orena_http_error(422, 'import_text_empty', 'There is nothing to keep.', retryable=False)
    if body.form == 'url' and not body.url.strip().lower().startswith(('http://', 'https://')):
        raise orena_http_error(422, 'import_url_invalid', 'A link must start with http:// or https://.', retryable=False)
    ident = _work_id(scope, 'imported', client)

    def at_most_the_limit(connection) -> None:
        # Counted inside the creating transaction, after the account's stream lock: two creations at 19 cannot both pass.
        from sqlalchemy import text as sql
        from writing_coach.persistence.mutation_commit import MutationRefused

        held = connection.execute(
            sql("SELECT count(*) FROM works WHERE incarnation_id = :inc AND language_code = :lang "
                "AND kind = 'imported' AND lifecycle <> 'deleted'"),
            {'inc': scope.incarnation, 'lang': scope.language},
        ).scalar_one()
        if held >= MAX_IMPORTS:
            raise MutationRefused('import_limit')

    payload = {'id': client, 'form': body.form, 'title': body.title.strip(),
               **({'text': body.text} if body.form == 'text' else {'url': body.url.strip()})}
    return _commit(
        scope, kind='imported', ident=ident, operation_id=body.operationId, expected_version=body.expectedVersion,
        payload=payload, source={'kind': 'imported', 'id': client, 'revision': ''}, conflict_code='import_conflict',
        create_guard=at_most_the_limit,
    )


@router.delete('/imports/{import_id}')
def delete_import(import_id: str, operationId: str = Query(min_length=8, max_length=120),
                  expectedVersion: int = Query(ge=1)) -> dict[str, Any]:
    """Delete a private import. Anything that pointed at it now finds it unavailable (ADA section 7)."""
    scope = work_api._scope()  # noqa: SLF001
    client = _import_uuid(import_id)
    ident = _work_id(scope, 'imported', client)
    row = _backbone().work.get_work(scope, ident)
    if row is None:
        raise orena_http_error(404, 'import_not_found', 'That import is not kept.', retryable=False)
    # A tombstone WITHOUT the content: deleting is erasing. Only what says which import this was stays (its id and
    # form); the title, the text and the link are dropped from the stored row, not merely hidden from the reads.
    tombstone = {'id': client, 'form': str((row['payload'] or {}).get('form') or 'text')}
    return _commit(
        scope, kind='imported', ident=ident, operation_id=operationId, expected_version=expectedVersion,
        payload=tombstone, source={'kind': 'imported', 'id': client, 'revision': ''},
        lifecycle='deleted', conflict_code='import_conflict',
    )


# --- Typed responses and Reading Transfer (I8, I9) --------------------------------------------------
#
# Learner work, NOT evidence (D-104 H-3): what the learner wrote and the coaching that came back. It is
# never scored and never read as understanding. `key` names the take: `transfer:<content>:<sentence>:<n>`,
# `freetalk:<invitation>:<n>`; the server derives the work id from it.

class ResponseSave(BaseModel):
    operationId: str = Field(min_length=8, max_length=120)
    expectedVersion: int = Field(ge=0)
    mode: str = Field(min_length=1, max_length=40, pattern=r'^[a-z][a-z0-9_.-]*$')
    answer: str = Field(default='', max_length=MAX_RESPONSE_ANSWER_CHARS)
    coaching: str = Field(default='', max_length=MAX_RESPONSE_ANSWER_CHARS)
    sentenceRef: str = Field(default='', max_length=255)
    sourceKind: str = Field(default='', max_length=40, pattern=r'^(|[a-z][a-z0-9_.-]*)$')
    sourceId: str = Field(default='', max_length=200)


def _response_shape(row: dict[str, Any]) -> dict[str, Any]:
    payload = row['payload'] or {}
    return {**{name: str(payload.get(name) or '') for name in ('mode', 'answer', 'coaching', 'sentenceRef')},
            'version': int(row['version'])}


@router.get('/responses/{key:path}')
def get_response(key: str) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    row = _read(scope, 'response', _key(key, 'response_key_invalid'))
    if row is None:
        raise orena_http_error(404, 'response_not_found', 'No response kept for this.', retryable=False)
    return {'response': _response_shape(row)}


@router.put('/responses/{key:path}')
def put_response(key: str, body: ResponseSave) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    key = _key(key, 'response_key_invalid')
    if bool(body.sourceKind) != bool(body.sourceId):
        raise orena_http_error(422, 'source_incomplete', 'A source is both kind and id, or neither.', retryable=False)
    payload = {'mode': body.mode, 'answer': body.answer, 'coaching': body.coaching, 'sentenceRef': body.sentenceRef}
    return _commit(
        scope, kind='response', ident=_work_id(scope, 'response', key), operation_id=body.operationId,
        expected_version=body.expectedVersion, payload=payload,
        source={'kind': body.sourceKind, 'id': body.sourceId, 'revision': ''} if body.sourceKind else {},
        conflict_code='response_conflict',
    )


# --- Where a kept word was met (I12d) -------------------------------------------------------------------

class ProvenanceIn(BaseModel):
    operationId: str = Field(min_length=8, max_length=120)
    reason: str = Field(min_length=1, max_length=40)
    sourceKind: str = Field(default='', max_length=40)
    sourceId: str = Field(default='', max_length=200)
    sourceRevision: str = Field(default='', max_length=120)
    focus: str = Field(default='', max_length=1200)
    availability: str = Field(default='unknown', max_length=20)


def _saved_word_id(scope: Scope, word: str) -> str | None:
    from sqlalchemy import text

    engine = _backbone().provenance._engine  # noqa: SLF001
    with engine.connect() as connection:
        found = connection.execute(
            text('SELECT id FROM saved_words WHERE user_id = :user AND language_code = :lang '
                 'AND normalized_word = :word'),
            {'user': scope.account, 'lang': scope.language, 'word': word.casefold()},
        ).scalar()
    return str(found) if found else None


@router.get('/library/vocabulary/{word}/provenance')
def get_word_provenance(word: str) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    saved = _saved_word_id(scope, _key(word, 'word_invalid'))
    if saved is None:
        raise orena_http_error(404, 'word_not_found', 'That word is not kept.', retryable=False)
    rows = _backbone().provenance.occurrences_for(scope, saved)
    return {'occurrences': [
        {'id': str(row['id']), 'reason': row['reason'], 'focus': row['focus'],
         'source': {'kind': row['source_kind'], 'id': row['source_id'], 'revision': row['source_revision']},
         'availability': row['availability']}
        for row in rows
    ]}


@router.post('/library/vocabulary/{word}/provenance')
def attach_word_provenance(word: str, body: ProvenanceIn) -> dict[str, Any]:
    from writing_coach.persistence.provenance_repository import ProvenanceRejected

    scope = work_api._scope()  # noqa: SLF001
    saved = _saved_word_id(scope, _key(word, 'word_invalid'))
    if saved is None:
        raise orena_http_error(404, 'word_not_found', 'That word is not kept.', retryable=False)
    # One id per operation: a retry replays the occurrence it made, a different operation is another one.
    occurrence = str(stable_uuid('provenance', scope.account, scope.incarnation, scope.language, body.operationId))
    try:
        outcome = _backbone().provenance.attach_occurrence(
            scope=scope, occurrence_id=occurrence, operation_id=body.operationId, saved_word_id=saved,
            reason=body.reason, focus=body.focus, availability=body.availability,
            source={'kind': body.sourceKind, 'id': body.sourceId, 'revision': body.sourceRevision}
            if body.sourceKind else {},
        )
    except ProvenanceRejected as refused:
        raise orena_http_error(422, refused.reason, 'That was not accepted.', retryable=False) from refused
    status = outcome.get('status')
    if status in {'committed', 'replay'}:
        return {'status': status, 'id': occurrence}
    reason = str(outcome.get('reason') or 'rejected')
    if reason in {'cross_account_saved_word', 'cross_language_saved_word', 'unknown_saved_word', 'scope_denied'}:
        raise orena_http_error(404, 'word_not_found', 'That word is not kept.', retryable=False)
    raise orena_http_error(422, reason, 'That was not accepted.', retryable=False)
