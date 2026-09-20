import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  filterMediaItems,
  listeningItem,
  mediaCard,
  mediaContinuation,
  renderAdminMediaImporter,
} from '../static/orena/ui/media-library.js';
import { route } from '../static/orena/product/intent.js';
import { experienceFor } from '../static/orena/ui/reference.js';

const mixedContinuation = {
  value: {
    continuation: [
      { id: 'story:alice', title: 'Alice', intent: 'reading' },
      { id: 'media:night-market', title: 'Night market voices', intent: 'follow', kind: 'audio' },
      { id: 'voice:coffee', title: 'Order coffee', intent: 'speaking' },
    ],
    conversations: {},
  },
};
assert.deepEqual(
  mediaContinuation(mixedContinuation, 'en').map((item) => item.id),
  ['media:night-market'],
  'Continue listening contains listening media only',
);

const sharedVideo = {
  id: 'media:rainy-taxi',
  lesson_id: 'rainy-taxi',
  title: 'A rainy day taxi',
  description: 'This description belongs in the encounter, not the library.',
  language: 'en',
  level: 'A2',
  duration_ms: 266000,
  media_type: 'video',
  kind: 'video',
  provider: 'youtube',
  source_label: 'VOA Learning English',
  thumbnail_url: 'https://images.example.test/rainy-taxi.jpg',
};
const sharedAudio = {
  id: 'media:night-market',
  lesson_id: 'night-market',
  title: 'Night market voices',
  language: 'en',
  level: 'B1',
  duration_ms: 91000,
  media_type: 'audio',
  kind: 'audio',
  provider: 'wikimedia-commons',
  source_label: 'Wikimedia Commons',
  thumbnail_url: '',
};
const personalAudio = {
  id: 'url:https://example.test/own-audio',
  title: 'My interview clip',
  language: 'en',
  duration_ms: 62000,
  kind: 'audio',
  provider: 'direct',
  origin: 'imported',
};

const card = mediaCard(sharedVideo, copy.en, { intent: 'follow' });
assert.ok(card.indexOf('<img ') < card.indexOf('A rainy day taxi'), 'the thumbnail comes before the title');
assert.match(card, /<img src="https:\/\/images\.example\.test\/rainy-taxi\.jpg"[^>]*loading="lazy"[^>]*referrerpolicy="no-referrer"/);
assert.doesNotMatch(card, /This description belongs/, 'a media card never renders its description');
assert.match(card, /4:26/, 'duration is visible');
assert.match(card, /VOA Learning English/, 'source is visible');
assert.match(card, /A2/, 'a genuinely known level is visible');
assert.match(card, /lang="en"/, 'the learning-content title carries its own language');
assert.match(card, /aria-label="Open A rainy day taxi"/, 'the card link has a specific accessible name');

/* A source with no thumbnail of its own gets Orena's designed cover, drawn
   deterministically from its identity and what it is (ART_BIBLE.md D.1, D-057).
   The waveform placeholder it replaced was the same drawing on every card. */
const fallback = mediaCard(sharedAudio, copy.en, { intent: 'follow' });
assert.match(fallback, /class="content-cover" data-cover-motif="wave"/,
  'missing thumbnails use the designed cover for a voice');
assert.doesNotMatch(fallback, /<img /, 'missing thumbnails do not invent an image');
assert.doesNotMatch(fallback, /sound-art|text-art/, 'the shared placeholder artwork is retired');
assert.equal(
  mediaCard(sharedAudio, copy.en, { intent: 'follow' }),
  fallback,
  'the same item always draws the same cover',
);

assert.deepEqual(
  filterMediaItems([sharedVideo, sharedAudio], { type: 'video' }).map((item) => item.id),
  ['media:rainy-taxi'],
  'the type filter narrows the loaded catalog',
);
assert.deepEqual(
  filterMediaItems([sharedVideo, sharedAudio], { query: 'market', level: 'B1', source: 'Wikimedia Commons' }).map((item) => item.id),
  ['media:night-market'],
  'search, level, and source filters compose',
);

/* Browsing what can be listened to is the approved library, scoped (D-059
   Phase 7): the shared catalogue and the learner's own media are cards in the
   same surface, with its own search and facets. This gate keeps what the card
   itself must guarantee; the library's own composition is
   test_orena_library_browse.mjs. */
const world = readFileSync(new URL('../static/orena/ui/world.js', import.meta.url), 'utf8');
assert.match(world, /only: intent === 'reading' \? \['books'\] : \['audio', 'video'\]/,
  'Listening opens on the approved library, scoped to what can be listened to');
assert.doesNotMatch(world, /paintMediaLibrary|media-shelf/, 'the retired media shelf is gone');

