"""Free expression reuses per-take evidence without inventing a reference."""
import pytest
from writing_coach.speaking_evaluator import build_speaking_evaluation, SpeakingEvaluationInvalid
from writing_coach.speech_api import SpeakingAttemptIn, _normalize_speaking_attempt
from writing_coach.core.request_context import LANGUAGE_CODE_CTX


@pytest.fixture(autouse=True)
def language_scope(request):
    language = getattr(request.node, 'callspec', None)
    token = LANGUAGE_CODE_CTX.set(language.params.get('language', 'en') if language else 'en')
    yield
    LANGUAGE_CODE_CTX.reset(token)


@pytest.mark.parametrize('language,words', [('en', 'I would take the train.'), ('zh', '我想坐火车去。')])
def test_free_expression_survives_the_existing_persistence_boundary(language, words):
    evaluation = build_speaking_evaluation(language=language, reference_text='', transcript_text=words)
    record = _normalize_speaking_attempt(SpeakingAttemptIn(
        language=language, take_id='take-free', segment_id='voice:invitation',
        reference_text='', transcript_text=words, evaluation=evaluation,
    ))
    assert record['reference_text'] == ''
    assert record['transcript_text'] == words
    assert record['dimensions']['content_match'] is None
    assert 'proficiency' not in record['dimensions']
    assert evaluation['dimensions']['proficiency'] is None
    assert record['evidence']['content'] == {'missing_tokens': [], 'extra_tokens': []}


def test_free_expression_cannot_claim_reference_alignment():
    with pytest.raises(SpeakingEvaluationInvalid):
        build_speaking_evaluation(language='en', reference_text='', transcript_text='My own idea.', content_match=100)
    evaluation = build_speaking_evaluation(language='en', reference_text='', transcript_text='My own idea.')
    evaluation['dimensions']['content_match'] = 100
    with pytest.raises(SpeakingEvaluationInvalid):
        _normalize_speaking_attempt(SpeakingAttemptIn(language='en',take_id='take-free',segment_id='voice:free',reference_text='',transcript_text='My own idea.',evaluation=evaluation))


def test_absent_alignment_is_inapplicable_not_unmeasured():
    """A dimension that does not apply is a different claim from one that failed.

    Free expression has no line to match. Reporting that as "not measured"
    would describe a gap in the stack, when the truth is that the task never
    had a line in it.
    """
    free = build_speaking_evaluation(language='en', reference_text='', transcript_text='My own idea.')
    assert free['dimensions']['content_match'] is None
    assert free['provenance']['content_match'] == 'not_applicable'

    against_a_line = build_speaking_evaluation(
        language='en',
        reference_text='I would take the train.',
        transcript_text='I would take the bus.',
        content_match={'content_match': 72, 'missing_tokens': ['train'], 'extra_tokens': ['bus']},
    )
    assert against_a_line['provenance']['content_match'] == 'deterministic_reference_alignment'

    # A reference that was given but produced no alignment is still unmeasured:
    # something could have been compared and was not.
    unmeasured = build_speaking_evaluation(
        language='en', reference_text='I would take the train.', transcript_text='I would take the bus.',
    )
    assert unmeasured['provenance']['content_match'] is None


def test_inapplicable_alignment_survives_persistence():
    evaluation = build_speaking_evaluation(language='en', reference_text='', transcript_text='My own idea.')
    record = _normalize_speaking_attempt(SpeakingAttemptIn(
        language='en', take_id='take-free', segment_id='voice:free',
        reference_text='', transcript_text='My own idea.', evaluation=evaluation,
    ))
    assert record['provenance']['content_match'] == 'not_applicable'
