import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';
import {
  bindContentRails,
  contentRail,
  discoverySpread,
} from '../static/orena/ui/discovery.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const discovery = read('static/orena/ui/discovery.js');
const rail = read('static/orena/ui/content-rail.js');
const world = read('static/orena/ui/world.js');
const styles = read('static/orena/reference.css');

for (const key of [
  'discover',
  'continueLearning',
  'reading',
  'listening',
  'speaking',
  'writing',
  'vocabulary',
  'collectionViewAll',
  'railPrevious',
  'railNext',
  'railEmpty',
]) {
  for (const ui of ['en', 'zh']) {
    assert.equal(typeof referenceCopy[ui][key], 'string', `${ui}.${key} must be localized`);
    assert.ok(referenceCopy[ui][key].trim(), `${ui}.${key} must not be empty`);
  }
}

const sampleMedia = Array.from({ length: 5 }, (_, index) => ({
  id: `media:listen-${index}`,
  lesson_id: `listen-${index}`,
  kind: index % 2 ? 'audio' : 'video',
  title: `Listening ${index + 1}`,
  language: 'en',
  level: index < 2 ? 'A2' : 'B1',
  duration_ms: 90000 + index * 1000,
  poster_url: `https://example.com/listen-${index}.jpg`,
}));
const sampleReading = Array.from({ length: 5 }, (_, index) => ({
  id: `story:read-${index}`,
  kind: 'story',
  title: `Story ${index + 1}`,
  language: 'en',
  level: index < 2 ? 'A2' : 'B1',
  time: `${index + 2} min`,
  origin: 'generated',
}));
const sampleSpeaking = Array.from({ length: 3 }, (_, index) => ({
  key: `speak-${index}`,
  title: `Speaking prompt ${index + 1}`,
  prompt: `Say something useful ${index + 1}`,
}));
const sampleWriting = sampleReading.slice(0, 4).map((item, index) => ({
  ...item,
  prompt: `Writing prompt ${index + 1}`,
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

for (const ui of ['en', 'zh']) {
  const rendered = discoverySpread(
    {
      c: copy[ui], language: 'en', support: 'vi', ui, memory,
    },
    {
      media: sampleMedia,
      reading: sampleReading,
      speaking: sampleSpeaking,
      writing: sampleWriting,
      vocabulary: sampleVocabulary,
      catalogError: '',
    },
  );

  const railIds = [...rendered.matchAll(/data-content-rail="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(
    railIds,
    ['continue', 'reading', 'listening', 'speaking', 'writing', 'vocabulary'],
    `${ui}: vertical feed contains one resume rail followed by five separate domain rails`,
  );
  assert.equal((rendered.match(/class="content-rail__track"/g) || []).length, 6);
  assert.equal((rendered.match(/data-reading-card/g) || []).length, 5);
  assert.equal((rendered.match(/data-listening-card/g) || []).length, 5);
  assert.equal((rendered.match(/data-speaking-card/g) || []).length, 3);
  assert.equal((rendered.match(/data-writing-card/g) || []).length, 4);
  assert.equal((rendered.match(/data-vocabulary-card/g) || []).length, 5);
  assert.match(rendered, /data-vocabulary-skin="silver"/,
    `${ui}: Discover preserves the canonical level material/skin`);
  assert.match(rendered, /data-vocabulary-state="due"/,
    `${ui}: Discover preserves real review state`);
  assert.match(rendered, /★★☆/,
    `${ui}: Discover preserves learner mastery evidence`);
  assert.match(rendered, /data-discover-vocabulary-save="1"/,
    `${ui}: an unsaved feed item keeps the existing save action`);
  assert.match(rendered, /data-vocabulary-study="0"/,
    `${ui}: Vocabulary keeps its existing study action`);
  assert.match(rendered, /https:\/\/example\.com\/listen-0\.jpg/);
  assert.match(rendered, /1:30/);
  assert.match(rendered, /nghĩa 1/);
  assert.match(rendered, /#\/practice\?intent=reading/);
  assert.match(rendered, /#\/practice\?intent=follow/);
  assert.match(rendered, /#\/practice\?id=voice%3Aspeak-0&amp;intent=speaking/);
  assert.match(rendered, /#\/expression\?id=story%3Aread-0/);
  assert.match(rendered, /#\/language/);
  assert.doesNotMatch(rendered, /discover-domain-card|discover-domain-rail|New content|新上线/);
  assert.doesNotMatch(rendered, /voice-description|card-description/);
}

const noContinue = discoverySpread(
  { c: copy.en, language: 'en', support: 'vi', ui: 'en', memory: { value: { continuation: [], expressions: {}, conversations: {} } } },
  { media: sampleMedia, reading: sampleReading, speaking: sampleSpeaking, writing: sampleWriting, vocabulary: sampleVocabulary },
);
assert.doesNotMatch(noContinue, /data-content-rail="continue"/, 'Continue is truthful and disappears without resumable work');
assert.equal((noContinue.match(/data-content-rail=/g) || []).length, 5, 'the five domain rails remain visible');

const bounded = discoverySpread(
  { c: copy.en, language: 'en', support: 'vi', ui: 'en', memory },
  {
    media: Array.from({ length: 20 }, (_, index) => ({ ...sampleMedia[0], id: `media:large-${index}`, title: `Media ${index}` })),
    reading: Array.from({ length: 20 }, (_, index) => ({ ...sampleReading[0], id: `story:large-${index}`, title: `Story ${index}` })),
    speaking: sampleSpeaking,
    writing: sampleWriting,
    vocabulary: sampleVocabulary,
  },
);
assert.equal((bounded.match(/data-reading-card/g) || []).length, 12, 'Discover previews Reading rather than rendering an unbounded library');
assert.equal((bounded.match(/data-listening-card/g) || []).length, 12, 'Discover previews Listening rather than rendering an unbounded library');

const primitive = contentRail({
  id: 'test',
  title: 'Test rail',
  icon: 'book',
  seeAllHref: '#/test',
  seeAllLabel: 'See all',
  previousLabel: 'Previous',
  nextLabel: 'Next',
  items: ['<a href="#/a">A</a>', '<a href="#/b">B</a>'],
});
assert.match(primitive, /aria-labelledby="content-rail-test-title"/);
assert.match(primitive, /data-content-rail-prev/);
assert.match(primitive, /data-content-rail-next/);
assert.match(primitive, /role="list"/);
assert.equal(typeof bindContentRails, 'function');
const emptyPrimitive = contentRail({
  id: 'empty', title: 'Empty', icon: 'book', items: [], seeAllHref: '#/empty',
  seeAllLabel: 'See all', previousLabel: 'Previous', nextLabel: 'Next', emptyLabel: 'Nothing here yet.',
});
assert.match(emptyPrimitive, /class="content-rail__item content-rail__item--empty" role="listitem"/,
  'an empty rail still satisfies the ARIA list ownership contract');

assert.match(styles, /\.content-rail__track\s*\{[^}]*display:\s*flex;/s);
assert.match(styles, /\.content-rail__track\s*\{[^}]*overflow-x:\s*auto;/s);
assert.match(styles, /\.content-rail__track\s*\{[^}]*scroll-snap-type:\s*x\s+mandatory;/s);
assert.match(styles, /\.content-rail__track\s*\{[^}]*flex-wrap:\s*nowrap;/s);
assert.match(styles, /\.content-rail__track\s*\{[^}]*touch-action:\s*pan-y;/s,
  'touch rails leave vertical page movement to the browser');
assert.doesNotMatch(styles, /\.content-rail__track\s*\{[^}]*padding[^}]*38px/s,
  'desktop rail controls overlay the rail edge instead of consuming card space');
assert.match(styles, /\.content-rail__viewport:(?:hover|focus-within)[^}]*\.content-rail__control/s,
  'desktop rail controls appear contextually rather than staying noisy');
assert.match(styles, /\.content-rail--continue\s+\.content-rail__item\s*\{[^}]*calc\(\(100%\s*-\s*2\s*\*\s*var\(--rail-gap\)\)\s*\/\s*3\)/s,
  'Continue fits complete cards at desktop widths instead of clipping half a card');
assert.match(styles, /\.content-rail__item\s*\{[^}]*scroll-snap-align:\s*start;/s);
assert.match(styles, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.content-rail__item\s*\{[^}]*flex-basis:\s*min\((?:5[0-9]|6[0-5])vw,/s,
  'mobile deliberately peeks the next card instead of stacking domain items');
assert.match(styles, /\.discover-listening-card__visual\s*\{[^}]*aspect-ratio:\s*16\s*\/\s*9;/s);
assert.match(styles, /\.discover-reading-card__visual\s*\{[^}]*aspect-ratio:\s*3\s*\/\s*4;/s);
assert.doesNotMatch(styles, /\.content-rail[^}]*background:\s*#(?:[0-9a-f]{3}|[0-9a-f]{6})/i,
  'rails and cards use semantic Orena tokens, not a new palette');
assert.doesNotMatch(styles, /\.content-rail__track[^}]*flex-wrap:\s*wrap/s);

assert.match(world, /api\.listeningLibrary\(language\)/);
assert.match(world, /api\.readingSessions\(12\)/);
assert.match(world, /api\.dailyVocabularyFeed\(language\)/);
assert.match(world, /voiceInvitations\(language\)/);
assert.match(world, /reading:\s*readable/);
assert.match(world, /\n\s*vocabulary,\n/);
assert.doesNotMatch(discovery, /const\s+(?:media|reading|speaking|writing|vocabulary)\s*=\s*\[/,
  'Discover adapts domain data and does not own a hard-coded content catalog');
assert.doesNotMatch(rail, /globalThis\.addEventListener\?\.\('resize'/,
  'rail binding must not leak one global resize listener on every Discover render');
assert.match(rail, /resizeObserver\?\.disconnect\(\)/,
  'rail binding returns lifecycle cleanup for its ResizeObservers');
assert.match(world, /return unbindContentRails;/,
  'renderWorld hands rail cleanup back to the app route lifecycle');
assert.match(rail, /const\s+verticalDistance\s*=\s*Math\.abs\(event\.clientY - startY\)/,
  'pointer dragging waits for a horizontal gesture before taking control');

const appSource = read('static/orena/app.js');
assert.doesNotMatch(appSource, /<span>\$\{c\.internal\}<\/span>/,
  'internal review status must not leak into the learner footer');

console.log('Discover: separate real-content rails, localized controls, compact responsive shelf behavior: PASS');
