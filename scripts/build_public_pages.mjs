// Builds the public pages (Landing, Terms, Privacy, Delete account) from the pinned design files.
//
//   node scripts/build_public_pages.mjs            write templates/orena/public/*.html and static/orena/public/*
//   node scripts/build_public_pages.mjs --check    fail if the committed output differs from a fresh build
//   node scripts/build_public_pages.mjs --release  fail while any fact is still unconfirmed (the check that must
//                                                  pass before the pages go to :8000)
//   node scripts/build_public_pages.mjs --release --effective-date YYYY-MM-DD
//                                                  the deploy step: stamps the publish date (the repository keeps
//                                                  it null), fails if anything is still pending, and writes the
//                                                  pages (--out-dir DIR writes elsewhere, for tests)
//
// The pages are the design's own files, run by the design's own template runtime (support.js, vendored byte for
// byte beside them), so layout, type, spacing and motion are the pinned design. The legal WORDS are no longer the
// design's (D-161, a human-authorised deviation: the design's text claimed things Orena does not do): Terms,
// Privacy and Delete account take their text from docs/legal/public/<page>.<vi|en>.json and the facts in
// docs/legal/public/facts.json, laid out with the design's own markup (scripts/public_legal_text.mjs). The build
// also changes only what a prototype file cannot keep when it becomes a route: relative links between prototype
// files become the app's addresses, asset URLs become /orena-assets URLs, fonts are served from this origin
// (D-161), and the Donate link is removed (the Donate page is out of scope, D-160). Every substitution must
// match, or the build fails: a re-pin that moves one of them is noticed here and not in production.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { LANGS, applyText, loadFacts, loadTexts, Pending } from './public_legal_text.mjs';
import { staticPage } from './public_legal_static.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pin = path.join(root, 'docs/design/canonical-ui/screens');
const check = process.argv.includes('--check');
const release = process.argv.includes('--release');

const APP_SIGN_IN = '/?app=1#/welcome';
const APP_OPEN = '/?app=1';

function sub(text, name, pattern, replacement, { min = 1 } = {}) {
  let n = 0;
  const out = text.replace(pattern, (...m) => {
    n += 1;
    return typeof replacement === 'function' ? replacement(...m) : replacement;
  });
  if (n < min) throw new Error(`${name}: expected at least ${min} match(es), found ${n}`);
  return out;
}

// Fonts are served from this origin: a page never contacts Google (D-161). The design's font lines (a preconnect
// and the css2 stylesheet) become one stylesheet link.
function fonts(text) {
  text = sub(text, 'font preconnect', /[ \t]*<link rel="preconnect" href="https:\/\/fonts\.googleapis\.com">\r?\n/g, '');
  return sub(text, 'font stylesheet', /<link href="https:\/\/fonts\.googleapis\.com\/css2\?[^"]*" rel="stylesheet">/g,
    '<link href="/orena-assets/fonts/fonts.css" rel="stylesheet">');
}

function common(text) {
  text = fonts(text);
  text = sub(text, 'support.js', /src="\.\/support\.js"/g, 'src="/orena-assets/public/support.js"');
  text = sub(text, 'background', /assets\/bg\/midnight-wide\.jpg/g, '/orena-assets/public/bg/midnight-wide.jpg');
  text = sub(text, 'sign-in', /href="Onboarding\.dc\.html"/g, `href="${APP_SIGN_IN}"`, { min: 0 });
  text = sub(text, 'open', /href="Orena\.dc\.html"/g, `href="${APP_OPEN}"`);
  text = sub(text, 'privacy', /href="Orena Privacy\.dc\.html(\?lang=en)?"/g, (_m, q) => `href="/privacy${q || ''}"`);
  text = sub(text, 'terms', /href="Orena Terms\.dc\.html(\?lang=en)?"/g, (_m, q) => `href="/terms${q || ''}"`);
  return text;
}

function legal(text) {
  // The logo goes to the front door; the footer's "About" goes to the Landing.
  text = sub(text, 'landing', /<a href="Orena Landing\.dc\.html"( style="[^"]*")/g, (_m, style) =>
    style.includes('gap:10px') ? `<a href="/"${style}` : `<a href="/landing"${style}`);
  // Donate is out of scope: its footer links are removed, and the text of the in-sentence link stays as text.
  text = sub(text, 'donate footer', /[ \t]*<a href="Orena Donate\.dc\.html" style="color:var\(--muted\)">[^<]*<\/a>\r?\n/g, '');
  text = sub(text, 'donate inline', /<a href="Orena Donate\.dc\.html">([^<]*)<\/a>/g, (_m, inner) => inner, { min: 0 });
  // The design has no Chinese; a request for it shows English.
  text = sub(text, 'lang zh', /if \(q === 'en' \|\| q === 'vi'\) return q;/g, "if (q === 'en' || q === 'vi') return q; if (q === 'zh') return 'en';");
  return common(text);
}

