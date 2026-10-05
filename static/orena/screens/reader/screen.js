/* Reader (design route `reader`, frame 14; `#/read/:id`, D-091). The one reading surface for every
   text source: a published article, a shared-library book's chapter, or a learner's own imported
   text (source.js). The content id is Content Detail's own scheme ("<kind>:<id>", a book chapter
   "book:<bookId>:<chapterId>"; screens/content/model.js) - the same id Content Detail's primary
   action already hands the router.

   What the frame draws and where each piece gets its data:
   - toolbar: Aa (text size, product/reader-settings.js), theme (the device's light/dark choice,
     kit/device.js), Listen (the browser's own speech synthesis), bookmark (`/api/library/items`, or
     device memory for an imported text), Aids and the ⋯ menu;
   - Aids: translation (`POST /api/reading/translate`, in turns), the vocabulary lens (words kept from
     this text's own sentences), word roles and pinyin (`POST /api/media-learning/annotate`, the
     local non-AI tagger);
   - the text itself: a tap on a word opens the Word Quick Sheet (or, with word roles on, names the
     word's role), a tap on the sentence around it or a text selection offers Translate / Highlight
     / Note / Ask Orena (the selection toolbar); notes are the Sentence Quick Sheet's own
     device-memory notes and highlights are this screen's (highlights.js), both listed in
     "Notes & highlights" (a docked panel on a desk, the design's bottom sheet on a phone);
   - the position: kept in device memory (`memory.enter`, furthest point read) and restored.
   Summary is generated on request (D-130, POST /api/reading/summary): only when the learner opens
   it, once - the server keeps it - shown in the frame's docked panel with its loading and retry
   states. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { markGlyph } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { theme, device, toggleAppearance, onDeviceChange } from '../../kit/device.js';
import { openSheet, sheetHead, fillSheet } from '../../kit/overlay.js';
import { toast } from '../../kit/toast.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { readReaderSettings, writeReaderSettings } from '../../product/reader-settings.js';
import { openWordSheet, openSentenceSheet } from '../quick-sheet/sheet.js';
import { loadNotes, noteKeyFor, noteTypeColorKey } from '../quick-sheet/model.js';
import { t } from './copy.js';
import { mountReaderLexical } from './lexical.js';
import { loadHighlights, isHighlighted, toggleHighlight } from './highlights.js';
import { pullIntoDevice, scheduleAnnotationPush, noteRemoved } from './annotations-sync.js';
import { loadReadable, realContentIdOf, loadQuizSize, loadSaved, loadSavedFromText } from './source.js';
import {
  parseContentId,
  contentIdFor,
  sentencesOf,
  segmentId,
  segmentSentence,
  ROLES,
  aidsCount,
  endOfContent,
  percentFromScroll,
  scrollTopFor,
  placeFor2,
  furthest,
  excerptFrom,
  readerSizePx,
  steppedSize,
  toolbarMeta,
  pageOf,
  sentenceTurns,
  sentenceTranslationsFrom,
  paragraphMeaning,
  roleToast,
  squash,
} from './model.js';

const ROLE_KEY = Object.freeze({
  noun: 'roleNoun',
  verb: 'roleVerb',
  modifier: 'roleModifier',
  connector: 'roleConnector',
  pronoun: 'rolePronoun',
  number: 'roleNumber',
});

const ROLE_HELP_KEY = Object.freeze({
  noun: 'roleNounHelp',
  verb: 'roleVerbHelp',
  modifier: 'roleModifierHelp',
  connector: 'roleConnectorHelp',
  pronoun: 'rolePronounHelp',
  number: 'roleNumberHelp',
});

const ANNOTATE_CONCURRENCY = 6;
const NBSP = String.fromCharCode(160);

function relativeWhen(iso, uiLang) {
  const at = Date.parse(iso);
  if (!Number.isFinite(at)) return '';
  const seconds = Math.round((at - Date.now()) / 1000);
  const abs = Math.abs(seconds);
  let unit = 'second';
  let value = seconds;
  if (abs >= 86400) [unit, value] = ['day', Math.round(seconds / 86400)];
  else if (abs >= 3600) [unit, value] = ['hour', Math.round(seconds / 3600)];
  else if (abs >= 60) [unit, value] = ['minute', Math.round(seconds / 60)];
  else value = 0;
  try {
    return new Intl.RelativeTimeFormat(uiLang, { numeric: 'auto' }).format(value, unit);
  } catch {
    return '';
  }
}

export default async function mountReader(element, ctx) {
  await useStyles('screens/reader/reader.css');
  const parsed = parseContentId(ctx.params?.id);
  if (!['article', 'book', 'text'].includes(parsed.kind)) throw new Error(`Reader: unknown content id "${ctx.params?.id}"`);
  const memory = ctx.context.memory;
  const owner = ctx.context.owner;

  const doc = await loadReadable(parsed, memory);
  const [quizSize, savedInfo, savedFrom] = await Promise.all([loadQuizSize(doc.kind, doc.id), loadSaved(doc.kind, doc, memory), loadSavedFromText(doc)]);
  const hasQuiz = quizSize > 0;
  /* Practice mode (Content Detail's "Practice this text", the frame's startPractice): read, answer the
     text's questions, go on to the next reading. Only a text that has questions can be practised. */
  const practice = hasQuiz && ctx.query?.get?.('mode') === 'practice';
  if (!ctx.isCurrent()) return undefined;
  if (!doc.paragraphs.length) throw new Error('This text has nothing to read.');

  const contentId = realContentIdOf(doc);
  ctx.setCrumb(doc.title);

  const isZh = doc.language === 'zh';
  const language = doc.language;
  const support = () => languages().support;
  const source = { kind: 'reading', content_id: contentId, title: doc.title };
  let storage = null;
  try {
    storage = window.localStorage;
  } catch {
    storage = null;
  }

  /* ---- per-visit state ---- */
  let menuOpen = ''; // 'aa' | 'aids' | 'more' | ''
  let translationOn = false;
  let vocabLensOn = true; // frame 14 opens with the vocabulary lens on (rdLens: true)
  let posOn = false;
  let pinyinOn = isZh && ctx.context.pinyin !== false;
  let notesOpen = false;
  let summaryOpen = false;
  let summary = { state: 'idle', bullets: [] }; // 'idle' | 'loading' | 'ready' | 'failed'
  let listening = false;
  let sheetOpen = false;
  let notesSheet = null;
  let settings = readReaderSettings();
  let savedState = { saved: savedInfo.saved, itemId: savedInfo.itemId };
  let savedWords = savedFrom ? savedFrom.bySentence : new Map();
  let selected = null; // { seg, text }
  let picked = ''; // word-role tap: "seg|word"
  let highlights = storage ? loadHighlights(storage, owner, contentId) : [];
  let alive = true;
  const expandedNotes = new Set();
  const translations = new Map(); // sentence segment id -> meaning (D-130: the sentence is the shared unit)
  let translationState = 'idle'; // 'idle' | 'loading' | 'ready' | 'failed'
  const annotations = new Map(); // segment -> tokens (offsets relative to the sentence)
  const annotationLoads = new Map(); // paragraph index -> the one shared in-flight/finished request
  let translationLoad = null;

  /* ---- the text, once: paragraph -> sentences (raw text for markup, squashed for keys/sheets) ---- */
  const paragraphs = doc.blocks.map((block) => {
    if (block.type !== 'paragraph') return block;
    const sentences = sentencesOf(block.text).map((raw2, si) => ({ seg: segmentId(block.pi, si), raw: raw2, text: squash(raw2) }));
    return { ...block, sentences };
  });
  const sentenceBySeg = new Map();
  for (const block of paragraphs) if (block.type === 'paragraph') for (const s of block.sentences) sentenceBySeg.set(s.seg, s);
  const paragraphTexts = doc.paragraphs.map((p) => p.text);

  const stored = memory.value.continuation.find((entry) => entry.id === contentId);
  let furthestPercent = Number.isFinite(stored?.place?.within) ? stored.place.within : 0;
  // A finished text opens at its top; one in progress opens where it was left.
  let percent = furthestPercent >= 100 ? 0 : furthestPercent;

  function recordVisit(within) {
    memory.enter({
      id: contentId,
      title: doc.isBook ? doc.chapterTitle || doc.title : doc.title,
      context: doc.isBook ? doc.title : '',
      excerpt: excerptFrom(paragraphTexts, within ?? 0),
      place: placeFor2(doc.isBook ? 'book' : 'flat', {
        chapterIndex: doc.neighbours?.index ?? 0,
        chapterTotal: doc.chapters.length || 1,
        percent: within,
      }),
    });
  }
  recordVisit(Number.isFinite(stored?.place?.within) ? stored.place.within : null);

  /* ---- data on demand ---- */

  /* One request per paragraph, shared by every caller: two overlapping aids (word roles and
     pinyin) converge on the same fetch, and a caller that awaits it always finds its tokens. */
  function annotateParagraph(pi) {
    if (annotationLoads.has(pi)) return annotationLoads.get(pi);
    const promise = fetchAnnotations(pi);
    annotationLoads.set(pi, promise);
    return promise;
  }

  async function fetchAnnotations(pi) {
    const block = paragraphs.find((b) => b.type === 'paragraph' && b.pi === pi);
    if (!block || !block.sentences.length) return;
    try {
      const value = await api.annotateMediaText({ text: block.text.slice(0, 1200), source_language: language });
      const found = value?.annotations || [];
      let cursor = 0;
      for (const s of block.sentences) {
        const at = block.text.indexOf(s.raw, cursor);
        const start = at >= 0 ? at : cursor;
        const end = start + s.raw.length;
        cursor = end;
        annotations.set(
          s.seg,
          found
            .filter((tok) => Number.isInteger(tok?.start) && tok.start >= start && tok.end <= end)
            .map((tok) => ({ start: tok.start - start, end: tok.end - start, pos: tok.pos || '', pronunciation: tok.pronunciation || '' })),
        );
      }
    } catch {
      /* No tagger answer: this paragraph stays plain. */
    }
  }

  async function ensureAnnotations() {
    const pending = doc.paragraphs.map((p) => p.pi);
    let next = 0;
    const workers = Array.from({ length: Math.min(ANNOTATE_CONCURRENCY, pending.length) }, async () => {
      while (next < pending.length) await annotateParagraph(pending[next++]);
    });
    await Promise.all(workers);
  }

  /* Translation on request (D-130): every sentence still missing a meaning is asked for, in turns;
     the paragraphs show "loading" at once, fill in as turns answer, and a failure leaves a short
     retry line - never a "not available" dead end. The server caches each sentence, so asking again
     (here or in the Sentence Quick Sheet) never translates the same sentence twice. */
  function ensureTranslation() {
    if (translationLoad) return translationLoad;
    const target = support();
    if (!target || target === language) return null; // nothing to translate into: the aid is not offered
    // The paragraph being read first, then outwards from it, so the meaning the learner is looking
    // at arrives first (LEX-004).
    const here = Number(/^p(\d+)/.exec(readingAnchor()?.seg || '')?.[1] ?? 0);
    const paraOf = (seg) => Number(/^p(\d+)/.exec(seg)?.[1] ?? 0);
    const missing = [...sentenceBySeg.values()]
      .filter((s) => !translations.has(s.seg))
      .sort((a, b) => Math.abs(paraOf(a.seg) - here) - Math.abs(paraOf(b.seg) - here) || paraOf(a.seg) - paraOf(b.seg));
    if (!missing.length) {
      translationState = 'ready';
      return null;
    }
    translationState = 'loading';
    paintBody();
    translationLoad = (async () => {
      let failed = false;
      for (const turn of sentenceTurns(missing)) {
        try {
          const response = await api.readingTranslate({ source_language: language, target_language: target, content_id: contentId, segments: turn });
          for (const [seg, meaning] of sentenceTranslationsFrom(response)) translations.set(seg, meaning);
          if (response?.status !== 'ready') failed = true;
        } catch {
          failed = true;
        }
        if (!alive) return;
        paintBody();
      }
      translationState = failed ? 'failed' : 'ready';
      paintBody();
    })().finally(() => {
      translationLoad = null;
    });
    return translationLoad;
  }

  /* ---- notes and highlights (device memory) ---- */

  function notesFor(seg) {
    const s = sentenceBySeg.get(seg);
    if (!s || !storage) return [];
    try {
      return loadNotes(storage, owner, noteKeyFor(s.text, { ...source, segment: seg }));
    } catch {
      return [];
    }
  }

  /* Every note of the text in reading order, numbered as the frame numbers them (1, 2, 3... across
     the whole text), plus the number each sentence's marker shows (its first note's). */
  function collectNotes() {
    const all = [];
    const numBySeg = new Map();
    for (const block of paragraphs) {
      if (block.type !== 'paragraph') continue;
      for (const s of block.sentences) {
        for (const note of notesFor(s.seg)) {
          all.push({ note, seg: s.seg, sentence: s.text, num: all.length + 1 });
          if (!numBySeg.has(s.seg)) numBySeg.set(s.seg, all.length);
        }
      }
    }
    return { all, numBySeg };
  }

  const flat = (value) => String(value ?? '').replace(/\s+/g, ' ').trim();
  const highlighted = (seg) => {
    const s = sentenceBySeg.get(seg);
    return Boolean(s) && isHighlighted(highlights, seg, s.text);
  };

  /* ---- markup ---- */

  function toggleBtn(key, on, label, iconName) {
    return html`<button type="button" class="s-reader__toggle" data-act="toggle" data-key="${key}" data-on="${on ? 1 : 0}" aria-pressed="${on ? 'true' : 'false'}" aria-label="${label}" title="${label}">${raw(icon(iconName, { size: 17 }))}</button>`;
  }

  function pill(key, label, on, extra = '') {
    return html`<button type="button" class="${cls('s-reader__pill', extra)}" data-act="menu" data-key="${key}" data-on="${on ? 1 : 0}" aria-expanded="${menuOpen === key ? 'true' : 'false'}">${label}</button>`;
  }

  const KIND_LABEL = { article: 'kindArticle', book: 'kindBook', text: 'kindText' };
  const toolbarMetaText = () =>
    practice
      ? toolbarMeta({ author: t('practiceTitle'), level: doc.level, kindLabel: '', modeLabel: doc.minutes ? t('minutes', { n: doc.minutes }) : '', pageLabel: t('pageOf', pageOf(sentenceBySeg.size, percent)) })
      : toolbarMeta({
      isBook: doc.isBook,
      chapterTitle: doc.chapterTitle,
      author: doc.author,
      level: doc.level,
      chapterIndex: doc.neighbours?.index,
      chapterTotal: doc.neighbours?.total,
      kindLabel: t(KIND_LABEL[doc.kind] || 'kindText'),
      modeLabel: t('modeActive'),
      pageLabel: t('pageOf', pageOf(sentenceBySeg.size, percent)),
    });

  function toolbarMarkup() {
    const aids = aidsCount({ translation: translationOn, vocabLens: vocabLensOn, posLens: posOn });
    const meta = toolbarMetaText();
    const dark = theme() === 'dark';
    return html`<div class="s-reader__toolbar">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-act="back" aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-reader__titleblock"><div class="s-reader__title" lang="${langAttr(language)}">${doc.title}</div><div class="s-reader__meta" data-meta>${meta}</div></div>
      <div class="s-reader__tools">
        <button type="button" class="s-reader__pill s-reader__pill--aa" data-act="menu" data-key="aa" data-on="${menuOpen === 'aa' ? 1 : 0}" aria-expanded="${menuOpen === 'aa' ? 'true' : 'false'}" title="${t('readingAppearance')}">${t('aa')}</button>
        ${toggleBtn('theme', dark, t('themeDark'), 'moon')}
        ${toggleBtn('listen', listening, listening ? t('listenPause') : t('listen'), 'volume-2')}
        ${toggleBtn('bookmark', savedState.saved, t('saveLabel'), 'bookmark')}
        ${pill('aids', html`${t('aidsLabel')}${aids ? ` · ${aids}` : ''}`, menuOpen === 'aids' || translationOn || vocabLensOn || posOn)}
        ${practice ? '' : pill('more', '⋯', menuOpen === 'more' || notesOpen || summaryOpen, 's-reader__pill--more')}
      </div>
    </div>`;
  }

  function menuItem(key, label, { on = false, toggle = false } = {}) {
    return html`<button type="button" class="s-reader__menu-item" data-act="item" data-key="${key}" data-on="${on ? 1 : 0}"${toggle ? raw(` aria-pressed="${on ? 'true' : 'false'}"`) : ''}>${label}</button>`;
  }

  /* A Reading Aid as an icon toggle (D-131, LEX-009): the icon with a filled active state and a short
     caption under it on every breakpoint; the full name is the tooltip and the accessible name. */
  function aidToggle(key, iconName, label, caption, on) {
    return html`<button type="button" class="s-reader__aid" data-act="item" data-key="${key}" data-on="${on ? 1 : 0}" aria-pressed="${on ? 'true' : 'false'}" aria-label="${label}" title="${label}">${raw(icon(iconName, { size: 18 }))}<span class="s-reader__aid-caption" aria-hidden="true">${caption}</span></button>`;
  }

  function menuMarkup() {
    if (!menuOpen) return '';
    let items = '';
    if (menuOpen === 'aa') {
      items = html`<button type="button" class="s-reader__menu-item" data-act="item" data-key="aa-smaller" aria-label="${t('aaSmaller')}">A−</button><button type="button" class="s-reader__menu-item" data-act="item" data-key="aa-larger" aria-label="${t('aaLarger')}">A+</button><span class="s-reader__menu-item s-reader__menu-item--flat">${readerSizePx(settings.size)}px</span>`;
    } else if (menuOpen === 'aids') {
      const canTranslate = Boolean(support()) && support() !== language; // no aid that could only answer "nothing to translate"
      const lang = String(support() || '').toUpperCase();
      // Pinyin is offered only for a Chinese text: an aid that cannot apply is not shown (D-131).
      items = html`<div class="s-reader__aids" role="group" aria-label="${t('aidsLabel')}">${
        canTranslate ? aidToggle('translation', 'languages', t('translationAid', { lang }), t('aidShortTranslation', { lang }), translationOn) : ''
      }${aidToggle('vocab', 'scan-text', t('vocabLensAid'), t('aidShortLens'), vocabLensOn)}${aidToggle('pos', 'tags', t('wordRolesAid'), t('aidShortRoles'), posOn)}${
        isZh ? aidToggle('pinyin', 'case-lower', t('pinyinAid'), t('aidShortPinyin'), pinyinOn) : ''
      }</div>`;
    } else {
      items = html`${menuItem('notes', t('notesLabel', { n: collectNotes().all.length }), { on: notesOpen, toggle: true })}${menuItem('summary', t('summaryLabel'), { on: summaryOpen, toggle: true })}${menuItem(
        'save',
        savedState.saved ? t('savedLabel') : t('saveLabel'),
        { on: savedState.saved, toggle: true },
      )}${menuItem('discuss', shellCopy('discussion'))}${menuItem('respond', t('writeResponse'))}${menuItem('transfer', shellCopy('readingTransfer'))}`;
    }
    return html`<div class="s-reader__menu" role="group">${items}<span class="s-reader__menu-spacer"></span><button type="button" class="s-reader__menu-close" data-act="menu-close" aria-label="${shellCopy('close')}">${raw(icon('x', { size: 17 }))}</button></div>`;
  }

  function topMarkup() {
    return html`${toolbarMarkup()}${menuMarkup()}<div class="s-reader__progress" data-progress><span style="width:${percent}%"></span></div>`;
  }

  /* Pinyin above a Hanzi (frame 14's `data-py` over `data-hz`): a column of the reading over the
     character. With pinyin on, EVERY character of a Chinese text is such a column - punctuation and
     an unannotated run carry a blank reading - exactly as the frame builds them, so a line's
     characters share one baseline and one pitch. */
  function pystackMarkup(hanzi, syllable) {
    return html`<span class="s-reader__pystack"><span class="s-reader__py">${syllable || NBSP}</span><span>${hanzi}</span></span>`;
  }

  const stacked = () => pinyinOn && isZh;

  function plainMarkup(text) {
    if (!stacked()) return html`${text}`;
    return html`${Array.from(text).map((ch) => (/\s/.test(ch) ? ch : pystackMarkup(ch, '')))}`;
  }

  /* The learner's highlighted spans in one sentence, as [start, end) offsets into its text (LEX-013).
     A highlight of the whole sentence is the sentence's own `is-highlighted`, not a span. */
  function spanRanges(s, joined) {
    const whole = flat(s.text);
    const ranges = [];
    for (const item of highlights) {
      if (item.segment !== s.seg) continue;
      const text = flat(item.sentence);
      if (!text || text === whole) continue;
      const at = joined.indexOf(text);
      if (at >= 0) ranges.push([at, at + text.length]);
    }
    return ranges;
  }

  const inRanges = (ranges, i) => ranges.some(([a, b]) => i >= a && i < b);

  /* `text` starting at `start` in the sentence, with the highlighted characters marked. */
  function markedText(text, start, ranges) {
    if (!ranges.length) return text;
    const out = [];
    let run = '';
    let runOn = null;
    let i = start;
    for (const ch of Array.from(text)) {
      const on = inRanges(ranges, i);
      if (runOn !== null && on !== runOn) {
        out.push(runOn ? html`<mark class="s-reader__hl">${run}</mark>` : run);
        run = '';
      }
      run += ch;
      runOn = on;
      i += ch.length;
    }
    if (run) out.push(runOn ? html`<mark class="s-reader__hl">${run}</mark>` : run);
    return html`${out}`;
  }

  function stackMarked(hanzi, syllable, on) {
    return on ? html`<mark class="s-reader__hl">${pystackMarkup(hanzi, syllable)}</mark>` : pystackMarkup(hanzi, syllable);
  }

  function pieceMarkup(piece, seg, start = 0, ranges = []) {
    if (!piece.word) {
      if (!ranges.length) return plainMarkup(piece.text);
      if (!stacked()) return markedText(piece.text, start, ranges);
      let i = start;
      return html`${Array.from(piece.text).map((ch) => {
        const at = i;
        i += ch.length;
        return /\s/.test(ch) ? ch : stackMarked(ch, '', inRanges(ranges, at));
      })}`;
    }
    const role = piece.role;
    const isPicked = picked === `${seg}|${piece.text}`;
    const attrs = `${role ? ` data-role="${role}"` : ''}${piece.saved ? ' data-saved="1"' : ''}`;
    const chars = piece.pinyin.length ? piece.pinyin : Array.from(piece.text).map((h) => ({ h, p: '' }));
    let i = start;
    const inner = stacked()
      ? chars.map((c) => {
          const at = i;
          i += String(c.h).length;
          return ranges.length ? stackMarked(c.h, c.p, inRanges(ranges, at)) : pystackMarkup(c.h, c.p);
        })
      : markedText(piece.text, start, ranges);
    return html`<span class="${cls('s-reader__w', isPicked && 'is-picked')}" data-w="${piece.text}"${raw(attrs)}>${inner}</span>`;
  }

  function sentenceMarkup(s, numBySeg) {
    const tokens = annotations.get(s.seg);
    const saved = savedWords.get(s.text) || new Set();
    const pieces = segmentSentence(s.raw, tokens, { saved });
    const mark = numBySeg.get(s.seg);
    const ranges = spanRanges(s, pieces.map((piece) => piece.text).join(''));
    let offset = 0;
    return html`<span class="${cls('s-reader__sentence', highlighted(s.seg) && 'is-highlighted', selected?.seg === s.seg && 'is-selected')}" data-sentence data-segment="${s.seg}">${pieces.map((piece) => {
      const start = offset;
      offset += piece.text.length;
      return pieceMarkup(piece, s.seg, start, ranges);
    })}${
      mark ? html`<span class="s-reader__notemark">${mark}</span>` : ''
    }</span>${isZh ? '' : ' '}`;
  }

  function noteCard(entry) {
    const expanded = expandedNotes.has(entry.note.id);
    return html`<div class="s-reader__note" data-expanded="${expanded ? 1 : 0}">
      <button type="button" class="s-reader__note-head" data-act="note-toggle" data-id="${entry.note.id}" aria-expanded="${expanded ? 'true' : 'false'}" title="${expanded ? t('noteCollapse') : t('noteExpand')}">
        <span class="s-reader__note-num">${entry.num}</span>
        <span class="s-reader__note-body"><span class="s-reader__note-label">${t('yourNote', { when: relativeWhen(entry.note.at, languages().ui) })}</span><span class="s-reader__note-text">${entry.note.text}</span></span>
        <span class="s-reader__note-chev">${raw(icon('chevron-down', { size: 16, stroke: 2.2 }))}</span>
      </button>
      ${expanded
        ? html`<div class="s-reader__note-expanded"><div class="s-reader__note-src" lang="${langAttr(language)}">“${entry.sentence}”</div><button type="button" class="s-reader__note-edit" data-act="note-edit" data-seg="${entry.seg}">${t('editInSentence')}</button></div>`
        : ''}
    </div>`;
  }

  function blockMarkup(block, notes) {
    if (block.type === 'break') return html`<hr class="s-reader__break">`;
    if (block.type === 'heading') return html`<h2 class="s-reader__heading" lang="${langAttr(language)}">${block.text}</h2>`;
    const cards = notes.all.filter((entry) => sentenceBySeg.get(entry.seg) && block.sentences.some((s) => s.seg === entry.seg));
    return html`<div>
      <p class="s-reader__paragraph" lang="${langAttr(language)}" data-tl="${isZh ? 'zh' : ''}">${block.sentences.map((s) => sentenceMarkup(s, notes.numBySeg))}</p>
      ${cards.length ? html`<div class="s-reader__notes">${cards.map(noteCard)}</div>` : ''}
      ${translationOn ? translationMarkup(block) : ''}
    </div>`;
  }

  function translationMarkup(block) {
    const meaning = paragraphMeaning(block.sentences.map((s) => s.seg), translations, support());
    if (meaning) return html`<p class="s-reader__translation" lang="${langAttr(support())}">${meaning}</p>`;
    // LEX-004: a visible placeholder in each paragraph's own slot while its meaning is asked for,
    // sized like a short translation so the text below moves little when it arrives.
    if (translationState === 'loading') return html`<div class="s-reader__translation s-reader__translation--pending" role="status" aria-label="${t('translationLoading')}"><span class="o-bone"></span><span class="o-bone"></span></div>`;
    if (translationState === 'failed') {
      return html`<p class="s-reader__translation s-reader__translation--state">${t('translationFailed')} <button type="button" class="s-reader__retry" data-act="translation-retry">${t('retry')}</button></p>`;
    }
    return '';
  }

  function endMarkup() {
    const info = endOfContent({ isBook: doc.isBook, hasQuiz, hasNextChapter: Boolean(doc.neighbours?.next), chapterNumber: (doc.neighbours?.index ?? 0) + 1 });
    return html`<div class="s-reader__end">
      ${doc.isBook
        ? html`<div class="s-reader__chapters-row"><span class="s-reader__chapters-label">${t('chapters')}</span>${doc.chapters.map(
            (chapter, i) => html`<button type="button" class="s-reader__chapter" data-act="chapter" data-id="${chapter.id}" aria-current="${chapter.id === doc.chapterId ? 'true' : 'false'}" title="${chapter.title}">${i + 1}</button>`,
          )}</div>`
        : ''}
      <div class="s-reader__endnote">${practice ? t('endNotePractice', { n: quizSize }) : t(info.endNoteKey, info.endNoteParams)}</div>
      <div class="s-reader__cta-row">
        <button type="button" class="s-reader__cta-primary" data-act="end-primary">${info.primaryIsCheck ? shellCopy('checkUnderstanding') : t('markAsFinished')}</button>
        ${info.secondaryHas && !practice ? html`<button type="button" class="s-reader__cta-secondary" data-act="end-secondary">${t('markAsFinished')}</button>` : ''}
        ${info.hasNextChapter ? html`<button type="button" class="s-reader__cta-next" data-act="end-next">${t('nextChapterCta')}</button>` : ''}
      </div>
    </div>`;
  }

  function legendMarkup() {
    if (!posOn) return '';
    return html`<div class="s-reader__poslegend">${ROLES.map(
      (role) => html`<span class="s-reader__poslegend-item"><span class="s-reader__poslegend-swatch" data-role="${role}"></span>${t(ROLE_KEY[role])}</span>`,
    )}<span class="s-reader__poslegend-hint">${t('posLegendHint')}</span></div>`;
  }

  /* The rows of "Notes & highlights", in reading order. */
  function panelRows() {
    const notes = collectNotes().all;
    const rows = notes.map((entry) => ({ seg: entry.seg, kind: entry.note.type, text: entry.note.text, sentence: entry.sentence }));
    for (const item of highlights) {
      const s = sentenceBySeg.get(item.segment);
      if (s && flat(item.sentence)) rows.push({ seg: item.segment, kind: 'highlight', text: flat(item.sentence), sentence: '' });
    }
    const order = (seg) => {
      const m = /^p(\d+)s(\d+)$/.exec(seg);
      return m ? Number(m[1]) * 100000 + Number(m[2]) : 0;
    };
    return rows.sort((a, b) => order(a.seg) - order(b.seg));
  }

  const TYPE_KEY = { factual: 'typeFactual', reflection: 'typeReflection', question: 'typeQuestion', highlight: 'typeHighlight' };

  function panelBodyMarkup() {
    const rows = panelRows();
    if (!rows.length) return html`<div class="s-reader__aside-empty">${t('noNotesYet')}</div>`;
    return html`<div class="s-reader__notelist">${rows.map(
      (row) => html`<button type="button" class="s-reader__notelist-row" data-act="note-open" data-seg="${row.seg}"><div class="s-reader__notelist-type" style="color:${row.kind === 'highlight' ? 'var(--green)' : noteTypeColorKey(row.kind)}">${t(TYPE_KEY[row.kind] || 'typeFactual')}</div><div class="s-reader__notelist-text" ${row.kind === 'highlight' ? raw(`lang="${langAttr(language)}"`) : ''}>${row.text}</div>${
        row.sentence ? html`<div class="s-reader__notelist-src" lang="${langAttr(language)}">“${row.sentence}”</div>` : ''
      }</button>`,
    )}</div>`;
  }

  /* The frame's Summary panel: title, "Generated on request", the bullets, and its closing line. */
  function summaryBodyMarkup() {
    if (summary.state === 'ready') {
      return html`<ul class="s-reader__summary" lang="${langAttr(support())}">${summary.bullets.map((line) => html`<li>${line}</li>`)}</ul><div class="s-reader__aside-foot">${t('summaryStays')}</div>`;
    }
    if (summary.state === 'failed') {
      return html`<div class="s-reader__aside-empty">${t('summaryFailed')} <button type="button" class="s-reader__retry" data-act="summary-retry">${t('retry')}</button></div>`;
    }
    return html`<div class="s-reader__aside-empty" role="status"><span class="o-spinner"></span> ${t('summaryLoading')}</div>`;
  }

  function summaryHeadMarkup() {
    return html`<div class="s-reader__aside-head"><div class="s-reader__aside-title">${t('summaryLabel')}</div><span class="s-reader__aside-tag">${t('summaryGenerated')}</span></div>`;
  }

  function asideMarkup() {
    if (device() === 'mobile') return '';
    if (summaryOpen) return html`<aside class="s-reader__aside" data-aside>${summaryHeadMarkup()}${summaryBodyMarkup()}</aside>`;
    if (!notesOpen) return '';
    return html`<aside class="s-reader__aside" data-aside><div class="s-reader__aside-title">${t('notesHighlights')}</div>${panelBodyMarkup()}</aside>`;
  }

  /* Asked for only when the learner opens Summary, never on opening the text (D-130). */
  async function loadSummary() {
    if (summary.state === 'loading' || summary.state === 'ready') return;
    summary = { state: 'loading', bullets: [] };
    paintBody();
    if (summarySheet) refreshSummarySheet();
    const target = support() || 'en';
    const which = doc.kind === 'article' ? { article_id: doc.id } : doc.isBook ? { book_id: doc.bookId, chapter_id: doc.chapterId } : { text: paragraphTexts.join('\n\n') };
    try {
      const value = await api.readingSummary({ source_language: language, target_language: target, ...which });
      const bullets = Array.isArray(value?.bullets) ? value.bullets.map((line) => String(line || '').trim()).filter(Boolean) : [];
      summary = bullets.length ? { state: 'ready', bullets } : { state: 'failed', bullets: [] };
    } catch {
      summary = { state: 'failed', bullets: [] };
    }
    if (!alive) return;
    paintBody();
    if (summarySheet) refreshSummarySheet();
  }

  function seltbMarkup() {
    if (!selected || sheetOpen) return '';
    const on = isHighlighted(highlights, selected.seg, selected.span || selected.text);
    const button = (act, iconName, label) =>
      html`<button type="button" class="s-reader__seltb-btn" data-act="${act}" aria-label="${label}">${raw(icon(iconName, { size: 17 }))}<span class="s-reader__seltb-label">${label}</span></button>`;
    return html`<div class="s-reader__seltb" role="toolbar" aria-label="${(selected.span || selected.text).slice(0, 80)}">
      ${button('sel-translate', 'languages', t('selTranslate'))}
      ${button('sel-highlight', 'highlighter', on ? t('selHighlighted') : t('selHighlight'))}
      ${button('sel-note', 'pen-line', t('selNote'))}
      <button type="button" class="s-reader__seltb-ask" data-act="sel-ask">${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${shellCopy('askOrena')}</button>
      <button type="button" class="s-reader__seltb-close" data-act="sel-close" aria-label="${shellCopy('close')}">${raw(icon('x', { size: 16 }))}</button>
    </div>`;
  }

  /* ---- painting ---- */

  const skeleton = html`<div class="s-reader"><div class="s-reader__top" data-part="top"></div><div class="s-reader__scroll" data-scroll-region data-part="scroll"><div data-part="grid"></div></div><div data-part="seltb"></div></div>`;
  mount(element, skeleton);
  const topEl = element.querySelector('[data-part="top"]');
  const scrollEl = element.querySelector('[data-part="scroll"]');
  const gridEl = element.querySelector('[data-part="grid"]');
  const seltbEl = element.querySelector('[data-part="seltb"]');

  function paintTop() {
    if (!alive) return;
    mount(topEl, topMarkup());
  }

  /* The sentence at the top of the reading region, and how far below the region's top it sits: a
     repaint (a translation arriving, a note, an aid) keeps that sentence where it was (LEX-004). */
  function readingAnchor() {
    const top = scrollEl.getBoundingClientRect().top;
    for (const el of scrollEl.querySelectorAll('[data-sentence]')) {
      const box = el.getBoundingClientRect();
      if (box.bottom > top + 1) return { seg: el.dataset.segment, offset: box.top - top };
    }
    return null;
  }

  function restoreAnchor(anchor) {
    if (!anchor) return;
    const el = scrollEl.querySelector(`[data-sentence][data-segment="${anchor.seg}"]`);
    if (!el) return;
    const shift = el.getBoundingClientRect().top - scrollEl.getBoundingClientRect().top - anchor.offset;
    if (Math.abs(shift) > 0.5) scrollEl.scrollTop += shift;
  }

  function paintBody() {
    if (!alive) return;
    const top = scrollEl.scrollTop;
    const anchor = top > 0 ? readingAnchor() : null;
    const notes = collectNotes();
    const split = (notesOpen || summaryOpen) && device() !== 'mobile';
    mount(
      gridEl,
      html`<div class="${cls('s-reader__grid', split && 's-reader__grid--split')}">
        <article class="s-reader__article" style="font-size:${readerSizePx(settings.size)}px"${raw(`${posOn ? ' data-pos="1"' : ''}${vocabLensOn ? ' data-lens="1"' : ''}`)}>
          ${legendMarkup()}
          ${paragraphs.map((block) => blockMarkup(block, notes))}
          ${endMarkup()}
        </article>
        ${asideMarkup()}
      </div>`,
    );
    scrollEl.scrollTop = top;
    restoreAnchor(anchor);
  }

  function paintSel() {
    if (!alive) return;
    mount(seltbEl, seltbMarkup());
    for (const el of element.querySelectorAll('.s-reader__sentence.is-selected')) el.classList.remove('is-selected');
    if (selected) element.querySelector(`[data-sentence][data-segment="${selected.seg}"]`)?.classList.add('is-selected');
  }

  function paintAll() {
    paintTop();
    paintBody();
    paintSel();
  }

  /* ---- selection ---- */

  /* `span` is the text the learner dragged across (frame 14's `selText`): the actions keep that exact
     span; the sentence around it is its context. A tap, or a drag over the whole sentence, has none. */
  function select(seg, span = '') {
    const s = sentenceBySeg.get(seg);
    if (!s) return;
    const own = flat(span);
    selected = { seg, text: s.text, span: own && own !== flat(s.text) && flat(s.text).includes(own) ? own : '' };
    paintSel();
  }

  function clearSelection() {
    selected = null;
    try {
      window.getSelection?.()?.removeAllRanges();
    } catch {
      /* Nothing to clear. */
    }
    paintSel();
  }

  const unitOf = (node) => (node?.closest ? node.closest('[data-sentence]') : null);

  function onSheetOpen() {
    sheetOpen = true;
    paintSel();
  }
  async function onWordSheetClose() {
    sheetOpen = false;
    paintSel();
    // A word kept from the sheet is one of "the words kept from this text": read it back.
    const fresh = await loadSavedFromText(doc);
    if (!alive || !fresh) return;
    if (JSON.stringify([...fresh.bySentence].map(([k, v]) => [k, [...v].sort()])) !== JSON.stringify([...savedWords].map(([k, v]) => [k, [...v].sort()]))) {
      savedWords = fresh.bySentence;
      paintBody();
    }
  }
  function onSentenceSheetClose() {
    sheetOpen = false;
    paintSel();
  }

  function openWord(word, seg) {
    const s = sentenceBySeg.get(seg);
    if (!s) return;
    stopSpeech();
    openWordSheet(ctx, { word, lang: language, sentence: s.text, source: { ...source, segment: seg }, onOpen: onSheetOpen, onClose: onWordSheetClose });
  }

  async function openSentence(tab) {
    if (!selected) return;
    const s = sentenceBySeg.get(selected.seg);
    if (!s) return;
    stopSpeech();
    const handle = await openSentenceSheet(ctx, {
      sentence: s.text,
      focus: selected.span,
      lang: language,
      source: { ...source, segment: s.seg },
      onOpen: onSheetOpen,
      onClose: onSentenceSheetClose,
      // A note or a highlight saved from the sheet (its "Save highlight") shows in the text at once.
      onNote: () => {
        if (storage) highlights = loadHighlights(storage, owner, contentId);
        paintBody();
        paintTop();
      },
    });
    // The sheet has no initial-tab option (kit request): the Note tab is reached by its own button.
    if (tab && handle?.element) handle.element.querySelector(`[data-tab="${tab}"]`)?.click();
  }

  function onTapWord({ word, unit }) {
    const seg = unit.dataset.segment;
    const piece = segmentSentence(sentenceBySeg.get(seg)?.raw || '', annotations.get(seg)).find((p) => p.word && p.text === word);
    if (posOn && piece?.role) {
      picked = `${seg}|${word}`;
      paintBody();
      toast(roleToast(word, t(ROLE_KEY[piece.role]), t(ROLE_HELP_KEY[piece.role])), { iconName: 'info' });
      return;
    }
    openWord(word, seg);
  }

  function onTapSentence({ unit }) {
    const seg = unit.dataset.segment;
    if (selected?.seg === seg && !sheetOpen) clearSelection();
    else select(seg);
  }

  function onSelect({ unit, text }) {
    select(unit.dataset.segment, text);
  }

  function toggleSelectedHighlight() {
    if (!selected || !storage) return;
    const s = sentenceBySeg.get(selected.seg);
    if (!s) return;
    const result = toggleHighlight(storage, owner, contentId, { segment: s.seg, sentence: selected.span || s.text });
    if (!result.on) for (const gone of highlights) if (!result.list.some((item) => item.id === gone.id)) noteRemoved(contentId, gone.id);
    highlights = result.list;
    scheduleAnnotationPush(storage, owner, contentId);
    try {
      window.getSelection?.()?.removeAllRanges();
    } catch {
      /* Nothing to clear. */
    }
    paintBody();
    paintSel();
    if (notesSheet) refreshNotesSheet();
  }

  function askAboutSelection() {
    if (!selected) return;
    const s = sentenceBySeg.get(selected.seg);
    if (!s) return;
    const text = selected.span || s.text;
    clearSelection();
    stopSpeech();
    askOrena({
      surface: 'reading.workspace',
      activity_type: 'reading',
      content_id: contentId,
      selected_item: { type: 'sentence', id: s.seg, text },
    });
  }

  /* ---- Notes & highlights on a phone: the design's bottom sheet ---- */

  function notesSheetMarkup(handleTitle) {
    return html`${sheetHead({ title: handleTitle, closeLabel: shellCopy('close') })}<div class="o-sheet__body">${panelBodyMarkup()}</div>`;
  }

  function refreshNotesSheet() {
    if (!notesSheet) return;
    fillSheet(notesSheet.element, notesSheet, notesSheetMarkup(t('notesHighlights')));
  }

  function openNotesSheet() {
    notesOpen = true;
    notesSheet = openSheet({
      label: t('notesHighlights'),
      render(sheetEl, handle) {
        notesSheet = handle;
        fillSheet(sheetEl, handle, notesSheetMarkup(t('notesHighlights')));
        sheetEl.addEventListener('click', onSheetClick);
      },
      onClose() {
        notesSheet = null;
        notesOpen = false;
        if (alive) paintTop();
      },
    });
  }

  let summarySheet = null;
  function refreshSummarySheet() {
    if (!summarySheet) return;
    fillSheet(summarySheet.element, summarySheet, html`${sheetHead({ title: t('summaryLabel'), closeLabel: shellCopy('close') })}<div class="o-sheet__body"><span class="s-reader__aside-tag">${t('summaryGenerated')}</span>${summaryBodyMarkup()}</div>`);
  }
  function openSummarySheet() {
    summaryOpen = true;
    summarySheet = openSheet({
      label: t('summaryLabel'),
      render(sheetEl, handle) {
        summarySheet = handle;
        refreshSummarySheet();
        sheetEl.addEventListener('click', (event) => {
          if (event.target.closest?.('[data-act="summary-retry"]')) loadSummary();
        });
      },
      onClose() {
        summarySheet = null;
        summaryOpen = false;
        if (alive) paintTop();
      },
    });
  }

  function closeNotes() {
    notesOpen = false;
    if (notesSheet) notesSheet.close();
    paintTop();
    paintBody();
  }

  function scrollToSentence(seg) {
    const target = scrollEl.querySelector(`[data-sentence][data-segment="${seg}"]`);
    if (!target) return;
    const top = target.getBoundingClientRect().top - scrollEl.getBoundingClientRect().top + scrollEl.scrollTop - 120;
    scrollEl.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  }

  function openNoteFor(seg) {
    scrollToSentence(seg);
    select(seg);
    if (notesSheet) notesSheet.close();
    // The frame opens the sentence's own sheet on its Note tab.
    queueMicrotask(() => openSentence('Note'));
  }

  /* ---- read-aloud (the browser's own speech synthesis) ---- */

  function stopSpeech() {
    if (!listening) return;
    listening = false;
    try {
      window.speechSynthesis?.cancel();
    } catch {
      /* No speech to cancel. */
    }
    if (alive) paintTop();
  }

  function canSpeak() {
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') return false;
    const voices = window.speechSynthesis.getVoices?.() || [];
    if (!voices.length) return true; // voices load lazily: try
    const wanted = isZh ? 'zh' : 'en';
    return voices.some((voice) => String(voice.lang || '').toLowerCase().startsWith(wanted));
  }

  function toggleListen() {
    if (listening) {
      stopSpeech();
      toast(t('listenStopped'), { iconName: 'volume-2' });
      return;
    }
    if (!canSpeak()) {
      toast(t('listenUnavailable'), { iconName: 'info' });
      return;
    }
    const start = Math.min(paragraphTexts.length - 1, Math.max(0, Math.floor((percent / 100) * paragraphTexts.length)));
    const queue = paragraphTexts.slice(start);
    try {
      window.speechSynthesis.cancel();
      queue.forEach((text, index) => {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = isZh ? 'zh-CN' : 'en-US';
        if (index === queue.length - 1) {
          utterance.onend = () => {
            if (!alive || !listening) return;
            listening = false;
            paintTop();
          };
        }
        utterance.onerror = () => {
          if (!alive || !listening) return;
          listening = false;
          paintTop();
        };
        window.speechSynthesis.speak(utterance);
      });
    } catch {
      toast(t('listenUnavailable'), { iconName: 'info' });
      return;
    }
    listening = true;
    paintTop();
    toast(t('listenStarted'), { iconName: 'volume-2' });
  }

  /* ---- bookmark ---- */

  async function setSaved(next) {
    const memoryId = contentIdFor('text', doc.id);
    if (doc.kind === 'text') {
      if (memory.value.kept.includes(memoryId) !== next) memory.keep(memoryId);
      savedState = { saved: memory.value.kept.includes(memoryId), itemId: '' };
      return;
    }
    const libKind = doc.kind === 'article' ? 'reading' : 'book';
    const sourceId = doc.isBook ? doc.bookId : doc.id;
    if (!next && savedState.itemId) {
      await api.libraryItemDelete(savedState.itemId).catch(() => {});
      savedState = { saved: false, itemId: '' };
    } else if (next) {
      const result = await api.libraryKeep({ kind: libKind, source_id: sourceId }).catch(() => null);
      if (result?.item) savedState = { saved: true, itemId: result.item.id };
    }
  }

  async function toggleBookmark() {
    const was = savedState.saved;
    await setSaved(!was);
    if (!alive) return;
    paintTop();
    if (savedState.saved === was) {
      // The library did not take the change: say so, in the toast the design already draws.
      toast(t('saveFailed'), { iconName: 'info' });
      return;
    }
    if (savedState.saved) {
      toast(t('savedToast'), {
        undo: async () => {
          await setSaved(false);
          if (alive) paintTop();
        },
        undoLabel: shellCopy('undo'),
      });
    } else toast(t('removedToast'), { iconName: 'check' });
  }

  /* ---- actions ---- */

  function goTo(routeId, params = { id: contentId }) {
    stopSpeech();
    ctx.go(ctx.href(routeId, params));
  }

  function finish() {
    // "Mark as finished" is the learner's own word that they read it: the record says so.
    furthestPercent = 100;
    recordVisit(100);
    goTo('rcomplete');
  }

  async function onItem(key) {
    if (key === 'aa-smaller' || key === 'aa-larger') {
      settings = { ...settings, size: steppedSize(settings.size, key === 'aa-smaller' ? -1 : 1) };
      writeReaderSettings(settings);
      paintTop();
      paintBody();
      return;
    }
    if (key === 'translation') {
      translationOn = !translationOn;
      paintTop();
      if (translationOn) {
        paintBody();
        await ensureTranslation();
      } else paintBody();
      return;
    }
    if (key === 'vocab') {
      vocabLensOn = !vocabLensOn;
      paintTop();
      paintBody();
      return;
    }
    if (key === 'pos') {
      posOn = !posOn;
      if (!posOn) picked = '';
      paintTop();
      if (posOn) await ensureAnnotations();
      paintBody();
      return;
    }
    if (key === 'pinyin') {
      pinyinOn = !pinyinOn;
      paintTop();
      if (pinyinOn) await ensureAnnotations();
      paintBody();
      return;
    }
    if (key === 'notes') {
      menuOpen = '';
      summaryOpen = false;
      if (summarySheet) summarySheet.close();
      if (notesOpen) closeNotes();
      else if (device() === 'mobile') {
        paintTop();
        openNotesSheet();
      } else {
        notesOpen = true;
        paintTop();
        paintBody();
      }
      return;
    }
    if (key === 'summary') {
      menuOpen = '';
      if (summaryOpen) {
        summaryOpen = false;
        if (summarySheet) summarySheet.close();
        paintTop();
        paintBody();
        return;
      }
      notesOpen = false;
      if (notesSheet) notesSheet.close();
      if (device() === 'mobile') {
        paintTop();
        openSummarySheet();
      } else {
        summaryOpen = true;
        paintTop();
        paintBody();
      }
      loadSummary();
      return;
    }
    if (key === 'save') {
      await toggleBookmark();
      paintTop();
      return;
    }
    if (key === 'discuss') goTo('discussion');
    else if (key === 'respond') goTo('respond');
    else if (key === 'transfer') goTo('rtransfer');
  }

  function onSheetClick(event) {
    const target = event.target.closest?.('[data-act]');
    if (!target) return;
    if (target.dataset.act === 'note-open') openNoteFor(target.dataset.seg);
  }

  function onClick(event) {
    const target = event.target.closest?.('[data-act]');
    if (!target || !element.contains(target)) return;
    const { act, key, id, seg } = target.dataset;
    if (act === 'back') {
      stopSpeech();
      ctx.back();
    } else if (act === 'menu') {
      menuOpen = menuOpen === key ? '' : key;
      paintTop();
    } else if (act === 'menu-close') {
      menuOpen = '';
      paintTop();
    } else if (act === 'item') onItem(key);
    else if (act === 'toggle') {
      if (key === 'theme') toggleAppearance();
      else if (key === 'listen') toggleListen();
      else if (key === 'bookmark') toggleBookmark();
    } else if (act === 'chapter') {
      if (id !== doc.chapterId) goTo('reader', { id: contentIdFor('book', `${doc.bookId}:${id}`) });
    } else if (act === 'end-primary') {
      if (hasQuiz) {
        stopSpeech();
        ctx.go(ctx.href('checku', { id: contentId }, practice ? { mode: 'practice' } : {}));
      } else finish();
    } else if (act === 'end-secondary') finish();
    else if (act === 'end-next') {
      const next = doc.neighbours?.next;
      if (next) goTo('reader', { id: contentIdFor('book', `${doc.bookId}:${next.id}`) });
    } else if (act === 'note-toggle') {
      if (expandedNotes.has(id)) expandedNotes.delete(id);
      else expandedNotes.add(id);
      paintBody();
    } else if (act === 'note-edit') openNoteFor(seg);
    else if (act === 'note-open') openNoteFor(seg);
    else if (act === 'sel-translate') openSentence('Translation');
    else if (act === 'sel-note') openSentence('Note');
    else if (act === 'sel-highlight') toggleSelectedHighlight();
    else if (act === 'sel-ask') askAboutSelection();
    else if (act === 'sel-close') clearSelection();
    else if (act === 'translation-retry') ensureTranslation();
    else if (act === 'summary-retry') {
      summary = { state: 'idle', bullets: [] };
      loadSummary();
    }
  }
  element.addEventListener('click', onClick);

  /* ---- position ---- */

  /* Where the learner is, from the reading region's own scroll: the bar and the toolbar's second
     line follow it, and the furthest point ever reached is what the device remembers. */
  function syncPosition() {
    if (!alive || !ctx.isCurrent()) return;
    percent = percentFromScroll(scrollEl.scrollTop, scrollEl.scrollHeight, scrollEl.clientHeight);
    const bar = element.querySelector('[data-progress] > span');
    if (bar) bar.style.width = `${percent}%`;
    const meta = element.querySelector('[data-meta]');
    if (meta) mount(meta, toolbarMetaText());
    const next = furthest(furthestPercent, percent);
    if (next > furthestPercent) {
      furthestPercent = next;
      recordVisit(next);
    }
  }

  let scrollTimer = 0;
  function onScroll() {
    clearTimeout(scrollTimer);
    scrollTimer = window.setTimeout(syncPosition, 200);
  }

  /* ---- boot ---- */

  if (isZh) await ensureAnnotations();
  if (!ctx.isCurrent()) return undefined;
  paintAll();

  const restore = () => {
    if (!alive || scrollEl.scrollTop > 0) return;
    scrollEl.scrollTop = scrollTopFor(furthestPercent >= 100 ? 0 : furthestPercent, scrollEl.scrollHeight, scrollEl.clientHeight);
  };
  restore();
  syncPosition();

  /* "Show in text" from Check Understanding (cuShowInText): the evidence sentence is brought into
     view and opened in its Sentence Quick Sheet. */
  const evidence = squash(ctx.query?.get?.('evidence') || '');
  if (evidence) {
    const hit = [...sentenceBySeg.values()].find((s) => s.text.includes(evidence) || evidence.includes(s.text));
    if (hit) {
      scrollEl.scrollTop = 0;
      requestAnimationFrame(() => {
        scrollToSentence(hit.seg);
        select(hit.seg);
        openSentence('Translation');
      });
    }
  }
  document.fonts?.ready?.then(() => {
    restore();
    syncPosition();
  }).catch(() => {});

  scrollEl.addEventListener('scroll', onScroll, { passive: true });
  const lexical = mountReaderLexical({ root: scrollEl, unitOf, onTapWord, onTapSentence, onSelect });
  let lastDevice = device();
  const releaseDevice = onDeviceChange(({ device: now }) => {
    // The theme toggle's pressed state follows the device's theme; a desk/phone change moves the
    // Notes panel between its docked form and the bottom sheet.
    paintTop();
    if (now === lastDevice) return;
    lastDevice = now;
    if (notesSheet) notesSheet.close();
    notesOpen = false;
    paintTop();
    paintBody();
  });

  // The notes and highlights the account holds for this text arrive on this device too (D4 I10).
  pullIntoDevice(storage, owner, contentId)
    .then((changed) => {
      if (!changed || !alive) return;
      highlights = loadHighlights(storage, owner, contentId);
      paintBody();
    })
    .catch(() => {});

  return () => {
    alive = false;
    clearTimeout(scrollTimer);
    try {
      window.speechSynthesis?.cancel();
    } catch {
      /* Nothing speaking. */
    }
    lexical();
    releaseDevice();
    scrollEl.removeEventListener('scroll', onScroll);
    element.removeEventListener('click', onClick);
    if (notesSheet) notesSheet.close();
  };
}
