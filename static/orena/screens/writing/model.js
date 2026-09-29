/* Writing (frame 18, `#/write` and `#/write/:id`; D-091): pure data mapping. No DOM, no fetch -
   what scripts/test_orena_screen_writing.mjs exercises directly, against payloads captured from the
   real routes (scripts/fixtures/api/writing_essay_*.json).

   The backend answers two different shapes for one essay: `GET /api/essays/{id}`
   (`row_to_dict(detail=True)`, `app.py`) gives the rich shape this screen needs - `issues[]` with
   a real `priority` flag ("high" only ever marks the first-listed finding; a backend gap, not
   something invented here), `strengths[]` as grounded quote+reason pairs, `dimensions{}` as a plain
   dict, a free-text `summary`, `next_actions`, `review_kept_at`, the whole revision series - while
   `GET /api/essays/{id}/review` (`writing_contract.py#project_review`, the WritingReview
   contract) is the one place a per-issue `kind` (grammar/vocabulary/punctuation/register/
   naturalness) is computed. Nothing here re-derives that mapping client-side (no hardcoding,
   AGENTS.md §6): `mapEssay` takes both answers and reads `kind` off the review by the issue's own
   `id` (both endpoints number issues from the same stored `errors_json`, in order).

   Grammar links (`grammar_links`, R5 concept ids) are deliberately not read: R5 is being retired
   and Grammar Lab will own grammar content (2026-09-28 human decision), so the finding detail
   carries no "Related grammar" and no grammar-drill entry until that contract exists. */
import { languageKey, measureMinimum, measureWriting, minimumFor } from '../../capabilities/writing-limits.js';
import { marksIn } from '../../product/draft-marks.js';

const KIND_COPY_KEY = {
  register: 'kindRegister',
  grammar: 'kindGrammar',
  punctuation: 'kindPunctuation',
  vocabulary: 'kindVocabulary',
  naturalness: 'kindNaturalness',
};

/* The frame's four dimensions, in the frame's own order, and which finding kinds count against
   each one (a finding's kind is the backend's; "Coherence" has no sentence-level kind of its own -
   `writing_contract.KIND_OF_CATEGORY` files coherence findings under naturalness). */
const DIMENSIONS = [
  { key: 'grammar', copy: 'kindGrammar', kinds: ['grammar'] },
  { key: 'vocabulary', copy: 'kindVocabulary', kinds: ['vocabulary'] },
  { key: 'coherence', copy: 'kindCoherence', kinds: [] },
  { key: 'naturalness', copy: 'kindNaturalness', kinds: ['naturalness', 'register'] },
];

/* Every category either language's evaluator can return (ERROR_CATEGORIES in
   `languages/english/profile.py` and `languages/chinese/profile.py`), each with its own interface label. `other` names nothing, so it is not here. */
const CATEGORY_KEYS = new Set([
  'article', 'tense', 'agreement', 'word_choice', 'word_form', 'preposition', 'sentence_structure',
  'punctuation', 'coherence', 'task', 'naturalness', 'register', 'spelling', 'word_order', 'particle',
  'aspect', 'complement', 'measure_word', 'ba_sentence', 'bei_sentence', 'conjunction',
  'character_choice', 'collocation', 'redundancy',
]);
export const CATEGORY_IDS = Object.freeze([...CATEGORY_KEYS]);

function text(value) {
  return String(value ?? '').trim();
}

/* ------------------------------------------------------------------------------ counts -- */

/* The count shown under a draft is the count the server stores for it (`word_count`, from
   `writing_unit_count` in `writing_coach/languages/runtime.py`), so the number does not jump when the
   review comes back: Han characters plus Latin words for Chinese, runs of word characters (an
   apostrophe or a hyphen may join them) for everything else. Not the review minimum's counters
   (`capabilities/writing-limits.js`), which answer another question - "is this writing at all?" -
   and part from this one on a bare number or a Latin word among Han characters. */
