/* Gate for the Search screen's pure data mapping (frame 27; Design Contract rule 40). Imports only
   the DOM-free module (static/orena/screens/search/model.js), no browser, no network. */
import assert from 'node:assert/strict';

const {
  normalizeQuery, readRecent, pushRecent, RECENT_MAX, matchesText,
  wordItems, articleItems, listeningItems, deviceTextItems, deviceMediaItems,
  legacyActionId, collectionItems, totalItems,
} = await import('../static/orena/screens/search/model.js');

// 1. normalizeQuery / matchesText
assert.equal(normalizeQuery('  coffee  '), 'coffee');
assert.equal(normalizeQuery(null), '');
assert.equal(matchesText('Morning Routines', 'rout'), true);
assert.equal(matchesText('Morning Routines', 'zzz'), false);
assert.equal(matchesText('Anything', ''), true, 'an empty needle matches everything (no filter yet)');

// 2. Recent searches: bounded, de-duplicated case-insensitively, most-recent-first, device-only.
{
  const store = new Map();
  const storage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
  };
  assert.deepEqual(readRecent(storage), [], 'no recent searches yet');
  pushRecent(storage, 'buffer');
  pushRecent(storage, 'Tram');
  const afterDup = pushRecent(storage, 'BUFFER');
  assert.deepEqual(afterDup, ['BUFFER', 'Tram'], 'a repeat query (any case) moves to the front instead of duplicating');
  for (let i = 0; i < RECENT_MAX + 5; i += 1) pushRecent(storage, `q${i}`);
  const bounded = readRecent(storage);
  assert.equal(bounded.length, RECENT_MAX, 'the recent list never exceeds its bound');
  assert.deepEqual(pushRecent(storage, '   '), bounded, 'a blank query leaves the recent list unchanged');
}
{
  // A storage that throws (private mode / quota) degrades to an empty, never-persisted list.
  const angry = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.deepEqual(readRecent(angry), []);
  assert.deepEqual(pushRecent(angry, 'x'), ['x'], 'a storage failure still shows this search for the rest of the visit');
  assert.deepEqual(readRecent(angry), [], 'but nothing survived to be read back, since nothing could be written');
}

// 3. wordItems: the shared vocabulary catalogue, mapped to the word route (no word ids - the
// route param is the word text itself).
{
  const items = wordItems({ items: [{ word: 'buffer', part_of_speech: 'noun', short_meanings: ['a cushion of time'] }, { word: '' }] });
  assert.equal(items.length, 1, 'an entry with no word text is dropped');
  assert.deepEqual(items[0], { kindKey: 'word', title: 'buffer', lang: '', meta: 'a cushion of time · noun', open: { route: 'word', id: 'buffer' } });
  // languages-5 / finding A: GET /api/vocabulary/catalogue/search is queried with a real language
  // (screen.js's own runSearch), carried straight onto every returned word.
  assert.equal(wordItems({ items: [{ word: 'x' }] }, 'zh')[0].lang, 'zh');
}

// 4. articleItems / listeningItems: client-filtered by title or topic (neither route takes a
// free-text query), opened as shared content ids.
{
  const payload = { items: [{ id: 12, title: 'Morning Routines', topic: 'Daily life', level: 'B1' }, { id: 13, title: 'Cooking Basics', topic: 'Food' }] };
  const found = articleItems(payload, 'routine');
  assert.equal(found.length, 1);
  assert.deepEqual(found[0].open, { route: 'content', id: 'article:12' });
  assert.equal(articleItems(payload, 'daily').length, 1, 'a topic match counts too');
  assert.equal(articleItems(payload, 'nothing-like-this').length, 0);

  const media = listeningItems({ items: [{ id: 'm1', title: 'Café Talk', topic: 'Daily life' }] }, 'café');
  assert.deepEqual(media[0].open, { route: 'content', id: 'media:m1' });

  // languages-5 fix (review issue 1, finding B.3 "also Search"): `topic` is kept separate from the
  // joined `meta` string (never folded in unmarked) so screen.js can mark it lang="en" on its own,
  // the same open-taxonomy metadata as Discover's card tag (docs/project/UI_BACKEND_GAPS.md N-35).
  assert.equal(found[0].topic, 'Daily life');
  assert.equal(found[0].meta, 'B1', 'meta carries only the level now - topic moved to its own field');
  const noLevel = articleItems(payload, '').find((a) => a.title === 'Cooking Basics');
  assert.equal(noLevel.topic, 'Food');
  assert.equal(noLevel.meta, '', 'no level on this fixture - meta is empty, not "undefined"/"null"');
  assert.equal(media[0].topic, 'Daily life');
  assert.equal(media[0].meta, '', 'no level on this fixture - meta is empty, not "undefined"/"null"');

  // languages-5 / finding A: the item's own real `language` field wins when present; the search's
  // own queried language is the fallback for a payload that carries none.
  assert.equal(articleItems({ items: [{ id: 1, title: 'x', language: 'zh' }] }, '', 'en')[0].lang, 'zh', 'the article\'s own field wins over the query language');
  assert.equal(articleItems({ items: [{ id: 1, title: 'x' }] }, '', 'en')[0].lang, 'en', 'falls back to the language this search itself queried with');
  assert.equal(listeningItems({ items: [{ id: 'm2', title: 'x', language: 'zh' }] }, '', 'en')[0].lang, 'zh');
  assert.equal(listeningItems({ items: [{ id: 'm2', title: 'x' }] }, '', 'en')[0].lang, 'en');
}

