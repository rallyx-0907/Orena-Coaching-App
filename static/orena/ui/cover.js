/* Designed covers, drawn from the content's own identity.

   A shelf of texts without cover images used to be a shelf of one cover wearing
   different letters: every passage drew its first character on a tinted
   rectangle, so five spines read as one block of colour with an alphabet on it.
   `ART_BIBLE.md` §D.1 forbids that outright - no letter, no `Aa 字`, no
   repeated abstract block - and asks instead for one deterministic system with
   parameters.

   That is what this is. A cover is exactly three things: a ground colour chosen
   by a hash of the content id, one motif from the approved brand shape
   vocabulary chosen by what the content *is*, and one warm light wash always
   coming from the same corner. The same item always draws the same cover, two
   items rarely collide, and nothing on a shelf is a style of its own.

   The palette here is artwork, not interface. `DESIGN_CONTRACT.md` rule 16
   allows artwork a richer authored palette and forbids it becoming a second
   colour owner, so these values live in this module as drawing data and never
   as CSS custom properties. Nothing outside a cover reads them, and every piece
   of UI around the cover still takes its colour from `theme.css`. */

/* Six grounds, all from `assets/brand/orena/tokens/brand-tokens.json`. Each
   carries its own motif and light values so a motif is never invisible on its
   own ground. */
const GROUNDS = [
  { ground: '#0e2a47', motif: '#1e4568', accent: '#ff7a3d', light: '#f2c572' },
  { ground: '#f8f3e9', motif: '#e2d4bb', accent: '#e24a2d', light: '#f2c572' },
  { ground: '#8ca8a1', motif: '#6c8d86', accent: '#f2c572', light: '#fdf6e7' },
  { ground: '#2b5357', motif: '#3d6667', accent: '#f2c572', light: '#8ca8a1' },
  { ground: '#f2c572', motif: '#e0a64b', accent: '#e24a2d', light: '#fdf6e7' },
  { ground: '#e06a46', motif: '#c4502f', accent: '#f2c572', light: '#f2c572' },
];

/* Motifs are the same shape family as `assets/brand/orena/pattern/*.png`, drawn
   as vectors so a cover and an approved pattern asset read as one system. Each
   is composed inside a 100x100 field and cropped by the card's own ratio. */
const MOTIFS = {
  // Growth, nature, ordinary life. The brand's two-leaf spray.
  leaf: (c) => `
    <path d="M50 78 C50 60 44 40 30 26 C48 28 60 44 58 66 Z" fill="${c.motif}"/>
    <path d="M52 80 C54 56 66 36 84 26 C84 52 72 72 54 82 Z" fill="${c.accent}" opacity=".9"/>
    <path d="M50 86 C50 66 52 52 62 40" stroke="${c.motif}" stroke-width="3.4" stroke-linecap="round" fill="none"/>`,
  // Story and fiction: the curled-tail arc of the Orena mark.
  arc: (c) => `
    <path d="M24 66 A26 26 0 1 1 76 66" stroke="${c.accent}" stroke-width="13" stroke-linecap="round" fill="none"/>
    <path d="M38 78 A14 14 0 1 0 62 78" stroke="${c.motif}" stroke-width="9" stroke-linecap="round" fill="none"/>`,
  // Journey and place.
  mountain: (c) => `
    <circle cx="72" cy="30" r="11" fill="${c.accent}"/>
    <path d="M4 82 L32 44 L48 64 L62 40 L96 82 Z" fill="${c.motif}"/>
    <path d="M48 64 L62 40 L96 82 Z" fill="${c.accent}" opacity=".55"/>`,
  // Classical text, essay, reference.
  line: (c) => `
    <rect x="22" y="34" width="56" height="6" rx="3" fill="${c.motif}"/>
    <rect x="22" y="48" width="42" height="6" rx="3" fill="${c.accent}"/>
    <rect x="22" y="62" width="50" height="6" rx="3" fill="${c.motif}"/>
    <rect x="22" y="76" width="30" height="6" rx="3" fill="${c.motif}" opacity=".7"/>`,
  // An idea, a surprise, something to notice. The brand's four-point sparkle.
  spark: (c) => `
    <path d="M52 20 C56 42 66 52 88 56 C66 60 56 70 52 92 C48 70 38 60 16 56 C38 52 48 42 52 20 Z" fill="${c.accent}"/>
    <path d="M24 22 C26 31 30 35 39 37 C30 39 26 43 24 52 C22 43 18 39 9 37 C18 35 22 31 24 22 Z" fill="${c.motif}"/>`,
  // A voice, audio, anything heard.
  wave: (c) => `
    <circle cx="50" cy="56" r="9" fill="${c.accent}"/>
    <path d="M66 40 A22 22 0 0 1 66 72" stroke="${c.motif}" stroke-width="6" stroke-linecap="round" fill="none"/>
    <path d="M78 28 A38 38 0 0 1 78 84" stroke="${c.motif}" stroke-width="6" stroke-linecap="round" fill="none" opacity=".7"/>
    <path d="M34 40 A22 22 0 0 0 34 72" stroke="${c.motif}" stroke-width="6" stroke-linecap="round" fill="none"/>`,
  // Two people, two masses, no faces.
  talk: (c) => `
    <path d="M14 30 H62 A8 8 0 0 1 70 38 V60 A8 8 0 0 1 62 68 H34 L22 80 V68 H14 A8 8 0 0 1 6 60 V38 A8 8 0 0 1 14 30 Z" fill="${c.motif}"/>
    <path d="M52 14 H88 A8 8 0 0 1 96 22 V42 A8 8 0 0 1 88 50 H76 V62 L64 50 H52 A8 8 0 0 1 44 42 V22 A8 8 0 0 1 52 14 Z" fill="${c.accent}"/>`,
};

