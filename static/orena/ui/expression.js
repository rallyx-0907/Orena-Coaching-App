import {
  pageIntro,
  practiceReturn,
  continuationShelf,
  draftStatus,
  responseComposer,
  bindComposer,
  progressReporter,
  keptProvenance,
  hint,
  workspaceFrames,
  refreshDraftStatus,
} from './patterns.js';
import { esc, status, focusRegion } from './html.js';
import { markedHtml, issueMarks } from './draft-marks.js';
import {
  renderVocabularyCollectionCard,
  renderVocabularyBrowseCard,
  renderVocabularyRow,
  renderVocabularyStudyCard,
  compactSupportMeaning,
  supportMeaning,
  vocabularyLevel,
  vocabularyKeepPayload,
  vocabularyStatus,
  masteryStars,
} from './vocabulary-experience.js';
import { openUnderstanding, judgementLabel } from './understanding.js';
import { wordDeepHtml } from './word-deep.js';
import { addWordScreen, createDeckScreen, saveToDeckSheet } from './word-add.js';
import { vocabularySearchHtml } from './vocabulary-search.js';
import { wordClipsHtml } from './word-clips.js';
import { wordStrokesHtml } from './word-strokes.js';
import { strokeTraced, tracedStroke } from '../product/stroke-trace.js';
import {
  bindWritingFeedback,
  revisionHtml,
  writingReviewFailure,
  writingReviewWaiting,
} from './writing-feedback.js';
import {
  MAX_CHARACTERS,
  editWouldFit,
  measureWriting,
} from '../capabilities/writing-limits.js';
import { learningToolbar, bindLearningToolbar } from './learning-toolbar.js';
import { icon } from './phosphor.js';
import { contentCover } from './cover.js';
import { referenceCopy } from './reference.js';
import { openRegisters } from './registers.js';
import { link, sourceLink } from '../product/intent.js';
import { patternsFor } from '../content/patterns.js';

/* One review sitting, not a library: what is due comes a page at a time, and
   the room asks again when it has worked through the page. */
const RECALL_QUEUE = 60;

/* What the room reads of the learner's own words: a first page, which is
   state and not a screen. The study view, the word sheet and "ask about this
   word" read it to know what the learner already has. Browsing, searching and
   paging a learner's whole vocabulary is Thu vien cua toi's (D-074), and it
   asks for its own. */
const SAVED_PAGE = 50;
import {
  grammarShelf,
  filterGrammar,
  grammarFamilies,
} from '../product/grammar-shelf.js';
import { recallShape, blankContext } from '../product/recall.js';
import {
  NEW_PER_DAY,
  REVIEW_LIMIT,
  TYPING_TRIES,
  checkTyped,
  choicesFor,
  meaningOf,
  readReviewSettings,
  taskFor,
} from '../product/recall-modes.js';
import { reviewSettingsSheet, taskCard, taskFoot } from './recall-tasks.js';
import { flushQueue, withWaiting, worthKeeping } from '../product/review-queue.js';
import { collectionSearch, bindCollectionSearch } from './collection-search.js';
import { contentFor } from '../content/texts.js';
import { scene } from './brand.js';
import { draftSync } from '../product/draft-sync.js';

/* A piece the learner already submitted, reopened by its series.

   `essay:<series>` is the Writing room's server identity, where every other
   id here is the device's. It loads the series the server keeps - scoped to
   this account and learning language, so another's or another language's is
   simply not found - and continues it: the latest version in the box unless a
   draft is waiting, the versions as the history, the next review joining the
   same series, and the latest review already beside it. */
async function serverSeries(api, id) {
  const series = /^essay:(\d+)$/.exec(id);
  if (!series) return null;
  const root = await api.essay(Number(series[1]));
  const revisions = [...(root.revisions || [])].sort(
    (a, b) => Number(a.revision_no || 0) - Number(b.revision_no || 0),
  );
  const latest = revisions.at(-1) || root;
  const detail = latest.id === root.id ? root : await api.essay(latest.id);
  return { revisions, latest: detail };
}

