/* Word Detail (frame 22, `#/word/:id`; D-091). The saved-word reference page: the shared
   VocabularyCard in `detail` mode (kit/vocabulary-card.js, D-179 - the entry's content from
   product/vocabulary-card.js#toVocabularyModel, the learner's saved state beside it), real context clips from the listening
   catalogue, the Deep Word explanation, mastery evidence, and - for a Chinese headword - the
   Stroke Practice sheet (frame 60). Every binding maps to a real answer (`POST
   /api/dictionary/word-detail`, `GET /api/library/vocabulary`, `.../clips`, `.../audio`,
   `/api/chinese/stroke-order`); a field none of them carries is left out (rule 40), never
   invented. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { loadingMarkup } from '../../kit/states.js';
import { toast } from '../../kit/toast.js';
import { openSheet } from '../../kit/overlay.js';
import { rowBadge } from '../../kit/components.js';
import { vocabularyCard, bindVocabularyCards, fitVocabularyCards } from '../../kit/vocabulary-card.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { t } from './copy.js';
import {
  contextFor,
  mapDeepWord,
  mapClips,
  mapMasteryEvidence,
  restorePayload,
  stageCopyKey,
  catalogueLanguage,
} from './model.js';
import { toVocabularyModel, learnerState, savePayloadOf, highlightParts } from '../../product/vocabulary-card.js';
import { mountStrokeSheet } from './stroke-sheet.js';
import { createStrokeTiles } from './stroke-tiles.js';
import { speakOnDevice } from '../../kit/device-voice.js';
import { wordSeed } from '../../product/word-seed.js';
import { meaningLanguageLabel } from '../../product/vocabulary-meaning.js';

async function fetchItem(word) {
  try {
    const page = await api.libraryVocabulary({ query: word, limit: 5, order: 'word' });
    const norm = String(word).trim().toLowerCase();
    return (page?.items || []).find((row) => String(row.word || '').trim().toLowerCase() === norm) || null;
  } catch {
    return null;
  }
}

/* The catalogue's own answer for a word opened without a list before it (a direct link, a reload):
   its localizations are the sense's meanings, read-only, no provider (D-124). */
