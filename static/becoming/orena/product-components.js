/* Orena product components — the reusable product layer.
 *
 * ORENA_COMPONENT_CONTRACT §1 defines the build order:
 *
 *   design tokens -> UI primitives -> product components -> recipe -> page
 *
 * Everything here sits at the third step. A product component takes SEMANTIC
 * data - what the thing is, what the learner can do with it - and never a
 * page-specific HTML fragment, a column count or a card width. That is the
 * whole point: the same call has to survive a native port that renders it with
 * different primitives, so anything layout-shaped stays in CSS and anything
 * page-shaped stays in the screen.
 *
 * There is deliberately no `bodyHtml` or `secondaryActions` escape hatch. A
 * caller that can pass raw markup will eventually pass page markup, and then
 * the component is a template rather than a component - the native port has to
 * reimplement whatever the page happened to inject. Quotes, notes and secondary
 * links are semantic props instead, and the component decides how they look.
 *
 * Markup is a string, matching the rest of this frontend. There is no framework
 * and none is being introduced.
 *
 * Every component is namespaced `.oc-*` and lives inside `[data-orena-ui="v2"]`
 * so migrating one screen cannot restyle the screens that have not migrated.
 */

import {attr, esc} from '../components/primitives.js';
import {oIcon} from './icons.js';

/* Extra attributes let a migrated screen keep a stable contract hook - the
   handoff attributes Home has always exposed - without a component growing a
   prop for every caller. Values are escaped; keys are restricted to the
   data-attribute shape so a caller cannot inject an event handler. */
function extraAttributes(map = {}) {
  return Object.entries(map || {})
    .filter(([key, value]) => /^data-[a-z0-9-]+$/.test(key) && value !== null && value !== undefined && value !== false)
    .map(([key, value]) => ` ${key}="${attr(String(value))}"`)
    .join('');
}

const ACCENT_FAMILIES = new Set(['listening', 'speaking', 'writing', 'reading', 'grammar', 'review']);
const accent = value => (ACCENT_FAMILIES.has(String(value || '')) ? String(value) : 'listening');

const ARTWORK_RATIOS = new Set(['hero', 'world', 'tile']);

/* Language of the text a component is about to render.
 *
 * This is the whole of the EN/ZH typography rule: the language belongs to the
 * STRING, not to the screen. A Chinese lesson title inside an English
 * interface is Chinese; an English interface label on a Chinese learner's Home
 * is English. Emitting `lang` both drives CJK typography and tells a screen
 * reader which voice to use, so the two can never drift apart. */
function langAttributes(code = '') {
  const value = String(code || '').trim();
  if (!value) return {attribute: '', className: ''};
  return {
    attribute: ` lang="${attr(value)}"`,
    className: /^zh(-|$)/i.test(value) ? ' cjk' : '',
  };
}

/* ------------------------------------------------------------- artwork --- */

/* Artwork is content, not background filler (ORENA_RESPONSIVE_COMPOSITION §14).
 * This is the real container: a stable aspect ratio, a controlled crop and a
 * safe subject inset, so replacing the placeholder with production artwork in
 * H2 is an asset change rather than a layout change.
 *
 * When the content genuinely has a poster - the real video lessons do - it is
 * rendered as an image with a semantic label. Otherwise the frame carries a
 * deterministic tonal wash keyed to the artwork name. The wash is deliberately
 * textless and carries no meaning of its own; it is a development stand-in,
 * never a generated mascot and never a slogan baked into a picture.
 */
export function artworkFrame({artwork = '', posterUrl = '', label = '', ratio = 'world', accentFamily = ''} = {}) {
  const shape = ARTWORK_RATIOS.has(ratio) ? ratio : 'world';
  const key = String(artwork || 'default').trim() || 'default';
  const image = posterUrl
    ? `<img class="oc-artwork-image" src="${attr(posterUrl)}" alt="${attr(label)}" loading="lazy" decoding="async">`
    : '';
  return `<div class="oc-artwork" data-artwork="${attr(key)}" data-artwork-ratio="${attr(shape)}" data-accent="${attr(accent(accentFamily))}"${image ? '' : ' role="presentation"'}>
    <div class="oc-artwork-frame">${image}</div>
  </div>`;
}

