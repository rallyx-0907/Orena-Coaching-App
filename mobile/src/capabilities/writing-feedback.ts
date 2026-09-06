/** Language-aware capability adapter; independent of routes and product shells. */

export type GuidanceMode = 'guided' | 'examples' | 'concise' | 'advanced';
export type WordRole = 'verb' | 'noun' | 'adjective' | 'adverb';
export type SupportKey = 'grammar' | 'vocabulary' | 'expressions' | 'roles';
export type SupportState = Record<SupportKey, boolean>;

export const WORD_ROLES: readonly WordRole[] = ['verb', 'noun', 'adjective', 'adverb'];
export const SUPPORT_KEYS: readonly SupportKey[] = ['grammar', 'vocabulary', 'expressions', 'roles'];

/** The categories the evaluator actually reports, in write.js's order. */
export const RUBRIC_CATEGORIES = [
  'task_achievement', 'coherence', 'grammar', 'verb_tense',
  'vocabulary', 'collocation', 'naturalness',
] as const;

const BAND_TIERS: Record<string, string> = {
  A1: 'beginner', A2: 'elementary', B1: 'intermediate',
  B2: 'upper', C1: 'advanced', C2: 'proficient',
  HSK1: 'beginner', HSK2: 'beginner', HSK3: 'elementary',
  HSK4: 'intermediate', HSK5: 'upper', HSK6: 'advanced', 'HSK7-9': 'proficient',
};

/** CEFR and HSK both collapse onto the same six-step ladder. */
export function bandTier(level: string): string | null {
  return BAND_TIERS[String(level || '').toUpperCase()] ?? BAND_TIERS[level] ?? null;
}

const EN_RANK: Record<string, number> = {A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6};
const ZH_RANK: Record<string, number> = {HSK1: 1, HSK2: 2, HSK3: 3, HSK4: 4, HSK5: 5, HSK6: 6, 'HSK7-9': 7};

function rankFor(language: 'en' | 'zh', level: string): number {
  return Number((language === 'zh' ? ZH_RANK : EN_RANK)[level] || 0);
}

export function guidanceMode(style: string | undefined, language: 'en' | 'zh', level: string): GuidanceMode {
  const chosen = style || 'guided';
  const rank = rankFor(language, level);
  if (chosen === 'deep') return 'advanced';
  if (chosen === 'concise') return 'concise';
  if (chosen === 'examples') return 'examples';
  if (language === 'zh') {
    if (rank && rank <= 2) return 'guided';
    if (rank >= 6) return 'advanced';
  } else {
    if (rank && rank <= 2) return 'guided';
    if (rank >= 5) return 'advanced';
  }
  return 'guided';
}

/** adaptive.js ships these labels in English for every locale; kept as-is. */
export function guidanceLabel(mode: GuidanceMode): string {
  return {guided: 'Step-by-step', examples: 'Examples first', concise: 'Concise', advanced: 'Deep analysis'}[mode] || 'Adaptive';
}

export function writingScaffold(mode: GuidanceMode, language: 'en' | 'zh'): {title: string; items: string[]} {
  if (mode === 'advanced') {
    return {
      title: language === 'zh' ? '保留自主空间' : 'Keep your autonomy',
      items: language === 'zh'
        ? ['先写真实观点', '需要时再增加限制条件', '提交后再深入分析']
        : ['Write the real idea first', 'Add constraints only when they help', 'Use analysis after the draft exists'],
    };
  }
  if (mode === 'concise') {
    return {
      title: language === 'zh' ? '只保留必要提示' : 'Only the essentials',
      items: language === 'zh'
        ? ['表达一个清楚意思', '提交后只看最重要问题']
        : ['Express one clear idea', 'Review only the highest-value issue after submission'],
    };
  }
  if (mode === 'examples') {
    return {
      title: language === 'zh' ? '先用例子建立方向' : 'Use examples as anchors',
      items: language === 'zh'
        ? ['先写你会表达的版本', '提交后比较更自然的用法', '再回到自己的句子修改']
        : ['Write the version you can produce now', 'Compare it with stronger usage after review', 'Return to your own sentence and revise'],
    };
  }
  return {
    title: language === 'zh' ? '一步一步，不需要一次写完美' : 'One step at a time',
    items: language === 'zh'
      ? ['先把意思写清楚', '再补充必要支持', '最后检查结尾是否完整']
      : ['Get the meaning down first', 'Add enough support for the idea', 'Finish with a clear ending'],
  };
}

export type DifficultyAdjustment = {state: string; delta: number; key: string};