export async function renderExpression(root, ctx) {
  const { c, language, api, memory, alive } = ctx,
    id = ctx.location.id || 'expression:free';
  const series = await serverSeries(api, id).catch(() => undefined);
  if (!alive()) return;
  // Asked for by id and not found here: say so, rather than opening an empty
  // room that looks like the piece.
  if (series === undefined) throw Error(c.unavailable);
  const source =
    memory.value.continuation.find((x) => x.id === id) ||
    memory.value.imports.find((x) => x.id === id) ||
    contentFor(language).find((x) => `story:${x.id}` === id);
  const serverRevisions = (series?.revisions || []).map((entry) => ({
    text: String(entry.text || ''),
    essay_id: Number.isInteger(entry.id) ? entry.id : null,
    revision_no: Number.isInteger(entry.revision_no) ? entry.revision_no : null,
    overall: Number.isFinite(entry.overall) ? entry.overall : null,
    level: typeof entry.level_estimate === 'string' ? entry.level_estimate : '',
  }));
  // A reopened series keeps the server's versions and adds what this device
  // recorded since; a device record is never allowed to hide them.
  const revisionsOf = () => {
    const own = memory.value.revisions?.[id] || [];
    if (!serverRevisions.length) return own;
    const known = new Set(serverRevisions.map((entry) => entry.essay_id));
    return [
      ...serverRevisions,
      ...own.filter((entry) => !entry.essay_id || !known.has(entry.essay_id)),
    ];
  };
  // Continue the server's series across visits instead of starting a new one
  // every time the learner comes back to the same piece.
  let parentId =
    [...revisionsOf()].reverse().find((x) => x.essay_id)?.essay_id ?? null;
  /* The room opened from the sidebar is `expression:free`, not `essay:<n>`, so
     it has no server series to load - and reopening it therefore came back
     with the draft restored and the review it had already paid for missing.

     The device knows which server version this piece last became: that is the
     same number the next review continues from. Reading it back is one GET,
     never an evaluation, and it is what makes a reload cost nothing at all. */
  const lastReview =
    series?.latest ||
    (parentId ? await api.essay(parentId).catch(() => null) : null);
  const seriesTitle = series
    ? String(series.latest.prompt || '').split('\n')[0].trim()
    : '';
  const title = source?.title || seriesTitle || c.freeTitle;
  const hasSource = source && !id.startsWith('expression:');
  const original = contentFor(language).find((x) => 'story:' + x.id === id);
  const excerpt =
    source?.excerpt ||
    original?.paragraphs?.[0] ||
    source?.text?.slice(0, 1200) ||
    '';
  const prompt = original?.prompt || c.responsePrompt;
  const invitations = contentFor(language).slice(0, 2);
  /* Writing, composed as a workspace.

     What it replaced: a page-wide heading, one very tall box, then - under the
     box, where a learner only arrives after writing - the draft status, a
     character count, a "feedback target" selector naming a model setting, the
     Review button, and finally a field asking what the piece was for. The
     thing the learner most needed before starting was the last thing they
     could reach, the primary action sat at the bottom of a form, and the
     result pane stood empty beside it taking half the room.

     Now: what this piece is for sits in the heading, before and during the
     writing. The page is the learner's own surface. The actions under it are
     one bar - a shared icon-first toolbar for the secondary ones, the level
     setting among them, and one primary Review. The margin beside it holds the
     source while there is nothing to say and the feedback once there is, and
     the workspace gives the page more width until the review arrives
     (DESIGN_CONTRACT rules 19, 24, 27). */
  const intention = memory.value.expressions[`${id}::task`] || '';
  /* The level the review aims at comes from what the app already knows: the level the learner declared in
     their profile, else the level of the text they are answering. With neither there is nothing to aim at
     and the evaluator reads the level the writing shows, as it always did. */
  const isLevel = (value) => (/^(A1|A2|B1|B2|C1|C2)$/.test(String(value || '')) ? String(value) : '');
  const targetLevel = isLevel(ctx.profile?.declared_level) || isLevel(original?.level) || isLevel(source?.level) || null;
  /* What the frame gives no button of its own stays reachable behind the menu: exploring how a
     sentence sounds in other registers, and the versions of this piece (D-068, rule 4 of the design's
     patterns: everything deeper sits behind one button). */
  const writingActions = [
    {
      name: 'more',
      icon: 'menu',
      kind: 'menu',
      label: c.stageMore,
      items: [
        { name: 'seeReview', label: c.writingSeeReview },
        { name: 'seeCompare', label: c.writingSeeCompare },
        { name: 'registers', label: c.registerExplore },
        { name: 'history', label: c.revisionHistory },
      ],
    },
  ];
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  root.innerHTML = `<header class="wr-top"><a class="wr-back" href="${hasSource ? sourceLink(id) : link('writing')}">${icon('arrow-left', { size: 20 })}<span>${esc(c.writingName)}</span></a><strong class="wr-title">${esc(title)}</strong>${draftStatus(ctx)}<span class="wr-count" data-word-count></span><button class="primary wr-go" form="expressionForm" data-review-action>${icon('sparkle', { size: 18 })}<span>${esc(c.reviewAction)}</span></button><button type="button" class="wr-second" data-revise-more>${icon('pencil-simple', { size: 17 })}<span>${esc(c.revision)}</span></button><span class="wr-menu">${learningToolbar(writingActions, { label: c.writingName })}</span></header><section class="learning-workspace writing-workspace" data-workspace="activity" data-review="waiting" data-compare="off"><div class="wr-tabs" role="group" aria-label="${esc(c.review)}"><button type="button" class="wr-tab" data-wr-tab="activity">${esc(r.writingTabDraft)}</button><button type="button" class="wr-tab" data-wr-tab="result">${esc(r.writingTabReview)}</button></div><div class="workspace-activity"><span class="wr-pane-label">${esc(r.writingTabDraft)}</span><form id="expressionForm" class="writing-sheet"><div class="wr-prompt">${icon('lightbulb', { size: 20 })}<div class="wr-prompt__body">${hasSource ? `<p class="wr-prompt__text" lang="${language}">${esc(prompt)}</p>` : ''}<label class="sr-only" for="writingTask">${esc(c.writingTask)}</label><input id="writingTask" name="task" maxlength="240" autocomplete="off" placeholder="${esc(c.writingIntentionNone)}" value="${esc(intention)}"></div></div><div class="draft-elsewhere" data-draft-elsewhere role="status" hidden></div><label class="sr-only" for="expressionText">${c.respond}</label><div class="wr-draft"><div class="wr-mirror" data-draft-marks aria-hidden="true" lang="${language}"></div><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="10" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id] || series?.latest.text || '')}</textarea></div><span class="meta" data-character-count aria-live="polite"></span><p class="writing-trouble" data-writing-trouble hidden></p></form></div><section class="workspace-result writing-result" aria-label="${esc(c.review)}"><span class="wr-pane-label">${esc(r.writingTabReview)}</span><div class="workspace-result__bar"><button type="button" class="quiet" data-back-to-writing>← ${esc(c.writingKeepWriting)}</button></div><p class="review-stale" data-review-stale-note hidden><span>${esc(c.reviewStale)}</span><button type="button" class="quiet" data-review-again>${esc(c.reviewStaleAction)}</button></p><div class="workspace-result__scroll" id="writingFeedback" aria-live="polite">${excerpt ? `<aside class="expression-context"><small>${esc(c.expressionContext)}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote><a class="quiet" href="${sourceLink(id)}">${c.returnLabel} ↗</a></aside>` : writingReviewWaiting(c)}</div></section></section><div class="workspace-secondary">${excerpt ? '' : `<aside class="expression-starters"><h2>${c.expressionStarters}</h2><p class="meta">${c.expressionStarterNote}</p>${invitations.map((item) => `<a href="${link('expression', { id: 'story:' + item.id })}"><small>${c.generated}</small><strong lang="${language}">${esc(item.prompt)}</strong><span>${c.usePrompt} ↗</span></a>`).join('')}</aside>`}<section class="revision-history" data-revisions></section></div>${continuationShelf(ctx, 2)}`;
  /* The activity and its result share one frame. Wide screens show both at
     once, so the result is beside the writing rather than below it. Narrow
     screens take them one frame at a time, and the learner is placed at the
     start of the result frame instead of halfway down the page. */
  const { showResult, showActivity } = workspaceFrames(
    root.querySelector('.learning-workspace'),
    {
      back: root.querySelector('[data-back-to-writing]'),
      focus: () => root.querySelector('#expressionText'),
      result: root.querySelector('#writingFeedback'),
    },
  );
  const workspace = root.querySelector('.writing-workspace');
  /* The revision compare takes the whole room (three columns, as the frame draws it); going back to the
     draft gives the room back to the two panes. */
  /* Whether a version has one before it to be read against, and which of the two views is up. */
  const topBar = root.querySelector('.wr-top');
  let hasCompare = false;
  const setCompare = (on) => {
    workspace.dataset.compare = on ? 'on' : 'off';
    topBar.dataset.compare = hasCompare ? workspace.dataset.compare : 'none';
    paintGo();
  };
  topBar.dataset.compare = 'none';
  const toActivity = () => {
    setCompare(false);
    showActivity();
    fitDraft();
  };
  workspace.querySelector('[data-wr-tab="activity"]').onclick = toActivity;
  workspace.querySelector('[data-wr-tab="result"]').onclick = showResult;
  /* Which words the review on screen was written about.

     A learner who edits after a review still wants to see it - it is the last
     thing anybody said about their writing - but it stops being *current* the
     moment the words change. So the text it answered is remembered, and the
     room says plainly whose version it belongs to rather than deleting it or
     letting it pass for an answer about what is now in the box. */
  let reviewedText = null;
  const writingMenu = bindLearningToolbar(root.querySelector('.wr-menu .learning-toolbar'), {
    onAction: (name) => {
      if (name === 'seeReview') {
        setCompare(false);
        return showResult();
      }
      if (name === 'seeCompare') {
        setCompare(true);
        return showResult();
      }
      if (name === 'registers')
        return openRegisters(ctx, { text: root.querySelector('textarea').value, title });
      if (name === 'history')
        root
          .querySelector('[data-revisions]')
          ?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    },
  });
  /* One compact line beside the action, never a pane. A provider that is not
     configured changes nothing about the writing, so it takes one row to say
     so and the workspace stays the workspace. */
  const trouble = root.querySelector('[data-writing-trouble]');
  /* Say whether the review on screen is still about what is in the box.

     Called whenever the words change and whenever a review arrives. It never
     removes the feedback: a learner mid-revision is looking at it precisely
     because they are acting on it, and taking it away the moment they type
     would be taking away the reason they were typing. It stops being current,
     visibly, and says how to make it current again. */
  function markReviewFreshness() {
    const stale = reviewedText !== null && reviewedText !== box.value;
    workspace.dataset.reviewStale = String(stale);
    paintGo();
    paintMarks();
    // A distinct name from the workspace's own flag above: one selector that
    // matched both would have hidden the whole workspace, and only the grid's
    // own `display` kept that from showing.
    const note = root.querySelector('[data-review-stale-note]');
    if (note) note.hidden = !stale;
  }
  /* The top bar's one primary action follows the room, as the frame draws it: Review while there is
     nothing current to read, "Revise" once there is (it takes the learner back to the draft). */
  const go = root.querySelector('[data-review-action]');
  function paintGo() {
    const fresh = workspace.dataset.review === 'ready' && workspace.dataset.reviewStale !== 'true';
    const mode = fresh && workspace.dataset.compare === 'on' ? 'done' : fresh ? 'revise' : 'review';
    go.dataset.mode = mode;
    topBar.dataset.mode = mode;
    const shown = { done: ['check', c.writingDone], revise: ['pencil-simple', c.revision] }[mode] || ['sparkle', workspace.dataset.review === 'ready' ? c.reviewAgain : c.reviewAction];
    go.innerHTML = `${icon(shown[0], { size: 18 })}<span>${esc(shown[1])}</span>`;
  }
  root.querySelector('[data-revise-more]').onclick = () => {
    toActivity();
    root.querySelector('textarea').focus();
  };
  go.onclick = (event) => {
    if (go.dataset.mode === 'done') {
      event.preventDefault();
      location.hash = link('writing');
      return;
    }
    if (go.dataset.mode !== 'revise') return;
    event.preventDefault();
    toActivity();
    root.querySelector('textarea').focus();
  };
  /* The review's findings, marked in the draft, and the box fitted to its words so the pane - not the box -
     is what scrolls. */
  const marks = root.querySelector('[data-draft-marks]');
  let appliedNow = () => new Set();
  function paintMarks() {
    const on = workspace.dataset.review === 'ready' && reviewIssues.length > 0;
    marks.innerHTML = on ? markedHtml(box.value, issueMarks(reviewIssues.filter((issue) => !appliedNow().has(issue.id)))) : '';
    fitDraft();
  }
  // A pane that is not on screen (a phone shows one at a time) has no height to measure: it is fitted when it appears.
  function fitDraft() {
    box.style.blockSize = '';
    if (workspace.dataset.review === 'waiting' || !box.offsetParent) return;
    box.style.blockSize = 'auto';
    box.style.blockSize = `${box.scrollHeight}px`;
  }
  let reviewIssues = [];
  const sayTrouble = (html) => {
    trouble.innerHTML = html || '';
    trouble.hidden = !html;
  };
  const paintRevisions = () => {
    const list = revisionsOf();
    const host = root.querySelector('[data-revisions]');
    if (!list.length) {
      host.innerHTML = '';
      return;
    }
    host.innerHTML = `<div class="section-head"><h2>${esc(c.revisionHistory)}</h2>${hint({ text: c.revisionNote })}</div><ol class="revision-list">${list
      .map(
        (entry, index) =>
          `<li><button class="quiet" data-revision="${index}"><small>${esc(c.revisionLabel)} ${entry.revision_no ?? index + 1}${entry.overall != null ? ` · ${entry.overall}` : ''}${entry.level ? ` · ${esc(entry.level)}` : ''}</small><span lang="${esc(language)}">${esc(entry.text.slice(0, 120))}${entry.text.length > 120 ? '…' : ''}</span></button></li>`,
      )
      .join('')}</ol>`;
    host.querySelectorAll('[data-revision]').forEach((button) => {
      button.onclick = () => {
        const entry = revisionsOf()[Number(button.dataset.revision)];
        if (!entry) return;
        // Bringing a version back is a choice the learner makes explicitly,
        // and the words currently in the box are never lost to it silently.
        const current = root.querySelector('textarea');
        if (current.value.trim() && current.value !== entry.text)
          memory.recordRevision(id, { text: current.value });
        current.value = entry.text;
        memory.write(id, entry.text);
        sync.edit(draftNow());
        updateCount();
        paintRevisions();
        current.focus();
        status(c.revisionRestored);
      };
    });
  };
  /* A running character count answers nothing while a piece is a few
     sentences long. It appears only as the draft nears the limit the box
     enforces, which is when the number starts to decide something. */
  const LIMIT = 12000;
  const words = new Intl.Segmenter(language, { granularity: 'word' });
  const updateCount = () => {
    const value = root.querySelector('textarea').value;
    const length = [...value].length;
    const n = [...words.segment(value)].filter((part) => part.isWordLike).length;
    root.querySelector('[data-word-count]').textContent = `${n} ${r.writingWords}`;
    root.querySelector('[data-character-count]').textContent =
      length >= LIMIT * 0.9 ? `${length} / ${LIMIT} ${c.draftCount}` : '';
  };
  updateCount();
  paintRevisions();
  /* The review in the baseline's shape: the version beside the one before it when
     there is one, then the findings, each of which opens as a sheet and can be
     applied to the draft. Both come from the contract endpoints, so what is
     shown is what the evaluator said and nothing else. */
  let feedbackBinding = null;
  const presentReview = async (result, text) => {
    const feedback = root.querySelector('#writingFeedback');
    feedbackBinding?.destroy();
    feedbackBinding = null;
    feedback.innerHTML = `<div class="wf" role="status" aria-label="${esc(c.quickThinking)}"><p class="qs-skeleton"><span></span></p></div>`;
    workspace.dataset.review = 'ready';
    let review;
    let compare = null;
    try {
      review = await api.essayReview(result.id);
      if ((result.revision_no || 1) > 1) compare = await api.essayRevision(result.id).catch(() => null);
    } catch (error) {
      if (!alive()) return;
      feedback.innerHTML = writingReviewWaiting(c);
      sayTrouble(writingReviewFailure(c, error));
      const retry = trouble.querySelector('[data-retry-review]');
      if (retry) retry.onclick = () => presentReview(result, text);
      return;
    }
    if (!alive()) return;
    hasCompare = Boolean(compare);
    setCompare(hasCompare);
    feedback.innerHTML = `${compare ? revisionHtml(c, compare, { language }) : ''}<div data-wf-review></div>`;
    reviewIssues = review.issues || [];
    feedbackBinding = bindWritingFeedback({
      ctx,
      host: feedback.querySelector('[data-wf-review]'),
      review,
      draft: root.querySelector('#expressionText'),
      language,
      alive,
      onApplied: () => paintMarks(),
    });
    appliedNow = feedbackBinding.applied;
    reviewedText = text;
    markReviewFreshness();
    sayTrouble('');
  };
  /* Reopened, the latest review is already there: the piece comes back with
     what was said about it, not as a blank result frame - and without asking a
     provider for anything, because it was already paid for once.

     Whether it is *this* learner's review is the server's answer, not a guess:
     every stored evaluation now carries the identity it was produced under
     (`writing_coach/writing_review_identity.py`), including the support
     language. A device-side record could only vouch for reviews this device
     made; the identity travels with the evaluation, so a review earned on
     another device is recognised here too - and a Vietnamese one is never
     replayed to a learner now reading Chinese. */
  const reviewSpeaksTo = (essay) => {
    const identity = essay?.module_data?.review;
    if (!identity) return false;
    return (
      String(identity.support_language || '') === String(ctx.support || '') &&
      String(identity.learning_language || '').split('-')[0] === String(language).split('-')[0]
    );
  };
  /* Kept with the account when this deployment keeps work there; on this
     device always. The status says which is true, and a version changed on
     another device is shown for the learner to choose, never merged. */
  const box = root.querySelector('#expressionText');
  // It goes with the page: a width that changes (the window, or the pane appearing) fits the box again.
  let fittedWidth = 0;
  new ResizeObserver(([entry]) => {
    if (entry.contentRect.width === fittedWidth) return;
    fittedWidth = entry.contentRect.width;
    fitDraft();
  }).observe(box.parentElement);
  const taskInput = root.querySelector('[name=task]');
  const elsewhereNode = root.querySelector('[data-draft-elsewhere]');
  // The piece comes back with what was said about it. Nothing is asked of a
  // provider to do this: the evaluation was stored with the essay.
  if (lastReview && Array.isArray(lastReview.issues) && reviewSpeaksTo(lastReview))
    presentReview(lastReview, String(lastReview.text || ''));
  root.querySelector('[data-review-again]').onclick = () =>
    root.querySelector('form').requestSubmit();
  // The draft is the words and the task they answer, always together.
  function draftNow() {
    return { text: box.value, task: taskInput.value };
  }
  const showDraft = (draft) => {
    box.value = draft.text;
    taskInput.value = draft.task;
    memory.write(id, draft.text);
    memory.write(`${id}::task`, draft.task);
    updateCount();
    // The account's copy may be a version the review on screen predates.
    markReviewFreshness();
  };
  const sync = draftSync({
    api,
    memory,
    id,
    onWhere: (where) => {
      if (alive()) refreshDraftStatus(root.querySelector('[data-draft-status]'), ctx, where);
    },
    onElsewhere: (other) => {
      if (!alive()) return;
      elsewhereNode.innerHTML = `<p>${esc(c.draftElsewhere)}</p><blockquote lang="${esc(language)}">${esc(other.text.slice(0, 280))}${other.text.length > 280 ? '…' : ''}</blockquote>${other.task ? `<p class="draft-elsewhere__task"><span>${esc(c.writingTask)}</span> ${esc(other.task)}</p>` : ''}<div class="draft-elsewhere__actions"><button type="button" class="quiet" data-use-elsewhere>${esc(c.draftUseElsewhere)}</button><button type="button" class="quiet" data-keep-here>${esc(c.draftKeepHere)}</button></div>`;
      elsewhereNode.hidden = false;
      elsewhereNode.querySelector('[data-use-elsewhere]').onclick = () => {
        // The words in the box are kept as a version first, never lost.
        if (box.value.trim()) memory.recordRevision(id, { text: box.value });
        const chosen = sync.useElsewhere();
        if (chosen) {
          showDraft(chosen);
          paintRevisions();
        }
        elsewhereNode.hidden = true;
        box.focus();
      };
      elsewhereNode.querySelector('[data-keep-here]').onclick = () => {
        sync.keepHere(draftNow());
        elsewhereNode.hidden = true;
        box.focus();
      };
    },
  });
  const openedWith = draftNow();
  sync
    .open({
      text: memory.value.expressions[id] || '',
      task: memory.value.expressions[`${id}::task`] || '',
    })
    .then((draft) => {
      // Only a room the learner has not touched since it opened takes the
      // account's copy; typed words and task are never replaced under them.
      const now = draftNow();
      if (!alive() || !draft || now.text !== openedWith.text || now.task !== openedWith.task) return;
      showDraft(draft);
    });
  taskInput.addEventListener('input', () => {
    memory.write(`${id}::task`, taskInput.value);
    sync.edit(draftNow());
  });
  /* A paste that does not fit is refused before it is inserted.

     The order matters: a learner who drops a whole document into the box
     should be told so, not watched while the page lays out a megabyte and the
     network carries it to a server that was always going to refuse it. The
     edit is measured as it would leave the box, so what is judged is the
     result - and when it does not fit, nothing is inserted and nothing the
     learner already wrote is touched. Never truncated: keeping the first
     twelve thousand characters of somebody's document is a worse answer than
     saying it will not fit. */
  box.addEventListener('paste', (event) => {
    const incoming = event.clipboardData?.getData('text') ?? '';
    if (!incoming) return;
    const measured = editWouldFit(box.value, incoming, box.selectionStart, box.selectionEnd);
    if (measured.withinLimits) return;
    event.preventDefault();
    sayTrouble(`<span>${esc(c.writingTooLongPaste)}</span>`);
  });
  box.oninput = (event) => {
    /* The box's own maxlength stops typing past the bound, and a paste is
       stopped above. This is the last line: any other way text arrives - a
       drop, an extension, a script - is measured here, and an over-long value
       is rolled back rather than saved or sent. */
    const measured = measureWriting(event.target.value);
    if (!measured.withinLimits) {
      event.target.value = memory.value.expressions[id] || '';
      updateCount();
      sayTrouble(`<span>${esc(c.writingTooLong)}</span>`);
      return;
    }
    memory.write(id, event.target.value);
    memory.enter({ id, title, intent: 'writing', excerpt });
    refreshDraftStatus(root.querySelector('[data-draft-status]'), ctx);
    sync.edit(draftNow());
    updateCount();
    markReviewFreshness();
  };
  root.querySelector('form').onsubmit = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    // The primary action by role: a hint beside the draft status is also a
    // button inside this form and must never be the one that gets disabled.
    const button = root.querySelector('[data-review-action]'),
      feedback = root.querySelector('#writingFeedback');
    button.disabled = true;
    sayTrouble('');
    workspace.dataset.review = 'working';
    feedback.innerHTML = `<p class="review-working" role="status">${esc(c.reviewWorking)}</p>`;
    /* The result is the point of pressing Review, so its frame opens at once -
       loading, feedback or an honest failure - instead of leaving the learner
       to discover it below the writing area. */
    showResult();
    try {
      const text = root.querySelector('textarea').value;
      /* What the learner is actually writing. A lab report, a support email
         and a commit message are not the same task, and judging any of them as
         generic prose marks correct domain choices as mistakes. The evaluator
         has always accepted a task; nothing asked the learner for one. */
      const task = root.querySelector('[name=task]').value.trim();
      if (task) memory.write(`${id}::task`, task);
      const ask = (parent) =>
        ctx.mutate(() =>
          api.evaluate({
            prompt: [
              source ? `${title}\n${c.responsePrompt}` : c.freeTitle,
              task && `${c.writingTask} ${task}`,
            ]
              .filter(Boolean)
              .join('\n'),
            text,
            target_cefr: targetLevel,
            learning_language: language,
            parent_essay_id: parent,
          }),
        );
      /* This device remembers which server version this piece continues, and
         the server is the one that knows whether that version still exists in
         this learning scope. When it does not - a reset sandbox, a piece begun
         under another learning language - the request came back refused and
         explicitly not retryable, and the learner was told their writing could
         not be reviewed. Permanently: nothing on the page could clear a number
         they cannot see.

         A parent the server does not recognise is a stale device record, not a
         reason to refuse a learner their review. It is dropped and the piece
         starts a series again, which costs the comparison with the previous
         version and nothing else. */
      let result;
      try {
        result = await ask(parentId);
      } catch (error) {
        if (!parentId || error?.category !== 'parent_essay_not_found') throw error;
        parentId = null;
        result = await ask(null);
      }
      if (!alive()) return;
      parentId = result.id;
      memory.recordRevision(id, {
        text,
        essay_id: Number.isInteger(result.id) ? result.id : null,
        revision_no: Number.isInteger(result.revision_no)
          ? result.revision_no
          : null,
        overall: Number.isFinite(result.overall) ? result.overall : null,
        level: typeof result.app_cefr === 'string' ? result.app_cefr : '',
        support: ctx.support,
      });
      paintRevisions();
      presentReview(result, text);
    } catch (error) {
      if (alive()) {
        /* A review that did not arrive is news about the review, not about the
           writing. It is said in one line beside the action that asked for it,
           and the learner is put back on their page with their draft intact -
           rather than left in a result frame holding a single sentence. */
        workspace.dataset.review = 'waiting';
        feedback.innerHTML = excerpt
          ? `<aside class="expression-context"><small>${esc(c.expressionContext)}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote></aside>`
          : writingReviewWaiting(c);
        sayTrouble(writingReviewFailure(c, error));
        showActivity();
        const retry = trouble.querySelector('[data-retry-review]');
        if (retry) retry.onclick = () => form.requestSubmit();
      }
    } finally {
      if (alive()) {
        button.disabled = false;
        paintGo();
      }
    }
  };
}
/* The saved-word list already carries what `writing_coach/vocabulary_cards.py`
   shapes into a Vocabulary Card server-side for other surfaces; this mirrors
   that same mapping here so the list renders through the one card contract
   instead of a second, page-local one. Definition and kept translation are
   distinct meanings, not one paragraph choosing between them. */
function vocabularyCardFromLibraryItem(item, language, { pinyinAllowed }) {
  const meanings = [];
  const appendMeaning = (meaning) => {
    const text = String(meaning?.text || '').trim();
    const meaningLanguage = String(meaning?.language || '').trim().toLowerCase();
    if (text && !meanings.some((entry) => entry.language === meaningLanguage && entry.text === text)) {
      meanings.push({ language: meaningLanguage || 'unknown', text });
    }
  };
  const definition = String(item.definition || '').trim();
  const translation = String(item.translation_vi || '').trim();
  const shortMeanings = Array.isArray(item.short_meanings) ? item.short_meanings : [];
  if (definition) meanings.push({ language, text: definition });
  if (translation && !shortMeanings.some((meaning) => String(meaning?.language || '').toLowerCase() === 'vi')) meanings.push({ language: 'vi', text: translation });
  Object.entries(item.support_translations || {}).forEach(([meaningLanguage, text]) => appendMeaning({ language: meaningLanguage, text }));
  shortMeanings.forEach(appendMeaning);
  (Array.isArray(item.detailed_definitions) ? item.detailed_definitions : []).forEach(appendMeaning);
  const kind = String(item.source_kind || '').trim();
  const fragment = String(item.source_fragment || '').trim();
  // Where this came from, as the learner would name it: the piece's own title,
  // which the saved record already carries.
  const where = String(item.focus_note || '').trim();
  const card = {
    identity: { language, normalized: String(item.normalized_term || item.normalized_word || item.word || '').toLowerCase() },
    headword: item.word,
    meanings,
    source_encounters: kind && fragment ? [{ kind, fragment, where }] : [],
  };
  const pronunciation = String(item.phonetic || item.pronunciation || item.pronunciations?.[0]?.text || item.readings?.[0]?.text || '').trim();
  if (pronunciation && pinyinAllowed) card.pronunciation = pronunciation;
  if (Array.isArray(item.examples)) card.examples = item.examples;
  if (Array.isArray(item.short_meanings) && item.short_meanings.length) card.short_meanings = item.short_meanings;
  if (Array.isArray(item.detailed_definitions) && item.detailed_definitions.length) card.detailed_definitions = item.detailed_definitions;
  if (Array.isArray(item.usage_notes) && item.usage_notes.length) card.usage = String(item.usage_notes[0]?.text || item.usage_notes[0] || '').trim();
  for (const field of ['level', 'framework', 'topic']) {
    if (item[field]) card[field] = item[field];
  }
  if (item.orthography) card.orthography = item.orthography;
  return card;
}
/* Recall: one item at a time, over the language the learner kept.

   It reads the same saved-language contract My Language does and grades
   through the same scheduler - there is no second store and no second
   algorithm here, only the review loop over what is already due.

   Three stages, because a review session has three questions. What is waiting
   (the landing, which says how much rather than dropping the learner into item
   one with no idea of the size of it). Then one item, until the queue empties.
   Then what actually happened - reviewed, still due - with no score, no
   streak and no mastery invented for the occasion. */
