/* Home (D-066, D-067), drawn from Orena Home Discover ("Home - top", "Home - scrolled", the phone's
   two frames) and HomeTemplate: a top bar (the one search, the level, the streak), the Continue strip,
   then a stack of rails - what is new for the learner, then Reading, Listening, Speaking, Writing and
   Vocabulary.

   Every card is a real item the app holds: the catalogue's own listening and reading, the speaking
   situations, the writing prompts, the vocabulary collections. A rail with nothing in it is not drawn,
   and a card shows only what its item carries - a level, a length, a place - never an invented figure.
   What the frames leave no place for and the learner still has (the words of the day, what they kept,
   what is due) follows the rails, in the same rows. */
import { esc } from './html.js';
import { icon } from './phosphor.js';
import { art, duration } from './content.js';
import { contentCover } from './cover.js';
import { refCopy, streakChip } from './reference.js';
import { link, continuationExperience, continuationLink } from '../product/intent.js';
import { continuationEntries, continuationPlace } from './patterns.js';
import { contentFor } from '../content/texts.js';
import { voiceInvitations } from '../content/voice-invitations.js';
import { todayWords } from './discovery.js';

const RAIL_LIMIT = 12;
const LEVEL = /^(A1|A2|B1|B2|C1|C2)$/;
// What the learner is learning, in its own name.
const LANGUAGE_NAME = { en: 'English', zh: '中文' };
const fill = (text, values) => Object.entries(values).reduce((s, [k, v]) => s.replaceAll(`{${k}}`, String(v)), String(text));

/* How long a thing takes, from whatever the item states; unknown stays unknown. */
function lengthOf(item, r) {
  const ms = Number(item?.duration_ms) || 0;
  if (ms >= 60000) return fill(r.libraryMinutes, { n: Math.round(ms / 60000) });
  if (ms > 0) return duration(ms);
  const stated = /(\d+)/.exec(String(item?.time || ''));
  return stated ? fill(r.libraryMinutes, { n: stated[1] }) : '';
}

const SKILL_ICON = { listening: 'headphones', reading: 'book-open', speaking: 'microphone', writing: 'pen-nib', practice: 'keyboard', recall: 'cards', understanding: 'sparkle' };

function card(ctx, { href, title, meta = '', visual, glyph = '', percent = null, language = ctx.language }) {
  return `<a class="hm-card" href="${esc(href)}"><span class="hm-art">${visual}${glyph ? `<span class="hm-badge">${icon(glyph, { size: 15 })}</span>` : ''}${percent !== null ? `<span class="hm-track" role="img" aria-label="${percent}%"><i style="inline-size:${percent}%"></i></span>` : ''}</span><span class="hm-card__body"><strong lang="${esc(language)}">${esc(title)}</strong>${meta ? `<small>${esc(meta)}</small>` : ''}</span></a>`;
}

function rail(ctx, { id, title, sub = '', items, all = '', carets = false }) {
  if (!items.length) return '';
  const r = refCopy(ctx);
  const controls = carets
    ? `<span class="hm-carets"><button type="button" class="hm-caret" data-rail-step="-1" aria-label="${esc(`${r.railPrevious}: ${title}`)}" disabled>${icon('caret-left', { size: 17 })}</button><button type="button" class="hm-caret hm-caret--next" data-rail-step="1" aria-label="${esc(`${r.railNext}: ${title}`)}">${icon('caret-right', { size: 17 })}</button></span>`
    : all
      ? `<a class="hm-all" href="${esc(all)}"><span class="hm-all__long">${esc(r.collectionViewAll)}</span><span class="hm-all__short">${esc(r.homeAllShort)}</span></a>`
      : '';
  return `<section class="hm-rail" data-rail="${esc(id)}" aria-labelledby="hm-${esc(id)}"><header class="hm-rail__head"><h2 id="hm-${esc(id)}">${esc(title)}</h2>${sub ? `<span class="hm-sub">${esc(sub)}</span>` : ''}${controls}</header><div class="hm-cards" data-cards>${items.join('')}</div></section>`;
}

