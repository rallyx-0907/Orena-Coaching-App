import { esc } from './html.js';
import { pageIntro } from './patterns.js';

const alive = (ctx) => (typeof ctx.alive === 'function' ? ctx.alive() : true);

function valueLabel(c, value) {
  return c[`adminValue_${value}`] || value || '—';
}

function frame(c, body) {
  return `<div class="admin-room">${pageIntro({
    eyebrow: c.admin,
    title: c.adminTitle,
    note: c.adminNote,
    compact: true,
  })}<section class="thread-shelf admin-summary" aria-live="polite">${body}</section></div>`;
}

function loading(c) {
  return frame(c, `<p class="loading" role="status">${esc(c.adminLoading)}</p>`);
}

function empty(c) {
  return frame(c, `<p class="empty">${esc(c.adminEmpty)}</p>`);
}

function error(c) {
  return frame(c, `<div class="notice" role="alert"><p>${esc(c.adminUnavailable)}</p><button class="quiet" type="button" data-admin-retry>${esc(c.adminRetry)}</button></div>`);
}

function summary(c, payload) {
  const indicators = Array.isArray(payload.indicators) ? payload.indicators.filter((item) => item && typeof item === 'object') : [];
  const rows = indicators.map((item) => `<li><strong>${esc(c[`adminIndicator_${item.name}`] || item.name || '—')}</strong><span>${esc(valueLabel(c, item.state))}</span><small>${esc(c[`adminSource_${item.name}`] || item.source || '—')}</small>${item.detail ? `<p>${esc(item.detail)}</p>` : ''}</li>`).join('');
  return frame(c, `<div class="section-head"><div><h2>${esc(c.adminIndicators)}</h2><p>${esc(c.adminState)}: <strong>${esc(valueLabel(c, payload.evidence_state || payload.state))}</strong></p></div><p>${esc(c.adminApproval)}: <strong>${esc(valueLabel(c, payload.approval_state))}</strong></p></div><ul class="admin-indicators">${rows}</ul><p class="meta"><strong>${esc(c.adminRedaction)}:</strong> ${esc(payload.redaction || '—')}</p>`);
}

const IMPORT_FIELDS = [
  'term', 'short_meaning', 'detailed_definition', 'pronunciation',
  'part_of_speech', 'example', 'usage', 'level', 'framework', 'topic',
  'meaning_language', 'target_language', 'reading', 'orthography', 'sense_key',
];

function fieldLabel(c, field) {
  return c[`adminVocabularyField_${field}`] || field.replaceAll('_', ' ');
}

function importer(c) {
  return `<section class="thread-shelf admin-vocabulary-importer" data-admin-vocabulary-importer><div class="section-head"><div><h2>${esc(c.adminVocabularyTitle)}</h2><p>${esc(c.adminVocabularyNote)}</p></div></div><form data-admin-vocabulary-form><div class="admin-vocabulary-grid"><label><span>${esc(c.adminVocabularyFiles)}</span><input type="file" data-admin-vocabulary-files multiple accept=".csv,.tsv,.json,.txt,.xlsx"></label><label><span>${esc(c.adminVocabularyCollectionTitle)}</span><input type="text" data-admin-vocabulary-title maxlength="255" required placeholder="${esc(c.adminVocabularyCollectionTitlePlaceholder)}"></label><label><span>${esc(c.adminVocabularyLanguage)}</span><input type="text" data-admin-vocabulary-language value="en" maxlength="20" required></label><label><span>${esc(c.adminVocabularyFramework)}</span><input type="text" data-admin-vocabulary-framework placeholder="TOEIC, HSK, CEFR…"></label><label><span>${esc(c.adminVocabularyLevel)}</span><input type="text" data-admin-vocabulary-level placeholder="A1–C2 or HSK1–HSK7-9"></label><label><span>${esc(c.adminVocabularyMeaningLanguage)}</span><input type="text" data-admin-vocabulary-meaning-language value="vi" maxlength="20"></label><label><span>${esc(c.adminVocabularyTopic)}</span><input type="text" data-admin-vocabulary-topic></label><label><span>${esc(c.adminVocabularyCollectionId)}</span><input type="text" data-admin-vocabulary-collection-id placeholder="${esc(c.adminVocabularyCollectionIdPlaceholder)}"></label></div><div class="button-row"><button class="outline" type="button" data-admin-vocabulary-preview>${esc(c.adminVocabularyPreview)}</button><button class="primary" type="button" data-admin-vocabulary-import disabled>${esc(c.adminVocabularyImport)}</button></div><p class="meta" data-admin-vocabulary-status role="status">${esc(c.adminVocabularyChooseSource)}</p><div data-admin-vocabulary-preview-output></div><div data-admin-vocabulary-results></div></form></section>`;
}

