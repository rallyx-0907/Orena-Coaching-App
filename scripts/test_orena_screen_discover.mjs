/* Gate for Discover's data mapping and filtering (Design Contract rules 40, 42; frame
   04-Discover.html, 52-Filter-Sheet.html). screens/discover/model.js is DOM-free - imported
   directly, no globals to stub. */
import assert from 'node:assert/strict';
import { practiceCandidates, practiceHref, preparedMediaEntry } from '../static/orena/screens/discover/model.js';
{
  for (const language of ['en', 'zh']) {
    const ready = entryFromMedia({lesson_id:'ready', language, available_modes:['shadowing']}, []);
    const unavailable = entryFromMedia({lesson_id:'listen-only', language, available_modes:['listen']}, []);
    assert.deepEqual(practiceCandidates([ready, unavailable, {kind:'upload',id:'upload:pending'}]), [ready]);
    const href = (route, params, query) => ({route,params,query});
    assert.deepEqual(practiceHref(ready, href, {source:'ready',segment:'line-2'}), {route:'shadow',params:{id:'ready'},query:{segment:'line-2'}});
    assert.deepEqual(practiceHref(ready, href, {source:'other',segment:'line-2'}), {route:'shadow',params:{id:'ready'},query:{}});
    const payload = {catalog:{lesson_id:'private'},asset:{processing_state:'ready'},playback:{kind:'embed'}};
    const source = {hasModelAudio:true,language,title:'My media'};
    const imported = preparedMediaEntry('upload:private',payload,source,language,[]);
    assert.equal(imported.id,'media:private');
    assert.deepEqual(practiceHref(imported,href,{source:'upload:private',segment:'line-2'}),{route:'shadow',params:{id:'private'},query:{segment:'line-2'}});
    assert.equal(preparedMediaEntry('x',payload,{...source,hasModelAudio:false},language,[]),null);
    assert.equal(preparedMediaEntry('x',payload,{...source,language:'other'},language,[]),null);
    assert.equal(preparedMediaEntry('x',{...payload,asset:{processing_state:'processing'}},source,language,[]),null);
    assert.deepEqual(practiceHref({speakingId:'speak:12'},href),{route:'speak',params:{id:'speak:12'},query:{}});
  }
}
import {
  progressFromContinuation, entryFromArticle, entryFromBook, entryFromMedia, entryFromCollection,
  entryFromTextImport, entryFromMediaImport, filterOptions, topicKey, topicLabel, typeLabel, matchesFilters,
  hasAnyFilter, filterCount, visibleEntries, presentCard, hrefFor,
} from '../static/orena/screens/discover/model.js';

/* A tiny stand-in for copy/discover.js's translate function - a plain function of its two
   arguments, exactly what presentCard()/typeLabel() are documented to take. */
function fill(text, params) {
  if (!params) return text;
  return String(text).replace(/\{(\w+)\}/g, (m, name) => (params[name] ?? m));
}
const LABELS = {
  typeArticle: 'Article', typeBook: 'Book', typeVideo: 'Video', typeAudio: 'Audio',
  typeCollection: 'Collection', typeText: 'Text', typeUpload: 'Imported',
  topic_daily_life: 'Daily life', topic_culture: 'Culture',
  durationMinRead: '{n} min read', progressPercent: '{pct}%', progressLearnedOf: '{learned} / {total} learned',
};
function stubT() {
  const t = (key, params) => fill(LABELS[key] ?? key, params);
  t.plural = (key, n, params = {}) => {
    const forms = {
      durationChapters: n === 1 ? '{n} chapter' : '{n} chapters',
      durationItems: n === 1 ? '{n} item' : '{n} items',
      collectionWordCount: n === 1 ? '{n} word' : '{n} words',
      resultsLabel: n === 1 ? '{n} result' : '{n} results',
      showResults: n === 1 ? 'Show {n} result' : 'Show {n} results',
    };
    return fill(forms[key] ?? key, { n, ...params });
  };
  return t;
}
const t = stubT();
const href = (id, params = {}) => `#/${id}${params.id ? `/${params.id}` : ''}`;

// 1. progressFromContinuation: null with no match or an incomplete place; a whole clamped
// percent otherwise; prefix mode for a book's per-chapter continuation id.
{
  assert.equal(progressFromContinuation([], 'article:1'), null, 'no continuation at all');
  assert.equal(progressFromContinuation([{ id: 'article:1', place: { index: 0, total: 5 } }], 'article:1'), null, 'index 0 is not started');
  assert.equal(progressFromContinuation([{ id: 'article:1', place: { index: 2, total: 4 } }], 'article:1'), 50, 'exact-id match computes a percent');
  assert.equal(progressFromContinuation([{ id: 'book:9:ch2', place: { index: 3, total: 3 } }], 'book:9', { idPrefix: 'book:9:' }), 100, 'prefix match finds a chapter row');
  assert.equal(progressFromContinuation([{ id: 'book:9:ch2', place: { index: 3, total: 3 } }], 'book:9', { idPrefix: 'book:10:' }), null, 'prefix match is exact to the book id, not a substring of another book');
}

