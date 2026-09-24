import { esc } from './html.js';
import { icon } from './phosphor.js';
import { hint } from './patterns.js';
import { openUnderstanding } from './understanding.js';

/* An optional check on what a passage left behind. It is offered after the
   text, never before it, and nothing in the encounter waits for it: a learner
   who reads a piece and moves on has read it.

   What makes it worth answering is not the score. Every result names the words
   in the passage that settle the question, and those words can be taken into
   the shared explanation the same way any other phrase can. The API calls this
   a comprehension check only, and the surface repeats that rather than letting
   four questions look like a measure of the learner's reading.

   The approved quiz (D-059 Phase 5, Screens part 3 section 13) is one question
   at a time: a progress rail, the question, lettered options, then the answer
   with the words in the text that settle it. The API scores a whole set, so
   the answers are collected first and the same rail walks back through them
   with the results - a real score for real answers, never a per-question
   verdict invented on the client.

   The questions are an Admin-approved set for a published corpus article
   (D-075); the caller supplies `submit`, which saves the answer sheet as
   canonical Reading evidence and returns, per question, whether it was right,
   the correct option, the explanation in the learner's support language and
   the words of the passage that settle it. */

const fill = (template, values) =>
  String(template || '').replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match));

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];

/* Pure reading is a complete thing to do. A text with no questions says so in
   one quiet line rather than showing nothing, because an absent section and a
   section that failed to load look identical - and nothing is fabricated to
   make every text carry a check. */
export function comprehensionSection(c, questions, latestAttempt) {
  if (!questions?.length)
    return `<p class="meta comprehension-absent">${esc(c.readingOnlyNote)}</p>`;
  /* The invitation, not the questions: the check stays optional and stays
     closed until the learner opens it. */
  return `<section class="quiz" data-comprehension>
    <div class="quiz-invite" data-quiz-invite>
      <span class="ds-label">${esc(c.comprehension)} · ${esc(c.comprehensionOptional)}</span>
      <strong>${esc(fill(c.quizQuestions, { n: questions.length }))}</strong>
      ${latestAttempt ? `<p class="quiz-before ds-data">${esc(c.comprehensionDone)} · ${esc(latestAttempt.correct_count)}/${esc(latestAttempt.total)}</p>` : ''}
      <div class="button-row"><button type="button" class="primary" data-quiz-start>${icon('check-circle', { size: 18 })}<span>${esc(c.comprehensionCheck)}</span></button>${hint({ text: c.comprehensionNote })}</div>
    </div>
    <div class="quiz-step" data-quiz-step hidden></div>
    <p role="status" data-comprehension-status></p>
  </section>`;
}

/* Binds the check. `submit(answers)` resolves to one result per question;
   `onEvidence` lets the encounter show the passage where an answer lives, so a
   wrong answer sends the learner back to the text rather than to a correction;
   `placeOfEvidence` tells it which paragraph that was, when the encounter
   knows. */
