// Gate for the public pages (Landing, Terms, Privacy, Delete account).
//   - the committed output is a fresh build of the pinned design plus the repository-owned legal text (D-162);
//   - Terms, Privacy and Delete account are static HTML: the raw response of each language carries every heading
//     and every sentence of the repository text with no script needed, and loads no runtime, React or other origin;
//   - no page names an AI vendor or claims what Orena does not do; fonts come from this origin;
//   - the release check agrees with the facts file and the deploy step stamps the publish date.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';

const html = (n) => fs.readFileSync(`templates/orena/public/${n}`, 'utf8');
const LEGAL = [['privacy', 13], ['terms', 13], ['account-deletion', 5]];
const LANGS = ['en']; // legal documents are English only (D-238)
const readJson = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));
const build = (...args) => spawnSync(process.execPath, ['scripts/build_public_pages.mjs', ...args], { encoding: 'utf8' });

// 1. The committed output equals a fresh build (a re-pin or a text edit that is not rebuilt fails here), and no
//    page of the retired script-driven kind is left behind.
execFileSync(process.execPath, ['scripts/build_public_pages.mjs', '--check'], { stdio: 'inherit' });
for (const [page] of LEGAL) assert.ok(!fs.existsSync(`templates/orena/public/${page}.html`), `${page}.html (script-driven) is retired`);

// 2. The facts file is well formed, and the release check agrees with it: it fails while any fact is null (so
//    "pending" can never publish by accident), and the deploy step stamps the date.
const facts = readJson('docs/legal/public/facts.json');
assert.equal(facts.operator.name, 'RallyX', 'operator is RallyX (human decision 2026-10-09)');
assert.equal(facts.min_age, 13, 'minimum age is 13 (human decision 2026-10-09)');
assert.deepEqual([facts.retention.agent_turn_days, facts.retention.feedback_months, facts.retention.backup_days], [90, 24, 30], 'retention: 90 days, 24 months, backups 30 days');
assert.equal(facts.effective_date, null, 'the repository keeps the effective date null: the deploy step stamps it');
// The unstamped build keeps the effective-date token the runtime fills with LEGAL_EFFECTIVE_DATE (app.py
// `_legal_page`): twice per page ("Last updated" and "Effective"), never anywhere else.
for (const [page] of LEGAL) {
  const raw = html(`${page}.en.html`);
  assert.equal(raw.split('<mark data-effective-date').length - 1, 2, `${page}: the effective-date token appears exactly twice`);
  assert.equal(raw.split('[pending:').length - 1, 2, `${page}: no other pending marker`);
}
const rel = build('--release');
assert.equal(rel.status, 1, `--release must fail without the publish date:\n${rel.stdout}${rel.stderr}`);
assert.ok(/effective_date/.test(rel.stderr), 'the failure names the effective date');
assert.equal(build('--effective-date', '2026-10-12').status, 1, '--effective-date without --release is refused');
assert.equal(build('--release', '--effective-date', '12/10/2026').status, 1, 'a malformed date is refused');
const stampDir = fs.mkdtempSync(path.join(os.tmpdir(), 'orena-stamp-'));
try {
  const ok = build('--release', '--effective-date', '2026-10-12', '--out-dir', stampDir);
  assert.equal(ok.status, 0, `the deploy step passes with a date:\n${ok.stdout}${ok.stderr}`);
  for (const [page] of LEGAL) {
    const en = fs.readFileSync(path.join(stampDir, `templates/orena/public/${page}.en.html`), 'utf8');
    assert.ok(en.includes('October 12, 2026'), `${page}: the stamped date`);
    assert.ok(!/pending:/.test(en), `${page}: nothing pending once stamped`);
    assert.ok(!fs.existsSync(path.join(stampDir, `templates/orena/public/${page}.vi.html`)), `${page}: no Vietnamese page is built`);
  }
} finally {
  fs.rmSync(stampDir, { recursive: true, force: true });
}

// 3. Every section heading, in order, and every sentence of the repository text, verbatim, in the RAW html of each
//    language, read with every <script> removed (so nothing depends on JavaScript).
const markup = (s) => s
  .replace(/\*\*([^*]+)\*\*/g, '<strong style="color:var(--text);font-weight:600">$1</strong>')
  .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
