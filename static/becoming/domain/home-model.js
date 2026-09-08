/* The Home view model — platform-neutral, no DOM, no markup, no copy.
 *
 * This module answers "what is truthfully on this learner's Home right now?"
 * from semantic backend data. It is deliberately separate from the screen so a
 * native client can reach the same conclusions without re-deriving the product
 * (ORENA_RESPONSIVE_COMPOSITION §16: a native port should re-render Home, not
 * rediscover it).
 *
 * The rule that governs every function here: nothing is returned unless real
 * data supports it. A section with no data returns null or an empty list, and
 * the screen shows discovery instead of an invented number.
 */

const text = value => (typeof value === 'string' ? value.trim() : '');

/* ------------------------------------------------------------- library --- */

export function libraryItemsById(library) {
  const items = Array.isArray(library?.items) ? library.items : [];
  const map = new Map();
  for (const item of items) {
    const id = text(item?.lesson_id);
    if (id && !map.has(id)) map.set(id, item);
  }
  return map;
}

function sectionIds(library, sectionId) {
  const sections = Array.isArray(library?.sections) ? library.sections : [];
  const section = sections.find(entry => entry && text(entry.id) === sectionId);
  const ids = Array.isArray(section?.item_ids) ? section.item_ids : [];
  return ids.map(text).filter(Boolean);
}

/* --------------------------------------------------- server continuation - */

/* The D-049 contract: `continue-learning` is built server-side from durable
 * PostgreSQL progress and already carries the catalog's visibility boundary,
 * and `resume` carries where in the lesson the learner stopped.
 *
 * A resume entry is only usable if its lesson is also present in the library
 * items - the section and the items come from the same response, so a mismatch
 * means the payload is malformed and the honest answer is "no continuation"
 * rather than a card pointing at a lesson we cannot describe.
 */
export function serverListeningContinuation(library) {
  const items = libraryItemsById(library);
  const resume = library?.resume && typeof library.resume === 'object' && !Array.isArray(library.resume)
    ? library.resume
    : {};
  for (const lessonId of sectionIds(library, 'continue-learning')) {
    const item = items.get(lessonId);
    if (!item) continue;
    const hint = resume[lessonId];
    const entry = hint && typeof hint === 'object' && !Array.isArray(hint) ? hint : {};
    return {
      kind: 'listening',
      lessonId,
      item,
      title: text(item.title),
      sourceUrl: text(item.source?.source_url),
      posterUrl: text(item.poster_url),
      artwork: text(item.artwork),
      // May legitimately be empty: the server blanks a segment that no longer
      // exists in a revised lesson, and the learner then resumes at the start.
      segmentId: text(entry.segment_id),
      // Deliberately no percentage. The resume contract carries a position,
      // not a completion ratio, and inventing one would be fabrication.
      hasExactAttempt: entry.best_exact === true,
    };
  }
  return null;
}

/* Continuation priority (H1 brief §9). Server-backed Listening progress is the
   only durable, cross-device signal, so it outranks the local draft; a real
   in-progress Writing draft is second; otherwise Home is discovery-first. */
export function homeContinuation({library = null, hasWritingDraft = false} = {}) {
  const listening = serverListeningContinuation(library);
  if (listening) return listening;
  if (hasWritingDraft) return {kind: 'writing'};
  return null;
}

/* --------------------------------------------------------------- worlds -- */

/* Only worlds the backend measured as available are shown. An editorial world
   with no real lesson yet is defined in the manifest but has nothing behind it,
   and a card that opens onto nothing is worse than one fewer card. */
export function availableWorlds(payload, {locale = 'en', limit = 8} = {}) {
  const worlds = Array.isArray(payload?.worlds) ? payload.worlds : [];
  return worlds
    .filter(world => world && world.available === true && Number(world.lesson_count) > 0 && text(world.world_id))
    .slice(0, limit)
    .map(world => ({
      worldId: text(world.world_id),
      title: localized(world.title, locale),
      description: localized(world.description, locale),
      artwork: text(world.artwork),
      accentFamily: text(world.accent_family),
      lessonCount: Number(world.lesson_count),
      leadLessonId: text(world.lead_lesson_id),
      leadLessonTitle: text(world.lead_lesson_title),
      leadLessonSourceUrl: text(world.lead_lesson_source_url),
      posterUrl: text(world.lead_lesson_poster_url),
    }));
}

export function localized(map, locale = 'en') {
  if (!map || typeof map !== 'object' || Array.isArray(map)) return '';
  return text(map[locale]) || text(map.en) || '';
}

/* ----------------------------------------------------------- discovery --- */

/* What is left to explore after the learner's own continuation. Ordered by the
   server's discovery ranking, with anything already surfaced above removed so
   Home never shows the same lesson twice. */
export function discoveryItems(library, {exclude = [], limit = 6} = {}) {
  const skip = new Set([...exclude].map(text).filter(Boolean));
  const items = libraryItemsById(library);
  const ordered = [];
  const seen = new Set();
  for (const sectionId of ['recommended', 'movie-animation', 'stories', 'daily-conversations', 'quick-practice', 'new']) {
    for (const id of sectionIds(library, sectionId)) {
      if (seen.has(id) || skip.has(id) || !items.has(id)) continue;
      seen.add(id);
      ordered.push(items.get(id));
      if (ordered.length >= limit) return ordered;
    }
  }
  // Anything the named rails missed still deserves to be discoverable.
  for (const [id, item] of items) {
    if (seen.has(id) || skip.has(id)) continue;
    seen.add(id);
    ordered.push(item);
    if (ordered.length >= limit) break;
  }
  return ordered;
}

/* Minutes, only when the duration is real. An unknown duration renders no
   duration rather than a plausible-looking zero. */
export function durationMinutes(item) {
  const ms = Number(item?.duration_ms);
  if (!Number.isFinite(ms) || ms <= 0) return null;
  return Math.max(1, Math.round(ms / 60000));
}