function renderPreview(c, previews, mappings) {
  return previews.map((item, index) => {
    if (item.error) return `<article class="admin-vocabulary-source admin-vocabulary-source--error"><h3>${esc(item.filename)}</h3><p class="notice" role="alert">${esc(item.error)}</p></article>`;
    const detected = item.detected_mapping || {};
    mappings[item.filename] ||= { ...detected };
    const fields = IMPORT_FIELDS.map((field) => {
      const selected = mappings[item.filename][field] || '';
      const options = [`<option value="">${esc(c.adminVocabularyNotProvided)}</option>`, ...(item.headers || []).map((header) => `<option value="${esc(header)}" ${header === selected ? 'selected' : ''}>${esc(header)}</option>`)].join('');
      return `<label><span>${esc(fieldLabel(c, field))}</span><select data-admin-vocabulary-map data-file-index="${index}" data-field="${esc(field)}">${options}</select></label>`;
    }).join('');
    const sample = (item.sample || []).slice(0, 3).map((row) => `<pre>${esc(JSON.stringify(row, null, 2))}</pre>`).join('');
    const warnings = (item.warnings || []).map((warning) => `<li>${esc(warning)}</li>`).join('');
    return `<article class="admin-vocabulary-source"><div class="section-head"><div><h3>${esc(item.filename)}</h3><p>${esc(item.row_count)} ${esc(c.adminVocabularyRows)} · ${esc(item.format.toUpperCase())}</p></div><span class="admin-vocabulary-hash">${esc(item.content_hash ? item.content_hash.slice(0, 12) : '')}</span></div><div class="admin-vocabulary-mapping-grid">${fields}</div>${warnings ? `<ul class="admin-vocabulary-warnings">${warnings}</ul>` : ''}<details><summary>${esc(c.adminVocabularySample)}</summary>${sample}</details></article>`;
  }).join('');
}

function renderImportResults(c, items) {
  if (!Array.isArray(items) || !items.length) return '';
  return `<section class="admin-vocabulary-results"><h3>${esc(c.adminVocabularyResults)}</h3><ul>${items.map((item) => `<li><strong>${esc(item.filename || 'source')}</strong><span>${esc(item.status || 'failed')}</span><small>${esc(item.imported || 0)} ${esc(c.adminVocabularyImported)} · ${esc(item.duplicates || 0)} ${esc(c.adminVocabularyDuplicates)} · ${esc(item.skipped || 0)} ${esc(c.adminVocabularySkipped)}${item.failure_reason ? ` · ${esc(item.failure_reason)}` : ''}</small></li>`).join('')}</ul></section>`;
}

