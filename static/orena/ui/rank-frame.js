/* The learner's rank, drawn as the frame around their avatar (D-067).

   Ported from the design project's master, "Orena Rank Frame Master v2", read
   at the source on 2026-09-22. The whole thing is one generator: give it a
   rank and it returns the geometry. Nothing here is a picture - no raster, no
   sprite, no per-rank artwork to keep in step. One SVG of 400x400 built from
   polar coordinates, plus two CSS discs for the aura.

   The rules the master sets, kept exactly:

   - **One light, at -48 degrees.** Every gradient is `userSpaceOnUse` with its
     axis along that direction, so all the facets agree about where the light
     is and the ring reads as one solid of crystal rather than a ring of tiles.
   - **Thirty-two ranks in eight bands of four.** Amethyst, Sapphire, Orchid,
     Amber, Aquamarine, Carnelian, Moonstone, Prismatic. A band decides the
     palette and which layers exist; the four steps inside a band only raise
     the intensity. From Amber up each facet is lit from two hues at once, so
     a high rank reads multi-coloured instead of pale.
   - **The glow is separate from the material.** Turn off every blur and the
     crystal still reads, because the shape is in the facets, not the light.
   - **Three levels of detail.** Full on the profile and the master's 470px
     hero: every layer, a gradient per facet, bevels and cuts. `mid` up to
     170px: the same ornaments and orbit but shared gradients, no sparks, at
     most twenty facets. `min` at 96px and under: the girdle alone.

   What this file will not do is decide a learner's rank. `ProgressOverview`'s
   contract carries `tier: {name, level, current, target}`; the thresholds are
   the product's to state, not this lane's. */

export const RANK_NAMES = [
  'Initiate', 'Apprentice', 'Scribe', 'Reader', 'Cantor', 'Artisan', 'Adept', 'Voyager',
  'Linguist', 'Virtuoso', 'Luminary', 'Oracle', 'Sage', 'Maestro', 'Herald', 'Polyglot',
  'Navigator', 'Cartographer', 'Wayfinder', 'Chronicler', 'Rhapsode', 'Orator', 'Vesper', 'Ember',
  'Archivist', 'Curator', 'Lumen', 'Aurora', 'Celestial', 'Empyrean', 'Zenith', 'Paragon',
];

export const RANK_BANDS = [
  { name: 'Amethyst', from: 1, to: 4 },
  { name: 'Sapphire', from: 5, to: 8 },
  { name: 'Orchid', from: 9, to: 12 },
  { name: 'Amber', from: 13, to: 16 },
  { name: 'Aquamarine', from: 17, to: 20 },
  { name: 'Carnelian', from: 21, to: 24 },
  { name: 'Moonstone', from: 25, to: 28 },
  { name: 'Prismatic', from: 29, to: 32 },
];

export const RANK_COUNT = RANK_NAMES.length;

/* Per-rank constants, straight from the master. Index 0 is rank 1. */
const HUE = [302, 296, 290, 284, 276, 270, 263, 256, 320, 330, 339, 348, 80, 71, 62, 52, 196, 188, 178, 168, 32, 25, 18, 10, 250, 264, 278, 292, 302, 274, 246, 318];
const CHR = [0.055, 0.07, 0.085, 0.10, 0.115, 0.125, 0.135, 0.145, 0.15, 0.16, 0.17, 0.18, 0.135, 0.145, 0.155, 0.165, 0.13, 0.14, 0.15, 0.16, 0.15, 0.16, 0.17, 0.18, 0.135, 0.15, 0.16, 0.17, 0.18, 0.19, 0.205, 0.22];
const FACETS = [8, 10, 12, 14, 16, 18, 20, 22, 24, 24, 26, 28, 28, 30, 30, 32, 32, 34, 34, 36, 36, 38, 38, 40, 40, 40, 42, 42, 44, 44, 46, 48];
const TICKS = [0, 12, 18, 24, 24, 30, 36, 42, 48, 48, 54, 54, 60, 60, 66, 72, 72, 78, 84, 84, 90, 90, 96, 96, 96, 102, 102, 108, 108, 114, 120, 120];
const PETALS = [0, 0, 0, 4, 6, 6, 8, 8, 10, 12, 12, 12, 14, 14, 16, 16, 16, 18, 18, 20, 20, 20, 22, 22, 22, 24, 24, 24, 24, 26, 26, 28];
const NODES = [0, 0, 3, 4, 4, 5, 6, 6, 6, 6, 8, 8, 8, 10, 10, 12, 12, 12, 14, 14, 16, 16, 16, 18, 18, 18, 20, 20, 20, 22, 24, 24];
const SHARDS = [0, 0, 0, 0, 0, 4, 4, 6, 6, 8, 8, 8, 8, 10, 10, 12, 12, 12, 14, 14, 16, 16, 16, 18, 18, 18, 20, 20, 20, 22, 22, 24];
const STARP = [0, 0, 0, 0, 6, 6, 8, 8, 10, 12, 12, 12, 12, 14, 14, 14, 16, 16, 16, 18, 18, 18, 20, 20, 20, 22, 22, 24, 24, 24, 26, 26];
/* The second hue a band splits its facets towards, from Amber up. */
const SPLIT = [0, 0, 0, 14, 20, 26, 34, 44];

