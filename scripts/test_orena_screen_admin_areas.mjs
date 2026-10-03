/* Gate for the rest of Platform Admin in the new UI (D-101 E slice 2; Orena-Admin.dc.html): the
   Reading pipeline, Content and Imports areas. Their rules are the shared modules the old console
   also imports (capabilities/admin-reading.js, admin-imports.js, admin-content.js, admin-tray.js);
   their pages are pure builders drawn from fixtures in all three languages; and - the three access
   guarantees for every new route - each place mounts for an admin asking only for endpoints the
   server's authorization matrix already refuses to anyone else (tests/test_admin_authorization_matrix.py),
   while the No access rule (zero requests for a non-admin) is asserted for every route in
   test_orena_screen_admin.mjs. No browser: the screen is driven through a stand-in for its DOM. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

/* ---- a browser, just enough of one ------------------------------------------------------------ */
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
class Fake {
  constructor() { this.innerHTML = ''; this.textContent = ''; this.value = ''; this.disabled = false; this.dataset = {}; this.children = new Map(); }
  querySelector(selector) { if (!this.children.has(selector)) this.children.set(selector, new Fake()); return this.children.get(selector); }
  querySelectorAll() { return []; }
  addEventListener() {}
  removeEventListener() {}
  contains() { return false; }
  focus() {}
  remove() {}
  append() {}
  setAttribute() {}
}
globalThis.document = {
  documentElement: { lang: 'en', dataset: {} }, activeElement: null, head: { append() {} }, getElementById: () => null,
  createElement: () => Object.assign(new Fake(), { addEventListener(type, fn) { if (type === 'load') queueMicrotask(fn); } }),
  addEventListener() {}, removeEventListener() {},
};
const requests = [];
let fixtureFor = () => ({ status: 404, body: { detail: 'not found' } });
globalThis.fetch = async (url, options = {}) => {
  const method = String(options.method || 'GET').toUpperCase();
  const path = String(url).split('?')[0];
  requests.push({ method, path });
  const { status = 200, body = {} } = fixtureFor(method, path, String(url)) || {};
  return { ok: status >= 200 && status < 300, status, headers: { get: () => 'application/json' }, json: async () => body, text: async () => JSON.stringify(body) };
};
const unhandled = [];
process.on('unhandledRejection', (error) => unhandled.push(String(error?.stack || error)));

const copyIndex = await import('../static/orena/copy/index.js');
await import('../static/orena/copy/shell.js');
const { t } = await import('../static/orena/screens/admin/copy.js');
const model = await import('../static/orena/screens/admin/model.js');
const { ROUTES, href, match } = await import('../static/orena/shell/routes.js');
const reading = await import('../static/orena/capabilities/admin-reading.js');
const imports = await import('../static/orena/capabilities/admin-imports.js');
const content = await import('../static/orena/capabilities/admin-content.js');
const tray = await import('../static/orena/capabilities/admin-tray.js');
const { adminApi } = await import('../static/orena/capabilities/admin-api.js');

/* ---- fixtures ------------------------------------------------------------------------------------ */
const NOW = '2026-09-28T15:06:04.870476+00:00';
const target = (id, extra = {}) => ({ id, text: `target ${id}`, canonical_form: id, target_type: 'word', context: 'a sentence with the target', meaning: '', rank: 0, machine_suggested: true, admin_approved: false, admin_rejected: false, ...extra });
const article = (extra = {}) => ({
  id: 'A', title: 'The Tortoise and the Hare', body: 'Slow but steady wins the race.\n\nA second paragraph.', excerpt: '', language: 'en', topic: 'fables', subtopic: '',
  estimated_level: 'B2', estimated_level_confidence: 0.47, reviewed_level: null, effective_level: 'B2', word_count: 134, reading_time_seconds: 45, is_adapted: false,
  automation: { allowed: false, override: null, source_default: false, origin: 'source' },
  content_kind: 'article', analysis: { sentence_count: 7, average_sentence_length: 19.1, quality_issues: ['too_short'], detected_language: 'en' }, status: 'published', content_revision: 3,
  created_at: NOW, updated_at: NOW, targets: [target('T1'), target('T2', { admin_rejected: true })],
  source: { id: 'SI', source_id: 'S0', canonical_url: '', title: 'The Tortoise', author: 'Aesop', body: 'orig', content_hash: 'abc123abc123abc123', metadata: { input_kind: 'text', source_name: 'Gutenberg', detected_language: 'en', detected_language_confidence: 0.99 },
    rights: { license_note: 'Public domain' }, rights_state: { can_republish: 'allowed', can_adapt: 'unknown', automation_allowed: 'denied', attribution_required: 'required' } },
  events: [{ id: 'E', actor: 'x', action: 'created', reason: '', changes: {}, created_at: NOW }], duplicates: [{ source_name: 'Other source' }], ...extra,
});
const question = (id, extra = {}) => ({ id, rank: 0, question_type: 'main_idea', prompt: 'What wins the race?', options: ['The hare', 'The tortoise', 'The fox'], correct_index: 1, explanation: 'The text says slow but steady wins.', evidence_text: 'Slow but steady', evidence_start: 0, evidence_end: 15, machine_suggested: true, admin_approved: false, admin_rejected: false, ...extra });
const set = (extra = {}) => ({ id: 'S', article_id: 'A', language_code: 'en', support_language: 'vi', status: 'needs_review', model: 'gemini-x', created_at: NOW, anchored: true, validation: {}, questions: [question('Q1', { admin_approved: true }), question('Q2')], ...extra });
const record = (kind, extra = {}) => ({ kind, id: kind[0].toUpperCase(), title: `A ${kind}`, subtitle: 'Someone', language: 'en', status: 'published', origin: 'imported', facts: { chapter_count: 2, word_count: 100, duration_ms: 60000, level: 'B1', item_count: 3, transcript: 'available', segment_count: 1 }, actions: ['archive', 'unpublish'], created_at: NOW, updated_at: NOW, image: '', ...extra });
const source = (extra = {}) => ({ id: 'SRC', slug: 'gutenberg', name: 'Gutenberg', source_type: 'direct_url', base_url: 'https://gutenberg.org', state: 'active', languages: ['en'], rights: { automation_allowed: false, can_republish: true, can_adapt: false, attribution_required: true, license_note: 'PD' }, polling_enabled: false, last_checked_at: NOW, last_success_at: null, last_error: '', created_at: NOW, ...extra });
const job = (extra = {}) => ({ id: 'J', job_type: 'ingest_text', status: 'failed', stage: 'fetching', attempt: 1, max_attempts: 3, last_error_code: 'fetch_failed', last_error: 'boom', result_kind: '', result_article_id: '', submitted_by: 'admin', created_at: NOW, finished_at: null, ...extra });

