"""I6 read step: LearnerSummary from the evidence each domain already owns.

docs/product/ORENA_EVIDENCE_ARCHITECTURE.md §§1-5 - domain-separated measures,
activity labelled as activity, assisted and synthetic results named, unknown
not zero, no trend without comparable measurements, and no achievements
without an approved policy. Hermetic: sources are fakes shaped like the rows
the real owner reads return.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from writing_coach.learner_summary import (
    POLICY_VERSION,
    Source,
    SummaryRequestError,
    learner_summary,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)

ESSAYS = [
    {'id': 31, 'created_at': '2026-09-12T10:00:00+00:00', 'overall': 38.0, 'evaluator': 'ollama:qwen3:8b', 'cefr_estimate': 'A2'},
    {'id': 12, 'created_at': '2026-06-01T10:00:00+00:00', 'overall': 55.0, 'evaluator': 'ollama:qwen3:8b'},
    {'id': 7, 'created_at': '2026-09-10T10:00:00+00:00', 'overall': 70.0, 'evaluator': 'fallback-demo'},
]
# Canonical Reading attempts (D-082). The first was recorded without an
# observation time; one with no questions is not a check answered.
READING = [
    {'id': 'attempt-1', 'kind': 'reading_attempt', 'article_id': 'a1', 'created_at': None,
     'correct_count': 3, 'total': 4},
    {'id': 'attempt-0', 'kind': 'reading_attempt', 'article_id': 'a2', 'created_at': '2026-09-12T09:30:00+00:00',
     'correct_count': 0, 'total': 0},
]
LISTENING = [
    {'asset_id': 'a', 'segment_id': 'a:000', 'checked_attempt_count': 2, 'revealed': False, 'best_accuracy_percent': 92, 'updated_at': '2026-09-12T11:00:00Z'},
    {'asset_id': 'a', 'segment_id': 'a:001', 'checked_attempt_count': 1, 'revealed': True, 'best_accuracy_percent': 100, 'updated_at': '2026-09-12T11:05:00Z'},
    {'asset_id': 'a', 'segment_id': 'a:002', 'checked_attempt_count': 0, 'revealed': False, 'best_accuracy_percent': None, 'updated_at': '2026-09-12T11:06:00Z'},
]
SPEAKING = [{
    'take_id': 'take-1', 'created_at': '2026-09-12T12:00:00+00:00',
    'dimensions': {'transcription_confidence': 0.9, 'content_match': None, 'pronunciation': None},
    'provenance': {'transcription_confidence': 'speech_asr', 'content_match': 'not_applicable', 'pronunciation': None},
    'evidence': {'synthetic_demo': False},
}]
LIBRARY = [
    {'word': 'harbour', 'added_at': '2026-09-11T08:00:00Z', 'successful_recalls': 2},
    {'word': 'lantern', 'added_at': '2026-01-01T08:00:00Z', 'successful_recalls': 1},
]


def sources(fail=(), **overrides):
    data = {
        'writing': ESSAYS, 'reading': READING, 'listening': LISTENING,
        'speaking': SPEAKING, 'grammar': {'present-perfect', 'articles'}, 'language': LIBRARY,
    }
    data.update(overrides)

    def reader(domain):
        def read():
            if domain in fail:
                raise RuntimeError(f'{domain} unavailable')
            return data[domain]
        return read

    return [Source(domain, reader(domain)) for domain in data]


def test_every_domain_reports_on_its_own_and_nothing_is_averaged():
    result = learner_summary('en', sources(), now=NOW)
    assert result['policyVersion'] == POLICY_VERSION
    assert result['outcome'] == 'current'
    assert set(result['domains']) == {'writing', 'reading', 'listening', 'speaking', 'grammar', 'language'}
    assert not any(key in result for key in ('score', 'overall', 'level')), 'no universal number'


def test_activity_is_a_labelled_count_inside_the_window():
    writing = learner_summary('en', sources(), now=NOW, window='30d')['domains']['writing']
    assert writing['activity']['label'] == 'submitted_versions'
    assert writing['activity']['count'] == 2, 'the June piece is outside 30 days'
    assert learner_summary('en', sources(), now=NOW, window='all')['domains']['writing']['activity']['count'] == 3


def test_a_demonstration_evaluator_is_synthetic_not_a_measurement():
    observations = learner_summary('en', sources(), now=NOW)['domains']['writing']['observations']
    demo = next(o for o in observations if o['ref']['id'] == '7')
    real = next(o for o in observations if o['ref']['id'] == '31')
    assert demo['synthetic'] is True and real['synthetic'] is False
    assert real['producer'] == 'ollama:qwen3:8b' and real['levelEstimate'] == 'A2'


def test_a_revealed_line_is_assisted_and_an_unchecked_line_is_not_counted():
    listening = learner_summary('en', sources(), now=NOW)['domains']['listening']
    assert listening['activity']['count'] == 2, 'a line never checked is not reconstruction'
    by_ref = {o['ref']['id']: o for o in listening['observations']}
    assert by_ref['a#a:001']['assisted'] is True
    assert by_ref['a#a:000']['assisted'] is False


def test_records_with_no_observation_time_are_undated_not_placed_in_the_window():
    result = learner_summary('en', sources(), now=NOW)
    reading = result['domains']['reading']
    assert reading['activity'] == {'label': 'checks_answered', 'count': 0, 'undated': 1, 'lastObservedAt': None, 'countKind': 'exact'}
    assert reading['observations'][0]['value'] == {'correct': 3, 'total': 4}
    assert reading['observations'][0]['observedAt'] is None
    grammar = result['domains']['grammar']
    assert grammar['activity']['undated'] == 2 and grammar['activity']['count'] == 0


def test_speaking_keeps_measured_not_applicable_and_not_measured_apart():
    take = learner_summary('en', sources(), now=NOW)['domains']['speaking']['observations'][0]
    assert take['value'] == {'transcription_confidence': 0.9}
    assert take['status'] == {'content_match': 'not_applicable', 'pronunciation': None}
    assert take['producer'] == {'transcription_confidence': 'speech_asr'}


def test_an_owner_that_cannot_be_read_is_unavailable_not_zero():
    result = learner_summary('en', sources(fail={'speaking', 'listening'}), now=NOW)
    assert result['outcome'] == 'partial'
    assert result['unavailableDomains'] == ['listening', 'speaking']
    assert result['domains']['speaking'] == {'status': 'unavailable'}


def test_a_read_that_fills_its_bound_makes_counts_lower_bounds():
    bounded = [Source(s.domain, s.read, 2 if s.domain == 'listening' else None) for s in sources()]
    result = learner_summary('en', bounded, now=NOW)
    assert result['outcome'] == 'partial' and result['truncatedDomains'] == ['listening']
    assert result['domains']['listening']['activity']['countKind'] == 'at_least'
    assert result['domains']['writing']['activity']['countKind'] == 'exact'


def test_no_evidence_at_all_is_empty_not_a_row_of_zeros_presented_as_progress():
    empty = learner_summary('zh', sources(writing=[], reading=[], listening=[], speaking=[], grammar=set(), language=[]), now=NOW)
    assert empty['outcome'] == 'empty'
    assert all(domain['status'] == 'empty' for domain in empty['domains'].values())
    assert empty['learningLanguage'] == 'zh'


def test_no_domain_claims_a_trend_without_comparable_measurements():
    for name, domain in learner_summary('en', sources(), now=NOW)['domains'].items():
        assert domain['growth']['status'] == 'unavailable', name
        assert domain['growth']['reason'], name


def test_no_approved_achievement_policy_means_no_achievements():
    achievements = learner_summary('en', sources(), now=NOW)['achievements']
    assert achievements == {'status': 'unavailable', 'reason': 'no_approved_policy', 'items': []}


@pytest.mark.parametrize('arguments, reason', [
    ({'window': '1y'}, 'window_unknown'),
])
def test_bad_requests_are_refused(arguments, reason):
    with pytest.raises(SummaryRequestError) as refused:
        learner_summary('en', sources(), now=NOW, **arguments)
    assert refused.value.reason == reason
    with pytest.raises(SummaryRequestError):
        learner_summary(' ', sources(), now=NOW)
