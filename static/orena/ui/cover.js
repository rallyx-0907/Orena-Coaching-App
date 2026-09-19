/* The Design System's artwork slot (D-059, D-060).

   Real imagery always wins - `art()` in content.js uses a poster or an approved
   image when the item has one. When it has none, the item gets the artwork slot
   the approved design system defines for exactly this case: a dark ground, a
   domain-hued bloom and a fine dot field, at the card's own ratio (2:3 cover,
   16:9 media, 21:9 detail). Swapping in real artwork later changes nothing
   around it, because the slot already occupies the real geometry.

   The earlier Art Bible covers - brand grounds with a leaf, arc or wave motif -
   are retired here by explicit human direction (D-060): the design system is
   the visual source of truth, and the old style does not return just because
   real artwork is still missing. That missing artwork is tracked as a gap
   (docs/project/UI_BACKEND_GAPS.md), not hidden.

   What varies is data, not style: the hue comes from what the content is, the
   bloom position and a small hue offset from a stable hash of its identity, so
   the same item always looks the same and a shelf still has rhythm. The recipe
   itself lives once, in components.css (`.content-cover`); covers stay dark in
   both themes, as the design system specifies ("artwork keeps its own light"). */

/* What the content is decides its hue family - the same wheel the domains use
   (Reading 295, Listening 235, Speaking 170, Dictation 110, Writing 55,
   Vocabulary 350) plus a few neighbours the design's own shelves use. Read
   real authored fields - `kind`, `material`, `topic` - and never invent one. */
const MATERIAL_KIND = {
  fable: 'story',
  story: 'story',
  fiction: 'story',
  book: 'story',
  classical_excerpt: 'text',
  poem: 'text',
  essay: 'text',
  article: 'text',
  reference: 'text',
  conversation: 'talk',
  dialogue: 'talk',
  audio: 'wave',
  video: 'wave',
};
const TOPIC_KIND = [
  [/science|idea|space|cosmic|physic|astronom|technolog|think/i, 'spark'],
  [/travel|journey|city|place|mountain|street|road|world|nature/i, 'place'],
  [/talk|conversation|interview|people|voice/i, 'talk'],
  [/life|home|food|garden|every\s?day|family/i, 'life'],
];
/* Hue families. Each kind owns a small arc of the wheel; the item's hash picks
   a point inside it, the way the design's library shelf varies from cover to
   cover without leaving the system. */
const HUES = {
  story: [295, 320, 270],
  text: [270, 250, 295],
  wave: [235, 200, 250],
  talk: [200, 170, 235],
  spark: [320, 295, 350],
  place: [170, 150, 110],
  life: [350, 55, 320],
};

export function coverMotif(item) {
  const kind = String(item?.kind || '').toLowerCase();
  if (kind === 'conversation') return 'talk';
  if (kind === 'audio' || kind === 'video') return 'wave';
  const material = String(item?.material || '').toLowerCase();
  if (MATERIAL_KIND[material]) return MATERIAL_KIND[material];
  const text = `${item?.topic || ''} ${item?.title || ''} ${item?.subtitle || ''}`;
  for (const [pattern, name] of TOPIC_KIND) if (pattern.test(text)) return name;
  return 'story';
}

/* A stable unsigned 32-bit hash of the content identity. Every derived index
   uses an unsigned shift: a signed one made large hashes negative, and a
   negative index is what used to draw `rotate(undefined)` into the old SVG. */
function identityHash(item) {
  const seed = String(item?.id || item?.key || item?.title || 'orena');
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

const BLOOM_AT = ['70% 10%', '30% 20%', '60% 70%', '78% 15%', '20% 20%'];

export function coverRecipe(item, { motif = '' } = {}) {
  const hash = identityHash(item);
  const name = HUES[motif] ? motif : coverMotif(item);
  const family = HUES[name];
  return {
    motif: name,
    hue: family[(hash >>> 3) % family.length],
    bloom: BLOOM_AT[(hash >>> 7) % BLOOM_AT.length],
  };
}

export function contentCover(item, { motif = '', label = '' } = {}) {
  const recipe = coverRecipe(item, { motif });
  const a11y = label ? ` role="img" aria-label="${String(label).replace(/"/g, '&quot;')}"` : ' aria-hidden="true"';
  return `<span class="content-cover" data-cover-motif="${recipe.motif}" data-cover-hue="${recipe.hue}" style="--cover-hue:${recipe.hue};--cover-bloom:${recipe.bloom}"${a11y}></span>`;
}

export const COVER_MOTIFS = Object.keys(HUES);
