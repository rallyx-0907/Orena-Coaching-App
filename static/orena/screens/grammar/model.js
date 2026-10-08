/* Pure data shaping for the Grammar Library (route "grammarlib") on the grammar content contract's catalogue
   projection (docs/project/GRAMMAR_CONTENT_CONTRACT.md §9; D-100). No DOM, no fetch:
   scripts/test_orena_screen_grammar.mjs exercises this against contract-shaped, test-only rows.

   A topic's title is `header.native_title` (+ `native_title_pinyin` for Chinese), never `header.title` (contract §1):
   the point's name in the language being learned. Counting and grouping by function within a level is the UI's job
   (§9: "đếm và nhóm theo function trong mỗi level là việc của UI"). */
import { contractText, levelCode, sortCatalog } from '../../product/grammar-source.js';

/* A level's short code, "B1" or "HSK3": the design's level button and hero title. */
export function levelTile(level) {
  return levelCode(level).replace(/\s+/g, '');
}

/* ---- The Library (design export 2026-10-08, frames "Grammar Library" and "Grammar category"; state `glVals`) -----------
   Composed for the corpus as it is:
   - categories are the corpus's functions (the contract's topic layer, §9) that have points at the chosen level, in
     the catalogue's `functions` order; each takes one of the design's six category hues and icons by its place in that
     list, so a function keeps its look across levels (the corpus carries no hue or icon - UI_BACKEND_GAPS G-14);
   - status is what the progress API knows: learned (a completed point, with its last quiz score) or not started.
     The design's third state, "learning" with a percentage, and the bookmark have no source and are not drawn (G-14);
   - continue learning: the design shows in-progress topics; with no such state it shows the next three not-yet-learned
     points of the level in catalogue order (the human asked for the section, 2026-10-08).
   The topic card's "meaning" line is `header.sub` in the support language (a short gloss, as the design's), falling
   back to `header.title`; its reading is the pinyin of `native_title_pinyin`. */

export const CATEGORY_LOOKS = Object.freeze([
  { hue: 'var(--gcat-1)', icon: 'message-square' },
  { hue: 'var(--gcat-2)', icon: 'zap' },
  { hue: 'var(--gcat-3)', icon: 'link' },
  { hue: 'var(--gcat-4)', icon: 'arrow-up-right' },
  { hue: 'var(--gcat-5)', icon: 'star' },
  { hue: 'var(--gcat-6)', icon: 'chart-column' },
]);
export const CONTINUE_LIMIT = 3;
export const PANEL_LIMIT = 6;
export const SORTS = Object.freeze(['def', 'st', 'az']);
export const STATUSES = Object.freeze(['all', 'L', 'N']);

function searchable(row) {
  const header = row.header || {};
  const parts = [header.native_title, ...(Array.isArray(header.native_title_pinyin) ? header.native_title_pinyin : [])];
  for (const field of [header.title, header.sub]) {
    if (field && typeof field === 'object') parts.push(...Object.values(field));
    else if (field) parts.push(field);
  }
  return parts.filter(Boolean).join(' ').toLowerCase();
}

/* `rows` the catalogue points, `functions` its functions, `progress` the progress API's list, `current` the learner's
   declared level code; `state` = {level, cat, all, q, st, sort}. */
