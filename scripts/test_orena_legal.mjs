/* Gate for the in-app legal pages (completion plan item 5, D-128; D-238).

   1. static/orena/legal/content.js is exactly what the public legal text gives (scripts/build_orena_legal.mjs,
      from docs/legal/public/*.en.json + facts.json): one source for the in-app and the public pages.
   2. No bracket placeholder can reach a learner: no [UPPER_CASE], [DECISION: ...] or [[...]] mark and no
      {{token}} in any served legal string, with or without an effective date.
   3. The operator facts the public pages state (name, country, minimum age) are shown.
   4. The pages are English only (D-238): every interface language reads the English text, marked lang="en";
      the addresses resolve (a `?lang=` is ignored) and nothing else does.
   5. Built from kit pieces only: the page header and section heading, and the page's own column CSS
      uses colour tokens only. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { buildContent, moduleText, DOCS } = await import('./build_orena_legal.mjs');
const generated = moduleText(buildContent());
assert.equal(fs.readFileSync('static/orena/legal/content.js', 'utf8').replace(/\r\n/g, '\n'), generated, 'content.js is what the public text gives: run node scripts/build_orena_legal.mjs');

const { setLanguages } = await import('../static/orena/copy/index.js');
const { legalAddress, legalMarkup, datedText, LEGAL_PAGES } = await import('../static/orena/legal/page.js');
assert.deepEqual([...LEGAL_PAGES].sort(), Object.keys(DOCS).sort());

const textOf = (markup) => String(markup).replace(/<[^>]+>/g, ' ').replace(/&#039;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ');
// Any square bracket pair, [[ ]], {{ }}, ‹ ›, and the words TODO / TBD / XXX, in any case, in a served string.
const BRACKETS = /\[[^\]]*\]|\[\[|\]\]|\{\{|\}\}|‹|›|\b(?:TODO|TBD|XXX)\b|\bDRAFT\b|awaiting approval/i;
const facts = JSON.parse(fs.readFileSync('docs/legal/public/facts.json', 'utf8'));
const walk = (value, visit) => {
  if (typeof value === 'string') visit(value);
  else if (Array.isArray(value)) value.forEach((entry) => walk(entry, visit));
  else if (value && typeof value === 'object') Object.values(value).forEach((entry) => walk(entry, visit));
};

// Served strings: everything in the generated content (the dates line is a structured block the page fills in or removes).
const noDate = (text) => text;
for (const [page, doc] of Object.entries(buildContent())) {
  walk(doc, (text) => assert.ok(!BRACKETS.test(noDate(text)), `${page}: no placeholder in "${text.slice(0, 60)}"`));
}
const { LEGAL } = await import('../static/orena/legal/content.js');
walk(LEGAL, (text) => assert.ok(!BRACKETS.test(text), `served content.js string has no placeholder: ${text.slice(0, 60)}`));
const reader = (override) => (name) => (name === 'facts.json' ? JSON.stringify(override) : fs.readFileSync(`docs/legal/public/${name}`, 'utf8'));
assert.throws(() => buildContent(reader({ ...facts, operator: { name: null, country: 'x' } })), /unconfirmed/, 'an unconfirmed fact fails the build instead of showing a mark');

for (const page of Object.keys(DOCS)) {
  const reference = textOf(String(legalMarkup(page, 'en')));
  for (const ui of ['en', 'vi', 'zh']) {
    setLanguages({ ui });
    const markup = String(legalMarkup(page, ui));
    const text = textOf(markup);
    assert.equal(text, reference, `${page}/${ui}: every interface language reads the same English page`);
    assert.ok(!BRACKETS.test(text) && !text.includes('Last updated'), `${page}/${ui}: no placeholder, and with no effective date the date line is left out`);
    const dated = textOf(String(legalMarkup(page, ui, '2026-10-20')));
    assert.ok(dated.includes('Last updated: October 20, 2026. Effective: October 20, 2026.') && !BRACKETS.test(dated), `${page}/${ui}: the server's effective date is shown`);
    for (const banned of ['Note to counsel', 'Sources in the codebase', 'strip before publishing', 'not legal advice', 'DECISION']) {
      assert.ok(!text.includes(banned), `${page}/${ui}: "${banned}" does not reach the page`);
    }
    assert.ok(markup.includes('class="o-h1"') && markup.includes('c-section-head__title'), `${page}/${ui}: kit page header and section headings`);
    assert.ok(markup.includes('lang="en"') && !markup.includes('lang="vi"'), `${page}/${ui}: the text is marked English`);
  }
}
for (const page of ['terms', 'privacy']) {
  const text = textOf(String(legalMarkup(page, 'en')));
  assert.ok(text.includes(facts.operator.name), `${page}: the operator the public pages name is shown`);
}
assert.ok(textOf(String(legalMarkup('terms', 'en'))).includes(`aged ${facts.min_age} and over`), 'terms: the minimum age fact is shown');
assert.match(textOf(String(legalMarkup('refund', 'en'))), /Payments are not live/, 'refund: states what the public Terms state');

assert.equal(datedText(['Last updated', 'Effective'], '2026-10-05'), 'Last updated: October 5, 2026. Effective: October 5, 2026.');
assert.equal(datedText(['Last updated', 'Effective'], 'x"><b>'), '', 'a malformed date is left out, never shown');
assert.equal(datedText(['Last updated', 'Effective'], null), '', 'no date: the line is left out');
assert.deepEqual(legalAddress('#/legal/privacy?lang=vi'), { page: 'privacy' }, 'a language on the address is ignored');
assert.deepEqual(legalAddress('#/legal/terms?lang=fr'), { page: 'terms' });
assert.equal(legalAddress('#/legal/other'), null);
assert.equal(legalAddress('#/today'), null);

// The links to the public pages (D-238): one address for every language, and the label is only its own name -
// no "(English)" note anywhere a legal link or page renders (#437).
const links = await import('../static/orena/legal/links.js');
for (const ui of ['en', 'vi', 'zh']) assert.equal(links.legalHref('/privacy', ui), '/privacy', 'the address carries no language');
assert.deepEqual(Object.keys(links).sort(), ['legalHref'], 'no label helper adds a language note');
{
  const NOTE = /\(English\)|\(tiếng Anh\)|（英文）|\(英文\)/i;
  const rendering = [
    'static/orena/legal/links.js', 'static/orena/legal/page.js', 'static/orena/screens/consent/sheet.js',
    'static/orena/screens/consent/copy.js', 'static/orena/screens/onboarding/screen.js', 'static/orena/screens/onboarding/copy.js',
    'static/orena/screens/settings/screen.js', 'static/orena/screens/settings/copy.js', 'static/orena/screens/settings/model.js',
    'scripts/build_orena_legal.mjs', 'scripts/build_public_pages.mjs', 'scripts/public_legal_static.mjs', 'scripts/public_legal_text.mjs',
  ];
  for (const file of rendering) assert.ok(!NOTE.test(fs.readFileSync(file, 'utf8')), `${file}: no "(English)" note`);
  for (const dir of ['templates/orena', 'templates/orena/public']) {
    if (!fs.existsSync(dir)) continue;
    for (const name of fs.readdirSync(dir).filter((n) => n.endsWith('.html'))) {
      assert.ok(!NOTE.test(fs.readFileSync(`${dir}/${name}`, 'utf8')), `${dir}/${name}: no "(English)" note`);
    }
  }
}

// The consent sheet and its copy carry no placeholder either (PRE-005 v2 fields are filled by the server, never shown as marks).
for (const file of ['static/orena/screens/consent/copy.js', 'static/orena/screens/consent/sheet.js']) {
  assert.ok(!/\[[A-Z][A-Z_ ]+\]|\[DECISION|\[\[[A-Za-z_]|\bTBD\b|\bTODO\b/.test(fs.readFileSync(file, 'utf8')), `${file}: no placeholder`);
}

// The legal-rendering modules carry no draft marker or placeholder wording of their own.
for (const file of ['static/orena/legal/page.js', 'static/orena/legal/links.js']) {
  assert.ok(!/DRAFT|awaiting approval|\bTBD\b|\bTODO\b|‹|›/i.test(fs.readFileSync(file, 'utf8')), `${file}: no draft marker`);
}
assert.ok(!/^\d+\./.test(buildContent().refund.sections[0].heading), 'refund: the reused Terms heading has no section number');

const css = fs.readFileSync('static/orena/legal/legal.css', 'utf8');
assert.ok(!/#[0-9a-f]{3,8}\b|rgba?\(/i.test(css), 'the legal column uses colour tokens only');

console.log(`Orena legal pages: ${LEGAL_PAGES.length} pages, English only, content is the public text, no placeholder reaches a learner: PASS`);

// Settings, Privacy, the consent sheet and the sign-in line: the legal links show their translated name only (#437).
{
  const { readFileSync } = await import('node:fs');
  const settings = readFileSync(new URL('../static/orena/screens/settings/screen.js', import.meta.url), 'utf8');
  assert.match(settings, /rel="noopener">\$\{rowLabel\(row\)\}<\/a>/, 'Settings legal rows show the row label only');
  for (const file of ['settings/screen.js', 'consent/sheet.js', 'onboarding/screen.js']) {
    const text = readFileSync(new URL(`../static/orena/screens/${file}`, import.meta.url), 'utf8');
    assert.doesNotMatch(text, /legalLabel|LEGAL_LANGUAGE_NOTE/, `${file}: no language note helper`);
  }
}