/* ---------------------------------------------------------- section ------ */

/* Section chrome is shared so every rail on a migrated screen has the same
   rhythm rather than each page inventing its own heading.
 *
 * `state` is part of the contract, not decoration: a section that is still
 * loading says so in its own box while the rest of the page is already usable,
 * which is what stops one slow provider from holding the whole screen. */
function sectionShell({id, title, description, variant, bodyClass, component, items, empty, state}) {
  const headingId = id ? `${id}-heading` : '';
  const body = state === 'loading'
    ? `<p class="oc-empty" data-oc-notice="loading">${esc(empty)}</p>`
    : items.length
      ? `<div class="${bodyClass}"${component ? ` data-oc-component="${attr(component)}"` : ''}>${items.join('')}</div>`
      : `<p class="oc-empty">${esc(empty)}</p>`;
  return `<section class="oc-section${variant ? ` oc-section--${attr(variant)}` : ''}"${id ? ` data-oc-section="${attr(id)}"` : ''} data-section-state="${attr(state)}"${headingId ? ` aria-labelledby="${attr(headingId)}"` : ''}>
    <header class="oc-section-head">
      <div class="oc-section-titles">
        <h2 class="oc-section-title"${headingId ? ` id="${attr(headingId)}"` : ''}>${esc(title)}</h2>
        ${description ? `<p class="oc-section-lede">${esc(description)}</p>` : ''}
      </div>
    </header>
    ${body}
  </section>`;
}

/* A section of already-rendered product components. `items` are component
   output, never page-authored markup. */
export function productSection({
  id = '', title = '', description = '', items = [], empty = '', state = 'ready', variant = '',
} = {}) {
  return sectionShell({
    id, title, description, variant, bodyClass: 'oc-stack', component: '',
    items, empty, state,
  });
}

/* ------------------------------------------------------- JourneyHero ----- */

/* The dominant emotional entry point, with exactly one primary action.
 * ORENA_HOME_GOLDEN_SPEC §7A: no metrics, no feature checklist, no CEFR, no
 * score. The continuation object may sit inside the hero band on a wide
 * canvas; the hero does not own what it says. */
export function journeyHero({
  eyebrow = '',
  title = '',
  supportingText = '',
  artwork = '',
  posterUrl = '',
  artworkLabel = '',
  accentFamily = '',
  lang = '',
  primaryAction = null,
  continuation = '',
} = {}) {
  const text = langAttributes(lang);
  const action = primaryAction
    ? `<button class="oc-btn oc-btn--primary"${primaryAction.id ? ` id="${attr(primaryAction.id)}"` : ''} type="button"${extraAttributes(primaryAction.attributes)}>
        <span>${esc(primaryAction.label || '')}</span>${oIcon('arrowRight')}
      </button>`
    : '';
  return `<section class="oc-hero" data-oc-component="journey-hero" data-accent="${attr(accent(accentFamily))}">
    <div class="oc-hero-art">${artworkFrame({artwork, posterUrl, label: artworkLabel, ratio: 'hero', accentFamily})}</div>
    <div class="oc-hero-body"${text.attribute}>
      ${eyebrow ? `<p class="oc-hero-eyebrow">${esc(eyebrow)}</p>` : ''}
      <h1 class="oc-hero-title${text.className}">${esc(title)}</h1>
      ${supportingText ? `<p class="oc-hero-lede${text.className}">${esc(supportingText)}</p>` : ''}
      ${action ? `<div class="oc-hero-actions">${action}</div>` : ''}
    </div>
    ${continuation ? `<div class="oc-hero-continue">${continuation}</div>` : ''}
  </section>`;
}

/* ------------------------------------------------- ContinueJourneyCard --- */

