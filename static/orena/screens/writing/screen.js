/* Writing (frame 18, `#/write` and `#/write/:id`; D-091): compose or continue a draft, request an
   AI review, read it (strengths, priority/other issues, dimension scores, an estimated range),
   open one finding for its WHY/HOW detail, apply a fix, and revise. Frame 61 (Prompt Setup) opens
   from here as a sheet, never its own route (no frame draws one for it).

   Real data throughout: `POST /api/evaluate` (the Review action, bounded by `writing-limits.js`,
   rule 28), `GET /api/essays/{id}` (the rich detail this screen is built from - issues with a real
   `priority` flag, grounded strengths, dimension scores, the revision series) merged with `GET
   /api/essays/{id}/review` for the one thing only that endpoint computes (a finding's `kind`; see
   model.js), and `POST`/`DELETE /api/essays/{id}/keep` (called directly via `request()` -
   `infrastructure/api.js` has no wrapper for it and is a shared file this screen does not own).

   The draft itself is device memory synced to the account when one exists (`product/draft-sync.js`,
   kept whole, not rewritten - AGENTS.md §7: drafts are device memory by design), under the same
   keys the old room used (`essay:<series>`, `expression:free`) so a piece continues across the
   cutover. The frame draws no multi-device conflict choice, so a conflict is left unresolved: the
   learner's words stay on this device (saved as such) and the other device's copy is not
   overwritten.

   One `finding` state drives both the popover in the draft and the detail card in the review, as
   the frame's does. Nothing here draws what the frame does not: there is no "Related grammar" and no
   "Practice this" (both lead to R5 grammar content, retired 2026-09-28; Grammar Lab's contract is
   not written yet). */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { markGlyph } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { openSheet, sheetHead, bindClose } from '../../kit/overlay.js';
import { toast } from '../../kit/toast.js';
import { langAttr } from '../../kit/lang.js';
import { shellCopy as s } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api, request } from '../../infrastructure/api.js';
import { editWouldFit, measureWriting } from '../../capabilities/writing-limits.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { orenaPresent } from '../../agent/presence.js';
import { draftSync, snapshot } from '../../product/draft-sync.js';
import { applyFix } from '../../product/revision.js';
import { t } from './copy.js';
import {
  DEFAULT_REGISTER,
  DEFAULT_TARGET,
  NEW_DRAFT_KEY,
  PARKED_INDEX,
  PARKED_PREFIX,
  SETUP_REGISTERS,
  SETUP_TARGETS,
  allIssues,
  buildSegments,
  charCountOf,
  dimensionRows,
  draftKeyFor,
  findingIsOpen,
  firstSentence,
  levelCode,
  intentKey,
  intentRecord,
  levelLabel,
  mapEssay,
  parkedKeys,
  parsePiece,
  readIntent,
  reviewGate,
  reviewPayload,
  saveTone,
  setupLevels,
  tooShortNotice,
  reviewCountdown,
  whenLabel,
  wordCountOf,
} from './model.js';

const REGISTER_KEY = { informal: 'registerInformal', neutral: 'registerNeutral', formal: 'registerFormal' };
const LIMIT_KEY = { characters: 'tooLongCharacters', bytes: 'tooLongBytes', lines: 'tooLongLines' };
const HOLE = '';

/* Register and target length are the learner's own intention for the piece; the backend has no field
   for them (model.js `reviewPayload`), so they are kept with the draft on this device (model.js
   `readIntent`) - per piece, and carried from a new draft to the piece its first review becomes. */

/* An old Chinese review may have been written under an earlier evaluator contract (D-103.7). Opening the
   essay asks the server to refresh exactly that review if - and only if - its stored language pair is
   affected; the server keeps the earlier review as history and answers `current` at no cost otherwise.
   Once per essay per visit, only where the pair can be affected, and a refusal or an unavailable
   provider leaves the review as it was. It runs in the BACKGROUND: the room draws the stored review at
   once (a provider call can take a minute) and repaints the review when a refreshed one arrives. */
const refreshAsked = new Set();

/* Resolves to the server's status ('refreshed', 'current', ...) or '' when nothing was asked or it failed. */
async function refreshIfStale(id, language) {
  if (language !== 'zh' || refreshAsked.has(id)) return '';
  refreshAsked.add(id);
  try {
    return String((await api.refreshEssayReview(id))?.status || '');
  } catch {
    return ''; /* the stored review stands */
  }
}

async function fetchEssay(id) {
  const [detail, review] = await Promise.all([api.essay(id), api.essayReview(id)]);
  return mapEssay(detail, review);
}

