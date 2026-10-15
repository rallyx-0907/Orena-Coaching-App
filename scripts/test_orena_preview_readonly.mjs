/* The administrator's preview of a held item is read-only (D-210).

   `#/listening/preview:<id>` opens the real learner player on an item that is not published. It must make no call
   that stores learner state: no place, no practice or dictation attempt, no saved word, note, highlight, response or
   record of where a word was met. This gate drives the real request path with a stubbed `fetch` and counts. It also
   reads the Listening room, the line practice, the word sheet and the Vocabulary Focus for the controls and flags
   that keep the learner out of the way of a write. The server wall is pytest
   (tests/test_media_preview_readonly.py). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const calls = [];
globalThis.fetch = async (url, options = {}) => {
  calls.push({ method: String(options.method || 'GET').toUpperCase(), url: String(url) });
  return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({}), text: async () => '{}' };
};

const { api } = await import('../static/orena/infrastructure/api.js');
const { enterPreview, previewActive, isLearnerStateWrite } = await import('../static/orena/infrastructure/preview-mode.js');
const { sendPlace } = await import('../static/orena/product/continue-sync.js');
const { mediaRef } = await import('../static/orena/product/media-source.js');

/* --- Which address is a preview ------------------------------------------------------------------------ */
assert.equal(mediaRef('preview:held-one').kind, 'preview');
for (const other of ['held-one', 'upload:upload-abc', 'url:https://example.test/x']) assert.notEqual(mediaRef(other).kind, 'preview');

/* --- What counts as storing learner state -------------------------------------------------------------- */
const STATE = [
  ['PUT', '/api/continue/media%3Aheld-one'],
  ['POST', '/api/listening/progress'],
  ['POST', '/api/listening/shadowing-progress'],
  ['POST', '/api/library/vocabulary'],
  ['POST', '/api/library/vocabulary/restore'],
  ['POST', '/api/library/vocabulary/harbour/review'],
  ['POST', '/api/library/vocabulary/harbour/provenance'],
  ['DELETE', '/api/library/vocabulary/harbour'],
  ['POST', '/api/library/items'],
  ['POST', '/api/library/collections/c1/items'],
  ['PUT', '/api/annotations/media%3Aheld-one'],
  ['PUT', '/api/responses/react%3Aone'],
  ['POST', '/api/vocabulary/decks/d1/words'],
  ['POST', '/api/agent/turn'],
  ['POST', '/api/agent/voice/session'],
  ['POST', '/api/conversations/conversation%3Ax/turns'],
];
const NOT_STATE = [
  ['GET', '/api/listening/progress?asset_id=held-one'],
  ['GET', '/api/library/vocabulary?query=x'],
  ['GET', '/api/library/vocabulary/summary'],
  ['GET', '/api/annotations/media%3Aheld-one'],
  ['POST', '/api/dictionary/word-detail'],
  ['POST', '/api/dictionary/sentence-sheet'],
  ['POST', '/api/media/annotate'],
  ['POST', '/api/media/translate'],
  ['GET', '/api/media/admin/player/held-one'],
  ['GET', '/api/conversations/conversation%3Ax'],
];
for (const [method, url] of STATE) assert.equal(isLearnerStateWrite(method, url), true, `${method} ${url} stores learner state`);
for (const [method, url] of NOT_STATE) assert.equal(isLearnerStateWrite(method, url), false, `${method} ${url} does not`);

/* --- While a preview is open, no writer reaches the network -------------------------------------------- */
const writers = [
  ['saveListeningProgress', () => api.saveListeningProgress({ asset_id: 'held-one', segment_id: 's1' })],
  ['saveShadowingProgress', () => api.saveShadowingProgress({ asset_id: 'held-one', segment_id: 's1', completed_rounds: 1 })],
  ['saveLibraryVocabulary', () => api.saveLibraryVocabulary({ word: 'harbour' })],
  ['deleteLibraryVocabulary', () => api.deleteLibraryVocabulary('harbour')],
  ['restoreLibraryVocabulary', () => api.restoreLibraryVocabulary({ word: 'harbour' })],
  ['reviewLibraryVocabulary', () => api.reviewLibraryVocabulary('harbour', 'got_it')],
  ['attachProvenance', () => api.attachProvenance('harbour', { operationId: 'op-00000001', reason: 'from_listening' })],
  ['libraryKeep', () => api.libraryKeep({ kind: 'media', source_id: 'media:held-one' })],
  ['libraryCollectionAdd', () => api.libraryCollectionAdd('c1', 'i1')],
  ['saveAnnotations', () => api.saveAnnotations('media:held-one', { operationId: 'op-00000002', expectedVersion: 0 })],
  ['saveResponse', () => api.saveResponse('react:one', { operationId: 'op-00000003', expectedVersion: 0, mode: 'react' })],
  ['vocabularyDeckAdd', () => api.vocabularyDeckAdd('d1', 'harbour')],
];
const place = { id: 'media:held-one', title: 'Held', segment: 's1', intent: 'listening', place: { index: 1, total: 1, within: 20 } };

assert.equal(previewActive(), false, 'no preview is open at the start');
const release = enterPreview();
assert.equal(previewActive(), true);
for (const [name, call] of writers) {
  calls.length = 0;
  await assert.rejects(call(), (error) => error.category === 'preview_read_only' && error.status === 409, `${name} is refused in a preview`);
  assert.equal(calls.length, 0, `${name} made no network call in a preview`);
}
calls.length = 0;
await sendPlace(place, 1_000_000);
assert.equal(calls.length, 0, 'the continuation place is not sent from a preview');

/* Reads and lookups keep working: the preview is for looking. */
calls.length = 0;
await api.listeningProgress('held-one');
await api.libraryVocabulary({ query: 'harbour', limit: 5 });
assert.equal(calls.length, 2, 'a read is not a write');

