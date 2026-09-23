"""I4 step 1: typed collection query over existing owners.

docs/product/ORENA_COLLECTION_ARCHITECTURE.md §§2-3 and §5 acceptance - mixed
source/work rows, namespace ID collision, owner outage, snapshot pagination with
concurrent additions, query/cursor mismatch, EN/ZH retrieval, and every result
reaching a real destination. Hermetic: owners are fakes shaped like the rows
the real owner reads return.
"""
from __future__ import annotations

import pytest

from writing_coach.collection_query import (
    CollectionQueryError,
    LessonRef,
    Owner,
    QueryScope,
    grammar_entries,
    language_entries,
    media_entries_with,
    query_collection,
    reading_entries,
    route,
    speaking_entries_with,
    writing_entries,
)

SECRET = b'test-secret'
EN = QueryScope(account='learner-a', language='en')


def lessons(asset: str, segment: str) -> LessonRef | None:
    # One source backs two lessons; the segment decides which.
    if asset == 'shared-source':
        return LessonRef('lesson-one', 'Lesson one') if segment.endswith(':000') else LessonRef('lesson-two', 'Lesson two')
    if asset == 'known-source':
        return LessonRef('known-lesson', 'Known lesson')
    return None


def owners(*, library=None, reading=None, essays=None, listening=None, speaking=None, grammar=None, fail=(), bounds=None):
    bounds = bounds or {}

    def reader(domain, rows):
        def read():
            if domain in fail:
                raise RuntimeError(f'{domain} store unavailable')
            return rows or []
        return read

    return [
        Owner('language', reader('language', library), language_entries, bounds.get('language')),
        Owner('reading', reader('reading', reading), reading_entries, bounds.get('reading')),
        Owner('media', reader('media', listening), media_entries_with(lessons), bounds.get('media')),
        Owner('writing', reader('writing', essays), writing_entries, bounds.get('writing')),
        Owner('speaking', reader('speaking', speaking), speaking_entries_with(lessons), bounds.get('speaking')),
        Owner('grammar', reader('grammar', grammar), grammar_entries, bounds.get('grammar')),
    ]


LIBRARY = [
    {'word': 'Harbour', 'definition': 'a sheltered place for boats', 'added_at': '2026-09-10T08:00:00+00:00', 'source_kind': 'reading'},
    {'word': 'lantern', 'definition': 'a lamp with a case', 'added_at': '2026-09-11T08:00:00Z'},
]
READING = [{'id': 1, 'title': 'The last train home', 'topic': 'travel', 'created_at': '2026-09-12T09:00:00+00:00', 'question_count': 4}]
ESSAYS = [{'id': 7, 'series_id': 1, 'prompt': '', 'text': 'Yesterday I went to the harbour and watched the boats.', 'created_at': '2026-09-09T10:00:00+00:00', 'revision_no': 2}]
LISTENING = [
    {'asset_id': 'shared-source', 'segment_id': 'shared-source:000', 'updated_at': '2026-09-12T10:00:00+00:00'},
    {'asset_id': 'shared-source', 'segment_id': 'shared-source:004', 'updated_at': '2026-09-12T11:00:00+00:00'},
    {'asset_id': 'shared-source', 'segment_id': 'shared-source:005', 'updated_at': '2026-09-12T11:30:00+00:00'},
    {'asset_id': 'gone-source', 'segment_id': 'gone-source:001', 'updated_at': '2026-09-01T10:00:00+00:00'},
]
GRAMMAR = [
    {'id': 'a2-past-simple', 'title': 'Past simple', 'level': 'A2', 'completed_at': '2026-09-07T09:00:00+00:00'},
]
SPEAKING = [
    {'take_id': 'take-lesson', 'asset_id': 'known-source', 'segment_id': 'known-source:001', 'reference_text': 'Anna, do you have a pen?', 'transcript_text': 'Anna do you have a pen', 'created_at': '2026-09-12T12:00:00+00:00'},
    {'take_id': 'take-free', 'asset_id': '', 'segment_id': '', 'reference_text': '', 'transcript_text': 'I would like a coffee', 'created_at': '2026-09-08T12:00:00+00:00'},
]


def everything(**extra):
    return owners(library=LIBRARY, reading=READING, essays=ESSAYS, listening=LISTENING, speaking=SPEAKING,
                  grammar=GRAMMAR, **extra)


def refs(result):
    return [(entry['ref']['domain'], entry['ref']['id']) for entry in result['entries']]


