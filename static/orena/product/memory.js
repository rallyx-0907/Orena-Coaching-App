// Content relationships and unfinished work, scoped to an authenticated owner.
// Practice evidence remains in the existing PostgreSQL-backed capability APIs.
const volatile = new Map();
import { restoreConversation } from './conversation.js';
import { practiceIntentions } from './intent.js';

/* Why a learner kept something. A small, stable vocabulary rather than free
   text, so the collection can say it in either interface language and group by
   it. "manual" is not a reason - it is how the save happened. */
export const KEEP_REASONS = [
  'looked_up',
  'from_reading',
  'from_listening',
  'from_writing',
  'from_speaking',
  'from_grammar',
];

function keptRecord(term, item) {
  return {
    term: String(term).slice(0, 180),
    // The encounter this came from, so the learner can go back to it. Empty
    // when the origin cannot be routed to, which the surface must respect.
    origin: String(item.origin || '').slice(0, 200),
    where: String(item.where || '').slice(0, 240),
    why: item.why,
    context: String(item.context || '').slice(0, 1200),
    at: typeof item.at === 'string' ? item.at.slice(0, 40) : '',
  };
}
/* A position inside a whole, or nothing. Both numbers have to be real and the
   index has to fit inside the total, because a progress figure that cannot be
   true is worse than no progress figure at all. */
function readPlace(place) {
  const index = Number(place?.index);
  const total = Number(place?.total);
  if (!Number.isInteger(index) || !Number.isInteger(total)) return null;
  if (index < 1 || total < 1 || index > total) return null;
  return { index, total };
}

