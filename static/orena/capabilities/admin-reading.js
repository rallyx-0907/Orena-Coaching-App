/* Reading pipeline: the Platform Admin's rules for the Reading content engine, without any
   presentation. Shared by the old console (admin/reading.js re-exports the pure parts) and the new
   UI's Admin (screens/admin/reading*.js), which draws the pinned `Orena Admin.dc.html` on top of it
   (D-101 E: one Admin backend, one implementation of its rules).

   The rules this file keeps, because they are the ones an operator would be hurt by:

   - Nothing here decides. Every action is a call to a server route that already exists; publishing
     is one of them and never a side effect of opening, editing or approving anything.
   - Rights are decision support, not a gate (D-082): an unanswered or refused right warns before
     Publish and never disables it. The three answers stay three - `false` is a refusal and an
     absent answer is a question nobody asked.
   - A comprehension set is hidden from learners until an administrator approves it, every question
     decided; the server refuses an approval whose questions are no longer in the text. */
import { adminApi, failureReason } from './admin-api.js';

/* The queue's tabs and the statuses each asks the server for. */
export const QUEUE_TABS = ['review', 'published', 'rejected', 'archived'];
export const TAB_STATUS = {
  review: 'draft,processing,needs_review,ready',
  published: 'published',
  rejected: 'rejected',
  archived: 'archived,unpublished',
};
export const PAGE_LIMIT = 25;

export function tabFrom(value) {
  return QUEUE_TABS.includes(value) ? value : 'review';
}

/* The four right-to-use questions the snapshot records, and the three answers each can have. */
export const RIGHTS_QUESTIONS = ['can_republish', 'can_adapt', 'automation_allowed', 'attribution_required'];

/* The single word an article's rights read as in a list: what a reviewer is deciding on. The
   republish answer decides it; a refusal outranks an unanswered question. */
export function rightsLevel(state) {
  const answer = (state || {}).can_republish || 'unknown';
  return answer === 'allowed' || answer === 'denied' ? answer : 'unknown';
}

/* Copyright is a hard gate at Publish (D-105). This is the server's rule
   (reading_admin_api.publication_blockers) read ahead of the click: publishing needs the right to
   republish and, for an adapted text, the right to adapt. An unanswered question refuses as
   surely as a denial. The server still decides; this only says why before asking. */
export function publicationBlockers(article) {
  const state = article?.source?.rights_state || {};
  const blockers = [];
  const republish = state.can_republish || 'unknown';
  if (republish === 'denied') blockers.push({ code: 'rights_not_cleared', question: 'can_republish' });
  else if (republish !== 'allowed') blockers.push({ code: 'rights_unknown', question: 'can_republish' });
  if (article?.is_adapted) {
    const adapt = state.can_adapt || 'unknown';
    if (adapt === 'denied') blockers.push({ code: 'adaptation_not_cleared', question: 'can_adapt' });
    else if (adapt !== 'allowed') blockers.push({ code: 'adaptation_unknown', question: 'can_adapt' });
  }
  return blockers;
}

/* Advice that does not stop publication: attribution is an obligation, not a permission. */
export function publicationAdvice(article) {
  const state = article?.source?.rights_state || {};
  return (state.attribution_required || 'unknown') === 'unknown' ? [{ code: 'attribution_unknown', level: 'warning' }] : [];
}

/* The rights questions an administrator answers on the review page, with the words each answer
   takes. An answer of '' is "unanswered". */
export const RIGHTS_EDIT = [
  { id: 'can_republish', yes: 'allowed', no: 'denied' },
  { id: 'can_adapt', yes: 'allowed', no: 'denied' },
  { id: 'attribution_required', yes: 'required', no: 'not_required' },
  /* A source's automation permission is a default; the article may carry a reviewed override (D-106).
     '' clears the override so the source default applies again. */
  { id: 'automation_allowed', yes: 'allowed', no: 'denied', override: true },
];