const C = 200;
const LIGHT = -48;
/* The master's own two cut-offs: `min` at and below LITE_SIZE, `mid` up to MID_SIZE. */
export const LITE_SIZE = 96;
export const MID_SIZE = 170;

const rad = (d) => ((d - 90) * Math.PI) / 180;
const f2 = (n) => Math.round(n * 100) / 100;
const P = (deg, r) => [C + r * Math.cos(rad(deg)), C + r * Math.sin(rad(deg))];
const pt = (deg, r) => {
  const [x, y] = P(deg, r);
  return `${f2(x)} ${f2(y)}`;
};
const lit = (deg) => {
  const d = ((((deg - LIGHT) % 360) + 540) % 360) - 180;
  return 0.5 + 0.5 * Math.cos((d * Math.PI) / 180);
};
const lx = Math.cos(rad(LIGHT));
const ly = Math.sin(rad(LIGHT));

export function clampRank(rank) {
  const n = Math.round(Number(rank) || 0);
  return Math.max(1, Math.min(RANK_COUNT, n));
}

export function bandOf(rank) {
  return RANK_BANDS[Math.min(RANK_BANDS.length - 1, Math.floor((clampRank(rank) - 1) / 4))];
}

export function rankName(rank) {
  return RANK_NAMES[clampRank(rank) - 1];
}

function specFor(rank) {
  const i = clampRank(rank) - 1;
  const band = Math.min(7, Math.floor(i / 4));
  const h = HUE[i];
  const ch = CHR[i];
  /* Above Orchid a band splits into two hues, so each facet reads as two
     colours meeting rather than one wash. */
  const split = band < 3 ? 0 : SPLIT[band];
  const h2 = (h + split) % 360;
  const h3 = ((h - split * 0.7) + 360) % 360;
  const pal = {
    spec: `oklch(0.97 ${f2(ch * (band >= 5 ? 0.5 : 0.3))} ${f2(h3)})`,
    light: `oklch(0.85 ${f2(ch)} ${h})`,
    warm: `oklch(0.80 ${f2(ch * 1.1)} ${f2(h2)})`,
    cool: `oklch(0.72 ${f2(ch * 1.15)} ${f2(h3)})`,
    mid: `oklch(0.60 ${f2(ch * 1.15)} ${h})`,
    deep: `oklch(0.22 ${f2(ch * 0.6)} ${h})`,
    accent: `oklch(0.82 ${f2(ch * 1.1)} ${f2(h2)})`,
    aura: (a) => `oklch(0.70 ${f2(ch * 1.1)} ${h} / ${f2(a)})`,
    aura2c: (a) => `oklch(0.74 ${f2(ch * 1.15)} ${f2(h2)} / ${f2(a)})`,
    avHue: h,
  };
  const n = i + 1;
  const shape = {
    facets: FACETS[i],
    ticks: TICKS[i],
    major: TICKS[i] ? (i < 4 ? 4 : 12) : 0,
    petals: PETALS[i],
    nodes: NODES[i],
    shards: SHARDS[i],
    starPts: STARP[i],
    star2: n >= 17 ? 0.42 : 0,
    orbit: n >= 9 ? 1 : 0,
    tilt: ((n * 29) % 70) - 35,
    sparks: Math.max(0, Math.min(5, Math.floor((n - 2) / 3.6))),
    prism: n >= 15 ? Math.min(3, n - 14) : 0,
    aura: f2((0.04 + n * 0.010) * (n > 16 ? 1.5 : 1)),
    scatter: f2((0.05 + n * 0.008) * (n > 16 ? 1.7 : 1)),
    ring: f2(Math.min(0.92, 0.2 + n * 0.022)),
    dodeca: n >= 4 ? f2(Math.min(0.56, 0.16 + n * 0.011)) : 0,
    rot: (n * 11) % 30,
  };
  return { pal, shape, band };
}

