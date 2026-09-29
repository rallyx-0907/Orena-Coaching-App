/* Gate for My Library's pure data mapping (screens/library/model.js). No DOM, no fetch: every
   function here takes already-fetched API data and returns the shape the screen paints. Design
   Contract rule 40 (never invent data) is what these assertions exist to hold: a metric the
   backend does not measure comes back 0/empty, never a guess. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  contentRows, contentRouteId, wordKindOf, isNewWord, masteryFilled, wordMeaning, languageRows,
  libraryCollectionRows, deckRows, collectionsAndDecks, dueStats, pinnedKindKey, dueListRows,
} from '../static/orena/screens/library/model.js';

// --- Content tab: only reading/media domains, a real content-kind route id, honest 0% progress ---
{
  assert.equal(contentRouteId('reading', 'a1'), 'article:a1', 'a reading-domain entry routes as content-kind "article" (screens/content/model.js\'s own KINDS), not the raw backend domain name');
  assert.equal(contentRouteId('media', 'lesson-2'), 'media:lesson-2', 'media is already the same word on both sides');

  const entries = [
    { ref: { domain: 'reading', id: 'a1' }, title: 'A Morning in the City', snippet: 'daily life' },
    { ref: { domain: 'media', id: 'lesson-2' }, title: 'Ordering coffee', snippet: '' },
    { ref: { domain: 'writing', id: '9' }, title: 'An essay' },
    { ref: { domain: 'grammar', id: 'present-perfect' }, title: 'Present perfect' },
  ];
  const rows = contentRows(entries);
  assert.equal(rows.length, 2, 'only reading and media entries become Content-tab rows');
  assert.deepEqual(rows.map((r) => r.contentId), ['article:a1', 'media:lesson-2'], 'the id is a content-kind route id screens/content/model.js\'s parseContentId actually recognises, not the raw domain string');
  assert.equal(rows[0].source, 'daily life', 'snippet becomes the source line');
  assert.equal(rows[1].source, '', 'a media entry with no snippet gets an honest empty source, not invented text');
  for (const row of rows) assert.equal(row.pct, 0, 'no account-level reading/listening position exists, so progress is the rule-40 zero, never a guess');
  assert.deepEqual(contentRows([]), [], 'no entries is an empty list, not a crash');
  assert.deepEqual(contentRows(undefined), [], 'a missing list defaults to empty');
}

// --- Saved-Language tab -----------------------------------------------------------------------
{
  assert.equal(wordKindOf('resilient'), 'word', 'a single token is a word');
  assert.equal(wordKindOf('break the ice'), 'phrase', 'more than one token is a phrase');
  assert.equal(wordKindOf('  spaced  '), 'word', 'surrounding whitespace alone is not a second token');

  assert.equal(isNewWord({ last_reviewed_at: '' }), true, 'never reviewed is NEW');
  assert.equal(isNewWord({ last_reviewed_at: '2026-01-01T00:00:00Z' }), false, 'a review timestamp is not NEW');

  assert.equal(masteryFilled({ review_stage: 2 }), 2, 'the stage fills that many bars');
  assert.equal(masteryFilled({ review_stage: 99 }, 4), 4, 'a stage past the meter size is clamped, not overflowed');
  assert.equal(masteryFilled({ review_stage: -3 }), 0, 'a negative stage floors at 0');
  assert.equal(masteryFilled({}), 0, 'a missing stage is 0, not invented');

  assert.equal(wordMeaning({ definition: 'to bounce back' }, 'zh'), 'to bounce back', 'the saved definition always wins, in any support language');
  assert.equal(wordMeaning({ translation_vi: 'kiên cường' }, 'vi'), 'kiên cường', 'the vi field is read only for vi support');
  assert.equal(wordMeaning({ translation_vi: 'kiên cường' }, 'zh'), '', 'the vi-only field never leaks into zh support - an honest empty line instead');
  assert.equal(wordMeaning({ translation_vi: 'kiên cường', source_fragment: 'stayed resilient' }, 'en'), 'stayed resilient', 'with no definition and no vi support, the source fragment is the fallback');
  assert.equal(wordMeaning({}, 'en'), '', 'nothing measured is an honest empty sub-line');

  const rows = languageRows([
    { word: 'break the ice', last_reviewed_at: '', review_stage: 0 },
    { word: 'resilient', last_reviewed_at: '2026-01-01T00:00:00Z', review_stage: 3, definition: 'able to recover' },
  ], 'en');
  assert.equal(rows[0].kind, 'phrase');
  assert.equal(rows[0].isNew, true);
  assert.equal(rows[1].kind, 'word');
  assert.equal(rows[1].isNew, false);
  assert.equal(rows[1].filled, 3);
  assert.equal(rows[1].sub, 'able to recover');
}

// --- Collections tab: two backend concepts, one honest shape (no invented cover/level) -------
{
  const lib = libraryCollectionRows([{ id: 'abc', title: 'My reading set', size: 5 }]);
  assert.equal(lib[0].collectionId, 'library:abc', 'a generic library collection is prefixed so it cannot collide with a deck id');
  assert.equal(lib[0].size, 5);

  const deck = deckRows([{ id: 'xyz', title: 'HSK 3 words', size: 12, cover: 'violet' }]);
  assert.equal(deck[0].collectionId, 'deck:xyz');
  assert.equal(deck[0].size, 12);

  const merged = collectionsAndDecks([{ id: '1', title: 'A', size: 1 }], [{ id: '2', title: 'B', size: 2 }]);
  assert.equal(merged.length, 2, 'both sources appear in the one Collections tab');
  assert.deepEqual(merged.map((r) => r.collectionId), ['library:1', 'deck:2']);
}

// --- Due-Review tab: only what the queue actually measures -----------------------------------
{
  const stats = dueStats({ due_count: 7, pinned_count: 3, total: 10 });
  assert.equal(stats.dueCount, 10);
  assert.equal(stats.dueWords, 7, 'due_count is the SRS-due vocabulary');
  assert.equal(stats.dueSource, 3, 'pinned_count is the closest real number to "source-aware"');
  assert.equal(stats.duePhrases, 0, 'no backend concept distinguishes a due phrase from a due word - the honest rule-40 zero');
  assert.equal(stats.dueMin, 0, 'no duration is measured for a session - the honest rule-40 zero, not a guessed estimate');
  assert.deepEqual(dueStats({}), { dueCount: 0, dueWords: 0, duePhrases: 0, dueSource: 0, dueMin: 0 }, 'an empty queue is all zeros, never omitted');
  assert.equal(dueStats({ due_count: 4, pinned_count: 2 }).dueCount, 6, 'without a total field, dueCount is derived from the two it does have');

  assert.equal(pinnedKindKey({ kind: 'word' }), 'kindWord');
  assert.equal(pinnedKindKey({ kind: 'grammar' }), 'kindGrammar');
  assert.equal(pinnedKindKey({ kind: 'unknown-future-kind' }), 'kindWord', 'an unrecognised kind falls back rather than crashing');

  const list = dueListRows({ pinned: [{ word: 'resilient', kind: 'word' }, { word: '', kind: 'reading' }] });
  assert.equal(list[0].text, 'resilient');
  assert.equal(list[1].text, '', 'a pinned row with no captured title is empty text, not an invented one - the screen falls back to its kind label');
  assert.equal(list[1].kindKey, 'kindReading');
  assert.deepEqual(dueListRows({}), [], 'no pinned field is an empty preview list, not a crash');
}

// M1 (api-audit): `GET /api/library/review-queue`'s `pinned[].kind` is a `LibraryItem.kind`
// (writing_coach/persistence/models.py LIBRARY_KINDS), which is 'listening' for a pinned
// listening/media item - never 'media' (that string is a *different* vocabulary, the
// `/api/collection` domain field). This fixture is a real, live capture (not hand-written): a
// listening lesson was kept and pinned through this same sandbox's own
// `POST /api/library/items` + `PATCH /api/library/items/{id}` flow, then
// `GET /api/library/review-queue` was captured as returned - the real
// `library_review_queue.json` capture has an empty `pinned` array (nothing was pinned yet in
// that capture), so it cannot exercise this path on its own.
{
  const queue = JSON.parse(
    readFileSync(new URL('../scripts/fixtures/api/library_review_queue_pinned_listening.json', import.meta.url)),
  );
  assert.equal(queue.pinned[0].kind, 'listening', 'sanity: the real backend writes "listening", never "media", for a pinned listening item');

  // Old code mapped only `media: 'kindMedia'`, so this real 'listening' value fell through to
  // the 'kindWord' default - a live pinned listening item silently mislabeled "Word"/"Từ".
  assert.equal(pinnedKindKey(queue.pinned[0]), 'kindMedia', 'a pinned listening item (the real API kind, "listening") maps to the Listening fallback label, not the Word default');

  const rows = dueListRows(queue);
  assert.equal(rows[0].text, '', 'the real pinned listening row has no word text, so the screen falls back to its kind label');
  assert.equal(rows[0].kindKey, 'kindMedia', 'the real payload reaches dueListRows() with the correct kind key end to end');
}

// languages-5 / finding A: screen.js marks Saved content's title and Saved language's word with
// the active learning language (both GET /api/collection and GET /api/library/vocabulary are
// scoped server-side to it) via the shared kit/lang.js helper - never left unmarked.
{
  const { readFileSync } = await import('node:fs');
  const screenSrc = readFileSync(new URL('../static/orena/screens/library/screen.js', import.meta.url), 'utf8');
  assert.match(screenSrc, /import\s*\{\s*langAttr,\s*langSpan\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'imports the shared lang helper from kit/lang.js');
  assert.match(screenSrc, /langSpan\(row\.title,\s*language\)/, 'the Saved content row title is wrapped with the active learning language');
  assert.match(screenSrc, /lang="\$\{langAttr\(language\)\}"/, 'the Saved language row word carries a real lang attribute');
}

console.log('Orena My Library screen: content/language/collections/due mapping, rule-40 zeros, no invented data: PASS');
