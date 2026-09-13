/** Language-aware capability adapter; independent of routes and product shells. */

export type LibraryItem = {
  word: string;
  phonetic?: string;
  part_of_speech?: string;
  definition?: string;
  translation_vi?: string;
  added_at?: string;
  review_stage?: number;
  stage_label?: string;
  successful_recalls?: number;
  lapse_count?: number;
  last_reviewed_at?: string;
  next_review_at?: string;
  due?: boolean;
};

export const PAGE_SIZE = 10;
export const SOON_DAYS = 3;
const DAY = 86400000;

export type ItemType = 'word' | 'collocation' | 'phrasalVerb' | 'idiom' | 'proverb' | 'phrase' | 'measure' | 'separable' | 'colloquial' | 'xiehouyu';

/**
 * Order matters: the generic phrase term is a substring of the phrasal-verb
 * term, and "idiom" appears inside "idiomatic", so narrower rules go first.
 */
const TYPE_RULES: [ItemType, RegExp[]][] = [
  ['measure', [/measure\s*word/i, /classifier/i, /量词/, /lượng từ/i]],
  ['separable', [/separable/i, /离合词/, /ly hợp/i]],
  ['phrasalVerb', [/phrasal/i, /动词短语/, /cụm động từ/i]],
  ['collocation', [/collocat/i, /搭配/, /kết hợp từ/i]],
  ['idiom', [/idiom/i, /成语/, /thành ngữ/i]],
  ['xiehouyu', [/歇后语/, /allegorical/i]],
  ['proverb', [/proverb/i, /saying/i, /谚语/, /俗语/, /tục ngữ/i]],
  ['colloquial', [/惯用语/, /set\s*phrase/i, /quán ngữ/i]],
  ['phrase', [/phrase/i, /expression/i, /短语/, /cụm từ/i]],
];

/** The full list for each language, in the order a learner meets them. */
export const TYPE_ORDER_EN: readonly ItemType[] = ['word', 'collocation', 'phrasalVerb', 'idiom', 'proverb', 'phrase'];
export const TYPE_ORDER_ZH: readonly ItemType[] = ['word', 'collocation', 'measure', 'separable', 'idiom', 'colloquial', 'proverb', 'xiehouyu', 'phrase'];

/** A learner of Chinese meets these categories under their Chinese names. */
export const NATIVE_TYPE_NAMES: Partial<Record<ItemType, string>> = {
  word: '单词', collocation: '搭配', idiom: '成语', colloquial: '惯用语',
  proverb: '谚语', xiehouyu: '歇后语', separable: '离合词', measure: '量词', phrase: '短语',
};

export function labelledType(item: LibraryItem): ItemType | null {
  const label = String(item.part_of_speech || '').trim();
  if (!label) return null;
  for (const [key, patterns] of TYPE_RULES) {
    if (patterns.some((pattern) => pattern.test(label))) return key;
  }
  return null;
}

/**
 * What kind of thing this is: what the dictionary labelled it, or -- failing
 * that -- whether it reads as more than one unit in the language being learned.
 */
export function itemType(item: LibraryItem, language: string): ItemType {
  const labelled = labelledType(item);
  if (labelled) return labelled;
  const word = String(item.word || '').trim();
  const multi = language === 'zh' ? [...word].length > 3 : /\s/.test(word);
  return multi ? 'phrase' : 'word';
}

export function parseTime(value: string | undefined): number | null {
  const parsed = Date.parse(String(value || '').replace(' ', 'T'));
  return Number.isFinite(parsed) ? parsed : null;
}

/** Whole days between today and a scheduled date, both taken at midnight. */
export function daysFromNow(value: string | undefined, now: Date = new Date()): number | null {
  const at = parseTime(value);
  if (at === null) return null;
  const start = new Date(now); start.setHours(0, 0, 0, 0);
  const target = new Date(at); target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - start.getTime()) / DAY);
}

export function isSoon(item: LibraryItem, now?: Date): boolean {
  if (item.due) return false;
  const days = daysFromNow(item.next_review_at, now);
  return days !== null && days <= SOON_DAYS;
}

export function reviewedToday(item: LibraryItem, now?: Date): boolean {
  return daysFromNow(item.last_reviewed_at, now) === 0;
}

export type RelativeTone = 'due' | 'soon' | 'later' | 'none';

/** When this item comes back, as a phrase rather than a raw timestamp. */
export function relativeTone(item: LibraryItem, now?: Date): {tone: RelativeTone; days: number | null} {
  if (item.due) return {tone: 'due', days: 0};
  const days = daysFromNow(item.next_review_at, now);
  if (days === null) return {tone: 'none', days: null};
  if (days <= 0) return {tone: 'due', days};
  return {tone: days <= SOON_DAYS ? 'soon' : 'later', days};
}