async function renderRecallLanguage(root, ctx) {
  const { api, c, language, alive, memory } = ctx;
  /* The queue is what is due, asked for as what is due and in that order. A
     learner with ten thousand saved words reviews the same handful today as a
     learner with fifty, so the room reads a page of them, not a library. */
  const data = await api.libraryVocabulary({ status: 'due', order: 'due', limit: RECALL_QUEUE });
  if (!alive()) return;
  let items = data.items || [],
    revealed = false,
    reviewed = 0,
    stage = 'landing';
  /* What the summary is made of, all of it measured here: when the sitting
     started, how each card was graded, and which ones were forgotten - with
     enough of each to say where it came from. */
  /* What can be heard, by word: `null` while the answer is outstanding, the
     record when there is a clip, `false` when there is none. The frame draws
     the pill on a card whose word has a recording; a pill that played nothing
     would be worse than no pill, so one is drawn only once the answer is in
     (recorded in UI_BACKEND_GAPS.md). */
  const heard = new Map();
  let playing = null;
  /* How this learner wants to be asked, and where this card has got to in
     answering. `taskState` is cleared with the card, never carried across one:
     a wrong answer belongs to the word it was given for. */
  let settings = readReviewSettings(memory.value.reviewSettings);
  let settingsOpen = false;
  let task = null;
  let taskWord = '';
  let taskState = null;
  let recorded = null;
  /* Answers given with no network. The frame says they are kept on the device
     and sync when there is a connection, and draws how many are waiting. */
  let waiting = [...(memory.value.reviewQueue || [])];
  let offline = typeof navigator !== 'undefined' && navigator.onLine === false;

  /* One place every grade goes, whether the learner gave it to a flashcard or
     to one of the four task cards. When it cannot reach the server it waits
     rather than being lost, and the next connection sends it. */
  const record = async (word, grade) => {
    try {
      await ctx.mutate(() => api.reviewLibraryVocabulary(word, grade));
      return true;
    } catch (error) {
      if (!worthKeeping(error)) throw error;
      waiting = withWaiting(waiting, word, grade, new Date().toISOString());
      memory.setReviewQueue(waiting);
      offline = true;
      return false;
    }
  };

  const drain = async () => {
    if (!waiting.length) return;
    const left = await flushQueue(waiting, (item) =>
      ctx.mutate(() => api.reviewLibraryVocabulary(item.word, item.grade)),
    );
    if (!alive()) return;
    waiting = left;
    memory.setReviewQueue(waiting);
    paint(false);
  };

  if (typeof window !== 'undefined') {
    window.addEventListener('online', () => {
      offline = false;
      if (alive()) drain();
    });
    window.addEventListener('offline', () => {
      offline = true;
      if (alive()) paint(false);
    });
  }

  const freshTask = (item) => {
    const hasAudio = Boolean(heard.get(item.word));
    const pool = (items || []).filter((other) => other.word !== item.word);
    const mode = taskFor({ ...item, language }, settings, { hasAudio, pool });
    const options =
      mode === 'listen_choose'
        ? choicesFor(item, pool)
        : mode === 'cloze'
          ? choicesFor(
              { ...item, definition: item.word },
              pool.map((other) => ({ ...other, definition: other.word })),
            )
          : [];
    return { mode, state: { typed: '', tries: 0, verdict: null, chosen: -1, options, attempts: [], speed: 1 } };
  };

  /* The card decides how it is asked once, when it comes up. Deciding again on
     every paint would change the question under a learner mid-answer. */
  const ensureTask = (item) => {
    if (!item) {
      task = null;
      taskWord = '';
      taskState = null;
      return;
    }
    if (taskWord === item.word && task) return;
    const fresh = freshTask(item);
    task = fresh.mode;
    taskWord = item.word;
    taskState = fresh.state;
    recorded = null;
  };

  /* What a task answer is worth. The scheduler takes three answers, and the
     product's rule is the plain one: right first time is remembering it, right
     on the second try is being unsure of it, and not getting there is
     forgetting it. */
  const gradeFor = (state, ok) => (!ok ? 'again' : state.tries <= 1 ? 'got_it' : 'unsure');
  let startedAt = 0;
  const tally = { got_it: 0, unsure: 0, again: 0 };
  const forgotten = [];
  let counts = null;
  drain();

  function paint(moveFocus = false) {
    if (!alive()) return;
    const due = items.filter((x) => x.due),
      current = due[0];
    /* The question worth asking depends on how this phrase entered the
       learner's life, which their own saving already recorded. */
    const keptNow = current ? memory.value.keptLanguage?.[current.word] : null;
    const shape = current ? recallShape(current, keptNow) : 'meaning';
    const gap = current ? blankContext(current.source_fragment, current.word) : null;
    /* The sentence a phrase was met in is the best scaffold retrieval has, so
       it is shown rather than hidden - but with the phrase itself withheld at
       every occurrence until the learner commits. Printing it whole is how a
       recall task quietly becomes a reading task. */
    const withheld = (marker) =>
      gap.segments
        .map((part) => esc(part))
        .join(`<b>${marker}</b>`);
    /* The approved review session: what is due and how far through it the
       learner is, the word itself, and - once they have committed - how well
       they knew it. The scheduler accepts two answers, so Hard and Easy keep
       their place in the approved panel and say they are not available yet
       (GAP-019); no interval is printed, because nothing previews one. */
    const r = referenceCopy[ctx.ui] || referenceCopy.en;
    const passed = Math.min(reviewed, reviewed + due.length);
    const total = reviewed + due.length;

    /* The bar the source draws over the card: the way back, one segment per
       card in this sitting, and how far through it the learner is. */
    const rail = `<div class="vocab-review__rail" aria-hidden="true">${Array.from(
      { length: Math.min(total, 12) },
      (_, position) => `<span class="vocab-review__step"${position < passed ? ' data-tone="done"' : ''}></span>`,
    ).join('')}</div>`;

    /* Three diamonds for how well this word is held, from the same review
       stage every other surface counts. */
    const mastery = (item) => {
      const held = Math.max(0, Math.min(3, Math.round((Number(item.review_stage) || 0) * 3 / 4)));
      return `<span class="vocab-card__mastery" aria-hidden="true">${
        [0, 1, 2].map((index) => `<span class="vocab-card__gem"${index < held ? ' data-earned="true"' : ''}></span>`).join('')
      }</span>`;
    };

    /* What each grade will do, taken from the scheduler that will do it - the
       card carries its own intervals, so nothing here is a written-in number
       (D-066 rule 4). */
    const when = (plan) => {
      if (!plan) return '';
      if (plan.minutes) return `${plan.minutes}m`;
      if (plan.days) return `${plan.days}d`;
      return '';
    };
    const grade = (key, label, tone) => {
      const plan = current?.schedule?.[key];
      return `<button type="button" class="vocab-grade" data-tone="${tone}" data-grade="${key}">`
        + `<span class="vocab-grade__label">${esc(label)}</span>`
        + `<span class="vocab-grade__when ds-data">${esc(when(plan))}</span>`
        + `</button>`;
    };
    const grades = `<div class="vocab-grades">`
      + grade('again', r.vocabGradeAgain, 'again')
      + grade('unsure', r.vocabGradeUnsure, 'unsure')
      + grade('got_it', r.vocabGradeGotIt, 'got')
      + `</div>`;

    /* The card itself. Opened, it carries the word, its reading, the meaning
       and the sentence it was met in; closed, the word alone and the way in.
       The question the learner is asked still depends on how the word entered
       their life - the product's rule, which this composition keeps. */
    const front = shape === 'in_context' && gap
      ? `<blockquote class="vocab-card__context" lang="${language}">${withheld('&nbsp;'.repeat(3))}</blockquote>`
      : `<span class="vocab-card__word" lang="${language}">${esc(shape === 'say' ? '···' : current?.word || '')}</span>`
        + (shape === 'say' ? `<span class="vocab-card__meaning" lang="${esc(ctx.support)}">${esc(current?.definition || current?.translation_vi || '')}</span>` : '');
    const back = `<span class="vocab-card__word" lang="${language}">${esc(current?.word || '')}</span>`
      + (current?.phonetic && (language !== 'zh' || ctx.profile.pinyin !== 'off')
        ? `<span class="vocab-card__reading ds-data">${esc(current.phonetic)}</span>`
        : '')
      + `<span class="vocab-card__rule" aria-hidden="true"></span>`
      + `<span class="vocab-card__meaning" lang="${esc(ctx.support)}">${esc(current?.definition || current?.translation_vi || '')}</span>`
      + (current?.source_fragment
        ? `<span class="vocab-card__example" lang="${language}">${esc(current.source_fragment)}</span>`
        : '')
      /* Where the word was met, said after the learner has committed and not
         before - the product's rule about a kept word keeping its source. The
         frame draws the sentence but not its title; this line is the
         difference, recorded in UI_BACKEND_GAPS.md. */
      + (current?.focus_note ? `<span class="recall-where">${esc(current.focus_note)}</span>` : '');
    /* "Nghe phát âm", as the frame draws it: a pill under the word, carrying
       the speaker. It is inside the card's own button, so it stops the flip -
       hearing a word is not answering it. The attribution the licence obliges
       travels on the control itself; where it should be *shown* is a question
       for the human, because the frame draws no place for it
       (UI_BACKEND_GAPS.md). */
    const listen = (item) => {
      const found = item ? heard.get(item.word) : null;
      if (!found) return '';
      const label = playing === item.word ? r.vocabListening : r.vocabListen;
      return `<span class="vocab-listen" role="button" tabindex="0" data-listen="${esc(item.word)}"`
        + ` aria-label="${esc(`${label} — ${found.attribution}`)}" title="${esc(found.attribution)}">`
        + `${icon('speaker-high', { filled: true, size: 12 })}<span>${esc(label)}</span></span>`;
    };
    /* The sitting's own notice, not the card's: frame 31 draws it above
       whatever card is up, and a flashcard sitting can be offline too. */
    const offlineNotice = offline
      ? `<div class="recall-offline" role="status">${icon('wifi-slash', { size: 18 })}<span>${esc(c.recallOffline)}</span></div>`
      : '';
    const waitingLine = waiting.length
      ? `<p class="recall-waiting ds-data">${esc(String(c.recallWaiting).replace('{n}', String(waiting.length)))}</p>`
      : '';
    const card = current
      ? `<section class="vocab-review">`
        + `<header class="vocab-review__bar">`
        + `<a class="vocab-review__back" href="${esc(link('language'))}" aria-label="${esc(c.back)}">${icon('caret-left', { size: 22 })}</a>`
        + rail
        + `<span class="vocab-review__count ds-data">${esc(passed)} / ${esc(total)}</span>`
        + `</header>`
        + offlineNotice
        + `<div class="vocab-review__stage">`
        + `<button type="button" class="vocab-card" data-flip aria-pressed="${revealed}" data-state="${revealed ? 'open' : 'closed'}" data-shape="${shape}">`
        + mastery(current)
        + `<span class="vocab-card__body"><small class="vocab-card__ask">${esc(c[`recallAsk_${shape}`])}</small>${revealed ? back : front}</span>`
        + listen(current)
        + `<span class="vocab-card__flip">${esc(revealed ? r.vocabFlipBack : r.vocabFlipOpen)}</span>`
        + `</button>`
        + (revealed ? grades : `<p class="vocab-review__hint">${esc(r.vocabGradesAfterOpen)}</p>`)
        + waitingLine
        + `<p role="status" data-recall-status></p>`
        + `</div>`
        + `</section>`
      : '';
    /* What is waiting, before the first card. The source opens straight on the
       card; this step is the product's, and it is kept because a learner
       dropped into card one has no idea whether this is three words or thirty
       (pinned by test_orena_language_and_recall.mjs). Recorded for the human
       in UI_BACKEND_GAPS.md as a difference from the frame. */
    const landing = due.length
      ? `<section class="recall-landing"><small>${esc(c.vocabularyDueState)}</small><h2>${due.length} ${esc(c.vocabularyWordCount)}</h2><p>${esc(due.slice(0, 3).map((x) => x.word).join(' · '))}${due.length > 3 ? ' …' : ''}</p><button class="primary" data-recall-start>${esc(c.recallName)} →</button></section>`
      : `<section class="empty">${scene('completion', { size: 'medium' })}<h2>${c.allDone}</h2><p>${esc(c.allDoneNote)}</p><a class="outline" href="${link('language')}">${c.language} →</a></section>${continuationShelf(ctx, 3)}`;
    /* The session's own account of itself (D-067, "Review summary"): how long
       it took and how many cards, the three grades as a bar and as figures,
       what was forgotten - each with where it came from - and what comes back
       next. Every number here was measured in this sitting or counted by the
       database; none of it is a score. */
    const minutes = startedAt ? Math.max(0, Math.round((Date.now() - startedAt) / 1000)) : 0;
    const spent = minutes >= 60
      ? String(r.reviewSpentMinutes).replace('{m}', String(Math.floor(minutes / 60))).replace('{s}', String(minutes % 60))
      : String(r.reviewSpentSeconds).replace('{s}', String(minutes));
    const graded = tally.got_it + tally.unsure + tally.again;
    const figure = (key, tone) =>
      `<div class="review-done__figure" data-tone="${tone}"><strong>${esc(tally[key])}</strong>`
      + `<span>${esc(key === 'got_it' ? r.vocabGradeGotIt : key === 'unsure' ? r.vocabGradeUnsure : r.vocabGradeAgain)}</span></div>`;
    const bar = graded
      ? `<div class="review-done__bar" aria-hidden="true">`
        + `<span data-tone="got" style="flex:${tally.got_it}"></span>`
        + `<span data-tone="unsure" style="flex:${tally.unsure}"></span>`
        + `<span data-tone="again" style="flex:${tally.again}"></span>`
        + `</div>`
      : '';
    const forgottenRows = forgotten.length
      ? `<section class="review-done__block"><span class="ds-label">${esc(r.reviewForgotHere)}</span>`
        + `<div class="review-done__list">${forgotten.map((item) => `<div class="review-done__row">`
          + `<span class="review-done__word" lang="${esc(language)}">${esc(item.word)}</span>`
          + `<span class="review-done__gloss" lang="${esc(ctx.support)}">${esc(item.meaning)}</span>`
          + `<span class="review-done__from">${esc(item.from)}</span>`
          + `</div>`).join('')}</div></section>`
      : '';
    const nextLine = counts
      ? String(r.reviewNextDay)
        .replace('{n}', String(Number(counts.summary?.due_next_day || 0)))
        .replace('{w}', esc(c.vocabularyWordCount))
      : '';
    const done = `<section class="review-done">`
      + `<div class="review-done__head">`
      + `<span class="ds-label">${esc(String(r.reviewSession).replace('{t}', spent))}</span>`
      + `<h2>${esc(String(r.reviewFinished).replace('{n}', String(reviewed)))}</h2>`
      + `</div>`
      + (graded ? `<div class="review-done__scores">${bar}<div class="review-done__figures">${figure('got_it', 'got')}${figure('unsure', 'unsure')}${figure('again', 'again')}</div></div>` : '')
      + forgottenRows
      + `<div class="review-done__foot">`
      + (nextLine ? `<span class="review-done__next">${esc(nextLine)}</span>` : '')
      + (tally.again ? `<button type="button" class="outline" data-recall-again>${esc(String(r.reviewAgainAll).replace('{n}', String(tally.again)))}</button>` : '')
      + `<a class="primary" href="${esc(link('language'))}">${esc(r.reviewDone)}</a>`
      + `</div>`
      + `</section>`;
    /* The four task frames draw their own shell: a way out of the sitting, one
       continuous bar rather than a segment per card, the count, and - on the
       desktop frame - the way to the settings. The flashcard keeps its own
       (frames 08-10), so neither is bent to fit the other. */
    ensureTask(current);
    const asked = current && task && task !== 'flashcard' ? task : '';
    const walked = total ? Math.round((passed / total) * 100) : 0;
    const taskShell = asked
      ? `<section class="recall-run">`
        + `<header class="recall-run__bar">`
        + `<a class="recall-run__leave" href="${esc(link('language'))}" aria-label="${esc(c.back)}">${icon('x', { size: 21 })}</a>`
        + `<span class="recall-run__track"><span style="width:${walked}%"></span></span>`
        + `<span class="recall-run__count ds-data">${esc(passed)} / ${esc(total)}</span>`
        + `<button type="button" class="icon-button recall-run__settings" data-recall-settings aria-label="${esc(c.recallSettings)}">${icon('sliders-horizontal', { size: 20 })}</button>`
        + `</header>`
        + offlineNotice
        + `<div class="recall-run__stage">${taskCard(c, asked, { ...current, language }, taskState)}</div>`
        + taskFoot(c, asked, taskState, recorded)
        + waitingLine
        + `<p role="status" data-recall-status></p>`
        + `</section>`
      : '';
    /* The sheet outlives the card it was opened from: turning a mode off can
       change what this card is asked, and the learner must not lose the sheet
       they are still setting. */
    const sheet = settingsOpen
      ? reviewSettingsSheet(c, settings, { newPerDay: NEW_PER_DAY, limitPerDay: REVIEW_LIMIT })
      : '';
    const reviewing = stage !== 'landing' && current;
    /* While a card is up the screen is the card, and when the sitting ends the
       screen is its summary: both carry their own way on, so the room's return
       link and the page intro stay out of them. */
    const sitting = reviewing || (stage !== 'landing' && !current);
    root.innerHTML = `${sitting ? '' : practiceReturn(c, 'recall')}${
      sitting ? '' : pageIntro({ title: c.recallTitle, note: c.recallTruth, eyebrow: c.recallName, compact: true })
    }${stage === 'landing' ? landing : current ? taskShell || card : done}${sheet}`;
    /* Asked once per word, when its card is on screen: the answer is cached
       on the server by (entry identity, reading), so a second sitting with the
       same word costs nothing. A word with no catalogue identity, or one whose
       reading is still ambiguous, answers "not available" and no pill is
       drawn - which is the audio rule, seen from the room. */
    if (current && !heard.has(current.word)) {
      heard.set(current.word, null);
      api.wordAudio(current.word, current.reading_key || '')
        .then((answer) => {
          if (!alive()) return;
          heard.set(current.word, answer?.available ? answer : false);
          if (answer?.available) paint(false);
        })
        .catch(() => { if (alive()) heard.set(current.word, false); });
    }
    root.querySelector('[data-recall-start]')?.addEventListener('click', () => {
      stage = 'card';
      revealed = false;
      startedAt = Date.now();
      tally.got_it = 0;
      tally.unsure = 0;
      tally.again = 0;
      forgotten.length = 0;
      paint(true);
    });
    /* "Review the ones you forgot" is the same queue again: the cards graded
       `again` are due in ten minutes, so the room asks for what is due and
       carries on. */
    root.querySelector('[data-recall-again]')?.addEventListener('click', async () => {
      try {
        const again = await api.libraryVocabulary({ status: 'due', order: 'due', limit: RECALL_QUEUE });
        if (!alive()) return;
        items = again.items || [];
        revealed = false;
        stage = 'card';
        startedAt = Date.now();
        paint(true);
      } catch {
        /* Nothing to say here that the next paint will not say. */
      }
    });
    root.querySelectorAll('[data-grade]').forEach(
      (button) =>
        (button.onclick = async () => {
          root
            .querySelectorAll('[data-grade]')
            .forEach((x) => (x.disabled = true));
          const report = progressReporter(
            root.querySelector('[data-recall-status]'),
            ctx,
            alive,
          );
          report.saving();
          const answer = button.dataset.grade;
          /* The same one place every grade goes: with no network it waits on
             the device rather than being lost. */
          const grade = () => record(current.word, answer);
          try {
            await grade();
          } catch {
            report.failed(c.failedSave, () => button.onclick());
            if (alive())
              root
                .querySelectorAll('[data-grade]')
                .forEach((x) => (x.disabled = false));
            return;
          }
          // The grade is already recorded. If only the refresh fails, say that
          // rather than telling the learner their answer was lost, and let the
          // retry fetch the list again instead of re-submitting the grade.
          const refresh = async () => {
            try {
              const [updated, totals] = await Promise.all([
                api.libraryVocabulary({ status: 'due', order: 'due', limit: RECALL_QUEUE }),
                api.libraryVocabularySummary().catch(() => null),
              ]);
              if (!alive()) return;
              /* Recorded once the grade is saved, so the summary can only ever
                 describe what really happened. */
              if (answer in tally) tally[answer] += 1;
              if (answer === 'again' && !forgotten.some((item) => item.word === current.word)) {
                forgotten.push({
                  word: current.word,
                  meaning: current.definition || current.translation_vi || '',
                  from: current.focus_note || (current.source_kind ? c[`saved_${current.source_kind}`] || '' : ''),
                });
              }
              items = updated.items || [];
              counts = totals;
              revealed = false;
              reviewed += 1;
              paint(true);
              status(c.persisted);
            } catch {
              report.failed(c.savedNotRefreshed, refresh);
            }
          };
          await refresh();
        }),
    );
    root.querySelectorAll('[data-listen]').forEach((control) => {
      const play = async (event) => {
        /* Inside the card's button: hearing a word must not flip it. */
        event.preventDefault();
        event.stopPropagation();
        const word = control.dataset.listen;
        const found = heard.get(word);
        if (!found) return;
        playing = word;
        paint(false);
        try {
          const sound = new Audio(found.url);
          await sound.play();
          sound.addEventListener('ended', () => { playing = null; if (alive()) paint(false); }, { once: true });
        } catch {
          playing = null;
          if (alive()) paint(false);
        }
      };
      control.addEventListener('click', play);
      control.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') play(event);
      });
    });
    /* The four task modes. Every answer goes through one place, so what a
       task is worth cannot drift between modes. */
    const settle = async (ok) => {
      taskState.verdict = { ok };
      const answer = gradeFor(taskState, ok);
      recorded = {
        tone: answer === 'got_it' ? 'got' : answer === 'unsure' ? 'unsure' : 'again',
        label: answer === 'got_it' ? r.vocabGradeGotIt : answer === 'unsure' ? r.vocabGradeUnsure : r.vocabGradeAgain,
        when: (() => {
          const plan = current?.schedule?.[answer];
          if (!plan) return '';
          if (plan.minutes) return `${plan.minutes}m`;
          if (plan.days) return `${plan.days}d`;
          return '';
        })(),
      };
      paint(false);
      try {
        await record(current.word, answer);
        if (!alive()) return;
        if (answer in tally) tally[answer] += 1;
        if (answer === 'again' && !forgotten.some((item) => item.word === current.word))
          forgotten.push({
            word: current.word,
            meaning: meaningOf(current),
            from: current.focus_note || (current.source_kind ? c[`saved_${current.source_kind}`] || '' : ''),
          });
      } catch {
        /* The next card's read will say what the library really holds. */
      }
    };
    root.querySelector('[data-recall-typed]')?.addEventListener('input', (event) => {
      taskState.typed = event.target.value;
      const on = root.querySelector('[data-recall-check]');
      if (on) on.disabled = !taskState.typed.trim();
    });
    root.querySelector('[data-recall-typed]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') root.querySelector('[data-recall-check]')?.click();
    });
    root.querySelector('[data-recall-check]')?.addEventListener('click', async () => {
      if (!taskState || taskState.verdict) return;
      taskState.tries += 1;
      if (asked === 'cloze') {
        await settle(taskState.options[taskState.chosen] === current.word);
        return;
      }
      const expected = asked === 'dictation' ? current.word : meaningOf(current);
      const judged = checkTyped(taskState.typed, expected);
      if (judged.ok) {
        taskState.verdict = { ok: true, foldedOnly: judged.foldedOnly };
        await settle(true);
        return;
      }
      if (taskState.tries < TYPING_TRIES) {
        /* Another go: what was typed is kept where the learner can see it was
           not right, and the field is theirs again. */
        if (asked === 'dictation') taskState.attempts.push(taskState.typed);
        taskState.verdict = { ok: false };
        paint(false);
        taskState.verdict = null;
        taskState.typed = '';
        window.setTimeout(() => { if (alive()) paint(false); }, 900);
        return;
      }
      if (asked === 'dictation') taskState.attempts.push(taskState.typed);
      await settle(false);
    });
    root.querySelectorAll('[data-recall-choose]').forEach((button) => {
      button.onclick = async () => {
        if (!taskState || taskState.verdict) return;
        taskState.chosen = Number(button.dataset.recallChoose);
        if (asked === 'cloze') { paint(false); return; }
        taskState.tries += 1;
        await settle(taskState.options[taskState.chosen] === meaningOf(current));
      };
    });
    root.querySelector('[data-recall-unknown]')?.addEventListener('click', async () => {
      if (!taskState || taskState.verdict) return;
      taskState.tries = TYPING_TRIES + 1;
      if (asked === 'dictation' && taskState.typed) taskState.attempts.push(taskState.typed);
      await settle(false);
    });
    root.querySelector('[data-recall-next]')?.addEventListener('click', async () => {
      try {
        const [updated, totals] = await Promise.all([
          api.libraryVocabulary({ status: 'due', order: 'due', limit: RECALL_QUEUE }),
          api.libraryVocabularySummary().catch(() => null),
        ]);
        if (!alive()) return;
        items = updated.items || [];
        counts = totals;
        reviewed += 1;
        task = null;
        taskWord = '';
        taskState = null;
        recorded = null;
        paint(true);
      } catch {
        status(c.savedNotRefreshed);
      }
    });
    root.querySelectorAll('[data-recall-speak]').forEach((button) => {
      button.onclick = async () => {
        const found = heard.get(current?.word);
        if (!found) return;
        try {
          const sound = new Audio(found.url);
          sound.playbackRate = taskState?.speed || 1;
          await sound.play();
        } catch {
          /* A recording that will not play is not an answer the learner owes. */
        }
      };
    });
    root.querySelector('[data-recall-speed]')?.addEventListener('click', () => {
      taskState.speed = taskState.speed === 1 ? 0.75 : 1;
      paint(false);
    });
    /* The settings sheet: read, changed one at a time, written whole. */
    root.querySelector('[data-recall-settings]')?.addEventListener('click', () => {
      settingsOpen = true;
      paint(false);
    });
    root.querySelector('[data-recall-settings-close]')?.addEventListener('click', () => {
      settingsOpen = false;
      paint(false);
    });
    root.querySelectorAll('[data-recall-setting]').forEach((input) => {
      input.oninput = () => {
        settings = readReviewSettings({ ...settings, [input.dataset.recallSetting]: input.value });
        memory.setReview(settings);
        paint(false);
      };
    });
    root.querySelectorAll('[data-recall-mode]').forEach((button) => {
      button.onclick = () => {
        const name = button.dataset.recallMode;
        settings = readReviewSettings({
          ...settings,
          modes: { ...settings.modes, [name]: !settings.modes[name] },
        });
        memory.setReview(settings);
        /* A mode turned on or off changes which question this card is set, so
           the card is asked again from the start rather than half in one mode
           and half in another. */
        task = null;
        taskWord = '';
        taskState = null;
        paint(false);
      };
    });
    root.querySelector('[data-flip]')?.addEventListener('click', () => {
      revealed = !revealed;
      paint(true);
    });
    if (moveFocus)
      focusRegion(root.querySelector('.vocab-card, .empty h2'));
  }
  paint();
}
function vocabularyCopy(c, supportLanguage) {
  return {
    ...c,
    supportLanguage,
    save: c.vocabularySave,
    saved: c.vocabularySaved,
    study: c.vocabularyStudy,
    open: c.vocabularyOpen,
    flip: c.vocabularyFlip,
    know: (referenceCopy[supportLanguage] || referenceCopy.en).vocabKnow,
    front: c.vocabularyRecall,
    back: c.vocabularyLearn,
    vocabularyFeedSoundOn: c.vocabularyFeedSoundOn,
    vocabularyFeedSoundOff: c.vocabularyFeedSoundOff,
    audio: c.vocabularyAudio,
    review: c.vocabularyReview,
    example: c.vocabularyExample,
    usage: c.vocabularyUsage,
    orthography: c.vocabularyOrthography,
    strokes: c.vocabularyStrokes,
    newWord: c.vocabularyNew,
    learning: c.vocabularyLearningState,
    due: c.vocabularyDueState,
    mastered: c.vocabularyMasteredState,
    words: c.vocabularyWordCount,
  };
}

