/* Respond to Content (design route `respond`, frame 45, D-091, D-088). A focus workspace: pick a
   response kind (Opinion/Summary/Reaction/Continuation), write with the source still beside it, get
   real feedback, then Revise / Ask Orena why / Done. See SCRATCH/reports/listening.md for the
   measurement diff and every deviation from the frame:
   - Result tiles: Words (the learner's own count) and Fixes (the real evaluation's findings) are
     measured; "Uses the source" is not - no endpoint measures it (`POST /api/evaluate` grades
     grammar, vocabulary, coherence, task achievement, naturalness) - so it renders 0 (rule 40).
   - "Next step" is the evaluation's own first priority (`next_actions[0]`), left out when it named
     none. A failed request keeps the response as written and says so with the drawn toast; the
     frame draws no error state.
   - No 60-150 word range is enforced anywhere in the backend, so none is drawn.
   - The live counter beside "Get feedback" reads in the same unit the request's own floor is
     judged in for this learning language (`measureMinimum`: Han characters for zh, words for
     en) - not the Segmenter word count the Result state's own "Words" tile shows once there is
     a real result (a different, honest answer to "how long is this piece", the same split
     `screens/writing/model.js#wordCountOf`/`reviewGate` already draws). The frame draws no
     "N more needed" notice for a draft under the floor (unlike Writing's `tooShortNotice`), so
     nothing is added here (rule 43); recorded as a backend/design gap below.

   Entry: Listening's end-of-media ("Write a response", `id` = `media:<lessonId>`) or Reader's
   "More" menu / Check Understanding (`id` = the real content id, "<kind>:<id>",
   screens/content/model.js's own scheme). One id shape: the kind prefix says which source it is. */
import { html, mount } from '../../kit/html.js';
import { useStyles } from '../../kit/styles.js';
import { openMedia } from '../../product/media-source.js';
import { langAttr } from '../../kit/lang.js';
import { pageHeader } from '../../kit/components.js';
import { toast } from '../../kit/toast.js';
import { shellCopy as s } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { sentenceSpans } from '../../product/reader-text.js';
import { measureWriting, measureMinimum } from '../../capabilities/writing-limits.js';
import { t } from './copy.js';
import {
  parseContentId, sourceLinesFromText, sourceLinesFromSegments,
  wordCountOf, canGetFeedback, mapFeedback,
} from './model.js';

const KINDS = ['opinion', 'summary', 'reaction', 'continuation'];

function joinParagraphs(raw) {
  if (Array.isArray(raw?.paragraphs) && raw.paragraphs.length) return raw.paragraphs.join(' ');
  if (Array.isArray(raw?.blocks) && raw.blocks.length) {
    return raw.blocks.filter((b) => b?.type === 'paragraph' || !b?.type).map((b) => String(b?.text || '')).join(' ');
  }
  return '';
}

