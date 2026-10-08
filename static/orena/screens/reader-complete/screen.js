/* Reading Complete (design route `rcomplete`, frame 40; `#/read/:id/done`, D-091). The reading
   session's own summary card: the document's real title, three real facts and the exits.

   The three facts, each measured or honest (rule 40), recorded in the report:
   - "saved from this text": the learner's saved words whose `source_fragment` is a sentence of this
     very text (reader/model.js#savedFromSentences) - the library keeps no link from a saved word to
     its document, so the sentence is the only provenance there is;
   - "notes & highlights": the device-memory notes (the Sentence Quick Sheet's) and highlights
     (reader/highlights.js) made on this text;
   - "understood": the latest real comprehension attempt at this article's approved question set
     (`GET /api/reading/practice/evidence`), or the frame's own em dash when there is none.
   The "Next" row names a real next chapter or a real unread article (model.js#nextPick); the frame's
   claim that it is "same theme" is not made, because the backend has no relatedness signal. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { api, request } from '../../infrastructure/api.js';
import { loadNotes, noteKeyFor } from '../quick-sheet/model.js';
import { parseContentId, contentIdFor, sentencesOf, segmentId, squash } from '../reader/model.js';
import { loadReadable, loadSavedFromText } from '../reader/source.js';
import { loadHighlights, isHighlighted } from '../reader/highlights.js';
import { t } from './copy.js';
import { originPlaceKey, originRouteId, comprehensionLabel, nextPick } from './model.js';

const ORIGIN_KEY = 'orena.next.navOrigin';

/* The router keeps the last primary place the learner was in (shell/router.js ORIGIN_KEY) - the
   frame's "Back to {origin}". */
function readOrigin() {
  try {
    return window.sessionStorage.getItem(ORIGIN_KEY) || '';
  } catch {
    return '';
  }
}

function statCell(value, label) {
  return html`<div class="s-rcomplete__stat"><div class="s-rcomplete__stat-value">${value}</div><div class="s-rcomplete__stat-label">${label}</div></div>`;
}

export default async function mountReaderComplete(element, ctx) {
  await useStyles('screens/reader-complete/reader-complete.css');
  const parsed = parseContentId(ctx.params?.id);
  if (!['article', 'book', 'text'].includes(parsed.kind)) throw new Error(`Reading Complete: unknown content id "${ctx.params?.id}"`);
  const memory = ctx.context.memory;
  const owner = ctx.context.owner;

  const doc = await loadReadable(parsed, memory);
  const contentId = doc.isBook ? contentIdFor('book', `${doc.bookId}:${doc.chapterId}`) : contentIdFor(doc.kind, doc.id);
  const [savedFrom, evidence, articles] = await Promise.all([
    loadSavedFromText(doc),
    doc.kind === 'article' ? request('/api/reading/practice/evidence?limit=50').then((r) => r?.items).catch(() => []) : [],
    doc.kind === 'article' ? api.readingArticles(doc.language).then((r) => r?.items).catch(() => []) : [],
  ]);
  if (!ctx.isCurrent()) return undefined;

  // Notes and highlights of this text, from device memory.
  let notesAndHighlights = 0;
  try {
    const storage = window.localStorage;
    const highlights = loadHighlights(storage, owner, contentId);
    for (const block of doc.paragraphs) {
      sentencesOf(block.text).forEach((sentence, si) => {
        const seg = segmentId(block.pi, si);
        const text = squash(sentence);
        notesAndHighlights += loadNotes(storage, owner, noteKeyFor(text, { kind: 'reading', content_id: contentId, segment: seg })).length;
        if (isHighlighted(highlights, seg, text)) notesAndHighlights += 1;
      });
    }
  } catch {
    notesAndHighlights = 0;
  }

  const title = doc.isBook ? doc.chapterTitle || doc.title : doc.title;
  ctx.setCrumb(title || shellCopy('readingComplete'));

  const origin = readOrigin();
  const next = nextPick({ doc, articles, continuation: memory.value.continuation });
  const nextLabel = next.kind === 'chapter' ? t('nextChapter') : next.kind === 'discover' || next.sameTheme ? t('nextSameTheme') : t('nextLabel');
  const nextTitle = next.kind === 'discover' ? t('chooseNext') : next.title;

  mount(
    element,
    html`<div class="s-rcomplete" data-scroll-region>
      <div class="s-rcomplete__card">
        <span class="s-rcomplete__blob s-rcomplete__blob--a"></span>
        <span class="s-rcomplete__blob s-rcomplete__blob--b"></span>
        <div class="s-rcomplete__eyebrow">${t('sessionComplete')}</div>
        <div class="s-rcomplete__title" lang="${langAttr(doc.language)}">${title}</div>
        <div class="s-rcomplete__stats">
          ${statCell(savedFrom ? savedFrom.count : 0, t('savedFromText'))}
          ${statCell(notesAndHighlights, t('notesHighlights'))}
          ${statCell(comprehensionLabel(evidence, doc.id), t('understood'))}
        </div>
        ${next.kind === 'discover' ? '' : html`<button type="button" class="s-rcomplete__next" data-next>
          <span class="s-rcomplete__next-body"><span class="s-rcomplete__next-label">${nextLabel}</span><span class="s-rcomplete__next-title"${next.kind === 'discover' ? '' : raw(` lang="${langAttr(doc.language)}"`)}>${nextTitle}</span></span>
          <span class="s-rcomplete__next-chev">${raw(icon('chevron-right', { size: 20 }))}</span>
        </button>`}
        <div class="s-rcomplete__actions">
          ${savedFrom?.words?.length ? html`<button type="button" class="s-rcomplete__secondary" data-review>${t('reviewSavedWords')}</button>` : ''}
          <button type="button" class="s-rcomplete__secondary" data-transfer>${shellCopy('readingTransfer')}</button>
          <button type="button" class="s-rcomplete__primary" data-back>${t('backTo', { place: shellCopy(originPlaceKey(origin)) })}</button>
        </div>
      </div>
    </div>`,
  );

  element.querySelector('[data-next]')?.addEventListener('click', () => {
    if (next.kind === 'chapter') ctx.go(ctx.href('reader', { id: next.id }));
    else if (next.kind === 'article') ctx.go(ctx.href('content', { id: next.id }));
    else ctx.go(ctx.href('discover'));
  });
  // This text's kept words, not the general due queue (LEX-024).
  element.querySelector('[data-review]')?.addEventListener('click', () => ctx.go(ctx.href('review', {}, { words: (savedFrom?.words || []).join(',') })));
  element.querySelector('[data-transfer]')?.addEventListener('click', () => ctx.go(ctx.href('rtransfer', { id: contentId })));
  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.go(ctx.href(originRouteId(origin))));

  return undefined;
}
