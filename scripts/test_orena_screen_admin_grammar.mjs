/* Grammar in Platform Admin (proposals/ADMIN_GRAMMAR_UI.md, layout approved 2026-10-08): the queue's tab rules, the
   per-language publish, a point's actions and publish blockers, and the three pages (G2 import, G3 queue, G4 point)
   built in English, Vietnamese and Chinese from the shared Admin blocks, with the learner Concept page as the preview.
   Pure builders over fixtures shaped as writing_coach/grammar_admin_api.py answers; no network. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} }, activeElement: null, head: { append() {} }, getElementById: () => null, addEventListener() {}, removeEventListener() {} };

const copyIndex = await import('../static/orena/copy/index.js');
await import('../static/orena/copy/shell.js');
const { t } = await import('../static/orena/screens/admin/copy.js');
const { href, match } = await import('../static/orena/shell/routes.js');
const model = await import('../static/orena/screens/admin/model.js');
const pages = await import('../static/orena/screens/admin/grammar-pages.js');
const { conceptPreviewMarkup } = await import('../static/orena/screens/grammar-concept/screen.js');
const text = (markup) => String(markup?.html ?? markup ?? '');

const version = (n, extra = {}) => ({ id: `v-${n}`, version: n, review_status: 'imported', rights_status: 'cleared', is_published: false, ...extra });
const row = (id, latest, extra = {}) => ({
  id, language: id.startsWith('zh') ? 'zh' : 'en', lifecycle: 'unpublished', function: 'fn.x', sequence: 1, published_at: null,
  level: id.startsWith('zh') ? { framework: 'hsk3', value: '1', rank: 1 } : { framework: 'cefr', value: 'A1', rank: 1 },
  header: { native_title: id.startsWith('zh') ? '比' : 'Past simple: be', title: { en: 'Title', vi: 'Tiêu đề' }, sub: { en: 'comparison', vi: 'so sánh hơn' } },
  latest_version: latest, ...extra,
});
const points = [
  row('en.a', version(1)),
  row('en.b', version(1, { review_status: 'accepted' })),
  row('en.c', version(2, { review_status: 'accepted', is_published: true }), { lifecycle: 'published', published_at: '2026-10-08T09:00:00Z' }),
  row('en.d', version(1, { review_status: 'rejected' })),
  row('en.e', version(1, { review_status: 'accepted' }), { lifecycle: 'archived' }),
  row('en.f', version(3, { review_status: 'accepted' })),
];

/* ---- routes and areas ---- */
assert.equal(match('#/admin/content/grammar').route.id, 'adminGrammar');
assert.equal(match('#/admin/content/grammar/en.canon.a1.001').params.id, 'en.canon.a1.001');
assert.equal(match('#/admin/imports/grammar').route.id, 'adminImportGrammar');
assert.equal(model.areaOf('adminGrammar'), 'content', 'review and publish live in Content');
assert.equal(model.areaOf('adminGrammarPoint'), 'content');
assert.equal(model.areaOf('adminImportGrammar'), 'imports', 'import lives in Imports');

/* ---- the queue's rules ---- */
assert.deepEqual(points.map(pages.tabOf), ['review', 'accepted', 'published', 'rejected', 'archived', 'accepted']);
assert.deepEqual(pages.tabCounts(points), { review: 1, accepted: 2, published: 1, rejected: 1, archived: 1 });
assert.deepEqual(pages.publishableItems(points), [{ point_id: 'en.b', version_id: 'v-1' }, { point_id: 'en.f', version_id: 'v-3' }], 'publish takes every accepted point of the language at its newest version');
assert.deepEqual(pages.shownPoints(points, { tab: 'accepted', q: 'en.f' }).map((p) => p.id), ['en.f']);
assert.deepEqual(pages.shownPoints(points, { tab: 'review', level: 'B1' }), [], 'the level chip filters');
assert.deepEqual(pages.shownPoints(points, { tab: 'review', q: 'so sánh', ui: 'vi' }).map((p) => p.id), ['en.a'], 'search reads the localized sub');

/* ---- a point's actions and blockers ---- */
const detail = (latest, extra = {}) => ({ id: 'en.a', language: 'en', lifecycle: 'unpublished', versions: [version(1, { review_status: 'accepted' }), latest], events: [], ...extra });
assert.deepEqual(pages.pointActions(detail(version(2))), ['accept', 'reject', 'archive', 'restrict'], 'an imported version is accepted or rejected');
assert.deepEqual(pages.pointActions(detail(version(2, { review_status: 'accepted' }))), ['publish', 'archive', 'restrict']);
assert.deepEqual(pages.pointActions(detail(version(2, { review_status: 'accepted', is_published: true }), { lifecycle: 'published' })), ['unpublish', 'restrict']);
assert.deepEqual(pages.pointActions(detail(version(2, { rights_status: 'restricted', review_status: 'accepted' }))), ['publish', 'archive', 'clear']);
assert.deepEqual(pages.pointActions(detail(version(2), { lifecycle: 'archived' })), ['restore']);
assert.deepEqual(pages.publishBlockers(detail(version(2, { review_status: 'accepted' }))), []);
assert.deepEqual(pages.publishBlockers(detail(version(2, { review_status: 'accepted', rights_status: 'unknown' }))), ['grNeedsRights']);
assert.deepEqual(pages.publishBlockers(detail(version(2))), ['grNeedsAccept']);

