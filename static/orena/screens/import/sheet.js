/* Import overlay (pinned design frame 58, opened from Discover's "+ Import"). Two real paths, no
   fictional preview or fake progress (Design Contract rule 40):

   - text  -> device memory (product/memory.js#add), straight into the Reader - there never was a
             preview/processing step for text, in the old dialog or the new frame's own bindings.
   - url   -> capabilities/media-acquisition.js#acquireMedia (POST /api/media-learning/import, then
             /import/status while the backend's own job is resumable), then Listening.

   - file  -> the device's file picker, then POST /api/media-learning/upload (D-098: the human wired
             File to that route, with the types and size limit it already enforces), then
             Listening. The frame draws no File step of its own, so none is added: the picker is
             the device's, and the wait is the drawn Processing step.

   The frame's own "Preview" step (I3b) has no cheap counterpart on the backend - the only way to
   learn a URL's title/thumbnail/duration is to run the same acquisition the "Processing" step runs -
   so Preview and Processing are one real step here (recorded in SCRATCH/reports/sheets.md), and the
   frame's four-stage checklist (fetch/transcribe/translate/ready) is one status row, because that is
   all the backend's own job state (`import_job.state`/`resumable`/`failure_kind`) reports. */
import { openSheet, fillSheet } from '../../kit/overlay.js';
import { html, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { processingProgressMarkup } from '../../kit/states.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy as s } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { href } from '../../shell/routes.js';
import { api } from '../../infrastructure/api.js';
import { acquireMedia } from '../../capabilities/media-acquisition.js';
import { isSupportedMediaUrl } from '../../product/media-url.js';
import { sourceFromLesson } from '../../product/speaking-source.js';
import { t } from './copy.js';
import { textStats, importErrorKey, urlMediaEntry, uploadMediaEntry } from './model.js';

const STEP_LABEL = { type: 'stepType', text: 'stepText', url: 'stepUrl', processing: 'stepProcessing' };

export async function openImport(ctx = {}, { mediaRoute = 'listening' } = {}) {
  const context = ctx.context || {};
  const memory = context.memory || null;
  const admittedForPractice = (id, result) => {
    if (!['shadow','dictation'].includes(mediaRoute)) return true;
    const source = sourceFromLesson(id, result, '', languages().support);
    return source?.hasModelAudio && source.language === context.language && (!result.asset?.processing_state || result.asset.processing_state === 'ready');
  };
  const navigate = (routeId, params) => {
    const target = href(routeId, params);
    if (typeof ctx.go === 'function') ctx.go(target);
    else window.location.hash = target;
  };

  let alive = true;
  let sheetEl = null;
  let sheetHandle = null;

  const state = {
    step: 'type',
    title: '',
    text: '',
    url: '',
    urlError: '',
    textError: '',
    processError: '',
    busy: false,
    processing: null,
    source: 'url',
    file: null,
    fileRefused: false,
  };

  function go(step) {
    state.step = step;
    state.urlError = '';
    state.textError = '';
    state.processError = '';
    paint();
  }

  function optionMarkup() {
    return html`
      <button type="button" class="s-import__option s-import__option--primary" data-pick="url">
        <div class="s-import__option-title">${t('optionUrlTitle')}</div>
        <div class="s-import__option-sub">${t('introUrl')}</div>
      </button>
      <button type="button" class="s-import__option" data-pick="text">
        <div class="s-import__option-title">${t('optionTextTitle')}</div>
        <div class="s-import__option-sub">${t('introText')}</div>
      </button>
      <button type="button" class="s-import__option" data-pick="file">
        <div class="s-import__option-title">${t('optionFileTitle')}</div>
        <div class="s-import__option-sub">${t('introFile')}</div>
      </button>
      <input type="file" accept="audio/*,video/*" data-file hidden>
    `;
  }

  function textMarkup() {
    const stats = textStats(state.text);
    return html`
      <label class="s-import__label" for="s-import-title">${t('fieldTitleLabel')}</label>
      <input id="s-import-title" class="s-import__input" data-field="title" value="${state.title}" placeholder="${t('fieldTitlePlaceholder')}" maxlength="120">
      <label class="s-import__label" for="s-import-text">${t('fieldTextLabel')}</label>
      <textarea id="s-import-text" class="s-import__textarea" data-field="text" lang="${langAttr(context.language)}" rows="8" placeholder="${t('fieldTextPlaceholder')}" maxlength="12000">${state.text}</textarea>
      <div class="s-import__stats">
        <span class="o-tag o-tag--accent" data-role="lang">${context.language === 'zh' ? s('lang_zh') : s('lang_en')}</span>
        <span class="o-tag" data-role="stats">${stats.unit === 'characters' ? t('statsCharacters', { count: stats.count, sentences: stats.sentences }) : t('statsWords', { count: stats.count, sentences: stats.sentences })}</span>
      </div>
      <div class="s-import__warn" data-role="tooshort" ${stats.tooShort ? '' : 'hidden'}>${t('tooShort')}</div>
      ${state.textError ? html`<div class="s-import__error">${state.textError}</div>` : ''}
      <div class="s-import__footer">
        <button type="button" class="o-btn o-btn--secondary o-btn--sm" data-back="type">${s('back')}</button>
        <button type="button" class="o-btn o-btn--primary s-import__cta" data-submit="text" ${stats.tooShort ? 'disabled' : ''}>${t('importToReader')}</button>
      </div>
    `;
  }

  function urlMarkup() {
    return html`
      <label class="s-import__label" for="s-import-url">${t('fieldUrlLabel')}</label>
      <input id="s-import-url" class="s-import__input s-import__input--url" type="url" inputmode="url" data-field="url" value="${state.url}" placeholder="${t('fieldUrlPlaceholder')}">
      ${state.urlError ? html`<div class="s-import__error">${state.urlError}</div>` : ''}
      <div class="s-import__footer">
        <button type="button" class="o-btn o-btn--secondary o-btn--sm" data-back="type">${s('back')}</button>
        <button type="button" class="o-btn o-btn--primary s-import__cta" data-submit="url">${t('importAndProcess')}</button>
      </div>
    `;
  }

  function processingMarkup() {
    if (state.processError) {
      return html`
        <div class="s-import__error">${state.processError}</div>
        <div class="s-import__footer">
          <button type="button" class="o-btn o-btn--secondary o-btn--sm" data-back="${state.source === 'file' ? 'type' : 'url'}">${s('back')}</button>
          <button type="button" class="o-btn o-btn--primary s-import__cta" data-retry>${s('retry')}</button>
        </div>
        ${state.source === 'file' ? html`<input type="file" accept="audio/*,video/*" data-file hidden>` : ''}
      `;
    }
    return html`
      <div class="s-import__stage">
        <span class="o-spinner" aria-hidden="true"></span>
        <div class="s-import__stage-label">${t('statusImporting')}</div>
      </div>
      <div class="s-import__note" role="status">${t(state.processing?.stage === 'transcribe' ? 'aiTranscript' : state.processing?.stage === 'translate' ? 'aiTranslation' : 'noPercent')}</div>
      ${processingProgressMarkup(state.processing?.stage, Object.fromEntries(['fetch','transcribe','segment','translate','ready'].map(stage => [stage,t(`stage_${stage}`)])))}
    `;
  }

  function bodyMarkup() {
    if (state.step === 'text') return textMarkup();
    if (state.step === 'url') return urlMarkup();
    if (state.step === 'processing') return processingMarkup();
    return optionMarkup();
  }

  function markup() {
    return html`<div class="o-sheet__head">
      <div>
        <div class="o-sheet__title">${t('title')}</div>
        <div class="s-import__step">${t(STEP_LABEL[state.step])}</div>
      </div>
      <button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button>
    </div>
    <div class="o-sheet__body s-import__body">${bodyMarkup()}</div>`;
  }

  function paint() {
    if (!sheetEl || !alive) return;
    fillSheet(sheetEl, sheetHandle, markup());
    bind();
  }

  function bind() {
    sheetEl.querySelector('[data-pick="url"]')?.addEventListener('click', () => go('url'));
    sheetEl.querySelector('[data-pick="text"]')?.addEventListener('click', () => go('text'));
    /* A refused file is chosen again (Retry opens the picker); a file the server could not store is
       sent again as it is. */
    const fileInput = sheetEl.querySelector('[data-file]');
    sheetEl.querySelector('[data-pick="file"]')?.addEventListener('click', () => fileInput?.click());
    fileInput?.addEventListener('change', () => {
      const [file] = fileInput.files || [];
      if (file) submitFile(file);
    });
    sheetEl.querySelectorAll('[data-back]').forEach((btn) => btn.addEventListener('click', () => go(btn.dataset.back)));

    if (state.step === 'text') {
      const titleInput = sheetEl.querySelector('[data-field="title"]');
      const textArea = sheetEl.querySelector('[data-field="text"]');
      const statsEl = sheetEl.querySelector('[data-role="stats"]');
      const warnEl = sheetEl.querySelector('[data-role="tooshort"]');
      const submitBtn = sheetEl.querySelector('[data-submit="text"]');
      titleInput?.addEventListener('input', () => { state.title = titleInput.value; });
      textArea?.addEventListener('input', () => {
        state.text = textArea.value;
        const stats = textStats(state.text);
        if (statsEl) statsEl.textContent = stats.unit === 'characters' ? t('statsCharacters', { count: stats.count, sentences: stats.sentences }) : t('statsWords', { count: stats.count, sentences: stats.sentences });
        if (warnEl) warnEl.hidden = !stats.tooShort;
        // Not offered until there is enough to import; the line above says why (LEX-081).
        if (submitBtn) submitBtn.disabled = stats.tooShort;
      });
      submitBtn?.addEventListener('click', submitText);
    }
    if (state.step === 'url') {
      const urlInput = sheetEl.querySelector('[data-field="url"]');
      urlInput?.addEventListener('input', () => { state.url = urlInput.value; });
      urlInput?.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); submitUrl(); } });
      sheetEl.querySelector('[data-submit="url"]')?.addEventListener('click', submitUrl);
    }
    if (state.step === 'processing' && state.processError) {
      sheetEl.querySelector('[data-retry]')?.addEventListener('click', () => {
        if (state.source !== 'file') submitUrl();
        else if (state.fileRefused) fileInput?.click();
        else submitFile(state.file);
      });
    }
  }

  function submitText() {
    if (state.busy) return;
    const stats = textStats(state.text);
    if (stats.tooShort) {
      // The frame never disables this button - it stays full-accent and answers an early click
      // with this same toast (its impTextProcess handler); the inline warning line already shown
      // under the stats chip is the frame's other half of this state.
      toast(t('tooShort'), { iconName: 'circle-alert' });
      return;
    }
    if (!memory?.add) {
      state.textError = t('error_generic');
      paint();
      return;
    }
    try {
      const item = memory.add({ title: state.title.trim() || state.text.trim().slice(0, 60), text: state.text });
      sheetHandle?.close();
      navigate('reader', { id: item.id });
    } catch {
      // The only remaining throw path once tooShort is guarded is memory.add's own 20-item cap
      // (product/memory.js) - a real, honest limit, not a made-up message.
      state.textError = t('error_generic');
      paint();
    }
  }

  /* The route answers with the stored entry's learner payload and its `media_id`; a refusal carries
     its own category (media_upload_invalid: not audio/video, empty or over the route's limit;
     media_upload_unavailable: storage failed), each said in the learner's language. */
  async function submitFile(file) {
    if (state.busy || !file) return;
    const support = languages().support;
    state.busy = true;
    state.source = 'file';
    state.file = file;
    state.fileRefused = false;
    state.step = 'processing';
    state.processing = null;
    state.processError = '';
    paint();
    try {
      let result = await api.mediaUpload(file, context.language);
      for (let attempt = 0; alive && result?.asset?.processing_state === 'processing' && attempt < 60; attempt++) {
        state.processing = result.processing;
        paint();
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (!alive) return;
        const mediaId = result.media_id;
        result = { ...await api.mediaMy(mediaId, support), media_id: mediaId };
      }
      if (!alive) return;
      state.busy = false;
      const entry = uploadMediaEntry(result, file.name);
      if (!entry) {
        state.processError = t('error_generic');
        paint();
        return;
      }
      memory?.addMedia?.(entry);
      if (!admittedForPractice(result.media_id, result)) {
        state.processError = t('error_practice_unavailable');
        paint();
        return;
      }
      sheetHandle?.close();
      navigate(mediaRoute, { id: result.media_id });
    } catch (error) {
      if (!alive) return;
      state.busy = false;
      state.fileRefused = error?.category === 'media_upload_invalid';
      state.processError = t(importErrorKey(error?.category));
      paint();
    }
  }

  async function submitUrl() {
    if (state.busy) return;
    state.source = 'url';
    if (!isSupportedMediaUrl(state.url.trim())) {
      state.urlError = t('urlInvalid');
      paint();
      return;
    }
    state.busy = true;
    state.step = 'processing';
    state.processing = null;
    state.processError = '';
    paint();
    try {
      const result = await acquireMedia({
        api,
        url: state.url.trim(),
        // Prepare the support-language projection once at the import boundary (D-121).
        target: languages().support,
        owner: context.owner || 'local',
        language: context.language,
        alive: () => alive,
        onProgress: (result) => { state.processing = result?.processing; if (alive) paint(); },
      });
      if (!alive) return;
      state.busy = false;
      if (!result || result.asset?.processing_state === 'failed') {
        state.processError = t(importErrorKey(result?.import_job?.failure_kind));
        paint();
        return;
      }
      const entry = result.media_id ? uploadMediaEntry(result) : urlMediaEntry(state.url.trim(), result);
      memory?.addMedia?.(entry);
      if (!admittedForPractice(entry.id, result)) {
        state.processError = t('error_practice_unavailable');
        paint();
        return;
      }
      sheetHandle?.close();
      navigate(mediaRoute, { id: entry.id });
    } catch (error) {
      if (!alive) return;
      state.busy = false;
      state.processError = t(importErrorKey(error?.category));
      paint();
    }
  }

  await useStyles('screens/import/import.css');
  if (!ctx.isCurrent || ctx.isCurrent()) {
    sheetHandle = openSheet({
      label: t('title'),
      className: 's-import',
      render(element, handle) {
        sheetEl = element;
        sheetHandle = handle;
        paint();
        return () => {
          alive = false;
        };
      },
    });
  }
  return sheetHandle;
}
