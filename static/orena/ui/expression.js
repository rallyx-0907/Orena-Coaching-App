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
  root.innerHTML = `<div class="back-row"><a href="${hasSource ? sourceLink(id) : link('practice')}">← ${hasSource ? c.returnLabel : c.practice}</a></div>${pageIntro({ title, note: hasSource ? prompt : c.writingNote, eyebrow: c.writingName })}<section class="learning-workspace writing-workspace" data-workspace="activity"><div class="workspace-activity"><form id="expressionForm" class="writing-sheet"><label class="sr-only" for="expressionText">${c.respond}</label><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="10" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id] || series?.latest.text || '')}</textarea><div class="expression-tools">${draftStatus(ctx)}<span class="meta" data-character-count aria-live="polite"></span><label class="review-target">${c.reviewTarget}<select name="target"><option value="">${c.chooseTarget}</option>${levels.map((level) => `<option value="${esc(level)}">${esc(level)}</option>`).join('')}</select></label><button class="primary">${c.review} ↗</button></div><div class="writing-task"><span class="writing-task__label"><label for="writingTask">${esc(c.writingTask)}</label>${hint({ text: c.writingTaskNote })}</span><input id="writingTask" name="task" maxlength="240" autocomplete="off" placeholder="${esc(c.writingTaskPlaceholder)}" value="${esc(memory.value.expressions[`${id}::task`] || '')}"></div></form></div><section class="workspace-result writing-result" aria-label="${esc(c.review)}"><div class="workspace-result__bar"><button type="button" class="quiet" data-back-to-writing>← ${esc(c.reviewBack)}</button></div><div class="workspace-result__scroll" id="writingFeedback" aria-live="polite">${writingReviewWaiting(c)}</div></section></section><div class="workspace-secondary"><aside class="expression-context">${excerpt ? `<small>${c.expressionContext}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote><a class="quiet" href="${sourceLink(id)}">${c.returnLabel} ↗</a>` : `<div class="expression-starters"><h2>${c.expressionStarters}</h2><p class="meta">${c.expressionStarterNote}</p>${invitations.map((item) => `<a href="${link('expression', { id: 'story:' + item.id })}"><small>${c.generated}</small><strong lang="${language}">${esc(item.prompt)}</strong><span>${c.usePrompt} ↗</span></a>`).join('')}</div>`}</aside><section class="revision-history" data-revisions></section></div>${continuationShelf(ctx, 2)}`;
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
  root.querySelector('textarea').oninput = (event) => {
    memory.write(id, event.target.value);
    memory.enter({ id, title, intent: 'writing', excerpt });
    refreshDraftStatus(root.querySelector('[data-draft-status]'), ctx);
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
export async function renderLanguage(root, ctx) {
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
              }<p role="status" data-recall-status></p></section>` : `<section class="empty">${scene('completion', { size: 'medium' })}<h2>${c.allDone}</h2><p>${esc(c.allDoneNote)}</p><a class="outline" href="${link('language')}">${c.language} →</a></section>${continuationShelf(ctx, 3)}`) : items.length ? `<section class="word-collection language-cabinet">${items.map((x) => `<article>${keptProvenance(c, memory.value.keptLanguage?.[x.word]) || `<small>${esc(x.focus_note || c.sourceContext)}</small>`}<h2 lang="${language}">${esc(x.word)}</h2>${x.phonetic && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(x.phonetic)}</p>` : ''}<blockquote lang="${language}">${esc(x.source_fragment || '')}</blockquote><details><summary>${c.meaning}</summary><p>${esc(x.definition || x.translation_vi || '')}</p></details>${x.source_fragment ? `<button class="quiet" data-word-explain="${esc(x.word)}">${esc(c.lookCloser)} ↗</button>` : ''}</article>`).join('')}</section>` : `<section class="empty">${scene('empty', { size: 'medium' })}<h2>${c.noWords}</h2><p>${c.noWordsNote}</p><a class="primary" href="#/">${c.discover} ↗</a></section>`}`;
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