def test_mixed_owners_come_back_as_one_typed_newest_first_result():
    result = query_collection(EN, everything(), secret=SECRET)
    assert result['completeness'] == 'complete'
    assert result['totalKind'] == 'exact' and result['total'] == len(result['entries']) == 10
    stamps = [entry['updatedAt'] for entry in result['entries']]
    assert refs(result)[0] == ('speaking', 'take-lesson')
    assert stamps.index('2026-09-11T08:00:00Z') < stamps.index('2026-09-10T08:00:00+00:00'), 'mixed ISO shapes compare as instants'
    kinds = {entry['ref']['domain']: entry['kind'] for entry in result['entries']}
    assert kinds == {'language': 'language', 'reading': 'text', 'media': 'media', 'writing': 'work',
                     'speaking': 'work', 'grammar': 'pattern'}


def test_a_completed_pattern_reaches_its_lesson_and_claims_no_mastery():
    """Grammar records that the learner worked through a pattern. The entry
    carries the pattern, its level and the way back into it - never a score,
    because the curriculum policy is explicit that completion is not mastery."""
    result = query_collection(EN, everything(), secret=SECRET, kinds=['pattern'])
    entry = next(item for item in result['entries'] if item['ref']['domain'] == 'grammar')
    assert entry['ref']['id'] == 'a2-past-simple'
    assert entry['title'] == 'Past simple'
    assert entry['relationship'] == 'completed'
    assert entry['action'] == {'kind': 'open_source', 'route': route('practice', id='a2-past-simple', intent='grammar')}
    assert entry['detail'] == {'level': 'A2'}
    assert 'score' not in entry['detail'] and entry['snippet'] == ''


def test_the_same_numeric_id_in_two_domains_stays_two_objects():
    result = query_collection(EN, everything(), secret=SECRET)
    ids = refs(result)
    assert ('reading', '1') in ids and ('writing', '1') in ids


def test_every_action_is_a_real_route_or_none():
    # Keyed by domain and id: keyed by id alone, essay series 1 would overwrite
    # reading session 1 - the collision domain refs exist to prevent.
    result = {(entry['ref']['domain'], entry['ref']['id']): entry for entry in query_collection(EN, everything(), secret=SECRET)['entries']}
    # The same strings intent.js link() builds.
    assert result[('reading', '1')]['action'] == {'kind': 'open_source', 'route': '#/encounter?id=reading%3A1&intent=reading'}
    assert result[('language', 'harbour')]['action']['route'] == '#/language'
    assert result[('media', 'lesson-one')]['action']['route'] == '#/encounter?id=media%3Alesson-one&intent=dictation'
    assert result[('speaking', 'take-lesson')]['action']['route'] == '#/encounter?id=media%3Aknown-lesson&intent=speaking'
    # An essay series reopens in the Writing room, continued.
    assert result[('writing', '1')]['action'] == {'kind': 'resume_work', 'route': '#/expression?id=essay%3A1'}
    # No route reopens a free take yet: no action, and it says why.
    assert result[('speaking', 'take-free')]['action'] is None
    assert result[('speaking', 'take-free')]['detail']['actionUnavailable'] == 'no_route'
    assert route('discover') == '#/'


def test_one_source_behind_two_lessons_groups_by_the_lesson_the_segment_belongs_to():
    media = {entry['ref']['id']: entry for entry in query_collection(EN, everything(), secret=SECRET, kinds=['media'])['entries']}
    assert media['lesson-one']['detail']['segments'] == 1
    assert media['lesson-two']['detail']['segments'] == 2
    assert media['lesson-two']['updatedAt'] == '2026-09-12T11:30:00+00:00'


def test_progress_no_lesson_claims_is_shown_unavailable_not_guessed():
    media = {entry['ref']['id']: entry for entry in query_collection(EN, everything(), secret=SECRET, kinds=['media'])['entries']}
    orphan = media['asset:gone-source']
    assert orphan['availability'] == 'unavailable'
    assert orphan['action'] is None and orphan['title'] == ''


def test_an_owner_outage_is_a_partial_result_not_an_empty_collection():
    result = query_collection(EN, everything(fail={'reading', 'speaking'}), secret=SECRET)
    assert result['completeness'] == 'partial'
    assert result['unavailableOwners'] == ['reading', 'speaking']
    assert result['total'] is None and result['totalKind'] == 'unknown'
    assert ('language', 'harbour') in refs(result), 'the owners that answered are still shown'


def test_an_owner_read_that_fills_its_bound_makes_the_count_unknown():
    result = query_collection(EN, everything(bounds={'reading': 1}), secret=SECRET)
    assert result['truncatedOwners'] == ['reading']
    assert result['completeness'] == 'partial' and result['total'] is None


def test_entries_of_another_learning_language_never_reach_the_result():
    foreign = LIBRARY + [{'word': '港口', 'definition': 'harbour', 'added_at': '2026-09-12T08:00:00Z', 'language_code': 'zh'}]
    result = query_collection(EN, owners(library=foreign), secret=SECRET, query='harbour')
    assert refs(result) == [('language', 'harbour')]
    assert result['total'] == 1