function bindImporter(root, ctx) {
  const shell = root.querySelector('[data-admin-vocabulary-importer]');
  if (!shell) return;
  shell.querySelector('.admin-vocabulary-grid')?.insertAdjacentHTML('beforeend', `<label><span>${esc(ctx.c.adminVocabularyRightsStatus)}</span><select data-admin-vocabulary-rights-status><option value="">${esc(ctx.c.adminVocabularyRightsUnknown)}</option><option value="public_domain">${esc(ctx.c.adminVocabularyRightsPublicDomain)}</option><option value="licensed">${esc(ctx.c.adminVocabularyRightsLicensed)}</option><option value="creator_authorized">${esc(ctx.c.adminVocabularyRightsCreatorAuthorized)}</option><option value="internal_curated">${esc(ctx.c.adminVocabularyRightsInternalCurated)}</option></select></label><label><span>${esc(ctx.c.adminVocabularyCompleteness)}</span><select data-admin-vocabulary-completeness><option value="complete">${esc(ctx.c.adminVocabularyCompletenessComplete)}</option><option value="partial">${esc(ctx.c.adminVocabularyCompletenessPartial)}</option><option value="unknown" selected>${esc(ctx.c.adminVocabularyCompletenessUnknown)}</option></select></label><label class="admin-vocabulary-publish"><span>${esc(ctx.c.adminVocabularyPublish)}</span><input type="checkbox" data-admin-vocabulary-publish></label>`);
  const meaningLanguageInput = shell.querySelector('[data-admin-vocabulary-meaning-language]');
  if (meaningLanguageInput && ctx.support) meaningLanguageInput.value = ctx.support;
  const filesInput = shell.querySelector('[data-admin-vocabulary-files]');
  const previewButton = shell.querySelector('[data-admin-vocabulary-preview]');
  const importButton = shell.querySelector('[data-admin-vocabulary-import]');
  const status = shell.querySelector('[data-admin-vocabulary-status]');
  const output = shell.querySelector('[data-admin-vocabulary-preview-output]');
  const results = shell.querySelector('[data-admin-vocabulary-results]');
  const state = { files: [], previews: [], mappings: {} };
  const setStatus = (message) => { if (status) status.textContent = message; };
  filesInput?.addEventListener('change', () => {
    state.files = [...(filesInput.files || [])]; state.previews = []; state.mappings = {};
    if (output) output.innerHTML = ''; if (results) results.innerHTML = '';
    if (importButton) importButton.disabled = true;
    setStatus(state.files.length ? `${state.files.length} ${ctx.c.adminVocabularyFilesSelected}` : ctx.c.adminVocabularyChooseSource);
  });
  previewButton?.addEventListener('click', async () => {
    if (!state.files.length) { setStatus(ctx.c.adminVocabularyChooseSource); return; }
    previewButton.disabled = true; setStatus(ctx.c.adminVocabularyPreviewing);
    try {
      const payload = await ctx.api.adminVocabularyPreview(state.files);
      if (!alive(ctx)) return;
      state.previews = Array.isArray(payload?.items) ? payload.items : []; state.mappings = {};
      if (output) output.innerHTML = renderPreview(ctx.c, state.previews, state.mappings);
      const hasTerm = state.previews.some((item) => !item.error && item.detected_mapping?.term);
      if (importButton) importButton.disabled = !hasTerm;
      setStatus(hasTerm ? ctx.c.adminVocabularyMappingReady : ctx.c.adminVocabularyMappingRequired);
    } catch (error) { setStatus(error.message || ctx.c.adminUnavailable); }
    finally { previewButton.disabled = false; }
  });
  output?.addEventListener('change', (event) => {
    const select = event.target.closest('[data-admin-vocabulary-map]'); if (!select) return;
    const item = state.previews[Number(select.dataset.fileIndex)]; if (!item) return;
    state.mappings[item.filename] ||= {}; state.mappings[item.filename][select.dataset.field] = select.value || null;
    const termReady = state.previews.some((preview) => !preview.error && state.mappings[preview.filename]?.term);
    if (importButton) importButton.disabled = !termReady;
  });
  importButton?.addEventListener('click', async () => {
    if (!state.files.length) return;
    const publish = Boolean(shell.querySelector('[data-admin-vocabulary-publish]')?.checked);
    const metadata = { title: shell.querySelector('[data-admin-vocabulary-title]')?.value || '', language_code: shell.querySelector('[data-admin-vocabulary-language]')?.value || '', framework: shell.querySelector('[data-admin-vocabulary-framework]')?.value || '', level: shell.querySelector('[data-admin-vocabulary-level]')?.value || '', meaning_language: shell.querySelector('[data-admin-vocabulary-meaning-language]')?.value || '', topic: shell.querySelector('[data-admin-vocabulary-topic]')?.value || '', collection_id: shell.querySelector('[data-admin-vocabulary-collection-id]')?.value || '', rights_status: shell.querySelector('[data-admin-vocabulary-rights-status]')?.value || '', completeness: shell.querySelector('[data-admin-vocabulary-completeness]')?.value || 'unknown', publish, publication_attested: publish };
    if (!metadata.title || !metadata.language_code) { setStatus(ctx.c.adminVocabularyMetadataRequired); return; }
    importButton.disabled = true; setStatus(ctx.c.adminVocabularyImporting);
    try {
      const payload = await ctx.api.adminVocabularyImport(state.files, metadata, state.mappings);
      if (!alive(ctx)) return;
      if (results) results.innerHTML = renderImportResults(ctx.c, payload?.items);
      setStatus(payload?.collection?.catalog_status === 'published' ? ctx.c.adminVocabularyComplete : payload?.collection?.catalog_status === 'not_created' ? ctx.c.adminVocabularyNoCollection : ctx.c.adminVocabularyPendingReview);
    } catch (error) { setStatus(error.message || ctx.c.adminUnavailable); importButton.disabled = false; }
  });
}

export async function renderAdmin(root, ctx) {
  const c = ctx.c;
  root.innerHTML = loading(c);
  try {
    const payload = await ctx.api.adminReadinessSummary();
    if (!alive(ctx)) return;
    if (!payload || payload.available === false) {
      root.innerHTML = `${empty(c)}${importer(c)}`;
      bindImporter(root, ctx);
      return;
    }
    const indicators = Array.isArray(payload.indicators) ? payload.indicators : [];
    root.innerHTML = `${indicators.length ? summary(c, payload) : empty(c)}${importer(c)}`;
    bindImporter(root, ctx);
  } catch {
    if (!alive(ctx)) return;
    root.innerHTML = error(c);
    root.querySelector('[data-admin-retry]')?.addEventListener('click', () => renderAdmin(root, ctx));
  }
}
