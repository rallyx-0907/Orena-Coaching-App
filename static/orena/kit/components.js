/* Shared components of the new learner UI (D-091 primitives pass): the pieces the pinned design
   draws the same way in two or more destination screens - Today, Discover, Content Detail,
   Practice Hub, Skill Hub, My Library, Collection Detail, Word Detail, Grammar Library, Grammar
   Concept, Progress, Profile, Settings, Search, Filter Sheet, Import, Notifications, Coming soon.
   Each function returns html`` Markup built only from its parameters - no sample text, no colour
   literal (every colour a caller passes is expected to already be a var(--token) string, exactly
   like the design's own data-bound style props). A component drawn in only one of those screens
   stays with that screen's own stylesheet instead of living here (see SCRATCH/reports/primitives.md
   for the full signature-by-signature accounting).

   Composes kit/kit.css primitives (.o-card, .o-tag, .o-overlay-pill, .o-iconbtn, .o-h1/.o-sub) -
   it never redefines them. Classes here are prefixed .c-. */
import { html, raw, cls, esc, px } from './html.js';
import { icon } from './icons.js';

/* data-* attributes from a plain object, values escaped, false/null/undefined dropped. Keys are
   developer-chosen constants, never learner or API text. */
function dataAttrs(dataset = {}) {
  const pairs = Object.entries(dataset)
    .filter(([, value]) => value !== undefined && value !== null && value !== false)
    .map(([key, value]) => ` data-${key}="${esc(String(value))}"`)
    .join('');
  return raw(pairs);
}

/* ---- Media card: Today's "For you" rail, Discover's result grid, My Library's Content and
   Collections tabs (D2 S1 "Content card"/"For-You media card"). 20px card shell (kit's
   .o-card/.o-card--hover) + an artwork block with an optional type pill (top-left), duration pill
   (bottom-right) and a start progress strip, then a title/meta/tag body. `image` is a full
   background-image CSS value the caller already resolved (a URL or none) - not a colour. Pass
   `imageHeight` for a fixed-height image area (Today's rail cards); otherwise the block holds the
   16:10 ratio Discover and My Library draw. */
/* A media title as a headline: hashtags a source appends ("… #kungfupanda #learnchinese") are incidental
   metadata, not the title (LEX-036). The title itself is never shortened; a title that is only hashtags stays. */
