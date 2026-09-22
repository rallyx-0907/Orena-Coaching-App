/* Home (D-066, D-067), built to Orena Home Discover and HomeTemplate: a top bar (the one search, the
   level, the streak), the Continue strip, then the rails - what is new for the learner, Reading,
   Listening, Speaking, Writing, Vocabulary. These assertions hold what makes it honest: every card is a
   real item, a rail with nothing in it is not drawn, and no number is invented for a card that states
   none. The composition that used to live here - a greeting, a hero pair, "for you" and "saved" - was
   the previous document's and is deleted with `discoverySpread`. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';
import { homeHtml, bindHome } from '../static/orena/ui/home.js';
import { contentRail, bindContentRails } from '../static/orena/ui/content-rail.js';

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const home = read('static/orena/ui/home.js');
const discovery = read('static/orena/ui/discovery.js');
const rail = read('static/orena/ui/content-rail.js');
const world = read('static/orena/ui/world.js');
const styles = read('static/orena/home.css');
const reference = read('static/orena/reference.css');

for (const key of [
  'continue', 'collectionViewAll', 'homeAllShort', 'forYou', 'reading', 'listening', 'speaking',
  'writing', 'vocabulary', 'savedTitle', 'homeSub_reading', 'homeSub_listening', 'homeSub_speaking',
  'homeSub_writing', 'homeSub_vocabulary', 'homeResume_listening', 'homeResume_reading',
  'homeResume_writing', 'homeResume_speaking', 'homeWords', 'railPrevious', 'railNext',
  'greetNamed', 'greetPlain', 'searchPlaceholder', 'reviewDue', 'reviewNote',
]) {
  for (const ui of ['en', 'zh', 'vi']) {
    assert.equal(typeof referenceCopy[ui][key], 'string', `${ui}.${key} must be localized`);
    assert.ok(referenceCopy[ui][key].trim(), `${ui}.${key} must not be empty`);
  }
}

const sampleMedia = Array.from({ length: 5 }, (_, index) => ({
  id: `media:listen-${index}`,
  kind: index % 2 ? 'audio' : 'video',
  title: `Listening ${index + 1}`,
  language: 'en',
  level: index < 2 ? 'A2' : 'B1',
  duration_ms: 540000 + index * 1000,
  poster_url: `https://example.com/listen-${index}.jpg`,
}));
const sampleReading = Array.from({ length: 5 }, (_, index) => ({
  id: `story:read-${index}`,
  kind: 'story',
  title: `Story ${index + 1}`,
  language: 'en',
  level: index < 2 ? 'A2' : 'B1',
  time: `${index + 2} min`,
}));
const sampleVocabulary = Array.from({ length: 5 }, (_, index) => ({
  identity: { language: 'en' },
  headword: `word-${index + 1}`,
  pronunciation: `/word-${index + 1}/`,
  level: index < 2 ? 'A2' : 'B1',
  saved: index === 0,
  due: index === 0,
  review_stage: index === 0 ? 2 : 0,
  meanings: [
    { language: 'en', text: `definition ${index + 1}` },
    { language: 'vi', text: `nghĩa ${index + 1}` },
  ],
}));
const sampleCollections = [{ id: 'c1', title: 'Everyday life', language_code: 'en', word_count: 120 }];

const memory = {
  value: {
    continuation: [
      { id: 'media:listen-0', title: 'Listening 1', intent: 'follow' },
      { id: 'story:read-0', title: 'Story 1', intent: 'reading' },
    ],
    conversations: {},
    expressions: {},
  },
};
const ctxFor = (ui, extra = {}) => ({ c: copy[ui], language: 'en', support: 'vi', ui, memory, ...extra });

for (const ui of ['en', 'zh', 'vi']) {
  const rendered = homeHtml(ctxFor(ui, { profile: { declared_level: 'B1' } }), {
    media: sampleMedia,
    reading: sampleReading,
    vocabulary: sampleVocabulary,
    saved: sampleReading.slice(0, 2),
    due: 3,
    collections: sampleCollections,
  });
  const r = referenceCopy[ui];

  /* The template's own order: the Continue strip, then the rails the frames draw. */
  const railIds = [...rendered.matchAll(/data-rail="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(railIds, ['for-you', 'reading', 'listening', 'speaking', 'writing', 'vocabulary', 'saved'],
    `${ui}: the frames' rails, in their order`);
  assert.ok(rendered.indexOf('hm-continue') < rendered.indexOf('data-rail='),
    `${ui}: what the learner was in the middle of comes before the catalogue`);
  assert.match(rendered, /class="lib-head hm-top"/, `${ui}: Home carries the baseline's own top bar`);
  assert.match(rendered, /data-home-search/, `${ui}: with the one search`);
  assert.match(rendered, /class="hm-chip">B1</, `${ui}: the level the learner declared, never a guess`);
  assert.match(rendered, /class="streak-chip"/, `${ui}: and the streak`);
  assert.match(rendered, new RegExp(escapeRegExp(r.homeResume_listening)),
    `${ui}: the way back in is named for the room it returns to`);
  assert.match(rendered, /<h1 class="sr-only">/, `${ui}: the page is named for assistive technology`);

  // Every card is a real item, and its metadata is the item's own.
  assert.match(rendered, /https:\/\/example\.com\/listen-0\.jpg/, `${ui}: real artwork first`);
  assert.match(rendered, /class="content-cover" data-cover-motif="[a-z]+" data-cover-hue="\d+"/,
    `${ui}: an item without an image gets the one designed cover`);
  assert.match(rendered, new RegExp(`A2 · ${escapeRegExp(r.libraryMinutes.replace('{n}', '9'))}`),
    `${ui}: a length is the item's own, in whole minutes`);
  assert.match(rendered, new RegExp(escapeRegExp(r.homeWords.replace('{n}', '120'))),
    `${ui}: a word set counts its own words`);
  assert.doesNotMatch(rendered, /hm-track/, `${ui}: no progress is drawn for a thread that records no place`);
  assert.match(rendered, new RegExp(escapeRegExp(r.reviewDue.replace('{n}', '3'))),
    `${ui}: what is due is the learner's own saved words`);
  // The retired composition must not come back through a stale class.
  assert.doesNotMatch(rendered, /home-greeting|home-hero|discover-start|discover-feed|review-card/,
    `${ui}: nothing of the previous document's Home survives`);
}

