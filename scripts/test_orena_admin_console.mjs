import assert from 'node:assert/strict';
import fs from 'node:fs';
import { adminCopy } from '../static/orena/admin/copy.js';
import { chip, tone, table } from '../static/orena/admin/format.js';
import { columnChart, barList, niceCeiling } from '../static/orena/admin/charts.js';
import { overviewView, attentionLink } from '../static/orena/admin/overview.js';
import {
  routingView,
  runtimeView,
  providersView,
  capabilityKind,
  credentialState,
  mergeProviders,
  modelOptions,
  servicesView,
} from '../static/orena/admin/ai.js';
import { usersSummaryView, accountsTable, accountDetailView, retentionView } from '../static/orena/admin/users.js';
import { contentTable, contentDetailView, imageSource } from '../static/orena/admin/content.js';
import {
  runQueue,
  bookOutcome,
  mediaOutcome,
  failureText,
  validateVocabulary,
  defaultCollectionTitle,
  historyView,
  booksView,
  mediaView,
  vocabularyView,
  renderImports,
} from '../static/orena/admin/imports.js';
import { readinessView, systemView, operationsView, activationView, impactView } from '../static/orena/admin/operations.js';
import { sectionFrom, sectionHref, frameView, envView, hashParams, badgeCounts, SECTIONS } from '../static/orena/admin/shell.js';

const read = (path) => fs.readFileSync(path, 'utf8');
const en = adminCopy.en;
const zh = adminCopy.zh;
const href = sectionHref;

