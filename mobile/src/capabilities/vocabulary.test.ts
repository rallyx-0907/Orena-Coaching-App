import {countsByType, daysFromNow, focusAreas, isSoon, itemType, labelledType, libraryCounts, masteryStage, masteryTone, pageOf, recallAccuracy, relativeTone, reviewedToday, typeTabs, visibleItems, type LibraryItem} from './vocabulary';

const NOW = new Date('2026-06-10T09:00:00Z');
const at = (days: number) => new Date(NOW.getTime() + days * 86400000).toISOString();
const item = (over: Partial<LibraryItem> = {}): LibraryItem => ({word: 'clarity', ...over});

describe('itemType', () => {
  it('trusts the dictionary label first', () => {
    expect(labelledType(item({part_of_speech: 'phrasal verb'}))).toBe('phrasalVerb');
    expect(labelledType(item({part_of_speech: 'idiom'}))).toBe('idiom');
    expect(labelledType(item({part_of_speech: '量词'}))).toBe('measure');
    expect(labelledType(item({part_of_speech: 'noun'}))).toBeNull();
  });

  /* Order matters in the rule table: "phrase" is a substring of "phrasal verb"
     and "idiom" is inside "idiomatic", so the narrower rules have to win. */
  it('does not let a broad rule swallow a narrow one', () => {
    expect(labelledType(item({part_of_speech: 'phrasal verb'}))).not.toBe('phrase');
    expect(labelledType(item({part_of_speech: 'idiomatic expression'}))).toBe('idiom');
  });

  it('falls back to whether it reads as more than one unit', () => {
    expect(itemType(item({word: 'clarity'}), 'en')).toBe('word');
    expect(itemType(item({word: 'take responsibility'}), 'en')).toBe('phrase');
    expect(itemType(item({word: '越来越'}), 'zh')).toBe('word');
    expect(itemType(item({word: '一见钟情'}), 'zh')).toBe('phrase');
  });
});

describe('scheduling', () => {
  it('counts whole days from midnight', () => {
    expect(daysFromNow(at(0), NOW)).toBe(0);
    expect(daysFromNow(at(1), NOW)).toBe(1);
    expect(daysFromNow(undefined, NOW)).toBeNull();
    expect(daysFromNow('not a date', NOW)).toBeNull();
  });

  it('calls an item soon only when it is not already due', () => {
    expect(isSoon(item({next_review_at: at(2)}), NOW)).toBe(true);
    expect(isSoon(item({next_review_at: at(9)}), NOW)).toBe(false);
    expect(isSoon(item({due: true, next_review_at: at(2)}), NOW)).toBe(false);
  });

  it('knows what was reviewed today', () => {
    expect(reviewedToday(item({last_reviewed_at: at(0)}), NOW)).toBe(true);
    expect(reviewedToday(item({last_reviewed_at: at(-1)}), NOW)).toBe(false);
    expect(reviewedToday(item({}), NOW)).toBe(false);
  });

  it('describes when an item comes back', () => {
    expect(relativeTone(item({due: true}), NOW).tone).toBe('due');
    expect(relativeTone(item({next_review_at: at(1)}), NOW).tone).toBe('soon');
    expect(relativeTone(item({next_review_at: at(30)}), NOW).tone).toBe('later');
    // Nothing scheduled is its own state, not "due".
    expect(relativeTone(item({}), NOW).tone).toBe('none');
  });
});

describe('mastery', () => {
  it('clamps the stage to the five dots the reference draws', () => {
    expect(masteryStage(item({review_stage: -3}))).toBe(0);
    expect(masteryStage(item({review_stage: 9}))).toBe(4);
    expect(masteryStage(item({}))).toBe(0);
  });

  it('bands the stage without claiming mastery', () => {
    expect(masteryTone(0)).toBe('new');
    expect(masteryTone(1)).toBe('reviewing');
    expect(masteryTone(2)).toBe('good');
    expect(masteryTone(4)).toBe('strong');
  });
});

describe('counts', () => {
  const items = [
    item({word: 'a', due: true}),
    item({word: 'b', next_review_at: at(1)}),
    item({word: 'c', next_review_at: at(40)}),
  ];

  it('splits the library into due, soon and later', () => {
    expect(libraryCounts(items, NOW)).toEqual({all: 3, due: 1, soon: 1, later: 1});
  });

  it('offers every category the language has, even the empty ones', () => {
    const tabs = typeTabs([item({word: 'clarity'})], 'en');
    expect(tabs).toContain('word');
    expect(tabs).toContain('idiom');
    expect(typeTabs([], 'zh')).toContain('measure');
  });

  it('adds a labelled category the standard order does not name', () => {
    expect(typeTabs([item({part_of_speech: '歇后语'})], 'en')).toContain('xiehouyu');
  });

  it('counts by type', () => {
    expect(countsByType([item({word: 'a'}), item({word: 'take part'})], 'en')).toEqual({word: 1, phrase: 1});
  });
});