/* Nothing real is never dressed as something. The Speaking situations and the Writing prompts are the
   app's own authored content, so they stay; every rail that reads the catalogue goes. */
const empty = homeHtml(ctxFor('en', { memory: { value: { continuation: [], expressions: {}, conversations: {} } } }),
  { media: [], reading: [], vocabulary: [], saved: [], due: 0, collections: [] });
assert.deepEqual([...empty.matchAll(/data-rail="([^"]+)"/g)].map((match) => match[1]), ['speaking', 'writing'],
  'an empty catalogue renders no invented rail');
assert.doesNotMatch(empty, /hm-continue/, 'a learner with no history is shown no strip to continue');
assert.doesNotMatch(empty, /hm-review/, 'nothing due draws nothing');
assert.match(empty, /class="lib-head hm-top"/, 'the room is still itself');

/* A rail previews; it never becomes the library. */
const many = homeHtml(ctxFor('en'), {
  media: Array.from({ length: 30 }, (_, index) => ({ ...sampleMedia[0], id: `media:l-${index}`, title: `Media ${index}` })),
  reading: Array.from({ length: 30 }, (_, index) => ({ ...sampleReading[0], id: `story:r-${index}`, title: `Story ${index}` })),
  vocabulary: [], saved: [], due: 0, collections: [],
});
for (const body of many.split('data-rail="').slice(1)) {
  const id = body.slice(0, body.indexOf('"'));
  const cards = (body.match(/class="hm-card"/g) || []).length;
  assert.ok(cards <= 12, `rail ${id} previews at most 12 cards, rendered ${cards}`);
}