// 2. entryFromArticle: id shape, real fields carried, no image/author field the source has none
// of, progress read from continuation.
{
  const entry = entryFromArticle(
    { id: 'a1', title: 'Why We Love Routines', level: 'B2', topic: 'Daily life', reading_time_seconds: 340 },
    [{ id: 'article:a1', place: { index: 1, total: 1 } }],
  );
  assert.equal(entry.id, 'article:a1');
  assert.equal(entry.kind, 'article');
  assert.equal(entry.author, '', 'no source/publication field exists for an article - left out, not invented');
  assert.equal(entry.image, '', 'no image field exists for an article');
  assert.equal(entry.readingSeconds, 340);
  assert.equal(entry.started, true);
  assert.equal(entry.progressPct, 100);
  assert.equal(entry.language, '', 'no language field on this fixture - never invented');
  assert.equal(entryFromArticle({ id: 'a2', title: 'x' }, []).readingSeconds, null, 'a missing reading_time_seconds is left out, not defaulted to 0');
  // languages-5 / finding A: the article's own real language field
  // (reading_content_repository.py's `_learner_row`), carried straight through.
  assert.equal(entryFromArticle({ id: 'a3', title: 'x', language: 'zh' }, []).language, 'zh');
}

// 3. entryFromBook: cover only from a real cover_asset_key; progress by the book's chapter-id
// prefix, not the book id alone.
{
  const withCover = entryFromBook({ id: 'b1', title: 'The Slow Commute', author: 'M. Okafor', cover_asset_key: 'k1' }, [], '/api/reading/library/books/b1/cover');
  assert.equal(withCover.id, 'book:b1');
  assert.equal(withCover.image, 'url(/api/reading/library/books/b1/cover)');
  const withoutCover = entryFromBook({ id: 'b2', title: 'x' }, [], '/api/reading/library/books/b2/cover');
  assert.equal(withoutCover.image, '', 'no cover_asset_key draws no image, never a placeholder URL');
  const started = entryFromBook({ id: 'b3', title: 'x' }, [{ id: 'book:b3:ch4', place: { index: 4, total: 8 } }], '');
  assert.equal(started.started, true);
  assert.equal(started.progressPct, 50);
  // languages-5 / finding A: a book's own field is `learning_language`, a different name than an
  // article's `language` - both mapped to the same `entry.language`.
  assert.equal(entryFromBook({ id: 'b4', title: 'x', learning_language: 'en' }, [], '').language, 'en');
}

// 4. entryFromMedia: media type from media_type, an insecure or missing poster draws no image,
// source_label carried as the meta field.
{
  const video = entryFromMedia({ lesson_id: 'm1', media_type: 'video', title: 'A Morning in the City', level: 'B2', topic: 'Daily life', duration_ms: 78000, poster_url: 'https://img/x.jpg', source_label: 'Everyday English' }, []);
  assert.equal(video.id, 'media:m1');
  assert.equal(video.mediaType, 'video');
  assert.equal(video.image, 'url(https://img/x.jpg)');
  assert.equal(video.author, 'Everyday English');
  assert.equal(video.clipMs, 78000);
  const insecure = entryFromMedia({ media_object_id: 'm2', media_type: 'audio', poster_url: 'http://img/x.jpg' }, []);
  assert.equal(insecure.image, '', 'a non-https poster draws no image');
  assert.equal(insecure.id, 'media:m2', 'falls back to media_object_id when lesson_id is absent');
  // languages-5 / finding A: the media item's own `language` field
  // (writing_coach/listening_api.py `stored_media_metadata`/`catalog_lessons`).
  assert.equal(entryFromMedia({ lesson_id: 'm3', title: 'x', language: 'zh' }, []).language, 'zh');
}

// 5. entryFromCollection: progress from the collection's own learned/item_count, not the
// continuation shelf; zero items is not "started".
{
  const learning = entryFromCollection({ id: 'c1', title: 'Daily Life A2', item_count: 40, level_range: 'A2-B1', progress: { learned_count: 10 } });
  assert.equal(learning.id, 'collection:c1');
  assert.equal(learning.started, true);
  assert.equal(learning.progressPct, 25);
  assert.equal(learning.progressLearned, 10);
  assert.equal(learning.progressTotal, 40);
  const untouched = entryFromCollection({ id: 'c2', title: 'x', item_count: 12, progress: { learned_count: 0 } });
  assert.equal(untouched.started, false);
  assert.equal(untouched.progressPct, null);
  const empty = entryFromCollection({ id: 'c3', title: 'x', item_count: 0 });
  assert.equal(empty.itemCount, null, 'zero items is left out, not shown as a real count');
  // languages-5 / finding A: `language_code` (writing_coach/vocabulary_library.py `_summary`).
  assert.equal(entryFromCollection({ id: 'c4', title: 'x', language_code: 'en' }).language, 'en');
}

