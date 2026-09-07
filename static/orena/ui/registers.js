import { esc, dialog, focusRegion } from './html.js';

/* One meaning across the registers a learner has to tell apart. Deliberately
   not a rewrite button: a version is only shown alongside the signals that put
   it in that register and the situation where it would be the wrong choice,
   because the learning is in the difference rather than in any one sentence.

   The learner's own words stay at the top throughout, the way they do in the
   explanation surface. */

export const REGISTERS = [
  'conversational',
  'concise_professional',
  'formal',
  'academic',
  'technical',
];

export function registerLabel(c, key) {
  return c[`register_${key}`] || '';
}

function version(c, item, language) {
  return `<article class="register-version">
    <h3>${esc(registerLabel(c, item.register) || item.register)}</h3>
    <blockquote lang="${esc(language)}">${esc(item.text)}</blockquote>
    ${item.why ? `<p>${esc(item.why)}</p>` : ''}
    ${
      (item.signals || []).length
        ? `<p class="meta">${esc(c.registerSignals)}</p><ul>${item.signals.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`
        : ''
    }
    ${item.use_when ? `<p><b>${esc(c.registerUseWhen)}</b> ${esc(item.use_when)}</p>` : ''}
    ${item.avoid_when ? `<p><b>${esc(c.registerAvoidWhen)}</b> ${esc(item.avoid_when)}</p>` : ''}
  </article>`;
}

export function openRegisters(ctx, { text, title, situation = '' }) {
  const { c, api, language, support } = ctx;
  const source = String(text || '').trim();
  if (!source) return null;

  const sheet = dialog({
    title: c.registerTitle,
    body: `<div class="registers">
      <section class="understanding-source">
        <small>${esc(title || c.writingName)}</small>
        <blockquote lang="${esc(language)}">${esc(source.slice(0, 1200))}</blockquote>
      </section>
      <p class="meta">${esc(c.registerNote)}</p>
      <form class="register-ask" data-situation>
        <label for="registerSituation">${esc(c.registerSituation)}</label>
        <input id="registerSituation" name="situation" maxlength="240" value="${esc(situation)}" placeholder="${esc(c.registerSituationPlaceholder)}" autocomplete="off">
        <button class="primary">${esc(c.registerCompare)}</button>
      </form>
      <section class="register-body" aria-live="polite" data-register-body></section>
    </div>`,
  });

  const body = sheet.querySelector('[data-register-body]');
  const form = sheet.querySelector('[data-situation]');
  const alive = () => sheet.isConnected;

  async function run() {
    body.textContent = c.loading;
    form.querySelector('button').disabled = true;
    try {
      const result = await api.registerComparison({
        text: source.slice(0, 2400),
        source_language: language,
        target_language: support,
        situation: form.elements.situation.value.trim(),
      });
      if (!alive()) return;
      const versions = (result.versions || []).filter(
        (x) => x && REGISTERS.includes(x.register) && x.text,
      );
      if (!result.available || !versions.length) {
        // Nothing is rewritten in place of an answer that did not arrive.
        body.innerHTML = `<p class="notice">${esc(c.registerUnavailable)}</p>`;
        return;
      }
      body.innerHTML = `${result.meaning ? `<p class="register-meaning">${esc(result.meaning)}</p>` : ''}<div class="register-versions">${versions
        .map((item) => version(c, item, language))
        .join('')}</div>${
        result.what_changes
          ? `<section class="register-changes"><h3>${esc(c.registerWhatChanges)}</h3><p>${esc(result.what_changes)}</p></section>`
          : ''
      }`;
      focusRegion(body);
    } catch {
      if (alive()) body.innerHTML = `<p class="notice">${esc(c.registerUnavailable)}</p>`;
    } finally {
      if (alive()) form.querySelector('button').disabled = false;
    }
  }

  form.onsubmit = (event) => {
    event.preventDefault();
    run();
  };
  run();
  return sheet;
}