export function learnerMemory(storage, owner, language) {
  const key = `orena.encounters.v1:${encodeURIComponent(owner)}:${language}`;
  let available = true,
    value = {
      imports: [],
      mediaImports: [],
      kept: [],
      continuation: [],
      expressions: {},
      answers: {},
      revisions: {},
      conversations: {},
      keptLanguage: {},
    };
  try {
    const parsed =
      volatile.get(key) || JSON.parse(storage.getItem(key) || 'null');
    if (parsed && typeof parsed === 'object') {
      value.conversations = Object.fromEntries(
        Object.values(parsed.conversations || {})
          .slice(-12)
          .map((raw) => restoreConversation(raw, language))
          .filter(Boolean)
          .map((item) => [item.id, item]),
      );
      value.imports = (Array.isArray(parsed.imports) ? parsed.imports : [])
        .filter(
          (x) =>
            x &&
            x.origin === 'imported' &&
            x.language === language &&
            typeof x.id === 'string' &&
            typeof x.title === 'string' &&
            typeof x.text === 'string' &&
            x.text.length <= 12000,
        )
        .slice(0, 20);
      value.kept = (Array.isArray(parsed.kept) ? parsed.kept : [])
        .filter((x) => typeof x === 'string')
        .slice(0, 100);
      value.mediaImports = (
        Array.isArray(parsed.mediaImports) ? parsed.mediaImports : []
      )
        .filter(
          (x) =>
            x &&
            x.origin === 'imported' &&
            x.language === language &&
            typeof x.id === 'string' &&
            x.id.startsWith('url:') &&
            typeof x.title === 'string',
        )
        .slice(0, 100);
      value.continuation = (
        Array.isArray(parsed.continuation) ? parsed.continuation : []
      )
        .filter(
          (x) => x && typeof x.id === 'string' && typeof x.title === 'string',
        )
        // An intention that is no longer part of the product routes nowhere;
        // the thread is still worth returning to without it.
        .map((x) => ({
          ...x,
          intent: practiceIntentions.includes(x.intent) ? x.intent : null,
        }))
        .slice(0, 20);
      /* What a learner actually submitted for review, kept in order. The live
         draft is overwritten as they type; without this, revising a piece
         destroys the version they revised from. */
      value.revisions = Object.fromEntries(
        Object.entries(parsed.revisions || {})
          .filter(
            ([key, list]) =>
              !['__proto__', 'constructor', 'prototype'].includes(key) &&
              Array.isArray(list),
          )
          .slice(-40)
          .map(([key, list]) => [
            key,
            list
              .filter((x) => x && typeof x.text === 'string')
              .slice(-20)
              .map((x) => ({
                text: x.text.slice(0, 12000),
                at: typeof x.at === 'string' ? x.at.slice(0, 40) : '',
                essay_id: Number.isInteger(x.essay_id) ? x.essay_id : null,
                revision_no: Number.isInteger(x.revision_no)
                  ? x.revision_no
                  : null,
                overall: Number.isFinite(x.overall) ? x.overall : null,
                level: typeof x.level === 'string' ? x.level.slice(0, 24) : '',
              })),
          ]),
      );
      for (const field of ['expressions', 'answers'])
        value[field] = Object.fromEntries(
          Object.entries(parsed[field] || {})
            .filter(
              ([k, v]) =>
                !['__proto__', 'constructor', 'prototype'].includes(k) &&
                typeof v === 'string',
            )
            .slice(-100)
            .map(([k, v]) => [k, v.slice(0, 12000)]),
        );
      value.keptLanguage = Object.fromEntries(
        Object.entries(parsed.keptLanguage || {})
          .filter(
            ([term, item]) =>
              typeof term === 'string' &&
              term &&
              !['__proto__', 'constructor', 'prototype'].includes(term) &&
              item &&
              KEEP_REASONS.includes(item.why),
          )
          .slice(-200)
          .map(([term, item]) => [term, keptRecord(term, item)]),
      );
    }
    if (volatile.has(key)) available = false;
  } catch {
    available = false;
  }
  const save = () => {
    try {
      storage.setItem(key, JSON.stringify(value));
      volatile.delete(key);
      available = true;
    } catch {
      volatile.set(key, value);
      available = false;
    }
    return available;
  };
  return {
    get value() {
      return value;
    },
    get available() {
      return available;
    },
    /* Language the learner chose to keep, with enough around it to answer what
       it was, where they met it, what it meant there and why they kept it. The
       word itself and its review history live in the account library; this is
       the route back and the reason, which that table has no column for.

       Device-scoped, like everything else here: on another device the learner
       still has their words and their review state, and loses only the path
       back to where they found them. */
    rememberLanguage(entry) {
      const term = String(entry?.term || '').trim();
      if (
        !term ||
        ['__proto__', 'constructor', 'prototype'].includes(term) ||
        !KEEP_REASONS.includes(entry.why)
      )
        return false;
      value.keptLanguage = Object.fromEntries(
        [
          ...Object.entries(value.keptLanguage).filter(([k]) => k !== term),
          [term, keptRecord(term, { ...entry, at: new Date().toISOString() })],
        ].slice(-200),
      );
      return save();
    },
    forgetLanguage(term) {
      if (!value.keptLanguage[String(term)]) return false;
      delete value.keptLanguage[String(term)];
      return save();
    },
    keep(id) {
      value.kept = value.kept.includes(id)
        ? value.kept.filter((x) => x !== id)
        : [id, ...value.kept].slice(0, 100);
      return save();
    },
    conversation(state) {
      const valid = restoreConversation(state, language);
      if (!valid) throw Error('Invalid conversation memory');
      value.conversations = Object.fromEntries(
        [
          ...Object.entries(value.conversations).filter(
            ([id]) => id !== valid.id,
          ),
          [valid.id, valid],
        ].slice(-12),
      );
      return save();
    },
    /* An intention survives a later visit that does not name one.

       `segment`, `source_url` and `excerpt` already carried forward from the
       previous visit; `intent` did not, so any arrival that stayed silent
       about it erased what the learner had been doing. Reopening the story
       they had been writing about relabelled their draft "You opened this"
       and sent Resume back to the story - the shelf showed the draft and then
       declined to open it.

       The question is whether the caller stated an intention, not what it
       stated: closing a practice panel passes `intent: null` on purpose, and
       that still means the learner is back to the encounter itself. */
    enter(entry) {
      const { id, title, segment, source_url, excerpt, context, place } = entry;
      const previous = value.continuation.find((x) => x.id === id);
      value.continuation = [
        {
          id,
          title,
          segment: segment ?? previous?.segment ?? '',
          intent: 'intent' in entry ? entry.intent : (previous?.intent ?? null),
          source_url: source_url ?? previous?.source_url ?? '',
          excerpt: String(excerpt ?? previous?.excerpt ?? '').slice(0, 1200),
          /* Where this sits in something larger, when it sits in something
             larger. A chapter is a chapter *of a book*, and "Chapter IV" on its
             own is the database row, not the continuity - so the whole it
             belongs to and its position in that whole travel with the entry.
             Both are optional and neither is guessed: a text that belongs to
             nothing keeps none of this. */
          context: String(context ?? previous?.context ?? '').slice(0, 240),
          place: readPlace(place ?? previous?.place),
        },
        ...value.continuation.filter((x) => x.id !== id),
      ].slice(0, 20);
      return save();
    },
    write(id, text, field = 'expressions') {
      if (
        !['expressions', 'answers'].includes(field) ||
        ['__proto__', 'constructor', 'prototype'].includes(id)
      )
        throw Error('Invalid draft');
      value[field][id] = String(text).slice(0, 12000);
      return save();
    },
    /* Called when a draft is sent for review, never on a keystroke: this is a
       record of what the learner stood behind, not of their typing. */
    recordRevision(id, entry) {
      if (
        ['__proto__', 'constructor', 'prototype'].includes(id) ||
        !String(entry?.text ?? '').trim()
      )
        return false;
      const list = value.revisions[id] || [];
      const last = list[list.length - 1];
      // Reviewing the same words twice is one revision, not two.
      if (last && last.text === entry.text) return save();
      value.revisions[id] = [
        ...list,
        {
          text: String(entry.text).slice(0, 12000),
          at: new Date().toISOString(),
          essay_id: Number.isInteger(entry.essay_id) ? entry.essay_id : null,
          revision_no: Number.isInteger(entry.revision_no)
            ? entry.revision_no
            : null,
          overall: Number.isFinite(entry.overall) ? entry.overall : null,
          level:
            typeof entry.level === 'string' ? entry.level.slice(0, 24) : '',
        },
      ].slice(-20);
      return save();
    },
    add({ title, text }) {
      if (
        value.imports.length >= 20 ||
        !title?.trim() ||
        !text?.trim() ||
        text.length > 12000
      )
        throw Error('Invalid text');
      const item = {
        id: `text:${crypto.randomUUID()}`,
        title: title.trim().slice(0, 120),
        text: text.trim(),
        language,
        origin: 'imported',
        kind: 'text',
      };
      value.imports.unshift(item);
      save();
      return item;
    },
    /* A media membership record. Two kinds of id are accepted, and they mean
       different things: `url:` is a source the learner pasted and Orena can
       re-acquire from the provider, `upload:` is a file whose bytes Orena
       stores itself. Both are imports, so both belong in My content; anything
       else (a curated `media:` lesson) is not the learner's and is refused
       here rather than silently filed as theirs.

       `thumbnail_url` and `provider` are additive: without them the library
       card falls back to the Orena sound artwork, exactly as it did before,
       so a record written by an older build still renders. */
    addMedia({ id, title, kind, duration_ms, thumbnail_url, provider }) {
      const own = id.startsWith('url:') || id.startsWith('upload:');
      if (!own || !title) return false;
      const item = {
        id,
        title: String(title).slice(0, 500),
        kind,
        language,
        origin: 'imported',
        duration_ms,
      };
      /* Only an https thumbnail is stored, for the same reason `art()` only
         renders one: a value that could carry a script or a private address
         never reaches an <img> through the memory record either. */
      const thumbnail = String(thumbnail_url || '');
      if (/^https:\/\//.test(thumbnail) && !thumbnail.includes('@'))
        item.thumbnail_url = thumbnail.slice(0, 600);
      if (provider) item.provider = String(provider).slice(0, 40);
      value.mediaImports = [
        item,
        ...value.mediaImports.filter((x) => x.id !== id),
      ].slice(0, 100);
      return save();
    },
    remove(id) {
      value.imports = value.imports.filter((x) => x.id !== id);
      value.mediaImports = value.mediaImports.filter((x) => x.id !== id);
      value.kept = value.kept.filter((x) => x !== id);
      value.continuation = value.continuation.filter((x) => x.id !== id);
      delete value.expressions[id];
      delete value.revisions[id];
      save();
    },
  };
}