function continueStrip(ctx, entries) {
  const r = refCopy(ctx);
  const item = entries[0];
  if (!item) return '';
  const experience = continuationExperience(item);
  const place = continuationPlace(item);
  const skill = experience === 'listening' ? ctx.c.followName : ctx.c[`${experience}Name`] || ctx.c.resume;
  const action = r[`homeResume_${experience}`] || r.continueAction;
  const more = entries.length > 1
    ? `<a class="hm-all" href="${esc(link('continue'))}"><span class="hm-all__long">${esc(r.collectionViewAll)}</span><span class="hm-all__short">${esc(r.homeAllShort)}</span></a>`
    : '';
  const progress = place
    ? `<span class="hm-progress"><span class="hm-bar" role="img" aria-label="${place.percent}%"><i style="inline-size:${place.percent}%"></i></span><small>${place.percent}%</small></span>`
    : '';
  return `<section class="hm-section" aria-labelledby="hm-continue"><header class="hm-rail__head"><h2 id="hm-continue">${esc(r.continue)}</h2>${more}</header><a class="hm-continue" href="${esc(continuationLink(item))}"><span class="hm-continue__art" aria-hidden="true">${art(item)}</span><span class="hm-continue__body"><small>${icon(SKILL_ICON[experience] || 'clock-counter-clockwise', { size: 16 })}<span>${esc(skill)}</span></small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${progress}</span><span class="hm-go">${icon('play', { filled: true, size: 17 })}<span>${esc(action)}</span></span></a></section>`;
}

/* What is due is the learner's own saved vocabulary. The frames draw no place for it on Home, so it is
   the Continue strip's own shape and appears only when something is due. */
function reviewStrip(ctx, due) {
  const r = refCopy(ctx);
  if (!(Number(due) > 0)) return '';
  return `<a class="hm-review" href="${esc(link('practice', { intent: 'recall' }))}"><span class="hm-review__mark">${icon('cards', { filled: true, size: 20 })}</span><span class="hm-review__body"><strong>${esc(fill(r.reviewDue, { n: due }))}</strong><small>${esc(r.reviewNote)}</small></span><span class="hm-go hm-go--quiet">${esc(r.startAction)}</span></a>`;
}

