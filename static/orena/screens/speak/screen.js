/* Scripted Pronunciation (frame 15, `#/speak/:id`; D-091). One line, said and assessed: the
   target sentence as tappable tokens, model/mine playback, a mic recorder, and a result card with
   a score ring, three metric slots and the ASR line. There is no "next line" control (confirmed against
   the source, SCRATCH/inventory/D5-speaking.md - neither Scripted Pronunciation nor Compare With
   Model draws one), so this room works the one line `product/speaking-source.js` resolves from
   the route (the first of the source, or the segment a link names).

   Real data only: `GET /api/speaking/items/{id}` or `GET /api/listening/library/{lessonId}`
   (the line + its model audio, when the source has one), `POST /api/speech/pronunciation`
   (`capabilities/speaking-take.js`, unchanged, through `product/speaking-recorder.js`), the
   audio-free record it keeps (`POST /api/speech/attempts`), and this tab's own take list
   (`product/take-store.js`, D-076). Unreturned Fluency remains unavailable, with no score
   track or session fact, instead of being represented as a measured zero. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { markGlyph } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr, langSpan } from '../../kit/lang.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
import { loadSpeakingSource, segmentOf } from '../../product/speaking-source.js';
import { originalSegmentPlayer } from '../../product/original-segment-player.js';
import { pairWord } from '../../product/compare-reference.js';
import { pronunciationView } from '../../capabilities/pronunciation-result.js';
import { createSpeakingRecorder, TAKE, MAX_TAKE_MS } from '../../product/speaking-recorder.js';
import { lineKey, listTakes, viewOfTake, bestTake, attemptIdOf } from '../../product/take-store.js';
import { openMicState, micGate } from '../mic/sheet.js';
import { t } from './copy.js';
import { tokenStrip, tipFor, detailFor, metricsFor, recorderState, recCaptionKey, micStateFor, attemptOrdinal, ringTone, verdictKey, bandInk, clockLabel, restingWave, liveWave, whenLabel, WAVE_BARS } from './model.js';

/* The frame's play triangle and pause bars are filled shapes (`fill="currentColor"`), not outlines. */
const filled = (name, size) => raw(icon(name, { size }).replace('fill="none"', 'fill="currentColor"'));

/* The provider's own miscue verdict on a word (`error_type`: "None", "Mispronunciation",
   "Omission", "Insertion", "UnexpectedBreak", "MissingBreak", "Monotone"), translated - a type
   this copy table has no key for still reads as "not passed" rather than the raw provider string. */
function errorLabel(errorType) {
  if (!errorType || errorType === 'None') return t('passed');
  const key = `error${errorType}`;
  return t.has(key) ? t(key) : t('errorOther');
}

