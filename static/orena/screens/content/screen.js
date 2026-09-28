/* Content Detail (design route `detail`, frame 05, D-091). One generic preview page for every
   content kind Discover/Today/My Library/Search link into: an article, a shared-library book (or
   one of its chapters), a Listening lesson (curated or admin-imported), a learner's own uploaded
   media, or a learner's own imported text. Its primary action hands off to the Reader or the
   Listening workspace; neither is built yet, so that hand-off lands on the design's own Coming
   soon screen through the router's normal fallback (shell/screens.js has no entry for either),
   exactly as the brief asks - this screen does not special-case that.

   Not drawn here (rule 43/44): no chapter list (the frame draws none - a book's chapters are the
   Reader's own concern, per the frame), no bulk actions, no toast on Save (the frame changes only
   the button's own label). */
import { html, mount, cls } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { heroMedia, listRow, rowThumb } from '../../kit/components.js';
import { langSpan, langAttr } from '../../kit/lang.js';
import { api } from '../../infrastructure/api.js';
import { t } from './copy.js';
import {
  parseContentId,
  contentIdFor,
  minutesFrom,
  metaLine,
  libraryKindFor,
  primaryDestination,
  placeFor,
  normalizeArticle,
  normalizeBook,
  normalizeMedia,
  normalizeText,
  pickRelated,
} from './model.js';

function typeLabel(kind, playbackKind) {
  if (kind === 'article') return t('typeArticle');
  if (kind === 'book') return t('typeBook');
  if (kind === 'text') return t('typeText');
  return playbackKind === 'audio' ? t('typeAudio') : t('typeVideo');
}

function minutesLabel(minutes) {
  return minutes == null ? '' : t('minutes', { n: minutes });
}

async function loadDetail(kind, id, ctx) {
  if (kind === 'article') return normalizeArticle(await api.readingArticle(id));
  if (kind === 'book') return normalizeBook(await api.libraryBook(id));
  if (kind === 'media') return normalizeMedia(await api.listeningLibraryLesson(id, ''));
  if (kind === 'upload') return normalizeMedia(await api.mediaMy(id));
  // text: a learner's own import, device memory only (product/memory.js) - never the network.
  const record = ctx.context.memory.value.imports.find((item) => item.id === contentIdFor('text', id));
  if (!record) throw new Error('This text is not on this device.');
  return normalizeText(record);
}

/* Whether an article has an approved question set to practise with (R2's "Practice this text").
   404 means Free Reading (no set) - not an error the learner needs to see; any other failure
   also hides the button rather than risk a control that cannot actually open anything. */
async function loadHasPractice(kind, id) {
  if (kind !== 'article') return false;
  try {
    await api.readingPracticeSet(id);
    return true;
  } catch {
    return false;
  }
}

/* Saved state: the server's own kept-item state for a kind `/api/library/items` understands, or
   device memory's `kept[]` for a learner's own text import, which has no server kind. */
async function loadSaved(libKind, sourceId, contentId, memory) {
  if (!libKind) return { saved: memory.value.kept.includes(contentId), itemId: '' };
  const result = await api.libraryItems({ kind: libKind, sources: [sourceId] }).catch(() => null);
  const item = result?.items?.[0];
  return { saved: Boolean(item), itemId: item?.id || '' };
}

/* A handful of other real content of the same kind, never a fabricated "similar to this"
   ranking - there is no relatedness signal in the backend today (recorded in
   docs/project/UI_BACKEND_GAPS.md); this is the same catalogue Discover would show, just capped
   and pointed at Content Detail for each item. Upload/text have no shared catalogue at all, so
   they render no Related section (rule 40: an absent list is empty, not invented). */
async function loadRelated(kind, id, language) {
  try {
    if (kind === 'article') {
      const page = await api.readingArticles(language);
      return pickRelated(page?.items, {
        excludeId: id,
        map: (item) => ({
          id: contentIdFor('article', item.id),
          title: item.title,
          // languages-5 / finding A: the related list is the same language-scoped catalogue this
          // content item itself came from (loadRelated's own `language` argument).
          lang: language,
          meta: metaLine([t('typeArticle'), item.level, minutesLabel(minutesFrom(item.reading_time_seconds))]),
          image: '',
        }),
      });
    }
    if (kind === 'book') {
      const page = await api.libraryBooks(language);
      return pickRelated(page?.items, {
        excludeId: id,
        map: (item) => ({
          id: contentIdFor('book', item.id),
          title: item.title,
          lang: language,
          meta: metaLine([t('typeBook'), item.author || '']),
          image: item.cover_asset_key ? `url("/api/reading/library/books/${encodeURIComponent(item.id)}/cover")` : '',
        }),
      });
    }
    if (kind === 'media') {
      const page = await api.listeningLibrary(language);
      return pickRelated(page?.items, {
        excludeId: id,
        map: (item) => ({
          id: contentIdFor('media', item.lesson_id),
          title: item.title,
          lang: language,
          meta: metaLine([item.media_type === 'audio' ? t('typeAudio') : t('typeVideo'), item.level, minutesLabel(minutesFrom(item.duration_ms, { unitMs: true }))]),
          image: item.thumbnail_url ? `url("${item.thumbnail_url}")` : '',
        }),
      });
    }
  } catch (error) {
    console.error('[Orena content] related list failed', error);
  }
  return [];
}

