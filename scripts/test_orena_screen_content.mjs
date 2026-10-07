/* Gate for the Content Detail screen's DOM-free logic (design route `detail`, frame 05,
   static/orena/screens/content/model.js). Checks the id scheme every content-linking surface
   shares, rule-40 zero fallbacks (a field the backend did not measure is absent, never a
   fabricated placeholder), and the Related list's exclude/limit/drop-incomplete behaviour. */
import assert from 'node:assert/strict';

const {
  parseContentId,
  contentIdFor,
  minutesFrom,
  mmss,
  metaLine,
  libraryKindFor,
  primaryDestination,
  placeFor,
  mediaPlaceFor,
  segmentStarts,
  normalizeArticle,
  normalizeBook,
  normalizeMedia,
  normalizeText,
  pickRelated,
} = await import('../static/orena/screens/content/model.js');

// 1. The shared content-id scheme (article/book/media/upload/text; book carries an optional
// chapter; an id this screen does not recognise comes back with no kind, never a guess).
assert.deepEqual(parseContentId('article:abc-1'), { kind: 'article', id: 'abc-1' });
assert.deepEqual(parseContentId('book:b1'), { kind: 'book', id: 'b1', chapterId: '' });
assert.deepEqual(parseContentId('book:b1:c2'), { kind: 'book', id: 'b1', chapterId: 'c2' });
assert.deepEqual(parseContentId('media:m9'), { kind: 'media', id: 'm9' });
assert.deepEqual(parseContentId('upload:u3'), { kind: 'upload', id: 'u3' });
assert.deepEqual(parseContentId('text:t7'), { kind: 'text', id: 't7' });
assert.deepEqual(parseContentId('collection:c1'), { kind: '', id: '' }, 'a collection id is not this screen\'s to resolve');
assert.deepEqual(parseContentId('bogus'), { kind: '', id: '' });
assert.deepEqual(parseContentId(''), { kind: '', id: '' });
assert.equal(contentIdFor('article', 'abc-1'), 'article:abc-1');

// 2. Rule 40: minutes are absent (null) for anything that is not a real, finite, non-negative
// number - never a fabricated duration - and a real zero-length record stays a real zero.
assert.equal(minutesFrom(undefined), null);
assert.equal(minutesFrom(null), null);
assert.equal(minutesFrom(-4), null);
assert.equal(minutesFrom(Number.NaN), null);
assert.equal(minutesFrom(0), 0);
assert.equal(minutesFrom(30), 1, 'a nonzero duration under a minute still reads as 1 min, never 0');
assert.equal(minutesFrom(600), 10);
assert.equal(minutesFrom(90_000, { unitMs: true }), 2, 'ms durations divide down to seconds first');
assert.equal(mmss(44_000), '0:44');
assert.equal(mmss(75_000), '1:15');
assert.equal(mmss(undefined), null);
assert.equal(mmss(-1), null);

// 3. metaLine never leaves a stray separator for a missing part.
assert.equal(metaLine(['A', 'B1', 'C']), 'A · B1 · C');
assert.equal(metaLine(['A', '', 'C']), 'A · C');
assert.equal(metaLine(['', '', '']), '');

// 4. The server "kind" each content kind keeps under, or null for a device-memory-only import.
assert.equal(libraryKindFor('article'), 'reading');
assert.equal(libraryKindFor('book'), 'book');
assert.equal(libraryKindFor('media'), 'listening');
assert.equal(libraryKindFor('upload'), 'listening');
assert.equal(libraryKindFor('text'), null);

// 5. Primary CTA destination: reader for an id-carrying text source, listening for a bare media
// id - the harness's own routing rule, not the prototype's per-item demo branching.
assert.equal(primaryDestination('article'), 'reader');
assert.equal(primaryDestination('book'), 'reader');
assert.equal(primaryDestination('text'), 'reader');
assert.equal(primaryDestination('media'), 'listening');
assert.equal(primaryDestination('upload'), 'listening');

// 6. placeFor: started only with a real measured percent; an entry with a position but no
// percent, or no entry at all, is "not started" rather than an invented bar.
assert.deepEqual(placeFor([], 'article:x'), { started: false, percent: 0 });
assert.deepEqual(placeFor([{ id: 'article:x', place: { index: 2, total: 5 } }], 'article:x'), { started: false, percent: 0 }, 'a position with no percent shows no progress row');
assert.deepEqual(placeFor([{ id: 'article:x', place: { within: 61.6 } }], 'article:x'), { started: true, percent: 62 });
assert.deepEqual(placeFor([{ id: 'article:x', place: { within: 150 } }], 'article:x'), { started: true, percent: 100 }, 'clamped to 100');
assert.deepEqual(placeFor([{ id: 'other', place: { within: 50 } }], 'article:x'), { started: false, percent: 0 });

// 7. Article/book/media/text normalisation: real fields carried through, an absent field is ''
// or null, never a placeholder string or a guessed number.
// D-130: the description is the article's own metadata; the body is never presented as one.
assert.deepEqual(normalizeArticle({ title: 'Sông Hồng', attribution: { author: 'Báo X' }, level: 'B1', reading_time_seconds: 300, body: 'ngắn', description: 'Mô tả bài' }), {
  title: 'Sông Hồng', language: '', source: 'Báo X', level: 'B1', minutes: 5, desc: 'Mô tả bài', image: '',
});
assert.deepEqual(normalizeArticle({ title: 'No attribution', body: 'text' }), { title: 'No attribution', language: '', source: '', level: '', minutes: null, desc: '', image: '' });
// languages-5 / finding A: the article's own real language field
// (reading_content_repository.py's `_article` projection), carried through untranslated.
assert.equal(normalizeArticle({ title: 'x', body: '', language: 'zh' }).language, 'zh');
assert.equal(normalizeArticle({ title: 'Long', body: 'x'.repeat(400) }).desc, '', 'no description metadata: the block is hidden');

