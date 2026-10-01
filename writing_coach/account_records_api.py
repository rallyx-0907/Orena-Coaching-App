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

import hashlib
import logging
import os
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
# Ids of removed highlights and notes the server remembers, newest last (D4 I10). Ids are minted once by the
# device that made the item, so a removed id can never legitimately come back: a write that carries one is refused.
MAX_TOMBSTONES = 500
NOTE_TYPES = ('factual', 'reflection', 'question')
_logger = logging.getLogger(__name__)
MAX_IMPORTS = 20
PENDING_SWEEP_PER_READ = 5  # a list read finishes at most this many owed file removals
# Deleted imports are tombstones that are never removed, so "create, delete, create" would grow rows without bound
# while the live count stays under MAX_IMPORTS. The total of an account's import rows, live and deleted, is bounded
# separately (operator configuration, never a learner-facing number; limits review P1-1).
IMPORT_TOMBSTONES_FLOOR = 52
IMPORT_TOMBSTONES_DEFAULT = 360


def _import_row_bound() -> int:
    raw = os.environ.get('ORENA_LIMIT_IMPORT_TOMBSTONES', '').strip()
    if not raw:
        return IMPORT_TOMBSTONES_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError('ORENA_LIMIT_IMPORT_TOMBSTONES must be an integer.') from None
    if value < IMPORT_TOMBSTONES_FLOOR:
        raise RuntimeError(f'ORENA_LIMIT_IMPORT_TOMBSTONES must be at least {IMPORT_TOMBSTONES_FLOOR}.')
    return value


_import_row_bound()  # a misconfiguration refuses at startup, not at the first import
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
            conflict_code: str, create_guard: Any = None, digest_payload: Any = None) -> dict[str, Any]:
    references = {'work': ident, 'kind': kind, 'lifecycle': lifecycle, 'source': source}
    # The digest guards an operation id against reuse with different INPUT; it is computed over what the client
    # sent (`digest_payload`), not over anything the server derived, so a replay digests the same.
    outcome = _backbone().work.commit_mutation(
        scope=scope, domain=kind, operation_id=operation_id,
        digest=semantic_digest(kind, references, payload if digest_payload is None else digest_payload), expected_version=expected_version,
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
            'tombstones': list(payload.get('tombstones') or []),
            'cleared': bool(payload.get('cleared')), 'version': int(row['version'])}


def _item_ids(payload: dict[str, Any]) -> list[str]:
    return [str(item.get('id')) for key in ('highlights', 'notes') for item in (payload.get(key) or []) if item.get('id')]


@router.get('/annotations/{content_id:path}')
def get_annotations(content_id: str) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    content_id = _key(content_id, 'content_id_invalid')
    row = None if _text_import_deleted(scope, content_id) else _read(scope, 'annotation', content_id)
    if row is None:
        raise orena_http_error(404, 'annotation_not_found', 'Nothing kept for this text.', retryable=False)
    return {'annotation': _annotation_shape(row)}


