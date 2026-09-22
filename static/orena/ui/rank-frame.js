/* The learner's rank, drawn as the frame around their avatar (D-067).

   Ported from the design project's master, "Orena Rank Frame Master v2" - the
   whole thing is one generator: give it a rank and it returns the geometry.
   Nothing here is a picture. There is no raster, no sprite and no per-rank
   artwork to keep in step: one SVG of 400x400 built from polar coordinates,
   plus two CSS discs for the aura.

   The rules the master sets, kept exactly:

   - **One light, at -48 degrees.** Every gradient is `userSpaceOnUse` with its
     axis along that direction, so all the facets agree about where the light
     is and the ring reads as one solid of crystal rather than a ring of tiles.
   - **Five bands of four.** Amethyst, Sapphire, Orchid, Amber, Prismatic. A
     band decides the colour and which layers of geometry exist; the four steps
     inside a band only raise the intensity - a little more bevel, a little
     more aura, a few more shards.
   - **The glow is separate from the material.** Turn off every blur and the
     crystal still reads, because the shape is in the facets, not the light.
   - **Small sizes drop layers, not quality.** At 96px and under the engraved
     ring, the shards, the petals and the orbit go; the girdle and its lit
     edges stay.

   What this file will not do is decide a learner's rank. `ProgressOverview`'s
   contract carries `tier: {name, level, current, target}` and nothing serves it
   yet, so the frame is drawn only where a tier is known. No thresholds are
   invented here. */

export const RANK_NAMES = [
  'Initiate', 'Apprentice', 'Scribe', 'Reader', 'Cantor',
  'Artisan', 'Adept', 'Voyager', 'Linguist', 'Virtuoso',
  'Luminary', 'Oracle', 'Sage', 'Maestro', 'Herald',
  'Polyglot', 'Archivist', 'Aurora', 'Celestial', 'Paragon',
];

export const RANK_BANDS = [
  { name: 'Amethyst', from: 1, to: 4 },
  { name: 'Sapphire', from: 5, to: 8 },
  { name: 'Orchid', from: 9, to: 12 },
  { name: 'Amber', from: 13, to: 16 },
  { name: 'Prismatic', from: 17, to: 20 },
];

export const RANK_COUNT = RANK_NAMES.length;

/* Per-rank constants, straight from the master. Index 0 is rank 1. */
const HUE = [302, 296, 290, 284, 276, 270, 263, 256, 320, 330, 339, 348, 80, 71, 62, 52, 300, 282, 266, 314];
const CHR = [0.055, 0.07, 0.085, 0.10, 0.115, 0.125, 0.135, 0.145, 0.15, 0.16, 0.17, 0.18, 0.135, 0.145, 0.155, 0.165, 0.075, 0.09, 0.10, 0.115];
const FACETS = [8, 10, 12, 14, 16, 18, 20, 22, 24, 24, 26, 28, 28, 30, 30, 32, 32, 34, 36, 36];
const TICKS = [0, 12, 18, 24, 24, 30, 36, 42, 48, 48, 54, 54, 60, 60, 66, 72, 72, 78, 84, 90];
const PETALS = [0, 0, 0, 4, 6, 6, 8, 8, 10, 12, 12, 12, 14, 14, 16, 16, 16, 18, 18, 20];
const NODES = [0, 0, 3, 4, 4, 5, 6, 6, 6, 6, 8, 8, 8, 10, 10, 12, 12, 12, 16, 16];
const SHARDS = [0, 0, 0, 0, 0, 4, 4, 6, 6, 8, 8, 8, 8, 10, 10, 12, 12, 14, 16, 16];
const STARP = [0, 0, 0, 0, 6, 6, 8, 8, 10, 12, 12, 12, 12, 14, 14, 14, 16, 16, 18, 18];

