/** Language-aware capability adapter; independent of routes and product shells. */

export type EvidenceItem = {
  category?: string; fragment?: string; suggestion?: string; confidence?: number;
  explanation_vi?: string; explanation_en?: string; explanation_zh?: string;
  mini_rule_vi?: string; mini_rule_en?: string; mini_rule_zh?: string;
};

/** review.js's scoreBand thresholds, as message keys the screen translates. */
export function scoreBandKey(overall: unknown): string | null {
  const value = Number(overall);
  if (!Number.isFinite(value)) return null;
  if (value >= 90) return 'review.score_excellent';
  if (value >= 78) return 'review.score_strong';
  if (value >= 65) return 'review.score_good';
  if (value >= 50) return 'review.score_fair';
  return 'review.score_weak';
}

/**
 * The evaluator reports confidence in the evidence, not severity of the
 * mistake. Bands mirror the confidence filter the backend already applies.
 */
export function confidenceBand(item: {confidence?: unknown} = {}): 'high' | 'medium' | 'low' {
  const value = Number(item.confidence);
  if (!Number.isFinite(value)) return 'medium';
  if (value >= 0.8) return 'high';
  if (value >= 0.6) return 'medium';
  return 'low';
}

/** review.js only keeps evidence that actually quotes the learner's own text. */
export function normalizedEvidenceItems(value: unknown): EvidenceItem[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is EvidenceItem =>
    Boolean(item) && typeof item === 'object' && !Array.isArray(item)
    && typeof (item as EvidenceItem).fragment === 'string'
    && (item as EvidenceItem).fragment!.trim().length > 0);
}

const CATEGORY_ALIASES: Record<string, string> = {
  article: 'grammar', article_usage: 'grammar', subject_verb_agreement: 'grammar',
  word_order: 'grammar', sentence_structure: 'grammar',
  verb_form: 'verb_tense', tense: 'verb_tense',
  word_choice: 'vocabulary', lexical_choice: 'vocabulary', precision: 'vocabulary',
  organization: 'coherence', organisation: 'coherence', linking: 'coherence', flow: 'coherence',
  tone: 'naturalness', register: 'naturalness',
};

/** support.js's categoryKey: many reported categories share one explanation. */
export function categoryKey(category: string | undefined): string {
  const key = String(category || 'expression').toLowerCase().replace(/-/g, '_').replace(/ /g, '_');
  return CATEGORY_ALIASES[key] || key;
}

const CATEGORY_REASON: Record<'en' | 'zh', Record<string, string>> = {
  en: {
    grammar: 'The new version makes the grammatical relationship clearer and reduces ambiguity in time, number, or sentence structure.',
    verb_tense: 'The new version aligns the verb time more clearly with the time frame already signaled by the sentence.',
    collocation: 'The new version uses a more conventional word combination, so the phrase reads less like a literal translation.',
    vocabulary: 'The new version chooses a word that matches the intended meaning more precisely.',
    naturalness: 'The new version removes wording that sounds translated or unusually formal for this context.',
    coherence: 'The new version makes the relationship between ideas easier to follow.',
    task_achievement: 'The new version answers the task more directly and makes the key information easier to identify.',
    expression: 'The new version keeps the meaning while making the phrasing clearer and easier to reuse.',
  },
  zh: {
    grammar: '新的表达让语法关系更清楚，减少时态、数量或句子结构上的歧义。',
    verb_tense: '新的表达让动词时间和句子中的时间信息更一致。',
    collocation: '新的表达使用更常见的词语搭配，减少逐字翻译的感觉。',
    vocabulary: '新的表达选择了更准确的词来表达原意。',
    naturalness: '新的表达减少生硬或直译感，更符合这个语境里的自然用法。',
    coherence: '新的表达让句子之间的关系更清楚，更容易跟上思路。',
    task_achievement: '新的表达更直接回应任务要求，并突出关键信息。',
    expression: '新的表达保留原意，同时让说法更清楚、更容易复用。',
  },
};

const CATEGORY_RULE: Record<'en' | 'zh', Record<string, string>> = {
  en: {
    verb_tense: 'Match the main verb to the time signal in the sentence before polishing vocabulary or style.',
    collocation: 'Learn natural word combinations as units instead of memorizing isolated words.',
    naturalness: 'Compare how words are normally combined in this context, not only whether the sentence is grammatically possible.',
    grammar: 'Identify the main grammatical relationship first, then refine smaller details.',
    vocabulary: 'Choose words for meaning and context, not simply because they sound more advanced.',
    coherence: 'Make it clear whether each sentence adds, explains, contrasts, or concludes the previous idea.',
    expression: 'Preserve the meaning first, then make the phrasing clearer and more natural.',
  },
  zh: {
    verb_tense: '先确认句子的时间信息，再调整动词形式和其他表达。',
    collocation: '把自然搭配当成一个整体来学习，而不是只记单个词。',
    naturalness: '不仅看语法是否成立，也要看这个语境里是否真的这样搭配。',
    grammar: '先确定句子的主要语法关系，再处理小细节。',
    vocabulary: '按意义和语境选词，不要只追求“更高级”的词。',
    coherence: '让每句话和上一句之间的补充、解释、对比或结论关系清楚。',
    expression: '先保留原意，再让表达更清楚、更自然。',
  },
};

