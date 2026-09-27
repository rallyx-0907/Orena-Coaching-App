/* Pure data mapping for Search (frame 27): real sources only, no invented result (rule 40).

   No global search endpoint exists (docs SCRATCH C2 "Explicit checks"), so this composes what
   does: the shared vocabulary catalogue, the learner's own cross-owner collection, the published
   Reading articles and the Listening catalogue (both client-filtered by title/topic, since neither
   takes a free-text query), and the learner's own device-memory imports (product/memory.js).
   Curated vocabulary collections and full-text search over transcripts/article sentences have no
   endpoint in this build either; they are not composed here (see the search report's backend gaps).

   Every function here is DOM-free and network-free: screen.js calls the API and memory reads, and
   hands their answers to these functions. */

const RECENT_KEY = 'orena.next.search.recent.v1';
export const RECENT_MAX = 8;

export function normalizeQuery(raw) {
  return String(raw ?? '').trim();
}

function safeParse(text) {
  try {
    const parsed = JSON.parse(text || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function readRecent(storage) {
  if (!storage) return [];
  let raw = '';
  try {
    raw = storage.getItem(RECENT_KEY) || '';
  } catch {
    return [];
  }
  return safeParse(raw)
    .filter((entry) => typeof entry === 'string' && entry.trim())
    .map((entry) => entry.trim())
    .slice(0, RECENT_MAX);
}

/* Most-recent-first, case-insensitively de-duplicated, capped. Returns the new list; storage
   errors (private mode, quota) are swallowed the same way product/memory.js swallows them - a
   recent-search list is a convenience, never a place a learner's real content lives. */
export function pushRecent(storage, query) {
  const q = normalizeQuery(query);
  const current = readRecent(storage);
  if (!q) return current;
  const next = [q, ...current.filter((entry) => entry.toLowerCase() !== q.toLowerCase())].slice(0, RECENT_MAX);
  try {
    storage?.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* this visit only */
  }
  return next;
}

export function matchesText(haystack, needle) {
  const n = String(needle ?? '').trim().toLowerCase();
  if (!n) return true;
  return String(haystack ?? '').toLowerCase().includes(n);
}

function firstMeaning(list) {
  const first = Array.isArray(list) ? list[0] : null;
  if (first == null) return '';
  if (typeof first === 'string') return first;
  return String(first.text ?? first.meaning ?? '');
}

/* GET /api/vocabulary/catalogue/search - the shared, admin-curated dictionary. Server-searched
   and server-bounded; no client filtering. */
export function wordItems(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items
    .map((entry) => {
      const word = String(entry?.word ?? '').trim();
      if (!word) return null;
      const meta = [firstMeaning(entry?.short_meanings), entry?.part_of_speech].filter(Boolean).join(' · ');
      return { kindKey: 'word', title: word, meta, open: { route: 'word', id: word } };
    })
    .filter(Boolean);
}

/* GET /api/reading/articles - one page of published articles, client-filtered by title/topic
   since the route takes no free-text query (SCRATCH C2 §1). */
export function articleItems(payload, query) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items
    .filter((article) => matchesText(article?.title, query) || matchesText(article?.topic, query))
    .map((article) => {
      const id = article?.id;
      const title = String(article?.title ?? '').trim();
      if (id == null || !title) return null;
      const meta = [article?.topic, article?.level].filter(Boolean).join(' · ');
      return { kindKey: 'article', title, meta, open: { route: 'content', id: `article:${id}` } };
    })
    .filter(Boolean);
}

/* GET /api/listening/library - the curated + admin-imported catalogue, client-filtered the same
   way (the route takes level/topic/tag filters, not a free-text query). */
export function listeningItems(payload, query) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  return items
    .filter((item) => matchesText(item?.title, query) || matchesText(item?.topic, query))
    .map((item) => {
      const id = item?.id;
      const title = String(item?.title ?? '').trim();
      if (id == null || !title) return null;
      const meta = [item?.topic, item?.level].filter(Boolean).join(' · ');
      return { kindKey: 'media', title, meta, open: { route: 'content', id: `media:${id}` } };
    })
    .filter(Boolean);
}

/* The learner's own device-memory imports (product/memory.js `learnerMemory().value`).

   `imports` (pasted text) already stores its own id as "text:<uuid>" - screens/content/model.js
   splits a content route id on its *first* colon only, so the route id is that stored id
   unchanged (one prefix, not two); screens/content/screen.js reconstructs `"text:" + id` to find
   it again, so doubling the prefix here would make it unfindable.

   `mediaImports` (a pasted link or an uploaded file, told apart only by their own "url:"/
   "upload:" id prefix) both resolve through the *same* `api.mediaMy(id)` call
   (screens/content/screen.js's `kind === 'upload'` branch, infrastructure/api.js's own doc:
   "Two kinds of id are accepted"): a real catalogue lesson is the only thing that opens through
   `kind === 'media'`. So every device media import is kind 'upload' here, and the route id is
   "upload:" + the stored id verbatim (its own url:/upload: prefix survives inside the rest of
   the string, which parseContentId does not split further for a non-book kind). */
export function deviceTextItems(memoryValue, query) {
  const items = Array.isArray(memoryValue?.imports) ? memoryValue.imports : [];
  return items
    .filter((item) => matchesText(item?.title, query))
    .map((item) => {
      const title = String(item?.title ?? '').trim();
      if (!item?.id || !title) return null;
      return { kindKey: 'text', title, meta: '', open: { route: 'content', id: item.id } };
    })
    .filter(Boolean);
}

export function deviceMediaItems(memoryValue, query) {
  const items = Array.isArray(memoryValue?.mediaImports) ? memoryValue.mediaImports : [];
  return items
    .filter((item) => matchesText(item?.title, query))
    .map((item) => {
      const title = String(item?.title ?? '').trim();
      const rawId = String(item?.id ?? '');
      if (!rawId || !title) return null;
      return { kindKey: 'upload', title, meta: '', open: { route: 'content', id: `upload:${rawId}` } };
    })
    .filter(Boolean);
}

const COLLECTION_KIND = { language: 'word', reading: 'article', media: 'media', writing: 'writing', speaking: 'speaking', grammar: 'grammar' };
const RELATIONSHIP_KEY = { saved: 'relationship_saved', completed: 'relationship_completed', practised: 'relationship_practised', submitted: 'relationship_submitted', spoken: 'relationship_spoken' };

/* The `#/page?id=<value>&intent=…` string `collection_query.py`'s `route()` builds (the old UI's
   own scheme) still carries the one thing this screen needs out of it for reading/media/speaking:
   an `id` query value already shaped `<contentKind>:<value>` (e.g. "article:123", "media:456") -
   exactly the shared content-id contract's own shape (SURFACE_AGENT_BRIEF §"Data and behaviour
   notes"). Parsed, never executed: this never navigates through the legacy route itself. */
export function legacyActionId(route) {
  const raw = String(route ?? '');
  const at = raw.indexOf('?');
  if (at < 0) return '';
  try {
    return new URLSearchParams(raw.slice(at + 1)).get('id') || '';
  } catch {
    return '';
  }
}

/* GET /api/collection - the learner's own kept/practised/submitted items across every wired
   owner. An entry whose real destination cannot be resolved (no `action`, e.g. a free Speaking
   take with no lesson) opens nothing (rule 40): the row renders, but not as a link. */
export function collectionItems(payload, relationshipLabel) {
  const entries = Array.isArray(payload?.entries) ? payload.entries : [];
  return entries
    .map((entry) => {
      const domain = String(entry?.ref?.domain ?? '');
      const bareId = String(entry?.ref?.id ?? '');
      const title = String(entry?.title ?? '').trim();
      if (!title) return null;
      let open = null;
      /* `ref.id` for a 'language' entry is the saved word NFKC-normalised and casefolded for
         de-duplication (writing_coach/collection_query.py `language_entries`), not the word text
         itself - the word route takes the word's own text (no word ids exist, SURFACE_AGENT_BRIEF
         "Data and behaviour notes"), which is `title` here (the same string the row displays). */
      if (domain === 'language' && bareId) open = { route: 'word', id: title };
      else if (domain === 'writing' && bareId) open = { route: 'writingDraft', id: bareId };
      else if (domain === 'grammar' && bareId) open = { route: 'gconcept', id: bareId };
      else if (domain === 'reading' || domain === 'media' || domain === 'speaking') {
        const inner = legacyActionId(entry?.action?.route);
        if (inner) open = { route: 'content', id: inner };
      }
      const snippet = String(entry?.snippet ?? '').trim();
      const relKey = RELATIONSHIP_KEY[entry?.relationship];
      const meta = snippet || (relKey && typeof relationshipLabel === 'function' ? relationshipLabel(relKey) : '');
      return { kindKey: COLLECTION_KIND[domain] || domain, title, meta, open };
    })
    .filter(Boolean);
}

export function totalItems(groups) {
  return groups.reduce((sum, group) => sum + group.items.length, 0);
}
