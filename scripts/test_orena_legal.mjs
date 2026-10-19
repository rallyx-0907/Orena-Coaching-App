/* Gate for the legal pages (completion plan item 5, D-128).

   1. static/orena/legal/content.js is exactly what the drafts give (scripts/build_orena_legal.mjs).
   2. Nothing marked "strip before publishing" reaches a page: no Note to counsel, no codebase appendix,
      no draft banner.
   3. Every [DECISION: ...] and [OPERATOR]-style placeholder of the published sections stays visible.
   4. The three pages are English only (D-238): every interface language reads the English text, marked
      lang="en"; the addresses resolve (a `?lang=` is ignored) and nothing else does.
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
assert.equal(fs.readFileSync('static/orena/legal/content.js', 'utf8').replace(/\r\n/g, '\n'), generated, 'content.js is what the drafts give: run node scripts/build_orena_legal.mjs');

const { setLanguages } = await import('../static/orena/copy/index.js');
const { legalAddress, legalMarkup, LEGAL_PAGES } = await import('../static/orena/legal/page.js');
assert.deepEqual([...LEGAL_PAGES].sort(), Object.keys(DOCS).sort());

const textOf = (markup) => String(markup).replace(/<[^>]+>/g, ' ').replace(/&#039;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ');
const placeholders = (text) => [...text.matchAll(/\[(?:DECISION:[^\]]*|[A-Z][A-Z ]+)\]/g)].map((m) => m[0].replace(/\s+/g, ' '));

for (const [page, name] of Object.entries(DOCS)) {
  const draft = fs.readFileSync(`docs/legal/DRAFT_${name}.md`, 'utf8').replace(/\r\n/g, '\n');
  assert.ok(!draft.includes('# Tiếng Việt'), `${page}: the draft has no Vietnamese section (D-238)`);
  const end = draft.search(/\n## Sources in the codebase/);
  const english = draft.slice(draft.indexOf('# English'), end > 0 ? end : undefined);
  const reference = textOf(String(legalMarkup(page, 'en')));
  for (const ui of ['en', 'vi', 'zh']) {
    setLanguages({ ui });
    const markup = String(legalMarkup(page, ui));
    const text = textOf(markup);
    assert.equal(text, reference, `${page}/${ui}: every interface language reads the same English page`);
    for (const banned of ['Note to counsel', 'Sources in the codebase', 'strip before publishing', 'not legal advice', '中文版待批准', 'Tiếng Việt']) {
      assert.ok(!text.includes(banned), `${page}/${ui}: "${banned}" does not reach the page`);
    }
    assert.ok(markup.includes('class="o-h1"') && markup.includes('c-section-head__title'), `${page}/${ui}: kit page header and section headings`);
    const expected = placeholders(english.replace(/\*\*|\*|`/g, '').replace(/\s+/g, ' '));
    for (const mark of expected) assert.ok(text.includes(mark), `${page}/${ui}: placeholder ${mark.slice(0, 60)} stays visible`);
    assert.ok(markup.includes('lang="en"') && !markup.includes('lang="vi"'), `${page}/${ui}: the text is marked English`);
  }
}

assert.deepEqual(legalAddress('#/legal/privacy?lang=vi'), { page: 'privacy' }, 'a language on the address is ignored');
assert.deepEqual(legalAddress('#/legal/terms?lang=fr'), { page: 'terms' });
assert.equal(legalAddress('#/legal/other'), null);
assert.equal(legalAddress('#/today'), null);

// The links to the public pages (D-238): one address for every language; "(English)" after the label outside English.
const { legalHref, legalLabel } = await import('../static/orena/legal/links.js');
for (const ui of ['en', 'vi', 'zh']) assert.equal(legalHref('/privacy', ui), '/privacy', 'the address carries no language');
assert.equal(legalLabel('Privacy Policy', 'en'), 'Privacy Policy', 'no note in English');
assert.equal(legalLabel('Chính sách quyền riêng tư', 'vi'), 'Chính sách quyền riêng tư (English)');
assert.equal(legalLabel('隐私政策', 'zh'), '隐私政策 (English)');

const css = fs.readFileSync('static/orena/legal/legal.css', 'utf8');
assert.ok(!/#[0-9a-f]{3,8}\b|rgba?\(/i.test(css), 'the legal column uses colour tokens only');

console.log(`Orena legal pages: ${LEGAL_PAGES.length} pages, English only, content is the drafts', nothing to strip leaks, placeholders kept: PASS`);

// Settings, Privacy: the three legal rows get the same "(English)" note through the same helper (D-238).
{
  const { readFileSync } = await import('node:fs');
  const settings = readFileSync(new URL('../static/orena/screens/settings/screen.js', import.meta.url), 'utf8');
  assert.match(settings, /legalLabel\(rowLabel\(row\), copyLanguages\(\)\.ui\)/, 'Settings legal rows use legalLabel');
}
