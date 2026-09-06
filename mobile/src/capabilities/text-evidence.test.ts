import {
  categoryKey, categoryReason, categoryRule, changedSegments, confidenceBand,
  feedbackBudget, findEvidenceRanges, learnerTextSpans, normalizedEvidenceItems,
  normalizedPosAnnotations, scoreBandKey, sentenceContext, weakestMetric,
} from './text-evidence';

describe('review domain helpers ported from the web', () => {
  it('bands the score the way review.js does', () => {
    expect(scoreBandKey(91)).toBe('review.score_excellent');
    expect(scoreBandKey(78)).toBe('review.score_strong');
    expect(scoreBandKey(65)).toBe('review.score_good');
    expect(scoreBandKey(50)).toBe('review.score_fair');
    expect(scoreBandKey(10)).toBe('review.score_weak');
    expect(scoreBandKey('nope')).toBeNull();
  });

  it('bands confidence in the evidence, defaulting to medium when absent', () => {
    expect(confidenceBand({confidence: 0.9})).toBe('high');
    expect(confidenceBand({confidence: 0.6})).toBe('medium');
    expect(confidenceBand({confidence: 0.2})).toBe('low');
    expect(confidenceBand({})).toBe('medium');
  });

  it('keeps only evidence that quotes the learner', () => {
    expect(normalizedEvidenceItems([{fragment: 'I has'}, {fragment: '   '}, {}, null, 'x'])).toEqual([{fragment: 'I has'}]);
    expect(normalizedEvidenceItems(undefined)).toEqual([]);
  });

  it('collapses reported categories onto the shared explanation keys', () => {
    // Normalised, then collapsed through the alias table.
    expect(categoryKey('subject-verb agreement')).toBe('grammar');
    expect(categoryKey('word_order')).toBe('grammar');
    expect(categoryKey('Tense')).toBe('verb_tense');
    expect(categoryKey(undefined)).toBe('expression');
  });

  it('answers in the interface language and falls back to expression', () => {
    expect(categoryReason('verb_form', 'en')).toBe(categoryReason('verb_tense', 'en'));
    expect(categoryReason('unmapped_category', 'en')).toBe(categoryReason('expression', 'en'));
    expect(categoryRule('collocation', 'zh')).toContain('搭配');
  });

  it('marks only what actually changed between the fragment and the suggestion', () => {
    const parts = changedSegments('I has a dog', 'I have a dog', 'en');
    expect(parts.beforeChange).toBe('has');
    expect(parts.afterChange).toBe('have');
    expect(parts.beforePrefix).toBe('I ');
    expect(parts.beforeSuffix).toBe(' a dog');
    // zh diffs by character, since there are no spaces to tokenise on.
    expect(changedSegments('我写了', '我写完了', 'zh').afterChange).toBe('完');
  });

  it('reports the weakest rubric metric', () => {
    expect(weakestMetric({grammar: 80, vocabulary: 60, coherence: 75})).toEqual({key: 'vocabulary', value: 60});
    expect(weakestMetric({})).toBeNull();
  });

  it('gives each guidance mode its own evidence budget', () => {
    expect(feedbackBudget('concise').visibleEvidence).toBe(1);
    expect(feedbackBudget('guided')).toMatchObject({visibleEvidence: 2, showRule: true});
    expect(feedbackBudget('advanced')).toMatchObject({visibleEvidence: 4, showMetrics: true});
  });

  it('maps evidence onto the learner text without overlapping marks', () => {
    const text = 'I has a dog and I has a cat.';
    const ranges = findEvidenceRanges(text, [{fragment: 'I has'}, {fragment: 'I has'}], [{fragment: 'a cat'}]);
    // The second identical fragment takes the next free occurrence, not the same one.
    expect(ranges.map((range) => [range.start, range.end, range.kind])).toEqual([
      [0, 5, 'error'], [16, 21, 'error'], [22, 27, 'strength'],
    ]);
  });

  it('drops annotations whose offsets no longer match the text', () => {
    const text = 'I write daily';
    expect(normalizedPosAnnotations(text, [
      {fragment: 'I', start: 0, end: 1, pos: 'pronoun'},
      {fragment: 'write', start: 2, end: 7, pos: 'verb'},
      {fragment: 'daily', start: 99, end: 104, pos: 'adverb'}, // out of range
      {fragment: 'wrong', start: 8, end: 13, pos: 'noun'}, // does not match the source
    ])).toEqual([
      {fragment: 'I', start: 0, end: 1, pos: 'pronoun', group: 'reference'},
      {fragment: 'write', start: 2, end: 7, pos: 'verb', group: 'verb'},
    ]);
  });

  it('splits the text into evidence spans, filling the gaps with word roles', () => {
    const text = 'I has a dog';
    const spans = learnerTextSpans(
      text,
      findEvidenceRanges(text, [{fragment: 'I has'}], []),
      normalizedPosAnnotations(text, [{fragment: 'dog', start: 8, end: 11, pos: 'noun'}]),
    );
    expect(spans).toEqual([
      {text: 'I has', evidence: 'error', index: 0},
      {text: ' a '},
      {text: 'dog', group: 'noun'},
    ]);
    expect(spans.map((span) => span.text).join('')).toBe(text);
  });

  it('quotes the sentence a fragment sits in', () => {
    const text = 'I write daily. I has a dog. It sleeps.';
    expect(sentenceContext(text, 'I has')).toBe('I has a dog.');
    expect(sentenceContext(text, 'not here')).toBe('');
  });
});