// 6. entryFromTextImport / entryFromMediaImport: device-memory ids travel through this screen's
// content-id contract exactly as the brief states.
{
  const text = entryFromTextImport({ id: 'text:abc', title: 'My pasted note' });
  assert.equal(text.id, 'text:abc', 'a text import\'s own id already is the content id - unchanged');
  const upload = entryFromMediaImport({ id: 'upload:xyz', title: 'My clip', provider: 'youtube', duration_ms: 5000 }, []);
  assert.equal(upload.id, 'upload:upload:xyz', 'the kind prefix wraps the memory module\'s own id verbatim, colon and all');
  const fromUrl = entryFromMediaImport({ id: 'url:abc', title: 'x' }, []);
  assert.equal(fromUrl.id, 'upload:url:abc');
  assert.equal(fromUrl.kind, 'upload', 'a pasted-link import is still the "upload" kind - the contract has no separate "url" kind');
}

// 7. filterOptions: derived from what is actually loaded, sorted, deduplicated; a media entry's
// group value is its media type, not the generic "media" kind.
{
  const entries = [
    { kind: 'article', level: 'B2', topic: 'Daily life' },
    { kind: 'article', level: 'B1', topic: 'Daily life' },
    { kind: 'media', mediaType: 'video', level: 'B2', topic: 'Travel' },
    { kind: 'media', mediaType: 'audio', level: '', topic: '' },
    { kind: 'book', level: '', topic: '' },
  ];
  const groups = filterOptions(entries);
  assert.deepEqual(groups.level, ['B1', 'B2']);
  assert.deepEqual(groups.topic, ['Daily life', 'Travel']);
  assert.deepEqual(groups.type, ['article', 'book', 'media-audio', 'media-video']);
}

// 8. typeLabel: known kind/media-type values translate; an unrecognised value passes through
// rather than throwing (defensive, should never actually happen).
{
  assert.equal(typeLabel('media-video', t), 'Video');
  assert.equal(typeLabel('collection', t), 'Collection');
  assert.equal(typeLabel('mystery', t), 'mystery');
}

// 9. matchesFilters / hasAnyFilter / filterCount: AND across groups, OR within a group; an empty
// filter set matches everything.
{
  const entry = { kind: 'article', level: 'B2', topic: 'Daily life' };
  const none = { level: new Set(), topic: new Set(), type: new Set() };
  assert.equal(hasAnyFilter(none), false);
  assert.equal(matchesFilters(entry, none), true);
  const levelOnly = { level: new Set(['B2']), topic: new Set(), type: new Set() };
  assert.equal(matchesFilters(entry, levelOnly), true);
  assert.equal(matchesFilters({ ...entry, level: 'A2' }, levelOnly), false);
  const levelOr = { level: new Set(['A2', 'B2']), topic: new Set(), type: new Set() };
  assert.equal(matchesFilters(entry, levelOr), true, 'multiple selections in one group are OR');
  const both = { level: new Set(['B2']), topic: new Set(['Travel']), type: new Set() };
  assert.equal(matchesFilters(entry, both), false, 'two different groups are AND - this entry fails the topic group');
  assert.equal(filterCount({ level: new Set(['A2', 'B2']), topic: new Set(['Travel']), type: new Set() }), 3);
}

// 10. visibleEntries: tab + search query + filters, all three combined and all three live.
{
  const entries = [
    { id: 'article:1', kind: 'article', title: 'Why We Love Routines', author: '', level: 'B2', topic: 'Daily life' },
    { id: 'book:2', kind: 'book', title: 'The Slow Commute', author: 'M. Okafor', level: '', topic: '' },
    { id: 'media:3', kind: 'media', mediaType: 'video', title: 'Sunday Market Haul', author: 'Street Kitchen', level: 'B2', topic: 'Food' },
  ];
  assert.equal(visibleEntries(entries, { tab: 'all' }).length, 3);
  assert.equal(visibleEntries(entries, { tab: 'read' }).length, 2, 'article + book both bucket into "read"');
  assert.equal(visibleEntries(entries, { tab: 'listen' }).length, 1);
  assert.equal(visibleEntries(entries, { tab: 'all', query: 'okafor' }).length, 1, 'the query matches the author too, case-insensitively');
  assert.equal(visibleEntries(entries, { tab: 'all', filters: { level: new Set(['B2']), topic: new Set(), type: new Set() } }).length, 2);
}

