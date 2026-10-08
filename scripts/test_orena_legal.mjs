/* Gate for the legal pages (completion plan item 5, D-128).

   1. static/orena/legal/content.js is exactly what the drafts give (scripts/build_orena_legal.mjs).
   2. Nothing marked "strip before publishing" reaches a page: no Note to counsel, no codebase appendix,
      no draft banner.
   3. Every [DECISION: ...] and [OPERATOR]-style placeholder of the published sections stays visible.
   4. The three pages render in English, Vietnamese and Chinese; Chinese reads the English text, marked
      lang="en", and says so; the addresses resolve and nothing else does.
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
  const english = draft.slice(draft.indexOf('# English'), draft.indexOf('# Tiếng Việt'));
  const vietnamese = draft.slice(draft.indexOf('# Tiếng Việt'), draft.search(/\n## Sources in the codebase/) > 0 ? draft.search(/\n## Sources in the codebase/) : undefined);
  for (const ui of ['en', 'vi', 'zh']) {
    setLanguages({ ui });
    const markup = String(legalMarkup(page, ui));
    const text = textOf(markup);
    for (const banned of ['Note to counsel', 'Sources in the codebase', 'strip before publishing', 'not legal advice']) {
      assert.ok(!text.includes(banned), `${page}/${ui}: "${banned}" does not reach the page`);
    }
    assert.ok(markup.includes('class="o-h1"') && markup.includes('c-section-head__title'), `${page}/${ui}: kit page header and section headings`);
    const own = ui === 'vi' ? vietnamese : english;
    const expected = placeholders(own.replace(/\*\*|\*|`/g, '').replace(/\s+/g, ' '));
    for (const mark of expected) assert.ok(text.includes(mark), `${page}/${ui}: placeholder ${mark.slice(0, 60)} stays visible`);
    assert.ok(markup.includes(`lang="${ui === 'vi' ? 'vi' : 'en'}"`), `${page}/${ui}: the text is marked with its own language`);
    if (ui === 'zh') assert.ok(/中文版待批准/.test(text), `${page}/zh: says the Chinese text waits for approval`);
  }
}

assert.deepEqual(legalAddress('#/legal/privacy?lang=vi'), { page: 'privacy', lang: 'vi' });
assert.deepEqual(legalAddress('#/legal/terms?lang=fr'), { page: 'terms', lang: '' });
assert.equal(legalAddress('#/legal/other'), null);
assert.equal(legalAddress('#/today'), null);

const css = fs.readFileSync('static/orena/legal/legal.css', 'utf8');
assert.ok(!/#[0-9a-f]{3,8}\b|rgba?\(/i.test(css), 'the legal column uses colour tokens only');

console.log(`Orena legal pages: ${LEGAL_PAGES.length} pages x 3 languages, content is the drafts', nothing to strip leaks, placeholders kept: PASS`);
