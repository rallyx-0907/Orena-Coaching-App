/* Word Detail (frame 22, `#/word/:id`; D-091). The saved-word reference page: the word card
   (pronunciation, meaning, example, mastery footer), real context clips from the listening
   catalogue, the Deep Word explanation, mastery evidence, and - for a Chinese headword - the
   Stroke Practice sheet (frame 60). Every binding maps to a real answer (`POST
   /api/dictionary/word-detail`, `GET /api/library/vocabulary`, `.../clips`, `.../audio`,
   `/api/chinese/stroke-order`); a field none of them carries is left out (rule 40), never
   invented. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { loadingMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { openSheet } from '../../kit/overlay.js';
import { masteryBars, rowBadge } from '../../kit/components.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { t } from './copy.js';
import {
  contextFor,
  mapWordCard,
  mapDeepWord,
  mapClips,
  mapMasteryEvidence,
  restorePayload,
  savePayload,
  cardLanguage,
  posLabel,
} from './model.js';
import { mountStrokeSheet } from './stroke-sheet.js';

async function fetchItem(word) {
  try {
    const page = await api.libraryVocabulary({ query: word, limit: 5, order: 'word' });
    const norm = String(word).trim().toLowerCase();
    return (page?.items || []).find((row) => String(row.word || '').trim().toLowerCase() === norm) || null;
  } catch {
    return null;
  }
}

function sourceNoteKey(kind) {
  const map = {
    dictionary: 'sourceKindDictionary',
    feedback: 'sourceKindFeedback',
    strength: 'sourceKindStrength',
    reading: 'sourceKindReading',
    feed: 'sourceKindFeed',
    collection: 'sourceKindCollection',
  };
  return map[kind] || '';
}

function evidenceRow(row) {
  const notes = {
    evidenceReviewed: t('evidenceReviewedLabel'),
    evidenceMissed: t('evidenceMissedLabel'),
    evidenceRecalled: t('evidenceRecalledLabel'),
    evidenceSaved: t('evidenceSavedLabel'),
  };
  const label = notes[row.key] || '';
  const parts = [];
  if (row.date) parts.push(new Date(row.date).toLocaleDateString(languages().ui));
  if (row.n) parts.push(row.key === 'evidenceMissed' ? t.plural('evidenceMissedCount', row.n) : t.plural('evidenceRecalledCount', row.n));
  const sourceKey = sourceNoteKey(row.source);
  if (sourceKey) parts.push(t(sourceKey));
  return html`<div class="s-word-evidence">
    ${rowBadge({ glyph: row.glyph, bg: row.bg, size: 20 })}
    <div class="s-word-evidence__body"><div class="s-word-evidence__label">${label}</div><div class="s-word-evidence__note">${parts.join(' · ')}</div></div>
  </div>`;
}

function clipRow(clip, index) {
  return html`<div class="s-word-clip">
    <button type="button" class="s-word-clip__play" data-clip-play="${index}" aria-label="${t('playClip')}">${raw(icon('play', { size: 14 }))}</button>
    <div class="s-word-clip__body"><div class="s-word-clip__text">${clip.text}</div><div class="s-word-clip__source">${clip.source}</div></div>
    <button type="button" class="s-word-clip__open" data-clip-open="${index}">${t('open')}</button>
  </div>`;
}

function deepWordMarkup(rows) {
  if (!rows.length) return '';
  return html`<details class="s-word-panel s-word-deep">
    <summary class="s-word-panel__title">${t('deepWordTitle')}</summary>
    <div class="s-word-deep__rows">
      ${rows.map((row) => html`<div class="s-word-deep__row"><b>${t(row.key)}</b> · ${row.value}</div>`)}
    </div>
  </details>`;
}

/* languages-4 (2): the pos chip's closed-space translation, honest about what it could not
   translate (model.js#posLabel's own comment) - an unmapped value is marked `lang="en"` as
   untranslated content metadata rather than shown as if it were interface copy. */
function posMarkup(pos) {
  if (!pos) return '';
  const label = posLabel(pos, t);
  return html`<span class="o-tag"${label.known ? '' : raw(` lang="${langAttr('en')}"`)}>${label.text}</span>`;
}

