/* Gate for the derived General catalogue's title (D-188): the server sends `system_kind` with an English fallback
   title; Discover, Library and Collection Detail name it in the interface language (EN, VI, ZH) and leave every other
   collection's stored title alone. */
import assert from 'node:assert/strict';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const copy = await import('../static/orena/copy/index.js');
const { collectionTitle, GENERAL_SYSTEM_KIND } = await import('../static/orena/copy/general-catalogue.js');
const { entryFromCollection } = await import('../static/orena/screens/discover/model.js');
const { curatedRows } = await import('../static/orena/screens/library/model.js');
const { collectionViewModel } = await import('../static/orena/screens/collection/model.js');

const general = { id: 'orena-general-en', title: 'General catalogue', system_kind: GENERAL_SYSTEM_KIND, item_count: 3, language_code: 'en' };
const real = { id: 'toeic', title: '600 TOEIC Essential', item_count: 600, language_code: 'en' };
const expected = { en: 'General catalogue', vi: 'Danh mục chung', zh: '通用词库' };

for (const [ui, title] of Object.entries(expected)) {
  copy.setLanguages({ ui, support: 'en' });
  assert.equal(collectionTitle(general), title, `${ui}: the General catalogue is named in the interface language`);
  assert.equal(entryFromCollection(general).title, title, `${ui}: Discover`);
  assert.equal(curatedRows([general])[0].title, title, `${ui}: Library`);
  assert.equal(collectionViewModel({ ...general, items: [] }).title, title, `${ui}: Collection Detail`);
  assert.equal(collectionTitle(real), real.title, `${ui}: another collection keeps its stored title`);
  assert.equal(entryFromCollection(real).title, real.title);
}

// A server answer without system_kind is a plain collection, even with the same words in its title.
copy.setLanguages({ ui: 'vi', support: 'en' });
assert.equal(collectionTitle({ title: 'General catalogue' }), 'General catalogue');
assert.equal(collectionTitle(null), '');

console.log('test_orena_general_catalogue: ok');
