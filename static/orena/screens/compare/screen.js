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
import { langAttr } from '../../kit/lang.js';
import { toast } from '../../kit/toast.js';
import { shellCopy } from '../../copy/shell.js';
import { languages } from '../../copy/index.js';
import { api } from '../../infrastructure/api.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
import { originalSegmentPlayer } from '../../product/original-segment-player.js';
import { loadSpeakingSource, segmentOf } from '../../product/speaking-source.js';
import { lineUnits, placeWords } from '../../product/speaking-line.js';
import { comparisonReference, decorateComparison, pairWord, pairedTiming, readingFor } from '../../product/compare-reference.js';
import { toneOf } from '../../capabilities/pronunciation-result.js';
import { decodeAudio, analyse } from '../../capabilities/audio-analysis.js';
import { createSpeakingRecorder, TAKE } from '../../product/speaking-recorder.js';
import { lineKey, listTakes, viewOfTake, attemptIdOf } from '../../product/take-store.js';
import { loadLineAttempts, reviewableAttempts } from '../../product/speaking-history.js';
import { openSheet, sheetHead, fillSheet } from '../../kit/overlay.js';
import { micStateFor } from '../speak/model.js';
import { openMicState, micGate } from '../mic/sheet.js';
import { t } from './copy.js';
import {
  ringColor, scoreLabelKey, headlineKey, wordStatus, pronunciationStatusKey, statusTone, tileMinWidth, wordDetailFor, defaultWordIndex,
  chipsFor, metricLineFor, axisFor, CHART, chartLines, hasVoice, wordPitchLines, wordPages, PLAYBACK_MODES, nextSpeed, playPlan, pillsFor, toneKey,
  ipaByStart, historyFor,
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
  await useStyles('capabilities/original-segment-player.css');
  const language = ctx.context?.language || 'en';
  const { ui, support } = languages();
  const segmentId = segmentOf(ctx.query);

  mount(element, '');
  element.classList.add('s-compare-root');

  const source = await loadSpeakingSource(ctx.params.id, { api, support, language, owner: ctx.context.owner || 'local', segmentId });
  if (!ctx.isCurrent()) return undefined;
  const lineQuery = { segment:source.line.lineId };
  const lines = source.lines || [];
  ctx.setCrumb(source.lessonId ? t('practiceTitle') : t('title'));
  ctx.context?.memory?.enter?.({id:source.sourceId, title:source.title,
    intent:'speaking_compare', segment:source.line.lineId});

  const key = lineKey(source.sourceId, source.line.lineId);
  /* This tab's takes (audio and the full assessment) and what the account holds for this line: a fresh
     browser still has every verified attempt, without its audio (D-076), and each one can be reviewed. */
  const [tabTakes, serverRows] = await Promise.all([
    listTakes(key),
    loadLineAttempts(api, { assetId: source.assetId, segmentId: source.line.lineId }).then((rows) => rows || []),
  ]);
  if (!ctx.isCurrent()) return undefined;
  let tabList = tabTakes;
  const withAccount = (list) => reviewableAttempts(list.map((take) => ({ ...take, attemptId: take.attemptId || attemptIdOf(take.id) })), serverRows);
  let takes = withAccount(tabList);
  mount(element,'');
  const renderRoot=document.createElement('div');
  renderRoot.className='s-compare-body';
  element.append(renderRoot);

  const requested = ctx.query.get('attempt');
  /* A named attempt opens as asked (Attempt History); otherwise this tab's newest take (its audio and word timing
     draw the full comparison), else the account's newest attempt - the room never hides a result it has. */
  let selectedId = takes.some((item) => item.id === requested) ? requested : tabList[0]?.id || takes[0]?.id || '';
  let wordSel = null;
  let tab = 'pitch';
  let mode = source.hasModelAudio ? PLAYBACK_MODES[0] : 'you_only';
  let speed = 1;
  let errorText = '';
  let rec = { phase: TAKE.IDLE, levels: new Array(40).fill(0), elapsedMs: 0 };
  const contours = new Map(); // take id -> { you } once measured
  let playing = false;
  let modelPreview = false;
  let playWord = null; // the word being played in "Word by word"
  let playToken = 0;
  let meaningOpen = false; // the support-language meaning is revealed on tap (D-139 HD-6)
  let audioEl = null;
  let finishAudio = null;
  let revealSelection = true; // the first paint, and every change of attempt, brings the selection into view
  let tileWidth = Math.max(1, element.clientWidth - 48);
  let sizing = null;
  let reference = null;
  const originalPlayer = originalSegmentPlayer(source);


  const q = (selector) => element.querySelector(selector);
  const takeOf = (id) => takes.find((item) => item.id === id) || null;
  const selectedTake = () => takeOf(selectedId);
  const viewNow = () => decorateComparison(viewOfTake(selectedTake()), source, reference);
  const estimateNote = () => (reference?.timingEstimated ? html`<span class="s-compare-muted" data-timing-estimated>${t('timingEstimated')}</span>` : '');
  const modelWordFor = (word) => pairWord(source.line.text, viewNow()?.words || [], word?.index, reference?.words || [], language);
  async function readReference() {
    reference=await comparisonReference(source,{owner:ctx.context.owner || 'local',support});
    if(ctx.isCurrent()) paint();
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
          tabList = finished.list;
          takes = withAccount(tabList);
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
    micGate(ctx, () => recorder.start(), { textFallback: false }); // pronunciation has no typed fallback
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
    modelPreview = false;
    q('[data-original-player]')?.classList.remove('is-model-playing');
    originalPlayer?.stop();
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
  const playModelLine = (token, range = {}) => {
    if (source.hasModelAudio && alive(token)) {
      modelPreview = true;
      q('[data-original-player]')?.classList.add('is-model-playing');
      return originalPlayer.play({...range,speed}).finally(() => {
        if (!alive(token)) return;
        modelPreview = false;
        q('[data-original-player]')?.classList.remove('is-model-playing');
      });
    }
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
          if (modelWord) await playModelLine(token, wordSpan(modelWord));
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
    if (modelWord) void playModelLine(playToken, wordSpan(modelWord));
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
    // One syllable per Han character: a Latin word inside the line ("Vector") has none and takes none (LEX-031).
    const han = (unit) => /\p{Script=Han}/u.test(unit.text);
    const aligned = language === 'zh' && syllables.length === units.filter((unit) => unit.unit && han(unit)).length;
    let spokenAt = 0;
    /* English IPA is the assessment provider's own sounds for the word, from the newest attempt that has
       them (D-139 HD-5); with none, the reading row is not drawn at all - no dashes. Chinese keeps pinyin. */
    const ipa = ipaByStart(takes.map(viewOfTake), source.line.text, language, placeWords);
    const readingRow = language === 'zh' || ipa.size > 0;
    /* Punctuation stays on its word (design: "stop," is one token): a closing mark joins the word
       before it, an opening quote or bracket the word after it. */
    const marks = (text) => /^[\p{P}\p{S}]+$/u.test(text.trim());
    const opening = (text) => /^[\p{Ps}\p{Pi}]+$/u.test(text.trim());
    const items = [];
    let lead = '';
    for (const unit of units) {
      const text = unit.text;
      if (!unit.unit && marks(text)) {
        if (opening(text)) lead += text.trim();
        else if (items.length && !items[items.length - 1].plain) items[items.length - 1].tail += text.trim();
        else items.push({ unit, plain: true, lead: '', tail: '' });
        continue;
      }
      items.push({ unit, plain: false, lead, tail: '' });
      lead = '';
    }
    return items.map(({ unit, plain, lead: head, tail }) => {
      const shown = `${head}${unit.text}${tail}`;
      if (plain || !unit.unit || (language === 'zh' && !han(unit))) return shown.trim() ? html`<span class="s-compare-token">${readingRow ? html`<span class="s-compare-token__sub" aria-hidden="true">${raw('&nbsp;')}</span>` : ''}<span class="s-compare-token__word" lang="${langAttr(language)}">${shown}</span></span>` : '';
      const reading = language === 'en' ? ipa.get(unit.start) || '' : aligned ? syllables[spokenAt++] : readingFor(unit.text, reference, language, unit.start);
      const tone = language === 'zh' && reading ? toneOf(reading) : null;
      if (!readingRow) return html`<span class="s-compare-token"><span class="s-compare-token__word" lang="${langAttr(language)}">${shown}</span></span>`;
      return html`<span class="s-compare-token"><span class="s-compare-token__sub" title="${reading || language !== 'zh' ? '' : t('readingUnavailable')}" style="color:${tone && tone < 5 ? `var(--tone${tone})` : 'var(--text3)'}">${reading || (language === 'zh' ? '—' : raw('&nbsp;'))}</span><span class="s-compare-token__word" lang="${langAttr(language)}">${shown}</span></span>`;
    });
  }

  const lineAt = () => lines.findIndex((line) => line.lineId === source.line.lineId);
  const busyNow = () => [TAKE.RECORDING, TAKE.PROCESSING].includes(rec.phase);

  /* Previous / Next line at the bottom of the room, as frame 28 draws them (D-139 HD-4). On a phone the
     result state already spends the bottom on the playback bar, so the pair gives way to it (rule 49):
     the line list behind "..." still moves to any line, and Try again returns to the pair. */
  function lineNavigation(withBar = false) {
    if (!source.lessonId || lines.length < 2) return '';
    const at = lineAt();
    const busy = busyNow();
    return html`<div class="${cls('s-compare-linenav', withBar && 's-compare-linenav--with-bar')}">
      <button type="button" class="s-compare-linenav__btn" data-fk="line-prev" data-source-line="${lines[at - 1]?.lineId || ''}" ${busy || at <= 0 ? raw('disabled') : ''}>${raw('&larr;')} ${t('previousLine')}</button>
      <button type="button" class="s-compare-linenav__btn" data-fk="line-next" data-source-line="${lines[at + 1]?.lineId || ''}" ${busy || at >= lines.length - 1 ? raw('disabled') : ''}>${t('nextLine')}${raw(icon('arrow-right', { size: 16 }))}</button>
    </div>`;
  }

  /* The line list and "Choose media" live in a sheet behind "..." (D-139 HD-4); Listen returns to this
     exact line in Listening. */
  function openMore() {
    const at = lineAt();
    openSheet({
      label: t('lineAndMedia'),
      render(sheet, handle) {
        fillSheet(sheet, handle, html`${sheetHead({ title: t('lineAndMedia'), closeLabel: shellCopy('close') })}
          <div class="s-compare-more">
            <div class="s-compare-more__media" lang="${langAttr(language)}">${source.title}</div>
            <div class="s-compare-more__lines">${lines.map((line, index) => html`<button type="button" class="s-compare-more__line" data-source-line="${line.lineId}" aria-current="${index === at}"><span class="s-compare-more__n">${line.ordinal}</span><span lang="${langAttr(language)}">${line.text}</span></button>`)}</div>
            <div class="s-compare-more__actions">
              <button type="button" class="s-compare-ghost" data-listen-source>${t('listenSource')}</button>
              <button type="button" class="s-compare-ghost" data-choose-media>${t('chooseMedia')}</button>
            </div>
          </div>`);
        sheet.querySelectorAll('[data-source-line]').forEach((button) => button.addEventListener('click', () => goLine(button.dataset.sourceLine)));
        sheet.querySelector('[data-listen-source]').addEventListener('click', () => ctx.go(ctx.href('listening', { id: source.lessonId }, lineQuery)));
        sheet.querySelector('[data-choose-media]').addEventListener('click', () => ctx.go(ctx.href('discover', {}, { tab: 'listen', practice: 'pronunciation', source: source.lessonId, segment: source.line.lineId })));
      },
    });
  }

  function goLine(id) {
    if (!id || recorder.busy) return;
    stopPlay();
    ctx.go(ctx.href('compare', { id: source.sourceId }, { segment: id }));
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
      <div class="s-compare-record__content"><div class="s-compare-tokens">${tokensMarkup()}</div>
      ${support !== language ? html`<div class="s-compare-meaning"><button type="button" class="s-compare-reveal" data-fk="meaning" data-meaning aria-expanded="${meaningOpen}">${t(meaningOpen ? 'hideMeaning' : 'showMeaning')}</button>${meaningOpen ? html`<p class="s-compare-note" lang="${langAttr(support)}">${source.line.meaning || t('meaningUnavailable')}</p>` : ''}</div>` : ''}
      ${source.hasModelAudio ? '' : html`<p class="s-compare-note">${t('modelUnavailable')}</p>`}
      </div>
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
          ${estimateNote()}
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
          <span class="s-compare-muted">${t('timingCompared')}</span>${estimateNote()}
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
      <div class="s-compare-legend"><span><i style="background:var(--accent)"></i>${t('legendModel')}</span><span><i style="background:var(--green)"></i>${t('legendYou')}</span>${estimateNote()}</div>
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

  /* The component's own Attempt history card (frame 16, D-139 HD-7): every attempt this line has, the
     sparkline of their scores, and for each the three numbers the assessment measured with the change
     from the attempt before. Tapping one opens its analysis above - for an attempt only the account
     remembers, without audio (D-076). The frame's "Clear" is not drawn: the account's record is not
     deleted from here. */
  function historyMarkup() {
    const history = historyFor(takes, selectedId, viewOfTake);
    if (!history.count) return '';
    const dots = history.spark;
    const line = dots.map((dot) => `${dot.cx.toFixed(1)},${dot.cy.toFixed(1)}`).join(' ');
    const summary = history.scoredCount < 2
      ? (history.count < 2 ? t('histSummaryFirst') : '')
      : t('histSummary', { first: history.first, last: history.last, n: history.scoredCount, best: history.best, bestN: history.bestN });
    const when = (at) => new Date(at).toLocaleString(ui, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    return html`<div class="s-compare-card s-compare-hist">
      <div class="s-compare-hist__top">
        <div class="s-compare-hist__head">
          <div class="s-compare-hist__title"><span>${t('attemptHistory')}</span><span class="s-compare-hist__count">${history.count}</span></div>
          ${summary ? html`<div class="s-compare-hist__summary">${summary}</div>` : ''}
        </div>
        ${dots.length ? html`<svg viewBox="0 0 180 40" class="s-compare-hist__spark" aria-hidden="true"><line x1="0" y1="36" x2="180" y2="36" stroke="var(--border)" stroke-width="1"></line><polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></polyline>${dots.map((dot) => html`<circle cx="${dot.cx.toFixed(1)}" cy="${dot.cy.toFixed(1)}" r="${dot.id === selectedId ? 4.5 : 3}" fill="${dot.id === selectedId ? 'var(--accent)' : 'var(--surface)'}" stroke="var(--accent)" stroke-width="2"></circle>`)}</svg>` : ''}
      </div>
      <div class="s-compare-hist__rows">${history.rows.map((row) => html`<div class="${cls('s-compare-hist__row', row.active && 's-compare-hist__row--on')}">
        <button type="button" class="s-compare-hist__open" data-fk="hist-${row.n}" data-hist-select="${row.id}" aria-pressed="${row.active}">
          <span class="s-compare-hist__who">
            <span class="s-compare-hist__n">#${row.n}</span>
            <span class="s-compare-hist__what">
              <span class="s-compare-hist__when"><span>${when(row.at)}</span>${row.isBest ? html`<span class="s-compare-hist__best">${t('histBest')}</span>` : ''}</span>
              <span class="s-compare-hist__focus">${row.focus ? t('histFocusWord', { word: row.focus }) : t('histFocusNone')}</span>
            </span>
          </span>
          <span class="s-compare-hist__metrics">${row.metrics.map((metric) => html`<span class="s-compare-hist__metric"><span class="s-compare-hist__label">${t(metric.key)}</span><span class="s-compare-hist__value"><b>${metric.value ?? '—'}</b>${metric.delta.zero ? html`<i style="color:var(--muted)">${t('histSame')}</i>` : metric.delta.text ? html`<i style="color:${metric.delta.tone}">${metric.delta.text}</i>` : ''}</span></span>`)}</span>
        </button>
        ${row.hasAudio ? html`<button type="button" class="s-compare-hist__play" data-hist-play="${row.id}" aria-label="${t('histPlay')}" title="${t('histPlay')}">${filled('play', 14)}</button>` : ''}
      </div>`)}</div>
      <div class="s-compare-hist__note">${t('histNote')}</div>
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

    originalPlayer?.park(element);
    mount(
      renderRoot,
      html`<div class="s-compare-header">
        <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${shellCopy('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
        <div class="s-compare-title-block"><div class="s-compare-title">${source.lessonId ? t('practiceTitle') : t('title')}</div><div class="s-compare-note s-compare-subtitle">${t('subtitle')}</div></div>
        ${takes.length ? pillsMarkup() : ''}
        <button type="button" class="s-compare-history" data-attempts aria-label="${t('attemptHistory')}"><span>${t('attemptHistory')}</span></button>
        ${source.lessonId ? html`<button type="button" class="o-iconbtn s-compare-more-btn" data-more aria-label="${t('more')}" title="${t('more')}" ${busyNow() ? raw('disabled') : ''}>${raw(icon('ellipsis', { size: 18 }))}</button>` : ''}
      </div>
      <div class="s-compare-scroll${showRecord ? ' s-compare-scroll--record' : ''}" data-scroll-region>
        ${source.playback?.kind === 'embed' ? html`<div class="s-compare-model-preview${modelPreview ? ' is-model-playing' : ''}" data-original-player></div>` : ''}
        ${showRecord ? recordCard() : ''}
        ${errorText ? html`<div class="s-compare-error"><b>${t('errorTitle')}</b> ${errorText}</div>` : ''}
        ${result ? summaryMarkup(view, take) : ''}
        ${result && view.words.length ? detailMarkup(view, take) : ''}
        ${result && !showRecord ? historyMarkup() : ''}
      </div>
      ${result ? barMarkup() : ''}
      ${lineNavigation(result)}`,
    );
    if (originalPlayer) {
      if(source.playback.kind === 'embed') originalPlayer.attach(q('[data-original-player]'));
      else originalPlayer.attach(element);
    }
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
    element.querySelectorAll('[data-source-line]').forEach((button) => button.addEventListener('click', () => goLine(button.dataset.sourceLine)));
    q('[data-more]')?.addEventListener('click', openMore);
    q('[data-meaning]')?.addEventListener('click', () => {
      meaningOpen = !meaningOpen;
      paint();
    });
    element.querySelectorAll('[data-hist-select]').forEach((button) => button.addEventListener('click', () => {
      select(button.dataset.histSelect);
      q('[data-scroll-region]')?.scrollTo({ top: 0, behavior: 'smooth' });
    }));
    element.querySelectorAll('[data-hist-play]').forEach((button) => button.addEventListener('click', () => {
      const url = takeOf(button.dataset.histPlay)?.url;
      if (!url) {
        toast(t('noTakeAudio'));
        return;
      }
      stopPlay();
      void playFile(url, playToken);
    }));
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
  void readReference();

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
    originalPlayer?.dispose();
    sizing.disconnect();
    releasers.forEach((release) => release());
    recorder.dispose();
    stopPlay();
  };
}
