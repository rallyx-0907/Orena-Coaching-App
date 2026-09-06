import {alignToReference, hasWeakPronunciationEvidence, isSyntheticScore, scoreBand, stamp, transcriptLines, weakPronunciationWords} from './voice-assessment';

describe('scoreBand', () => {
  it('bands a real measurement', () => {
    expect(scoreBand(95)).toBe('strong');
    expect(scoreBand(80)).toBe('strong');
    expect(scoreBand(79)).toBe('steady');
    expect(scoreBand(60)).toBe('steady');
    expect(scoreBand(59)).toBe('developing');
  });

  /* A missing score is "not measured", never a band and never zero: the screen
     draws a ring and a word from this, and either would read as a judgement of
     the learner that nothing actually measured. */
  it('refuses to band anything that is not a real number', () => {
    expect(scoreBand(null)).toBeNull();
    expect(scoreBand(undefined)).toBeNull();
    expect(scoreBand(Number.NaN)).toBeNull();
    expect(scoreBand('88')).toBeNull();
  });
});

describe('stamp', () => {
  it('reads as M:SS and never goes negative', () => {
    expect(stamp(0)).toBe('0:00');
    expect(stamp(180000)).toBe('3:00');
    expect(stamp(-1)).toBe('0:00');
  });
});

describe('pronunciation evidence', () => {
  it('lists a word the provider named an error on', () => {
    expect(hasWeakPronunciationEvidence({word: 'practise', error_type: 'Mispronunciation'})).toBe(true);
  });

  it('lists a word the provider scored low', () => {
    expect(hasWeakPronunciationEvidence({word: 'practise', accuracy_score: 72})).toBe(true);
  });

  it('leaves out a word the provider was happy with', () => {
    expect(hasWeakPronunciationEvidence({word: 'good', accuracy_score: 95, error_type: 'None'})).toBe(false);
    expect(hasWeakPronunciationEvidence({word: 'good'})).toBe(false);
  });

  it('shows at most four, so the panel is evidence and not a wall', () => {
    const words = Array.from({length: 9}, (_, index) => ({word: `w${index}`, accuracy_score: 10}));
    expect(weakPronunciationWords({words})).toHaveLength(4);
  });

  it('has nothing to show without a provider result', () => {
    expect(weakPronunciationWords(null)).toEqual([]);
    expect(weakPronunciationWords({})).toEqual([]);
  });
});

describe('isSyntheticScore', () => {
  it('marks generated numbers so they are never read as a measurement', () => {
    expect(isSyntheticScore({score_kind: 'synthetic_demo'})).toBe(true);
    expect(isSyntheticScore({score_kind: 'provider'})).toBe(false);
    expect(isSyntheticScore(null)).toBe(false);
  });
});

describe('alignToReference', () => {
  it('marks which words of the line came back', () => {
    const {alignment, band} = alignToReference('Good morning everyone', 'good morning', 'en');
    expect(alignment.map((item) => item.matched)).toEqual([true, true, false]);
    expect(band).toBe('close');
  });

  it('reports a full match as strong', () => {
    expect(alignToReference('Good morning.', 'good morning', 'en').band).toBe('strong');
  });

  it('reports a mostly missed line as worth retrying', () => {
    expect(alignToReference('one two three four five', 'one', 'en').band).toBe('retry');
  });

  it('collects words that were not in the line', () => {
    expect(alignToReference('good morning', 'good morning everyone there', 'en').extra).toEqual(['everyone', 'there']);
  });

  it('does not credit one spoken word against two identical reference words', () => {
    const {alignment} = alignToReference('the the', 'the', 'en');
    expect(alignment.map((item) => item.matched)).toEqual([true, false]);
  });

  it('compares Chinese by character', () => {
    expect(alignToReference('我今天很好', '我今天很好', 'zh').band).toBe('strong');
  });

  it('has nothing to align when the line is empty', () => {
    expect(alignToReference('', 'anything', 'en').alignment).toEqual([]);
  });
});

describe('transcriptLines', () => {
  it('breaks the recognised text into sentences', () => {
    expect(transcriptLines('Hello there. How are you? Fine!')).toEqual(['Hello there.', 'How are you?', 'Fine!']);
  });

  it('breaks on CJK sentence marks too', () => {
    expect(transcriptLines('你好。你好吗？')).toEqual(['你好。你好吗？']);
  });

  it('has nothing to show for empty text', () => {
    expect(transcriptLines('')).toEqual([]);
  });
});
