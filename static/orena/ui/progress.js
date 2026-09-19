/* Progress (D-059): the learner's own recorded evidence, one domain at a time.

   The design system draws a streak, weekly minutes and a bar chart. Orena
   records none of those, and LearnerSummary's first rule is that unknown is
   not zero - so this page shows what the summary actually holds: each
   domain's activity in the chosen window, the reason a trend is not shown yet,
   and the honest state when a domain could not be read. Nothing is invented to
   fill the design's shapes (docs/product/ORENA_EVIDENCE_ARCHITECTURE.md).

   The row wording is `growthDomainRow`, shared with the settings sheet, so the
   two can never describe the same evidence differently. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { GROWTH_DOMAINS, growthDomainRow } from './growth-summary.js';
import { referenceCopy } from './reference.js';
import { link } from '../product/intent.js';

const WINDOWS = ['7d', '30d', '90d', 'all'];
/* Each evidence domain wears the design-system domain it belongs to. Grammar
   is horizontal (D-050), so it takes the neutral tile rather than a hue. */
const DOMAIN_LOOK = {
  reading: { domain: 'reading', icon: 'book-open', href: () => link('practice', { intent: 'reading' }) },
  listening: { domain: 'listening', icon: 'headphones', href: () => link('practice', { intent: 'follow' }) },
  speaking: { domain: 'speaking', icon: 'microphone', href: () => link('practice', { intent: 'speaking' }) },
  writing: { domain: 'writing', icon: 'pencil-simple', href: () => link('expression') },
  grammar: { domain: 'neutral', icon: 'sparkle', href: () => link('practice', { intent: 'grammar' }) },
  language: { domain: 'vocabulary', icon: 'cards', href: () => link('language') },
};
const ORDER = ['reading', 'listening', 'speaking', 'writing', 'language', 'grammar'];

function domainCard(c, key, domain) {
  const look = DOMAIN_LOOK[key];
  const { label, value } = growthDomainRow(c, key, domain);
  const state = !domain || domain.status === 'unavailable' ? 'unavailable' : 'ready';
  return `<li class="progress-domain" data-state="${state}"><a class="progress-domain__link" href="${look.href()}"><span class="domain-tile" data-domain="${look.domain}">${icon(look.icon, { size: 20 })}</span><span class="progress-domain__text"><span class="progress-domain__label">${label}</span><span class="progress-domain__value">${value}</span></span>${icon('caret-right', { size: 18, className: 'progress-domain__go' })}</a></li>`;
}

function skeleton() {
  return `<ul class="progress-domains" aria-hidden="true">${ORDER.map(() => '<li class="progress-domain"><span class="skeleton skeleton--card"></span></li>').join('')}</ul>`;
}

export async function renderProgress(root, ctx) {
  const c = ctx.c;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  let windowKey = 'all';
  let summary = ctx.growth || null;
  let released = false;

  const windowControl = () =>
    `<div class="segmented" role="radiogroup" aria-label="${esc(r.progressWindow)}">${WINDOWS.map(
      (key) =>
        `<button type="button" role="radio" aria-checked="${key === windowKey}" data-window="${key}">${esc(r[`progressWindow_${key}`])}</button>`,
    ).join('')}</div>`;

  const body = (state) => {
    if (state === 'loading') return skeleton();
    if (state === 'failed' || !summary)
      return `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 22 })}<div><strong>${esc(c.growthUnavailable)}</strong></div><button class="outline" type="button" data-progress-retry>${icon('arrow-counter-clockwise', { size: 18 })}<span>${esc(c.retry)}</span></button></div>`;
    const rows = ORDER.filter((key) => GROWTH_DOMAINS.includes(key))
      .map((key) => domainCard(c, key, summary.domains?.[key]))
      .join('');
    const partial = summary.outcome === 'partial' ? `<p class="meta">${esc(c.growthPartialNote)}</p>` : '';
    return `<ul class="progress-domains">${rows}</ul>${partial}<p class="progress-footnote">${icon('trophy', { size: 18 })}<span>${esc(c.growthAchievements)}: ${esc(c.growthAchievementsUnavailable)}</span></p>`;
  };

  const paint = (state) => {
    if (released || !ctx.alive()) return;
    root.innerHTML = `<section class="progress-page"><header class="page-head"><div><h1>${esc(r.progress)}</h1><p class="page-head__note">${esc(c.growthNote)}</p></div>${windowControl()}</header><div class="progress-body" aria-live="polite" aria-busy="${state === 'loading'}">${body(state)}</div></section>`;
    root.querySelectorAll('[data-window]').forEach((button) => {
      button.onclick = () => {
        if (button.dataset.window === windowKey) return;
        windowKey = button.dataset.window;
        load();
      };
    });
    root.querySelector('[data-progress-retry]')?.addEventListener('click', load);
  };

  async function load() {
    paint('loading');
    try {
      summary = await ctx.api.learnerSummary(windowKey);
      if (windowKey === 'all') ctx.growth = summary;
      paint('ready');
    } catch {
      summary = null;
      paint('failed');
    }
  }

  if (summary) paint('ready');
  else await load();
  return () => {
    released = true;
  };
}