/* A place the learner actually reached is drawn, and it is the place the thread recorded. */
const placed = homeHtml(
  ctxFor('en', {
    memory: {
      value: {
        continuation: [{ id: 'media:listen-0', title: 'Listening 1', intent: 'follow', place: { index: 5, total: 10 } }],
        conversations: {}, expressions: {},
      },
    },
  }),
  { media: sampleMedia, reading: [], vocabulary: [], saved: [], due: 0, collections: [] },
);
assert.match(placed, /class="hm-bar" role="img" aria-label="50%"/, 'a recorded place is drawn as it was recorded');

/* Every number in the stylesheet is the frame's: the desktop card 300x170 at radius 16 in a 20px rail,
   the phone's 232x132 at 15 in a 14px one, the Continue art 210x118, the top bar 84 tall. */
for (const [pattern, why] of [
  [/\.hm-card\s*\{[^}]*inline-size:\s*300px;/s, 'a card is 300px wide on a desk'],
  [/\.hm-art\s*\{[^}]*block-size:\s*170px;/s, 'and its artwork 170px tall'],
  [/\.hm-cards\s*\{[^}]*gap:\s*20px;/s, 'the rail leaves 20px between cards'],
  [/\.hm-continue__art\s*\{[^}]*inline-size:\s*210px;[^}]*block-size:\s*118px;/s, 'the Continue artwork is 210x118'],
  [/\.hm-go\s*\{[^}]*block-size:\s*52px;/s, 'the way back in is a 52px pill'],
  [/@media \(max-width: 900px\)[\s\S]*\.hm-card\s*\{[^}]*inline-size:\s*232px;/s, 'a phone card is 232px'],
  [/@media \(max-width: 900px\)[\s\S]*\.hm-art\s*\{[^}]*block-size:\s*132px;/s, 'and its artwork 132px'],
  [/@media \(max-width: 900px\)[\s\S]*\.hm-search-open\s*\{[^}]*display:\s*grid;/s, 'a phone opens search rather than carrying the field'],
]) {
  assert.match(styles, pattern, why);
}
assert.doesNotMatch(styles, /background:\s*#(?:[0-9a-f]{3}|[0-9a-f]{6})\b/i,
  'Home paints with the semantic tokens, never a new palette');

/* The room reads its own data, and hands its bindings back when the route changes. */
assert.match(world, /api\.listeningLibrary\(language\)/);
assert.match(world, /api\.readingSessions\(12\)/);
assert.match(world, /api\.dailyVocabularyFeed\(language\)/);
assert.match(world, /api\.vocabularyLibraryCollections\(language\)/, 'the Vocabulary rail is the learner\'s own sets');
assert.match(world, /api\.libraryVocabulary\(\)/, 'what is due on Home is the saved vocabulary itself');
assert.match(world, /unbindHome\(\);\s+releaseLibrary\(\);/, 'renderWorld hands Home\'s bindings back to the route lifecycle');
assert.doesNotMatch(world, /discoverySpread/, 'the retired composition is not rendered anywhere');
assert.doesNotMatch(discovery, /discoverySpread|discover-start|home-hero/, 'and it no longer exists');
assert.doesNotMatch(reference, /discover-content-card|discover-prompt-card|home-label-row/,
  'its stylesheet went with it');
assert.doesNotMatch(home, /const\s+(?:media|reading|vocabulary|collections)\s*=\s*\[/,
  'Home adapts domain data and owns no catalogue of its own');
assert.equal(typeof bindHome, 'function');

/* The shared rail primitive still serves the surfaces that use it (the continuation shelf). */
const primitive = contentRail({
  id: 'test', title: 'Test rail', icon: 'book', seeAllHref: '#/test', seeAllLabel: 'See all',
  previousLabel: 'Previous', nextLabel: 'Next', items: ['<a href="#/a">A</a>'],
});
assert.match(primitive, /aria-labelledby="content-rail-test-title"/);
assert.match(primitive, /role="list"/);
assert.equal(typeof bindContentRails, 'function');
assert.match(rail, /resizeObserver\?\.disconnect\(\)/, 'rail binding returns lifecycle cleanup');

const appSource = read('static/orena/app.js');
assert.doesNotMatch(appSource, /<span>\$\{c\.internal\}<\/span>/,
  'internal review status must not leak into the learner footer');

console.log('Home: the frames\' top bar, Continue strip and rails, real items only, EN/ZH/VI: PASS');
