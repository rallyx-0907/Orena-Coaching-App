// Gate for the public pages (Landing, Terms, Privacy, Delete account): the committed output is a fresh build of the
// pinned design plus the repository-owned legal text (docs/legal/public, D-161); that text is on the pages
// verbatim, in both languages, with every section heading; no page names an AI vendor or claims what Orena does
// not do; no page loads anything from another origin (scripts, fonts); and the release check agrees with the facts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';

const built = (n) => fs.readFileSync(`templates/orena/public/${n}`, 'utf8');
const LEGAL = [['privacy', 'privacy.html', 13], ['terms', 'terms.html', 13], ['account-deletion', 'account-deletion.html', 5]];
const readJson = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));

// 1. The committed output equals a fresh build (a re-pin or a text edit that is not rebuilt fails here).
execFileSync(process.execPath, ['scripts/build_public_pages.mjs', '--check'], { stdio: 'inherit' });

// 2. The facts file is well formed, and the release check agrees with it: it must fail while any fact is null and
//    pass only when none is (so "pending" can never publish by accident).
const facts = readJson('docs/legal/public/facts.json');
assert.equal(facts.operator.name, 'RallyX', 'operator is RallyX (human decision 2026-10-09)');
assert.ok(Number.isInteger(facts.min_age) && facts.min_age >= 13, 'min_age is an integer, 13 or more');
for (const key of ['agent_turn_days', 'feedback_months', 'backup_days']) {
  const v = facts.retention[key];
  assert.ok(v === null || (Number.isInteger(v) && v > 0), `retention.${key} is null or a positive integer`);
}
assert.ok(facts.effective_date === null || /^\d{4}-\d{2}-\d{2}$/.test(facts.effective_date), 'effective_date is null or YYYY-MM-DD');
const nulls = [facts.effective_date, facts.retention.agent_turn_days, facts.retention.feedback_months, facts.retention.backup_days].filter((v) => v === null).length;
const rel = spawnSync(process.execPath, ['scripts/build_public_pages.mjs', '--release'], { encoding: 'utf8' });
assert.equal(rel.status, nulls ? 1 : 0, `--release must ${nulls ? 'fail while facts are pending' : 'pass with every fact set'}:\n${rel.stderr}`);
if (nulls) console.log(`note: ${nulls} fact(s) pending, so --release fails until they are set (expected before publication)`);

// 3. Every section heading, in both languages, in order; the contacts; and every sentence of the repository text,
//    verbatim, in the page (fragments between fact placeholders are matched exactly).
const markup = (s) => s
  .replace(/\*\*([^*]+)\*\*/g, '<strong style="color:var(--text);font-weight:600">$1</strong>')
  .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
function expectIn(html, s, where) {
  for (const part of s.split(/\{\{[^}]*\}\}/)) {
    if (!part.trim()) continue;
    assert.ok(html.includes(markup(part)), `${where}: missing text: ${part.slice(0, 90)}`);
  }
}
const allText = [];
for (const [page, file, count] of LEGAL) {
  const html = built(file);
  const headings = [...html.matchAll(/<h2\b[^>]*>([^<]+)<\/h2>/g)].map((m) => m[1]);
  assert.equal(headings.length, count * 2, `${file}: ${count} sections in two languages (found ${headings.length})`);
  const expected = [];
  for (const lang of ['vi', 'en']) {
    const data = readJson(`docs/legal/public/${page}.${lang}.json`);
    assert.equal(data.sections.length, count, `${page}.${lang}: ${count} sections`);
    expected.push(...data.sections.map((s) => s.h));
    expectIn(html, data.intro, `${file} ${lang} intro`);
    for (const item of data.summary.items) expectIn(html, item, `${file} ${lang} summary`);
    for (const sec of data.sections) {
      for (const b of sec.blocks) {
        const strings = b.p ? [b.p] : b.lead ? [b.lead] : b.ul ? b.ul : b.cards ? b.cards.flat() : b.contact ? b.contact.flat() : [];
        assert.ok(strings.length, `${page}.${lang}: block with no text`);
        for (const s of strings) expectIn(html, s, `${file} ${lang} §${sec.h}`);
      }
    }
    for (const [key, label] of data.nav) assert.ok(html.includes(`>${label}</a>`), `${file}: nav ${key}`);
    assert.deepEqual(data.nav.map((n) => n[0]), ['privacy', 'terms', 'account-deletion'], `${page}.${lang}: nav order`);
    allText.push(JSON.stringify(data));
  }
  // The headings come out in the order vi..., en... (the page renders the Vietnamese pane first).
  assert.deepEqual(headings, expected, `${file}: headings`);
  for (const mail of ['orena.legal@chillpickle.org', 'orena.support@chillpickle.org']) assert.ok(html.includes(mail), `${file}: ${mail}`);
  assert.ok(html.includes('RallyX') || html.includes('{{fact'), `${file}: operator is named`);
  assert.ok(!html.includes('{{fact') && !html.includes('{{date}}'), `${file}: no unresolved placeholder`);
  assert.ok(html.includes("if (q === 'zh') return 'en';"), `${file}: ?lang=zh shows English`);
}