function vocabularyCardFromSavedItem(item, language, supportLanguage, pinyinAllowed) {
  const card = vocabularyCardFromLibraryItem(item, language, { pinyinAllowed });
  card.saved = true;
  card.review_stage = Number(item.review_stage) || 0;
  card.due = Boolean(item.due);
  card.successful_recalls = Number(item.successful_recalls) || 0;
  card.lapse_count = Number(item.lapse_count) || 0;
  card.support_language = supportLanguage;
  return card;
}

function vocabularyStatusMatches(card, filter) {
  if (filter === 'all') return true;
  if (filter === 'saved') return Boolean(card.saved);
  return vocabularyStatus(card) === filter;
}

function vocabularyLevelOrder(level) {
  const normalized = String(level || '').toUpperCase().replace(/[–—]/g, '-').replace(/\s+/g, '');
  if (normalized === 'HSK7-9') return 7;
  const match = normalized.match(/^(?:HSK)?([1-6])$/);
  if (match) return Number(match[1]);
  return { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 }[normalized] || 0;
}

export function vocabularyInteractionItems(view, { visibleItems = [], savedCards = [], studyItems = [] } = {}) {
  if (view === 'collection' || view === 'collection-list') return visibleItems;
  if (view === 'overview') return savedCards;
  if (view === 'study') return studyItems;
  return [];
}

