/* Node gate for the two sheet screens' DOM-free logic (Design Contract rule 40: text stats, error
   mapping and membership records never invent a number, and a continuation entry this UI cannot
   route correctly is left out rather than guessed). Imports only the *-free modules, never sheet.js
   (which touches the DOM/overlay layer) or copy.js (covered by scripts/test_orena_copy.mjs). */
import assert from 'node:assert/strict';
import { textStats, countSentences, importErrorKey, urlMediaEntry } from '../static/orena/screens/import/model.js';
import { continuationRoute, notificationRows } from '../static/orena/screens/notifications/model.js';
import { isSupportedMediaUrl } from '../static/orena/product/media-url.js';

// ---- product/media-url.js (moved out of app.js, rule: pure logic moves, never copies) ----
assert.equal(isSupportedMediaUrl('https://www.youtube.com/watch?v=abcdefghijk'), true);
assert.equal(isSupportedMediaUrl('https://youtu.be/abcdefghijk'), true);
assert.equal(isSupportedMediaUrl('https://youtube.com/shorts/abcdefghijk'), true);
assert.equal(isSupportedMediaUrl('http://www.youtube.com/watch?v=abcdefghijk'), false, 'https only');
assert.equal(isSupportedMediaUrl('https://user:pass@www.youtube.com/watch?v=abcdefghijk'), false, 'no embedded credentials');
assert.equal(isSupportedMediaUrl('https://www.youtube.com:8080/watch?v=abcdefghijk'), false, 'no explicit port');
assert.equal(isSupportedMediaUrl('https://vimeo.com/12345'), false, 'unsupported host');
assert.equal(isSupportedMediaUrl('not a url'), false);

// ---- import/model.js: sentence/word/character stats, never a fabricated count ----
assert.deepEqual(textStats(''), { unit: 'words', count: 0, sentences: 0, tooShort: true });
const short = textStats('One sentence only.');
assert.equal(short.tooShort, true, 'fewer than two sentences is too short');
assert.equal(short.sentences, 1);
const enough = textStats('Two sentences. Right here.');
assert.equal(enough.tooShort, false);
assert.equal(enough.sentences, 2);
assert.equal(enough.unit, 'words');
assert.equal(enough.count, 4);
const zh = textStats('这是第一句。这是第二句！');
assert.equal(zh.unit, 'characters', 'mostly-Han text is counted in characters, not space-split words');
assert.equal(zh.sentences, 2);
assert.equal(zh.tooShort, false);
assert.equal(countSentences('No terminal punctuation here'), 1, 'content with no terminator is still one unfinished sentence');
assert.equal(countSentences(''), 0);

// ---- import/model.js: the backend's own failure categories, never an invented per-error message ----
assert.equal(importErrorKey('malformed_url'), 'error_malformed_url');
assert.equal(importErrorKey('media_unavailable'), 'error_media_unavailable');
assert.equal(importErrorKey('something_the_backend_never_sent'), 'error_generic');
assert.equal(importErrorKey(undefined), 'error_generic');
// The upload route's own categories are not mapped: the frame draws no File upload step (no
// `impIsFile` block; its own handler is a toast), so this screen never reaches that route.
assert.equal(importErrorKey('media_upload_invalid'), 'error_generic', 'the File step is not built - no upload category is recognised');

// ---- import/model.js: membership records only from fields the response actually returned ----
const urlEntry = urlMediaEntry('https://youtu.be/abcdefghijk', {
  asset: { title: 'A clip', source_type: 'external-video', duration_ms: 78000, thumbnail_url: 'https://img.example/x.jpg', source_provider: 'youtube' },
  playback: { kind: 'embed' },
});
assert.equal(urlEntry.id, 'url:https://youtu.be/abcdefghijk');
assert.equal(urlEntry.title, 'A clip');
assert.equal(urlEntry.kind, 'embed');
assert.equal(urlEntry.duration_ms, 78000);
assert.equal(urlEntry.provider, 'youtube');
const urlEntryNoTitle = urlMediaEntry('https://youtu.be/abcdefghijk', { asset: {} });
assert.equal(urlEntryNoTitle.title, 'https://youtu.be/abcdefghijk', 'no title in the response falls back to the url itself, never a made-up name');
assert.equal(urlEntryNoTitle.duration_ms, undefined, 'a missing duration is left out, never 0 or a guess');

// ---- notifications/model.js: only the ids this UI can route correctly become a row ----
assert.deepEqual(continuationRoute({ id: 'text:abc' }), { routeId: 'reader', kind: 'reading' });
assert.deepEqual(continuationRoute({ id: 'book:1/2' }), { routeId: 'reader', kind: 'reading' });
assert.deepEqual(continuationRoute({ id: 'url:https://x' }), { routeId: 'listening', kind: 'listening' });
assert.deepEqual(continuationRoute({ id: 'upload:m1' }), { routeId: 'listening', kind: 'listening' });
assert.deepEqual(continuationRoute({ id: 'expression:free' }), { routeId: 'writingDraft', kind: 'writing' });
assert.equal(continuationRoute({ id: 'voice:invitation' }), null, 'speaking has no 1:1 new-shell route yet - left out, not misrouted');
assert.equal(continuationRoute({ id: 'grammar:en_1' }), null);

const rows = notificationRows({
  due: 3,
  continuation: [
    { id: 'text:a', title: 'A text', place: { index: 1, total: 2, within: 40 } },
    { id: 'voice:x', title: 'Not routable' },
    { id: 'url:https://y', title: 'A video' },
  ],
});
assert.equal(rows.length, 3, 'the due row plus the two routable continuation entries; the speaking one is dropped');
assert.deepEqual(rows[0], { type: 'due', due: 3 });
assert.equal(rows[1].routeId, 'reader');
assert.equal(rows[1].percent, 40);
assert.equal(rows[2].routeId, 'listening');
assert.equal(rows[2].percent, null, 'no place recorded is left blank, never shown as 0%');

assert.deepEqual(notificationRows({ due: 0, continuation: [] }), [], 'no real signal at all: an empty row list, for the sheet to render its empty state');

const zeroPercentRows = notificationRows({ due: 0, continuation: [{ id: 'text:z', title: 'Just started', place: { index: 0, total: 2, within: 0 } }] });
assert.equal(zeroPercentRows[0].percent, 0, 'a real 0% is kept as the number 0, distinct from no place recorded (null)');

// languages-5 / finding A: sheet.js source checks (not imported as a module, per this gate's own
// rule above - read as plain text) confirming both sheets wire the shared kit/lang.js helper.
{
  const { readFileSync } = await import('node:fs');
  const importSrc = readFileSync(new URL('../static/orena/screens/import/sheet.js', import.meta.url), 'utf8');
  assert.match(importSrc, /import\s*\{\s*langAttr\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'Import sheet imports the shared lang helper');
  assert.match(importSrc, /<textarea[^>]*lang="\$\{langAttr\(context\.language\)\}"/, 'the pasted-text textarea carries a real lang attribute, matching the old text-import dialog\'s own behaviour');

  const notificationsSrc = readFileSync(new URL('../static/orena/screens/notifications/sheet.js', import.meta.url), 'utf8');
  assert.match(notificationsSrc, /import\s*\{\s*langSpan\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'Notifications sheet imports the shared lang helper');
  assert.match(notificationsSrc, /langSpan\(row\.title,\s*context\.language\)/, 'a continuation row\'s title is wrapped with the active learning language');
}

console.log('Orena screen sheets (Import, Notifications): media-url move, text stats, error mapping, membership records and continuation routing all pure and honest: PASS');