export function homeHtml(ctx, { media = [], reading = [], nextReading = null, vocabulary = [], saved = [], due = 0, collections = [], catalogError = '' }) {
  const r = refCopy(ctx);
  const entries = continuationEntries(ctx.memory).slice(0, 8);
  const places = new Map(entries.map((entry) => [entry.id, continuationPlace(entry)]));
  const percentOf = (id) => (places.get(id) ? places.get(id).percent : null);

  const listening = (item, badge) => card(ctx, { href: link('encounter', { id: item.id, intent: 'follow' }), title: item.title, meta: [item.level, lengthOf(item, r)].filter(Boolean).join(' · '), visual: art(item), glyph: badge ? 'headphones' : '', percent: percentOf(item.id), language: item.language || ctx.language });
  const reads = (item, badge) => card(ctx, { href: link('encounter', { id: item.id, intent: 'reading', rec: item.recommendation || '' }), title: item.title, meta: [item.level, lengthOf(item, r)].filter(Boolean).join(' · '), visual: art(item), glyph: badge ? 'book-open' : '', percent: percentOf(item.id), language: item.language || ctx.language });

  /* What is new for the learner alternates listening and reading, so a phone's first two cards show both.
     The article the Reading selection policy chose for them leads its reading side. */
  const forYouReading = nextReading ? [nextReading, ...reading.filter((item) => item.id !== nextReading.id)] : reading;
  const mixed = [];
  for (let i = 0; mixed.length < RAIL_LIMIT && (i < media.length || i < forYouReading.length); i++) {
    if (media[i]) mixed.push(listening(media[i], true));
    if (forYouReading[i] && mixed.length < RAIL_LIMIT) mixed.push(reads(forYouReading[i], true));
  }
  const level = LEVEL.test(String(ctx.profile?.declared_level || '')) ? ctx.profile.declared_level : '';

  const situations = voiceInvitations(ctx.language).map((item) => card(ctx, { href: link('practice', { id: `voice:${item.key}`, intent: 'speaking' }), title: item.title, visual: contentCover({ id: `voice:${item.key}`, title: item.title, material: 'conversation' }) }));
  const prompts = contentFor(ctx.language).filter((item) => item.prompt).map((item) => card(ctx, { href: link('expression', { id: `story:${item.id}` }), title: item.prompt, meta: [item.level, lengthOf(item, r)].filter(Boolean).join(' · '), visual: contentCover(item) }));
  const sets = collections.map((set) => {
    const total = Number(set.progress?.total_count ?? set.word_count ?? set.total) || 0;
    return card(ctx, { href: link('language'), title: set.title || '', meta: total ? fill(r.homeWords, { n: total }) : '', visual: contentCover({ id: set.id, title: set.title, material: 'book' }, { motif: 'life' }), language: set.language_code || ctx.language });
  });
  const kept = saved.slice(0, RAIL_LIMIT).map((item) => (item.kind === 'audio' || item.kind === 'video' ? listening(item, false) : reads(item, false)));

  const rails = [
    rail(ctx, { id: 'for-you', title: r.forYou, sub: level ? fill(r.writingForLevel, { level }) : '', items: mixed, carets: true }),
    rail(ctx, { id: 'reading', title: r.reading, sub: r.homeSub_reading, items: reading.slice(0, RAIL_LIMIT).map((item) => reads(item, false)), all: link('practice', { intent: 'reading' }) }),
    rail(ctx, { id: 'listening', title: r.listening, sub: r.homeSub_listening, items: media.slice(0, RAIL_LIMIT).map((item) => listening(item, false)), all: link('practice', { intent: 'follow' }) }),
    rail(ctx, { id: 'speaking', title: r.speaking, sub: r.homeSub_speaking, items: situations.slice(0, RAIL_LIMIT), all: link('practice', { intent: 'speaking' }) }),
    rail(ctx, { id: 'writing', title: r.writing, sub: r.homeSub_writing, items: prompts.slice(0, RAIL_LIMIT), all: link('writing') }),
    rail(ctx, { id: 'vocabulary', title: r.vocabulary, sub: r.homeSub_vocabulary, items: sets.slice(0, RAIL_LIMIT), all: link('language') }),
    rail(ctx, { id: 'saved', title: r.savedTitle, items: kept, all: link('collection') }),
  ].join('');

  const name = String(ctx.user?.name || '').trim() || String(ctx.user?.email || '').split('@')[0] || '';
  const meta = [level, LANGUAGE_NAME[ctx.language] || String(ctx.language || '').toUpperCase()].filter(Boolean).join(' · ');
  const top = `<header class="lib-head hm-top"><div class="hm-hello"><strong>${esc(name ? fill(r.greetNamed, { name }) : r.greetPlain)}</strong><small>${esc(meta)}</small></div><form class="lib-search hm-search" role="search" data-home-search><label class="sr-only" for="homeSearch">${esc(r.searchPlaceholder)}</label>${icon('magnifying-glass', { size: 19 })}<input id="homeSearch" type="search" name="q" autocomplete="off" placeholder="${esc(r.searchPlaceholder)}"></form><a class="hm-search-open" href="${esc(link('search'))}" aria-label="${esc(r.searchPlaceholder)}">${icon('magnifying-glass', { size: 20 })}</a><div class="hm-chips">${level ? `<span class="hm-chip">${esc(level)}</span>` : ''}${streakChip(ctx)}</div></header>`;

  return `<div class="lib hm-page">${top}<div class="hm-body"><h1 class="sr-only">${esc(r.home)}</h1>${catalogError}${continueStrip(ctx, entries)}${reviewStrip(ctx, due)}${rails}${vocabulary.length ? `<div class="hm-words">${todayWords(ctx, vocabulary.slice(0, 5))}</div>` : ''}</div></div>`;
}

/* A rail steps by a card at a time from its head; the search is the app's one search. */
export function bindHome(root, ctx) {
  const form = root.querySelector('[data-home-search]');
  if (form)
    form.onsubmit = (event) => {
      event.preventDefault();
      const query = String(new FormData(form).get('q') || '').trim();
      if (query) ctx.go('search', { q: query });
    };
  const cleanups = [];
  root.querySelectorAll('.hm-rail').forEach((section) => {
    const track = section.querySelector('[data-cards]');
    const steps = [...section.querySelectorAll('[data-rail-step]')];
    if (!track) return;
    const update = () => {
      steps.forEach((button) => {
        button.disabled = Number(button.dataset.railStep) < 0 ? track.scrollLeft <= 2 : track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
      });
    };
    steps.forEach((button) => {
      button.onclick = () => {
        const first = track.querySelector('.hm-card');
        const gap = Number.parseFloat(getComputedStyle(track).columnGap) || 0;
        track.scrollBy({ left: Number(button.dataset.railStep) * ((first?.getBoundingClientRect().width || 300) + gap), behavior: 'smooth' });
      };
    });
    track.addEventListener('scroll', update, { passive: true });
    update();
    cleanups.push(() => track.removeEventListener('scroll', update));
  });
  return () => cleanups.forEach((cleanup) => cleanup());
}
