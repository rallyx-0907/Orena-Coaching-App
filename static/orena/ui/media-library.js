import { esc, safeExternal } from './html.js';
import { art, duration, bindImages } from './content.js';
import { link } from '../product/intent.js';
import { continuationEntries } from './patterns.js';

/* Listening = media library.

   The catalogue, the learner's own imports and the administrator's imports are
   one thing seen three ways, so they share one card. A card is what a person
   browses by: a real thumbnail, a title, and the shortest true metadata line
   that helps them choose. A description is deliberately absent - the encounter
   already shows it, and repeating it here is what turned this surface into a
   list of documents instead of a shelf of media.

   Nothing here fetches or resolves a provider. Every field arrives already
   normalized from `/api/listening/library`, so browsing costs no network work
   beyond the read itself and no request ever re-scrapes a source. */

// Only an https image reaches an <img>, for the same reason content.js does it:
// a value that could carry a script or a private address must not become a
// request the learner's browser makes.
function thumbnailOf(item) {
  const raw = String(item.thumbnail_url || item.poster_url || '');
  return safeExternal(raw) ? raw : '';
}

function kindMark(item, c) {
  const label = item.kind === 'video' || item.kind === 'embed' ? c.mediaVideo : c.mediaAudio;
  // The mark is decoration; the label is what a screen reader gets.
  return `<span class="media-card__kind" aria-hidden="true">${item.kind === 'video' || item.kind === 'embed' ? '▶' : '♪'}</span><span class="sr-only">${esc(label)}</span>`;
}

function metadataLine(item, c) {
  const source = item.source_label || '';
  return [source, item.level]
    .filter(Boolean)
    .map((part) => esc(part))
    .join(' · ');
}

export function mediaCard(item, c, { intent = '' } = {}) {
  const thumbnail = thumbnailOf(item);
  const visual = thumbnail
    ? `<img src="${esc(thumbnail)}" alt="${esc(item.title)}" loading="lazy" referrerpolicy="no-referrer">`
    : art({ ...item, poster_url: '' });
  const length = Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '';
  const meta = metadataLine(item, c);
  // The image comes first and the link names itself after it: a learner
  // scanning the grid orients on the picture, and a screen reader still hears
  // which item the link opens.
  return `<article class="media-card"><span class="media-card__visual">${visual}${length ? `<span class="media-card__duration">${esc(length)}</span>` : ''}${kindMark(item, c)}</span><a class="media-card__body" href="${esc(link('encounter', { id: item.id, intent }))}" aria-label="${esc(`${c.mediaOpen} ${item.title}`)}"><strong class="media-card__title" lang="${esc(item.language || '')}">${esc(item.title)}</strong>${meta ? `<span class="media-card__meta">${meta}</span>` : ''}</a></article>`;
}

/* Search and filters narrow what has already been read. `source` matches the
   label a card actually shows, because a learner filters by what they see, not
   by a provider id they never meet. */
export function filterMediaItems(items, { type = '', query = '', level = '', source = '' } = {}) {
  const needle = String(query || '').trim().toLocaleLowerCase();
  const wantedType = String(type || '').trim().toLocaleLowerCase();
  const wantedLevel = String(level || '').trim().toLocaleLowerCase();
  const wantedSource = String(source || '').trim().toLocaleLowerCase();
  return (items || []).filter((item) => {
    const kind = String(item.kind === 'embed' ? 'video' : item.kind || item.media_type || '').toLocaleLowerCase();
    if (wantedType && wantedType !== 'all' && kind !== wantedType) return false;
    if (wantedLevel && String(item.level || '').toLocaleLowerCase() !== wantedLevel) return false;
    if (wantedSource && String(item.source_label || '').toLocaleLowerCase() !== wantedSource) return false;
    if (!needle) return true;
    return `${item.title || ''} ${item.source_label || ''}`.toLocaleLowerCase().includes(needle);
  });
}

export function mediaFacets(items) {
  const list = items || [];
  return {
    types: [...new Set(list.map((item) => (item.kind === 'embed' ? 'video' : item.kind || item.media_type || '')).filter(Boolean))].sort(),
    levels: [...new Set(list.map((item) => item.level || '').filter(Boolean))].sort(),
    sources: [...new Set(list.map((item) => item.source_label || '').filter(Boolean))].sort(),
  };
}

