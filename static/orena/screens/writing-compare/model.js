/* Compare Versions (frame 19, `#/write/:id/compare`; D-091): pure data mapping from the real
   `RevisionCompare` contract (`GET /api/essays/{id}/revision`, `writing_coach/writing_contract.py
   #project_revision`) plus the essay's own prompt, version dates and estimated range
   (`GET /api/essays/{id}` for the revised version and for the earlier one, which the contract does
   not carry). No DOM, no fetch - what scripts/test_orena_screen_writing-compare.mjs exercises
   directly, against payloads captured from the real routes.

   The frame's legend draws exactly 3 categories (`hint-placeholder-count="3"`) and the real
   contract computes exactly 3 (`fixed`/`remaining`/`added`) - the spec's fourth word "reworked"
   is not a fourth bucket the backend computes; a changed pair already counts as `remaining`
   (`writing_contract.py`'s own comment: "a changed pair is the same problem in new words, so it
   counts as remaining"). Nothing is invented to reach four.

   The frame draws one summary line, "Grammar A -> B · range X -> Y", with the word "Grammar" typed
   in (not bound to a dimension): that is what this builds - the grammar dimension's real movement
   and the estimated range's, each only when both sides are real. */
import { marksIn } from '../../product/draft-marks.js';

function text(value) {
  return String(value ?? '').trim();
}

function mapChange(item) {
  return { title: text(item?.title), detail: text(item?.detail) };
}

/* The revision to read the earlier version's range from: `revisions` is the essay detail's own
   series list (`id`, `revision_no`). */
export function revisionIdOf(detail, version) {
  const found = (Array.isArray(detail?.revisions) ? detail.revisions : []).find((entry) => Number(entry?.revision_no) === Number(version));
  return found && Number.isFinite(found.id) ? found.id : null;
}

function createdAtOf(detail, version) {
  const found = (Array.isArray(detail?.revisions) ? detail.revisions : []).find((entry) => Number(entry?.revision_no) === Number(version));
  return text(found?.created_at);
}

function movement(entry) {
  return entry && Number.isFinite(entry.from) && Number.isFinite(entry.to) ? { from: Math.round(entry.from), to: Math.round(entry.to) } : null;
}

/* `essayDetail`: the revised version's `GET /api/essays/{id}`; `earlierDetail`: the earlier one's
   (optional - without it the range line simply has no earlier side). */
export function mapCompare(essayDetail, compare, earlierDetail = null) {
  if (!compare?.previous || !compare?.current) return null;
  const previousVersion = Math.max(1, Number(compare.previous.version) || 1);
  const currentVersion = Math.max(1, Number(compare.current.version) || 1);
  const grammar = movement((Array.isArray(compare.dimensionDeltas) ? compare.dimensionDeltas : []).find((entry) => entry?.name === 'grammar'));
  const rangeFrom = text(earlierDetail?.cefr_estimate);
  const rangeTo = text(essayDetail?.cefr_estimate);
  return {
    prompt: text(essayDetail?.prompt),
    previous: { version: previousVersion, text: text(compare.previous.text), createdAt: createdAtOf(essayDetail, previousVersion) },
    current: { version: currentVersion, text: text(compare.current.text), createdAt: createdAtOf(essayDetail, currentVersion) },
    fixed: (Array.isArray(compare.fixed) ? compare.fixed : []).map(mapChange),
    remaining: (Array.isArray(compare.remaining) ? compare.remaining : []).map(mapChange),
    added: (Array.isArray(compare.added) ? compare.added : []).map(mapChange),
    grammar,
    range: rangeFrom && rangeTo ? { from: rangeFrom, to: rangeTo } : null,
  };
}

/* What a fixed change became: `detail` for a fixed change is "words -> correction"
   (`writing_contract._change(fixed=True)`), and the correction is what the frame lists. */
function correctionOf(change) {
  const parts = change.detail.split(' → ');
  return text(parts.length > 1 ? parts[parts.length - 1] : change.title || change.detail);
}

/* Legend rows: always the real 3 categories, 0 shown honestly as 0 (rule 40), never hidden. Each
   row's line is the words themselves joined with " · " (fixed: what they became; still present and
   new: the words), and "—" when there is nothing to list - the frame's own fallback. */
export function legendRows(compare) {
  if (!compare) return [];
  const line = (items) => items.filter(Boolean).join(' · ') || '—';
  return [
    { key: 'fixed', color: 'var(--green)', n: compare.fixed.length, items: line(compare.fixed.map(correctionOf)) },
    { key: 'remaining', color: 'var(--red)', n: compare.remaining.length, items: line(compare.remaining.map((change) => change.title)) },
    { key: 'added', color: 'var(--amber)', n: compare.added.length, items: line(compare.added.map((change) => change.title)) },
  ];
}

/* Diff spans: each change's own words, marked once in whichever version(s) they occur in - a
   fixed problem is marked in the earlier text (where it was), a remaining one in both, a new
   one only in the revised text. Never overlapping (`product/draft-marks.js#marksIn`, the same
   non-overlap rule the Writing screen's own inline findings use). */
function segmentsFor(versionText, items) {
  if (!versionText) return [];
  const marks = marksIn(
    versionText,
    items.map((entry, index) => ({ id: `${entry.tone}-${index}`, fragment: entry.title, tone: entry.tone })),
  );
  const segments = [];
  let at = 0;
  for (const mark of marks) {
    if (mark.start > at) segments.push({ tone: 'plain', text: versionText.slice(at, mark.start) });
    segments.push({ tone: mark.tone, text: versionText.slice(mark.start, mark.end) });
    at = mark.end;
  }
  if (at < versionText.length) segments.push({ tone: 'plain', text: versionText.slice(at) });
  return segments;
}

export function earlierSegments(compare) {
  if (!compare) return [];
  const items = [...compare.fixed.map((c) => ({ ...c, tone: 'fixed' })), ...compare.remaining.map((c) => ({ ...c, tone: 'remaining' }))].filter((c) => c.title);
  return segmentsFor(compare.previous.text, items);
}

export function revisedSegments(compare) {
  if (!compare) return [];
  const items = [...compare.remaining.map((c) => ({ ...c, tone: 'remaining' })), ...compare.added.map((c) => ({ ...c, tone: 'added' }))].filter((c) => c.title);
  return segmentsFor(compare.current.text, items);
}
