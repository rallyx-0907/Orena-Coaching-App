import { esc } from './html.js';
import { editorialIntro, referenceCopy } from './reference.js';
import { link, sourceLink, continuationLink } from '../product/intent.js';
import { keptProvenance } from './patterns.js';

/* DEFERRED. Reachable at #/collection, deliberately not a primary destination.

   This was built during an IA run whose scope went beyond the change that was
   actually wanted. It is kept rather than deleted because it works and because
   the retrieval idea is worth revisiting on purpose - but My content and My
   language are the approved learner-facing surfaces, and they are unchanged.
   Do not promote this without a deliberate product decision.

   Everything the learner has met, kept or made, in one place to retrieve from.

   My content and My language remain exactly what they were - their routes,
   their stores and their deep views are untouched. This is the retrieval layer
   over them, because a learner looking for something they saw last week does
   not know whether they filed it under content or under language. They know
   they read it, or heard it, or wrote it.

   That is why the lenses here are skills, where on Discover they would be
   wrong: this is not a place to choose a discipline to study, it is a place to
   remember through. An item met through several capabilities appears under
   each lens that applies; nothing is duplicated in storage to achieve it. */

const LENSES = ['all', 'reading', 'listening', 'speaking', 'writing', 'language'];

/* A skill lens is a question about how the learner met something, so it is
   answered from what they actually did with it - the intent they entered it
   through, the reason they kept it - never from a guess about the content. */
export function lensesFor(item) {
  const found = new Set(['all']);
  const intent = item.intent || '';
  const why = item.why || '';
  const id = String(item.id || '');
  if (intent === 'reading' || why === 'from_reading' || id.startsWith('story:'))
    found.add('reading');
  if (['follow', 'dictation', 'shadowing'].includes(intent) || why === 'from_listening' || /^(media:|url:)/.test(id))
    found.add('listening');
  if (intent === 'speaking' || why === 'from_speaking' || id.startsWith('conversation:'))
    found.add('speaking');
  if (intent === 'writing' || why === 'from_writing' || id.startsWith('expression:'))
    found.add('writing');
  if (item.kind === 'language') found.add('language');
  return [...found];
}

export function collectionItems(ctx) {
  const { memory } = ctx;
  const seen = new Map();
  const add = (item) => {
    if (!item.id || seen.has(item.id)) return;
    seen.set(item.id, { ...item, lenses: lensesFor(item) });
  };
  for (const entry of memory.value.continuation || [])
    add({ ...entry, kind: 'thread', at: entry.at || '' });
  for (const entry of memory.value.imports || [])
    add({ ...entry, kind: 'content' });
  for (const entry of memory.value.mediaImports || [])
    add({ ...entry, kind: 'content' });
  for (const [term, kept] of Object.entries(memory.value.keptLanguage || {}))
    add({
      id: `language:${term}`,
      title: term,
      kind: 'language',
      why: kept?.why,
      where: kept?.where,
      origin: kept?.origin,
      at: kept?.at || '',
    });
  return [...seen.values()];
}

const rowFor = (c, item) => {
  const href =
    item.kind === 'language'
      ? link('language')
      : item.kind === 'thread'
        ? continuationLink(item)
        : sourceLink(item.id);
  return `<li><a href="${esc(href)}"><small>${esc(item.where || c[`${item.kind}Label`] || '')}</small><span lang="${esc(item.lang || '')}">${esc(item.title || item.id)}</span></a></li>`;
};

export function renderCollection(root, ctx) {
  const c = { ...referenceCopy[ctx.ui], ...ctx.c };
  const all = collectionItems(ctx);
  let lens = 'all';
  let query = '';

  root.innerHTML = `${editorialIntro(ctx, {
    title: c.collectionTitle,
    note: c.collectionNote,
    state: 'remembering',
    eyebrow: c.collection,
  })}<form class="collection-find" data-find><label><span class="sr-only">${esc(c.collectionSearch)}</span><input type="search" name="q" autocomplete="off" placeholder="${esc(c.collectionSearchHint)}"></label></form><nav class="lens-row" aria-label="${esc(c.collectionLenses)}">${LENSES.map(
    (id) =>
      `<button data-lens="${id}" ${id === 'all' ? 'aria-current="true"' : ''}>${esc(c[`lens_${id}`])}</button>`,
  ).join('')}</nav><p class="meta" role="status" data-found></p><div class="collection-shelves" data-shelves></div>`;

  const shelves = root.querySelector('[data-shelves]');
  const found = root.querySelector('[data-found]');

  const paint = () => {
    const needle = query.trim().toLocaleLowerCase();
    const matching = all.filter(
      (item) =>
        item.lenses.includes(lens) &&
        (!needle ||
          `${item.title || ''} ${item.where || ''}`
            .toLocaleLowerCase()
            .includes(needle)),
    );
    found.textContent = `${matching.length} ${c.collectionResults}`;
    /* An overview, not one long feed: each shelf shows a useful handful and
       says how to see the rest. Scrolling is not retrieval. */
    const shelf = (title, kind, route) => {
      const items = matching.filter((x) => x.kind === kind);
      if (!items.length) return '';
      return `<section class="collection-shelf"><div class="section-head"><h2>${esc(title)}</h2>${route && items.length > 6 ? `<a class="quiet" href="${esc(route)}">${esc(c.collectionViewAll)} ↗</a>` : ''}</div><ul>${items.slice(0, 6).map((x) => rowFor(c, x)).join('')}</ul></section>`;
    };
    shelves.innerHTML =
      [
        shelf(c.collectionThreads, 'thread', link('continue')),
        shelf(c.collectionYourContent, 'content', link('content')),
        shelf(c.collectionYourLanguage, 'language', link('language')),
      ].join('') ||
      `<section class="empty"><h2>${esc(c.collectionEmpty)}</h2><p>${esc(c.collectionEmptyNote)}</p><a class="primary" href="#/">${esc(c.discover)} ↗</a></section>`;
  };

  root.querySelectorAll('[data-lens]').forEach((button) => {
    button.onclick = () => {
      lens = button.dataset.lens;
      root
        .querySelectorAll('[data-lens]')
        .forEach((x) => x.toggleAttribute('aria-current', x === button));
      paint();
    };
  });
  root.querySelector('[data-find]').oninput = (event) => {
    query = event.target.value;
    paint();
  };
  root.querySelector('[data-find]').onsubmit = (event) => event.preventDefault();
  paint();
}
