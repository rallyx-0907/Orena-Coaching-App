import { duration, origin, art, bindImages } from './content.js';
import { companionArt } from './brand.js';
import { pageIntro, intentNavigation, continuationShelf } from './patterns.js';
import { esc, dialog } from './html.js';
import {
  link,
  continuationLink,
  practiceIntentions,
  supports,
} from '../product/intent.js';
import { contentFor } from '../content/texts.js';
import { readingEntry } from '../content/reading.js';
import { openReadingRequest, readingRow } from './reading.js';

// Imported media carries no catalog level, and its length is unknown until the
// asset reports one. Join only what is actually true of this item, so an import
// never shows a stray separator or a fabricated 0:00.
function mediaLine(item) {
  return [
    item.level,
    Number(item.duration_ms) > 0 ? duration(item.duration_ms) : '',
  ]
    .filter(Boolean)
    .map((part) => esc(part))
    .join(' · ');
}
function mediaItem(item, intent, c) {
  return `<a class="voice-row" href="${link('encounter', { id: item.id, intent })}"><span class="voice-cover">${art(item)}<span class="voice-play" aria-hidden="true">▶</span></span><span><small>${mediaLine(item)}${mediaLine(item) ? ' · ' : ''}${item.kind === 'video' || item.kind === 'embed' ? c.video : c.audio}</small><strong lang="${item.language}">${esc(item.title)}</strong>${item.description ? `<span class="voice-description">${esc(item.description)}</span>` : ''}<span class="byline">${esc(item.source?.creator || origin(item, c))}</span></span><span aria-hidden="true">↗</span></a>`;
}
function contentRow(item, intent, c) {
  return `<article class="collection-row"><a class="collection-art" aria-label="${esc(item.title)}" href="${link('encounter', { id: item.id, intent })}">${art(item)}</a><div><small>${esc(origin(item, c))}</small><h2><a lang="${item.language || ''}" href="${link('encounter', { id: item.id, intent })}">${esc(item.title)} ↗</a></h2></div><button class="quiet" data-remove="${esc(item.id)}" aria-label="${esc(c.remove + ': ' + item.title)}">×</button></article>`;
}
export async function renderWorld(root, ctx) {
  const { api, c, language, memory, location, alive } = ctx;
  const text = contentFor(language).map((x) => ({
    ...x,
    id: `story:${x.id}`,
    language,
  }));
  const result = await Promise.allSettled([
    api.listeningLibrary(language),
    api.readingSessions(12),
  ]);
  if (!alive()) return;
  const media = (
    result[0].status === 'fulfilled' ? result[0].value.items || [] : []
  )
    .filter((x) => x.language === language)
    .map((x) => ({
      ...x,
      id: `media:${x.lesson_id}`,
      kind: x.playback_kind,
      origin: 'curated',
    }));
  const failed = result[0].status === 'rejected';
  // Passages the learner asked for before. They live with the account rather
  // than on the device, so an empty list here is not the same as none kept.
  const reading = (
    result[1].status === 'fulfilled' ? result[1].value.items || [] : []
  ).map((x) => readingEntry(x, language));
  const readingFailed = result[1].status === 'rejected';
  // Everything that is read rather than listened to, in one list.
  const readable = [...reading, ...text, ...memory.value.imports];
  const all = [
    ...media,
    ...reading,
    ...text,
    ...memory.value.imports,
    ...memory.value.mediaImports,
  ];
  // Curated and imported media are one library: whatever a learner brought in
  // is practisable everywhere the catalog is.
  const practiceMedia = [...media, ...memory.value.mediaImports];
  const intent = location.intent;
  const destination = (id) => link('encounter', { id, intent });
  const headline = (title, note, eyebrow = '') =>
    pageIntro({ title, note, eyebrow });
  const continuation = continuationShelf(ctx);
  const catalogError = failed
    ? `<p class="notice" role="alert">${c.unavailable} <button data-retry>${c.retry}</button></p>`
    : '';
  const readingError = readingFailed
    ? `<p class="notice" role="alert">${c.unavailable} <button data-retry>${c.retry}</button></p>`
    : '';
  if (location.page === 'practice') {
    root.innerHTML = `${headline(intent ? c[`${intent}Intent`] || c[intent] : c.choose, intent ? c[`${intent}IntentNote`] || c[`${intent}Note`] : c.chooseNote, c.practice)}${intentNavigation(c, intent)}${!intent ? `<section class="practice-invitation"><span class="big-voice" aria-hidden="true">“</span><div><h2>${c.shadowing}</h2><p>${c.shadowingNote}</p><a class="primary" href="${link('practice', { intent: 'shadowing' })}">${c.shadowingName} →</a></div><div class="practice-small"><h3>${c.dictation}</h3><p>${c.dictationNote}</p><a href="${link('practice', { intent: 'dictation' })}">${c.dictationName} →</a></div></section>` : ''}${
      intent === 'reading'
        ? `<section class="voices"><div class="section-head"><h2>${c.readingCollection}</h2><button class="quiet" data-read>＋ ${c.readingBring}</button></div>${readingError}${
            readable.map((x) => readingRow(x, c)).join('') ||
            `<p>${c.empty}</p>`
          }</section>`
        : `<section class="voices"><div class="section-head"><h2>${c.chooseMoment}</h2><button class="quiet" data-bring>＋ ${c.bring}</button></div>${catalogError}${
            practiceMedia
              .filter((x) => supports(x, intent))
              .map((x) => mediaItem(x, intent, c))
              .join('') || `<p>${c.noCatalog}</p>`
          }</section>`
    }${continuation}`;
  } else if (location.page === 'content') {
    const kept = all.filter(
      (x) => memory.value.kept.includes(x.id) || x.origin === 'imported',
    );
    root.innerHTML = `${headline(c.content, c.local)}${!memory.available ? `<p class="notice">${c.memoryUnavailable}</p>` : ''}${catalogError}<section>${kept.length ? kept.map((x) => contentRow(x, null, c)).join('') : `<div class="empty">${companionArt()}<h2>${c.empty}</h2><p>${c.emptyNote}</p><button class="primary" data-bring>${c.bring} ↗</button></div>`}</section>${continuation}<button class="outline" data-bring>＋ ${c.bring}</button>`;
  } else {
    const feature = media.find((x) => x.kind === 'video') || media[0];
    root.innerHTML = `<section class="arrival"><div><small>${c.edition}</small><h1>${c.hello}</h1><p>${c.intro}</p></div>${companionArt()}</section><div class="world-opening">${feature ? `<article class="window"><a class="window-media" aria-label="${esc(feature.title)}" href="${destination(feature.id)}">${art(feature)}<span class="play-disc" aria-hidden="true">▶</span><span class="duration">${duration(feature.duration_ms)}</span></a><div class="window-caption"><div><small>${c.video} · ${esc(feature.level)} · ${esc(origin(feature, c))}</small><h2 lang="${language}"><a href="${destination(feature.id)}">${esc(feature.title)} ↗</a></h2></div><p>${esc(feature.description)}</p></div></article>` : `<div class="window">${catalogError}<h2>${c.noCatalog}</h2></div>`}<aside class="side-story"><small>${c.stories}</small><a href="${destination(text[0].id)}">${art(text[0])}<h2 lang="${language}">${esc(text[0].title)} ↗</h2><p lang="${language}">${esc(text[0].subtitle)}</p></a><small>${c.generated}</small></aside></div><section class="intent-ribbon"><div><h2>${c.choose}</h2><p>${c.chooseNote}</p></div><a href="${link('practice', { intent: 'dictation' })}">${c.dictationName} ↗</a><a href="${link('practice', { intent: 'shadowing' })}">${c.shadowingName} ↗</a><a href="${link('practice', { intent: 'reading' })}">${c.readingName} ↗</a><a href="${link('expression')}">${c.writingName} ↗</a><a href="${link('practice')}">${c.practice} →</a></section>${continuation}<section class="voices"><div class="section-head"><h2>${c.voices}</h2><span class="wave" aria-hidden="true">▂ ▆ ▃ ▇ ▄ ▂</span></div>${practiceMedia
      .filter((x) => x !== feature)
      .map((x) => mediaItem(x, null, c))
      .join('')}</section><section class="text-paths">${text
      .slice(1)
      .map(
        (x) =>
          `<a href="${destination(x.id)}"><small>${c.generated}</small><h2 lang="${language}">${esc(x.title)} ↗</h2><p lang="${language}">${esc(x.subtitle)}</p>${art(x)}</a>`,
      )
      .join(
        '',
      )}</section><section class="bring-invitation"><span aria-hidden="true">＋</span><div><h2>${c.bring}</h2><p>${c.emptyNote}</p></div><button class="outline" data-bring>${c.importAction} ↗</button></section>`;
  }
  root
    .querySelectorAll('[data-bring]')
    .forEach((x) => (x.onclick = ctx.import));
  root
    .querySelectorAll('[data-read]')
    .forEach((x) => (x.onclick = () => openReadingRequest(ctx)));
  root
    .querySelector('[data-retry]')
    ?.addEventListener('click', () => renderWorld(root, ctx));
  root.querySelectorAll('[data-remove]').forEach(
    (button) =>
      (button.onclick = () => {
        const id = button.dataset.remove;
        const sheet = dialog({
          title: c.remove,
          body: `<p>${c.removeNote}</p><button class="primary" data-confirm>${c.remove}</button>`,
        });
        sheet.querySelector('[data-confirm]').onclick = () => {
          memory.remove(id);
          sheet.close();
          renderWorld(root, ctx);
        };
      }),
  );
  bindImages(root, c);
}