function expectIn(page, s, where) {
  for (const part of s.split(/\{\{[^}]*\}\}/)) {
    if (!part.trim()) continue;
    assert.ok(page.includes(markup(part)), `${where}: missing text: ${part.slice(0, 90)}`);
  }
}
const noScript = (h) => h.replace(/<script[\s\S]*?<\/script>/g, '');
const rendered = [];
for (const [page, count] of LEGAL) {
  for (const lang of LANGS) {
    const file = `${page}.${lang}.html`;
    const raw = html(file);
    const h = noScript(raw);
    const data = readJson(`docs/legal/public/${page}.${lang}.json`);
    assert.equal(data.sections.length, count, `${page}.${lang}: ${count} sections`);
    assert.deepEqual([...h.matchAll(/<h2\b[^>]*>([^<]+)<\/h2>/g)].map((m) => m[1]), data.sections.map((s) => s.h), `${file}: headings`);
    assert.deepEqual([...h.matchAll(/<a href="#s(\d+)"[^>]*>([^<]+)<\/a>/g)].map((m) => m[2]), data.sections.map((s) => s.toc || s.h), `${file}: contents list`);
    assert.ok(h.includes(`<title>${data.title}</title>`) && h.includes(`<html lang="${lang}">`), `${file}: title and lang`);
    expectIn(h, data.intro, `${file} intro`);
    expectIn(h, data.summary.label, `${file} summary`);
    for (const item of data.summary.items) expectIn(h, item, `${file} summary`);
    for (const sec of data.sections) {
      for (const b of sec.blocks) {
        const strings = b.p ? [b.p] : b.lead ? [b.lead] : b.ul ? b.ul : b.cards ? b.cards.flat() : b.contact ? b.contact.flat() : [];
        assert.ok(strings.length, `${page}.${lang}: block with no text`);
        for (const s of strings) expectIn(h, s, `${file} §${sec.h}`);
      }
    }
    for (const [key, label] of data.nav) assert.ok(h.includes(`>${label}</a>`), `${file}: nav ${key}`);
    assert.deepEqual(data.nav.map((n) => n[0]), ['privacy', 'terms', 'account-deletion'], `${page}.${lang}: nav order`);
    // The three-pill tab row fits a 360px phone: below 480px it spans the column, the pills share it, and it wraps
    // rather than scrolling or clipping "Delete account" (CB).
    assert.equal((h.match(/<nav class="lg-nav" style="display:flex;/g) || []).length, 1, `${file}: the tab row carries lg-nav`);
    assert.ok(h.includes('@media (max-width:479px){.lg-nav{align-self:stretch!important;flex-wrap:wrap}.lg-nav>a{flex:1 1 auto!important;justify-content:center;padding:0 8px!important}}'), `${file}: the narrow tab row rule`);
    for (const mail of ['orena.legal@chillpickle.org', 'orena.support@chillpickle.org']) assert.ok(h.includes(mail), `${file}: ${mail}`);
    assert.ok(h.includes('RallyX'), `${file}: the operator is named`);
    // One language: no switch, no alternate-language link (D-238).
    assert.ok(!/hreflang=/.test(h) && !/>VI<\/a>/.test(h), `${file}: no language switch`);
    assert.ok(!h.includes('?lang='), `${file}: links carry no language`);
    // Static: no runtime, no React, no external script, one small inline script at most.
    assert.ok(!/support\.js|<x-dc|<helmet|sc-if|style-hover|react|babel/i.test(raw), `${file}: no design runtime`);
    assert.ok(!/<script[^>]+\bsrc=/i.test(raw), `${file}: no script file`);
    assert.ok((raw.match(/<script/g) || []).length <= 1, `${file}: at most one inline enhancement script`);
    assert.ok(!/\{\{/.test(h), `${file}: no template binding left`);
    // Both anchors work without script: every contents link has its section.
    for (let i = 1; i <= count; i += 1) assert.ok(h.includes(`id="s${i}"`), `${file}: section s${i}`);
    rendered.push(h.replace(/<[^>]+>/g, ' '));
  }
}

// 4. Nothing false or vendor-naming comes back. These are claims the audit found untrue, and the vendor names the
//    human decided not to publish (2026-10-09: describe AI and speech providers by function). Owner decision
//    2026-10-18 (via delegate; the light-consent decision in DECISION_LOG): the Privacy Policy names the AI
//    providers Google (Gemini) and Groq, and Microsoft Azure Speech for pronunciation, so those are asserted below,
//    not forbidden. OpenRouter, OpenAI and DeepSeek have no key on :8000, so they stay forbidden until the owner answers.
const text = rendered.join('\n');
const forbidden = [
  /\bApple\b/, /orena\.app/i, /payment partner/i, /đối tác thanh toán/i, /at rest/i, /khi lưu trữ/i, /App Store/i,
  /train models/i, /huấn luyện mô hình/i, /Settings → Privacy/, /Cài đặt → Quyền riêng tư/, /Export all of your/i,
 /OpenRouter/i, /OpenAI/i, /DeepSeek/i, /Supadata/i, /Cloudflare/i, /Anthropic/i, /Google Fonts/i,
];
for (const re of forbidden) assert.ok(!re.test(text), `legal pages must not say ${re}`);
for (const [lang, re] of [['en', /Google \(Gemini\) and Groq, and Microsoft Azure Speech/]]) {
  assert.ok(re.test(html(`privacy.${lang}.html`).replace(/<[^>]+>/g, ' ')), `privacy.${lang}: names the AI providers`);
  assert.ok(!/thử nghiệm|pilot|trial/i.test(html(`privacy.${lang}.html`) + html(`terms.${lang}.html`)), `${lang}: no pilot wording`);
}
// The age statements (human decision 2026-10-09): 13 and over, no date of birth, no technical age gate in the beta.
for (const lang of LANGS) {
  for (const page of ['privacy', 'terms']) {
    const t = noScript(html(`${page}.${lang}.html`)).replace(/<[^>]+>/g, ' ');
    assert.ok(/13/.test(t), `${page}.${lang}: states the minimum age 13`);
  }
}
assert.ok(/does not collect your date of birth/.test(html('privacy.en.html')), 'privacy: no date of birth collected');
assert.ok(/no technical age check/.test(html('terms.en.html')), 'terms: no technical age gate in the beta');
// The recent product facts the English text states: notes kept up to 180 days (PRE-005), voice chat for Plus and Pro (D-236).
const privacyText = noScript(html('privacy.en.html')).replace(/<[^>]+>/g, ' ');
assert.ok(/up to 180 days/.test(privacyText), 'privacy: explicit memory is kept up to 180 days');
assert.ok(/Voice chat with Orena is a feature of the Plus and Pro plans/.test(noScript(html('terms.en.html')).replace(/<[^>]+>/g, ' ')), 'terms: voice chat is a paid-plan feature');
// No Vietnamese or Chinese legal text is left in the tree.
for (const page of ['privacy', 'terms', 'account-deletion']) {
  for (const lang of ['vi', 'zh']) {
    assert.ok(!fs.existsSync(`templates/orena/public/${page}.${lang}.html`) && !fs.existsSync(`docs/legal/public/${page}.${lang}.json`), `${page}.${lang}: retired (D-238)`);
  }
}

// 5. The Landing (still the design's own runtime-driven page, PUB-1) points at the deletion page; no page links to a
//    prototype file or to Donate.
const PAGES = ['landing.html', ...LEGAL.flatMap(([p]) => LANGS.map((l) => `${p}.${l}.html`))];
for (const out of PAGES) {
  const t = html(out);
  assert.ok(!/\.dc\.html/.test(t.replace(/data-dc-script/g, '')), `${out}: no prototype-file link`);
  assert.ok(!/donate/i.test(t), `${out}: no Donate link`);
}
assert.ok(html('landing.html').includes('/orena-assets/public/support.js'), 'landing: runtime served from /orena-assets');
assert.ok(!/x-import/.test(html('landing.html')), 'landing: no JSX import, so no Babel');
assert.ok(html('landing.html').includes('href="/account-deletion?lang=en"'), 'landing footer links Delete account');

// 6. Nothing is loaded from another origin: not scripts, not fonts (self-hosted since D-162). The only absolute URL
//    left is the SVG namespace name, which is never fetched.
const served = [...PAGES.map(html), fs.readFileSync('static/orena/public/support.js', 'utf8'), fs.readFileSync('templates/orena/index.html', 'utf8')];
for (const t of served) {
  for (const m of t.matchAll(/https?:\/\/[A-Za-z0-9.-]+/g)) assert.ok(m[0] === 'http://www.w3.org', `external origin: ${m[0]}`);
  assert.ok(!/unpkg|jsdelivr|cdnjs|<script[^>]+src="https?:/i.test(t), 'no CDN script reference');
  assert.ok(!/fonts\.googleapis\.com|fonts\.gstatic\.com/.test(t), 'no Google Fonts');
}
for (const out of PAGES) assert.ok(html(out).includes('/orena-assets/fonts/fonts.css'), `${out}: self-hosted fonts`);
assert.ok(fs.readFileSync('templates/orena/index.html', 'utf8').includes('/orena-assets/fonts/fonts.css'), 'shell: self-hosted fonts');

// 7. The font stylesheet only points at files that exist beside it, and every family has its licence text.
const fontCss = fs.readFileSync('static/orena/fonts/fonts.css', 'utf8');
assert.ok(!/https?:/.test(fontCss), 'fonts.css: no absolute URL');
const files = [...fontCss.matchAll(/src:url\(([^)]+)\)/g)].map((m) => m[1]);
assert.ok(files.length > 100, `fonts.css: ${files.length} faces`);
for (const f of files) assert.ok(fs.existsSync(`static/orena/fonts/${f}`), `font file ${f}`);
for (const fam of ['Fredoka', 'Outfit', 'Plus Jakarta Sans', 'Literata', 'JetBrains Mono', 'Noto Sans SC', 'Noto Serif SC']) {
  assert.ok(fontCss.includes(`font-family:'${fam}'`), `fonts.css declares ${fam}`);
}
for (const l of ['fredoka', 'outfit', 'plusjakartasans', 'literata', 'jetbrainsmono', 'notosanssc', 'notoserifsc']) {
  assert.ok(/SIL OPEN FONT LICENSE/i.test(fs.readFileSync(`static/orena/fonts/licences/OFL-${l}.txt`, 'utf8')), `licence text ${l}`);
}

// 8. The Landing's runtime: React is the npm file the design pins, and the design's own SRI hash still matches the
//    vendored bytes.
const runtimeText = fs.readFileSync('static/orena/public/support.js', 'utf8');
for (const [file, key] of [['react.production.min.js', 'REACT_SRI'], ['react-dom.production.min.js', 'REACT_DOM_SRI']]) {
  const bytes = fs.readFileSync(`static/orena/public/vendor/${file}`);
  const sri = 'sha384-' + createHash('sha384').update(bytes).digest('base64');
  assert.ok(runtimeText.includes(`var ${key} = "${sri}"`), `${file} matches ${key}`);
  assert.ok(runtimeText.includes(`/orena-assets/public/vendor/${file}`), `${file} is what the runtime loads`);
}
assert.ok(!fs.existsSync('static/orena/public/vendor/babel-not-shipped.js'), 'Babel is not shipped');
const pinned = fs.readFileSync('docs/design/canonical-ui/screens/support.js');
assert.ok(pinned.includes('unpkg.com/react@18.3.1'), 'the pinned runtime is untouched');

// Privacy does not say speaking keeps only scores and feedback (answers, written or spoken, are kept as learning
// activity), and it carries the learning-activity paragraph that says so without "only".
{
  const privacy = html('privacy.en.html').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  assert.ok(!/only your scores and feedback/i.test(privacy), 'privacy: the "only scores and feedback" claim is gone');
  const m = privacy.match(/Your learning activity\.[^.]*\.[^.]*\.[^.]*\./);
  assert.ok(m, 'privacy: the learning-activity paragraph is present');
  assert.ok(/written or spoken/.test(m[0]) && !/\bonly\b/i.test(m[0]), 'privacy: written and spoken answers, no "only"');
}

// The Settings "Learner audio" line (translated UI copy) makes no "only scores and feedback" claim in any language.
{
  const lines = fs.readFileSync('static/orena/screens/settings/copy.js', 'utf8').split('\n').filter((l) => l.includes('learnerAudioSub:'));
  assert.equal(lines.length, 3, 'settings copy: learnerAudioSub in en, vi and zh');
  for (const l of lines) assert.ok(!/chỉ giữ|只保留|\bonly your scores/i.test(l), `settings copy: no "only scores" claim: ${l.slice(0, 60)}`);
}

// Retention text (AY): payment/billing records, usage and quota 12 months, admin action logs 24 months.
{
  const strip = (f) => html(f).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
  const privacy = strip('privacy.en.html');
  assert.ok(privacy.includes('Records of your plan usage and quota are kept for 12 months.'), 'privacy: usage and quota 12 months');
  assert.ok(privacy.includes('Logs of administrator actions (which may identify the account acted on) are kept for 24 months.'), 'privacy: admin action logs 24 months');
  assert.ok(privacy.includes('Once payments start, payment and billing records are kept for as long as accounting law requires (in Vietnam, at least 10 years)'), 'privacy: billing records');
  assert.ok(strip('account-deletion.en.html').includes('Payment and billing records are kept as required for accounting and legal purposes.'), 'deletion: billing records kept');
}

console.log('public pages gate passed');
