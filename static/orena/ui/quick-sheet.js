/* The Quick Sheet (D-066): one floating layer for asking about language, called
   from Reading, a Listening transcript, Speaking and - later - Writing and
   Vocabulary. A popover on a desk, a bottom sheet on a phone, and the same
   sheet grows as the learner asks: the first layer answers the commonest
   question at once, everything deeper opens only when asked.

   Two questions stay two paths (D-066 rule 8). The deterministic lookup fills
   the headword, the reading and the part of speech immediately; "meaning in
   this sentence" is the contextual explanation and arrives after. When it does
   not arrive the sheet says the meaning is the dictionary's rather than passing
   a dictionary sense off as a contextual one.

   The shapes it reads are the canonical contracts (WordDetail, SentenceSheet),
   served by /api/dictionary/word-detail and /sentence-sheet. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { progressReporter, savedLanguageLink } from './patterns.js';
import { keepPayload } from './reading-room.js';

const VERDICTS = {
  natural: { key: 'natural', icon: 'check-circle', tone: 'good' },
  'possible-unnatural': { key: 'possibleUnnatural', icon: 'warning-circle', tone: 'warn' },
  'context-inappropriate': { key: 'contextInappropriate', icon: 'compass', tone: 'caution' },
  'wrong-meaning': { key: 'wrongMeaning', icon: 'arrow-u-up-left', tone: 'bad' },
  'register-mismatch': { key: 'registerMismatch', icon: 'user-focus', tone: 'info' },
  'uncommon-legit': { key: 'uncommonLegit', icon: 'sparkle', tone: 'rare' },
  'grammatically-impossible': { key: 'grammaticallyImpossible', icon: 'x-circle', tone: 'impossible' },
};
const ROLE_KEY = {
  adverbial: 'quickRoleAdverbial',
  verb: 'quickRoleVerb',
  subject: 'quickRoleSubject',
  complement: 'quickRoleComplement',
};
// The generic questions the baseline offers after the one written for this word.
const CHIPS = [
  'quickChipContrast',
  'quickChipWhen',
  'quickChipNatural',
  'quickChipExamples',
  'quickChipMistakes',
  'quickChipRegister',
  'quickChipRelated',
];
// Parts of speech that are grammar rather than vocabulary: the primary action
// then names the grammar point, as the Chinese variant of the baseline draws.
const FUNCTION_WORDS = new Set(['adposition', 'particle', 'auxiliary', 'determiner', 'conjunction']);

const posName = (c, pos) => (pos && pos !== 'other' ? c[`pos_${pos}`] || '' : '');
const label = (text) => `<span class="qs-label">${esc(text)}</span>`;
const button = (action, body, { cls = '', attrs = '' } = {}) =>
  `<button type="button" class="${cls}" data-qs="${action}"${attrs ? ` ${attrs}` : ''}>${body}</button>`;

/* The selection, marked wherever it stands in its sentence. */
function highlighted(text, selection) {
  const at = selection ? text.toLocaleLowerCase().indexOf(selection.toLocaleLowerCase()) : -1;
  if (at < 0) return esc(text);
  return `${esc(text.slice(0, at))}<mark class="qs-mark">${esc(text.slice(at, at + selection.length))}</mark>${esc(text.slice(at + selection.length))}`;
}

const speaker = (c, size, on) =>
  button('speak', icon('speaker-high', { filled: true, size }), {
    cls: `qs-speak${on ? '' : ' qs-speak--rest'}`,
    attrs: `aria-label="${esc(c.selectionPronounce)}"`,
  });

const composer = (c, placeholder) =>
  `<form class="qs-composer" data-qs-form><label class="sr-only" for="qs-question">${esc(placeholder)}</label><span class="qs-composer__field">${icon('chat-teardrop-text', { size: 18 })}<input id="qs-question" name="question" autocomplete="off" maxlength="400" placeholder="${esc(placeholder)}"></span><button type="submit" class="qs-send" aria-label="${esc(c.quickSend)}">${icon('arrow-up', { filled: true, size: 19 })}</button></form>`;

