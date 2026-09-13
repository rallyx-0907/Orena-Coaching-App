/* Your growth: a read-only glance at the learner's own recorded evidence, one
   domain at a time. LearnerSummary (I6) already decided every honest state
   this renders - unavailable, empty, undated, at-least, no trend yet, no
   approved achievement policy - so this module adds no new judgement of its
   own: never a score, a rank, or an invented trend, and never a domain shown
   as empty when the read simply failed.

   The fixed window is `all`: an "undated" record (grammar completion carries
   no timestamp - see writing_coach/learner_summary.py's `_grammar`) is real
   activity that happened, and `all` is the one window where leaving it out
   would be the misleading choice rather than the honest one. There is no
   window switcher here; adding one is a later, separate slice.

   See docs/product/ORENA_EVIDENCE_ARCHITECTURE.md §§1-5. */
import { esc } from './html.js';
import { hint } from './patterns.js';

export const GROWTH_DOMAINS = ['writing', 'reading', 'listening', 'speaking', 'grammar', 'language'];

/* One domain's row: its label (with a hint explaining why it has no trend,
   when the summary named a reason) and its activity, or the summary's own
   words for "could not be read" / "nothing yet". */
export function growthDomainRow(c, key, domain) {
  const label = c['growthDomain_' + key] || key;
  if (!domain || domain.status === 'unavailable')
    return { label: esc(label), value: esc(c.growthDomainUnavailable) };
  const activity = domain.activity || { count: 0, undated: 0, label: '' };
  // Time-placed and undated records are both real activity that happened;
  // only a trend needs to know when, and no domain claims one yet.
  const total = (activity.count || 0) + (activity.undated || 0);
  // English inflects "1 check answered" against "5 checks answered". Chinese
  // does not ("1/5 次完成的检测"), so its `_one` copy is identical to its plural
  // copy - kept as its own key only so EN and ZH stay the same key set
  // (governance check in scripts/test_orena_product.mjs).
  const activityLabel =
    (total === 1 && c['growthActivity_' + activity.label + '_one']) ||
    c['growthActivity_' + activity.label] ||
    activity.label ||
    '';
  const atLeast = activity.countKind === 'at_least' && total ? `${c.growthAtLeast} ` : '';
  const value = total ? `${atLeast}${total} ${activityLabel}`.trim() : c.growthEmptyDomain;
  const reason = domain.growth?.reason && c['growthReason_' + domain.growth.reason];
  const labelHtml = reason
    ? `${esc(label)}${hint({ text: reason, label: `${label}: ${c.growthNoTrendYet}` })}`
    : esc(label);
  return { label: labelHtml, value: esc(value) };
}

export function growthSummarySection(ctx) {
  const c = ctx.c;
  const growth = ctx.growth;
  if (!growth)
    return `<section class="growth-summary"><h2>${c.growthTitle}</h2><p>${c.growthUnavailable}</p></section>`;
  const rows = GROWTH_DOMAINS.map((key) => {
    const { label, value } = growthDomainRow(c, key, growth.domains?.[key]);
    return `<li><span>${label}</span><span>${value}</span></li>`;
  }).join('');
  const partial = growth.outcome === 'partial' ? `<p class="meta">${c.growthPartialNote}</p>` : '';
  return `<section class="growth-summary"><h2>${c.growthTitle}</h2><p>${c.growthNote}</p>${partial}<ul>${rows}</ul><p class="growth-achievements">${c.growthAchievements}: ${c.growthAchievementsUnavailable}</p></section>`;
}
