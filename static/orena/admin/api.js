/* The admin console's server boundary.

   Console aggregates live under /api/admin/console; everything else is an
   existing admin contract used exactly as it was built: the AI control plane
   (/api/admin/ai/*), readiness and product activity, the media preview and the
   vocabulary source importer. Every route is guarded on the server; nothing
   here decides who may call it. */
import { request } from '../infrastructure/api.js';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

function query(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

const json = (method, body) => ({ method, headers: JSON_HEADERS, body: JSON.stringify(body ?? {}) });

/* For the few answers whose failure body is itself the information - a health
   check says *why* it failed - read the response instead of throwing it away. */
async function raw(url, options = {}) {
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...options });
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  return { ok: response.ok, status: response.status, body };
}

function files(field, list) {
  const form = new FormData();
  for (const file of list || []) form.append(field, file, file.name);
  return form;
}

export const adminApi = {
  overview: () => request('/api/admin/console/overview'),
  usersSummary: (days = 30) => request(`/api/admin/console/users/summary${query({ days })}`),
  users: (params) => request(`/api/admin/console/users${query(params)}`),
  user: (id) => request(`/api/admin/console/users/${encodeURIComponent(id)}`),
  content: (params) => request(`/api/admin/console/content${query(params)}`),
  contentDetail: (kind, id) => request(`/api/admin/console/content/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`),
  archiveBook: (id) => request(`/api/admin/console/content/book/${encodeURIComponent(id)}/archive`, { method: 'POST' }),
  publishCollection: (id, body) => request(`/api/admin/console/content/vocabulary/${encodeURIComponent(id)}/publish`, json('POST', body)),
  reprocessMedia: (id) => request(`/api/admin/console/content/media/${encodeURIComponent(id)}/reprocess`, { method: 'POST' }),
  importBook: (file, language) => {
    const form = files('files', [file]);
    form.append('learning_language', language);
    return request('/api/admin/console/imports/books', { method: 'POST', body: form });
  },
  importMediaUrl: (item, language) => request('/api/admin/console/imports/media', json('POST', { language, items: [item] })),
  importMediaFile: (file, language) => {
    const form = files('file', [file]);
    form.append('language', language);
    return request('/api/admin/console/imports/media-upload', { method: 'POST', body: form });
  },
  mediaPreview: (urls, language) => request('/api/media/admin/preview', json('POST', { urls, language })),
  vocabularyPreview: (list) => request('/api/admin/vocabulary/preview', { method: 'POST', body: files('files', list) }),
  vocabularyImport: (list, metadata, mappings) => {
    const form = files('files', list);
    form.append('metadata', JSON.stringify(metadata));
    form.append('mappings', JSON.stringify(mappings));
    return request('/api/admin/vocabulary/import', { method: 'POST', body: form });
  },
  history: (params) => request(`/api/admin/console/imports/history${query(params)}`),
  runtime: () => request('/api/admin/console/runtime'),
  aiConfig: () => request('/api/admin/ai/config'),
  aiCatalog: () => request('/api/admin/ai/catalog'),
  aiOperations: (limit = 200) => request(`/api/admin/ai/operations${query({ limit })}`),
  saveCapability: (key, body) => raw(`/api/admin/ai/config/${encodeURIComponent(key)}`, json('PUT', body)),
  testCapability: (key, standby = false) =>
    raw(`/api/admin/ai/test/${encodeURIComponent(key)}${standby ? '?standby=true' : ''}`, { method: 'POST' }),
  testProvider: (id, body = {}) => raw(`/api/admin/ai/credentials/${encodeURIComponent(id)}/test`, json('POST', body)),
  saveProvider: (id, body) => raw(`/api/admin/ai/credentials/${encodeURIComponent(id)}`, json('PUT', body)),
  removeProvider: (id) => raw(`/api/admin/ai/credentials/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  // Reading Content Engine. Submitting is multipart because a file may ride
  // with it; everything else is JSON. Nothing here decides who may call it.
  readingSources: () => request('/api/admin/reading/sources'),
  readingSetSourceState: (id, state) =>
    request(`/api/admin/reading/sources/${encodeURIComponent(id)}`, json('POST', { state })),
  readingSetPolling: (id, state, enabled) =>
    request(`/api/admin/reading/sources/${encodeURIComponent(id)}`, json('POST', { state, polling_enabled: enabled })),
  readingQueue: (params) => request(`/api/admin/reading/queue${query(params)}`),
  readingArticle: (id) => request(`/api/admin/reading/articles/${encodeURIComponent(id)}`),
  readingEditArticle: (id, body) =>
    request(`/api/admin/reading/articles/${encodeURIComponent(id)}`, json('POST', body)),
  readingSetStatus: (id, status, reason = '') =>
    request(`/api/admin/reading/articles/${encodeURIComponent(id)}/status`, json('POST', { status, reason })),
  readingDecideTarget: (articleId, targetId, approved) =>
    request(
      `/api/admin/reading/articles/${encodeURIComponent(articleId)}/targets/${encodeURIComponent(targetId)}`,
      json('POST', { approved }),
    ),
  readingJobs: (params) => request(`/api/admin/reading/jobs${query(params)}`),
  readingJob: (id) => request(`/api/admin/reading/jobs/${encodeURIComponent(id)}`),
  readingRetryJob: (id) => request(`/api/admin/reading/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
  readingOperations: () => request('/api/admin/reading/operations'),
  readingSubmit: (submitted, file = null) => {
    const form = new FormData();
    for (const [key, value] of Object.entries(submitted)) form.append(key, value === true ? 'true' : value === false ? 'false' : String(value ?? ''));
    if (file) form.append('upload', file, file.name);
    return request('/api/admin/reading/jobs', { method: 'POST', body: form });
  },
  readiness: () => request('/api/admin/readiness-summary'),
  productActivity: (days = 7) => request(`/api/admin/product-activity${query({ window_days: days })}`),
};

/* The words a failed answer carries, whatever shape it came in. */
export function failureReason(result) {
  const detail = result?.body?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') return String(detail.message || detail.error || '');
  return '';
}