/* The article-level override as the editor's choice: '' when the source default applies. */
export function automationChoice(automation) {
  if (!automation || automation.override === null || automation.override === undefined) return '';
  return automation.override ? 'allowed' : 'denied';
}

/* The state the server holds -> the request body for the rights route: only what changed. */
export function rightsChanges(state, draft, automation = null) {
  const body = {};
  for (const question of RIGHTS_EDIT) {
    if (draft[question.id] === undefined) continue;
    const held = question.override ? automationChoice(automation) : state?.[question.id] === 'unknown' || state?.[question.id] === undefined ? '' : state[question.id];
    if (draft[question.id] === held) continue;
    body[question.id] = draft[question.id] === question.yes ? true : draft[question.id] === question.no ? false : null;
  }
  return body;
}

export function levelOptions(language) {
  return language === 'zh'
    ? ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6']
    : ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
}

export function readingMinutes(seconds) {
  return Math.max(1, Math.round(Number(seconds || 0) / 60));
}

/* The status an action asks for. Restoring returns an item to review; it never republishes. */
export const ARTICLE_ACTION_STATUS = {
  publish: 'published',
  unpublish: 'unpublished',
  reject: 'rejected',
  archive: 'archived',
  restore: 'needs_review',
};

/* Which actions an article offers from where it is (the design's dActions). */
export function articleActions(status) {
  if (status === 'published') return ['unpublish', 'archive'];
  if (status === 'rejected') return ['restore'];
  if (status === 'archived' || status === 'unpublished') return ['restore'];
  if (status === 'processing') return [];
  return ['reject', 'archive', 'publish'];
}

/* Only these read as editable in the review pane; a rejected or archived item is kept as it was. */
export function isEditable(status) {
  return status === 'published' || ['draft', 'needs_review', 'ready'].includes(status);
}

/* The queue tab an article belongs to (for the back link and its position). */
export function tabOf(status) {
  if (status === 'published') return 'published';
  if (status === 'rejected') return 'rejected';
  if (status === 'archived' || status === 'unpublished') return 'archived';
  return 'review';
}

/* What the operator typed becomes the multipart submission the engine takes. An absent answer is
   absent - not a refusal - so a rights question nobody answered arrives as no field at all. */
export function submissionFrom({ mode, title = '', body = '', url = '', language = '', source = '', author = '', sourceUrl = '', rights = '', adapt = '', attribution = '', license = '' }) {
  const kind = ['url', 'text', 'file'].includes(mode) ? mode : 'text';
  const submitted = { kind };
  if (kind === 'text') Object.assign(submitted, { text: body, title: title.trim() });
  if (kind === 'url') submitted.url = url.trim();
  if (kind === 'file') submitted.title = title.trim();
  if (language && language !== 'auto') submitted.language = language;
  if (source.trim()) submitted.source_name = source.trim();
  if (author.trim()) submitted.author = author.trim();
  if (kind === 'text' && sourceUrl.trim()) submitted.url = sourceUrl.trim();
  if (rights === 'allowed') submitted.can_republish = true;
  else if (rights === 'denied') submitted.can_republish = false;
  if (adapt === 'allowed') submitted.can_adapt = true;
  else if (adapt === 'denied') submitted.can_adapt = false;
  if (attribution === 'required') submitted.attribution_required = true;
  else if (attribution === 'not_required') submitted.attribution_required = false;
  if (license.trim()) submitted.license_note = license.trim();
  return submitted;
}

