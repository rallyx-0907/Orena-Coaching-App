import { esc, dialog, focusRegion } from './html.js';
import { link } from '../product/intent.js';
import { progressReporter, savedLanguageLink } from './patterns.js';
import { attempt, isReady, canRetry } from '../capabilities/outcome.js';

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

  /* Which question this panel is currently waiting for.

     The selection and its passage are fixed when the panel opens, so they
     cannot drift. The question can: a learner who asks "why this way" and then
     "when would I use it" has two requests in flight, and whichever returns
     last wins the panel - which may be the answer to the question they already
     moved on from. Each ask takes a ticket, and only the newest one is allowed
     to paint. A late answer is dropped, not shown against the wrong question. */
  let asking = 0;

  async function run(asked) {
    const ticket = ++asking;
    const current = () => alive() && ticket === asking;
    body.textContent = c.loading;
    askForm.hidden = true;
    suggestions.innerHTML = '';
    /* An explanation that is not coming and one that did not arrive are
       different news. The first is the provider being absent here; the second
       is a request that failed on the way and is worth asking again. Both used
       to read as the same sentence, with no way forward from either. */
    const outcome = await attempt(
      () =>
        api.contextualDictionary({
          text: source,
          source_language: language,
          target_language: support,
          context: passage,
          question: String(asked || '').trim(),
        }),
      {
        // A payload about different text is not an answer about this selection,
        // whatever else it carries.
        read: (result) => ({
          ok: Boolean(result?.available) && result.selected_text === source,
        }),
      },
    );
    if (!current()) return;
    // Keeping the phrase with a note of their own stays available whatever
    // happened; it is often the more valuable half anyway.
    askForm.hidden = false;
    keepForm.hidden = false;
    if (!isReady(outcome)) {
      const retryable = canRetry(outcome);
      body.innerHTML = `<p class="notice">${esc(retryable ? c.understandingFailed : c.understandingUnavailable)}</p>`;
      paintSuggestions([]);
      if (retryable) {
        const again = document.createElement('button');
        again.className = 'outline';
        again.textContent = c.retry;
        again.onclick = () => run(asked);
        body.append(again);
      }
      return;
    }
    const result = outcome.value;
    body.innerHTML = explanationBlock(c, result);
    paintSuggestions(result.follow_ups);
    if (!keepForm.elements.note.value)
      keepForm.elements.note.value = [result.natural_translation, result.summary]
        .filter(Boolean)
        .join('\n\n');
    focusRegion(body);
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

// "other" is the tagger admitting it has no class to give, not a class to show.
export function posLabel(c, pos) {
  return pos && pos !== 'other' ? c[`pos_${pos}`] || '' : '';
}

/* The word card: the first, quick answer about one word or short phrase, where
   the learner pointed at it. It says what the word means in this sentence, how
   it sounds and what kind of word it is - and hands anything deeper to the full
   explanation above rather than growing into a second one.

   `state` is what the gloss request came to: loading, ready, unavailable (the
   provider is not there - nothing to retry) or failed (worth trying again).
   Local facts - word class, Chinese pinyin - still show when the meaning does
   not arrive. */
export function wordCardBody(c, { selection, language, support, state, result = {}, headingId = '' }) {
  const found = result || {};
  const word = String(selection || '').trim();
  const baseForm = String(found.base_form || '').trim();
  const facts = [
    posLabel(c, found.part_of_speech)
      ? `<span>${esc(posLabel(c, found.part_of_speech))}</span>`
      : '',
    baseForm && baseForm.toLowerCase() !== word.toLowerCase()
      ? `<span>${esc(c.wordCardBaseForm)}: <span lang="${esc(language)}">${esc(baseForm)}</span></span>`
      : '',
  ].filter(Boolean);
  const meaning =
    state === 'ready' && found.meaning
      ? `<p class="word-card__meaning" lang="${esc(support)}">${esc(found.meaning)}</p>`
      : state === 'failed'
        ? `<p class="word-card__meaning" data-state="failed">${esc(c.wordCardFailed)} <button type="button" class="quiet" data-word-retry>${esc(c.retry)}</button></p>`
        : state === 'unavailable'
          ? `<p class="word-card__meaning" data-state="unavailable">${esc(c.wordCardUnavailable)}</p>`
          : `<p class="word-card__meaning" data-state="loading" role="status">${esc(c.wordCardLoading)}</p>`;
  return `<div class="word-card__head"><strong class="word-card__word"${headingId ? ` id="${esc(headingId)}"` : ''} lang="${esc(language)}">${esc(word)}</strong>${found.pronunciation ? `<span class="word-card__reading">${esc(found.pronunciation)}</span>` : ''}</div>${facts.length ? `<p class="word-card__facts">${facts.join('<span aria-hidden="true"> · </span>')}</p>` : ''}${meaning}<div class="word-card__actions"><button type="button" class="primary" data-word-keep${state === 'loading' ? ' disabled' : ''}>${esc(c.wordCardKeep)} ＋</button><button type="button" class="quiet" data-word-more>${esc(c.wordCardMore)} ↗</button></div><p class="meta" role="status" data-word-status></p>`;
}

// A kept word carries its meaning and the sentence it was met in.
export function glossKeepPayload({ selection, result = {}, context = '', title = '' }) {
  const found = result || {};
  return {
    word: String(selection || '').trim().slice(0, 180),
    phonetic: String(found.pronunciation || '').slice(0, 180),
    part_of_speech: String(found.part_of_speech || '').slice(0, 120),
    definition: String(found.meaning || '').slice(0, 2400),
    source_kind: 'reading',
    source_fragment: String(context || '').slice(0, 1200),
    focus_note: String(title || '').slice(0, 2400),
  };
}

let wordCardSequence = 0;
let activeWordCard = null;

/* Opens beside the word on a wide screen and as a sheet along the bottom of a
   narrow one (CSS). It is not modal: reading carries on underneath, and a tap
   anywhere else, Escape, scrolling or leaving the room closes it. One card at
   a time. `returnFocus` is where keyboard focus goes back to on Escape. */
export function openWordCard(
  ctx,
  { selection, context, anchor, title = '', origin = null, returnFocus = null },
) {
  const { c, api, language, support } = ctx;
  const word = String(selection || '').trim();
  const sentence = String(context || word).trim();
  if (!word) return null;
  activeWordCard?.close();

  const card = document.createElement('div');
  const headingId = `orena-word-card-${++wordCardSequence}`;
  card.className = 'word-card';
  card.setAttribute('role', 'dialog');
  card.setAttribute('aria-modal', 'false');
  card.setAttribute('aria-labelledby', headingId);
  card.tabIndex = -1;
  const closeLabel = document.documentElement.dataset.close || 'Close';
  let state = 'loading';
  let result = {};
  let asking = 0;

  const alive = () => card.isConnected;
  const place = () => {
    card.style.removeProperty('top');
    card.style.removeProperty('left');
    if (window.matchMedia('(max-width: 700px)').matches) return;
    const box = anchor?.getBoundingClientRect?.();
    if (!box) return;
    const gap = 8;
    const width = card.offsetWidth;
    const height = card.offsetHeight;
    const room = document.documentElement.clientWidth;
    const top =
      box.bottom + gap + height <= window.innerHeight - gap
        ? box.bottom + gap
        : Math.max(gap, box.top - gap - height);
    card.style.top = `${Math.round(top)}px`;
    card.style.left = `${Math.round(Math.min(Math.max(gap, box.left), room - width - gap))}px`;
  };

  const handle = { element: card, close: () => close() };
  const onKey = (event) => {
    if (event.key !== 'Escape') return;
    event.preventDefault();
    close({ restore: true });
  };
  const onPointer = (event) => {
    if (!card.contains(event.target)) close();
  };
  const onScroll = (event) => {
    if (!card.contains(event.target)) close();
  };
  const onLeave = () => close();
  function close({ restore = false } = {}) {
    if (!card.isConnected) return;
    document.removeEventListener('keydown', onKey);
    document.removeEventListener('pointerdown', onPointer, true);
    document.removeEventListener('scroll', onScroll, true);
    window.removeEventListener('resize', onLeave);
    window.removeEventListener('hashchange', onLeave);
    card.remove();
    if (activeWordCard === handle) activeWordCard = null;
    if (restore) (returnFocus?.isConnected ? returnFocus : null)?.focus?.({ preventScroll: true });
  }

  const keep = async (button) => {
    const report = progressReporter(card.querySelector('[data-word-status]'), ctx, alive);
    const save = async () => {
      button.disabled = true;
      report.saving();
      try {
        await ctx.mutate(() =>
          api.saveLibraryVocabulary(
            glossKeepPayload({ selection: word, result, context: sentence, title }),
          ),
        );
        // As in the full explanation: the way back is written only after the
        // account has the word.
        if (origin?.why)
          ctx.memory.rememberLanguage({
            term: word,
            origin: origin.id || '',
            where: origin.where || title,
            why: origin.why,
            context: sentence,
          });
        report.saved(savedLanguageLink(c));
      } catch {
        report.failed(c.failedSave, save);
        if (alive()) button.disabled = false;
      }
    };
    await save();
  };

  const paint = () => {
    card.innerHTML = `<button type="button" class="word-card__close" data-word-close aria-label="${esc(closeLabel)}">×</button>${wordCardBody(c, { selection: word, language, support, state, result, headingId })}`;
    card.querySelector('[data-word-close]').onclick = () => close({ restore: true });
    card.querySelector('[data-word-keep]').onclick = (event) => keep(event.currentTarget);
    card.querySelector('[data-word-more]').onclick = () => {
      close();
      openUnderstanding(ctx, { selection: word, context: sentence, title, origin });
    };
    const retry = card.querySelector('[data-word-retry]');
    if (retry) retry.onclick = () => ask();
    place();
  };

  async function ask() {
    const ticket = ++asking;
    state = 'loading';
    paint();
    let next = 'failed';
    let found = {};
    try {
      const value = await api.contextualGloss({
        text: word,
        context: sentence,
        source_language: language,
        target_language: support,
      });
      // An answer about other words is not an answer about this one.
      found = value?.selected_text === word ? value : {};
      next = value?.available && value.selected_text === word ? 'ready' : 'unavailable';
    } catch {
      next = 'failed';
    }
    if (!alive() || ticket !== asking) return;
    state = next;
    result = found;
    paint();
  }

  document.body.append(card);
  document.addEventListener('keydown', onKey);
  document.addEventListener('pointerdown', onPointer, true);
  document.addEventListener('scroll', onScroll, true);
  window.addEventListener('resize', onLeave);
  window.addEventListener('hashchange', onLeave);
  activeWordCard = handle;
  ask();
  card.focus({ preventScroll: true });
  return handle;
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
