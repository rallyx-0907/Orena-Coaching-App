/* Compare With Model (frame 16 + the embedded `Compare With Model.dc.html`, `#/speak/:id/compare`;
   D-091). The frame is a recorder and its analysis in one: a record card until there is a take,
   then the result summary, the word detail, and a sticky playback bar. This room reads this line's
   own takes (`product/take-store.js`, D-076) and records a new one in place through the same
   recorder Scripted Pronunciation uses (`product/speaking-recorder.js`) - real audio, decoded and
   measured client-side (`capabilities/audio-analysis.js`'s YIN pitch tracker, not the design
   prototype's own from-scratch `acf()`/synthesized model contour, SCRATCH/inventory/
   C5-listening-dictation-speaking.md §5).

   Paired word plots follow the approved frame. Learner plots use measured audio and provider
   word intervals; model word plots/timing stay unavailable until source word intervals exist.
   Prototype demonstration contours and coaching claims are never substituted for evidence. */
import { html, mount, raw, cls } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { useStyles } from '../../kit/styles.js';
import { loadingMarkup } from '../../kit/states.js';
import { langAttr } from '../../kit/lang.js';
import { toast } from '../../kit/toast.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
import { loadSpeakingSource, segmentOf } from '../../product/speaking-source.js';
import { lineUnits } from '../../product/speaking-line.js';
import { comparisonReference, decorateComparison, pairWord, pairedTiming, readingFor } from '../../product/compare-reference.js';
import { toneOf } from '../../capabilities/pronunciation-result.js';
import { decodeAudio, analyse } from '../../capabilities/audio-analysis.js';
import { createSpeakingRecorder, TAKE } from '../../product/speaking-recorder.js';
import { lineKey, listTakes, viewOfTake } from '../../product/take-store.js';
import { micStateFor } from '../speak/model.js';
import { openMicState, micGate } from '../mic/sheet.js';
import { t } from './copy.js';
import {
  ringColor, scoreLabelKey, headlineKey, wordStatus, pronunciationStatusKey, statusTone, tileMinWidth, wordDetailFor, defaultWordIndex,
  chipsFor, metricLineFor, axisFor, CHART, chartLines, hasVoice, wordPitchLines, wordPages, PLAYBACK_MODES, nextSpeed, playPlan, pillsFor, toneKey,
} from './model.js';

const filled = (name, size) => raw(icon(name, { size }).replace('fill="none"', 'fill="currentColor"'));
const glyph = (kind, size = 18) => raw(icon(kind === 'ok' ? 'circle-check' : kind === 'bad' ? 'circle-x' : kind === 'clock' ? 'clock' : 'info', { size, stroke: 2.2 }));
const KIND_INK = { ok: 'var(--green)', bad: 'var(--red)', clock: 'var(--amber)', info: 'var(--muted)' };
const MODE_KEY = { model_then_you: 'modeModelYou', word_by_word: 'modeWord', model_only: 'modeModel', you_only: 'modeYou' };
const ERROR_KEY = {
  no_speech: 'errNotHeard', too_short: 'errNotHeard', offline: 'errOffline', unavailable: 'errService', service: 'errService',
  microphone: 'errMic', unsupported: 'errMic', recording_failed: 'errMic', too_long: 'errTooLong', audio_unsupported: 'errAudio', line_invalid: 'errLine',
};
const seconds = (ms) => (ms / 1000).toFixed(2);

/* The provider's own miscue verdict on a word, translated - a type this copy table has no key for
   still reads as "not passed" rather than the raw provider string. */
function errorLabel(errorType) {
  if (!errorType || errorType === 'None') return t('passed');
  const key = `error${errorType}`;
  return t.has(key) ? t(key) : t('errorOther');
}

