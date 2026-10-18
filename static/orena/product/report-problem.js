/* "Report a problem" on an AI-written output (PRE-206, owner decision of 2026-10-18).

   One small text link opens the existing Feedback screen with a context reference in the query: which area it is
   about and a short reference (surface, content id, the word or sentence). The Feedback screen turns that into a
   chosen area and a one-line reference at the start of the message; POST /api/feedback is unchanged and takes no new
   field - the reference travels in `text`, with whatever the learner adds. The learner's own words are never read
   here. */
import { html } from '../kit/html.js';
import { shellCopy } from '../copy/shell.js';
import { href } from '../shell/routes.js';

export const REF_LIMIT = 140;

/* Collapse a reference to one short line: no newlines, no brackets (the screen wraps it in some), bounded. */
export function cleanRef(parts) {
  const text = (Array.isArray(parts) ? parts : [parts])
    .map((part) => String(part ?? '').replace(/[\r\n\t[\]]+/g, ' ').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join(' | ');
  return text.length > REF_LIMIT ? `${text.slice(0, REF_LIMIT - 1)}…` : text;
}

/* The address of the Feedback screen for one output: `area` is one of Feedback's areas, `ref` its short reference. */
export function reportHref({ area = '', surface = '', id = '', text = '' } = {}) {
  return href('feedback', {}, { area, ref: cleanRef([surface, id, text]) });
}

/* The link itself - the sheet "retry" / Discover "Clear filters" text-button pattern (`o-btn--link`). The caller binds
   it with `bindReport(root, go)`: the address is on the button, the navigation is the caller's own `go`. */
export function reportLink(output) {
  return html`<button type="button" class="o-btn o-btn--link" data-report-problem data-report-href="${reportHref(output)}">${shellCopy('reportProblem')}</button>`;
}

export function bindReport(root, go) {
  root?.querySelectorAll?.('[data-report-problem]').forEach((button) => {
    button.addEventListener('click', () => go(button.dataset.reportHref));
  });
}