const thread = (c, items, support) =>
  items.length
    ? `<div class="qs-thread" aria-live="polite">${items
        .map(
          (item) =>
            `<div class="qs-turn"><p class="qs-turn__q" lang="${esc(support)}">${esc(item.question)}</p>${
              item.state === 'loading'
                ? `<p class="qs-turn__a qs-muted" role="status">${esc(c.quickThinking)}</p>`
                : item.state === 'failed'
                  ? `<p class="qs-turn__a">${esc(c.lookupFailed)} ${button('retry-turn', esc(c.retry), { cls: 'qs-link', attrs: `data-turn="${item.id}"` })}</p>`
                  : `<p class="qs-turn__a" lang="${esc(support)}">${esc(item.answer || c.quickNothing)}</p>`
            }</div>`,
        )
        .join('')}</div>`
    : '';

/* What the sheet knows about the word right now, from whichever answer has come. */
export function wordView(c, s) {
  const detail = s.detail || {};
  const lookup = s.lookup || {};
  const script = detail.script || (s.language === 'zh' ? 'hanzi' : 'latin');
  const reading = detail.pinyin || detail.ipa || lookup.pronunciation || '';
  const pos = posName(c, detail.partOfSpeech || lookup.part_of_speech);
  const rawPos = detail.partOfSpeech || lookup.part_of_speech || '';
  return {
    headword: detail.headword || lookup.base_form || s.selection,
    script,
    reading,
    readingIsPinyin: script === 'hanzi',
    ipa: script === 'hanzi' ? detail.ipa || '' : '',
    pos,
    isFunctionWord: FUNCTION_WORDS.has(rawPos),
    meaning: detail.contextMeaning || '',
    meaningSource: detail.meaningSource || '',
    verdict: VERDICTS[detail.usageVerdict] || null,
    deeper: detail.deeper || {},
    followUps: detail.followUps || [],
    saved: Boolean(detail.saved) || s.kept,
  };
}

function wordHead(c, v, s, { small = false } = {}) {
  const readingLine = `${v.reading ? `<span class="qs-reading${v.readingIsPinyin ? ' qs-reading--pinyin' : ''}"${v.readingIsPinyin ? ' data-reading="pinyin"' : ''}>${esc(v.reading)}</span>` : ''}${v.ipa ? `<span class="qs-reading">${esc(v.ipa)}</span>` : ''}${v.pos ? `<span class="qs-chip">${esc(v.pos)}</span>` : ''}`;
  return `<div class="qs-head${small ? ' qs-head--small' : ''}"><div class="qs-title"><strong class="qs-word qs-word--${v.script}" lang="${esc(s.language)}">${esc(v.headword)}</strong>${small ? '' : `<div class="qs-reading-row">${readingLine}</div>`}</div>${small ? `<span class="qs-reading">${esc(v.reading)}</span>` : ''}${speaker(c, small ? 17 : 23, !small)}</div>`;
}

function layerOne(c, s, v) {
  const loading = s.detailState === 'loading';
  const meaning = v.meaning
    ? `<p class="qs-meaning" lang="${esc(s.support)}">${esc(v.meaning)}</p>${v.meaningSource === 'dictionary' ? `<p class="qs-source">${esc(c.quickFromDictionary)}</p>` : ''}`
    : loading
      ? `<p class="qs-meaning qs-skeleton" role="status" aria-label="${esc(c.quickLoading)}"><span></span></p>`
      : `<p class="qs-meaning qs-muted">${esc(c.quickNothing)}</p>`;
  const why = v.isFunctionWord && s.language === 'zh' ? `${c.quickGrammarOf} ${v.headword}` : c.quickWhy;
  const saveBody = v.saved
    ? `${icon('bookmark-simple', { filled: true, size: 19 })}${esc(c.selectionSaved)}`
    : `${icon('bookmark-simple', { size: 19 })}${esc(c.quickSave)}`;
  return `${wordHead(c, v, s)}<hr class="qs-rule"><div class="qs-group">${label(c.quickMeaningLabel)}${meaning}</div><blockquote class="qs-well" lang="${esc(s.language)}">${highlighted(s.context, s.selection)}</blockquote><div class="qs-actions">${button('save', saveBody, { cls: 'qs-btn', attrs: v.saved ? 'aria-pressed="true"' : '' })}${button('why', `${icon('sparkle', { size: 19 })}${esc(why)}`, { cls: 'qs-btn qs-btn--primary', attrs: loading ? '' : '' })}</div><p class="meta qs-status" role="status" data-panel-status></p>`;
}