const sparkPath = (cx, cy, s) =>
  `M ${cx} ${cy - s} Q ${cx} ${cy} ${cx + s} ${cy} Q ${cx} ${cy} ${cx} ${cy + s} Q ${cx} ${cy} ${cx - s} ${cy} Q ${cx} ${cy} ${cx} ${cy - s} Z`;

/* Which level of detail a size asks for, as the master's own build() takes it:
   'min', 'mid', or false for the full crystal. */
export function detailFor(size) {
  if (size <= LITE_SIZE) return 'min';
  if (size <= MID_SIZE) return 'mid';
  return false;
}

/* The geometry only, with no markup, so a gate can assert what a rank is made
   of without parsing SVG. */
export function rankGeometry(rank, { lite = false } = {}) {
  const { pal, shape, band } = specFor(rank);
  const c = { ...shape };
  if (lite === 'min' || lite === true) {
    c.facets = Math.min(c.facets, 14);
    c.ticks = 0;
    c.major = 0;
    c.petals = 0;
    c.shards = 0;
    c.nodes = 0;
    c.starPts = 0;
    c.sparks = 0;
    c.star2 = 0;
    c.orbit = 0;
  } else if (lite === 'mid') {
    c.facets = Math.min(c.facets, 20);
    c.ticks = Math.min(c.ticks, 24);
    c.major = c.ticks ? 8 : 0;
    c.petals = Math.min(c.petals, 12);
    c.shards = Math.min(c.shards, 8);
    c.nodes = Math.min(c.nodes, 6);
    c.sparks = 0;
  }
  return { pal, shape: c, band };
}