export default async function mountWriting(element, ctx) {
  await useStyles('screens/writing/writing.css');
  const context = ctx.context;
  const language = context.language || 'en';
  const memory = context.memory;
  const uiLocale = languages().ui;
  const supportLang = languages().support;

  const piece = parsePiece(ctx.params?.id);
  if (piece.kind === 'unknown') throw new Error('Writing: not a piece this room knows');
  const essay0 = piece.kind === 'essay' ? await fetchEssay(piece.id) : null;
  if (!ctx.isCurrent()) return undefined;
  if (piece.kind === 'essay' && !essay0) throw new Error(`Writing: essay ${piece.id} not found`);
  // A reviewed piece opens on its latest revision: an older number (a series' first essay,
  // `essay:<series>`) is only a way in.
  if (essay0 && essay0.latestId && essay0.latestId !== essay0.id) {
    ctx.replace(ctx.href('writingDraft', { id: essay0.latestId }));
    return undefined;
  }
  let essay = essay0;

  const key = draftKeyFor(essay);
  const storedText = String(memory.value.expressions[key] || '');
  const storedTask = String(memory.value.expressions[`${key}::task`] || '');
  let text = essay ? storedText || essay.text : storedText;
  let promptText = essay ? essay.prompt : storedTask;
  const intent = readIntent(memory.value.expressions, key);
  let level = levelCode(essay?.level, language) || levelCode(intent.level, language) || levelCode(context.level, language) || setupLevels(language)[1].id;
  /* How the learner came in (Practice Hub, HW-1/HW-2): `entry=free` names the blank page "Free writing";
     `setup=prompt|topic` opens Prompt Setup over the room, as the design does, before writing. Neither
     clears a draft that is waiting: the learner's words are never emptied by an entry. A reviewed piece is
     its own piece and ignores both. */
  const entryFree = !essay && ctx.query?.get('entry') === 'free';
  const entrySetup = !essay ? ctx.query?.get('setup') || '' : '';
  // An earlier draft chosen from the Practice Hub's list (LEX-062).
  const entryOpen = !essay ? ctx.query?.get('open') || '' : '';
  if (ctx.query?.has('entry') || ctx.query?.has('setup') || ctx.query?.has('open')) history.replaceState(null, '', location.hash.split('?')[0]);
  /* Register and target start at the design's own defaults for a new draft (Informal, ~150 words); a piece
     already reviewed shows only what the learner chose for it. */
  let register = intent.register || (essay ? '' : DEFAULT_REGISTER);
  let target = intent.target || (essay ? 0 : DEFAULT_TARGET);
  let free = !essay && (intent.free || entryFree);
  let failed = null;

  let leftMode = essay && text === essay.text ? 'marked' : 'edit';
  let rightMode = essay ? 'review' : 'none';
  let activePane = essay ? 'review' : 'draft';
  let finding = null;
  let whyHow = 'why';
  let saveWhere = 'device';
  let editedAt = 0;
  let savingTimer = 0;
  let busyReview = false;
  let busyKeep = false;
  let entered = false;
  const dismissed = new Set();
  const root = document.createElement('section');
  root.className = 's-writing__root';

  const sync = draftSync({
    api,
    memory,
    id: key,
    /* One statement of where the words are. An edit the account has not answered yet is "Saving", not "on this
       device" (it flipped to the device and back on every keystroke); only an answer that never comes (8 s) or a
       draft the account does not keep says "on this device". */
    onWhere: (where) => {
      const pending = where === 'device' && sync.active && Date.now() - editedAt < 8000;
      saveWhere = pending ? 'saving' : where;
      clearTimeout(savingTimer);
      if (pending) {
        savingTimer = setTimeout(() => {
          if (saveWhere === 'saving') {
            saveWhere = 'device';
            refreshChrome();
          }
        }, 8000 - (Date.now() - editedAt) + 50);
      }
      refreshChrome();
    },
    // The other device's copy is the account's; this device's words stay here, saved as such.
    onElsewhere: () => {},
  });
  /* Only words this device really holds are a local snapshot: with none, the account's draft (if it
     keeps one) is what opens - "the latest version in the box unless a draft is waiting". */
  const local = storedText || (!essay && storedTask) ? snapshot(storedText, essay ? essay.prompt : storedTask) : snapshot('', '');
  const opened = await sync.open(local);
  if (!ctx.isCurrent()) return undefined;
  if (opened) {
    text = opened.text;
    if (opened.task) promptText = opened.task;
    memory.write(key, text);
    if (essay) leftMode = text === essay.text ? 'marked' : 'edit';
  }
  // The sheet is named for the entry: a blank page is Free writing, a task is a Prompt (LEX-077).
  const setupTitle = () => (free ? t('freeSetupTitle') : t('promptSetupTitle'));
  const untitled = () => (free ? t('freeTitle') : t('promptFallback'));

  /* Where the learner came in decides the draft they get (LEX-054). Free Writing and Your Topic are new
     drafts: with nothing waiting they start blank; with a draft waiting the learner is asked before anything
     is set aside (below), and a draft set aside is kept, never deleted. Continue draft (no entry) opens what
     waits - the current draft, else the newest one set aside. */
  const fresh = !essay && (entryFree || entrySetup === 'topic');
  const saveIntent = () => {
    try {
      memory.write(intentKey(key), intentRecord({ register, target, level, free }));
    } catch {
      /* Device memory refused; the choice holds for this visit. */
    }
  };
  function startBlank() {
    text = '';
    promptText = '';
    register = DEFAULT_REGISTER;
    target = DEFAULT_TARGET;
    free = entryFree;
    finding = null;
    entered = false;
    memory.write(key, '');
    memory.write(`${key}::task`, '');
    saveIntent();
    sync.edit(snapshot('', ''));
  }
  /* Set the current draft aside under its own key: words, task and intent on the device, and the same
     snapshot with the account when it keeps drafts. */
  function parkCurrent() {
    // A draft with no words is not a draft to keep: nothing is parked for it (LEX-077).
    if (!text.trim()) return;
    const id = `${PARKED_PREFIX}${Date.now().toString(36)}`;
    memory.write(id, text);
    memory.write(`${id}::task`, promptText);
    memory.write(intentKey(id), intentRecord({ register, target, level, free }));
    memory.write(PARKED_INDEX, [...parkedKeys(memory.value.expressions).filter((k) => k !== id), id].join(','));
    const parked = draftSync({ api, memory, id });
    void parked
      .open(snapshot(text, promptText))
      .then(() => parked.flush())
      .catch(() => {});
  }
  function restoreParked(wanted = '') {
    const ex = memory.value.expressions;
    const keys = parkedKeys(ex);
    const id = wanted && keys.includes(wanted) ? wanted : [...keys].reverse().find((k) => String(ex[k] || '').trim());
    if (!id) return;
    // Choosing an earlier draft while words are in the box sets those words aside first: nothing is replaced.
    if (promptText.trim() || (wanted && text.trim())) parkCurrent(); // a task typed with no words is set aside too, not dropped
    const kept = parkedKeys(memory.value.expressions).filter((k) => k !== id);
    const back = readIntent(ex, id);
    text = String(ex[id] || '');
    promptText = String(ex[`${id}::task`] || '');
    register = back.register || DEFAULT_REGISTER;
    target = back.target || DEFAULT_TARGET;
    free = back.free;
    level = levelCode(back.level, language) || level;
    memory.write(key, text);
    memory.write(`${key}::task`, promptText);
    saveIntent();
    memory.write(PARKED_INDEX, kept.join(','));
    memory.write(id, '');
    memory.write(`${id}::task`, '');
    memory.write(intentKey(id), '');
    sync.edit(snapshot(text, promptText));
  }
  let choicePending = false;
  if (!essay) {
    const holds = Boolean(text.trim());
    if (fresh && holds) choicePending = true;
    else if (fresh) startBlank();
    else if (entryOpen) restoreParked(entryOpen);
    else if (!entrySetup && !text.trim()) restoreParked();
  }
  // A blank page has no task: a draft that carries one is a prompt draft, whatever the entry said (LEX-077).
  if (free && promptText.trim()) free = false;
  ctx.setCrumb(promptText || untitled());

  /* ------------------------------------------------------------------------- helpers -- */

  const currentIssue = () => allIssues(essay).find((issue) => issue.id === finding) || null;
  const langOf = (code) => langAttr(code);
  const findingIsFixed = (issue) => !findingIsOpen(issue, text);

  function typeLabel(issue) {
    return issue.kindKey ? t(issue.kindKey) : '';
  }

  /* "Grammar · Tense" - the finding's kind and its finer category, whichever the review carries. */
  function findingTitle(issue, { lower = false } = {}) {
    const category = issue.categoryKey ? t(issue.categoryKey) : '';
    return [typeLabel(issue), lower ? category.toLocaleLowerCase(uiLocale) : category].filter(Boolean).join(' · ');
  }

  function enterContinuation() {
    if (entered) return;
    if (!essay && !text.trim()) return;
    entered = true;
    try {
      memory.enter({ id: key, title: promptText || essay?.prompt || untitled(), intent: 'writing', excerpt: text.slice(0, 240) });
    } catch {
      /* Device memory refused; the room works without a Continue entry. */
    }
  }

  function countLabel({ short = false } = {}) {
    const words = wordCountOf(text, language);
    /* With a target length the count is progress toward it ("56 / 100 words", Hanzi for Chinese). */
    const progress = target ? t.plural(language === 'zh' ? 'hanziProgress' : 'wordsProgress', words, { target }) : null;
    if (language === 'zh') return progress || t.plural('hanziCount', words);
    const counted = progress || t.plural('wordsOnly', words);
    if (short) return counted;
    // Each count takes its own plural form: "1 word · 5 characters", never one form for both.
    return `${counted} · ${t.plural('charsOnly', charCountOf(text))}`;
  }

  /* The length is counted in the unit of the language being written: words, or Hanzi (LEX-063). */
  const targetUnitKey = () => (language === 'zh' ? 'targetHanziOption' : 'targetWordsOption');

  function metaLine() {
    // A blank page has no prompt to name; a prompt draft's line starts with that word.
    const parts = free ? [] : [t('metaPrefix')];
    if (level) parts.push(levelLabel(level));
    if (register) parts.push(t(REGISTER_KEY[register]));
    if (target) parts.push(`~${t.plural(targetUnitKey(), target)}`);
    parts.push(essay ? t('versionLabel', { n: essay.revisionNo }) : t('versionNone'));
    return parts.join(' · ');
  }

  /* -------------------------------------------------------------------------- markup -- */

  function headerMarkup() {
    return html`<button type="button" class="o-iconbtn o-iconbtn--back" data-act="back" aria-label="${s('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-writing__title">
        <div class="s-writing__title-text" lang="${langOf(language)}">${leftMode === 'edit' && promptText ? (free ? t('freeTitle') : t('draftTab')) : promptText || untitled()}</div>
        <div class="s-writing__title-meta">${metaLine()}</div>
      </div>
      <button type="button" class="s-writing__btn" data-act="setup">${t('setupBtn')}</button>
      ${essay?.canCompare ? html`<button type="button" class="s-writing__btn" data-act="compare">${s('compareVersions')}</button>` : ''}
      <button type="button" class="s-writing__cta" data-act="review" aria-describedby="writing-review-hint">${busyReview ? t('reviewingCta') : essay ? t('reviewAgainCta') : t('reviewCta')}</button>`;
  }

  function tabsMarkup() {
    return html`<button type="button" class="s-writing__tab" data-act="tab" data-tab="draft" aria-selected="${activePane === 'draft'}">${t('draftTab')}</button><button type="button" class="s-writing__tab" data-act="tab" data-tab="review" aria-selected="${activePane === 'review'}">${t('resultTab')}</button>`;
  }

  function draftMetaMarkup() {
    const tone = saveTone(saveWhere);
    return html`<div class="s-writing__draftmeta">
      <span data-count-label>${countLabel()}</span>
      <span class="s-writing__hint" id="writing-review-hint" data-review-hint aria-live="polite">${reviewHint()}</span>
      <span class="s-writing__save" style="color:${tone.color}"><i class="s-writing__save-dot" data-save-dot style="background:${tone.color}"></i><span data-save-label>${t(tone.key)}</span></span>
    </div>`;
  }

  /* The task, read as content beside the writing (LEX-055): the whole prompt, wrapping, never one clipped
     line; the title above it stays one line as the frame draws it. */
  function briefMarkup() {
    return promptText ? html`<div class="s-writing__brief" data-prompt-brief lang="${langOf(language)}">${promptText}</div>` : '';
  }

  function editorMarkup() {
    return html`<textarea class="s-writing__textarea" data-draft-textarea rows="16" lang="${langOf(language)}" maxlength="12000" placeholder="${t('draftPlaceholder')}">${text}</textarea>`;
  }

  function popoverMarkup(issue, tone) {
    const canApply = !findingIsFixed(issue) && applyFix(text, issue) !== null;
    const dot = tone === 'priority' ? 'var(--red)' : 'var(--amber)';
    return html`<span class="s-writing__pop" data-segment-pop>
      <span class="s-writing__pop-cat" style="color:${dot}"><i style="background:${dot}"></i>${findingTitle(issue, { lower: true })}</span>
      <span class="s-writing__pop-fix"><span class="s-writing__pop-old" lang="${langOf(language)}">${issue.fragment}</span>${raw(icon('arrow-right', { size: 15 }))}<span class="s-writing__pop-new" lang="${langOf(language)}">${issue.correction}</span></span>
      ${issue.why ? html`<span class="s-writing__pop-why" lang="${langOf(supportLang)}">${firstSentence(issue.why)}</span>` : ''}
      <span class="s-writing__pop-actions">
        <button type="button" class="s-writing__pop-accept" data-act="accept" ${canApply ? '' : 'disabled'}>${raw(icon('check', { size: 14 }))}${t('accept')}</button>
        <button type="button" class="s-writing__pop-dismiss" data-act="dismiss">${s('dismiss')}</button>
        ${orenaPresent() ? html`<button type="button" class="s-writing__pop-ask" data-act="ask" aria-label="${t('askDeeper')}">${markGlyph({ size: 20, symbol: 'ol-intel-still' })}</button>` : ''}
      </span>
    </span>`;
  }

  function segmentMarkup(segment) {
    if (segment.kind === 'plain') return html`${segment.text}`;
    if (segment.kind === 'strength') return html`<span class="s-writing__seg s-writing__seg--strength">${segment.text}</span>`;
    const isOpen = finding === segment.id;
    return html`<span class="s-writing__segwrap"><span class="s-writing__seg s-writing__seg--${segment.kind}" data-act="segment" data-id="${segment.id}" role="button" tabindex="0" aria-expanded="${isOpen}">${segment.text}</span>${isOpen ? popoverMarkup(segment.issue, segment.kind) : ''}</span>`;
  }

  function markedMarkup() {
    const segments = buildSegments(essay, text, dismissed);
    return html`<div class="s-writing__marked">
        <div class="s-writing__marked-head">
          <span class="s-writing__marked-title" lang="${langOf(language)}">${promptText || t('draftTab')}</span>
          <span class="s-writing__marked-meta">${countLabel({ short: true })} · ${t('savedShort')}</span>
        </div>
        <div class="s-writing__marked-body" data-scroll-region lang="${langOf(language)}">${segments.map(segmentMarkup)}</div>
      </div>
      <div class="s-writing__marked-foot">
        <button type="button" class="s-writing__btn s-writing__btn--edit" data-act="edit">${t('editDraft')}</button>
        <span class="s-writing__legend-item"><i data-tone="priority"></i>${t('legendPriority')}</span>
        <span class="s-writing__legend-item"><i data-tone="other"></i>${t('legendOther')}</span>
        <span class="s-writing__legend-item"><i data-tone="strength"></i>${t('legendStrength')}</span>
      </div>`;
  }

  function findingRow(issue) {
    const fixed = findingIsFixed(issue);
    return html`<button type="button" class="s-writing__finding" data-act="open-finding" data-id="${issue.id}" style="background:${finding === issue.id ? 'var(--accent-soft)' : 'var(--surface)'}">
      ${typeLabel(issue) ? html`<span class="s-writing__finding-type">${typeLabel(issue)}</span>` : ''}
      <span class="s-writing__finding-frag" lang="${langOf(language)}" style="text-decoration:${fixed ? 'line-through' : 'none'}">${issue.fragment}</span>
      <span class="s-writing__finding-state" style="color:${fixed ? 'var(--green)' : 'var(--red)'}">${t(fixed ? 'stateFixed' : 'stateOpen')}</span>
    </button>`;
  }

  function rangeMarkup() {
    const [before, after] = t('estimatedRange', { range: HOLE }).split(HOLE);
    return html`<div class="s-writing__range" lang="${langOf(uiLocale)}">${before}<b>${levelLabel(essay.range)}</b>${after}</div>`;
  }

  function dimensionNote(note) {
    if (!note) return '';
    return note.key === 'dimFixes' ? t.plural('dimFixes', note.n) : t(note.key);
  }

  /* A dismissed finding does not count as an open issue (the design's own promise in its toast): it leaves the
     lists, the dimension counts and the Next bar for this visit. */
  const undismissed = (list) => list.filter((issue) => !dismissed.has(issue.id));

  function reviewSummaryMarkup(enter) {
    const when = whenLabel(essay.createdAt, uiLocale);
    const priority = undismissed(essay.priorityIssues);
    const other = undismissed(essay.otherIssues);
    const rows = dimensionRows(essay.dimensions, [...priority, ...other], text);
    const next = priority[0] || null;
    return html`<div class="${cls('s-writing__review-card', enter && 'is-enter')}" data-scroll-region>
      <div class="s-writing__review-head">
        <div>
          <div class="s-writing__review-eyebrow">${t('reviewTab')} · ${t('versionLabel', { n: essay.revisionNo })}${when ? ` · ${when}` : ''}</div>
          ${essay.summary ? html`<div class="s-writing__review-overall" lang="${langOf(supportLang)}">${essay.summary}</div>` : ''}
        </div>
        <button type="button" class="${cls('s-writing__keep', essay.kept && 'is-kept')}" data-act="keep" ${busyKeep ? 'disabled' : ''}>${t(essay.kept ? 'kept' : 'keep')}</button>
      </div>
      ${
        essay.strengths.length
          ? html`<div><div class="s-writing__section-title s-writing__section-title--good">${t('strengths')}</div>${essay.strengths.map(
              (strength) => html`<div class="s-writing__strength"><span lang="${langOf(language)}">“${strength.span}”</span>${strength.note ? html` — <span class="s-writing__strength-note" lang="${langOf(supportLang)}">${strength.note}</span>` : ''}</div>`,
            )}</div>`
          : ''
      }
      <div><div class="s-writing__section-title s-writing__section-title--bad">${t.plural('priorityIssues', priority.length)}</div>${priority.map(findingRow)}</div>
      ${
        other.length
          ? html`<details><summary class="s-writing__section-title s-writing__section-title--other">${t.plural('otherIssues', other.length)}</summary><div class="s-writing__other">${other.map(findingRow)}</div></details>`
          : ''
      }
      <div class="s-writing__scorecard">
        <div class="s-writing__scorecard-head">
          <span>${t('feedbackSummary')}</span>
          ${essay.overall != null ? html`<span class="s-writing__score">${essay.overall}<small>${t('outOf100')}</small></span>` : ''}
        </div>
        ${rows.map(
          (row) => html`<div class="s-writing__dim">
            <div class="s-writing__dim-row"><span>${t(row.labelKey)}</span><span style="color:${row.color}">${dimensionNote(row.note)}</span></div>
            <div class="s-writing__dim-track"><div class="s-writing__dim-fill" style="width:${row.pct};background:${row.color}"></div></div>
          </div>`,
        )}
      </div>
      ${essay.range ? rangeMarkup() : ''}
      ${next ? html`<button type="button" class="s-writing__next" data-act="next">${t('nextPrefix', { label: t('nextOpenFirst') })}</button>` : ''}
    </div>`;
  }

  function findingBodyMarkup(issue) {
    if (whyHow === 'why') return html`<div class="s-writing__finding-body" lang="${langOf(supportLang)}">${issue.why}</div>`;
    return issue.how || issue.examples[0]
      ? html`<div class="s-writing__example-box">
          ${issue.how ? html`<span lang="${langOf(supportLang)}"><b>${t('reusablePattern')}</b> · ${issue.how}</span>` : ''}
          ${issue.examples[0] ? html`<span><b>${t('anotherExample')}</b> · <span lang="${langOf(language)}">${issue.examples[0]}</span></span>` : ''}
        </div>`
      : '';
  }

  function findingDetailMarkup(issue, enter) {
    const fixed = findingIsFixed(issue);
    const canApply = !fixed && applyFix(text, issue) !== null;
    return html`<div class="${cls('s-writing__finding-card', enter && 'is-enter')}" data-scroll-region>
      <div class="s-writing__finding-head">
        <span>${findingTitle(issue)}</span>
        <button type="button" class="s-writing__close" data-act="close-finding" aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button>
      </div>
      <div class="s-writing__finding-old" lang="${langOf(language)}">${issue.fragment}</div>
      <div class="s-writing__finding-new" lang="${langOf(language)}">${issue.correction}</div>
      <div class="s-writing__whyhow">
        <button type="button" class="${cls('s-writing__pill', whyHow === 'why' && 'is-active')}" data-act="why" aria-pressed="${whyHow === 'why'}">${t('whyTab')}</button>
        <button type="button" class="${cls('s-writing__pill', whyHow === 'how' && 'is-active')}" data-act="how" aria-pressed="${whyHow === 'how'}">${t('howTab')}</button>
      </div>
      <div data-finding-body>${findingBodyMarkup(issue)}</div>
      <div class="s-writing__finding-actions">
        <button type="button" class="s-writing__apply" data-act="apply" ${canApply ? '' : 'disabled'}>${t(fixed ? 'appliedCheck' : 'applySuggestion')}</button>
        ${orenaPresent() ? html`<button type="button" class="s-writing__ask" data-act="ask">${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${t('askDeeper')}</button>` : ''}
      </div>
    </div>`;
  }

  /* A review that did not come stays on screen, with the way to ask again, until the learner acts (LEX-061):
     it is the next attempt, not a timer, that clears it. */
  function failedMarkup() {
    return failed
      ? html`<div class="s-writing__failed" role="alert" lang="${langOf(uiLocale)}"><span>${t('reviewFailed')}</span>${failed.retry ? html`<button type="button" class="s-writing__btn" data-act="review">${s('retry')}</button>` : ''}</div>`
      : '';
  }

  function reviewPaneMarkup(enter) {
    return html`${failedMarkup()}${reviewPaneBody(enter)}`;
  }

  function reviewPaneBody(enter) {
    if (rightMode === 'loading') return html`<div class="s-writing__reviewing">${t('reviewing')}</div>`;
    if (rightMode === 'review' && essay) {
      const issue = currentIssue();
      return issue ? findingDetailMarkup(issue, enter) : reviewSummaryMarkup(enter);
    }
    return html`<div class="s-writing__noreview" lang="${langOf(uiLocale)}">${t('noReviewYet')}</div>`;
  }

  /* ---------------------------------------------------------------------- painting -- */

  element.append(root);
  mount(
    root,
    html`<div class="s-writing__header" data-slot="header"></div>
      <div class="s-writing__tabs" data-slot="tabs"></div>
      <div class="s-writing__grid">
        <div class="s-writing__pane s-writing__pane--draft" data-slot="draft"></div>
        <div class="s-writing__pane s-writing__pane--review" data-slot="review"></div>
      </div>`,
  );
  const slot = (name) => root.querySelector(`[data-slot="${name}"]`);

  function paintHeader() {
    ctx.setCrumb(promptText || untitled());
    mount(slot('header'), headerMarkup());
    refreshChrome();
  }

  function paintTabs() {
    mount(slot('tabs'), tabsMarkup());
    root.dataset.activePane = activePane;
  }

  const draftScroller = (pane) => pane.querySelector('.s-writing__marked-body, [data-draft-textarea]');

  function paintDraft() {
    const pane = slot('draft');
    const before = draftScroller(pane);
    const kind = before?.className;
    const top = before?.scrollTop || 0;
    mount(pane, html`${leftMode === 'edit' ? briefMarkup() : ''}${draftMetaMarkup()}${leftMode === 'edit' ? editorMarkup() : markedMarkup()}`);
    const after = draftScroller(pane);
    if (after && after.className === kind) after.scrollTop = top;
    refreshChrome();
    placePopover();
  }

  /* `enter` plays the frame's `rise` on a card that has just appeared; a refresh in place (a fix
     applied, a keystroke moving a finding to fixed) keeps the reader's scroll and does not replay. */
  function paintReview({ enter = false } = {}) {
    const pane = slot('review');
    const before = pane.querySelector('[data-scroll-region]')?.scrollTop || 0;
    mount(pane, reviewPaneMarkup(enter));
    const card = pane.querySelector('[data-scroll-region]');
    if (card && !enter) card.scrollTop = before;
  }

  function paintAll() {
    paintHeader();
    paintTabs();
    paintDraft();
    paintReview({ enter: true });
  }

  /* A popover opens under the line of the marked span the learner pointed at (a span that wraps has one
     box per line - `getClientRects` - and the popover hangs from that one, not from the span's far end).
     It is kept inside the card horizontally, and the card scrolls (inside itself, never the page) to show it. */
  let pointer = null;
  function placePopover() {
    const pop = root.querySelector('[data-segment-pop]');
    const body = root.querySelector('.s-writing__marked-body');
    const seg = root.querySelector('.s-writing__seg[aria-expanded="true"]');
    if (!pop || !body || !seg) return;
    // The popover itself can make the card scroll (a scrollbar narrows it and rewraps the text), so the
    // placing is done again against what it left behind until it holds still.
    for (let pass = 0; pass < 3; pass += 1) {
      const box = body.getBoundingClientRect();
      const width = Math.min(300, body.clientWidth);
      pop.style.maxWidth = `${width}px`;
      const rects = [...seg.getClientRects()].filter((rect) => rect.width > 0);
      if (!rects.length) return;
      const hit = pointer && rects.find((rect) => pointer.y >= rect.top && pointer.y <= rect.bottom);
      const line = hit || rects[0];
      pop.style.left = '0px'; // its width is measured from the left edge, where it has the whole card
      const popWidth = Math.min(pop.offsetWidth || width, width);
      const start = (hit && pointer.x >= line.left && pointer.x <= line.right ? pointer.x : line.left) - box.left;
      const left = `${Math.max(0, Math.min(start, body.clientWidth - popWidth))}px`;
      const top = `${line.bottom - box.top + body.scrollTop + 8}px`;
      const same = pop.dataset.at === `${left}|${top}`;
      pop.style.left = left;
      pop.style.top = top;
      pop.dataset.at = `${left}|${top}`;
      if (same) break;
    }
    const box = body.getBoundingClientRect();
    const below = pop.getBoundingClientRect().bottom - box.bottom;
    if (below > 0) body.scrollTop += below + 8;
  }

  function refreshChrome() {
    const countEl = root.querySelector('[data-count-label]');
    if (countEl) countEl.textContent = countLabel();
    const tone = saveTone(saveWhere);
    const dotEl = root.querySelector('[data-save-dot]');
    if (dotEl) dotEl.style.background = tone.color;
    const labelEl = root.querySelector('[data-save-label]');
    if (labelEl) labelEl.textContent = t(tone.key);
    const saveWrap = root.querySelector('.s-writing__save');
    if (saveWrap) saveWrap.style.color = tone.color;
    const cta = root.querySelector('[data-act="review"]');
    if (cta) {
      const gate = reviewGate(text, language);
      cta.disabled = !gate.canReview || busyReview;
      cta.title = !gate.canReview && !busyReview ? gateNotice(gate.reason) : '';
    }
    const hintEl = root.querySelector('[data-review-hint]');
    if (hintEl) hintEl.textContent = reviewHint();
  }

  /* One line under the draft while Review is off (D-098): what is still missing, counting down in
     the unit the language is written in, or which ceiling the draft is over. Empty otherwise. */
  function reviewHint() {
    if (busyReview) return '';
    const gate = reviewGate(text, language);
    if (gate.canReview) return '';
    if (gate.reason === 'tooShort') {
      const { key: moreKey, n } = reviewCountdown(text, language);
      return t.plural(moreKey, n);
    }
    return gateNotice(gate.reason);
  }

  /* Why Review is off, said in the unit the language is written in ("at least 2 Hanzi"). */
  function gateNotice(reason) {
    if (reason === 'tooShort') {
      const { key: noticeKey, n } = tooShortNotice(language);
      return t.plural(noticeKey, n);
    }
    return LIMIT_KEY[reason] ? t(LIMIT_KEY[reason]) : '';
  }

  /* ------------------------------------------------------------------------ actions -- */

  function setText(next, { fromEditor = false } = {}) {
    text = next;
    editedAt = Date.now();
    memory.write(key, text);
    sync.edit(snapshot(text, promptText));
    enterContinuation();
    refreshChrome();
    if (!fromEditor) paintDraft();
    scheduleReviewRefresh();
  }

  /* Findings read the live draft (open or fixed), so the review follows what the learner types. */
  let refreshTimer = 0;
  function scheduleReviewRefresh() {
    clearTimeout(refreshTimer);
    if (!essay || rightMode !== 'review') return;
    refreshTimer = setTimeout(() => {
      if (ctx.isCurrent()) paintReview();
    }, 200);
  }

  function openFinding(id, { tab = 'why' } = {}) {
    finding = id;
    whyHow = tab;
    activePane = 'review';
    paintTabs();
    paintDraft();
    paintReview({ enter: true });
  }

  function closeFinding() {
    finding = null;
    paintDraft();
    paintReview({ enter: true });
  }

  function applyIssue(issue, { closeAfter = false } = {}) {
    const result = applyFix(text, issue);
    if (!result) return;
    if (closeAfter) finding = null;
    setText(result.text);
    clearTimeout(refreshTimer);
    paintReview({ enter: closeAfter });
    toast(t('appliedToast'));
    const area = root.querySelector('[data-draft-textarea]');
    if (area) {
      area.focus({ preventScroll: true });
      area.setSelectionRange(result.start, result.end);
    }
  }

  function askAbout(issue) {
    askOrena({
      surface: ctx.route.intent || 'writing.review',
      activity_type: 'writing',
      essay_id: essay?.id,
      selected_item: { type: 'feedback_item', id: issue.id, text: issue.fragment },
    });
  }

  async function toggleKeep() {
    if (!essay || busyKeep) return;
    busyKeep = true;
    paintReview();
    try {
      const wasKept = essay.kept;
      await request(`/api/essays/${essay.id}/keep`, { method: wasKept ? 'DELETE' : 'POST' });
      if (!ctx.isCurrent()) return;
      essay = { ...essay, kept: !wasKept };
    } catch {
      /* Left as it stood - no false confirmation. */
    } finally {
      busyKeep = false;
      if (ctx.isCurrent()) paintReview();
    }
  }

  async function runReview() {
    const gate = reviewGate(text, language);
    if (!gate.canReview || busyReview) return;
    busyReview = true;
    rightMode = 'loading';
    failed = null;
    const hadFinding = finding !== null;
    finding = null;
    // On a phone the answer, or its failure, is on the other tab: take the learner there.
    activePane = 'review';
    paintTabs();
    paintHeader();
    if (hadFinding) paintDraft();
    paintReview();
    const ask = (parentId) => api.evaluate(reviewPayload({ prompt: promptText, text, level, parentId, language }));
    try {
      let result;
      try {
        result = await ask(essay?.id);
      } catch (error) {
        /* A parent the server does not know (a reset account, another learning language) is a
           stale record, not a reason to refuse the review: the piece starts a series again. */
        if (!essay || error?.category !== 'parent_essay_not_found') throw error;
        result = await ask(null);
      }
      if (!ctx.isCurrent()) return;
      const nextKey = `essay:${result.series_id ?? result.id}`;
      memory.recordRevision(nextKey, {
        text,
        essay_id: result.id,
        revision_no: result.revision_no,
        overall: result.overall,
        level: result.app_cefr,
        support: supportLang,
      });
      memory.write(intentKey(nextKey), intentRecord({ register, target, level, free: false }));
      if (!essay) {
        memory.write(intentKey(NEW_DRAFT_KEY), '');
        // The piece now lives under its series; the free-writing slot (and its Continue entry) is
        // empty for the next one.
        memory.remove(NEW_DRAFT_KEY);
        memory.write(`${NEW_DRAFT_KEY}::task`, '');
        sync.edit(snapshot('', ''));
      }
      busyReview = false;
      if (essay && result.id === essay.id) {
        // The same words under the same task were reviewed already: the stored review answers.
        essay = await fetchEssay(essay.id);
        if (!ctx.isCurrent()) return;
        rightMode = 'review';
        leftMode = text === essay.text ? 'marked' : 'edit';
        dismissed.clear();
        activePane = 'review';
        paintAll();
        return;
      }
      ctx.replace(ctx.href('writingDraft', { id: result.id }));
    } catch (error) {
      if (!ctx.isCurrent() || error?.name === 'AbortError') return;
      busyReview = false;
      rightMode = essay ? 'review' : 'none';
      failed = { retry: error?.retryable !== false };
      activePane = 'review';
      paintTabs();
      paintHeader();
      paintReview();
    }
  }

  /* -------------------------------------------------------------------- Prompt setup -- */

  function pillGroup(label, options, selected, group) {
    return html`<div class="s-writing-setup__group"><span class="s-writing-setup__label">${label}</span><div class="${cls('s-writing-setup__pills', options.length <= 3 && 's-writing-setup__pills--even')}">${options.map(
      (option) => html`<button type="button" class="${cls('s-writing__pill', 's-writing__pill--setup', selected === option.id && 'is-active')}" data-choice="${group}" data-value="${option.id}" aria-pressed="${selected === option.id}">${option.label}</button>`,
    )}</div></div>`;
  }

  function paintSetup(sheetEl, handle, { required = false } = {}) {
    mount(
      sheetEl,
      html`${sheetHead({ title: setupTitle(), closeLabel: s('close') })}
      <div class="s-writing-setup__body" data-scroll-region>
        <div>
          <label class="s-writing-setup__label" for="s-writing-prompt">${t('promptFieldLabel')}</label>
          <textarea id="s-writing-prompt" class="s-writing-setup__input" data-prompt-input rows="3" maxlength="240" lang="${langOf(language)}" placeholder="${t('promptPlaceholder')}">${promptText}</textarea>
        </div>
        ${pillGroup(t('levelGroupLabel'), setupLevels(language), level, 'level')}
        ${pillGroup(t('registerGroupLabel'), SETUP_REGISTERS.map((id) => ({ id, label: t(REGISTER_KEY[id]) })), register, 'register')}
        ${pillGroup(t('targetGroupLabel'), SETUP_TARGETS.map((n) => ({ id: String(n), label: t.plural(targetUnitKey(), n) })), String(target || ''), 'target')}
      </div>
      <div class="s-writing-setup__foot">
        <button type="button" class="s-writing-setup__write" data-write ${required && !promptText.trim() ? 'disabled' : ''}>${t('writeCta')}</button>
      </div>`,
    );
    bindClose(sheetEl, handle);
    sheetEl.querySelector('[data-prompt-input]')?.addEventListener('input', (event) => {
      promptText = event.target.value;
      memory.write(`${key}::task`, promptText);
      sync.edit(snapshot(text, promptText));
      free = false;
      saveIntent();
      const write = sheetEl.querySelector('[data-write]');
      if (write) write.disabled = required && !promptText.trim();
      paintHeader();
    });
    sheetEl.querySelectorAll('[data-choice]').forEach((button) => {
      button.addEventListener('click', () => {
        const group = button.dataset.choice;
        const value = button.dataset.value;
        if (group === 'level') level = value;
        else if (group === 'register') register = value;
        else target = Number(value);
        free = false;
        saveIntent();
        paintSetup(sheetEl, handle, { required });
        refreshChrome();
        sheetEl.querySelector(`[data-choice="${group}"][data-value="${value}"]`)?.focus({ preventScroll: true });
        paintHeader();
      });
    });
    sheetEl.querySelector('[data-write]')?.addEventListener('click', () => handle.close());
  }

  /* ------------------------------------------------------------------------- events -- */

  /* A draft is waiting and the learner chose a new one (Free Writing, Your Topic): continue or start new,
     before anything is set aside. Leaving the sheet any other way is "continue" - nothing is replaced. */
  function openChoice() {
    const name = promptText.trim() || untitled();
    const count = language === 'zh' ? t.plural('hanziCount', wordCountOf(text, language)) : t.plural('wordsOnly', wordCountOf(text, language));
    openSheet({
      label: t('choiceTitle'),
      className: 's-writing-setup',
      render: (sheetEl, handle) => {
        mount(
          sheetEl,
          html`${sheetHead({ title: t('choiceTitle'), closeLabel: s('close') })}
          <div class="s-writing-setup__body"><div class="s-writing-choice__line" lang="${langOf(language)}">${name} · ${count}</div><p class="s-writing-choice__kept">${t('choiceKept')}</p></div>
          <div class="s-writing-setup__foot s-writing-choice__foot">
            <button type="button" class="s-writing-setup__write" data-continue>${t('choiceContinue')}</button>
            <button type="button" class="s-writing__btn s-writing-choice__continue" data-new>${t('choiceNew')}</button>
          </div>`,
        );
        bindClose(sheetEl, handle);
        sheetEl.querySelector('[data-continue]')?.addEventListener('click', () => handle.close());
        sheetEl.querySelector('[data-new]')?.addEventListener('click', () => {
          parkCurrent();
          startBlank();
          paintAll();
          handle.close();
          if (entrySetup === 'topic') openSetup({ focusPrompt: true, required: true });
        });
      },
    });
  }

  function openSetup({ focusPrompt = false, required = false } = {}) {
    openSheet({
      label: setupTitle(),
      className: 's-writing-setup',
      render: (sheetEl, handle) => {
        paintSetup(sheetEl, handle, { required });
        // The sheet takes focus when it has rendered; the topic field takes it from there.
        if (focusPrompt) setTimeout(() => sheetEl.querySelector('[data-prompt-input]')?.focus({ preventScroll: true }), 0);
      },
      // The header is repainted while the sheet is open, so the button that opened it is a new one.
      onClose: () => {
        // The prompt may have changed under the sheet: the brief beside the writing shows the task as it now is.
        if (leftMode === 'edit') paintDraft();
        root.querySelector('[data-act="setup"]')?.focus({ preventScroll: true });
      },
    });
  }

  function onClick(event) {
    const node = event.target.closest('[data-act]');
    if (!node || !root.contains(node)) return;
    const act = node.dataset.act;
    if (act === 'back') ctx.back();
    else if (act === 'setup') openSetup();
    else if (act === 'compare') {
      if (essay) ctx.go(ctx.href('wrcompare', { id: essay.id }));
    } else if (act === 'review') runReview();
    else if (act === 'tab') {
      activePane = node.dataset.tab;
      paintTabs();
      // A popover opened while the draft was out of sight (a phone) is placed now that it is seen.
      if (activePane === 'draft') placePopover();
    } else if (act === 'edit') {
      finding = null;
      leftMode = 'edit';
      paintDraft();
      paintReview({ enter: true });
      root.querySelector('[data-draft-textarea]')?.focus({ preventScroll: true });
    } else if (act === 'segment') {
      pointer = event.clientX || event.clientY ? { x: event.clientX, y: event.clientY } : null;
      finding === node.dataset.id ? closeFinding() : openFinding(node.dataset.id);
    } else if (act === 'open-finding') openFinding(node.dataset.id);
    else if (act === 'close-finding') closeFinding();
    else if (act === 'why' || act === 'how') {
      whyHow = act;
      const issue = currentIssue();
      const body = root.querySelector('[data-finding-body]');
      if (issue && body) {
        mount(body, findingBodyMarkup(issue));
        root.querySelectorAll('.s-writing__whyhow [data-act]').forEach((pill) => {
          pill.classList.toggle('is-active', pill.dataset.act === whyHow);
          pill.setAttribute('aria-pressed', String(pill.dataset.act === whyHow));
        });
      }
    } else if (act === 'apply') {
      const issue = currentIssue();
      if (issue) applyIssue(issue);
    } else if (act === 'accept') {
      const issue = currentIssue();
      if (issue) applyIssue(issue, { closeAfter: true });
    } else if (act === 'dismiss') {
      if (finding) dismissed.add(finding);
      finding = null;
      paintDraft();
      paintReview({ enter: true });
      toast(t('dismissedToast'));
    } else if (act === 'ask') {
      const issue = currentIssue();
      if (issue) askAbout(issue);
    } else if (act === 'keep') toggleKeep();
    else if (act === 'next') {
      const first = undismissed(essay.priorityIssues)[0];
      if (first) openFinding(first.id, { tab: 'how' });
    }
  }

  function onKeydown(event) {
    if ((event.key === 'Enter' || event.key === ' ') && event.target.matches?.('[data-act="segment"]')) {
      event.preventDefault();
      event.target.click();
    }
  }

  function refuseTooLong(measured) {
    toast(t(LIMIT_KEY[measured.limitExceeded] || 'tooLongCharacters'));
  }

  function onInput(event) {
    const box = event.target;
    if (!box.matches?.('[data-draft-textarea]')) return;
    /* The box's own maxlength stops typing past the bound and a paste is refused below; any other
       way text arrives (a drop, an extension) is measured here and rolled back, never saved or sent
       (rule 28: nothing is silently truncated). */
    const measured = measureWriting(box.value);
    if (!measured.withinLimits) {
      box.value = text;
      refuseTooLong(measured);
      return;
    }
    setText(box.value, { fromEditor: true });
  }

  function onPaste(event) {
    const box = event.target;
    if (!box.matches?.('[data-draft-textarea]')) return;
    const incoming = event.clipboardData?.getData('text') ?? '';
    if (!incoming) return;
    const measured = editWouldFit(box.value, incoming, box.selectionStart, box.selectionEnd);
    if (measured.withinLimits) return;
    event.preventDefault();
    refuseTooLong(measured);
  }

  root.addEventListener('click', onClick);
  root.addEventListener('keydown', onKeydown);
  root.addEventListener('input', onInput);
  root.addEventListener('paste', onPaste);

  paintAll();
  enterContinuation();
  // After the router has focused the room, so the sheet keeps the focus it takes.
  if (choicePending) setTimeout(() => { if (ctx.isCurrent()) openChoice(); }, 0);
  else if (entrySetup) setTimeout(() => { if (ctx.isCurrent()) openSetup({ focusPrompt: entrySetup === 'topic', required: true }); }, 0);

  if (essay) {
    const shown = essay.id;
    void refreshIfStale(shown, language).then(async (status) => {
      if (status !== 'refreshed' || !ctx.isCurrent() || !essay || essay.id !== shown) return;
      try {
        const fresh = await fetchEssay(shown);
        // Only the review on screen changes; whatever the learner is typing is theirs and stays.
        if (!ctx.isCurrent() || !essay || essay.id !== shown || !fresh) return;
        essay = fresh;
        paintHeader();
        paintReview();
      } catch {
        /* the review already on screen stands */
      }
    });
  }

  return () => {
    clearTimeout(refreshTimer);
    sync.flush().catch(() => {});
  };
}