// 11. presentCard: the duration pill only appears when the entry actually carries the count it
// would be built from (rule 40) - a null field draws no pill rather than "0 min read"/"0:00".
{
  const noReadingTime = presentCard({ id: 'article:1', kind: 'article', title: 'x', readingSeconds: null, tags: [] }, t);
  assert.equal(noReadingTime.duration, '', 'no reading_time_seconds -> no duration pill');
  const withReadingTime = presentCard({ id: 'article:1', kind: 'article', title: 'x', readingSeconds: 100 }, t);
  assert.equal(withReadingTime.duration, '2 min read', 'rounds 100 seconds to the nearest minute');
  const withChapters = presentCard({ id: 'book:1', kind: 'book', title: 'x', chapterCount: 4 }, t);
  assert.equal(withChapters.duration, '4 chapters');
  const withClip = presentCard({ id: 'media:1', kind: 'media', mediaType: 'video', title: 'x', clipMs: 78000 }, t);
  assert.equal(withClip.duration, '1:18', 'a clip length renders as clock time, matching the design\'s own video example');
  const collection = presentCard({ id: 'collection:1', kind: 'collection', title: 'x', itemCount: 40 }, t);
  assert.equal(collection.meta, '40 words', 'a collection shows its real word count as meta');
  assert.equal(collection.duration, '40 items', 'the design\'s own script gives a collection both the meta line and a corner count badge in a different unit (P1, discover.review.md) - a collection with a real itemCount draws a non-empty duration pill too');
  const collectionNoCount = presentCard({ id: 'collection:2', kind: 'collection', title: 'x', itemCount: null }, t);
  assert.equal(collectionNoCount.duration, '', 'rule 40: no real itemCount draws no duration pill, never "0 items"');
  const started = presentCard({ id: 'article:1', kind: 'article', title: 'x', started: true, progressPct: 56 }, t);
  assert.ok(started.tags.some((tag) => tag.label === '56%' && tag.tone === 'good'), 'a started item carries its progress as a tag, in the design\'s own tone');
  const learnedCollection = presentCard({ id: 'collection:1', kind: 'collection', title: 'x', started: true, progressLearned: 10, progressTotal: 40 }, t);
  assert.ok(learnedCollection.tags.some((tag) => tag.label === '10 / 40 learned'), 'a collection\'s progress reads as a count, not a bare percent');

  // languages-5 / finding A: the card's title carries the entry's own real language (or '' for a
  // device-memory import, which has none) - screen.js wraps it with kit/lang.js's langSpan.
  assert.equal(presentCard({ id: 'article:1', kind: 'article', title: 'x', language: 'zh' }, t).titleLang, 'zh');
  assert.equal(presentCard({ id: 'text:1', kind: 'text', title: 'x' }, t).titleLang, '', 'a device-memory import carries no language field - left unmarked, never guessed');

  // P-06: a topic reaches a learner only when the vocabulary names it, in the interface language; any other
  // tag (internal, test, ungoverned) is dropped from the cards and the Filter Sheet.
  const known = presentCard({ id: 'article:1', kind: 'article', title: 'x', topic: 'Daily life' }, t);
  assert.ok(known.tags.some((tag) => tag.label === 'Daily life'), 'a known topic is a card tag, labelled by the copy table');
  const raw = presentCard({ id: 'article:1', kind: 'article', title: 'x', topic: 'sandbox-test' }, t);
  assert.ok(!raw.tags.some((tag) => /sandbox/.test(tag.label)), 'an internal tag never reaches a card');
  assert.deepEqual(filterOptions([{ kind: 'article', level: '', topic: 'sandbox-test' }, { kind: 'article', level: '', topic: 'culture' }, { kind: 'article', level: '', topic: 'daily-life' }]).topic, ['culture', 'daily-life'], 'the Filter Sheet lists only known topics');
  assert.equal(topicKey('Daily life'), 'daily_life');
  assert.equal(topicKey('sandbox-test'), '');
  assert.equal(topicLabel('culture', t), 'Culture');
  // P-03: a card with no cover carries the tile of its type.
  assert.equal(presentCard({ id: 'article:1', kind: 'article', title: 'x' }, t).cover.icon, 'book-open');
  assert.equal(presentCard({ id: 'media:1', kind: 'media', mediaType: 'audio', title: 'x' }, t).cover.icon, 'headphones');
}

// 12. hrefFor: every kind but a collection opens Content Detail by its content id; a collection
// opens its own detail route by the raw id alone.
{
  assert.equal(hrefFor({ id: 'article:1', kind: 'article' }, href), '#/content/article:1');
  assert.equal(hrefFor({ id: 'collection:9', kind: 'collection' }, href), '#/collection/9');
}

console.log('Orena Discover: data mapping, filters, tabs, search and presentation all pure, no invented data: PASS');
