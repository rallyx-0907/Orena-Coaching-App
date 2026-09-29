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

/* languages-4 (2) / finding B.2: `level_names[level]` (writing_coach/languages/grammar_registry.py
   `GrammarProvider.level_names`) is the backend's own English label ("Foundation", "Upper-
   intermediate", …) for a closed, small value space - exactly nine distinct labels across both
   providers, the English track's six (A1-C2) and the Chinese/HSK track's seven (HSK1-7-9), each
   provider reusing the same English word for the levels that mean the same standing. Closed enough
   to map the level *code* (not the backend's own English text, which is not itself translated) to
   real interface copy in en/vi/zh (grammar/copy.js) - this frontend cannot change backend code, so
   the mapping lives here, keyed by the one stable thing both providers already return: `library.
   levels`, the same array `level` itself comes from. A level code this table does not recognise
   (a future provider) falls back to the raw code rather than guessing a label. */
const LEVEL_NAME_KEY = Object.freeze({
  A1: 'levelFoundation', A2: 'levelCore', B1: 'levelIntermediate', B2: 'levelUpperIntermediate',
  C1: 'levelAdvanced', C2: 'levelMastery',
  HSK1: 'levelFoundation', HSK2: 'levelBasic', HSK3: 'levelLowerIntermediate', HSK4: 'levelIntermediate',
  HSK5: 'levelUpperIntermediate', HSK6: 'levelAdvanced', 'HSK7-9': 'levelAdvancedMastery',
});

export function levelName(level, t) {
  const key = LEVEL_NAME_KEY[level];
  return key ? t(key) : String(level || '');
}

/* One row per level the API lists, in the order it lists them (curriculum order, A1..C2), each
   with the concepts of that level as the group's grid. A level with no concepts (should not
   happen against a real catalogue) is left out rather than drawn empty. */
export function buildLibraryGroups(library, support = 'en', t) {
  const lessons = Array.isArray(library?.lessons) ? library.lessons : [];
  const levels = Array.isArray(library?.levels) ? library.levels : [];
  const items = grammarShelf({ lessons }, [], support);
  const groups = [];
  for (const level of levels) {
    const levelItems = items.filter((item) => item.level === level);
    if (!levelItems.length) continue;
    const rollup = grammarFamilies(levelItems)[0];
    const completed = levelItems.filter((item) => item.completed).length;
    groups.push({
      level,
      levelName: levelName(level, t),
      // languages-4 (1) / finding A: whether this group's own lesson titles are genuine
      // target-language content this build can honestly mark with `lang`. The English track's
      // titles are real English at every level (docs/project/UI_BACKEND_GAPS.md N-33, spot-checked
      // against writing_coach/languages/english/grammar_curriculum.json); the Chinese/HSK track's
      // titles are a content gap - authored in Vietnamese only, not Chinese, with no locale-map
      // shape to select from (N-33) - so marking them `lang="zh"` would misrepresent Vietnamese
      // text as Chinese. `library.levels` (and so every group built from it) is scoped to one
      // provider per response - never a mix - so this is decided once per group, not per item.
      titleLang: level.startsWith('HSK') ? '' : 'en',
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