export function categoryReason(category: string | undefined, locale: 'en' | 'zh'): string {
  const table = CATEGORY_REASON[locale] ?? CATEGORY_REASON.en;
  return table[categoryKey(category)] || table.expression || CATEGORY_REASON.en.expression!;
}

export function categoryRule(category: string | undefined, locale: 'en' | 'zh'): string {
  const table = CATEGORY_RULE[locale] ?? CATEGORY_RULE.en;
  return table[categoryKey(category)] || table.expression || CATEGORY_RULE.en.expression!;
}

export type Metrics = Record<string, number>;

/** feedback.js's metricsFrom: the five rubric dimensions the evaluator scores. */
export function metricsFrom(result: Record<string, unknown> = {}): Metrics {
  return {
    grammar: Number(result.grammar || 0),
    vocabulary: Number(result.vocabulary || 0),
    coherence: Number(result.coherence || 0),
    task_achievement: Number(result.task_achievement || 0),
    naturalness: Number(result.naturalness || 0),
  };
}

export function weakestMetric(metrics: Metrics): {key: string; value: number} | null {
  const entries = Object.entries(metrics).filter(([, value]) => Number.isFinite(Number(value)));
  if (!entries.length) return null;
  entries.sort((a, b) => Number(a[1]) - Number(b[1]));
  const [key, value] = entries[0]!;
  return {key, value: Number(value)};
}

/** feedback.js's benchmarkLabel: an estimate, never presented as a certified level. */
export function benchmarkLabel(result: {cefr_estimate?: unknown; level_estimate?: unknown} = {}): string | null {
  const level = String(result.cefr_estimate || result.level_estimate || '').trim();
  return level ? `${level} estimate` : null;
}