/* ---- the three pages in three languages ---- */
const learnerPoint = JSON.parse(fs.readFileSync(new URL('./fixtures/grammar/points/zh.guo_experience.json', import.meta.url), 'utf8'));
const check = {
  ok: true, language: 'zh', set_version: '2026-10-08.zh.complete', package_hash: 'f'.repeat(64), point_count: 380, problem_count: 0, problems: [], refusals: [],
  validator: { passed: true }, already_imported: null,
  diff: { counts: { new: 378, changed: 1, unchanged: 0, refused: 1, unlisted: 0 }, points: Array.from({ length: 25 }, (_, i) => ({ id: `zh.p${i}`, state: i === 0 ? 'refused' : 'new' })) },
};
for (const ui of ['en', 'vi', 'zh']) {
  copyIndex.setLanguages({ ui, support: 'vi' });
  const grammar = { file: { name: 'zh-complete.zip' }, check, result: null, error: '', checking: false, importing: false, showAll: false, basis: 'orena_original', attestation: t('grImpAttestDefault') };
  const imp = text(pages.importPage({ grammar, t, ui, href }).markup);
  assert.ok(imp.includes(t('grImpPlan')) && imp.includes('380') && imp.includes('2026-10-08.zh.complete'), `${ui}: the check shows language, set, points, hash`);
  assert.ok(imp.includes('data-a="grammar-import"') && imp.includes(t('grBasis_orena_original')), `${ui}: one confirmation per package, Orena original by default`);
  assert.ok(imp.indexOf('zh.p0') < imp.indexOf('zh.p1'), `${ui}: refused points lead the plan`);
  assert.ok(!imp.includes('zh.p24') && imp.includes('data-a="grammar-show-all"'), `${ui}: the plan shows ${pages.PLAN_PREVIEW} rows, then Show all`);
  const already = text(pages.importPage({ grammar: { ...grammar, check: { ...check, already_imported: { created_at: '2026-10-08T09:00:00Z' } } }, t, ui, href }).markup);
  assert.ok(already.includes(t('grImpAlready')) && !already.includes('data-a="grammar-import"'), `${ui}: an imported package is not imported twice`);
  const done = text(pages.importPage({ grammar: { ...grammar, result: { batch: { language: 'zh', counts: { new: 378, changed: 1, unchanged: 0, refused: 1 } } } }, t, ui, href }).markup);
  assert.ok(done.includes(t('grImpDone')) && done.includes('#/admin/content/grammar?language=zh'), `${ui}: the receipt leads to the review queue`);

  for (const tab of pages.GRAMMAR_TABS) {
    const queue = text(pages.queuePage({ points, view: { tab, language: 'en', level: 'all', q: '' }, t, ui, href, loading: false, busy: '' }).markup);
    assert.ok(queue.includes(t(`grTab_${tab}`)), `${ui}/${tab}: tabs drawn`);
    if (tab === 'review') assert.ok(queue.includes('data-a="grammar-accept-all"'), `${ui}: bulk accept on the review tab`);
    if (tab === 'accepted') assert.ok(queue.includes('data-a="grammar-publish-all"') && queue.includes(t('grPublishAll', { n: '2' })), `${ui}: publish accepted, per language`);
  }
  const empty = text(pages.queuePage({ points: [], view: { tab: 'review', language: 'zh', level: 'all', q: '' }, t, ui, href, loading: false, busy: '' }).markup);
  assert.ok(empty.includes(t('grEmpty_review')), `${ui}: the empty queue says so`);

  const preview = conceptPreviewMarkup(learnerPoint, { support: 'vi' });
  const page = text(pages.pointPage({ point: detail(version(2, { review_status: 'accepted', rights_status: 'unknown' })), summary: points[0], preview, t, ui, href, busy: '' }).markup);
  assert.ok(page.includes('s-gc s-gc--preview') && page.includes(t('grLearnerView')), `${ui}: the preview is the learner Concept page`);
  assert.ok(page.includes(`title="${t('grNeedsRights')}"`) && page.includes(t('grNeedsRights')), `${ui}: publish is blocked until rights are cleared, and says why`);
}
copyIndex.setLanguages({ ui: 'en', support: 'en' });

/* ---- the preview is read-only and shows the answers ---- */
{
  const markup = text(conceptPreviewMarkup(learnerPoint, { support: 'en' }));
  assert.ok(!markup.includes('data-try-input') && !markup.includes('data-quiz-next') && !markup.includes('data-back'), 'nothing in the preview is interactive');
  const answers = (markup.match(/s-gc__opt--ok/g) || []).length;
  assert.equal(answers, learnerPoint.quick_practice.length, 'every quiz question shows its right answer');
}

/* ---- the CI gate list runs this file ---- */
assert.ok(fs.readFileSync('.github/workflows/ci.yml', 'utf8').includes('scripts/test_orena_screen_admin_grammar.mjs'), 'CI runs this gate');

console.log('Orena Admin Grammar: routes in Imports and Content, queue tabs, per-language publish, point actions and blockers, import/queue/point pages in 3 languages, learner preview read-only: PASS');
