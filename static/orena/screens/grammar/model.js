/* Pure data shaping for the Grammar Library (frame 44, route "grammarlib") on the grammar content
   contract's catalogue projection (docs/project/GRAMMAR_CONTENT_CONTRACT.md §9; D-100). No DOM,
   no fetch: scripts/test_orena_screen_grammar.mjs exercises this against a contract-shaped,
   test-only fixture.

   What each card draws, from which field (frame 44's concept card):
   - title   `header.native_title` (+ `native_title_pinyin` for Chinese), never `header.title`
             (contract §1): the point's name in the language being learned;
   - note    `header.title` in the support language - the gloss §1 names for "dòng phụ";
   - tile    the level value (`level.value`, CEFR A1-C2 or HSK 1-9).
   How the page is composed from them is buildLibrary below (§9: "đếm và nhóm theo function trong mỗi level là
   việc của UI"). Not drawn, for want of a source: the frame's "recent errors" and "saved" groups. */
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

/* ---- The Library's information architecture (human decision 2026-10-08, after the PR #107 review) -------------------
   Frame 44 draws concept groups "by what matters for you right now" (recent errors, at your level, saved, recommended).
   With 215 / 380 real points a group per level became one long flat grid, so the page is composed of the frame's own
   group and card from the top down:
   - levels: one card per level of the corpus - its points and how many the learner completed - the learner's level
     marked; choosing one sets the level the rest of the page reads;
   - continue: the next points not completed yet at that level, in curriculum order (function, sequence) - the frame's
     "At your level" group;
   - topics: the corpus's functions (the contract's topic layer, §9), with their counts at that level;
   - all: every point of that level (and topic, when one is chosen), in sections by topic, at the end.
   Inside a level-scoped section the level tile would repeat the same code on every card, so cards there carry none; a
   card's tag is the learner's own state: done (with the last quiz score) or new. Nothing here is invented learner data:
   completion comes from GET /api/grammar/v1/progress, the level from the profile's declared level. */

export const CONTINUE_LIMIT = 6;
export const TOPIC_PREVIEW = 8;

function levelKey(level) {
  return levelTile(level);
}

function itemOf(row, support, done) {
  const header = row.header || row;
  const state = done.get(String(row.id));
  return {
    id: String(row.id),
    title: String(header.native_title || ''),
    titlePinyin: Array.isArray(header.native_title_pinyin) ? header.native_title_pinyin : null,
    lang: String(row.id).startsWith('zh.') ? 'zh' : 'en',
    note: contractText(header.title, support),
    done: Boolean(state),
    score: state?.last_quiz && Number.isFinite(state.last_quiz.total) ? { correct: state.last_quiz.correct, total: state.last_quiz.total } : null,
  };
}

/* `progress` is the progress API's list ({point_id, last_quiz}); `current` the profile's declared level code ("B1",
   "HSK3"); `selected` the level the learner picked on this page; `topic` a function id or ''. */
export function buildLibrary({ rows = [], functions = [], progress = [], current = '', selected = '', topic = '', support = 'en', t = (key) => key } = {}) {
  const list = sortCatalog(Array.isArray(rows) ? rows : []);
  const done = new Map((progress || []).map((entry) => [String(entry.point_id), entry]));
  const levels = [];
  for (const row of list) {
    const key = levelKey(row.level);
    let level = levels.find((entry) => entry.key === key);
    if (!level) {
      level = { key, level: row.level, heading: levelHeading(row.level, t), count: 0, done: 0 };
      levels.push(level);
    }
    level.count += 1;
    if (done.has(String(row.id))) level.done += 1;
  }
  const currentKey = levels.some((entry) => entry.key === current) ? current : '';
  const chosen = levels.find((entry) => entry.key === selected) || levels.find((entry) => entry.key === currentKey) || levels[0] || null;
  for (const level of levels) {
    level.current = level.key === currentKey;
    level.selected = Boolean(chosen) && level.key === chosen.key;
  }
  const atLevel = chosen ? list.filter((row) => levelKey(row.level) === chosen.key) : [];
  const names = new Map(functions.map((fn) => [fn.id, contractText(fn.title, support) || fn.id]));
  const topicName = (id) => (id ? names.get(id) || id : t('otherTopic'));

  const continueItems = atLevel.filter((row) => !done.has(String(row.id))).slice(0, CONTINUE_LIMIT).map((row) => itemOf(row, support, done));

  const topics = [];
  for (const row of atLevel) {
    const id = row.function || '';
    let entry = topics.find((item) => item.id === id);
    if (!entry) {
      entry = { id, title: topicName(id), count: 0, done: 0 };
      topics.push(entry);
    }
    entry.count += 1;
    if (done.has(String(row.id))) entry.done += 1;
  }
  topics.sort((a, b) => b.count - a.count || a.title.localeCompare(b.title));
  const activeTopic = topics.some((entry) => entry.id === topic) ? topic : '';
  for (const entry of topics) entry.selected = entry.id === activeTopic;

  const sections = [];
  for (const row of atLevel) {
    const id = row.function || '';
    if (activeTopic && id !== activeTopic) continue;
    let section = sections.find((item) => item.id === id);
    if (!section) {
      section = { id, title: topicName(id), items: [] };
      sections.push(section);
    }
    section.items.push(itemOf(row, support, done));
  }

  // Sections follow the topics' order (largest first), so the page reads the same way down as across.
  const order = new Map(topics.map((entry, index) => [entry.id, index]));
  sections.sort((x, y) => order.get(x.id) - order.get(y.id));

  return {
    levels,
    level: chosen,
    continue: continueItems,
    levelComplete: Boolean(chosen) && chosen.count > 0 && chosen.done === chosen.count,
    topics,
    topic: activeTopic,
    sections,
    shown: sections.reduce((n, section) => n + section.items.length, 0),
  };
}