export default async function mountScriptedPronunciation(element, ctx) {
  await useStyles('screens/speak/speak.css');
  await useStyles('capabilities/original-segment-player.css');
  const language = ctx.context?.language || 'en';
  const support = languages().support;
  const segmentId = segmentOf(ctx.query);
  const lineQuery = segmentId ? { segment: segmentId } : {};

  // This lesson route's delayed loading skeleton is owned by the router.
  mount(element, '');
  element.classList.add('s-speak-root');

  const source = await loadSpeakingSource(ctx.params.id, { api, support, language, owner: ctx.context.owner || 'local', segmentId });
  if (!ctx.isCurrent()) return undefined;
  ctx.setCrumb(source.title);
  ctx.context?.memory?.enter?.({ id: source.sourceId, title: source.title, intent: 'speaking', segment: source.line.lineId, excerpt: source.line.text });

  const key = lineKey(source.sourceId, source.line.lineId);
  let takes = await listTakes(key);
  if (!ctx.isCurrent()) return undefined;
  mount(element, '');
  const renderRoot = document.createElement('div');
  renderRoot.style.display = 'contents';
  element.append(renderRoot);
  const originalPlayer = originalSegmentPlayer(source);

  /* Coming back to a line that already has attempts shows the newest one again, as it was: the
     full assessment when this tab still holds it, the smaller shape a reopened attempt has
     otherwise (`viewOfTake`). Never "no attempt yet" beside a Compare button that says there is. */
  let currentTakeRef = takes[0]?.id || '';
  let view = takes.length ? viewOfTake(takes[0]) : pronunciationView(null);
  let rec = { phase: TAKE.IDLE, error: null, levels: new Array(WAVE_BARS).fill(0), elapsedMs: 0 }; // what the recorder last said
  let tokenSel = null; // index of a tapped word, once a result exists
  let playing = null; // 'model' | 'mine' | null
  let takeAudio = null;

  const q = (selector) => element.querySelector(selector);
  /* A line with attempts and no take in flight reads as a finished one, and a failed take leaves
     the attempt before it in place. */
  const phase = () => (rec.phase === TAKE.IDLE && takes.length ? TAKE.RESULT : rec.phase);
  const hasResult = () => view.measured && (phase() === TAKE.RESULT || phase() === TAKE.ERROR);
  const recognizedText = () => view.heard || '';

  const recorder = createSpeakingRecorder({
    api,
    source,
    key,
    language,
    facts: (finished) => [
      { label: t('metricAccuracy'), value: finished.accuracy },
      ...(finished.fluencyMeasured ? [{ label: t('metricFluency'), value: finished.fluency }] : []),
    ],
    on: {
      change(next) {
        if (!ctx.isCurrent()) return;
        const finished = next.latest;
        if (finished?.take_ref && finished.take_ref !== currentTakeRef) {
          currentTakeRef = finished.take_ref;
          takes = finished.list;
          view = finished.view;
          tokenSel = null;
        }
        rec = { ...rec, ...next };
        paint();
      },
      level(levels) {
        rec = { ...rec, levels };
        paintWave();
      },
      tick(ms) {
        rec = { ...rec, elapsedMs: ms };
        paintClock();
      },
      failure(error) {
        if (error.kind === 'microphone' || error.kind === 'unsupported') {
          openMicState(ctx, { state: 'blocked', onAction: (action) => (action === 'retry' ? void begin() : undefined) });
        } else {
          openMicState(ctx, {
            state: micStateFor(error.kind),
            onAction: (action) => {
              if (action === 'tryagain' || action === 'retry') (error.retry ? recorder.retry() : begin());
            },
          });
        }
      },
    },
  });

  function paintWave() {
    const wave = q('[data-wave]');
    if (!wave) return;
    const heights = liveWave(rec.levels);
    [...wave.children].forEach((bar, at) => {
      bar.style.height = `${heights[at]}%`;
    });
  }
  function paintClock() {
    if (rec.phase !== TAKE.RECORDING) return;
    const sub = q('[data-clock]');
    if (sub) sub.textContent = `${clockLabel(rec.elapsedMs)} / ${clockLabel(MAX_TAKE_MS)}`;
    const caption = q('[data-caption]');
    if (caption) caption.textContent = t('captionRecording', { s: (rec.elapsedMs / 1000).toFixed(1) });
  }

  function stopPlayback() {
    originalPlayer?.stop();
    takeAudio?.pause();
    takeAudio = null;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    playing = null;
  }

  async function begin() {
    if (recorder.busy) return;
    stopPlayback();
    micGate(ctx, () => recorder.start());
  }

  /* The browser's own voice reads a word or a line when no recorded model exists for it - a real
     playback, never a fabricated measurement. */
  function speak(text, onEnd) {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return onEnd?.();
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === 'zh' ? 'zh-CN' : 'en-US';
    utterance.onend = () => onEnd?.();
    utterance.onerror = () => onEnd?.();
    window.speechSynthesis.speak(utterance);
  }
  function ended(what) {
    if (playing !== what) return;
    playing = null;
    if (ctx.isCurrent()) paint();
  }
  function playModel() {
    if (source.lessonId && !source.hasModelAudio) return;
    if (playing === 'model') {
      stopPlayback();
      paint();
      return;
    }
    stopPlayback();
    playing = 'model';
    if (source.hasModelAudio) {
      originalPlayer?.play().then(() => ended('model'));
    } else if (!source.lessonId) {
      speak(source.line.text, () => ended('model'));
    }
    paint();
  }
  function playModelWord(index) {
    if (source.lessonId && !source.hasModelAudio) return;
    if (source.hasModelAudio) {
      const word = pairWord(source.line.text, view.words, index, source.line.wordTimings, source.language);
      if (!word) return;
      stopPlayback();
      playing = 'model';
      originalPlayer.play({from:word.offsetMs/1000,to:(word.offsetMs+word.durationMs)/1000}).then(() => ended('model'));
      paint();
      return;
    }
    stopPlayback();
    playing = 'model';
    speak(view.words[index]?.text || '', () => ended('model'));
    paint();
  }
  function playMine() {
    if (playing === 'mine') {
      stopPlayback();
      paint();
      return;
    }
    const current = takes.find((item) => item.id === currentTakeRef);
    if (!current?.url) return;
    stopPlayback();
    playing = 'mine';
    takeAudio = new Audio(current.url);
    takeAudio.addEventListener('ended', () => ended('mine'), { once: true });
    takeAudio.addEventListener('error', () => ended('mine'), { once: true });
    takeAudio.play().catch(() => ended('mine'));
    paint();
  }

  function goCompare() {
    stopPlayback();
    ctx.go(ctx.href('compare', { id: ctx.params.id }, { ...lineQuery, attempt: currentTakeRef }));
  }

  function tipMarkup(tip) {
    const label = errorLabel(tip.errorType);
    return html`<div class="s-speak-tip">
      <div class="s-speak-tip__text"><span class="s-speak-tip__word" lang="${langAttr(language)}">${tip.word}${tip.pinyin ? ` ${tip.pinyin}` : ''}</span> · ${label}${tip.weakest ? ` · ${t('weakestOf', { u: tip.weakest.label, n: tip.weakest.score })}` : ''}</div>
      <div class="s-speak-tip__actions">
        <button type="button" class="s-speak-btn" data-retry>${raw(icon('rotate-ccw', { size: 15 }))}${t('retry')}</button>
        <button type="button" class="s-speak-btn s-speak-btn--outline" data-play-model>${raw(icon('volume-2', { size: 15 }))}${t('hearModel')}</button>
      </div>
    </div>`;
  }

  function detailMarkup(detail) {
    const label = errorLabel(detail.errorType);
    return html`<div class="s-speak-detail">
      <div class="s-speak-detail__head"><b class="s-speak-detail__word" lang="${langAttr(language)}">${detail.word}</b>${detail.scoreKnown ? html`<span class="s-speak-detail__score" style="color:${detail.ink}">${detail.score}/100</span>` : ''}</div>
      ${detail.pinyin ? html`<div class="s-speak-detail__reading">${t('expectedReading', { reading: detail.pinyin })}</div>` : ''}
      <div class="s-speak-detail__issue">${label}${detail.weakest ? ` · ${t('weakestOf', { u: detail.weakest.label, n: detail.weakest.score })}` : ''}</div>
      <div class="s-speak-detail__actions">
        <button type="button" class="s-speak-mini" data-word-model="${detail.index}"${source.hasModelAudio && !pairWord(source.line.text,view.words,detail.index,source.line.wordTimings,source.language) ? raw(' disabled') : ''}>${filled('play', 14)}${t('modelWord')}</button>
        <button type="button" class="s-speak-mini s-speak-mini--ghost" data-close-detail>${t('close')}</button>
      </div>
    </div>`;
  }

  function tokenMarkup(shown) {
    const tokens = tokenStrip(source.line.text, language, shown ? view : pronunciationView(null));
    return tokens.map((unit) => {
      if (!unit.unit) return html`${unit.text}`;
      const active = shown && unit.wordIndex != null && tokenSel === unit.wordIndex;
      const rules = unit.band ? `border-bottom-color:${bandInk(unit.band)}` : '';
      const tappable = shown && unit.wordIndex != null;
      return html`<button type="button" class="${cls('s-speak-token', active && 's-speak-token--active')}" style="${rules}"${tappable ? raw(` data-token="${unit.wordIndex}" aria-pressed="${active}"`) : raw(' tabindex="-1"')} lang="${langAttr(language)}">${unit.text}</button>`;
    });
  }

  function resultMarkup() {
    if (!hasResult()) return '';
    const overall = view.overall;
    const ring = ringTone(overall);
    const ordinal = attemptOrdinal(takes, currentTakeRef);
    const current = takes.find((item) => item.id === currentTakeRef);
    const when = whenLabel(current?.at || Date.now(), languages().ui);
    const best = bestTake(takes);
    const isBest = takes.length > 1 && best?.id === currentTakeRef;
    const metrics = metricsFor(view);
    return html`<div class="s-speak-result">
      <div class="s-speak-result__head">
        <div class="s-speak-result__who">
          <div class="s-speak-ring" style="background:conic-gradient(${ring.ink} ${overall * 3.6}deg, var(--surface3) 0)"><div class="s-speak-ring__disc"><b>${overall}</b><span>${t('ringCaption')}</span></div></div>
          <div>
            <div class="s-speak-result__attempt">${t('attemptLabel', { n: ordinal, when })}</div>
            <div class="s-speak-result__verdict">${t(verdictKey(overall))}</div>
          </div>
        </div>
        ${isBest ? html`<span class="s-speak-badge">${t('bestAttempt')}</span>` : ''}
      </div>
      ${
        metrics.length
          ? html`<div class="s-speak-metrics">${metrics.map((m) => html`<div class="s-speak-metric"><div class="s-speak-metric__row"><span>${t(`metric${m.key[0].toUpperCase()}${m.key.slice(1)}`)}</span><b>${m.value ?? '—'}</b></div>${m.value == null ? '' : html`<div class="s-speak-metric__track"><i style="width:${Math.max(0, Math.min(100, m.value))}%;background:${m.ink}"></i></div>`}</div>`)}</div>`
          : ''
      }
      ${recognizedText() ? html`<div class="s-speak-asr">${t('asrLabel')} <i lang="${langAttr(language)}">“${recognizedText()}”</i> ${t('asrNote')}</div>` : ''}
      <div class="s-speak-actions">
        <button type="button" class="s-speak-primary" data-go-compare>${t('compareWithModel')}</button>
        <button type="button" class="s-speak-secondary" data-retry>${t('retry')}</button>
        <button type="button" class="s-speak-ai" data-ask-orena>${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${t('whereAmIGoingWrong')}</button>
      </div>
    </div>`;
  }

  function paint() {
    const scroller = q('[data-scroll-region]');
    const scrollTop = scroller?.scrollTop || 0;
    const focused = element.contains(document.activeElement) ? document.activeElement?.closest?.('[data-mic],[data-play-model],[data-play-mine],[data-token]') : null;
    const focusKey = focused ? (focused.matches('[data-token]') ? `[data-token="${focused.dataset.token}"]` : focused.matches('[data-mic]') ? '[data-mic]' : focused.matches('[data-play-mine]') ? '[data-play-mine]' : '.s-speak-side[data-play-model]') : '';

    const shown = hasResult();
    const now = phase();
    const pill = recorderState(now);
    const recording = now === TAKE.RECORDING;
    const processing = now === TAKE.PROCESSING;
    const tip = shown && tokenSel == null ? tipFor(view) : null;
    const detail = shown && tokenSel != null ? detailFor(view, tokenSel) : null;
    const captionKey = recCaptionKey(now, shown);
    const minePlayable = Boolean(takes.find((item) => item.id === currentTakeRef)?.url);
    const bars = recording ? liveWave(rec.levels) : restingWave();
    const tail = [t('segmentN', { n: source.line.ordinal }), source.level].filter(Boolean).join(' · ');

    originalPlayer?.park(element);
    mount(
      renderRoot,
      html`<div class="s-speak-header">
        <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
        <div class="s-speak-title-block">
          <div class="s-speak-title">${t('title')}</div>
          <div class="s-speak-sub">${t('fromOpen')}${langSpan(source.title, source.language)}${t('fromClose')} · ${tail}</div>
        </div>
        ${takes.length ? html`<button type="button" class="s-speak-compare" data-go-compare>${t('compare')}</button>` : ''}
      </div>
      <div class="s-speak-scroll" data-scroll-region>
        ${source.playback?.kind === 'embed' ? html`<div data-original-player></div>` : ''}
        <div class="s-speak-card">
          <div class="s-speak-label">${t('targetSentence')}</div>
          <div class="s-speak-line" lang="${langAttr(language)}">${tokenMarkup(shown)}</div>
          ${source.line.reading ? html`<div class="s-speak-reading">${source.line.reading}</div>` : ''}
          ${tip ? tipMarkup(tip) : ''}
          ${detail ? detailMarkup(detail) : ''}
          <div class="s-speak-recorder">
            <button type="button" class="s-speak-side" data-play-model>${playing === 'model' ? filled('pause', 16) : raw(icon('volume-2', { size: 16 }))}${t('model')}</button>
            <span class="s-speak-spacer"></span>
            <div class="s-speak-mid">
              <div class="s-speak-pill" style="background:${pill.bg};color:${pill.ink}"><i></i><b>${t(`state${pill.key[0].toUpperCase()}${pill.key.slice(1)}`)}</b>${recording ? html`<span data-clock>${clockLabel(rec.elapsedMs)} / ${clockLabel(MAX_TAKE_MS)}</span>` : ''}</div>
              <button type="button" class="s-speak-mic" data-mic aria-pressed="${recording}" aria-label="${recording ? t('stop') : t('record')}">${recording ? html`<span class="s-speak-mic__stop"></span>` : raw(icon('mic', { size: 28 }))}</button>
              <span class="s-speak-caption" data-caption>${captionKey ? t(captionKey, { s: (rec.elapsedMs / 1000).toFixed(1) }) : ''}</span>
            </div>
            <span class="s-speak-spacer"></span>
            <button type="button" class="s-speak-side" data-play-mine${minePlayable ? '' : raw(' disabled')}>${playing === 'mine' ? filled('pause', 16) : filled('play', 14)}${t('mine')}</button>
          </div>
          <div class="${cls('s-speak-wave', (recording || playing) && 's-speak-wave--on', recording && 's-speak-wave--rec')}" data-wave>${bars.map((height, at) => html`<i style="height:${height}%;animation-delay:${(at * 41) % 700}ms"></i>`)}</div>
          ${processing ? html`<div class="s-speak-processing">${t('processingLabel')}</div>` : ''}
        </div>
        ${resultMarkup()}
      </div>`,
    );
    if (originalPlayer) originalPlayer.attach(source.playback.kind === 'embed' ? q('[data-original-player]') : element);
    if (source.lessonId && !source.hasModelAudio) element.querySelectorAll('[data-play-model],[data-word-model]').forEach(button => { button.disabled = true; });
    bind();
    const region = q('[data-scroll-region]');
    if (region) region.scrollTop = scrollTop;
    if (focusKey) q(focusKey)?.focus({ preventScroll: true });
  }

  function bind() {
    q('[data-back]').addEventListener('click', () => ctx.back());
    element.querySelectorAll('[data-play-model]').forEach((btn) => btn.addEventListener('click', playModel));
    q('[data-play-mine]')?.addEventListener('click', playMine);
    q('[data-mic]').addEventListener('click', () => (phase() === TAKE.RECORDING ? recorder.stop() : begin()));
    element.querySelectorAll('[data-go-compare]').forEach((btn) => btn.addEventListener('click', goCompare));
    element.querySelectorAll('[data-retry]').forEach((btn) => btn.addEventListener('click', () => begin()));
    q('[data-ask-orena]')?.addEventListener('click', () => {
      const attemptId = attemptIdOf(currentTakeRef);
      askOrena({
        surface: 'speaking.workspace',
        activity_type: 'pronunciation_practice',
        content_id: ctx.params.id,
        take_ref: currentTakeRef || undefined,
        // The stored record is named only together with the line (AGENT_CONTRACT §3, gap N-9).
        ...(attemptId ? { attempt_id: attemptId } : {}),
        selected_item: { type: 'sentence', id: source.line.lineId, text: source.line.text },
      });
    });
    element.querySelectorAll('[data-token]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const at = Number(btn.dataset.token);
        tokenSel = tokenSel === at ? null : at;
        paint();
      });
    });
    q('[data-close-detail]')?.addEventListener('click', () => {
      tokenSel = null;
      paint();
    });
    q('[data-word-model]')?.addEventListener('click', () => playModelWord(Number(q('[data-word-model]').dataset.wordModel)));
  }

  paint();

  /* Actions the agent may run while this room is open (AGENT_CONTRACT §7). A take the agent names
     that this tab does not hold is "unknown", said as such and never guessed at. */
  const takeNamed = (payload) => {
    const ref = payload?.take_ref;
    if (!ref) return takes.find((item) => item.id === currentTakeRef) || null;
    return takes.find((item) => item.id === ref) || null;
  };
  const releasers = [
    registerActionHandler('play_model', () => {
      if (source.lessonId && !source.hasModelAudio) return { ok: false, reason: 'unavailable' };
      playModel();
      return { ok: true };
    }),
    registerActionHandler('play_user', (payload) => {
      const named = takeNamed(payload);
      if (!named?.url) return { ok: false, reason: 'unknown_take' };
      currentTakeRef = named.id;
      view = viewOfTake(named);
      paint();
      playMine();
      return { ok: true };
    }),
    registerActionHandler('say_again', () => {
      if (recorder.busy) return { ok: false, reason: 'busy' };
      void begin();
      return { ok: true };
    }),
    registerActionHandler('compare_with_model', (payload) => {
      const named = takeNamed(payload);
      if (!named) return { ok: false, reason: 'unknown_take' };
      ctx.go(ctx.href('compare', { id: ctx.params.id }, { ...lineQuery, attempt: named.id }));
      return { ok: true };
    }),
  ];

  return () => {
    releasers.forEach((release) => release());
    recorder.dispose();
    stopPlayback();
    originalPlayer?.dispose();
  };
}