/** `review_stage` runs 0-4, which is exactly the five dots the reference draws. */
export function masteryStage(item: LibraryItem): number {
  return Math.max(0, Math.min(4, Number(item.review_stage) || 0));
}

export function masteryTone(stage: number): 'strong' | 'good' | 'reviewing' | 'new' {
  return stage >= 3 ? 'strong' : stage >= 2 ? 'good' : stage >= 1 ? 'reviewing' : 'new';
}

export type LibraryCounts = {all: number; due: number; soon: number; later: number};

export function libraryCounts(items: readonly LibraryItem[], now?: Date): LibraryCounts {
  const due = items.filter((item) => item.due).length;
  const soon = items.filter((item) => isSoon(item, now)).length;
  return {all: items.length, due, soon, later: items.length - due - soon};
}

export function countsByType(items: readonly LibraryItem[], language: string): Record<string, number> {
  return items.reduce<Record<string, number>>((groups, item) => {
    const key = itemType(item, language);
    groups[key] = (groups[key] || 0) + 1;
    return groups;
  }, {});
}

/**
 * Every category the language has, whether or not this learner has met it, then
 * anything the dictionary labelled that the list does not name. An empty
 * category is still worth showing: it tells a learner the kind exists.
 */
export function typeTabs(items: readonly LibraryItem[], language: string): string[] {
  const order = language === 'zh' ? TYPE_ORDER_ZH : TYPE_ORDER_EN;
  const seen = countsByType(items, language);
  return [...order, ...Object.keys(seen).filter((key) => !(order as readonly string[]).includes(key))];
}

/**
 * Accuracy over recorded recalls only, and null when nothing has been recorded
 * -- an unanswered library is not 0% accurate.
 */
export function recallAccuracy(items: readonly LibraryItem[]): {accuracy: number | null; recalls: number; lapses: number} {
  const recalls = items.reduce((total, item) => total + (Number(item.successful_recalls) || 0), 0);
  const lapses = items.reduce((total, item) => total + (Number(item.lapse_count) || 0), 0);
  return {accuracy: recalls + lapses ? Math.round((recalls / (recalls + lapses)) * 100) : null, recalls, lapses};
}

/** The three parts of speech with the most items due, for the focus panel. */
export function focusAreas(items: readonly LibraryItem[], fallbackLabel: string): [string, number][] {
  const groups = items.filter((item) => item.due).reduce<Record<string, number>>((map, item) => {
    const key = String(item.part_of_speech || '').trim() || fallbackLabel;
    map[key] = (map[key] || 0) + 1;
    return map;
  }, {});
  return Object.entries(groups).sort((a, b) => b[1] - a[1]).slice(0, 3);
}

export type LibraryFilter = 'all' | 'due' | 'soon' | 'new';
export type LibrarySort = 'next' | 'added' | 'alpha' | 'mastery';

export function visibleItems(items: readonly LibraryItem[], view: {tab: string; filter: LibraryFilter; sort: LibrarySort}, language: string, now?: Date): LibraryItem[] {
  let rows = [...items];
  if (view.tab !== 'all') rows = rows.filter((item) => itemType(item, language) === view.tab);
  if (view.filter === 'due') rows = rows.filter((item) => item.due);
  else if (view.filter === 'soon') rows = rows.filter((item) => isSoon(item, now));
  else if (view.filter === 'new') rows = rows.filter((item) => !Number(item.review_stage));
  if (view.sort === 'alpha') rows.sort((a, b) => a.word.localeCompare(b.word));
  else if (view.sort === 'added') rows.sort((a, b) => String(b.added_at).localeCompare(String(a.added_at)));
  else if (view.sort === 'mastery') rows.sort((a, b) => (Number(b.review_stage) || 0) - (Number(a.review_stage) || 0));
  else rows.sort((a, b) => (a.due === b.due ? String(a.next_review_at).localeCompare(String(b.next_review_at)) : a.due ? -1 : 1));
  return rows;
}

export function pageOf<T>(rows: readonly T[], page: number, size: number = PAGE_SIZE): {slice: T[]; page: number; pages: number; from: number; to: number} {
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const current = Math.min(Math.max(1, page), pages);
  const slice = rows.slice((current - 1) * size, current * size);
  return {slice, page: current, pages, from: rows.length ? ((current - 1) * size) + 1 : 0, to: Math.min(current * size, rows.length)};
}
