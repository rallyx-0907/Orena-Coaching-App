// Shared experience patterns, not a catalog of historical skill screens.
// The caller owns state and effects; these functions render escaped content.
import { esc } from './html.js';
import { scene } from './brand.js';
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
}) {
  return `<header class="page-intro"><div>${eyebrow ? `<small>${esc(eyebrow)}</small>` : ''}<h1${language ? ` lang="${esc(language)}"` : ''}>${esc(title)}</h1>${note ? `<p>${esc(note)}</p>` : ''}</div>${state ? scene(state, { size: 'medium' }) : ''}</header>`;
}

/* Where a practice room sits, and the way back to the map.

   Every room used to carry the whole practice map as a tab bar - eight modes
   repeated on each of them - which told the learner, on every screen, that
   Orena is a set of academic skills to pick between. The complete map belongs
   in Practice, which the learner chose to enter. Inside a mode, navigation is
   local: where you are, and how to leave.

   `intentNavigation` remains for surfaces that genuinely need the whole map. */
export function practiceReturn(c, current) {
  return `<nav class="practice-return" aria-label="${esc(c.practice)}"><a href="${link('practice')}">← ${esc(c.practice)}</a><span aria-current="page">${esc(c[current + 'Name'] || '')}</span></nav>`;
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

export function continuationShelf(ctx, limit = 3) {
  const { memory, c, language } = ctx;
  const entries = memory.value.continuation.slice(0, limit);
  if (!entries.length) return '';
  return `<section class="thread-shelf" aria-label="${esc(c.continue)}"><div class="section-head"><h2>${esc(c.continue)}</h2><span class="meta">${esc(c.deviceThreads)}</span></div><div class="thread-list">${entries
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

export function draftStatus(ctx) {
  return `<span class="draft-status meta" role="status" data-draft-status>${esc(ctx.memory.available ? ctx.c.draftSaved : ctx.c.memoryUnavailable)}</span>`;
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
    root.querySelector('[data-draft-status]').textContent = ctx.memory.available
      ? ctx.c.draftSaved
      : ctx.c.memoryUnavailable;
  });
}