const styles = readFileSync(new URL('../static/orena/media-library.css', import.meta.url), 'utf8');
assert.match(styles, /\.media-card__title\s*\{[^}]*-webkit-line-clamp:\s*2/s, 'titles clamp to two lines');
assert.match(styles, /\.media-card__visual\s*\{[^}]*aspect-ratio:\s*16\s*\/\s*9/s, 'thumbnail frame is 16:9');
assert.match(styles, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.media-grid/s, 'the grid has an intentional phone layout');
assert.match(styles, /prefers-reduced-motion:\s*reduce/, 'reduced-motion users do not receive decorative motion');

const copyKeys = [
  'mediaListening', 'mediaContinue', 'mediaLibrary', 'mediaMyContent',
  'mediaAll', 'mediaVideo', 'mediaAudio', 'mediaSearch', 'mediaSearchPlaceholder',
  'mediaLevel', 'mediaSource', 'mediaNoMatches', 'mediaLibraryEmpty', 'mediaMyContentEmpty',
  'mediaOpen', 'mediaThumbnailAlt', 'mediaRemove',
  'adminMediaTitle', 'adminMediaNote', 'adminMediaUrls', 'adminMediaUrlsPlaceholder',
  'adminMediaFiles', 'adminMediaLanguage', 'adminMediaPreview', 'adminMediaPreviewing',
  'adminMediaImport', 'adminMediaImporting', 'adminMediaTitleField', 'adminMediaLevelField',
  'adminMediaTopicField', 'adminMediaTagsField', 'adminMediaResults',
  'adminMediaReady', 'adminMediaChooseSource', 'adminMediaStatusOk', 'adminMediaStatusError',
];
for (const key of copyKeys) {
  assert.equal(typeof copy.en[key], 'string', `en.${key} is localized`);
  assert.ok(copy.en[key].trim(), `en.${key} is not empty`);
  assert.equal(typeof copy.zh[key], 'string', `zh.${key} is localized`);
  assert.ok(copy.zh[key].trim(), `zh.${key} is not empty`);
}

const admin = renderAdminMediaImporter(copy.en, {
  language: 'en',
  previews: [
    { url: 'https://video.example/ok', status: 'ok', title: 'Editable title', language: 'en', level: 'A2', topic: 'travel', tags: ['taxi'] },
    { url: 'https://video.example/bad', status: 'error', detail: 'Unsupported source' },
  ],
  results: [
    { url: 'https://video.example/ok', status: 'ok', detail: 'Imported', lesson_id: 'rainy-taxi' },
    { url: 'https://video.example/bad', status: 'error', detail: 'Unsupported source' },
  ],
});
assert.match(admin, /data-admin-media-preview/, 'the importer exposes Preview');
assert.match(admin, /data-admin-media-import/, 'the importer exposes Import');
for (const field of ['title', 'level', 'language', 'topic', 'tags']) {
  assert.match(admin, new RegExp(`data-admin-media-field="${field}"`), `${field} can be corrected after preview`);
}
assert.match(admin, /admin-media-result--ok[\s\S]*admin-media-result--error/, 'successful and failed items remain visible together');

/* D-057: Listening opens on the covers. Search, type, level and source stay
   available, folded into a utility rather than leading the page, and themed
   shelves appear only once the library is bigger than a shelf - never as the
   same items printed twice. */
/* Shelves, search and facets over what can be listened to are the approved
   library's own contract now (D-059 Phase 7); what this file still owns is the
   card and the identity it carries. */