export function bindComprehension(
  root,
  ctx,
  { submit: submitAnswers, questions, onEvidence, placeOfEvidence = null, origin = null },
) {
  const section = root.querySelector('[data-comprehension]');
  if (!section || !questions?.length || typeof submitAnswers !== 'function') return;
  const { c, support, alive } = ctx;
  const invite = section.querySelector('[data-quiz-invite]');
  const step = section.querySelector('[data-quiz-step]');
  const state = section.querySelector('[data-comprehension-status]');

  const total = questions.length;
  const answers = questions.map(() => null);
  let index = 0;
  let results = null;
  let sending = false;

  const rail = () =>
    `<div class="quiz-rail" aria-hidden="true">${questions
      .map((_, position) => {
        const done = results ? true : answers[position] !== null;
        const tone = results ? (results[position]?.correct ? 'right' : 'wrong') : done ? 'done' : '';
        return `<span class="quiz-rail__step"${tone ? ` data-tone="${tone}"` : ''}></span>`;
      })
      .join('')}</div>`;

  const optionRow = (option, choice) => {
    const picked = answers[index] === choice;
    const found = results?.[index];
    const correct = found ? choice === found.correct_index : false;
    const wrong = found ? picked && !correct : false;
    const tone = correct ? ' data-tone="right"' : wrong ? ' data-tone="wrong"' : picked ? ' data-tone="picked"' : '';
    const mark = correct
      ? icon('check', { size: 14 })
      : wrong
        ? icon('x', { size: 14 })
        : esc(LETTERS[choice] || String(choice + 1));
    return `<button type="button" class="quiz-option"${tone}${results ? ' disabled' : ''} data-quiz-option="${choice}" aria-pressed="${picked}"><span class="quiz-option__letter ds-data">${mark}</span><span class="quiz-option__text">${esc(option)}</span>${
      results && picked ? `<span class="ds-label quiz-option__mine">${esc(c.quizYourAnswer)}</span>` : ''
    }</button>`;
  };

  const evidencePanel = (found) => {
    if (!found) return '';
    // Written in the learner's support language: a set is served only in it.
    const explanation = found.explanation || '';
    const fragment = found.evidence_fragment || '';
    if (!explanation && !fragment) return '';
    const place = fragment && placeOfEvidence ? placeOfEvidence(fragment) : null;
    const where = Number.isInteger(place) && place >= 0
      ? fill(c.quizFromParagraph, { n: place + 1 })
      : fragment
        ? c.quizFromText
        : '';
    return `<div class="quiz-answer">${icon('info', { size: 20 })}<div>${
      explanation ? `<p lang="${esc(support || '')}">${esc(explanation)}</p>` : ''
    }${fragment ? `<blockquote>${esc(fragment)}</blockquote>` : ''}${
      where ? `<p class="ds-label quiz-answer__where">${esc(where)}</p>` : ''
    }${fragment ? `<button type="button" class="quiet" data-quiz-look="${esc(fragment)}">${esc(c.lookCloser)} ↗</button>` : ''}</div></div>`;
  };

  function paintStep() {
    if (!alive()) return;
    const question = questions[index];
    const found = results?.[index];
    const last = index === total - 1;
    const action = results
      ? last
        ? `<button type="button" class="primary" data-quiz-done>${esc(c.quizFinish)}</button>`
        : `<button type="button" class="primary" data-quiz-next>${esc(c.quizNext)}${icon('arrow-right', { size: 16 })}</button>`
      : last
        ? `<button type="button" class="primary" data-quiz-submit${answers[index] === null || sending ? ' disabled' : ''}>${esc(c.comprehensionCheck)}</button>`
        : `<button type="button" class="primary" data-quiz-next${answers[index] === null ? ' disabled' : ''}>${esc(c.quizNext)}${icon('arrow-right', { size: 16 })}</button>`;
    step.innerHTML = `<header class="quiz-bar"><button type="button" class="icon-button quiz-close" data-quiz-close aria-label="${esc(c.close || c.back || '')}">${icon('x', { size: 18 })}</button>${rail()}<span class="ds-data quiz-place">${esc(fill(c.quizPlace, { n: index + 1, t: total }))}</span></header><div class="quiz-head"><span class="ds-label quiz-kind">${esc(c.comprehension)}</span><span class="chip quiz-type">${esc(c.quizMultipleChoice)}</span></div><h3 class="quiz-question">${esc(question.question)}</h3><div class="quiz-options">${question.options
      .map(optionRow)
      .join('')}</div>${evidencePanel(found)}${
      results && last
        ? `<p class="quiz-score heading-with-hint">${esc(c.comprehensionScore)} ${results.filter((item) => item.correct).length}/${total}${hint({ text: c.comprehensionClaim })}</p>`
        : ''
    }<div class="quiz-actions">${action}</div>`;
    bindStep();
  }

  function bindStep() {
    step.querySelectorAll('[data-quiz-option]').forEach((button) => {
      button.onclick = () => {
        answers[index] = Number(button.dataset.quizOption);
        paintStep();
      };
    });
    step.querySelector('[data-quiz-next]')?.addEventListener('click', () => {
      index = Math.min(index + 1, total - 1);
      paintStep();
      step.scrollIntoView({ block: 'nearest' });
    });
    step.querySelector('[data-quiz-submit]')?.addEventListener('click', submit);
    step.querySelector('[data-quiz-done]')?.addEventListener('click', close);
    step.querySelector('[data-quiz-close]')?.addEventListener('click', close);
    step.querySelectorAll('[data-quiz-look]').forEach((button) => {
      button.onclick = () => {
        const fragment = button.dataset.quizLook;
        const context = onEvidence?.(fragment) || fragment;
        openUnderstanding(ctx, {
          origin: origin || null,
          selection: fragment,
          context,
          title: c.comprehension,
        });
      };
    });
  }

  function close() {
    step.hidden = true;
    invite.hidden = false;
    index = 0;
  }

  async function submit() {
    if (sending) return;
    sending = true;
    state.textContent = c.saving;
    paintStep();
    try {
      const scored = await ctx.mutate(() => submitAnswers(answers));
      if (!alive()) return;
      if (!Array.isArray(scored) || scored.length !== total)
        throw Error('Reading check unavailable');
      results = scored;
      state.textContent = '';
      index = 0;
      paintStep();
    } catch {
      if (alive()) state.textContent = c.comprehensionUnavailable;
    } finally {
      sending = false;
      if (alive() && !results) paintStep();
    }
  }

  invite.querySelector('[data-quiz-start]').onclick = () => {
    invite.hidden = true;
    step.hidden = false;
    index = 0;
    paintStep();
    step.scrollIntoView({ block: 'nearest' });
  };
}
