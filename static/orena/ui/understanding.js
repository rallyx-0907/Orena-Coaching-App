import { esc, dialog, focusRegion } from './html.js';
import { link } from '../product/intent.js';
import { progressReporter, savedLanguageLink } from './patterns.js';

/* One contextual explanation surface for every capability. Reading opens it on
   a highlight, Listening on a transcript selection, Writing on a correction,
   Practice on the line being worked. They all pass the same three things - the
   selection, the context it came from, and what the learner wants to know - so
   an explanation is never a lookup detached from where it was needed.

   The selection and its context stay on screen through every follow-up. Going
   deeper must not cost the learner the thing they were looking at. */

// The product's vocabulary for what kind of usage something is. "Wrong" hides
// six different things a learner needs to tell apart.
export const JUDGEMENT_KEYS = [
  'natural',
  'possible_but_unnatural',
  'contextually_inappropriate',
  'wrong_for_intended_meaning',
  'register_mismatch',
  'uncommon_but_legitimate',
  'grammatically_impossible',
];

export function judgementLabel(c, judgement) {
  return c[`judge_${judgement}`] || '';
}

function examplesBlock(c, result) {
  const good = result.examples || [];
  const bad = result.counter_examples || [];
  if (!good.length && !bad.length) return '';
  return `<div class="understanding-examples">${
    good.length
      ? `<section><h3>${esc(c.usedWell)}</h3>${good
          .map(
            (x) =>
              `<blockquote>${esc(x.text)}${x.note ? `<small>${esc(x.note)}</small>` : ''}</blockquote>`,
          )
          .join('')}</section>`
      : ''
  }${
    bad.length
      ? `<section><h3>${esc(c.easilyMisused)}</h3>${bad
          .map(
            (x) =>
              `<blockquote class="counter">${esc(x.text)}<small><b>${esc(judgementLabel(c, x.judgement))}</b>${x.note ? ` · ${esc(x.note)}` : ''}</small></blockquote>`,
          )
          .join('')}</section>`
      : ''
  }</div>`;
}

