// Builds the public pages (Landing, Terms, Privacy) from the pinned design files.
//
//   node scripts/build_public_pages.mjs           write templates/orena/public/*.html and static/orena/public/*
//   node scripts/build_public_pages.mjs --check   fail if the committed output differs from a fresh build
//
// The pages are the design's own files, run by the design's own template runtime (support.js, vendored byte for
// byte beside them), so layout, copy, legal text and motion are the pinned design and nothing is retyped. The
// build changes only what a prototype file cannot keep when it becomes a route: relative links between prototype
// files become the app's addresses, asset URLs become /orena-assets URLs, and the Donate link is removed (the
// Donate page is out of scope, D-160). Every substitution must match, or the build fails: a re-pin that moves one
// of them is noticed here and not in production.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pin = path.join(root, 'docs/design/canonical-ui/screens');
const check = process.argv.includes('--check');

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

function common(text) {
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
  return common(text);
}

const pages = [
  ['Orena-Landing.dc.html', 'landing.html', landing],
  ['Orena-Terms.dc.html', 'terms.html', legal],
  ['Orena-Privacy.dc.html', 'privacy.html', legal],
];
const copies = [
  ['support.js', 'static/orena/public/support.js'],
  ['assets/bg/midnight-wide.jpg', 'static/orena/public/bg/midnight-wide.jpg'],
];

const outputs = new Map();
for (const [src, dest, fn] of pages) {
  const text = fs.readFileSync(path.join(pin, src), 'utf8');
  outputs.set(`templates/orena/public/${dest}`, Buffer.from(fn(text), 'utf8'));
}
for (const [src, dest] of copies) outputs.set(dest, fs.readFileSync(path.join(pin, src)));

let bad = 0;
for (const [rel, buf] of outputs) {
  const file = path.join(root, rel);
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
if (check) console.log(`public pages match the pinned design (${outputs.size} files)`);