function filterBar(c, facets, state = {}) {
  const typeOption = (value, label) =>
    `<option value="${esc(value)}"${state.type === value ? ' selected' : ''}>${esc(label)}</option>`;
  const listOption = (value) => `<option value="${esc(value)}"${state[value === state.level ? 'level' : ''] === value ? ' selected' : ''}>${esc(value)}</option>`;
  return `<div class="media-filter">${
    facets.types.length > 1
      ? `<label><span class="sr-only">${esc(c.mediaVideo)} / ${esc(c.mediaAudio)}</span><select data-media-type>${typeOption('all', c.mediaAll)}${typeOption('video', c.mediaVideo)}${typeOption('audio', c.mediaAudio)}</select></label>`
      : ''
  }${
    facets.levels.length
      ? `<label><span class="sr-only">${esc(c.mediaLevel)}</span><select data-media-level><option value="">${esc(c.mediaLevel)}: ${esc(c.mediaAll)}</option>${facets.levels.map(listOption).join('')}</select></label>`
      : ''
  }${
    facets.sources.length > 1
      ? `<label><span class="sr-only">${esc(c.mediaSource)}</span><select data-media-source><option value="">${esc(c.mediaSource)}: ${esc(c.mediaAll)}</option>${facets.sources.map(listOption).join('')}</select></label>`
      : ''
  }<label class="media-find"><span class="sr-only">${esc(c.mediaSearch)}</span><input type="search" data-media-search value="${esc(state.query || '')}" placeholder="${esc(c.mediaSearchPlaceholder)}" autocomplete="off"></label></div>`;
}

function grid(c, items, empty) {
  return items.length
    ? `<div class="media-grid">${items.map((item) => mediaCard(item, c, { intent: 'follow' })).join('')}</div>`
    : `<p class="empty">${esc(empty)}</p>`;
}

/* Shelves appear when the library is big enough to need them, from real data
   only. With a handful of items a themed shelf is the same items printed
   twice; with a real catalogue, one flat wall is what the learner scrolls
   past. Same rule the book library uses (D-057). */
const SHELF_THRESHOLD = 8;
const SHORT_LISTEN_MS = 5 * 60 * 1000;

function themedShelf(id, title, c, items) {
  if (!items.length) return '';
  return `<section class="media-shelf media-shelf--themed" data-media-shelf="${esc(id)}"><div class="section-head"><h3>${esc(title)}</h3></div><div class="media-grid media-grid--rail">${items
    .map((item) => `<div class="media-card__wrap">${mediaCard(item, c, { intent: 'follow' })}</div>`)
    .join('')}</div></section>`;
}

function themedShelves(c, items) {
  if (items.length <= SHELF_THRESHOLD) return '';
  const short = items.filter(
    (item) => Number(item.duration_ms) > 0 && Number(item.duration_ms) <= SHORT_LISTEN_MS,
  );
  const videos = items.filter((item) => item.kind === 'video' || item.kind === 'embed');
  const audio = items.filter((item) => item.kind === 'audio');
  return `${short.length >= 3 ? themedShelf('short', c.mediaShort, c, short) : ''}${
    videos.length >= 3 && audio.length ? themedShelf('videos', c.mediaVideos, c, videos) : ''
  }${audio.length >= 3 && videos.length ? themedShelf('audio', c.mediaAudioShelf, c, audio) : ''}`;
}

/* The covers lead; search, type, level and source are how a learner finds one
   thing they already have in mind, folded away until wanted rather than being
   the first thing Listening shows (D-057 rule 17). */
function shelf(title, attribute, c, state, { utility = true } = {}) {
  const items = filterMediaItems(state.items, state);
  const facets = mediaFacets(state.items);
  const find = utility && state.items.length
    ? `<details class="library-utility"><summary><span>${esc(c.mediaFind)}</span></summary>${filterBar(c, facets, state)}</details>`
    : filterBar(c, facets, state);
  return `<section class="media-shelf" ${attribute}><div class="section-head"><h2>${esc(title)}</h2></div>${themedShelves(c, state.items)}<div data-media-results>${grid(c, items, c.mediaNoMatches)}</div>${find}</section>`;
}

/* One small rail, and only from real continuation entries. There is no
   fabricated progress here: if the learner has nothing to continue, the rail
   does not exist. */