function landing(text) {
  text = sub(text, 'title', /<helmet>\r?\n/, '<helmet>\n<title>Orena</title>\n');
  // The footer's legal row gains the deletion page, in the row's own link style.
  text = sub(text, 'footer deletion', /(<a href="Orena Terms\.dc\.html\?lang=en" style="color:var\(--muted\)">Terms<\/a>)/g,
    (_m, terms) => `${terms}<a href="Orena Account Deletion.dc.html?lang=en" style="color:var(--muted)">Delete account</a>`);
  text = sub(text, 'deletion link', /href="Orena Account Deletion\.dc\.html(\?lang=en)?"/g, (_m, q) => `href="/account-deletion${q || ''}"`);
  return common(text);
}

const facts = loadFacts(root);
const pending = new Pending();

// The deploy step stamps the publish date: `--release --effective-date YYYY-MM-DD`. The repository keeps it null.
const dateIdx = process.argv.indexOf('--effective-date');
const stamped = dateIdx > 0 ? process.argv[dateIdx + 1] : null;
if (dateIdx > 0) {
  if (!release) { console.error('--effective-date is only for --release'); process.exit(1); }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(stamped || '') || Number.isNaN(Date.parse(stamped))) {
    console.error(`--effective-date needs YYYY-MM-DD, got ${JSON.stringify(stamped)}`);
    process.exit(1);
  }
  facts.effective_date = stamped;
}
const outIdx = process.argv.indexOf('--out-dir');
const outRoot = outIdx > 0 ? path.resolve(process.argv[outIdx + 1]) : root;

// Terms, Privacy and Delete account are static, script-free pages (public_legal_static.mjs): one file per
// language, `<page>.<vi|en>.html`. The design's Terms and Privacy pages are the skeletons; the deletion page uses
// the Terms one.
const LEGAL_SOURCES = [['terms', 'Orena-Terms.dc.html'], ['privacy', 'Orena-Privacy.dc.html'], ['account-deletion', 'Orena-Terms.dc.html']];
const pages = [['Orena-Landing.dc.html', 'landing.html', landing]];
const copies = [['assets/bg/midnight-wide.jpg', 'static/orena/public/bg/midnight-wide.jpg']];

// The runtime loads React from unpkg (and Babel for .jsx imports, which none of these pages use). The served copy
// points at the same npm files vendored under static/orena/public/vendor/ (react@18.3.1, react-dom@18.3.1: the
// design's own SRI hashes still match them byte for byte) and at a Babel path that is not shipped and never asked
// for. The pinned support.js stays byte-identical in docs/design.
const VENDOR = '/orena-assets/public/vendor';
function runtime(text) {
  text = sub(text, 'react url', /https:\/\/unpkg\.com\/react@18\.3\.1\/umd\/react\.production\.min\.js/g, `${VENDOR}/react.production.min.js`);
  text = sub(text, 'react-dom url', /https:\/\/unpkg\.com\/react-dom@18\.3\.1\/umd\/react-dom\.production\.min\.js/g, `${VENDOR}/react-dom.production.min.js`);
  text = sub(text, 'babel url', /https:\/\/unpkg\.com\/@babel\/standalone@[0-9.]+\/babel\.min\.js/g, `${VENDOR}/babel-not-shipped.js`);
  return text;
}

const outputs = new Map();
for (const [src, dest, fn] of pages) {
  const text = fs.readFileSync(path.join(pin, src), 'utf8');
  outputs.set(`templates/orena/public/${dest}`, Buffer.from(fn(text), 'utf8'));
}
for (const [page, src] of LEGAL_SOURCES) {
  const texts = loadTexts(root, page);
  const filled = applyText(legal(fs.readFileSync(path.join(pin, src), 'utf8')), page, texts, facts, pending);
  for (const lang of LANGS) outputs.set(`templates/orena/public/${page}.${lang}.html`, Buffer.from(staticPage(filled, page, lang, texts), 'utf8'));
}
for (const [src, dest] of copies) outputs.set(dest, fs.readFileSync(path.join(pin, src)));
outputs.set('static/orena/public/support.js', Buffer.from(runtime(fs.readFileSync(path.join(pin, 'support.js'), 'utf8')), 'utf8'));

if (release) {
  if (pending.paths.size) {
    console.error(`NOT RELEASABLE: ${pending.paths.size} fact(s) are unconfirmed (docs/legal/public/facts.json; the publish date is set at deploy with --effective-date YYYY-MM-DD):`);
    for (const p of [...pending.paths].sort()) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log('release check passed: every fact the public legal text states is confirmed');
  if (stamped === null) process.exit(0);
}
else if (pending.paths.size) {
  console.warn(`note: ${pending.paths.size} unconfirmed fact(s) render as "[pending: ...]" and block --release: ${[...pending.paths].sort().join(', ')}`);
}

let bad = 0;
for (const [rel, buf] of outputs) {
  const file = path.join(check ? root : outRoot, rel);
  if (check) {
    if (!fs.existsSync(file) || !fs.readFileSync(file).equals(buf)) {
      console.error(`DRIFT ${rel}`);
      bad += 1;
    }
  } else {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, buf);
    console.log(`wrote ${rel} (${buf.length} bytes)`);
  }
}
if (bad) process.exit(1);
if (check) console.log(`public pages match the pinned design and the repository legal text (${outputs.size} files)`);
