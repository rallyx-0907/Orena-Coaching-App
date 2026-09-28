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
import { langAttr, langSpan } from '../../kit/lang.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { t } from './copy.js';
import { api } from '../../infrastructure/api.js';
import { supportLanguage } from '../../product/languages.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { pickLocale, primaryPattern, examplesOf, mistakeOf, quizQuestions, personalPractice, headerMeta } from './model.js';

/* languages-5 / finding A: `pattern.parts[].text`/`.from`/`.to` are the concept's own real
   target-language content - a pattern word, a transformed sentence (model.js's own header comment:
   "a plain string is target-language content") - marked with the learner's active learning
   language, the one this whole concept is written in (`ctx.context.language`, the third source
   kit/lang.js's own doc comment names: no per-field language comes back from GET /api/library/
   grammar/{id}, but every field this screen shows is definitionally in that one language). `part.
   label`/the chip's own `title` attribute is support-layer prose (pickLocale), never marked. */
function patternMarkup(pattern, lang) {
  const eyebrow = html`<div class="s-gc__eyebrow">${t('pattern')}</div>`;
  if (pattern.kind === 'chips') {
    return html`${eyebrow}<div class="s-gc__chips">${pattern.parts.map(
      (part) => html`<span class="${`s-gc__chip s-gc__chip--${part.role}`}" lang="${langAttr(lang)}" title="${part.label}">${part.text}</span>`,
    )}</div>`;
  }
  if (pattern.kind === 'transform') {
    return html`${eyebrow}<div class="s-gc__chips">
      <span class="s-gc__chip s-gc__chip--k" lang="${langAttr(lang)}">${pattern.from}</span>
      <span class="s-gc__arrow" aria-hidden="true">${raw(icon('arrow-right', { size: 16 }))}</span>
      <span class="s-gc__chip s-gc__chip--b" lang="${langAttr(lang)}">${pattern.to}</span>
    </div>`;
  }
  // `kind: 'rows'` is the generic fallback for a block type frame 47 draws no chip shape for
  // (model.js's own comment) - its `text`/`label` may be target-language content or support prose
  // depending on the block, a distinction the pure mapping does not carry through, so this shape
  // is left unmarked rather than guessed at (kit/lang.js: no `lang` is safer than a wrong one).
  //
  // `text` is conditional, matching `label`/`note`: a `timeline` block's `events[]` never carries
  // a `text` field (writing_coach/grammar_learning_model.py `_validate_timeline` - only
  // `label`/`position`/`note`), so `pattern.rows[].text` is always `''` for that block type.
  // Rendering it unconditionally left a permanently empty middle line on every timeline row (real,
  // reachable: `a2-present-perfect-vs-past-simple`'s primary pattern block, per
  // capabilities/grammar-pedagogy.js's `primaryModelType` for the `temporal_aspect` archetype).
  // Other row-shaped blocks (`contrast`, `scene`) always carry a real `text`, so this changes
  // nothing for them - only the row's designated main-text slot, always empty before, is now
  // honestly left out instead of drawn empty (rule 40).
  return html`${eyebrow}${pattern.rows.map(
    (row) => html`<div class="s-gc__row">${row.label ? html`<div class="s-gc__rowLabel">${row.label}</div>` : ''}${
      row.text ? html`<div>${row.text}</div>` : ''
    }${row.note ? html`<div class="s-gc__rowNote">${row.note}</div>` : ''}</div>`,
  )}`;
}

function exampleMarkup(example, lang) {
  // `lang` sits on a span around the target-language sentence only, not the row - the translation
  // line right below it is support-layer prose (D-079: Vietnamese today, per model.js's own
  // comment), a different language the outer element must not also claim.
  return html`<div class="s-gc__example"><span lang="${langAttr(lang)}">${example.text}</span>${example.translation ? html`<div class="s-gc__exampleTr">${example.translation}</div>` : ''}</div>`;
}

function mistakeMarkup(mistake, lang) {
  return html`<div class="s-gc__eyebrow">${t('mistake')}</div>
  <div class="s-gc__mistake">
    <div class="s-gc__mline"><span class="s-gc__glyph s-gc__glyph--bad">✕</span><span class="s-gc__mtext--bad" lang="${langAttr(lang)}">${mistake.incorrect}</span></div>
    <div class="s-gc__mline"><span class="s-gc__glyph s-gc__glyph--good">✓</span><span class="s-gc__mtext--good" lang="${langAttr(lang)}">${mistake.correct}</span></div>
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
  // languages-5 / finding A: the active learning language this whole concept is written in - the
  // pattern/example/mistake target-language text is genuinely in it for both tracks (N-33's own
  // finding: "the raw Chinese example sentences...are genuinely theirs"). The lesson *title* is a
  // narrower case (N-33/N-20): the Chinese/HSK track's own titles are a Vietnamese-only content
  // gap, not genuinely Chinese, so only the English track's title is marked.
  const language = context.language === 'zh' ? 'zh' : 'en';
  const titleLang = language === 'zh' ? '' : 'en';

  mount(
    element,
    html`<div class="s-gc">
      <div class="s-gc__head">${pageHeader({
        back: { label: shell('back'), dataset: { back: '1' } },
        title: langSpan(lesson.title, titleLang),
        meta: [shell('grammar'), meta.level, meta.family].filter(Boolean).join(' · '),
        compact: true,
        actions: [html`<button type="button" class="s-gc__ask" data-ask>${t('askOrena')}</button>`],
      })}</div>
      <div class="s-gc__scroll" data-scroll-region>
        <div class="s-gc__inner">
          <div class="o-card o-card--24 s-gc__card">
            ${summary ? html`<div class="s-gc__summary">${summary}</div>` : ''}
            ${pattern ? patternMarkup(pattern, language) : ''}
            ${examples.length ? html`<div class="s-gc__eyebrow">${t('examples')}</div>${examples.map((example) => exampleMarkup(example, language))}` : ''}
            ${mistake ? mistakeMarkup(mistake, language) : ''}
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
