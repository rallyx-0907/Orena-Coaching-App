/* Gate for MV2-3 (D-248 §4-§5, UI_BACKEND_GAPS "Monetisation v2" G1-G8): the badge, the tier wash, the light upgrade
   sheet, a locked article's preview and a paid tool's lock, each state from the server's answers only.

   - nothing is drawn and nothing locks while `access.enforced` is off;
   - a Plus/Pro Reading card carries Pricing's tag and a fill wash (never an outline), a rotation pick none, a video never;
   - an unknown plan never locks (no upgrade prompt over an outage);
   - the sheet shows three benefits, the catalogue's dong prices (none hard-coded), the trial seam and "See all plans",
     in EN, VI and ZH;
   - the locked preview keeps the title, the cover and the first paragraph, with no blur and no gradient;
   - a 403 `plan_required` from a scored take opens the sheet; the weekly look-up 429 says its own sentence. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US', onLine: true }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { setLanguages } = await import('../static/orena/copy/index.js');
const { accessFrom, cardView, toolLocked } = await import('../static/orena/product/content-access.js');
const { mediaCard, planTag, toolLock } = await import('../static/orena/kit/components.js');
const { upgradePrice } = await import('../static/orena/screens/plan/model.js');
const { upgradeSheetMarkup, priceLine, benefitKeys } = await import('../static/orena/screens/plan/upgrade-sheet.js');
const { lockedPreviewMarkup } = await import('../static/orena/screens/reader/locked.js');
const { failureOf } = await import('../static/orena/capabilities/speaking-take.js');
const { quotaMessage } = await import('../static/orena/screens/plan/quota-notice.js');
const { t: planT } = await import('../static/orena/screens/plan/copy.js');

const commerce = (block) => ({ available: true, readiness: 'known', content_access: block });
const PLUS_CARD = { id: 'a1', access: { tier: 'plus', rotation: false } };
const PRO_CARD = { id: 'a2', access: { tier: 'pro', rotation: false } };
const FREE_CARD = { id: 'a3', access: { tier: 'free', rotation: false } };
const ROTATION_CARD = { id: 'a4', access: { tier: 'free', rotation: true } };

// ---- 1. the flag: off draws nothing and locks nothing ----------------------------------------------------------------
const off = accessFrom(commerce({ enforced: false, tier: 'free', trial_available: null }));
assert.deepEqual({ ...cardView(PLUS_CARD, off) }, { badge: null, locked: false }, 'enforcement off: no badge, no lock');
assert.deepEqual({ ...cardView(PLUS_CARD, accessFrom(null)) }, { badge: null, locked: false }, 'no commerce read: nothing');
assert.deepEqual({ ...cardView(PLUS_CARD, accessFrom({ available: false })) }, { badge: null, locked: false }, 'an older server without the block');

// ---- 2. enforcement on ---------------------------------------------------------------------------------------------
const free = accessFrom(commerce({ enforced: true, tier: 'free', trial_available: null }));
const plus = accessFrom(commerce({ enforced: true, tier: 'plus', trial_available: false }));
const unknown = accessFrom(commerce({ enforced: true, tier: null, trial_available: null }));
assert.equal(free.trialAvailable, null, 'an unknown trial is not a no');
assert.equal(plus.trialAvailable, false);
assert.deepEqual({ ...cardView(PLUS_CARD, free) }, { badge: 'plus', locked: true }, 'Free on a Plus card: tag + lock');
assert.deepEqual({ ...cardView(PRO_CARD, free) }, { badge: 'pro', locked: true });
assert.deepEqual({ ...cardView(PLUS_CARD, plus) }, { badge: 'plus', locked: false }, 'a Plus learner keeps the tag, never the lock');
assert.deepEqual({ ...cardView(PRO_CARD, plus) }, { badge: 'pro', locked: true });
assert.deepEqual({ ...cardView(FREE_CARD, free) }, { badge: null, locked: false });
assert.deepEqual({ ...cardView(ROTATION_CARD, free) }, { badge: null, locked: false }, 'G7: a rotation pick shows no tag that week');
assert.deepEqual({ ...cardView(PLUS_CARD, unknown) }, { badge: 'plus', locked: false }, 'an unreadable plan never locks');
assert.deepEqual({ ...cardView({ id: 'x' }, free) }, { badge: null, locked: false }, 'a card without a block is free');

// ---- 3. the badge and the wash (G1-G3) -------------------------------------------------------------------------------
const card = String(mediaCard({ title: 'Rain', tier: 'plus', tierLabel: 'Plus' }));
assert.ok(card.includes('c-media--tier-plus'), 'the tier wash class');
assert.ok(card.includes('<span class="o-plan-tag c-media__tier">Plus</span>'), 'Pricing\'s tag, top right of the cover');
assert.ok(String(mediaCard({ title: 'Rain', tier: 'pro', tierLabel: 'Pro' })).includes('c-media--tier-pro'));
assert.ok(!String(mediaCard({ title: 'Rain' })).includes('o-plan-tag'), 'no tier: no tag');
assert.ok(!String(mediaCard({ title: 'Rain', tier: 'free' })).includes('c-media--tier'), 'free: no wash');
assert.equal(String(planTag('Pro')), '<span class="o-plan-tag">Pro</span>');

const css = readFileSync('static/orena/kit/components.css', 'utf8');
const rule = (selector) => {
  const at = css.indexOf(`${selector} {`);
  assert.ok(at >= 0, `missing ${selector}`);
  return css.slice(at, css.indexOf('}', at));
};
const tag = rule('.o-plan-tag');
for (const decl of ['padding: 4px 10px', 'border-radius: 999px', 'background: var(--surface2)', 'color: var(--text)', 'font-size: 11.5px', 'font-weight: 700']) {
  assert.ok(tag.includes(decl), `the Pricing tag pill (pp.tag): ${decl}`);
}
assert.ok(rule('.c-media__tier').includes('top: 8px') && rule('.c-media__tier').includes('right: 8px'), 'G1: 8px inset, top right');
assert.ok(rule('.c-media--tier-plus').includes('background: var(--spark-soft)'), 'G2: Plus is a --spark-soft wash');
assert.ok(rule('.c-media--tier-pro').includes('background: var(--accent-soft)'), 'G2: Pro is an --accent-soft wash');
for (const selector of ['.o-plan-tag', '.c-media--tier-plus', '.c-media--tier-pro', '.o-tool-lock']) {
  assert.ok(!/\b(border|outline)\s*:/.test(rule(selector)) && !/box-shadow/.test(rule(selector)), `D-147: ${selector} draws no outline, border or ring`);
}
assert.ok(rule('.o-tool-lock').includes('color: var(--text3)'), 'G6: the lock is --text3');
assert.ok(String(toolLock({ label: 'Part of Plus' })).includes('aria-label="Part of Plus"'));
assert.ok(String(toolLock({ size: 14 })).includes('width="14"'), 'the lock at the control\'s icon size');

// A video is never badged: Discover passes a tier only for an article (YouTube III.F.3.a).
const discover = readFileSync('static/orena/screens/discover/screen.js', 'utf8');
assert.ok(/entry\.kind === 'article' \? cardView\(/.test(discover), 'Discover badges an article only');
assert.ok(!/tier:/.test(readFileSync('static/orena/screens/listening/screen.js', 'utf8').match(/mediaCard\([^)]*\)/g)?.join('') || ''), 'no tier on a video card');

// ---- 4. tools around a video (G6) -------------------------------------------------------------------------------------
const payload = { access: { viewing: 'free', tools: { lookup: { tier: 'free', locked: false }, translation: { tier: 'plus', locked: true }, dictation: { tier: 'plus', locked: true }, shadowing_score: { tier: 'plus', locked: true }, save_to_review: { tier: 'plus', locked: true } } } };
assert.equal(toolLocked(payload, 'translation'), true);
assert.equal(toolLocked(payload, 'lookup'), false, 'look-up is metered, never locked');
assert.equal(toolLocked({}, 'translation'), false, 'no access block (enforcement off): nothing locked');
assert.equal(toolLocked(payload, 'player'), false, 'the player is not a tool');
const listening = readFileSync('static/orena/screens/listening/screen.js', 'utf8');
for (const tool of ['translation', 'dictation', 'shadowing_score', 'save_to_review']) {
  assert.ok(listening.includes(`lockMark('${tool}'`), `the ${tool} control shows its lock`);
  assert.ok(listening.includes(`upsell('${tool}')`), `a tap on a locked ${tool} opens the sheet`);
}
assert.ok(/function upsell\(tool\) \{\s*if \(playing && playbackOk\) togglePlayback/.test(listening), 'the player is paused before the sheet opens (RMF)');
assert.ok(!/data-act="play"[^>]*lockMark|data-player[^>]*lockMark/.test(listening), 'the player is never locked');

// The word sheet's Save from a video names the video, and its 403 opens the sheet (found in the :8021 pass).
const { wordSavePayload, sourceMediaOf } = await import('../static/orena/screens/quick-sheet/model.js');
assert.deepEqual(sourceMediaOf({ kind: 'listening', content_id: 'media:youtube-abc' }), { source_media_id: 'youtube-abc' });
assert.deepEqual(sourceMediaOf({ kind: 'reading', content_id: 'article:a1' }), {});
assert.equal(wordSavePayload({ word: 'x' }, 's', { kind: 'listening', content_id: 'youtube-abc' }).source_media_id, 'youtube-abc');
assert.ok(/catch \(error\) \{\s*\/\* The sheet stays as it was[^*]*\*\/\s*offerPlan\(error\);/.test(readFileSync('static/orena/screens/quick-sheet/sheet.js', 'utf8')));

// The Shadowing route (`shadow`, the compare room) scores a shadowing take against its video (found in the :8021 pass).
assert.ok(/ctx\.route\?\.id === 'shadow' && source\.assetId \? \{ practice: 'shadowing', mediaId: source\.assetId \}/.test(readFileSync('static/orena/screens/compare/screen.js', 'utf8')));
assert.ok(/practice,\s*mediaId,/.test(readFileSync('static/orena/product/speaking-recorder.js', 'utf8')), 'the recorder hands both to the take');

// A scored take refused for the plan opens the sheet, never retries.
const refused = Object.assign(new Error('x'), { status: 403, category: 'plan_required', context: { required_tier: 'plus', tool: 'shadowing_score' } });
assert.deepEqual({ ...failureOf(refused), error: null }, { kind: 'plan_required', retry: false, error: null });
// The weekly look-up meter spent: the existing quota sentence, the videos still play.
setLanguages({ ui: 'en' });
assert.equal(quotaMessage({ context: { feature: 'media.tools_weekly', used: 3, limit: 3 } }), 'You have looked up words in 3 of 3 videos this week. The videos still play.');

// ---- 5. the upgrade sheet (G4/G5), EN/VI/ZH --------------------------------------------------------------------------
const catalogue = { id: 'plus', prices: { monthly: { USD: 3.49, VND: 79000 }, yearly: { USD: 29.99, VND: 690000 } } };
setLanguages({ ui: 'vi' });
const vi = upgradePrice(catalogue, 'vi');
assert.equal(priceLine(vi).replace(/\s/g, ' '), '79.000 ₫ / tháng · 690.000 ₫ / năm', 'the catalogue\'s dong prices, formatted for vi');
assert.equal(upgradePrice({ id: 'plus', prices: { monthly: { USD: 9.99 } } }, 'en'), null, 'no dong price in the catalogue: no price line');
assert.equal(priceLine(upgradePrice({ id: 'plus', prices: { yearly: { VND: 690000 } } }, 'vi')).replace(/\s/g, ' '), '690.000 ₫ / năm');
const upgradeSource = readFileSync('static/orena/screens/plan/upgrade-sheet.js', 'utf8');
assert.ok(!/79[.,]?000|690[.,]?000/.test(upgradeSource), 'no price is hard-coded in the sheet');
assert.deepEqual(benefitKeys('reading').length, 3);
assert.equal(benefitKeys('tool')[0], 'benefitVideoTools', 'a tool lock leads with the video tools');

const sheets = {};
for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui });
  const markup = String(upgradeSheetMarkup({ kind: 'reading', tier: 'plus', price: upgradePrice(catalogue, ui), trialAvailable: null }));
  sheets[ui] = markup;
  assert.ok(markup.includes('data-sheet-close'), `${ui}: a close control`);
  assert.ok(markup.includes('o-coming__icon'), `${ui}: the Coming-soon lock in a well`);
  assert.equal((markup.match(/s-pricing-card__feat"/g) || []).length, 3, `${ui}: three benefit rows`);
  assert.ok(markup.includes(planT('startTrial')), `${ui}: the 7-day trial button`);
  assert.ok(markup.includes(planT('seePlans')), `${ui}: See all plans`);
  assert.ok(markup.includes(planT('upgradeLeadReading', { plan: 'Plus' })), `${ui}: the lead line`);
}
assert.ok(sheets.vi.includes('Dùng thử 7 ngày'), 'VI says the 7-day trial');
assert.ok(sheets.zh.includes('免费试用 7 天'), 'ZH says the 7-day trial');
assert.notEqual(sheets.en, sheets.vi);
setLanguages({ ui: 'en' });
const used = String(upgradeSheetMarkup({ kind: 'tool', tier: 'plus', price: null, trialAvailable: false }));
assert.ok(used.includes('Upgrade to Plus') && !used.includes('data-upgrade-plans'), 'a used trial: Upgrade, no repeated See all plans');
assert.ok(used.includes(planT('upgradeLeadTool', { plan: 'Plus' })), 'a tool says the video stays free');
assert.ok(/go\(href\(access\.trialAvailable === false \? 'pricing' : 'billing'\)\)/.test(upgradeSource), 'the trial seam: the existing Plan screen until Billing wires the trial');
assert.ok(upgradeSource.includes('upgradeSheetOpened(source)'), 'upgrade_sheet_open goes through #466\'s hook');

// ---- 6. the locked preview (G8) -------------------------------------------------------------------------------------
const preview = { title: 'Rain returns', first_paragraph: 'The river rose overnight.', language: 'en', image: { url: '/static/reading/x.jpg', credit: 'Photo: A', typographic: false } };
const locked = String(lockedPreviewMarkup({ preview, tier: 'plus' }));
assert.ok(locked.includes('Rain returns') && locked.includes('The river rose overnight.'), 'title and first paragraph stay visible');
assert.ok(locked.includes('o-coming__card') && locked.includes('data-locked-unlock'), 'the soft end-of-preview block opens the sheet');
assert.ok(locked.includes('<span class="o-plan-tag">Plus</span>'));
assert.ok(locked.includes('data-scroll-region'), 'only the Reader\'s region scrolls (rule 49)');
const readerCss = readFileSync('static/orena/screens/reader/reader.css', 'utf8');
const lockedCss = readerCss.slice(readerCss.indexOf('A locked article\'s preview')).replace(/\/\*[\s\S]*?\*\//g, '');
assert.ok(!/blur|gradient|mask|opacity/.test(lockedCss), 'no blur, no fade-out gradient');
setLanguages({ ui: 'zh' });
const zh = String(lockedPreviewMarkup({ preview: { ...preview, language: 'zh', first_paragraph: '河水涨了。' }, tier: 'plus' }));
assert.ok(zh.includes('data-tl="zh"') && zh.includes('开通 Plus 继续阅读'), 'ZH: the Chinese body face and the ZH line');
setLanguages({ ui: 'en' });

for (const file of ['static/orena/screens/reader/screen.js', 'static/orena/screens/content/screen.js']) {
  const source = readFileSync(file, 'utf8');
  assert.ok(/const refusal = planRequired\(error\);\s*if \(refusal\) return mountLockedPreview\(/.test(source), `${file}: a 403 plan_required is the preview, never an error`);
}

console.log('MV2-3 upgrade/access gate OK');