export function headlineTitle(value) {
  const text = String(value ?? '').trim();
  const stripped = text.replace(/(?:\s*[#＃][^\s#＃]+)+\s*$/u, '').replace(/\s*[#＃][^\s#＃]+/gu, '').trim();
  return stripped || text;
}

export function mediaCard({
  image = '',
  imageHeight = null,
  kind = '',
  duration = '',
  progress = null,
  title,
  fullTitle = '',
  meta = '',
  tags = [],
  dataset = {},
} = {}) {
  const pct = progress == null ? null : Math.max(0, Math.min(100, Number(progress)));
  // The headline is held to two lines (LEX-036); the source's whole title stays one hover/long-press away.
  const full = String(fullTitle || '').trim();
  const imgRules = [image ? `background-image:${image}` : '', imageHeight ? `height:${px(imageHeight)}` : ''].filter(Boolean).join(';');
  return html`<button type="button" class="o-card o-card--hover c-media"${dataAttrs(dataset)}>
    <span class="c-media__img" style="${imgRules}">
      ${kind ? html`<span class="o-overlay-pill c-media__badge c-media__badge--tl">${kind}</span>` : ''}
      ${duration ? html`<span class="o-overlay-pill c-media__badge c-media__badge--br">${duration}</span>` : ''}
      ${pct != null ? html`<span class="c-media__progress"><span style="width:${pct}%"></span></span>` : ''}
    </span>
    <span class="c-media__body">
      <span class="c-media__title"${full ? raw(` title="${esc(full)}"`) : ''}>${title}</span>
      ${meta ? html`<span class="c-media__meta">${meta}</span>` : ''}
      ${tags.length ? html`<span class="c-media__tags">${tags.map((t) => html`<span class="${cls('o-tag', t.tone && `o-tag--${t.tone}`)}"${t.lang ? raw(` lang="${esc(t.lang)}"`) : ''}>${t.label}</span>`)}</span>` : ''}
    </span>
  </button>`;
}

/* ---- List row: the app's single most-repeated composite (My Library's Content/Saved-
   language/Active-use rows, Progress's Evidence/History/Next/Knowing-Using rows, Profile's action
   rows, Settings' rows, Search's results, Notifications, Grammar Library's concept rows, Skill
   Hub's mode rows, Import's stage rows). A leading slot (icon swatch, thumbnail, level tile, badge
   circle - build with the small helpers below or with a screen's own markup), a title/sub body, a
   trailing slot (pill, control, text) and an optional chevron. `radius`/`pad` take the frame's own
   measured numbers (they range 14-20px / 12-20px across screens - a real, recorded difference, not
   one to paper over with a single constant).

   A few more shapes the frames draw only some of these rows in, each opt-in so every other
   consumer's own confirmed-live geometry (15px title, no explicit line-height - 19px "normal" in
   both design and app) is unchanged (D-091 kit fidelity pass):
   - `kind`: a third line above the title (kind label, no timestamp - no per-row time source exists
     anywhere this screen reads from, rule 40), confirmed against Notifications' own row
     (59-Notifications.html: kind+when / title, line-height 1.4 / sub 13.5px - the "when" half is
     dropped, not invented). `kit/components.css`'s `.c-row__kind + .c-row__title` /
     `.c-row__kind ~ .c-row__sub` selectors carry the two size deltas this shape alone needs.
   - `inlineSub`/`titleSize`: Profile's own action rows (25-Profile-Today-s-progress.html) draw the
     sub on the *same* line as the title (`margin-left:10px`, no truncation) at a 16px title,
     instead of stacked underneath at 15px - confirmed live, not a guess. `tag:'a'`/`href` covers
     the one row of those that is a real external navigation (Platform admin), not an in-app route.
   - `titleLineHeight`: Grammar Library's own concept row (44-Grammar-Library.html) draws its 15px
     title at an explicit `line-height:20px` - measured live against every *other* 15px-title
     consumer of this row (Progress, My Library, Search, Settings, Skill Hub) and confirmed each of
     them draws no line-height at all (19px "normal" in this font, not 20px - a real, if small,
     difference, not one to paper over by making 20px the row's own default and regressing five
     other screens' already-confirmed fidelity). A future edit to Grammar Library's own screen.js
     (not this pass's file to touch) can pass `titleLineHeight: 20` to pick it up. */
export function listRow({
  tag = 'button',
  variant = 'shadow',
  radius = 16,
  pad = '14px 16px',
  leading = null,
  kind = '',
  title,
  titleSize = 15,
  titleLineHeight = null,
  inlineSub = false,
  sub = '',
  trailing = null,
  chevron = false,
  href = '',
  dataset = {},
  className = '',
} = {}) {
  const classes = cls('c-row', `c-row--${variant}`, className);
  const titleClasses = cls('c-row__title', inlineSub && 'c-row__title--loose');
  const titleRules = [titleSize !== 15 ? `font-size:${px(titleSize)}` : '', titleLineHeight != null ? `line-height:${px(titleLineHeight)}` : ''].filter(Boolean).join(';');
  const titleStyle = titleRules ? raw(` style="${titleRules}"`) : '';
  const titleMarkup = html`<span class="${titleClasses}"${titleStyle}>${title}${inlineSub && sub ? html`<span class="c-row__sub c-row__sub--inline">${sub}</span>` : ''}</span>`;
  const inner = html`${leading ? html`<span class="c-row__lead">${leading}</span>` : ''}<span class="c-row__body">${kind ? html`<span class="c-row__kind">${kind}</span>` : ''}${titleMarkup}${!inlineSub && sub ? html`<span class="c-row__sub">${sub}</span>` : ''}</span>${trailing ? html`<span class="c-row__trail">${trailing}</span>` : ''}${chevron ? html`<span class="c-row__chevron" aria-hidden="true">${raw(icon('chevron-right', { size: 20 }))}</span>` : ''}`;
  const style = `border-radius:${px(radius)};padding:${pad}`;
  if (tag === 'div') return html`<div class="${classes}" style="${style}"${dataAttrs(dataset)}>${inner}</div>`;
  if (tag === 'a') return html`<a class="${classes}" style="${style}" href="${href}"${dataAttrs(dataset)}>${inner}</a>`;
  return html`<button type="button" class="${classes}" style="${style}"${dataAttrs(dataset)}>${inner}</button>`;
}

/* listRow leading slot: a tinted icon swatch (Practice Hub's mode tiles, the "Continue" row). */
export function rowIconSwatch({ iconName, tint = 'var(--accent)', ink = 'var(--accent-ink)', size = 40, radius = 12 } = {}) {
  return html`<span class="c-row__swatch" style="width:${px(size)};height:${px(size)};border-radius:${px(radius)};background:${tint};color:${ink}">${raw(icon(iconName, { size: Math.round(size * 0.5) }))}</span>`;
}

/* listRow leading slot: an artwork thumbnail (My Library's Content tab, Content Detail's related
   rows). `image` is a resolved background-image CSS value. */
export function rowThumb({ image = '', width = 64, height = 64, radius = 16 } = {}) {
  const rules = image ? `background-image:${image}` : '';
  return html`<span class="${cls('c-row__thumb', !image && 'o-art')}" style="width:${px(width)};height:${px(height)};border-radius:${px(radius)};${rules}"></span>`;
}

/* listRow leading slot: a small coloured glyph badge (Progress's Evidence/Milestone rows). `glyph`
   is a short bound string (an initial, a symbol), not an icon name. */
export function rowBadge({ glyph = '', bg = 'var(--accent)', ink = 'var(--accent-ink)', size = 22 } = {}) {
  return html`<span class="c-row__badge" style="width:${px(size)};height:${px(size)};background:${bg};color:${ink}">${glyph}</span>`;
}

/* ---- Section heading row: a title with an optional trailing "see all"/"details" link (Today's
   "For you", Progress's "Knowing -> Using"). `size` 'lg' is the page-level heading (Today);
   'sm' is a card-internal heading (Progress). */
export function sectionHead({ title, size = 'lg', action = null } = {}) {
  return html`<div class="${cls('c-section-head', size === 'sm' && 'c-section-head--sm')}">
    <h2 class="c-section-head__title">${title}</h2>
    ${action ? html`<button type="button" class="c-section-head__action"${dataAttrs(action.dataset)}>${action.label}${action.chevron ? raw(icon('chevron-right', { size: 16 })) : ''}</button>` : ''}
  </div>`;
}

/* ---- Progress ring: Today's daily-goal ring and its 3 skill mini-rings, and Profile's Today's-
   progress daily-goal ring (D1 "Progress ring" - Profile's own export used an unconfirmed
   conic-gradient technique, so this canonicalises on the more fully measured SVG construction; the
   Profile surface agent should re-measure against the source before relying on the default size).
   `center` is caller-built Markup (a percent label, an icon) - the ring itself draws no text. */
export function progressRing({ percent, size = 112, radius = 50, stroke = 12, color = 'var(--accent)', trackColor = 'var(--surface3)', center = null } = {}) {
  const pct = Math.max(0, Math.min(100, Number(percent) || 0));
  const c = size / 2;
  return html`<span class="c-ring" style="width:${px(size)};height:${px(size)}">
    <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" class="c-ring__svg" aria-hidden="true">
      <circle cx="${c}" cy="${c}" r="${radius}" fill="none" stroke="${trackColor}" stroke-width="${stroke}"></circle>
      <circle cx="${c}" cy="${c}" r="${radius}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round" pathLength="100" stroke-dasharray="${pct} 100" class="c-ring__fill"></circle>
    </svg>
    ${center ? html`<span class="c-ring__center">${center}</span>` : ''}
  </span>`;
}

/* ---- Segmented control: Settings' "choice" rows (target/support/interface language, reader
   size, session length) and Progress's Overview range picker (week/month/year). Confirmed live
   against Settings (D-091 verification): track `border:0;border-radius:14px;overflow:hidden;
   background:var(--surface2);padding:4px;gap:4px`, options size to their own label
   (`padding:9px 12px`, no fixed height, no per-option radius - the track's own overflow:hidden
   is what rounds the corners). `equalWidth` is Progress's range picker, whose three options split
   the track evenly instead (`flex:1;height:36px`). Selected uses --accent/--accent-ink in the
   frame's own binding; this draws --accent-fill/--accent-ink instead (D-093 - white ink never
   sits on --accent, the kit gate enforces it). `variant` 'hero' is the on-accent-card treatment
   Progress draws for the track; its own selected-option colour was not fully readable in the
   export (D8), so it keeps the same --accent-fill/--accent-ink pairing rather than inventing the
   design's literal white-pill selected state - recorded under "kit requests". */
export function segmentedControl({ options = [], variant = 'surface', equalWidth = false, name = '', dataset = {} } = {}) {
  const classes = cls('c-seg', `c-seg--${variant}`, equalWidth && 'c-seg--equal');
  return html`<div class="${classes}" role="group"${dataAttrs({ ...dataset, seg: name || null })}>
    ${options.map((opt) => html`<button type="button" class="c-seg__opt" aria-pressed="${opt.selected ? 'true' : 'false'}"${dataAttrs({ value: opt.value })}>${opt.label}</button>`)}
  </div>`;
}

/* ---- Hero media: Content Detail's and Collection Detail's cover (image, dark scrim, one frosted
   pill, overlay title/meta - confirmed live against Content Detail, D-091 verification: the
   overlay is `position:absolute;left:20px;right:20px;bottom:18px`, title `margin-top:8px`, meta
   `margin-top:4px;opacity:.85`; both frames draw exactly one pill, never a row of several). The
   design's overlay text is white regardless of theme (it sits on a photo scrim in both), via the
   theme-independent `--toast-ink`; its pill is `--photo-chip` (rgba(255,255,255,.18), confirmed
   against both frames - a kit fidelity pass correction from the primitives pass's own `--toast-
   chip` reuse, a different alpha, .14, meant for the toast's own dark chip). The scrim itself
   still approximates the design's literal `rgba(8,8,16,.85→.05)` with `var(--scrim)` fading to
   transparent - recorded under "kit requests" below.

   `image: ''` (N-19: no backend cover) is not a frame the source draws, but it happens on this
   sandbox's own seeded content, so `.c-hero`'s own `background-color` fallback (components.css)
   must still hold white overlay text at AA - it reads `--toast-bg`, not a themed surface (D-093
   AA fix; caller passes no separate "no image" markup, the fallback is CSS-only). */
export function heroMedia({ image = '', height = 260, radius = 24, pill = '', title, titleSize = 28, meta = '', dataset = {} } = {}) {
  const rules = [`height:${px(height)}`, `border-radius:${px(radius)}`, image ? `background-image:${image}` : ''].filter(Boolean).join(';');
  return html`<div class="c-hero" style="${rules}"${dataAttrs(dataset)}>
    <span class="c-hero__scrim" aria-hidden="true"></span>
    <div class="c-hero__content">
      ${pill ? html`<span class="c-hero__pill">${pill}</span>` : ''}
      <div class="c-hero__title" style="font-size:${px(titleSize)}">${title}</div>
      ${meta ? html`<div class="c-hero__meta">${meta}</div>` : ''}
    </div>
  </div>`;
}

/* ---- Page header: a back button, a title (+ optional meta), optional trailing actions. `compact`
   is the smaller in-page header Grammar Concept draws (confirmed live, D-091 verification: back
   button is the *plain* 40x40/radius-12 o-iconbtn with a 19px icon, not the --back modifier's
   radius 14/21px - that belongs only to the full o-h1 header Settings and Grammar Library draw;
   title 17px/600, meta 13px/var(--muted)). Skill Hub's own header used a 14px/21px back button in
   the export (D2) - a small, recorded drift from Grammar Concept's; this canonicalises on the one
   directly confirmed against the live source. */
export function pageHeader({ back = null, title, meta = '', compact = false, titleSize = 17, actions = [] } = {}) {
  const backBtn = back
    ? html`<button type="button" class="${cls('o-iconbtn', !compact && 'o-iconbtn--back')}" aria-label="${back.label}"${dataAttrs(back.dataset)}>${raw(icon('arrow-left', { size: compact ? 19 : 21 }))}</button>`
    : '';
  const trail = actions.length ? html`<div class="c-pagehead__actions">${actions}</div>` : '';
  if (compact) {
    return html`<div class="c-pagehead c-pagehead--compact">${backBtn}<div class="c-pagehead__body"><div class="c-pagehead__title--compact" style="font-size:${px(titleSize)}">${title}</div>${meta ? html`<div class="c-pagehead__meta">${meta}</div>` : ''}</div>${trail}</div>`;
  }
  return html`<div class="c-pagehead">${backBtn}<div class="c-pagehead__body"><h1 class="o-h1">${title}</h1>${meta ? html`<p class="o-sub">${meta}</p>` : ''}</div>${trail}</div>`;
}

/* ---- Mastery bars: the small vertical-bar meter on My Library's Saved-Language rows and
   Collection Detail's word rows (D2 S7 "pixel-for-pixel identical" - the strongest confirmed
   shared primitive in that pass). `filled` of `total` bars are drawn in `color`, the rest in
   `emptyColor`. */
export function masteryBars({ filled = 0, total = 4, color = 'var(--accent)', emptyColor = 'var(--surface3)' } = {}) {
  const bars = Array.from({ length: total }, (_, i) => html`<span class="c-bars__bar" style="background:${i < filled ? color : emptyColor}"></span>`);
  return html`<span class="c-bars" role="img" aria-label="${filled} / ${total}">${bars}</span>`;
}
