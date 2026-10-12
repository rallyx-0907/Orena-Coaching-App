/* Vocabulary Daily Feed (frame 36, `#/feed`; D-091). A horizontally swipeable deck of flip cards
   over today's real feed: `GET /api/vocabulary/feed` (day-seeded, excludes words already saved -
   `writing_coach/vocabulary_feed.py`). Reuses `screens/collection/model.js#supportMeaning`,
   `screens/word/model.js#highlightExample`/`cardLanguage`/`posLabel` and
   `screens/word/stroke-sheet.js#mountStrokeSheet`, exactly as Review Session and the Wave B
   overlays already do for the same shared Word Card primitive (D7 §4). The turned card is the shared
   VocabularyCard in `feed` mode (kit/vocabulary-card.js, D-17W): Save, never a grade. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { vocabularyCard, bindVocabularyCards } from '../../kit/vocabulary-card.js';
import { toVocabularyModel, savePayloadOf } from '../../product/vocabulary-card.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { emptyMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { openSheet } from '../../kit/overlay.js';
import { masteryBars } from '../../kit/components.js';
import { COVER_VISUALS } from '../../kit/cover-visuals.js';
import { rememberWordSeed } from '../../product/word-seed.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { t } from './copy.js';
import { mapFeedCards } from './model.js';
import { cardLanguage, posLabel } from '../word/model.js';
import { mountStrokeSheet } from '../word/stroke-sheet.js';
import { strokesMarkup, hydrateStrokes } from '../review/strokes.js';

/* A feed candidate was never saved, so it has no schedule: its mastery meter is the canonical
   component at its measured value - no bars filled and the real stage-0 label ("New") - never an
   invented "Recalled" (Design Contract rule 40; the frame draws this meter on every card). */
function masteryMarkup() {
  return html`<span class="s-feed-mastery">${masteryBars({ filled: 0, total: 4 })}<span class="s-feed-mastery__stage">${t('stageNew')}</span></span>`;
}

function frontMarkup(card, index, saved) {
  const cardLang = cardLanguage(card.script);
  const pos = card.pos ? posLabel(card.pos, t).text : '';
  const reading = [card.ipa ? html`<span>${card.ipa}</span>` : '', card.ipa && pos ? ' · ' : '', pos ? html`<i>${pos}</i>` : ''];
  return html`<div class="s-feed-face s-feed-face--front">
    <div class="s-feed-card__top">
      <div class="s-feed-card__id">
        <div class="s-feed-card__word" lang="${langAttr(cardLang)}">${card.word}</div>
        ${card.ipa || pos ? html`<div class="s-feed-card__reading">${reading}</div>` : ''}
      </div>
      ${masteryMarkup()}
    </div>
    <div class="s-feed-art">
      <div class="s-feed-art__image" aria-hidden="true"><span class="s-feed-art__tile" style="background:${COVER_VISUALS.vocab.tint}">${raw(icon(COVER_VISUALS.vocab.icon, { size: 30 }))}</span></div>
      <div class="s-feed-art__caption">${t('revealCaption')}</div>
    </div>
    <div class="s-feed-front-actions">
      <button type="button" class="s-feed-pill" data-play="${index}">${raw(icon('volume-2', { size: 16 }))}${t('play')}</button>
      <button type="button" class="s-feed-save" data-save="${index}" style="${saved ? 'background:var(--green-soft);color:var(--green)' : 'background:var(--accent-fill);color:var(--accent-ink)'}" aria-pressed="${saved ? 'true' : 'false'}">${t(saved ? 'saved' : 'save')}</button>
      <button type="button" class="s-feed-detail" data-detail="${index}">${t('detail')}</button>
    </div>
  </div>`;
}

/* The turned card: the shared VocabularyCard (`feed` mode) - the entry's content, the play disc and
   the save disc; a feed word is never graded here (D-17W). */
function backMarkup(model, saved) {
  const strokes = model.script === 'hanzi'
    ? strokesMarkup({ word: model.word, prefix: 's-feed', label: t('strokeOrder'), buttonLabel: t('practiseStrokes'), buttonAttr: 'data-practise-strokes', buttonClass: 's-feed-strokes-btn' })
    : '';
  return html`<div class="s-feed-face s-feed-face--back">
    ${vocabularyCard(model, { mode: 'feed', learner: { saved, hasSchedule: false }, slots: { strokes } })}
  </div>`;
}

function cardMarkup(card, model, index, flipped, saved) {
  return html`<div class="s-feed-card${cls(flipped && ' is-flipped')}" data-card="${index}" role="button" tabindex="0">
    ${flipped ? backMarkup(model, saved) : frontMarkup(card, index, saved)}
  </div>`;
}