// 5. Device-memory imports: a text import's route id is its own stored id unchanged (one
// "text:" prefix, not two - screens/content/screen.js reconstructs the prefix to find it again).
// A media import - pasted link or uploaded file alike - is kind 'upload' and keeps its own
// url:/upload: prefix inside the route id, because that is the raw id `api.mediaMy()` needs.
{
  const memory = {
    imports: [{ id: 'text:abc', title: 'My pasted note' }],
    mediaImports: [{ id: 'url:xyz', title: 'A talk I saved' }, { id: 'upload:1', title: 'My recording' }],
  };
  const texts = deviceTextItems(memory, 'note');
  assert.deepEqual(texts[0], { kindKey: 'text', title: 'My pasted note', meta: '', open: { route: 'content', id: 'text:abc' } });
  const mediaAll = deviceMediaItems(memory, '');
  assert.equal(mediaAll.length, 2, 'every device media import is kind upload, whichever way it was added');
  assert.ok(mediaAll.every((x) => x.kindKey === 'upload'));
  assert.deepEqual(mediaAll.find((x) => x.title === 'A talk I saved').open, { route: 'content', id: 'upload:url:xyz' });
  assert.deepEqual(mediaAll.find((x) => x.title === 'My recording').open, { route: 'content', id: 'upload:upload:1' });
}

// 6. legacyActionId: reads the `id` query value out of the old scheme's `#/page?id=...` string
// (collection_query.py's own `route()`), which already carries the shared content-id shape.
{
  assert.equal(legacyActionId('#/encounter?id=article%3A123&intent=reading'), 'article:123');
  assert.equal(legacyActionId('#/encounter?id=media%3A456&intent=dictation'), 'media:456');
  assert.equal(legacyActionId('#/language'), '', 'a route with no id query value resolves to nothing');
  assert.equal(legacyActionId(''), '');
  assert.equal(legacyActionId(null), '');
}

// 7. collectionItems: the learner's own cross-owner "My Library" query, mapped to a real
// destination per domain - and to no destination (rule 40) when the API gave none.
{
  const relLabel = (key) => ({ relationship_saved: 'Saved', relationship_practised: 'Practised' })[key] || key;
  const payload = {
    entries: [
      { ref: { domain: 'language', id: 'buffer' }, title: 'buffer', relationship: 'saved', snippet: '' },
      { ref: { domain: 'language', id: 'café' }, title: 'Café', relationship: 'saved', snippet: '' },
      { ref: { domain: 'reading', id: '9' }, title: 'Morning Routines', relationship: 'practised', snippet: '', action: { route: '#/encounter?id=article%3A9&intent=reading' } },
      { ref: { domain: 'writing', id: '5' }, title: 'My essay', relationship: 'submitted', snippet: 'the text of it' },
      { ref: { domain: 'grammar', id: 'present-perfect' }, title: 'Present perfect', relationship: 'completed', snippet: '' },
      { ref: { domain: 'speaking', id: 'take-1' }, title: 'A free take', relationship: 'spoken', snippet: '', action: null },
      { ref: { domain: 'media', id: 'asset:zz' }, title: '', relationship: 'practised', snippet: '' },
    ],
  };
  const items = collectionItems(payload, relLabel);
  assert.equal(items.length, 6, 'an entry with no title is dropped');
  const byTitle = Object.fromEntries(items.map((x) => [x.title, x]));
  assert.deepEqual(byTitle.buffer.open, { route: 'word', id: 'buffer' });
  assert.equal(byTitle.buffer.meta, 'Saved', 'a real relationship label fills in when the owner gave no snippet');
  assert.deepEqual(
    byTitle['Café'].open, { route: 'word', id: 'Café' },
    'the word route opens with the saved word\'s own text (the row\'s title), not `ref.id` - collection_query.py\'s ' +
    'language_entries() casefolds and NFKC-normalises `ref.id` for de-duplication only, so a saved "Café" must not ' +
    'route to a lowercased "café"',
  );
  assert.deepEqual(byTitle['Morning Routines'].open, { route: 'content', id: 'article:9' });
  assert.deepEqual(byTitle['My essay'].open, { route: 'writingDraft', id: '5' });
  assert.equal(byTitle['My essay'].meta, 'the text of it', 'a real snippet wins over the relationship label');
  assert.deepEqual(byTitle['Present perfect'].open, { route: 'gconcept', id: 'present-perfect' });
  assert.equal(byTitle['A free take'].open, null, 'no action from the owner means no destination - never a guessed one');
}