function continuationRail(c, entries) {
  if (!entries.length) return '';
  return `<section class="media-shelf media-shelf--rail"><div class="section-head"><h2>${esc(c.mediaContinue)}</h2></div><div class="media-grid media-grid--rail">${entries
    .map((item) => `<div class="media-card__wrap" data-media-continue>${mediaCard(item, c, { intent: item.intent || 'follow' })}</div>`)
    .join('')}</div></section>`;
}

export function mediaContinuation(memory, language) {
  return continuationEntries(memory, { experience: 'listening' })
    .slice(0, 3)
    .map((entry) => ({
      id: entry.id,
      title: entry.title || entry.id,
      language,
      kind: entry.kind === 'audio' ? 'audio' : 'video',
      duration_ms: entry.duration_ms || 0,
      intent: entry.intent || 'follow',
    }));
}

/* Inner content only: the caller owns a permanent wrapper so this repaints only
   its own container. */
export function mediaLibrary(c, state = {}) {
  const shared = state.sharedItems || [];
  const mine = state.myItems || [];
  const continuation = state.continuation || [];
  const personalState = {
    items: mine,
    type: state.myType || 'all',
    query: state.myQuery || '',
    level: state.myLevel || '',
    source: state.mySource || '',
  };
  return `${shelf(c.mediaLibrary, 'data-media-shared', c, { items: shared, type: state.type || 'all', query: state.query || '', level: state.level || '', source: state.source || '' })}${continuationRail(c, continuation)}${shelf(c.mediaMyContent, 'data-media-personal', c, personalState)}`;
}

/* The mounted library: reads the one catalogue, then filters in place. A read
   failure is a retry, never an empty library - "we could not reach it" and "you
   have nothing" must not look the same. */
export function paintMediaLibrary(container, ctx) {
  if (!container) return () => {};
  const { api, c, language, memory, location, alive } = ctx;
  let shared = [];
  let error = false;
  let loaded = false;
  let filters = { type: 'all', query: '', level: '', source: '' };
  let personalFilters = { type: 'all', query: '', level: '', source: '' };

  const personal = () =>
    (memory?.value?.mediaImports || []).map((entry) => ({
      ...entry,
      language: entry.language || language,
      source_label: entry.provider ? '' : '',
    }));

  function paint() {
    if (!alive()) return;
    const state = {
      ...filters,
      myType: personalFilters.type,
      myQuery: personalFilters.query,
      myLevel: personalFilters.level,
      mySource: personalFilters.source,
      sharedItems: shared,
      myItems: personal(),
      continuation: mediaContinuation(memory, language),
    };
    container.innerHTML = `${error ? `<p class="notice" role="alert">${esc(c.unavailable)} <button type="button" data-media-retry>${esc(c.retry)}</button></p>` : ''}${!loaded && !error ? `<p class="loading" role="status">${esc(c.loading)}</p>` : mediaLibrary(c, state)}`;
    bindImages(container, c);
    container.querySelector('[data-media-retry]')?.addEventListener('click', load);
    bind(container);
  }

  function readFilters(source, target) {
    const read = (name) => source.querySelector(`[data-media-${name}]`)?.value || '';
    target.type = read('type') || 'all';
    target.query = read('search') || '';
    target.level = read('level') || '';
    target.source = read('source') || '';
  }

  function bind(scope) {
    scope.querySelectorAll('[data-media-shared] [data-media-type], [data-media-shared] [data-media-search], [data-media-shared] [data-media-level], [data-media-shared] [data-media-source]').forEach((control) => {
      const event = control.tagName === 'INPUT' ? 'input' : 'change';
      control.addEventListener(event, () => {
        readFilters(scope.querySelector('[data-media-shared]'), filters);
        repaintShelf(scope.querySelector('[data-media-shared]'), shared, filters, c.mediaNoMatches);
      });
    });
    scope.querySelectorAll('[data-media-personal] [data-media-type], [data-media-personal] [data-media-search], [data-media-personal] [data-media-level], [data-media-personal] [data-media-source]').forEach((control) => {
      const event = control.tagName === 'INPUT' ? 'input' : 'change';
      control.addEventListener(event, () => {
        readFilters(scope.querySelector('[data-media-personal]'), personalFilters);
        repaintShelf(scope.querySelector('[data-media-personal]'), personal(), personalFilters, c.mediaNoMatches);
      });
    });
  }

  // Only the results region repaints, so typing in the search field never costs
  // the learner their focus or their scroll position.
  function repaintShelf(section, items, state, empty) {
    const results = section?.querySelector('[data-media-results]');
    if (!results) return;
    results.innerHTML = grid(c, filterMediaItems(items, state), empty);
    bindImages(results, c);
  }

  async function load() {
    loaded = false;
    error = false;
    paint();
    try {
      const payload = await api.listeningLibrary(language);
      if (!alive()) return;
      shared = (payload?.items || []).filter((item) => item.language === language);
    } catch {
      if (!alive()) return;
      error = true;
    }
    loaded = true;
    paint();
  }

  load();
  return () => {};
}