// 4. Nothing false or vendor-naming comes back. These are claims the audit found untrue, and the vendor names the
//    human decided not to publish (2026-10-09: describe AI and speech providers by function).
const rendered = LEGAL.map(([, file]) => built(file).replace(/<[^>]+>/g, ' ')).join('\n');
const forbidden = [
  /\bApple\b/, /orena\.app/i, /payment partner/i, /đối tác thanh toán/i, /at rest/i, /khi lưu trữ/i, /App Store/i,
  /train models/i, /huấn luyện mô hình/i, /Settings → Privacy/, /Cài đặt → Quyền riêng tư/, /Export all of your/i,
  /Gemini/i, /Groq/i, /Azure/i, /OpenAI/i, /DeepSeek/i, /Supadata/i, /Cloudflare/i, /Anthropic/i, /Google Fonts/i,
];
for (const re of forbidden) assert.ok(!re.test(rendered), `legal pages must not say ${re}`);

// 5. No page links to a prototype file or to Donate; sign-in buttons go to the shell, not to /login or the Landing.
const PAGES = ['landing.html', ...LEGAL.map(([, f]) => f)];
for (const out of PAGES) {
  const text = built(out);
  assert.ok(!/\.dc\.html/.test(text.replace(/data-dc-script/g, '')), `${out}: no prototype-file link`);
  assert.ok(!/donate/i.test(text), `${out}: no Donate link`);
  assert.ok(text.includes('/orena-assets/public/support.js'), `${out}: runtime served from /orena-assets`);
  assert.ok(!/x-import/.test(text), `${out}: no JSX import, so no Babel`);
}
assert.ok(built('landing.html').includes('href="/account-deletion?lang=en"'), 'landing footer links Delete account');

// 6. Nothing is loaded from another origin: not scripts, not fonts (self-hosted since D-161). The only absolute
//    URL left is the SVG namespace name, which is never fetched.
const served = [...PAGES.map(built), fs.readFileSync('static/orena/public/support.js', 'utf8'), fs.readFileSync('templates/orena/index.html', 'utf8')];
for (const text of served) {
  for (const m of text.matchAll(/https?:\/\/[A-Za-z0-9.-]+/g)) {
    assert.ok(['http://www.w3.org'].includes(m[0]), `external origin: ${m[0]}`);
  }
  assert.ok(!/unpkg|jsdelivr|cdnjs|<script[^>]+src="https?:/i.test(text), 'no CDN script reference');
}
for (const out of PAGES) assert.ok(built(out).includes('/orena-assets/fonts/fonts.css'), `${out}: self-hosted fonts`);
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

// 8. React is the npm file the design pins: the design's own SRI hash still matches the vendored bytes.
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

console.log('public pages gate passed');
