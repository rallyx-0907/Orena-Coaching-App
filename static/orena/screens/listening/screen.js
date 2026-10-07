/* Listening Workspace (design route `listening`, frame 06, D-091, D-088). A focus workspace
   (Design Contract rules 47/49): the Listening / Dictation switch (D-137, human direction 2026-10-06:
   Dictation replaces the Shadowing tab and works in place; Shadowing stays a line action), a real player, a synced
   transcript, the selected-line actions (Active mode) or the "now playing" card (Follow), and an
   in-place end-of-media summary. See SCRATCH/reports/listening.md for the measurement diff, the
   rule-49 recomposition (N-6) and every backend gap.

   What the frame's script does, restated over the real player and transcript:
   - Follow: a tap on a line seeks there and plays on. Active: a tap selects the line and plays it
     to its end; the selected line's actions appear. "Work on this line" and the Active switch both
     select the line being played; Follow clears the selection. Shadowing leaves the room.
   - "Line" back restarts the current line after its first second, else goes back one; Line forward
     goes on; Replay plays the selected (or current) line to its end; the speed cycles 1x, 0.75x,
     0.5x, 1.25x.
   - Word highlight marks the word being spoken - the asset's own word timing when it has some that
     reconciles with the line, otherwise the segment-timing estimate the control's "est." admits. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { markGlyph } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { toast } from '../../kit/toast.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy as s } from '../../copy/shell.js';
import { askOrena } from '../../shell/agent-bridge.js';
import { setViewSelection } from '../../shell/view-context.js';
import { registerActionHandler } from '../../agent/dispatcher.js';
import {
  connectMediaPlayer, disconnectMediaPlayer, mediaPlayer, playbackAvailable, posterUrl,
  replaySegment, seekPlayback, togglePlayback, setPlaybackRate,
} from '../../capabilities/media-player.js';
import { activeCanonicalSegment } from '../../capabilities/transcript-timeline.js';
import { readStage, writeStage, transcriptDefaults } from '../../product/transcript-stage.js';
import { encounter } from '../../product/encounter.js';
import { openMedia, rememberMedia } from '../../product/media-source.js';
import { processingProgressMarkup } from '../../kit/states.js';
import { openWordSheet } from '../quick-sheet/sheet.js';
import { openVocabFocus } from './vocab-sheet.js';
import { keepProvenance } from '../../product/account-records.js';
import { t } from './copy.js';
import { mapLesson as dictationLesson, progressBySegment } from '../dictation/model.js';
import { createLinePractice } from '../dictation/line-practice.js';
import { t as dictT } from '../dictation/copy.js';
import {
  nextSpeed, speedLabel, contentIdFor, mmss, minutesFrom, metaLine, mapLesson,
  wordTokens, hanTokens, currentTokenIndices, wordHighlightEstimated, rowTone, modeHintKey, selectionAfterModeChange,
  previousIndex, nextIndex, vocabularyForSegment, placeFor, dictationLinesCompleted,
  pickNextRecommendation, progressPercent, keyWordsFrom, msAtSeekFraction, timeLabel, reachedEnd, listenedMinutesLabel,
  phraseSaveable, phraseSavePayload, phraseSaved, transcriptState,
} from './model.js';

export default async function listening(element, ctx) {
  await Promise.all([useStyles('screens/listening/listening.css'), useStyles('screens/dictation/dictation.css')]);
  const c = ctx.context;
  const support = languages().support;
  const lessonId = ctx.params.id;

  /* A curated lesson, a stored upload or a pasted link: one resolver, one payload shape
     (product/media-source.js). A source with no transcript still opens and plays. */
  const payload = await openMedia(lessonId, {
    api, support, language: c.language, owner: c.owner || 'local', alive: () => ctx.isCurrent(),
  });
  if (!ctx.isCurrent()) return undefined;
  if (!payload?.asset || !payload.playback) throw new Error('This media is unavailable.');

  const lesson = mapLesson(payload, { fallbackLanguage: c.language });
  const language = lesson.language;
  const enc = encounter(payload, support);
  const segments = enc.segments;
  const routeId = lesson.lessonId || lessonId;
  const contentId = contentIdFor(routeId);
  const place = placeFor(c.memory?.value?.continuation, contentId);
  const playbackOk = playbackAvailable(lesson.playback);
  const clipEndMs = lesson.excerptEndMs || (lesson.excerptStartMs + (lesson.durationMs || 0));
  const hasMeanings = () => segments.some((seg) => enc.meaning(seg.segment_id));
  const showMeaningToggle = support !== language || hasMeanings();
  const durationMinutes = minutesFrom(lesson.durationMs);
  const isZh = language === 'zh';

  /* Real, but not blocking: the end-of-media stats and next-recommendation only need to be true
     by the time the clip actually ends. */
  let nextRec = null;
  let savedBaseline = null;
  let dictProgressItems = [];
  /* Dictation mode: the same line practice as the Dictation room, over this lesson's lines. Its stored
     progress arrives with the side loads; until then a check folds the server's copy in at save time. */
  const dictLesson = dictationLesson(payload);
  const dictById = new Map();
  let dictPriorRead = false;
  const sideLoads = Promise.allSettled([
    api.listeningLibrary(c.language).then((res) => { nextRec = pickNextRecommendation(res?.items, lesson.lessonId, lesson.topic); }),
    api.libraryVocabularySummary().then((res) => { savedBaseline = Number(res?.summary?.saved) || 0; }),
    lesson.mediaObjectId ? api.listeningProgress(lesson.mediaObjectId).then((res) => {
      dictProgressItems = res?.items || [];
      for (const [id, item] of progressBySegment(dictProgressItems)) dictById.set(id, item);
      dictPriorRead = true;
    }) : Promise.resolve(),
  ]);

  /* The learner's transcript defaults are the device keys Settings writes (product/transcript-
     stage.js): auto-scroll and meaning under the transcript. Word highlight is kept beside them. */
  const stageRaw = readStage();
  const defaults = transcriptDefaults(stageRaw);
  let mode = 'follow';
  let speed = 1;
  let showTrans = defaults.meaning;
  let autoScroll = defaults.autoscroll;
  let wordHighlight = stageRaw.wordhl !== false;
  let moreOpen = false;
  let moreActs = false; // the phone's secondary line actions (Dictation, Shadowing, React) are shown
  let selectedId = null;
  const explicitSegment = ctx.query.get('segment') || ctx.query.get('seg');
  const requestedSegment = explicitSegment || place.segmentId;
  let currentId = segments.some((seg) => seg.segment_id === requestedSegment) ? requestedSegment : (segments[0]?.segment_id || null);
  let playing = false;
  let bounded = false; // a line is being played to its end; reaching the clip's end then is not "media completed"
  // A named or remembered line reopens on that line, paused (L-09): coming back from Dictation, React or
  // Shadowing never resets the learner to the first line.
  const resumeAt = segments.some((seg) => seg.segment_id === requestedSegment);
  let timeMs = resumeAt ? (segments.find(seg=>seg.segment_id===currentId)?.start_ms ?? lesson.excerptStartMs) : lesson.excerptStartMs;
  let ended = false;
  let playedMs = 0;
  let lastTickAt = null;
  let rememberedId = '';
  let lastActiveIndex = -2; // which segment the clock last said we are in (-1: between lines)
  let barSeek = false; // the seek bar moved the time while paused: the line follows it
  let seekingTo = resumeAt ? {id:currentId,at:Date.now()} : null;
  const savedPhrases = new Set(); // segment texts known to be saved this session
  let markedEls = []; // the word currently marked as spoken
  const tokenCache = new Map();

  const segOf = (id) => segments.find((seg) => seg.segment_id === id) || null;
  const indexOf = (id) => segments.findIndex((seg) => seg.segment_id === id);

  function tokensOf(seg) {
    if (!tokenCache.has(seg.segment_id)) {
      tokenCache.set(seg.segment_id, isZh ? hanTokens(seg.original_text, lesson.pinyinChars[seg.segment_id]) : wordTokens(seg.original_text));
    }
    return tokenCache.get(seg.segment_id);
  }

  const dictationOn = lesson.modes.dictation && dictLesson.segments.length > 0;
  const practice = createLinePractice({
    lesson: dictLesson,
    byId: dictById,
    priorRead: () => dictPriorRead,
    memory: c.memory || null,
    onCheck: (line) => {
      if (playing && playbackOk) togglePlayback(playerEl, lesson.playback);
      paintVeil();
      paintRows();
      scrollRowIntoView(line.id);
    },
    // Retry hides the line again (LEX-038): its row and the picture are veiled until the new attempt is checked.
    onRetry: () => {
      paintVeil();
      paintRows();
    },
    onNext: (line) => {
      const at = indexOf(line.id);
      if (at >= segments.length - 1) { onMode('follow'); return; }
      // The next line starts hidden and still: the learner plays it when ready.
      currentId = segments[at + 1].segment_id;
      seekingTo = { id: currentId, at: Date.now() };
      if (playbackOk) seekPlayback(playerEl, lesson.playback, segments[at + 1].start_ms);
      paintRows();
      paintSelected();
      rememberPlace(true);
      scrollRowIntoView(currentId);
    },
  });

  // Reached by the Dictation route (Practice Hub, Progress) the room opens in Dictation, on the remembered or
  // named line (LEX-034): one Dictation experience, whichever way the learner came in.
  if (dictationOn && (ctx.route?.id === 'dictation' || ctx.query.get('mode') === 'dictation')) mode = 'dictation';

  /* A hidden line: one muted bar per word (per character in Chinese), so its length is known and its
     words are not. */
  function hiddenBars(seg) {
    const count = isZh ? [...String(seg.original_text).matchAll(/\p{Script=Han}/gu)].length : wordTokens(seg.original_text).filter((tok) => tok.core).length;
    return html`${Array.from({ length: Math.max(1, Math.min(count, 24)) }, () => html`<span class="s-listening__bar${isZh ? ' s-listening__bar--han' : ''}"></span>`)}`;
  }

  function saveStage() {
    writeStage({ ...readStage(), autoscroll: autoScroll, meaning: showTrans, wordhl: wordHighlight });
  }

  function rememberPlace(force = false) {
    if (!force && currentId === rememberedId) return;
    rememberedId = currentId;
    // The line in view, for an Orena conversation already running ("explain this sentence"). In Dictation the
    // line's words are the answer, so only its id is shared, never its text.
    const line = segOf(currentId);
    if (line && mode !== 'dictation') setViewSelection({ type: 'sentence', id: line.segment_id, text: line.original_text });
    try {
      c.memory?.enter({ id: contentId, title: lesson.title, segment: currentId || '', intent: null });
    } catch {
      /* Device memory unavailable (private window): the session still works, it just does not
         resume next time. */
    }
  }

  const kindLabel = lesson.playbackKind === 'audio' ? t('typeAudio') : t('typeVideo');
  element.classList.add('s-listening');
  mount(
    element,
    html`<div class="s-listening__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${s('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-listening__titles">
        <div class="s-listening__title" lang="${langAttr(language)}">${lesson.title}</div>
        <div class="s-listening__meta">${metaLine([kindLabel, payload.transcript_origin === 'generated_asr' ? t('generatedTranscript') : '', lesson.levelText || (lesson.sourceLevel ? t('sourceLevel', {level: lesson.sourceLevel}) : t('levelUnknown')), durationMinutes != null ? `${durationMinutes} ${t.plural('minutesLabel', durationMinutes)}` : ''])}</div>
      </div>
      <div class="s-listening__modes" data-modes role="group"></div>
    </div>
    <div class="s-listening__body">
      <div class="s-listening__media">
        <div class="s-listening__player${lesson.posterUrl ? '' : ' is-bare'}" data-player>
          ${lesson.posterUrl ? html`<img src="${posterUrl(lesson.posterUrl)}" alt="">` : ''}
          ${playbackOk ? raw(mediaPlayer(lesson.playback, lesson.title, {
            startMs: timeMs, endMs: lesson.excerptEndMs, poster: lesson.posterUrl, controls: false,
          })) : html`<div class="s-listening__unavailable">${t('playbackUnavailable')}</div>`}
          ${playbackOk ? html`<button type="button" class="s-listening__playbtn" data-play aria-label="${t('playPause')}">${raw(icon('play', { size: 24 }))}</button>
          <div class="s-listening__time" data-time></div>` : ''}
        </div>
        ${playbackOk ? html`<div class="s-listening__seek" data-seek role="slider" aria-label="${t('playPause')}"><div class="s-listening__seek-fill" data-seek-fill></div></div>` : ''}
        <div class="s-listening__controls" data-controls></div>
        <div class="s-listening__slot" data-selected-slot></div>
      </div>
      <div class="s-listening__transcript">
        <div class="s-listening__transcript-head"><span class="s-listening__transcript-title">${t('transcript')}</span><span class="s-listening__transcript-hint" data-mode-hint></span></div>
        <div class="s-listening__transcript-body" data-scroll-region data-rows></div>
      </div>
    </div>
    <div class="s-listening__slot" data-end-slot></div>`,
  );

  const playerEl = element.querySelector('[data-player]');
  const timeEl = element.querySelector('[data-time]');
  const seekFillEl = element.querySelector('[data-seek-fill]');
  const rowsEl = element.querySelector('[data-rows]');
  const selectedSlot = element.querySelector('[data-selected-slot]');
  const endSlot = element.querySelector('[data-end-slot]');

  /* Back (LEX-043): while the learner is typing an answer it only closes the keyboard - the lesson, the line and
     the draft stay. Otherwise it leaves the lesson for where the learner came from, or, opened directly, for the
     lesson's own page rather than an unrelated Today. */
  element.querySelector('[data-back]').addEventListener('click', () => {
    if (element.classList.contains('is-typing') || document.activeElement?.matches?.('.s-dict__input')) {
      document.activeElement?.blur?.();
      element.classList.remove('is-typing');
      element.style.removeProperty('--ls-visible-h');
      return;
    }
    if (ctx.hasHistory?.() === false) ctx.replace(ctx.href('content', { id: contentId }));
    else ctx.back();
  });

  /* ---------------------------------------------------------------- modes ---- */
  function modesMarkup() {
    const list = [
      { id: 'follow', label: s('listening'), on: true },
      { id: 'dictation', label: s('dictation'), on: dictationOn },
    ];
    const pressed = (id) => (id === 'dictation') === (mode === 'dictation');
    return html`${list.map((item) => html`<button type="button" class="s-listening__mode" data-mode="${item.id}" ${item.on ? '' : raw('disabled')} title="${item.on ? '' : t('transcriptUnavailable')}" aria-pressed="${String(pressed(item.id))}">${item.label}</button>`)}`;
  }
  function paintModes() {
    element.classList.toggle('is-dictation', mode === 'dictation');
    const holder = element.querySelector('[data-modes]');
    mount(holder, modesMarkup());
    holder.querySelectorAll('[data-mode]').forEach((button) => button.addEventListener('click', () => onMode(button.dataset.mode)));
    mount(element.querySelector('[data-mode-hint]'), html`${t(modeHintKey(mode))}`);
  }
  /* The address carries the mode (LEX-044): a reload - a phone tab brought back, a rotation or device switch that
     reloads - reopens Dictation on its line with the answer still hidden, never the Listening transcript. */
  function keepModeInUrl() {
    const { mode: _named, ...rest } = Object.fromEntries(ctx.query);
    try {
      history.replaceState(history.state, '', ctx.href(mode === 'dictation' ? 'dictation' : 'listening', ctx.params, rest));
    } catch {
      /* An address the route table cannot build: the mode still works, it just does not survive a reload. */
    }
  }
  function onMode(id) {
    if (id === mode) return;
    // Switching never plays on: the learner is on the same line, paused, in either mode.
    if (playing && playbackOk) togglePlayback(playerEl, lesson.playback);
    bounded = false;
    if (id === 'dictation') {
      mode = 'dictation';
      selectedId = null;
      keepModeInUrl();
      paintModes();
      paintControls();
      paintRows();
      paintSelected();
      scrollRowIntoView(currentId);
      return;
    }
    mode = id;
    selectedId = selectionAfterModeChange(id, currentId);
    bounded = false;
    keepModeInUrl();
    paintModes();
    paintControls();
    paintRows();
    paintSelected();
  }

  /* ---------------------------------------------------------------- player ---- */
  function paintTime() {
    element.querySelector('.s-listening__player')?.classList.toggle('is-playing', playing);
    if (timeEl) timeEl.textContent = timeLabel(timeMs, lesson.excerptStartMs, clipEndMs);
    if (seekFillEl) seekFillEl.style.width = `${progressPercent(timeMs, lesson.excerptStartMs, clipEndMs)}%`;
    // Redrawn only when play/pause flips (LEX-045): replacing the icon on every clock tick swapped the node under a
    // press on the button's centre, and the browser dropped that click - only the rim answered.
    const glyph = element.querySelector('[data-play]');
    if (glyph && glyph.dataset.glyph !== String(playing)) {
      glyph.dataset.glyph = String(playing);
      mount(glyph, raw(icon(playing ? 'pause' : 'play', { size: 24 })));
    }
  }

  let chromeTimer = null;
  function revealPlayerChrome() {
    playerEl.classList.add('show-chrome');
    clearTimeout(chromeTimer);
    chromeTimer = setTimeout(() => playerEl.classList.remove('show-chrome'), 2000);
  }
  playerEl.addEventListener('pointermove', revealPlayerChrome);
  playerEl.addEventListener('pointerdown', revealPlayerChrome);

  function onMediaTime(event) {
    const detail = event.detail || {};
    const now = Number(detail.time_ms);
    if (Number.isFinite(now)) {
      if (playing && lastTickAt != null) playedMs += Math.max(0, now - lastTickAt);
      timeMs = now;
      lastTickAt = now;
    }
    const wasPlaying = playing;
    playing = detail.player_state === 1;
    if (playing && !wasPlaying) revealPlayerChrome();
    if (!playing) lastTickAt = null;
    paintTime();
    if (seekingTo) {
      const target = segOf(seekingTo.id);
      const arrived = target && timeMs >= target.start_ms - 200 && timeMs <= target.end_ms + 200;
      if (arrived || Date.now() - seekingTo.at > 1500) seekingTo = null;
    }
    // Only playback moves the current line: a paused player (a line just chosen, a return from practice)
    // keeps the learner's line even when the player has not reported the new time yet (L-09).
    // In Dictation the line is the learner's choice: playback is bounded to it, and a late clock report from
    // the line just checked must not pull the room back to it after Next segment (LEX-032).
    if (!seekingTo && mode !== 'dictation' && (playing || barSeek)) {
      barSeek = false;
      const found = activeCanonicalSegment(segments, timeMs);
      const foundIndex = found ? indexOf(found.segment_id) : -1;
      if (foundIndex !== lastActiveIndex) {
        lastActiveIndex = foundIndex;
        if (found) currentId = found.segment_id;
        paintRows();
        paintNowPlaying();
        rememberPlace();
        if (autoScroll) scrollRowIntoView(currentId);
      }
    }
    paintWordHighlight();
    if (!ended && !bounded && !playing && reachedEnd(timeMs, clipEndMs)) {
      ended = true;
      showEnded();
    }
  }
  if (playbackOk) {
    playerEl.addEventListener('orena:media-time', onMediaTime);
    connectMediaPlayer(playerEl, lesson.playback);
    if (resumeAt) seekPlayback(playerEl, lesson.playback, timeMs);
    playerEl.querySelector('[data-play]')?.addEventListener('click', () => {
      // Dictation plays only the line being written, and stops at its end.
      if (mode === 'dictation' && !playing) return playLine(currentId);
      bounded = false;
      togglePlayback(playerEl, lesson.playback);
    });
    element.querySelector('[data-seek]')?.addEventListener('click', (event) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const fraction = (event.clientX - rect.left) / rect.width;
      if (mode === 'dictation') return; // the line being written is the only place Dictation plays
      bounded = false;
      barSeek = true;
      seekPlayback(playerEl, lesson.playback, msAtSeekFraction(fraction, lesson.excerptStartMs, clipEndMs));
    });
  }

  /* Keep a row in view inside the transcript's own region (never scrolling the page). */
  function scrollRowIntoView(id) {
    const row = rowsEl?.querySelector(`[data-seg="${CSS.escape(id)}"]`);
    if (!row) return;
    // Measured against the region itself, not offsetParent: the line's first row (pinyin included) is never
    // left under the Transcript header (mobile QA BUG-08).
    const region = rowsEl.getBoundingClientRect();
    const box = row.getBoundingClientRect();
    const top = box.top - region.top + rowsEl.scrollTop;
    const bottom = top + box.height;
    const view = rowsEl.clientHeight;
    // The current line is the focus (LEX-047): whole, in the upper part of the pane, with a short strip of the
    // previous line above it as context - never parked at the bottom edge under a centred past line. A line taller
    // than the pane starts at its top and the learner scrolls for the rest.
    const clipped = top < rowsEl.scrollTop + 8 || bottom > rowsEl.scrollTop + view - 8;
    const low = top - rowsEl.scrollTop > view * 0.45;
    if (!clipped && !low) return;
    const context = Math.max(0, Math.min(Math.round(view * 0.18), view - box.height - 16));
    rowsEl.scrollTop = Math.max(0, top - 8 - context);
  }
  // A pane that changes size (a panel opened or closed, a rotation, the keyboard) frames the current line again,
  // unless the learner has just scrolled the transcript themselves.
  let userScrollAt = 0;
  const markUserScroll = () => { userScrollAt = Date.now(); };
  rowsEl.addEventListener('wheel', markUserScroll, { passive: true });
  rowsEl.addEventListener('touchmove', markUserScroll, { passive: true });
  let lastPaneHeight = 0;
  const paneObserver = typeof ResizeObserver === 'function' ? new ResizeObserver(() => {
    const height = rowsEl.clientHeight;
    if (!height || height === lastPaneHeight) return;
    lastPaneHeight = height;
    if (autoScroll && Date.now() - userScrollAt > 3000 && currentId) scrollRowIntoView(currentId);
  }) : null;
  paneObserver?.observe(rowsEl);

  /* The frame's `playSeg`: from the line's start to its end, then stop. */
  function playLine(id) {
    const seg = segOf(id);
    if (!seg || !playbackOk) return;
    bounded = true;
    ended = false;
    currentId = id;
    seekingTo = { id, at: Date.now() };
    replaySegment(playerEl, lesson.playback, seg.start_ms, seg.end_ms, speed);
    paintRows();
    paintNowPlaying();
    if (mode === 'dictation') { paintDictationCard(); rememberPlace(true); }
  }

  /* ---------------------------------------------------------------- controls row ---- */
  function pill({ id, label, iconName, iconAfter = false, pressed = null, variant = '', title = '', aria = '', disabled = false }) {
    const glyph = iconName ? raw(icon(iconName, { size: iconName === 'play' ? 14 : 15 })) : '';
    return html`<button type="button" class="s-listening__pill${variant ? ` s-listening__pill--${variant}` : ''}" data-act="${id}"${disabled ? raw(' disabled') : ''}${pressed != null ? raw(` aria-pressed="${String(pressed)}"`) : ''}${title ? raw(` title="${title.replace(/"/g, '&quot;')}"`) : ''}${aria ? raw(` aria-label="${aria.replace(/"/g, '&quot;')}"`) : ''}>${iconAfter ? html`${label}${glyph}` : html`${glyph}${label}`}</button>`;
  }

  function toggles(prefix) {
    // Verified word timing when every line has it, otherwise the frame's estimate, labelled "· est." (D-137).
    const estimated = wordHighlightEstimated(segments);
    return html`${pill({ id: 'auto', label: t('autoScroll'), pressed: autoScroll, variant: 'toggle' })}${pill({ id: 'wordhl', label: t(estimated ? 'wordHighlightEst' : 'wordHighlight'), pressed: wordHighlight, variant: 'toggle', title: estimated ? t('wordHighlightHint') : '' })}`;
  }

  function controlsMarkup() {
    const labelSpan = (text) => html`<span class="s-listening__pill--label">${text}</span>`;
    return html`
      ${playbackOk ? pill({ id: 'prev', label: labelSpan(t('line')), iconName: 'skip-back', aria: t('prevLine'), title: t('prevLine') }) : ''}
      ${playbackOk ? pill({ id: 'replay', label: t('replay'), iconName: 'rotate-ccw', variant: 'primary', aria: t('replayLine'), title: t('replayLine') }) : ''}
      ${playbackOk ? pill({ id: 'next', label: labelSpan(t('line')), iconName: 'skip-forward', iconAfter: true, aria: t('nextLine'), title: t('nextLine') }) : ''}
      ${playbackOk ? pill({ id: 'speed', label: speedLabel(speed), variant: 'speed' }) : ''}
      ${mode === 'follow' && segOf(currentId) ? html`<button type="button" class="s-listening__pill s-listening__pill--pick" data-act="pick">${t('workOnThisLine')}</button>` : ''}
      <span class="s-listening__spacer"></span>
      ${mode === 'dictation' ? '' : aidsMarkup()}`;
  }

  /* The listening aids act on visible text; in Dictation the text is hidden, so they step aside (LEX-035). */
  function aidsMarkup() {
    return html`${showMeaningToggle ? html`<button type="button" class="s-listening__pill s-listening__pill--toggle" data-act="trans" aria-pressed="${String(showTrans)}"><span class="s-listening__trans-code">${support}</span><span class="s-listening__trans-label">${t('meaning')}</span></button>` : ''}
      <button type="button" class="s-listening__more" data-act="more" aria-pressed="${String(moreOpen)}" aria-label="${t('more')}" title="${t('more')}"><span class="s-listening__more-glyph">${raw(icon('ellipsis', { size: 18 }))}</span></button>
      <span class="s-listening__secondary">${toggles()}</span>
      ${moreOpen ? html`<div class="s-listening__drawer"><div class="s-listening__drawer-row">${toggles()}</div></div>` : ''}`;
  }

  function paintControls() {
    const holder = element.querySelector('[data-controls]');
    mount(holder, controlsMarkup());
    holder.querySelectorAll('[data-act]').forEach((button) => button.addEventListener('click', () => onControl(button.dataset.act)));
  }

  function onControl(action) {
    const at = indexOf(currentId);
    if (action === 'prev') {
      const target = segments[previousIndex(segments, at, timeMs)];
      if (target) playLine(target.segment_id);
      return;
    }
    if (action === 'next') {
      const target = segments[nextIndex(segments, at)];
      if (target) playLine(target.segment_id);
      return;
    }
    if (action === 'replay') return playLine(selectedId || currentId);
    if (action === 'pick') return onSelectedAction('pick');
    if (action === 'speed') {
      speed = nextSpeed(speed);
      if (playbackOk) setPlaybackRate(playerEl, lesson.playback, speed);
      paintControls();
      return;
    }
    if (action === 'trans') {
      showTrans = !showTrans;
      saveStage();
      if (showTrans && !hasMeanings()) toast(t('meaningUnavailable'));
      paintControls();
      paintRows();
      paintNowPlaying();
      return;
    }
    if (action === 'more') { moreOpen = !moreOpen; paintControls(); return; }
    if (action === 'auto') { autoScroll = !autoScroll; saveStage(); paintControls(); return; }
    if (action === 'wordhl') { wordHighlight = !wordHighlight; saveStage(); paintControls(); paintWordHighlight(); }
  }

  /* ---------------------------------------------------------------- transcript ---- */
  function rowTextMarkup(seg) {
    const tokens = tokensOf(seg);
    return html`${tokens.map((token, index) => {
      if (!token.core) return html`<span>${token.text}</span>`;
      if (isZh && token.pinyin !== undefined && /\p{Script=Han}/u.test(token.core)) {
        return html`<span class="s-listening__word s-listening__word--tap s-listening__han" data-word="${token.core}" data-seg="${seg.segment_id}" data-tok="${index}">${token.pinyin ? html`<span class="s-listening__han-py" data-py="1">${token.pinyin}</span>` : ''}<span class="s-listening__han-hz" data-hz="1" lang="zh">${token.text}</span></span>`;
      }
      return html`<span class="s-listening__word s-listening__word--tap" data-word="${token.core}" data-seg="${seg.segment_id}" data-tok="${index}" lang="${langAttr(language)}">${token.text}</span>`;
    })}`;
  }

  function rowsMarkup() {
    if (!segments.length) {
      const processing = transcriptState(payload) === 'processing';
      return html`<div class="s-listening__transcript-state" role="status">${processing ? html`<span class="o-spinner" aria-hidden="true"></span>${processingProgressMarkup(payload.processing?.stage, Object.fromEntries(['fetch','transcribe','segment','translate','ready'].map(stage => [stage,t(`stage_${stage}`)])))}` : ''}${t(processing && payload.processing?.stage === 'transcribe' ? 'aiTranscript' : processing ? 'transcriptProcessing' : 'transcriptUnavailable')} <button type="button" class="o-btn o-btn--secondary o-btn--sm" data-refresh>${t('refreshStatus')}</button></div>`;
    }
    return segments.map((seg) => {
      const tone = rowTone({ isCurrent: seg.segment_id === currentId, isSelected: seg.segment_id === selectedId, endMs: seg.end_ms, timeMs });
      // Dictation: a line's words, reading and meaning stay hidden until it is checked.
      const hidden = mode === 'dictation' && !practice.revealed(seg.segment_id);
      if (hidden) {
        return html`<button type="button" class="s-listening__row is-${tone}${seg.segment_id === currentId ? ' is-playing' : ''}" data-seg="${seg.segment_id}">
          <span class="s-listening__row-time">${mmss(seg.start_ms) ?? ''}</span>
          <span class="s-listening__row-main"><span class="s-listening__row-hidden" aria-label="${dictT('placeholder')}">${hiddenBars(seg)}</span></span>
        </button>`;
      }
      const meaning = showTrans ? enc.meaning(seg.segment_id) : '';
      const playingRow = seg.segment_id === currentId;
      return html`<button type="button" class="s-listening__row is-${tone}${playingRow ? ' is-playing' : ''}" data-seg="${seg.segment_id}">
        <span class="s-listening__row-time">${mmss(seg.start_ms) ?? ''}</span>
        <span class="s-listening__row-main">
          <span class="s-listening__row-text" data-zhf="${isZh ? '1' : '0'}" data-text>${rowTextMarkup(seg)}</span>
          ${meaning ? html`<span class="s-listening__row-vi" style="display:block" lang="${langAttr(support)}">${meaning}</span>` : ''}
        </span>
      </button>`;
    });
  }

  function paintRows() {
    const keep = rowsEl.scrollTop;
    mount(rowsEl, html`${rowsMarkup()}`);
    rowsEl.querySelector('[data-refresh]')?.addEventListener('click', () => window.location.reload());
    rowsEl.scrollTop = keep;
    paintWordHighlight();
  }

  rowsEl.addEventListener('click', (event) => {
    const wordEl = event.target.closest('[data-word]');
    if (wordEl) {
      event.stopPropagation();
      onWordTap(wordEl.dataset.word, wordEl.dataset.seg);
      return;
    }
    const rowEl = event.target.closest('[data-seg]');
    if (rowEl) onRowTap(rowEl.dataset.seg);
  });

  /* The word being spoken, marked on the current row only (`markedEls` is declared with the room's state:
     a resumed line seeks during mount, and the clock can arrive before this point). */
  function paintWordHighlight() {
    for (const el of markedEls) el.classList.remove('is-word-current');
    markedEls = [];
    if (!wordHighlight || !playing) return;
    const seg = segOf(currentId);
    if (!seg) return;
    const indices = currentTokenIndices(seg, tokensOf(seg), timeMs);
    const row = rowsEl.querySelector(`[data-seg="${CSS.escape(seg.segment_id)}"]`);
    for (const at of indices) {
      const el = row?.querySelector(`[data-tok="${at}"]`);
      if (el) { el.classList.add('is-word-current'); markedEls.push(el); }
    }
  }

  function onRowTap(id) {
    const seg = segOf(id);
    if (!seg) return;
    if (mode === 'dictation') {
      playLine(id);
      return;
    }
    if (mode === 'active') {
      selectedId = id;
      playLine(id);
      paintSelected();
      rememberPlace(true);
      return;
    }
    // Follow: seek there and play on.
    bounded = false;
    ended = false;
    currentId = id;
    seekingTo = { id, at: Date.now() };
    if (playbackOk) replaySegment(playerEl, lesson.playback, seg.start_ms, null, speed);
    paintRows();
    paintNowPlaying();
    rememberPlace(true);
  }

  function onWordTap(word, segId) {
    const seg = segOf(segId);
    if (playing && playbackOk) togglePlayback(playerEl, lesson.playback);
    openWordSheet(ctx, {
      word,
      lang: language,
      sentence: seg?.original_text || '',
      source: { kind: 'listening', content_id: routeId, segment: segId, title: lesson.title },
    });
  }

  /* ---------------------------------------------------------------- selected / now playing ---- */
  function phraseLabelFor(seg) {
    return savedPhrases.has(seg.original_text) ? t('phraseSaved') : t('savePhrase');
  }

  function selectedMarkup(seg) {
    const meaning = enc.meaning(seg.segment_id);
    const saved = savedPhrases.has(seg.original_text);
    return html`<div class="s-listening__selected">
      <div class="s-listening__selected-head">
        <span class="s-listening__selected-label">${t('selectedSegment', { time: mmss(seg.start_ms) ?? '' })}</span>
        <span class="s-listening__selected-tools">
          <button type="button" class="s-listening__selected-close s-listening__moreacts" data-act="more-acts" aria-expanded="${String(moreActs)}" aria-label="${t('more')}" title="${t('more')}">${raw(icon('ellipsis', { size: 17 }))}</button>
          <button type="button" class="s-listening__selected-close" data-act="clear" aria-label="${s('close')}">${raw(icon('x', { size: 17 }))}</button>
        </span>
      </div>
      <div class="s-listening__selected-scroll" data-scroll-region>
        <div class="s-listening__selected-text" lang="${langAttr(language)}">${seg.original_text}</div>
        ${meaning ? html`<div class="s-listening__selected-vi" lang="${langAttr(support)}">${meaning}</div>` : ''}
      </div>
      <div class="s-listening__selected-actions" data-scroll-region>
        ${playbackOk ? pill({ id: 'play-seg', label: t('playSegment'), iconName: 'play', variant: 'primary' }) : ''}
        <button type="button" class="s-listening__pill${saved ? ' s-listening__pill--saved' : ''}" data-act="save-phrase" aria-pressed="${String(saved)}">${phraseLabelFor(seg)}</button>
        ${pill({ id: 'vocab', label: t('vocabularyFocus') })}
        <button type="button" class="s-listening__pill--ai" data-act="explain">${markGlyph({ size: 20, symbol: 'ol-intel-still' })}${t('explain')}</button>
        <span class="s-listening__extra-acts${moreActs ? ' is-open' : ''}">
          ${lesson.modes.dictation ? pill({ id: 'dictation', label: s('dictation') }) : ''}
          ${lesson.modes.shadowing ? pill({ id: 'shadowing', label: s('shadowing') }) : ''}
          ${pill({ id: 'react', label: s('reactReuse') })}
        </span>
      </div>
    </div>`;
  }

  function nowPlayingMarkup(cur) {
    const meaning = showTrans ? enc.meaning(cur.segment_id) : '';
    return html`<div class="s-listening__nowplaying">
      <div class="s-listening__nowplaying-head">
        <span class="s-listening__nowplaying-label">${t('nowPlaying', { time: mmss(cur.start_ms) ?? '' })}</span>
        <button type="button" class="s-listening__nowplaying-pick" data-act="pick">${t('workOnThisLine')}</button>
      </div>
      <div class="s-listening__nowplaying-text" lang="${langAttr(language)}">${cur.original_text}</div>
      ${meaning ? html`<div class="s-listening__nowplaying-vi" lang="${langAttr(support)}">${meaning}</div>` : ''}
    </div>`;
  }

  /* The frame shows one or the other: the selected line's actions in Active mode once a line is
     selected, the "now playing" card otherwise (which the phone does not draw). */
  function dictationMarkup(seg) {
    const at = indexOf(seg.segment_id);
    return html`<div class="s-listening__selected s-listening__dict">
      <div class="s-listening__selected-head">
        <span class="s-listening__selected-label">${dictT('headerTitle', { n: at + 1, total: segments.length })} · ${mmss(seg.start_ms) ?? ''}</span>
      </div>
      <div class="s-listening__dict-stage" data-scroll-region data-dict-stage></div>
      <div class="s-listening__dict-dock" data-dict-dock></div>
    </div>`;
  }

  /* Dictation hides the picture while a line is unchecked: a video's own burned-in or provider captions
     would show the answer. Sound stays; the picture returns once the line is checked. */
  function paintVeil() {
    playerEl.classList.toggle('is-veiled', mode === 'dictation' && !practice.revealed(currentId));
  }

  /* Typing on a phone (mobile QA BUG-02): while the answer box has focus the on-screen keyboard takes half the
     screen, so the room keeps only what the task needs - the line's transport, the answer, the hint and Check -
     and gives the rest back when typing ends. The class is removed a moment after focus leaves, so a tap on Check
     or Hint lands before the layout returns. The visible height follows `visualViewport`, so the card is laid out
     above the keyboard rather than behind it. */
  let typingTimer = 0;
  const viewport = window.visualViewport || null;
  function fitVisible() {
    if (viewport) element.style.setProperty('--ls-visible-h', `${Math.round(viewport.height)}px`);
  }
  selectedSlot.addEventListener('focusin', (event) => {
    if (!event.target.matches?.('.s-dict__input')) return;
    clearTimeout(typingTimer);
    fitVisible();
    element.classList.add('is-typing');
    // Safari scrolls the window to reveal a focused field; the room is the viewport, so it goes back to the top.
    requestAnimationFrame(() => window.scrollTo(0, 0));
  });
  selectedSlot.addEventListener('focusout', () => {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => {
      if (document.activeElement?.matches?.('.s-dict__input')) return;
      element.classList.remove('is-typing');
      element.style.removeProperty('--ls-visible-h');
    }, 300);
  });
  viewport?.addEventListener('resize', () => { if (element.classList.contains('is-typing')) fitVisible(); });

  /* The Dictation card is redrawn only when its line changes: replaying or the clock never rebuilds the answer
     box, so the learner's typing, focus and phone keyboard stay put. */
  let dictShownId = null;
  function paintDictationCard() {
    paintVeil();
    if (dictShownId === currentId && selectedSlot.querySelector('.s-listening__dict')) return;
    paintSelected();
  }

  function paintSelected() {
    paintVeil();
    dictShownId = null;
    if (mode === 'dictation') {
      const seg = segOf(currentId);
      dictShownId = currentId;
      const line = seg && dictLesson.segments.find((item) => item.id === seg.segment_id);
      mount(selectedSlot, line ? dictationMarkup(seg) : html``);
      if (line) {
        const last = indexOf(seg.segment_id) >= segments.length - 1;
        practice.show(line, { stage: selectedSlot.querySelector('[data-dict-stage]'), dock: selectedSlot.querySelector('[data-dict-dock]'), next: last ? dictT('finish') : dictT('nextSegment') });
      }
      return;
    }
    const sel = mode === 'active' ? segOf(selectedId) : null;
    const cur = sel ? null : segOf(currentId);
    mount(selectedSlot, sel ? selectedMarkup(sel) : cur ? nowPlayingMarkup(cur) : html``);
    selectedSlot.querySelectorAll('[data-act]').forEach((button) => button.addEventListener('click', () => onSelectedAction(button.dataset.act)));
    if (sel) refreshPhraseState(sel);
  }
  function paintNowPlaying() {
    if (mode === 'active' && segOf(selectedId)) return;
    if (mode === 'dictation') { paintDictationCard(); return; }
    paintSelected();
  }

  /* Whether the selected line is already saved as a phrase (a vocabulary entry named by its
     text), asked of the real library once per line. */
  const phraseChecked = new Set();
  async function refreshPhraseState(seg) {
    if (phraseChecked.has(seg.original_text) || !phraseSaveable(seg.original_text)) return;
    phraseChecked.add(seg.original_text);
    try {
      const res = await api.libraryVocabulary({ query: seg.original_text, limit: 5 });
      if (!ctx.isCurrent()) return;
      if (phraseSaved(res?.items, seg.original_text)) {
        savedPhrases.add(seg.original_text);
        if (selectedId === seg.segment_id) paintSelected();
      }
    } catch {
      phraseChecked.delete(seg.original_text);
    }
  }

  async function togglePhrase(seg) {
    const text = seg.original_text;
    if (!phraseSaveable(text)) { toast(t('phraseTooLong')); return; }
    try {
      if (savedPhrases.has(text)) {
        await api.deleteLibraryVocabulary(text);
        savedPhrases.delete(text);
        toast(t('removedToast'));
      } else {
        await api.saveLibraryVocabulary(phraseSavePayload(text, { meaning: enc.meaning(seg.segment_id) || '' }));
        savedPhrases.add(text);
        // The line kept as a phrase is recorded like a kept word: where it was met, and the sentence.
        void keepProvenance({ term: text, source: { kind: 'listening', content_id: routeId, segment: seg.segment_id }, sentence: text });
        toast(t('phraseSaved'));
      }
    } catch {
      if (ctx.isCurrent()) toast(t('saveFailed'));
      return;
    }
    if (ctx.isCurrent() && selectedId === seg.segment_id) paintSelected();
  }

  /* Vocabulary Focus: the lesson's curated terms for the line, or else the line's own key words from the
     local tagger (D-137 L-11: never an empty panel, never a claimed level). */
  async function openVocab(id, seg) {
    let terms = vocabularyForSegment(lesson.vocabulary, seg.original_text);
    let curated = terms.length > 0;
    if (!curated) {
      try {
        const res = await api.annotateMediaText({ text: seg.original_text, source_language: language });
        terms = keyWordsFrom(res?.annotations, language);
      } catch {
        terms = [];
      }
      if (!ctx.isCurrent()) return;
    }
    const where = { n: indexOf(id) + 1, time: mmss(seg.start_ms) ?? '' };
    openVocabFocus(ctx, {
      label: curated ? t('segmentLabel', where) : t('lineWordsLabel', where),
      terms,
      lang: language,
      support,
      context: seg.original_text,
      source: { kind: 'listening', content_id: routeId, segment: id },
      onPlay: () => playLine(id),
    });
  }

  function onSelectedAction(action) {
    if (action === 'pick') {
      mode = 'active';
      selectedId = currentId;
      bounded = false;
      paintModes();
      paintControls();
      paintRows();
      paintSelected();
      return;
    }
    const id = selectedId || currentId;
    const seg = segOf(id);
    if (action === 'clear') { selectedId = null; paintRows(); paintSelected(); return; }
    // The phone shows the frequent line actions and keeps the rest one tap away (LEX-037).
    if (action === 'more-acts') { moreActs = !moreActs; paintSelected(); return; }
    if (!seg) return;
    if (action === 'play-seg') return playLine(id);
    if (action === 'save-phrase') return togglePhrase(seg);
    if (action === 'vocab') {
      if (playing && playbackOk) togglePlayback(playerEl, lesson.playback);
      void openVocab(id, seg);
      return;
    }
    if (action === 'dictation') { currentId = id; return onMode('dictation'); }
    if (action === 'explain') {
      askOrena({
        surface: 'listening.workspace',
        activity_type: 'listening',
        // The contract's one namespace (§6.1, F-9): `media:<id>`, never the bare route id.
        content_id: contentId,
        selected_item: { type: 'sentence', id, text: seg.original_text, lang: language },
        // Explain explains: the question goes at once, no choosing first (LEX-042).
        ask: dictT('explainAsk'),
      });
      return;
    }
    if (action === 'shadowing') return ctx.go(ctx.href('shadow', { id: routeId }, { seg: id }));
    if (action === 'react') return ctx.go(ctx.href('react', { id: routeId }, { seg: id }));
  }

  /* ---------------------------------------------------------------- end of media ---- */
  async function showEnded() {
    await sideLoads;
    if (!ctx.isCurrent()) return;
    const savedNow = await api.libraryVocabularySummary().then((res) => Number(res?.summary?.saved) || 0).catch(() => savedBaseline ?? 0);
    if (!ctx.isCurrent()) return;
    const savedDelta = savedBaseline != null ? Math.max(0, savedNow - savedBaseline) : 0;
    const dictCount = dictationLinesCompleted(dictProgressItems);
    const listened = listenedMinutesLabel(playedMs);
    const nextMinutes = nextRec?.minutes != null ? `${nextRec.minutes} ${t.plural('minutesLabel', nextRec.minutes)}` : '';
    mount(
      endSlot,
      html`<div class="s-listening__end" role="dialog" aria-label="${t('mediaCompleted')}">
        <div class="s-listening__end-card">
          <div class="s-listening__end-eyebrow">${t('mediaCompleted')}</div>
          <div class="s-listening__end-title" lang="${langAttr(language)}">${lesson.title}</div>
          <div class="s-listening__end-stats">
            <div class="s-listening__end-tile"><div class="s-listening__end-value">${savedDelta}</div><div class="s-listening__end-label">${t.plural('itemsSavedLabel', savedDelta)}</div></div>
            <div class="s-listening__end-tile"><div class="s-listening__end-value">${dictCount}</div><div class="s-listening__end-label">${t.plural('dictationLinesLabel', dictCount)}</div></div>
            <div class="s-listening__end-tile"><div class="s-listening__end-value">${listened || '0:00'}</div><div class="s-listening__end-label">${t('listened')}</div></div>
          </div>
          <button type="button" class="o-btn o-btn--secondary o-btn--block s-listening__end-respond" data-act="respond">${t('writeResponse')}</button>
          ${nextRec ? html`<button type="button" class="s-listening__end-next" data-act="next">
            <span class="s-listening__end-next-thumb" style="${nextRec.posterUrl ? `background-image:url('${posterUrl(nextRec.posterUrl)}')` : ''}"></span>
            <span class="s-listening__end-next-body">
              <span class="s-listening__end-next-eyebrow">${nextRec.topic ? t('nextBecause', { topic: String(nextRec.topic).replace(/-/g, ' ') }) : t('nextPlain')}</span>
              <span class="s-listening__end-next-title">${metaLine([nextRec.title, nextMinutes])}</span>
            </span>
            ${raw(icon('chevron-right', { size: 20 }))}
          </button>` : ''}
          <div class="s-listening__end-actions">
            <button type="button" class="o-btn o-btn--secondary" data-act="replay-all">${t('replayAll')}</button>
            ${lesson.modes.dictation ? html`<button type="button" class="o-btn o-btn--secondary" data-act="dictation-all">${s('dictation')}</button>` : ''}
            <button type="button" class="o-btn o-btn--secondary" data-act="saved">${t('reviewSaved')}</button>
            <button type="button" class="o-btn o-btn--primary" data-act="discover">${s('discover')}</button>
          </div>
        </div>
      </div>`,
    );
    endSlot.querySelectorAll('[data-act]').forEach((button) => button.addEventListener('click', () => onEndAction(button.dataset.act)));
    endSlot.querySelector('[data-act="replay-all"]')?.focus();
  }

  function hideEnded() {
    ended = false;
    mount(endSlot, html``);
  }

  function onEndAction(action) {
    if (action === 'respond') return ctx.go(ctx.href('respond', { id: contentId }));
    if (action === 'next' && nextRec) return ctx.go(ctx.href('content', { id: contentIdFor(nextRec.lessonId) }));
    if (action === 'replay-all') {
      hideEnded();
      bounded = false;
      if (playbackOk) replaySegment(playerEl, lesson.playback, lesson.excerptStartMs, null, speed);
      return;
    }
    if (action === 'dictation-all') {
      hideEnded();
      currentId = segments[0]?.segment_id || currentId;
      return onMode('dictation');
    }
    if (action === 'saved') return ctx.go(ctx.href('library'));
    if (action === 'discover') return ctx.go(ctx.href('discover'));
  }

  paintModes();
  paintTime();
  paintControls();
  paintRows();
  paintSelected();
  rememberPlace(true);
  scrollRowIntoView(currentId);

  // A stored import can finish after the Import sheet's polling window.
  // Re-enter the same workspace when it changes; keep manual refresh available
  // if a status request fails, and never poll after the learner leaves.
  let processingTimer = null;
  if (transcriptState(payload) === 'processing' && payload.asset?.asset_id) {
    const refreshProcessing = async () => {
      if (!ctx.isCurrent()) return;
      try {
        const updated = await api.mediaMy(payload.asset.asset_id, support);
        if (!ctx.isCurrent()) return;
        if (updated?.asset?.processing_state !== 'processing') {
          rememberMedia(lessonId, { support, language: c.language, owner: c.owner || 'local' }, updated);
          ctx.go(ctx.href('listening', { id: lessonId }));
          return;
        }
        payload.processing = updated.processing;
        paintRows();
      } catch { /* The explicit refresh action remains available. */ }
      if (ctx.isCurrent()) processingTimer = setTimeout(refreshProcessing, 3000);
    };
    processingTimer = setTimeout(refreshProcessing, 3000);
  }

  /* AGENT_CONTRACT.md §7: `play_model` = "play reference audio" - here, the selected (or
     current) transcript line. Listening has no learner take of its own (`play_user`/
     `say_again`/`compare_with_model` do not apply: there is nothing to compare or re-record). */
  const releasePlayModel = registerActionHandler('play_model', () => {
    const id = (mode === 'active' && selectedId) || currentId; // Dictation: the line being written
    if (!id || !playbackOk) return { ok: false, reason: 'not_available' };
    playLine(id);
    return { ok: true };
  });

  return () => {
    clearTimeout(chromeTimer);
    clearTimeout(typingTimer);
    playerEl.removeEventListener('pointermove', revealPlayerChrome);
    playerEl.removeEventListener('pointerdown', revealPlayerChrome);
    clearTimeout(processingTimer);
    releasePlayModel();
    paneObserver?.disconnect();
    if (playbackOk) {
      playerEl.removeEventListener('orena:media-time', onMediaTime);
      disconnectMediaPlayer(playerEl);
    }
  };
}
