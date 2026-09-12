// Shared experience patterns, not a catalog of historical skill screens.
// The caller owns state and effects; these functions render escaped content.
import { esc } from './html.js';
import { scene } from './brand.js';
import { symbol } from './symbols.js';
import {
  link,
  continuationLink,
  sourceLink,
  practiceIntentions,
} from '../product/intent.js';

/* Why Orena kept something, and the way back to where the learner met it.

   A kept phrase that cannot answer "where did I see this?" is an anonymous
   card, which is the thing this product is trying not to produce. The reason
   is a stable key rather than free text, so it reads in either interface
   language; the route back is offered only when there is genuinely something
   to return to. */
export function keptProvenance(c, kept) {
  if (!kept) return '';
  const reason = c[`kept_${kept.why}`] || '';
  const where = String(kept.where || '').trim();
  return `<p class="kept-because">${reason ? esc(reason) : ''}${
    where
      ? `${reason ? ' · ' : ''}${
          kept.origin
            ? `<a href="${sourceLink(kept.origin)}">${esc(where)} ↗</a>`
            : esc(where)
        }`
      : ''
  }</p>`;
}

/* One page opening for the whole product. `scene` names an approved state, so
   an experience looks like itself at the top of the page without any surface
   knowing an image path - and a page with nothing worth illustrating simply
   passes nothing. */
export function pageIntro({
  title,
  note = '',
  eyebrow = '',
  language = '',
  scene: state = '',
  compact = false,
}) {
  /* A room where the learner is about to do something opens compactly: the
     activity is the protagonist, so the heading orients and then gets out of
     the way, and it carries no artwork. Entry, discovery and empty states keep
     the full opening, where atmosphere is doing real work. */
  return `<header class="page-intro${compact ? ' page-intro--compact' : ''}"><div>${eyebrow ? `<small>${esc(eyebrow)}</small>` : ''}<h1${language ? ` lang="${esc(language)}"` : ''}>${esc(title)}</h1>${note ? `<p>${esc(note)}</p>` : ''}</div>${state && !compact ? scene(state, { size: 'medium' }) : ''}</header>`;
}

/* The way back from a practice room to the map.

   Every room used to carry the whole practice map as a tab bar - eight modes
   repeated on each of them - which told the learner, on every screen, that
   Orena is a set of academic skills to pick between. The complete map belongs
   in Practice, which the learner chose to enter. Inside a mode, navigation is
   local: how to leave. Where you are is already the heading's eyebrow, so the
   way back sits above it, in the same place every other room puts it.

   `intentNavigation` remains for surfaces that genuinely need the whole map. */
export function practiceReturn(c) {
  return `<nav class="back-row practice-return" aria-label="${esc(c.practice)}"><a href="${link('practice')}">← ${esc(c.practice)}</a></nav>`;
}

/* Supplementary information as a symbol, with its words on demand.

   A hint is for what a learner may want to know, never for what they need in
   order to do the task - those instructions stay on screen as text. The
   trigger carries its own label for assistive technology and describes itself
   with the full text, so the symbol never has to be understood on its own.
   Hover and keyboard focus reveal it on a pointer device; a tap toggles it on
   touch. `installHints` wires that once for the whole document. */
let hintSequence = 0;
export function hint({ text, label = '', icon = 'info', tone = 'info' }) {
  if (!text) return '';
  const id = `orena-hint-${++hintSequence}`;
  return `<span class="hint" data-tone="${esc(tone)}"><button type="button" class="hint__trigger" aria-expanded="false" aria-describedby="${id}">${symbol(icon)}<span class="sr-only">${esc(label || text)}</span></button><span class="hint__bubble" role="tooltip" id="${id}">${esc(text)}</span></span>`;
}

function placeHint(root) {
  const bubble = root.querySelector('.hint__bubble');
  if (!bubble) return;
  root.dataset.align = '';
  const box = bubble.getBoundingClientRect();
  if (box.right > window.innerWidth - 8) root.dataset.align = 'end';
  else if (box.left < 8) root.dataset.align = 'start';
}

