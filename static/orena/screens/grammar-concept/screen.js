/* Frame "Grammar Concept" (pinned design, frame 47 - canonical per D-099; frame 23 is not built;
   route "gconcept", a learning workspace, Design Contract rule 49).

   Data: one point of the grammar content contract, through the seam product/grammar-source.js
   (D-100). No API exists yet, so every point is "not found" and the screen draws the design's
   empty state under its own header; an old R5 id resolves through the catalogue's `aliases` and
   the address is replaced (contract §9). model.js says what each part draws from which field.

   "Try it yourself" (D-100 point 3): drawn as frame 47 draws it - prompt, one-line input, Check,
   and the result line under it. Until the contract has a rule for recognising the target pattern,
   the result line never says the pattern was used and nothing is recorded as evidence: it shows
   the contract's `sample` sentence, the one thing that can honestly be said. Finishing the quiz
   records the point as completed through the Grammar Store's progress API with the answers in
   `quick_practice` order; the server grades them from the published key, and the screen draws only what
   the frame draws (score, Retry). A failed save says so in a toast and is sent again on the next finish. */
import { html, mount, raw } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { pageHeader } from '../../kit/components.js';
import { langAttr, langSpan } from '../../kit/lang.js';
import { emptyMarkup } from '../../kit/states.js';
import { shellCopy as shell } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { t } from './copy.js';
import { grammarCatalog, grammarPoint, recordGrammarCompletion } from '../../product/grammar-source.js';
import { toast } from '../../kit/toast.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { conceptView, sectionsOf } from './model.js';
import { hanziMarkup } from '../grammar/hanzi.js';

const HEADINGS = { timeline: 'timeline', word_order: 'wordOrder', morphology: 'wordForm' };

function eyebrow(text) {
  return html`<div class="s-gc__eyebrow">${text}</div>`;
}

/* Target-language text, with its pinyin stack when it is Chinese. */
function material(text, pinyin, lang) {
  return lang === 'zh' ? hanziMarkup(text, pinyin) : text;
}

const joiner = (glyph) => html`<span class="s-gc__join" aria-hidden="true">${glyph}</span>`;

function joined(items, glyph = '+') {
  return items.map((item, i) => (i ? html`${joiner(glyph)}${item}` : item));
}

function chipsMarkup(cells, lang) {
  return html`<div class="s-gc__chips" lang="${langAttr(lang)}">${joined(
    cells.map((cell) => html`<span class="${`s-gc__chip s-gc__chip--${cell.bucket}`}">${cell.text}</span>`),
  )}</div>`;
}

function patternMarkup(cells, lang) {
  return html`${eyebrow(t('pattern'))}${chipsMarkup(cells, lang)}`;
}

/* pattern.variants: the negative / question forms the point declares, each under its own small label. */
function variantsMarkup(variants, lang) {
  return html`${eyebrow(t('variants'))}<div class="s-gc__variants">${variants.map(
    (variant) => html`<div class="s-gc__variant"><span class="s-gc__vlabel">${t(`form_${variant.form}`)}</span>${chipsMarkup(variant.cells, lang)}</div>`,
  )}</div>`;
}

function timelineMarkup(ill) {
  const at = (n) => `left:${n}%`;
  return html`<div class="s-gc__tl">
      <div class="s-gc__tlAxis"></div>
      ${ill.bars.map((bar) => html`<div class="s-gc__tlBar" style="${`left:${bar.from}%;width:${bar.to - bar.from}%`}"></div>`)}
      ${ill.dots.map((n) => html`<span class="s-gc__tlDot" style="${at(n)}"></span>`)}
      ${ill.marks.map((mark) => html`<span class="s-gc__tlMark" style="${at(mark.at)}">${t(mark.key)}</span>`)}
      <span class="s-gc__tlMark" style="${at(ill.now)}">${t('markNow')}</span>
    </div>
    <div class="s-gc__tlCaption">${ill.relevance || t(ill.caption)}</div>`;
}

