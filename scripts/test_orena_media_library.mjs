import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  filterMediaItems,
  mediaCard,
  mediaContinuation,
  mediaLibrary,
  renderAdminMediaImporter,
} from '../static/orena/ui/media-library.js';

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

const fallback = mediaCard(sharedAudio, copy.en, { intent: 'follow' });
assert.match(fallback, /class="sound-art"/, 'missing thumbnails use the existing Orena media artwork');
assert.doesNotMatch(fallback, /<img /, 'missing thumbnails do not invent an image');

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

const library = mediaLibrary(copy.en, {
  sharedItems: [sharedVideo, sharedAudio],
  myItems: [personalAudio],
  continuation: [{ id: sharedVideo.id, title: sharedVideo.title, intent: 'follow' }],
});
const sharedStart = library.indexOf('data-media-shared');
const myStart = library.indexOf('data-media-personal');
assert.ok(sharedStart !== -1 && myStart > sharedStart, 'Shared Library and My content are separate sections');
assert.match(library.slice(sharedStart, myStart), /A rainy day taxi/);
assert.doesNotMatch(library.slice(sharedStart, myStart), /My interview clip/);
assert.match(library.slice(myStart), /My interview clip/);
assert.doesNotMatch(library.slice(myStart), /A rainy day taxi/);
assert.equal((library.match(/data-media-continue/g) || []).length, 1, 'only real continuation entries create the continuation rail');

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

console.log('Media Library: thumbnail-first cards, filters, separate libraries, localized admin importer: PASS');
