// Content relationships and unfinished work, scoped to an authenticated owner.
// Practice evidence remains in the existing PostgreSQL-backed capability APIs.
const volatile = new Map();
import { setRemovedImports } from './import-removed.js';
import { restoreConversation } from './conversation.js';
import { practiceIntentions } from './intent.js';
import { readReviewSettings } from './recall-modes.js';
import { readQueue } from './review-queue.js';

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
  /* How far into this one piece the learner has read, as a whole percentage.
     Optional: a place with none is one they have opened and not yet moved
     through, which is a different thing from 0% and is drawn differently. */
  const within = Number(place?.within);
  if (!Number.isFinite(within)) return { index, total };
  return { index, total, within: Math.max(0, Math.min(100, Math.round(within))) };
}

/* Where a record is also sent: a visit (product/continue-sync.js), an import, a kept word's origin
   (product/account-records.js). Set once by the shell; absent in tests and before boot, and then the
   device is the only holder, as it always was. Every method is optional and best effort. */
let placeSink = null;
export function setPlaceSink(sink) {
  placeSink = sink && typeof sink.enter === 'function' ? sink : null;
}

export function learnerMemory(storage, owner, language) {
  const key = `orena.encounters.v1:${encodeURIComponent(owner)}:${language}`;
  let available = true,
    value = {
      imports: [],
      mediaImports: [],
      /* Imports this device knows were deleted (membership ids, never content): they are not listed, not
         re-added by a sync and not opened (product/import-removed.js). Bounded like the account's own. */
      removedImports: [],
      /* For each deleted import, the account RECORD ids this device knew when it deleted (and the account may still
         hold): only those are ever sent a delete again. A record another device made later is never touched. */
      removedRecords: {},
      /* The account's change position (imports) as of this device's last successful list read. A record the account
         holds with a greater sequence was made after it - another device's re-import - never the one deleted here. */
      importMark: 0,
      /* Imports hidden by "Delete from Orena" whose Undo window is open (or was when the page closed): the exact
         snapshot to restore. The deletion itself is committed when the window ends. */
      staged: {},
      kept: [],
      continuation: [],
      expressions: {},
      answers: {},
      revisions: {},
      conversations: {},
      keptLanguage: {},
      /* How this learner wants to be asked: the two limits and which review
         modes are on. Device memory by design, like the kept-language
         provenance above - it is a preference about this device's sessions,
         it owns none of the learner's content, and no persistence decision is
         made for learner-owned data by keeping it here (AGENTS "Architecture
         holds"). */
      reviewSettings: null,
      /* Answers given with no network, waiting their turn. Device memory for
         the same reason: they are this device's unsent work, and they leave
         it as soon as there is a connection. */
      reviewQueue: [],
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
      value.removedImports = (Array.isArray(parsed.removedImports) ? parsed.removedImports : [])
        .filter((x) => typeof x === 'string' && x.length <= 2100)
        .slice(-400);
      value.staged = Object.fromEntries(
        Object.entries(parsed.staged && typeof parsed.staged === 'object' ? parsed.staged : {})
          .filter(([id, snap]) => /^(text|url|upload):/.test(id) && snap && typeof snap === 'object')
          .slice(-20),
      );
      value.importMark = Number.isFinite(parsed.importMark) && parsed.importMark > 0 ? Math.trunc(parsed.importMark) : 0;
      // A deletion the account has not confirmed: { owed: record ids known when it was made, mark: the list position
      // then, media: an uploaded file whose stored copy still has to be confirmed deleted }.
      value.removedRecords = Object.fromEntries(
        Object.entries(parsed.removedRecords && typeof parsed.removedRecords === 'object' ? parsed.removedRecords : {})
          .filter(([id]) => /^(text|url|upload):/.test(id))
          .slice(-400)
          .map(([id, debt]) => {
            const owed = Array.isArray(debt) ? debt : Array.isArray(debt?.owed) ? debt.owed : [];
            return [id, {
              owed: owed.filter((x) => typeof x === 'string').slice(0, 20),
              mark: Number.isFinite(debt?.mark) && debt.mark > 0 ? Math.trunc(debt.mark) : 0,
              media: debt?.media === true,
            }];
          }),
      );
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
            (x.id.startsWith('url:') || x.id.startsWith('upload:')) &&
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
      value.reviewSettings = readReviewSettings(parsed.reviewSettings);
      value.reviewQueue = readQueue(parsed.reviewQueue);
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
  const scopeKey = `${owner}:${language}`;
  setRemovedImports(value.removedImports, scopeKey);
  const isImportId = (id) => /^(text|url|upload):/.test(String(id || ''));
  const markRemoved = (id) => {
    value.removedImports = [...value.removedImports.filter((x) => x !== id), id].slice(-400);
    setRemovedImports(value.removedImports, scopeKey);
  };
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
      const record = keptRecord(term, { ...entry, at: new Date().toISOString() });
      value.keptLanguage = Object.fromEntries(
        [
          ...Object.entries(value.keptLanguage).filter(([k]) => k !== term),
          [term, record],
        ].slice(-200),
      );
      const saved = save();
      placeSink?.keepLanguage?.(record);
      return saved;
    },
    /* One settings sheet, written whole: the sheet reads what is there, changes
       one thing and hands the lot back, so a half-written patch cannot leave
       two settings disagreeing. Clamped on the way in and on the way out. */
    setReview(next) {
      value.reviewSettings = readReviewSettings(next);
      return save();
    },
    /* The whole queue, written at once: it is a list in an order, and a caller
       that could push one and drop another could reorder a schedule. */
    setReviewQueue(next) {
      value.reviewQueue = readQueue(next);
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
      placeSink?.enter(value.continuation[0]);
      return save();
    },
    /* The server's places merged with the device's own (product/continue-sync.js). This is a cache
       refresh: it neither sends anything nor reorders what a visit just wrote. */
    replaceContinuation(list) {
      value.continuation = (Array.isArray(list) ? list : []).slice(0, 20);
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
          /* Which language the review that came back was written in. The
             evaluator answers in the learner's support language, and the
             stored evaluation does not record which one that was - so a piece
             reviewed in Vietnamese and reopened after switching to Chinese
             replayed Vietnamese sentences inside a Chinese room. The device
             remembers what it asked for, which is enough to know whether a
             stored review still speaks the learner's language. */
          support:
            typeof entry.support === 'string' ? entry.support.slice(0, 12) : '',
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
      placeSink?.addImport?.(item);
      return item;
    },
    /* The account's imports merged into this device's list (a cache refresh: it sends nothing). The
       device's own come first; the cap is the same 20 the server keeps. */
    mergeImports(list) {
      const gone = new Set(value.removedImports);
      const items = (Array.isArray(list) ? list : []).filter((x) => !gone.has(x?.id));
      const known = new Set(value.imports.map((x) => x.id));
      const extra = items.filter((x) => x?.id && !/^(url|upload):/.test(x.id) && !known.has(x.id));
      const knownMedia = new Set(value.mediaImports.map((x) => x.id));
      const media = items.filter((x) => x?.id && /^(url|upload):/.test(x.id) && x.title && !knownMedia.has(x.id));
      if (!extra.length && !media.length) return false;
      value.imports = [...value.imports, ...extra].slice(0, 20);
      value.mediaImports = [...value.mediaImports, ...media.map((x) => ({ ...x, language, origin: 'imported' }))].slice(0, 100);
      return save();
    },
    /* Imports the account says were deleted (elsewhere, or here and not yet confirmed): leave this device -
       the lists, the saved place, the kept mark, anything written against them - and stay gone (a sync never
       brings them back, no room opens them). Returns whether anything changed. */
    applyDeletions(ids) {
      let changed = false;
      for (const id of Array.isArray(ids) ? ids : []) {
        if (!isImportId(id)) continue;
        if (!value.removedImports.includes(id)) {
          markRemoved(id);
          placeSink?.dropLocal?.(id);
          changed = true;
        }
        const held = value.imports.length + value.mediaImports.length + value.kept.length + value.continuation.length
          + (id in value.expressions ? 1 : 0) + (id in value.revisions ? 1 : 0) + (id in value.answers ? 1 : 0);
        value.imports = value.imports.filter((x) => x.id !== id);
        value.mediaImports = value.mediaImports.filter((x) => x.id !== id);
        value.kept = value.kept.filter((x) => x !== id);
        value.continuation = value.continuation.filter((x) => x.id !== id);
        delete value.expressions[id];
        delete value.revisions[id];
        delete value.answers[id];
        const after = value.imports.length + value.mediaImports.length + value.kept.length + value.continuation.length
          + (id in value.expressions ? 1 : 0) + (id in value.revisions ? 1 : 0) + (id in value.answers ? 1 : 0);
        if (after !== held) changed = true;
      }
      if (changed) save();
      return changed;
    },
    isRemoved(id) {
      return value.removedImports.includes(id);
    },
    /* "Delete from Orena" with Undo: hide the import everywhere at once (lists, saved place, kept mark, anything
       written against it) but keep an exact snapshot; nothing is sent and nothing is erased until commitRemoval. */
    stageRemoval(id) {
      if (!isImportId(id) || value.staged[id]) return false;
      const snap = {
        imports: value.imports.findIndex((x) => x.id === id),
        mediaImports: value.mediaImports.findIndex((x) => x.id === id),
        continuation: value.continuation.findIndex((x) => x.id === id),
        kept: value.kept.indexOf(id),
      };
      snap.import = snap.imports >= 0 ? value.imports[snap.imports] : null;
      snap.media = snap.mediaImports >= 0 ? value.mediaImports[snap.mediaImports] : null;
      snap.place = snap.continuation >= 0 ? value.continuation[snap.continuation] : null;
      snap.expression = value.expressions[id] ?? null;
      snap.revisions = value.revisions[id] ?? null;
      snap.answer = value.answers[id] ?? null;
      value.staged[id] = snap;
      value.imports = value.imports.filter((x) => x.id !== id);
      value.mediaImports = value.mediaImports.filter((x) => x.id !== id);
      value.kept = value.kept.filter((x) => x !== id);
      value.continuation = value.continuation.filter((x) => x.id !== id);
      delete value.expressions[id];
      delete value.revisions[id];
      delete value.answers[id];
      markRemoved(id); // hidden and unopenable while the window is open
      save();
      return true;
    },
    isStaged(id) {
      return Boolean(value.staged[id]);
    },
    stagedIds() {
      return Object.keys(value.staged);
    },
    /* Undo: the import comes back exactly - same place in its list, same saved place, same kept mark. */
    undoRemoval(id) {
      const snap = value.staged[id];
      if (!snap) return false;
      const put = (list, index, item) => {
        if (item) list.splice(Math.min(Math.max(index, 0), list.length), 0, item);
      };
      put(value.imports, snap.imports, snap.import);
      put(value.mediaImports, snap.mediaImports, snap.media);
      put(value.continuation, snap.continuation, snap.place);
      if (snap.kept >= 0) value.kept.splice(Math.min(snap.kept, value.kept.length), 0, id);
      if (snap.expression != null) value.expressions[id] = snap.expression;
      if (snap.revisions != null) value.revisions[id] = snap.revisions;
      if (snap.answer != null) value.answers[id] = snap.answer;
      delete value.staged[id];
      value.removedImports = value.removedImports.filter((x) => x !== id);
      setRemovedImports(value.removedImports, scopeKey);
      save();
      return true;
    },
    /* The Undo window ended (or the page is closing): the deletion is real - sent to the account, or recorded to be. */
    commitRemoval(id) {
      if (!value.staged[id]) return Promise.resolve(false);
      delete value.staged[id];
      return this.remove(id);
    },
    /* Deletions staged by an earlier page that never reached their end (Undo is not offered after a reload):
       commit them now, except the ones whose window is open in this page. */
    flushStaged(keep = []) {
      return Promise.all(Object.keys(value.staged).filter((id) => !keep.includes(id)).map((id) => this.commitRemoval(id)));
    },
    /* A deletion the account has not confirmed, or null: { owed, mark, media } (see the load above). */
    debtFor(id) {
      return value.removedRecords[id] || null;
    },
    debtIds() {
      return Object.keys(value.removedRecords);
    },
    /* Replace (or, with null, settle) the unconfirmed deletion of an import. */
    setDebt(id, debt) {
      if (debt) value.removedRecords[id] = debt;
      else delete value.removedRecords[id];
      save();
    },
    /* The account's position as of a successful list read; it only moves forward. */
    setImportMark(mark) {
      if (!Number.isFinite(mark) || mark <= value.importMark) return false;
      value.importMark = Math.trunc(mark);
      return save();
    },
    /* The same import was kept again by another device after this one deleted it: it is the learner's again here.
       An older record this device still owes a delete for stays owed - only the marker that hid the import clears. */
    reinstate(id) {
      if (!value.removedImports.includes(id)) return false;
      value.removedImports = value.removedImports.filter((x) => x !== id);
      setRemovedImports(value.removedImports, scopeKey);
      save();
      return true;
    },
    get scope() {
      return scopeKey;
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
      // Importing it again is a new decision: the earlier deletion no longer hides it on this device. (A delete the
      // account has not confirmed stays owed for the OLD record - only the marker that hid the import clears.)
      const wasRemoved = value.removedImports.includes(id);
      if (wasRemoved) {
        value.removedImports = value.removedImports.filter((x) => x !== id);
        setRemovedImports(value.removedImports, scopeKey);
      }
      const existed = value.mediaImports.some((x) => x.id === id);
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
      save();
      // A new (or re-)import is kept with the account as a NEW record whatever this page believed about an earlier one; an
      // item that was already listed is only re-sent when its first send never reached the account.
      placeSink?.addImport?.(item, { fresh: !existed || wasRemoved });
      return true;
    },
    remove(id) {
      if (isImportId(id)) {
        markRemoved(id);
        // What this deletion owes the account: the records this device knows now - and always a text's own record, whose
        // id is the import's id - plus the list position, so a record made later by another device is told apart from
        // any this device had not yet read (a delete before the first list read must not be lost).
        const owed = (placeSink?.recordsFor?.(id) || []).map(String);
        if (id.startsWith('text:') && !owed.includes(id.slice(5))) owed.push(id.slice(5));
        value.removedRecords[id] = { owed: owed.slice(0, 20), mark: value.importMark, media: id.startsWith('upload:') };
      }
      value.imports = value.imports.filter((x) => x.id !== id);
      value.mediaImports = value.mediaImports.filter((x) => x.id !== id);
      value.kept = value.kept.filter((x) => x !== id);
      value.continuation = value.continuation.filter((x) => x.id !== id);
      placeSink?.clear(id);
      placeSink?.dropLocal?.(id);
      const accountDeletion = placeSink?.removeImport?.(id);
      delete value.expressions[id];
      delete value.revisions[id];
      delete value.answers[id];
      save();
      return Promise.resolve(accountDeletion).catch(() => false);
    },
  };
}
