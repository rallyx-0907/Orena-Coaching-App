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
import { renderVocabularyCard } from './vocabulary-card.js';
import {
  renderVocabularyCollectionCard,
  renderVocabularyBrowseCard,
  renderVocabularyFeedPreview,
  renderVocabularyRow,
  renderVocabularyStudyCard,
  compactSupportMeaning,
  supportMeaning,
  vocabularyKeepPayload,
  vocabularyStatus,
} from './vocabulary-experience.js';
import { openUnderstanding, judgementLabel } from './understanding.js';
import {
  writingReview,
  writingReviewFailure,
  writingReviewWaiting,
  shownIssues,
} from './writing-review.js';
import {bindRevisionWorkbench} from './revision-workbench.js';
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
  root.innerHTML = `<div class="back-row"><a href="${hasSource ? sourceLink(id) : link('practice')}">← ${hasSource ? c.returnLabel : c.practice}</a></div>${pageIntro({ title, note: hasSource ? prompt : c.writingNote, eyebrow: c.writingName })}<section class="learning-workspace writing-workspace" data-workspace="activity"><div class="workspace-activity"><form id="expressionForm" class="writing-sheet"><div class="draft-elsewhere" data-draft-elsewhere role="status" hidden></div><label class="sr-only" for="expressionText">${c.respond}</label><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="10" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id] || series?.latest.text || '')}</textarea><div class="expression-tools">${draftStatus(ctx)}<span class="meta" data-character-count aria-live="polite"></span><label class="review-target">${c.reviewTarget}<select name="target"><option value="">${c.chooseTarget}</option>${levels.map((level) => `<option value="${esc(level)}">${esc(level)}</option>`).join('')}</select></label><button class="primary">${c.review} ↗</button></div><div class="writing-task"><span class="writing-task__label"><label for="writingTask">${esc(c.writingTask)}</label>${hint({ text: c.writingTaskNote })}</span><input id="writingTask" name="task" maxlength="240" autocomplete="off" placeholder="${esc(c.writingTaskPlaceholder)}" value="${esc(memory.value.expressions[`${id}::task`] || '')}"></div></form></div><section class="workspace-result writing-result" aria-label="${esc(c.review)}"><div class="workspace-result__bar"><button type="button" class="quiet" data-back-to-writing>← ${esc(c.reviewBack)}</button></div><div class="workspace-result__scroll" id="writingFeedback" aria-live="polite">${writingReviewWaiting(c)}</div></section></section><div class="workspace-secondary"><aside class="expression-context">${excerpt ? `<small>${c.expressionContext}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote><a class="quiet" href="${sourceLink(id)}">${c.returnLabel} ↗</a>` : `<div class="expression-starters"><h2>${c.expressionStarters}</h2><p class="meta">${c.expressionStarterNote}</p>${invitations.map((item) => `<a href="${link('expression', { id: 'story:' + item.id })}"><small>${c.generated}</small><strong lang="${language}">${esc(item.prompt)}</strong><span>${c.usePrompt} ↗</span></a>`).join('')}</div>`}</aside><section class="revision-history" data-revisions></section></div>${continuationShelf(ctx, 2)}`;
  /* The activity and its result share one frame. Wide screens show both at
     once, so the result is beside the writing rather than below it. Narrow
     screens take them one frame at a time, and the learner is placed at the
     start of the result frame instead of halfway down the page. */
  const { showResult } = workspaceFrames(
    root.querySelector('.learning-workspace'),
    {
      back: root.querySelector('[data-back-to-writing]'),
      focus: () => root.querySelector('#expressionText'),
      result: root.querySelector('#writingFeedback'),
    },
  );
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
  // Reopened, the latest review is already there: the piece comes back with
  // what was said about it, not as a blank result frame.
  if (series?.latest && Array.isArray(series.latest.issues))
    presentReview(series.latest, String(series.latest.text || ''));
  /* Kept with the account when this deployment keeps work there; on this
     device always. The status says which is true, and a version changed on
     another device is shown for the learner to choose, never merged. */
  const box = root.querySelector('#expressionText');
  const taskInput = root.querySelector('[name=task]');
  const elsewhereNode = root.querySelector('[data-draft-elsewhere]');
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
  box.oninput = (event) => {
    memory.write(id, event.target.value);
    memory.enter({ id, title, intent: 'writing', excerpt });
    refreshDraftStatus(root.querySelector('[data-draft-status]'), ctx);
    sync.edit(draftNow());
    updateCount();
  };
  root.querySelector('form').onsubmit = async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    // The primary action by role: a hint beside the draft status is also a
    // button inside this form and must never be the one that gets disabled.
    const button = form.querySelector('button.primary'),
      feedback = root.querySelector('#writingFeedback');
    button.disabled = true;
    feedback.textContent = c.loading;
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
      const result = await ctx.mutate(() =>
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
          parent_essay_id: parentId,
        }),
      );
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
      });
      paintRevisions();
      presentReview(result, text);
    } catch (error) {
      if (alive()) {
        feedback.innerHTML = writingReviewFailure(c, error);
        const retry = feedback.querySelector('[data-retry-review]');
        if (retry) retry.onclick = () => form.requestSubmit();
      }
    } finally {
      if (alive()) button.disabled = false;
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
  const definition = String(item.definition || '').trim();
  const translation = String(item.translation_vi || '').trim();
  if (definition) meanings.push({ language, text: definition });
  if (translation) meanings.push({ language: 'vi', text: translation });
  const kind = String(item.source_kind || '').trim();
  const fragment = String(item.source_fragment || '').trim();
  const card = {
    identity: { language, normalized: String(item.word || '').toLowerCase() },
    headword: item.word,
    meanings,
    source_encounters: kind && fragment ? [{ kind, fragment }] : [],
  };
  const pronunciation = String(item.phonetic || '').trim();
  if (pronunciation && pinyinAllowed) card.pronunciation = pronunciation;
  if (Array.isArray(item.examples)) card.examples = item.examples;
  for (const field of ['level', 'framework', 'topic']) {
    if (item[field]) card[field] = item[field];
  }
  if (item.orthography) card.orthography = item.orthography;
  return card;
}
async function renderRecallLanguage(root, ctx) {
  const { api, c, language, alive, memory } = ctx;
  const data = await api.libraryVocabulary();
  if (!alive()) return;
  let items = data.items || [],
    recalling = ctx.location.intent === 'recall',
    revealed = false;
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
    root.innerHTML = `${recalling ? practiceReturn(c, 'recall') : ''}${pageIntro({ title: recalling ? c.recallTitle : c.wordsTitle, note: recalling ? c.recallTruth : c.wordsIntro, eyebrow: recalling ? c.recallName : c.language, scene: recalling ? undefined : 'remembering', compact: recalling })}${items.length ? `<div class="language-summary"><span>${due.length} ${c.due}</span>${due.length && !recalling ? `<button class="primary" data-recall>${c.recallName} →</button>` : ''}</div>` : ''}${recalling ? (current ? `<section class="recall-moment" data-shape="${shape}"><small>${esc(c[`recallAsk_${shape}`])}</small>${
                shape === 'in_context' && gap
                  ? `<blockquote class="recall-gap" lang="${language}">${withheld(revealed ? esc(current.word) : '&nbsp;'.repeat(3))}</blockquote>`
                  : `<h2 lang="${language}">${revealed || shape !== 'say' ? esc(current.word) : '···'}</h2>${current.phonetic && revealed && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(current.phonetic)}</p>` : ''}${shape === 'say' && !revealed ? `<p lang="${esc(ctx.support)}">${esc(current.definition || current.translation_vi || '')}</p>` : ''}${shape !== 'in_context' && current.source_fragment ? `<blockquote class="${gap && !revealed ? 'recall-gap' : ''}" lang="${language}">${gap && !revealed ? withheld('&nbsp;'.repeat(3)) : esc(current.source_fragment)}</blockquote>` : ''}`
              }${
                revealed
                  ? `${shape === 'say' ? '' : `<p lang="${esc(ctx.support)}">${esc(current.definition || current.translation_vi || '')}</p>`}${keptProvenance(c, keptNow)}${shape === 'reuse' ? `<a class="outline" href="${link('expression')}">${esc(c.recallUseInWriting)} ↗</a>` : ''}<div class="button-row"><button class="outline" data-grade="again">${c.again}</button><button class="primary" data-grade="got_it">${c.gotIt}</button></div><p class="meta">${c.recallTruth}</p>`
                  : `<button class="primary" data-reveal>${esc(c[`recallReveal_${shape}`])} →</button>`
              }<p role="status" data-recall-status></p></section>` : `<section class="empty">${scene('completion', { size: 'medium' })}<h2>${c.allDone}</h2><p>${esc(c.allDoneNote)}</p><a class="outline" href="${link('language')}">${c.language} →</a></section>${continuationShelf(ctx, 3)}`) : items.length ? `<section class="word-collection language-cabinet">${items
              .map((x) => {
                const pinyinAllowed = language !== 'zh' || ctx.profile.pinyin !== 'off';
                const card = vocabularyCardFromLibraryItem(x, language, { pinyinAllowed });
                return renderVocabularyCard(c, card, {
                  before: keptProvenance(c, memory.value.keptLanguage?.[x.word]) || `<small>${esc(x.focus_note || c.sourceContext)}</small>`,
                  after: x.source_fragment ? `<button class="quiet" data-word-explain="${esc(x.word)}">${esc(c.lookCloser)} ↗</button>` : '',
                });
              })
              .join('')}</section>` : `<section class="empty">${scene('empty', { size: 'medium' })}<h2>${c.noWords}</h2><p>${c.noWordsNote}</p><a class="primary" href="#/">${c.discover} ↗</a></section>`}`;
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
    root.querySelector('[data-recall]')?.addEventListener('click', () => {
      recalling = true;
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
      focusRegion(root.querySelector('.recall-moment h2, .empty h2'));
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
  const normalized = String(level || '').toUpperCase();
  const match = normalized.match(/^(?:HSK)?([1-6])$/);
  if (match) return Number(match[1]);
  return { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 }[normalized] || 0;
}

export function vocabularyInteractionItems(view, { feedCards = [], visibleItems = [], savedCards = [], studyItems = [] } = {}) {
  if (view === 'feed') return feedCards;
  if (view === 'collection') return visibleItems;
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
  let sort = 'recommended';

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
  const statusSummary = `<div class="vocabulary-summary-metrics"><div><strong>${stateCount('saved')}</strong><span>${esc(c.vocabularySavedCount)}</span></div><div><strong>${stateCount('learning')}</strong><span>${esc(c.vocabularyLearningCount)}</span></div><div class="is-due"><strong>${stateCount('due')}</strong><span>${esc(c.vocabularyDueCount)}</span></div><div><strong>${stateCount('mastered')}</strong><span>${esc(c.vocabularyMasteredCount)}</span></div></div>`;

  const updateCollectionCards = (items) => items.map((card) => {
    const saved = cardByWord(card.headword);
    return saved ? { ...card, saved: true, review_stage: saved.review_stage, due: saved.due, successful_recalls: saved.successful_recalls, lapse_count: saved.lapse_count } : card;
  });

  const overview = () => {
    const dueItems = savedCards.filter((item) => item.due);
    const recent = [...savedCards].sort((a, b) => String(b.added_at || '').localeCompare(String(a.added_at || ''))).slice(0, 5);
    const libraryBody = collectionError
      ? `<p class="notice" role="alert">${esc(c.unavailable)} <button data-vocabulary-retry="collections">${esc(c.retry)}</button></p>`
      : collections.length
        ? `<div class="vocabulary-collection-grid">${collections.map((collection, index) => renderVocabularyCollectionCard(copy, collection, { index })).join('')}</div>`
        : `<p class="meta">${esc(c.vocabularyLibraryEmpty)}</p>`;
    const feedBody = feedError
      ? `<p class="notice" role="alert">${esc(c.unavailable)} <button data-vocabulary-retry="feed">${esc(c.retry)}</button></p>`
      : feedCards.length
        ? `<div class="vocabulary-feed-preview">${feedCards.slice(0, 4).map((card, index) => renderVocabularyFeedPreview(copy, card, { index })).join('')}</div>`
        : `<p class="meta">${esc(c.vocabularyFeedEmpty)}</p>`;
    return `${pageIntro({ title: c.vocabularyTitle, note: c.vocabularyOverviewNote, eyebrow: c.language, scene: 'remembering' })}<section class="vocabulary-overview-hero"><div>${statusSummary}<div class="button-row">${dueItems.length ? `<button class="primary" data-vocabulary-continue>${esc(c.vocabularyContinueReview)} →</button>` : ''}<button class="outline" data-vocabulary-manage>${esc(c.vocabularyManage)}</button></div></div><div class="vocabulary-overview-callout"><small>${esc(c.vocabularyDueCount)}</small><strong>${dueItems.length ? esc(dueItems[0].headword) : esc(c.allDone)}</strong><p>${dueItems.length ? esc(compactSupportMeaning(dueItems[0], support)) : esc(c.allDoneNote)}</p></div></section><section class="vocabulary-overview-section"><div class="section-head"><div><small>${esc(c.vocabularyLibraryTitle)}</small><h2>${esc(c.vocabularyAllWords)}</h2></div><button class="quiet" data-vocabulary-library>${esc(c.vocabularyOpenLibrary)} →</button></div>${libraryBody}</section><section class="vocabulary-overview-section"><div class="section-head"><div><small>${esc(c.vocabularyFeedTitle)}</small><h2>${esc(c.vocabularyOpenFeed)}</h2></div><button class="quiet" data-vocabulary-feed>${esc(c.vocabularyOpenFeed)} →</button></div>${feedBody}</section>${recent.length ? `<section class="vocabulary-overview-section vocabulary-recent"><div class="section-head"><h2>${esc(c.vocabularyRecent)}</h2><button class="quiet" data-vocabulary-manage>${esc(c.vocabularyManage)} →</button></div><div class="vocabulary-row-list">${recent.map((card) => renderVocabularyRow(copy, card, { index: savedCards.indexOf(card) })).join('')}</div></section>` : ''}${savedError ? `<p class="notice" role="alert">${esc(c.unavailable)} <button data-vocabulary-retry="saved">${esc(c.retry)}</button></p>` : ''}`;
  };

  const management = (title, note = '', withBack = false) => {
    const source = activeItems;
    const filtered = source.filter((card) => vocabularyStatusMatches(card, filter) && `${card.headword} ${supportMeaning(card, support)} ${card.level || ''} ${card.framework || ''}`.toLowerCase().includes(query.toLowerCase()));
    visibleItems = [...filtered].sort((left, right) => {
      if (sort === 'alpha') return String(left.headword).localeCompare(String(right.headword));
      if (sort === 'level') return vocabularyLevelOrder(left.level) - vocabularyLevelOrder(right.level) || String(left.headword).localeCompare(String(right.headword));
      if (sort === 'due') return Number(Boolean(right.due)) - Number(Boolean(left.due)) || String(left.headword).localeCompare(String(right.headword));
      return 0;
    });
    const filterNames = ['all', 'new', 'learning', 'due', 'mastered', 'saved'];
    const filterCopy = { all: 'vocabularyFilterAll', new: 'vocabularyFilterNew', learning: 'vocabularyFilterLearning', due: 'vocabularyFilterDue', mastered: 'vocabularyFilterMastered', saved: 'vocabularyFilterSaved' };
    const filters = filterNames.map((name) => `<button class="vocabulary-filter ${filter === name ? 'is-active' : ''}" data-vocabulary-filter="${name}" aria-pressed="${filter === name}">${esc(c[filterCopy[name]])}</button>`).join('');
    const sortOptions = [['recommended', c.vocabularySortRecommended], ['alpha', c.vocabularySortAlpha], ['level', c.vocabularySortLevel], ['due', c.vocabularySortDue]].map(([value, label]) => `<option value="${value}" ${sort === value ? 'selected' : ''}>${esc(label)}</option>`).join('');
    const results = visibleItems.length
      ? view === 'collection'
        ? `<section class="vocabulary-browse-grid">${visibleItems.map((card, index) => renderVocabularyBrowseCard(copy, card, { index, source: 'collection' })).join('')}</section>`
        : `<section class="vocabulary-row-list vocabulary-saved-management">${visibleItems.map((card, index) => renderVocabularyRow(copy, card, { index })).join('')}</section>`
      : `<section class="empty vocabulary-empty"><h2>${esc(c.vocabularyNoMatches)}</h2></section>`;
    return `${pageIntro({ title, note, eyebrow: c.vocabularyTitle, compact: true })}${withBack ? `<button class="quiet vocabulary-back" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button>` : ''}<div class="vocabulary-management-toolbar"><label><span class="sr-only">${esc(c.vocabularySearch)}</span><input type="search" data-vocabulary-search value="${esc(query)}" placeholder="${esc(c.vocabularySearch)}"></label><div class="vocabulary-management-options"><label class="vocabulary-sort-control"><span>${esc(c.vocabularySort)}</span><select data-vocabulary-sort aria-label="${esc(c.vocabularySort)}">${sortOptions}</select></label><div class="vocabulary-filter-row" role="group" aria-label="${esc(c.vocabularyFilter)}">${filters}</div></div></div><p class="meta" role="status">${esc(visibleItems.length)} ${esc(c.vocabularyWordCount)}</p>${results}`;
  };

  const feedView = () => `${pageIntro({ title: c.vocabularyFeedTitle, note: c.vocabularyFeedNote, eyebrow: c.vocabularyTitle, compact: true })}<button class="quiet vocabulary-back" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button>${feedError ? `<p class="notice" role="alert">${esc(c.unavailable)} <button data-vocabulary-retry="feed">${esc(c.retry)}</button></p>` : feedCards.length ? `<section class="vocabulary-feed-preview vocabulary-feed-preview--full">${feedCards.map((card, index) => renderVocabularyFeedPreview(copy, card, { index })).join('')}</section>` : `<section class="empty"><h2>${esc(c.vocabularyFeedEmpty)}</h2></section>`}`;

  const studyView = () => {
    const card = studyItems[studyIndex];
    if (!card) return `<section class="empty"><h2>${esc(c.noWords)}</h2></section>`;
    return `${pageIntro({ title: c.vocabularyStudy, note: c.vocabularyOverviewNote, eyebrow: c.vocabularyTitle, compact: true })}<div class="vocabulary-study-toolbar"><button class="quiet" data-vocabulary-back>${esc(c.vocabularyBackOverview)}</button><span>${studyIndex + 1} / ${studyItems.length}</span></div><section class="vocabulary-study-layout">${renderVocabularyStudyCard(copy, card, { index: studyIndex })}<nav class="vocabulary-study-nav"><button class="outline" data-study-prev ${studyIndex === 0 ? 'disabled' : ''}>←</button><button class="primary" data-study-next ${studyIndex >= studyItems.length - 1 ? 'disabled' : ''}>${studyIndex >= studyItems.length - 1 ? c.allDone : c.nextLine} →</button></nav></section>`;
  };

  const collectionView = () => management(activeCollection?.title || c.vocabularyLibraryTitle, `${activeCollection?.progress?.learned_count || 0} / ${activeCollection?.item_count || 0} ${c.vocabularyWordCount}`, true);

  const paint = () => {
    if (!alive()) return;
    root.innerHTML = view === 'overview' ? overview() : view === 'saved' ? management(c.vocabularyManage, c.vocabularyOverviewNote, true) : view === 'collection' ? collectionView() : view === 'feed' ? feedView() : studyView();
    bind();
  };

  const setStudy = (items, index = 0) => {
    studyItems = items;
    studyIndex = Math.max(0, Math.min(index, items.length - 1));
    returnView = view === 'study' ? returnView : view;
    view = 'study';
    paint();
  };

  const openCollection = async (id) => {
    try {
      const detail = await api.vocabularyLibraryCollection(id);
      if (!alive()) return;
      activeCollection = detail;
      activeItems = updateCollectionCards(detail.items || []);
      query = '';
      filter = 'all';
      sort = 'recommended';
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
    root.querySelectorAll('[data-vocabulary-manage]').forEach((button) => (button.onclick = () => { activeItems = savedCards; query = ''; filter = 'all'; sort = 'recommended'; view = 'saved'; paint(); }));
    root.querySelectorAll('[data-vocabulary-library]').forEach((button) => (button.onclick = () => root.querySelector('.vocabulary-collection-grid')?.scrollIntoView({ behavior: 'smooth', block: 'start' })));
    root.querySelectorAll('[data-vocabulary-feed]').forEach((button) => (button.onclick = () => { view = 'feed'; paint(); }));
    root.querySelectorAll('[data-vocabulary-collection]').forEach((button) => (button.onclick = () => openCollection(button.dataset.vocabularyCollection)));
    root.querySelectorAll('[data-vocabulary-back]').forEach((button) => (button.onclick = () => { view = view === 'study' ? returnView : 'overview'; paint(); }));
    root.querySelector('[data-vocabulary-continue]')?.addEventListener('click', () => setStudy(savedCards.filter((card) => card.due)));
    root.querySelector('[data-vocabulary-search]')?.addEventListener('input', (event) => { query = event.target.value; paint(); const input = root.querySelector('[data-vocabulary-search]'); input?.focus(); input?.setSelectionRange(query.length, query.length); });
    root.querySelectorAll('[data-vocabulary-filter]').forEach((button) => (button.onclick = () => { filter = button.dataset.vocabularyFilter; paint(); }));
    root.querySelector('[data-vocabulary-sort]')?.addEventListener('change', (event) => { sort = event.target.value; paint(); });
    const interactionPool = () => vocabularyInteractionItems(view, { feedCards, visibleItems, savedCards, studyItems });
    root.querySelectorAll('[data-vocabulary-study]').forEach((button) => (button.onclick = () => { const index = Number(button.dataset.vocabularyStudy); setStudy(interactionPool(), index); }));
    root.querySelectorAll('[data-vocabulary-save]').forEach((button) => (button.onclick = () => { const index = Number(button.dataset.vocabularySave); saveCard(interactionPool()[index], view === 'feed' ? 'feed' : view === 'collection' ? 'collection' : 'manual'); }));
    root.querySelectorAll('[data-study-flip]').forEach((button) => (button.onclick = () => { const card = root.querySelector('.vocabulary-study-card'); const front = root.querySelector('[data-study-front]'); const back = root.querySelector('[data-study-back]'); const showingBack = card.dataset.studyState === 'back'; card.dataset.studyState = showingBack ? 'front' : 'back'; front.hidden = !showingBack; back.hidden = showingBack; }));
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