function verdictCard(c, v, support, full = 'ready') {
  if (full === 'loading')
    return `<section class="qs-verdict" role="status" aria-label="${esc(c.quickThinking)}"><span class="qs-skeleton"><span></span></span><span class="qs-skeleton"><span></span></span></section>`;
  if (full === 'failed')
    return `<section class="qs-verdict"><p>${esc(c.lookupFailed)} ${button('retry-full', esc(c.retry), { cls: 'qs-link' })}</p></section>`;
  const verdict = v.verdict;
  if (!verdict) return '';
  const text = v.deeper.whyHere || v.meaning;
  return `<section class="qs-verdict"><span class="qs-verdict__label qs-tone--${verdict.tone}">${icon(verdict.icon, { filled: true, size: 14 })}${esc(c[`quickVerdict_${verdict.key}`])}</span>${text ? `<p lang="${esc(support)}">${esc(text)}</p>` : ''}</section>`;
}

function askView(c, s, v) {
  const chips = [...v.followUps.slice(0, 1), ...CHIPS.map((key) => c[key])];
  return `${wordHead(c, v, s, { small: true })}${verdictCard(c, v, s.support, s.full)}${label(c.quickAskNext)}<div class="qs-chips">${chips
    .map((text) => button('chip', esc(text), { cls: 'qs-chip qs-chip--ask', attrs: `data-text="${esc(text)}"` }))
    .join('')}</div>${thread(c, s.thread, s.support)}<div class="qs-foot">${composer(c, c.quickFreeQuestion)}<div class="qs-actions">${button('save', `${icon('bookmark-simple', { filled: v.saved, size: 18 })}${esc(v.saved ? c.selectionSaved : c.quickSaveWord)}`, { cls: 'qs-btn' })}${button('deeper', `${icon('arrows-out-simple', { size: 18 })}${esc(c.quickDeeper)}`, { cls: 'qs-btn' })}</div></div><p class="meta qs-status" role="status" data-panel-status></p>`;
}

function section(name, body, cls = '') {
  return body ? `<section class="qs-section ${cls}">${label(name)}${body}</section>` : '';
}

function deeperView(c, s, v) {
  const d = v.deeper;
  const contrast = (d.contrast || []).length
    ? `<div class="qs-rows">${d.contrast.map((row) => `<div class="qs-row"><span class="qs-row__term">${esc(row.term)}</span><span class="qs-row__note" lang="${esc(s.support)}">${esc(row.note)}</span></div>`).join('')}</div>`
    : '';
  const examples = (d.examples || []).length
    ? `<div class="qs-examples" lang="${esc(s.language)}">${d.examples.map((line) => `<span>${highlighted(line, s.selection)}</span>`).join('')}</div>`
    : '';
  /* The note is a headline (the forms) and what follows it, as the frame draws it. */
  const noteLines = d.grammarNote ? String(d.grammarNote).split('\n') : [];
  const grammar = noteLines.length
    ? `<div class="qs-note" lang="${esc(s.support)}"><span class="qs-note__head" lang="${esc(s.language)}">${esc(noteLines[0])}</span>${noteLines.length > 1 ? `<span class="qs-note__body">${esc(noteLines.slice(1).join(' '))}</span>` : ''}</div>`
    : '';
  const related = (d.relatedExpressions || []).length
    ? `<div class="qs-chips">${d.relatedExpressions.map((item) => `<span class="qs-chip qs-chip--plain" title="${esc(item.note)}">${esc(item.term)}</span>`).join('')}</div>`
    : '';
  const p = (text) => (text ? `<p class="qs-text" lang="${esc(s.support)}">${esc(text)}</p>` : '');
  return `<div class="qs-top"><span class="qs-grab" aria-hidden="true"></span><div class="qs-top__row"><strong class="qs-word qs-word--small qs-word--${v.script}" lang="${esc(s.language)}">${esc(v.headword)}</strong><span class="qs-reading">${esc(v.reading)}</span>${button('close', esc(c.quickClose), { cls: 'qs-link qs-top__close' })}</div></div><div class="qs-scroll">${s.full === 'loading' ? `<p class="qs-meaning qs-skeleton" role="status" aria-label="${esc(c.quickThinking)}"><span></span></p>` : s.full === 'failed' ? `<p class="qs-text">${esc(c.lookupFailed)} ${button('retry-full', esc(c.retry), { cls: 'qs-link' })}</p>` : ''}${section(c.quickCore, p(d.coreIdea), 'qs-section--core')}${section(c.quickMental, p(d.mentalModel))}${section(c.quickContrast, contrast)}${section(c.quickExamples, examples)}${section(c.quickWhyHere, p(d.whyHere), 'qs-section--why')}${section(c.quickMistake, p(d.commonMistake), 'qs-section--mistake')}${section(c.quickGrammarNote, grammar)}${section(c.quickRelated, related)}${thread(c, s.thread, s.support)}</div><div class="qs-foot qs-foot--bar">${(v.followUps || []).length ? `${label(c.quickMightAsk)}${button('chip', esc(v.followUps[0]), { cls: 'qs-chip qs-chip--ask', attrs: `data-text="${esc(v.followUps[0])}"` })}` : ''}${composer(c, c.quickFollowUp)}${button('save-explanation', `${icon('bookmark-simple', { size: 18 })}${esc(c.quickSaveExplanation)}`, { cls: 'qs-btn qs-btn--primary', attrs: `aria-disabled="true" title="${esc(c.quickExplanationSoon)}"` })}</div>`;
}

