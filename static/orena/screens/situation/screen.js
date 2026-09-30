/* Frame 31 "Situation Reaction" (pinned design, focus route 'situation'; E2 §4). React to a real,
   Orena-authored scenario in the learner's own words - typed or spoken, transcribed via the same
   real ASR as Free Talk - then real coaching on that answer, `POST /api/dictionary/spoken-response`.

   Rule 40/D-076: the frame's own Intent-achieved/Clarity result grid is a regex-hit-count and a
   word-count bucket in the source (E2 §4), not a real judgement - not reproduced. "One useful
   improvement" and "Natural alternative" instead bind to the real coaching's own `next_attempt`
   and `say_again`/`another_way` (model.js's header comment). "Try another context" has no real
   content behind it either (the frame's own `.variant` sub-object does not exist in real content)
   and is dropped, as is the context pill (no real delivery-mode field). Finish logs one entry to
   the session's speaking ledger (`product/speaking-session.js`) and opens Speaking Summary, like
   the source's `spFinish`.

   Rule 49: this route is a learning workspace; the card is the one region that can grow long and
   is what scrolls (`data-scroll-region`), never the page. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { langAttr } from '../../kit/lang.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy as ts } from '../../copy/shell.js';
import { createLocalAudioRecorder } from '../../capabilities/audio-recorder.js';
import { logSpeakingTask } from '../../product/speaking-session.js';
import { saveResponse } from '../../product/account-records.js';
import { micGate, openMicState } from '../mic/sheet.js';
import { t } from './copy.js';
import { scenarios, progressLabel, naturalAlternative } from './model.js';

export default async function situation(element, ctx) {
  await useStyles('screens/situation/situation.css');
  const language = ctx.context.language;
  const support = languages().support;
  const recorder = createLocalAudioRecorder();
  const lang = langAttr(language);
  const supportLang = langAttr(support);

  let disposed = false;
  const alive = () => !disposed && ctx.isCurrent();

  const bank = scenarios(language);
  let index = 0;
  let state = 'input'; // input | transcribing (speech to text) | feedback (coaching) | result
  let answer = '';
  let coaching = null;
  let errorText = '';
  let recording = false;
  let lastBlob = null; // the recording awaiting a transcript, kept so a Retry sends the same take again

  element.classList.add('s-sit');

  const current = () => bank[index] || null;

  function headMarkup() {
    const label = progressLabel(index, bank.length);
    return html`<div class="s-sit__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${ts('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-sit__headcol"><h1 class="s-sit__title">${ts('situationReaction')}</h1><div class="s-sit__sub">${t('subtitle', { index: label.index, total: label.total })}</div></div>
    </div>`;
  }

  function inputMarkup() {
    const busy = state !== 'input';
    return html`<section class="o-card o-card--24 s-sit__card">
      <div class="s-sit__scenario" lang="${lang}">${current()?.scenario || ''}</div>
      <textarea class="s-sit__textarea" rows="3" lang="${lang}" placeholder="${t('answerPlaceholder')}" data-answer ${busy ? 'disabled' : ''}>${answer}</textarea>
      <div class="s-sit__row">
        <button type="button" class="s-sit__mic" aria-pressed="${recording ? 'true' : 'false'}" data-mic ${busy ? 'disabled' : ''}>${raw(icon('mic', { size: 16 }))}${state === 'transcribing' ? t('transcribing') : recording ? t('micRecording') : t('micIdle')}</button>
        <span class="s-sit__spacer"></span>
        <button type="button" class="o-btn o-btn--primary s-sit__submit" data-submit ${busy ? 'disabled' : ''}>${state === 'feedback' ? t('gettingFeedback') : t('submitCta')}</button>
      </div>
    </section>`;
  }

  function resultMarkup() {
    const improve = String(coaching?.next_attempt || '').trim();
    const alt = naturalAlternative(coaching);
    return html`<section class="o-card o-card--24 s-sit__card">
      <div class="s-sit__scenario" lang="${lang}">${current()?.scenario || ''}</div>
      <div class="s-sit__scroll" data-scroll-region>
        <div class="s-sit__answer" lang="${lang}">“${answer}”</div>
        ${improve ? html`<div class="o-card s-sit__improve"><b>${t('improvement')}</b> · <span lang="${supportLang}">${improve}</span></div>` : ''}
        ${alt ? html`<div class="s-sit__alt"><b>${t('naturalAlternative')}</b> · <span lang="${lang}">${alt}</span></div>` : ''}
      </div>
      ${errorText ? html`<p class="s-sit__error" role="alert">${errorText}</p>` : ''}
      <div class="s-sit__actions">
        <button type="button" class="o-btn o-btn--secondary" data-retry>${t('retry')}</button>
        ${bank.length > 1 ? html`<button type="button" class="o-btn o-btn--secondary" data-new>${t('newScenario')}</button>` : ''}
        <span class="s-sit__spacer"></span>
        <button type="button" class="o-btn o-btn--secondary" data-finish>${t('finish')}</button>
      </div>
    </section>`;
  }

  function paint() {
    const fit = state === 'result'; // the result card fits the viewport and scrolls its own answer and feedback (rule 49)
    mount(element, html`${headMarkup()}<div class="s-sit__body${fit ? ' s-sit__body--fit' : ''}" ${fit ? '' : 'data-scroll-region'}>${fit ? resultMarkup() : inputMarkup()}</div>`);
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    bind();
  }

  function reset(nextIndex = index) {
    index = nextIndex;
    state = 'input';
    answer = '';
    coaching = null;
    errorText = '';
    paint();
  }

  function bind() {
    if (state !== 'result') {
      const textarea = element.querySelector('[data-answer]');
      textarea.oninput = () => { answer = textarea.value; };
      element.querySelector('[data-mic]').onclick = () => (recording ? void stopMic() : void toggleMic());
      element.querySelector('[data-submit]').onclick = () => void submit();
      return;
    }
    element.querySelector('[data-retry]').onclick = () => reset();
    element.querySelector('[data-new]')?.addEventListener('click', () => reset((index + 1) % bank.length));
    element.querySelector('[data-finish]').onclick = () => {
      logSpeakingTask({ kind: 'situation_reaction', contentId: current()?.key || '', facts: [] });
      ctx.go(ctx.href('spsummary'));
    };
  }

  async function toggleMic() {
    await micGate(ctx, async () => {
      const started = await recorder.start();
      if (!alive()) return recorder.cleanup();
      if (!started) return void problem('blocked');
      recording = true;
      paint();
    });
  }

  async function stopMic() {
    recording = false;
    const take = await recorder.stop();
    if (!alive() || !take?.blob) return paint();
    lastBlob = take.blob;
    await transcribe();
  }

  async function transcribe() {
    state = 'transcribing';
    paint();
    try {
      const result = await api.transcribeSpeech(lastBlob, language);
      if (!alive()) return;
      const text = String(result?.text || result?.transcript || '').trim();
      state = 'input';
      paint();
      if (!text) return void problem('notheard');
      answer = text;
      paint();
    } catch {
      if (!alive()) return;
      state = 'input';
      paint();
      void problem(navigator.onLine === false ? 'offline' : 'provider');
    }
  }

  /* The Mic state sheet's own buttons, wired: Retry sends the same take again (or asks for the
     microphone again), Try again records again, and typing instead / continuing without the
     transcript leaves the learner in the answer box. */
  function problem(kind) {
    return openMicState(ctx, {
      state: kind,
      onAction: (key) => {
        if (key === 'retry' && kind === 'provider' && lastBlob) return void transcribe();
        if (key === 'retry' || key === 'tryagain') return void toggleMic();
        if (key === 'continue' || key === 'typeInstead') element.querySelector('[data-answer]')?.focus();
        return undefined;
      },
    });
  }

  async function submit() {
    const textarea = element.querySelector('[data-answer]');
    answer = textarea?.value.trim() || answer.trim();
    if (!answer) return; // the frame's own `srSubmit` returns on an empty answer without a notice
    state = 'feedback';
    errorText = '';
    paint();
    try {
      const result = await api.spokenResponseCoaching({
        transcript: answer.slice(0, 2400),
        source_language: language,
        target_language: support,
        situation: (current()?.scenario || '').slice(0, 1200),
      });
      if (!alive()) return;
      coaching = result?.available ? result : null;
      errorText = result?.available ? '' : t('serviceError');
    } catch {
      if (!alive()) return;
      coaching = null;
      errorText = t('serviceError');
    }
    state = 'result';
    // The answer is the learner's own work, kept with the account when it keeps work (D4 I8).
    void saveResponse({ kind: 'situation', source: { kind: 'invitation', id: current()?.key || 'open' }, mode: 'situation', answer, coaching });
    paint();
  }

  paint();

  return () => {
    disposed = true;
    recorder.cleanup();
  };
}
