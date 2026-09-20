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
import {
  renderVocabularyCollectionCard,
  renderVocabularyBrowseCard,
  renderVocabularyFeedCarousel,
  bindVocabularyFeedCarousel,
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
import {
  writingReview,
  writingReviewFailure,
  writingReviewWaiting,
  shownIssues,
} from './writing-review.js';
import { locateInText } from './writing-locate.js';
import {
  MAX_CHARACTERS,
  editWouldFit,
  measureWriting,
} from '../capabilities/writing-limits.js';
import {bindRevisionWorkbench} from './revision-workbench.js';
import { learningToolbar, bindLearningToolbar } from './learning-toolbar.js';
import { icon } from './phosphor.js';
import { contentCover } from './cover.js';
import { referenceCopy } from './reference.js';
import { openRegisters } from './registers.js';
import { link, sourceLink } from '../product/intent.js';
import { patternsFor } from '../content/patterns.js';
import {
  grammarShelf,
  filterGrammar,
  grammarFamilies,
} from '../product/grammar-shelf.js';
import { recallShape, blankContext } from '../product/recall.js';
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
  const levels =
    ctx.languageProfiles?.find((x) => x.code === language)?.levels || [];
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
  const writingActions = [
    {
      name: 'more',
      icon: 'more',
      kind: 'menu',
      label: c.stageMore,
      items: [
        { name: 'registers', label: c.registerExplore },
        { name: 'history', label: c.revisionHistory },
      ],
    },
  ];
  root.innerHTML = `<div class="back-row"><a href="${hasSource ? sourceLink(id) : link('practice')}">← ${hasSource ? c.returnLabel : c.practice}</a>${draftStatus(ctx)}</div><header class="writing-head"><small>${esc(c.writingName)}</small><h1>${esc(title)}</h1><div class="writing-intention"><label class="sr-only" for="writingTask">${esc(c.writingTask)}</label><input id="writingTask" name="task" maxlength="240" autocomplete="off" placeholder="${esc(c.writingIntentionNone)}" value="${esc(intention)}">${hint({ text: c.writingTaskNote })}</div>${hasSource ? `<p class="writing-head__prompt" lang="${language}">${esc(prompt)}</p>` : ''}</header><section class="learning-workspace writing-workspace" data-workspace="activity" data-review="waiting"><div class="workspace-activity"><form id="expressionForm" class="writing-sheet"><div class="draft-elsewhere" data-draft-elsewhere role="status" hidden></div><label class="sr-only" for="expressionText">${c.respond}</label><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="10" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id] || series?.latest.text || '')}</textarea><div class="writing-bar"><span class="meta" data-character-count aria-live="polite"></span><label class="review-target"><span class="sr-only">${esc(c.reviewTarget)}</span><select name="target" data-tip="${esc(c.reviewTarget)}" aria-label="${esc(c.reviewTarget)}"><option value="">${c.chooseTarget}</option>${levels.map((level) => `<option value="${esc(level)}">${esc(level)}</option>`).join('')}</select></label>${learningToolbar(writingActions, { label: c.writingName })}<button class="primary" data-review-action>${esc(c.reviewAction)}</button></div><p class="writing-trouble" data-writing-trouble hidden></p></form></div><section class="workspace-result writing-result" aria-label="${esc(c.review)}"><div class="workspace-result__bar"><button type="button" class="quiet" data-back-to-writing>← ${esc(c.writingKeepWriting)}</button></div><p class="review-stale" data-review-stale-note hidden><span>${esc(c.reviewStale)}</span><button type="button" class="quiet" data-review-again>${esc(c.reviewStaleAction)}</button></p><div class="workspace-result__scroll" id="writingFeedback" aria-live="polite">${excerpt ? `<aside class="expression-context"><small>${esc(c.expressionContext)}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote><a class="quiet" href="${sourceLink(id)}">${c.returnLabel} ↗</a></aside>` : writingReviewWaiting(c)}</div></section></section><div class="workspace-secondary">${excerpt ? '' : `<aside class="expression-starters"><h2>${c.expressionStarters}</h2><p class="meta">${c.expressionStarterNote}</p>${invitations.map((item) => `<a href="${link('expression', { id: 'story:' + item.id })}"><small>${c.generated}</small><strong lang="${language}">${esc(item.prompt)}</strong><span>${c.usePrompt} ↗</span></a>`).join('')}</aside>`}<section class="revision-history" data-revisions></section></div>${continuationShelf(ctx, 2)}`;
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
  /* Which words the review on screen was written about.

     A learner who edits after a review still wants to see it - it is the last
     thing anybody said about their writing - but it stops being *current* the
     moment the words change. So the text it answered is remembered, and the
     room says plainly whose version it belongs to rather than deleting it or
     letting it pass for an answer about what is now in the box. */
  let reviewedText = null;
  /* The secondary writing actions, in the shared bar rather than a second row
     of large buttons beside the primary one. Registers and the history of the
     piece are both things a learner reaches for sometimes, not every time. */
  const writingBar = bindLearningToolbar(root.querySelector('.writing-bar .learning-toolbar'), {
    onAction: (name) => {
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
    // A distinct name from the workspace's own flag above: one selector that
    // matched both would have hidden the whole workspace, and only the grid's
    // own `display` kept that from showing.
    const note = root.querySelector('[data-review-stale-note]');
    if (note) note.hidden = !stale;
  }
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
  const updateCount = () => {
    const length = [...root.querySelector('textarea').value].length;
    root.querySelector('[data-character-count]').textContent =
      length >= LIMIT * 0.9 ? `${length} / ${LIMIT} ${c.draftCount}` : '';
  };
  updateCount();
  paintRevisions();
  const presentReview = (result, text) => {
    const feedback = root.querySelector('#writingFeedback');
    // Only show a finding whose wording is genuinely in what the learner
    // wrote, so a struck-through phrase is always one of their own.
    const corrections = shownIssues(result, text);
    feedback.innerHTML = writingReview(c, result, { language, text });
    bindRevisionWorkbench(feedback,ctx,{issues:corrections,reviewedText:text,draft:root.querySelector('#expressionText'),id,title});
    feedback.querySelector('[data-revise]').onclick = () =>
      root.querySelector('textarea').focus();
    feedback.querySelector('[data-registers]').onclick = () =>
      openRegisters(ctx, { text, title });
    workspace.dataset.review = 'ready';
    reviewedText = text;
    markReviewFreshness();
    sayTrouble('');
    /* A quoted phrase is findable in the learner's own words rather than
       something to hunt for by eye, and the caret is left in it, so the
       revision has already begun (`ui/writing-locate.js`). */
    feedback.querySelectorAll('[data-locate]').forEach((button) => {
      button.onclick = () => {
        const issue = corrections[Number(button.dataset.locate)];
        const box = root.querySelector('#expressionText');
        if (!issue || !box) return;
        showActivity();
        if (!locateInText(box, issue.quote)) status(c.revisionAmbiguous);
      };
    });
    // "Why?" opens the same explanation surface reading and listening use,
    // with the learner's own sentence as the context it reasons about.
    feedback.querySelectorAll('[data-why]').forEach((button) => {
      button.onclick = () => {
        const issue = corrections[Number(button.dataset.why)];
        if (!issue) return;
        const sentence =
          text
            .split(/(?<=[.!?。！？])\s+/)
            .find((part) => part.includes(issue.quote)) || text;
        openUnderstanding(ctx, {
          selection: issue.quote,
          context: sentence.slice(0, 2400),
          title,
          question: c.askWhy,
          origin: { id, where: title, why: 'from_writing' },
        });
      };
    });
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
    const button = form.querySelector('button.primary'),
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
            target_cefr: root.querySelector('[name=target]').value || null,
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
        button.textContent = workspace.dataset.review === 'ready' ? c.reviewAgain : c.reviewAction;
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
  const data = await api.libraryVocabulary();
  if (!alive()) return;
  let items = data.items || [],
    revealed = false,
    reviewed = 0,
    stage = 'landing';
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
    const rail = `<div class="review-rail" aria-hidden="true">${Array.from(
      { length: Math.min(reviewed + due.length, 12) },
      (_, position) => `<span class="review-rail__step"${position < passed ? ' data-tone="done"' : ''}></span>`,
    ).join('')}</div>`;
    const grade = (key, label, live) =>
      `<button type="button" class="review-grade${live === 'good' ? ' review-grade--good' : ''}"${live ? ` data-grade="${key}"` : ` disabled title="${esc(r.vocabGradeUnavailable)}"`}>${icon(
        key === 'again' ? 'arrow-counter-clockwise' : key === 'hard' ? 'clock' : key === 'got_it' ? 'check' : 'lightning',
        { size: 15 },
      )}<span>${esc(label)}</span><span class="ds-data review-grade__when">—</span></button>`;
    const grades = `<div class="review-grades"><span class="ds-label">${esc(r.vocabHowWell)}</span>${grade('again', c.again, 'again')}${grade('hard', r.vocabGradeHard, '')}${grade('got_it', c.gotIt, 'good')}${grade('easy', r.vocabGradeEasy, '')}</div>`;
    const card = current
      ? `<section class="review-session" data-shape="${shape}"><header class="review-bar"><span class="ds-data">${esc(due.length)} ${esc(c.vocabularyDueState)}</span>${rail}<span class="ds-data">${esc(passed)} / ${esc(reviewed + due.length)}</span></header><div class="review-body"><div class="review-prompt"><small>${esc(c[`recallAsk_${shape}`])}</small>${
          shape === 'in_context' && gap
            ? `<blockquote class="recall-gap" lang="${language}">${withheld(revealed ? esc(current.word) : '&nbsp;'.repeat(3))}</blockquote>`
            : `<h2 lang="${language}">${revealed || shape !== 'say' ? esc(current.word) : '···'}</h2>${current.phonetic && revealed && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(current.phonetic)}</p>` : ''}${shape === 'say' && !revealed ? `<p lang="${esc(ctx.support)}">${esc(current.definition || current.translation_vi || '')}</p>` : ''}${shape !== 'in_context' && current.source_fragment ? `<blockquote class="${gap && !revealed ? 'recall-gap' : ''}" lang="${language}">${gap && !revealed ? withheld('&nbsp;'.repeat(3)) : esc(current.source_fragment)}</blockquote>` : ''}`
        }${
          revealed
            ? `${shape === 'say' ? '' : `<p class="review-meaning" lang="${esc(ctx.support)}">${esc(current.definition || current.translation_vi || '')}</p>`}${current.focus_note ? `<p class="recall-where">${esc(current.focus_note)}</p>` : ''}${keptProvenance(c, keptNow)}${current.source_fragment ? `<button class="quiet" data-word-explain="${esc(current.word)}">${esc(c.lookCloser)} ↗</button>` : ''}${shape === 'reuse' ? `<a class="outline" href="${link('expression')}">${esc(c.recallUseInWriting)} ↗</a>` : ''}<p class="meta">${c.recallTruth}</p>`
            : `<button class="primary" data-reveal>${esc(c[`recallReveal_${shape}`])} →</button>`
        }<p role="status" data-recall-status></p></div>${revealed ? grades : ''}</div></section>`
      : '';
    /* What is waiting, before the first item. A learner dropped straight into
       item one has no idea whether this is three words or thirty. */
    const landing = due.length
      ? `<section class="recall-landing"><small>${esc(c.vocabularyDueState)}</small><h2>${due.length} ${esc(c.vocabularyWordCount)}</h2><p>${esc(due.slice(0, 3).map((x) => x.word).join(' · '))}${due.length > 3 ? ' …' : ''}</p><button class="primary" data-recall-start>${esc(c.recallName)} →</button></section>`
      : `<section class="empty">${scene('completion', { size: 'medium' })}<h2>${c.allDone}</h2><p>${esc(c.allDoneNote)}</p><a class="outline" href="${link('language')}">${c.language} →</a></section>${continuationShelf(ctx, 3)}`;
    /* What actually happened. Real counts only: what was reviewed in this
       sitting and what is still waiting. No score, no streak, no mastery. */
    const done = `<section class="empty recall-done">${scene('completion', { size: 'medium' })}<h2>${esc(c.allDone)}</h2><p>${reviewed} ${esc(c.vocabularyWordCount)}${due.length ? ` · ${due.length} ${esc(c.vocabularyDueState)}` : ''}</p><p class="meta">${esc(c.allDoneNote)}</p><div class="button-row">${due.length ? `<button class="primary" data-recall-start>${esc(c.vocabularyContinueReview)} →</button>` : ''}<a class="outline" href="${link('language')}">${c.language} →</a></div></section>`;
    root.innerHTML = `${practiceReturn(c, 'recall')}${pageIntro({ title: c.recallTitle, note: c.recallTruth, eyebrow: c.recallName, compact: true })}${
      stage === 'landing' ? landing : current ? card : done
    }`;
    /* A kept word already carries the sentence it came from, which is exactly
       the context the shared explanation needs. Without this, the collection
       is a list to reread rather than something a learner can question - the
       same gap Grammar had. */
    root.querySelectorAll('[data-word-explain]').forEach((button) => {
      button.onclick = () => {
        const entry = items.find((x) => x.word === button.dataset.wordExplain);
        if (!entry?.source_fragment) return;
        const kept = memory.value.keptLanguage?.[entry.word];
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
    root.querySelector('[data-recall-start]')?.addEventListener('click', () => {
      stage = 'card';
      revealed = false;
      paint(true);
    });
    root.querySelector('[data-reveal]')?.addEventListener('click', () => {
      revealed = true;
      paint(true);
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
          const grade = () =>
            ctx.mutate(() =>
              api.reviewLibraryVocabulary(current.word, button.dataset.grade),
            );
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
              const updated = await api.libraryVocabulary();
              if (!alive()) return;
              items = updated.items || [];
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
    if (moveFocus)
      focusRegion(root.querySelector('.review-prompt h2, .review-prompt blockquote, .empty h2'));
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

export function vocabularyInteractionItems(view, { feedCards = [], visibleItems = [], savedCards = [], studyItems = [] } = {}) {
  if (view === 'feed') return feedCards;
  if (view === 'collection' || view === 'collection-list') return visibleItems;
  if (view === 'saved' || view === 'overview') return savedCards;
  if (view === 'study') return studyItems;
  return [];
}

export async function renderLanguage(root, ctx) {
  if (ctx.location.intent === 'recall') return renderRecallLanguage(root, ctx);
  const { api, c, language, support, alive } = ctx;
  const copy = vocabularyCopy(c, support);
  const pinyinAllowed = language !== 'zh' || ctx.profile.pinyin !== 'off';
  const results = await Promise.allSettled([
    api.libraryVocabulary(),
    api.vocabularyLibraryCollections(language),
    api.dailyVocabularyFeed(language),
  ]);
  if (!alive()) return;

  let savedData = results[0].status === 'fulfilled' ? results[0].value : { items: [], summary: {} };
  let collections = results[1].status === 'fulfilled' ? results[1].value.items || [] : [];
  let feedCards = results[2].status === 'fulfilled' ? results[2].value.items || [] : [];
  const savedError = results[0].status === 'rejected';
  const collectionError = results[1].status === 'rejected';
  const feedError = results[2].status === 'rejected';
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

  const refreshSavedCards = () => {
    savedCards = (savedData.items || []).map((item) =>
      vocabularyCardFromSavedItem(item, language, support, pinyinAllowed),
    );
  };
  refreshSavedCards();

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

  /* Vocabulary home, as the design draws it (D-059 Phase 6, Screens part 4
     section 18): the domain tile, what the learner has kept and mastered, what
     is due, their collections, and the way to everything saved. Every figure
     is read from the learner's own saved vocabulary; a collection's tier has
     no source yet and says so rather than inventing one (GAP-020). */
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const collectionTile = (collection) => {
    const progress = collection.progress || {};
    const learned = Number(progress.learned_count) || 0;
    const total = Number(collection.item_count) || 0;
    const percent = total ? Math.round((learned / total) * 100) : 0;
    return `<button type="button" class="vocab-collection" data-vocabulary-collection="${esc(collection.id)}"><span class="vocab-collection__head"><strong>${esc(collection.title || '')}</strong><span class="ds-label vocab-collection__tier" title="${esc(r.bookSoon)}">${esc(r.vocabTier)} —</span></span><span class="progress-bar"${percent ? '' : ' data-unavailable'}><span style="width:${percent}%"></span></span><span class="ds-data vocab-collection__count">${esc(learned)} / ${esc(total)}</span></button>`;
  };
  const overview = () => {
    const dueItems = savedCards.filter((item) => item.due);
    const saved = stateCount('saved');
    const mastered = stateCount('mastered');
    const preview = dueItems
      .slice(0, 3)
      .map((item) => item.headword)
      .join(' · ');
    const due = dueItems.length
      ? `<div class="vocab-due"><div><strong>${esc(dueItems.length)} ${esc(c.vocabularyWordCount)}</strong><small>${esc(preview)}${dueItems.length > 3 ? ' …' : ''}</small></div><button type="button" class="primary" data-vocabulary-continue>${esc(c.vocabularyContinueReview)}</button></div>`
      : saved
        ? `<div class="state-panel state-panel--empty">${icon('check-circle', { size: 20, filled: true })}<div><strong>${esc(c.allDone)}</strong><p>${esc(c.allDoneNote)}</p></div></div>`
        : `<div class="state-panel state-panel--empty">${icon('cards', { size: 22 })}<div><strong>${esc(c.noWords)}</strong><p>${esc(c.noWordsNote)}</p></div><a class="primary" href="${esc(link('practice', { intent: 'reading' }))}">${icon('book-open', { size: 16 })}<span>${esc(c.readingName)}</span></a></div>`;
    const collectionsBlock = collectionError
      ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-vocabulary-retry="collections">${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
      : `<div class="vocab-collections">${collections
          .slice(0, 2)
          .map(collectionTile)
          .join('')}<button type="button" class="vocab-collection vocab-collection--browse" data-vocabulary-library>${icon('plus', { size: 20 })}<span>${esc(r.vocabBrowseCollections)}</span></button></div>${
          collections.length ? '' : `<p class="vocab-note">${esc(c.vocabularyLibraryEmpty)}</p>`
        }`;
    const row = (attribute, name, label, count) =>
      `<button type="button" class="vocab-row" ${attribute}>${icon(name, { size: 18 })}<span>${esc(label)}</span><span class="ds-data">${esc(count)}</span>${icon('caret-right', { size: 17 })}</button>`;
    return `<section class="vocab-home"><header class="vocab-home__head"><span class="domain-tile" data-domain="vocabulary" aria-hidden="true">${icon('cards', { size: 21 })}</span><div class="vocab-home__title"><h1>${esc(c.vocabularyTitle)}</h1><p class="ds-label">${esc(saved)} ${esc(c.vocabularySavedCount)} · ${esc(mastered)} ${esc(c.vocabularyMasteredCount)}</p></div>${
      dueItems.length
        ? `<span class="chip vocab-home__due" data-domain="vocabulary">${icon('cards', { size: 14, filled: true })}${esc(dueItems.length)} ${esc(c.vocabularyDueState)}</span>`
        : ''
    }</header><div class="vocab-home__body">${due}<section class="vocab-block"><span class="ds-label">${esc(r.vocabYourCollections)}</span>${collectionsBlock}</section>${row('data-vocabulary-manage', 'bookmark-simple', r.vocabSavedWords, saved)}${
      feedCards.length ? row('data-vocabulary-feed', 'sparkle', c.vocabularyFeedTitle, feedCards.length) : ''
    }${
      savedError
        ? `<div class="state-panel" data-tone="error" role="alert">${icon('warning-circle', { size: 20 })}<div><strong>${esc(c.unavailable)}</strong></div><button type="button" class="outline" data-vocabulary-retry="saved">${icon('arrow-counter-clockwise', { size: 16 })}<span>${esc(c.retry)}</span></button></div>`
        : ''
    }</div></section>`;
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
    visibleItems = [...filtered].sort((left, right) => {
      if (sort === 'alpha') return String(left.headword).localeCompare(String(right.headword));
      if (sort === 'level') return vocabularyLevelOrder(left.level) - vocabularyLevelOrder(right.level) || String(left.headword).localeCompare(String(right.headword));
      if (sort === 'due') return Number(Boolean(right.due)) - Number(Boolean(left.due)) || String(left.headword).localeCompare(String(right.headword));
      return 0;
    });
    const filterNames = ['all', 'new', 'learning', 'due', 'mastered', 'saved'];
    const filterCopy = { all: 'vocabularyFilterAll', new: 'vocabularyFilterNew', learning: 'vocabularyFilterLearning', due: 'vocabularyFilterDue', mastered: 'vocabularyFilterMastered', saved: 'vocabularyFilterSaved' };
    const filters = filterNames.map((name) => `<button class="vocabulary-filter ${filter === name ? 'is-active' : ''}" data-vocabulary-filter="${name}" aria-pressed="${filter === name}">${esc(c[filterCopy[name]])}</button>`).join('');
    const levelFilters = collectionLevels.length
      ? `<div class="vocabulary-level-filter" role="group" aria-label="${esc(c.vocabularyLevelFilter || c.vocabularyFilter)}"><span class="vocabulary-level-filter__label">${esc(c.vocabularyLevelFilter || c.vocabularyFilter)}</span><div class="vocabulary-filter-row">${[['all', c.vocabularyFilterAll], ...collectionLevels.map((level) => [level, level])].map(([name, label]) => `<button class="vocabulary-filter ${levelFilter === name ? 'is-active' : ''}" data-vocabulary-level-filter="${esc(name)}" aria-pressed="${levelFilter === name}">${esc(label)}</button>`).join('')}</div></div>`
      : '';
    const sortOptions = [['recommended', c.vocabularySortRecommended], ['alpha', c.vocabularySortAlpha], ['level', c.vocabularySortLevel], ['due', c.vocabularySortDue]].map(([value, label]) => `<option value="${value}" ${sort === value ? 'selected' : ''}>${esc(label)}</option>`).join('');
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

  const feedView = () => `${pageIntro({ title: c.vocabularyFeedTitle, note: c.vocabularyFeedNote, eyebrow: c.vocabularyTitle, compact: true })}<button class="quiet vocabulary-back" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button>${feedError ? `<p class="notice" role="alert">${esc(c.unavailable)} <button data-vocabulary-retry="feed">${esc(c.retry)}</button></p>` : feedCards.length ? renderVocabularyFeedCarousel(copy, feedCards, { limit: 5, full: true }) : `<section class="empty"><h2>${esc(c.vocabularyFeedEmpty)}</h2></section>`}`;

  const studyView = () => {
    const card = studyItems[studyIndex];
    if (!card) return `<section class="empty"><h2>${esc(c.noWords)}</h2></section>`;
    return `${pageIntro({ title: c.vocabularyStudy, note: c.vocabularyOverviewNote, eyebrow: c.vocabularyTitle, compact: true })}<div class="vocabulary-study-toolbar"><button class="quiet" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button><span>${studyIndex + 1} / ${studyItems.length}</span></div><section class="vocabulary-study-layout">${renderVocabularyStudyCard(copy, card, { index: studyIndex })}<nav class="vocabulary-study-nav"><button class="outline" data-study-prev ${studyIndex === 0 ? 'disabled' : ''}>←</button><button class="primary" data-study-next ${studyIndex >= studyItems.length - 1 ? 'disabled' : ''}>${studyIndex >= studyItems.length - 1 ? c.allDone : c.nextLine} →</button></nav></section>`;
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
    return `<section class="vocab-collection-page"><button type="button" class="icon-button vocab-back" data-vocabulary-back aria-label="${esc(c.vocabularyBackOverview)}">${icon('caret-right', { size: 20, className: 'is-flipped' })}</button><header class="vocab-collection__hero"><span class="vocab-collection__art">${contentCover({ id: String(collection.id || collection.title || ''), title: collection.title || '', material: 'collection' })}</span><div class="vocab-collection__copy"><div class="vocab-collection__chips"><span class="chip vocab-tier">${esc(r.vocabTier)} —</span>${level ? `<span class="chip">${esc(level)}</span>` : ''}</div><h1 lang="${esc(language)}">${esc(collection.title || c.vocabularyLibraryTitle)}</h1><div class="vocab-collection__progress"><span class="progress-bar"${percent ? '' : ' data-unavailable'}><span style="width:${percent}%"></span></span><span class="ds-data">${esc(learned)} / ${esc(total)}</span></div><div class="vocab-collection__actions"><button type="button" class="primary" data-vocabulary-collection-study>${icon('play', { size: 16, filled: true })}<span>${esc(c.vocabularyContinueReview)}</span></button><button type="button" class="icon-button" data-vocabulary-shuffle aria-label="${esc(r.vocabShuffle)}">${icon('shuffle', { size: 19 })}</button></div></div></header><div class="vocab-collection__body"><div class="vocab-words__head"><span class="ds-label">${esc(r.vocabWordsLabel)}</span><button type="button" class="chip vocab-words__filter" data-vocabulary-not-mastered aria-pressed="${notMastered}">${icon('funnel', { size: 13 })}<span>${esc(r.vocabNotMastered)}</span></button></div>${
      shown.length
        ? `<div class="vocab-words">${shown.map(wordTile).join('')}</div>`
        : `<div class="state-panel state-panel--empty">${icon('cards', { size: 20 })}<div><strong>${esc(c.vocabularyNoMatches)}</strong></div></div>`
    }${
      words.length > shown.length
        ? `<button type="button" class="vocab-show-all" data-vocabulary-show-all>${esc(String(r.vocabShowAll).replace('{n}', String(words.length)))}${icon('caret-down', { size: 16 })}</button>`
        : ''
    }</div></section>`;
  };
  const collectionView = () => management(activeCollection?.title || c.vocabularyLibraryTitle, `${activeCollection?.progress?.learned_count || 0} / ${activeCollection?.item_count || 0} ${c.vocabularyWordCount}`, true);

  const paint = () => {
    if (!alive()) return;
    root.innerHTML = view === 'overview' ? overview() : view === 'library' ? libraryView() : view === 'saved' ? management(c.vocabularyManage, c.vocabularyOverviewNote, true) : view === 'collection' ? collectionDetail() : view === 'collection-list' ? collectionView() : view === 'feed' ? feedView() : studyView();
    bind();
  };

  const setStudy = (items, index = 0) => {
    studyItems = items;
    studyIndex = Math.max(0, Math.min(index, items.length - 1));
    returnView = view === 'study' ? returnView : view;
    view = 'study';
    paint();
  };

  const openCollection = async (id, params = {}) => {
    const requestId = ++collectionRequest;
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
      if (!alive()) return;
      root.innerHTML = `<p class="notice" role="alert">${esc(error.message || c.unavailable)} <button data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button></p>`;
      bind();
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

  const bind = () => {
    root.querySelectorAll('[data-vocabulary-manage]').forEach((button) => (button.onclick = () => { activeItems = savedCards; query = ''; filter = 'all'; levelFilter = 'all'; sort = 'recommended'; view = 'saved'; paint(); }));
    root.querySelectorAll('[data-vocabulary-library]').forEach((button) => (button.onclick = () => { view = 'library'; paint(); }));
    root.querySelectorAll('[data-vocabulary-feed]').forEach((button) => (button.onclick = () => { view = 'feed'; paint(); }));
    root.querySelectorAll('[data-vocabulary-collection]').forEach((button) => (button.onclick = () => openCollection(button.dataset.vocabularyCollection)));
    root.querySelectorAll('[data-vocabulary-back]').forEach((button) => (button.onclick = () => { view = view === 'study' ? returnView : view === 'collection-list' ? 'collection' : 'overview'; paint(); }));
    root.querySelector('[data-vocabulary-not-mastered]')?.addEventListener('click', () => { notMastered = !notMastered; paint(); });
    root.querySelector('[data-vocabulary-show-all]')?.addEventListener('click', () => { view = 'collection-list'; paint(); });
    root.querySelector('[data-vocabulary-collection-study]')?.addEventListener('click', () => { if (visibleItems.length) setStudy(visibleItems); });
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
    root.querySelector('[data-vocabulary-continue]')?.addEventListener('click', () => setStudy(savedCards.filter((card) => card.due)));
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
    root.querySelectorAll('[data-vocabulary-filter]').forEach((button) => (button.onclick = () => { filter = button.dataset.vocabularyFilter; paint(); }));
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
    root.querySelector('[data-vocabulary-sort]')?.addEventListener('change', (event) => { sort = event.target.value; paint(); });
    const interactionPool = () => vocabularyInteractionItems(view, { feedCards, visibleItems, savedCards, studyItems });
    root.querySelectorAll('[data-vocabulary-study]').forEach((button) => (button.onclick = () => { const index = Number(button.dataset.vocabularyStudy); const pool = button.dataset.vocabularyStudySource === 'feed' ? feedCards.slice(0, 5) : interactionPool(); setStudy(pool, index); }));
    root.querySelectorAll('[data-vocabulary-save]').forEach((button) => (button.onclick = () => { const index = Number(button.dataset.vocabularySave); const source = button.closest('[data-vocabulary-source]')?.dataset.vocabularySource; const pool = source === 'feed' ? feedCards.slice(0, 5) : interactionPool(); saveCard(pool[index], source === 'feed' ? 'feed' : view === 'collection' ? 'collection' : 'manual'); }));
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
    bindVocabularyFeedCarousel(root);
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