fixtureFor = (method, url) => {
  if (url === '/api/admin/console/overview') return ok({ accounts: { available: true, total: 1 }, activity: { available: true, active_7d: 1 }, content: { published: 2 }, attention: [] });
  if (url === '/api/admin/console/users/summary') return ok({ available: true, accounts: { available: true, total: 1 }, activity: { available: true, active_7d: 1 } });
  if (url === '/api/admin/console/users') return ok({ available: true, items: [{ id: 'U', display_name: 'Test user', email_masked: 'u***@example.org', languages: ['en', 'zh'] }], total: 1 });
  if (url === '/api/admin/console/users/U') return ok({ available: true, id: 'U', display_name: 'Test user', profiles: [], activity: [] });
  if (url === '/api/admin/console/runtime') return ok({ ai: { learner_runtime_mode: 'legacy', credential_store: 'configured' }, stores: {} });
  if (url === '/api/admin/ai/operations') return ok({ has_data: false, recent: [], by_capability: [] });
  const ok = (body) => ({ body });
  if (url === '/api/admin/reading/operations') return ok({ queue: { failed: 1, completed: 2 }, articles: { published: 1, needs_review: 1, rejected: 1, archived: 1 }, published: 1, recent: [] });
  if (url === '/api/admin/reading/sources') return ok({ items: [source(), source({ id: 'SRC2', name: 'Draft source', state: 'needs_review' })] });
  if (url === '/api/admin/reading/queue') return ok({ items: [{ id: 'A', title: 'The Tortoise and the Hare', language: 'en', topic: 'fables', level: 'B2', reviewed_level: null, word_count: 134, reading_time_seconds: 45, status: 'needs_review', created_at: NOW }], next_cursor: 'c' });
  if (url === '/api/admin/reading/articles/A' && method === 'GET') return ok(article());
  if (url === '/api/admin/reading/articles/A/rights' && method === 'POST') return ok(article());
  if (url === '/api/admin/reading/articles/A/comprehension-sets') return ok({ items: [set()] });
  if (url === '/api/admin/reading/comprehension-sets/S') return ok(set());
  if (url === '/api/admin/reading/jobs') return ok({ items: [job(), job({ id: 'J2', status: 'completed', stage: 'done', last_error_code: '', result_article_id: 'A' })], next_cursor: null });
  if (url === '/api/admin/reading/jobs/J') return ok(job());
  if (url === '/api/admin/console/content') return ok({ items: [record('book'), record('media'), record('vocabulary')], total: 3, counts: { all: 3, book: 1, media: 1, vocabulary: 1 }, status_counts: {}, sources: {}, offset: 0, limit: 25 });
  if (url === '/api/admin/console/content/book/B') return ok({ record: record('book'), book: { chapters: [{ id: 'C1', title: 'Chapter one' }], imported_by: 'admin', description: '' } });
  if (url === '/api/admin/console/content/media/M') return ok({ record: record('media', { actions: ['unpublish', 'archive', 'reprocess'] }), source: { url: 'https://example.org/v', license: 'CC', review_status: '' }, transcript: { segments: [{ start_ms: 0, text: 'Hello' }], segment_count: 1 } });
  if (url === '/api/admin/console/content/vocabulary/V') return ok({ record: record('vocabulary', { status: 'draft', actions: ['publish', 'archive'] }), entries: [{ term: 'agenda', meaning: 'a plan', part_of_speech: 'noun' }], entry_total: 1, sources: [{ filename: 'w.csv', created_at: NOW, status: 'imported', imported: 3, duplicates: 0, skipped: 0 }], admission: { rights_status: 'licensed', completeness: 'complete' } });
  if (url === '/api/admin/console/imports/history') return ok({ available: true, total: 1, offset: 0, limit: 20, items: [{ kind: 'book', status: 'published', source: 'a.epub', created_at: NOW, result: { title: 'A', chapter_count: 2 } }] });
  return { status: 404, body: { detail: 'not found' } };
};