const C = 200;
const LIGHT = -48;
/* At and below this the master says to drop the outer layers. */
export const LITE_SIZE = 96;

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
  const band = Math.min(4, Math.floor(i / 4));
  const h = HUE[i];
  const ch = CHR[i];
  const pal = {
    spec: band === 4 ? '#FFFFFF' : `oklch(0.96 ${f2(ch * 0.35)} ${h})`,
    light: `oklch(0.84 ${f2(ch)} ${h})`,
    mid: `oklch(0.60 ${f2(ch * 1.05)} ${h})`,
    deep: `oklch(0.22 ${f2(ch * 0.55)} ${h})`,
    accent: `oklch(0.80 ${f2(ch)} ${(h + 20) % 360})`,
    aura: (a) => `oklch(0.68 ${f2(ch)} ${h} / ${f2(a)})`,
    avHue: h,
  };
  const rankNo = i + 1;
  const shape = {
    facets: FACETS[i],
    ticks: TICKS[i],
    major: TICKS[i] ? (i < 4 ? 4 : 12) : 0,
    petals: PETALS[i],
    nodes: NODES[i],
    shards: SHARDS[i],
    starPts: STARP[i],
    star2: rankNo >= 17 ? 0.42 : 0,
    orbit: rankNo >= 9 ? 1 : 0,
    tilt: ((rankNo * 29) % 70) - 35,
    sparks: Math.max(0, Math.min(5, Math.floor((rankNo - 2) / 3.6))),
    prism: rankNo >= 15 ? Math.min(3, rankNo - 14) : 0,
    aura: f2(0.04 + rankNo * 0.016),
    scatter: f2(0.05 + rankNo * 0.013),
    ring: f2(0.2 + rankNo * 0.031),
    dodeca: rankNo >= 4 ? f2(0.16 + rankNo * 0.016) : 0,
    rot: (rankNo * 11) % 30,
  };
  return { pal, shape, band };
}

const sparkPath = (cx, cy, s) =>
  `M ${cx} ${cy - s} Q ${cx} ${cy} ${cx + s} ${cy} Q ${cx} ${cy} ${cx} ${cy + s} Q ${cx} ${cy} ${cx - s} ${cy} Q ${cx} ${cy} ${cx} ${cy - s} Z`;

/* The geometry only, with no markup, so a gate can assert what a rank is made
   of without parsing SVG. */
export function rankGeometry(rank, { lite = false } = {}) {
  const { pal, shape, band } = specFor(rank);
  const c = { ...shape };
  if (lite) {
    c.ticks = Math.min(c.ticks, 24);
    c.major = c.ticks ? 6 : 0;
    c.petals = 0;
    c.shards = 0;
    c.nodes = Math.min(c.nodes, 6);
    c.sparks = Math.min(c.sparks, 2);
    c.star2 = 0;
    c.orbit = 0;
  }
  return { pal, shape: c, band };
}