export function installHints(doc = document) {
  if (doc.__orenaHints) return;
  doc.__orenaHints = true;
  const closeAll = (except) =>
    doc.querySelectorAll('.hint[data-open]').forEach((node) => {
      if (node === except) return;
      delete node.dataset.open;
      node.querySelector('.hint__trigger')?.setAttribute('aria-expanded', 'false');
    });
  doc.addEventListener('click', (event) => {
    const trigger = event.target.closest?.('.hint__trigger');
    if (!trigger) {
      if (!event.target.closest?.('.hint')) closeAll();
      return;
    }
    const root = trigger.closest('.hint');
    const open = !('open' in root.dataset);
    closeAll(root);
    if (open) root.dataset.open = '';
    else delete root.dataset.open;
    trigger.setAttribute('aria-expanded', String(open));
    if (open) placeHint(root);
  });
  const reveal = (event) => {
    const root = event.target.closest?.('.hint');
    if (root) placeHint(root);
  };
  doc.addEventListener('mouseover', reveal);
  doc.addEventListener('focusin', reveal);
  doc.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeAll();
  });
}

/* The two frames of a learning workspace on a narrow screen: the activity, and
   the result the learner is placed at the start of. Wide screens show both at
   once and nothing moves. `back` is the control that returns to the work. */
export function workspaceFrames(workspace, { back, focus, result } = {}) {
  const narrow = () => window.matchMedia('(max-width: 1000px)').matches;
  const showResult = () => {
    workspace.dataset.workspace = 'result';
    if (narrow()) {
      result?.scrollTo?.({ top: 0 });
      workspace.scrollIntoView({ block: 'start' });
    }
  };
  const showActivity = () => {
    workspace.dataset.workspace = 'activity';
    focus?.()?.focus?.();
    if (narrow()) workspace.scrollIntoView({ block: 'start' });
  };
  if (back) back.onclick = showActivity;
  return { showResult, showActivity };
}
export function intentNavigation(c, current) {
  return `<nav class="intent-nav" aria-label="${esc(c.practice)}">${practiceIntentions.map((key) => `<a href="${key === 'writing' ? link('expression') : link('practice', { intent: key })}" ${key === current ? 'aria-current="page"' : ''}>${esc(c[key + 'Name'])}</a>`).join('')}</nav>`;
}

/* Two threads can share an intention and be entirely different things: a
   conversation and a single take are both Speaking, and both used to read
   "Speaking · <the same situation>" on the shelf. The id prefix already routes
   the entry, so it can name its shape too - otherwise the only way to tell two
   threads apart is to open one. */
function threadShape(item, c) {
  if (item.id.startsWith('conversation:')) return c.conversationTitle;
  return item.intent ? c[item.intent + 'Name'] : c.openedLabel;
}

/* What is actually waiting there. A conversation knows how far it got, which
   is worth more than "there is more to come back to". */
function threadState(item, memory, c) {
  const state = memory.value.conversations?.[item.id];
  if (state)
    return state.ended
      ? c.conversationEnded
      : `${state.turns.length} ${c.conversationTurnsSoFar}`;
  return item.segment ? c.resumeMoment : c.resumeEncounter;
}

/* Whether the work behind a thread is still there to return to.

   Conversations are kept to the last twelve and continuation to the last
   twenty, so the four oldest conversations could sit on the shelf saying
   "there is more to come back to" and then fail to open. A thread that cannot
   be resumed is not a thread; it is a promise the product cannot keep. */
export function resumable(item, memory) {
  if (item.id.startsWith('conversation:'))
    return Boolean(memory.value.conversations?.[item.id]);
  return true;
}

export function continuationShelf(ctx, limit = 3) {
  const { memory, c, language } = ctx;
  const entries = memory.value.continuation
    .filter((item) => resumable(item, memory))
    .slice(0, limit);
  if (!entries.length) return '';
  return `<section class="thread-shelf" aria-label="${esc(c.continue)}"><div class="section-head"><h2>${esc(c.continue)}</h2>${hint({ text: c.deviceThreads })}</div><div class="thread-list">${entries
    .map((item) => {
      const draft = memory.value.expressions[item.id]?.trim();
      const action =
        draft && item.intent === 'writing'
          ? c.draftLabel
          : threadShape(item, c);
      return `<a class="thread" href="${continuationLink(item)}"><small>${esc(action)}</small><strong lang="${language}">${esc(item.title)}</strong>${draft ? `<p lang="${language}">${esc(draft)}</p>` : `<p>${esc(threadState(item, memory, c))}</p>`}<span class="thread-action">${esc(c.resume)} <span aria-hidden="true">→</span></span></a>`;
    })
    .join('')}</div></section>`;
}

