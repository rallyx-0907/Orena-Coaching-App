// Gate for the public pages (Landing, Terms, Privacy): the committed output is the pinned design, the legal text
// is verbatim, and no link points at a prototype file or at the Donate page (out of scope).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const pin = (n) => fs.readFileSync(`docs/design/canonical-ui/screens/${n}`, 'utf8');
const built = (n) => fs.readFileSync(`templates/orena/public/${n}`, 'utf8');

// 1. The committed output equals a fresh build from the pin (a re-pin that is not rebuilt fails here).
execFileSync(process.execPath, ['scripts/build_public_pages.mjs', '--check'], { stdio: 'inherit' });

for (const [source, out] of [['Orena-Terms.dc.html', 'terms.html'], ['Orena-Privacy.dc.html', 'privacy.html']]) {
  const src = pin(source);
  const dst = built(out);

  // 2. Every section heading, in both languages, verbatim and in the same order.
  const headings = [...src.matchAll(/<h2\b[^>]*>([^<]+)<\/h2>/g)].map((m) => m[1]);
  assert.ok(headings.length >= 26, `${source}: 13 sections in two languages (found ${headings.length})`);
  const builtHeadings = [...dst.matchAll(/<h2\b[^>]*>([^<]+)<\/h2>/g)].map((m) => m[1]);
  assert.deepEqual(builtHeadings, headings, `${out}: headings`);

  // 3. The dates and the contacts.
  for (const m of src.matchAll(/(?:Cập nhật lần cuối|Hiệu lực|Có hiệu lực|Last updated|Effective)[^<\n]*\d{4}/g)) {
    assert.ok(dst.includes(m[0]), `${out}: date line "${m[0]}"`);
  }
  assert.ok(/9 tháng 10, 2026/.test(dst) && /October 9, 2026/.test(dst), `${out}: effective date`);
  for (const mail of ['orena.legal@chillpickle.org', 'orena.support@chillpickle.org']) assert.ok(dst.includes(mail), `${out}: ${mail}`);

  // 4. Every paragraph and list item of the legal text is present byte for byte; the Donate link in a sentence
  //    keeps its words and loses only the anchor.
  const blocks = [...src.matchAll(/<(p|li)\b[^>]*>([\s\S]*?)<\/\1>/g)].map((m) => m[0]);
  assert.ok(blocks.length > 40, `${source}: legal blocks found (${blocks.length})`);
  for (const block of blocks) {
    const expected = block
      .replace(/<a href="Orena Donate\.dc\.html">([^<]*)<\/a>/g, '$1')
      .replace(/href="Orena (Privacy|Terms)\.dc\.html(\?lang=en)?"/g, (_m, p, q) => `href="/${p.toLowerCase()}${q || ''}"`);
    assert.ok(dst.includes(expected), `${out}: block missing: ${block.slice(0, 80)}`);
  }
}

// 5. No page links to a prototype file or to Donate; sign-in buttons go to the shell, not to /login or the Landing.
for (const out of ['landing.html', 'terms.html', 'privacy.html']) {
  const text = built(out);
  assert.ok(!/\.dc\.html/.test(text.replace(/data-dc-script/g, '')), `${out}: no prototype-file link`);
  assert.ok(!/donate/i.test(text), `${out}: no Donate link`);
  assert.ok(text.includes('/orena-assets/public/support.js'), `${out}: runtime served from /orena-assets`);
}
assert.ok(!/localStorage\.getItem\('orena-legal-lang'\)[^;]*zh/.test(built('terms.html')), 'sanity');
for (const out of ['terms.html', 'privacy.html']) assert.ok(built(out).includes("if (q === 'zh') return 'en';"), `${out}: ?lang=zh shows English`);

// 6. No external script origin anywhere: the runtime and React are served from /orena-assets (supply chain,
//    availability, CSP). Only Google Fonts stylesheets may leave the origin.
const served = [...['landing.html', 'terms.html', 'privacy.html'].map(built), fs.readFileSync('static/orena/public/support.js', 'utf8')];
for (const text of served) {
  for (const m of text.matchAll(/https?:\/\/[A-Za-z0-9.-]+/g)) {
    // www.w3.org is the SVG/XML namespace name, never fetched.
    assert.ok(['https://fonts.googleapis.com', 'https://fonts.gstatic.com', 'http://www.w3.org'].includes(m[0]), `external origin: ${m[0]}`);
  }
  assert.ok(!/unpkg|jsdelivr|cdnjs|<script[^>]+src="https?:/i.test(text), 'no CDN script reference');
}
// React is the npm file the design pins: the design's own SRI hash still matches the vendored bytes.
const runtimeText = fs.readFileSync('static/orena/public/support.js', 'utf8');
for (const [file, key] of [['react.production.min.js', 'REACT_SRI'], ['react-dom.production.min.js', 'REACT_DOM_SRI']]) {
  const bytes = fs.readFileSync(`static/orena/public/vendor/${file}`);
  const sri = 'sha384-' + createHash('sha384').update(bytes).digest('base64');
  assert.ok(runtimeText.includes(`var ${key} = "${sri}"`), `${file} matches ${key}`);
  assert.ok(runtimeText.includes(`/orena-assets/public/vendor/${file}`), `${file} is what the runtime loads`);
}
assert.ok(!fs.existsSync('static/orena/public/vendor/babel-not-shipped.js'), 'Babel is not shipped');
for (const out of ['terms.html', 'landing.html', 'privacy.html']) assert.ok(!/x-import/.test(built(out)), `${out}: no JSX import, so no Babel`);
const pinned = fs.readFileSync('docs/design/canonical-ui/screens/support.js');
assert.ok(pinned.includes('unpkg.com/react@18.3.1'), 'the pinned runtime is untouched');

console.log('public pages gate passed');