/* ---------------------------------------------------------------------------
   The Media Source Importer (Platform Admin)

   Preview first, then import. The preview shows what was really resolved - a
   thumbnail, a title, a type, a source, a duration, the learning language and
   the level - and every field an operator may correct is editable before
   anything is written. One failed source is one row; it never ends the batch.
   --------------------------------------------------------------------------- */

const ADMIN_FIELDS = ['title', 'level', 'language', 'topic', 'tags'];

function adminField(c, index, field, value, label) {
  return `<label><span>${esc(label)}</span><input type="text" data-admin-media-field="${esc(field)}" data-admin-media-index="${index}" value="${esc(value || '')}" maxlength="240"></label>`;
}

function adminPreviewRow(c, item, index) {
  const url = esc(item.url || '');
  if (item.status !== 'ok')
    return `<article class="admin-media-source admin-media-source--error" data-admin-media-source="${index}"><p class="meta" lang="en">${url}</p><p class="notice" role="alert">${esc(item.detail || item.error || c.adminMediaStatusError)}</p></article>`;
  const thumbnail = safeExternal(item.thumbnail_url) ? item.thumbnail_url : '';
  return `<article class="admin-media-source" data-admin-media-source="${index}"><div class="admin-media-preview"><span class="admin-media-thumb">${
    thumbnail
      ? `<img src="${esc(thumbnail)}" alt="${esc(c.mediaThumbnailAlt)}" loading="lazy" referrerpolicy="no-referrer">`
      : art({ ...item, poster_url: '' })
  }</span><div><p class="meta" lang="en">${url}</p><p><strong>${esc(item.title || '')}</strong></p><p class="byline">${esc(item.source_label || item.provider || '')}${Number(item.duration_ms) > 0 ? ` · ${esc(duration(item.duration_ms))}` : ''}${item.media_type ? ` · ${esc(item.media_type === 'video' ? c.mediaVideo : c.mediaAudio)}` : ''}</p></div></div><div class="admin-media-fields">${adminField(c, index, 'title', item.title, c.adminMediaTitleField)}${adminField(c, index, 'level', item.level, c.adminMediaLevelField)}${adminField(c, index, 'language', item.language, c.adminMediaLanguage)}${adminField(c, index, 'topic', item.topic, c.adminMediaTopicField)}${adminField(c, index, 'tags', (item.tags || []).join(', '), c.adminMediaTagsField)}</div><p class="meta">${esc(item.has_transcript ? c.adminMediaReady : c.adminMediaStatusError)}</p></article>`;
}

export function renderAdminMediaImporter(c, state = {}) {
  const previews = state.previews || [];
  const results = state.results || [];
  const busy = state.busy || '';
  const language = state.language === 'zh' ? 'zh' : 'en';
  const resultRows = results.length
    ? `<section class="admin-media-results"><h3>${esc(c.adminMediaResults)}</h3><ul>${results
        .map((result) =>
          result.status === 'ok'
            ? `<li class="admin-media-result admin-media-result--ok"><span lang="en">${esc(result.url || '')}</span><small>${esc(result.detail || c.adminMediaStatusOk)}</small></li>`
            : `<li class="admin-media-result admin-media-result--error"><span lang="en">${esc(result.url || '')}</span><small>${esc(result.detail || c.adminMediaStatusError)}</small></li>`,
        )
        .join('')}</ul></section>`
    : '';
  const previewBlock = previews.length
    ? `<div data-admin-media-preview-output>${previews.map((item, index) => adminPreviewRow(c, item, index)).join('')}</div>`
    : '<div data-admin-media-preview-output></div>';
  return `<section class="media-shelf admin-media"><div class="section-head"><div><h2>${esc(c.adminMediaTitle)}</h2><p>${esc(c.adminMediaNote)}</p></div></div><form data-admin-media-form><div class="admin-media-grid"><label><span>${esc(c.adminMediaUrls)}</span><textarea data-admin-media-urls rows="4" placeholder="${esc(c.adminMediaUrlsPlaceholder)}"></textarea></label><label><span>${esc(c.adminMediaFiles)}</span><input type="file" data-admin-media-files multiple accept="video/*,audio/*"></label><label><span>${esc(c.adminMediaLanguage)}</span><select data-admin-media-language><option value="en"${language === 'en' ? ' selected' : ''}>English</option><option value="zh"${language === 'zh' ? ' selected' : ''}>中文</option></select></label></div><div class="button-row"><button class="outline" type="button" data-admin-media-preview ${busy ? 'disabled' : ''}>${esc(busy === 'preview' ? c.adminMediaPreviewing : c.adminMediaPreview)}</button><button class="primary" type="button" data-admin-media-import ${busy === 'preview' || !previews.length ? 'disabled' : ''}>${esc(busy === 'import' ? c.adminMediaImporting : c.adminMediaImport)}</button></div><p class="meta" data-admin-media-status role="status">${esc(previews.length ? c.adminMediaReady : c.adminMediaChooseSource)}</p>${previewBlock}<div data-admin-media-results>${resultRows}</div></form></section>`;
}