function boxesMarkup(ill, lang) {
  return html`<div class="s-gc__boxes">${joined(
    ill.boxes.map(
      (box) => html`<div class="s-gc__box"><span class="${`s-gc__boxChip s-gc__boxChip--${box.bucket}`}" lang="${langAttr(lang)}">${box.text}</span>${
        box.label ? html`<span class="s-gc__boxLabel">${box.label}</span>` : ''
      }</div>`,
    ),
  )}</div>`;
}

function morphologyMarkup(ill, lang) {
  return ill.rows.map(
    (row) => html`<div class="s-gc__morph">
      <div class="s-gc__morphRow" lang="${langAttr(lang)}">
        <span class="s-gc__boxChip s-gc__boxChip--k">${material(row.base, row.basePinyin, lang)}</span>
        ${row.affix ? html`${joiner('+')}<span class="s-gc__boxChip s-gc__boxChip--a">${row.affix}</span>` : ''}
        ${joiner('→')}
        <span class="s-gc__boxChip s-gc__boxChip--b">${material(row.result, row.resultPinyin, lang)}</span>
      </div>
      ${row.note ? html`<div class="s-gc__boxLabel">${row.note}</div>` : ''}
    </div>`,
  );
}

function illustrationMarkup(ill, lang) {
  const body = ill.kind === 'timeline' ? timelineMarkup(ill) : ill.kind === 'word_order' ? boxesMarkup(ill, lang) : morphologyMarkup(ill, lang);
  return html`${eyebrow(t(HEADINGS[ill.kind]))}<div class="s-gc__ill">${body}</div>`;
}

function exampleMarkup(example, lang) {
  return html`<div class="s-gc__example">
    <div class="s-gc__exText" lang="${langAttr(lang)}">${example.parts.map((part) => {
      const text = material(part.text, part.pinyin, lang);
      return part.bucket ? html`<span class="${`s-gc__hl s-gc__hl--${part.bucket}`}">${text}</span>` : text;
    })}</div>
    ${example.translation ? html`<div class="s-gc__exTr">${example.translation}</div>` : ''}
    ${example.annotation ? html`<div class="s-gc__exNote">${example.annotation}</div>` : ''}
  </div>`;
}

function mistakeMarkup(mistake, lang) {
  return html`<div class="s-gc__mistake">
    <div class="s-gc__mline"><span class="s-gc__glyph s-gc__glyph--bad" aria-hidden="true">✕</span><s class="s-gc__mbad" lang="${langAttr(lang)}">${material(mistake.wrong, mistake.wrongPinyin, lang)}</s></div>
    <div class="s-gc__mline s-gc__mline--good"><span class="s-gc__glyph s-gc__glyph--good" aria-hidden="true">✓</span><span lang="${langAttr(lang)}">${material(mistake.right, mistake.rightPinyin, lang)}</span></div>
    ${mistake.reason ? html`<div class="s-gc__mwhy">${t('why')} ${mistake.reason}</div>` : ''}
  </div>`;
}

function compareSide(label, example, pinyin, meaning, lang, tone) {
  return html`<div class="${`s-gc__cside s-gc__cside--${tone}`}">
    ${label ? html`<div class="s-gc__clabel" lang="${langAttr(lang)}">${label}</div>` : ''}
    ${example ? html`<div class="s-gc__cex" lang="${langAttr(lang)}">${material(example, pinyin, lang)}</div>` : ''}
    ${meaning ? html`<div class="s-gc__cmean">${meaning}</div>` : ''}
  </div>`;
}

/* compare[]: this point against a neighbouring one, side by side where there is room. `titles` maps a
   point id to its native title when the catalogue could be read; an unresolved side carries no label. */