/* ---- 1. the shared rules ----------------------------------------------------------------------- */
/* Rights: three answers, and copyright is a hard gate at Publish (D-105). */
assert.equal(reading.rightsLevel({ can_republish: 'allowed' }), 'allowed');
assert.equal(reading.rightsLevel({ can_republish: 'denied' }), 'denied');
assert.equal(reading.rightsLevel({}), 'unknown', 'an unanswered right is unknown, not refused');
assert.deepEqual(reading.publicationAdvice(article()).map((w) => w.code), []);
assert.deepEqual(reading.publicationBlockers(article()), [], 'allowed republish (not adapted) is not blocked');
assert.deepEqual(reading.publicationBlockers(article({ source: { rights_state: { can_republish: 'denied' } } })).map((w) => w.code), ['rights_not_cleared']);
assert.deepEqual(reading.publicationBlockers(article({ source: { rights_state: {} }, is_adapted: true })).map((w) => w.code), ['rights_unknown', 'adaptation_unknown'], 'an unanswered right refuses as a denial does');
assert.deepEqual(reading.publicationBlockers(article({ source: { rights_state: { can_republish: 'allowed', can_adapt: 'allowed' } }, is_adapted: true })), []);
assert.deepEqual(reading.publicationAdvice(article({ source: { rights_state: { can_republish: 'denied' } } })).map((w) => `${w.code}:${w.level}`), ['attribution_unknown:warning'], 'attribution is advice, never a block');
/* The request body for answering rights: only what changed; unanswered is null. */
assert.deepEqual(reading.rightsChanges({ can_republish: 'unknown', attribution_required: 'required' }, { can_republish: 'allowed', attribution_required: 'required' }), { can_republish: true });
assert.deepEqual(reading.rightsChanges({ can_republish: 'allowed' }, { can_republish: '' }), { can_republish: null });
assert.deepEqual(reading.rightsChanges({}, { attribution_required: 'not_required', can_adapt: 'denied' }), { attribution_required: false, can_adapt: false });
/* Automation: the source default unless the article carries an override (D-106). */
assert.equal(reading.automationChoice({ override: null, source_default: true }), '');
assert.equal(reading.automationChoice({ override: false }), 'denied');
assert.deepEqual(reading.rightsChanges({}, { automation_allowed: 'allowed' }, { override: null }), { automation_allowed: true });
assert.deepEqual(reading.rightsChanges({}, { automation_allowed: '' }, { override: true }), { automation_allowed: null }, 'clearing the override returns to the source default');
assert.deepEqual(reading.rightsChanges({}, { automation_allowed: 'allowed' }, { override: true }), {}, 'an unchanged answer sends nothing');
for (const status of ['needs_review', 'ready', 'draft']) assert.ok(reading.articleActions(status).includes('publish'), `${status} offers Publish (the server decides on rights)`);
assert.deepEqual(reading.articleActions('published'), ['unpublish', 'archive']);
assert.deepEqual(reading.articleActions('rejected'), ['restore']);
assert.equal(reading.ARTICLE_ACTION_STATUS.restore, 'needs_review', 'restoring returns to review, never republishes');
assert.equal(reading.tabOf('unpublished'), 'archived');
assert.equal(reading.tabFrom('bogus'), 'review');
/* Submission: an absent answer is absent. */
const text = reading.submissionFrom({ mode: 'text', title: ' A title ', body: 'Body', language: 'auto', rights: '', source: 'Gutenberg', author: '', sourceUrl: '', license: '' });
assert.deepEqual(text, { kind: 'text', text: 'Body', title: 'A title', source_name: 'Gutenberg' });
assert.ok(!('can_republish' in text) && !('can_adapt' in text) && !('attribution_required' in text) && !('language' in text), 'no rights answer and no language are simply not sent');
assert.deepEqual(reading.submissionFrom({ mode: 'url', url: 'https://x.org/a', rights: 'allowed', adapt: 'denied', attribution: 'not_required' }), { kind: 'url', url: 'https://x.org/a', can_republish: true, can_adapt: false, attribution_required: false });
assert.equal(reading.submissionFrom({ mode: 'url', url: ' https://x.org/a ', rights: 'allowed' }).can_republish, true);
assert.equal(reading.submissionFrom({ mode: 'url', url: 'https://x.org/a', rights: 'denied' }).can_republish, false);
assert.equal(reading.submissionProblem({ kind: 'url', url: 'nope' }), 'addErrUrl');
assert.equal(reading.submissionProblem({ kind: 'text', text: '  ' }), 'addErrBody');
assert.equal(reading.submissionProblem({ kind: 'file' }, null), 'addErrFile');
assert.equal(reading.submissionProblem({ kind: 'text', text: 'x' }), '');
/* Sets: the database's review graph. */
const at = (status, extra = {}) => set({ status, ...extra });
assert.deepEqual(reading.setActions(at('draft')).map((a) => a.id), ['review', 'discard']);
const approve = (s) => reading.setActions(s).find((a) => a.id === 'approve');
assert.equal(approve(at('needs_review')).enabled, false, 'an undecided question blocks approval');
assert.equal(approve(at('needs_review', { questions: [question('Q1', { admin_approved: true }), question('Q2', { admin_rejected: true })] })).enabled, true);
assert.equal(approve(at('needs_review', { questions: [question('Q1', { admin_rejected: true })] })).enabled, false, 'approval needs one approved question');
assert.equal(approve(at('needs_review', { anchored: false, questions: [question('Q1', { admin_approved: true })] })).enabled, false, 'a stale set cannot be approved');
assert.deepEqual(reading.setActions(at('approved')).map((a) => a.id), ['archive']);
assert.equal(reading.questionsEditable(at('approved')), false, 'a decided set is frozen');
assert.equal(reading.questionsEditable(at('needs_review')), true);
assert.deepEqual(reading.setProgress(set()), { total: 2, approved: 1, rejected: 0, undecided: 1 });
assert.equal(reading.setIsStale(at('needs_review', { anchored: false })), true);
assert.equal(reading.learnerAddress('reading', 'abc'), '#/content/article%3Aabc');
assert.equal(reading.learnerAddress('book', 'b1', 'c1'), '#/content/book%3Ab1%3Ac1');
assert.equal(match(reading.learnerAddress('reading', 'abc')).route.id, 'content', 'the learner link is an address the new UI serves');
/* Imports. */
assert.deepEqual(imports.vocabularyProblems({ files: [], metadata: {} }).map((p) => p.key), ['validationFiles', 'validationTitle']);
assert.deepEqual(imports.vocabularyProblems({ files: [1], previews: [{ filename: 'a.csv' }], mappings: { 'a.csv': {} }, metadata: { title: 'T', publish: true, attested: false } }).map((p) => p.key), ['validationTerm', 'validationAttest']);
assert.equal(imports.slugFor('Open Stories!'), 'open-stories');
assert.equal(imports.sourceBody({ name: ' Open ', url: 'https://o.org', rights: { can_republish: true } }).attribution_required, true);
assert.equal(imports.sourceBody({ name: 'x', rights: { attribution_required: false } }).attribution_required, false);
assert.equal(imports.sourceBody({ name: 'x', rights: {} }).automation_allowed, false, 'polling is not built, so a source never asks for it');
assert.equal(imports.bookOutcome({ status: 'duplicate', title: 'T', book_id: 'B' }).state, 'duplicate');
assert.equal(imports.mediaOutcome({ status: 'failed', category: 'media_unavailable' }).code, 'media_unavailable');
const queue = [{ state: 'to_import', n: 1 }, { state: 'to_import', n: 2 }];
await imports.runQueue(queue, async (item) => { if (item.n === 1) throw Object.assign(new Error('x'), { category: 'boom' }); return { state: 'published' }; });
assert.deepEqual(queue.map((item) => item.state), ['failed', 'published'], 'one failure never holds up the rest');
assert.equal(imports.defaultCollectionTitle('my_word-list.csv'), 'My word list');
/* Content. */
assert.deepEqual(content.lifecycleIntents(record('vocabulary', { actions: ['publish', 'archive'] })), ['archive'], 'vocabulary publishes through its attested form, not the footer');
assert.deepEqual(content.lifecycleIntents(record('media', { actions: ['restore', 'republish', 'archive'] })), ['archive', 'restore', 'republish']);
assert.equal(content.COLLECTION_STATES.restore, 'unpublished', 'restoring never republishes a collection');
assert.equal(content.canPublish({ attested: false }), false);
assert.deepEqual(content.publishChecks({ rights: 'licensed', completeness: 'complete', attested: true }).map((c) => c.pass), [true, true, true]);
assert.equal(content.publishChecks({ rights: 'restricted', completeness: 'partial', attested: false })[0].level, 'strong');
const bookLearnerLink = content.learnerLink(record('book'), { book: { chapters: [{ id: 'C1' }] } });
const { parseContentId } = await import('../static/orena/screens/content/model.js');
assert.deepEqual(parseContentId(decodeURIComponent(bookLearnerLink.slice('#/content/'.length))),
  { kind: 'book', id: 'B', chapterId: 'C1' }, 'Admin book link must resolve through the actual learner route parser');