export default async function content(element, ctx) {
  await useStyles('screens/content/content.css');
  const parsed = parseContentId(ctx.params?.id);
  if (!parsed.kind) throw new Error(`Unknown content id: ${ctx.params?.id}`);
  const { kind, id, chapterId } = parsed;
  const contentId = kind === 'book' && chapterId ? contentIdFor('book', `${id}:${chapterId}`) : contentIdFor(kind, id);
  const language = ctx.context.language;
  const libKind = libraryKindFor(kind);

  const [detail, hasPractice, saved, related] = await Promise.all([
    loadDetail(kind, id, ctx),
    loadHasPractice(kind, id),
    loadSaved(libKind, id, contentId, ctx.context.memory),
    loadRelated(kind, id, language),
  ]);
  if (!ctx.isCurrent()) return undefined;

  const state = { saved: saved.saved, itemId: saved.itemId };
  const place = placeFor(ctx.context.memory.value.continuation, contentId);
  const destination = primaryDestination(kind);
  const primaryLabel = destination === 'listening'
    ? (place.started ? t('continueListening') : t('listen'))
    : (place.started ? t('continueReading') : t('startReading'));
  const primaryHref = destination === 'listening' ? ctx.href('listening', { id }) : ctx.href('reader', { id: contentId });
  const isMedia = Boolean(detail.segments && detail.segments.length);
  const transcriptLabel = isMedia
    ? (detail.transcriptOrigin === 'provider_caption' ? t.plural('captions', detail.segments.length) : t.plural('generated', detail.segments.length))
    : '';

  mount(
    element,
    html`<div class="s-content">
      <button type="button" class="s-content__back" data-back>${t('back')}</button>
      ${heroMedia({
        image: detail.image,
        height: 'var(--hero-h)',
        pill: typeLabel(kind, detail.playbackKind),
        title: langSpan(detail.title, detail.language),
        meta: metaLine([detail.source, detail.level, minutesLabel(detail.minutes)]),
      })}
      <div class="${cls('s-content__grid', !related.length && 's-content__grid--full')}">
        <div class="s-content__main">
          ${place.started
            ? html`<div class="s-content__progress">
                <div class="s-content__progress-labels"><span>${t('progressPercent', { pct: place.percent })}</span><span>${t('resume')}</span></div>
                <div class="s-content__bar"><span style="width:${place.percent}%"></span></div>
              </div>`
            : ''}
          <div class="s-content__actions">
            <a class="o-btn o-btn--primary s-content__primary" href="${primaryHref}">${primaryLabel}</a>
            ${hasPractice ? html`<a class="s-content__ai" href="${ctx.href('checku', { id: contentId })}">${t('practiceThisText')}</a>` : ''}
            <button type="button" class="s-content__secondary" data-save aria-pressed="${state.saved ? 'true' : 'false'}">${state.saved ? t('saved') : t('save')}</button>
          </div>
          ${detail.desc ? html`<p class="s-content__desc" lang="${langAttr(detail.language)}">${detail.desc}</p>` : ''}
          ${isMedia
            ? html`<div class="o-card s-content__transcript">
                <div class="s-content__transcript-head">
                  <span>${t('transcript')}</span><span class="o-tag">${transcriptLabel}</span>
                </div>
                <div class="s-content__transcript-body">
                  ${detail.segments.slice(0, 3).map((segment) => html`<div class="s-content__seg"><span class="s-content__seg-time">${segment.time}</span><span class="s-content__seg-text" lang="${langAttr(detail.language)}">${segment.text}</span></div>`)}
                </div>
              </div>`
            : ''}
        </div>
        ${related.length
          ? html`<div class="s-content__side">
              <div class="s-content__side-head">${t('related')}</div>
              ${related.map((item) => listRow({
                variant: 'outline',
                radius: 16,
                pad: '12px',
                leading: item.image ? rowThumb({ image: item.image, width: 64, height: 48, radius: 12 }) : null,
                title: langSpan(item.title, item.lang),
                sub: item.meta,
                dataset: { go: ctx.href('content', { id: item.id }) },
              }))}
            </div>`
          : ''}
      </div>
    </div>`,
  );

  // Related rows carry data-go, the shell's own delegated navigation (shell/router.js onClick) -
  // no listener of this screen's own is needed for them.
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  element.querySelector('[data-save]').addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    if (!libKind) {
      ctx.context.memory.keep(contentId);
      state.saved = ctx.context.memory.value.kept.includes(contentId);
    } else if (state.saved && state.itemId) {
      await api.libraryItemDelete(state.itemId).catch(() => {});
      state.saved = false;
      state.itemId = '';
    } else {
      const result = await api.libraryKeep({ kind: libKind, source_id: id }).catch(() => null);
      if (result?.item) {
        state.saved = true;
        state.itemId = result.item.id;
      }
    }
    button.disabled = false;
    button.setAttribute('aria-pressed', state.saved ? 'true' : 'false');
    button.textContent = state.saved ? t('saved') : t('save');
  });
}