/* --- Leaving the preview gives the writers back -------------------------------------------------------- */
release();
release(); // a second release is harmless
assert.equal(previewActive(), false);
for (const [name, call] of writers) {
  calls.length = 0;
  await call();
  assert.equal(calls.length, 1, `${name} writes again outside a preview`);
}
calls.length = 0;
await sendPlace({ ...place, id: 'media:published-one' }, 2_000_000);
assert.equal(calls.length, 1, 'a published item still keeps its place');

/* --- The room keeps the learner out of the way of a write ---------------------------------------------- */
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const room = read('static/orena/screens/listening/screen.js');
const practice = read('static/orena/screens/dictation/line-practice.js');
const wordSheet = read('static/orena/screens/quick-sheet/sheet.js');
const vocab = read('static/orena/screens/listening/vocab-sheet.js');

assert.match(room, /const preview = mediaRef\(lessonId\)\.kind === 'preview'/, 'the room knows it is a preview from the address');
assert.match(room, /if \(preview\) leavePreview = enterPreview\(\)/, 'a preview turns the request wall on');
assert.match(room, /leavePreview\(\);/, 'and turns it off when the room goes');
assert.match(room, /readOnly: preview,\s*\n\s*onCheck/, 'the line practice is read-only in a preview');
assert.match(room, /source: \{ kind: 'listening', content_id: routeId, segment: segId, title: lesson\.title \},\s*readOnly: preview/, 'the word sheet is read-only');
assert.match(room, /segment: id \},\s*readOnly: preview/, 'the Vocabulary Focus is read-only');
assert.match(room, /if \(preview\) return;\s*\n\s*try \{\s*\n\s*\/\* How far into the clip/, 'no place is remembered in a preview');
assert.match(room, /\$\{preview \? '' : html`<button[^`]*data-act="save-phrase"/, 'no Save phrase control is drawn in a preview');
assert.match(room, /async function togglePhrase\(seg\) \{\s*\n\s*if \(preview\) return;/, 'and the handler is closed too');
assert.match(room, /lesson\.modes\.shadowing && !preview/, 'no link into Shadowing, which saves, from a preview');
assert.match(room, /\$\{preview \? '' : pill\(\{ id: 'react'/, 'no link into React, which saves, from a preview');
assert.match(room, /\$\{preview \? '' : html`<button[^`]*data-act="respond"/, 'no link into Respond, which saves, from a preview');

assert.match(practice, /readOnly = false/, 'the line practice takes the flag');
assert.match(practice, /function saveDraft\(value\) \{\s*\n\s*if \(readOnly\) return;/, 'no draft is written');
assert.match(practice, /function readDraft\(\) \{\s*\n\s*if \(readOnly\) return '';/, 'no draft is read back');
assert.match(practice, /if \(readOnly\) return;\s*\n\s*evidence\.compare[\s\S]*await persist\(line, outgoing\)/, 'a checked attempt is not stored in a preview');

assert.match(wordSheet, /readOnly = false/, 'the word sheet takes the flag');
assert.match(wordSheet, /\$\{readOnly \? '' : html`<button[^`]*data-save\b/, 'no save icon in a preview');
assert.match(wordSheet, /\$\{readOnly \? '' : html`<div class="s-qs__actions">\s*<button[^`]*data-save-cta/, 'no save button in a preview');
assert.match(wordSheet, /loading \|\| readOnly \? ''/, 'no link to the word page, which saves, in a preview');
assert.match(wordSheet, /if \(busy \|\| readOnly\) return;/, 'and the save handler is closed too');

assert.match(vocab, /readOnly = false/, 'the Vocabulary Focus takes the flag');
assert.match(vocab, /\$\{readOnly \? '' : html`<button[^`]*s-vocab__save/, 'no Save in the Vocabulary Focus in a preview');
assert.match(vocab, /if \(!row \|\| readOnly\) return;/, 'and its handler is closed too');

/* No Orena conversation is opened from a preview (D-210): Explain and Ask deeper are not drawn. */
assert.match(room, /\$\{preview \? '' : html`<button[^`]*data-act="explain"/, 'no Explain in a preview');
assert.match(wordSheet, /\$\{readOnly \? '' : html`<div class="s-qs__actions">/, 'no Ask deeper (nor the save row) in a preview');
assert.match(wordSheet, /card\.whyHere && readOnly\) return html`<div class="s-qs__why">/, 'the "why here" row is text, not a way into Orena, in a preview');

/* An item unpublished while a learner is on it: the attempt is not kept, quietly (no note, no retry that cannot work). */
assert.match(practice, /error\?\.status === 404 && \/media_not_available\/[\s\S]{0,300}return;/, 'a 404 media_not_available ends the save without a note');

/* The preview entry page (Content Detail, `#/content/media:preview:<id>`) draws no Save and no "..." (D-210):
   hidden, not disabled, and nothing behind "..." that writes (Shadowing saves; Delete is the learner's own import). */
const content = read('static/orena/screens/content/screen.js');
assert.match(content, /const preview = kind === 'media' && mediaRef\(id\)\.kind === 'preview'/, 'the entry page knows it is a preview from the address');
assert.match(content, /\$\{preview \? '' : html`<button[^`]*data-save\b/, 'no Save control is drawn in a preview');
assert.match(content, /\[data-save\]'\)\?\.addEventListener\('click', async \(event\) => \{\s*\n\s*if \(preview\) return;/, 'and its handler is closed too');
assert.match(content, /detail\.canShadow && !preview/, 'no way into Shadowing, which saves, from a preview');
assert.match(content, /const hasMore = !preview && \(/, 'no "..." button in a preview');

console.log('preview read-only gate: ok');
