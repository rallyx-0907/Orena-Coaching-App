/* The brand artwork, and the one way it reaches a page.

   The learner UI (D-143) draws the logo and the Orena Intelligence mark
   (D-090) from the one copy in the Art Bible, through kit/brand.js. The
   pre-cutover semantic scene/feeling library (content/brand-library.js,
   ui/brand.js) went with the retired UI. What stays: the sprite the kit loads
   exists and carries every symbol the kit names, the brand route serves only
   product directories, and the design reference sheets never reach the
   product. */
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { BRAND_SPRITE_URL, INTEL_STATES, brandChip, intelChip, markGlyph } from '../static/orena/kit/brand.js';

const repo = (path) => new URL(`../${path}`, import.meta.url);
const read = (path) => readFileSync(repo(path), 'utf8');

/* The sprite the kit fetches is the Art Bible's own file, and every symbol the kit references exists in it. */
assert.equal(BRAND_SPRITE_URL, '/orena-brand/logo/orena-marks.svg');
const spritePath = 'assets/brand/orena/logo/orena-marks.svg';
assert.ok(existsSync(repo(spritePath)), 'the sprite is served from the Art Bible, not copied into the web tree');
const sprite = read(spritePath);
for (const symbol of ['ol-mark', ...Object.values(INTEL_STATES)])
  assert.ok(sprite.includes(`id="${symbol}"`), `${symbol} is in the sprite`);

/* The chips are decorative and resolve to those symbols; an unknown state falls back to the idle mark. */
assert.match(String(brandChip()), /aria-hidden="true"[\s\S]*<use href="#ol-mark">/);
for (const [state, symbol] of Object.entries(INTEL_STATES))
  assert.match(String(intelChip({ state })), new RegExp(`<use href="#${symbol}">`), `${state} draws ${symbol}`);
assert.match(String(intelChip({ state: 'nonsense' })), /<use href="#ol-intel">/, 'an unknown state is the idle mark');
assert.match(String(markGlyph()), /aria-hidden="true"/);

/* The design reference sheets are authority for people, not runtime imagery -
   megabytes each. Nothing may point at them, and the route never serves them. */
assert.ok(!read('static/orena/kit/brand.js').includes('references/'), 'the reference sheets are not product imagery');
const app = read('app.py');
/* `logo` joined the product directories with D-090: the logo and the Orena Intelligence mark are
   served from their one copy in the Art Bible. The reference sheets still never are. */
assert.ok(
  app.includes('ORENA_BRAND_SERVED = ("actions", "expressions", "scenes", "logo")'),
  'the brand route serves only product directories',
);
assert.ok(!/ORENA_BRAND_SERVED = \([^)]*references/.test(app), 'the reference sheets are never served');
assert.ok(
  app.includes('ORENA_BRAND_ROOT = (ROOT / "assets" / "brand" / "orena").resolve()'),
  'artwork is served from where it lives rather than copied into the web tree',
);

console.log('Orena brand: sprite and symbols resolve, only product directories are served, references excluded: PASS');