// 8. totalItems: sums every group's own item count.
assert.equal(totalItems([{ items: [1, 2] }, { items: [] }, { items: [3] }]), 3);

// 9. Cross-surface contract check: every route id this screen builds for a content result must
// round-trip through screens/content/model.js's own parseContentId (the shared "<kind>:<id>"
// contract) into exactly the {kind, id} that screen's loadDetail() then calls its API with -
// checked against the real module, not a re-typed copy of its rule.
{
  const fs = await import('node:fs');
  const contentModelPath = new URL('../static/orena/screens/content/model.js', import.meta.url);
  if (fs.existsSync(contentModelPath)) {
    const { parseContentId } = await import(contentModelPath.href);
    assert.deepEqual(parseContentId(articleItems({ items: [{ id: 9, title: 'x' }] }, '').at(0)?.open.id), { kind: 'article', id: '9' });
    assert.deepEqual(parseContentId(listeningItems({ items: [{ id: 'm1', title: 'x' }] }, '').at(0)?.open.id), { kind: 'media', id: 'm1' });
    const text = deviceTextItems({ imports: [{ id: 'text:abc', title: 'x' }] }, '').at(0);
    assert.deepEqual(parseContentId(text.open.id), { kind: 'text', id: 'abc' }, 'a text import\'s route id parses to the bare uuid content/screen.js re-prefixes');
    const upload = deviceMediaItems({ mediaImports: [{ id: 'upload:1', title: 'x' }] }, '').at(0);
    assert.deepEqual(parseContentId(upload.open.id), { kind: 'upload', id: 'upload:1' }, 'an upload\'s route id parses to the exact raw id api.mediaMy() needs');
    const pastedLink = deviceMediaItems({ mediaImports: [{ id: 'url:xyz', title: 'x' }] }, '').at(0);
    assert.deepEqual(parseContentId(pastedLink.open.id), { kind: 'upload', id: 'url:xyz' }, 'a pasted-link import is also kind upload - only a real catalogue lesson is kind media');
    const collectionArticle = collectionItems({ entries: [{ ref: { domain: 'reading', id: '9' }, title: 'x', action: { route: '#/encounter?id=article%3A9' } }] }).at(0);
    assert.deepEqual(parseContentId(collectionArticle.open.id), { kind: 'article', id: '9' });
  } else {
    console.log('Orena search screen: content/model.js not present yet in this tree - cross-surface check skipped, not failed');
  }
}

// 10. languages-5 / finding A: screen.js wires the shared kit/lang.js helper for a result's title.
{
  const { readFileSync } = await import('node:fs');
  const screenSrc = readFileSync(new URL('../static/orena/screens/search/screen.js', import.meta.url), 'utf8');
  assert.match(screenSrc, /import\s*\{\s*langSpan\s*\}\s*from\s*'\.\.\/\.\.\/kit\/lang\.js'/, 'imports the shared lang helper from kit/lang.js');
  assert.match(screenSrc, /langSpan\(item\.title,\s*item\.lang\)/, 'a result row title is wrapped with the item\'s own language');
  // languages-5 fix (review issue 1, finding B.3 "also Search"): a result's own open-taxonomy
  // `topic` (article/media) is wrapped lang="en" in its own span, not folded unmarked into `sub`.
  assert.match(screenSrc, /langSpan\(item\.topic,\s*'en'\)/, 'an article/media result\'s topic is marked lang="en", mirroring Discover\'s card tag');
}

console.log('Orena search screen: recent searches, real-source mapping, rule-40 fallbacks: PASS');