assert.equal(bookLearnerLink, '#/content/book%3AB%3AC1');
assert.equal(content.learnerLink(record('media', { status: 'archived' }), {}), '', 'an unpublished item has no learner link');
/* Tray: the memory and the clock. */
tray.clear();
tray.watch({ id: 'J1', label: 'My article' });
assert.equal(tray.inFlight(), 1);
assert.equal(tray.progress({ stage: 'analyzing', status: 'running' }) > tray.progress({ stage: 'fetching', status: 'running' }), true);
await tray.refresh({ readingJob: async () => ({ status: 'completed', stage: 'done', result_kind: 'article_created', result_article_id: 'A' }) }, 1000);
assert.equal(tray.items()[0].articleId, 'A', 'a finished job says which article it made');
assert.equal(tray.inFlight(), 0);
await tray.refresh({ readingJob: async () => ({ status: 'completed' }) }, 1000 + tray.SETTLED_MS + 1);
assert.equal(tray.items().length, 0, 'a settled job leaves');
const oldTray = await import('../static/orena/admin/tray.js');
assert.equal(oldTray.watch, tray.watch, 'the old console shares the tray memory');
assert.equal((await import('../static/orena/admin/imports.js')).runQueue, imports.runQueue, 'the old console shares the importer rules');
assert.equal((await import('../static/orena/admin/content.js')).RIGHTS, content.RIGHTS);