function diffUnits(value: string, language: 'en' | 'zh'): string[] {
  const source = String(value || '');
  if (language === 'zh') return [...source];
  return source.match(/\s+|[A-Za-z0-9À-ỹ]+(?:['’-][A-Za-z0-9À-ỹ]+)*|[^\sA-Za-z0-9À-ỹ]+/gu) || [source];
}

export type ChangedSegments = {
  beforePrefix: string; beforeChange: string; beforeSuffix: string;
  afterPrefix: string; afterChange: string; afterSuffix: string;
};

/**
 * feedback.js's changedSegments: the shared prefix and suffix are peeled off so
 * only what actually changed is marked, rather than restating the whole line.
 */
export function changedSegments(before: string, after: string, language: 'en' | 'zh'): ChangedSegments {
  const left = diffUnits(before, language);
  const right = diffUnits(after, language);

  let prefix = 0;
  while (prefix < left.length && prefix < right.length && left[prefix] === right[prefix]) prefix += 1;

  let suffix = 0;
  while (suffix < left.length - prefix && suffix < right.length - prefix
    && left[left.length - 1 - suffix] === right[right.length - 1 - suffix]) suffix += 1;

  return {
    beforePrefix: left.slice(0, prefix).join(''),
    beforeChange: left.slice(prefix, left.length - suffix).join(''),
    beforeSuffix: suffix ? left.slice(left.length - suffix).join('') : '',
    afterPrefix: right.slice(0, prefix).join(''),
    afterChange: right.slice(prefix, right.length - suffix).join(''),
    afterSuffix: suffix ? right.slice(right.length - suffix).join('') : '',
  };
}

/**
 * adaptive.js's feedbackBudget: how much evidence each guidance mode shows.
 * Review reads it to decide how many issues are visible at once.
 */
export function feedbackBudget(mode: 'guided' | 'examples' | 'concise' | 'advanced') {
  if (mode === 'concise') return {visibleEvidence: 1, extraEvidence: 2, showRule: false, showMetrics: false};
  if (mode === 'guided') return {visibleEvidence: 2, extraEvidence: 3, showRule: true, showMetrics: false};
  if (mode === 'examples') return {visibleEvidence: 3, extraEvidence: 3, showRule: false, showMetrics: false};
  return {visibleEvidence: 4, extraEvidence: 5, showRule: true, showMetrics: true};
}

/* ------------------------------------------------------------------ text map */
/**
 * domain/feedback-map.js: the learner's own text carries the evidence, so the
 * fragments quoted in the panels are the same characters marked in the draft.
 */

export type EvidenceRange = {start: number; end: number; kind: 'error' | 'strength'; index: number};

function findRange(source: string, lower: string, fragment: string, taken: EvidenceRange[]): {start: number; end: number} | null {
  const needle = fragment.toLocaleLowerCase();
  let from = 0;
  for (;;) {
    const start = lower.indexOf(needle, from);
    if (start < 0) return null;
    const end = start + fragment.length;
    if (!taken.some((range) => start < range.end && end > range.start)) return {start, end};
    from = start + 1;
  }
}

export function findEvidenceRanges(text: string, errors: EvidenceItem[] = [], strengths: EvidenceItem[] = []): EvidenceRange[] {
  const source = String(text || '');
  const lower = source.toLocaleLowerCase();
  const ranges: EvidenceRange[] = [];
  const candidates = [
    ...errors.map((item, index) => ({item, index, kind: 'error' as const})),
    ...strengths.map((item, index) => ({item, index, kind: 'strength' as const})),
  ];
  for (const candidate of candidates) {
    const fragment = String(candidate.item?.fragment || '').trim();
    if (!fragment) continue;
    const range = findRange(source, lower, fragment, ranges);
    if (!range) continue;
    ranges.push({...range, kind: candidate.kind, index: candidate.index});
  }
  return ranges.sort((a, b) => a.start - b.start);
}

export type PosGroup = 'noun' | 'verb' | 'modifier' | 'connector' | 'reference' | 'number' | 'other';

const POS_VISUAL_GROUP: Record<string, PosGroup> = {
  noun: 'noun', verb: 'verb', adjective: 'modifier', adverb: 'modifier',
  pronoun: 'reference', determiner: 'reference', preposition: 'connector',
  conjunction: 'connector', particle: 'connector', numeral: 'number', other: 'other',
};

export type PosAnnotation = {start: number; end: number; fragment: string; pos: string; group: PosGroup};

/**
 * Only annotations that still index back into this exact text are kept: an
 * offset that no longer matches would mark the wrong word.
 */
export function normalizedPosAnnotations(text: string, annotations: unknown): PosAnnotation[] {
  const source = String(text || '');
  if (!Array.isArray(annotations)) return [];
  const output: PosAnnotation[] = [];
  let lastEnd = -1;
  const sorted = [...annotations].sort((a, b) => (Number((a as {start?: unknown})?.start) || 0) - (Number((b as {start?: unknown})?.start) || 0));
  for (const raw of sorted) {
    const item = raw as {start?: unknown; end?: unknown; fragment?: unknown; pos?: unknown};
    const start = Number(item?.start);
    const end = Number(item?.end);
    const fragment = String(item?.fragment || '');
    const pos = String(item?.pos || 'other').toLowerCase();
    if (!Number.isInteger(start) || !Number.isInteger(end)) continue;
    if (start < 0 || end <= start || end > source.length) continue;
    if (start < lastEnd) continue;
    if (source.slice(start, end) !== fragment) continue;
    output.push({start, end, fragment, pos: POS_VISUAL_GROUP[pos] ? pos : 'other', group: POS_VISUAL_GROUP[pos] || 'other'});
    lastEnd = end;
  }
  return output;
}

export type TextSpan = {text: string; evidence?: 'error' | 'strength'; index?: number; group?: PosGroup};

/**
 * One flat list of spans for the learner's text: evidence marks win, and the
 * POS lens fills what is left when it is switched on -- the same precedence
 * feedback-map.js applies when it renders annotations inside evidence slices.
 */
export function learnerTextSpans(text: string, ranges: EvidenceRange[], annotations: PosAnnotation[]): TextSpan[] {
  const source = String(text || '');
  if (!source) return [];
  const spans: TextSpan[] = [];
  let cursor = 0;

  const pushPlain = (from: number, to: number) => {
    if (from >= to) return;
    let inner = from;
    for (const item of annotations) {
      if (item.end <= from || item.start >= to) continue;
      const start = Math.max(item.start, from);
      const end = Math.min(item.end, to);
      if (start > inner) spans.push({text: source.slice(inner, start)});
      spans.push({text: source.slice(start, end), group: item.group});
      inner = end;
    }
    if (inner < to) spans.push({text: source.slice(inner, to)});
  };

  for (const range of ranges) {
    if (range.start < cursor) continue;
    pushPlain(cursor, range.start);
    spans.push({text: source.slice(range.start, range.end), evidence: range.kind, index: range.index});
    cursor = range.end;
  }
  pushPlain(cursor, source.length);
  return spans;
}

const SENTENCE_BREAK = /[.!?。！？\n]/u;

/** feedback-map.js's sentenceContext: the sentence a fragment sits in. */
export function sentenceContext(text: string, fragment: string): string {
  const source = String(text || '');
  const value = String(fragment || '').trim();
  if (!source || !value) return '';
  const start = source.toLocaleLowerCase().indexOf(value.toLocaleLowerCase());
  if (start < 0) return '';
  let from = start;
  let to = start + value.length;
  while (from > 0 && !SENTENCE_BREAK.test(source[from - 1]!)) from -= 1;
  while (to < source.length && !SENTENCE_BREAK.test(source[to]!)) to += 1;
  if (to < source.length) to += 1;
  return source.slice(from, to).trim();
}
