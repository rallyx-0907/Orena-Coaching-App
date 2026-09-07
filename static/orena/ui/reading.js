import { esc, dialog } from './html.js';
import { origin } from './content.js';
import {
  READING_SUBJECTS,
  READING_FORMS,
  readingId,
} from '../content/reading.js';
import { link } from '../product/intent.js';

/* Asking for something to read. The learner chooses what it is about and what
   form it takes, because a book excerpt, a news report and a short quotation
   are read differently.

   When no generator is configured the API answers with its built-in passage
   instead, which is the same words whatever was asked for. That is said here
   rather than left for the learner to notice, and the encounter repeats it. */

export function openReadingRequest(ctx) {
  const { c, api, alive } = ctx;
  const levels =
    ctx.languageProfiles?.find((x) => x.code === ctx.language)?.levels || [];
  const sheet = dialog({
    title: c.readingAsk,
    body: `<form class="reading-ask">
      <p class="meta">${esc(c.readingAskNote)}</p>
      <label for="readingForm">${esc(c.readingForm)}</label>
      <select id="readingForm" name="material">${READING_FORMS.map(
        (form) =>
          `<option value="${form}">${esc(c[`form_${form}`] || form)}</option>`,
      ).join('')}</select>
      <label for="readingLevel">${esc(c.reviewTarget)}</label>
      <select id="readingLevel" name="target_level" required><option value="">${esc(c.chooseTarget)}</option>${levels.map((level) => `<option value="${esc(level)}">${esc(level)}</option>`).join('')}</select>
      <label for="readingSubject">${esc(c.readingSubject)}</label>
      <select id="readingSubject" name="topic">${READING_SUBJECTS.map(
        (topic) =>
          `<option value="${topic}">${esc(c[`subject_${topic}`] || topic)}</option>`,
      ).join('')}</select>
      <button class="primary">${esc(c.readingBring)}</button>
      <p role="status" data-reading-status></p>
    </form>`,
  });
  const form = sheet.querySelector('.reading-ask');
  const state = sheet.querySelector('[data-reading-status]');
  form.onsubmit = async (event) => {
    event.preventDefault();
    state.textContent = c.readingWorking;
    form.querySelector('button').disabled = true;
    try {
      const session = await ctx.mutate(() =>
        api.createReadingSession({
          topic: form.elements.topic.value,
          material: form.elements.material.value,
          target_level: form.elements.target_level.value,
          recycle_library: true,
        }),
      );
      if (!alive() || !sheet.isConnected) return;
      sheet.close();
      window.location.hash = link('encounter', {
        id: readingId(session.id),
        intent: 'reading',
      });
    } catch {
      if (!alive()) return;
      state.textContent = c.readingUnavailable;
      form.querySelector('button').disabled = false;
    }
  };
  return sheet;
}

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
  return `<a class="reading-row" href="${href}"><span class="reading-mark" aria-hidden="true">${esc(
    (item.title || '?').trim().slice(0, 1),
  )}</span><span><small>${esc(origin(item, c))}${item.level ? ` · ${esc(item.level)}` : ''}</small><strong lang="${esc(item.language || '')}">${esc(item.title)}</strong>${
    item.subtitle
      ? `<span class="voice-description" lang="${esc(item.language || '')}">${esc(item.subtitle)}</span>`
      : ''
  }${check ? `<span class="byline">${esc(check)}</span>` : ''}</span><span aria-hidden="true">↗</span></a>`;
}