export async function renderLanguage(root, ctx) {
  if (ctx.location.intent === 'recall') return renderRecallLanguage(root, ctx);
  const { api, c, language, support, alive, memory } = ctx;
  const copy = vocabularyCopy(c, support);
  const pinyinAllowed = language !== 'zh' || ctx.profile.pinyin !== 'off';
  const results = await Promise.allSettled([
    api.libraryVocabulary({ limit: SAVED_PAGE, order: 'recent' }),
    api.vocabularyLibraryCollections(language),
  ]);
  if (!alive()) return;

  let savedData = results[0].status === 'fulfilled' ? results[0].value : { items: [], summary: {} };
  let collections = results[1].status === 'fulfilled' ? results[1].value.items || [] : [];
  const savedError = results[0].status === 'rejected';
  const collectionError = results[1].status === 'rejected';
  let savedCards = [];
  let view = 'overview';
  let returnView = 'overview';
  let activeCollection = null;
  let activeItems = [];
  let visibleItems = [];
  let studyItems = [];
  let studyIndex = 0;
  let query = '';
  let filter = 'all';
  let levelFilter = 'all';
  let sort = 'recommended';
  let notMastered = false;
  let collectionSearchTimer = null;
  let collectionRequest = 0;
  /* Which chip the library is filtered by: 'all', 'published', or a
     language code the catalogue actually holds. */
  let packFilter = 'all';
  /* Why a set would not open, so its own screen can say so and offer the way
     back in - frame 32 draws the code, because a learner reporting a problem
     can quote it. */
  let collectionFailed = null;
  let deckSettingsOpen = false;
  /* The learner's own review settings, read where the review session reads
     them: how many new cards a day is what "learn some new ones" means. */
  let settings = readReviewSettings(memory.value.reviewSettings);
  /* A pass over a set that is not counted - "không tính lịch". The cards are
     the set's; nothing is written to the schedule. */
  let practiceOnly = false;
  /* The learner's study sets: Vocabulary's own, not My Library's collections
     (the human's decision of 2026-09-23 - the two are different domains).
     `decksUnavailable` is true while the Deck tables are still a proposal,
     and the screens say so rather than quietly filing words elsewhere. */
  let decks = [];
  let deckCovers = [];
  let decksUnavailable = false;
  /* The room's own search: what was typed, which chip is on, and the two
     lists. Both halves are read from the server - the learner's words by the
     read that already pages them, the catalogue by its own bounded search -
     so the browser never holds either of them whole. */
  let searching = null;
  let searchTimer = null;
  let searchRequest = 0;
  let decksRead = false;
  let adding = null;
  let deckSheet = null;
  let newDeck = null;

  /* A kept word into one of the learner's sets. The word is kept first, so
     what is filed is the library item that keeping made - there is no second
     record of the word anywhere. */
  /* A word the learner has, into one of their sets. The word is saved first,
     so a failure to file never leaves it half-kept - and the set stores a
     reference, never a copy. */
  const fileWord = async (word, deckId) => {
    try {
      await ctx.mutate(() => api.vocabularyDeckAdd(deckId, word));
      return true;
    } catch {
      return false;
    }
  };

  const SEARCH_DEBOUNCE_MS = 220;
  const SEARCH_LIMIT = 20;

  const runSearch = async () => {
    const wanted = (searching?.query || '').trim();
    const token = (searchRequest += 1);
    if (!wanted) {
      searching = { ...searching, saved: [], catalogue: [], savedTotal: 0, busy: false };
      paint();
      return;
    }
    searching.busy = true;
    paint();
    const [mine, catalogue] = await Promise.all([
      api.libraryVocabulary({ query: wanted, limit: SEARCH_LIMIT }).catch(() => null),
      api.vocabularyCatalogueSearch(wanted, language, SEARCH_LIMIT).catch(() => null),
    ]);
    if (!alive() || token !== searchRequest) return;
    searching = {
      ...searching,
      saved: mine?.items || [],
      savedTotal: Number(mine?.total || (mine?.items || []).length),
      catalogue: catalogue?.items || [],
      busy: false,
    };
    paint();
  };

  const readDecks = async () => {
    if (decksRead) return decks;
    try {
      const answer = await api.vocabularyDecks();
      decks = answer.items || [];
      deckCovers = answer.covers || [];
      decksUnavailable = false;
    } catch (error) {
      decks = [];
      /* 503 is "this server has no study sets yet", which is a different
         thing from "you have none" and is said differently. */
      decksUnavailable = Number(error?.status || 0) === 503;
    }
    decksRead = true;
    return decks;
  };

  /* The languages a new set may be in: the ones this account actually learns,
     named in the interface's own language. */
  const deckLanguages = () => [{ code: language, label: c[`language_${language}`] || language.toUpperCase() }];
  /* One word, opened all the way: which word, what came back, and which of the
     two pages the phone is on. `deepReturn` is the view to go back to, so a
     word opened from a review card returns to that card rather than to the
     room's front. */
  let deepWord = '';
  let deepData = null;
  let deepState = 'ready';
  let deepPage = 'meaning';
  let deepReturn = 'overview';
  let deepRequest = 0;
  /* The word heard where it is said. `sound` is the one element playing, so a
     second clip cannot start over the first. */
  let clipState = null;
  let sound = null;
  /* Nét chữ. `strokeState.at` is which stroke is being traced, and `points`
     is the one the learner is drawing now, in the glyph's own coordinates. */
  let strokeState = null;
  let strokeTimer = null;
  let points = [];

  const refreshSavedCards = () => {
    savedCards = (savedData.items || []).map((item) =>
      vocabularyCardFromSavedItem(item, language, support, pinyinAllowed),
    );
  };
  refreshSavedCards();

  async function openWordDeep(word) {
    const wanted = String(word || '').trim();
    if (!wanted) return;
    const token = (deepRequest += 1);
    if (view !== 'deep') deepReturn = view;
    deepWord = wanted;
    deepData = null;
    deepState = 'loading';
    deepPage = 'meaning';
    view = 'deep';
    document.addEventListener('keydown', deepKeys);
    paint();
    try {
      const [data, clips] = await Promise.all([
        api.wordDeep(wanted),
        api.wordClips(wanted).catch(() => null),
      ]);
      if (!alive() || token !== deepRequest) return;
      deepData = { ...data, language, clipCount: Number(clips?.total || 0) };
      deepState = 'ready';
    } catch {
      if (!alive() || token !== deepRequest) return;
      deepState = 'failed';
    }
    paint();
  }

  const stopClip = () => {
    if (!sound) return;
    sound.pause();
    sound = null;
  };

  /* Play exactly the moment the clip is, and stop at its end - the segment is
     what the learner asked to hear, not the lesson it sits in. */
  const playClip = () => {
    const clip = clipState?.clips?.[clipState.at];
    if (!clip?.url || clip.kind === 'embed') return;
    stopClip();
    sound = new Audio(clip.url);
    sound.playbackRate = clipState.speed || 1;
    sound.currentTime = (Number(clip.startMs) || 0) / 1000;
    const stopAtEnd = () => {
      if (sound && sound.currentTime * 1000 >= (Number(clip.endMs) || 0)) {
        stopClip();
        clipState.playing = false;
        if (alive()) paint();
      }
    };
    sound.addEventListener('timeupdate', stopAtEnd);
    sound
      .play()
      .then(() => {
        clipState.playing = true;
        if (alive()) paint();
      })
      .catch(() => {
        clipState.playing = false;
        if (alive()) paint();
      });
  };

  async function openWordClips(word) {
    const wanted = String(word || '').trim();
    if (!wanted) return;
    returnView = view;
    clipState = { word: wanted, reading: deepData?.reading || '', clips: [], at: 0, playing: false, speed: 1, busy: true };
    view = 'clips';
    paint();
    try {
      const answer = await api.wordClips(wanted);
      if (!alive()) return;
      clipState = { ...clipState, clips: answer.clips || [], busy: false };
    } catch {
      if (!alive()) return;
      clipState = { ...clipState, busy: false };
    }
    paint();
  }

  const stopStrokes = () => {
    window.clearInterval(strokeTimer);
    strokeTimer = null;
  };

  /* Watching it written: one stroke appears at a time, slowly, which is what
     the frame says under the button. */
  const watchStrokes = () => {
    const total = Number(strokeState?.character?.stroke_count) || 0;
    if (!total) return;
    stopStrokes();
    strokeState.tracing = false;
    strokeState.at = 0;
    strokeState.playing = true;
    paint();
    strokeTimer = window.setInterval(() => {
      if (!alive() || !strokeState) return stopStrokes();
      strokeState.at += 1;
      if (strokeState.at >= total) {
        stopStrokes();
        strokeState.playing = false;
        strokeState.at = total;
      }
      paint();
    }, 700);
  };

  async function openWordStrokes(word) {
    const wanted = String(word || '').trim();
    if (!wanted) return;
    returnView = view;
    strokeState = { word: wanted, character: null, at: 0, playing: false, tracing: false, wrong: false, busy: true };
    view = 'strokes';
    paint();
    try {
      const answer = await api.chineseStrokeOrder(wanted);
      if (!alive()) return;
      /* One character at a time: the frame is a character's strokes, and a
         two-character word opens on its first. */
      const first = (answer.characters || [])[0];
      strokeState = {
        ...strokeState,
        character: first ? { ...first, glyph_size: answer.glyph_size } : null,
        parts: strokeParts(wanted),
        busy: false,
      };
    } catch {
      if (!alive()) return;
      strokeState = { ...strokeState, busy: false };
    }
    paint();
  }

  /* What a character is made of. The stroke capability does not answer this by
     design, so it comes from the catalogue entry's own orthography facts when
     a curator has supplied them - and the section is simply absent otherwise
     (UI_BACKEND_GAPS.md). */
  const strokeParts = (word) => {
    const character = String(word).slice(0, 1);
    const facts = deepData?.orthography?.parts?.[character] || {};
    const listed = [
      ...(facts.radical ? [{ ...facts.radical.value, role: facts.radical.value?.role || c.strokesRadical }] : []),
      ...((facts.components?.value || []).map((item) => ({
        ...item,
        role: item.role === 'phonetic' ? c.strokesPhonetic : item.role === 'semantic' ? c.strokesSemantic : item.role,
      }))),
    ];
    return listed.filter((item) => item && item.surface);
  };

  const closeWordDeep = () => {
    deepRequest += 1;
    view = deepReturn || 'overview';
    deepWord = '';
    deepData = null;
    document.removeEventListener('keydown', deepKeys);
    paint();
  };

  /* Escape leaves the way the back arrow does, which is what the desktop
     frame's own note asks for. */
  function deepKeys(event) {
    if (event.key !== 'Escape' || view !== 'deep') return;
    event.preventDefault();
    closeWordDeep();
  }

  const summary = () => savedData.summary || {
    saved: savedCards.length,
    learning: savedCards.filter((item) => (Number(item.review_stage) || 0) < 3).length,
    due: savedCards.filter((item) => item.due).length,
    mastered: savedCards.filter((item) => (Number(item.review_stage) || 0) >= 3).length,
  };
  const stateCount = (key) => Number(summary()[key] || 0);
  const cardByWord = (word) => savedCards.find((item) => item.headword.toLowerCase() === String(word).toLowerCase());
  /* How much a learner has kept, said once and quietly.

     This was four large tiles - saved, learning, due, mastered - and it opened
     the room, so the first thing My Language said about somebody's language
     was a count of it. The numbers are real and worth having; they are not
     what the room is about. They sit as one line under the heading, and the
     language itself takes the space. */
  const statusSummary = `<p class="vocabulary-tally">${[
    `${stateCount('saved')} ${esc(c.vocabularySavedCount)}`,
    `${stateCount('learning')} ${esc(c.vocabularyLearningCount)}`,
    `${stateCount('mastered')} ${esc(c.vocabularyMasteredCount)}`,
  ].join(' · ')}</p>`;

  const updateCollectionCards = (items) => items.map((card) => {
    const saved = cardByWord(card.headword);
    return saved ? { ...card, saved: true, review_stage: saved.review_stage, due: saved.due, successful_recalls: saved.successful_recalls, lapse_count: saved.lapse_count } : card;
  });

  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  /* --- Vocabulary, on its own frame (D-067, "Vocabulary library") --------
     The room is the library: the filter chips, then a grid of collections -
     a cover of 290x186 with its progress along the bottom, the name at 18/700
     and one mono line saying what it is. Two rows of the learner's own follow
     it, because the design has no screen for a learner's own set yet (its
     matrix marks "My Content" INCOMPLETE) and their words must stay reachable;
     that difference is recorded in UI_BACKEND_GAPS.md.

     Nothing is manufactured: what is due appears only when something is, and
     an empty catalogue says it is empty rather than drawing placeholder
     covers. */
  const collectionCover = (collection) => {
    /* The frame's own cover material: a dotted field, a lit corner and a
       diagonal fall, hue by collection so two packs never look alike. */
    const hue = [...String(collection.id || collection.title || '')]
      .reduce((total, letter) => (total * 31 + letter.charCodeAt(0)) % 360, 7);
    const progress = Number(collection.progress?.learned_count || 0);
    const total = Number(collection.item_count || 0);
    const percent = total ? Math.max(0, Math.min(100, Math.round((progress / total) * 100))) : 0;
    return `<span class="vocab-cover" style="--cover-hue:${hue}">${
      percent ? `<span class="vocab-cover__progress"><span style="inline-size:${percent}%"></span></span>` : ''
    }</span>`;
  };

  const collectionCard = (collection) => {
    const total = Number(collection.item_count || 0);
    const learned = Number(collection.progress?.learned_count || 0);
    const percent = total ? Math.round((learned / total) * 100) : 0;
    const line = [
      String(collection.language_code || '').toUpperCase(),
      total ? `${total.toLocaleString()} ${c.vocabularyWordCount}` : '',
      percent ? `${percent}%` : '',
    ].filter(Boolean).join(' · ');
    return `<button type="button" class="vocab-pack" data-vocabulary-collection="${esc(collection.id)}">`
      + collectionCover(collection)
      + `<span class="vocab-pack__text"><span class="vocab-pack__name">${esc(collection.title)}</span>`
      + `<span class="vocab-pack__line ds-data">${esc(line)}</span></span>`
      + `</button>`;
  };

  const overview = () => {
    /* The chips the frame draws: everything, the published packs, then one per
       language the catalogue actually holds. A chip for a language with no
       collection would be a filter onto nothing. */
    const languages = [...new Set(collections.map((item) => String(item.language_code || '').toLowerCase()).filter(Boolean))];
    const chip = (id, label) =>
      `<button type="button" class="vocab-chip" data-vocabulary-filter-pack="${esc(id)}" aria-pressed="${packFilter === id}">${esc(label)}</button>`;
    const chips = `<div class="vocab-chips" role="group" aria-label="${esc(c.vocabularyLibraryTitle)}">`
      + chip('all', c.vocabularyFilterAll)
      + chip('published', r.vocabPacksReady)
      + languages.map((code) => chip(code, code === 'zh' ? '中文' : code.toUpperCase())).join('')
      + `</div>`;

    const shown = collections.filter((item) => {
      if (packFilter === 'all' || packFilter === 'published') return true;
      return String(item.language_code || '').toLowerCase() === packFilter;
    });

    const packs = collectionError
      ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-vocabulary-retry="collections">${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
      : shown.length
        ? `<div class="vocab-packs">${shown.map(collectionCard).join('')}</div>`
        : `<div class="state-panel state-panel--empty">${icon('cards', { size: 22 })}<div><strong>${esc(c.vocabularyLibraryEmpty)}</strong></div></div>`;

    /* The frame's body is the chips and the packs, and nothing else: this is
       the shared catalogue a learner takes words from. Their own words are
       Thư viện của tôi's (D-074), which is where the rows that used to sit
       here went - not restyled, removed. */
    /* The head frames 01 and 02 draw and the room did not have: its name, and
       the way into its own search. */
    const head = `<header class="vocab-library__head"><h1>${esc(c.vocabularyTitle)}</h1><button type="button" class="icon-button vocab-library__search" data-search-open aria-label="${esc(c.vocabularySearch)}">${icon('magnifying-glass', { size: 19 })}</button></header>`;
    return `<section class="vocab-library">${head}${chips}${packs}</section>`;
  };

  const libraryView = () => {
    const body = collectionError
      ? `<p class="notice" role="alert">${esc(c.unavailable)} <button data-vocabulary-retry="collections">${esc(c.retry)}</button></p>`
      : collections.length
        ? `<div class="vocabulary-collection-grid vocabulary-collection-grid--full">${collections.map((collection, index) => renderVocabularyCollectionCard(copy, collection, { index })).join('')}</div>`
        : `<p class="meta">${esc(c.vocabularyLibraryEmpty)}</p>`;
    return `${pageIntro({ title: c.vocabularyLibraryTitle, note: c.vocabularyLibraryNote, eyebrow: c.vocabularyTitle, compact: true })}<button class="quiet vocabulary-back" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button><section class="vocabulary-overview-section vocabulary-library-view"><div class="section-head"><div><small>${esc(c.vocabularyLibraryTitle)}</small><h2>${esc(c.vocabularyAllWords)}</h2></div></div>${body}</section>`;
  };

  const management = (title, note = '', withBack = false) => {
    const source = activeItems;
    const collectionLevels = view === 'collection'
      ? [...new Set((activeCollection?.levels || source.map((card) => vocabularyLevel(card))).filter(Boolean))].sort((left, right) => vocabularyLevelOrder(left) - vocabularyLevelOrder(right) || left.localeCompare(right))
      : [];
    const filtered = source.filter((card) => (levelFilter === 'all' || vocabularyLevel(card) === levelFilter) && vocabularyStatusMatches(card, filter) && `${card.headword} ${supportMeaning(card, support)} ${card.level || ''} ${card.framework || ''}`.toLowerCase().includes(query.toLowerCase()));
    /* A level is not something the learner's database holds: it comes from the
       curated catalogue and is attached when a word is read. So level cannot
       be an order the server applies, and ordering the page that happens to be
       loaded by it would tell the learner their whole vocabulary was sorted
       when only part of it was. The option is therefore offered only when
       everything the list claims to cover is actually here, and the sort falls
       back to the one the server did apply until then. */
    const complete = !activeCollection?.pagination?.has_more;
    const applied = sort === 'level' && !complete ? 'recommended' : sort;
    visibleItems = [...filtered].sort((left, right) => {
      if (applied === 'alpha') return String(left.headword).localeCompare(String(right.headword));
      if (applied === 'level') return vocabularyLevelOrder(left.level) - vocabularyLevelOrder(right.level) || String(left.headword).localeCompare(String(right.headword));
      if (applied === 'due') return Number(Boolean(right.due)) - Number(Boolean(left.due)) || String(left.headword).localeCompare(String(right.headword));
      return 0;
    });
    const filterNames = ['all', 'new', 'learning', 'due', 'mastered', 'saved'];
    const filterCopy = { all: 'vocabularyFilterAll', new: 'vocabularyFilterNew', learning: 'vocabularyFilterLearning', due: 'vocabularyFilterDue', mastered: 'vocabularyFilterMastered', saved: 'vocabularyFilterSaved' };
    const filters = filterNames.map((name) => `<button class="vocabulary-filter ${filter === name ? 'is-active' : ''}" data-vocabulary-filter="${name}" aria-pressed="${filter === name}">${esc(c[filterCopy[name]])}</button>`).join('');
    const levelFilters = collectionLevels.length
      ? `<div class="vocabulary-level-filter" role="group" aria-label="${esc(c.vocabularyLevelFilter || c.vocabularyFilter)}"><span class="vocabulary-level-filter__label">${esc(c.vocabularyLevelFilter || c.vocabularyFilter)}</span><div class="vocabulary-filter-row">${[['all', c.vocabularyFilterAll], ...collectionLevels.map((level) => [level, level])].map(([name, label]) => `<button class="vocabulary-filter ${levelFilter === name ? 'is-active' : ''}" data-vocabulary-level-filter="${esc(name)}" aria-pressed="${levelFilter === name}">${esc(label)}</button>`).join('')}</div></div>`
      : '';
    const sortOptions = [['recommended', c.vocabularySortRecommended], ['alpha', c.vocabularySortAlpha], ['level', c.vocabularySortLevel], ['due', c.vocabularySortDue]]
      .map(([value, label]) => `<option value="${value}"${value === 'level' && !complete ? ' disabled' : ''} ${applied === value ? 'selected' : ''}>${esc(label)}</option>`)
      .join('');
    const results = visibleItems.length
      ? view === 'collection'
        ? `<section class="vocabulary-browse-grid">${visibleItems.map((card, index) => renderVocabularyBrowseCard(copy, card, { index, source: 'collection' })).join('')}</section>`
        : `<section class="vocabulary-row-list vocabulary-saved-management">${visibleItems.map((card, index) => renderVocabularyRow(copy, card, { index })).join('')}</section>`
      : `<section class="empty vocabulary-empty"><h2>${esc(c.vocabularyNoMatches)}</h2></section>`;
    const pagination = view === 'collection' && activeCollection?.pagination?.has_more
      ? `<div class="button-row vocabulary-load-more"><button class="outline" data-vocabulary-load-more>${esc(c.vocabularyLoadMore || 'Load more words')}</button></div>`
      : '';
    const collectionProgress = view === 'collection' && activeCollection
      ? (() => { const progress = activeCollection.progress || {}; const learned = Number(progress.learned_count) || 0; const total = Number(activeCollection.item_count) || 0; const percent = total ? Math.round((learned / total) * 100) : 0; return `<section class="vocabulary-collection-detail-progress" aria-label="${esc(c.vocabularyProgress || 'Progress')}"><div><span>${esc(c.vocabularyProgress || 'Progress')}</span><strong>${esc(learned)} / ${esc(total)} ${esc(c.vocabularyWordCount)}</strong></div><div class="vocabulary-progress" aria-hidden="true"><span style="width:${percent}%"></span></div></section>`; })()
      : '';
    return `${pageIntro({ title, note, eyebrow: c.vocabularyTitle, compact: true })}${withBack ? `<button class="quiet vocabulary-back" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button>` : ''}${collectionProgress}<div class="vocabulary-management-toolbar"><label><span class="sr-only">${esc(c.vocabularySearch)}</span><input type="search" data-vocabulary-search value="${esc(query)}" placeholder="${esc(c.vocabularySearch)}"></label><div class="vocabulary-management-options">${levelFilters}<label class="vocabulary-sort-control"><span>${esc(c.vocabularySort)}</span><select data-vocabulary-sort aria-label="${esc(c.vocabularySort)}">${sortOptions}</select></label><div class="vocabulary-filter-row" role="group" aria-label="${esc(c.vocabularyFilter)}">${filters}</div></div></div><p class="meta" role="status">${esc(visibleItems.length)} ${esc(c.vocabularyWordCount)}</p>${results}${pagination}`;
  };

  const studyView = () => {
    const card = studyItems[studyIndex];
    if (!card) return `<section class="empty"><h2>${esc(c.noWords)}</h2></section>`;
    return `${pageIntro({ title: c.vocabularyStudy, note: c.vocabularyOverviewNote, eyebrow: c.vocabularyTitle, compact: true })}<div class="vocabulary-study-toolbar"><button class="quiet" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button>${practiceOnly ? `<span class="study-free ds-data">${esc(c.deckFreePractice)}</span>` : ''}<span>${studyIndex + 1} / ${studyItems.length}</span></div><section class="vocabulary-study-layout">${renderVocabularyStudyCard(copy, card, { index: studyIndex, practice: practiceOnly })}<nav class="vocabulary-study-nav"><button class="outline" data-study-prev ${studyIndex === 0 ? 'disabled' : ''}>←</button><button class="primary" data-study-next ${studyIndex >= studyItems.length - 1 ? 'disabled' : ''}>${studyIndex >= studyItems.length - 1 ? c.allDone : c.nextLine} →</button></nav></section>`;
  };

  /* A collection, as the design draws it (Screens part 1 section 05): the
     collection's own artwork, what it is, how far through it the learner is,
     and one way in - then a compact overview of its words, never 150 rows.
     "Show all" opens the full list, where search, level, status and sort live.
     A tier has no source yet and reads as a dash (GAP-020). */
  const WORD_PREVIEW = 8;
  const collectionStars = (card) => {
    const earned = (masteryStars(card).match(/★/g) || []).length;
    return `<span class="vocabulary-stars" aria-label="${esc(masteryStars(card))}">${[0, 1, 2]
      .map((step) => `<span${step < earned ? ' class="is-earned"' : ''}>${icon('star', { size: 11, filled: step < earned })}</span>`)
      .join('')}</span>`;
  };
  /* The set's own head: the way back, its name, and - when there is something
     to adjust - the way to the review settings. Frames 30 and 32 draw it. */
  const deckHead = (title, adjust) =>
    `<header class="deck-state__head"><button type="button" class="icon-button" data-vocabulary-back aria-label="${esc(c.vocabularyBackOverview)}">${icon('caret-right', { size: 22, className: 'is-flipped' })}</button><strong>${esc(title)}</strong>${
      adjust
        ? `<button type="button" class="icon-button" data-deck-settings aria-label="${esc(c.recallSettings)}">${icon('sliders-horizontal', { size: 20 })}</button>`
        : ''
    }</header>`;

  /* Frame 32: the set would not load. What it says is the true thing - the
     learner's progress is in the library, not in this screen - and the code is
     there to be quoted. */
  const deckLoadError = () =>
    `<section class="deck-state">${deckHead(activeCollection?.title || c.vocabularyLibraryTitle, false)}<div class="deck-state__body"><span class="deck-state__mark" data-tone="bad">${icon('cloud-x', { size: 30 })}</span><h2>${esc(c.deckLoadFailed)}</h2><p>${esc(c.deckLoadFailedNote)}</p><span class="deck-state__code ds-data">${esc(collectionFailed)}</span></div><div class="deck-state__foot"><button type="button" class="primary" data-vocabulary-retry-collection>${icon('arrow-clockwise', { size: 18 })}<span>${esc(c.retry)}</span></button></div></section>`;

  /* Frame 30: everything in this set that was due today has been reviewed.
     Both numbers are counted, not estimated: what comes back tomorrow is the
     library's own count, and what is left to learn is this set's. */
  const deckNothingDue = () => {
    const collection = activeCollection || {};
    const total = Number(collection.item_count) || 0;
    const learned = Number(collection.progress?.learned_count) || 0;
    const tomorrow = Number(summary().due_next_day || 0);
    const unlearned = Math.max(0, total - learned);
    const fresh = Math.min(settings.newPerDay, unlearned);
    return `<section class="deck-state">${deckHead(collection.title || c.vocabularyLibraryTitle, true)}<div class="deck-state__body"><span class="deck-state__mark" data-tone="good">${icon('check', { size: 32 })}</span><h2>${esc(c.deckAllDoneToday)}</h2><p>${esc(
      String(c.deckNextUp).replace('{n}', String(tomorrow)).replace('{m}', String(unlearned)),
    )}</p></div><div class="deck-state__foot">${
      fresh
        ? `<button type="button" class="primary" data-deck-learn-new="${esc(fresh)}">${esc(String(c.deckLearnNew).replace('{n}', String(fresh)))}</button>`
        : ''
    }<button type="button" class="outline" data-deck-free-practice>${esc(c.deckFreePractice)}</button></div></section>${
      deckSettingsOpen ? reviewSettingsSheet(c, settings, { newPerDay: NEW_PER_DAY, limitPerDay: REVIEW_LIMIT }) : ''
    }`;
  };

  /* Frame 29: the room when the learner has kept nothing yet. The starter
     sets are the catalogue's own - the same ones the full room draws - so this
     is the room with an explanation over it, not a different room. */
  const emptyRoom = () => {
    const starters = collections.slice(0, 4);
    return `<section class="vocab-empty"><header class="vocab-empty__head"><h1>${esc(c.vocabularyTitle)}</h1><button type="button" class="icon-button vocab-empty__add" data-add-open aria-label="${esc(c.addWord)}">${icon('plus', { size: 19 })}</button></header><div class="vocab-empty__say"><h2>${esc(c.vocabularyNoWordsYet)}</h2><p>${esc(c.vocabularyNoWordsNote)}</p></div>${
      starters.length
        ? `<div class="vocab-empty__packs">${starters
            .map(
              (pack) =>
                `<button type="button" class="vocab-pack" data-vocabulary-pack="${esc(pack.id)}"><span class="vocab-pack__art">${contentCover({ id: String(pack.id || pack.title || ''), title: pack.title || '', material: 'collection' })}</span><span class="vocab-pack__title">${esc(pack.title)}</span><span class="vocab-pack__meta ds-data">${esc([String(pack.language_code || language).toUpperCase(), `${Number(pack.item_count) || 0} ${c.vocabularyWordCount}`, pack.levels?.[0] || pack.level || ''].filter(Boolean).join(' · '))}</span></button>`,
            )
            .join('')}</div>`
        : ''
    }<div class="vocab-empty__foot"><button type="button" class="outline" data-add-open>${icon('plus', { size: 18 })}<span>${esc(c.addWordSelf)}</span></button></div></section>`;
  };

  const collectionDetail = () => {
    const collection = activeCollection || {};
    const progress = collection.progress || {};
    const learned = Number(progress.learned_count) || 0;
    const total = Number(collection.item_count) || 0;
    const percent = total ? Math.round((learned / total) * 100) : 0;
    const words = activeItems.filter((card) => !notMastered || vocabularyStatus(card) !== 'mastered');
    visibleItems = words;
    const shown = words.slice(0, WORD_PREVIEW);
    const level = collection.levels?.[0] || collection.level || '';
    const wordTile = (card, index) =>
      `<button type="button" class="vocab-word" data-vocabulary-study="${esc(index)}"><span class="vocab-word__text"><strong lang="${esc(card.identity?.language || language)}">${esc(card.headword)}</strong>${card.pronunciation ? `<small class="ds-data">${esc(card.pronunciation)}</small>` : ''}</span>${collectionStars(card)}</button>`;
    return `<section class="vocab-collection-page"><button type="button" class="icon-button vocab-back" data-vocabulary-back aria-label="${esc(c.vocabularyBackOverview)}">${icon('caret-right', { size: 20, className: 'is-flipped' })}</button><header class="vocab-collection__hero"><span class="vocab-collection__art">${contentCover({ id: String(collection.id || collection.title || ''), title: collection.title || '', material: 'collection' })}</span><div class="vocab-collection__copy"><div class="vocab-collection__chips"><span class="chip vocab-tier">${esc(r.vocabTier)} —</span><span class="chip">${esc([language.toUpperCase(), level].filter(Boolean).join(' · '))}</span></div><h1 lang="${esc(language)}">${esc(collection.title || c.vocabularyLibraryTitle)}${total ? ` · ${total} ${esc(c.vocabularyWordCount)}` : ''}</h1><div class="vocab-collection__progress"><span class="progress-bar"${percent ? '' : ' data-unavailable'}><span style="width:${percent}%"></span></span><span class="ds-data">${esc(learned)} / ${esc(total)}</span></div><div class="vocab-collection__actions"><button type="button" class="primary" data-vocabulary-collection-study>${icon('play', { size: 16, filled: true })}<span>${esc(c.vocabularyContinueReview)}</span></button><button type="button" class="icon-button" data-vocabulary-shuffle aria-label="${esc(r.vocabShuffle)}">${icon('shuffle', { size: 19 })}</button></div></div></header><div class="vocab-collection__body"><div class="vocab-words__head"><span class="ds-label">${esc(r.vocabWordsLabel)}</span><button type="button" class="chip vocab-words__filter" data-vocabulary-not-mastered aria-pressed="${notMastered}">${icon('funnel', { size: 13 })}<span>${esc(r.vocabNotMastered)}</span></button></div>${
      shown.length
        ? `<div class="vocab-words">${shown.map(wordTile).join('')}</div>`
        : `<div class="state-panel state-panel--empty">${icon('cards', { size: 20 })}<div><strong>${esc(c.vocabularyNoMatches)}</strong></div></div>`
    }${
      words.length > shown.length
        ? `<button type="button" class="vocab-show-all" data-vocabulary-show-all>${esc(String(r.vocabShowAll).replace('{n}', String(total || words.length)))}${icon('caret-down', { size: 16 })}</button>`
        : ''
    }</div></section>`;
  };
  const collectionView = () => management(activeCollection?.title || c.vocabularyLibraryTitle, `${activeCollection?.progress?.learned_count || 0} / ${activeCollection?.item_count || 0} ${c.vocabularyWordCount}`, true);

  const paint = () => {
    if (!alive()) return;
    /* No `saved` view: a learner's own words are Thư viện của tôi's (D-074),
       which lists, searches, marks, files and deletes them. */
    const bare = view === 'overview' && !savedCards.length && !savedError;
    const deckState = { unavailable: decksUnavailable, covers: deckCovers };
    root.innerHTML = view === 'strokes' ? wordStrokesHtml(c, { ...strokeState, language }) : view === 'clips' ? wordClipsHtml(c, { ...clipState, language }) : view === 'search' ? vocabularySearchHtml(c, { ...searching, language }) : bare ? emptyRoom() : view === 'add-word' ? addWordScreen(c, { ...adding, ...deckState, decks }) : view === 'new-deck' ? createDeckScreen(c, { ...newDeck, ...deckState, languages: deckLanguages() }) : view === 'deck-error' ? deckLoadError() : view === 'deck-done' ? deckNothingDue() : view === 'deep' ? wordDeepHtml(c, deepData || { headword: deepWord, language }, { page: deepPage, state: deepState }) : view === 'overview' ? overview() : view === 'library' ? libraryView() : view === 'collection' ? collectionDetail() : view === 'collection-list' ? collectionView() : studyView();
    if (deckSheet)
      root.insertAdjacentHTML(
        'beforeend',
        saveToDeckSheet(c, { ...deckSheet, ...deckState, decks }),
      );
    bind();
  };

  const setStudy = (items, index = 0, { practice = false } = {}) => {
    deckSettingsOpen = false;
    /* Cleared on every session, never carried: a free pass must not be able to
       silence the one after it. */
    practiceOnly = practice;
    studyItems = items;
    studyIndex = Math.max(0, Math.min(index, items.length - 1));
    returnView = view === 'study' ? returnView : view;
    view = 'study';
    paint();
  };

  const openCollection = async (id, params = {}) => {
    const requestId = ++collectionRequest;
    collectionFailed = null;
    try {
      const detail = await api.vocabularyLibraryCollection(id, params);
      if (!alive() || requestId !== collectionRequest) return;
      activeCollection = detail;
      activeItems = updateCollectionCards(detail.items || []);
      const isRefinement = Object.prototype.hasOwnProperty.call(params, 'search') || Object.prototype.hasOwnProperty.call(params, 'level');
      query = isRefinement ? String(params.search || '') : '';
      levelFilter = isRefinement ? String(params.level || '') || 'all' : 'all';
      if (!isRefinement) {
        filter = 'all';
        sort = 'recommended';
      }
      view = 'collection';
      paint();
    } catch (error) {
      if (!alive() || requestId !== collectionRequest) return;
      /* Frame 32 rather than a notice bar: the set has its own screen for not
         loading, and it carries the code a learner can quote. */
      collectionFailed = `VOC-${Number(error?.status || 0) || 'OFF'}`;
      view = 'deck-error';
      paint();
    }
  };

  const saveCard = async (card, sourceKind = 'manual') => {
    if (!card || card.saved) return;
    const payload = vocabularyKeepPayload(card, sourceKind, support);
    try {
      const result = await ctx.mutate(() => api.saveLibraryVocabulary(payload));
      const saved = result.item || {};
      card.saved = true;
      card.review_stage = Number(saved.review_stage) || 0;
      card.due = Boolean(saved.due);
      const existing = savedCards.findIndex((item) => item.headword.toLowerCase() === card.headword.toLowerCase());
      const savedCard = vocabularyCardFromSavedItem(saved, language, support, pinyinAllowed);
      if (existing >= 0) savedCards[existing] = savedCard;
      else savedCards.unshift(savedCard);
      savedData = { ...savedData, items: [...(savedData.items || []), saved], summary: { ...summary(), saved: stateCount('saved') + (existing >= 0 ? 0 : 1), learning: stateCount('learning') + (existing >= 0 ? 0 : 1), due: stateCount('due') + (existing >= 0 ? 0 : 1) } };
      if (view === 'study') studyItems[studyIndex] = { ...card, ...savedCard };
      paint();
    } catch {
      paint();
    }
  };

  /* Tracing: the learner's finger, converted once into the glyph's own
     coordinates, and judged against the stroke's median - which is the one
     piece of the vendored data that says which way a stroke runs. */
  const bindTracing = (square) => {
    if (!square || !strokeState?.tracing || !strokeState.character) return;
    const size = Number(strokeState.character.glyph_size) || 1024;
    const ink = square.querySelector('[data-strokes-ink]');
    const at = (event) => {
      const box = square.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * size;
      /* The glyph box runs upward; the screen runs downward. One conversion,
         here, so nothing downstream has to know. */
      const y = 900 - ((event.clientY - box.top) / box.height) * size;
      return [x, y];
    };
    const draw = () => {
      if (!ink) return;
      ink.innerHTML = points.length
        ? `<polyline points="${points.map(([x, y]) => `${x},${900 - y}`).join(' ')}" />`
        : '';
    };
    square.onpointerdown = (event) => {
      event.preventDefault();
      square.setPointerCapture(event.pointerId);
      points = [at(event)];
      strokeState.wrong = false;
      draw();
    };
    square.onpointermove = (event) => {
      if (!points.length) return;
      points.push(at(event));
      draw();
    };
    square.onpointerup = () => {
      const medians = strokeState.character.medians || [];
      const meant = medians[strokeState.at];
      const judged = tracedStroke(points, meant, { size });
      points = [];
      draw();
      if (judged.ok) {
        strokeState.at += 1;
        strokeState.wrong = false;
        if (strokeState.at >= (Number(strokeState.character.stroke_count) || 0)) {
          strokeState.tracing = false;
          strokeState.at = Number(strokeState.character.stroke_count) || 0;
        }
        paint();
        return;
      }
      /* Wrong: the frame shakes it and shows the right stroke faintly, which
         is what `data-wrong` turns on. Which stroke they actually drew is
         worth knowing - out of order is a different mistake from a scribble -
         so it is read, and said in the status line. */
      const other = strokeTraced(points, medians, { size });
      strokeState.wrong = true;
      strokeState.wrongReason = other >= 0 ? 'order' : judged.reason;
      paint();
      window.setTimeout(() => {
        if (!alive() || !strokeState) return;
        strokeState.wrong = false;
        paint();
      }, 600);
    };
  };

  const bind = () => {
    /* One word, opened all the way. The word on the back of a review card
       opens itself; the screen's own foot moves between the two pages the
       phone frames draw, and Escape leaves the way the back arrow does. */
    root.querySelectorAll('[data-vocabulary-deep]').forEach((node) => {
      const open = (event) => {
        event.stopPropagation();
        openWordDeep(node.dataset.vocabularyDeep);
      };
      node.onclick = open;
      node.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') open(event);
      };
    });
    root.querySelectorAll('[data-word-deep-back]').forEach((button) => (button.onclick = closeWordDeep));
    root.querySelector('[data-word-deep-clips]')?.addEventListener('click', () => openWordClips(deepWord));
    /* Nét chữ opens from the character itself on the deep screen's head - an
       attribute and a keyboard role, no pixel added, as the way into the deep
       screen itself is opened. */
    const openStrokes = root.querySelector('[data-word-deep-strokes]');
    if (openStrokes) {
      openStrokes.onclick = () => openWordStrokes(deepWord);
      openStrokes.onkeydown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openWordStrokes(deepWord);
        }
      };
    }
    root.querySelector('[data-strokes-back]')?.addEventListener('click', () => {
      stopStrokes();
      strokeState = null;
      view = returnView || 'overview';
      paint();
    });
    root.querySelector('[data-strokes-play]')?.addEventListener('click', () => {
      if (strokeState.playing) {
        stopStrokes();
        strokeState.playing = false;
        paint();
        return;
      }
      watchStrokes();
    });
    root.querySelector('[data-strokes-trace]')?.addEventListener('click', () => {
      stopStrokes();
      strokeState.playing = false;
      strokeState.tracing = !strokeState.tracing;
      strokeState.at = 0;
      strokeState.wrong = false;
      paint();
    });
    root.querySelector('[data-strokes-free]')?.addEventListener('click', () => {
      stopStrokes();
      strokeState.playing = false;
      strokeState.tracing = true;
      strokeState.at = 0;
      strokeState.free = true;
      strokeState.wrong = false;
      paint();
    });
    bindTracing(root.querySelector('[data-strokes-square]'));
    /* The clips screen. */
    root.querySelector('[data-clips-back]')?.addEventListener('click', () => {
      stopClip();
      clipState = null;
      view = returnView || 'overview';
      paint();
    });
    root.querySelector('[data-clip-toggle]')?.addEventListener('click', () => {
      if (clipState.playing) {
        stopClip();
        clipState.playing = false;
        paint();
        return;
      }
      playClip();
    });
    root.querySelector('[data-clip-again]')?.addEventListener('click', playClip);
    root.querySelector('[data-clip-speed]')?.addEventListener('click', () => {
      clipState.speed = clipState.speed === 1 ? 0.75 : 1;
      if (sound) sound.playbackRate = clipState.speed;
      paint();
    });
    root.querySelectorAll('[data-clip-play]').forEach((button) => {
      button.onclick = () => {
        stopClip();
        clipState.at = Number(button.dataset.clipPlay);
        clipState.playing = false;
        paint();
        playClip();
      };
    });
    root.querySelector('[data-clip-open]')?.addEventListener('click', (event) => {
      stopClip();
      location.hash = link('encounter', { id: `media:${event.currentTarget.dataset.clipOpen}`, intent: 'follow' });
    });
    root.querySelectorAll('[data-word-deep-retry]').forEach((button) => (button.onclick = () => openWordDeep(deepWord)));
    root.querySelectorAll('[data-word-deep-page]').forEach((button) => {
      button.onclick = () => {
        deepPage = button.dataset.wordDeepPage;
        paint();
      };
    });
    root.querySelectorAll('[data-word-deep-speak]').forEach((button) => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          const found = await api.wordAudio(deepWord, deepData?.reading || '');
          if (!alive()) return;
          if (!found?.available || !found.url) return;
          button.title = found.attribution || '';
          await new Audio(found.url).play();
        } catch {
          /* A word with no recording is a word with no recording. */
        } finally {
          if (alive()) button.disabled = false;
        }
      };
    });
    root.querySelectorAll('[data-word-deep-keep]').forEach((button) => {
      button.onclick = async () => {
        if (!deepData) return;
        button.disabled = true;
        try {
          const wasSaved = deepData.saved;
          if (wasSaved) await ctx.mutate(() => api.deleteLibraryVocabulary(deepWord));
          else await ctx.mutate(() => api.saveLibraryVocabulary({ word: deepWord }));
          if (!alive()) return;
          deepData = { ...deepData, saved: !wasSaved };
          /* Just kept: frame 22 is the sheet titled with the word that was
             saved, so this is where it belongs - the learner says which set it
             goes in, or makes one. Unkeeping opens nothing. */
          if (!wasSaved) {
            await readDecks();
            if (!alive()) return;
            deckSheet = { word: deepWord, note: deepData.gloss || '', chosen: decks[0]?.id || '' };
          }
          paint();
        } catch {
          button.disabled = false;
        }
      };
    });
    /* "Ask more" is the shared explanation, over the sentence this word was
       met in - the same one every other surface asks through. */
    root.querySelectorAll('[data-word-deep-ask]').forEach((button) => {
      button.onclick = () => {
        const context = (deepData?.sources || [])[0]?.title || (deepData?.senses || [])[0]?.example || deepWord;
        openUnderstanding(ctx, {
          selection: deepWord,
          context: String(context).slice(0, 2400),
          title: c.wordDeepAsk,
          question: c.askWhy,
          origin: null,
        });
      };
    });
    /* A kept word already carries the sentence it came from, which is exactly
       the context the shared explanation needs. Without this the list is
       something to reread rather than something a learner can question - the
       same gap Grammar had. */
    root.querySelectorAll('[data-word-explain]').forEach((button) => {
      button.onclick = () => {
        const entry = (savedData.items || []).find((x) => x.word === button.dataset.wordExplain);
        if (!entry?.source_fragment) return;
        const kept = ctx.memory.value.keptLanguage?.[entry.word];
        openUnderstanding(ctx, {
          selection: entry.word,
          context: entry.source_fragment.slice(0, 2400),
          title: entry.focus_note || c.sourceContext,
          question: c.askWhy,
          // Asking again about a word already kept must not lose where it came
          // from, so its own provenance rides along unchanged.
          origin: kept
            ? { id: kept.origin, where: kept.where, why: kept.why }
            : null,
        });
      };
    });
    root.querySelectorAll('[data-vocabulary-library]').forEach((button) => (button.onclick = () => { view = 'library'; paint(); }));
    root.querySelectorAll('[data-vocabulary-collection]').forEach((button) => (button.onclick = () => openCollection(button.dataset.vocabularyCollection)));
    root.querySelectorAll('[data-vocabulary-filter-pack]').forEach((button) => (button.onclick = () => {
      packFilter = button.dataset.vocabularyFilterPack;
      paint();
    }));
    root.querySelectorAll('[data-vocabulary-back]').forEach((button) => (button.onclick = () => { view = view === 'study' ? returnView : view === 'collection-list' ? 'collection' : 'overview'; paint(); }));
    root.querySelector('[data-vocabulary-not-mastered]')?.addEventListener('click', () => { notMastered = !notMastered; paint(); });
    root.querySelector('[data-vocabulary-show-all]')?.addEventListener('click', () => { view = 'collection-list'; paint(); });
    root.querySelector('[data-vocabulary-collection-study]')?.addEventListener('click', () => {
      /* Nothing in this set is due: frame 30 rather than a session of cards
         that were answered this morning. */
      const due = visibleItems.filter((card) => card.due);
      if (!due.length && visibleItems.some((card) => card.saved)) {
        returnView = view;
        view = 'deck-done';
        paint();
        return;
      }
      if (visibleItems.length) setStudy(due.length ? due : visibleItems);
    });
    /* The room's own search. */
    root.querySelectorAll('[data-search-open]').forEach((node) => {
      if (node.dataset.searchOpen) return;
      node.onclick = () => {
        returnView = view;
        searching = { query: '', filter: 'all', saved: [], catalogue: [], savedTotal: 0, busy: false };
        view = 'search';
        paint();
        root.querySelector('[data-search-input]')?.focus();
      };
    });
    root.querySelector('[data-search-input]')?.addEventListener('input', (event) => {
      searching.query = event.target.value;
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => { if (alive()) runSearch(); }, SEARCH_DEBOUNCE_MS);
    });
    root.querySelector('[data-search-clear]')?.addEventListener('click', () => {
      searching.query = '';
      runSearch();
    });
    root.querySelector('[data-search-cancel]')?.addEventListener('click', () => {
      window.clearTimeout(searchTimer);
      searchRequest += 1;
      searching = null;
      view = returnView || 'overview';
      paint();
    });
    root.querySelectorAll('[data-search-filter]').forEach((button) => {
      button.onclick = () => {
        searching.filter = button.dataset.searchFilter;
        paint();
      };
    });
    /* A result opens the word all the way - which is where the deep frames say
       they are opened from. */
    root.querySelectorAll('[data-search-open]').forEach((button) => {
      if (!button.dataset.searchOpen) return;
      button.onclick = () => openWordDeep(button.dataset.searchOpen);
    });
    root.querySelectorAll('[data-search-keep]').forEach((button) => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await ctx.mutate(() => api.saveLibraryVocabulary({ word: button.dataset.searchKeep }));
          if (!alive()) return;
          await runSearch();
          status(c.persisted);
        } catch {
          if (alive()) button.disabled = false;
        }
      };
    });

    /* Adding a word by hand, and where it lands. */
    root.querySelectorAll('[data-add-open]').forEach((button) => {
      button.onclick = async () => {
        await readDecks();
        if (!alive()) return;
        adding = { word: '', meaning: '', example: '', chosen: decks[0]?.id || '', found: false, again: true, busy: false };
        returnView = view;
        view = 'add-word';
        paint();
      };
    });
    const takeField = (selector, key) =>
      root.querySelector(selector)?.addEventListener('input', (event) => {
        adding[key] = event.target.value;
        const go = root.querySelector('[data-add-save]');
        if (go) go.disabled = !(adding.word.trim() && adding.meaning.trim());
      });
    takeField('[data-add-word]', 'word');
    takeField('[data-add-meaning]', 'meaning');
    takeField('[data-add-example]', 'example');
    /* The catalogue is asked about the word as it is typed, and what it knows
       fills the rest in - the frame's "đã điền sẵn". It never overwrites what
       the learner has already written. */
    root.querySelector('[data-add-word]')?.addEventListener('change', async () => {
      const wanted = adding.word.trim();
      if (!wanted) return;
      try {
        const found = await api.wordDeep(wanted);
        if (!alive() || adding.word.trim() !== wanted) return;
        adding.found = Boolean(found?.senses?.length);
        if (adding.found && !adding.meaning.trim()) adding.meaning = found.senses[0].meaning || '';
        if (adding.found && !adding.example.trim()) adding.example = found.senses[0].example || '';
        paint();
      } catch {
        /* A word the catalogue does not know is still a word worth keeping. */
      }
    });
    root.querySelector('[data-add-again]')?.addEventListener('change', (event) => {
      adding.again = event.target.checked;
    });
    root.querySelector('[data-add-cancel]')?.addEventListener('click', () => {
      adding = null;
      view = returnView || 'overview';
      paint();
    });
    root.querySelector('[data-add-pick-deck]')?.addEventListener('click', () => {
      deckSheet = { word: adding.word || c.addWord, note: adding.meaning || '', chosen: adding.chosen };
      paint();
    });
    root.querySelector('[data-add-save]')?.addEventListener('click', async () => {
      if (!adding || adding.busy) return;
      adding.busy = true;
      paint();
      try {
        await ctx.mutate(() =>
          api.saveLibraryVocabulary({
            word: adding.word.trim(),
            definition: adding.meaning.trim(),
            source_fragment: adding.example.trim(),
            source_kind: 'manual',
          }),
        );
        if (adding.chosen) await fileWord(adding.word.trim(), adding.chosen);
        if (!alive()) return;
        savedData = await api.libraryVocabulary({ limit: SAVED_PAGE, order: 'recent' });
        refreshSavedCards();
        if (adding.again) {
          adding = { ...adding, word: '', meaning: '', example: '', found: false, busy: false };
        } else {
          adding = null;
          view = returnView || 'overview';
        }
        paint();
        status(c.persisted);
      } catch {
        if (!alive()) return;
        adding.busy = false;
        paint();
        status(c.failedSave);
      }
    });
    /* Which set: the sheet frame 22 draws, over whatever screen opened it. */
    root.querySelectorAll('[data-deck-pick]').forEach((button) => {
      button.onclick = () => {
        deckSheet.chosen = button.dataset.deckPick;
        paint();
      };
    });
    root.querySelector('[data-deck-close]')?.addEventListener('click', () => {
      deckSheet = null;
      paint();
    });
    root.querySelector('[data-deck-save]')?.addEventListener('click', async () => {
      const chosen = deckSheet?.chosen;
      const word = deckSheet?.word;
      deckSheet = null;
      if (adding) adding.chosen = chosen;
      else if (chosen && word) await fileWord(word, chosen);
      paint();
    });
    root.querySelector('[data-deck-new]')?.addEventListener('click', () => {
      deckSheet = null;
      newDeck = { title: '', language, cover: deckCovers[0] || 'violet', covers: deckCovers, locked: false, busy: false };
      returnView = view;
      view = 'new-deck';
      paint();
    });
    root.querySelector('[data-deck-title]')?.addEventListener('input', (event) => {
      newDeck.title = event.target.value;
      const go = root.querySelector('[data-deck-create]');
      if (go) go.disabled = !newDeck.title.trim();
    });
    root.querySelectorAll('[data-deck-language]').forEach((button) => {
      button.onclick = () => {
        newDeck.language = button.dataset.deckLanguage;
        paint();
      };
    });
    /* The cover the frame draws a chooser for. It is a name, not a colour -
       `theme.css` stays the only thing that knows what each one looks like. */
    root.querySelectorAll('[data-deck-cover]').forEach((button) => {
      button.onclick = () => {
        newDeck.cover = button.dataset.deckCover;
        paint();
      };
    });
    root.querySelector('[data-deck-cancel]')?.addEventListener('click', () => {
      newDeck = null;
      view = returnView || 'overview';
      paint();
    });
    root.querySelector('[data-deck-create]')?.addEventListener('click', async () => {
      if (!newDeck || newDeck.busy) return;
      newDeck.busy = true;
      paint();
      try {
        const answer = await ctx.mutate(() =>
          api.vocabularyDeckCreate({ title: newDeck.title.trim(), cover: newDeck.cover || 'violet' }),
        );
        if (!alive()) return;
        const made = answer.deck || answer;
        decks = [...decks, made];
        if (adding) adding.chosen = made.id;
        newDeck = null;
        view = returnView || 'overview';
        paint();
        status(c.persisted);
      } catch {
        if (!alive()) return;
        newDeck.busy = false;
        paint();
        status(c.failedSave);
      }
    });
    root.querySelector('[data-deck-settings]')?.addEventListener('click', () => {
      deckSettingsOpen = true;
      paint();
    });
    root.querySelector('[data-recall-settings-close]')?.addEventListener('click', () => {
      deckSettingsOpen = false;
      paint();
    });
    root.querySelectorAll('[data-recall-setting]').forEach((input) => {
      input.oninput = () => {
        settings = readReviewSettings({ ...settings, [input.dataset.recallSetting]: input.value });
        memory.setReview(settings);
        paint();
      };
    });
    root.querySelectorAll('[data-recall-mode]').forEach((button) => {
      button.onclick = () => {
        const name = button.dataset.recallMode;
        settings = readReviewSettings({ ...settings, modes: { ...settings.modes, [name]: !settings.modes[name] } });
        memory.setReview(settings);
        paint();
      };
    });
    root.querySelector('[data-vocabulary-retry-collection]')?.addEventListener('click', () => {
      if (activeCollection?.id) openCollection(activeCollection.id);
    });
    root.querySelector('[data-deck-learn-new]')?.addEventListener('click', () => {
      const fresh = activeItems.filter((card) => !card.saved).slice(0, Number(root.querySelector('[data-deck-learn-new]').dataset.deckLearnNew) || 0);
      if (fresh.length) setStudy(fresh);
    });
    root.querySelector('[data-deck-free-practice]')?.addEventListener('click', () => {
      if (!activeItems.length) return;
      setStudy(activeItems, 0, { practice: true });
    });
    root.querySelector('[data-vocabulary-shuffle]')?.addEventListener('click', () => {
      if (!visibleItems.length) return;
      /* A shuffled pass is a different order of the same words, nothing more. */
      const order = [...visibleItems];
      for (let index = order.length - 1; index > 0; index -= 1) {
        const swap = Math.floor(Math.random() * (index + 1));
        [order[index], order[swap]] = [order[swap], order[index]];
      }
      setStudy(order);
    });
    root.querySelector('[data-vocabulary-search]')?.addEventListener('input', (event) => {
      query = event.target.value;
      if (view === 'collection' && activeCollection) {
        if (collectionSearchTimer) clearTimeout(collectionSearchTimer);
        const collectionId = activeCollection.id;
        collectionSearchTimer = setTimeout(() => {
          openCollection(collectionId, {
            search: query,
            level: levelFilter === 'all' ? '' : levelFilter,
          });
        }, 250);
        return;
      }
      paint();
      const input = root.querySelector('[data-vocabulary-search]');
      input?.focus();
      input?.setSelectionRange(query.length, query.length);
    });
    root.querySelector('[data-vocabulary-load-more]')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const pagination = activeCollection?.pagination || {};
        const next = await api.vocabularyLibraryCollection(activeCollection.id, {
          search: query, level: levelFilter === 'all' ? '' : levelFilter, limit: pagination.limit || 100, offset: (pagination.offset || 0) + (pagination.limit || activeItems.length || 100),
        });
        if (!alive()) return;
        activeItems = [...activeItems, ...(next.items || [])];
        activeCollection = { ...activeCollection, ...next, items: activeItems };
        paint();
      } catch { button.disabled = false; }
    });
    root.querySelectorAll('[data-vocabulary-filter]').forEach((button) => (button.onclick = () => {
      filter = button.dataset.vocabularyFilter;
      paint();
    }));
    root.querySelectorAll('[data-vocabulary-level-filter]').forEach((button) => (button.onclick = () => {
      levelFilter = button.dataset.vocabularyLevelFilter;
      if (view === 'collection' && activeCollection) {
        openCollection(activeCollection.id, {
          search: query,
          level: levelFilter === 'all' ? '' : levelFilter,
        });
      } else {
        paint();
      }
    }));
    root.querySelector('[data-vocabulary-sort]')?.addEventListener('change', (event) => {
      sort = event.target.value;
      paint();
    });
    const interactionPool = () => vocabularyInteractionItems(view, { visibleItems, savedCards, studyItems });
    root.querySelectorAll('[data-vocabulary-study]').forEach((button) => (button.onclick = () => setStudy(interactionPool(), Number(button.dataset.vocabularyStudy))));
    root.querySelectorAll('[data-vocabulary-save]').forEach((button) => (button.onclick = () => saveCard(interactionPool()[Number(button.dataset.vocabularySave)], view === 'collection' ? 'collection' : 'manual')));
    const studyCard = root.querySelector('.vocabulary-study-card');
    const setStudyState = (nextState) => {
      if (!studyCard) return;
      const front = studyCard.querySelector('[data-study-front]');
      const back = studyCard.querySelector('[data-study-back]');
      const showingBack = nextState === 'back';
      studyCard.dataset.studyState = nextState;
      front?.setAttribute('aria-hidden', showingBack ? 'true' : 'false');
      back?.setAttribute('aria-hidden', showingBack ? 'false' : 'true');
      if (front) front.inert = showingBack;
      if (back) back.inert = !showingBack;
    };
    const flipStudyCard = () => {
      if (!studyCard) return;
      setStudyState(studyCard.dataset.studyState === 'back' ? 'front' : 'back');
    };
    if (studyCard) {
      studyCard.addEventListener('click', (event) => {
        if (event.target.closest('button, a, input, select, textarea, [data-study-no-flip]')) return;
        flipStudyCard();
      });
      studyCard.addEventListener('keydown', (event) => {
        if (event.target !== studyCard || !['Enter', ' '].includes(event.key)) return;
        event.preventDefault();
        flipStudyCard();
      });
    }
    root.querySelectorAll('[data-study-flip]').forEach((button) => (button.onclick = (event) => { event.stopPropagation(); flipStudyCard(); }));
    root.querySelector('[data-study-prev]')?.addEventListener('click', () => { if (studyIndex > 0) { studyIndex -= 1; paint(); } });
    root.querySelector('[data-study-next]')?.addEventListener('click', () => { if (studyIndex < studyItems.length - 1) { studyIndex += 1; paint(); } });
    root.querySelector('[data-study-audio]')?.addEventListener('click', () => { const word = studyItems[studyIndex]?.headword; if (word && 'speechSynthesis' in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(word)); });
    root.querySelectorAll('[data-study-grade]').forEach((button) => (button.onclick = async () => { const card = studyItems[studyIndex]; button.disabled = true; try { const result = await ctx.mutate(() => api.reviewLibraryVocabulary(card.headword, button.dataset.studyGrade)); if (result.item) { const updated = vocabularyCardFromSavedItem(result.item, language, support, pinyinAllowed); studyItems[studyIndex] = updated; const savedIndex = savedCards.findIndex((item) => item.headword.toLowerCase() === card.headword.toLowerCase()); if (savedIndex >= 0) savedCards[savedIndex] = updated; savedData.items = savedData.items.map((item) => item.word.toLowerCase() === card.headword.toLowerCase() ? result.item : item); savedData.summary = { ...summary(), due: savedCards.filter((item) => item.due).length, learning: savedCards.filter((item) => (Number(item.review_stage) || 0) < 3).length, mastered: savedCards.filter((item) => (Number(item.review_stage) || 0) >= 3).length }; } paint(); } catch { button.disabled = false; } }));
    root.querySelectorAll('[data-vocabulary-retry]').forEach((button) => (button.onclick = () => location.reload()));
  };

  paint();
}