assert.deepEqual(normalizeBook({ id: 'b1', title: 'Truyện', author: 'Tác giả', description: 'Mô tả' }), {
  title: 'Truyện', language: '', source: 'Tác giả', level: '', minutes: null, desc: 'Mô tả', image: '',
});
// languages-5 / finding A: `learning_language`, a book's own field name (different from an
// article's `language`).
assert.equal(normalizeBook({ id: 'b1', title: 'T', learning_language: 'en' }).language, 'en');
assert.equal(
  normalizeBook({ id: 'b1', title: 'T', cover_asset_key: 'books/b1/cover.jpg' }).image,
  'url("/api/reading/library/books/b1/cover")',
);
assert.equal(normalizeBook({ id: 'b1', title: 'T' }).image, '', 'no cover asset key -> no fabricated image');

const media = normalizeMedia({
  catalog: { title: 'Bản tin', level: 'A2', duration_ms: 125_000, description: 'Mô tả nghe', source: { creator: 'Đài X' } },
  asset: { title: 'ignored, catalog wins', thumbnail_url: '', source_provider: '' },
  playback: { kind: 'audio' },
  transcript_origin: 'generated_asr',
  transcript: { segments: [{ start_ms: 0, original_text: 'Xin chào' }, { start_ms: 3000, original_text: '' }, { start_ms: NaN, original_text: 'dropped, bad time' }] },
});
assert.equal(media.title, 'Bản tin');
assert.equal(media.minutes, 2);
assert.equal(media.playbackKind, 'audio');
assert.equal(media.transcriptOrigin, 'generated_asr');
assert.deepEqual(media.segments, [{ time: '0:00', text: 'Xin chào' }], 'an empty text or an unreal timestamp is dropped, not shown blank');
assert.equal(media.language, '', 'this fixture carries neither catalog.language nor asset.source_language');
// languages-5 / finding A: `catalog.language` for a curated/shared lesson.
assert.equal(normalizeMedia({ catalog: { language: 'zh' }, asset: {} }).language, 'zh');
// ...else the asset's own `source_language`, for a learner's own upload (no `catalog` at all).
assert.equal(normalizeMedia({ asset: { source_language: 'en' } }).language, 'en');

const upload = normalizeMedia({ asset: { title: 'Học viên tự tải lên', duration_ms: null }, playback: { kind: 'video' }, transcript: null });
assert.deepEqual(upload, { title: 'Học viên tự tải lên', language: '', source: '', level: '', minutes: null, desc: '', image: '', playbackKind: 'video', transcriptOrigin: 'none', segments: [] });

const text = normalizeText({ title: 'Của tôi', text: 'ngắn' });
assert.deepEqual(text, { title: 'Của tôi', source: '', level: '', minutes: null, desc: 'ngắn', image: '' });

// 8. pickRelated: excludes the current item by its own raw id (before the caller's map renames
// it to a content route id), caps at the limit, and drops anything map could not title.
const rawItems = [
  { id: 'keep-me', title: 'Có tên' },
  { id: 'x', title: 'Hiện tại' },
  { id: 'no-title', title: '' },
  { id: 'also-keep', title: 'Khác' },
  { id: 'over-limit', title: 'Thừa' },
];
const related = pickRelated(rawItems, {
  excludeId: 'x',
  limit: 2,
  map: (item) => ({ id: `article:${item.id}`, title: item.title }),
});
assert.deepEqual(related, [{ id: 'article:keep-me', title: 'Có tên' }, { id: 'article:also-keep', title: 'Khác' }]);
assert.deepEqual(pickRelated(undefined, { excludeId: 'x', map: (i) => i }), []);
assert.deepEqual(
  pickRelated([{ lesson_id: 'x', title: 'Excluded by lesson_id' }, { lesson_id: 'm2', title: 'Kept' }], { excludeId: 'x', map: (item) => ({ id: item.lesson_id, title: item.title }) }),
  [{ id: 'm2', title: 'Kept' }],
);

// X-11: a media place carries a line, not a percent - it resumes at that line's start (the entry Today calls "Continue").
{
  const starts = segmentStarts({ transcript: { segments: [{ segment_id: 'm:1', start_ms: 0 }, { segment_id: 'm:2', start_ms: 44000 }, { segment_id: 'bad', start_ms: null }] } });
  assert.deepEqual(starts, { 'm:1': 0, 'm:2': 44000 });
  assert.deepEqual(mediaPlaceFor([{ id: 'media:a', segment: 'm:2' }], 'media:a', starts, 88000), { started: true, atMs: 44000, at: '0:44', percent: 50 });
  assert.deepEqual(mediaPlaceFor([{ id: 'media:a', segment: 'm:2' }], 'media:a', starts, null), { started: true, atMs: 44000, at: '0:44', percent: null }, 'no duration, no percent');
  assert.deepEqual(mediaPlaceFor([{ id: 'media:a', segment: 'gone' }], 'media:a', starts, 88000), { started: true, atMs: null, at: '', percent: null }, 'a place whose line is not in the transcript still continues, with no strip');
  assert.equal(mediaPlaceFor([], 'media:a', starts, 88000).started, false);
  assert.equal(mediaPlaceFor([{ id: 'media:b', segment: 'm:2' }], 'media:a', starts, 88000).started, false);
}

console.log('Orena Content Detail model: id scheme, rule-40 fallbacks, normalisation and related-list selection: PASS');
