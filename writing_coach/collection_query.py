"""Collection retrieval over the owners that already exist (I4, step 1).

Specification: docs/product/ORENA_COLLECTION_ARCHITECTURE.md §§2-3, §5 -
"Opus first implements typed query adapters over existing stores". This module
is a query/projection, never an owner: it reads each domain through the read it
already exposes and holds no copy, writes nothing, and moves no authority. No
schema, no membership table and no navigation change follow from it; the
deferred `#/collection` presentation is untouched.

What it answers, and the rules each answer keeps:

- **One typed entry per thing, namespaced by domain.** Reading session 1 and
  essay series 1 are different objects, so a ref is `{domain, id}`, never a
  bare id.
- **Every action is a real destination or none.** An entry opens through the
  current routing contract (`static/orena/product/intent.js`) or carries no
  action; nothing is guessed from a title. An essay series reopens in the
  Writing room; a free Speaking take has no route that reopens it yet, so it
  says so.
- **An owner that fails is named, not hidden.** A result missing an owner is
  `partial` with that owner in `unavailableOwners`, never an empty collection.
  An owner read that reached its bound may have more, so it makes the count
  unknown rather than inferring a total.
- **Scope before anything else.** Entries of another learning language are
  dropped before search, counts or snippets.
- **A cursor belongs to its query.** It is signed and binds the account, the
  resolved incarnation (or its absence), the language, the filters, the sort
  and a snapshot of the whole ordered result. Reused with another query, from
  another scope, or after the result changed, it is refused - the last as
  `refresh_required`, because paging on over changed data would skip or repeat
  entries without saying so.

Search is declared, not implied: title and snippet, Unicode-normalised and
case-folded, substring match; a query containing CJK characters also matches
across whitespace, since Chinese needs no spaces between words. There is no
semantic search and no romanisation of Chinese for identity.

Identity note, the same one `writing_coach/product/commerce.py` records: no
production caller resolves an account incarnation from a request yet, so a
cursor issued before that wiring binds `incarnation=None` and cannot by itself
tell a deleted-and-re-registered account from the original. That row of the
acceptance matrix stays pending until incarnation resolution is wired (I2).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any
from urllib.parse import urlencode

DOMAINS = ('language', 'reading', 'media', 'writing', 'speaking', 'grammar')
KIND_OF = {
    'language': 'language',
    'reading': 'text',
    'media': 'media',
    'writing': 'work',
    'speaking': 'work',
    'grammar': 'pattern',
}
MAX_LIMIT = 50
DEFAULT_LIMIT = 20
MAX_QUERY = 120
SNIPPET = 160
SEARCHED_FIELDS = ('title', 'snippet')
_log = logging.getLogger(__name__)


class CollectionQueryError(ValueError):
    """A request the query refuses; `reason` is a stable key a surface can say."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class QueryScope:
    """Server-derived facts the query runs in. None of them is inferred here."""

    account: str
    language: str
    incarnation: str | None = None

    def __post_init__(self) -> None:
        if not str(self.account or '').strip():
            raise CollectionQueryError('account_required')
        if not str(self.language or '').strip():
            raise CollectionQueryError('language_required')


@dataclass(frozen=True)
class CollectionEntry:
    domain: str
    id: str
    title: str
    learning_language: str
    relationship: str
    updated_at: str = ''
    snippet: str = ''
    availability: str = 'available'
    action: Mapping[str, str] | None = None
    durability: str = 'account'
    detail: Mapping[str, Any] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return KIND_OF[self.domain]

    def as_dict(self) -> dict[str, Any]:
        return {
            'ref': {'domain': self.domain, 'id': self.id},
            'kind': self.kind,
            'title': self.title,
            'snippet': self.snippet,
            'learningLanguage': self.learning_language,
            'relationship': self.relationship,
            'availability': self.availability,
            'durability': self.durability,
            'updatedAt': self.updated_at,
            'action': dict(self.action) if self.action else None,
            'detail': dict(self.detail),
        }