function cardMarkup(card, strokeTiles) {
  const cardLang = cardLanguage(card.script);
  const meta = [
    card.ipa ? html`<span class="s-word-card__ipa">${card.ipa}</span>` : '',
    posMarkup(card.pos),
    card.hasLevel ? html`<span class="o-tag s-word-card__level">${card.level}</span>` : '',
  ];
  const footer = [];
  if (card.hasSchedule) {
    footer.push(html`<span class="s-word-card__bars">${masteryBars({ filled: card.filled, total: 4 })}</span>`);
    if (card.stageKey) footer.push(html`<span class="s-word-card__stage">${t(card.stageKey)}</span>`);
    if (card.due) footer.push(html`<span class="s-word-card__due">· ${card.due.key === 'dueToday' ? t('dueToday') : t.plural('dueInDays', card.due.n)}</span>`);
  }
  return html`<div class="s-word-card">
    <div class="s-word-card__top">
      <div class="s-word-card__id">
        <div class="s-word-card__word" lang="${langAttr(cardLang)}">${card.word}</div>
        <div class="s-word-card__meta">${meta}</div>
      </div>
      <div class="s-word-card__actions">
        <button type="button" class="s-word-icon s-word-icon--play" data-play aria-label="${t('playWord')}">${raw(icon('volume-2', { size: 19 }))}</button>
        <button type="button" class="s-word-icon" data-save style="background:${card.savedBg};color:${card.savedColor}" aria-label="${t(card.saved ? 'unsaveWord' : 'saveWord')}" aria-pressed="${card.saved ? 'true' : 'false'}">${raw(icon('bookmark-check', { size: 19 }))}</button>
      </div>
    </div>
    ${
      card.hasMeaning
        ? html`<div class="s-word-card__meaning"><div class="s-word-card__meaning-text">${card.meaning}</div>${card.hasSupport ? html`<div class="s-word-card__support">${card.support}</div>` : ''}</div>`
        : ''
    }
    ${
      card.hasExample
        ? html`<div class="s-word-card__example" lang="${langAttr(cardLang)}">“${card.exampleParts.map((part) => html`<span class="${cls(part.hit && 's-word-card__hit')}">${part.value}</span>`)}”</div>`
        : ''
    }
    ${strokeTiles}
    ${footer.length ? html`<div class="s-word-card__footer">${footer}</div>` : ''}
  </div>`;
}

