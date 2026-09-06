import {
  bandTier, countUnits, difficultyAdjustment, evaluationErrorKey, guidanceMode,
  normalizedWatchlist, savedLabel, watchlistTrend, writingScaffold,
} from './writing-feedback';

describe('writing domain helpers ported from the web', () => {
  it('counts units the way language.js does for each learning language', () => {
    expect(countUnits('I write every day', 'en')).toBe(4);
    // zh counts Han characters plus latin words, not whitespace tokens:
    // five characters, then "5" and "words".
    expect(countUnits('我今天写了 5 words', 'zh')).toBe(5 + 2);
    expect(countUnits('', 'en')).toBe(0);
  });

  it('maps CEFR and HSK onto the same six-step band ladder', () => {
    expect(bandTier('B2')).toBe('upper');
    expect(bandTier('HSK4')).toBe('intermediate');
    expect(bandTier('HSK7-9')).toBe('proficient');
    expect(bandTier('nonsense')).toBeNull();
  });

  it('follows adaptive.js when choosing a guidance mode', () => {
    expect(guidanceMode('deep', 'en', 'A1')).toBe('advanced');
    expect(guidanceMode('guided', 'en', 'A2')).toBe('guided');
    expect(guidanceMode('guided', 'en', 'C1')).toBe('advanced');
    // zh needs one more band before it counts as advanced.
    expect(guidanceMode('guided', 'zh', 'HSK5')).toBe('guided');
    expect(guidanceMode('guided', 'zh', 'HSK6')).toBe('advanced');
  });

  it('gives each guidance mode its own scaffold in both languages', () => {
    expect(writingScaffold('concise', 'en').items).toHaveLength(2);
    expect(writingScaffold('guided', 'zh').title).toBe('一步一步，不需要一次写完美');
  });

  it('reports a difficulty adjustment only from a well-formed recommendation', () => {
    expect(difficultyAdjustment({difficulty: {state: 'stretch', length_delta: -20}}))
      .toEqual({state: 'stretch', delta: 20, key: 'write.difficulty_stretch'});
    expect(difficultyAdjustment({difficulty: {state: 'stretch', length_delta: 1.5}}))
      .toEqual({state: 'insufficient', delta: 0, key: 'write.difficulty_insufficient'});
    expect(difficultyAdjustment({})).toBeNull();
    expect(difficultyAdjustment(null)).toBeNull();
  });

  it('keeps only recurring watchlist patterns whose counts actually add up', () => {
    const kept = {category: 'article', status: 'recurring', total: 5, older: 2, newer: 3};
    expect(normalizedWatchlist([
      kept,
      {...kept, category: 'not_a_category'},
      {...kept, status: 'improving'},
      {...kept, total: 4}, // total !== older + newer
      {...kept, older: 4, newer: 1}, // newer must not fall below older
      {...kept, total: 2, older: 1, newer: 1}, // below the evidence floor
    ])).toEqual([kept]);
    expect(normalizedWatchlist('nope')).toEqual([]);
  });

  it('names the trend from the two measured points', () => {
    expect(watchlistTrend({category: 'a', status: 'recurring', total: 5, older: 3, newer: 2})).toBe('down');
    expect(watchlistTrend({category: 'a', status: 'recurring', total: 5, older: 2, newer: 3})).toBe('up');
    expect(watchlistTrend({category: 'a', status: 'recurring', total: 4, older: 2, newer: 2})).toBe('flat');
  });

  it('ages the saved stamp the way write.js does', () => {
    const now = 1_000_000_000;
    expect(savedLabel(null, now)).toEqual({key: 'write.saved_never'});
    expect(savedLabel(0, now)).toEqual({key: 'write.saved_never'});
    expect(savedLabel(now, now)).toEqual({key: 'write.saved_now'});
    // A future stamp means a skewed clock, which write.js reports as unsaved
    // rather than inventing a negative age.
    expect(savedLabel(now + 120000, now)).toEqual({key: 'write.saved_never'});
    expect(savedLabel(now - 120000, now)).toEqual({key: 'write.saved_minutes', n: 2});
    expect(savedLabel(now - 7200000, now)).toEqual({key: 'write.saved_hours', n: 2});
  });

  it('names the evaluator failure instead of a generic outage', () => {
    expect(evaluationErrorKey('language_scope_mismatch')).toBe('write.language_scope_mismatch');
    expect(evaluationErrorKey('evaluation_provider_failure')).toBe('write.evaluation_provider_failure');
    expect(evaluationErrorKey('something_else')).toBe('write.review_failed');
    expect(evaluationErrorKey(undefined)).toBe('write.review_failed');
  });
});