@dataclass(frozen=True)
class Owner:
    """One domain's existing read and how its rows become entries.

    `read` is the owner's own bounded read; `bound` is that bound when the read
    has one, so a full read can be recognised as possibly incomplete.

    `searches` says the owner can answer a search itself. It matters where an
    owner holds more than its bound: the learner's saved language is thousands
    of words and this query reads two hundred, so searching after the read
    would search two hundred words and report "nothing found" for the rest.
    Such an owner is handed the query and searches all of what it holds; the
    bound then limits the matches, which is a page, not a blind spot. The
    result is still filtered here afterwards, so an owner that searches more
    loosely than this query declares cannot widen it.
    """

    domain: str
    read: Callable[..., Sequence[Mapping[str, Any]]]
    to_entries: Callable[[Sequence[Mapping[str, Any]], str], list[CollectionEntry]]
    bound: int | None = None
    searches: bool = False


# --- Routes: the same strings `intent.js` link() builds -----------------------


def route(page: str, *, id: str = '', intent: str | None = None) -> str:
    params = {}
    if id:
        params['id'] = id
    if intent:
        params['intent'] = intent
    path = '' if page == 'discover' else page
    return f"#/{path}{'?' + urlencode(params) if params else ''}"


def _action(kind: str, destination: str) -> dict[str, str]:
    return {'kind': kind, 'route': destination}


def _language_of(row: Mapping[str, Any], scope_language: str) -> str:
    """The language an owner stored the row in, when it says; the owners read
    through the request's language, so otherwise it is that one."""
    return str(row.get('language_code') or row.get('language') or scope_language).strip().casefold()


def _clip(text: Any, size: int = SNIPPET) -> str:
    value = ' '.join(str(text or '').split())
    return value if len(value) <= size else value[: size - 1].rstrip() + '…'


# --- Owner mappings: existing rows to typed entries ----------------------------


def language_entries(rows: Sequence[Mapping[str, Any]], language: str) -> list[CollectionEntry]:
    """Saved words, from the library owner. Review scheduling stays there."""
    entries = []
    for row in rows:
        word = str(row.get('word') or '').strip()
        if not word:
            continue
        entries.append(CollectionEntry(
            domain='language',
            id=unicodedata.normalize('NFKC', word).casefold(),
            title=word,
            snippet=_clip(row.get('definition') or row.get('source_fragment')),
            learning_language=_language_of(row, language),
            relationship='saved',
            updated_at=str(row.get('added_at') or ''),
            action=_action('review_language', route('language')),
            # What the owner already recorded about reviewing this word. The
            # library's detail panel shows it; nothing here computes a measure
            # or invents one for a kind that has no schedule.
            detail={
                'sourceKind': str(row.get('source_kind') or ''),
                'successfulRecalls': int(row.get('successful_recalls') or 0),
                'lastReviewedAt': str(row.get('last_reviewed_at') or ''),
                'nextReviewAt': str(row.get('next_review_at') or ''),
                'sourceFragment': _clip(row.get('source_fragment'), 280),
            },
        ))
    return entries


def grammar_entries(rows: Sequence[Mapping[str, Any]], language: str) -> list[CollectionEntry]:
    """Patterns the learner marked complete, from the grammar owner.

    The owner records completion, not a time and not a measure: marking a
    pattern complete is the learner saying they have worked through it, which
    `ORENA_STATUS` and the curriculum policy are explicit is not mastery. So an
    entry carries what is recorded - the pattern and its level - and nothing
    that would read as a score.
    """
    entries = []
    for row in rows:
        lesson = str(row.get('id') or row.get('lesson_id') or '').strip()
        if not lesson:
            continue
        entries.append(CollectionEntry(
            domain='grammar',
            id=lesson,
            title=str(row.get('title') or ''),
            learning_language=_language_of(row, language),
            relationship='completed',
            updated_at=str(row.get('completed_at') or ''),
            action=_action('open_source', route('practice', id=lesson, intent='grammar')),
            detail={'level': str(row.get('level') or '')},
        ))
    return entries


