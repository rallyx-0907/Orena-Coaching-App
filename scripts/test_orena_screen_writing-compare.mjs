// Compare Versions (frame 19, `#/write/:id/compare`): data-mapping assertions over payloads captured
// from the real routes (scripts/fixtures/api/writing_essay_*.json, README there), so a field the
// model reads that the backend does not send fails here. Imports only DOM-free modules.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { mapCompare, legendRows, earlierSegments, revisedSegments, revisionIdOf } from '../static/orena/screens/writing-compare/model.js';

const load = (name) => JSON.parse(fs.readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8'));
const detail = load('writing_essay_detail.json');
const detailV1 = load('writing_essay_detail_v1.json');
const revision = load('writing_essay_revision.json');
const first = load('writing_essay_revision_first.json');

// --- the model reads only fields the real routes send ---
for (const field of ['previous', 'current', 'fixed', 'remaining', 'added', 'dimensionDeltas']) assert.ok(field in revision, `GET /api/essays/{id}/revision carries "${field}"`);
for (const field of ['version', 'text']) {
  assert.ok(field in revision.previous && field in revision.current, `previous/current.${field}`);
}
for (const field of ['title', 'detail']) assert.ok(field in revision.fixed[0], `fixed[].${field}`);
for (const field of ['name', 'from', 'to']) assert.ok(field in revision.dimensionDeltas[0], `dimensionDeltas[].${field}`);
for (const field of ['prompt', 'cefr_estimate', 'revisions']) assert.ok(field in detail, `GET /api/essays/{id} carries "${field}"`);
for (const field of ['id', 'revision_no', 'created_at']) assert.ok(field in detail.revisions[0], `revisions[].${field}`);
assert.equal(first.status, 404, 'a first version answers 404: nothing to compare (the entry button is hidden for it)');

// --- the series: which essay is the earlier version ---
assert.equal(revisionIdOf(detail, revision.previous.version), detailV1.id);
assert.equal(revisionIdOf(detail, 99), null);
assert.equal(revisionIdOf(null, 1), null);

// --- mapCompare ---
const mapped = mapCompare(detail, revision, detailV1);
assert.equal(mapped.prompt, 'Write about your last weekend');
assert.equal(mapped.previous.version, 1);
assert.equal(mapped.current.version, 2);
assert.equal(mapped.previous.createdAt, detail.revisions[0].created_at, 'the version dates come from the series list');
assert.equal(mapped.current.createdAt, detail.revisions[1].created_at);
assert.equal(mapped.fixed.length, 4);
assert.equal(mapped.remaining.length, 1);
assert.equal(mapped.added.length, 1);
// The frame's one summary line: the grammar dimension's real movement and the estimated range's.
assert.deepEqual(mapped.grammar, { from: 48, to: 71 });
assert.deepEqual(mapped.range, { from: 'B1', to: 'B1' });
// Each side of the range must be real, else there is no range line; a missing grammar delta is no line either.
assert.equal(mapCompare(detail, revision, null).range, null);
assert.equal(mapCompare({ ...detail, cefr_estimate: '' }, revision, detailV1).range, null, 'an insufficient-evidence review has no range to move from');
assert.equal(mapCompare(detail, { ...revision, dimensionDeltas: revision.dimensionDeltas.filter((d) => d.name !== 'grammar') }, detailV1).grammar, null);
assert.equal(mapCompare(detail, { ...revision, dimensionDeltas: [{ name: 'grammar', from: null, to: 60 }] }, detailV1).grammar, null, 'a non-number is never shown as 0');

// No comparison at all (a first version, or a malformed answer) maps to null, never a half-built shape.
assert.equal(mapCompare(detail, {}), null);
assert.equal(mapCompare(detail, null), null);

// --- the legend: always the real three categories, zero shown honestly, "—" when nothing to list ---
const legend = legendRows(mapped);
assert.deepEqual(legend.map((row) => row.key), ['fixed', 'remaining', 'added']);
assert.deepEqual(legend.map((row) => row.n), [4, 1, 1]);
assert.deepEqual(legend.map((row) => row.color), ['var(--green)', 'var(--red)', 'var(--amber)'], 'the frame: Fixed green, Still present red, New amber');
assert.equal(legend[0].items, 'We were very happy · the weather was nice · together. It was · I went to the beach', 'what the fixed words became');
assert.equal(legend[1].items, 'I like swim in the sea');
assert.equal(legend[2].items, 'go their again');
const emptyLegend = legendRows(mapCompare(detail, { ...revision, fixed: [] }, detailV1));
assert.equal(emptyLegend[0].n, 0);
assert.equal(emptyLegend[0].items, '—');
assert.deepEqual(legendRows(null), []);

// --- diff spans: fixed + remaining anchored in the earlier text, remaining + added in the revised
//     one, reconstructing each version's exact text with nothing dropped or duplicated ---
const earlier = earlierSegments(mapped);
assert.equal(earlier.map((s) => s.text).join(''), revision.previous.text);
assert.deepEqual(
  earlier.filter((s) => s.tone !== 'plain').map((s) => [s.tone, s.text]),
  [
    ['fixed', 'I go to the beach'],
    ['fixed', 'We was very happy'],
    ['fixed', 'the weather were nice'],
    ['remaining', 'I like swim in the sea'],
    ['fixed', 'together, it was'],
  ],
);
assert.equal(earlier.some((s) => s.tone === 'added'), false, 'nothing "new" is marked in the earlier version');

const revised = revisedSegments(mapped);
assert.equal(revised.map((s) => s.text).join(''), revision.current.text);
assert.deepEqual(
  revised.filter((s) => s.tone !== 'plain').map((s) => [s.tone, s.text]),
  [
    ['remaining', 'I like swim in the sea'],
    ['added', 'go their again'],
  ],
);
assert.equal(revised.some((s) => s.tone === 'fixed'), false, '"fixed" only ever marks where the problem WAS, not the revised text');

assert.deepEqual(earlierSegments(null), []);
assert.deepEqual(revisedSegments(null), []);

// --- the same model over a comparison captured from the running stack (a local evaluator) ---
{
  const liveDetail = load('writing_essay_detail_live.json');
  const liveV1 = load('writing_essay_detail_v1_live.json');
  const liveRevision = load('writing_essay_revision_live.json');
  assert.equal(revisionIdOf(liveDetail, liveRevision.previous.version), liveV1.id);
  const live = mapCompare(liveDetail, liveRevision, liveV1);
  assert.deepEqual(legendRows(live).map((r) => r.n), [2, 3, 1]);
  assert.deepEqual(live.grammar, { from: 55, to: 65 });
  assert.equal(live.range, null, 'neither review demonstrated a band: no range line');
  assert.equal(legendRows(live)[0].items, 'Last weekend I went to the beach with my family. · We were very happy because the weather was nice.');
  assert.equal(earlierSegments(live).map((s) => s.text).join(''), liveRevision.previous.text);
  assert.equal(revisedSegments(live).map((s) => s.text).join(''), liveRevision.current.text);
  assert.ok(earlierSegments(live).some((s) => s.tone === 'fixed'));
}

// --- the copy: every label in all three languages, the same placeholders ---
{
  const store = new Map();
  globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
  const copy = await import('../static/orena/copy/index.js');
  const { t } = await import('../static/orena/screens/writing-compare/copy.js');
  for (const locale of ['en', 'vi', 'zh']) {
    copy.setLanguages({ ui: locale, support: locale });
    for (const key of ['earlierTab', 'revisedTab', 'changesHeader', 'fixedLabel', 'remainingLabel', 'newLabel', 'gramWord', 'rangeWord']) {
      assert.ok(t(key) && t(key) !== key, `${locale}: ${key}`);
    }
    assert.ok(t('versionLabel', { n: 2, when: 'X' }).includes('2') && t('versionLabel', { n: 2, when: 'X' }).includes('X'), `${locale}: versionLabel`);
    assert.ok(t('versionBare', { n: 2 }).includes('2'), `${locale}: versionBare`);
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
}

console.log('Orena Compare Versions screen model: PASS');