export default async function mountWordDetail(element, ctx) {
  await useStyles('screens/word/word.css');
  const word = String(ctx.params?.id || '').trim();
  const language = ctx.context?.language || 'en';

  // The Deep Word lookup (api.wordDetail) is AI-backed and can take several seconds on an
  // uncached word (writing_coach/word_detail.py); paint the shared loading skeleton (kit/states.js
  // - the same primitive the router's own lesson skeleton and Collection Detail use) beneath the
  // back button immediately, rather than leaving the main column blank until both lookups settle.
  mount(
    element,
    html`<button type="button" class="o-iconbtn" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 19 }))}</button>
    ${loadingMarkup(t('wordLoading'))}`,
  );
  element.classList.add('s-word-root');
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());

  let item = await fetchItem(word);
  if (!ctx.isCurrent()) return undefined;
  const context = contextFor(word, item);
  const [detail, clipsPayload] = await Promise.all([
    api.wordDetail({ depth: 'full', text: word, context, source_language: language, target_language: languages().support }).catch(() => null),
    api.wordClips(word, 6).catch(() => null),
  ]);
  if (!ctx.isCurrent()) return undefined;

  if (!detail && !item) throw new Error(`Word Detail: no lookup and no saved record for "${word}"`);

  let card = mapWordCard(word, { detail, item });
  const deepRows = mapDeepWord(detail);
  const clips = mapClips(clipsPayload);

  ctx.setCrumb(card.word);

  const glyphCache = new Map();
  async function glyphOf(ch) {
    if (glyphCache.has(ch)) return glyphCache.get(ch);
    try {
      const { glyphSvg } = await import('../../product/hanzi-strokes.js');
      const payload = await api.chineseStrokeOrder(ch);
      const data = (payload?.characters || [])[0] || null;
      const svg = data ? glyphSvg(data, { upto: data.stroke_count, faint: false }) : '';
      glyphCache.set(ch, svg);
      return svg;
    } catch {
      return '';
    }
  }

  let audio = null;
  function playUrl(url, { startMs = 0, endMs = 0 } = {}) {
    audio?.pause();
    audio = new Audio(url);
    audio.currentTime = startMs / 1000;
    if (endMs > startMs) {
      const stopAt = endMs / 1000;
      audio.addEventListener('timeupdate', () => {
        if (audio.currentTime >= stopAt) audio.pause();
      });
    }
    audio.play().catch(() => {});
  }

  async function paint() {
    // Recomputed on every paint, not once at mount: `item` changes on save/unsave/undo, and the
    // evidence panel must always reflect the item this render's `card` was built from, never a
    // frozen snapshot from the first load (rule 40 - a deleted item leaves no evidence to show).
    const evidence = mapMasteryEvidence(item);
    const strokeTiles = card.script === 'hanzi' ? await Promise.all([...card.word].filter((ch) => /[㐀-鿿]/.test(ch)).map(glyphOf)) : [];
    const strokesMarkup =
      card.script === 'hanzi'
        ? html`<div class="s-word-strokes">
        <div class="s-word-strokes__label">${t('strokeOrder')}</div>
        <div class="s-word-strokes__tiles">${strokeTiles.map((svg) => html`<span class="s-word-strokes__tile">${raw(svg)}</span>`)}</div>
        <button type="button" class="o-btn o-btn--secondary s-word-strokes__btn" data-practise-strokes>${raw(icon('pencil', { size: 16 }))}${t('practiseStrokes')}</button>
      </div>`
        : '';

    const clipsPanel = html`<div class="s-word-panel">
      <div class="s-word-panel__head"><div class="s-word-panel__title">${t('contextClipsTitle', { n: clips.length })}</div></div>
      ${clips.length ? clips.map((clip, index) => clipRow(clip, index)) : html`<div class="s-word-empty">${t('contextClipsEmpty')}</div>`}
    </div>`;

    const evidencePanel = html`<div class="s-word-panel">
      <div class="s-word-panel__title">${t('masteryEvidenceTitle')}</div>
      ${evidence.length ? evidence.map(evidenceRow) : html`<div class="s-word-empty">${t('masteryEvidenceEmpty')}</div>`}
    </div>`;

    mount(
      element,
      html`<button type="button" class="o-iconbtn" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 19 }))}</button>
      ${cardMarkup(card, strokesMarkup)}
      <div class="s-word-grid">
        <div class="s-word-col">${clipsPanel}${deepWordMarkup(deepRows)}</div>
        ${evidencePanel}
      </div>`,
    );
    bind();
  }

  function bind() {
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    element.querySelector('[data-play]')?.addEventListener('click', async () => {
      try {
        const audioInfo = await api.wordAudio(word);
        if (audioInfo?.available && audioInfo.url) playUrl(audioInfo.url);
        else toast(t('noAudio'));
      } catch {
        toast(t('noAudio'));
      }
    });
    element.querySelector('[data-save]')?.addEventListener('click', async () => {
      const button = element.querySelector('[data-save]');
      button.disabled = true;
      try {
        if (card.saved) {
          // Only offer Undo when we hold the exact record to restore (rule 40: never
          // reconstruct source_kind/added_at/schedule from the word card's own display fields).
          const payload = restorePayload(item);
          await api.deleteLibraryVocabulary(word);
          item = null;
          // Rebuild the whole card from the now-null item, exactly like the save and undo
          // branches below - never hand-patch just `saved`/`savedBg`/`savedColor`, which left the
          // mastery footer (bars/stage/due) reporting the just-deleted item's stale schedule.
          // `detail` is a snapshot fetched once at mount and never refetched, so its own `saved`
          // flag can still say `true` here (it reflected the truth before this delete); override
          // it with the delete we just confirmed, the one signal `mapWordCard` cannot get right
          // on its own for this transition (rule 40 - don't let a stale snapshot outrank a real
          // action that just happened).
          card = mapWordCard(word, { detail: detail ? { ...detail, saved: false } : detail, item });
          await paint();
          toast(
            t('removedToast'),
            payload
              ? {
                  undo: async () => {
                    const restored = await api.restoreLibraryVocabulary(payload).catch(() => null);
                    item = restored?.item || item;
                    card = mapWordCard(word, { detail, item });
                    await paint();
                  },
                  undoLabel: shellCopy('undo'),
                }
              : {},
          );
        } else {
          const saved = await api.saveLibraryVocabulary(savePayload(card));
          item = saved?.item || item;
          card = mapWordCard(word, { detail, item });
          await paint();
          toast(t('savedToast'));
        }
      } finally {
        element.querySelector('[data-save]') && (element.querySelector('[data-save]').disabled = false);
      }
    });
    element.querySelector('[data-practise-strokes]')?.addEventListener('click', () => {
      // The frame's sheet title is the word plus its own pinyin when the lookup has one
      // (`skWord`, E4 §7) - not a second, disconnected reading.
      const titleWord = card.ipa ? `${card.word} · ${card.ipa}` : card.word;
      openSheet({
        label: t('strokePracticeTitle', { word: titleWord }),
        render: (sheetEl, handle) =>
          mountStrokeSheet(sheetEl, handle, {
            word: card.word,
            titleWord,
            chineseStrokeOrder: api.chineseStrokeOrder,
            t,
            closeLabel: shellCopy('close'),
          }),
      });
    });
    element.querySelectorAll('[data-clip-play]').forEach((button) => {
      button.addEventListener('click', () => {
        const clip = clips[Number(button.dataset.clipPlay)];
        if (clip?.url) playUrl(clip.url, { startMs: clip.startMs, endMs: clip.endMs });
      });
    });
    element.querySelectorAll('[data-clip-open]').forEach((button) => {
      button.addEventListener('click', () => {
        const clip = clips[Number(button.dataset.clipOpen)];
        if (clip?.lessonId) ctx.go(ctx.href('listening', { id: clip.lessonId }));
      });
    });
  }

  await paint();

  return () => {
    audio?.pause();
  };
}
