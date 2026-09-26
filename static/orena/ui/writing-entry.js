/* The Writing entry (D-066, D-067), drawn from Orena Writing, "Writing entry" (1920x1080, 390x827).

   Under the library's own top bar (the room's name, a search, "new piece"): the draft in progress with the way
   back into it, four ways to begin (free writing, from a prompt, your own topic, a response to something read
   or heard), and a rail of prompts for you. Everything is what the app already holds: the draft is the
   learner's own continuation, the prompts are the texts' own, and nothing is drawn for what does not exist -
   no draft, no card. */
import { esc, dialog } from './html.js';
import { feedbackHtml } from './writing-feedback.js';
import { icon } from './phosphor.js';
import { refCopy } from './reference.js';
import { link, continuationExperience } from '../product/intent.js';
import { contentCover } from './cover.js';
import { contentFor } from '../content/texts.js';
import { continuationEntries } from './patterns.js';

const fill = (text, values) => Object.entries(values).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, String(v)), String(text));
const KIND_LABEL = { story: 'libraryKind_story', conversation: 'libraryKind_dialogue' };

/* A new piece has an address of its own, so it never continues the free one. */
const newPieceId = () => `expression:${Date.now().toString(36)}`;

/* The pieces that were reviewed, read back from the account (D-072.1). Every review Orena wrote is already
   stored with its piece, so this asks the server for the pieces and lets the room replay the review the
   evaluation carries - it copies nothing and writes nothing. Only what the row actually states is printed:
   the version, the level the evaluator estimated and its date; a row with no score prints no score. */
export function gradedHtml({ ctx, r, essays }) {
  if (!essays.length) return '';
  const when = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? '' : date.toLocaleDateString(ctx.ui === 'vi' ? 'vi-VN' : ctx.ui === 'zh' ? 'zh-CN' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  };
  const rows = essays
    .map((essay) => {
      const title = String(essay.prompt || '').split('\n')[0].trim() || ctx.c.freeTitle;
      const meta = [
        Number(essay.revision_no) > 1 ? fill(r.writingVersionShort, { n: essay.revision_no }) : '',
        /^(A1|A2|B1|B2|C1|C2)$/.test(String(essay.cefr_estimate || '')) ? essay.cefr_estimate : '',
        when(essay.created_at),
      ].filter(Boolean).join(' · ');
      return `<button type="button" class="we-graded__row" data-review="${esc(essay.id)}" data-title="${esc(title)}"><span class="we-tile we-tile--small">${icon('check-circle', { size: 20 })}</span><span class="we-graded__text"><strong lang="${esc(ctx.language)}">${esc(title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span>${icon('arrow-right', { size: 17 })}</button>`;
    })
    .join('');
  return `<section class="we-graded"><header><h2>${esc(r.writingGraded)}</h2><span>${esc(r.writingGradedNote)}</span></header><div class="we-graded__rows">${rows}</div></section>`;
}

export function writingEntryHtml({ ctx, r, draft, words, prompts, replyLink, level }) {
  const c = ctx.c;
  const mode = (glyph, title, note, href, attrs = '') =>
    `<a class="we-mode" href="${esc(href)}"${attrs ? ` ${attrs}` : ''}><span class="we-tile we-tile--small">${icon(glyph, { size: 22 })}</span><strong>${esc(title)}</strong><span>${esc(note)}</span></a>`;
  const resume = draft
    ? `<section class="we-continue"><span class="we-tile">${icon('note-pencil', { size: 27 })}</span><div class="we-continue__text"><small>${esc(r.writingDraftNow)}</small><strong lang="${esc(ctx.language)}">${esc(draft.title || c.freeTitle)}</strong><span>${esc(words)} ${esc(r.writingWords)}</span></div><a class="we-go" href="${esc(link('expression', { id: draft.id }))}"><span>${esc(r.writingContinue)}</span>${icon('arrow-right', { size: 18 })}</a></section>`
    : '';
  const cards = prompts
    .map((item) => {
      const badge = r[KIND_LABEL[item.kind]] || '';
      const meta = [item.level, item.time && r.libraryMinutes ? fill(r.libraryMinutes, { n: (/\d+/.exec(item.time) || [''])[0] }) : ''].filter(Boolean).join(' · ');
      return `<a class="we-card" href="${esc(link('expression', { id: `story:${item.id}` }))}" data-search="${esc(`${item.prompt} ${item.title}`.toLowerCase())}"><span class="we-card__art">${contentCover(item)}${badge ? `<span class="we-badge">${esc(badge)}</span>` : ''}</span><strong lang="${esc(ctx.language)}">${esc(item.prompt)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</a>`;
    })
    .join('');
  const rail = prompts.length
    ? `<section class="we-rail" data-rail><header><h2>${esc(r.writingSuggestions)}</h2>${level ? `<span>${esc(fill(r.writingForLevel, { level }))}</span>` : ''}<button type="button" class="we-all" data-rail-all aria-expanded="false">${esc(r.writingSeeAll)}</button></header><div class="we-cards" data-cards>${cards}</div></section>`
    : '';
  return `<div class="lib we-page"><header class="lib-head"><h1>${esc(c.writingName)}</h1><label class="lib-search">${icon('magnifying-glass', { size: 16 })}<span class="sr-only">${esc(r.writingEntrySearch)}</span><input type="search" autocomplete="off" placeholder="${esc(r.writingEntrySearch)}" data-we-query></label><a class="lib-import lib-import--primary" href="${esc(link('expression', { id: 'expression:new' }))}" data-new-piece>${icon('pencil-simple', { size: 17 })}<span>${esc(r.writingNew)}</span></a></header><div class="we-body">${resume}<div class="we-modes">${mode('feather', r.writingModeFree, r.writingModeFreeNote, link('expression', { id: 'expression:new' }), 'data-new-piece')}${mode('lightbulb', r.writingModePrompt, r.writingModePromptNote, link('writing'), 'data-we-prompts')}${mode('pencil-line', r.writingModeTopic, r.writingModeTopicNote, link('expression', { id: 'expression:new' }), 'data-new-piece')}${mode('quotes', r.writingModeReply, r.writingModeReplyNote, replyLink)}</div>${rail}<div data-graded></div></div>`;
}