/* Sentence parts: each chunk the model named, coloured by its role, with the
   words between them left plain, so the row still reads as the sentence. */
function structureRow(c, sentence) {
  const parts = sentence.structure || [];
  if (!parts.length) return '';
  let cursor = 0;
  const out = [];
  for (const part of parts) {
    const at = sentence.sentence.indexOf(part.chunk, cursor);
    if (at < 0) continue;
    const gap = sentence.sentence.slice(cursor, at).trim();
    if (gap) out.push(`<span class="qs-gap">${esc(gap)}</span>`);
    out.push(`<span class="qs-part qs-part--${esc(part.role)}" title="${esc(c[ROLE_KEY[part.role]] || part.role)}">${esc(part.chunk)}</span>`);
    cursor = at + part.chunk.length;
  }
  const rest = sentence.sentence.slice(cursor).trim();
  if (rest) out.push(`<span class="qs-gap">${esc(rest)}</span>`);
  return `<div class="qs-parts" lang="${esc(sentence.__language || '')}">${out.join('')}</div>`;
}

function sentenceView(c, s) {
  const sentence = s.sentence;
  const loading = s.sentenceState === 'loading';
  if (!sentence) {
    return `<div class="qs-head"><div class="qs-title">${label(c.quickWholeSentence)}</div>${speaker(c, 17, false)}</div><blockquote class="qs-well qs-well--serif" lang="${esc(s.language)}">${esc(s.selection)}</blockquote>${
      loading
        ? `<p class="qs-meaning qs-skeleton" role="status" aria-label="${esc(c.quickLoading)}"><span></span></p>`
        : `<p class="qs-meaning qs-muted">${esc(c.quickNothing)} ${button('retry', esc(c.retry), { cls: 'qs-link' })}</p>`
    }`;
  }
  const wordCount = (sentence.vocabulary || []).filter((item) => !item.saved).length;
  if (s.view === 'parts') {
    const vocab = (sentence.vocabulary || []).length
      ? `<div class="qs-rows">${sentence.vocabulary
          .map(
            (item) =>
              `<div class="qs-row qs-row--word"><span class="qs-row__term">${esc(item.term)}</span><span class="qs-row__note" lang="${esc(s.support)}">${esc(item.meaning)}</span>${button('save-term', icon('bookmark-simple', { filled: item.saved, size: 18 }), { cls: 'qs-icon', attrs: `data-term="${esc(item.term)}" data-meaning="${esc(item.meaning)}" aria-pressed="${item.saved}" aria-label="${esc(item.saved ? c.selectionSaved : c.quickSave)}"` })}</div>`,
          )
          .join('')}</div>`
      : '';
    return `<div class="qs-top"><span class="qs-grab" aria-hidden="true"></span><div class="qs-top__row"><strong class="qs-top__title">${esc(c.quickThisSentence)}</strong>${button('close', esc(c.quickClose), { cls: 'qs-link qs-top__close' })}</div></div><div class="qs-scroll">${section(c.quickStructure, `${structureRow(c, { ...sentence, __language: s.language })}${sentence.shortExplanation ? `<p class="qs-text" lang="${esc(s.support)}">${esc(sentence.shortExplanation)}</p>` : ''}`)}${section(c.quickSentenceVocab, vocab)}${thread(c, s.thread, s.support)}</div><div class="qs-foot qs-foot--bar">${composer(c, c.quickFollowUp)}${button('save-all', `${icon('bookmark-simple', { size: 18 })}${esc(c.quickSaveAll.replace('{n}', String(wordCount)))}`, { cls: 'qs-btn qs-btn--primary' })}</div><p class="meta qs-status" role="status" data-panel-status></p>`;
  }
  return `<div class="qs-head"><div class="qs-title">${label(c.quickWholeSentence)}</div>${speaker(c, 17, false)}</div><blockquote class="qs-well qs-well--serif" lang="${esc(s.language)}">${esc(sentence.sentence)}</blockquote>${section(c.quickSentenceMeaning, `<p class="qs-meaning qs-meaning--sentence" lang="${esc(s.support)}">${esc(sentence.translation || c.quickNothing)}</p>`)}${section(c.quickShortExplain, `<p class="qs-text" lang="${esc(s.support)}">${esc(sentence.shortExplanation || c.quickNothing)}</p>`)}<div class="qs-chips">${[c.quickChipSentenceGrammar, c.quickChipSentenceVocab, c.quickChipAskMore].map((text) => button('parts', esc(text), { cls: 'qs-chip qs-chip--ask' })).join('')}</div><div class="qs-actions">${button('save-sentence', `${icon('bookmark-simple', { filled: s.kept, size: 18 })}${esc(s.kept ? c.selectionSaved : c.quickSaveSentence)}`, { cls: 'qs-btn' })}${button('parts', `${icon('sparkle', { size: 18 })}${esc(c.quickExplainSentence)}`, { cls: 'qs-btn qs-btn--primary' })}</div><p class="meta qs-status" role="status" data-panel-status></p>`;
}

