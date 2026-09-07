import { esc } from './html.js';
import { openUnderstanding } from './understanding.js';

/* An optional check on what a passage left behind. It is offered after the
   text, never before it, and nothing in the encounter waits for it: a learner
   who reads a piece and moves on has read it.

   What makes it worth answering is not the score. Every result names the words
   in the passage that settle the question, and those words can be taken into
   the shared explanation the same way any other phrase can. The API calls this
   a comprehension check only, and the surface repeats that rather than letting
   four questions look like a measure of the learner's reading. */

/* Pure reading is a complete thing to do. A text with no questions says so in
   one quiet line rather than showing nothing, because an absent section and a
   section that failed to load look identical - and nothing is fabricated to
   make every text carry a check. */
export function comprehensionSection(c, questions, latestAttempt) {
  if (!questions?.length)
    return `<p class="meta comprehension-absent">${esc(c.readingOnlyNote)}</p>`;
  return `<details class="comprehension" data-comprehension>
    <summary>${esc(c.comprehension)} · ${esc(c.comprehensionOptional)}</summary>
    ${latestAttempt ? `<p class="meta">${esc(c.comprehensionDone)} · ${esc(latestAttempt.correct_count)}/${esc(latestAttempt.total)} · ${esc(c.comprehensionClaim)}</p>` : ''}
    <p class="meta">${esc(c.comprehensionNote)}</p>
    <form data-comprehension-form>${questions
      .map(
        (item, index) => `<fieldset class="comprehension-question">
        <legend>${esc(item.question)}</legend>
        ${item.options
          .map(
            (option, choice) =>
              `<label><input type="radio" name="q${index}" value="${choice}"> <span>${esc(option)}</span></label>`,
          )
          .join('')}
      </fieldset>`,
      )
      .join('')}
      <button class="outline" type="submit">${esc(c.comprehensionCheck)}</button>
      <p role="status" data-comprehension-status></p>
    </form>
    <div data-comprehension-results></div>
  </details>`;
}

function result(c, item, support) {
  return `<article class="comprehension-result" data-correct="${item.correct ? 'yes' : 'no'}">
    <small>${esc(item.correct ? c.comprehensionRight : c.comprehensionWrong)}</small>
    <p>${esc(item.question)}</p>
    ${
      item.correct
        ? ''
        : `<p class="meta">${esc(c.comprehensionAnswer)} ${esc(item.options[item.correct_index] || '')}</p>`
    }
    ${
      item.evidence_fragment
        ? `<blockquote data-evidence="${esc(item.evidence_fragment)}">${esc(item.evidence_fragment)}</blockquote><button class="quiet" data-look="${esc(item.evidence_fragment)}">${esc(c.lookCloser)} ↗</button>`
        : ''
    }
    ${support === 'vi' && item.explanation_vi ? `<p lang="vi">${esc(item.explanation_vi)}</p>` : ''}
  </article>`;
}

/* Binds the check. `onEvidence` lets the encounter show the passage where an
   answer lives, so a wrong answer sends the learner back to the text rather
   than to a correction. */
export function bindComprehension(
  root,
  ctx,
  { sessionId, questions, onEvidence },
) {
  const section = root.querySelector('[data-comprehension]');
  if (!section || !questions?.length) return;
  const { c, api, support, alive } = ctx;
  const form = section.querySelector('[data-comprehension-form]');
  const output = section.querySelector('[data-comprehension-results]');
  const state = section.querySelector('[data-comprehension-status]');

  form.onsubmit = async (event) => {
    event.preventDefault();
    const answers = questions.map((_, index) => {
      const picked = form.querySelector(`input[name="q${index}"]:checked`);
      return picked ? Number(picked.value) : null;
    });
    // The check is whole or not at all: the API scores a complete set, and a
    // partial one would be reported back as a failure the learner cannot act on.
    if (answers.some((value) => value === null)) {
      state.textContent = c.comprehensionIncomplete;
      return;
    }
    state.textContent = c.saving;
    form.querySelector('button').disabled = true;
    try {
      const scored = await ctx.mutate(() =>
        api.submitReadingAnswers(sessionId, answers),
      );
      if (!alive()) return;
      if (!scored.valid || !Array.isArray(scored.results))
        throw Error('Reading check unavailable');
      state.textContent = '';
      output.innerHTML = `<p class="comprehension-score">${esc(c.comprehensionScore)} ${scored.correct_count}/${scored.total}</p><p class="meta">${esc(c.comprehensionClaim)}</p>${(
        scored.results || []
      )
        .map((item) => result(c, item, support))
        .join('')}`;
      output.querySelectorAll('[data-look]').forEach((button) => {
        button.onclick = () => {
          const fragment = button.dataset.look;
          const context = onEvidence?.(fragment) || fragment;
          openUnderstanding(ctx, {
            selection: fragment,
            context,
            title: c.comprehension,
          });
        };
      });
      output.scrollIntoView({ block: 'nearest' });
    } catch {
      if (alive()) state.textContent = c.comprehensionUnavailable;
    } finally {
      if (alive()) form.querySelector('button').disabled = false;
    }
  };
}
