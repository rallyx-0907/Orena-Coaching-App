// Content relationships and unfinished work, scoped to an authenticated owner.
// Practice evidence remains in the existing PostgreSQL-backed capability APIs.
const volatile = new Map();
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
    };
  try {
    const parsed =
      volatile.get(key) || JSON.parse(storage.getItem(key) || 'null');
    if (parsed && typeof parsed === 'object') {
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
                revision_no: Number.isInteger(x.revision_no) ? x.revision_no : null,
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
    keep(id) {
      value.kept = value.kept.includes(id)
        ? value.kept.filter((x) => x !== id)
        : [id, ...value.kept].slice(0, 100);
      return save();
    },
    enter({ id, title, segment, intent = null, source_url, excerpt }) {
      const previous = value.continuation.find((x) => x.id === id);
      value.continuation = [
        {
          id,
          title,
          segment: segment ?? previous?.segment ?? '',
          intent,
          source_url: source_url ?? previous?.source_url ?? '',
          excerpt: String(excerpt ?? previous?.excerpt ?? '').slice(0, 1200),
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
          revision_no: Number.isInteger(entry.revision_no) ? entry.revision_no : null,
          overall: Number.isFinite(entry.overall) ? entry.overall : null,
          level: typeof entry.level === 'string' ? entry.level.slice(0, 24) : '',
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
    addMedia({ id, title, kind, duration_ms }) {
      if (!id.startsWith('url:') || !title) return false;
      const item = {
        id,
        title: String(title).slice(0, 500),
        kind,
        language,
        origin: 'imported',
        duration_ms,
      };
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
