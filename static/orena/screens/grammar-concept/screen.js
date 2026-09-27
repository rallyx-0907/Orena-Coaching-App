/* Frame "Grammar Concept" (pinned design, frame 47 - the generic template every real concept
   route reaches; route "gconcept", a learning workspace, Design Contract rule 49).

   Rule 40 / rule 44 notes (see model.js's header comment for the data-shaping decisions):
   - the "Try it yourself" card's button asks Orena instead of grading with a fabricated regex -
     the backend has no correctness judgement for free text (SCRATCH/inventory/C6, §3.2);
   - a block type frame 47 draws no visual for degrades to a generic chip/row rendering rather
     than a bespoke widget;
   - completion (`POST /api/library/grammar/{id}/complete`) fires once the learner finishes the
     quiz - the closest drawn signal to "did something evidencing engagement" this frame has (no
     control on 47 calls it explicitly); recorded as a decision, not left unresolved. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { pageHeader } from '../../kit/components.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { t } from './copy.js';
import { api } from '../../infrastructure/api.js';
import { supportLanguage } from '../../product/languages.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { pickLocale, primaryPattern, examplesOf, mistakeOf, quizQuestions, personalPractice, headerMeta } from './model.js';

function patternMarkup(pattern) {
  const eyebrow = html`<div class="s-gc__eyebrow">${t('pattern')}</div>`;
  if (pattern.kind === 'chips') {
    return html`${eyebrow}<div class="s-gc__chips">${pattern.parts.map(
      (part) => html`<span class="${`s-gc__chip s-gc__chip--${part.role}`}" title="${part.label}">${part.text}</span>`,
    )}</div>`;
  }
  if (pattern.kind === 'transform') {
    return html`${eyebrow}<div class="s-gc__chips">
      <span class="s-gc__chip s-gc__chip--k">${pattern.from}</span>
      <span class="s-gc__arrow" aria-hidden="true">${raw(icon('arrow-right', { size: 16 }))}</span>
      <span class="s-gc__chip s-gc__chip--b">${pattern.to}</span>
    </div>`;
  }
  return html`${eyebrow}${pattern.rows.map(
    (row) => html`<div class="s-gc__row">${row.label ? html`<div class="s-gc__rowLabel">${row.label}</div>` : ''}<div>${row.text}</div>${
      row.note ? html`<div class="s-gc__rowNote">${row.note}</div>` : ''
    }</div>`,
  )}`;
}

function exampleMarkup(example) {
  return html`<div class="s-gc__example">${example.text}${example.translation ? html`<div class="s-gc__exampleTr">${example.translation}</div>` : ''}</div>`;
}

function mistakeMarkup(mistake) {
  return html`<div class="s-gc__eyebrow">${t('mistake')}</div>
  <div class="s-gc__mistake">
    <div class="s-gc__mline"><span class="s-gc__glyph s-gc__glyph--bad">✕</span><span class="s-gc__mtext--bad">${mistake.incorrect}</span></div>
    <div class="s-gc__mline"><span class="s-gc__glyph s-gc__glyph--good">✓</span><span class="s-gc__mtext--good">${mistake.correct}</span></div>
    ${mistake.why ? html`<div class="s-gc__mwhy">${mistake.why}</div>` : ''}
  </div>`;
}

function optionMarkup(option, index, pick, answered, question) {
  const isPicked = pick === index;
  const isCorrect = option === question.answer;
  let cls = 's-gc__opt';
  let glyph = String.fromCharCode(65 + index);
  if (answered && isCorrect) {
    cls += ' s-gc__opt--correct';
    glyph = '✓';
  } else if (answered && isPicked) {
    cls += ' s-gc__opt--wrong';
    glyph = '✕';
  }
  return html`<button type="button" class="${cls}" data-pick="${index}"${answered ? raw(' disabled') : ''}><span class="s-gc__optGlyph">${glyph}</span>${option}</button>`;
}

function quizMarkup(quiz, state) {
  if (state.done) {
    const score = quiz.reduce((sum, question, i) => sum + (question.options[state.picks[i]] === question.answer ? 1 : 0), 0);
    return html`<div class="s-gc__quizhead"><h2 class="s-gc__title">${t('quiz')}</h2></div>
      <div class="s-gc__qdone">
        <div class="s-gc__score">${t('quizScore', { score, total: quiz.length })}</div>
        <button type="button" class="o-btn o-btn--secondary" data-quiz-retry>${t('retryQuiz')}</button>
      </div>`;
  }
  const question = quiz[state.qi];
  const pick = state.picks[state.qi];
  const answered = pick != null;
  return html`<div class="s-gc__quizhead"><h2 class="s-gc__title">${t('quiz')}</h2><span class="s-gc__quizprog">${t('quizProgress', { n: state.qi + 1, total: quiz.length })}</span></div>
    <div class="s-gc__qprompt">${question.prompt}</div>
    <div class="s-gc__options">${question.options.map((option, i) => optionMarkup(option, i, pick, answered, question))}</div>
    ${
      answered
        ? html`<div class="s-gc__why">${question.explanation}</div><div class="s-gc__quizfoot"><button type="button" class="o-btn o-btn--primary s-gc__cta" data-quiz-next>${
            state.qi < quiz.length - 1 ? t('next') : t('finish')
          }</button></div>`
        : ''
    }`;
}

function tryMarkup(tryIt) {
  return html`<h2 class="s-gc__title">${t('tryIt')}</h2>
    ${tryIt.prompt ? html`<div class="s-gc__tryPrompt">${tryIt.prompt}</div>` : ''}
    <div class="s-gc__tryRow"><textarea class="s-gc__tryInput" data-try-input placeholder="${tryIt.placeholder}"></textarea></div>
    <div class="s-gc__quizfoot"><button type="button" class="o-btn o-btn--primary s-gc__cta" data-try-ask>${t('checkWithOrena')}</button></div>`;
}

export default async function grammarConcept(element, ctx) {
  await useStyles('screens/grammar-concept/grammar-concept.css');
  const context = ctx.context;
  const support = supportLanguage(context.profile);
  const lesson = await api.grammarLesson(ctx.params.id);
  if (!ctx.isCurrent()) return;
  ctx.setCrumb(lesson.title);

  const pattern = primaryPattern(lesson, support);
  const examples = examplesOf(lesson, support);
  const mistake = mistakeOf(lesson, support);
  const quiz = quizQuestions(lesson, support);
  const tryIt = personalPractice(lesson, support);
  const meta = headerMeta(lesson);
  const summary = pickLocale(lesson?.learning_model?.meaning?.summary, support);

  mount(
    element,
    html`<div class="s-gc">
      <div class="s-gc__head">${pageHeader({
        back: { label: shell('back'), dataset: { back: '1' } },
        title: lesson.title,
        meta: [shell('grammar'), meta.level, meta.family].filter(Boolean).join(' · '),
        compact: true,
        actions: [html`<button type="button" class="s-gc__ask" data-ask>${t('askOrena')}</button>`],
      })}</div>
      <div class="s-gc__scroll" data-scroll-region>
        <div class="s-gc__inner">
          <div class="o-card o-card--24 s-gc__card">
            ${summary ? html`<div class="s-gc__summary">${summary}</div>` : ''}
            ${pattern ? patternMarkup(pattern) : ''}
            ${examples.length ? html`<div class="s-gc__eyebrow">${t('examples')}</div>${examples.map(exampleMarkup)}` : ''}
            ${mistake ? mistakeMarkup(mistake) : ''}
          </div>
          ${quiz.length ? html`<div class="o-card o-card--24 s-gc__card" data-quiz></div>` : ''}
          ${tryIt ? html`<div class="o-card o-card--24 s-gc__card" data-try></div>` : ''}
        </div>
      </div>
    </div>`,
  );

  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
  element.querySelector('[data-ask]')?.addEventListener('click', () =>
    askOrena({
      surface: 'grammar_concept',
      activity_type: 'grammar',
      content_id: lesson.id,
      selected_item: { type: 'grammar_point', id: lesson.id, text: lesson.title },
    }),
  );

  const quizHolder = element.querySelector('[data-quiz]');
  if (quizHolder && quiz.length) {
    const state = { qi: 0, picks: new Array(quiz.length).fill(null), done: false };
    const renderQuiz = () => {
      mount(quizHolder, quizMarkup(quiz, state));
      if (state.done) {
        quizHolder.querySelector('[data-quiz-retry]')?.addEventListener('click', () => {
          state.qi = 0;
          state.picks.fill(null);
          state.done = false;
          renderQuiz();
        });
        return;
      }
      if (state.picks[state.qi] == null) {
        quizHolder.querySelectorAll('[data-pick]').forEach((button) => {
          button.addEventListener('click', () => {
            state.picks[state.qi] = Number(button.dataset.pick);
            renderQuiz();
          });
        });
      } else {
        quizHolder.querySelector('[data-quiz-next]')?.addEventListener('click', () => {
          if (state.qi < quiz.length - 1) {
            state.qi += 1;
          } else {
            state.done = true;
            api.completeGrammar(lesson.id).catch(() => {});
          }
          renderQuiz();
        });
      }
    };
    renderQuiz();
  }

  const tryHolder = element.querySelector('[data-try]');
  if (tryHolder && tryIt) {
    mount(tryHolder, tryMarkup(tryIt));
    tryHolder.querySelector('[data-try-ask]')?.addEventListener('click', () => {
      const text = tryHolder.querySelector('[data-try-input]')?.value.trim() || '';
      askOrena({
        surface: 'grammar_concept',
        activity_type: 'grammar',
        content_id: lesson.id,
        selected_item: text ? { type: 'sentence', text } : { type: 'grammar_point', id: lesson.id, text: lesson.title },
      });
    });
  }
}