function explanationBlock(c, result) {
  const judgement = judgementLabel(c, result.judgement);
  return `${result.question ? `<p class="understanding-question">${esc(result.question)}</p>` : ''}${
    judgement && result.judgement !== 'natural'
      ? `<p class="judgement" data-judgement="${esc(result.judgement)}">${esc(judgement)}</p>`
      : ''
  }${result.natural_translation ? `<p class="understanding-meaning">${esc(result.natural_translation)}</p>` : ''}${
    result.summary ? `<p>${esc(result.summary)}</p>` : ''
  }${result.judgement_reason ? `<p>${esc(result.judgement_reason)}</p>` : ''}${
    result.register ? `<p class="meta">${esc(c.registerLabel)}: ${esc(result.register)}</p>` : ''
  }${
    (result.grammar_notes || []).length
      ? `<ul class="understanding-notes">${result.grammar_notes.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
      : ''
  }${
    (result.vocabulary || []).length
      ? `<dl class="understanding-vocab">${result.vocabulary
          .map(
            (x) =>
              `<dt>${esc(x.fragment)}${x.pronunciation ? ` <small>${esc(x.pronunciation)}</small>` : ''}</dt><dd>${esc(x.meaning)}${x.pos ? ` <small>${esc(x.pos)}</small>` : ''}</dd>`,
          )
          .join('')}</dl>`
      : ''
  }${result.usage_note ? `<p>${esc(result.usage_note)}</p>` : ''}${examplesBlock(c, result)}`;
}

/* `selection` is the language in question, `context` the text it came from.
   The API refuses a selection its context does not contain, which is the same
   rule the learner sees: an explanation is always about something on screen. */
/* `origin` is how a kept phrase finds its way home: the encounter it came from
   and why the learner was there. Every capability that opens this surface knows
   both; without them a saved word becomes an anonymous card. */
export function openUnderstanding(
  ctx,
  { selection, context, title, question = '', origin = null },
) {
  const { c, api, language, support } = ctx;
  const source = String(selection || '').trim();
  const passage = String(context || source).trim();
  if (!source) return null;

  const sheet = dialog({
    title: c.inspect,
    body: `<div class="understanding">
      <section class="understanding-source">
        <small>${esc(title || c.sourceContext)}</small>
        <blockquote lang="${esc(language)}">${esc(source)}</blockquote>
        ${passage && passage !== source ? `<details><summary>${esc(c.inContext)}</summary><p lang="${esc(language)}">${esc(passage)}</p></details>` : ''}
      </section>
      <section class="understanding-body" aria-live="polite" data-understanding-body></section>
      <form class="understanding-ask" data-ask hidden>
        <label class="sr-only" for="understandingQuestion">${esc(c.askAnything)}</label>
        <input id="understandingQuestion" name="question" maxlength="200" placeholder="${esc(c.askPlaceholder)}" autocomplete="off">
        <button class="outline">${esc(c.ask)}</button>
      </form>
      <div class="understanding-suggestions" data-suggestions></div>
      <form class="understanding-keep" data-keep-form hidden>
        <label class="sr-only" for="understandingNote">${esc(c.note)}</label>
        <textarea id="understandingNote" name="note" rows="2" maxlength="2400"></textarea>
        <button class="primary">${esc(c.savePhrase)} ＋</button>
        <p role="status" data-keep-status></p>
      </form>
    </div>`,
  });

  const body = sheet.querySelector('[data-understanding-body]');
  const suggestions = sheet.querySelector('[data-suggestions]');
  const askForm = sheet.querySelector('[data-ask]');
  const keepForm = sheet.querySelector('[data-keep-form]');
  const alive = () => sheet.isConnected;

  const paintSuggestions = (offered) => {
    // A learner should never face an empty prompt: the standing questions are
    // always available, and anything the explanation suggests joins them.
    const asks = [
      ...new Set([...(offered || []), c.askWhy, c.askWhen, c.askDifference]),
    ].slice(0, 5);
    suggestions.innerHTML = asks
      .map((q) => `<button class="quiet" data-follow>${esc(q)}</button>`)
      .join('');
    suggestions
      .querySelectorAll('[data-follow]')
      .forEach((button) => (button.onclick = () => run(button.textContent)));
  };

  async function run(asked) {
    body.textContent = c.loading;
    askForm.hidden = true;
    suggestions.innerHTML = '';
    try {
      const result = await api.contextualDictionary({
        text: source,
        source_language: language,
        target_language: support,
        context: passage,
        question: String(asked || '').trim(),
      });
      if (!alive()) return;
      if (!result.available || result.selected_text !== source) {
        // Say what is missing rather than showing an empty explanation. The
        // learner can still keep the phrase with a note of their own, which is
        // often the more valuable half anyway.
        body.innerHTML = `<p class="notice">${esc(c.understandingUnavailable)}</p>`;
        askForm.hidden = false;
        paintSuggestions([]);
        keepForm.hidden = false;
        return;
      }
      body.innerHTML = explanationBlock(c, result);
      askForm.hidden = false;
      paintSuggestions(result.follow_ups);
      keepForm.hidden = false;
      if (!keepForm.elements.note.value)
        keepForm.elements.note.value = [result.natural_translation, result.summary]
          .filter(Boolean)
          .join('\n\n');
      focusRegion(body);
    } catch {
      if (!alive()) return;
      body.innerHTML = `<p class="notice">${esc(c.understandingUnavailable)}</p>`;
      askForm.hidden = false;
      paintSuggestions([]);
      keepForm.hidden = false;
    }
  }

  askForm.onsubmit = (event) => {
    event.preventDefault();
    const asked = askForm.elements.question.value.trim();
    if (!asked) return;
    askForm.elements.question.value = '';
    run(asked);
  };

  // Language worth explaining is language worth keeping, and keeping it here
  // reaches Recall the same way keeping it anywhere else does.
  keepForm.onsubmit = async (event) => {
    event.preventDefault();
    const report = progressReporter(
      keepForm.querySelector('[data-keep-status]'),
      ctx,
      alive,
    );
    const save = async () => {
      keepForm.querySelector('button').disabled = true;
      report.saving();
      try {
        await ctx.mutate(() =>
          api.saveLibraryVocabulary({
            word: source,
            definition: keepForm.elements.note.value,
            source_kind: 'manual',
            source_fragment: passage.slice(0, 1200),
            focus_note: String(title || '').slice(0, 2400),
          }),
        );
        /* The library owns the word and its review history; it has no column
           for where the learner met it. That lives beside it in memory, so a
           kept phrase can lead back to the passage, turn or line it came from.
           Written after the account save: a route back to something that was
           never saved would be worse than no route at all. */
        if (origin?.why)
          ctx.memory.rememberLanguage({
            term: source,
            origin: origin.id || '',
            where: origin.where || String(title || ''),
            why: origin.why,
            context: passage,
          });
        report.saved(savedLanguageLink(c));
      } catch {
        report.failed(c.failedSave, save);
        if (alive()) keepForm.querySelector('button').disabled = false;
      }
    };
    await save();
  };

  run(question);
  return sheet;
}

/* What the learner has actually selected inside a given element, so a
   highlight anywhere in a passage can be investigated in its own context. */
export function selectionWithin(root) {
  const selection = window.getSelection?.();
  if (!selection || selection.isCollapsed || !selection.rangeCount) return null;
  const range = selection.getRangeAt(0);
  if (!root.contains(range.commonAncestorContainer)) return null;
  const text = String(selection).trim();
  if (!text) return null;
  const block =
    range.startContainer.parentElement?.closest('p, blockquote, li, h1, h2, h3') ||
    root;
  return { text, context: block.textContent.trim() || root.textContent.trim() };
}

export function understandingLink(c, id) {
  return `<a class="quiet" href="${link('encounter', { id })}">${esc(c.returnLabel)} ↗</a>`;
}