def test_search_is_case_and_width_insensitive_on_the_declared_fields():
    result = query_collection(EN, everything(), secret=SECRET, query='HARBOUR')
    assert refs(result) == [('language', 'harbour'), ('writing', '1')]
    assert result['searchedFields'] == ['title', 'snippet']


def test_chinese_matches_by_characters_without_spaces_or_romanisation():
    zh = QueryScope(account='learner-a', language='zh')
    library = [
        {'word': '火车站', 'definition': '坐 火车 的 地方', 'added_at': '2026-09-12T08:00:00Z'},
        {'word': '书包', 'definition': '装书的包', 'added_at': '2026-09-11T08:00:00Z'},
    ]
    assert refs(query_collection(zh, owners(library=library), secret=SECRET, query='火车'))[0] == ('language', '火车站')
    assert refs(query_collection(zh, owners(library=library), secret=SECRET, query='坐火车')) == [('language', '火车站')]
    assert refs(query_collection(zh, owners(library=library), secret=SECRET, query='huoche')) == []


def test_paging_covers_every_entry_exactly_once():
    seen, cursor = [], None
    while True:
        page = query_collection(EN, everything(), secret=SECRET, limit=4, cursor=cursor)
        seen += refs(page)
        cursor = page['nextCursor']
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 10


def test_a_concurrent_addition_asks_for_a_refresh_instead_of_skipping_or_repeating():
    first = query_collection(EN, everything(), secret=SECRET, limit=4)
    grown = LIBRARY + [{'word': 'anchor', 'definition': 'holds a boat', 'added_at': '2026-09-13T08:00:00Z'}]
    with pytest.raises(CollectionQueryError) as refused:
        query_collection(EN, owners(library=grown, reading=READING, essays=ESSAYS, listening=LISTENING, speaking=SPEAKING),
                         secret=SECRET, limit=4, cursor=first['nextCursor'])
    assert refused.value.reason == 'refresh_required'


def test_a_cursor_reused_with_another_query_is_refused():
    first = query_collection(EN, everything(), secret=SECRET, limit=4)
    with pytest.raises(CollectionQueryError) as refused:
        query_collection(EN, everything(), secret=SECRET, limit=4, cursor=first['nextCursor'], query='boat')
    assert refused.value.reason == 'cursor_query_mismatch'


@pytest.mark.parametrize('other', [
    QueryScope(account='learner-b', language='en'),
    QueryScope(account='learner-a', language='zh'),
    QueryScope(account='learner-a', language='en', incarnation='inc-2'),
])
def test_a_cursor_from_another_scope_is_refused(other):
    first = query_collection(EN, everything(), secret=SECRET, limit=4)
    with pytest.raises(CollectionQueryError) as refused:
        query_collection(other, everything(), secret=SECRET, limit=4, cursor=first['nextCursor'])
    assert refused.value.reason == 'cursor_scope_mismatch'


def test_a_tampered_or_foreign_cursor_is_refused():
    first = query_collection(EN, everything(), secret=SECRET, limit=4)
    token = first['nextCursor']
    tampered = token[:-2] + ('AA' if not token.endswith('AA') else 'BB')
    for bad in (tampered, 'not-a-cursor', token):
        with pytest.raises(CollectionQueryError) as refused:
            query_collection(EN, everything(), secret=b'another-secret' if bad == token else SECRET, limit=4, cursor=bad)
        assert refused.value.reason == 'cursor_invalid'


@pytest.mark.parametrize('arguments, reason', [
    ({'limit': 0}, 'limit_invalid'),
    ({'limit': 51}, 'limit_invalid'),
    ({'kinds': ['folders']}, 'kind_unknown'),
    ({'query': 'x' * 121}, 'query_too_long'),
])
def test_bad_requests_are_refused_with_a_stable_reason(arguments, reason):
    with pytest.raises(CollectionQueryError) as refused:
        query_collection(EN, everything(), secret=SECRET, **arguments)
    assert refused.value.reason == reason


def test_a_scope_without_account_or_language_is_refused():
    for bad in ({'account': '', 'language': 'en'}, {'account': 'a', 'language': ' '}):
        with pytest.raises(CollectionQueryError):
            QueryScope(**bad)


def test_the_query_writes_nothing_and_holds_no_copy():
    calls = []

    class Library:
        def read(self):
            calls.append('read')
            return LIBRARY

    owner = Owner('language', Library().read, language_entries)
    query_collection(EN, [owner], secret=SECRET)
    assert calls == ['read'], 'one read through the owner, nothing else'
