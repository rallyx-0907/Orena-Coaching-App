import { esc } from './html.js';
import { origin } from './content.js';
import { link } from '../product/intent.js';

/* One row for anything readable: a passage the learner asked for, an authored
   story, a text they brought in. They differ in where they came from, which is
   what the label says, and in nothing else about how they are read. */
/* Whether a check is waiting, said before the learner opens the text. Reading
   a piece through is a complete thing to do, so a passage with no questions
   says so plainly rather than being indistinguishable from one whose questions
   simply have not loaded - and nothing is invented to make every text alike. */
export function checkLabel(c, item) {
  if (item.attempted) return c.comprehensionDone;
  /* Two ways of knowing, and one way of not. A list entry from the API states
     its count. A full readable item carries its own paragraphs, so the absence
     of questions on it is a fact rather than a gap - `readable()` only sets the
     field when there are some. A stub with neither says nothing at all, because
     "no questions" and "not loaded yet" are different claims. */
  const whole = Boolean(item.paragraphs?.length || item.text);
  const count = Number.isInteger(item.question_count)
    ? item.question_count
    : whole
      ? (item.questions || []).length
      : null;
  if (count === null) return '';
  return count > 0 ? `${count} ${c.comprehensionWaiting}` : c.readingOnly;
}

export function readingRow(item, c) {
  const href = link('encounter', { id: item.id, intent: 'reading' });
  const check = checkLabel(c, item);
  return `<a class="reading-row reading-volume" href="${href}"><span class="reading-mark" aria-hidden="true">${esc(
    (item.title || '?').trim().slice(0, 1),
  )}</span><span class="reading-volume-copy"><small>${esc(origin(item, c))}${item.level ? ` · ${esc(item.level)}` : ''}</small><strong lang="${esc(item.language || '')}">${esc(item.title)}</strong>${
    item.subtitle
      ? `<span class="voice-description" lang="${esc(item.language || '')}">${esc(item.subtitle)}</span>`
      : ''
  }${check ? `<span class="byline">${esc(check)}</span>` : ''}</span><span aria-hidden="true">↗</span></a>`;
}