def reading_entries(rows: Sequence[Mapping[str, Any]], language: str) -> list[CollectionEntry]:
    """Passages the learner asked for, from the reading owner."""
    entries = []
    for row in rows:
        if row.get('id') in (None, ''):
            continue
        ident = str(int(row['id']))
        entries.append(CollectionEntry(
            domain='reading',
            id=ident,
            title=str(row.get('title') or ''),
            snippet=_clip(row.get('topic')),
            learning_language=_language_of(row, language),
            relationship='started',
            updated_at=str(row.get('created_at') or ''),
            action=_action('open_source', route('encounter', id=f'reading:{ident}', intent='reading')),
            detail={'questionCount': int(row.get('question_count') or 0)},
        ))
    return entries


def writing_entries(rows: Sequence[Mapping[str, Any]], language: str) -> list[CollectionEntry]:
    """The latest revision of each essay series, from the Writing owner.

    Each reopens its series in the Writing room (`essay:<series>`): the latest
    version, its history and its review, continued rather than restarted.
    """
    entries = []
    for row in rows:
        series = row.get('series_id') or row.get('id')
        if series in (None, ''):
            continue
        text = str(row.get('text') or '')
        prompt = str(row.get('prompt') or '').strip()
        entries.append(CollectionEntry(
            domain='writing',
            id=str(int(series)),
            title=_clip(prompt or text, 80),
            snippet=_clip(text),
            learning_language=_language_of(row, language),
            relationship='submitted',
            updated_at=str(row.get('created_at') or ''),
            action=_action('resume_work', route('expression', id=f'essay:{int(series)}')),
            detail={'revisions': int(row.get('revision_no') or 1)},
        ))
    return entries


@dataclass(frozen=True)
class LessonRef:
    lesson_id: str
    title: str


LessonResolver = Callable[[str, str], 'LessonRef | None']


def media_entries_with(resolve: LessonResolver) -> Callable[[Sequence[Mapping[str, Any]], str], list[CollectionEntry]]:
    """Listening progress, grouped into the lesson it belongs to.

    Progress is stored against the source media and a segment; the lesson a
    route opens is found through the catalog, by source and by whether the
    segment falls inside the lesson's excerpt, because one source can back
    several lessons. A row no lesson claims is shown as unavailable, with no
    action - it is the learner's own progress, but there is nowhere true to
    send them.
    """

    def to_entries(rows: Sequence[Mapping[str, Any]], language: str) -> list[CollectionEntry]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            asset = str(row.get('asset_id') or '')
            segment = str(row.get('segment_id') or '')
            if not asset:
                continue
            lesson = resolve(asset, segment)
            key = lesson.lesson_id if lesson else f'asset:{asset}'
            group = grouped.setdefault(key, {'lesson': lesson, 'asset': asset, 'segments': set(), 'updated': '', 'language': _language_of(row, language)})
            group['segments'].add(segment)
            group['updated'] = max(group['updated'], str(row.get('updated_at') or ''))
        entries = []
        for key, group in grouped.items():
            lesson = group['lesson']
            entries.append(CollectionEntry(
                domain='media',
                id=key,
                title=lesson.title if lesson else '',
                learning_language=group['language'],
                relationship='practised',
                updated_at=group['updated'],
                availability='available' if lesson else 'unavailable',
                action=_action('open_source', route('encounter', id=f'media:{lesson.lesson_id}', intent='dictation')) if lesson else None,
                detail={'segments': len(group['segments'])},
            ))
        return entries

    return to_entries