/* Resume real persisted learner state.
 *
 * `progressLabel` is a string the caller has to be able to defend. There is no
 * numeric progress prop on purpose: the resume contract carries a lesson, a
 * segment and an attempt count, not a completion ratio, and a component that
 * accepted a percentage would invite one to be invented. When a real contract
 * later supplies completion, it arrives as its own prop and the meter appears
 * with it.
 *
 * `titleLang` describes the TITLE, which is learning content. The kicker,
 * subtitle and resume label are interface copy in the interface language. */
export function continueJourneyCard({
  journeyId = '',
  kicker = '',
  title = '',
  titleLang = '',
  subtitle = '',
  progressLabel = '',
  artwork = '',
  posterUrl = '',
  accentFamily = '',
  resumeLabel = '',
  actionAttributes = {},
  attributes = {},
} = {}) {
  const heading = langAttributes(titleLang);
  return `<article class="oc-continue" data-oc-component="continue-journey" data-journey-id="${attr(journeyId)}" data-accent="${attr(accent(accentFamily))}"${extraAttributes(attributes)}>
    ${artworkFrame({artwork, posterUrl, label: title, ratio: 'tile', accentFamily})}
    <div class="oc-continue-body">
      ${kicker ? `<p class="oc-kicker">${esc(kicker)}</p>` : ''}
      <h3 class="oc-continue-title${heading.className}"${heading.attribute}>${esc(title)}</h3>
      ${subtitle ? `<p class="oc-continue-sub">${esc(subtitle)}</p>` : ''}
      ${progressLabel ? `<p class="oc-continue-state">${esc(progressLabel)}</p>` : ''}
    </div>
    <button class="oc-btn oc-btn--primary oc-btn--compact" type="button"${extraAttributes(actionAttributes)}>${esc(resumeLabel)}</button>
  </article>`;
}

/* ---------------------------------------------------------- WorldCard ---- */

/* A World should read as a place to enter. Artwork leads, the title stays out
 * of the image, and the lesson count is supporting metadata rather than the
 * visual hero (ORENA_COMPONENT_CONTRACT §5). The count is only rendered when
 * the caller passes one it measured. */
/* A World's lead label reads as one phrase - "Start with {title}" - but it is
   made of two different languages: the prefix is interface copy in the
   interface language, and the title is the lesson's own content language.
   Treating the whole phrase as one string forces a single `lang`, which is
   wrong in either direction as soon as interface and content languages
   differ. The two halves carry their own `lang` instead. */
export function worldCard({
  worldId = '',
  title = '',
  description = '',
  lang = '',
  artwork = '',
  posterUrl = '',
  accentFamily = '',
  countLabel = '',
  leadPrefix = '',
  leadTitle = '',
  leadSuffix = '',
  leadLang = '',
  variant = 'standard',
  attributes = {},
  openAttributes = {},
} = {}) {
  const shape = ['featured', 'standard', 'compact'].includes(variant) ? variant : 'standard';
  const text = langAttributes(lang);
  const lead = langAttributes(leadLang);
  const leadMarkup = leadTitle
    ? `<span class="oc-meta oc-meta--lead">${leadPrefix ? `<span class="oc-lead-prefix${text.className}"${text.attribute}>${esc(leadPrefix)}</span> ` : ''}<span class="oc-lead-title${lead.className}"${lead.attribute}>${esc(leadTitle)}</span>${leadSuffix ? ` <span class="oc-lead-suffix${text.className}"${text.attribute}>${esc(leadSuffix)}</span>` : ''}</span>`
    : '';
  return `<article class="oc-world" data-oc-component="world-card" data-world-id="${attr(worldId)}" data-variant="${attr(shape)}" data-accent="${attr(accent(accentFamily))}"${extraAttributes(attributes)}>
    <button class="oc-world-open" type="button" data-world-open="${attr(worldId)}"${extraAttributes(openAttributes)}>
      ${artworkFrame({artwork, posterUrl, label: title, ratio: 'world', accentFamily})}
      <span class="oc-world-body">
        <span class="oc-world-title${text.className}"${text.attribute}>${esc(title)}</span>
        ${description ? `<span class="oc-world-lede${text.className}"${text.attribute}>${esc(description)}</span>` : ''}
        <span class="oc-world-meta">
          ${countLabel ? `<span class="oc-meta">${esc(countLabel)}</span>` : ''}
          ${leadMarkup}
        </span>
      </span>
    </button>
  </article>`;
}