// ---- copy: one vocabulary, both interface languages ----------------------
assert.deepEqual(Object.keys(en).sort(), Object.keys(zh).sort(), 'EN and ZH admin copy carry the same keys');
const placeholders = (text) => [...String(text).matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
for (const key of Object.keys(en)) {
  assert.ok(String(en[key]).trim(), `en.${key} is empty`);
  assert.ok(String(zh[key]).trim(), `zh.${key} is empty`);
  assert.deepEqual(placeholders(zh[key]), placeholders(en[key]), `${key}: EN and ZH use the same placeholders`);
}

/* Everything the server can say has words in both languages. The lists are
   read from the Python that produces them, so a new kind, capability or
   indicator cannot reach the console without a label. */
const metricsSource = read('writing_coach/admin_metrics.py');
const attentionKinds = [...new Set([...metricsSource.matchAll(/"kind": "([a-z_]+)"/g)].map((match) => match[1]))];
assert.ok(attentionKinds.length >= 14, 'attention kinds were read from admin_metrics.py');
for (const kind of attentionKinds) {
  for (const copy of [en, zh]) {
    assert.ok(copy[`attention_${kind}`], `attention kind "${kind}" has a title`);
    assert.ok(copy[`attention_${kind}_detail`], `attention kind "${kind}" has a detail`);
  }
}
const capabilities = [...read('writing_coach/ai/capabilities.py').matchAll(/_definition\(\s*"([a-z_]+)"/g)].map((match) => match[1]);
assert.ok(capabilities.length >= 10, 'capability keys were read from the registry');
for (const key of capabilities) {
  assert.ok(en[`cap_${key}`] && zh[`cap_${key}`], `capability "${key}" is named in both languages`);
  assert.ok(en[`capHint_${key}`] && zh[`capHint_${key}`], `capability "${key}" is explained in both languages`);
}
const indicators = [...read('writing_coach/readiness_summary.py').matchAll(/_indicator\("([a-z_]+)"/g)].map((match) => match[1]);
for (const name of new Set(indicators)) assert.ok(en[`indicator_${name}`] && zh[`indicator_${name}`], `indicator "${name}" is named`);
const epubCategories = [...read('writing_coach/epub_import.py').matchAll(/EpubImportError\("([a-z_]+)"/g)].map((match) => match[1]);
for (const code of new Set([...epubCategories, 'import_failed', 'storage_failed', 'reading_library_unavailable'])) {
  assert.ok(en[`error_${code}`] && zh[`error_${code}`], `book import error "${code}" is explained`);
}
const stageBlock = read('writing_coach/admin_content.py').split('_BOOK_STAGES = {')[1].split('}')[0];
const stages = [...stageBlock.matchAll(/": "([a-z]+)",/g)].map((match) => match[1]);
assert.ok(stages.length >= 5, 'book import stages were read from admin_content.py');
for (const stage of new Set([...stages, 'source', 'persistence', 'validation'])) {
  assert.ok(en[`stage_${stage}`] && zh[`stage_${stage}`], `import stage "${stage}" is named`);
}
const measures = [...read('writing_coach/persistence/admin_repository.py').matchAll(/\("([a-z_]+)", [A-Z]\w+, [A-Z]\w+\.language_code/g)].map((match) => match[1]);
for (const measure of new Set([...measures, 'reading_checks'])) assert.ok(en[`measure_${measure}`] && zh[`measure_${measure}`], `measure "${measure}" is named`);
const services = [...read('writing_coach/admin_console_api.py').matchAll(/"([a-z_]+)": (?:engine|attached)\(/g)].map((match) => match[1]);
for (const service of new Set([...services, 'transcript_fallback'])) assert.ok(en[`service_${service}`] && zh[`service_${service}`], `service "${service}" is named`);
const statuses = [
  'published', 'draft', 'archived', 'ready', 'processing', 'queued', 'failed', 'duplicate', 'skipped', 'healthy',
  'degraded', 'provider_failure', 'no_data', 'configured', 'not_configured', 'enabled', 'disabled', 'reserved',
  'deterministic', 'active', 'idle', 'no_activity', 'deleted', 'insufficient', 'deferred', 'unavailable', 'selected',
  'demo', 'invalid', 'mismatch', 'unreadable', 'not_applicable', 'not_granted', 'human_gated', 'index_missing',
  'index_corrupt', 'index_unreadable', 'not_active', 'fallback', 'transcript_missing', 'pending_review', 'imported',
  'legacy', 'capability', 'ok', 'off', 'unknown', 'to_import',
];
for (const status of statuses) assert.ok(en[`status_${status}`] && zh[`status_${status}`], `status "${status}" is named`);

// ---- states are words with a glyph, coloured only through a tone ----------
assert.equal(tone('failed'), 'bad');
assert.equal(tone('published'), 'ok');
assert.equal(tone('degraded'), 'warn');
assert.equal(tone('processing'), 'info');
assert.equal(tone('not_configured'), 'neutral');
const failedChip = chip('failed', en);
assert.match(failedChip, /data-tone="bad"/);
assert.match(failedChip, />✕</, 'a state carries a glyph, not colour alone');
assert.match(failedChip, /Failed/);
assert.doesNotMatch(failedChip, /style=/, 'a chip never carries inline colour');

// ---- charts ------------------------------------------------------------------
assert.equal(niceCeiling(7), 10);
assert.equal(niceCeiling(0), 1);
const series = Array.from({ length: 30 }, (_, index) => ({ date: `2026-08-${String(index + 1).padStart(2, '0')}`, value: index === 20 ? 6 : index % 3 }));
const chart = columnChart({ title: en.chartActive, series, t: en, ui: 'en' });
assert.equal((chart.match(/class="ac-chart__column"/g) || []).length, 30, 'one column per day');
assert.equal((chart.match(/class="ac-chart__peak"/g) || []).length, 1, 'only the peak is labelled');
assert.equal((chart.match(/<tr><td>/g) || []).length, 30, 'every value is also in the data table');
assert.doesNotMatch(chart, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i, 'charts take colour from the stylesheet only');
const flat = columnChart({ title: en.chartActive, series: series.map((point) => ({ ...point, value: 0 })), t: en, ui: 'en' });
assert.match(flat, new RegExp(en.chartEmpty));
assert.doesNotMatch(flat, /ac-chart__bar/, 'an empty month draws no bars');
const bars = barList({ ui: 'en', rows: [{ label: 'Writing', value: 4 }, { label: 'Reading', value: 2 }] });
assert.match(bars, /width:100%/);
assert.match(bars, /width:50%/);

// ---- overview: real numbers, or an honest absence --------------------------
const unavailable = overviewView({
  generated_at: '2026-09-18T10:00:00Z',
  accounts: { available: false },
  activity: { available: false },
  languages: { available: false },
  content: { published: 3, book: { published: 3, archived: 0 }, media: { published: 0, curated: 0, imported: 0, transcript_missing: 0 }, vocabulary: { published: 0, draft: 0 }, sources: { book: 'ok', media: 'ok', vocabulary: 'unavailable' } },
  imports: { available: false },
  ai: { runtime_mode: 'legacy', capabilities: {}, providers: {}, health: {} },
  attention: [],
}, en, 'en', href);
assert.match(unavailable, new RegExp(en.accountsUnavailable), 'no accounts means no account numbers');
assert.match(unavailable, /ac-kpi__value">—</, 'an unavailable figure is a dash, not zero');
assert.doesNotMatch(unavailable, /Active learners[^<]*<\/span><strong class="ac-kpi__value">0/, 'active learners are never invented as zero');
assert.doesNotMatch(unavailable, /data-chart/, 'no chart is drawn without its data');

const attention = [
  { kind: 'legacy_route_fallback', severity: 'warning', section: 'ai', provider: 'gemini' },
  { kind: 'transcript_missing', severity: 'warning', section: 'content', count: 2 },
  { kind: 'persistence_not_authoritative', severity: 'critical', section: 'operations' },
];
const live = overviewView({
  generated_at: '2026-09-18T10:00:00Z',
  accounts: { available: true, total: 12, admins: 1, new_7d: 3, new_30d: 5, registrations: series.map((point) => ({ date: point.date, count: point.value })) },
  activity: { available: true, active_7d: 4, active_30d: 9, new_7d: 1, returning_7d: 3, daily: series.map((point) => ({ date: point.date, learners: point.value })), domains: [{ domain: 'writing', events: 7, learners: 3 }], languages: [] },
  languages: { available: true, profiles: [{ language: 'zh', learners: 7 }], active_30d: [{ language: 'zh', learners: 4 }] },
  content: { published: 11, book: { published: 4, archived: 1 }, media: { published: 7, curated: 7, imported: 0, transcript_missing: 2 }, vocabulary: { published: 0, draft: 1 }, sources: { book: 'ok', media: 'ok', vocabulary: 'ok' } },
  imports: { available: true, failed_7d: 0, last_import_at: null },
  ai: { runtime_mode: 'legacy', capabilities: { configurable: 7, configured: 1, enabled: 1 }, providers: { configured: 1, total: 5 }, health: { degraded: 2 }, provider_names: { gemini: 'Gemini API' } },
  attention,
}, en, 'en', href);
assert.match(live, /ac-kpi__value">4</, 'active learners come from the payload');
assert.match(live, /Gemini API/, 'provider names come from the registry payload');
assert.match(live, /#\/admin\?id=content&amp;kind=media&amp;status=issues/, 'a problem links to the filter that shows it');
assert.match(live, /data-tone="bad"/, 'a critical problem turns the attention figure');
assert.equal((live.match(/data-chart/g) || []).length, 2, 'registrations and active learners are charted');
assert.deepEqual(attentionLink({ kind: 'import_failed' }), { status: 'failed' });

// ---- AI & Models: the registry decides the rows ------------------------------
const config = {
  capabilities: [
    { key: 'writing_evaluator', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, explicit_config_exists: true, config: { enabled: true, provider: 'groq', model: 'llama-x', backup_provider: null, backup_model: null } },
    { key: 'future_capability', operation: 'structured_text_generation', implemented: true, provider_backed: true, configurable: true, explicit_config_exists: false, config: null },
    { key: 'writing_linguistic', operation: 'deterministic', implemented: true, provider_backed: false, configurable: false, explicit_config_exists: false, config: null },
    { key: 'speech_asr', operation: 'speech_recognition', implemented: false, provider_backed: true, configurable: false, explicit_config_exists: false, config: null },
  ],
  providers: [
    { id: 'ollama', name: 'Ollama', kind: 'local', secret_mode: 'none', supported_operations: ['structured_text_generation'], server_configured: true },
    { id: 'groq', name: 'Groq API', kind: 'cloud', secret_mode: 'server-managed', supported_operations: ['structured_text_generation'], server_configured: false },
  ],
};
const catalog = {
  providers: [
    { id: 'ollama', configured: true, models: ['gemma3:12b'], configuration: { credential_env: null, credential_source: 'not_configured', endpoint_url: 'http://host.docker.internal:11434' } },
    { id: 'groq', configured: false, models: [], api_key: 'sk-SHOULD-NEVER-RENDER', configuration: { credential_env: 'GROQ_API_KEY', credential_source: 'encrypted_server_store', endpoint_url: 'https://api.groq.com/openai/v1' } },
  ],
};
assert.equal(capabilityKind(config.capabilities[2]), 'deterministic');
assert.equal(capabilityKind(config.capabilities[3]), 'reserved');
const providers = mergeProviders(config, catalog);
assert.equal(credentialState(providers[0]), 'not_required');
assert.equal(credentialState(providers[1]), 'unreadable', 'a stored key the server cannot use is named as such');
const state = { config, providers, operations: { by_capability: [{ capability: 'writing_evaluator', health_state: 'degraded', evidence_count: 4, failure_rate_percent: 50, avg_latency_ms: 2500 }] }, tests: new Map(), editing: null, draft: {}, catalogState: 'ready', providerTests: new Map(), runtime: { ai: { credential_store: 'not_configured' } } };
const routing = routingView(state, en, 'en');
assert.match(routing, /data-capability="future_capability"/, 'a capability added to the registry appears without a UI change');
assert.match(routing, /future capability/, 'an unnamed capability falls back to its key');
assert.equal((routing.match(/data-ac-action="edit"/g) || []).length, 2, 'only configurable capabilities can be edited');
assert.equal((routing.match(/data-ac-action="test"/g) || []).length, 1, 'only a saved, enabled route can be tested');
assert.match(routing, /Local \(deterministic\)/);
assert.match(routing, /Reserved/);
assert.match(routing, /Degraded/);
const providerMarkup = providersView({ ...state, providerForm: 'groq', providerMessage: '', confirmRemove: null, expanded: null }, en, 'en');
assert.doesNotMatch(providerMarkup, /sk-SHOULD-NEVER-RENDER/, 'a provider payload field is never echoed');
assert.match(providerMarkup, /type="password"/, 'a key is typed into a write-only field');
assert.match(providerMarkup, new RegExp(en.storeUnavailable.slice(0, 30)), 'saving a key without the encryption key is explained, not attempted');
const loading = modelOptions(providers[0], '', en, 'loading');
assert.equal(loading.disabled, true);
const empty = modelOptions(providers[1], '', en, 'ready');
assert.equal(empty.disabled, true);
assert.equal(empty.note, en.noModels);
const kept = modelOptions(providers[0], 'old-model', en, 'ready');
assert.match(kept.html, /old-model/, 'a saved model missing from the catalog stays visible');
const legacy = runtimeView({ ai: { learner_runtime_mode: 'legacy', legacy_selection: { source: 'saved', provider: 'gemini', model: 'gemini-x', provider_configured: false, effective: { provider: 'ollama', model: 'qwen3:8b', fallback: true } } } }, en);
assert.match(legacy, /Fallback/);
assert.match(legacy, /Human-gated/);
assert.match(legacy, /falls back to the local default|fall back to the local default/);

// ---- users: masked in the list, operational in the detail -------------------
const list = accountsTable({ available: true, items: [{ id: 'u1', display_name: 'Ana', email_masked: 'an•••@example.com', role: 'admin', joined_at: '2026-09-01T00:00:00Z', last_active_at: null, languages: ['zh'], level: null, status: 'no_activity' }], total: 1, limit: 25, offset: 0 }, en, 'en');
assert.match(list, /an•••@example\.com/);
assert.match(list, /No activity/);
assert.match(list, /Not recorded/, 'level is not invented');
assert.match(list, /1–1 of 1/);
const detail = accountDetailView({ id: 'u1', display_name: 'Ana', email: 'ana@example.com', role: 'user', status: 'active', joined_at: '2026-09-01T00:00:00Z', profiles: [{ language: 'zh', goal: 'exam', style: 'guided', support_language: 'vi', updated_at: '2026-09-02T00:00:00Z' }], activity: [{ measure: 'writing_submissions', language: 'zh', count: 3, last_at: null }] }, en, 'en');
assert.match(detail, /ana@example\.com/);
assert.match(detail, /Writing submissions/);
assert.match(detail, new RegExp(en.detailAudited));
assert.match(detail, /D-055/, 'the absence of account actions is explained');
assert.doesNotMatch(detail, /data-ac-action|suspend/i, 'no account action exists without a backend contract');
const insufficient = retentionView([{ days: 7, eligible_learners: 3, returned_learners: 2, state: 'insufficient', rate_percent: null, minimum_sample: 20 }], en, 'en');
assert.doesNotMatch(insufficient, /%/, 'a small sample never shows a rate');
const ready = retentionView([{ days: 7, eligible_learners: 40, returned_learners: 10, state: 'ready', rate_percent: 25, minimum_sample: 20 }], en, 'en');
assert.match(ready, /25% of 40/);
assert.match(usersSummaryView({ available: false }, en, 'en'), new RegExp(en.accountsUnavailable));

// ---- content: identity kept, actions only where they exist ------------------
const records = {
  items: [
    { kind: 'book', id: 'b1', title: 'Book', subtitle: 'Author', language: 'en', status: 'published', origin: 'imported', updated_at: '2026-09-10T00:00:00Z', image: '/api/reading/library/books/b1/cover', facts: { chapter_count: 3, word_count: 900 }, issues: [], actions: ['preview', 'archive'] },
    { kind: 'media', id: 'm1', title: 'Clip', subtitle: 'YouTube', language: 'zh', status: 'published', origin: 'imported', updated_at: null, image: 'http://insecure.example/x.jpg', facts: { duration_ms: 61000, transcript: 'missing', segment_count: 0 }, issues: ['transcript_missing'], actions: ['preview', 'reprocess'] },
    { kind: 'vocabulary', id: 'v1', title: 'HSK 1', subtitle: 'HSK', language: 'zh', status: 'draft', origin: 'imported', updated_at: null, image: '', facts: { item_count: 40 }, issues: ['pending_review'], actions: ['preview', 'publish'] },
  ],
  total: 3, limit: 25, offset: 0, sources: { book: 'ok', media: 'ok', vocabulary: 'ok' },
};
const contentMarkup = contentTable(records, en, 'en');
assert.equal((contentMarkup.match(/data-ac-intent="archive"/g) || []).length, 1);
assert.equal((contentMarkup.match(/data-ac-intent="publish"/g) || []).length, 1);
assert.equal((contentMarkup.match(/data-ac-intent="reprocess"/g) || []).length, 1);
assert.doesNotMatch(contentMarkup, /delete|unpublish/i, 'no action without a backend contract');
assert.match(contentMarkup, /Waiting for review/);
assert.match(contentMarkup, /<button type="button" class="ac-rowlink" data-ac-open="book:b1" lang="en">Book<\/button>/, 'the title opens the preview, so a narrow screen never has to scroll to the actions');
assert.match(contentMarkup, /No transcript/);
assert.doesNotMatch(contentMarkup, /insecure\.example/, 'only https or same-origin images are requested');
assert.equal(imageSource('javascript:alert(1)'), '');
assert.equal(imageSource('/api/media/files/x?variant=thumb'), '/api/media/files/x?variant=thumb');
const mediaDetail = contentDetailView({ record: records.items[1], transcript: { segment_count: 0, segments: [] }, source: { url: 'https://www.youtube.com/watch?v=abcdefghijk', license: 'x', review_status: 'checked' }, learner_link: '#/encounter?id=media%3Am1&intent=follow' }, en, 'en', 'reprocess');
assert.match(mediaDetail, new RegExp(en.noTranscript));
assert.match(mediaDetail, /data-ac-do="reprocess"/, 'reprocessing asks for confirmation first');
const vocabularyDetail = contentDetailView({ record: records.items[2], entries: [], entry_total: 0, sources: [], admission: { rights_status: 'licensed', completeness: 'complete' } }, en, 'en');
assert.match(vocabularyDetail, /name="attested"(?![^>]*checked)/, 'publication starts unattested');

// ---- imports: one item never holds up the rest -------------------------------
const snapshots = [];
const queue = [{ name: 'a' }, { name: 'b' }, { name: 'c' }];
await runQueue(queue, async (item) => {
  if (item.name === 'b') throw Object.assign(new Error('boom'), { category: 'storage_failed' });
  return { state: 'published' };
}, (items) => snapshots.push(items.map((item) => item.state).join(',')));
assert.deepEqual(queue.map((item) => item.state), ['published', 'failed', 'published'], 'a failure fails only its own item');
assert.ok(snapshots.includes('published,processing,queued'), 'items run one at a time');
assert.equal(queue[1].code, 'storage_failed');
assert.deepEqual(bookOutcome({ status: 'error', category: 'malformed_epub', stage: 'parse' }), { state: 'failed', code: 'malformed_epub', stage: 'parse' });
assert.equal(bookOutcome({ status: 'duplicate', title: 'X', book_id: 'b' }).state, 'duplicate');
assert.equal(mediaOutcome({ status: 'error', detail: 'This address is not a supported media file.' }).stage, 'source');
assert.equal(failureText({ code: 'malformed_epub', stage: 'parse' }, en), 'Failed at EPUB parsing: The EPUB structure could not be read.');
assert.match(failureText({ code: 'malformed_epub', stage: 'parse' }, zh), /EPUB 解析/);
assert.equal(failureText({ code: 'source', stage: 'source', message: 'The media file could not be read.' }, en), 'Failed at reading the source: The media file could not be read.');
assert.equal(failureText({ code: 'source', stage: 'source', message: 'The media file could not be read.' }, zh), '在「读取来源」失败：The media file could not be read.（服务器原文）', 'a Chinese line keeps Chinese punctuation and marks the server’s English as quoted');
assert.equal(historyView({ available: true, total: 1, limit: 20, offset: 0, items: [{ kind: 'vocabulary', source: 'a.csv', created_at: null, status: 'ready', result: { title: '核心词', imported: 2, duplicates: 0, skipped: 0 }, error: null, origin: 'receipt' }] }, { kind: '', status: '' }, zh, 'zh').includes('核心词：导入 2'), true, 'a Chinese result joins with a full-width colon');
assert.equal(defaultCollectionTitle('toeic_core-words.csv'), 'Toeic core words');
const problems = validateVocabulary({ files: [{ name: 'a.csv' }], previews: [{ filename: 'a.csv' }], mappings: {}, metadata: { title: '', publish: true, attested: false } }, en);
assert.deepEqual(problems, [en.validationTitle, 'a.csv: map a column to Term.', en.validationAttest]);
const history = historyView({ available: true, total: 2, limit: 20, offset: 0, summary: { total: 2, failed: 1 }, items: [
  { kind: 'book', source: 'broken.epub', created_at: '2026-09-17T00:00:00Z', status: 'failed', result: {}, error: { stage: 'parse', code: 'malformed_epub', message: '' }, origin: 'receipt' },
  { kind: 'book', source: 'Older', created_at: '2026-09-01T00:00:00Z', status: 'published', result: { title: 'Older', chapter_count: 2 }, error: null, origin: 'catalog' },
] }, { kind: '', status: '' }, en, 'en');
assert.match(history, /Failed at EPUB parsing/, 'history says where an import failed');
assert.match(history, new RegExp(en.beforeHistory));
assert.match(history, new RegExp(`${en.colSource}</th><th[^>]*>${en.colStatus}<`), 'state follows the source, so it is in view before any sideways scroll');
assert.match(historyView({ available: false }, { kind: '', status: '' }, en, 'en'), new RegExp(en.historyUnavailable));
const mediaFlow = mediaView({ urls: '', language: 'zh', running: false, checking: false, advanced: true, items: [{ url: 'https://www.youtube.com/watch?v=abcdefghijk', state: 'ready', title: 'Clip', has_transcript: false, segment_count: 0, tags: [] }] }, en, 'en');
assert.match(mediaFlow, /HSK7-9/, 'levels offered are the learning language’s own scale');
assert.doesNotMatch(mediaFlow, />C2</);
assert.match(mediaFlow, /No transcript/);
const checkedFlow = mediaView({ urls: '', language: 'en', running: false, checking: false, advanced: true, items: [
  { url: 'https://www.youtube.com/watch?v=abcdefghijk', state: 'ready', title: 'Clip', has_transcript: true, segment_count: 0, tags: [] },
  { url: 'https://example.com/page.html', state: 'failed', code: 'source', stage: 'source', message: 'This address is not a supported media file.' },
] }, en, 'en');
assert.doesNotMatch(checkedFlow, new RegExp(en.transcriptLines.replace('{count}', '0')), 'a transcript the preview did not count is not reported as empty');
assert.match(checkedFlow, new RegExp(en.transcriptAtImport), 'the count is deferred to the import that reads it');
assert.doesNotMatch(checkedFlow, /No transcript/, 'a source that could not be read makes no transcript claim');
assert.equal(checkedFlow.split('https://example.com/page.html').length - 1, 1, 'a source that could not be read is named once');
assert.doesNotMatch(checkedFlow, /——/, 'an unread source has no level or topic to show');
assert.match(checkedFlow, /data-ac-remove="1"/, 'a source that could not be read can be taken off the list');
assert.deepEqual(mediaOutcome({ status: 'ok', media_id: 'youtube-x', has_transcript: true, segment_count: 12 }), { state: 'published', contentId: 'youtube-x', has_transcript: true, segment_count: 12 });
const importedFlow = mediaView({ urls: '', language: 'en', running: false, checking: false, advanced: true, items: [
  { url: 'https://www.youtube.com/watch?v=abcdefghijk', state: 'published', title: 'Clip', level: 'A1', topic: 'animals', tags: [], has_transcript: true, segment_count: 12 },
  { file: {}, name: 'tone.wav', size: 10, state: 'published', has_transcript: false, segment_count: 0 },
] }, en, 'en');
assert.match(importedFlow, new RegExp(en.transcriptLines.replace('{count}', '12')), 'after the import the stored transcript is counted');
assert.match(importedFlow, /No transcript/, 'a stored file without a transcript says so');
assert.doesNotMatch(importedFlow, /A1animals/, 'level and topic are separate facts');
const vocabularyFlow = vocabularyView({ files: [{ name: 'core.csv' }], previews: [{ filename: 'core.csv', headers: ['word', 'meaning'], row_count: 2, format: 'csv', sample: [{ word: 'agenda', meaning: 'chương trình' }], warnings: [] }], mappings: { 'core.csv': { term: 'word' } }, metadata: { title: 'Core', language: 'en', meaning_language: 'vi', framework: '', level: '', topic: '', collection_id: '', rights_status: '', completeness: 'unknown', publish: false, attested: false }, errors: [], results: null, running: false, previewing: false }, en, 'en');
assert.match(vocabularyFlow, /<details class="ac-advanced">/, 'stable IDs and rights sit under Advanced');
assert.match(vocabularyFlow, /chương trình/, 'sample rows keep their diacritics');
const importedVocabulary = vocabularyView({ files: [{ name: 'core.csv' }], previews: [{ filename: 'core.csv', headers: ['word'], row_count: 1, format: 'csv', sample: [], warnings: [] }], mappings: { 'core.csv': { term: 'word' } }, metadata: { title: 'Core', language: 'en', meaning_language: 'vi', framework: '', level: '', topic: '', collection_id: '', rights_status: '', completeness: 'unknown', publish: false, attested: false }, errors: [], results: { items: [{ filename: 'core.csv', status: 'imported', imported: 1, duplicates: 0, skipped: 0 }], collection: { catalog_status: 'pending_review' } }, running: false, previewing: false }, en, 'en');
assert.match(importedVocabulary, /<button type="submit"[^>]*disabled/, 'an imported batch is not sent twice by a second click');
const chosenBooks = booksView({ items: [{ name: 'garden.epub', size: 2048, state: 'to_import' }], language: 'en', running: false }, en, 'en');
assert.match(chosenBooks, new RegExp(en.status_to_import), 'a chosen file says it is still to be imported');
assert.doesNotMatch(chosenBooks, /data-tone="ok"/, 'nothing reads as done before the import has run');
assert.match(chosenBooks, new RegExp(en.filesChosen.replace('{count}', '1')), 'the chooser counts the chosen files itself, so a repaint never reads as "no file"');
assert.match(booksView({ items: [], language: 'en', running: false }, en, 'en'), new RegExp(en.noFilesChosen));

/* A section's delegated handlers read the markup the section itself wrote, so
   they are checked against that markup: a small tree built from the rendered
   HTML, with `closest` and `querySelector` over real attributes. */
const VOID_TAGS = new Set(['input', 'img', 'br', 'hr', 'meta', 'link', 'source', 'col', 'wbr']);
class FakeNode {
  constructor(tagName = 'div', attributes = {}, parent = null) {
    Object.assign(this, { tagName, attributes, parent, children: [], listeners: {}, html: '' });
  }
  set innerHTML(html) {
    this.html = String(html);
    this.children = [];
    const stack = [this];
    for (const [, closing, tag, raw] of this.html.matchAll(/<(\/?)([a-zA-Z][\w-]*)((?:\s+[\w-]+(?:="[^"]*")?)*)\s*\/?>/g)) {
      const name = tag.toLowerCase();
      if (closing) {
        const at = stack.map((node) => node.tagName).lastIndexOf(name);
        if (at > 0) stack.length = at;
        continue;
      }
      const attributes = Object.fromEntries([...raw.matchAll(/([\w-]+)(?:="([^"]*)")?/g)].map(([, key, value]) => [key, value ?? '']));
      const node = new FakeNode(name, attributes, stack.at(-1));
      stack.at(-1).children.push(node);
      if (!VOID_TAGS.has(name)) stack.push(node);
    }
  }
  get innerHTML() {
    return this.html;
  }
  get name() {
    return this.attributes.name;
  }
  get type() {
    return this.attributes.type;
  }
  get dataset() {
    return Object.fromEntries(Object.entries(this.attributes)
      .filter(([key]) => key.startsWith('data-'))
      .map(([key, value]) => [key.slice(5).replace(/-(\w)/g, (_, letter) => letter.toUpperCase()), value]));
  }
  /* Compound selectors (`tag[attr="value"]`), descendant combinators and
     selector lists - the forms the console's own code uses. */
  simple(compound) {
    const [, tag, rest] = compound.match(/^([a-z]*)((?:\[[^\]]+\])*)$/) || [];
    if (tag === undefined || (tag && tag !== this.tagName)) return false;
    return [...rest.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].every(([, key, value]) => key in this.attributes && (value === undefined || this.attributes[key] === value));
  }
  matches(selector) {
    return selector.split(',').some((group) => {
      const parts = group.trim().match(/[a-z]*(?:\[[^\]]*\])+|[a-z]+/g) || [];
      if (!parts.length || !this.simple(parts.at(-1))) return false;
      let node = this.parent;
      for (const part of parts.slice(0, -1).reverse()) {
        while (node && !node.simple(part)) node = node.parent;
        if (!node) return false;
        node = node.parent;
      }
      return true;
    });
  }
  closest(selector) {
    for (let node = this; node; node = node.parent) if (node.matches(selector)) return node;
    return null;
  }
  querySelectorAll(selector) {
    return this.children.flatMap((child) => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }
  removeEventListener(type, listener) {
    this.listeners[type] = (this.listeners[type] || []).filter((entry) => entry !== listener);
  }
  focus() {}
}
const dispatch = (root, type, target) => (root.listeners[type] || []).forEach((listener) => listener({ type, target, preventDefault() {} }));

const importsRoot = new FakeNode();
const emptyHistory = { available: true, items: [], total: 0, limit: 20, offset: 0, summary: { total: 0, failed: 0 } };
await renderImports(importsRoot, { t: en, ui: 'en', alive: () => true, ctx: { language: 'en' }, params: {}, api: { history: async () => emptyHistory } });
dispatch(importsRoot, 'click', importsRoot.querySelector('button[data-ac-flow="books"]'));
const bookFiles = importsRoot.querySelector('form[data-ac-books] input');
assert.ok(bookFiles, 'choosing Books opens the book importer');
dispatch(importsRoot, 'click', bookFiles);
assert.ok(importsRoot.querySelector('form[data-ac-books] input'), 'working inside an import flow never closes it');
assert.match(importsRoot.querySelector('button[data-ac-flow="books"]').attributes['aria-pressed'], /true/, 'the chosen flow stays chosen');
const chosenInput = importsRoot.querySelector('form[data-ac-books] input');
chosenInput.files = [{ name: 'garden.epub', size: 2048 }, { name: 'broken.epub', size: 2048 }];
dispatch(importsRoot, 'change', chosenInput);
const booksForm = importsRoot.querySelector('form[data-ac-books]');
assert.equal(booksForm.querySelectorAll('tbody tr').length, 2, 'every chosen file is listed');
assert.match(importsRoot.querySelector('[data-ac-flow-host]').innerHTML, new RegExp(en.filesChosen.replace('{count}', '2')));

// ---- operations --------------------------------------------------------------
const readiness = readinessView({ available: true, state: 'deferred', evidence_state: 'degraded', approval_state: 'not_granted', indicators: [{ name: 'runtime_activation', state: 'deferred', source: 'Human activation policy' }] }, en);
assert.match(readiness, /Runtime activation/);
assert.match(readiness, /Not granted/);
assert.match(readiness, /not production-release approval/);
const system = systemView({ persistence_backend: 'postgresql', schema: { state: 'ready', current: '20260916_0009', expected: '20260916_0009' }, account_backbone: 'active', stores: { media_index: 'index_missing', reading_library: 'ok', vocabulary: 'ok', audit_log: 'ok' }, ai: { credential_store: 'not_configured' }, app_version: '1.4.0' }, en);
assert.match(system, /Not active/, 'billing is reported as not active');
assert.doesNotMatch(system, /USD|VND|\$\d|revenue:/i, 'no money is shown');
assert.match(operationsView({ available: true, has_data: false }, en, 'en'), new RegExp(en.opsEmpty));
const operationsTable = operationsView({ available: true, has_data: true, sample_limit: 200, recent: [], by_capability: [{ capability: 'learner_dictionary', health_state: 'degraded', total: 3, failure_rate_percent: 0, avg_latency_ms: 2600 }] }, en, 'en', { degraded_latency_ms: 2000, degraded_failure_rate_percent: 50 });
assert.match(operationsTable, /2 s/, 'a degraded state is explained with the latency rule the server applies');
assert.match(operationsTable, /50%/, 'and with its failure-rate rule');
assert.doesNotMatch(operationsView({ available: true, has_data: true, recent: [], by_capability: [] }, en, 'en'), new RegExp(en.opsHealthRule.split('{')[0]), 'no rule is shown when the server did not state one');

// ---- shell -------------------------------------------------------------------
assert.deepEqual(SECTIONS, ['overview', 'ai', 'users', 'content', 'imports', 'operations']);
assert.equal(sectionFrom({ id: 'ai' }), 'ai');
assert.equal(sectionFrom({ id: 'nope' }), 'overview');
assert.equal(sectionHref('overview'), '#/admin');
assert.equal(sectionHref('content', { kind: 'media', status: 'issues' }), '#/admin?id=content&kind=media&status=issues');
assert.deepEqual(hashParams('#/admin?id=content&kind=book'), { id: 'content', kind: 'book' });
assert.deepEqual(badgeCounts(attention), { ai: 1, content: 1, operations: 1 });
const frame = frameView({ section: 'users', t: zh, attention });
assert.match(frame, /aria-current="page">用户/);
assert.match(frame, /<h1>平台管理<\/h1>/);
assert.equal((frame.match(/class="ac-tab"/g) || []).length, 6);

// ---- hostile data is text, never markup ---------------------------------------
/* Every string the console shows can come from outside: a book's metadata, a
   file name, a provider's model list, a transcript, a server error, an account's
   name. Each view is rendered here with such a string in every field; none may
   reach the page as markup, and no link or image may carry a script URL. */
const EVIL = '<img src=x onerror=alert(1)>"\'><script>alert(2)</script>';
const SCRIPT_URL = 'javascript:alert(3)';
const inert = (html, where) => {
  assert.doesNotMatch(html, /<img src=x|<script>|<\/script>/i, `${where}: hostile text reached the page as markup`);
  assert.doesNotMatch(html, /(?:href|src)\s*=\s*"\s*javascript:/i, `${where}: a script URL became a link or image`);
  assert.doesNotMatch(html, /onerror=alert\(1\)>/, `${where}: an attribute was broken out of`);
};
const hostileRecord = (kind, extra = {}) => ({
  kind, id: EVIL, title: EVIL, subtitle: EVIL, language: EVIL, status: EVIL, origin: EVIL, updated_at: EVIL,
  created_at: EVIL, image: SCRIPT_URL, facts: { chapter_count: 1, word_count: 2, duration_ms: 1000, transcript: EVIL,
  segment_count: 1, item_count: 3, level: EVIL, topic: EVIL, provider: EVIL, framework: EVIL, rights_status: EVIL,
  completeness: EVIL }, issues: [EVIL], actions: ['preview', 'archive', 'publish', 'reprocess'], ...extra,
});
for (const ui of ['en', 'zh']) {
  const t = adminCopy[ui];
  inert(overviewView({
    generated_at: EVIL,
    accounts: { available: true, total: 1, admins: 0, new_7d: 1, new_30d: 1, registrations: [{ date: '2026-09-01', count: 1 }] },
    activity: { available: true, active_7d: 1, active_30d: 1, new_7d: 1, returning_7d: 0, daily: [{ date: '2026-09-01', learners: 1 }],
      domains: [{ domain: EVIL, events: 1, learners: 1 }], languages: [{ language: EVIL, learners: 1 }] },
    languages: { available: true, profiles: [{ language: EVIL, learners: 1 }], active_30d: [{ language: EVIL, learners: 1 }] },
    content: { published: 1, book: { published: 1, archived: 0 }, media: { published: 0, curated: 0, imported: 0, transcript_missing: 0 },
      vocabulary: { published: 0, draft: 0 }, sources: { [EVIL]: 'unavailable', book: 'ok' } },
    imports: { available: true, failed_7d: 1, last_import_at: EVIL },
    ai: { runtime_mode: EVIL, capabilities: {}, providers: {}, health: { [EVIL]: 1 }, provider_names: { gemini: EVIL } },
    attention: [{ kind: EVIL, severity: EVIL, section: EVIL, subject: EVIL, provider: 'gemini', count: 1 },
      { kind: 'legacy_route_fallback', severity: 'warning', section: 'ai', provider: 'gemini' }],
  }, t, ui, href), `overview ${ui}`);
  inert(accountsTable({ available: true, items: [{ id: EVIL, display_name: EVIL, email_masked: EVIL, role: EVIL, joined_at: EVIL,
    last_active_at: EVIL, languages: [EVIL], level: EVIL, status: EVIL }], total: 1, limit: 25, offset: 0 }, t, ui), `accounts ${ui}`);
  inert(accountDetailView({ id: EVIL, display_name: EVIL, email: EVIL, role: EVIL, status: EVIL, joined_at: EVIL, last_login_at: EVIL,
    last_active_at: EVIL, account_state: EVIL, profiles: [{ language: EVIL, goal: EVIL, style: EVIL, support_language: EVIL, updated_at: EVIL }],
    activity: [{ measure: EVIL, language: EVIL, count: 1, last_at: EVIL }] }, t, ui), `account detail ${ui}`);
  inert(usersSummaryView({ available: true, window_days: 30,
    accounts: { available: true, total: 1, admins: 0, new_7d: 1, new_30d: 1, registrations: [{ date: '2026-09-01', count: 1 }] },
    activity: { available: true, active_7d: 1, active_30d: 1, new_7d: 1, returning_7d: 0, segments: { active: 1, new: 1, returning: 0 },
      daily: [{ date: '2026-09-01', learners: 1 }], domains: [{ domain: EVIL, events: 1, learners: 1 }], languages: [{ language: EVIL, learners: 1 }] },
    segments_30d: { active: 1, new: 1, returning: 0 },
    retention: [{ days: 7, eligible_learners: 30, returned_learners: 3, state: 'ready', rate_percent: 10, minimum_sample: 20 }],
    level: { state: EVIL }, languages: { profiles: [{ language: EVIL, learners: 1 }], active: [{ language: EVIL, learners: 1 }] },
  }, t, ui), `users summary ${ui}`);
  inert(contentTable({ items: ['book', 'media', 'vocabulary'].map((kind) => hostileRecord(kind)), total: 3, limit: 25, offset: 0,
    sources: { [EVIL]: 'unavailable' } }, t, ui), `content ${ui}`);
  inert(contentDetailView({ record: hostileRecord('book'), book: { description: EVIL, imported_by: EVIL, chapters: [{ id: EVIL, title: EVIL }] },
    learner_link: SCRIPT_URL }, t, ui, 'archive'), `book detail ${ui}`);
  inert(contentDetailView({ record: hostileRecord('media'), transcript: { segment_count: 2, segments: [{ start_ms: 0, text: EVIL }] },
    source: { url: SCRIPT_URL, license: EVIL, review_status: EVIL, imported_by: EVIL, provider: EVIL }, learner_link: SCRIPT_URL }, t, ui, 'reprocess'),
  `media detail ${ui}`);
  inert(contentDetailView({ record: hostileRecord('vocabulary'), entries: [{ term: EVIL, reading: EVIL, meaning: EVIL, level: EVIL, part_of_speech: EVIL }],
    entry_total: 9, sources: [{ filename: EVIL, created_at: EVIL, status: 'failed', error: EVIL }], admission: { rights_status: EVIL, completeness: EVIL } }, t, ui),
  `vocabulary detail ${ui}`);
  inert(booksView({ language: 'en', running: false, items: [
    { name: EVIL, size: 1, state: 'published', title: EVIL, chapters: 1 },
    { name: EVIL, size: 1, state: 'duplicate', title: EVIL },
    { name: EVIL, size: 1, state: 'failed', code: EVIL, stage: EVIL, message: EVIL },
  ] }, t, ui), `books ${ui}`);
  inert(mediaView({ urls: EVIL, language: 'en', running: false, checking: false, advanced: true, items: [
    { url: EVIL, title: EVIL, state: 'ready', source_label: EVIL, thumbnail_url: SCRIPT_URL, has_transcript: false, level: EVIL, topic: EVIL, tags: [EVIL] },
    { url: EVIL, title: EVIL, state: 'published', source_label: EVIL, thumbnail_url: `/api/${EVIL}`, level: EVIL, topic: EVIL, tags: [EVIL] },
    { url: EVIL, state: 'failed', code: EVIL, stage: EVIL, message: EVIL },
    { file: {}, name: EVIL, size: 1, state: 'to_import' },
  ] }, t, ui), `media ${ui}`);
  inert(vocabularyView({ files: [{ name: EVIL }], previews: [
    { filename: EVIL, headers: [EVIL], row_count: 1, format: EVIL, sample: [{ [EVIL]: EVIL }], warnings: [EVIL] },
    { filename: EVIL, error: EVIL },
  ], mappings: { [EVIL]: { term: EVIL } }, metadata: { title: EVIL, language: 'en', meaning_language: EVIL, framework: EVIL, level: EVIL, topic: EVIL,
    collection_id: EVIL, rights_status: EVIL, completeness: 'unknown', publish: true, attested: false }, errors: [EVIL],
  results: { items: [{ filename: EVIL, status: 'failed', failure_reason: EVIL }, { filename: EVIL, status: 'imported', imported: 1, duplicates: 0, skipped: 0 }],
    collection: { catalog_status: EVIL } }, running: false, previewing: false }, t, ui), `vocabulary import ${ui}`);
  inert(historyView({ available: true, total: 2, limit: 20, offset: 0, summary: { total: 2, failed: 1 }, items: [
    { kind: EVIL, source: EVIL, created_at: EVIL, status: EVIL, result: { title: EVIL, transcript: EVIL }, error: { stage: EVIL, code: EVIL, message: EVIL }, origin: EVIL },
    { kind: 'vocabulary', source: EVIL, created_at: EVIL, status: 'ready', result: { title: EVIL, imported: 1 }, error: null, origin: 'receipt' },
  ] }, { kind: '', status: '' }, t, ui), `history ${ui}`);
  const evilConfig = {
    capabilities: [{ key: EVIL, operation: EVIL, implemented: true, provider_backed: true, configurable: true, explicit_config_exists: true,
      config: { enabled: true, provider: EVIL, model: EVIL, backup_provider: EVIL, backup_model: EVIL } }],
    providers: [{ id: EVIL, name: EVIL, kind: EVIL, secret_mode: 'server-managed', supported_operations: [EVIL], server_configured: true }],
  };
  const evilProviders = mergeProviders(evilConfig, { providers: [{ id: EVIL, configured: true, models: [EVIL],
    configuration: { credential_env: EVIL, credential_source: EVIL, endpoint_url: SCRIPT_URL } }] });
  const evilState = { config: evilConfig, providers: evilProviders, operations: { by_capability: [{ capability: EVIL, health_state: EVIL }] },
    tests: new Map([[EVIL, { state: 'failed', message: EVIL }]]), editing: EVIL, draft: { enabled: true, provider: EVIL, model: EVIL },
    catalogState: 'ready', providerTests: new Map([[EVIL, { state: 'failed', message: EVIL }]]), runtime: { ai: { credential_store: EVIL } },
    providerForm: EVIL, providerMessage: EVIL, confirmRemove: EVIL, expanded: EVIL };
  inert(routingView(evilState, t, ui), `routing ${ui}`);
  inert(providersView(evilState, t, ui), `providers ${ui}`);
  inert(runtimeView({ ai: { learner_runtime_mode: EVIL, legacy_selection: { source: EVIL, provider: EVIL, model: EVIL, provider_configured: false,
    effective: { provider: EVIL, model: EVIL, fallback: true } } } }, t, { [EVIL]: EVIL }), `runtime ${ui}`);
  inert(servicesView({ services: [{ id: EVIL, provider: EVIL, engine: EVIL, model: EVIL, state: EVIL }] }, t), `services ${ui}`);
  inert(operationsView({ available: true, has_data: true, sample_limit: 1, by_capability: [{ capability: EVIL, health_state: EVIL, total: 1,
    failure_rate_percent: 0, avg_latency_ms: 10, quota_state: EVIL, cost_totals: [{ currency: EVIL, amount: 1 }] }],
    recent: [{ created_at: EVIL, capability: EVIL, origin: EVIL, outcome: EVIL, provider: EVIL, model: EVIL, latency_ms: 1, error_class: EVIL }] },
  t, ui, { degraded_latency_ms: 2000, degraded_failure_rate_percent: 50 }), `operations ${ui}`);
  inert(readinessView({ available: true, state: EVIL, evidence_state: EVIL, approval_state: EVIL,
    indicators: [{ name: EVIL, state: EVIL, source: EVIL, detail: EVIL }] }, t), `readiness ${ui}`);
  inert(systemView({ persistence_backend: EVIL, schema: { state: EVIL, current: EVIL, expected: EVIL }, account_backbone: EVIL,
    stores: { media_index: EVIL, reading_library: EVIL, vocabulary: EVIL, audit_log: EVIL }, ai: { credential_store: EVIL }, app_version: EVIL }, t),
  `system ${ui}`);
  inert(activationView({ ai: { learner_runtime_mode: EVIL } }, t), `activation ${ui}`);
  inert(impactView({ learner_impact_failures: { available: true, by_capability: [{ capability: EVIL, failure_count: 1, degraded_count: 1 }] } }, t, ui),
    `impact ${ui}`);
  inert(envView({ persistence_backend: EVIL, ai: { learner_runtime_mode: EVIL }, app_version: EVIL }, t), `environment ${ui}`);
  inert(frameView({ section: EVIL, t, attention: [{ section: EVIL }] }), `frame ${ui}`);
}
assert.doesNotMatch(contentDetailView({ record: hostileRecord('book'), book: { chapters: [] }, learner_link: 'https://elsewhere.example/' }, en, 'en'),
  /elsewhere\.example/, 'an "open as a learner" link stays inside the app');
assert.match(contentDetailView({ record: hostileRecord('book'), book: { chapters: [] }, learner_link: '#/encounter?id=book%3A1' }, en, 'en'),
  /href="#\/encounter\?id=book%3A1"/);
assert.deepEqual(mediaOutcome({ status: 'duplicate', media_id: 'upload-1' }), { state: 'duplicate', contentId: 'upload-1' });
const duplicateFlow = mediaView({ urls: '', language: 'en', running: false, checking: false, advanced: false, items: [
  { file: {}, name: 'tone.wav', size: 10, state: 'duplicate', contentId: 'upload-1' },
] }, en, 'en');
assert.match(duplicateFlow, new RegExp(en.mediaDuplicate), 'a file already in the library says so');
assert.match(duplicateFlow, /role="status"/, 'a batch of duplicates is finished, not pending');

// ---- one colour owner ----------------------------------------------------------
const css = read('static/orena/admin/admin.css');
assert.doesNotMatch(css, /#[0-9a-f]{3,8}\b/i, 'admin.css declares no hex colour');
assert.doesNotMatch(css, /\b(?:rgb|rgba|hsl|hsla)\(/i, 'admin.css declares no functional colour');
assert.doesNotMatch(css, /:root/, 'admin.css declares no root tokens');
assert.doesNotMatch(css, /font-size:\s*\d+px/, 'admin type uses the shared scale or rem');
const defined = new Set(
  ['theme', 'foundation', 'reference'].flatMap((name) => [...read(`static/orena/${name}.css`).matchAll(/(--[\w-]+)\s*:/g)].map((match) => match[1])),
);
for (const inline of ['--count', '--at']) defined.add(inline);
for (const [, token] of css.matchAll(/var\((--[\w-]+)/g)) assert.ok(defined.has(token), `admin.css uses an undefined token ${token}`);
for (const pair of [['--sage-surface', '--on-sage'], ['--coral-surface', '--on-coral'], ['--sun-surface', '--on-sun'], ['--night-surface', '--on-night']]) {
  assert.ok(css.includes(pair[0]) && css.includes(pair[1]), `${pair[0]} is always worn with ${pair[1]}`);
}
assert.ok(table({ head: ['A'], rows: [] , empty: 'none' }).includes('none'));

console.log('Platform Admin control center: copy parity, server contracts, honest absence, no secrets, isolated imports, one colour owner PASS');
