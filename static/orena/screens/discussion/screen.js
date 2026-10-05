/* Discussion (design route `discussion`, frame 46, D-091). A persistent Q&A thread about the
   currently-open text, over the real `/api/texts/discussion` contract (D-072.2,
   writing_coach/text_discussion.py) - a different feature from the global "Ask Orena" contextual
   panel (E3 §5's own note: two separate surfaces in the source script, kept separate here too,
   since only this one has a real per-document persisted thread behind it; AGENT_CONTRACT's
   askOrena is not used on this screen for that reason).

   Sending follows the source's own `dsSend`: the learner's question is appended to the thread and
   the box is cleared at once, then "Orena is thinking…" shows until the reply arrives. The frame is
   mounted once and only the thread repaints, so the box keeps focus, and a question that could not
   be answered is put back in the box (with the toast) instead of being lost.

   The thread opens with Orena's own first bubble, as the frame seeds every thread ("I'm attached to
   "<title>". Ask what a part means ..."; D-129 R-31). Not drawn here: no error visual inside the thread (the frame draws none for this screen; the generic toast -
   already the app's shared mechanism for a real, transient failure - carries the
   503/409 message instead of inventing new per-screen error UI). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { intelChip } from '../../kit/brand.js';
import { pageHeader } from '../../kit/components.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { supportLanguage } from '../../product/languages.js';
import { api } from '../../infrastructure/api.js';
import { t } from './copy.js';
import {
  parseContentId, discussionSourceFor, newRequestId, mapTurns, canSend, isSendKey, optimisticTurn, MAX_BODY_CHARACTERS,
} from './model.js';

async function loadTitle(kind, id, chapterId, ctx) {
  try {
    if (kind === 'article') return (await api.readingArticle(id))?.title || '';
    if (kind === 'book') {
      if (chapterId) {
        const chapter = await api.libraryBookChapter(id, chapterId);
        if (chapter?.title) return chapter.title;
      }
      return (await api.libraryBook(id))?.title || '';
    }
    if (kind === 'media' || kind === 'upload') {
      const lesson = await api.listeningLibraryLesson(id, '');
      return lesson?.catalog?.title || lesson?.asset?.title || '';
    }
    if (kind === 'text') {
      const record = ctx.context.memory.value.imports.find((item) => item.id === `text:${id}`);
      return record?.title || '';
    }
  } catch {
    // A title that cannot be read still lets the thread itself open - the subtitle just omits it.
  }
  return '';
}

function bubbleMarkup(turn, learnerLang) {
  return html`<div class="s-discussion__row" data-role="${turn.isAssistant ? 'assistant' : 'learner'}">
    ${turn.isAssistant ? intelChip({ size: 28, mark: 22, state: 'idle' }) : ''}
    <div class="s-discussion__bubble" lang="${turn.isAssistant ? langAttr(learnerLang) : ''}">${turn.body}</div>
  </div>`;
}

function threadMarkup(turns, thinking, learnerLang, intro = '') {
  return html`${intro ? bubbleMarkup({ isAssistant: true, body: intro }, learnerLang) : ''}${turns.map((turn) => bubbleMarkup(turn, learnerLang))}${
    thinking
      ? html`<div class="s-discussion__thinking">${intelChip({ size: 30, mark: 24, state: 'thinking' })}${t('thinking')}</div>`
      : ''
  }`;
}

export default async function mountDiscussion(element, ctx) {
  await useStyles('screens/discussion/discussion.css');
  const contentId = String(ctx.params?.id || '');
  const parsed = parseContentId(contentId);
  const source = discussionSourceFor(parsed);

  const [title, initial] = await Promise.all([
    loadTitle(parsed.kind, parsed.id, parsed.chapterId, ctx),
    api.textDiscussion(source.source_kind, source.source_id).catch(() => ({ turns: [] })),
  ]);
  if (!ctx.isCurrent()) return undefined;

  let turns = mapTurns(initial.turns);
  let maxTurns = initial.max_turns;
  let pending = false;
  const supportLang = supportLanguage(ctx.context?.profile);

  const starters = [
    t('starterMeaning'), t('starterAuthor'), t('starterGrammar'), t('starterInterpret'), t('starterTrue'),
  ];

  mount(
    element,
    html`<div class="s-discussion">
      ${pageHeader({
        compact: true,
        back: { label: shellCopy('back'), dataset: { back: '1' } },
        title: shellCopy('discussion'),
        meta: [title, t('subtitleSuffix')].filter(Boolean).join(' · '),
      })}
      <div class="s-discussion__thread" data-scroll-region data-thread></div>
      <div class="s-discussion__foot">
        <div class="s-discussion__starters" data-scroll-region>${starters.map((label) => html`<button type="button" class="s-discussion__starter" data-starter>${label}</button>`)}</div>
        <div class="s-discussion__inputbar">
          <input type="text" class="s-discussion__input" data-input maxlength="${MAX_BODY_CHARACTERS}" aria-label="${t('placeholder')}" placeholder="${t('placeholder')}">
          <button type="button" class="s-discussion__send" data-send aria-label="${t('send')}">${raw(icon('arrow-up', { size: 17 }))}</button>
        </div>
      </div>
    </div>`,
  );
  const thread = element.querySelector('[data-thread]');
  const field = element.querySelector('[data-input]');

  function paintThread(thinking) {
    mount(thread, threadMarkup(turns, thinking, supportLang, title ? t('intro', { title }) : ''));
    thread.scrollTop = thread.scrollHeight;
  }

  async function send(text) {
    const question = String(text || '').trim();
    if (pending || !canSend(question)) return;
    const before = turns;
    const hadFocus = document.activeElement === field;
    pending = true;
    turns = [...turns, optimisticTurn(question)];
    field.value = '';
    paintThread(true);
    try {
      const response = await api.sendDiscussionTurn({ ...source, body: question, context: '', request_id: newRequestId() });
      if (!ctx.isCurrent()) return;
      const fresh = await api.textDiscussion(source.source_kind, source.source_id).catch(() => null);
      if (!ctx.isCurrent()) return;
      turns = mapTurns(fresh ? fresh.turns : response.turns);
      if (fresh?.max_turns) maxTurns = fresh.max_turns;
    } catch (error) {
      if (!ctx.isCurrent()) return;
      turns = before;
      field.value = question;
      toast(error?.status === 409 ? t('full', { n: maxTurns }) : t('unavailable'), { iconName: 'circle-alert' });
    } finally {
      pending = false;
      if (ctx.isCurrent()) {
        paintThread(false);
        if (hadFocus) field.focus();
      }
    }
  }

  element.querySelector('[data-back]')?.addEventListener('click', () => ctx.back());
  element.querySelector('[data-send]').addEventListener('click', () => send(field.value));
  field.addEventListener('keydown', (event) => {
    if (!isSendKey(event)) return;
    event.preventDefault();
    send(field.value);
  });
  element.querySelectorAll('[data-starter]').forEach((button) => {
    button.addEventListener('click', () => send(button.textContent));
  });

  paintThread(false);
  return undefined;
}