/* WorldRail is one semantic component whose composition adapts: a mosaic row on
   desktop, a grid on tablet, a horizontal rail on mobile. Three viewports, one
   product concept (ORENA_RESPONSIVE_COMPOSITION §9). */
export function worldRail({id = 'worlds', title = '', description = '', cards = [], empty = '', state = 'ready'} = {}) {
  return sectionShell({
    id, title, description, variant: 'worlds', bodyClass: 'oc-world-rail',
    component: 'world-rail', items: cards, empty, state,
  });
}

/* -------------------------------------------------- RecommendationTile --- */

/* One learning opportunity.
 *
 * `reason` is learner-facing language about why this is here; implementation
 * vocabulary such as a recommendation score must never reach it. `quote` is
 * the learner's own sentence when the recommendation is built from their own
 * evidence. `note` is one supporting line that needs its own contract hook.
 * `links` are secondary actions. All four are semantic, so a native client
 * renders them with native primitives instead of parsing HTML. */
export function recommendationTile({
  contentId = '',
  contentKind = '',
  title = '',
  subtitle = '',
  lang = '',
  reason = '',
  quote = '',
  quoteLang = '',
  note = null,
  meta = '',
  accentFamily = '',
  actionLabel = '',
  actionAttributes = null,
  links = [],
  attributes = {},
} = {}) {
  const text = langAttributes(lang);
  const quoted = langAttributes(quoteLang || lang);
  const action = actionLabel && actionAttributes
    ? `<button class="oc-btn oc-btn--primary oc-btn--compact" type="button"${extraAttributes(actionAttributes)}>${esc(actionLabel)}</button>`
    : '';
  const secondary = (Array.isArray(links) ? links : [])
    .filter(link => link && link.label)
    .map(link => `<button type="button" class="oc-link"${extraAttributes(link.attributes)}>${esc(link.label)}</button>`)
    .join('');
  const noteLine = note && note.text
    ? `<p class="oc-meta"${extraAttributes(note.attributes)}>${esc(note.text)}</p>`
    : '';
  return `<article class="oc-tile" data-oc-component="recommendation-tile" data-content-kind="${attr(contentKind)}"${contentId ? ` data-content-id="${attr(contentId)}"` : ''} data-accent="${attr(accent(accentFamily))}"${extraAttributes(attributes)}>
    <div class="oc-tile-body">
      ${reason ? `<p class="oc-kicker">${esc(reason)}</p>` : ''}
      <h3 class="oc-tile-title${text.className}"${text.attribute}>${esc(title)}</h3>
      ${subtitle ? `<p class="oc-tile-sub${text.className}"${text.attribute}>${esc(subtitle)}</p>` : ''}
      ${quote ? `<blockquote class="oc-quote${quoted.className}"${quoted.attribute}>&ldquo;${esc(quote)}&rdquo;</blockquote>` : ''}
      ${noteLine}
      ${meta ? `<p class="oc-meta">${esc(meta)}</p>` : ''}
    </div>
    ${action || secondary ? `<div class="oc-tile-actions">${action}${secondary}</div>` : ''}
  </article>`;
}

export function recommendationRail({id = 'for-you', title = '', description = '', tiles = [], empty = '', state = 'ready'} = {}) {
  return sectionShell({
    id, title, description, variant: 'for-you', bodyClass: 'oc-tile-rail',
    component: 'recommendation-rail', items: tiles, empty, state,
  });
}

/* ------------------------------------------------------ ChallengeCard ---- */