export function rankFrame(options = {}) {
  const rank = clampRank(options.rank);
  const size = Number(options.size) || 152;
  const uid = String(options.uid || `r${rank}`).replace(/[^a-zA-Z0-9_-]/g, '');
  const lite = options.lite === undefined ? detailFor(size) : options.lite;
  const { pal, shape: c, band } = rankGeometry(rank, { lite });
  const step = (rank - 1) % 4;
  const boost = step * 0.035;

  const grads = [];
  const sharedIds = {};
  /* Below the full crystal the master shares two gradients - one for the odd
     facets, one for the even - instead of one per facet, which is what keeps a
     ladder of thirty-two frames cheap without changing the material. */
  const gradient = (key, deg, r1, r2, spread) => {
    const odd = (parseInt(String(key).replace(/\D/g, ''), 10) || 0) % 2 === 1;
    const c1c = band < 3 ? pal.light : odd ? pal.warm : pal.cool;
    if (lite) {
      const id = `${uid}-sh${odd ? 'b' : 'a'}`;
      if (!sharedIds[id]) {
        sharedIds[id] = 1;
        const [ax, ay] = P(LIGHT, 130);
        const [bx, by] = P(LIGHT + 180, 130);
        grads.push({
          id, x1: f2(ax), y1: f2(ay), x2: f2(bx), y2: f2(by),
          c0: band >= 4 ? (odd ? pal.light : pal.warm) : pal.spec, o0: 0.95,
          c1: c1c, o1: band >= 4 ? 0.95 : 0.78,
          c2: pal.deep, o2: 0.78,
        });
      }
      return id;
    }
    const id = `${uid}-${key}`;
    const [cx, cy] = P(deg, (r1 + r2) / 2);
    const s = spread || (r2 - r1) * 0.9;
    grads.push({
      id,
      x1: f2(cx - lx * s), y1: f2(cy - ly * s), x2: f2(cx + lx * s), y2: f2(cy + ly * s),
      c0: band >= 4 ? (odd ? pal.light : pal.warm) : pal.spec, o0: f2(0.6 + 0.38 * lit(deg)),
      c1: c1c, o1: f2(0.55 + 0.4 * lit(deg)),
      c2: pal.deep, o2: 0.72,
    });
    return id;
  };

  /* The girdle: the ring of facets that carries the whole material. */
  const n = c.facets;
  const span = 360 / n;
  const rIn = 99;
  const rOut = 121;
  let facetSvg = '';
  for (let i = 0; i < n; i += 1) {
    const a0 = c.rot + i * span + span * 0.07;
    const a1 = c.rot + (i + 1) * span - span * 0.07;
    const mid = c.rot + i * span + span / 2;
    const L = lit(mid);
    const grad = gradient(`f${i}`, mid, rIn, rOut);
    const litEdge = Math.cos(rad(mid) - rad(LIGHT)) > 0 ? a0 : a1;
    facetSvg += `<path d="M ${pt(a0, rIn)} L ${pt(a0, rOut)} L ${pt(a1, rOut)} L ${pt(a1, rIn)} Z" fill="url(#${grad})" opacity="${f2(0.62 + 0.36 * L)}"/>`;
    if (!lite) {
      facetSvg += `<path d="M ${pt(a0 + span * 0.1, rOut - 1)} L ${pt(a1 - span * 0.1, rOut - 1)} L ${pt(a1 - span * 0.22, rOut - 6)} L ${pt(a0 + span * 0.22, rOut - 6)} Z" fill="${pal.spec}" opacity="${f2(0.06 + 0.5 * L ** 2.2 + boost)}"/>`;
      facetSvg += `<path d="M ${pt(a0 + span * 0.1, rIn + 1)} L ${pt(a1 - span * 0.1, rIn + 1)} L ${pt(a1 - span * 0.2, rIn + 7)} L ${pt(a0 + span * 0.2, rIn + 7)} Z" fill="${pal.deep}" opacity="${f2(0.42 - 0.3 * L)}"/>`;
      facetSvg += `<path d="M ${pt(a0, rIn)} L ${pt(a0, rOut)}" stroke="${pal.spec}" stroke-width="0.6" opacity="${f2(0.14 + 0.44 * L)}"/>`;
    }
    facetSvg += `<path d="M ${pt(litEdge, rIn + 3)} L ${pt(litEdge, rOut - 3)}" stroke="#FFFFFF" stroke-width="${f2(0.8 + 1.1 * L ** 3)}" stroke-linecap="round" opacity="${f2(0.1 + 0.62 * L ** 2.6 + boost)}"/>`;
  }

  let tickSvg = '';
  for (let i = 0; i < c.ticks; i += 1) {
    const a = i * (360 / c.ticks);
    const major = c.major && i % Math.round(c.ticks / c.major) === 0;
    tickSvg += `<path d="M ${pt(a, major ? 170 : 176)} L ${pt(a, major ? 192 : 187)}" stroke="url(#${uid}-eng)" stroke-width="${major ? 1.7 : 0.8}" opacity="${f2((major ? 0.3 : 0.16) + 0.5 * lit(a) + boost)}" stroke-linecap="round"/>`;
  }

  let nodeSvg = '';
  for (let i = 0; i < c.nodes; i += 1) {
    const a = i * (360 / c.nodes);
    nodeSvg += `<path d="M ${pt(a, 195)} L ${pt(a + 3.2, 181)} L ${pt(a, 167)} L ${pt(a - 3.2, 181)} Z" fill="${pal.light}" opacity="${f2(0.3 + 0.6 * lit(a))}"/>`;
    nodeSvg += `<path d="M ${pt(a - 3.2, 181)} L ${pt(a, 195)}" stroke="${pal.spec}" stroke-width="0.9" fill="none" opacity="${f2(0.15 + 0.7 * lit(a) ** 2.4)}"/>`;
  }

  let shardSvg = '';
  for (let i = 0; i < c.shards; i += 1) {
    const a = i * (360 / c.shards) + 180 / c.shards;
    const grad = gradient(`s${i}`, a, 128, 164);
    shardSvg += `<path d="M ${pt(a, 166)} L ${pt(a + 2.6, 132)} L ${pt(a - 2.6, 132)} Z" fill="url(#${grad})" opacity="${f2(0.4 + 0.5 * lit(a))}"/>`;
    shardSvg += `<path d="M ${pt(a, 166)} L ${pt(a - 2.6, 132)}" stroke="${pal.spec}" stroke-width="0.8" fill="none" opacity="${f2(0.12 + 0.6 * lit(a) ** 2.4)}"/>`;
  }

  let petalSvg = '';
  const pw = c.petals ? Math.min(8.5, (360 / c.petals) * 0.4) : 0;
  for (let i = 0; i < c.petals; i += 1) {
    const a = c.rot * 0.5 + i * (360 / c.petals);
    const grad = gradient(`p${i}`, a, 124, 162);
    petalSvg += `<path d="M ${pt(a, 124)} Q ${pt(a - pw, 142)} ${pt(a, 162)} Q ${pt(a + pw, 142)} ${pt(a, 124)} Z" fill="url(#${grad})" stroke="${pal.spec}" stroke-opacity="${f2(0.12 + 0.44 * lit(a) ** 2)}" stroke-width="0.7" opacity="${f2(0.3 + 0.5 * lit(a))}"/>`;
  }

  let star = '';
  if (c.starPts) {
    const k = c.starPts * 2;
    const sp = 360 / k;
    for (let i = 0; i < k; i += 1) star += `${i ? ' L ' : 'M '}${pt(c.rot + i * sp, i % 2 ? 104 : 158)}`;
    star += ' Z';
  }
  let star2 = '';
  if (c.star2 && c.starPts) {
    const k2 = (c.starPts + 2) * 2;
    const sp2 = 360 / k2;
    for (let i = 0; i < k2; i += 1) star2 += `${i ? ' L ' : 'M '}${pt(c.rot + 9 + i * sp2, i % 2 ? 112 : 150)}`;
    star2 += ' Z';
  }

  /* The master widens the engraved polygon with the facet count. */
  const dn = c.facets >= 30 ? 16 : c.facets >= 24 ? 12 : 8;
  let dode = '';
  for (let i = 0; i < dn; i += 1) dode += `${i ? ' L ' : 'M '}${pt(c.rot + i * (360 / dn) + 180 / dn, 150)}`;
  dode += ' Z';

  const rotate = (x, y, deg) => {
    const t = (deg * Math.PI) / 180;
    const dx = x - C;
    const dy = y - C;
    return [C + dx * Math.cos(t) - dy * Math.sin(t), C + dx * Math.sin(t) + dy * Math.cos(t)];
  };
  let orbitSvg = '';
  if (c.orbit) {
    const dots = [40, 215]
      .map((t, i) => {
        const [rx, ry] = rotate(C + 186 * Math.cos((t * Math.PI) / 180), C + 62 * Math.sin((t * Math.PI) / 180), c.tilt);
        const r0 = i ? 2.2 : 3.2;
        return `<circle cx="${f2(rx)}" cy="${f2(ry)}" r="${f2(r0 * 2.6)}" fill="${pal.spec}" opacity="0.2"/>`
          + `<circle cx="${f2(rx)}" cy="${f2(ry)}" r="${r0}" fill="${pal.spec}" opacity="0.92"/>`;
      })
      .join('');
    orbitSvg = `<g class="rank-frame__orbit"><ellipse cx="200" cy="200" rx="186" ry="62" fill="none" stroke="${pal.light}" stroke-opacity="0.3" stroke-width="0.9" transform="rotate(${c.tilt} 200 200)"/>${dots}</g>`;
  }

  const prisms = [
    { r: 126, color: '#8FB4FF', w: 1.4, op: 0.32, dash: '46 120', rot: -30 + c.rot },
    { r: 124, color: '#FFA8DC', w: 1.2, op: 0.28, dash: '38 130', rot: 96 + c.rot },
    { r: 128, color: '#FFD9A2', w: 1.1, op: 0.26, dash: '30 140', rot: 205 + c.rot },
  ]
    .slice(0, c.prism)
    .map((p) => `<circle cx="200" cy="200" r="${p.r}" fill="none" stroke="${p.color}" stroke-width="${p.w}" opacity="${p.op}" stroke-dasharray="${p.dash}" transform="rotate(${p.rot} 200 200)"/>`)
    .join('');

  /* From Amber up the master lays three coloured rings over the girdle: this
     is what makes a high band read as dispersion rather than a brighter wash. */
  const extraRings = band >= 4
    ? [
      { r: 123.5, color: pal.warm, op: f2(0.4 + band * 0.06), w: 1.5 },
      { r: 96.4, color: pal.cool, op: f2(0.36 + band * 0.06), w: 1.4 },
      { r: 131, color: pal.accent, op: f2(0.14 + band * 0.04), w: 0.9 },
    ]
      .map((e) => `<circle cx="200" cy="200" r="${e.r}" fill="none" stroke="${e.color}" stroke-opacity="${e.op}" stroke-width="${e.w}"/>`)
      .join('')
    : '';

  const spots = [[200, 4, 9, 0], [338, 92, 6, 1.4], [62, 292, 5, 2.8], [306, 318, 4, 4.2], [96, 76, 5, 5.4]];
  const sparks = spots
    .slice(0, c.sparks)
    .map(([x, y, s, delay]) => `<path d="${sparkPath(x, y, s)}" fill="#FFFFFF" opacity="0.9" style="transform-origin:${x}px ${y}px;animation-delay:${delay}s"/>`)
    .join('');

  const [rx1, ry1] = P(LIGHT, 200);
  const [rx2, ry2] = P(LIGHT + 180, 200);
  const caustic = `M ${pt(-96, 95.6)} A 95.6 95.6 0 0 1 ${pt(-18, 95.6)}`;

  const gradSvg = grads
    .map((g) => `<linearGradient id="${g.id}" gradientUnits="userSpaceOnUse" x1="${g.x1}" y1="${g.y1}" x2="${g.x2}" y2="${g.y2}"><stop offset="0" stop-color="${g.c0}" stop-opacity="${g.o0}"/><stop offset="0.38" stop-color="${g.c1}" stop-opacity="${g.o1}"/><stop offset="1" stop-color="${g.c2}" stop-opacity="${g.o2}"/></linearGradient>`)
    .join('');

  const aura1 = `radial-gradient(closest-side, ${pal.aura(c.aura + boost)}, ${pal.aura2c((c.aura + boost) * 0.5)} 52%, transparent 78%)`;
  const aura2 = `radial-gradient(60% 60% at 34% 26%, ${pal.aura2c(c.aura * 0.7)}, transparent 70%), radial-gradient(closest-side, ${pal.aura(c.aura * 0.55)}, transparent 72%)`;

  return `<span class="rank-frame" data-rank="${rank}" data-band="${bandOf(rank).name}" style="inline-size:${size}px;block-size:${size}px">`
    + `<span class="rank-frame__aura" style="background:${aura1}"></span>`
    + `<span class="rank-frame__aura rank-frame__aura--inner" style="background:${aura2}"></span>`
    + `<svg class="rank-frame__art" viewBox="0 0 400 400" aria-hidden="true" focusable="false">`
    + `<defs>${gradSvg}`
    + `<linearGradient id="${uid}-rim" gradientUnits="userSpaceOnUse" x1="${f2(rx1)}" y1="${f2(ry1)}" x2="${f2(rx2)}" y2="${f2(ry2)}"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.95"/><stop offset="0.42" stop-color="${pal.light}" stop-opacity="0.6"/><stop offset="1" stop-color="${pal.mid}" stop-opacity="0.18"/></linearGradient>`
    + `<linearGradient id="${uid}-eng" gradientUnits="userSpaceOnUse" x1="${f2(rx1)}" y1="${f2(ry1)}" x2="${f2(rx2)}" y2="${f2(ry2)}"><stop offset="0" stop-color="${pal.spec}" stop-opacity="0.85"/><stop offset="0.6" stop-color="${pal.light}" stop-opacity="0.42"/><stop offset="1" stop-color="${pal.mid}" stop-opacity="0.18"/></linearGradient>`
    + `<radialGradient id="${uid}-core" cx="0.5" cy="0.5" r="0.5"><stop offset="0.62" stop-color="${pal.light}" stop-opacity="0"/><stop offset="0.82" stop-color="${pal.light}" stop-opacity="${f2(c.scatter + boost * 0.4)}"/><stop offset="1" stop-color="${pal.accent}" stop-opacity="0"/></radialGradient>`
    + `<radialGradient id="${uid}-sheen" cx="0.3" cy="0.16" r="0.58"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.4"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>`
    + `<clipPath id="${uid}-clip"><circle cx="200" cy="200" r="92"/></clipPath>`
    + `</defs>`
    /* The master's order, outside in: the scattered core, the dispersion arcs,
       the girdle, its rims, the band's own rings, the caustic and the sheen. */
    + `<circle cx="200" cy="200" r="110" fill="url(#${uid}-core)" opacity="0.9"/>`
    + prisms
    + facetSvg
    + `<circle cx="200" cy="200" r="121" fill="none" stroke="url(#${uid}-rim)" stroke-width="1.1" opacity="0.8"/>`
    + `<circle cx="200" cy="200" r="97.5" fill="none" stroke="url(#${uid}-rim)" stroke-width="1.8" opacity="0.95"/>`
    + `<circle cx="200" cy="200" r="93.8" fill="none" stroke="${pal.spec}" stroke-opacity="0.55" stroke-width="0.7"/>`
    + extraRings
    + (lite ? '' : `<path d="${caustic}" fill="none" stroke="#FFFFFF" stroke-opacity="0.3" stroke-width="1.1"/>`)
    + `<g clip-path="url(#${uid}-clip)"><ellipse cx="152" cy="126" rx="118" ry="80" fill="url(#${uid}-sheen)" opacity="0.5"/></g>`
    + (sparks ? `<g class="rank-frame__sparks">${sparks}</g>` : '')
    /* The turning layers, which the master keeps in their own groups so the
       still material underneath never moves. */
    + `<g class="rank-frame__ring"><circle cx="200" cy="200" r="196" fill="none" stroke="url(#${uid}-rim)" stroke-width="1" opacity="${f2(c.ring)}"/>${tickSvg}${nodeSvg}${shardSvg}</g>`
    + `<g class="rank-frame__petals">${petalSvg}${c.dodeca ? `<path d="${dode}" fill="none" stroke="url(#${uid}-eng)" stroke-width="0.7" opacity="${c.dodeca}"/>` : ''}</g>`
    + (star ? `<path class="rank-frame__star" d="${star}" fill="none" stroke="url(#${uid}-eng)" stroke-width="0.9" opacity="${f2(0.42 + boost + band * 0.05)}"/>` : '')
    + (star2 ? `<path d="${star2}" fill="none" stroke="${pal.spec}" stroke-opacity="0.22" stroke-width="0.6" opacity="${c.star2}"/>` : '')
    + orbitSvg
    + `</svg>`
    + `<span class="rank-frame__avatar" style="box-shadow:inset 0 2px 14px rgba(255,255,255,0.12), inset 0 -10px 28px rgba(0,0,0,0.62), 0 0 46px ${pal.aura(0.16 + c.aura * 0.6)};background:radial-gradient(125% 125% at 32% 22%, oklch(0.42 0.04 ${pal.avHue}), oklch(0.17 0.014 292) 74%)">${options.avatar || ''}</span>`
    + `</span>`;
}
