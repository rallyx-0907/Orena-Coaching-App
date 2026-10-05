/* Gate for the Reading Complete screen's DOM-free logic (design route `rcomplete`, frame 40,
   static/orena/screens/reader-complete/model.js): the navigation-origin label and route, the
   "understood" stat from the real reading-evidence payload, and the "Next" row's target (a real next
   chapter, a real unread article of the same language, or the frame's own Discover row). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8'));
}

const { originPlaceKey, originRouteId, comprehensionLabel, nextPick } = await import('../static/orena/screens/reader-complete/model.js');

// 1. A recognised navigation origin maps to its real shellCopy place key and its route; an unknown
// or missing origin falls back to Discover, never a blank "Back to" label.
assert.equal(originPlaceKey('today'), 'today');
assert.equal(originPlaceKey('library'), 'myLibrary');
assert.equal(originPlaceKey('practice'), 'practiceHub');
assert.equal(originPlaceKey('progress'), 'progress');
assert.equal(originPlaceKey('orena'), 'orena');
assert.equal(originPlaceKey('bogus'), 'discover');
assert.equal(originPlaceKey(undefined), 'discover');
assert.equal(originRouteId('library'), 'library');
assert.equal(originRouteId('bogus'), 'discover');
assert.equal(originRouteId(''), 'discover');
assert.equal(originRouteId('constructor'), 'discover', 'a prototype key is not a place');

// 2. "understood": the latest real attempt at THIS article, as correct/total (the built evidence
// payload carries article_id/correct_count/total); never attempted, or an unreadable attempt, is the
// frame's own em dash.
{
  const evidence = fixture('reading_practice_evidence_attempt.json');
  assert.ok(Array.isArray(evidence.items) && evidence.items.length > 0);
  for (const field of ['article_id', 'correct_count', 'total']) assert.ok(field in evidence.items[0], `evidence item carries ${field}`);
  const id = evidence.items[0].article_id;
  assert.equal(comprehensionLabel(evidence.items, id), '2/3');
  assert.equal(comprehensionLabel(evidence.items, 'another-article'), '—');
  assert.equal(comprehensionLabel([], id), '—');
  assert.equal(comprehensionLabel(fixture('reading_practice_evidence.json').items, id), '—', 'the real empty answer');
  assert.equal(comprehensionLabel([{ article_id: id, correct_count: 1, total: 0 }], id), '—', 'a zero total is not a score');
  assert.equal(comprehensionLabel([{ article_id: id, correct_count: 3, total: 3 }, ...evidence.items], id), '3/3', 'newest first');
  assert.equal(comprehensionLabel(undefined, id), '—');
}

// 3. The Next row.
{
  const articles = fixture('reading_articles.en.json').items;
  assert.ok(articles.length >= 2 && articles.every((a) => 'id' in a && 'title' in a));
  const book = { kind: 'book', isBook: true, bookId: 'b', neighbours: { next: { id: 'c2', title: 'CHAPTER II' } } };
  assert.deepEqual(nextPick({ doc: book, articles: [], continuation: [] }), { kind: 'chapter', title: 'CHAPTER II', id: 'book:b:c2' });
  const lastChapter = { kind: 'book', isBook: true, bookId: 'b', neighbours: { next: null } };
  assert.equal(nextPick({ doc: lastChapter, articles, continuation: [] }).kind, 'discover');
  const first = { kind: 'article', id: articles[0].id, isBook: false };
  assert.deepEqual(nextPick({ doc: first, articles, continuation: [] }), { kind: 'article', title: articles[1].title, id: `article:${articles[1].id}`, sameTheme: false }, 'another article, never this one');
  // "Next · same theme" (frame 40): an article on the same topic is offered before any other.
  const themed = [{ id: 'a1', title: 'One', topic: 'food' }, { id: 'a2', title: 'Two', topic: 'work' }, { id: 'a3', title: 'Three', topic: 'work' }];
  assert.deepEqual(nextPick({ doc: { kind: 'article', id: 'a2', isBook: false, topic: 'work' }, articles: themed, continuation: [] }), { kind: 'article', title: 'Three', id: 'article:a3', sameTheme: true });
  const finished = [{ id: `article:${articles[1].id}`, title: 'x', place: { index: 1, total: 1, within: 100 } }];
  assert.equal(nextPick({ doc: first, articles, continuation: finished }).kind, 'discover', 'a finished article is not offered next');
  const inProgress = [{ id: `article:${articles[1].id}`, title: 'x', place: { index: 1, total: 1, within: 40 } }];
  assert.equal(nextPick({ doc: first, articles, continuation: inProgress }).kind, 'article', 'one in progress is');
  assert.equal(nextPick({ doc: first, articles: [], continuation: [] }).kind, 'discover');
  assert.equal(nextPick({ doc: { kind: 'text', id: 't', isBook: false }, articles, continuation: [] }).kind, 'discover', 'an imported text has no catalogue to pick from');
  assert.equal(nextPick({ doc: first, articles: [{ id: 'z', title: '' }], continuation: [] }).kind, 'discover', 'an untitled item is not offered');
}

console.log('Orena Reading Complete model: origin label/route, understood stat from real evidence, next row: PASS');
