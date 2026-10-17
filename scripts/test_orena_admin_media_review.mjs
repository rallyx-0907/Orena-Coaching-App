import assert from 'node:assert/strict';
import { applyLifecycle } from '../static/orena/capabilities/admin-content.js';
import { mediaPage } from '../static/orena/screens/admin/content-pages.js';
import { en, vi, zh } from '../static/orena/screens/admin/copy-content.js';
const calls = [];
await applyLifecycle({ setMediaStatus: async (...args) => calls.push(args) }, 'media', 'M', 'publish');
assert.deepEqual(calls, [['M', 'published']]);
await applyLifecycle({ setMediaStatus: async (...args) => calls.push(args) }, 'media', 'M', 'restore');
assert.deepEqual(calls[1], ['M', 'unpublished'], 'Restore returns to reviewable shelf without publication');

const correction = {
  index: 0, start_ms: 1000, end_ms: 2500,
  before: 'Hello world', after: '<script>alert(1)</script>.',
  reason: 'restore punctuation', provider: 'groq', model: 'configured-text-model',
};
const detail = {
  record: {
    id: 'M', kind: 'media', origin: 'imported', title: 'Sample', subtitle: 'YouTube',
    language: 'en', status: 'review', actions: [], facts: { transcript: 'available', segment_count: 1 },
    processing: { state: 'held', transcript_corrections: [correction] },
  },
  source: { original_url: 'https://example.test/media' },
  transcript: { segments: [{ text: correction.after, start_ms: correction.start_ms, end_ms: correction.end_ms }] },
};
const page = String(mediaPage({ detail, view: { busy: false, error: '' }, t: (key) => key, ui: { locale: 'en' }, href: () => '#/admin' }).markup);
assert.ok(page.includes('Hello world'), 'A12 shows the source text for each changed cue');
assert.ok(page.includes('&lt;script&gt;'), 'A12 escapes correction text as plain text');
assert.ok(page.includes('configured-text-model'), 'A12 shows correction provenance');
for (const pack of [en, vi, zh]) {
  assert.equal(typeof pack.ctTranscriptCorrections, 'string', 'A12 correction label exists in EN, VI and ZH');
}
console.log('Admin media review Publish uses canonical status API: PASS');
