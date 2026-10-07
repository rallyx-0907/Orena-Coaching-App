/* Frame 29 "Free Talk" (pinned design, focus route 'freetalk'; E2 §2). A real recording ->
   real ASR transcript (`POST /api/speech/transcribe`) -> a reviewable, editable transcript ->
   real coaching from that transcript (`POST /api/dictionary/spoken-response`) - "record ->
   transcribe -> coaching as today" (Wave B brief), the same pipeline the current Free Talk already
   runs (`ui/speaking-free.js`), against this design's own markup.

   Rule 49: this route is a learning workspace - the root fills `.o-main`'s column and the one
   card that can grow long scrolls in its own `data-scroll-region`, never the page. Rule 40: the
   frame's three result stat tiles (Words / Pace / Linking) render only what is really measurable
   from a real transcript and a real elapsed time (Words, Pace, and Linking, the count of linking
   words through the language adapter in linking.js, D-139 HD-9) - counts, not scores. Rule 43/44: the
   frame's own "Demo ASR" pill (a prototype self-disclosure) and its regex `analyze()` scoring are
   not reproduced; nothing here is invented. Finish logs one entry to the session's speaking ledger
   (`product/speaking-session.js`) and opens Speaking Summary, like the source's `spFinish`. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { markGlyph } from '../../kit/brand.js';
import { langAttr } from '../../kit/lang.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy as ts } from '../../copy/shell.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { createLocalAudioRecorder } from '../../capabilities/audio-recorder.js';
import { logSpeakingTask } from '../../product/speaking-session.js';
import { saveResponse } from '../../product/account-records.js';
import { micGate, openMicState } from '../mic/sheet.js';
import { t } from './copy.js';
import {
  DURATIONS_MS, topics, formatClock, waveBars, resultStats, ledgerFacts, fixesOf, strengthsOf, phraseWords, headlineKind,
} from './model.js';

const MIN_TAKE_MS = 600;

function headlineText(fixCount) {
  const kind = headlineKind(fixCount);
  if (kind === 'none') return t('headlineNone');
  if (kind === 'one') return t('headlineOne');
  return t.plural('headlineMany', fixCount);
}

export default async function freeTalk(element, ctx) {
  await useStyles('screens/free-talk/free-talk.css');
  const language = ctx.context.language;
  const support = languages().support;
  const recorder = createLocalAudioRecorder();

  let disposed = false;
  const alive = () => !disposed && ctx.isCurrent();

  const topicList = topics(language);
  let phrases = [];
  api.libraryVocabulary({ limit: 4, order: 'recent' }).then((page) => {
    if (!alive()) return;
    phrases = phraseWords(page);
    if (state === 'setup') paint();
  }).catch(() => {});

  let state = 'setup'; // setup | recording | transcribing | review | feedback | result
  let topicText = '';
  let topicSituation = ''; // the picked/typed topic's own sentence, sent as the coaching `situation`
  let durationMs = DURATIONS_MS[0];
  // The take is counted in the learning language's unit (model.js `unitCount`): characters for Chinese.
  const unitKeys = language === 'zh' ? { count: 'statChars', pace: 'statPaceUnitChars' } : { count: 'statWords', pace: 'statPaceUnit' };
  let startedAt = 0;
  let ticker = 0;
  let takeMs = 0;
  let lastTake = null; // the recording awaiting a transcript, kept so a Retry sends the same take again
  let heard = '';
  let coaching = null;
  let errorText = '';

  element.classList.add('s-ft');

  const stepKey = { setup: 'stepSetup', recording: 'stepRecording', transcribing: 'stepTranscript', review: 'stepTranscript', feedback: 'stepTranscript', result: 'stepResult' };

  function headMarkup() {
    return html`<div class="s-ft__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${ts('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-ft__headcol"><h1 class="s-ft__title">${ts('freeTalk')}</h1><div class="s-ft__sub">${t(stepKey[state])}</div></div>
    </div>`;
  }

  function setupMarkup() {
    return html`<section class="o-card o-card--24 s-ft__card s-ft__setup">
      <div>
        <div class="s-ft__label">${t('topicLabel')}</div>
        <input class="s-ft__input" type="text" placeholder="${t('topicPlaceholder')}" value="${topicText}" lang="${langAttr(language)}" autocomplete="off" data-topic-input>
        <div class="s-ft__pills">${topicList.map((item) => html`<button type="button" class="s-ft__suggest" data-topic="${item.key}" lang="${langAttr(language)}">${item.title}</button>`)}</div>
      </div>
      <div>
        <div class="s-ft__label">${t('durationLabel')}</div>
        <div class="s-ft__durations">${DURATIONS_MS.map((ms) => html`<button type="button" class="s-ft__duration" aria-pressed="${ms === durationMs ? 'true' : 'false'}" data-duration="${ms}">${t.plural('minutes', Math.round(ms / 60000))}</button>`)}</div>
      </div>
      ${phrases.length ? html`<div>
        <div class="s-ft__label">${t('phrasesLabel')}</div>
        <div class="s-ft__pills">${phrases.map((word) => html`<span class="s-ft__phrase" lang="${langAttr(language)}">${word}</span>`)}</div>
      </div>` : ''}
      <button type="button" class="o-btn o-btn--primary o-btn--block s-ft__start" data-start>${t('startCta')}</button>
    </section>`;
  }

  function recordingMarkup() {
    return html`<section class="o-card o-card--24 s-ft__card s-ft__record">
      <div class="s-ft__recap-label">${t('topicLabel')}</div>
      <div class="s-ft__recap" lang="${langAttr(language)}">${topicText}</div>
      <div class="s-ft__clock" data-clock>${formatClock(0)}</div>
      <div class="s-ft__wave" aria-hidden="true">${waveBars().map((bar) => html`<i style="height:${bar.height}%;animation-delay:${bar.delay}ms"></i>`)}</div>
      <div class="s-ft__micon"><span aria-hidden="true">●</span> ${t('micOn')}</div>
      <div class="s-ft__stopwrap">
        <button type="button" class="s-ft__stop" data-stop aria-label="${t('tapToFinish')}"><i></i></button>
        <span class="s-ft__stop-caption">${t('tapToFinish')}</span>
      </div>
    </section>`;
  }

  function workingMarkup() {
    return html`<section class="o-card o-card--24 s-ft__card s-ft__record"><p class="s-ft__working" role="status">${t('transcribing')}</p></section>`;
  }

  function reviewMarkup(busy) {
    return html`<section class="o-card o-card--24 s-ft__card s-ft__review">
      <div class="s-ft__review-title">${takeMs > 0 ? t('transcriptTitle', { time: formatClock(takeMs) }) : t('transcriptPlain')}</div>
      <textarea class="s-ft__textarea" rows="6" lang="${langAttr(language)}" data-transcript ${busy ? 'disabled' : ''}>${heard}</textarea>
      ${errorText ? html`<p class="s-ft__error" role="alert">${errorText}</p>` : ''}
      <div class="s-ft__review-actions">
        <button type="button" class="o-btn o-btn--secondary s-ft__again" data-again ${busy ? 'disabled' : ''}>${t('recordAgain')}</button>
        <button type="button" class="o-btn o-btn--primary s-ft__feedback" data-feedback ${busy ? 'disabled' : ''}>${busy ? t('gettingFeedback') : t('getFeedback')}</button>
      </div>
    </section>`;
  }

  function resultMarkup() {
    const ok = Boolean(coaching); // coaching that came back usable; otherwise only the measured stats show
    const fixes = fixesOf(coaching);
    const strengths = strengthsOf(coaching);
    const stats = resultStats(heard, takeMs, language);
    const speed = stats.pace ?? '—'; // the frame's own dash under 5 s
    const sayAgain = String(coaching?.say_again || '').trim();
    return html`<section class="o-card o-card--24 s-ft__card s-ft__result">
      ${ok ? html`<p class="s-ft__headline">${headlineText(fixes.length)}</p>` : ''}
      <div class="s-ft__stats">
        <div class="s-ft__stat"><span class="s-ft__stat-label">${t(unitKeys.count)}</span><span class="s-ft__stat-value">${stats.words}</span></div>
        <div class="s-ft__stat"><span class="s-ft__stat-label">${t('statPace')}</span><span class="s-ft__stat-value">${speed} <span class="s-ft__stat-unit">${t(unitKeys.pace)}</span></span></div>
        <div class="s-ft__stat"><span class="s-ft__stat-label">${t('statLinking')}</span><span class="s-ft__stat-value">${stats.linking}</span></div>
      </div>
      ${ok ? html`<div class="s-ft__scroll" data-scroll-region>
      <div>
        <span class="s-ft__section-title s-ft__section-title--good">${t('strengthsTitle')}</span>
        ${strengths.length
          ? strengths.map((item) => html`<p class="s-ft__strength"><b lang="${langAttr(language)}">${item.quote}</b> · <span lang="${langAttr(support)}">${item.why}</span></p>`)
          : html`<p class="s-ft__muted">${t('strengthsEmpty')}</p>`}
      </div>
      <div>
        <span class="s-ft__section-title s-ft__section-title--bad">${t('fixesTitle')}</span>
        ${fixes.length
          ? fixes.map((fix) => html`<div class="o-card s-ft__fix"><div class="s-ft__fix-change"><s lang="${langAttr(language)}">${fix.quote}</s>${fix.instead ? html` → <b lang="${langAttr(language)}">${fix.instead}</b>` : ''}</div>${fix.why ? html`<div class="s-ft__fix-why" lang="${langAttr(support)}">${fix.why}</div>` : ''}</div>`)
          : html`<p class="s-ft__muted">${t('fixesEmpty')}</p>`}
      </div>
      ${sayAgain ? html`<p class="s-ft__retry"><b>${t('retryTitle')}</b> · <span lang="${langAttr(language)}">${sayAgain}</span></p>` : ''}
      </div>` : ''}
      ${errorText ? html`<p class="s-ft__error" role="alert">${errorText}</p>` : ''}
      <div class="s-ft__actions">
        <button type="button" class="o-btn o-btn--secondary s-ft__talk-again" data-talk-again>${t('talkAgain')}</button>
        <button type="button" class="o-btn s-ft__ask" data-ask>${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${t('askAboutThis')}</button>
        <span class="s-ft__spacer"></span>
        <button type="button" class="o-btn o-btn--primary s-ft__finish" data-finish>${t('finish')}</button>
      </div>
    </section>`;
  }

  function cardMarkup() {
    if (state === 'setup') return setupMarkup();
    if (state === 'recording') return recordingMarkup();
    if (state === 'transcribing') return workingMarkup();
    if (state === 'review' || state === 'feedback') return reviewMarkup(state === 'feedback');
    return resultMarkup();
  }

  function paint() {
    const fit = state === 'result'; // the result card fits the viewport and scrolls its own feedback (rule 49)
    mount(element, html`${headMarkup()}<div class="s-ft__body${fit ? ' s-ft__body--fit' : ''}" ${fit ? '' : 'data-scroll-region'}>${cardMarkup()}</div>`);
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    bind();
  }

  function bind() {
    if (state === 'setup') {
      const input = element.querySelector('[data-topic-input]');
      input.oninput = () => { topicText = input.value; topicSituation = ''; };
      element.querySelectorAll('[data-topic]').forEach((button) => {
        button.onclick = () => {
          const item = topicList.find((entry) => entry.key === button.dataset.topic);
          if (!item) return;
          topicText = item.title;
          topicSituation = item.prompt;
          paint();
        };
      });
      element.querySelectorAll('[data-duration]').forEach((button) => {
        button.onclick = () => { durationMs = Number(button.dataset.duration); paint(); };
      });
      element.querySelector('[data-start]').onclick = () => {
        if (!topicText.trim()) return toast(t('pickTopicFirst'));
        void micGate(ctx, start);
      };
    } else if (state === 'recording') {
      element.querySelector('[data-stop]').onclick = () => void stop();
    } else if (state === 'review') {
      const textarea = element.querySelector('[data-transcript]');
      textarea.oninput = () => { heard = textarea.value; };
      element.querySelector('[data-again]').onclick = () => { state = 'setup'; paint(); };
      element.querySelector('[data-feedback]').onclick = () => void getFeedback();
    } else if (state === 'result') {
      element.querySelector('[data-talk-again]').onclick = () => { state = 'setup'; heard = ''; coaching = null; errorText = ''; paint(); };
      element.querySelector('[data-finish]').onclick = finish;
      element.querySelector('[data-ask]').onclick = () => askOrena({
        surface: 'speaking.free_talk',
        activity_type: 'free_talk',
        selected_item: { type: 'sentence', text: heard.slice(0, 600), lang: language },
      });
    }
  }

  function finish() {
    logSpeakingTask({
      kind: 'free_talk',
      facts: ledgerFacts(resultStats(heard, takeMs, language), { words: t(unitKeys.count), pace: t('statPace'), paceUnit: t(unitKeys.pace) }),
    });
    ctx.go(ctx.href('spsummary'));
  }

  async function start() {
    const started = await recorder.start();
    if (!alive()) return recorder.cleanup();
    if (!started) return void problem('blocked');
    startedAt = Date.now();
    state = 'recording';
    paint();
    clearInterval(ticker);
    ticker = setInterval(() => {
      if (!alive()) return clearInterval(ticker);
      const elapsed = Date.now() - startedAt;
      const clockEl = element.querySelector('[data-clock]');
      if (clockEl) clockEl.textContent = formatClock(elapsed);
      if (elapsed >= durationMs) void stop();
    }, 250);
  }

  async function stop() {
    if (state !== 'recording') return;
    clearInterval(ticker);
    const ms = Date.now() - startedAt;
    const take = await recorder.stop();
    if (!alive()) return;
    if (!take?.blob || ms < MIN_TAKE_MS) { state = 'setup'; paint(); return; }
    lastTake = { blob: take.blob, ms };
    await transcribe();
  }

  async function transcribe() {
    takeMs = lastTake.ms;
    state = 'transcribing';
    paint();
    try {
      const result = await api.transcribeSpeech(lastTake.blob, language);
      if (!alive()) return;
      const text = String(result?.text || result?.transcript || '').trim();
      if (!text) {
        state = 'setup';
        paint();
        return void problem('notheard');
      }
      heard = text;
      errorText = '';
      state = 'review';
      paint();
    } catch {
      if (!alive()) return;
      state = 'setup';
      paint();
      void problem(navigator.onLine === false ? 'offline' : 'provider');
    }
  }

  /* The Mic state sheet's own buttons, wired: Retry sends the same take again (or asks for the
     microphone again), Try again records again, and typing instead / continuing without the
     transcript opens the editable transcript step empty - the frame's transcript box is already a
     text field the learner fills in. */
  function problem(kind) {
    return openMicState(ctx, {
      state: kind,
      onAction: (key) => {
        if (key === 'retry' && kind === 'provider' && lastTake) return void transcribe();
        if (key === 'retry' || key === 'tryagain') return void micGate(ctx, start);
        if (key === 'continue' || key === 'typeInstead') {
          heard = '';
          takeMs = 0; // typed, not spoken: no elapsed time to measure a pace against
          errorText = '';
          state = 'review';
          paint();
        }
        return undefined;
      },
    });
  }

  async function getFeedback() {
    heard = element.querySelector('[data-transcript]')?.value.trim() || heard;
    if (!heard) return;
    state = 'feedback';
    errorText = '';
    paint();
    try {
      const result = await api.spokenResponseCoaching({
        transcript: heard.slice(0, 2400),
        source_language: language,
        target_language: support,
        situation: (topicSituation || topicText).slice(0, 1200),
      });
      if (!alive()) return;
      coaching = result?.available ? result : null;
      errorText = result?.available ? '' : t('serviceError');
      state = 'result';
      // The take is the learner's own work, kept with the account when it keeps work (D4 I8).
      void saveResponse({ kind: 'freetalk', source: { kind: 'invitation', id: topicText.trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').slice(0, 60) || 'open' }, mode: 'free_talk', answer: heard, coaching });
      paint();
    } catch {
      if (!alive()) return;
      coaching = null;
      errorText = t('serviceError');
      state = 'result';
      paint();
    }
  }

  paint();

  return () => {
    disposed = true;
    clearInterval(ticker);
    recorder.cleanup();
  };
}