async function loadSource(parsed, ctx, support) {
  const { kind, id, chapterId } = parsed;
  if (kind === 'media' || kind === 'upload') {
    const payload = await openMedia(id, { api, support, language: ctx.context.language, owner: ctx.context.owner || 'local' });
    const catalog = payload?.catalog || {};
    return {
      variant: 'media',
      kindKey: payload?.playback?.kind === 'audio' ? 'sourceKindAudio' : 'sourceKindVideo',
      title: catalog.title || payload?.asset?.title || '',
      lines: sourceLinesFromSegments(payload?.transcript?.segments, 4),
      language: catalog.language || payload?.asset?.source_language || '',
    };
  }
  if (kind === 'article') {
    const article = await api.readingArticle(id);
    return {
      variant: 'reading',
      kindKey: 'sourceKindArticle',
      title: article?.title || '',
      lines: sourceLinesFromText(sentenceSpans, article?.body, 4),
      language: article?.language || '',
    };
  }
  if (kind === 'book') {
    const book = await api.libraryBook(id);
    const ordered = [...(book?.chapters || [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
    const targetChapterId = chapterId || ordered[0]?.id;
    if (!targetChapterId) throw new Error('This book has no chapters.');
    const chapter = await api.libraryBookChapter(id, targetChapterId);
    return {
      variant: 'reading',
      kindKey: 'sourceKindBook',
      title: chapter?.title || book?.title || '',
      lines: sourceLinesFromText(sentenceSpans, joinParagraphs(chapter), 4),
      language: chapter?.language || book?.learning_language || '',
    };
  }
  // text: a learner's own import, device memory only - never the network.
  const record = ctx.context.memory?.value?.imports?.find((item) => item.id === `text:${id}`);
  return {
    variant: 'reading',
    kindKey: 'sourceKindText',
    title: record?.title || '',
    lines: sourceLinesFromText(sentenceSpans, record?.text, 4),
    language: record?.language || '',
  };
}

export default async function respondToContent(element, ctx) {
  await useStyles('screens/respond/respond.css');
  const c = ctx.context;
  const support = languages().support;
  const parsed = parseContentId(ctx.params.id);

  const source = await loadSource(parsed, ctx, support);
  if (!ctx.isCurrent()) return undefined;
  const variant = source.variant;
  /* The response is written in the language of what it answers; the learner's active learning
     language only when the source does not say (a learner's own text has no language field). */
  const language = source.language || c.language;

  let kind = 'opinion';
  let text = '';
  let result = null;
  let checking = false;

  element.classList.add('s-respond');
  mount(
    element,
    html`${pageHeader({
      compact: true,
      back: { label: s('back'), dataset: { back: '1' } },
      title: s('respondToContent'),
      meta: [source.title, t('subtitleSuffix')].filter(Boolean).join(' · '),
    })}
    <div class="s-respond__body">
      <div class="s-respond__card">
        <div class="s-respond__kinds" data-kinds></div>
        <div class="s-respond__prompt" data-prompt lang="${langAttr(support)}"></div>
        <div class="s-respond__region" data-scroll-region data-region></div>
        <div class="s-respond__foot" data-foot></div>
      </div>
      <div class="s-respond__source">
        <div class="s-respond__source-label">${t('sourceLabel', { kind: t(source.kindKey) })}</div>
        <div class="s-respond__source-title" lang="${langAttr(language)}">${source.title}</div>
        <div class="s-respond__source-lines" data-scroll-region>${source.lines.map((line) => html`<p class="s-respond__source-line" lang="${langAttr(language)}">${line}</p>`)}</div>
        <button type="button" class="s-respond__source-open" data-act="open-source">${t('openSource')}</button>
      </div>
    </div>`,
  );
  const kindsEl = element.querySelector('[data-kinds]');
  const promptEl = element.querySelector('[data-prompt]');
  const regionEl = element.querySelector('[data-region]');
  const footEl = element.querySelector('[data-foot]');
  element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
  /* The frame's own behaviour: a video source opens the room it came from, a text source goes back
     to where it was read. */
  element.querySelector('[data-act="open-source"]').addEventListener('click', () => {
    if (parsed.kind === 'media' || parsed.kind === 'upload') ctx.go(ctx.href('listening', { id: parsed.id }));
    else ctx.back();
  });

  const promptTextFor = () => t(`prompt${kind[0].toUpperCase()}${kind.slice(1)}${variant === 'media' ? 'Media' : 'Reading'}`);
  const kindLabel = (key) => t(`kind${key[0].toUpperCase()}${key.slice(1)}`);
  const feedbackReady = () => canGetFeedback(text, measureWriting, language) && !checking;
  /* The counter beside "Get feedback" is read in the same unit `canGetFeedback`'s own floor
     enforces for this learning language (Han characters for zh, words for en -
     `measureMinimum`) - not the Segmenter word count `wordCountOf` shows in the real Result
     tile below, which answers "how long is this piece" once there is a real result to show,
     not "why is the button off". The frame draws only a plain number here, no explanatory
     text (rule 43); when it is under the floor there is nothing on screen to say why - see
     the backend gap this report records. */
  const liveCount = () => measureMinimum(text, language).count;

  function paintKinds() {
    mount(kindsEl, html`${KINDS.map((key) => html`<button type="button" class="s-respond__kind" data-kind="${key}" aria-pressed="${String(key === kind)}">${kindLabel(key)}</button>`)}`);
    kindsEl.querySelectorAll('[data-kind]').forEach((button) => button.addEventListener('click', () => {
      kind = button.dataset.kind;
      result = null; // another kind is another task: the frame clears the result with the chip
      paint();
    }));
    mount(promptEl, html`${promptTextFor()}`);
  }

  function fixRow(issue) {
    return html`<div class="s-respond__fix">
      <div class="s-respond__fix-line" lang="${langAttr(language)}"><s>${issue.quote}</s>${issue.suggestion ? html` → <b>${issue.suggestion}</b>` : ''}</div>
      ${issue.why ? html`<div class="s-respond__fix-why">${issue.why}</div>` : ''}
    </div>`;
  }

  function paintRegion() {
    if (result) {
      mount(regionEl, html`
        <div class="s-respond__tiles">
          <div class="s-respond__tile"><div class="s-respond__tile-label">${t('wordsTile')}</div><div class="s-respond__tile-value">${wordCountOf(text, language)}</div></div>
          <div class="s-respond__tile"><div class="s-respond__tile-label">${t('fixesLabel')}</div><div class="s-respond__tile-value">${result.issues.length}</div></div>
        </div>
        ${result.issues.map(fixRow)}
        ${result.nextStep ? html`<div class="s-respond__callout"><b>${t('nextStepLabel')}</b> · ${result.nextStep}</div>` : ''}`);
      return;
    }
    mount(regionEl, html`<textarea class="s-respond__textarea" rows="8" lang="${langAttr(language)}" placeholder="${t('placeholder')}" data-text>${text}</textarea>`);
    const textarea = regionEl.querySelector('[data-text]');
    textarea.addEventListener('input', () => {
      text = textarea.value;
      const count = footEl.querySelector('[data-count]');
      if (count) count.textContent = `${liveCount()} ${t.plural('wordsLabel', liveCount())}`;
      const button = footEl.querySelector('[data-act="feedback"]');
      if (button) button.disabled = !feedbackReady();
    });
  }

  function paintFoot() {
    if (result) {
      mount(footEl, html`
        <button type="button" class="s-respond__btn" data-act="revise">${t('revise')}</button>
        ${result.id ? html`<button type="button" class="s-respond__btn" data-act="ask">${t('askOrenaWhy')}</button>` : ''}
        <span class="s-respond__spacer"></span>
        <button type="button" class="s-respond__primary" data-act="done">${t('done')}</button>`);
    } else {
      const count = liveCount();
      mount(footEl, html`
        <span class="s-respond__count" data-count>${count} ${t.plural('wordsLabel', count)}</span>
        <span class="s-respond__spacer"></span>
        <button type="button" class="s-respond__primary" data-act="feedback" ${feedbackReady() ? '' : 'disabled'}>${checking ? '…' : t('getFeedback')}</button>`);
    }
    footEl.querySelector('[data-act="feedback"]')?.addEventListener('click', onGetFeedback);
    footEl.querySelector('[data-act="revise"]')?.addEventListener('click', () => { result = null; paint(); });
    footEl.querySelector('[data-act="ask"]')?.addEventListener('click', () => {
      // "Ask Orena why" asks why about the feedback on screen, at once, with the essay attached (LEX-022).
      const shown = result?.nextStep || result?.issues?.[0]?.why || result?.issues?.[0]?.quote || '';
      askOrena({
        surface: 'writing.review',
        activity_type: 'writing',
        essay_id: result?.id,
        ...(shown ? { selected_item: { type: 'feedback_item', text: shown.slice(0, 500) } } : {}),
        ask: t('askWhyQuestion'),
      });
    });
    footEl.querySelector('[data-act="done"]')?.addEventListener('click', () => ctx.back());
  }

  function paint() {
    element.classList.toggle('is-result', Boolean(result));
    paintKinds();
    paintRegion();
    paintFoot();
  }

  async function onGetFeedback() {
    if (!feedbackReady()) return;
    checking = true;
    paintFoot();
    try {
      const raw = await api.evaluate({
        prompt: promptTextFor(),
        text,
        writing_context: { journal_context: `${t('sourceLabel', { kind: t(source.kindKey) })}: ${source.title}`.slice(0, 1000) },
        learning_language: language,
      });
      if (!ctx.isCurrent()) return;
      result = mapFeedback(raw);
    } catch {
      if (!ctx.isCurrent()) return;
      toast(t('feedbackError'));
    } finally {
      checking = false;
      if (ctx.isCurrent()) paint();
    }
  }

  paint();
  return undefined;
}