export function difficultyAdjustment(recommendation: unknown): DifficultyAdjustment | null {
  const value = (recommendation as {difficulty?: unknown} | null | undefined)?.difficulty;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as {state?: unknown; length_delta?: unknown};
  const state = ['stretch', 'scaffold', 'hold', 'insufficient'].includes(String(record.state)) ? String(record.state) : 'insufficient';
  const rawDelta = record.length_delta;
  if (typeof rawDelta !== 'number' || !Number.isFinite(rawDelta) || !Number.isInteger(rawDelta)) {
    return {state: 'insufficient', delta: 0, key: 'write.difficulty_insufficient'};
  }
  return {state, delta: Math.abs(rawDelta), key: `write.difficulty_${state}`};
}

/** language.js's countUnits: Han characters + latin words for zh, words for en. */
export function countUnits(text: string, language: 'en' | 'zh'): number {
  const value = String(text || '');
  if (language === 'zh') {
    const han = (value.match(/[㐀-䶿一-鿿]/g) || []).length;
    const latin = (value.match(/[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*/g) || []).length;
    return han + latin;
  }
  return (value.match(/\b[\w'-]+\b/g) || []).length;
}

const WATCHLIST_CATEGORIES = new Set([
  'article', 'tense', 'agreement', 'word_choice', 'word_form', 'preposition',
  'sentence_structure', 'punctuation', 'coherence', 'task', 'naturalness',
  'spelling', 'other', 'word_order', 'particle', 'aspect', 'complement',
  'measure_word', 'ba_sentence', 'bei_sentence', 'conjunction',
  'character_choice', 'collocation', 'redundancy', 'register',
]);

export type WatchlistItem = {category: string; status: string; total: number; older: number; newer: number};

function numberValue(raw: unknown): number | null {
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string' && raw.trim() !== '') {
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

/**
 * write.js's normalizedWatchlist, gate for gate: only recurring categories with
 * internally consistent, actually-rising counts survive, so the panel never
 * shows a pattern the evidence does not support.
 */
export function normalizedWatchlist(value: unknown): WatchlistItem[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    .map((item) => {
      const category = typeof item.category === 'string' ? item.category.trim() : '';
      const status = typeof item.status === 'string' ? item.status.trim().toLowerCase() : '';
      const total = numberValue(item.total);
      const older = numberValue(item.older);
      const newer = numberValue(item.newer);
      if (!WATCHLIST_CATEGORIES.has(category) || status !== 'recurring'
        || total === null || !Number.isInteger(total) || total <= 0
        || older === null || !Number.isInteger(older) || older < 0
        || newer === null || !Number.isInteger(newer) || newer < 0
        || total !== older + newer || total < 3 || older < 1 || newer < older) return null;
      return {category, status, total, older, newer};
    })
    .filter((item): item is WatchlistItem => item !== null)
    .sort((a, b) => b.total - a.total)
    .slice(0, 4);
}

export function watchlistTrend(item: WatchlistItem): 'up' | 'down' | 'flat' {
  if (item.newer < item.older) return 'down';
  if (item.newer > item.older) return 'up';
  return 'flat';
}

export type SavedLabel = {key: 'write.saved_never' | 'write.saved_now' | 'write.saved_minutes' | 'write.saved_hours'; n?: number};

/** write.js's savedLabel, as a key plus its count so the screen can translate it. */
export function savedLabel(savedAt: number | null | undefined, now: number = Date.now()): SavedLabel {
  const raw = typeof savedAt === 'number' ? savedAt : null;
  if (raw === null || !Number.isFinite(raw) || !Number.isInteger(raw) || raw <= 0) return {key: 'write.saved_never'};
  const minutes = Math.floor((now - raw) / 60000);
  if (!Number.isFinite(minutes) || minutes < 0) return {key: 'write.saved_never'};
  if (minutes < 1) return {key: 'write.saved_now'};
  if (minutes < 60) return {key: 'write.saved_minutes', n: minutes};
  return {key: 'write.saved_hours', n: Math.floor(minutes / 60)};
}

/**
 * write.js's writingEvaluationErrorMessage: the evaluator's own categories name
 * what actually failed, so the learner is not told "unavailable" when the real
 * answer is that their learning language changed underneath the draft.
 */
export function evaluationErrorKey(serverCategory: string | undefined): string {
  const byCategory: Record<string, string> = {
    evaluation_unavailable: 'write.evaluation_unavailable',
    evaluation_provider_failure: 'write.evaluation_provider_failure',
    language_scope_mismatch: 'write.language_scope_mismatch',
  };
  return byCategory[String(serverCategory || '').trim()] || 'write.review_failed';
}