/* What is missing before a submission can go: the field's copy key, or '' when it can. */
export function submissionProblem(submitted, file) {
  if (submitted.kind === 'url' && !/^https?:\/\//i.test(submitted.url || '')) return 'addErrUrl';
  if (submitted.kind === 'text' && !String(submitted.text || '').trim()) return 'addErrBody';
  if (submitted.kind === 'file' && !file) return 'addErrFile';
  return '';
}

/* ---- comprehension sets ---------------------------------------------------------------- */

export function questionState(question) {
  if (question.admin_approved) return 'approved';
  if (question.admin_rejected) return 'rejected';
  return 'undecided';
}

export function setProgress(set) {
  const questions = set?.questions || [];
  const approved = questions.filter((q) => q.admin_approved).length;
  const rejected = questions.filter((q) => q.admin_rejected).length;
  return { total: questions.length, approved, rejected, undecided: questions.length - approved - rejected };
}

/* Questions can be decided only while the set is undecided; a decided set is frozen by the database. */
export function questionsEditable(set) {
  return ['draft', 'needs_review'].includes(set?.status);
}

/* The set's transitions from where it is (the database's own review graph), each with what makes
   it available: approving needs one approved question, none undecided, and an anchored set. */
export function setActions(set) {
  const progress = setProgress(set);
  const anchored = set?.anchored !== false;
  const canApprove = progress.approved >= 1 && progress.undecided === 0 && anchored;
  switch (set?.status) {
    case 'draft':
      return [{ id: 'review', status: 'needs_review' }, { id: 'discard', discard: true }];
    case 'needs_review':
      return [
        { id: 'reject', status: 'rejected', reason: true },
        { id: 'discard', discard: true },
        { id: 'approve', status: 'approved', primary: true, enabled: canApprove, why: !anchored ? 'stale' : progress.undecided ? 'undecided' : 'none' },
      ];
    case 'approved':
      return [{ id: 'archive', status: 'archived' }];
    case 'stale':
      return [{ id: 'archive', status: 'archived' }];
    case 'archived':
      return [{ id: 'restore', status: 'approved', primary: true, enabled: anchored, why: 'stale' }];
    case 'rejected':
      return [{ id: 'discard', discard: true }];
    default:
      return [];
  }
}

/* A set is stale when the article's text is no longer the text its questions were written for. */
export function setIsStale(set) {
  return set?.anchored === false || set?.status === 'stale';
}

/* Where a learner opens content in the new UI: the same address the Discover cards use. */
export function learnerAddress(kind, id, chapterId = '') {
  const suffix = kind === 'book' && chapterId ? `:${chapterId}` : '';
  /* The learner UI files a Reading article under `article:` (screens/content/model.js). */
  const filed = kind === 'reading' ? 'article' : kind;
  return `#/content/${encodeURIComponent(`${filed}:${id}${suffix}`)}`;
}

/* ---- requests: one place that says what each action calls ---------------------------------- */

export async function loadQueue(api = adminApi, { tab = 'review', cursor = '' } = {}) {
  return api.readingQueue({ status: TAB_STATUS[tab], cursor, limit: PAGE_LIMIT });
}

/* Change an article's status. A rejection keeps its reason; the server refuses one without. */
export async function changeArticle(api = adminApi, id, action, reason = '') {
  const status = ARTICLE_ACTION_STATUS[action];
  if (!status) throw new Error(`Unknown article action: ${action}`);
  return api.readingSetStatus(id, status, reason);
}

/* Save what an operator can edit on a review pane. Only fields that changed are sent. */
export async function saveArticle(api = adminApi, id, article, edits) {
  const body = {};
  for (const key of ['title', 'body', 'topic']) {
    if (edits[key] !== undefined && edits[key] !== (article[key] ?? '')) body[key] = edits[key];
  }
  if (edits.reviewed_level !== undefined && (edits.reviewed_level || '') !== (article.reviewed_level || '')) body.reviewed_level = edits.reviewed_level;
  if (!Object.keys(body).length) return article;
  return api.readingEditArticle(id, body);
}

export async function submitContent(api = adminApi, submitted, file = null) {
  return api.readingSubmit(submitted, file);
}

/* The sets for an article, newest first as the server returns them. */
export async function loadSets(api = adminApi, articleId) {
  const found = await api.readingSets(articleId);
  return found.items || [];
}

export { failureReason };