export function buildLibrary({ rows = [], functions = [], progress = [], current = '', state = {}, support = 'en', ui = '', t = (key) => key } = {}) {
  const list = sortCatalog(Array.isArray(rows) ? rows : []);
  const done = new Map((progress || []).map((entry) => [String(entry.point_id), entry]));
  const fnOrder = (Array.isArray(functions) ? functions : []).map((fn) => fn.id);
  // A category is navigation, so its name follows the interface language; a topic's meaning stays in the support
  // language (design review 2026-10-08, UX rule 26).
  const fnName = new Map((functions || []).map((fn) => [fn.id, contractText(fn.title, ui || support) || fn.id]));

  const levels = [];
  for (const row of list) {
    const key = levelTile(row.level);
    let level = levels.find((entry) => entry.key === key);
    if (!level) levels.push((level = { key, level: row.level, count: 0 }));
    level.count += 1;
  }
  const selectedKey = [state.level, current].find((key) => levels.some((entry) => entry.key === key)) || levels[0]?.key || '';
  for (const level of levels) level.selected = level.key === selectedKey;
  const chosen = levels.find((entry) => entry.selected) || null;
  const atLevel = chosen ? list.filter((row) => levelTile(row.level) === chosen.key) : [];

  const catIds = [...new Set(atLevel.map((row) => row.function || ''))].sort((a, b) => {
    const ia = fnOrder.indexOf(a), ib = fnOrder.indexOf(b);
    return (ia < 0 ? 1e6 : ia) - (ib < 0 ? 1e6 : ib) || a.localeCompare(b);
  });
  const lookOf = (id) => {
    const index = fnOrder.indexOf(id);
    return CATEGORY_LOOKS[(index < 0 ? fnOrder.length : index) % CATEGORY_LOOKS.length];
  };
  const catName = (id) => (id ? fnName.get(id) || id : t('otherTopic'));

  const item = (row) => {
    const header = row.header || {};
    const state = done.get(String(row.id));
    const cat = row.function || '';
    return {
      id: String(row.id),
      title: String(header.native_title || ''),
      reading: Array.isArray(header.native_title_pinyin) ? header.native_title_pinyin.join(' ') : '',
      lang: String(row.id).startsWith('zh.') ? 'zh' : 'en',
      mean: contractText(header.sub, support) || contractText(header.title, support),
      cat,
      tag: catName(cat),
      ...lookOf(cat),
      learned: Boolean(state),
      score: state?.last_quiz && Number.isFinite(state.last_quiz.total) ? { correct: state.last_quiz.correct, total: state.last_quiz.total } : null,
    };
  };
  const items = atLevel.map(item);
  const q = String(state.q || '').trim().toLowerCase();
  const st = STATUSES.includes(state.st) ? state.st : 'all';
  const match = (entry, row) => (!q || searchable(row).includes(q)) && (st === 'all' || (st === 'L') === entry.learned);
  const sort = SORTS.includes(state.sort) ? state.sort : 'def';
  const sortList = (entries) => {
    if (sort === 'st') return [...entries].sort((a, b) => Number(a.learned) - Number(b.learned));
    if (sort === 'az') return [...entries].sort((a, b) => (a.reading || a.title).localeCompare(b.reading || b.title));
    return entries;
  };
  const filtered = (keep) => sortList(items.filter((entry, i) => keep(entry) && match(entry, atLevel[i])));

  const categories = catIds.map((id) => {
    const members = items.filter((entry) => entry.cat === id);
    return { id, name: catName(id), count: members.length, examples: members.slice(0, 3).map((entry) => entry.title), more: members.length > 3, ...lookOf(id) };
  });
  const catId = catIds.includes(state.cat) ? state.cat : catIds[0] ?? '';
  for (const category of categories) category.selected = category.id === catId;
  const panelAll = filtered((entry) => entry.cat === catId);
  const allCat = catIds.includes(state.all) ? state.all : 'all';
  const all = filtered((entry) => allCat === 'all' || entry.cat === allCat);
  const learned = items.filter((entry) => entry.learned).length;

  return {
    levels,
    level: chosen,
    stats: { total: items.length, learned, notStarted: items.length - learned },
    continue: items.filter((entry) => !entry.learned).slice(0, CONTINUE_LIMIT),
    categories,
    panel: categories.find((category) => category.selected) || null,
    panelItems: panelAll.slice(0, PANEL_LIMIT),
    allCat,
    all,
    filtering: Boolean(q) || st !== 'all',
    q: String(state.q || ''),
    st,
    sort,
  };
}
