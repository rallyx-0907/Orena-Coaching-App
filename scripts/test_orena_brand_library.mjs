/* The approved red-panda library, and the one way it reaches a page.

   Fifty-two approved assets existed and four reached the runtime, one of them
   used for two unrelated moments - because the only way to show any of it was
   to hardcode a path. These assertions keep the library addressable by meaning
   and keep the design reference sheets out of the product. */
import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import {
  SCENE_STATES,
  FEELINGS,
  sceneAsset,
  feelingAsset,
} from '../static/orena/content/brand-library.js';
import { scene, feeling, companionArt } from '../static/orena/ui/brand.js';

const repo = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(repo(path), 'utf8');

// Every semantic state resolves to artwork that is actually on disk. A state
// pointing at a missing file is a broken image on a learner's screen.
const SERVED = ['actions', 'expressions', 'scenes'];
for (const state of SCENE_STATES) {
  const asset = sceneAsset(state);
  assert.ok(asset, `no asset for "${state}"`);
  assert.ok(
    existsSync(repo(`assets/brand/orena/${asset.file}`)),
    `${state}: ${asset.file} does not exist`,
  );
  assert.ok(
    SERVED.includes(asset.file.split('/')[0]),
    `${state}: ${asset.file} is outside the served directories`,
  );
  assert.ok(asset.src.startsWith('/orena-brand/'), `${state}: not served from the brand route`);
  assert.ok(['character', 'scene'].includes(asset.kind), `${state}: unknown kind`);
}
for (const name of FEELINGS) {
  const asset = feelingAsset(name);
  assert.ok(existsSync(repo(`assets/brand/orena/${asset.file}`)), `${name} missing`);
  assert.equal(asset.kind, 'character', 'an expression is a character on transparency');
}

// A state nobody approved artwork for renders nothing rather than substituting
// a different panda: content is the protagonist.
assert.equal(sceneAsset('not-a-state'), null);
assert.equal(scene('not-a-state'), '');
assert.equal(feeling('not-a-feeling'), '');

// Kind decides presentation, so the surface never has to. A scene carries its
// own painted ground and is framed; a character sits on the page.
assert.match(scene('discovery'), /data-kind="scene"/);
assert.match(scene('writing'), /data-kind="character"/);
assert.match(scene('discovery'), /aria-hidden="true"/, 'decorative artwork is hidden from readers');
assert.match(
  scene('discovery', { label: 'A world worth entering' }),
  /alt="A world worth entering"/,
  'artwork given a label is announced',
);
assert.ok(!scene('discovery', { label: 'x' }).includes('aria-hidden'), 'a labelled figure is not hidden');
assert.match(scene('discovery'), /loading="lazy"/);
assert.ok(!scene('<script>').includes('<script>'), 'state names are escaped');

/* The design reference sheets are authority for people, not runtime imagery -
   megabytes each. Nothing may point at them. */
const library = read('static/orena/content/brand-library.js');
assert.ok(!library.includes('references/'), 'the reference sheets are not product imagery');
const app = read('app.py');
assert.ok(
  app.includes('ORENA_BRAND_SERVED = ("actions", "expressions", "scenes")'),
  'the brand route serves only product directories',
);
assert.ok(
  app.includes('ORENA_BRAND_ROOT = (ROOT / "assets" / "brand" / "orena").resolve()'),
  'artwork is served from where it lives rather than copied into the web tree',
);

/* One way in. A surface names a state; it never names a file. */
const surfaces = [
  'static/orena/ui/world.js',
  'static/orena/ui/expression.js',
  'static/orena/ui/speaking.js',
  'static/orena/ui/conversation.js',
  'static/orena/ui/encounter.js',
  'static/orena/ui/patterns.js',
];
for (const path of surfaces) {
  const source = read(path);
  assert.ok(
    !source.includes('/orena-brand/'),
    `${path} hardcodes a brand path instead of naming a state`,
  );
  assert.ok(
    !/orena-assets\/assets\/(master|exploring-world)\.png/.test(source),
    `${path} still reaches for the old reused image`,
  );
}

// The library is worth having only if it is actually used. Distinct states must
// resolve to distinct artwork, or this is one image with many names.
const files = SCENE_STATES.map((s) => sceneAsset(s).file);
assert.equal(new Set(files).size, files.length, 'two states share one image');
assert.ok(SCENE_STATES.length >= 15, 'the library should reach most of the approved set');

// And the approved set is bigger than what is mapped: report, do not fail.
const onDisk = SERVED.flatMap((dir) =>
  readdirSync(repo(`assets/brand/orena/${dir}`)).map((f) => `${dir}/${f}`),
);
const used = new Set([...files, ...FEELINGS.map((f) => feelingAsset(f).file)]);
const unused = onDisk.filter((f) => !used.has(f));
assert.ok(used.size >= 25, `only ${used.size} approved assets are reachable`);

assert.match(companionArt(), /data-state="discovery"/, 'the arrival keeps its own state');

console.log(
  `Orena brand library: ${used.size} approved assets reachable, ${unused.length} still unused, references excluded: PASS`,
);
