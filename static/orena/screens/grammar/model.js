/* Pure data shaping for the Grammar Library (frame 44, route "grammarlib"). No DOM, no fetch: a
   node gate (scripts/test_orena_screen_grammar.mjs) exercises this directly.

   The frame's own mock draws four fixed groups ("from your recent errors" / "at your level" /
   "saved concepts" / "recommended next") - sample content, not a data contract (D-068). The real
   backend (GET /api/library/grammar) has no per-learner "recent errors" feed, no saved-concept
   list and no recommendation ranking (Design Contract rule 40: nothing here invents one). What it
   does have, and what this groups by, is each lesson's own `level` and `module`/`category` - the
   same fields product/grammar-shelf.js's grammarFamilies() already groups on for the old UI. This
   keeps the frame's drawn shape (a heading, a real hint, a grid of tappable concept cards) while
   sourcing every group from a field the API actually returns. Recorded as a backend gap in
   SCRATCH/reports/grammar.md, not resolved by inventing the mock's other three groups. */
import { grammarShelf, grammarFamilies } from '../../product/grammar-shelf.js';

/* One row per level the API lists, in the order it lists them (curriculum order, A1..C2), each
   with the concepts of that level as the group's grid. A level with no concepts (should not
   happen against a real catalogue) is left out rather than drawn empty. */
export function buildLibraryGroups(library, support = 'en') {
  const lessons = Array.isArray(library?.lessons) ? library.lessons : [];
  const levels = Array.isArray(library?.levels) ? library.levels : [];
  const levelNames = library?.level_names || {};
  const items = grammarShelf({ lessons }, [], support);
  const groups = [];
  for (const level of levels) {
    const levelItems = items.filter((item) => item.level === level);
    if (!levelItems.length) continue;
    const rollup = grammarFamilies(levelItems)[0];
    const completed = levelItems.filter((item) => item.completed).length;
    groups.push({
      level,
      levelName: levelNames[level] || level,
      topics: rollup?.families?.length || 0,
      total: levelItems.length,
      completed,
      items: levelItems.map((item) => ({
        id: item.id,
        title: item.title,
        level: item.level,
        note: item.heading || item.line || item.module || item.category || '',
        completed: Boolean(item.completed),
      })),
    });
  }
  return groups;
}

/* Every lesson dropped by grammarShelf (kind === 'review', or no line at all) - so a caller can
   report real coverage instead of a silently smaller total (rule 40). */
export function droppedCount(library) {
  const lessons = Array.isArray(library?.lessons) ? library.lessons : [];
  const kept = new Set(grammarShelf({ lessons }, [], 'en').map((item) => item.id));
  return lessons.filter((lesson) => !kept.has(String(lesson.id))).length;
}