function compareMarkup(entries, titles, ownTitle, lang) {
  return html`<div class="s-gc__compare">${entries.map((entry) => {
    const other = titles.get(entry.withId) || '';
    return html`<div class="s-gc__cpair">${compareSide(ownTitle, entry.thisExample, entry.thisExamplePinyin, entry.thisMeaning, lang, 'this')}${compareSide(other, entry.otherExample, entry.otherExamplePinyin, entry.otherMeaning, lang, 'other')}</div>`;
  })}</div>`;
}

function optionMarkup(option, index, pick, question, lang) {
  const answered = pick != null;
  const state = answered && index === question.answer ? 'ok' : answered && index === pick ? 'bad' : '';
  const glyph = state === 'ok' ? '✓' : state === 'bad' ? '✕' : String.fromCharCode(65 + index);
  return html`<button type="button" class="${`s-gc__opt${state ? ` s-gc__opt--${state}` : ''}`}" data-pick="${index}"${answered ? raw(' disabled') : ''}><span class="s-gc__optGlyph">${glyph}</span><span class="s-gc__optText" lang="${langAttr(lang)}">${material(option.text, option.pinyin, lang)}</span></button>`;
}

function quizMarkup(quiz, state, lang) {
  const done = state.qi >= quiz.length;
  const head = html`<div class="s-gc__quizhead"><h2 class="s-gc__title">${t('quiz')}</h2><span class="s-gc__quizprog">${
    done ? t('quizDone') : t('quizProgress', { n: state.qi + 1, total: quiz.length })
  }</span></div>`;
  if (done) {
    const score = quiz.filter((question, i) => state.picks[i] === question.answer).length;
    return html`${head}<div class="s-gc__score">${t('quizScore', { score, total: quiz.length })}</div>
      <button type="button" class="o-btn o-btn--secondary s-gc__retry" data-quiz-retry>${t('retryQuiz')}</button>`;
  }
  const question = quiz[state.qi];
  const pick = state.picks[state.qi];
  return html`${head}
    <div class="s-gc__qprompt" lang="${langAttr(lang)}">${material(question.q, question.qPinyin, lang)}</div>
    <div class="s-gc__options">${question.options.map((option, i) => optionMarkup(option, i, pick, question, lang))}</div>
    ${
      pick != null
        ? html`${question.explain ? html`<div class="s-gc__why"><b>${t('why')}</b> ${question.explain}</div>` : ''}<button type="button" class="o-btn o-btn--primary s-gc__cta s-gc__next" data-quiz-next>${
            state.qi < quiz.length - 1 ? t('next') : t('finish')
          }</button>`
        : ''
    }`;
}

function tryMarkup(tryIt, lang) {
  return html`<h2 class="s-gc__title">${t('tryIt')}</h2>
    <div class="s-gc__tryPrompt">${tryIt.prompt}</div>
    <div class="s-gc__tryRow">
      <input class="s-gc__tryInput" data-try-input lang="${langAttr(lang)}" placeholder="${tryIt.placeholder || t('tryPlaceholder')}" aria-label="${tryIt.prompt}">
      <button type="button" class="o-btn o-btn--primary s-gc__cta" data-try-check>${t('check')}</button>
    </div>
    <div data-try-result></div>`;
}

/* The cards the learner reads, in learning order (model.js sectionsOf). The overview card holds the summary
   and when to use; the pattern card the formula, its illustration and its variants. A card with no data is
   not drawn. `quiz` and `tryIt` are given by the caller: live and interactive on the learner's page, static
   in Admin's preview. */