/* --- A card opens the thing it shows, in the room it belongs to -----------
   The regression this pins: the Listening library rendered catalogue rows
   straight from `/api/listening/library`, which identifies a lesson by
   `lesson_id` and carries no `id` and no `kind`. Every card therefore linked to
   `#/encounter?intent=follow` with no id at all - so the encounter could
   resolve nothing, and `experienceFor` fell back to Reading, which highlighted
   Reading in the rail and showed a Reading error over a learner's Listening
   intent.

   These fixtures are the real payload's field names on purpose. A fixture that
   invents `id` cannot catch this, which is exactly why the previous gate did
   not. The chain asserted here is the learner's: card -> href -> route ->
   room. */
{
  const catalogueRow = (over = {}) => ({
    lesson_id: 'en-daily-pen-in-my-bag',
    media_object_id: 'commons-voa-anna-pen',
    title: 'A pen in my bag',
    language: 'en',
    level: 'A1',
    duration_ms: 8547,
    playback_kind: 'audio',
    media_type: 'audio',
    source_label: 'Wikimedia Commons',
    thumbnail_url: '',
    ...over,
  });

  // The boundary that turns a catalogue row into something the product can open.
  const normalised = listeningItem(catalogueRow());
  assert.equal(normalised.id, 'media:en-daily-pen-in-my-bag', 'a lesson becomes its encounter locator');
  assert.equal(normalised.kind, 'audio', 'playback kind becomes the kind the card renders by');
  assert.equal(listeningItem(catalogueRow({ playback_kind: '', media_type: 'video' })).kind, 'video',
    'media type answers when playback kind is absent');
  assert.equal(listeningItem({ id: 'url:https://example.test/a', kind: 'video' }).id, 'url:https://example.test/a',
    'an item that already carries an identity keeps it');
  assert.equal(listeningItem({ lesson_id: '' }).id, '', 'a row with no identity is not given a fake one');

  const opens = (item) => {
    const html = mediaCard(item, copy.en, { intent: 'follow' });
    const href = /href="([^"]+)"/.exec(html)?.[1]?.replace(/&amp;/g, '&') || '';
    const location = route(href);
    return { href, location, experience: experienceFor(location) };
  };

  for (const [name, row] of [
    ['audio without a poster', catalogueRow()],
    ['video with a poster', catalogueRow({ lesson_id: 'en-travel-rainy-day-taxi', playback_kind: 'video', media_type: 'video', thumbnail_url: 'https://images.example.test/taxi.jpg' })],
    ['video without a poster', catalogueRow({ lesson_id: 'en-science-cosmic-calendar', playback_kind: 'video', media_type: 'video' })],
  ]) {
    const opened = opens(listeningItem(row));
    assert.match(opened.href, /id=media%3A/, `${name}: the card carries the content identity`);
    assert.equal(opened.location.page, 'encounter', `${name}: it opens an encounter`);
    assert.equal(opened.location.id, `media:${row.lesson_id}`, `${name}: it opens this exact item`);
    assert.equal(opened.location.intent, 'follow', `${name}: the learner's intention survives the link`);
    assert.equal(opened.experience, 'listening', `${name}: and lands in Listening, never Reading`);
  }

  /* The whole library rendered from RAW catalogue rows - exactly what
     `/api/listening/library` returns. This is the shape the shipped bug was
     rendered from, so it is the shape the gate has to use. */
  const rawLibrary = [catalogueRow(), catalogueRow({ lesson_id: 'en-travel-rainy-day-taxi', playback_kind: 'video', media_type: 'video' })]
    .map((row) => mediaCard(row, copy.en, { intent: 'follow' }))
    .join('');
  const rawHrefs = [...rawLibrary.matchAll(/href="([^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, '&'));
  assert.ok(rawHrefs.length >= 2, 'raw rows still render cards');
  for (const href of rawHrefs) {
    const location = route(href);
    assert.ok(location.id, `a raw catalogue row must still produce an openable card: ${href}`);
    assert.equal(experienceFor(location), 'listening', `and must stay in Listening: ${href}`);
  }

  // The same guarantee for a library rendered whole, and for Continue listening.
  const rendered = [
    listeningItem(catalogueRow()),
    ...mediaContinuation(
      { value: { continuation: [{ id: 'media:en-daily-pen-in-my-bag', title: 'A pen in my bag', intent: 'follow', kind: 'audio' }], conversations: {} } },
      'en',
    ),
  ]
    .map((row) => mediaCard(row, copy.en, { intent: 'follow' }))
    .join('');
  const hrefs = [...rendered.matchAll(/href="([^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, '&'));
  assert.ok(hrefs.length >= 2, 'the library and its continuation rail both render links');
  for (const href of hrefs) {
    const location = route(href);
    assert.ok(location.id, `every media link carries an id: ${href}`);
    assert.equal(experienceFor(location), 'listening', `every media link stays in Listening: ${href}`);
  }

  /* A route the product cannot classify must not take the learner's domain
     with it. An intention to follow is Listening even when the id is missing
     or malformed - the error belongs to the room the learner was in. */
  assert.equal(experienceFor({ page: 'encounter', id: '', intent: 'follow' }), 'listening',
    'a malformed media route stays in Listening');
  assert.equal(experienceFor({ page: 'encounter', id: '', intent: 'reading' }), 'reading',
    'and an intention to read stays in Reading');
  assert.equal(experienceFor({ page: 'encounter', id: 'story:one', intent: null }), 'reading',
    'a text with no stated intention is still Reading');
  assert.equal(experienceFor({ page: 'encounter', id: 'media:one', intent: null }), 'listening',
    'and a media id is still Listening');
}

console.log('Media Library: thumbnail-first cards, filters, separate libraries, localized admin importer: PASS');