/* Self-mounting, like every other admin section: it owns its own container so
   one section's repaint never touches another's DOM. */
export function paintAdminMediaImporter(container, ctx) {
  if (!container) return;
  const { api, c, language, alive } = ctx;
  let urls = '';
  let files = [];
  let chosen = language === 'zh' ? 'zh' : 'en';
  let previews = [];
  let results = [];
  let busy = '';

  function paint() {
    if (!alive()) return;
    container.innerHTML = renderAdminMediaImporter(c, { language: chosen, previews, results, busy });
    container.querySelector('[data-admin-media-urls]')?.addEventListener('input', (event) => {
      urls = event.target.value;
    });
    container.querySelector('[data-admin-media-files]')?.addEventListener('change', (event) => {
      files = [...(event.target.files || [])];
    });
    container.querySelector('[data-admin-media-language]')?.addEventListener('change', (event) => {
      chosen = event.target.value;
    });
    container.querySelector('[data-admin-media-preview]')?.addEventListener('click', preview);
    container.querySelector('[data-admin-media-import]')?.addEventListener('click', runImport);
    bindImages(container, c);
  }

  const wantedUrls = () =>
    urls
      .split(/[\n,]/)
      .map((line) => line.trim())
      .filter(Boolean);

  function corrections() {
    const byIndex = new Map();
    container.querySelectorAll('[data-admin-media-field]').forEach((input) => {
      const index = Number(input.dataset.adminMediaIndex);
      const entry = byIndex.get(index) || { tags: '' };
      entry[input.dataset.adminMediaField] = input.value;
      byIndex.set(index, entry);
    });
    return byIndex;
  }

  async function preview() {
    const list = wantedUrls();
    if (!list.length && !files.length) return;
    busy = 'preview';
    paint();
    try {
      const payload = list.length ? await api.adminMediaPreview(list, chosen) : { items: [] };
      if (!alive()) return;
      previews = payload?.items || [];
      results = [];
    } catch {
      if (!alive()) return;
      previews = [];
      results = [{ url: '', status: 'error', detail: c.adminMediaStatusError }];
    } finally {
      busy = '';
      if (alive()) paint();
    }
  }

  async function runImport() {
    const corrected = corrections();
    const list = wantedUrls();
    if (!list.length && !files.length) return;
    busy = 'import';
    paint();
    try {
      const items = list.map((url, index) => {
        const preview = previews[index] || {};
        const edit = corrected.get(index) || {};
        return {
          url,
          title: edit.title || preview.title || '',
          level: edit.level || preview.level || '',
          language: edit.language || '',
          topic: edit.topic || '',
          tags: String(edit.tags || '')
            .split(',')
            .map((tag) => tag.trim())
            .filter(Boolean),
        };
      });
      const payload = files.length
        ? await api.adminMediaUpload(files, chosen)
        : await api.adminMediaImport(items, chosen);
      if (!alive()) return;
      results = [...(payload?.items || []), ...(files.length ? [] : [])];
      urls = '';
      files = [];
      previews = [];
    } catch {
      if (!alive()) return;
      results = [{ url: '', status: 'error', detail: c.adminMediaStatusError }];
    } finally {
      busy = '';
      if (alive()) paint();
    }
  }

  paint();
}