function sectionCards(view, lang, { titles = new Map(), quiz = null, tryIt = null } = {}) {
  const { header } = view;
  const body = {
    overview: () => html`${header.summary ? html`<div class="s-gc__summary">${header.summary}</div>` : ''}${
      view.whenToUse.length ? html`${eyebrow(t('whenToUse'))}<ul class="s-gc__when">${view.whenToUse.map((line) => html`<li>${line}</li>`)}</ul>` : ''
    }`,
    pattern: () => html`${view.pattern.length ? patternMarkup(view.pattern, lang) : ''}${view.illustration ? illustrationMarkup(view.illustration, lang) : ''}${
      view.variants.length ? variantsMarkup(view.variants, lang) : ''
    }`,
    examples: () => html`${eyebrow(t('examples'))}<div class="s-gc__examples">${view.examples.map((example) => exampleMarkup(example, lang))}</div>`,
    mistakes: () => html`${eyebrow(t('mistake'))}<div class="s-gc__mistakes">${view.mistakes.map((mistake) => mistakeMarkup(mistake, lang))}</div>`,
    compare: () => html`${eyebrow(t('compare'))}${compareMarkup(view.compare, titles, header.title, lang)}`,
  };
  return sectionsOf(view).map((key) => {
    if (key === 'quiz') return quiz ? quiz() : '';
    if (key === 'tryIt') return tryIt ? tryIt() : '';
    return html`<section class="${`o-card o-card--24 s-gc__card s-gc__card--${key}`}">${body[key]()}</section>`;
  });
}

/* The learner's page for one point, read-only, for Admin's review (proposals/ADMIN_GRAMMAR_UI.md G4): the same header,
   card and parts the learner meets, every quiz question in its answered state with the right option marked and its
   explanation, and the Try-it prompt. Nothing here is interactive. */
export function conceptPreviewMarkup(point, { support = 'en', native = '' } = {}) {
  const view = conceptView(point, { support, native });
  const { header } = view;
  const lang = header.lang;
  const quiz = () => html`<section class="o-card o-card--24 s-gc__card"><div class="s-gc__quizhead"><h2 class="s-gc__title">${t('quiz')}</h2><span class="s-gc__quizprog">${view.quiz.length}</span></div>
        ${view.quiz.map((question) => html`<div class="s-gc__previewQ">
          <div class="s-gc__qprompt" lang="${langAttr(lang)}">${material(question.q, question.qPinyin, lang)}</div>
          <div class="s-gc__options">${question.options.map((option, i) => optionMarkup(option, i, question.answer, question, lang))}</div>
          ${question.explain ? html`<div class="s-gc__why"><b>${t('why')}</b> ${question.explain}</div>` : ''}
        </div>`)}</section>`;
  const tryIt = () => html`<section class="o-card o-card--24 s-gc__card"><h2 class="s-gc__title">${t('tryIt')}</h2><div class="s-gc__tryPrompt">${view.tryIt.prompt}</div>${
    view.tryIt.sample ? html`<div class="s-gc__tryResult"><span>${t('sample')}</span> <span lang="${langAttr(lang)}">${material(view.tryIt.sample, view.tryIt.samplePinyin, lang)}</span></div>` : ''}</section>`;
  return html`<div class="s-gc s-gc--preview">
    <div class="s-gc__head">${pageHeader({
      title: langSpan(material(header.title, header.titlePinyin, lang), lang),
      meta: [shell('grammar'), header.level, header.sub].filter(Boolean).join(' · '),
      compact: true,
    })}</div>
    <div class="s-gc__inner">${sectionCards(view, lang, { quiz, tryIt })}</div>
  </div>`;
}

function notFound(element, ctx) {
  mount(
    element,
    html`<div class="s-gc">
      <div class="s-gc__head">${pageHeader({ back: { label: shell('back'), dataset: { back: '1' } }, title: shell('grammar'), compact: true })}</div>
      ${emptyMarkup({ text: t('notFound'), iconName: 'inbox' })}
    </div>`,
  );
  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
}