const MOTIF_NAMES = Object.keys(MOTIFS);

/* What the content is decides the motif; only the ground varies by identity.
   Read real authored fields - `material`, `topic`, `kind` - and never invent a
   category to reach a nicer picture. */
const MATERIAL_MOTIF = {
  fable: 'arc',
  story: 'arc',
  fiction: 'arc',
  classical_excerpt: 'line',
  poem: 'line',
  essay: 'line',
  article: 'line',
  reference: 'line',
  conversation: 'talk',
  dialogue: 'talk',
  audio: 'wave',
  video: 'wave',
};

const TOPIC_MOTIF = [
  [/science|idea|space|cosmic|physic|astronom|technolog|think/i, 'spark'],
  [/travel|journey|city|place|mountain|street|road|world|nature/i, 'mountain'],
  [/talk|conversation|interview|people|voice/i, 'talk'],
  [/life|home|food|garden|every\s?day|family/i, 'leaf'],
];

export function coverMotif(item) {
  const kind = String(item?.kind || '').toLowerCase();
  if (kind === 'conversation') return 'talk';
  if (kind === 'audio' || kind === 'video') return 'wave';
  const material = String(item?.material || '').toLowerCase();
  if (MATERIAL_MOTIF[material]) return MATERIAL_MOTIF[material];
  const text = `${item?.topic || ''} ${item?.title || ''} ${item?.subtitle || ''}`;
  for (const [pattern, motif] of TOPIC_MOTIF) if (pattern.test(text)) return motif;
  return 'leaf';
}

/* A stable 32-bit hash of the content identity. The id is preferred because it
   survives a retitled item; the title is the fallback for anything that reaches
   a shelf before it has one. */
function identityHash(item) {
  const seed = String(item?.id || item?.key || item?.title || 'orena');
  let hash = 2166136261;
  for (let index = 0; index < seed.length; index += 1) {
    hash ^= seed.charCodeAt(index);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

/* One drawing, cropped by whatever ratio the card declares. `slice` keeps the
   motif centred and whole at 3:4 and at 16:9, which is why a single 100x100
   field can serve both shelves without a second set of shapes. */
export function contentCover(item, { motif = '', label = '' } = {}) {
  const hash = identityHash(item);
  const colours = GROUNDS[hash % GROUNDS.length];
  const name = MOTIFS[motif] ? motif : coverMotif(item);
  const draw = MOTIFS[name] || MOTIFS.leaf;
  // Controlled variation, not randomness: three sizes and three tilts, so a
  // shelf of one motif still has rhythm without any card leaving the system.
  const scale = [0.86, 1, 1.12][(hash >> 3) % 3];
  const tilt = [-7, 0, 6][(hash >> 6) % 3];
  return `<svg class="content-cover" data-cover-motif="${name}" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" role="img"${label ? ` aria-label="${label}"` : ' aria-hidden="true"'} focusable="false"><rect width="100" height="100" fill="${colours.ground}"/><circle cx="88" cy="8" r="46" fill="${colours.light}" opacity=".18"/><g transform="translate(50 52) rotate(${tilt}) scale(${scale}) translate(-50 -52)">${draw(colours)}</g></svg>`;
}

export const COVER_MOTIFS = MOTIF_NAMES;
export const COVER_GROUND_COUNT = GROUNDS.length;
