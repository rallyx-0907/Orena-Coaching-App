import pytest

from writing_coach import listening_catalog
from writing_coach.listening_catalog import lesson_metadata, validate_comprehension
from writing_coach import listening_api

# The shipped built-in Listening catalogue is empty since D-245; this module exercises catalogue lessons on the
# fixture-local copy of the retired manifest (conftest.fixture_listening_catalog).
pytestmark = pytest.mark.usefixtures("fixture_listening_catalog")


def test_questions_materialized_with_canonical_lesson():
    assert {lesson.source.language for lesson in listening_catalog.CATALOG if lesson.comprehension} == {'en', 'zh'}
    for lesson in listening_catalog.CATALOG:
        if not lesson.comprehension:
            continue  # Follow-only content does not promise a comprehension set.
        metadata = lesson_metadata(lesson)
        assert metadata['comprehension_count'] == len(lesson.comprehension)
        assert metadata['comprehension'] == list(lesson.comprehension)
        validate_comprehension(list(lesson.comprehension), lesson.media_object.transcript.segments)


@pytest.mark.parametrize('change', [
    {'correct_index': 99}, {'options': ['duplicate', 'duplicate']},
    {'evidence_segment_ids': ['outside-excerpt']}, {'explanation': ''},
])
def test_invalid_question_cannot_be_admitted(change):
    lesson = listening_catalog.CATALOG[0]
    question = dict(lesson.comprehension[0], **change)
    with pytest.raises(ValueError):
        validate_comprehension([question], lesson.media_object.transcript.segments)


def test_reopen_reads_persisted_questions_without_source_translation(monkeypatch):
    monkeypatch.setattr(listening_api, 'get_learner_profile', lambda: {'native_language': 'en'})
    resolve = listening_api.resolve_segment_meanings
    calls = []

    def read_only(**kwargs):
        calls.append(kwargs['translate'])
        assert kwargs['translate'] is None
        return resolve(**kwargs)

    monkeypatch.setattr(listening_api, 'resolve_segment_meanings', read_only)
    for language in ('en', 'zh'):
        lesson = next(item for item in listening_catalog.CATALOG if item.source.language == language and item.comprehension)
        first = listening_api.open_listening_library_lesson(lesson.lesson_id, 'en')
        reopened = listening_api.open_listening_library_lesson(lesson.lesson_id, 'en')
        assert first['catalog']['comprehension'] == reopened['catalog']['comprehension']
    assert calls == [None] * 4