def speaking_entries_with(resolve: LessonResolver) -> Callable[[Sequence[Mapping[str, Any]], str], list[CollectionEntry]]:
    """Speaking takes. A take answering a lesson line reopens that line's
    lesson; a free take has no route that reopens it yet."""

    def to_entries(rows: Sequence[Mapping[str, Any]], language: str) -> list[CollectionEntry]:
        entries = []
        for row in rows:
            take = str(row.get('take_id') or '')
            if not take:
                continue
            asset = str(row.get('asset_id') or '')
            lesson = resolve(asset, str(row.get('segment_id') or '')) if asset else None
            said = str(row.get('transcript_text') or '')
            entries.append(CollectionEntry(
                domain='speaking',
                id=take,
                title=_clip(row.get('reference_text') or said, 80),
                snippet=_clip(said),
                learning_language=_language_of(row, language),
                relationship='spoken',
                updated_at=str(row.get('created_at') or ''),
                action=_action('open_source', route('encounter', id=f'media:{lesson.lesson_id}', intent='speaking')) if lesson else None,
                detail={} if lesson else {'actionUnavailable': 'no_route'},
            ))
        return entries

    return to_entries


# --- Search -----------------------------------------------------------------


def _has_cjk(text: str) -> bool:
    # CJK ideographs, compatibility ideographs, kana.
    return any(
        '㐀' <= ch <= '鿿' or '豈' <= ch <= '﫿' or '぀' <= ch <= 'ヿ'
        for ch in text
    )


