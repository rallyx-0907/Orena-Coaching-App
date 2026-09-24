/* Every learner copy string is read by its semantic layer (D-079). This gate fails when:
   - a key exists in a pack without a declared layer (a new key must be classified), or a declaration
     names a key no pack has;
   - a declaration disagrees with the plain rule and is not a reviewed decision - so an explanation
     declared as interface, or a button declared as support, fails unless a human-readable reason is
     recorded for it in REVIEWED; a stale REVIEWED entry fails too;
   - a key named like guidance (…Note, …Hint, …Truth, …Tip, …Why) is declared interface unreviewed;
   - the layered copy a screen reads returns any key from the wrong language's pack (swept over every
     key of every table, for the human's cases A, B and C);
   - a surface reads a copy table directly (copy[…], referenceCopy[…]) instead of by layer. */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy, refCopy } from '../static/orena/ui/reference.js';
import { speakingCopy, speakCopy } from '../static/orena/ui/speaking-copy.js';
import { layeredCopy } from '../static/orena/ui/layered-copy.js';
import { COPY_LAYERS, REFERENCE_LAYERS, SPEAKING_LAYERS, REVIEWED, LAYERS } from '../static/orena/ui/copy-layers.js';

const TABLES = {
  copy: { packs: copy, layers: COPY_LAYERS },
  reference: { packs: referenceCopy, layers: REFERENCE_LAYERS },
  speaking: { packs: speakingCopy, layers: SPEAKING_LAYERS },
};
const REASONS = new Set([
  'admin', 'title', 'region-heading', 'button', 'placeholder', 'status', 'metadata', 'counter',
  'verdict', 'feedback', 'coaching', 'provenance', 'explanation', 'instruction',
]);
const SUPPORT_REASONS = new Set(['verdict', 'feedback', 'coaching', 'provenance', 'explanation', 'instruction']);

/* The plain rule, the same one the classification was drafted with: a key named as a label stays
   interface when short; a sentence of four words or more is support; a key named like guidance is
   support when it says something; anything very long is support; the rest is interface. */