export default async function mountFeed(element, ctx) {
  await Promise.all([useStyles('screens/feed/feed.css'), useStyles('kit/vocabulary-card.css')]);
  element.classList.add('s-feed-root');
  const context = ctx.context || {};
  const language = context.language || 'en';
  const support = languages().support;

  const payload = await api.dailyVocabularyFeed(language, context.level || '').catch(() => null);
  if (!ctx.isCurrent()) return undefined;

  const cards = mapFeedCards(payload, support);
  const models = (payload?.items || []).filter((entry) => String(entry?.headword || '').trim())
    .map((entry) => toVocabularyModel(entry, { supportLanguage: support }));
  for (const entry of payload?.items || []) rememberWordSeed(entry);
  const flipped = new Set();
  const savedIdx = new Set();
  let audio = null;

  function playUrl(url) {
    audio?.pause();
    audio = new Audio(url);
    audio.play().catch(() => {});
  }

  function paint() {
    const header = html`<div class="s-feed-head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-feed-head__title">
        <div class="s-feed-head__name">${shellCopy('dailyFeed')}</div>
        ${cards.length ? html`<div class="s-feed-head__sub">${t.plural('feedSubtitle', cards.length)}</div>` : ''}
      </div>
    </div>`;

    /* A flip or a save repaints the deck; the learner must stay on the card they are holding, not be
       thrown back to the first one. */
    const scrolled = element.querySelector('.s-feed-rail')?.scrollLeft || 0;
    mount(
      element,
      html`${header}${
        cards.length
          ? html`<div class="s-feed-rail" data-scroll-region>${cards.map((card, index) => cardMarkup(card, models[index], index, flipped.has(index), savedIdx.has(index)))}</div>`
          : emptyMarkup({ text: t('empty'), iconName: 'flame' })
      }`,
    );
    const rail = element.querySelector('.s-feed-rail');
    if (rail && scrolled) rail.scrollLeft = scrolled;
    bind();
    hydrateStrokes(element, api.chineseStrokeOrder, ctx.isCurrent).catch(() => {});
  }

  function bind() {
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    bindVocabularyCards(element);
    /* A card flips by tap or click, and by Enter / Space when it has the keyboard's focus (it is
       `role=button`); the repaint gives the focus back to the same card. */
    const flip = (index) => {
      if (flipped.has(index)) flipped.delete(index);
      else flipped.add(index);
      paint();
      element.querySelector(`[data-card="${index}"]`)?.focus({ preventScroll: true });
    };
    element.querySelectorAll('[data-card]').forEach((node) => {
      node.addEventListener('click', (event) => {
        if (event.target.closest('button')) return;
        flip(Number(node.dataset.card));
      });
      node.addEventListener('keydown', (event) => {
        if (event.target !== node || (event.key !== 'Enter' && event.key !== ' ')) return;
        event.preventDefault();
        flip(Number(node.dataset.card));
      });
    });
    // A control on either face names its card through the card it sits in.
    const indexOf = (button) => Number(button.closest('[data-card]')?.dataset.card);
    element.querySelectorAll('[data-play]').forEach((button) => {
      button.addEventListener('click', async (event) => {
        event.stopPropagation();
        const card = cards[indexOf(button)];
        try {
          const info = await api.wordAudio(card.word);
          if (info?.available && info.url) playUrl(info.url);
          else toast(t('noAudio'));
        } catch {
          toast(t('noAudio'));
        }
      });
    });
    element.querySelectorAll('[data-detail]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        const card = cards[Number(button.dataset.detail)];
        ctx.go(ctx.href('word', { id: card.word }));
      });
    });
    element.querySelectorAll('[data-save]').forEach((button) => {
      button.addEventListener('click', async (event) => {
        event.stopPropagation();
        const index = indexOf(button);
        const model = models[index];
        button.disabled = true;
        try {
          if (savedIdx.has(index)) {
            await api.deleteLibraryVocabulary(model.word);
            savedIdx.delete(index);
            toast(t('removedToast'));
          } else {
            await api.saveLibraryVocabulary(savePayloadOf(model, 'feed'));
            savedIdx.add(index);
            toast(t('savedToast'));
          }
        } finally {
          paint();
        }
      });
    });
    element.querySelectorAll('[data-practise-strokes]').forEach((button) => {
      button.addEventListener('click', async (event) => {
        event.stopPropagation();
        const card = cards[indexOf(button)];
        await useStyles('screens/word/word.css');
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
    });
  }

  paint();

  return () => {
    audio?.pause();
  };
}