/* One small concrete reason to act now, tied to real learning evidence.
 * `current`/`target` are rendered only when both are real finite numbers the
 * caller measured; a challenge with no measurement simply has no meter rather
 * than a decorative empty bar. No casino-style reward language belongs here. */
export function challengeCard({
  challengeId = '',
  kicker = '',
  title = '',
  description = '',
  lang = '',
  current = null,
  target = null,
  unitLabel = '',
  rewardCopy = '',
  accentFamily = 'review',
  actionLabel = '',
  actionAttributes = null,
  attributes = {},
} = {}) {
  const text = langAttributes(lang);
  const measured = Number.isFinite(Number(current)) && Number.isFinite(Number(target)) && Number(target) > 0;
  const ratio = measured ? Math.max(0, Math.min(100, Math.round((Number(current) / Number(target)) * 100))) : 0;
  const meter = measured
    ? `<div class="oc-meter" role="img" aria-label="${attr(`${current} / ${target}${unitLabel ? ` ${unitLabel}` : ''}`)}"><span style="width:${ratio}%"></span></div>`
    : '';
  const action = actionLabel && actionAttributes
    ? `<button class="oc-btn oc-btn--primary oc-btn--compact" type="button"${extraAttributes(actionAttributes)}>${esc(actionLabel)}</button>`
    : '';
  return `<article class="oc-challenge" data-oc-component="challenge-card"${challengeId ? ` data-challenge-id="${attr(challengeId)}"` : ''} data-accent="${attr(accent(accentFamily))}"${extraAttributes(attributes)}>
    <div class="oc-challenge-body">
      ${kicker ? `<p class="oc-kicker">${esc(kicker)}</p>` : ''}
      <h3 class="oc-challenge-title${text.className}"${text.attribute}>${esc(title)}</h3>
      ${description ? `<p class="oc-challenge-copy${text.className}"${text.attribute}>${esc(description)}</p>` : ''}
      ${meter}
      ${rewardCopy ? `<p class="oc-meta">${esc(rewardCopy)}</p>` : ''}
    </div>
    ${action}
  </article>`;
}

/* ------------------------------------------------------- DiscoveryCard --- */

/* Keeps the lower page exploratory. This is what replaces the analytics that
   used to live at the bottom of Home. */
export function discoveryCard({
  contentId = '',
  kicker = '',
  title = '',
  description = '',
  lang = '',
  meta = '',
  artwork = '',
  posterUrl = '',
  accentFamily = '',
  openAttributes = {},
} = {}) {
  const text = langAttributes(lang);
  return `<article class="oc-discovery" data-oc-component="discovery-card"${contentId ? ` data-content-id="${attr(contentId)}"` : ''} data-accent="${attr(accent(accentFamily))}">
    <button class="oc-discovery-open" type="button"${extraAttributes(openAttributes)}>
      ${artworkFrame({artwork, posterUrl, label: title, ratio: 'tile', accentFamily})}
      <span class="oc-discovery-body">
        ${kicker ? `<span class="oc-kicker">${esc(kicker)}</span>` : ''}
        <span class="oc-discovery-title${text.className}"${text.attribute}>${esc(title)}</span>
        ${description ? `<span class="oc-discovery-lede${text.className}"${text.attribute}>${esc(description)}</span>` : ''}
        ${meta ? `<span class="oc-meta">${esc(meta)}</span>` : ''}
      </span>
    </button>
  </article>`;
}

export function discoveryRail({id = 'continue-exploring', title = '', description = '', cards = [], empty = '', state = 'ready'} = {}) {
  return sectionShell({
    id, title, description, variant: 'discovery', bodyClass: 'oc-discovery-rail',
    component: 'discovery-rail', items: cards, empty, state,
  });
}

/* --------------------------------------------------------- section state - */

/* A failed optional section degrades to its own scoped notice; it never blanks
   the page around it (ORENA_HOME_GOLDEN_SPEC §11). */
export function sectionNotice({message = '', tone = 'quiet'} = {}) {
  return `<p class="oc-empty" data-oc-notice="${attr(tone)}">${esc(message)}</p>`;
}