export async function renderGrammar(root, ctx) {
  const { api, c, language, alive, memory } = ctx;
  if (!ctx.location.id) {
    const result = await api.grammarLibrary();
    if (!alive()) return;
    const lessons = grammarShelf(result, patternsFor(language), ctx.ui);
    /* A syllabus and a catalogue answer different questions. The flat list
       answers "where is the pattern whose name I already know"; a learner who
       does not yet know what they need has no way into it. The levels and
       families the syllabus already declares are the way in, and the catalogue
       stays underneath for anyone who does know. */
    const syllabus = grammarFamilies(lessons);
    const patternCount = (n) =>
      `${n} ${esc(n === 1 ? c.grammarPatternOne : c.grammarPatterns)}`;
    root.innerHTML = `${practiceReturn(c, 'grammar')}${pageIntro({ title: c.grammarTitle, note: c.grammarNote, eyebrow: c.grammarName, scene: 'thinking' })}<section class="grammar-syllabus" aria-label="${esc(c.grammarSyllabus)}">${syllabus
      .map(
        (level) =>
          `<section class="syllabus-level"><header><h2>${esc(level.level)}</h2><small>${patternCount(level.total)}</small></header><div class="family-row">${level.families
            .map(
              (family) =>
                `<button class="family-card" data-family="${esc(family.name)}" data-family-level="${esc(family.level)}"><small>${patternCount(family.count)}</small><h3>${esc(family.name)}</h3>${family.line ? `<p lang="${language}">${esc(family.line)}</p>` : ''}</button>`,
            )
            .join('')}</div></section>`,
      )
      .join('')}</section><details class="grammar-browse" data-browse><summary><span>${esc(c.grammarBrowse)}</span><small>${patternCount(lessons.length)}</small></summary>${collectionSearch(c, { facet: c.collectionLevel, options: (result.levels || []).map((level) => ({ value: level, label: level })) })}<p class="family-active" data-family-active hidden></p><div class="pattern-list" data-grammar-results></div><button class="outline" data-more>${esc(c.collectionMore)}</button></details>`;
    let shown = 18,
      family = '',
      filtered = lessons;
    const paint = () => {
      root.querySelector('[data-grammar-results]').innerHTML =
        filtered
          .slice(0, shown)
          .map(
            (x) =>
              `<a href="${link('practice', { intent: 'grammar', id: x.id })}"><small>${esc(x.level)}</small><h2 lang="${x.editorial ? ctx.ui : language}">${esc(x.heading)}</h2>${x.editorial ? `<p lang="${language}">${esc(x.line)}</p>` : ''}<span aria-hidden="true">↗</span></a>`,
          )
          .join('') || `<p>${esc(c.noPatterns)}</p>`;
      root.querySelector('[data-more]').hidden = shown >= filtered.length;
    };
    let search = { query: '', facet: 'all' };
    const refilter = () => {
      shown = 18;
      filtered = filterGrammar(lessons, {
        query: search.query,
        level: search.facet,
        family,
      });
      const label = root.querySelector('[data-family-active]');
      label.hidden = !family;
      label.innerHTML = family
        ? `<span>${esc(c.grammarInFamily)} ${esc(family)}</span><button class="quiet" data-leave-family>${esc(c.grammarSearchAll)}</button>`
        : '';
      const leave = label.querySelector('[data-leave-family]');
      if (leave)
        leave.onclick = () => {
          // The query the learner typed is theirs; only the scope widens.
          family = '';
          rerunSearch();
        };
      paint();
      return filtered.length;
    };
    const rerunSearch = bindCollectionSearch(root, c, (next) => {
      search = next;
      /* Searching stays inside the family the learner entered. Widening used to
         happen on the first keystroke, which meant a search could answer with
         patterns from a level they had not asked about and clearing the box
         dropped them into all 234 with no way back. Leaving a family is now
         something the learner does on purpose, below. */
      return refilter();
    });
    /* Entering a family opens the catalogue already narrowed to it, so the
       structure above and the list below are one place rather than two. */
    root.querySelectorAll('[data-family]').forEach((card) => {
      card.onclick = () => {
        family = card.dataset.family;
        const browse = root.querySelector('[data-browse]');
        browse.open = true;
        // Through the search binding, so the stated count matches the rows.
        rerunSearch();
        browse.scrollIntoView({
          behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
            ? 'auto'
            : 'smooth',
          block: 'start',
        });
      };
    });
    root.querySelector('[data-more]').onclick = () => {
      shown += 18;
      paint();
    };
    paint();
    return;
  }
  const lesson = await api.grammarLesson(ctx.location.id);
  if (!alive()) return;
  const examples = lesson.examples || [],
    id = `grammar:${lesson.id}`,
    note = patternsFor(language).find((x) => x.id === lesson.id),
    title =
      note?.title[ctx.ui] ||
      examples[0]?.target ||
      examples[0]?.en ||
      examples[0]?.zh ||
      lesson.title;
  /* A pattern is easier to hold onto against the thing it is not. The contrast
     is what a learner actually writes instead, named in the one judgement
     vocabulary the rest of the product uses, so "wrong" means the same thing
     here as it does in a writing review or a reading explanation. */
  const contrast = note?.contrast;
  const contrastBlock = contrast
    ? `<section class="pattern-contrast"><h2>${esc(c.notThis)}</h2><p class="judgement" data-judgement="${esc(contrast.judgement)}">${esc(judgementLabel(c, contrast.judgement))}</p><blockquote lang="${esc(language)}"><del>${esc(contrast.instead)}</del></blockquote><p>${esc(contrast.why[ctx.support] || contrast.why[ctx.ui] || contrast.why.en)}</p><blockquote class="pattern-right" lang="${esc(language)}">${esc(note.line)}</blockquote></section>`
    : '';
  root.innerHTML = `<div class="back-row"><a href="${link('practice', { intent: 'grammar' })}">← ${c.grammarName}</a></div>${pageIntro({ title, eyebrow: lesson.level, compact: true })}${note ? `<section class="pattern-focus"><small>${c.generatedNote}</small><div class="pattern-parts" lang="${language}">${note.parts.map((x) => `<span>${esc(x)}</span>`).join('<i aria-hidden="true">→</i>')}</div><p lang="${ctx.support}">${esc(note.note[ctx.support] || (ctx.support === 'vi' ? lesson.explanation_vi : '') || c.noMeaning)}</p></section>` : ''}<section class="grammar-encounter"><div><h2>${c.example}</h2>${examples.map((x, index) => `<blockquote lang="${language}">${esc(x.target || x.en || x.zh || '')}${x.pinyin && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<small>${esc(x.pinyin)}</small>` : ''}${ctx.support === 'vi' && (x.meaning_vi || x.vi) ? `<p lang="vi">${esc(x.meaning_vi || x.vi)}</p>` : ''}<button class="quiet" data-explain="${index}">${esc(c.lookCloser)} ↗</button></blockquote>`).join('')}</div>${contrastBlock}</section>${responseComposer(ctx, { id, title, prompt: c.yourExample })}`;
  /* Grammar was the one capability that could not ask its own question. Every
     example now reaches the same explanation surface reading, listening,
     writing and speaking use, carrying the pattern as the context it sits in. */
  root.querySelectorAll('[data-explain]').forEach((button) => {
    button.onclick = () => {
      const example = examples[Number(button.dataset.explain)];
      const sentence = example?.target || example?.en || example?.zh || '';
      if (!sentence) return;
      // The pattern is the context the example sits in, unless the example is
      // the pattern - sending the same sentence twice teaches nothing.
      const context = [...new Set([note?.line, sentence].filter(Boolean))].join(
        '\n',
      );
      openUnderstanding(ctx, {
        selection: sentence,
        context: context.slice(0, 2400),
        title,
        question: c.askWhy,
        origin: { id, where: title, why: 'from_grammar' },
      });
    };
  });
  bindComposer(root, ctx, { id, title }, () => note?.line || '');
}