/* Pure: the sheet's markup for a state. */
export function quickSheetHtml(c, s) {
  const closeLabel = esc(c.quickClose);
  const close = `<button type="button" class="qs-x" data-qs="close" aria-label="${closeLabel}">${icon('x', { size: 18 })}</button>`;
  if (s.kind === 'sentence') return `${s.view === 'parts' ? '' : close}${sentenceView(c, s)}`;
  const v = wordView(c, s);
  if (s.view === 'deeper') return deeperView(c, s, v);
  if (s.view === 'ask') return `${close}${askView(c, s, v)}`;
  return `${close}${layerOne(c, s, v)}`;
}

/* The controller: state, the two requests, and what each action does. The host
   (ui/lexical.js) owns the element and where it sits; this owns the meaning. */
export function createQuickSheet({ ctx, target, title, alive, paint, close, speak, remember, statusEl }) {
  const { api, language, support, c } = ctx;
  const kind = target.kind === 'word' ? 'word' : 'sentence';
  const state = {
    kind,
    view: 'sheet',
    selection: target.text,
    context: target.context || target.text,
    language,
    support,
    lookup: null,
    detail: null,
    detailState: 'loading',
    // The explanation behind "why here?" is asked for when opened: idle, loading, ready, failed.
    full: 'idle',
    sentence: null,
    sentenceState: 'loading',
    thread: [],
    kept: false,
  };
  let turns = 0;
  const render = () => alive() && paint(quickSheetHtml(c, state), state);
  const request = (question = '') => ({
    text: kind === 'word' ? target.text.slice(0, 80) : target.text.slice(0, 1600),
    context: state.context,
    source_language: language,
    target_language: support,
    ...(question ? { question } : {}),
  });

  async function load() {
    render();
    if (kind === 'word') {
      api
        .readingLookup({ text: request().text, context: state.context.slice(0, 1200), source_language: language, target_language: support })
        .then((value) => {
          state.lookup = value || null;
          render();
        })
        .catch(() => {});
      try {
        const detail = await api.wordDetail({ ...request(), context: state.context.slice(0, 1200), depth: 'sheet' });
        state.detail = detail;
        state.detailState = detail?.available ? 'ready' : 'unavailable';
        state.kept = state.kept || Boolean(detail?.saved);
      } catch {
        state.detailState = 'failed';
      }
    } else {
      try {
        const sheet = await api.sentenceSheet(request());
        state.sentence = sheet?.available ? sheet : null;
        state.sentenceState = sheet?.available ? 'ready' : 'unavailable';
      } catch {
        state.sentenceState = 'failed';
      }
    }
    render();
  }

  /* The full explanation, once, when the learner opens what sits behind the
     first layer. It fills in the verdict, the questions and the deeper sections
     and leaves the meaning and the reading already on screen as they were. */
  async function ensureFull() {
    if (kind !== 'word' || state.full === 'loading' || state.full === 'ready') return;
    state.full = 'loading';
    render();
    try {
      const full = await api.wordDetail({ ...request(), context: state.context.slice(0, 1200), depth: 'full' });
      if (full?.available) {
        state.detail = { ...state.detail, ...full, contextMeaning: state.detail?.contextMeaning || full.contextMeaning || '' };
        state.full = 'ready';
      } else state.full = 'failed';
    } catch {
      state.full = 'failed';
    }
    render();
  }

  async function ask(question, existing = null) {
    const text = String(question || '').trim();
    if (!text) return;
    const turn = existing || { id: ++turns, question: text, state: 'loading', answer: '' };
    turn.state = 'loading';
    if (!existing) state.thread.push(turn);
    if (kind === 'word' && state.view === 'sheet') state.view = 'ask';
    render();
    try {
      const value = await (kind === 'word' ? api.wordDetail(request(text)) : api.sentenceSheet(request(text)));
      turn.answer = value?.answer || '';
      turn.state = value?.available ? 'ready' : 'failed';
    } catch {
      turn.state = 'failed';
    }
    render();
  }

  /* One way to keep language from the sheet: saving, saved (with the way back to
     it) and failed (with a retry that runs the same action again). */
  async function persist(terms, { retry, done }) {
    const report = progressReporter(statusEl(), ctx, alive);
    report.saving();
    try {
      for (const item of terms)
        await ctx.mutate(() =>
          api.saveLibraryVocabulary(
            keepPayload({
              selection: item.term,
              result: { pronunciation: item.reading || '', part_of_speech: item.pos || '', meanings: item.meaning ? [{ text: item.meaning }] : [] },
              context: state.context,
              title,
            }),
          ),
        );
      for (const item of terms) remember?.(item.term, state.context);
      done();
      render();
      progressReporter(statusEl(), ctx, alive).saved(savedLanguageLink(c));
    } catch {
      report.failed(c.failedSave, retry);
    }
  }

  const act = async (action, data = {}) => {
    switch (action) {
      case 'close':
        return close();
      case 'speak':
        return speak(target.text);
      case 'why':
        state.view = 'ask';
        render();
        return ensureFull();
      case 'deeper':
        state.view = 'deeper';
        render();
        return ensureFull();
      case 'retry-full':
        state.full = 'idle';
        return ensureFull();
      case 'parts':
        state.view = 'parts';
        return render();
      case 'chip':
        return ask(data.text);
      case 'retry':
        state.detailState = 'loading';
        state.sentenceState = 'loading';
        return load();
      case 'retry-turn': {
        const turn = state.thread.find((item) => String(item.id) === String(data.turn));
        return turn && ask(turn.question, turn);
      }
      case 'save': {
        const v = wordView(c, state);
        return persist(
          [{ term: target.text, reading: v.reading, pos: state.detail?.partOfSpeech || '', meaning: v.meaning }],
          { retry: () => act('save'), done: () => (state.kept = true) },
        );
      }
      case 'save-sentence':
      case 'save-all': {
        const words = (state.sentence?.vocabulary || []).filter((item) => !item.saved);
        return persist(
          [{ term: target.text.slice(0, 180), meaning: state.sentence?.translation || '' }, ...words.map((w) => ({ term: w.term, meaning: w.meaning }))],
          {
            retry: () => act(action),
            done: () => {
              state.kept = true;
              for (const word of state.sentence?.vocabulary || []) word.saved = true;
            },
          },
        );
      }
      case 'save-term': {
        const word = (state.sentence?.vocabulary || []).find((item) => item.term === data.term);
        if (!word || word.saved) return undefined;
        return persist([{ term: word.term, meaning: word.meaning }], {
          retry: () => act(action, data),
          done: () => (word.saved = true),
        });
      }
      default:
        return undefined;
    }
  };

  return { state, load, act, ask, render };
}
