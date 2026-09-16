import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';
import { discoverySpread } from '../static/orena/ui/discovery.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const discovery = read('static/orena/ui/discovery.js');
const world = read('static/orena/ui/world.js');
const reference = read('static/orena/ui/reference.js');
const styles = read('static/orena/reference.css');

// Discover must expose a compact mental map before the editorial content. The
// links remain the existing intent routes; this test protects the information
// architecture rather than a particular visual treatment.
for (const key of [
  'startHere',
  'startNote',
  'goReadNote',
  'goListenNote',
  'goSpeakNote',
  'practiceShort',
  'writingShort',
  'vocabularyShort',
  'continueShort',
  'discoverMore',
]) {
  assert.ok(copy.en[key] || referenceCopy.en[key], `English Discover copy needs ${key}`);
  assert.ok(reference.includes(`${key}:`), `Discover copy contract needs ${key}`);
  for (const ui of ['en', 'zh']) assert.equal(typeof referenceCopy[ui][key], 'string', `${ui}.${key} must be localized`);
}

for (const marker of [
  'discover-dashboard',
  'discover-start',
  'discover-map__primary',
  'discover-map__secondary',
  "link('language')",
  "link('continue')",
  'vocabularyFeed',
  'continuationShelf(ctx,2)',
  'discover-progressive',
  '<summary>',
  '<details open',
]) {
  assert.match(discovery, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), `Discover layout needs ${marker}`);
}

assert.match(world, /discoveryVocabularySection\(c\)/, 'Discover still mounts the shared Feed helper');
assert.match(world, /vocabularyFeed: discoveryVocabularySection\(c\)/, 'Feed is placed inside the Discover dashboard composition');
assert.match(world, /matchMedia\('\(max-width: 700px\)'\)/, 'mobile progressive sections are closed by the Discover controller');
const discoverBranch = world.slice(world.indexOf('  } else {', world.indexOf('export async function renderWorld')), world.indexOf('  root\n    .querySelectorAll', world.indexOf('export async function renderWorld')));
assert.doesNotMatch(discoverBranch, /paintLibraryGrid/, 'Discover does not mount the Vocabulary Library');
assert.match(discovery, /class="editorial-spread"/, 'featured editorial content remains available');
assert.match(discovery, /class="studio-spread"/, 'Practice and Writing remain available');
assert.match(discovery, /class="story-walk"/, 'recommended stories remain available');

// The Discover-specific rules must compact the existing editorial primitives
// and deliberately change the phone composition, not just scale desktop down.
assert.match(styles, /\[data-experience='discover'\] \.discover-dashboard/);
assert.match(styles, /\[data-experience='discover'\] \.editorial-spread/);
assert.match(styles, /@media\s*\(max-width:600px\)[\s\S]*?\.discover-map__primary/);
assert.match(styles, /@media\s*\(max-width:600px\)[\s\S]*?\.discover-dashboard/);
assert.match(styles, /\.discover-progressive:not\(\[open\]\) > :not\(summary\) \{ display: none; \}/);
assert.match(styles, /\.discover-progressive\[open\] > \.studio-spread/);

const sampleMedia = [{
  id: 'media:discover-check',
  kind: 'video',
  title: 'A small signal',
  level: 'B1',
  description: 'A short check of the Discover feature map.',
  source: { creator: 'Orena' },
  origin: 'provided',
}];
const sampleStory = [{
  id: 'story:discover-check',
  title: 'A short story',
  subtitle: 'A way into the language.',
  origin: 'generated',
  art: 'table',
}];
for (const ui of ['en', 'zh']) {
  const rendered = discoverySpread(
    { c: copy[ui], language: ui, ui, memory: { value: { continuation: [] } } },
    { media: sampleMedia, text: sampleStory, catalogError: '', vocabularyFeed: '<section data-vocabulary-feed></section>' },
  );
  assert.match(rendered, new RegExp(referenceCopy[ui].startHere));
  assert.match(rendered, new RegExp(referenceCopy[ui].goRead));
  assert.match(rendered, new RegExp(referenceCopy[ui].goListen));
  assert.match(rendered, new RegExp(referenceCopy[ui].goSpeak));
  assert.match(rendered, /data-vocabulary-feed/);
  assert.doesNotMatch(rendered, /data-vocabulary-library/);
  assert.ok(rendered.indexOf('discover-start') < rendered.indexOf('data-vocabulary-feed'));
  assert.ok(rendered.indexOf('data-vocabulary-feed') < rendered.indexOf('editorial-spread'));
}

console.log('Discover layout contract: compact map, dashboard Feed/Continue, EN/ZH copy, responsive rules PASS');