/* ---- 2. every page, every language ------------------------------------------------------------ */
const problems = [];
const realError = console.error;
console.error = (...args) => problems.push(args.join(' '));
const rp = await import('../static/orena/screens/admin/reading-pages.js');
const ip = await import('../static/orena/screens/admin/imports-pages.js');
const cp = await import('../static/orena/screens/admin/content-pages.js');
const tp = await import('../static/orena/screens/admin/tray.js');
const common = (ui) => ({ t, ui, href, now: Date.now() });
const view = { q: '', level: 'all', dtab: 'article', edit: {}, newTarget: { text: '', type: 'word', meaning: '' }, support: 'vi', mode: 'text', rights: '', busy: false };
const sourceRow = source();
for (const ui of ['en', 'vi', 'zh']) {
  copyIndex.setLanguages({ ui, support: 'en' });
  const c = common(ui);
  const items = [{ id: 'A', title: 'Title', language: 'en', topic: 'fables', level: 'B2', reviewed_level: 'B1', word_count: 134, reading_time_seconds: 45, status: 'needs_review', created_at: NOW, source_name: 'Gutenberg', rights_level: 'unknown', target_count: 5 }];
  const pages = [
    rp.overviewPage({ ...c, ops: { articles: { published: 2 }, queue: { failed: 1 } }, sources: [sourceRow], next: items, failedJobs: 1 }),
    ...['review', 'published', 'rejected', 'archived'].map((tab) => rp.queuePage({ ...c, tab, items, next: 'c', counts: { review: 1, published: 1, rejected: 0, archived: 0 }, view })),
    rp.queuePage({ ...c, tab: 'review', items: [], next: null, counts: null, view: { ...view, q: 'zzz' } }),
    rp.articlePage({ ...c, article: article(), sets: [set(), set({ id: 'S2', status: 'approved' })], view: { ...view, evOpen: true } }),
    rp.articlePage({ ...c, article: article({ status: 'needs_review', source: { ...article().source, rights_state: { can_republish: 'denied' } } }), sets: [], view: { ...view, generating: true } }),
    rp.articlePage({ ...c, article: article({ status: 'rejected' }), sets: [], view }),
    ...['draft', 'needs_review', 'approved', 'archived', 'rejected', 'stale'].map((status) => rp.setPage({ ...c, set: set({ status }), article: article(), view: { busy: false } })),
    rp.setPage({ ...c, set: set({ anchored: false }), article: article(), view: { busy: false, error: 'boom' } }),
    ...['url', 'text', 'file'].map((mode) => rp.addPage({ ...c, view: { ...view, mode, last: { id: 'J', title: 'T' } } })),
    rp.sourcesPage({ ...c, sources: [sourceRow, source({ id: 'X', state: 'blocked' }), source({ id: 'Y', state: 'archived' })], view }),
    rp.sourcePage({ ...c, source: sourceRow, view: {} }),
    ip.hubPage({ ...c, recent: { book: 1, media: 2, vocabulary: 3, total: 6 }, failedJobs: 2 }),
    ip.booksPage({ ...c, books: { items: [{ name: 'a.epub', size: 1000, state: 'to_import' }, { name: 'b.epub', state: 'published', title: 'B', chapters: 3, contentId: 'B' }, { name: 'c.epub', state: 'failed', code: 'malformed_epub', stage: 'parse' }], language: 'en', running: false } }),
    ip.mediaPage({ ...c, media: { tab: 'url', urls: 'https://x', items: [{ url: 'https://x', title: 'V', state: 'ready', level: 'B1', has_transcript: true }, { url: 'https://y', state: 'failed', code: 'media_unavailable' }], language: 'en' } }),
    ip.mediaPage({ ...c, media: { tab: 'file', urls: '', items: [{ file: {}, name: 'a.mp3', size: 10, state: 'to_import' }], language: 'zh' } }),
    ip.vocabularyPage({ ...c, vocab: { files: [], previews: [], mappings: {}, step: 0, errors: [], results: null, metadata: {} } }),
    ip.vocabularyPage({ ...c, vocab: { files: [{ name: 'w.csv' }], previews: [{ filename: 'w.csv', headers: ['word', 'meaning'], row_count: 3, sample: [{ word: 'a', meaning: 'b' }], warnings: ['one duplicate'] }], mappings: { 'w.csv': { term: 'word' } }, step: 1, errors: [], results: null, metadata: { title: 'W', language: 'en', publish: true, attested: false, completeness: 'unknown', rights_status: '' } } }),
    ip.vocabularyPage({ ...c, vocab: { files: [{ name: 'w.csv' }], previews: [{ filename: 'w.csv', headers: [], row_count: 0, error: 'unreadable' }], mappings: {}, step: 1, errors: [], results: { items: [{ filename: 'w.csv', status: 'imported', imported: 3, duplicates: 1, skipped: 0 }], collection: { collection_id: 'V' } }, metadata: {} } }),
    ip.sourceFormPage({ ...c, form: { name: '', url: '', type: 'direct_url', language: 'en', can_republish: false, can_adapt: false, attribution_required: true, license: '', error: '', running: false } }),
    ip.jobsPage({ ...c, jobs: [job(), job({ id: 'J2', status: 'completed', stage: 'done', last_error_code: '' })], cursor: 'x', filter: 'failed' }),
    ip.jobPage({ ...c, job: job() }),
    ip.jobPage({ ...c, job: job({ status: 'completed', stage: 'done', last_error_code: '', result_article_id: 'A' }) }),
    ip.historyPage({ ...c, data: { available: true, total: 41, offset: 20, items: [{ kind: 'vocabulary', status: 'published', source: 'w.csv', created_at: NOW, result: { title: 'W', imported: 3, duplicates: 0, skipped: 1 } }, { kind: 'media', status: 'failed', source: 'https://x', created_at: NOW, error: { code: 'media_unavailable', stage: 'source' } }] }, filters: { kind: 'all', status: 'all' } }),
    cp.homePage({ ...c, counts: { counts: { book: 1, media: 2, vocabulary: 3, reading_review: 2, reading_published: 4 }, statusCounts: {} } }),
    ...['book', 'media', 'vocabulary'].map((kind) => cp.listPage({ ...c, kind, data: { items: [record(kind)], total: 30, sources: { media: 'unavailable' } }, view: { status: 'all' }, loading: false })),
    cp.bookPage({ ...c, detail: { record: record('book'), book: { chapters: [{ id: 'C1', title: 'One' }], imported_by: 'admin' } }, view: {} }),
    cp.mediaPage({ ...c, detail: { record: record('media', { actions: ['unpublish', 'reprocess'], facts: { transcript: 'missing' } }), source: {}, transcript: { segments: [], segment_count: 0 } }, view: {} }),
    cp.collectionPage({ ...c, detail: { record: record('vocabulary', { status: 'draft', actions: ['publish', 'archive'] }), entries: [{ term: 'a', meaning: 'b' }], entry_total: 1, sources: [] }, form: { rights: '', completeness: 'unknown', attested: false }, view: {} }),
    cp.collectionPage({ ...c, detail: { record: record('vocabulary', { status: 'published', actions: ['unpublish'] }), entries: [], sources: [] }, form: {}, view: {} }),
  ];
  for (const [index, page] of pages.entries()) {
    const html = String(page.markup);
    assert.ok(html.length > 150, `${ui} page ${index} drew something`);
    assert.doesNotMatch(html, /\{[a-zA-Z]+\}/, `${ui} page ${index} left a placeholder unfilled: ${html.match(/\{[a-zA-Z]+\}/)}`);
    assert.doesNotMatch(html, /undefined|\[object|NaN/, `${ui} page ${index} printed a JS value: ${html.match(/.{30}(undefined|\[object|NaN).{20}/)}`);
    assert.doesNotMatch(html, /<script|onerror=/i);
  }
  tray.watch({ id: 'J1', label: 'A <b>title</b>' });
  const trayHtml = String(tp.trayMarkup({ open: true, href }));
  assert.ok(trayHtml.includes('A &lt;b&gt;title&lt;/b&gt;'), 'a submitted title is text, never markup');
  tray.clear();
  assert.deepEqual(problems, [], `${ui}: no copy key is missing (${problems.slice(0, 3)})`);
}
copyIndex.setLanguages({ ui: 'en', support: 'en' });
{
  /* The behaviours the pages promise. */
  const c = common('en');
  const detail = String(rp.articlePage({ ...c, article: article({ status: 'needs_review', source: { ...article().source, rights_state: { can_republish: 'denied' } } }), sets: [], view }).markup);
  assert.match(detail, /data-action="publish"[^>]*disabled|disabled[^>]*data-action="publish"/, 'copyright blocks Publish (hard gate)');
  assert.ok(detail.includes(t('rdRightsAdviceDenied')), 'the refusal is said beside the button');
  assert.ok(detail.includes(t('rdBlockedTitle')) && detail.includes(t('rdBlockedText')), 'the refusal is stated honestly');
  assert.ok(detail.includes(t('rdWarn_rights_not_cleared')), 'the reason is listed');
  assert.match(detail, /data-a="rights-pick"[^>]*data-field="can_republish"[^>]*data-value="allowed"/, 'the admin can answer the rights question');
  assert.match(detail, /data-a="rights-save"/, 'and save the answers');
  assert.match(detail, /data-a="rights-pick"[^>]*data-field="automation_allowed"/, 'automation has its own override control');
  assert.ok(detail.includes(t('rdAutoEffective', { value: t('rdAnswerDenied'), origin: t('rdAutoFromSource') })) || detail.includes(t('rdAutoEffective', { value: t('rdAnswerAllowed'), origin: t('rdAutoFromSource') })) || detail.includes(t('rdAutoEffective', { value: t('rdAnswerAllowed'), origin: t('rdAutoFromArticle') })), 'the effective value and where it comes from');
  const overview = String(rp.overviewPage({ ...c, ops: { articles: {}, queue: {} }, sources: [], next: [{ id: 'A', title: 'Title', language: 'en', topic: 'x', level: 'B2', reading_time_seconds: 60, rights_level: 'denied' }], failedJobs: 0 }).markup);
  assert.ok(overview.includes(t('rdRightsDeny')), 'Next in review shows the same rights label as the queue');
  const cleared = String(rp.articlePage({ ...c, article: article({ status: 'needs_review' }), sets: [], view }).markup);
  assert.doesNotMatch(cleared, /data-action="publish"[^>]*disabled/, 'cleared rights leave Publish enabled');
  assert.ok(!cleared.includes(t('rdBlockedTitle')), 'no refusal when nothing refuses');
  const queue = String(rp.queuePage({ ...c, tab: 'review', items: [{ id: 'A', title: 'Title', language: 'en', topic: 'fables', level: 'B2', word_count: 134, reading_time_seconds: 45, status: 'needs_review', created_at: NOW, source_name: 'Gutenberg', rights_level: 'unknown', target_count: 5 }], next: null, counts: null, view }).markup);
  assert.ok(queue.includes(t('rdColTargets')) && queue.includes(t('rdColRights')), 'the review queue heads Targets and Rights');
  assert.ok(queue.includes('Gutenberg'), 'the row meta names the source');
  assert.ok(queue.includes(t('rdRightsUnknown')), 'the row draws the rights pill');
  const onlyPublished = String(rp.articlePage({ ...c, article: article({ status: 'needs_review' }), sets: [], view }).markup);
  assert.match(onlyPublished, /data-a="set-generate"[^>]*disabled/, 'questions are generated for a published article only');
  const approvedSet = String(rp.setPage({ ...c, set: set({ status: 'approved' }), article: article(), view: { busy: false } }).markup);
  assert.match(approvedSet, /data-a="question-decide"[^>]*disabled/, 'a decided set is frozen');
  const vocab = String(cp.collectionPage({ ...c, detail: { record: record('vocabulary', { status: 'draft', actions: ['publish'] }), entries: [], sources: [] }, form: { rights: 'licensed', completeness: 'complete', attested: false }, view: {} }).markup);
  assert.match(vocab, /data-a="collection-publish"[^>]*disabled/, 'vocabulary publishing waits for the attestation');
  assert.ok(vocab.includes(t('ctGateText')), 'the admission gate is explained');
}
console.error = realError;

/* ---- 3. every new place mounts for an admin, asking only for guarded endpoints -------------------- */
const matrix = fs.readFileSync('tests/test_admin_authorization_matrix.py', 'utf8');
const guarded = [...matrix.matchAll(/\("(GET|POST|PUT|DELETE)", "(\/api\/[^"]+)"\)/g)].map(([, method, route]) => ({ method, pattern: new RegExp(`^${route.replace(/\{[^}]+\}/g, '[^/]+')}$`) }));
assert.ok(guarded.length > 40);
const isGuarded = (request) => guarded.some((g) => g.method === request.method && g.pattern.test(request.path));
const screen = (await import('../static/orena/screens/admin/screen.js')).default;
const paramsFor = { adminUser: 'U', adminArticle: 'A', adminSet: 'S', adminSource: 'SRC', adminBook: 'B', adminMediaItem: 'M', adminCollection: 'V', adminJob: 'J' };
for (const routeId of model.ADMIN_ROUTE_IDS.filter((id) => id !== 'admin' && model.areaOf(id) !== 'ai')) {
  requests.length = 0;
  const element = new Fake();
  const ctx = { route: ROUTES.find((route) => route.id === routeId), params: { id: paramsFor[routeId] }, query: new URLSearchParams(), context: { isAdmin: true, name: 'Admin', user: { email: 'a@x.io' } }, href, go() {}, replace() {}, setCrumb() {}, isCurrent: () => true };
  const cleanup = await screen(element, ctx);
  await new Promise((resolve) => setTimeout(resolve, 40));
  assert.equal(typeof cleanup, 'function', `${routeId}: an admin gets the page`);
  const page = element.querySelector('[data-part="page"]').innerHTML;
  assert.ok(page.includes('class="a-page'), `${routeId}: the page is drawn (${page.slice(0, 120)})`);
  for (const request of requests) {
    assert.ok(/^\/api\/(admin|media\/admin)\//.test(request.path), `${routeId}: ${request.path} is an admin route`);
    assert.ok(isGuarded(request), `${routeId}: ${request.method} ${request.path} is in tests/test_admin_authorization_matrix.py (anonymous 401, learner 403)`);
  }
  cleanup();
}
assert.deepEqual(unhandled, [], 'no page left a rejected promise behind');

/* ---- 4. the writes the new areas make are the server's guarded ones -------------------------------- */
requests.length = 0;
fixtureFor = () => ({ body: { ok: true, id: 'J', items: [], results: [{ status: 'ok', title: 'B', chapter_count: 2, book_id: 'B' }] } });
{
  await reading.changeArticle(adminApi, 'A', 'publish');
  await reading.changeArticle(adminApi, 'A', 'reject', 'because');
  await reading.saveArticle(adminApi, 'A', { title: 'x', body: 'b', topic: '', reviewed_level: null }, { title: 'y', reviewed_level: 'B1' });
  await reading.submitContent(adminApi, { kind: 'text', text: 'hello' });
  await reading.loadQueue(adminApi, { tab: 'review' });
  await reading.loadSets(adminApi, 'A');
  await adminApi.readingGenerateSet('A', 'vi');
  await adminApi.readingSet('S');
  await adminApi.readingDecideQuestion('S', 'Q1', 'approve');
  await adminApi.readingSetTransition('S', 'approved');
  await adminApi.readingDiscardSet('S');
  await adminApi.readingAddTarget('A', { text: 'x' });
  await adminApi.readingSetRights('A', { can_republish: true });
  await adminApi.readingDecideTarget('A', 'T1', true);
  await adminApi.readingReorderTargets('A', ['T1']);
  await adminApi.readingSetSourceState('SRC', 'paused');
  await adminApi.readingCreateSource(imports.sourceBody({ name: 'S', url: 'https://s.org' }));
  await adminApi.readingRetryJob('J');
  await adminApi.readingJob('J');
  await imports.loadJobs(adminApi, { status: 'failed' });
  await imports.loadHistory(adminApi, { kind: 'book' });
  await imports.importBooks(adminApi, [{ file: new File(['x'], 'a.epub'), state: 'to_import' }], 'en');
  await imports.checkMediaUrls(adminApi, ['https://x.org/v'], 'en');
  await imports.importMedia(adminApi, [{ url: 'https://x.org/v', state: 'ready' }, { file: new File(['x'], 'a.mp3'), state: 'to_import' }], 'en');
  await imports.previewVocabulary(adminApi, [new File(['a,b'], 'w.csv')]);
  await imports.importVocabulary(adminApi, { files: [new File(['a,b'], 'w.csv')], metadata: { title: 'W', language: 'en' }, mappings: {} });
  for (const intent of ['archive', 'restore']) await content.applyLifecycle(adminApi, 'book', 'B', intent);
  for (const intent of ['unpublish', 'archive', 'republish']) await content.applyLifecycle(adminApi, 'media', 'M', intent);
  await content.applyLifecycle(adminApi, 'media', 'M', 'reprocess');
  for (const intent of ['unpublish', 'archive', 'restore']) await content.applyLifecycle(adminApi, 'vocabulary', 'V', intent);
  await content.publishCollection(adminApi, 'V', { rights: 'licensed', completeness: 'complete', attested: true });
  await content.loadContent(adminApi, { kind: 'book' });
  await content.contentCounts(adminApi);
  assert.ok(requests.length > 35, `the new areas exercised the endpoints (${requests.length})`);
  for (const request of requests) assert.ok(isGuarded(request), `${request.method} ${request.path} is in the authorization matrix`);
  const publishCall = requests.filter((r) => r.path === '/api/admin/console/content/vocabulary/V/publish');
  assert.equal(publishCall.length, 1);
  await assert.rejects(() => content.applyLifecycle(adminApi, 'book', 'B', 'publish'), /Unknown lifecycle/, 'an intent a kind does not have is refused, not guessed');
}

console.log(`Orena admin areas: shared Reading/Imports/Content/tray rules, ${ROUTES.filter((r) => r.admin).length} admin routes mounting for an admin on guarded endpoints only (${guarded.length} in the matrix), 3 languages x pages: PASS`);
