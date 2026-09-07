import {
  pageIntro,
  intentNavigation,
  continuationShelf,
  draftStatus,
  responseComposer,
  bindComposer,
  progressReporter,
} from './patterns.js';
import { esc, status, focusRegion } from './html.js';
import { openUnderstanding, judgementLabel } from './understanding.js';
import { writingReview, shownIssues } from './writing-review.js';
import { openRegisters } from './registers.js';
import { link, sourceLink } from '../product/intent.js';
import { patternsFor } from '../content/patterns.js';
import { contentFor } from '../content/texts.js';

export async function renderExpression(root, ctx) {
  const { c, language, api, memory, alive } = ctx,
    id = ctx.location.id || 'expression:free';
  const source =
    memory.value.continuation.find((x) => x.id === id) ||
    memory.value.imports.find((x) => x.id === id) ||
    contentFor(language).find((x) => `story:${x.id}` === id);
  const revisionsOf = () => memory.value.revisions?.[id] || [];
  // Continue the server's series across visits instead of starting a new one
  // every time the learner comes back to the same piece.
  let parentId =
    [...revisionsOf()].reverse().find((x) => x.essay_id)?.essay_id ?? null;
  const title = source?.title || c.freeTitle;
  const hasSource = source && !id.startsWith('expression:');
  const original = contentFor(language).find((x) => 'story:' + x.id === id);
  const excerpt =
    source?.excerpt ||
    original?.paragraphs?.[0] ||
    source?.text?.slice(0, 1200) ||
    '';
  const prompt = original?.prompt || c.responsePrompt;
  const invitations = contentFor(language).slice(0, 2);
  const levels = ctx.languageProfiles?.find(x => x.code === language)?.levels || [];
  root.innerHTML = `<div class="back-row"><a href="${hasSource ? sourceLink(id) : link('practice')}">← ${hasSource ? c.returnLabel : c.practice}</a></div><div class="expression-layout"><section class="expression-room">${pageIntro({ title, note: hasSource ? prompt : c.writingNote, eyebrow: c.writingName })}<form id="expressionForm"><label class="sr-only" for="expressionText">${c.respond}</label><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="10" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id] || '')}</textarea><div class="expression-tools">${draftStatus(ctx)}<span class="meta" data-character-count></span><label class="review-target">${c.reviewTarget}<select name="target" required><option value="">${c.chooseTarget}</option>${levels.map(level => `<option value="${esc(level)}">${esc(level)}</option>`).join('')}</select></label><button class="primary">${c.review} ↗</button></div><label class="writing-task"><span>${esc(c.writingTask)}</span><input name="task" maxlength="240" autocomplete="off" placeholder="${esc(c.writingTaskPlaceholder)}" value="${esc(memory.value.expressions[`${id}::task`] || '')}"><small>${esc(c.writingTaskNote)}</small></label></form><section id="writingFeedback" aria-live="polite"></section><section class="revision-history" data-revisions></section></section><aside class="expression-context">${excerpt ? `<small>${c.expressionContext}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote><a class="quiet" href="${sourceLink(id)}">${c.returnLabel} ↗</a>` : `<small>${c.expressionGuide}</small><p>${c.expressionGuideNote}</p><div class="expression-starters"><h2>${c.expressionStarters}</h2><p class="meta">${c.expressionStarterNote}</p>${invitations.map((item) => `<a href="${link('expression', { id: 'story:' + item.id })}"><small>${c.generated}</small><strong lang="${language}">${esc(item.prompt)}</strong><span>${c.usePrompt} ↗</span></a>`).join('')}</div>`}</aside></div>${continuationShelf(ctx, 2)}`;
  const paintRevisions = () => {
    const list = revisionsOf();
    const host = root.querySelector('[data-revisions]');
    if (!list.length) {
      host.innerHTML = '';
      return;
    }
    host.innerHTML = `<h2>${esc(c.revisionHistory)}</h2><p class="meta">${esc(c.revisionNote)}</p><ol class="revision-list">${list
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
  const updateCount = () => {
    root.querySelector('[data-character-count]').textContent =
      [...root.querySelector('textarea').value].length + ' ' + c.draftCount;
  };
  updateCount();
  paintRevisions();
  root.querySelector('textarea').oninput = (event) => {
    memory.write(id, event.target.value);
    memory.enter({ id, title, intent: 'writing', excerpt });
    root.querySelector('[data-draft-status]').textContent = memory.available
      ? c.draftSaved
      : c.memoryUnavailable;
    updateCount();
  };
  root.querySelector('form').onsubmit = async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button'),
      feedback = root.querySelector('#writingFeedback');
    button.disabled = true;
    feedback.textContent = c.loading;
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
          target_cefr: root.querySelector('[name=target]').value,
          learning_language: language,
          parent_essay_id: parentId,
        }),
      );
      if (!alive()) return;
      parentId = result.id;
      memory.recordRevision(id, {
        text,
        essay_id: Number.isInteger(result.id) ? result.id : null,
        revision_no: Number.isInteger(result.revision_no) ? result.revision_no : null,
        overall: Number.isFinite(result.overall) ? result.overall : null,
        level: typeof result.app_cefr === 'string' ? result.app_cefr : '',
      });
      paintRevisions();
      // Only show a finding whose wording is genuinely in what the learner
      // wrote, so a struck-through phrase is always one of their own.
      const corrections = shownIssues(result, text);
      feedback.innerHTML = writingReview(c, result, { language, text });
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
          });
        };
      });
    } catch {
      if (alive()) feedback.textContent = c.reviewUnavailable;
    } finally {
      if (alive()) button.disabled = false;
    }
  };
}
export async function renderLanguage(root, ctx) {
  const { api, c, language, alive } = ctx;
  const data = await api.libraryVocabulary();
  if (!alive()) return;
  let items = data.items || [],
    recalling = ctx.location.intent === 'recall',
    revealed = false;
  function paint(moveFocus = false) {
    if (!alive()) return;
    const due = items.filter((x) => x.due),
      current = due[0];
    root.innerHTML = `${pageIntro({ title: c.wordsTitle, note: c.wordsIntro, eyebrow: c.language })}${items.length ? `<div class="language-summary"><span>${due.length} ${c.due}</span>${due.length && !recalling ? `<button class="primary" data-recall>${c.recallName} →</button>` : ''}</div>` : ''}${recalling ? (current ? `<section class="recall-moment"><small>${c.recallName}</small><h2 lang="${language}">${esc(current.word)}</h2>${current.phonetic && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(current.phonetic)}</p>` : ''}<blockquote lang="${language}">${esc(current.source_fragment || '')}</blockquote>${revealed ? `<p>${esc(current.definition || current.translation_vi || '')}</p><div class="button-row"><button class="outline" data-grade="again">${c.again}</button><button class="primary" data-grade="got_it">${c.gotIt}</button></div><p class="meta">${c.recallTruth}</p>` : `<button class="primary" data-reveal>${c.showMeaning} →</button>`}<p role="status" data-recall-status></p></section>` : `<section class="empty"><h2>${c.allDone}</h2><a class="outline" href="${link('language')}">${c.language} →</a></section>${continuationShelf(ctx, 3)}`) : items.length ? `<section class="word-collection">${items.map((x) => `<article><small>${esc(x.focus_note || c.sourceContext)}</small><h2 lang="${language}">${esc(x.word)}</h2>${x.phonetic && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(x.phonetic)}</p>` : ''}<blockquote lang="${language}">${esc(x.source_fragment || '')}</blockquote><details><summary>${c.meaning}</summary><p>${esc(x.definition || x.translation_vi || '')}</p></details>${x.source_fragment ? `<button class="quiet" data-word-explain="${esc(x.word)}">${esc(c.lookCloser)} ↗</button>` : ''}</article>`).join('')}</section>` : `<section class="empty"><h2>${c.noWords}</h2><p>${c.noWordsNote}</p><a class="primary" href="#/">${c.discover} ↗</a></section>`}`;
    /* A kept word already carries the sentence it came from, which is exactly
       the context the shared explanation needs. Without this, the collection
       is a list to reread rather than something a learner can question - the
       same gap Grammar had. */
    root.querySelectorAll('[data-word-explain]').forEach((button) => {
      button.onclick = () => {
        const entry = items.find((x) => x.word === button.dataset.wordExplain);
        if (!entry?.source_fragment) return;
        openUnderstanding(ctx, {
          selection: entry.word,
          context: entry.source_fragment.slice(0, 2400),
          title: entry.focus_note || c.sourceContext,
          question: c.askWhy,
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
    if (moveFocus) focusRegion(root.querySelector('.recall-moment h2, .empty h2'));
  }
  paint();
}
export async function renderGrammar(root, ctx) {
  const { api, c, language, alive, memory } = ctx;
  if (!ctx.location.id) {
    const result = await api.grammarLibrary();
    if (!alive()) return;
    const lessons = patternsFor(language)
      .map((note) => ({
        ...((result.lessons || []).find((x) => x.id === note.id) || {}),
        ...note,
      }))
      .filter((x) => x.level);
    // An authored note whose Concept ID the catalog does not know, or a
    // catalog that answered with nothing usable, must read as an empty shelf
    // rather than a heading above a blank page.
    root.innerHTML = `${pageIntro({ title: c.grammarTitle, note: c.grammarNote, eyebrow: c.grammarName })}${intentNavigation(c, 'grammar')}${lessons.length ? `<div class="pattern-list">${lessons.map((x) => `<a href="${link('practice', { intent: 'grammar', id: x.id })}"><small>${esc(x.level)}</small><h2 lang="${ctx.ui}">${esc(x.title[ctx.ui])}</h2><p lang="${language}">${esc(x.line)}</p><span>↗</span></a>`).join('')}</div>` : `<section class="empty"><h2>${c.noPatterns}</h2><a class="primary" href="${link('practice')}">${c.practice} →</a></section>`}`;
    return;
  }
  const lesson = await api.grammarLesson(ctx.location.id);
  if (!alive()) return;
  const examples = lesson.examples || [],
    id = `grammar:${lesson.id}`,
    note = patternsFor(language).find((x) => x.id === lesson.id),
    title = note?.title[ctx.ui] || lesson.title;
  /* A pattern is easier to hold onto against the thing it is not. The contrast
     is what a learner actually writes instead, named in the one judgement
     vocabulary the rest of the product uses, so "wrong" means the same thing
     here as it does in a writing review or a reading explanation. */
  const contrast = note?.contrast;
  const contrastBlock = contrast
    ? `<section class="pattern-contrast"><h2>${esc(c.notThis)}</h2><p class="judgement" data-judgement="${esc(contrast.judgement)}">${esc(judgementLabel(c, contrast.judgement))}</p><blockquote lang="${esc(language)}"><del>${esc(contrast.instead)}</del></blockquote><p>${esc(contrast.why[ctx.support] || contrast.why[ctx.ui] || contrast.why.en)}</p><blockquote class="pattern-right" lang="${esc(language)}">${esc(note.line)}</blockquote></section>`
    : '';
  root.innerHTML = `<div class="back-row"><a href="${link('practice', { intent: 'grammar' })}">← ${c.grammarName}</a></div>${pageIntro({ title, note: c.grammarNote, eyebrow: lesson.level })}${note ? `<section class="pattern-focus"><small>${c.generatedNote}</small><div class="pattern-parts" lang="${language}">${note.parts.map((x) => `<span>${esc(x)}</span>`).join('<i aria-hidden="true">→</i>')}</div><p lang="${ctx.support}">${esc(note.note[ctx.support] || (ctx.support === 'vi' ? lesson.explanation_vi : '') || c.noMeaning)}</p></section>` : ''}<section class="grammar-encounter"><div><h2>${c.example}</h2>${examples.map((x, index) => `<blockquote lang="${language}">${esc(x.target || x.en || x.zh || '')}${x.pinyin && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<small>${esc(x.pinyin)}</small>` : ''}${ctx.support === 'vi' && (x.meaning_vi || x.vi) ? `<p lang="vi">${esc(x.meaning_vi || x.vi)}</p>` : ''}<button class="quiet" data-explain="${index}">${esc(c.lookCloser)} ↗</button></blockquote>`).join('')}</div>${contrastBlock}</section>${responseComposer(ctx, { id, title, prompt: c.yourExample })}`;
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
      });
    };
  });
  bindComposer(root, ctx, { id, title }, () => note?.line || '');
}
