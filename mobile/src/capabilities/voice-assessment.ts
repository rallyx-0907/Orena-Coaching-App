import type {PronunciationAssessment, PronunciationWord} from '../api/contracts/speech';

/**
 * Pure helpers ported from static/becoming/screens/speaking.js, so native reads
 * the same numbers the same way.
 *
 * The rule the whole file turns on: a missing score is "not measured", never
 * zero, and never a band. speaking.js is careful about this because the screen
 * shows rings and words like "Strong" — printing one of those over an absent
 * measurement would be inventing an assessment of the learner.
 */

export type ScoreBand = 'strong' | 'steady' | 'developing';

/** `scoreBand()`: null for anything that is not a real number. */
export function scoreBand(value: unknown): ScoreBand | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  if (value >= 80) return 'strong';
  if (value >= 60) return 'steady';
  return 'developing';
}

/** M:SS, the same stamp Listening uses for media positions. */
export function stamp(ms: number): string {
  const value = Number.isFinite(ms) ? Math.max(0, ms) : 0;
  return `${Math.floor(value / 60000)}:${String(Math.floor(value / 1000) % 60).padStart(2, '0')}`;
}

/** speaking.js's own cap: a take stops itself at three minutes. */
export const MAX_RECORDING_MS = 180000;

/**
 * `hasWeakPronunciationEvidence()`: which words are worth another pass. A word
 * is listed because the provider said something about it — a low accuracy score
 * or a named error — not because the screen needs four rows to look full.
 */
export function hasWeakPronunciationEvidence(word: PronunciationWord): boolean {
  const named = typeof word.error_type === 'string' && word.error_type !== '' && word.error_type.toLowerCase() !== 'none';
  const low = typeof word.accuracy_score === 'number' && Number.isFinite(word.accuracy_score) && word.accuracy_score < 80;
  return named || low;
}

export function weakPronunciationWords(pronunciation: PronunciationAssessment | null): PronunciationWord[] {
  if (!pronunciation || !Array.isArray(pronunciation.words)) return [];
  return pronunciation.words.filter(hasWeakPronunciationEvidence).slice(0, 4);
}

/** A demo score must never be read as a measurement of this learner's voice. */
export const isSyntheticScore = (pronunciation: PronunciationAssessment | null): boolean =>
  pronunciation?.score_kind === 'synthetic_demo';

export type ReferenceToken = {token: string; matched: boolean};

/**
 * `sourceCheck()`'s alignment: which words of the line came back in the
 * transcript. It is a comparison against this line — the screen says so — and
 * deliberately not a score.
 */
export function alignToReference(referenceText: string, transcriptText: string, language: string): {
  alignment: ReferenceToken[];
  extra: string[];
  band: 'strong' | 'close' | 'retry';
} {
  const split = (value: string): string[] => {
    const trimmed = String(value || '').trim();
    if (!trimmed) return [];
    if (language === 'zh') return [...trimmed.replace(/\s+/g, '')];
    return trimmed.toLocaleLowerCase().replace(/[.,!?;:"'()]/g, '').split(/\s+/).filter(Boolean);
  };
  const reference = split(referenceText);
  const spoken = split(transcriptText);
  const remaining = [...spoken];
  const alignment: ReferenceToken[] = reference.map((token) => {
    const index = remaining.indexOf(token);
    if (index >= 0) { remaining.splice(index, 1); return {token, matched: true}; }
    return {token, matched: false};
  });
  const matched = alignment.filter((item) => item.matched).length;
  const ratio = reference.length ? matched / reference.length : 0;
  return {
    alignment,
    extra: remaining.slice(0, 8),
    band: ratio >= 0.9 ? 'strong' : ratio >= 0.6 ? 'close' : 'retry',
  };
}

/**
 * The transcript is shown as sentences, the way the reference breaks it, rather
 * than one unbroken run of recognised text.
 */
export function transcriptLines(text: string): string[] {
  return String(text || '').split(/(?<=[.!?。！？])\s+/).map((line) => line.trim()).filter(Boolean);
}