/* One voice for work that leaves the device. Saving, saved, and a failure that
   always carries a retry that is already wired - a retry button rendered
   without a handler is the defect this exists to make impossible. `alive`
   decides whether a late answer still belongs on a screen the learner left. */
export function progressReporter(element, ctx, alive = () => true) {
  const c = ctx.c;
  const write = (html) => {
    if (alive() && element.isConnected) element.innerHTML = html;
  };
  return {
    saving: () => write(esc(c.saving)),
    saved: (followUp) =>
      write(
        followUp
          ? `${esc(c.persisted)} · <a class="quiet" href="${esc(followUp.href)}">${esc(followUp.label)} <span aria-hidden="true">→</span></a>`
          : esc(c.persisted),
      ),
    note: (message) => write(esc(message)),
    failed: (message, retry) => {
      write(
        `${esc(message || c.failedSave)}${retry ? ` <button class="quiet" data-retry-action>${esc(c.retry)}</button>` : ''}`,
      );
      if (retry) {
        const button = element.querySelector('[data-retry-action]');
        if (button) button.onclick = retry;
      }
    },
  };
}

// Language the learner just kept is language they should be able to meet again.
// Every save that adds to the collection offers the same next step.
export function savedLanguageLink(c) {
  return { href: link('language'), label: c.memoryLink };
}

/* Whether the draft is kept, as a status symbol rather than a sentence.

   Where a draft lives is worth knowing, not worth reading on every visit; the
   words are one hover, focus or tap away and are what assistive technology
   hears. A draft that could not be kept is the one case that matters, so it
   takes the warning symbol and tone - shape and colour both, never colour
   alone. */
function draftStatusState(ctx) {
  return ctx.memory.available
    ? { icon: 'saved', tone: 'quiet', text: ctx.c.draftSaved }
    : { icon: 'warning', tone: 'warning', text: ctx.c.memoryUnavailable };
}
export function draftStatus(ctx) {
  const state = draftStatusState(ctx);
  return `<span class="draft-status" role="status" data-draft-status data-state="${state.icon}">${hint(state)}</span>`;
}
export function refreshDraftStatus(node, ctx) {
  if (!node) return;
  const state = draftStatusState(ctx);
  if (node.dataset.state === state.icon) return;
  node.dataset.state = state.icon;
  node.innerHTML = hint(state);
}

// One writing continuation pattern inside media, stories and grammar. It never
// submits a practice attempt, estimates mastery or overwrites a saved draft.
export function responseComposer(ctx, { id, prompt, title }) {
  const { c, memory, language } = ctx;
  return `<section class="response"><div><small>${esc(c.respond)}</small><h2>${esc(prompt || c.responsePrompt)}</h2><p class="meta">${esc(c.responseNote)}</p></div><div><label class="sr-only" for="response">${esc(c.respond)}</label><textarea id="response" rows="4" maxlength="12000" lang="${language}" placeholder="${esc(c.responsePlaceholder)}">${esc(memory.value.expressions[id] || '')}</textarea><div class="composer-footer">${draftStatus(ctx)}<a class="outline" href="${link('expression', { id })}">${esc(c.develop)} <span aria-hidden="true">↗</span></a></div></div></section>`;
}

export function bindComposer(
  root,
  ctx,
  item,
  context = () => item.excerpt || '',
) {
  root.querySelector('#response')?.addEventListener('input', (event) => {
    ctx.memory.write(item.id, event.target.value);
    ctx.memory.enter({
      id: item.id,
      title: item.title,
      intent: 'writing',
      excerpt: context(),
    });
    refreshDraftStatus(root.querySelector('[data-draft-status]'), ctx);
  });
}
