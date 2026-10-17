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
/* Live-trial fixes: reason codes are translated copy in every language; deterministic edits never read "No change." */
const codes = ['rate_limited', 'spend_cap', 'correction_failed', 'correction_unavailable', 'provider_auth', 'provider_timeout',
  'provider_error', 'malformed_result', 'request_too_large', 'not_configured', 'corrector_unconfigured', 'unsupported_language',
  'empty_cue', 'lexemes_changed', 'edit_ratio_exceeded'];
for (const pack of [en, vi, zh]) {
  for (const code of codes) assert.equal(typeof pack[`ctCorrectionDetail_${code}`], 'string', `A12 detail copy ${code}`);
  for (const key of ['ctCorrectionState_unavailable', 'ctCorrectionState_failed', 'ctCorrectionState_partial', 'ctCorrectionNotApplied', 'ctCorrectionReason_noise_removed']) {
    assert.equal(typeof pack[key], 'string', `A12 copy ${key}`);
  }
}
assert.notEqual(en.ctCorrectionReason_noise_removed, 'No change.');
const speak = (pack) => Object.assign((key) => pack[key] ?? key, { has: (key) => key in pack });
const partial = {
  ...detail.record.processing,
  transcript_correction_state: 'partial', transcript_correction_detail: 'lexemes_changed',
  transcript_corrections: [
    { index: 0, start_ms: 1000, end_ms: 2500, before: '>> hello there', after: 'hello there', reason: '', reason_code: 'noise_removed', provider: '', model: '' },
    { index: 1, start_ms: 3000, end_ms: 4500, before: 'a b', after: 'A, b.', reason: 'restored punctuation', reason_code: 'model_edit', provider: 'groq', model: 'm' },
  ],
  transcript_correction_rejected: [{ index: 2, start_ms: 5000, code: 'edit_ratio_exceeded', before: 'x y', proposed: '<b>z</b>' }],
};
for (const [name, pack] of [['en', en], ['vi', vi], ['zh', zh]]) {
  const markup = String(mediaPage({ detail: { ...detail, record: { ...detail.record, processing: partial } }, view: { busy: false, error: '' }, t: speak(pack), ui: { locale: name }, href: () => '#/admin' }).markup);
  assert.ok(markup.includes(pack.ctCorrectionState_partial), `${name}: partial state is translated`);
  assert.ok(markup.includes(pack.ctCorrectionDetail_lexemes_changed), `${name}: reason code is translated`);
  assert.ok(markup.includes(pack.ctCorrectionReason_noise_removed), `${name}: deterministic edit has its own reason`);
  assert.ok(markup.includes(pack.ctCorrectionDetail_edit_ratio_exceeded) && markup.includes(`${pack.ctCorrectionNotApplied}: &lt;b&gt;z&lt;/b&gt;`), `${name}: a rejected cue is shown, escaped`);
  assert.ok(!markup.includes('No change.'), `${name}: never "No change." for a deterministic edit`);
}
/* Review P1: cleared rights + an unfinished correction is held, not failed; the operator is told why in every language. */
const { en: importsEn, vi: importsVi, zh: importsZh } = await import('../static/orena/screens/admin/copy-imports.js');
for (const [name, pack, importsPack] of [['en', en, importsEn], ['vi', vi, importsVi], ['zh', zh, importsZh]]) {
  assert.equal(typeof importsPack.impErr_transcript_correction_incomplete, 'string', `${name}: held-for-correction reason has copy`);
  const held = {
    ...detail.record, status: 'review',
    outcome: { state: 'held', reason: 'transcript_correction_incomplete', message: 'English fallback', detail: 'partial' },
    processing: { ...detail.record.processing, transcript_correction_state: 'partial' },
  };
  const merged = { ...pack, ...importsPack };
  const markup = String(mediaPage({ detail: { ...detail, record: held }, view: { busy: false, error: '' }, t: speak(merged), ui: { locale: name }, href: () => '#/admin' }).markup);
  assert.ok(markup.includes(importsPack.impErr_transcript_correction_incomplete), `${name}: the held banner says why it was not published`);
  assert.ok(!markup.includes('English fallback'), `${name}: the stored English sentence is only a fallback`);
}
const rightsHeld = { ...detail.record, status: 'review', outcome: { state: 'held', reason: 'rights_unknown', message: 'rights unknown' } };
const rightsMarkup = String(mediaPage({ detail: { ...detail, record: rightsHeld }, view: { busy: false, error: '' }, t: speak(en), ui: { locale: 'en' }, href: () => '#/admin' }).markup);
assert.ok(!rightsMarkup.includes('rights unknown'), 'a rights hold keeps its existing presentation (no new banner)');
console.log('Admin media review Publish uses canonical status API: PASS');