export function rankFrame(options = {}) {
  const rank = clampRank(options.rank);
  const size = Number(options.size) || 152;
  const uid = String(options.uid || `r${rank}`).replace(/[^a-zA-Z0-9_-]/g, '');
  const lite = options.lite === undefined ? size <= LITE_SIZE : Boolean(options.lite);
  const { pal, shape: c } = rankGeometry(rank, { lite });
  const step = (rank - 1) % 4;
  const boost = step * 0.035;

  const grads = [];
  let sharedId = null;
  const gradient = (key, deg, r1, r2) => {
    if (lite) {
      if (!sharedId) {
        sharedId = `${uid}-sh`;
        const [ax, ay] = P(LIGHT, 130);
        const [bx, by] = P(LIGHT + 180, 130);
        grads.push({
          id: sharedId, x1: f2(ax), y1: f2(ay), x2: f2(bx), y2: f2(by),
          c0: pal.spec, o0: 0.95, c1: pal.light, o1: 0.72, c2: pal.deep, o2: 0.78,
        });
      }
      return sharedId;
    }
    const id = `${uid}-${key}`;
    const [cx, cy] = P(deg, (r1 + r2) / 2);
    const s = (r2 - r1) * 0.9;
    grads.push({
      id,
      x1: f2(cx - lx * s), y1: f2(cy - ly * s), x2: f2(cx + lx * s), y2: f2(cy + ly * s),
      c0: pal.spec, o0: f2(0.55 + 0.42 * lit(deg)),
      c1: pal.light, o1: f2(0.42 + 0.38 * lit(deg)),
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
  if (c.star2) {
    const k2 = (c.starPts + 2) * 2;
    const sp2 = 360 / k2;
    for (let i = 0; i < k2; i += 1) star2 += `${i ? ' L ' : 'M '}${pt(c.rot + 9 + i * sp2, i % 2 ? 112 : 150)}`;
    star2 += ' Z';
  }

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
        return `<circle cx="${f2(rx)}" cy="${f2(ry)}" r="${i ? 2.2 : 3.2}" fill="${pal.spec}" opacity="0.9"/>`;
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

  const spots = [[200, 4, 9, 0], [338, 92, 6, 1.4], [62, 292, 5, 2.8], [306, 318, 4, 4.2], [96, 76, 5, 5.4]];
  const sparks = spots
    .slice(0, c.sparks)
    .map(([x, y, s, delay]) => `<path d="${sparkPath(x, y, s)}" fill="#FFFFFF" opacity="${lite ? 0.72 : 0.9}" style="transform-origin:${x}px ${y}px;animation-delay:${delay}s"/>`)
    .join('');

  const [rx1, ry1] = P(LIGHT, 200);
  const [rx2, ry2] = P(LIGHT + 180, 200);
  const caustic = `M ${pt(-96, 95.6)} A 95.6 95.6 0 0 1 ${pt(-18, 95.6)}`;

  const gradSvg = grads
    .map((g) => `<linearGradient id="${g.id}" gradientUnits="userSpaceOnUse" x1="${g.x1}" y1="${g.y1}" x2="${g.x2}" y2="${g.y2}"><stop offset="0" stop-color="${g.c0}" stop-opacity="${g.o0}"/><stop offset="0.38" stop-color="${g.c1}" stop-opacity="${g.o1}"/><stop offset="1" stop-color="${g.c2}" stop-opacity="${g.o2}"/></linearGradient>`)
    .join('');

  const aura1 = `radial-gradient(closest-side, ${pal.aura(c.aura + boost)}, ${pal.aura((c.aura + boost) * 0.35)} 56%, transparent 78%)`;
  const aura2 = `radial-gradient(closest-side, ${pal.aura(c.aura * 0.55)}, transparent 72%)`;

  return `<span class="rank-frame" data-rank="${rank}" style="inline-size:${size}px;block-size:${size}px">`
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
    + `<g class="rank-frame__ring"><circle cx="200" cy="200" r="196" fill="none" stroke="url(#${uid}-rim)" stroke-width="1" opacity="${f2(c.ring)}"/>${tickSvg}${nodeSvg}${shardSvg}</g>`
    + `<g class="rank-frame__petals">${petalSvg}${c.dodeca ? `<path d="${dode}" fill="none" stroke="url(#${uid}-eng)" stroke-width="0.7" opacity="${c.dodeca}"/>` : ''}</g>`
    + (star ? `<path class="rank-frame__star" d="${star}" fill="none" stroke="url(#${uid}-eng)" stroke-width="0.9" opacity="${f2(0.42 + boost)}"/>` : '')
    + (star2 ? `<path d="${star2}" fill="none" stroke="${pal.spec}" stroke-opacity="0.22" stroke-width="0.6" opacity="${c.star2}"/>` : '')
    + orbitSvg
    + `<circle cx="200" cy="200" r="110" fill="url(#${uid}-core)" opacity="0.9"/>`
    + prisms
    + facetSvg
    + `<circle cx="200" cy="200" r="121" fill="none" stroke="url(#${uid}-rim)" stroke-width="1.1" opacity="0.8"/>`
    + `<circle cx="200" cy="200" r="97.5" fill="none" stroke="url(#${uid}-rim)" stroke-width="1.8" opacity="0.95"/>`
    + `<circle cx="200" cy="200" r="93.8" fill="none" stroke="${pal.spec}" stroke-opacity="0.55" stroke-width="0.7"/>`
    + (lite ? '' : `<path d="${caustic}" fill="none" stroke="#FFFFFF" stroke-opacity="0.3" stroke-width="1.1"/>`)
    + `<g clip-path="url(#${uid}-clip)"><ellipse cx="152" cy="126" rx="118" ry="80" fill="url(#${uid}-sheen)" opacity="0.5"/></g>`
    + `<g class="rank-frame__sparks">${sparks}</g>`
    + `</svg>`
    + `<span class="rank-frame__avatar" style="box-shadow:inset 0 2px 14px rgba(255,255,255,0.12), inset 0 -10px 28px rgba(0,0,0,0.62), 0 0 46px ${pal.aura(0.16 + c.aura * 0.6)};background:radial-gradient(125% 125% at 32% 22%, oklch(0.42 0.04 ${pal.avHue}), oklch(0.17 0.014 292) 74%)">${options.avatar || ''}</span>`
    + `</span>`;
}