export function renderWritingEntry(root, ctx) {
  const { memory, language } = ctx;
  const r = refCopy(ctx);
  const entries = continuationEntries(memory, { experience: 'writing' });
  const draft = entries[0] || null;
  const text = draft ? String(memory.value.expressions?.[draft.id] || '') : '';
  const words = text
    ? [...new Intl.Segmenter(language, { granularity: 'word' }).segment(text)].filter((part) => part.isWordLike).length
    : 0;
  const prompts = contentFor(language).filter((item) => item.prompt);
  // A response to something read or heard is written about the thing most recently met.
  const met = (memory.value.continuation || []).find((item) => item?.id?.startsWith('story:') && ['reading', 'listening'].includes(continuationExperience(item)));
  const replyLink = met ? link('expression', { id: met.id }) : link('practice', { intent: 'reading' });
  const level = /^(A1|A2|B1|B2|C1|C2)$/.test(String(ctx.profile?.declared_level || '')) ? ctx.profile.declared_level : '';
  root.innerHTML = writingEntryHtml({ ctx, r, draft, words, prompts, replyLink, level });
  // A new piece gets its own address when it is asked for, so it never continues the one before it.
  root.querySelectorAll('[data-new-piece]').forEach((anchor) => {
    anchor.onclick = (event) => {
      event.preventDefault();
      location.hash = link('expression', { id: newPieceId() });
    };
  });
  const query = root.querySelector('[data-we-query]');
  const cards = [...root.querySelectorAll('.we-card')];
  query.oninput = () => {
    const q = query.value.trim().toLowerCase();
    cards.forEach((card) => (card.hidden = Boolean(q) && !card.dataset.search.includes(q)));
  };
  // "From a prompt" takes the learner to the prompts, on this page.
  const toPrompts = root.querySelector('[data-we-prompts]');
  if (toPrompts)
    toPrompts.onclick = (event) => {
      event.preventDefault();
      root.querySelector('[data-rail]')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    };
  /* The pieces that were reviewed arrive after the room does: the room is useful without them. */
  const graded = root.querySelector('[data-graded]');
  ctx.api
    .essays()
    .then((rows) => {
      if (!ctx.alive?.() && ctx.alive) return;
      const mine = (Array.isArray(rows) ? rows : [])
        .filter((row) => !row.language_code || row.language_code === ctx.language)
        .slice(0, 8);
      graded.innerHTML = gradedHtml({ ctx, r, essays: mine });
      /* A row opens the review that was stored with that piece - asked for by its own id, so it is the
         evaluator's own words and not a copy this room keeps. */
      graded.querySelectorAll('[data-review]').forEach((row) => {
        row.onclick = async () => {
          const sheet = dialog({ title: row.dataset.title, body: `<div class="wf" role="status"><p class="qs-skeleton"><span></span></p></div>` });
          sheet.classList.add('we-review-sheet');
          try {
            const review = await ctx.api.essayReview(row.dataset.review);
            sheet.querySelector('.wf').outerHTML = feedbackHtml(ctx.c, review, { language: ctx.language });
          } catch {
            sheet.querySelector('.wf').outerHTML = `<p class="notice" role="alert">${esc(ctx.c.unavailable)}</p>`;
          }
        };
      });
    })
    .catch(() => {
      // A list that did not arrive says nothing; the drafts and prompts are the room.
    });
  const all = root.querySelector('[data-rail-all]');
  if (all)
    all.onclick = () => {
      const open = all.getAttribute('aria-expanded') !== 'true';
      all.setAttribute('aria-expanded', String(open));
      root.querySelector('[data-rail]').toggleAttribute('data-all', open);
    };
}
