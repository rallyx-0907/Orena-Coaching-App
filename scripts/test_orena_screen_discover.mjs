/* Gate for Discover's data mapping and filtering (Design Contract rules 40, 42; frame
   04-Discover.html, 52-Filter-Sheet.html). screens/discover/model.js is DOM-free - imported
   directly, no globals to stub. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
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
  assert.equal(progressFromContinuation([{ id: 'article:1', place: { index: 2, total: 4 } }], 'article:1'), 25, 'exact-id match: item 2 of 4 means one whole item behind it (LEX-082)');
  assert.equal(progressFromContinuation([{ id: 'article:1', place: { index: 1, total: 1 } }], 'article:1'), null, 'a 1 of 1 place with nothing measured is not 100% (LEX-082)');
  assert.equal(progressFromContinuation([{ id: 'media:1', place: { index: 1, total: 1, within: 2 } }], 'media:1'), 2, 'a flat place reports how far in the learner is, never its 1/1 pair');
  assert.equal(progressFromContinuation([{ id: 'book:9:ch2', place: { index: 3, total: 3 } }], 'book:9', { idPrefix: 'book:9:' }), 67, 'prefix match finds a chapter row (chapter 3 of 3 opened: two behind it)');
  assert.equal(progressFromContinuation([{ id: 'book:9:ch2', place: { index: 3, total: 3 } }], 'book:9', { idPrefix: 'book:10:' }), null, 'prefix match is exact to the book id, not a substring of another book');
}

// 2. entryFromArticle: id shape, real fields carried, no image/author field the source has none
// of, progress read from continuation.
{
  const entry = entryFromArticle(
    { id: 'a1', title: 'Why We Love Routines', level: 'B2', topic: 'Daily life', reading_time_seconds: 340 },
    [{ id: 'article:a1', place: { index: 1, total: 1, within: 100 } }],
  );
  assert.equal(entry.id, 'article:a1');
  assert.equal(entry.kind, 'article');
  assert.equal(entry.author, '', 'no source/publication field exists for an article - left out, not invented');
  assert.equal(entry.image, '', 'no image field exists for an article');
  assert.equal(entry.readingSeconds, 340);
  assert.equal(entry.started, true);
  assert.equal(entry.progressPct, 100);
  assert.equal(entry.language, '', 'no language field on this fixture - never invented');
  // D-194: the approved same-origin picture reaches the card; any other address, or none, draws the tile.
  const picture = { url: '/api/reading/articles/0a52e5d0-0000-4000-8000-000000000001/image?v=2', credit: 'Photo: A', alt: '' };
  assert.equal(entryFromArticle({ id: 'a1', title: 'x', image: picture }, []).image, `url("${picture.url}")`);
  assert.equal(entryFromArticle({ id: 'a1', title: 'x', image: { ...picture, url: 'https://cdn.example.org/a.jpg' } }, []).image, '', 'a third-party address is never drawn');
  assert.equal(entryFromArticle({ id: 'a1', title: 'x', image: null }, []).image, '');
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
  assert.equal(started.progressPct, 38, 'chapter 4 of 8 opened: three chapters behind it');
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

// 13. The All tab is a sectioned overview (D-167): Listen - Watch, Read, Collections, Imported (the skill
// order, D-152), each the first OVERVIEW_LIMIT entries of its own tab with a "See all" that opens that tab;
// Imported is always drawn, as an import call to action while nothing is imported.
{
  const { overviewSections, OVERVIEW_TABS, OVERVIEW_LIMIT, TABS } = await import('../static/orena/screens/discover/model.js');
  const { overviewMarkup } = await import('../static/orena/screens/discover/overview.js');
  const { mediaCard } = await import('../static/orena/kit/components.js');
  const { registeredCopy } = await import('../static/orena/copy/index.js');
  await import('../static/orena/screens/discover/copy.js');
  const packs = registeredCopy().get('discover').packs;

  assert.deepEqual(OVERVIEW_TABS, ['listen', 'read', 'collections', 'imported'], 'the skill order (D-152): Listen before Read');
  assert.deepEqual(TABS, ['all', ...OVERVIEW_TABS], 'the tab bar and the overview sections share one order');
  for (const tab of OVERVIEW_TABS) assert.ok(TABS.includes(tab), `${tab} is a real tab, so its "See all" has somewhere to go`);
  assert.ok(OVERVIEW_LIMIT >= 4 && OVERVIEW_LIMIT <= 6, 'a few representative items, one row');

  const many = (n, make) => Array.from({ length: n }, (_, i) => make(i));
  const entries = [
    ...many(7, (i) => ({ id: `article:a${i}`, kind: 'article', title: `Article ${i}`, author: '', level: i % 2 ? 'B2' : 'A2', topic: '' })),
    ...many(3, (i) => ({ id: `book:b${i}`, kind: 'book', title: `Book ${i}`, author: 'Author', level: '', topic: '' })),
    ...many(8, (i) => ({ id: `media:m${i}`, kind: 'media', mediaType: i % 2 ? 'video' : 'audio', title: `Clip ${i}`, author: 'Src', level: '', topic: '' })),
    ...many(2, (i) => ({ id: `collection:c${i}`, kind: 'collection', title: `Words ${i}`, level: '', topic: '', itemCount: 10 })),
    { id: 'text:t0', kind: 'text', title: 'My text', author: '', level: '', topic: '' },
    { id: 'upload:u0', kind: 'upload', title: 'My upload', author: 'host', level: '', topic: '' },
  ];
  const sections = overviewSections(entries);
  assert.deepEqual(sections.map((section) => section.tab), OVERVIEW_TABS, 'four sections, in order');
  const KINDS = { read: ['article', 'book'], listen: ['media'], collections: ['collection'], imported: ['text', 'upload'] };
  for (const section of sections) {
    assert.ok(section.entries.length <= OVERVIEW_LIMIT, `${section.tab}: at most ${OVERVIEW_LIMIT} items`);
    assert.ok(section.entries.every((entry) => KINDS[section.tab].includes(entry.kind)), `${section.tab}: only its own type`);
    // Representative items are the tab's own first N, in the tab's own order.
    assert.deepEqual(section.entries, visibleEntries(entries, { tab: section.tab }).slice(0, OVERVIEW_LIMIT), `${section.tab}: the tab's own first items`);
    assert.equal(section.total, visibleEntries(entries, { tab: section.tab }).length, `${section.tab}: total is the tab's full count`);
  }
  assert.equal(sections[0].entries.length, OVERVIEW_LIMIT);
  assert.equal(sections[0].total, 8);
  assert.equal(sections[1].total, 10, 'Read is articles then books, exactly as the Read tab lists them');
  assert.equal(sections[3].entries.length, 2);

  // An empty section is left out (the design draws no empty state for a section) - Imported too: the design's way
  // to import is the Create lesson card above the page (2026-10-15 pin; owner, 2026-10-19), never a section's own CTA.
  const noImports = overviewSections(entries.filter((entry) => entry.kind !== 'text' && entry.kind !== 'upload'));
  assert.deepEqual(noImports.map((section) => section.tab), ['listen', 'read', 'collections'], 'with nothing imported, Imported is left out like any empty section');
  assert.ok(noImports.every((section) => !('empty' in section)), 'no section carries an import call to action');
  assert.deepEqual(overviewSections([]), [], 'a new learner with nothing loaded gets no sections (the page draws its empty state)');
  assert.deepEqual(overviewSections(entries.filter((entry) => entry.kind === 'media')).map((section) => section.tab), ['listen'], 'a source that failed leaves only its own section out');

  // Search and filters narrow every section alike; a narrowed page is not an invitation to import.
  assert.deepEqual(overviewSections(entries, { query: 'clip 3' }).map((section) => [section.tab, section.total]), [['listen', 1]]);
  assert.deepEqual(overviewSections(entries.filter((entry) => entry.kind !== 'text' && entry.kind !== 'upload'), { query: 'zzz' }), [], 'nothing matches a search: no sections');
  const b2 = overviewSections(entries, { filters: { level: new Set(['B2']), topic: new Set(), type: new Set() } });
  assert.deepEqual(b2.map((section) => section.tab), ['read'], 'a Level filter keeps only sections that still have a match');

  // Rendered, in each interface language: section headings are the tabs' own labels, each section has one
  // "See all" aimed at its tab, and the cards open where the type's own tab opens them.
  for (const ui of ['en', 'vi', 'zh']) {
    const pack = packs[ui];
    for (const key of ['seeAll', 'tabRead', 'tabListen', 'tabCollections', 'tabImported']) assert.ok(pack[key], `${ui}: ${key}`);
    for (const key of ['importCta', 'importAction']) assert.equal(pack[key], undefined, `${ui}: the old import call to action's words are gone (${key})`);
    const tr = (key, params) => fill(pack[key] ?? key, params);
    tr.plural = (key, n, params = {}) => fill(pack[`${key}_${n === 1 ? 'one' : 'other'}`] ?? pack[`${key}_other`] ?? key, { n, ...params });
    const card = (entry) => {
      const presented = presentCard(entry, tr);
      return mediaCard({ ...presented, title: presented.title, fullTitle: presented.title, dataset: { go: hrefFor(entry, href) } });
    };
    const markup = String(overviewMarkup(sections, { card, t: tr }));
    const found = [...markup.matchAll(/<section class="s-discover__section" data-section="(\w+)">([\s\S]*?)<\/section>/g)];
    assert.deepEqual(found.map((match) => match[1]), OVERVIEW_TABS, `${ui}: four sections in order`);
    const headings = [...markup.matchAll(/<h2 class="c-section-head__title">([^<]+)<\/h2>/g)].map((match) => match[1]);
    assert.deepEqual(headings, [pack.tabListen, pack.tabRead, pack.tabCollections, pack.tabImported], `${ui}: each heading is its tab's own label`);
    for (const [, tab, body] of found) {
      assert.equal([...body.matchAll(/data-see-all="(\w+)"/g)].map((match) => match[1]).join(), tab, `${ui}: ${tab} has one See all, aimed at the ${tab} tab`);
      assert.ok(body.includes(`${pack.seeAll}</button>`), `${ui}: See all is worded in the interface language`);
      const cards = [...body.matchAll(/class="o-card o-card--hover c-media" data-go="([^"]+)"/g)].map((match) => match[1]);
      assert.ok(cards.length >= 1 && cards.length <= OVERVIEW_LIMIT, `${ui}: ${tab} draws 1-${OVERVIEW_LIMIT} cards`);
    }
    assert.ok(found[2][2].includes('data-go="#/collection/c0"'), `${ui}: a collection card opens the collection route`);
    assert.ok(found[1][2].includes('data-go="#/content/article:a0"'), `${ui}: Read opens its articles`);

    // With nothing imported, the overview is the three other sections and draws no import control.
    const bare = String(overviewMarkup(noImports, { card, t: tr }));
    assert.deepEqual([...bare.matchAll(/data-section="(\w+)"/g)].map((match) => match[1]), ['listen', 'read', 'collections'], `${ui}: Imported is left out with nothing imported`);
    assert.ok(!/data-import|o-btn--vip|s-discover__importcta/.test(bare), `${ui}: no import control in the overview`);
  }

  // Import has one way in, the one the design draws: Discover's Create lesson card (2026-10-15 pin). The old entries -
  // Discover's header "+ Import" and its Imported call to action, Today's featured import card, My Library's header
  // "+ Import" (D-167 7-8) - and their VIP rainbow control are deleted (owner, 2026-10-19; Design Contract rule 44).
  {
    const read = (file) => fs.readFileSync(file, 'utf8');
    const OLD = /vipButton|o-btn--vip|vip-angle|o-vip-run|data-import\b|data-import-cta|importMarkup|s-today-import|s-discover__importcta|importAction|importValue|importCta/;
    for (const file of [
      'static/orena/kit/components.js', 'static/orena/kit/components.css', 'static/orena/kit/kit.css',
      'static/orena/screens/today/screen.js', 'static/orena/screens/today/today.css', 'static/orena/screens/today/copy.js',
      'static/orena/screens/library/screen.js', 'static/orena/screens/library/library.css',
      'static/orena/screens/discover/screen.js', 'static/orena/screens/discover/overview.js', 'static/orena/screens/discover/discover.css',
      'static/orena/screens/discover/copy.js', 'static/orena/copy/shell.js', 'static/orena/shell/frame.js',
    ]) assert.ok(!OLD.test(read(file)), `${file}: no old import entry, control or its words`);
    const { vipButton } = await import('../static/orena/kit/components.js');
    assert.equal(vipButton, undefined, 'the kit VIP import control is deleted, not left unused');
    for (const file of ['static/orena/screens/today/screen.js', 'static/orena/screens/library/screen.js']) {
      assert.ok(!/import\/open\.js|openImportFlow/.test(read(file)), `${file}: does not open Import (the design draws no import entry there)`);
    }
    // The only callers of the shared opener are Discover (the Create lesson card) and the import sheet's own module.
    const openers = [];
    const walk = (dir) => {
      for (const name of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = `${dir}/${name.name}`;
        if (name.isDirectory()) walk(full);
        else if (full.endsWith('.js') && /from '[^']*import\/open\.js'/.test(read(full))) openers.push(full);
      }
    };
    walk('static/orena');
    assert.deepEqual(openers, ['static/orena/screens/discover/screen.js'], 'Discover is the one screen that opens Import');
    assert.match(read('static/orena/screens/import/open.js'), /import\('\.\/sheet\.js'\)[\s\S]*module\.openImport\(ctx, options\)/, 'the shared opener opens the one import sheet');
    await import('../static/orena/copy/shell.js');
    await import('../static/orena/screens/today/copy.js');
    for (const ui of ['en', 'vi', 'zh']) {
      assert.equal(registeredCopy().get('shell').packs[ui].importAction, undefined, `${ui}: the old shared "+ Import" label is gone`);
      assert.equal(registeredCopy().get('today').packs[ui].importValue, undefined, `${ui}: Today's old import line is gone`);
    }
  }

  // The screen wires All to the overview and nothing else: the other tabs and the practice chooser keep the flat grid,
  // and a section's "See all" is the tab bar's own switch.
  const screenSource = fs.readFileSync('static/orena/screens/discover/screen.js', 'utf8');
  assert.match(screenSource, /const overview = !practice && state\.tab === 'all'/, 'only All, and never a practice chooser, is the overview');
  assert.match(screenSource, /openTab\(button\.dataset\.seeAll\)/, 'See all opens the tab through the same openTab the tab bar uses');
  assert.match(screenSource, /button\.addEventListener\('click', \(\) => openTab\(button\.dataset\.tab\)\)/, 'the tab bar keeps its own switch');
  assert.match(screenSource, /TAB_LABEL_KEY = \{ all: 'tabAll', listen: 'tabListen', read: 'tabRead', collections: 'tabCollections', imported: 'tabImported' \}/, 'the tab bar runs in the skill order (D-152)');
  assert.match(screenSource, /mountCreateLesson\(lessonHost, \{ t, language, tabs: lessonTabsFor\(practice\), open: \(initial\) => openImportFlow\(initial\) \}\)/, 'the Create lesson card opens the import flow with what was entered');
  assert.ok(!/data-import-cta/.test(screenSource), 'the Imported call to action is not wired: it is deleted');
  assert.match(screenSource, /if \(!list\.length && !state\.loading\) \{/, 'an empty All draws the page empty state like any tab (no always-drawn Imported)');
}

// The learner's place is the address, so Back from a collection (or a card) restores the tab, search and filters.
{
  const { readPlace, writePlace } = await import('../static/orena/screens/discover/model.js');
  const tabs = ['all', 'listen', 'read', 'collections', 'imported'];
  const filters = { level: new Set(['C2']), topic: new Set(), type: new Set(['collection', 'article']) };
  const qs = writePlace(new URLSearchParams(), { tab: 'collections', query: ' steadfast ', filters });
  const back = readPlace(new URLSearchParams(qs), tabs);
  assert.equal(back.tab, 'collections');
  assert.equal(back.query, 'steadfast');
  assert.deepEqual([...back.filters.level], ['C2']);
  assert.deepEqual([...back.filters.type].sort(), ['article', 'collection']);
  assert.equal(writePlace(new URLSearchParams('practice=dictation&tab=read'), { tab: 'all', query: '', filters: { level: new Set(), topic: new Set(), type: new Set() } }), 'practice=dictation', 'All with nothing set is the bare address, and a parameter Discover does not own is kept');
  assert.equal(readPlace(new URLSearchParams('tab=nonsense'), tabs).tab, 'all');
  const src = fs.readFileSync('static/orena/screens/discover/screen.js', 'utf8');
  assert.match(src, /readPlace\(ctx\.query, TABS\)/, 'the screen opens on the place the address names');
  assert.equal((src.match(/keepPlace\(\)/g) || []).length >= 5, true, 'tab, filter, clear and search each write the address');
}

// A Discover search with no result says what the box searches and offers global search with the query.
{
  const { searchEverywhereHref } = await import('../static/orena/screens/discover/model.js');
  const href = (route, params, query) => `#/${route}?${new URLSearchParams(query)}`;
  assert.equal(searchEverywhereHref(' 勇敢 ', href), '#/search?q=%E5%8B%87%E6%95%A2');
  const { default: copyApi } = await import('../static/orena/screens/discover/copy.js').catch(() => ({}));
  const copySrc = fs.readFileSync('static/orena/screens/discover/copy.js', 'utf8');
  for (const lang of ['en', 'vi', 'zh']) assert.equal((copySrc.match(/emptySearchText:/g) || []).length, 3, lang);
  assert.equal((copySrc.match(/searchEverywhere:/g) || []).length, 3);
  const src = fs.readFileSync('static/orena/screens/discover/screen.js', 'utf8');
  assert.match(src, /t\('emptySearchText'\)[\s\S]*t\('searchEverywhere'\)/);
  assert.match(src, /ctx\.go\(searchEverywhereHref\(typed, ctx\.href\)\)/);
}

// The "Create lesson" card (design 2026-10-15): four kinds, one field each, three hint chips, EN/VI/ZH words, tokens only.
{
  const { createLessonMarkup, LESSON_TABS, LESSON_HINTS } = await import('../static/orena/screens/discover/create-lesson.js');
  const { registeredCopy } = await import('../static/orena/copy/index.js');
  await import('../static/orena/screens/discover/copy.js');
  const packs = registeredCopy().get('discover').packs;
  const { ICONS } = await import('../static/orena/kit/icons.js');
  assert.deepEqual(LESSON_TABS.map((tab) => tab.id), ['link', 'text', 'file', 'audio'], 'the design\'s four kinds, in its order');
  for (const tab of LESSON_TABS) assert.ok(ICONS[tab.icon], `${tab.id}: a Lucide icon from the pinned package`);
  for (const hints of Object.values(LESSON_HINTS)) {
    assert.equal(hints.length, 3, 'three hint chips per kind');
    for (const hint of hints) {
      assert.ok(ICONS[hint.icon], `hint icon ${hint.icon} is a Lucide icon`);
      assert.match(hint.tone, /^(skill-[a-z]+|gcat-\d)$/, 'a hint hue is a tokens.css token');
    }
  }
  for (const ui of ['en', 'vi', 'zh']) {
    const pack = packs[ui];
    const t = (key) => pack[key];
    for (const tab of LESSON_TABS) {
      const markup = String(createLessonMarkup({ tab: tab.id, url: '', text: '' }, { t, language: ui === 'zh' ? 'zh' : 'en' }));
      assert.match(markup, /role="tablist"/, `${ui}/${tab.id}: a tablist`);
      assert.equal((markup.match(/role="tab"/g) || []).length, 4, `${ui}/${tab.id}: four tabs`);
      assert.equal((markup.match(/aria-selected="true"/g) || []).length, 1, `${ui}/${tab.id}: one selected`);
      assert.equal((markup.match(/class="s-ic__hint"/g) || []).length, 3, `${ui}/${tab.id}: three hints`);
      assert.match(markup, /data-lesson-create/);
      assert.ok(markup.includes(pack.lessonCreate) && markup.includes(pack.lessonTitle), `${ui}/${tab.id}: title and Create in the learner's language`);
      assert.ok(!/undefined/.test(markup), `${ui}/${tab.id}: no missing word`);
    }
    for (const key of ['lessonTitle', 'lessonSub', 'lessonCreate', 'lessonLinkPlaceholder', 'lessonTextPlaceholder', 'lessonDropFile', 'lessonDropAudio', 'lessonLinkFirst', 'lessonTextFirst', 'lessonDocumentSoon', 'lessonHintWebsite', 'lessonHintArticle', 'lessonHintEmail', 'lessonHintNotes', 'lessonHintPodcast', 'lessonTabLink', 'lessonTabText', 'lessonTabFile', 'lessonTabAudio']) assert.ok(pack[key], `${ui}: ${key}`);
  }
  assert.notEqual(packs.en.lessonTitle, packs.vi.lessonTitle);
  assert.notEqual(packs.en.lessonTitle, packs.zh.lessonTitle);
  const t = (key) => packs.en[key];
  assert.match(String(createLessonMarkup({ tab: 'link', url: 'https://x.test/a"b', text: '' }, { t, language: 'en' })), /value="https:\/\/x\.test\/a&quot;b"/, 'what the learner typed is escaped');
  assert.match(String(createLessonMarkup({ tab: 'text', url: '', text: '<b>x</b>' }, { t, language: 'en' })), /&lt;b&gt;x&lt;\/b&gt;<\/textarea>/, 'pasted text is escaped');
  const css = fs.readFileSync('static/orena/screens/discover/discover.css', 'utf8');
  const card = css.slice(css.indexOf('/* ---- The "Create lesson" card'));
  assert.equal(card.replace(/\/\*[\s\S]*?\*\//g, '').match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/), null, 'the card takes every colour from tokens.css');
  assert.match(card, /@container \(max-width: 560px\)\s*\{\s*\.s-ic__tabs \{ --ic-cols: 2; \}/, 'two columns of tabs under a 560px card');
  assert.ok(!/border:\s*1(\.5)?px (solid|dashed)(?! transparent)/.test(card.replace(/border:\s*1\.5px solid transparent/g, '')), 'no grey or violet outline (D-147)');
  // D-147 / design review: focus is the app's field pattern (border-color + --sh2), never a box-shadow ring.
  for (const selector of ['.s-ic__field:focus-within', '.s-ic__text:focus', '.s-ic__drop:focus-visible']) {
    const body = card.split('}').filter((rule) => rule.includes(selector)).join(' ');
    assert.ok(!/box-shadow:\s*0 0 0/.test(body), `${selector}: no box-shadow ring`);
  }
  assert.match(card, /\.s-ic__field:focus-within,\s*\.s-ic__text:focus\s*\{[^}]*border-color:\s*var\(--text3\);[^}]*box-shadow:\s*var\(--sh2\)/, 'the field focus pattern of the Import sheet');
  const decls = card.replace(/\/\*[\s\S]*?\*\//g, '').match(/:[^;{}]*;/g) || [];
  assert.deepEqual(decls.filter((d) => /\b(white|black|red|green|blue|gray|grey|orange|yellow|purple|pink|silver|gold)\b/.test(d.replace(/var\([^)]*\)/g, ''))), [], 'no named colour keyword in the card (tokens only)');
  // The solid card is a solid surface for the backdrop's text tokens (design review P1-2).
  const { surfaceSelectors } = await import('./build_backdrop_surfaces.mjs');
  assert.ok(surfaceSelectors().includes('.s-ic'), '.s-ic is in the solid-surface list');
  assert.match(fs.readFileSync('static/orena/shell/surfaces.css', 'utf8'), /^ {2}\.s-ic(,|$)/m, 'and in the generated surfaces.css');
  // Tabs pattern (WAI-ARIA): label, roving tabindex, aria-controls/tabpanel, arrow keys.
  const { nextLessonTab, isAcceptedLessonFile } = await import('../static/orena/screens/discover/create-lesson.js');
  assert.deepEqual(['ArrowRight', 'ArrowLeft', 'Home', 'End'].map((key) => nextLessonTab('link', key)), ['text', 'audio', 'link', 'audio'], 'arrows wrap, Home/End jump');
  assert.equal(nextLessonTab('audio', 'ArrowRight'), 'link');
  assert.equal(nextLessonTab('text', 'x'), null);
  const a11y = String(createLessonMarkup({ tab: 'file', url: '', text: '' }, { t, language: 'en' }));
  assert.match(a11y, /role="tablist" aria-label="Content type"/, 'the tablist is labelled');
  assert.equal((a11y.match(/tabindex="0"/g) || []).length >= 1 && (a11y.match(/role="tab"[^>]*tabindex="-1"/g) || []).length, 3, 'roving tabindex: three tabs at -1');
  assert.match(a11y, /id="s-ic-tab-file"[^>]*tabindex="0"|tabindex="0"[^>]*id="s-ic-tab-file"/, 'the selected tab is the tab stop');
  assert.match(a11y, /role="tabpanel" id="s-ic-panel" aria-labelledby="s-ic-tab-file"/, 'a tabpanel named by the selected tab');
  assert.equal((a11y.match(/aria-controls="s-ic-panel"/g) || []).length, 4, 'every tab controls the panel');
  assert.match(fs.readFileSync('static/orena/screens/discover/create-lesson.js', 'utf8'), /'file', labelKey: 'lessonTabFile', icon: 'file-minus'|id: 'file', labelKey: 'lessonTabFile', icon: 'file-minus'/, 'Document draws Lucide file-minus, as the design does');
  assert.ok(ICONS['file-minus']);
  // A dropped file passes the picker's own accept (audio/*, video/*).
  assert.equal(isAcceptedLessonFile({ type: 'audio/mpeg' }), true);
  assert.equal(isAcceptedLessonFile({ type: 'video/mp4' }), true);
  assert.equal(isAcceptedLessonFile({ type: 'application/pdf' }), false);
  assert.equal(isAcceptedLessonFile(null), false);
  // The card is Discover's alone: not in the practice choosers.
  assert.match(fs.readFileSync('static/orena/screens/discover/screen.js', 'utf8'), /<div data-lesson-host><\/div>/, 'the card is drawn on Discover and in its practice choosers');
  assert.match(fs.readFileSync('static/orena/screens/discover/screen.js', 'utf8'), /tabs: lessonTabsFor\(practice\)/, 'the chooser selects the kinds');
  // Owner decision on CL-7: a practice chooser offers only the kinds that practice can use; plain Discover keeps all four.
  const { lessonTabsFor } = await import('../static/orena/screens/discover/create-lesson.js');
  assert.deepEqual(lessonTabsFor(''), ['link', 'text', 'file', 'audio'], 'plain Discover: four kinds');
  assert.deepEqual(lessonTabsFor('nonsense'), ['link', 'text', 'file', 'audio']);
  for (const practice of ['listening', 'dictation', 'shadowing', 'pronunciation']) assert.deepEqual(lessonTabsFor(practice), ['link', 'audio'], `${practice}: link / video and audio only`);
  for (const ui of ['en', 'vi', 'zh']) {
    const two = String(createLessonMarkup({ tab: 'link', url: '', text: '' }, { t: (key) => packs[ui][key], language: 'en', tabs: ['link', 'audio'] }));
    assert.equal((two.match(/role="tab"/g) || []).length, 2, `${ui}: two tabs in a chooser`);
    assert.match(two, /--ic-cols:2/, `${ui}: the track lays out in two columns`);
    assert.equal((two.match(/class="s-ic__hint"/g) || []).length, 3, `${ui}: hints follow the visible tab`);
    assert.ok(!two.includes('data-lesson-tab="text"') && !two.includes('data-lesson-tab="file"'), `${ui}: no text or document tab in a chooser`);
  }
  assert.ok(!/--ic-cols:/.test(String(createLessonMarkup({ tab: 'link', url: '', text: '' }, { t, language: 'en' }))), 'four tabs keep the design\'s own 4 / 2 columns');
  assert.deepEqual(['ArrowRight', 'End', 'ArrowLeft'].map((key) => nextLessonTab('link', key, ['link', 'audio'])), ['audio', 'audio', 'audio'], 'arrows wrap inside the visible tabs');
  const sheet = fs.readFileSync('static/orena/screens/import/sheet.js', 'utf8');
  assert.match(sheet, /initial\.source === 'file'[\s\S]*initial\.source === 'text'[\s\S]*initial\.source === 'url'/, 'the sheet starts from what the card entered');
}

console.log('Orena Discover: data mapping, filters, tabs, search and presentation all pure, no invented data: PASS');