describe('recallAccuracy', () => {
  it('is scoped to recorded recalls', () => {
    expect(recallAccuracy([item({successful_recalls: 3, lapse_count: 1})])).toEqual({accuracy: 75, recalls: 3, lapses: 1});
  });

  /* An untouched library is not 0% accurate; it has nothing to report. */
  it('reports nothing rather than zero when nothing was recorded', () => {
    expect(recallAccuracy([item({})]).accuracy).toBeNull();
    expect(recallAccuracy([]).accuracy).toBeNull();
  });
});

describe('focusAreas', () => {
  it('names the three parts of speech with the most due items', () => {
    const items = [
      item({word: 'a', due: true, part_of_speech: 'noun'}),
      item({word: 'b', due: true, part_of_speech: 'noun'}),
      item({word: 'c', due: true, part_of_speech: 'verb'}),
      item({word: 'd', part_of_speech: 'adverb'}),
    ];
    expect(focusAreas(items, 'unlabelled')).toEqual([['noun', 2], ['verb', 1]]);
  });

  it('groups unlabelled due items under the fallback', () => {
    expect(focusAreas([item({due: true})], 'unlabelled')).toEqual([['unlabelled', 1]]);
  });
});

describe('visibleItems', () => {
  const items = [
    item({word: 'zebra', due: true, review_stage: 3, added_at: '2026-01-01', next_review_at: at(0)}),
    item({word: 'apple', review_stage: 0, added_at: '2026-05-01', next_review_at: at(2)}),
    item({word: 'mango', review_stage: 1, added_at: '2026-03-01', next_review_at: at(40)}),
  ];

  it('puts due items first by default', () => {
    expect(visibleItems(items, {tab: 'all', filter: 'all', sort: 'next'}, 'en', NOW)[0]!.word).toBe('zebra');
  });

  it('sorts alphabetically, by added date, and by stage', () => {
    expect(visibleItems(items, {tab: 'all', filter: 'all', sort: 'alpha'}, 'en', NOW).map((row) => row.word)).toEqual(['apple', 'mango', 'zebra']);
    expect(visibleItems(items, {tab: 'all', filter: 'all', sort: 'added'}, 'en', NOW)[0]!.word).toBe('apple');
    expect(visibleItems(items, {tab: 'all', filter: 'all', sort: 'mastery'}, 'en', NOW)[0]!.word).toBe('zebra');
  });

  it('filters by due, soon and new', () => {
    expect(visibleItems(items, {tab: 'all', filter: 'due', sort: 'next'}, 'en', NOW).map((r) => r.word)).toEqual(['zebra']);
    expect(visibleItems(items, {tab: 'all', filter: 'soon', sort: 'next'}, 'en', NOW).map((r) => r.word)).toEqual(['apple']);
    expect(visibleItems(items, {tab: 'all', filter: 'new', sort: 'next'}, 'en', NOW).map((r) => r.word)).toEqual(['apple']);
  });

  it('filters by category tab', () => {
    expect(visibleItems([...items, item({word: 'take part'})], {tab: 'phrase', filter: 'all', sort: 'next'}, 'en', NOW).map((r) => r.word)).toEqual(['take part']);
  });

  it('does not mutate the caller\'s list', () => {
    const original = [...items];
    visibleItems(items, {tab: 'all', filter: 'all', sort: 'alpha'}, 'en', NOW);
    expect(items).toEqual(original);
  });
});

describe('pageOf', () => {
  const rows = Array.from({length: 23}, (_, index) => index);

  it('slices a page and reports the range', () => {
    expect(pageOf(rows, 1)).toMatchObject({page: 1, pages: 3, from: 1, to: 10});
    expect(pageOf(rows, 3)).toMatchObject({page: 3, pages: 3, from: 21, to: 23});
  });

  it('clamps a page outside the range', () => {
    expect(pageOf(rows, 99).page).toBe(3);
    expect(pageOf(rows, 0).page).toBe(1);
  });

  it('reports an empty list as zero of zero', () => {
    expect(pageOf([], 1)).toMatchObject({page: 1, pages: 1, from: 0, to: 0});
  });
});
