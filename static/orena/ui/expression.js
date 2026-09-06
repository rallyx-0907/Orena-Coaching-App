import {
  pageIntro,
  intentNavigation,
  continuationShelf,
  draftStatus,
  responseComposer,
  bindComposer,
} from './patterns.js';
import { esc, status } from './html.js';
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
  let parentId = null;
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
  root.innerHTML = `<div class="back-row"><a href="${hasSource ? sourceLink(id) : link('practice')}">← ${hasSource ? c.returnLabel : c.practice}</a></div>${intentNavigation(c, 'writing')}<div class="expression-layout"><section class="expression-room">${pageIntro({ title, note: hasSource ? prompt : c.writingNote, eyebrow: c.writingName })}<form id="expressionForm"><label class="sr-only" for="expressionText">${c.respond}</label><textarea id="expressionText" lang="${language}" minlength="10" maxlength="12000" rows="10" required placeholder="${c.responsePlaceholder}">${esc(memory.value.expressions[id] || '')}</textarea><div class="expression-tools">${draftStatus(ctx)}<span class="meta" data-character-count></span><button class="primary">${c.review} ↗</button></div></form><section id="writingFeedback" aria-live="polite"></section></section><aside class="expression-context">${excerpt ? `<small>${c.expressionContext}</small><blockquote lang="${language}">${esc(excerpt)}</blockquote><a class="quiet" href="${sourceLink(id)}">${c.returnLabel} ↗</a>` : `<small>${c.expressionGuide}</small><p>${c.expressionGuideNote}</p><div class="expression-starters"><h2>${c.expressionStarters}</h2><p class="meta">${c.expressionStarterNote}</p>${invitations.map((item) => `<a href="${link('expression', { id: 'story:' + item.id })}"><small>${c.generated}</small><strong lang="${language}">${esc(item.prompt)}</strong><span>${c.usePrompt} ↗</span></a>`).join('')}</div>`}</aside></div>${continuationShelf(ctx, 2)}`;
  const updateCount = () => {
    root.querySelector('[data-character-count]').textContent =
      [...root.querySelector('textarea').value].length + ' ' + c.draftCount;
  };
  updateCount();
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
      const result = await ctx.mutate(() =>
        api.evaluate({
          prompt: source ? `${title}\n${c.responsePrompt}` : c.freeTitle,
          text,
          target_cefr: language === 'zh' ? 'HSK4' : 'B2',
          learning_language: language,
          parent_essay_id: parentId,
        }),
      );
      if (!alive()) return;
      parentId = result.id;
      // Only show a correction whose fragment is genuinely in what the learner
      // wrote, so a struck-through phrase is always one of their own.
      const corrections = (result.errors || []).filter(
        (x) => x.fragment && text.includes(x.fragment),
      );
      // A review that found nothing has to say so. Rendering an empty shell
      // reads as a failure the learner cannot tell apart from a real one.
      const findings = corrections.length || result.corrected_text;
      feedback.innerHTML = `<h2>${c.review}</h2>${result.evaluator === 'fallback-demo' ? `<p class="notice">${c.demoMeasurement}</p>` : ''}${findings ? '' : `<p>${c.noCorrections}</p>`}${result.corrected_text ? `<blockquote lang="${language}">${esc(result.corrected_text)}</blockquote>` : ''}${corrections.map((x) => `<article class="correction"><del lang="${language}">${esc(x.fragment)}</del><p lang="${language}">${esc(x.suggestion || '')}</p>${ctx.support === 'vi' && x.explanation_vi ? `<p lang="vi">${esc(x.explanation_vi)}</p>` : ''}</article>`).join('')}<p>${c.persisted}</p><button class="outline" data-revise>${c.revision} ↗</button>`;
      feedback.querySelector('[data-revise]').onclick = () =>
        root.querySelector('textarea').focus();
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
  function paint() {
    if (!alive()) return;
    const due = items.filter((x) => x.due),
      current = due[0];
    root.innerHTML = `${pageIntro({ title: c.wordsTitle, note: c.wordsIntro, eyebrow: c.language })}${items.length ? `<div class="language-summary"><span>${due.length} ${c.due}</span>${due.length && !recalling ? `<button class="primary" data-recall>${c.recallName} →</button>` : ''}</div>` : ''}${recalling ? (current ? `<section class="recall-moment"><small>${c.recallName}</small><h2 lang="${language}">${esc(current.word)}</h2>${current.phonetic && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(current.phonetic)}</p>` : ''}<blockquote lang="${language}">${esc(current.source_fragment || '')}</blockquote>${revealed ? `<p>${esc(current.definition || current.translation_vi || '')}</p><div class="button-row"><button class="outline" data-grade="again">${c.again}</button><button class="primary" data-grade="got_it">${c.gotIt}</button></div><p class="meta">${c.recallTruth}</p>` : `<button class="primary" data-reveal>${c.showMeaning} →</button>`}<p role="status" data-recall-status></p></section>` : `<section class="empty"><h2>${c.allDone}</h2><a class="outline" href="${link('language')}">${c.language} →</a></section>`) : items.length ? `<section class="word-collection">${items.map((x) => `<article><small>${esc(x.focus_note || c.sourceContext)}</small><h2 lang="${language}">${esc(x.word)}</h2>${x.phonetic && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<p class="pinyin">${esc(x.phonetic)}</p>` : ''}<blockquote lang="${language}">${esc(x.source_fragment || '')}</blockquote><details><summary>${c.meaning}</summary><p>${esc(x.definition || x.translation_vi || '')}</p></details></article>`).join('')}</section>` : `<section class="empty"><h2>${c.noWords}</h2><p>${c.noWordsNote}</p><a class="primary" href="#/">${c.discover} ↗</a></section>`}`;
    root.querySelector('[data-recall]')?.addEventListener('click', () => {
      recalling = true;
      paint();
    });
    root.querySelector('[data-reveal]')?.addEventListener('click', () => {
      revealed = true;
      paint();
    });
    root.querySelectorAll('[data-grade]').forEach(
      (button) =>
        (button.onclick = async () => {
          root
            .querySelectorAll('[data-grade]')
            .forEach((x) => (x.disabled = true));
          const output = root.querySelector('[data-recall-status]');
          output.textContent = c.saving;
          try {
            await ctx.mutate(() =>
              api.reviewLibraryVocabulary(current.word, button.dataset.grade),
            );
          } catch {
            if (alive()) {
              output.textContent = c.failedSave;
              root
                .querySelectorAll('[data-grade]')
                .forEach((x) => (x.disabled = false));
            }
            return;
          }
          // The grade is already recorded. If only the refresh fails, say that
          // rather than telling the learner their answer was lost.
          try {
            const updated = await api.libraryVocabulary();
            if (!alive()) return;
            items = updated.items || [];
            revealed = false;
            paint();
            status(c.persisted);
          } catch {
            if (alive()) {
              output.innerHTML =
                c.savedNotRefreshed +
                ' <button class="quiet" data-refresh>' +
                c.retry +
                '</button>';
              output.querySelector('[data-refresh]').onclick = async () => {
                const retry = output.querySelector('[data-refresh]');
                retry.disabled = true;
                try {
                  const updated = await api.libraryVocabulary();
                  if (!alive()) return;
                  items = updated.items || [];
                  revealed = false;
                  paint();
                } catch {
                  if (alive()) retry.disabled = false;
                }
              };
            }
          }
        }),
    );
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
    root.innerHTML = `${pageIntro({ title: c.grammarTitle, note: c.grammarNote, eyebrow: c.grammarName })}${intentNavigation(c, 'grammar')}${lessons.length ? `<div class="pattern-list">${lessons.map((x) => `<a href="${link('practice', { intent: 'grammar', id: x.id })}"><small>${esc(x.level)}</small><h2 lang="${language}">${esc(x.title[ctx.ui])}</h2><p lang="${language}">${esc(x.line)}</p><span>↗</span></a>`).join('')}</div>` : `<section class="empty"><h2>${c.noPatterns}</h2><a class="primary" href="${link('practice')}">${c.practice} →</a></section>`}`;
    return;
  }
  const lesson = await api.grammarLesson(ctx.location.id);
  if (!alive()) return;
  const examples = lesson.examples || [],
    id = `grammar:${lesson.id}`,
    note = patternsFor(language).find((x) => x.id === lesson.id),
    title = note?.title[ctx.ui] || lesson.title;
  root.innerHTML = `<div class="back-row"><a href="${link('practice', { intent: 'grammar' })}">← ${c.grammarName}</a></div>${pageIntro({ title, note: c.grammarNote, eyebrow: lesson.level })}${note ? `<section class="pattern-focus"><small>${c.generatedNote}</small><div class="pattern-parts" lang="${language}">${note.parts.map((x) => `<span>${esc(x)}</span>`).join('<i aria-hidden="true">→</i>')}</div><p lang="${ctx.support}">${esc(note.note[ctx.support] || (ctx.support === 'vi' ? lesson.explanation_vi : '') || c.noMeaning)}</p></section>` : ''}<section class="grammar-encounter"><div><h2>${c.example}</h2>${examples.map((x) => `<blockquote lang="${language}">${esc(x.target || x.en || x.zh || '')}${x.pinyin && (language !== 'zh' || ctx.profile.pinyin !== 'off') ? `<small>${esc(x.pinyin)}</small>` : ''}${ctx.support === 'vi' && (x.meaning_vi || x.vi) ? `<p lang="vi">${esc(x.meaning_vi || x.vi)}</p>` : ''}</blockquote>`).join('')}</div></section>${responseComposer(ctx, { id, title, prompt: c.yourExample })}`;
  bindComposer(root, ctx, { id, title }, () => note?.line || '');
}
