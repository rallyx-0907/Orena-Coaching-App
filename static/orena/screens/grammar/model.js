/* Pure data shaping for the Grammar Library (frame 44, route "grammarlib") on the grammar content
   contract's catalogue projection (docs/project/GRAMMAR_CONTENT_CONTRACT.md §9; D-100). No DOM,
   no fetch: scripts/test_orena_screen_grammar.mjs exercises this against a contract-shaped,
   test-only fixture.

   What each card draws, from which field (frame 44's concept card):
   - title   `header.native_title` (+ `native_title_pinyin` for Chinese), never `header.title`
             (contract §1): the point's name in the language being learned;
   - note    `header.title` in the support language - the gloss §1 names for "dòng phụ";
   - tile    the level value (`level.value`, CEFR A1-C2 or HSK 1-9).
   Groups are one per level, in `level.rank` order; inside a group the rows keep the feeder's
   `function`, `sequence` order, and the hint counts the group's `function` values (§9: "đếm và
   nhóm theo function trong mỗi level là việc của UI").

   Not drawn, because the content does not carry it (§9: learner state is joined by id and has no
   source yet): the frame's four sample groups (recent errors, at your level, saved, recommended)
   and the per-card status tag. Recorded in docs/project/UI_BACKEND_GAPS.md, not invented. */
import { contractText, levelCode, sortCatalog } from '../../product/grammar-source.js';

/* Level names (interface copy, grammar/copy.js). CEFR by its six levels; HSK 3.0 by its three
   bands (初等 1-3, 中等 4-6, 高等 7-9), the level number itself staying in the heading. */
const CEFR_KEY = Object.freeze({ A1: 'cefrA1', A2: 'cefrA2', B1: 'cefrB1', B2: 'cefrB2', C1: 'cefrC1', C2: 'cefrC2' });

export function levelNameKey(level) {
  if (level?.framework === 'hsk3') {
    const n = Number(level.value);
    if (!Number.isInteger(n) || n < 1 || n > 9) return '';
    return n <= 3 ? 'hskBand1' : n <= 6 ? 'hskBand2' : 'hskBand3';
  }
  if (level?.framework === 'cefr') return CEFR_KEY[String(level.value || '').toUpperCase()] || '';
  return '';
}

/* "B1 · Intermediate", "HSK 3 · Elementary" - an unknown level shows its bare code, never a guessed
   name. */
export function levelHeading(level, t) {
  const code = levelCode(level);
  const key = levelNameKey(level);
  return key ? t('levelHeading', { code, name: t(key) }) : code;
}

/* The 44x44 tile's text: the level value, "B1" or "HSK3" (the frame's tile holds a short code). */
export function levelTile(level) {
  return levelCode(level).replace(/\s+/g, '');
}

export function buildLibraryGroups(rows, support = 'en', t = (key) => key) {
  const list = Array.isArray(rows) ? sortCatalog(rows) : [];
  const groups = [];
  for (const row of list) {
    const header = row.header || row;
    const key = `${row.level?.framework || ''}:${row.level?.value ?? ''}`;
    let group = groups.find((entry) => entry.key === key);
    if (!group) {
      group = { key, level: row.level, heading: levelHeading(row.level, t), functions: new Set(), items: [] };
      groups.push(group);
    }
    if (row.function) group.functions.add(row.function);
    group.items.push({
      id: String(row.id),
      title: String(header.native_title || ''),
      titlePinyin: Array.isArray(header.native_title_pinyin) ? header.native_title_pinyin : null,
      lang: String(row.id).startsWith('zh.') ? 'zh' : 'en',
      note: contractText(header.title, support),
      tile: levelTile(row.level),
    });
  }
  return groups.map(({ functions, ...group }) => ({ ...group, topics: functions.size }));
}
