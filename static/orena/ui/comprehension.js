import { esc } from './html.js';
import { icon } from './phosphor.js';
import { highlighted } from './quick-sheet.js';
import { referenceCopy } from './reference.js';

/* An optional check on what a passage left behind. It is offered after the
   text, never before it, and nothing in the encounter waits for it: a learner
   who reads a piece and moves on has read it.

   What makes it worth answering is not the score. Every result names the words
   in the passage that settle the question, and those words lead back into the
   text, so a wrong answer sends the learner to the paragraph rather than to a
   correction.

   The canonical check (D-067, "Reading · comprehension question" and
   "· comprehension result") is one question, answered, then answered *back*:
   the verdict, the lines that settle it and why, before the next question. So
   the server scores one question as the learner answers it, and the attempt -
   the whole set, which is what a learner's record has always meant - is still
   written once, at the end. Nothing here invents a verdict on the client.

   The frames draw no rail, no lettered options, no question type, no running
   score and no invitation card: the check opens from the bar under the text,
   at question one (rule 44). */

const fill = (template, values) =>
  String(template || '').replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));

/* Pure reading is a complete thing to do. A text with no questions says so in
   one quiet line rather than showing nothing, because an absent section and a
   section that failed to load look identical - and nothing is fabricated to
   make every text carry a check. */
export function comprehensionSection(c, questions) {
  if (!questions?.length)
    return `<p class="meta comprehension-absent">${esc(c.readingOnlyNote)}</p>`;
  return `<section class="quiz" data-comprehension><div class="quiz-step" data-quiz-step></div><p role="status" data-comprehension-status></p></section>`;
}

/* Binds the check. `onEvidence` shows the passage an answer lives in, so "see
   it in the text" lands on the words themselves; `passageOfEvidence` is the
   paragraph they stand in, which the result quotes; `onDiscuss` opens the
   discussion the reader already has. */
export function bindComprehension(
  root,
  ctx,
  { sessionId, questions, onEvidence, passageOfEvidence = null, onDiscuss = null },
) {
  const section = root.querySelector('[data-comprehension]');
  if (!section || !questions?.length) return;
  const { c, api, support, alive } = ctx;
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const step = section.querySelector('[data-quiz-step]');
  const state = section.querySelector('[data-comprehension-status]');

  const total = questions.length;
  const answers = questions.map(() => null);
  const graded = questions.map(() => null);
  let index = 0;
  let sending = false;
  let recorded = false;

  const head = () =>
    `<header class="quiz-bar"><span class="ds-data quiz-place">${esc(fill(c.quizPlace, { n: index + 1, t: total }))}</span></header>`;

  const optionRow = (option, choice) =>
    `<button type="button" class="quiz-option"${answers[index] === choice ? ' data-tone="picked"' : ''} data-quiz-option="${choice}" aria-pressed="${answers[index] === choice}"><span class="quiz-option__text">${esc(option)}</span></button>`;

  const askingView = () => {
    const question = questions[index];
    return `${head()}<div class="quiz-ask"><h3 class="quiz-question">${esc(question.question)}</h3><div class="quiz-options">${question.options
      .map(optionRow)
      .join('')}</div></div><div class="quiz-foot"><p class="quiz-skip">${esc(c.quizSkip)}</p><button type="button" class="primary quiz-primary" data-quiz-answer${answers[index] === null || sending ? ' disabled' : ''}>${esc(c.quizAnswer)}</button></div>`;
  };

  /* The lines that settle it, in the paragraph they stand in, with the words
     themselves marked - which is how the frame draws them. */
  const evidence = (found) => {
    const fragment = found.evidence_fragment || '';
    if (!fragment) return '';
    const passage = passageOfEvidence?.(fragment) || fragment;
    return `<div class="quiz-evidence"><span class="ds-label">${esc(c.quizEvidenceLabel)}</span><blockquote class="quiz-evidence__text" lang="${esc(ctx.language)}">${highlighted(passage, fragment)}</blockquote></div>`;
  };

  const answeredView = () => {
    const found = graded[index];
    const last = index === total - 1;
    const explanation = support === 'vi' && found.explanation_vi ? found.explanation_vi : '';
    const verdict = found.correct
      ? `<span class="quiz-verdict" data-tone="right">${icon('check-circle', { filled: true, size: 24 })}<strong>${esc(c.quizRight)}</strong></span>`
      : `<span class="quiz-verdict" data-tone="wrong">${icon('x-circle', { filled: true, size: 24 })}<strong>${esc(c.quizWrong)}</strong></span>`;
    const back = found.evidence_fragment
      ? `<button type="button" class="quiz-quiet" data-quiz-look>${icon('arrow-u-up-left', { size: 18 })}${esc(c.quizBackToText)}</button>`
      : '';
    const discuss = onDiscuss
      ? `<button type="button" class="quiz-quiet" data-quiz-discuss>${icon('chats-circle', { size: 18 })}${esc(r.readerDiscuss)}</button>`
      : '';
    return `${head()}<div class="quiz-result">${verdict}${evidence(found)}${
      explanation ? `<p class="quiz-why" lang="vi">${esc(explanation)}</p>` : ''
    }</div><div class="quiz-foot">${back || discuss ? `<div class="quiz-actions">${back}${discuss}</div>` : ''}<button type="button" class="primary quiz-primary" data-quiz-next>${esc(last ? c.quizFinish : c.quizNext)}</button></div>`;
  };

  function paintStep() {
    if (!alive()) return;
    step.innerHTML = graded[index] ? answeredView() : askingView();
    bindStep();
  }

  function bindStep() {
    step.querySelectorAll('[data-quiz-option]').forEach((button) => {
      button.onclick = () => {
        answers[index] = Number(button.dataset.quizOption);
        paintStep();
      };
    });
    step.querySelector('[data-quiz-answer]')?.addEventListener('click', answer);
    step.querySelector('[data-quiz-next]')?.addEventListener('click', () => {
      if (index === total - 1) return leave();
      index += 1;
      paintStep();
      step.scrollIntoView({ block: 'nearest' });
    });
    step.querySelector('[data-quiz-look]')?.addEventListener('click', () => {
      onEvidence?.(graded[index].evidence_fragment);
      leave();
    });
    step.querySelector('[data-quiz-discuss]')?.addEventListener('click', () => {
      leave();
      onDiscuss?.();
    });
  }

  /* The check opened as a sheet over the text, so leaving it is closing that
     sheet - there is nothing underneath it to go back to. */
  function leave() {
    section.closest('dialog')?.close();
  }

  async function answer() {
    if (sending || answers[index] === null) return;
    sending = true;
    state.textContent = c.saving;
    paintStep();
    try {
      const scored = await api.gradeReadingAnswer(sessionId, index, answers[index]);
      if (!alive()) return;
      if (!scored.valid || !scored.result) throw Error('Reading check unavailable');
      graded[index] = scored.result;
      state.textContent = '';
      paintStep();
      await record();
    } catch {
      if (alive()) state.textContent = c.comprehensionUnavailable;
    } finally {
      sending = false;
      if (alive() && !graded[index]) paintStep();
    }
  }

  /* One attempt for the set, written when the learner has been through it, so
     what is stored about a learner's reading means what it always meant. */
  async function record() {
    if (recorded || answers.some((choice) => choice === null)) return;
    recorded = true;
    try {
      await ctx.mutate(() => api.submitReadingAnswers(sessionId, answers));
    } catch {
      recorded = false;
    }
  }

  paintStep();
}