const LABEL_SUFFIX = /(Title|Name|Label|Heading|Eyebrow|Button|Action|Tab|Nav|Link|Cta|Placeholder|Aria|Chip|Kind|Unit|Count|Time)$/;
const GUIDE_KEY = /(Note|Hint|Why|Explain|Explanation|Tip|Truth|Help|Guide|Guidance|Instruction|Coach|Feedback|Lead|Invite|Nudge|Reason|Text|Detail|Body|Empty|Intro|Question|Prompt)$/i;
const words = (s) => (s.match(/[\p{L}\p{N}_’']+/gu) || []).length + Math.floor((s.match(/[一-鿿]/g) || []).length / 2);
function plainRule(key, en) {
  const s = String(en).trim();
  const sentence = /[.!?…。！？]\s*$/.test(s) || s.includes('. ') || s.includes('? ');
  const n = words(s);
  if (LABEL_SUFFIX.test(key) && n <= 6) return 'interface';
  if (sentence && n >= 4) return 'support';
  if (GUIDE_KEY.test(key) && n >= 4) return 'support';
  if (n >= 9) return 'support';
  return 'interface';
}

for (const [table, { packs, layers }] of Object.entries(TABLES)) {
  const keys = new Set(Object.values(packs).flatMap((pack) => Object.keys(pack)));
  // 1. Every key declared, nothing declared that does not exist, only known layers.
  for (const key of keys) assert.ok(LAYERS.includes(layers[key]), `${table}.${key} has no declared language layer`);
  for (const key of Object.keys(layers)) assert.ok(keys.has(key), `${table}.${key} is declared but no pack has it`);
  // 2. A declaration against the plain rule is a reviewed decision, with its reason.
  const reviewed = REVIEWED[table] || {};
  for (const key of keys) {
    const rule = plainRule(key, packs.en[key] ?? '');
    const declared = layers[key];
    if (declared !== rule) {
      assert.ok(reviewed[key], `${table}.${key} ("${String(packs.en[key]).slice(0, 60)}") is declared ${declared} but reads as ${rule}: review it and record why`);
      assert.ok(REASONS.has(reviewed[key]), `${table}.${key}: "${reviewed[key]}" is not a known reason`);
      assert.equal(SUPPORT_REASONS.has(reviewed[key]), declared === 'support', `${table}.${key}: reason "${reviewed[key]}" does not fit the ${declared} layer`);
    }
  }
  for (const key of Object.keys(reviewed)) {
    assert.ok(keys.has(key), `REVIEWED.${table}.${key} names no key`);
    assert.notEqual(plainRule(key, packs.en[key]), layers[key], `REVIEWED.${table}.${key} is stale: the plain rule already agrees`);
  }
  // 3. A key named like guidance is not interface without a review.
  for (const key of keys)
    if (/(Note|Hint|Truth|Tip|Why)$/.test(key) && layers[key] === 'interface' && plainRule(key, packs.en[key] ?? '') === 'interface' && words(String(packs.en[key])) >= 4)
      assert.ok(reviewed[key], `${table}.${key} is named like guidance but declared interface`);
  // 4. The copy a screen reads: every key from the pack of its layer, for A, B and C.
  for (const [ui, support] of [['en', 'vi'], ['vi', 'vi'], ['zh', 'en']]) {
    const read = layeredCopy(packs, layers, ui, support);
    for (const key of keys) {
      const from = layers[key] === 'support' ? support : ui;
      const expected = packs[from]?.[key] ?? packs.en[key];
      assert.equal(read[key], expected, `${table}.${key} (${layers[key]}) for ui ${ui} / support ${support}`);
    }
    // A support language Orena has no pack for: guidance in English, never in the interface language.
    const ja = layeredCopy(packs, layers, ui, 'ja');
    for (const key of keys) if (layers[key] === 'support') assert.equal(ja[key], packs.en[key] ?? ja[key], `${table}.${key} for support ja`);
  }
}

// 5. The Speaking audit: the keys the human named, each in its audited layer.
const SPEAKING_AUDIT = {
  support: ['passedOf', 'passed', 'err_no_speech', 'err_too_short', 'err_too_long', 'err_microphone', 'err_unsupported',
    'err_unavailable', 'err_service', 'err_audio_unsupported', 'err_recording_failed', 'err_line_invalid', 'micTitle',
    'micText', 'offlineTitle', 'offlineText', 'notHeardTitle', 'notHeardText', 'notHeardShort', 'notHeardTwice',
    'detailSaid', 'detailScore', 'headlineNone_en', 'headlineNone_zh', 'headlineSome_en', 'headlineOne_en',
    'headlineSome_zh', 'headlineOne_zh', 'subTap', 'subFlagged', 'noResult', 'ftFixes', 'ftFixesOne', 'ftHeadlineFix',
    'ftHeadlineNone', 'ftHeadlineFixOne', 'summaryTitle', 'summaryTitleNone', 'shadowLag', 'headphones',
    'recordingHint', 'freeReady', 'tapWord_en', 'tapWord_zh', 'weakest', 'weakestLine', 'toneUnmeasured',
    'error_mispronunciation', 'error_omission', 'paceSlower', 'paceFaster', 'paceSame'],
  interface: ['ftFixOf', 'summaryMeta', 'summaryKept', 'nextLine', 'hearYours', 'compare', 'record', 'stop', 'retry',
    'close', 'modeListen', 'modeShadow', 'metricPronunciation', 'eachWord_zh', 'ftSayAgainLabel', 'ftSaid', 'lineOf',
    'scoring', 'listening', 'practiseAlone_en', 'practiseAlone_zh', 'keepRecent', 'skipLine', 'goNext'],
};
for (const [layer, keys] of Object.entries(SPEAKING_AUDIT))
  for (const key of keys) assert.equal(SPEAKING_LAYERS[key], layer, `speaking.${key} is audited as ${layer}`);
{
  const s = speakCopy('en', 'vi');
  assert.equal(s.passedOf, speakingCopy.vi.passedOf);
  assert.equal(s.err_service, speakingCopy.vi.err_service);
  assert.equal(s.ftFixOf, speakingCopy.en.ftFixOf);
  assert.equal(s.room, refCopy({ ui: 'en', support: 'vi' }).speaking);
  assert.equal(s.langOf('micText'), 'vi');
  assert.equal(s.langOf('nextLine'), 'en');
}

// 6. No surface reads a copy table directly.
const app = readFileSync(new URL('../static/orena/app.js', import.meta.url), 'utf8');
assert.equal(/\bcopy\[/.test(app), false, 'app.js reads the product copy by layer only');
for (const assignment of app.match(/ctx\.c = [^;]+;/g) || []) assert.match(assignment, /^ctx\.c = layeredCopy\(copy, COPY_LAYERS, ctx\.ui, ctx\.support\);$/);
assert.match(app, /c: layeredCopy\(copy, COPY_LAYERS, ui, undefined\),/);
const ui = new URL('../static/orena/ui/', import.meta.url);
for (const file of readdirSync(ui).filter((name) => name.endsWith('.js'))) {
  const src = readFileSync(new URL(file, ui), 'utf8');
  assert.equal(/referenceCopy\[/.test(src), false, `${file} indexes referenceCopy directly`);
  if (!['copy.js', 'copy-vi.js', 'layered-copy.js'].includes(file)) assert.equal(/\bcopy\[(ctx|scope|state|c)\.ui\]/.test(src), false, `${file} indexes copy directly`);
  assert.equal(/speakingCopy\[/.test(src) && file !== 'speaking-copy.js', false, `${file} indexes the Speaking copy directly`);
}
// Content explanations (grammar notes, pattern names, prepared meanings) are support content: nothing
// is picked by the interface language, and nothing falls back from the support language to it.
for (const dir of ['../static/orena/ui/', '../static/orena/product/', '../static/orena/content/']) {
  const base = new URL(dir, import.meta.url);
  for (const file of readdirSync(base).filter((name) => name.endsWith('.js') && !['copy-layers.js', 'layered-copy.js'].includes(name))) {
    const src = readFileSync(new URL(file, base), 'utf8');
    assert.equal(/\[(ctx|scope|state|c)\.ui\]|\?\.\[ui\]|\[ui\]\s*\|\|/.test(src), false, `${dir}${file} picks content by the interface language`);
    assert.equal(/\[ctx\.support\][^;\n]{0,80}\[ctx\.ui\]/.test(src), false, `${dir}${file} falls back from the support language to the interface's`);
  }
}
const speakingSource = readFileSync(new URL('speaking-copy.js', ui), 'utf8');
assert.equal(/GUIDANCE_KEYS/.test(speakingSource), false, 'no allowlist of guidance keys: every key is declared');
assert.match(speakingSource, /layeredCopy\(speakingCopy, SPEAKING_LAYERS, ui, support\)/);

console.log('Copy layers: every learner key declared, reviewed against the plain rule, read from the right language for A/B/C: PASS');