async function catalogueSeed(word, language) {
  try {
    const found = await api.vocabularyCatalogueSearch(word, language, 5);
    const norm = String(word).trim().toLowerCase();
    const hit = (found?.items || []).find((row) => String(row.normalized_word || row.word || '').trim().toLowerCase() === norm);
    return hit ? { pronunciation: String(hit.readings?.[0]?.text || '').trim(), short_meanings: hit.short_meanings || [], identity: { language }, entry: { ...hit, language_code: language } } : null;
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

/* A meaning that is not in the learner's support language says which language it is in (D-124). */
function meaningLabel(language) {
  return language ? meaningLanguageLabel(language, languages().support, languages().ui) : '';
}

/* The card: the entry's content (pure, D-179) and, beside it, what the learner's own record adds -
   saved state, the mastery footer, and the sentence they met the word in when the entry has no example. */
function cardMarkup(model, learner, item, strokes, meaningPending) {
  const stageKey = stageCopyKey(item);
  const footer = {
    stage: stageKey ? t(stageKey) : '',
    due: learner.due ? (learner.due.key === 'dueToday' ? t('dueToday') : t.plural('dueInDays', learner.due.n)) : '',
  };
  const latin = model.script !== 'hanzi';
  const decorated = { ...learner, contextParts: highlightParts(learner.context, { match: model.word, latin, caseless: latin }) };
  return vocabularyCard(model, { mode: 'detail', learner: decorated, slots: { strokes, footer, meaningLabel, meaningPending } });
}

export default async function mountWordDetail(element, ctx) {
  await useStyles('screens/word/word.css');
  await useStyles('kit/vocabulary-card.css');
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

  // The list the learner came from already knows the reading and the meaning (the seed), and the saved
  // record is a local read: paint from those at once (LEX-072). The AI-backed lookup and the clips refine the
  // page when they return; only a page with nothing at all to show waits for the lookup.
  let item = await fetchItem(word);
  if (!ctx.isCurrent()) return undefined;
  let seed = wordSeed(word);
  // The catalogue is asked in the word's own language (a Hanzi word is in the Chinese catalogue, whatever the
  // learner is learning now); it is a read, which the server allows for any enabled language.
  if (!item && !seed) seed = await catalogueSeed(word, catalogueLanguage(word, language));
  if (!ctx.isCurrent()) return undefined;

  let detail = null;
  let clips = [];
  let clipsReady = false;
  const pending = Promise.all([
    // The lookup runs in the learner's current learning language: the server refuses any other (409,
    // media_interaction.py#_validated_source_language). A Chinese word looked up under English can answer with an
    // English IPA labelled pinyin (UI_BACKEND_GAPS VC-15); the card mapper drops a reading of the wrong kind.
    api.wordDetail({ depth: 'full', contextual: true, text: word, context: contextFor(word, item), source_language: language, target_language: languages().support }).catch(() => null),
    api.wordClips(word, 6).catch(() => null),
  ]).then(([found, clipsPayload]) => ({ found, clipsPayload }));
  const hasSomethingToShow = Boolean(item || seed);
  // While the lookup is still out, a card with no meaning yet says so with the kit's skeleton, never "no meaning".
  let lookupPending = hasSomethingToShow;
  if (!hasSomethingToShow) {
    const { found, clipsPayload } = await pending;
    if (!ctx.isCurrent()) return undefined;
    // A refused or empty lookup never fails the page: the card is drawn from whatever exists - here only the
    // word itself - with no reading rather than a wrong one (rule 40).
    detail = found;
    clips = mapClips(clipsPayload);
    clipsReady = true;
  }

  // The entry's content: the saved record (which reads the catalogue entry through), else the card the
  // list left behind, else the catalogue's own search answer.
  const contentOf = () => toVocabularyModel(item || seed?.entry || null, { word, supportLanguage: languages().support, lookup: detail, seed });
  const learnerOf = () => learnerState(item, { saved: item ? true : Boolean(detail?.saved) });
  let model = contentOf();
  let learner = learnerOf();
  let deepRows = mapDeepWord(detail);

  ctx.setCrumb(model.word);

  // Word Detail's stroke order is frame 53's: the same looping tiles as the Quick Sheet (LEX-021).
  let strokeTiles = null;
  async function loadStrokeTiles() {
    if (strokeTiles) return strokeTiles;
    try {
      const payload = await api.chineseStrokeOrder(model.word);
      strokeTiles = createStrokeTiles(payload?.characters || []);
    } catch {
      strokeTiles = createStrokeTiles([]);
    }
    return strokeTiles;
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
    const tiles = model.script === 'hanzi' ? await loadStrokeTiles() : null;
    const strokesMarkup =
      model.script === 'hanzi'
        ? html`<div class="s-word-strokes">
        <div class="s-word-strokes__label">${t('strokeOrder')}</div>
        ${tiles.markup()}
        <button type="button" class="o-btn o-btn--secondary s-word-strokes__btn" data-practise-strokes>${raw(icon('pencil', { size: 16 }))}${t('practiseStrokes')}</button>
      </div>`
        : '';

    const clipsPanel = !clipsReady ? '' : html`<div class="s-word-panel">
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
      ${cardMarkup(model, learner, item, strokesMarkup, lookupPending)}
      <div class="s-word-grid">
        <div class="s-word-col">${clipsPanel}${deepWordMarkup(deepRows)}</div>
        ${evidencePanel}
      </div>`,
    );
    bind();
    strokeTiles?.start(element);
  }

  function bind() {
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    // The same pronunciation the Quick Sheet plays (LEX-020): the word at its reading, looked up as a word met in
    // a text when it is not in the catalogue, and the device's own voice - said to be the device's - only when
    // the server's voice failed or could not be reached.
    bindVocabularyCards(element);
    // The card is fully in view on arrival, actions included (rule 49, CLAUDE.md 6b).
    fitVocabularyCards(element, { viewport: true });
    // One play action per reading row (UK, US) and one on a card without them: the same word's voice.
    element.querySelectorAll('[data-play]').forEach((playButton) => playButton.addEventListener('click', async () => {
      const onDevice = () => {
        if (speakOnDevice(word, catalogueLanguage(word, language))) toast(t('sourceDevice'));
        else toast(t('noAudio'));
      };
      try {
        const audioInfo = await api.wordAudio(word, model.pronunciation.text || '', true);
        if (audioInfo?.available && audioInfo.url) playUrl(audioInfo.url);
        else if (audioInfo?.reason === 'synthesis_unavailable') onDevice();
        else toast(t('noAudio'));
      } catch {
        onDevice();
      }
    }));
    element.querySelector('[data-save]')?.addEventListener('click', async () => {
      const button = element.querySelector('[data-save]');
      button.disabled = true;
      try {
        if (learner.saved) {
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
          detail = detail ? { ...detail, saved: false } : detail;
          model = contentOf();
          learner = learnerOf();
          await paint();
          toast(
            t('removedToast'),
            payload
              ? {
                  undo: async () => {
                    const restored = await api.restoreLibraryVocabulary(payload).catch(() => null);
                    item = restored?.item || item;
                    model = contentOf();
                    learner = learnerOf();
                    await paint();
                  },
                  undoLabel: shellCopy('undo'),
                }
              : {},
          );
        } else {
          const saved = await api.saveLibraryVocabulary(savePayloadOf(model, 'dictionary'));
          item = saved?.item || item;
          model = contentOf();
          learner = learnerOf();
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
      const titleWord = model.pronunciation.text ? `${model.word} · ${model.pronunciation.text}` : model.word;
      openSheet({
        label: t('strokePracticeTitle', { word: titleWord }),
        render: (sheetEl, handle) =>
          mountStrokeSheet(sheetEl, handle, {
            word: model.word,
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

  if (hasSomethingToShow) {
    pending.then(async ({ found, clipsPayload }) => {
      if (!ctx.isCurrent()) return;
      lookupPending = false;
      detail = found;
      clips = mapClips(clipsPayload);
      clipsReady = true;
      deepRows = mapDeepWord(detail);
      model = contentOf();
      learner = learnerOf();
      await paint();
    });
  }

  const onResize = () => fitVocabularyCards(element, { viewport: true });
  window.addEventListener('resize', onResize);
  // D-181 option 1: on a phone this page arrives with the shell chrome collapsed and the card fits the whole height;
  // when the chrome comes back (scroll up, a pull or a tap at the top, focus) the column gives it its room again and
  // the card fits again, so the header and the bar never cover the card's actions.
  const shellRoot = document.documentElement;
  shellRoot.addEventListener('orena:chrome', onResize);

  return () => {
    window.removeEventListener('resize', onResize);
    shellRoot.removeEventListener('orena:chrome', onResize);
    audio?.pause();
    strokeTiles?.stop();
  };
}
