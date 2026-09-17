import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';
import { discoverySpread } from '../static/orena/ui/discovery.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const discovery = read('static/orena/ui/discovery.js');
const world = read('static/orena/ui/world.js');
const styles = read('static/orena/reference.css');

for (const key of ['discover', 'reading', 'listening', 'newContent', 'newContentEmpty']) {
  for (const ui of ['en', 'zh']) {
    assert.equal(typeof referenceCopy[ui][key], 'string', `${ui}.${key} must be localized`);
    assert.ok(referenceCopy[ui][key].trim(), `${ui}.${key} must not be empty`);
  }
}

const sampleMedia = [{
  id: 'media:discover-check',
  kind: 'video',
  title: 'A small signal',
  level: 'B1',
}];
const sampleStory = [{
  id: 'story:discover-check',
  title: 'A short story',
}];
const sampleNew = [{
  id: 'media:discover-check',
  kind: 'video',
  title: 'A small signal',
}, {
  id: 'media:new-upload',
  kind: 'audio',
  title: 'Fresh from the library',
}];

for (const ui of ['en', 'zh']) {
  const rendered = discoverySpread(
    {
      c: copy[ui], language: ui, ui,
      memory: { value: { continuation: [], expressions: {} } },
    },
    { media: sampleMedia, text: sampleStory, catalogError: '', newContent: sampleNew },
  );
  assert.equal((rendered.match(/class="discover-domain-card"/g) || []).length, 4, `${ui}: exactly four overview cards`);
  assert.match(rendered, /class="discover-domain-rail"/);
  assert.ok(rendered.indexOf(referenceCopy[ui].listening) < rendered.indexOf(referenceCopy[ui].reading));
  assert.ok(rendered.indexOf(referenceCopy[ui].reading) < rendered.indexOf(copy[ui].vocabularyTitle));
  assert.ok(rendered.indexOf(copy[ui].vocabularyTitle) < rendered.indexOf(referenceCopy[ui].newContent));
  assert.match(rendered, /#\/practice\?intent=follow/);
  assert.match(rendered, /#\/practice\?intent=reading/);
  assert.match(rendered, /#\/language/);
  assert.match(rendered, /#\/encounter\?id=media%3Anew-upload/);
  assert.equal((rendered.match(/A small signal/g) || []).length, 1, `${ui}: New content does not duplicate the Listening feature`);
  assert.equal(rendered.split(`>${copy[ui].vocabularyTitle}<`).length - 1, 1, `${ui}: the Vocabulary card does not repeat its label`);
  assert.doesNotMatch(rendered, /discover-actions|feature-window|data-vocabulary-feed|thread-shelf/);
  assert.doesNotMatch(rendered, /<p>/, 'Discover cards use icons and short labels rather than descriptions');
}

const empty = discoverySpread(
  {
    c: copy.en, language: 'en', ui: 'en',
    memory: { value: { continuation: [], expressions: {} } },
  },
  { media: sampleMedia, text: sampleStory, catalogError: '', newContent: [] },
);
assert.match(empty, new RegExp(referenceCopy.en.newContentEmpty));

assert.match(styles, /\.discover-domain-rail\s*\{[^}]*display:\s*flex;/s);
assert.match(styles, /\.discover-domain-rail\s*\{[^}]*overflow-x:\s*auto;/s);
assert.match(styles, /\.discover-domain-rail\s*\{[^}]*scroll-snap-type:\s*x\s+mandatory;/s);
assert.match(styles, /\.discover-domain-rail\s*\{[^}]*flex-wrap:\s*nowrap;/s);
assert.match(styles, /\.discover-domain-card\s*\{[^}]*scroll-snap-align:\s*start;/s);
assert.match(styles, /@media\s*\(max-width:\s*600px\)[\s\S]*?\.discover-domain-card\s*\{[^}]*flex-basis:\s*min\(/s,
  'mobile keeps one landscape card at a time in the horizontal rail');
assert.doesNotMatch(styles, /\.discover-domain-card[^}]*background:\s*var\(--sage-surface\)/s);
assert.doesNotMatch(styles, /\.discover-domain-card:hover[^}]*background:/s);

assert.match(world, /listeningPayload\.sections[\s\S]{0,120}\.find[\s\S]{0,120}section\.id === 'new'/, 'Discover derives New content from the truthful imported-content rail');
assert.doesNotMatch(world, /vocabularyFeed:\s*discoveryVocabularySection/);
assert.doesNotMatch(discovery, /continuationShelf/);

console.log('Discover layout: four compact domain cards in one swipeable row, localized and non-duplicative: PASS');