export default async function mountCompareWithModel(element, ctx) {
  await useStyles('screens/compare/compare.css');
  const language = ctx.context?.language || 'en';
  const { ui, support } = languages();
  const segmentId = segmentOf(ctx.query);
  const lineQuery = segmentId ? { segment: segmentId } : {};

  mount(element, loadingMarkup(shellCopy('loadingLesson')));
  element.classList.add('s-compare-root');

  const source = await loadSpeakingSource(ctx.params.id, { api, support, language, owner: ctx.context.owner || 'local', segmentId });
  if (!ctx.isCurrent()) return undefined;
  ctx.setCrumb(t('title'));
  ctx.context?.memory?.enter?.({id:source.sourceId, title:source.title,
    intent:'speaking_compare', segment:source.line.lineId});

  const key = lineKey(source.sourceId, source.line.lineId);
  let takes = await listTakes(key);
  if (!ctx.isCurrent()) return undefined;

  const requested = ctx.query.get('attempt');
  let selectedId = takes.some((item) => item.id === requested) ? requested : takes[0]?.id || '';
  let wordSel = null;
  let tab = 'pitch';
  let mode = source.hasModelAudio ? PLAYBACK_MODES[0] : 'you_only';
  let speed = 1;
  let errorText = '';
  let rec = { phase: TAKE.IDLE, levels: new Array(40).fill(0), elapsedMs: 0 };
  const contours = new Map(); // take id -> { you } once measured
  let playing = false;
  let playWord = null; // the word being played in "Word by word"
  let playToken = 0;
  let audioEl = null;
  let finishAudio = null;
  let revealSelection = true; // the first paint, and every change of attempt, brings the selection into view
  let tileWidth = Math.max(1, element.clientWidth - 48);
  let sizing = null;
  let reference = null;
  let showReferenceWait = false;
  let referenceTimer = 0;

  const q = (selector) => element.querySelector(selector);
  const takeOf = (id) => takes.find((item) => item.id === id) || null;
  const selectedTake = () => takeOf(selectedId);
  const viewNow = () => decorateComparison(viewOfTake(selectedTake()), source, reference);
  const modelWordFor = (word) => pairWord(source.line.text, viewNow()?.words || [], word?.index, reference?.words || [], language);
  const referencePending = () => !reference || ['readingState','audioState','alignmentState'].some(key=>reference[key]==='processing');

  async function prepareReference(fresh = false) {
    clearTimeout(referenceTimer);
    if (fresh) reference=null;
    referenceTimer=setTimeout(()=>{if(ctx.isCurrent()){showReferenceWait=true;paint();}},2300);
    let value;
    try {
      value=await comparisonReference(source,{api,support,owner:ctx.context.owner || 'local',fresh,
        onUpdate(next){if(ctx.isCurrent()){reference=next;paint();}},
      });
    } catch(error) {
      clearTimeout(referenceTimer);
      if (!ctx.isCurrent()) return;
      if (error.status === 404) { ctx.go(ctx.href('library')); return; }
      value={readings:{},positionReadings:[],words:[],model:null,readingState:'unavailable',audioState:'unavailable',alignmentState:'unavailable'};
    }
    clearTimeout(referenceTimer);
    if(ctx.isCurrent()){reference=value;showReferenceWait=false;paint();}
  }

  function referenceStatusMarkup() {
    if (referencePending()) {
      if (!showReferenceWait) return '';
      const states=['readingState','audioState','alignmentState'];
      const done=states.filter(key=>reference && reference[key]!=='processing').length;
      const label=t(!reference || reference.audioState==='processing'?'referenceAudio':reference.alignmentState==='processing'?'referenceAlignment':'referenceReading');
      return html`<div class="o-processing s-compare-reference" role="status" aria-live="polite"><span>${label}</span><progress class="o-loading__progress" max="3" value="${done}" aria-label="${label}"></progress></div>`;
    }
    if (source.hasModelAudio && reference?.alignmentState==='unavailable') return html`<div class="s-compare-error">${t('referenceFailed')} <button type="button" class="s-compare-ghost" data-reference-retry data-fk="reference-retry">${t('retryReference')}</button></div>`;
    return '';
  }
  const openWord = () => {
    const view = viewNow();
    if (playWord != null && view?.words?.[playWord]) return playWord;
    if (wordSel != null && view?.words?.[wordSel]) return wordSel;
    return defaultWordIndex(view);
  };

  function select(id) {
    stopPlay();
    revealSelection = true;
    selectedId = id;
    wordSel = defaultWordIndex(viewNow());
    errorText = '';
    paint();
    void measure(id);
  }

  /* ---- Recording in place ---- */
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
        if (finished?.take_ref && finished.take_ref !== selectedId && next.phase === TAKE.RESULT) {
          takes = finished.list;
          revealSelection = true;
          selectedId = finished.take_ref;
          wordSel = defaultWordIndex(viewOfTake(takeOf(selectedId)));
          errorText = '';
          void measure(selectedId);
        }
        if (next.phase === TAKE.RECORDING) errorText = '';
        rec = { ...rec, ...next };
        paint();
      },
      level(levels) {
        rec = { ...rec, levels };
        paintLive();
      },
      failure(error) {
        // A failure the same take can be scored again after (the service, the network) is offered
        // that through the mic sheet; every other one is the frame's own banner.
        if (error.retry) {
          errorText = '';
          openMicState(ctx, {
            state: micStateFor(error.kind),
            onAction: (action) => {
              if (action === 'tryagain' || action === 'retry') recorder.retry();
            },
          });
          return;
        }
        errorText = t(ERROR_KEY[error.kind] || 'errService');
      },
    },
  });

  function record() {
    if (recorder.busy) return;
    stopPlay();
    micGate(ctx, () => recorder.start());
  }

  /* ---- Measuring the audio (browser side) ---- */
  async function measure(id) {
    const take = takeOf(id);
    if (!contours.has(id)) {
      contours.set(id, 'loading');
      const you = take?.blob ? await decodeAudio(take.blob).then((decoded) => analyse(decoded)).catch(() => null) : null;
      contours.set(id, { you });
    }
    if (ctx.isCurrent() && selectedId === id) paint();
  }

  /* ---- Playback ---- */
  function stopPlay() {
    finishAudio?.();
    finishAudio=null;
    playToken++;
    audioEl?.pause();
    audioEl = null;
    playing = false;
    playWord = null;
  }
  const alive = (token) => token === playToken && ctx.isCurrent();

  function playFile(url, token, { from = 0, to = Infinity } = {}) {
    return new Promise((resolve) => {
      if (!url || !alive(token)) return resolve();
      audioEl?.pause();
      const el = new Audio(url);
      audioEl = el;
      el.playbackRate = speed;
      let settled=false;
      const done = () => {if(settled)return;settled=true;if(finishAudio===done)finishAudio=null;resolve();};
      finishAudio=done;
      el.addEventListener('ended', done, { once: true });
      el.addEventListener('error', done, { once: true });
      if (Number.isFinite(to)) {
        el.addEventListener('timeupdate', () => {
          if (el.currentTime >= to) {
            el.pause();
            done();
          }
        });
      }
      const start = () => {
        if (!alive(token) || audioEl !== el) { el.pause(); done(); return; }
        if (from > 0) el.currentTime = from;
        el.play().catch(done);
      };
      if (from > 0 && el.readyState < 1) el.addEventListener('loadedmetadata', start, { once: true });
      else start();
    });
  }
  const playModelLine = (token) => {
    if (source.hasModelAudio) return playFile(source.modelAudioUrl(source.line.lineId), token);
    toast(t('modelUnavailable'));
    return Promise.resolve();
  };
  const wordSpan = (word) => ({ from: Math.max(0, word.offsetMs / 1000 - 0.08), to: (word.offsetMs + word.durationMs) / 1000 + 0.08 });

  async function playAll() {
    if (playing) {
      stopPlay();
      paint();
      return;
    }
    stopPlay();
    const take = selectedTake();
    const view = viewNow();
    const hasTake = Boolean(take?.url);
    if (mode !== 'model_only' && !hasTake) toast(t('noTakeAudio'));
    const plan = playPlan(mode, { hasTake, hasWords: Boolean(view?.words?.some((word) => word.offsetKnown)) });
    if (!plan.length) return;
    const token = ++playToken;
    playing = true;
    paint();
    for (const step of plan) {
      if (!alive(token)) return;
      if (step === 'model') await playModelLine(token);
      else if (step === 'you') await playFile(take.url, token);
      else if (step === 'words') {
        for (const word of view.words) {
          if (!alive(token)) return;
          playWord = word.index;
          paint();
          const modelWord = modelWordFor(word);
          if (modelWord) await playFile(source.modelAudioUrl(source.line.lineId), token, wordSpan(modelWord));
          if (word.offsetKnown) await playFile(take.url, token, wordSpan(word));
        }
      }
    }
    if (alive(token)) {
      playing = false;
      playWord = null;
      paint();
    }
  }

  function hearYours(word) {
    const take = selectedTake();
    if (!take?.url || !word?.offsetKnown) {
      toast(t('noTakeAudio'));
      return;
    }
    stopPlay();
    const token = playToken;
    void playFile(take.url, token, wordSpan(word));
  }
  function hearWordModel(word) {
    stopPlay();
    const modelWord = modelWordFor(word);
    if (modelWord) void playFile(source.modelAudioUrl(source.line.lineId), playToken, wordSpan(modelWord));
    else toast(t('modelWordUnavailable'));
  }

  /* ---- Markup ---- */
  function tagLabel() {
    let name = language;
    try {
      name = new Intl.DisplayNames([ui], { type: 'language' }).of(language) || language;
    } catch {
      /* the code itself reads as a fallback */
    }
    return [name, source.level].filter(Boolean).join(' · ');
  }

  function tokensMarkup() {
    const units = lineUnits(source.line.text, language);
    const syllables = language === 'zh' ? String(source.line.reading || '').split(/\s+/).filter(Boolean) : [];
    const aligned = language === 'zh' && syllables.length === units.filter(unit=>unit.unit).length;
    let spokenAt = 0;
    return units.map((unit) => {
      if (!unit.unit) return unit.text.trim() ? html`<span class="s-compare-token"><span class="s-compare-token__sub" aria-hidden="true">${raw('&nbsp;')}</span><span class="s-compare-token__word" lang="${langAttr(language)}">${unit.text}</span></span>` : '';
      const reading = aligned ? syllables[spokenAt++] : readingFor(unit.text, reference, language, unit.start);
      const tone = language === 'zh' && reading ? toneOf(reading) : null;
      return html`<span class="s-compare-token"><span class="s-compare-token__sub" title="${reading ? '' : t('readingUnavailable')}" style="color:${tone && tone < 5 ? `var(--tone${tone})` : 'var(--text3)'}">${reading || '—'}</span><span class="s-compare-token__word" lang="${langAttr(language)}">${unit.text}</span></span>`;
    });
  }

  function liveLine() {
    const points = rec.levels.map((level, at) => `${(at * (300 / 39)).toFixed(1)},${(30 - Math.min(1, level) * 26).toFixed(1)}`).join(' ');
    return points;
  }

  function recordCard() {
    const recording = rec.phase === TAKE.RECORDING;
    const processing = rec.phase === TAKE.PROCESSING;
    const title = recording ? t('listeningTitle') : processing ? t('assessingTitle') : t('readyTitle');
    return html`<div class="s-compare-card s-compare-record">
      <div class="s-compare-record__top">
        <span class="s-compare-tag">${tagLabel()}</span>
        <div class="s-compare-record__tools">
          <button type="button" class="s-compare-tool" data-fk="hear" data-hear-line ${source.hasModelAudio ? '' : raw('disabled')} title="${source.hasModelAudio ? '' : t('modelUnavailable')}">${raw(icon('volume-2', { size: 17 }))}${t('hearModel')}</button>
          <button type="button" class="s-compare-speed" data-fk="speed" data-speed>${t('speedUnit', { n: speed })}</button>
        </div>
      </div>
      <div class="s-compare-tokens">${tokensMarkup()}</div>
      ${source.hasModelAudio ? '' : html`<p class="s-compare-note">${t('modelUnavailable')}</p>`}
      <div class="s-compare-recrow">
        <button type="button" class="s-compare-mic${recording ? ' is-rec' : ''}" data-fk="mic" data-mic aria-pressed="${recording}" aria-label="${recording ? t('stop') : t('record')}"${processing ? raw(' disabled') : ''} style="${recording ? `box-shadow:0 0 0 ${Math.round(4 + Math.max(...rec.levels, 0) * 18)}px var(--ring),var(--sh2)` : ''}">${recording ? html`<span class="s-compare-mic__stop"></span>` : raw(icon('mic', { size: 28 }))}</button>
        <div class="s-compare-recrow__status">
          <div class="s-compare-recrow__title" style="color:${recording ? 'var(--red)' : 'var(--text)'}">${title}</div>
          <div class="s-compare-note" data-record-status>${t(recording ? 'recordingSub' : processing ? 'assessingSub' : 'readySub', {s:Math.floor(rec.elapsedMs/1000)})}</div>
          ${processing ? html`<progress class="o-loading__progress" aria-label="${t('assessingTitle')}"></progress>` : ''}
          ${recording ? html`<svg viewBox="0 0 300 60" class="s-compare-live" aria-hidden="true"><polyline data-live points="${liveLine()}" fill="none" stroke="var(--green)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"></polyline></svg>` : ''}
        </div>
      </div>
    </div>`;
  }

  function pillsMarkup() {
    return html`<div class="s-compare-pills">${pillsFor(takes, selectedId).map(
      (pill) => html`<button type="button" class="${cls('s-compare-pill', pill.active && 's-compare-pill--active')}" data-select="${pill.id}" data-fk="pill-${pill.n}" aria-pressed="${pill.active}"><span class="s-compare-pill__label">${t('attemptN', { n: pill.n })}</span><span class="s-compare-pill__score">${pill.score ?? '—'}</span>${pill.crown ? html`<span class="s-compare-pill__crown">${filled('crown', 18)}</span>` : ''}</button>`,
    )}</div>`;
  }

  function chartMarkup({ model, you, bands = [], width = CHART.width }) {
    const g = (paths, color) => paths.map((points) => `<polyline points="${points}" stroke="${color}" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline>`).join('');
    const shade = bands
      .map((band) => `<rect x="${(band.from * width).toFixed(1)}" y="0" width="${Math.max(2, (band.to - band.from) * width).toFixed(1)}" height="${CHART.height}" fill="${band.status === 'wrong' ? 'var(--red-soft)' : 'var(--amber-soft)'}"></rect>`)
      .join('');
    const right = CHART.x + width;
    return html`<svg viewBox="0 0 ${width + 48} 130" class="s-compare-chart" aria-hidden="true">
      <line x1="40" y1="20" x2="${right}" y2="20" stroke="var(--border)"></line><line x1="40" y1="65" x2="${right}" y2="65" stroke="var(--border)" stroke-dasharray="4 4"></line><line x1="40" y1="110" x2="${right}" y2="110" stroke="var(--border)"></line>
      <text x="0" y="24" font-size="11" fill="var(--muted)">${t('chartHigh')}</text><text x="0" y="114" font-size="11" fill="var(--muted)">${t('chartLow')}</text>
      <g transform="translate(${CHART.x} ${CHART.y})">${raw(shade)}${raw(g(model, 'var(--accent)'))}${raw(g(you, 'var(--green)'))}</g>
    </svg>`;
  }

  function pitchPair(word, take, width = 100) {
    const you=contours.get(take.id)?.you, model=reference?.model, modelWord=modelWordFor(word);
    const values=[...[you, model].flatMap((audio,at)=>{
      const span=at===0 ? word : modelWord;
      return span?.offsetKnown ? (audio?.contour || []).filter(p=>p.st!=null && p.t>=span.offsetMs/1000 && p.t<=(span.offsetMs+span.durationMs)/1000).map(p=>Math.abs(p.st)) : [];
    })];
    const range=Math.max(2,...values.map(v=>v*1.15));
    return {model:wordPitchLines(model,modelWord,{width,range}),you:wordPitchLines(you,word,{width,range}),modelWord};
  }

  function miniPitch(lines, who, reason, processing = false) {
    return html`<span class="s-compare-tile__voice"><span>${t(who)}</span>${lines.length
      ? html`<svg viewBox="0 0 100 90" preserveAspectRatio="none" aria-hidden="true">${lines.map(points => html`<polyline points="${points}" fill="none" stroke="${who==='legendModel'?'var(--accent)':'var(--green)'}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"></polyline>`)}</svg>`
      : html`<span class="s-compare-tile__missing" title="${reason}" aria-label="${reason}">${processing ? html`<span class="o-spinner"></span>` : '—'}</span>`}</span>`;
  }

  function tilesMarkup(view, take) {
    const pages = wordPages(view.words, tileWidth, language);
    const pageAt = Math.max(0, pages.findIndex(page => page.some(word => word.index === (playWord ?? openWord()))));
    const page = pages[pageAt] || [];
    const analysis = contours.get(take.id);
    return html`<div class="s-compare-tiles"><div class="s-compare-tiles__row">${page.map((word) => {
      const status = wordStatus(word);
      const tone = statusTone(status);
      const on = openWord() === word.index || playWord === word.index;
      const ring = on ? `inset 0 0 0 2px ${playWord === word.index ? 'var(--accent)' : tone.stroke}` : 'none';
      const bg = status === 'ok' && on ? 'var(--green-soft)' : tone.bg;
      const sub = word.reading || word.pinyin || '';
      const pair = pitchPair(word,take);
      return html`<button type="button" class="s-compare-tile" data-word="${word.index}" data-fk="word-${word.index}" aria-pressed="${openWord() === word.index}" style="min-width:${Math.min(tileWidth, tileMinWidth(word.text, language))}px;flex-grow:${Math.max(1, word.durationMs || 0)};background:${bg};box-shadow:${ring}"><span class="s-compare-tile__word" lang="${langAttr(language)}" style="color:${tone.ink}">${word.text}</span><span class="s-compare-tile__sub" style="color:${tone.sub}">${sub || raw('&nbsp;')}</span><span class="s-compare-tile__pair">${miniPitch(pair.model, 'legendModel', t(pair.modelWord ? 'pitchUnavailable' : 'modelWordUnavailable'), !reference || reference.alignmentState==='processing')}<span class="s-compare-tile__divider"></span>${miniPitch(pair.you, 'legendYou', t('pitchUnavailable'), !analysis || analysis==='loading')}</span></button>`;
    })}</div>${pages.length > 1 ? html`<div class="s-compare-wordnav"><button type="button" class="o-iconbtn" data-word="${pages[pageAt - 1]?.[0]?.index ?? 0}" data-fk="previous-words" aria-label="${t('previousWords')}"${pageAt === 0 ? raw(' disabled') : ''}>${raw(icon('chevron-left', {size:18}))}</button><span>${t('wordRange', {from:page[0].index + 1, to:page.at(-1).index + 1, total:view.words.length})}</span><button type="button" class="o-iconbtn" data-word="${pages[pageAt + 1]?.[0]?.index ?? 0}" data-fk="next-words" aria-label="${t('nextWords')}"${pageAt === pages.length - 1 ? raw(' disabled') : ''}>${raw(icon('chevron-right', {size:18}))}</button></div>` : ''}</div>`;
  }

  function ringMarkup(score) {
    const color = ringColor(score);
    const c = 2 * Math.PI * 46;
    return html`<div class="s-compare-ring"><svg viewBox="0 0 112 112" aria-hidden="true"><circle cx="56" cy="56" r="46" fill="none" stroke="var(--surface3)" stroke-width="9"></circle><circle cx="56" cy="56" r="46" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" stroke-dasharray="${((c * score) / 100).toFixed(1)} ${c.toFixed(1)}"></circle></svg><div class="s-compare-ring__center"><b>${score}</b><small>${t('scoreOutOf')}</small></div></div>`;
  }

  function summaryMarkup(view, take) {
    const score = view.overall;
    const chips = chipsFor(view);
    const line = metricLineFor(view);
    const axis = axisFor(view);
    const metricText = [
      ...line.parts.map((part) => `${t(part.key)} ${part.value}`),
      ...(line.speechS != null ? [t('speechSeconds', { s: line.speechS })] : []),
    ].join(' · ');
    return html`<div class="s-compare-card s-compare-summary">
      <div class="s-compare-summary__top">
        <div class="s-compare-scorecol">${ringMarkup(score)}<span class="s-compare-scorelabel" style="color:${ringColor(score)}">${t(scoreLabelKey(score))}</span></div>
        <div class="s-compare-summary__copy">
          <div class="s-compare-headline">${t(headlineKey(score))}</div>
          <div class="s-compare-chips">${chips.map((chip) => html`<span class="s-compare-chip"><span style="color:${KIND_INK[chip.kind]};display:flex">${glyph(chip.kind)}</span>${chip.key === 'chipUnclear' ? t.plural('chipUnclear', chip.params.n) : t(chip.key, chip.params)}</span>`)}</div>
          ${metricText ? html`<div class="s-compare-metricline">${metricText}</div>` : ''}
        </div>
      </div>
      <div class="s-compare-legendrow">
        <div class="s-compare-legend">
          <span><i style="background:var(--accent)"></i>${t('legendModel')}</span>
          <span><i style="background:var(--green)"></i>${t('legendYou')}</span>
        </div>
        <div class="s-compare-legend s-compare-legend--small">
          <span><i class="s-compare-swatch s-compare-swatch--close"></i>${t('legendClose')}</span>
          <span><i class="s-compare-swatch s-compare-swatch--bad"></i>${t('legendNeedsWork')}</span>
        </div>
      </div>
      ${view.words.length ? tilesMarkup(view, take) : ''}
      ${axis ? html`<div class="s-compare-axis">${t('axisRight', { model: axis.modelS, you: axis.youS })}</div>` : ''}
    </div>`;
  }

  function wordChart(detail, take) {
    const analysis = contours.get(take.id);
    if (!analysis || analysis === 'loading' || !reference || reference.alignmentState === 'processing') return html`<div class="s-compare-chart s-compare-chart--wait" role="status" aria-label="${t('referenceAlignment')}"><span class="o-spinner"></span></div>`;
    const pair=pitchPair(detail,take,CHART.width);
    if (!pair.model.length && !pair.you.length) return html`<p class="s-compare-note">${t('pitchUnavailable')}</p>`;
    return html`${chartMarkup(pair)}${!pair.you.length ? html`<p class="s-compare-note">${t('yourLineUnavailable')}</p>` : ''}`;
  }

  function panelMarkup(detail, take) {
    if (tab === 'timing') {
      const modelWord=modelWordFor(detail);
      const timing=pairedTiming(detail,modelWord,viewNow().words,reference?.words || []);
      const row=(span,who,color)=>html`<span class="s-compare-timing__who" style="color:${color}">${t(who)}</span><div class="s-compare-timing__track">${span ? html`<span style="left:${(span.from/timing.total*100).toFixed(1)}%;width:${((span.to-span.from)/timing.total*100).toFixed(1)}%;background:${color}"></span>` : ''}</div>`;
      const spanText=(span,who)=>html`<span><span class="s-compare-muted">${t(who)} </span>${span ? t('timingSpan',{from:span.from.toFixed(2),to:span.to.toFixed(2)}) : t(who==='legendModel'?'modelWordUnavailable':'wordUnavailable')}</span>`;
      const delta=timing.deltaMs;
      return html`<div class="s-compare-panel">
        <div class="s-compare-panel__title">${t('timingTitle',{word:detail.text})}</div>
        <div class="s-compare-timing">${row(timing.model,'legendModel','var(--accent)')}${row(timing.you,'legendYou','var(--green)')}
          <span></span><div class="s-compare-timing__axis"><span>0 s</span><span>${timing.total.toFixed(2)} s</span></div>
        </div>
        <div class="s-compare-panel__body">${spanText(timing.model,'legendModel')}${spanText(timing.you,'legendYou')}
          ${delta==null ? '' : html`<span>${t(delta===0?'timingSame':delta>0?'timingLonger':'timingShorter',{s:(Math.abs(delta)/1000).toFixed(2)})}</span>`}
          <span class="s-compare-muted">${t('timingCompared')}</span>
        </div>
      </div>`;
    }
    if (tab === 'pron') {
      const ok = detail.status === 'ok';
      const title = t(pronunciationStatusKey(detail));
      const ink = ok ? 'var(--green)' : 'var(--red)';
      const heard = viewNow()?.heard;
      return html`<div class="s-compare-panel">
        <div class="s-compare-panel__status" style="color:${ink}">${glyph(ok ? 'ok' : 'bad')}${title}</div>
        ${
          detail.sounds.length
            ? html`<div class="s-compare-sounds"><span class="s-compare-muted">${t('pronSounds')}</span>${detail.sounds.map((sound) => html`<span class="s-compare-sound" style="${sound.score == null ? '' : `color:${sound.score >= 85 ? 'var(--green)' : sound.score >= 65 ? 'var(--amber)' : 'var(--red)'}`}">${sound.label}${sound.score == null ? '' : html` <b>${sound.score}</b>`}</span>`)}</div>`
            : detail.scoreKnown
              ? ''
              : html`<p class="s-compare-note">${t('wordUnavailable')}</p>`
        }
        ${heard ? html`<div class="s-compare-panel__heard">${t('pronHeard', { text: heard })}</div>` : ''}
      </div>`;
    }
    const toneTitle = language === 'zh' && detail.toneTarget != null && detail.pinyin;
    return html`<div class="s-compare-panel">
      <div class="s-compare-panel__title">${toneTitle ? t('toneTitle', { word: detail.text, pinyin: detail.pinyin, n: detail.toneTarget, name: t(toneKey(detail.toneTarget)) }) : t('pitchTitle', { word: detail.text })}</div>
      ${wordChart(detail, take)}
      <div class="s-compare-legend"><span><i style="background:var(--accent)"></i>${t('legendModel')}</span><span><i style="background:var(--green)"></i>${t('legendYou')}</span></div>
      ${modelWordFor(detail) ? '' : html`<p class="s-compare-note">${t('modelWordUnavailable')}</p>`}
    </div>`;
  }

  function detailMarkup(view, take) {
    const at = openWord();
    const detail = at == null ? null : wordDetailFor(view, at);
    if (!detail) return '';
    const tone = detail.tone;
    const ringPct = detail.scoreKnown ? detail.score : 0;
    const c = 2 * Math.PI * 26;
    // What the assessment found in this word: its miscue when the provider flagged it, and the
    // weakest sound when one sat below the "good" line (85). A clean word has nothing to add.
    const weak = detail.weakest && detail.weakest.score < 85 ? t('weakestOf', { u: detail.weakest.label, n: detail.weakest.score }) : '';
    const finding = detail.flagged || weak ? [detail.flagged ? errorLabel(detail.errorType) : '', weak].filter(Boolean).join(' · ') : '';
    const rows = [
      ...(language === 'zh' && detail.toneTarget != null ? [{ label: t('rowTone'), value: `${detail.toneTarget} · ${t(toneKey(detail.toneTarget))}`, ink: 'var(--text)', kind: '' }] : []),
      ...(detail.offsetKnown ? [{ label: t('rowStart'), value: `${seconds(detail.offsetMs)} s`, ink: 'var(--text)', kind: '' }, { label: t('rowLength'), value: `${seconds(detail.durationMs)} s`, ink: 'var(--text)', kind: '' }] : []),
      { label: t('rowPron'), value: t(pronunciationStatusKey(detail)), ink: detail.status === 'ok' ? 'var(--green)' : 'var(--red)', kind: detail.status === 'ok' ? 'ok' : 'bad' },
    ];
    return html`<div class="s-compare-card s-compare-detail">
      <div class="s-compare-detail__a">
        <div class="s-compare-detail__head">
          <div class="s-compare-detail__label">${t('wordDetail')}</div>
          ${
            detail.scoreKnown
              ? html`<div class="s-compare-detail__score"><span>${t('wordScore')}</span><div class="s-compare-mini"><svg viewBox="0 0 62 62" aria-hidden="true"><circle cx="31" cy="31" r="26" fill="none" stroke="var(--surface3)" stroke-width="6"></circle><circle cx="31" cy="31" r="26" fill="none" stroke="${tone.stroke}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${((c * ringPct) / 100).toFixed(1)} ${c.toFixed(1)}"></circle></svg><b>${detail.score}</b></div></div>`
              : ''
          }
        </div>
        <div class="s-compare-detail__word"><span lang="${langAttr(language)}">${detail.text}</span><button type="button" class="s-compare-round" data-fk="hear-word" data-hear-word title="${t('hearWord')}" aria-label="${t('hearWord')}">${raw(icon('volume-2', { size: 18 }))}</button></div>
        <div class="s-compare-detail__sub">${detail.reading ? html`<span class="s-compare-detail__reading">${detail.reading}</span>` : ''}<span class="s-compare-status" style="background:${tone.pillBg};color:${tone.pillInk}">${t(tone.pillKey)}</span></div>
        ${finding ? html`<div class="s-compare-tip"><span class="s-compare-tip__icon">${raw(icon('lightbulb', { size: 18 }))}</span><span>${finding}</span></div>` : ''}
      </div>
      <div class="s-compare-detail__b">
        <div class="s-compare-tabs" role="tablist">${[['pitch', language === 'zh' ? t('tabTone') : t('tabPitch')], ['timing', t('tabTiming')], ['pron', t('tabPron')]].map(([id, label]) => html`<button type="button" class="${cls('s-compare-tab', tab === id && 's-compare-tab--on')}" data-tab="${id}" data-fk="tab-${id}" role="tab" aria-selected="${tab === id}">${label}</button>`)}</div>
        ${panelMarkup(detail, take)}
      </div>
      <div class="s-compare-detail__c">
        <div class="s-compare-detail__label s-compare-detail__label--strong">${t('details')}</div>
        <div class="s-compare-rows">${rows.map((row) => html`<div class="s-compare-row"><span class="s-compare-muted">${row.label}</span><span class="s-compare-row__value" style="color:${row.ink}">${row.kind ? glyph(row.kind) : ''}${row.value}</span></div>`)}</div>
        <div class="s-compare-detail__buttons">
          <button type="button" class="s-compare-ghost" data-fk="hear-word-2" data-hear-word>${raw(icon('volume-2', { size: 18 }))}${t('hearWord')}</button>
          <button type="button" class="s-compare-ghost" data-fk="hear-yours" data-hear-yours>${raw(icon('mic', { size: 18 }))}${t('hearYours')}</button>
        </div>
      </div>
    </div>`;
  }

  function barMarkup() {
    return html`<div class="s-compare-bar">
      <button type="button" class="s-compare-bar__play" data-fk="play" data-play aria-label="${playing ? t('stop') : t('play')}"><span class="s-compare-bar__disc">${playing ? filled('pause', 14) : filled('play', 14)}</span><span data-pb-label>${playing ? t('stop') : t('play')}</span></button>
      <div class="s-compare-bar__modes" data-pb-modes>${PLAYBACK_MODES.map((m) => html`<button type="button" class="${cls('s-compare-bar__mode', mode === m && 's-compare-bar__mode--on')}" data-mode="${m}" data-fk="mode-${m}" ${!source.hasModelAudio && ['model_only','model_then_you'].includes(m) ? raw('disabled') : ''} aria-pressed="${mode === m}">${t(MODE_KEY[m])}</button>`)}</div>
      <button type="button" class="s-compare-bar__speed" data-fk="speed-bar" data-speed><span data-pb-label class="s-compare-muted">${t('speed')} </span>${t('speedUnit', { n: speed })}</button>
      <button type="button" class="s-compare-bar__again" data-fk="again" data-again>${raw(icon('rotate-cw', { size: 18, stroke: 2.2 }))}${t('tryAgain')}</button>
    </div>`;
  }

  function paintLive() {
    const line = q('[data-live]');
    if (line) line.setAttribute('points', liveLine());
    const status = q('[data-record-status]');
    if (status && rec.phase === TAKE.RECORDING) {
      const text=t('recordingSub',{s:Math.floor(rec.elapsedMs/1000)});
      if (status.textContent !== text) status.textContent=text;
    }
    const mic = q('[data-mic]');
    if (mic && rec.phase === TAKE.RECORDING) mic.style.boxShadow = `0 0 0 ${Math.round(4 + Math.max(...rec.levels, 0) * 18)}px var(--ring),var(--sh2)`;
  }

  function paint() {
    const scroller = q('[data-scroll-region]');
    const scrollTop = scroller?.scrollTop || 0;
    // The two horizontal strips keep where the learner had scrolled them across a repaint.
    const strips = { pills: q('.s-compare-pills')?.scrollLeft || 0, tiles: q('.s-compare-tiles')?.scrollLeft || 0 };
    const focusKey = element.contains(document.activeElement) ? document.activeElement?.closest?.('[data-fk]')?.dataset.fk || '' : '';
    const take = selectedTake();
    const view = take ? viewNow() : null;
    const recording = rec.phase === TAKE.RECORDING;
    const processing = rec.phase === TAKE.PROCESSING;
    const result = Boolean(take && view?.measured);
    const showRecord = !result || recording || processing || Boolean(errorText);

    mount(
      element,
      html`<div class="s-compare-header">
        <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
        <div class="s-compare-title-block"><div class="s-compare-title">${t('title')}</div><div class="s-compare-note">${t('subtitle')}</div></div>
        ${takes.length ? pillsMarkup() : ''}
        <button type="button" class="s-compare-history" data-attempts>${t('attemptHistory')}</button>
      </div>
      <div class="s-compare-scroll" data-scroll-region>
        ${referenceStatusMarkup()}
        ${showRecord ? recordCard() : ''}
        ${errorText ? html`<div class="s-compare-error"><b>${t('errorTitle')}</b> ${errorText}</div>` : ''}
        ${result ? summaryMarkup(view, take) : ''}
        ${result && view.words.length ? detailMarkup(view, take) : ''}
      </div>
      ${result ? barMarkup() : ''}`,
    );
    bind();
    const region = q('[data-scroll-region]');
    if (region) region.scrollTop = scrollTop;
    const pills = q('.s-compare-pills');
    if (pills) pills.scrollLeft = strips.pills;
    const tiles = q('.s-compare-tiles');
    if (tiles) tiles.scrollLeft = strips.tiles;
    // A selection made elsewhere (the Attempt History row, the agent, a new take) must be in view.
    if (revealSelection) {
      revealSelection = false;
      reveal(pills, pills?.querySelector('.s-compare-pill--active'));
      reveal(tiles, tiles?.querySelector('[aria-pressed="true"]'));
    }
    if (focusKey) {
      const target = q(`[data-fk="${focusKey}"]`);
      const pagingEnd = target?.disabled && ['previous-words', 'next-words'].includes(focusKey);
      (pagingEnd ? q('.s-compare-tile[aria-pressed="true"]') : target)?.focus({ preventScroll: true });
    }
    if (sizing) {
      sizing.disconnect();
      sizing.observe(element);
      sizing.observe(q('[data-scroll-region]'));
    }
  }

  /* Scrolls a horizontal strip so one child is inside it (the strip only - never the page). */
  function reveal(strip, child) {
    if (!strip || !child) return;
    const left = child.offsetLeft - strip.offsetLeft;
    if (left < strip.scrollLeft) strip.scrollLeft = left - 8;
    else if (left + child.offsetWidth > strip.scrollLeft + strip.clientWidth) strip.scrollLeft = left + child.offsetWidth - strip.clientWidth + 8;
  }

  function bind() {
    q('[data-reference-retry]')?.addEventListener('click',()=>void prepareReference(true));
    q('[data-back]').addEventListener('click', () => ctx.back());
    q('[data-attempts]').addEventListener('click', () => ctx.go(ctx.href('attempts', { id: ctx.params.id }, { ...lineQuery, attempt: selectedId })));
    element.querySelectorAll('[data-select]').forEach((button) => button.addEventListener('click', () => select(button.dataset.select)));
    element.querySelectorAll('[data-word]').forEach((button) => {
      button.addEventListener('click', () => {
        stopPlay();
        wordSel = Number(button.dataset.word);
        paint();
      });
    });
    element.querySelectorAll('[data-tab]').forEach((button) => {
      button.addEventListener('click', () => {
        tab = button.dataset.tab;
        paint();
      });
    });
    q('[data-hear-line]')?.addEventListener('click', () => {
      stopPlay();
      void playModelLine(playToken);
    });
    element.querySelectorAll('[data-speed]').forEach((button) => {
      button.addEventListener('click', () => {
        speed = nextSpeed(speed);
        paint();
      });
    });
    q('[data-mic]')?.addEventListener('click', () => (rec.phase === TAKE.RECORDING ? recorder.stop() : record()));
    element.querySelectorAll('[data-hear-word]').forEach((button) => button.addEventListener('click', () => hearWordModel(wordDetailFor(viewNow(), openWord()))));
    q('[data-hear-yours]')?.addEventListener('click', () => hearYours(viewNow()?.words?.[openWord()]));
    q('[data-play]')?.addEventListener('click', () => void playAll());
    element.querySelectorAll('[data-mode]').forEach((button) => {
      button.addEventListener('click', () => {
        stopPlay();
        mode = button.dataset.mode;
        paint();
      });
    });
    q('[data-again]')?.addEventListener('click', () => {
      q('[data-scroll-region]')?.scrollTo({ top: 0, behavior: 'smooth' });
      record();
    });
  }

  wordSel = takes.length ? defaultWordIndex(viewNow()) : null;
  paint();
  if (selectedId) void measure(selectedId);
  sizing = new ResizeObserver(() => {
    const measured = Math.max(1, q('.s-compare-tiles__row')?.clientWidth || element.clientWidth - 48);
    if (Math.abs(measured - tileWidth) < 1 || !ctx.isCurrent()) return;
    tileWidth = measured;
    paint();
  });
  sizing.observe(element);
  sizing.observe(q('[data-scroll-region]'));
  void prepareReference();

  const releasers = [
    registerActionHandler('play_model', () => {
      if (!source.hasModelAudio) return { ok: false, reason: 'model_unavailable' };
      stopPlay();
      void playModelLine(playToken);
      return { ok: true };
    }),
    registerActionHandler('play_user', (payload) => {
      const named = payload?.take_ref ? takeOf(payload.take_ref) : selectedTake();
      if (!named?.url) return { ok: false, reason: 'unknown_take' };
      if (named.id !== selectedId) select(named.id);
      stopPlay();
      void playFile(named.url, playToken);
      return { ok: true };
    }),
    registerActionHandler('say_again', () => {
      if (recorder.busy) return { ok: false, reason: 'busy' };
      record();
      return { ok: true };
    }),
    registerActionHandler('compare_with_model', (payload) => {
      const named = payload?.take_ref ? takeOf(payload.take_ref) : selectedTake();
      if (!named) return { ok: false, reason: 'unknown_take' };
      if (named.id !== selectedId) select(named.id);
      return { ok: true };
    }),
  ];

  return () => {
    clearTimeout(referenceTimer);
    sizing.disconnect();
    releasers.forEach((release) => release());
    recorder.dispose();
    stopPlay();
  };
}