export default async function grammarConcept(element, ctx) {
  await useStyles('screens/grammar-concept/grammar-concept.css');
  const context = ctx.context;
  const found = await grammarPoint(ctx.params.id, { targetLang: context.language === 'zh' ? 'zh' : 'en' });
  if (!ctx.isCurrent()) return;
  if (found.redirect) {
    ctx.replace(ctx.href('gconcept', { id: found.redirect }));
    return;
  }
  if (!found.point) {
    notFound(element, ctx);
    return;
  }

  const view = conceptView(found.point, { support: languages().support, native: context.profile?.native_language });
  const { header } = view;
  const lang = header.lang;
  ctx.setCrumb(header.title);

  /* compare[] names its neighbour by id; the catalogue says what it is called. A catalogue that cannot be read
     leaves that side unlabelled - nothing is guessed. */
  const titles = new Map();
  if (view.compare.length) {
    try {
      (await grammarCatalog(lang)).forEach((row) => titles.set(row.id, String(row.header?.native_title || row.native_title || '')));
    } catch {
      /* unlabelled */
    }
    if (!ctx.isCurrent()) return;
  }
  const cards = sectionCards(view, lang, {
    titles,
    quiz: () => html`<section class="o-card o-card--24 s-gc__card" data-quiz></section>`,
    tryIt: () => html`<section class="o-card o-card--24 s-gc__card" data-try></section>`,
  });

  mount(
    element,
    html`<div class="s-gc">
      <div class="s-gc__head">${pageHeader({
        back: { label: shell('back'), dataset: { back: '1' } },
        title: langSpan(material(header.title, header.titlePinyin, lang), lang),
        meta: [shell('grammar'), header.level, header.sub].filter(Boolean).join(' · '),
        compact: true,
        actions: [html`<button type="button" class="s-gc__ask" data-ask>${t('askOrena')}</button>`],
      })}</div>
      <div class="s-gc__scroll" data-scroll-region>
        <div class="s-gc__inner">
          ${cards}
        </div>
      </div>
    </div>`,
  );

  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
  element.querySelector('[data-ask]')?.addEventListener('click', () =>
    askOrena({
      surface: 'grammar_concept',
      activity_type: 'grammar',
      content_id: view.id,
      selected_item: { type: 'grammar_point', id: view.id, text: header.title },
    }),
  );

  const quizHolder = element.querySelector('[data-quiz]');
  if (quizHolder) {
    const state = { qi: 0, picks: new Array(view.quiz.length).fill(null) };
    const renderQuiz = () => mount(quizHolder, quizMarkup(view.quiz, state, lang));
    const total = Array.isArray(found.point.quick_practice) ? found.point.quick_practice.length : 0;
    const record = () => {
      const answers = new Array(total).fill(null);
      view.quiz.forEach((question, i) => {
        if (question.index < total) answers[question.index] = state.picks[i];
      });
      recordGrammarCompletion(view.id, answers).catch(() => {
        if (ctx.isCurrent()) toast(t('saveError'));
      });
    };
    quizHolder.addEventListener('click', (event) => {
      const pick = event.target.closest('[data-pick]');
      if (pick && state.picks[state.qi] == null) {
        state.picks[state.qi] = Number(pick.dataset.pick);
        renderQuiz();
      } else if (event.target.closest('[data-quiz-next]')) {
        state.qi += 1;
        if (state.qi >= view.quiz.length) record();
        renderQuiz();
      } else if (event.target.closest('[data-quiz-retry]')) {
        state.qi = 0;
        state.picks.fill(null);
        renderQuiz();
      }
    });
    renderQuiz();
  }

  const tryHolder = element.querySelector('[data-try]');
  if (tryHolder) {
    const tryIt = view.tryIt;
    mount(tryHolder, tryMarkup(tryIt, lang));
    const input = tryHolder.querySelector('[data-try-input]');
    const result = tryHolder.querySelector('[data-try-result]');
    const check = () => {
      if (!input.value.trim() || !tryIt.sample) return;
      mount(result, html`<div class="s-gc__tryResult"><span>${t('sample')}</span> <span lang="${langAttr(lang)}">${material(tryIt.sample, tryIt.samplePinyin, lang)}</span></div>`);
    };
    input.addEventListener('input', () => mount(result, ''));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') check();
    });
    tryHolder.querySelector('[data-try-check]').addEventListener('click', check);
  }
}
