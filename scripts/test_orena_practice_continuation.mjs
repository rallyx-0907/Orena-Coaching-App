import assert from 'node:assert/strict';
import fs from 'node:fs';
import { pendingRows, recentRows, recentMediaFacts } from '../static/orena/screens/practice/continuation.js';

const visits = [
  { id: 'media:clip', intent: 'speaking_compare', title: '中文', segment: 's2', place: { index: 1, total: 1 } },
  { id: 'expression:free', title: 'Draft' },
  { id: 'conversation:c', title: 'Conversation' },
  { id: 'article:a', title: 'Article', place: { index: 1, total: 1, within: 37 } },
];
const memory = { continuation: visits, expressions: { 'expression:free': 'A real unfinished draft' }, conversations: {} };
assert.deepEqual(pendingRows(memory, 'en').map(r => r.reason), ['draft', 'reading']);
assert.equal(pendingRows(memory, 'en')[1].query, undefined);
assert.deepEqual(pendingRows(memory, 'en')[1].params, { id: 'article:a' });
assert.equal(pendingRows({ ...memory, expressions: {} }, 'en').length, 1);
for (const within of [undefined, 0, 100]) {
  assert.equal(pendingRows({ continuation: [{ ...visits[3], place: { index: 1, total: 1, within } }] }, 'zh').length, 0);
}
const convo = { id: 'conversation:c', language: 'zh', title: '对话', situation: 'Say hello', ended: false,
  turns: [{ id: 't', role: 'learner', text: '你好' }] };
assert.equal(pendingRows({ continuation: [visits[2]], conversations: { [convo.id]: convo } }, 'zh')[0].reason, 'conversation');
for (const state of [{ ...convo, ended: true }, { ...convo, turns: [] }, { ...convo, language: 'en' }]) {
  assert.equal(pendingRows({ continuation: [visits[2]], conversations: { [convo.id]: state } }, 'zh').length, 0);
}
assert.equal(pendingRows({ continuation: [{ id: 'essay:2' }], expressions: { 'essay:2': 'Already submitted text' } }, 'en').length, 0);
const facts = new Map([
  ['media:clip', { canonicalId: 'clip', segment: 's2', index: 2, total: 8 }],
  ['media:upload:asset', { canonicalId: 'clip', segment: 's1', index: 1, total: 8 }],
]);
const recent = recentRows([visits[0], { ...visits[0], id: 'media:upload:asset' }], facts);
assert.equal(recent.length, 1, 'aliases of the same content and practice mode share one recent row');
assert.deepEqual(recent[0].query, { segment: 's2' }, 'the most recent selected segment survives');
assert.equal(recent[0].place, null, 'navigation sentinel is never presented as progress');
assert.equal(recentRows([visits[0], { ...visits[0], id: 'media:another-lesson' }], new Map([
  [visits[0].id, { canonicalId: 'lesson-a', assetId: 'shared-asset', segment: 's2' }],
  ['media:another-lesson', { canonicalId: 'lesson-b', assetId: 'shared-asset', segment: 's3' }],
])).length, 2, 'different lesson excerpts over one asset are not aliases');
assert.equal(recentRows([visits[0]], new Map([[visits[0].id, null]])).length, 0, 'unavailable media is not admitted');
assert.equal(pendingRows({ continuation: Array.from({ length: 6 }, (_, i) => ({ id: `article:${i}`, place: { within: 20 } })) }, 'en').length, 3);
for (const language of ['en', 'zh']) {
  const payload = JSON.parse(fs.readFileSync(new URL(`./fixtures/api/listening_library_lesson.${language}.json`, import.meta.url)));
  const calls = [];
  const readsOnly = { listeningLibraryLesson: async id => { calls.push(['GET lesson', id]); return payload; } };
  const segment = payload.transcript.segments[1].segment_id;
  const entries = [{ id: `media:read-only-${language}`, segment, intent: 'speaking_compare' }];
  const facts = await recentMediaFacts(entries, { api: readsOnly, language, support: 'vi' });
  assert.equal(facts.get(entries[0].id).segment, segment);
  await recentMediaFacts(entries, { api: readsOnly, language, support: 'vi' });
  assert.equal(calls.length, 1, 'reopening uses the shared ready source cache; no job/provider API exists in this double');
  const wrongLanguage = await recentMediaFacts(entries, { api: readsOnly, language: language === 'en' ? 'zh' : 'en', support: 'vi' });
  assert.equal(wrongLanguage.get(entries[0].id), null);
}
console.log('Practice continuation: actual unfinished work, no visit-as-progress, exact resume and alias dedup: PASS');