const HAN_UNIT = /[\u3400-\u4dbf\u4e00-\u9fff]/g;
const LATIN_UNIT = /[A-Za-z]+(?:['-][A-Za-z0-9]+)*/g;
const WORD_UNIT = /[\p{L}\p{N}_]+(?:['-]+[\p{L}\p{N}_]+)*/gu;

export function wordCountOf(value, language) {
  const body = String(value ?? '');
  if (languageKey(language) === 'zh') return (body.match(HAN_UNIT) || []).length + (body.match(LATIN_UNIT) || []).length;
  return (body.match(WORD_UNIT) || []).length;
}

export function charCountOf(value) {
  return measureWriting(value).characters;
}

/* Can this draft be sent for review at all - the server's own floor and ceiling
   (`writing-limits.js`, the same table and numbers `writing_coach/writing_limits.py` enforces),
   read once so the button and the request agree. The floor is the learning language's own
   (`minimumFor`: Han characters for Chinese, words otherwise), so an HSK 1 sentence is an
   attempt; it only says "this is not writing yet", never "this is too little to grade" - that
   is the evaluator's. `language` is the language the draft is sent for review in. */
export function reviewGate(value, language) {
  const trimmed = text(value);
  const measured = measureWriting(trimmed);
  // The server's own order: what is too large is refused before what is too small.
  if (!measured.withinLimits) return { canReview: false, reason: measured.limitExceeded };
  if (!measureMinimum(trimmed, language).met) return { canReview: false, reason: 'tooShort' };
  return { canReview: true, reason: '' };
}

/* The copy key and count that say what would be enough, in the unit the language writes in. */
const UNIT_NOTICE_KEY = { han: 'tooShortHan', kana_han: 'tooShortKanaHan', words: 'tooShortWords' };
export function tooShortNotice(language) {
  const { unit, minimum } = minimumFor(language);
  return { key: UNIT_NOTICE_KEY[unit] || 'tooShortWords', n: minimum };
}

/* ---------------------------------------------------------------------------- which piece -- */

/* `#/write/:id` is opened with an essay's number (Progress, Search) or with a continuation entry's
   own id (`essay:<n>`, `expression:free` - Notifications, Today's Continue). Both name a piece. */
export function parsePiece(param) {
  const value = text(param);
  if (!value) return { kind: 'new' };
  if (/^\d+$/.test(value)) return { kind: 'essay', id: Number(value) };
  const series = /^essay:(\d+)$/.exec(value);
  if (series) return { kind: 'essay', id: Number(series[1]) };
  if (value.startsWith('expression:')) return { kind: 'new' };
  return { kind: 'unknown' };
}

/* The device/account key of a draft, the one the old room used for the same piece: the server's
   series for a reviewed piece, the free-writing slot for a new one. */
export const NEW_DRAFT_KEY = 'expression:free';
export function draftKeyFor(essay) {
  return essay ? `essay:${essay.seriesId}` : NEW_DRAFT_KEY;
}

/* The revision to open for a piece: the latest of its series. `revisions` is the detail's own list
   (`id`, `revision_no`, oldest first). */
export function latestRevisionId(detail) {
  const revisions = (Array.isArray(detail?.revisions) ? detail.revisions : []).filter((entry) => Number.isFinite(entry?.id));
  if (!revisions.length) return Number(detail?.id) || null;
  return revisions.reduce((best, entry) => (Number(entry.revision_no) >= Number(best.revision_no) ? entry : best)).id;
}

/* ------------------------------------------------------------------------------- levels -- */

/* The level ladder Prompt Setup offers, per learning language: the frame's three steps (B1, B2,
   C1) for English and the same three steps of the Chinese ladder (HSK 3-5). A genuine linguistic
   difference (CEFR vs HSK) - the request carries the code the evaluator's own profile names
   (`languages/chinese/profile.py`: "HSK3", not "HSK 3"). */
const SETUP_LEVELS = { en: ['B1', 'B2', 'C1'], zh: ['HSK3', 'HSK4', 'HSK5'] };
const LEVEL_CODE = { en: /^(A1|A2|B1|B2|C1|C2)$/, zh: /^(HSK[1-6]|HSK7-9)$/ };

export function levelCode(value, language) {
  const code = text(value).replace(/\s+/g, '').toUpperCase();
  const pattern = LEVEL_CODE[languageKey(language)] || LEVEL_CODE.en;
  return pattern.test(code) ? code : '';
}

/* "HSK3" reads "HSK 3", the way Progress and Onboarding already draw a Chinese level. */
export function levelLabel(code) {
  return text(code).replace(/^(HSK)(\d)/, '$1 $2');
}

export function setupLevels(language) {
  return (SETUP_LEVELS[languageKey(language)] || SETUP_LEVELS.en).map((id) => ({ id, label: levelLabel(id) }));
}

export const SETUP_REGISTERS = ['informal', 'neutral', 'formal'];
export const SETUP_TARGETS = [100, 150, 250];

/* What is sent to `POST /api/evaluate` for a review. Only fields the evaluator really reads:
   the task (`prompt`), the words, the level it aims at, the learning language, and the revision
   this one continues. Register and target length are the learner's own intention for the piece;
   `EssayIn` declares a `writing_context` for them but `evaluate_with_ai` never passes it on
   (`app.py`), so sending them would only look like an effect (UI_BACKEND_GAPS, Writing). */
export function reviewPayload({ prompt, text: draft, level, parentId, language }) {
  const payload = { prompt: text(prompt), text: String(draft || ''), learning_language: languageKey(language) || 'en' };
  if (level) payload.target_cefr = level;
  if (parentId) payload.parent_essay_id = parentId;
  return payload;
}

/* -------------------------------------------------------------------------- the essay -- */

/* A real score grouped into the frame's three colours (green from 80, amber from 65, red below -
   the design's own binding for a dimension bar), a presentational grouping of a real number. */
function bandColor(value) {
  if (value >= 80) return 'var(--green)';
  if (value >= 65) return 'var(--amber)';
  return 'var(--red)';
}

export function mapStrengths(strengths) {
  return (Array.isArray(strengths) ? strengths : [])
    .map((item) => ({ id: text(item?.id), span: text(item?.quote), note: text(item?.why) }))
    .filter((item) => item.span);
}

export function findingIsOpen(issue, liveText) {
  return Boolean(issue?.fragment) && String(liveText || '').includes(issue.fragment);
}

/* The four dimensions the review carries, in the frame's order. A dimension the review does not
   carry is left out, never shown as 0 (`writing_contract.project_dimensions`). The note beside it
   is what is real: how many of its findings are still in the draft (the frame's "N fixes"), else
   "Strong" from 80, else nothing - the frame's "1 tip" is a count nothing measures. */
export function dimensionRows(dimensions, issues, liveText) {
  const dict = dimensions && typeof dimensions === 'object' ? dimensions : {};
  return DIMENSIONS.filter(({ key }) => typeof dict[key] === 'number' && Number.isFinite(dict[key])).map(({ key, copy, kinds }) => {
    const value = Math.round(Math.max(0, Math.min(100, dict[key])));
    const open = (issues || []).filter((issue) => kinds.includes(issue.kind) && findingIsOpen(issue, liveText)).length;
    let note = null;
    if (open > 0) note = { key: 'dimFixes', n: open };
    else if (value >= 80) note = { key: 'dimStrong', n: 0 };
    return { key, labelKey: copy, value, pct: `${value}%`, color: bandColor(value), note };
  });
}

function kindOf(id, kindById) {
  const kind = kindById instanceof Map ? kindById.get(id) : '';
  return Object.hasOwn(KIND_COPY_KEY, kind) ? kind : '';
}

export function mapIssue(item, kindById) {
  const id = text(item?.id);
  const kind = kindOf(id, kindById);
  const category = text(item?.category);
  return {
    id,
    priority: item?.priority === 'high',
    kind,
    kindKey: kind ? KIND_COPY_KEY[kind] : '',
    categoryKey: CATEGORY_KEYS.has(category) ? `cat_${category}` : '',
    fragment: text(item?.quote),
    correction: text(item?.suggestion),
    why: text(item?.why),
    how: text(item?.how),
    examples: (Array.isArray(item?.examples) ? item.examples : []).map(text).filter(Boolean),
  };
}

/* Review-scoped id lookup (WritingReview's own projection): a finding's `kind` is not on the detail
   endpoint at all, and both endpoints number the same stored list. */
export function kindMapFrom(review) {
  const map = new Map();
  for (const issue of review?.issues || []) if (issue?.id) map.set(String(issue.id), text(issue.kind));
  return map;
}

export function mapIssues(issues, kindById) {
  const all = (Array.isArray(issues) ? issues : []).map((item) => mapIssue(item, kindById)).filter((issue) => issue.fragment);
  return { priority: all.filter((issue) => issue.priority), other: all.filter((issue) => !issue.priority) };
}

/* The one essay this screen shows: the current revision plus everything needed to judge and
   revise it. `review` is the WritingReview answer for the same id (used for its per-issue `kind`
   only, above). The range is the evaluator's own demonstrated band (`cefr_estimate`, "based on
   this draft only" - empty when the sample was too thin to say), never the score-derived
   `app_cefr`, which always names something. */
export function mapEssay(detail, review) {
  if (!detail) return null;
  const kindById = kindMapFrom(review);
  const { priority, other } = mapIssues(detail.issues, kindById);
  const revisions = Array.isArray(detail.revisions) ? detail.revisions : [];
  const revisionNo = Math.max(1, Number(detail.revision_no) || 1);
  return {
    id: Number(detail.id),
    seriesId: Number(detail.series_id || detail.id),
    revisionNo,
    latestId: latestRevisionId(detail),
    prompt: text(detail.prompt),
    level: text(detail.target_cefr),
    text: String(detail.text || ''),
    overall: Number.isFinite(detail.overall) ? Math.round(detail.overall) : null,
    range: text(detail.cefr_estimate),
    createdAt: text(detail.created_at),
    summary: text(detail.summary?.interpretation),
    strengths: mapStrengths(detail.strengths),
    priorityIssues: priority,
    otherIssues: other,
    hasOther: other.length > 0,
    dimensions: detail.dimensions && typeof detail.dimensions === 'object' ? detail.dimensions : {},
    kept: Boolean(detail.review_kept_at),
    canCompare: revisions.length > 1 && revisionNo > 1,
  };
}

export const allIssues = (essay) => [...(essay?.priorityIssues || []), ...(essay?.otherIssues || [])];

/* The first priority finding: where the review's "Next" bar takes the learner. */
export function firstPriority(essay) {
  return (essay?.priorityIssues || [])[0] || null;
}

/* The reviewed draft, annotated: every strength quote and every finding fragment, placed once
   each (a highlight is earned - `product/draft-marks.js#marksIn`, the exact non-overlap rule
   `applyFix` also uses, so a highlighted span and an applicable fix always agree on where the words
   are). Marked against the LIVE draft, as the frame's does: a fix applied here leaves the card
   showing the learner's own new words, with the findings still standing marked. A dismissed finding
   is no longer marked. */
export function buildSegments(essay, liveText, dismissed = new Set()) {
  const body = String(liveText ?? essay?.text ?? '');
  if (!essay) return body ? [{ kind: 'plain', text: body }] : [];
  const items = [
    ...essay.priorityIssues.map((issue) => ({ id: issue.id, fragment: issue.fragment, tone: 'priority', issue })),
    ...essay.otherIssues.map((issue) => ({ id: issue.id, fragment: issue.fragment, tone: 'other', issue })),
    ...essay.strengths.map((strength) => ({ id: `s-${strength.id}`, fragment: strength.span, tone: 'strength', strength })),
  ].filter((item) => item.fragment && !dismissed.has(item.id));
  const byId = new Map(items.map((item) => [item.id, item]));
  const marks = marksIn(
    body,
    items.map((item) => ({ id: item.id, fragment: item.fragment, tone: item.tone })),
  );
  const segments = [];
  let at = 0;
  for (const mark of marks) {
    if (mark.start > at) segments.push({ kind: 'plain', text: body.slice(at, mark.start) });
    const source = byId.get(mark.id);
    segments.push({
      kind: mark.tone,
      text: body.slice(mark.start, mark.end),
      id: mark.id,
      issue: source?.issue || null,
      strength: source?.strength || null,
    });
    at = mark.end;
  }
  if (at < body.length) segments.push({ kind: 'plain', text: body.slice(at) });
  return segments;
}

/* The first sentence of a finding's reason: the popover's line (the full reason is in the finding's
   detail). A CJK full stop ends a sentence without a space after it. */
export function firstSentence(value) {
  const line = text(value);
  const found = /^(.+?(?:[.!?](?=\s|$)|[。！？]))/su.exec(line);
  return found ? found[1] : line;
}

/* "Today 09:12", "Yesterday 21:40", "Sep 20, 10:05" - in the interface language, with the words
   for today and yesterday from the platform's own calendar data, not from this file. `now` is
   injectable so the gate can pin it. */
export function whenLabel(iso, locale, now = new Date()) {
  const date = new Date(iso);
  if (!iso || Number.isNaN(date.getTime())) return '';
  const clock = new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(date);
  const startOf = (value) => new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  const days = Math.round((startOf(date) - startOf(now)) / 86400000);
  if (days === 0 || days === -1) {
    const word = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' }).format(days, 'day');
    return `${word.charAt(0).toLocaleUpperCase(locale)}${word.slice(1)} ${clock}`;
  }
  return new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date);
}

/* Both saved states are saved: the dot is the frame's green, the words say where. */
export function saveTone(where) {
  return { color: 'var(--green)', key: where === 'account' ? 'savedAccount' : 'savedDevice' };
}
