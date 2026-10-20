/* Gate for MV2-5 (D-248 §4, UI_BACKEND_GAPS "Monetisation v2 / As built in MV2-5"): own sets and list payloads.

   - a vocabulary set's word and a grammar point carry the server's tier; the first item stays open, a locked one shows
     Pricing's tag, the tier wash and the lock, and its tap opens the light upgrade sheet (kind `set`);
   - a word the server sent locked is never kept by "Add all"; a word the learner already saved is never locked (the
     server decides, and its `locked` wins over the client's comparison);
   - My Library and Search rows read the server's `access` block of a Reading item and draw the same tag and wash; a
     video never carries one (YouTube API Services Developer Policies III.F.3.a);
   - nothing is drawn and nothing locks while `access.enforced` is off;
   - the sheet's set lines and the locked grammar point read in EN, VI and ZH. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US', onLine: true }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { setLanguages } = await import('../static/orena/copy/index.js');
const { accessFrom, itemView, tierClass } = await import('../static/orena/product/content-access.js');
const { wordRow, collectionViewModel } = await import('../static/orena/screens/collection/model.js');
const { keepCollectionWords, isLockedCard } = await import('../static/orena/screens/collection/actions.js');
const { contentRows } = await import('../static/orena/screens/library/model.js');
const { articleItems, collectionItems } = await import('../static/orena/screens/search/model.js');
const { buildLibrary } = await import('../static/orena/screens/grammar/model.js');
const { upgradeSheetMarkup, benefitKeys, UPGRADE_KINDS } = await import('../static/orena/screens/plan/upgrade-sheet.js');
const { lockedConceptMarkup } = await import('../static/orena/screens/grammar-concept/screen.js');
const { t: planT } = await import('../static/orena/screens/plan/copy.js');

const commerce = (block) => ({ available: true, readiness: 'known', content_access: block });
const off = accessFrom(commerce({ enforced: false, tier: 'free', trial_available: null }));
const free = accessFrom(commerce({ enforced: true, tier: 'free', trial_available: null }));
const plus = accessFrom(commerce({ enforced: true, tier: 'plus', trial_available: null }));

// ---- 1. itemView: the server's `locked` wins; off draws nothing ------------------------------------------------------
const FIRST = { access: { tier: 'free', rotation: false, locked: false } };
const REST = { access: { tier: 'plus', rotation: false, locked: true } };
const SAVED_REST = { access: { tier: 'plus', rotation: false, locked: false } };
assert.deepEqual({ ...itemView(REST, off) }, { badge: null, locked: false }, 'enforcement off: no tag, no lock');
assert.deepEqual({ ...itemView(FIRST, free) }, { badge: null, locked: false }, 'the first item of a set stays open');
assert.deepEqual({ ...itemView(REST, free) }, { badge: 'plus', locked: true }, 'the rest: tag + lock');
assert.deepEqual({ ...itemView(SAVED_REST, free) }, { badge: 'plus', locked: false }, 'a word the learner saved is never locked');
assert.deepEqual({ ...itemView({ access: { tier: 'plus' } }, free) }, { badge: 'plus', locked: true }, 'a list block (no `locked`): compared with the plan');
assert.deepEqual({ ...itemView({ access: { tier: 'plus' } }, plus) }, { badge: 'plus', locked: false }, 'Plus keeps the tag, never the lock');
assert.equal(tierClass('plus'), 'o-tier--plus');
assert.equal(tierClass('pro'), 'o-tier--pro');
assert.equal(tierClass(null), '');

// ---- 2. a vocabulary set (Collection Detail) --------------------------------------------------------------------------
const first = { headword: 'buffer', identity: { language: 'en', normalized: 'buffer' }, meanings: [{ language: 'vi', text: 'vùng đệm' }], saved: false, ...FIRST };
const rest = { headword: 'hectic', identity: { language: 'en', normalized: 'hectic' }, saved: false, ...REST };
const savedRest = { headword: 'packed', identity: { language: 'en', normalized: 'packed' }, saved: true, review_stage: 2, ...SAVED_REST };
assert.equal(wordRow(first, 'vi', free).locked, false);
assert.equal(wordRow(first, 'vi', free).meaning, 'vùng đệm', 'the first word keeps its meaning');
assert.deepEqual([wordRow(rest, 'vi', free).locked, wordRow(rest, 'vi', free).badge], [true, 'plus']);
assert.deepEqual([wordRow(savedRest, 'vi', free).locked, wordRow(savedRest, 'vi', free).filled], [false, 2], 'a saved word keeps its review state');
assert.equal(wordRow(rest, 'vi', off).locked, false, 'off: nothing locks');
const model = collectionViewModel({ id: 'c', title: 'C', item_count: 3, items: [first, rest, savedRest] }, 'vi', free);
assert.equal(model.missingCount, 1, '"Add all" offers only the open, unsaved word');
assert.equal(model.savedCount, 1, '"Start review" keeps the saved word');
assert.ok(isLockedCard(rest) && !isLockedCard(first) && !isLockedCard(savedRest));
const sent = [];
const kept = await keepCollectionWords({ language_code: 'en', items: [{ ...first }, { ...rest }, { ...savedRest }] }, {
  language: 'en',
  save: async (payload) => { sent.push(payload.word); return { saved: true, item: { review_stage: 0 } }; },
});
assert.deepEqual(sent, ['buffer'], 'a locked word is never saved by "Add all"');
assert.equal(kept.added, 1);

const collectionScreen = readFileSync('static/orena/screens/collection/screen.js', 'utf8');
assert.ok(/data-word-locked=/.test(collectionScreen) && /planTag\(plan\)/.test(collectionScreen) && /toolLock\(/.test(collectionScreen), 'a locked word: tag + lock');
assert.ok(/openUpgradeSheet\(\{ source: 'collection', kind: 'set'/.test(collectionScreen), 'its tap opens the upgrade sheet');
assert.ok(/tierClass\(word\.badge\)/.test(collectionScreen), 'the tier wash on a paid word');

// ---- 3. a grammar set ------------------------------------------------------------------------------------------------
setLanguages({ ui: 'en', support: 'vi' });
const t = (key) => key;
t.plural = (key) => key;
const points = [
  { id: 'en.a', header: { native_title: 'A', title: { en: 'A', vi: 'A' } }, level: { framework: 'cefr', value: 'A1', rank: 1 }, function: 'fn.x', sequence: 1, access: { tier: 'free', rotation: false } },
  { id: 'en.b', header: { native_title: 'B', title: { en: 'B', vi: 'B' } }, level: { framework: 'cefr', value: 'A1', rank: 1 }, function: 'fn.x', sequence: 2, access: { tier: 'plus', rotation: false } },
];
const view = buildLibrary({ rows: points, functions: [{ id: 'fn.x', title: { en: 'X', vi: 'X' } }], progress: [], current: 'A1', state: {}, support: 'vi', ui: 'en', target: 'en', t });
const byId = Object.fromEntries(view.all.map((entry) => [entry.id, entry]));
assert.deepEqual(byId['en.a'].access, { tier: 'free', rotation: false }, 'the point carries the server\'s block');
assert.deepEqual({ ...itemView(byId['en.b'], free) }, { badge: 'plus', locked: true });
assert.deepEqual({ ...itemView(byId['en.a'], free) }, { badge: null, locked: false }, 'the first point of a set stays open');
const grammarScreen = readFileSync('static/orena/screens/grammar/screen.js', 'utf8');
assert.ok(/data-locked="\$\{esc\(entry\.badge \|\| 'plus'\)\}"/.test(grammarScreen), 'a locked point has no data-open: it cannot open the point');
assert.ok(/openUpgradeSheet\(\{ source: 'grammar', kind: 'set'/.test(grammarScreen));

for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui, support: ui === 'zh' ? 'en' : 'vi' });
  const refusal = { requiredTier: 'plus', itemId: 'en.b', preview: { header: { native_title: 'Past simple', sub: { en: 'Finished actions', vi: 'Hành động đã xong' } }, level: { value: 'A2' } } };
  const markup = String(lockedConceptMarkup(refusal, { support: ui === 'zh' ? 'en' : 'vi' }));
  assert.ok(markup.includes('Past simple'), `${ui}: the point's title stays visible`);
  assert.ok(markup.includes('o-coming__icon') && markup.includes('o-plan-tag'), `${ui}: the lock in a well and the plan's tag`);
  assert.ok(markup.includes(planT('partOfPlan', { plan: 'Plus' })) && markup.includes('data-locked-unlock="plus"'), `${ui}: one line and Unlock`);
  assert.ok(!markup.includes('quick_practice') && !/blur|gradient/.test(markup), `${ui}: no body, no blur`);
}

// ---- 4. the upgrade sheet from a set, EN/VI/ZH -----------------------------------------------------------------------
assert.ok(UPGRADE_KINDS.includes('set'));
assert.equal(benefitKeys('set')[0], 'benefitSets', 'a set leads with the sets');
const leads = new Set();
for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui });
  const markup = String(upgradeSheetMarkup({ kind: 'set', tier: 'plus', price: null, trialAvailable: null }));
  assert.ok(markup.includes(planT('upgradeLeadSet', { plan: 'Plus' })), `${ui}: the set lead line`);
  assert.ok(markup.includes(planT('benefitSets')), `${ui}: the set benefit`);
  leads.add(planT('upgradeLeadSet', { plan: 'Plus' }));
}
assert.equal(leads.size, 3, 'three translations, not one string');

// ---- 5. My Library and Search ----------------------------------------------------------------------------------------
const entries = [
  { ref: { domain: 'reading', id: 'a1' }, title: 'Rain', access: { tier: 'plus', rotation: false } },
  { ref: { domain: 'media', id: 'm1' }, title: 'A video', access: { tier: 'plus', rotation: false } },
];
const rows = contentRows(entries);
assert.deepEqual(rows[0].access, { tier: 'plus', rotation: false }, 'My Library: a Reading row reads its block');
assert.equal(rows[1].access, null, 'a video row never carries one (III.F.3.a)');
assert.deepEqual({ ...itemView(rows[0], free) }, { badge: 'plus', locked: true });
assert.deepEqual({ ...itemView(rows[1], free) }, { badge: null, locked: false });
const library = readFileSync('static/orena/screens/library/screen.js', 'utf8');
assert.ok(/planTag\(planName\(\{ id: badge \}\)/.test(library) && /tierClass\(badge\)/.test(library), 'My Library: tag + wash');

const articles = articleItems({ items: [{ id: 7, title: 'Rain returns', access: { tier: 'plus', rotation: false } }, { id: 8, title: 'Rain again' }] }, 'rain', 'en');
assert.deepEqual(articles.map((item) => item.access), [{ tier: 'plus', rotation: false }, null]);
const found = collectionItems({ entries: [
  { ref: { domain: 'reading', id: '9' }, title: 'Rain', relationship: 'practised', access: { tier: 'pro', rotation: false }, action: { route: '#/encounter?id=article%3A9&intent=reading' } },
  { ref: { domain: 'media', id: 'm' }, title: 'Clip', relationship: 'practised', access: { tier: 'plus' } },
] }, () => '');
assert.deepEqual(found.map((item) => item.access), [{ tier: 'pro', rotation: false }, null], 'Search: Reading only');
const search = readFileSync('static/orena/screens/search/screen.js', 'utf8');
assert.ok(/className: tierClass\(badge\)/.test(search) && /trailing: badge \? planTag\(/.test(search), 'Search: tag + wash');

// ---- 6. the row wash is a fill, never an outline (D-147) --------------------------------------------------------------
const css = readFileSync('static/orena/kit/components.css', 'utf8');
for (const [selector, token] of [['[class].o-tier--plus', '--spark-soft'], ['[class].o-tier--pro', '--accent-soft']]) {
  const at = css.indexOf(`${selector} {`);
  assert.ok(at >= 0, `missing ${selector}`);
  const rule = css.slice(at, css.indexOf('}', at));
  assert.ok(rule.includes(`background: var(${token})`), `${selector}: a ${token} wash`);
  assert.ok(!/\b(border|outline)\s*:|box-shadow/.test(rule), `D-147: ${selector} draws no outline, border or ring`);
}

console.log('MV2-5 set and list access gate OK');