def normalise(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', str(text or '')).casefold().split())


def matches(entry: CollectionEntry, query: str) -> bool:
    needle = normalise(query)
    if not needle:
        return True
    haystack = ' '.join(normalise(getattr(entry, name)) for name in SEARCHED_FIELDS)
    if needle in haystack:
        return True
    if _has_cjk(needle):
        return needle.replace(' ', '') in haystack.replace(' ', '')
    return False


# --- Cursor -----------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]


def _sign(secret: bytes, payload: bytes) -> str:
    return _b64(hmac.new(secret, payload, hashlib.sha256).digest())


def encode_cursor(secret: bytes, body: Mapping[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    return f'{_b64(payload)}.{_sign(secret, payload)}'


def decode_cursor(secret: bytes, token: str) -> dict[str, Any]:
    try:
        payload_part, signature = str(token).split('.', 1)
        payload = _unb64(payload_part)
    except (ValueError, TypeError):
        raise CollectionQueryError('cursor_invalid') from None
    if not hmac.compare_digest(_sign(secret, payload), signature):
        raise CollectionQueryError('cursor_invalid')
    try:
        body = json.loads(payload)
    except ValueError:
        raise CollectionQueryError('cursor_invalid') from None
    if not isinstance(body, dict):
        raise CollectionQueryError('cursor_invalid')
    return body


# --- The query --------------------------------------------------------------


def _instant(stamp: str) -> float | None:
    """Owners write their times in different ISO shapes; compare instants."""
    text = str(stamp or '').strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.timestamp()


def _order_key(entry: CollectionEntry) -> tuple:
    # Newest first; an entry without a readable time goes last; equal times
    # break on domain then id, so the order is total and a page boundary is
    # stable.
    moment = _instant(entry.updated_at)
    return (moment is None, -(moment or 0.0), entry.domain, entry.id)


def query_collection(
    scope: QueryScope,
    owners: Iterable[Owner],
    *,
    secret: bytes,
    query: str = '',
    kinds: Iterable[str] = (),
    domains: Iterable[str] = (),
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """`queryCollection(scope, {query, kinds, cursor, limit})`.

    Returns `{entries, nextCursor, completeness, unavailableOwners,
    truncatedOwners, snapshotVersion, total, totalKind, searchedFields}`.
    """
    query = str(query or '').strip()
    if len(query) > MAX_QUERY:
        raise CollectionQueryError('query_too_long')
    wanted = tuple(sorted({str(kind).strip() for kind in kinds if str(kind).strip()}))
    unknown = [kind for kind in wanted if kind not in set(KIND_OF.values())]
    if unknown:
        raise CollectionQueryError('kind_unknown')
    # A kind can hold two owners - writing and speaking are both work - and a
    # surface that names them separately asks by owner instead.
    owned = tuple(sorted({str(domain).strip() for domain in domains if str(domain).strip()}))
    if [domain for domain in owned if domain not in DOMAINS]:
        raise CollectionQueryError('domain_unknown')
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise CollectionQueryError('limit_invalid') from None
    if not 1 <= limit <= MAX_LIMIT:
        raise CollectionQueryError('limit_invalid')

    unavailable: list[str] = []
    truncated: list[str] = []
    collected: list[CollectionEntry] = []
    for owner in owners:
        if owner.domain not in DOMAINS:
            raise CollectionQueryError('owner_unknown')
        if wanted and KIND_OF[owner.domain] not in wanted:
            continue
        if owned and owner.domain not in owned:
            continue
        try:
            rows = list(owner.read(query) if owner.searches else owner.read())
            entries = owner.to_entries(rows, scope.language.strip().casefold())
        except Exception as error:
            # Named in the result, never swallowed into an empty one - and in
            # the log, by domain and error type only: no learner data.
            _log.warning('collection owner %s unavailable: %s', owner.domain, type(error).__name__)
            unavailable.append(owner.domain)
            continue
        if owner.bound is not None and len(rows) >= owner.bound:
            truncated.append(owner.domain)
        collected.extend(entries)

    # Scope first: another language's entry never reaches search, counts or
    # snippets, whatever an owner returned.
    language = scope.language.strip().casefold()
    scoped = [entry for entry in collected if entry.learning_language == language]
    found = sorted((entry for entry in scoped if matches(entry, query)), key=_order_key)

    filters = {'query': normalise(query), 'kinds': list(wanted), 'domains': list(owned),
               'sort': 'updated_desc', 'limit': limit}
    binding = {'account': scope.account, 'incarnation': scope.incarnation, 'language': scope.language}
    snapshot = _digest({
        'binding': binding,
        'refs': [[entry.domain, entry.id, entry.updated_at, entry.availability] for entry in found],
        'unavailable': unavailable,
    })

    offset = 0
    if cursor:
        body = decode_cursor(secret, cursor)
        if body.get('binding') != binding:
            raise CollectionQueryError('cursor_scope_mismatch')
        if body.get('filters') != _digest(filters):
            raise CollectionQueryError('cursor_query_mismatch')
        if body.get('snapshot') != snapshot:
            raise CollectionQueryError('refresh_required')
        offset = body.get('offset')
        if not isinstance(offset, int) or offset < 0 or offset > len(found):
            raise CollectionQueryError('cursor_invalid')

    page = found[offset: offset + limit]
    next_offset = offset + len(page)
    next_cursor = (
        encode_cursor(secret, {'binding': binding, 'filters': _digest(filters), 'snapshot': snapshot, 'offset': next_offset})
        if next_offset < len(found)
        else None
    )
    complete = not unavailable and not truncated
    # How many of each kind the same result holds, so a surface can label its
    # kinds without asking once per kind. It counts what was read: a request
    # that named kinds counted only those, and an owner that was unavailable or
    # filled its bound makes these counts as partial as the total is.
    kind_totals: dict[str, int] = {}
    domain_totals: dict[str, int] = {}
    for entry in found:
        kind_totals[entry.kind] = kind_totals.get(entry.kind, 0) + 1
        domain_totals[entry.domain] = domain_totals.get(entry.domain, 0) + 1
    return {
        'entries': [entry.as_dict() for entry in page],
        'kindTotals': kind_totals,
        'domainTotals': domain_totals,
        'nextCursor': next_cursor,
        'completeness': 'complete' if complete else 'partial',
        'unavailableOwners': unavailable,
        'truncatedOwners': truncated,
        'snapshotVersion': snapshot,
        'total': len(found) if complete else None,
        'totalKind': 'exact' if complete else 'unknown',
        'searchedFields': list(SEARCHED_FIELDS),
        'learningLanguage': scope.language,
    }