@router.put('/annotations/{content_id:path}')
def put_annotations(content_id: str, body: AnnotationSave) -> dict[str, Any]:
    scope = work_api._scope()  # noqa: SLF001
    content_id = _key(content_id, 'content_id_invalid')
    if _text_import_deleted(scope, content_id):
        raise orena_http_error(404, 'annotation_not_found', 'That text was deleted.', retryable=False)
    ids = [item.id for item in body.highlights] + [item.id for item in body.notes]
    if len(set(ids)) != len(ids):
        raise orena_http_error(422, 'annotation_duplicate_id', 'Each highlight and note has its own id.', retryable=False)
    request = ({'cleared': True} if body.cleared else {
        'highlights': [item.model_dump() for item in body.highlights],
        'notes': [item.model_dump() for item in body.notes],
    })
    ident = _work_id(scope, 'annotation', content_id)
    payload = dict(request)
    current = _backbone().work.get_work(scope, ident)
    if current is not None and int(current['version']) == body.expectedVersion:
        # The writer read exactly the version that stands, so what it dropped it removed on purpose: remember the
        # ids, and refuse a write that brings a remembered one back. (A writer on an older version gets the
        # version conflict from the commit below and re-reads; it never gets here.)
        previous = current['payload'] or {}
        remembered = [str(i) for i in previous.get('tombstones') or []]
        bringing_back = set(remembered) & set(ids)
        if bringing_back:
            raise orena_http_error(422, 'annotation_tombstoned', 'That was removed on another device.', retryable=False,
                                   context={'ids': sorted(bringing_back)})
        removed_now = [i for i in _item_ids(previous) if i not in set(ids)]
        payload['tombstones'] = (remembered + removed_now)[-MAX_TOMBSTONES:]
    elif current is not None:
        payload['tombstones'] = [str(i) for i in (current['payload'] or {}).get('tombstones') or []]
    return _commit(
        scope, kind='annotation', ident=ident, operation_id=body.operationId,
        expected_version=body.expectedVersion, payload=payload, digest_payload=request,
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
    form: str = Field(pattern=r'^(text|url|upload)$')
    title: str = Field(min_length=1, max_length=240)
    text: str = Field(default='', max_length=MAX_IMPORT_TEXT_CHARS)
    url: str = Field(default='', max_length=MAX_IMPORT_URL_CHARS)
    # A media import (a pasted link or an uploaded file) is kept as the reference the Listening room opens plus the
    # few display fields its library card needs - never the media bytes or a transcript. `upload` names the stored
    # media by `mediaId`; `url` keeps the link.
    mediaId: str = Field(default='', max_length=200)
    kind: str = Field(default='', max_length=40)
    durationMs: int | None = Field(default=None, ge=0, le=10**9)
    thumbnailUrl: str = Field(default='', max_length=600)
    provider: str = Field(default='', max_length=40)


def import_ref(form: str, reference: str) -> str:
    """A content-free reference to a media import's membership id (`url:<link>` or `upload:<media id>`): what a
    tombstone keeps so a device can tell WHICH of its imports was deleted without the link or the file being
    stored. A text import's membership id is its record id, so it needs none."""
    return hashlib.sha256(f'orena.import-ref:{form}:{reference}'.encode()).hexdigest()


def _import_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise orena_http_error(422, 'import_id_invalid', 'An import id is a UUID.', retryable=False) from None


def _import_shape(row: dict[str, Any]) -> dict[str, Any]:
    payload = row['payload'] or {}
    form = str(payload.get('form') or 'text')
    client = str(payload.get('id') or '')
    shape = {'id': f'{form}:{client}', 'form': form, 'title': str(payload.get('title') or ''),
             'text': str(payload.get('text') or ''), 'url': str(payload.get('url') or ''),
             'version': int(row['version']), 'sequence': int(row.get('updated_sequence') or 0)}
    if form in {'url', 'upload'}:
        shape.update({'mediaId': str(payload.get('mediaId') or ''), 'kind': str(payload.get('kind') or ''),
                      'durationMs': payload.get('durationMs'), 'thumbnailUrl': str(payload.get('thumbnailUrl') or ''),
                      'provider': str(payload.get('provider') or '')})
    return shape


IMPORT_PAGE = 50
DELETED_PAGE = 500


@router.get('/imports')
def list_imports(limit: int = Query(IMPORT_PAGE, ge=1, le=IMPORT_PAGE), cursor: int | None = Query(None, ge=0),
                 deletedLimit: int = Query(DELETED_PAGE, ge=1, le=DELETED_PAGE),
                 deletedCursor: int | None = Query(None, ge=0),
                 include: str = Query('both', pattern='^(both|imports|deleted)$')) -> dict[str, Any]:
    """The learner's imports and the tombstones of deleted ones, newest first, in pages. Nothing is silently left out:
    `nextCursor` / `nextDeletedCursor` name the next page of each list (null when it is the last), and a client pages
    until both are null, asking (`include`) only for the list that still has pages. A cursor is the change sequence of
    the last row of the page before."""
    scope = work_api._scope()  # noqa: SLF001
    work = _backbone().work
    live = work.list_works(scope, kind='imported', source_kind='imported', limit=limit + 1, before=cursor) if include != 'deleted' else []
    gone = (work.list_works(scope, kind='imported', source_kind='imported', limit=deletedLimit + 1, deleted=True, before=deletedCursor)
            if include != 'imports' else [])
    next_live = int(live[limit - 1]['updated_sequence']) if len(live) > limit else None
    next_gone = int(gone[deletedLimit - 1]['updated_sequence']) if len(gone) > deletedLimit else None
    live, gone = live[:limit], gone[:deletedLimit]
    # The account's change position for imports as of this read, over ALL its import rows (not just this page): a
    # device keeps it, and a record created later has a greater `sequence` - how a re-import by another device is
    # told from the record this device deleted.
    with work._engine.connect() as connection:  # noqa: SLF001
        from sqlalchemy import text as sql

        high_water = int(connection.execute(
            sql("SELECT COALESCE(max(updated_sequence), 0) FROM works WHERE incarnation_id = :inc AND language_code = :lang "
                "AND kind = 'imported'"), {'inc': scope.incarnation, 'lang': scope.language}).scalar_one())
    swept = 0
    for row in gone:
        if (row['payload'] or {}).get('mediaPending') and swept < PENDING_SWEEP_PER_READ:
            # A file removal an earlier deletion could not finish is completed on a later read (a few per read).
            swept += 1
            _finish_pending_media(scope, str(row['id']), row)
    return {'highWater': high_water, 'imports': [_import_shape(row) for row in live], 'nextCursor': next_live,
            'deleted': [{'id': f"{(row['payload'] or {}).get('form') or 'text'}:{(row['payload'] or {}).get('id') or ''}",
                         'ref': str((row['payload'] or {}).get('ref') or '')} for row in gone],
            'nextDeletedCursor': next_gone}


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

        live, total = connection.execute(
            sql("SELECT count(*) FILTER (WHERE lifecycle <> 'deleted'), count(*) FROM works "
                "WHERE incarnation_id = :inc AND language_code = :lang AND kind = 'imported'"),
            {'inc': scope.incarnation, 'lang': scope.language},
        ).one()
        if live >= MAX_IMPORTS or total >= _import_row_bound():
            raise MutationRefused('import_limit')

    if body.form == 'upload' and not body.mediaId.strip():
        raise orena_http_error(422, 'import_media_invalid', 'An uploaded file needs its stored media id.', retryable=False)
    payload = {'id': client, 'form': body.form, 'title': body.title.strip()}
    if body.form == 'text':
        payload['text'] = body.text
    else:
        payload['url'] = body.url.strip()
        if body.form == 'upload':
            payload['mediaId'] = body.mediaId.strip()
        payload['kind'] = body.kind.strip()
        if body.durationMs is not None:
            payload['durationMs'] = body.durationMs
        # The same rule the device applies: only an https thumbnail without credentials is kept.
        thumbnail = body.thumbnailUrl.strip()
        if thumbnail.startswith('https://') and '@' not in thumbnail:
            payload['thumbnailUrl'] = thumbnail
        if body.provider.strip():
            payload['provider'] = body.provider.strip()
    return _commit(
        scope, kind='imported', ident=ident, operation_id=body.operationId, expected_version=body.expectedVersion,
        payload=payload, source={'kind': 'imported', 'id': client, 'revision': ''}, conflict_code='import_conflict',
        create_guard=at_most_the_limit,
    )


def _other_live_import_names(scope: Scope, media_id: str) -> bool:
    """Whether a live import of this account (any language) still names the stored media. Two records can name the
    same file (two devices kept it); the files go with the LAST one."""
    from sqlalchemy import text as sql

    with _backbone().work._engine.connect() as connection:  # noqa: SLF001
        found = connection.execute(
            sql("SELECT count(*) FROM works WHERE incarnation_id = :inc AND kind = 'imported' AND lifecycle <> 'deleted' "
                "AND payload->>'form' = 'upload' AND payload->>'mediaId' = :media"),
            {'inc': scope.incarnation, 'media': media_id},
        ).scalar_one()
    return found > 0


def _source_candidates(source_id: str) -> list[str]:
    """The forms a source id of a kept word can take for one import: a text's `text:<id>`; a stored upload as
    `upload-<token>`, `media:upload-<token>` or `upload:upload-<token>`; a link as `url:<link>` (optionally behind the
    same prefixes)."""
    value = str(source_id or '')
    out = [value]
    for prefix in ('media:', 'upload:'):
        for item in list(out):
            if item.startswith(prefix):
                out.append(item[len(prefix):])
    return out


def _deleted_source_filter(scope: Scope):
    """A predicate over a provenance source id: True when it names an import this account has deleted (and has not
    kept again). Built from the tombstones (ids and hash references) - never from any stored excerpt."""
    from sqlalchemy import text as sql

    with _backbone().work._engine.connect() as connection:  # noqa: SLF001
        rows = connection.execute(
            sql("SELECT lifecycle, payload FROM works WHERE incarnation_id = :inc AND language_code = :lang "
                "AND kind = 'imported'"), {'inc': scope.incarnation, 'lang': scope.language}).mappings().all()
    gone_text, gone_refs, live_text, live_refs = set(), set(), set(), set()
    for row in rows:
        payload = row['payload'] or {}
        form = str(payload.get('form') or 'text')
        deleted = row['lifecycle'] == 'deleted'
        if form == 'text':
            (gone_text if deleted else live_text).add(f"text:{payload.get('id')}")
        elif deleted:
            if payload.get('ref'):
                gone_refs.add(str(payload['ref']))
        else:
            reference = str(payload.get('mediaId') or '') if form == 'upload' else str(payload.get('url') or '')
            if reference:
                live_refs.add(import_ref(form, reference))

    def is_deleted(source_id: str) -> bool:
        for item in _source_candidates(source_id):
            if item in gone_text and item not in live_text:
                return True
            if item.startswith('upload-') and (ref := import_ref('upload', item)) in gone_refs and ref not in live_refs:
                return True
            if item.startswith('url:') and (ref := import_ref('url', item[4:])) in gone_refs and ref not in live_refs:
                return True
        return False

    return is_deleted


def _text_import_deleted(scope: Scope, content_id: str) -> bool:
    """Whether a content id names a text import this account has deleted (its notes and highlights are not served)."""
    value = str(content_id or '')
    if not value.startswith('text:'):
        return False
    row = _backbone().work.get_work(scope, _work_id(scope, 'imported', value[5:]))
    return row is not None and row['lifecycle'] == 'deleted'


def _erase_derived_of_import(scope: Scope, form: str, client: str, reference: str) -> dict[str, int]:
    """What a deleted import must not leave behind as a copy of itself (D-108): the notes and highlights written on it,
    and the stored sentence of every kept word that was met in it. The words, their review history and the learner's
    Dictation / Shadowing progress are kept; a kept word's source is marked unavailable (provenance reads say so).
    Idempotent; returns counts only."""
    from sqlalchemy import bindparam, text as sql

    counts = {'annotations': 0, 'provenance': 0, 'words': 0}
    base = f'text:{client}' if form == 'text' else (reference if form == 'upload' else f'url:{reference}')
    sources = [base] + ([] if form == 'text' else [f'media:{base}', f'upload:{base}'])
    sources = sorted(set(sources))
    if form == 'text':
        row = _backbone().work.get_work(scope, _work_id(scope, 'annotation', f'text:{client}'))
        if row is not None and row['lifecycle'] != 'deleted':
            _commit(
                scope, kind='annotation', ident=str(row['id']), operation_id=f'erase-{uuid.uuid4()}',
                expected_version=int(row['version']), payload={}, source={'kind': 'content', 'id': f'text:{client}', 'revision': ''},
                lifecycle='deleted', conflict_code='annotation_conflict',
            )
            counts['annotations'] = 1
    if not sources:
        return counts
    with _backbone().work._engine.begin() as connection:  # noqa: SLF001
        found = connection.execute(
            sql("SELECT id, saved_word_id, focus FROM language_provenance WHERE incarnation_id = :inc AND language_code = :lang "
                "AND source_id IN :sources").bindparams(bindparam('sources', expanding=True)),
            {'inc': scope.incarnation, 'lang': scope.language, 'sources': sources},
        ).mappings().all()
        for row in found:
            focus = str(row['focus'] or '')
            connection.execute(
                sql("UPDATE language_provenance SET focus = '', availability = 'unavailable' WHERE id = :id"), {'id': row['id']})
            counts['provenance'] += 1
            fragment = connection.execute(
                sql('SELECT source_fragment FROM saved_words WHERE id = :id AND user_id = :user'),
                {'id': row['saved_word_id'], 'user': scope.account}).scalar()
            fragment = str(fragment or '')
            if fragment and focus and (fragment.casefold() in focus.casefold() or focus.casefold() in fragment.casefold()):
                connection.execute(sql("UPDATE saved_words SET source_fragment = '' WHERE id = :id AND user_id = :user"),
                                   {'id': row['saved_word_id'], 'user': scope.account})
                counts['words'] += 1
    return counts


def media_still_named(media_id: str) -> bool:
    """Whether a LIVE upload import of the current account still names this stored media (False when the account
    records are not kept at all: nothing can name it then). Used by the media delete route, so a file one device
    deletes is not taken from another device's import of the same file."""
    try:
        scope = work_api._scope()  # noqa: SLF001
    except Exception:  # noqa: BLE001 - records disabled or unavailable: no import names it
        return False
    return _other_live_import_names(scope, media_id)


def _finish_pending_media(scope: Scope, ident: str, row: dict[str, Any]) -> bool | None:
    """Complete the file removal an upload import's deletion owes, and only then clear its marker.

    The tombstone keeps the opaque stored-media id as `mediaPending` until the files are confirmed gone, so a replay,
    a repeated delete or a later list read can finish a removal that failed or was interrupted (files first, index
    entry last - nothing is left orphaned). The files stay while another live import of the account names them.
    Returns True/False for "removed"/"not removed", None when nothing was owed."""
    held = row['payload'] or {}
    media_id = str(held.get('mediaPending') or '')
    if not media_id:
        return None
    done = False
    removed = False
    if _other_live_import_names(scope, media_id):
        done = True  # the last live import will remove it; nothing is owed by this one
    else:
        try:
            from writing_coach import media_library_api

            removed = media_library_api.delete_owned_media(media_id, user_key=work_api._user_key(), language=scope.language)  # noqa: SLF001
            done = True  # removed, or never ours / already gone: nothing further is owed
        except Exception as exc:  # noqa: BLE001 - keep the marker; a retry completes it
            _logger.warning('uploaded media could not be removed after an import was deleted: %s', type(exc).__name__)
    if done:
        cleared = {key: value for key, value in held.items() if key != 'mediaPending'}
        try:
            _commit(
                scope, kind='imported', ident=ident, operation_id=f'sweep-{uuid.uuid4()}', expected_version=int(row['version']),
                payload=cleared, source={'kind': 'imported', 'id': str(held.get('id') or ''), 'revision': ''},
                lifecycle='deleted', conflict_code='import_conflict',
            )
        except Exception:  # noqa: BLE001 - a moved version means someone else already finished
            pass
    return removed if done else False


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
    if row['lifecycle'] == 'deleted':
        # Already deleted (a retry, or a second device): nothing to commit; finish any file removal still owed.
        return {'status': 'replay', 'version': int(row['version']), 'mediaDeleted': _finish_pending_media(scope, ident, row)}
    form_of = str((row['payload'] or {}).get('form') or 'text')
    reference = str((row['payload'] or {}).get('mediaId') or '') if form_of == 'upload' else str((row['payload'] or {}).get('url') or '')
    # A tombstone WITHOUT the content: deleting is erasing. Only what says which import this was stays (its id and
    # form, a hash reference, and for an upload the opaque stored-media id until its files are confirmed gone); the
    # title, the text and the link are dropped from the stored row, not merely hidden from the reads.
    held = row['payload'] or {}
    form = str(held.get('form') or 'text')
    media_id = str(held.get('mediaId') or '') if form == 'upload' else ''
    tombstone = {'id': client, 'form': form}
    if form == 'upload' and media_id:
        tombstone['ref'] = import_ref('upload', media_id)
        tombstone['mediaPending'] = media_id
    elif form == 'url' and held.get('url'):
        tombstone['ref'] = import_ref('url', str(held['url']))
    outcome = _commit(
        scope, kind='imported', ident=ident, operation_id=operationId, expected_version=expectedVersion,
        payload=tombstone, source={'kind': 'imported', 'id': client, 'revision': ''},
        lifecycle='deleted', conflict_code='import_conflict',
    )
    try:
        _erase_derived_of_import(scope, form_of, client, reference)
    except Exception as exc:  # noqa: BLE001 - the import is gone; reads still mask a deleted source
        _logger.warning('derived records of a deleted import could not be erased: %s', type(exc).__name__)
    media_deleted = None
    if media_id:
        fresh = _backbone().work.get_work(scope, ident)
        media_deleted = _finish_pending_media(scope, ident, fresh) if fresh else False
        if media_deleted and _other_live_import_names(scope, media_id):
            media_deleted = False  # kept: another live import still uses the file
    return {**outcome, 'mediaDeleted': media_deleted}


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
    is_deleted = _deleted_source_filter(scope)
    # A source that was deleted is reported unavailable and WITHOUT the stored sentence: an excerpt is never used to
    # bring deleted content back (D-108.2).
    return {'occurrences': [
        {'id': str(row['id']), 'reason': row['reason'], 'focus': '' if gone else row['focus'],
         'source': {'kind': row['source_kind'], 'id': row['source_id'], 'revision': row['source_revision']},
         'availability': 'unavailable' if gone else row['availability']}
        for row in rows for gone in [bool(row['source_id']) and is_deleted(row['source_id'])]
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
