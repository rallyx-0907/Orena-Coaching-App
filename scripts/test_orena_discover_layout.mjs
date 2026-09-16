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

function cssRule(source, selector, containing = '') {
  let searchFrom = 0;
  while (searchFrom < source.length) {
    const start = source.indexOf(`${selector} {`, searchFrom);
    if (start === -1) break;
    const open = source.indexOf('{', start);
    let depth = 0;
    for (let index = open; index < source.length; index += 1) {
      if (source[index] === '{') depth += 1;
      if (source[index] === '}') depth -= 1;
      if (depth === 0) {
        const block = source.slice(start, index + 1);
        if (!containing || block.includes(containing)) return block;
        searchFrom = index + 1;
        break;
      }
    }
  }
  throw new Error(`missing CSS rule: ${selector}${containing ? ` containing ${containing}` : ''}`);
}

// Discover opens with one clear page title, six short action labels and an
// explicit continuation heading. Descriptive copy belongs inside the
// destination, not in a second dashboard-like layer on the entry surface.
for (const key of ['discover', 'reading', 'listening', 'speaking', 'writing', 'practice', 'continueLearning']) {
  assert.ok(copy.en[key] || referenceCopy.en[key], `English Discover copy needs ${key}`);
  assert.ok(reference.includes(`${key}:`), `Discover copy contract needs ${key}`);
  for (const ui of ['en', 'zh']) assert.equal(typeof referenceCopy[ui][key], 'string', `${ui}.${key} must be localized`);
}

for (const marker of [
  'discover-hero',
  'discover-actions',
  'discover-content',
  'discover-content__rail',
  "link('language')",
  'vocabularyFeed',
  'continuationShelf(ctx,2,{title:r.continueLearning,compact:true})',
]) {
  assert.match(discovery, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), `Discover layout needs ${marker}`);
}

assert.match(world, /discoveryVocabularySection\(c\)/, 'Discover still mounts the shared Feed helper');
assert.match(world, /vocabularyFeed: discoveryVocabularySection\(c\)/, 'Feed is placed inside the Discover dashboard composition');
const feedRenderer = world.slice(world.indexOf('export function vocabularyFeedSection'), world.indexOf('async function paintVocabularyLibrary'));
assert.doesNotMatch(feedRenderer, /vocabularyFeedNote/, 'Discover Feed does not repeat an explanatory subtitle');
const discoverBranch = world.slice(world.indexOf('  } else {', world.indexOf('export async function renderWorld')), world.indexOf('  root\n    .querySelectorAll', world.indexOf('export async function renderWorld')));
assert.doesNotMatch(discoverBranch, /paintLibraryGrid/, 'Discover does not mount the Vocabulary Library');
assert.match(discovery, /class="editorial-spread discover-content"/, 'featured editorial content remains available');
assert.doesNotMatch(discovery, /discover-progressive|studio-spread|story-walk/, 'duplicate long-form sections are removed from Discover');

// The Discover-specific rules must compact the existing editorial primitives
// and deliberately change the phone composition, not just scale desktop down.
assert.match(styles, /\[data-experience='discover'\] \.discover-actions/);
assert.match(styles, /\[data-experience='discover'\] \.discover-content/);
assert.match(styles, /@media\s*\(max-width:600px\)[\s\S]*?\.discover-actions/);
assert.match(styles, /@media\s*\(max-width:600px\)[\s\S]*?\.thread-shelf--compact \.thread-list/);
assert.match(
  styles,
  /@media \(max-width: 600px\)[\s\S]*?\.discover-actions \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); \}/,
  'phone actions use a legible two-column grid rather than truncating labels',
);

// Discover wayfinding follows Orena's line-based navigation language. The
// primary paths and secondary destinations are deliberately different
// densities; neither is a rounded surface card and focus/hover does not add a
// sage/green fill. Three secondary destinations must occupy three equal tracks
// instead of leaving a fourth empty track or wrapping one item by accident.
const actionRule = cssRule(styles, "[data-experience='discover'] .discover-action");
assert.match(actionRule, /background:\s*transparent;/, 'quick action has no card surface');
assert.match(actionRule, /border:\s*0;/, 'quick action has no card border');
assert.match(actionRule, /border-radius:\s*0;/, 'quick action has no card radius');
const itemInteractionRule = cssRule(styles, "[data-experience='discover'] .discover-action:hover,\n[data-experience='discover'] .discover-action:focus-visible");
assert.doesNotMatch(itemInteractionRule, /--sage-surface|--on-sage/, 'wayfinding hover/focus does not invent a green card state');
assert.match(itemInteractionRule, /color:\s*var\(--accent\);/, 'wayfinding hover/focus stays typographic');
const actionsRule = cssRule(styles, "[data-experience='discover'] .discover-actions", 'grid-template-columns');
assert.match(actionsRule, /grid-template-columns:\s*repeat\(6,\s*minmax\(0,\s*1fr\)\);/, 'six actions use six equal desktop tracks');
const bringInvitationRule = cssRule(styles, "[data-experience='discover'] .bring-invitation", 'grid-template-columns');
assert.match(bringInvitationRule, /display:\s*grid;/, 'compact import invitation uses its declared grid alignment');
const discoverFeedPreviewRule = cssRule(styles, "[data-experience='discover'] .discovery-vocabulary-feed .vocabulary-feed-preview");
assert.match(discoverFeedPreviewRule, /height:\s*300px;/, 'compact Feed keeps enough height for visible Study and Save actions');

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
    {
      c: copy[ui], language: ui, ui,
      memory: { value: { continuation: [{ id: 'story:discover-check', title: 'A short story', intent: 'reading' }], expressions: {} } },
    },
    { media: sampleMedia, text: sampleStory, catalogError: '', vocabularyFeed: '<section data-vocabulary-feed></section>' },
  );
  assert.match(rendered, new RegExp(referenceCopy[ui].discover));
  assert.match(rendered, new RegExp(referenceCopy[ui].reading));
  assert.match(rendered, new RegExp(referenceCopy[ui].listening));
  assert.match(rendered, new RegExp(referenceCopy[ui].speaking));
  assert.match(rendered, new RegExp(referenceCopy[ui].continueLearning));
  assert.match(rendered, /data-vocabulary-feed/);
  assert.doesNotMatch(rendered, /data-vocabulary-library/);
  const actionStart = rendered.indexOf('discover-actions');
  const actionEnd = rendered.indexOf('</nav>', actionStart);
  const actions = rendered.slice(actionStart, actionEnd);
  assert.equal((actions.match(/class="discover-action"/g) || []).length, 6, `${ui} renders six compact actions`);
  assert.doesNotMatch(actions, /<small>|<p>/, `${ui} quick actions contain labels, not descriptions`);
  assert.doesNotMatch(rendered, /A short check of the Discover feature map\.|A way into the language\./, `${ui} featured cards omit long descriptions`);
  assert.ok(rendered.indexOf('discover-actions') < rendered.indexOf('thread-shelf--compact'));
  assert.ok(rendered.indexOf('thread-shelf--compact') < rendered.indexOf('editorial-spread'));
  assert.ok(rendered.indexOf('editorial-spread') < rendered.indexOf('data-vocabulary-feed'));
}

console.log('Discover layout contract: one headline, six compact actions, clear continuation, compact content rail, EN/ZH PASS');
