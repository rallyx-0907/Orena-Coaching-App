import {
  responseComposer,
  bindComposer,
  progressReporter,
  savedLanguageLink,
} from './patterns.js';
import { esc, safeExternal, dialog, status, focusRegion } from './html.js';
import {
  openUnderstanding,
  selectionWithin,
} from './understanding.js';
import { voiceEvidence } from './voice-evidence.js';
import { link, deeperPractice } from '../product/intent.js';
import { encounter } from '../product/encounter.js';
import {
  dictationEvidence,
  recoverListeningEvidence,
} from '../product/evidence.js';
import { contentFor } from '../content/texts.js';
import { preparedMeaning } from '../content/language-notes.js';
import {
  mediaPlayer,
  connectMediaPlayer,
  disconnectMediaPlayer,
  replaySegment,
  togglePlayback,
  setPlaybackRate,
  stopSegmentPlayback,
  seekPlayback,
} from '../capabilities/media-player.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import {
  linePieces,
  activeWordIndex,
  wordSpans,
} from '../capabilities/word-timeline.js';
import {
  dictationHint,
  MAX_HINT_LEVEL,
} from '../capabilities/dictation-hints.js';
import { evaluateVoice } from '../capabilities/voice-feedback.js';
import {
  acquireMedia,
  translationRequest,
} from '../capabilities/media-acquisition.js';
import { art, origin, duration, bindImages, audioIdentity } from './content.js';

/* Every capability investigates language through the one shared surface. This
   keeps the old call shape so the transcript, the story margin and the
   dictation comparison do not each need to know about it. */
export function inspectPhrase(ctx, text, title, context) {
  return openUnderstanding(ctx, {
    selection: text,
    context: context || text,
    title,
  });
}

function textEncounter(root, ctx, item) {
  const { c, language, memory } = ctx;
  let count = item.kind === 'conversation' ? 1 : item.paragraphs?.length || 1;
  const paragraphs = item.paragraphs || [item.text];
  memory.enter({ id: item.id, title: item.title, excerpt: paragraphs[0] });
  const paint = () => {
    root.innerHTML = `<div class="back-row"><a href="#/">← ${c.back}</a><button data-keep class="quiet" aria-pressed="${memory.value.kept.includes(item.id)}">${memory.value.kept.includes(item.id) ? c.saved : c.keep} ＋</button></div><header class="text-heading"><small>${origin(item, c)}</small><h1 lang="${language}">${esc(item.title)}</h1><p lang="${language}">${esc(item.subtitle || '')}</p></header><div class="text-encounter"><article class="passage ${item.kind === 'conversation' ? 'dialogue' : ''}" lang="${language}">${paragraphs
      .slice(0, count)
      .map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`)
      .join(
        '',
      )}${count < paragraphs.length ? `<button class="outline" data-next>${c.nextLine} →</button>` : item.question ? `<h2>${esc(item.question)}</h2>` : ''}</article><aside class="language-margin"><div class="margin-art">${art(item)}</div><h2>${c.inspect}</h2>${(item.phrases || []).map((p, i) => `<details><summary lang="${language}">${esc(p.word)}</summary>${p.phonetic && ctx.profile.pinyin !== 'off' ? `<p class="pinyin">${esc(p.phonetic)}</p>` : ''}<p>${esc(preparedMeaning(p, language, ctx.support).text)}</p><blockquote lang="${language}">${esc(p.example)}</blockquote><button data-note="${i}">${c.savePhrase} ＋</button><p role="status"></p></details>`).join('')}<button class="outline" data-inspect>${c.phrase} ↗</button></aside></div>${responseComposer(ctx, item)}<p class="provenance">${item.origin === 'imported' ? c.ownText : c.prepared}</p>`;
    root.querySelector('[data-keep]').onclick = () => {
      memory.keep(item.id);
      paint();
    };
    root.querySelector('[data-next]')?.addEventListener('click', () => {
      count++;
      paint();
      (
        root.querySelector('[data-next]') || root.querySelector('#response')
      )?.focus({ preventScroll: true });
    });
    const passage = root.querySelector('.passage');
    const investigate = () => {
      const picked = selectionWithin(passage);
      openUnderstanding(ctx, {
        selection: picked ? picked.text : paragraphs.join('\n').slice(0, 2400),
        context: picked ? picked.context : paragraphs.join('\n').slice(0, 2400),
        title: `${origin(item, c)} · ${item.title}`,
      });
    };
    root.querySelector('[data-inspect]').onclick = investigate;
    // A highlight is the natural way to ask about a phrase while reading, so
    // offer the action where the learner made it rather than only in the margin.
    passage.addEventListener('mouseup', () => {
      const picked = selectionWithin(passage);
      const button = root.querySelector('[data-inspect]');
      button.textContent = picked
        ? `${c.lookCloser}: ${picked.text.slice(0, 24)}${picked.text.length > 24 ? '…' : ''} ↗`
        : `${c.phrase} ↗`;
    });
    root.querySelectorAll('[data-note]').forEach(
      (button) =>
        (button.onclick = async () => {
          const p = item.phrases[Number(button.dataset.note)],
            output = button.nextElementSibling;
          const report = progressReporter(output, ctx, ctx.alive);
          const save = async () => {
            button.disabled = true;
            report.saving();
            try {
              await ctx.mutate(() =>
                ctx.api.saveLibraryVocabulary({
                  word: p.word,
                  phonetic: p.phonetic || '',
                  definition: preparedMeaning(p, language, ctx.support).text,
                  source_kind: 'manual',
                  source_fragment: paragraphs[p.paragraph].slice(0, 1200),
                  focus_note: `${origin(item, c)} · ${item.title}`,
                }),
              );
              report.saved(savedLanguageLink(c));
            } catch {
              report.failed(c.failedSave, save);
              if (ctx.alive()) button.disabled = false;
            }
          };
          await save();
        }),
    );
    bindComposer(root, ctx, item);
    bindImages(root, c);
  };
  paint();
}
function waitingMedia(root, ctx, payload) {
  const { c, language, memory } = ctx;
  const id = ctx.location.id,
    title = payload.asset.title || c.pendingMedia;
  // A catalog lesson whose transcript is still missing reaches this same
  // waiting room, and it must not be described as something the learner
  // brought in. addMedia already ignores anything that is not an import.
  const imported = id.startsWith('url:');
  memory.enter({ id, title, source_url: payload.asset.source_url });
  memory.addMedia({
    id,
    title,
    kind: payload.playback.kind,
    duration_ms: payload.asset.duration_ms,
  });
  root.innerHTML = `<div class="back-row"><a href="#/">← ${c.back}</a><small>${imported ? c.imported : c.curated}</small></div><header class="encounter-heading"><div><small>${c.pendingMedia}</small><h1 lang="${language}">${esc(title)}</h1></div><p>${c.pendingNote}</p></header><section class="pending-media"><div class="player-wrap">${mediaPlayer(payload.playback, title)}</div><div class="transport"><button data-play>${c.play}</button><button data-retry>${c.retry}</button></div><p data-recovery-state role="status">${c.pendingNote}</p></section>`;
  const playerRoot = root.querySelector('.pending-media');
  connectMediaPlayer(playerRoot, payload.playback);
  root.querySelector('[data-play]').onclick = () =>
    togglePlayback(playerRoot, payload.playback);
  root.querySelector('[data-retry]').onclick = () => window.location.reload();
  return () => disconnectMediaPlayer(playerRoot);
}
export async function renderEncounter(root, ctx) {
  const { api, c, language, memory, location, alive } = ctx;
  const id = location.id;
  if (id.startsWith('story:') || id.startsWith('text:')) {
    const item = id.startsWith('story:')
      ? contentFor(language).find((x) => `story:${x.id}` === id)
      : memory.value.imports.find((x) => x.id === id);
    if (!item) throw Error(c.unavailable);
    textEncounter(root, ctx, { ...item, id });
    return;
  }
  let pendingCleanup = null;
  const onProgress = (value) => {
    if (
      alive() &&
      !pendingCleanup &&
      value?.asset &&
      value?.playback &&
      !value.transcript?.segments?.length
    )
      pendingCleanup = waitingMedia(root, ctx, value);
  };
  let payload;
  try {
    payload = id.startsWith('media:')
      ? await api.listeningLibraryLesson(id.slice(6), ctx.support)
      : id.startsWith('url:')
        ? await acquireMedia({
            api,
            url: id.slice(4),
            target: ctx.support,
            owner: ctx.owner,
            language,
            alive,
            onProgress,
          })
        : null;
  } catch (error) {
    if (pendingCleanup && alive()) {
      root.querySelector('[data-recovery-state]').textContent = c.sourceOnly;
      return pendingCleanup;
    }
    pendingCleanup?.();
    throw error;
  }
  if (!alive()) {
    pendingCleanup?.();
    return;
  }
  if (!payload?.transcript?.segments?.length) {
    if (payload?.asset && payload.playback) {
      pendingCleanup ||= waitingMedia(root, ctx, payload);
      root.querySelector('[data-recovery-state]').textContent = c.sourceOnly;
      return pendingCleanup;
    }
    throw Error(c.unavailable);
  }
  pendingCleanup?.();
  if (payload.asset.source_language !== language) throw Error(c.unavailable);
  const model = encounter(payload, ctx.support),
    item = {
      ...payload.catalog,
      id,
      title: payload.asset.title,
      origin: id.startsWith('url:') ? 'imported' : 'curated',
      kind: payload.playback.kind,
    };
  if (id.startsWith('url:'))
    memory.addMedia({
      id,
      title: item.title,
      kind: item.kind,
      duration_ms: payload.asset.duration_ms,
    });
  const prior = memory.value.continuation.find((x) => x.id === id);
  if (prior?.segment) model.select(prior.segment);
  let practice = deeperPractice.includes(location.intent)
      ? location.intent
      : null,
    rate = 1,
    recording = false,
    recorder = createLocalAudioRecorder(),
    take = null,
    takeId = '',
    practiceTarget = null,
    lastClockSegment = null;
  let disposed = false,
    practiceVersion = 0;
  const isAlive = () => alive() && !disposed;
  const remember = () =>
    memory.enter({
      id,
      title: item.title,
      segment: model.current?.segment_id,
      intent: practice,
      source_url: payload.asset.source_url,
      excerpt: model.current?.original_text,
    });
  remember();
  root.innerHTML = `<div class="back-row"><a href="#/">← ${c.back}</a><small>${esc(origin(item, c))}</small><button class="quiet" data-keep aria-pressed="${memory.value.kept.includes(id)}">${memory.value.kept.includes(id) ? c.saved : c.keep} ＋</button></div><header class="encounter-heading"><div><small>${esc(c['topic_' + payload.catalog?.topic] || c.follow)} · ${duration((payload.catalog?.excerpt_end_ms || payload.asset.duration_ms) - (payload.catalog?.excerpt_start_ms || 0))}</small><h1 lang="${language}">${esc(item.title)}</h1></div><p>${c.followNote}</p></header><div class="media-encounter"><section class="media-stage"><div class="player-wrap ${payload.playback.kind === 'audio' ? 'audio-player' : ''}">${payload.playback.kind === 'audio' ? audioIdentity(item, c) : ''}${mediaPlayer(payload.playback, item.title, { startMs: payload.catalog?.excerpt_start_ms || 0, endMs: payload.catalog?.excerpt_end_ms, poster: payload.catalog?.poster_url })}</div><div class="transport"><button data-play aria-label="${c.play}">▶</button><button data-replay>${c.replay} ↺</button><label><span class="sr-only">${c.speed}</span><select data-rate aria-label="${c.speed}">${[0.5, 0.75, 1, 1.25, 1.5, 2].map((v) => `<option value="${v}" ${v === 1 ? 'selected' : ''}>${v}×</option>`).join('')}</select></label></div><label class="seek-line"><span class="sr-only">${c.seek}</span><input data-seek type="range" min="${payload.catalog?.excerpt_start_ms || 0}" max="${payload.catalog?.excerpt_end_ms || payload.asset.duration_ms}" value="${model.current.start_ms}" step="100" aria-label="${c.seek}"><output data-time>0:00</output></label><section class="follow-moment" aria-label="${c.follow}"><small>${c.current}</small><p class="spoken" lang="${language}"></p><p class="pinyin" data-pinyin></p><p class="meaning" lang="${ctx.support}"></p><button class="quiet" data-meaning hidden>${c.recoverMeaning} ↗</button></section><div class="moment-actions"><span>${location.intent === 'follow' ? c.followOptional : c.deeper}</span><button data-intent="dictation">${c.dictate} ↗</button><button data-intent="shadowing">${c.shadow} ↗</button><button data-intent="speaking">${c.speakingName} ↗</button><button data-inspect>${c.inspect} ＋</button></div><section class="practice-space" hidden></section></section><aside class="transcript-panel"><h2>${c.transcript}</h2><ol>${model.segments.map((s, i) => `<li><button data-segment="${esc(s.segment_id)}"><time>${duration(s.start_ms)}</time><span lang="${language}">${esc(s.original_text)}</span></button></li>`).join('')}</ol></aside></div><details class="source"><summary>${c.rights}</summary><p>${esc(payload.catalog?.source?.creator || origin(item, c))}</p><p>${esc(payload.catalog?.source?.license || '')}</p><a href="${esc(safeExternal(payload.catalog?.source?.provenance_url || payload.asset.source_url))}" target="_blank" rel="noopener noreferrer">${c.original} ↗</a></details>${responseComposer(ctx, item)}`;
  const playerRoot = root.querySelector('.media-stage');
  const mediaStatus = document.createElement('p');
  mediaStatus.className = 'notice';
  mediaStatus.setAttribute('role', 'status');
  mediaStatus.hidden = true;
  playerRoot.querySelector('.player-wrap').after(mediaStatus);
  const onMediaState = event => {
    const state = event.detail.state;
    mediaStatus.hidden = !['blocked', 'error'].includes(state);
    if (state === 'blocked') mediaStatus.textContent = c.mediaBlocked;
    if (state === 'error') {
      mediaStatus.innerHTML = `${c.mediaFailed} <button data-retry-media>${c.retry}</button>`;
      mediaStatus.querySelector('[data-retry-media]').onclick = () => ctx.go('encounter', {id, intent:practice});
    }
  };
  playerRoot.addEventListener('orena:media-state', onMediaState);
  const practiceRoot = root.querySelector('.practice-space');
  const moment = root.querySelector('.follow-moment');
  const transcript = root.querySelector('.transcript-panel');
  const original = moment.querySelector('.spoken'),
    meaning = moment.querySelector('.meaning');
  /* Word-level Follow sharpens the segment; it never replaces it. An asset
     whose word timing does not reconcile with the canonical line renders as
     plain text and keeps segment Follow exactly as it was. */
  let followSpans = null;
  let followWord = -1;
  function paintFollow(gap = false) {
    const s = model.current;
    if (!s) return;
    followSpans = gap ? null : wordSpans(s);
    followWord = -1;
    if (gap) original.textContent = c.pauseGap;
    else if (followSpans) {
      const pieces = linePieces(s);
      original.innerHTML = pieces
        .map((piece) =>
          piece.index < 0
            ? esc(piece.text)
            : `<span class="word" data-word="${piece.index}">${esc(piece.text)}</span>`,
        )
        .join('');
    } else original.textContent = s.original_text;
    const translated = model.meaning();
    meaning.textContent = gap
      ? ''
      : translated || (ctx.support === language ? c.sameLanguage : c.noMeaning);
    const pinyin = payload.catalog?.pinyin_by_segment?.[s.segment_id];
    moment.querySelector('[data-pinyin]').textContent =
      !gap && ctx.profile.pinyin !== 'off'
        ? typeof pinyin === 'string'
          ? pinyin
          : ''
        : '';
    moment.querySelector('[data-meaning]').hidden =
      gap || Boolean(translated) || ctx.support === language;
    root.querySelectorAll('[data-segment]').forEach((x) => {
      const active = !gap && x.dataset.segment === s.segment_id;
      x.setAttribute('aria-current', String(active));
    });
  }
  const playLine = () => {
    const s = practiceTarget || model.current;
    if (s)
      replaySegment(playerRoot, payload.playback, s.start_ms, s.end_ms, rate);
  };
  root.querySelector('[data-play]').onclick = () =>
    togglePlayback(playerRoot, payload.playback);
  root.querySelector('[data-replay]').onclick = playLine;
  root.querySelector('[data-rate]').onchange = (event) => {
    rate = Number(event.target.value);
    setPlaybackRate(playerRoot, payload.playback, rate);
  };
  root.querySelector('[data-keep]').onclick = (event) => {
    memory.keep(id);
    event.currentTarget.textContent = memory.value.kept.includes(id)
      ? c.saved
      : c.keep;
    event.currentTarget.setAttribute(
      'aria-pressed',
      String(memory.value.kept.includes(id)),
    );
  };
  root.querySelector('[data-inspect]').onclick = () => {
    const picked = selectionWithin(moment);
    inspectPhrase(
      ctx,
      picked ? picked.text : model.current.original_text,
      `${origin(item, c)} · ${item.title}`,
      model.current.original_text,
    );
  };
  root.querySelector('[data-meaning]').onclick = async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const translated = await api.translateMedia(
        translationRequest(payload, ctx.support),
      );
      if (isAlive()) {
        payload.translations = translated.translations || [];
        payload.translation = translated.translation;
        paintFollow();
      }
    } catch {
      // Saying "no meaning" again would look like nothing happened; the
      // learner asked for a retry and deserves to know it did not land.
      if (isAlive()) meaning.textContent = c.meaningUnavailable;
    } finally {
      button.disabled = false;
    }
  };
  root.querySelectorAll('[data-segment]').forEach(
    (button) =>
      (button.onclick = () => {
        if (recording) return;
        model.select(button.dataset.segment);
        practice = null;
        closePractice();
        const s = model.current;
        replaySegment(playerRoot, payload.playback, s.start_ms, null, rate);
        paintFollow();
        remember();
      }),
  );
  const seekInput = root.querySelector('[data-seek]');
  const timeOutput = root.querySelector('[data-time]');
  const playButton = root.querySelector('[data-play]');
  // While the learner is holding the handle, the clock must not write the
  // position back underneath them, or the thumb fights the drag.
  let scrubbing = false;
  const releaseScrub = () => {
    scrubbing = false;
  };
  seekInput.addEventListener('pointerdown', () => {
    scrubbing = true;
  });
  seekInput.addEventListener('keydown', () => {
    scrubbing = true;
  });
  seekInput.addEventListener('pointerup', releaseScrub);
  seekInput.addEventListener('pointercancel', releaseScrub);
  seekInput.addEventListener('keyup', releaseScrub);
  seekInput.addEventListener('blur', releaseScrub);
  seekInput.oninput = (event) => {
    timeOutput.textContent = duration(Number(event.target.value));
    seekPlayback(playerRoot, payload.playback, Number(event.target.value));
  };
  function onClock(event) {
    const playing = event.detail.player_state === 1;
    if (!scrubbing) {
      timeOutput.textContent = duration(event.detail.time_ms);
      seekInput.value = String(event.detail.time_ms);
    }
    playButton.textContent = playing ? 'Ⅱ' : '▶';
    playButton.setAttribute('aria-label', playing ? c.pause : c.playAction);
    if (followSpans) {
      const index = activeWordIndex(followSpans, event.detail.time_ms);
      if (index !== followWord) {
        followWord = index;
        original
          .querySelectorAll('.word')
          .forEach((node) =>
            node.toggleAttribute(
              'data-speaking',
              Number(node.dataset.word) === index,
            ),
          );
      }
    }
    if (practice) return;
    const s = model.follow(event.detail.time_ms);
    // "Between spoken lines" is only true of media that is running. At rest -
    // and a paused player sits at 0ms, before the first line - the learner
    // should still be looking at the line they are on.
    const key = s ? s.segment_id : playing ? 'gap' : lastClockSegment;
    if (key !== lastClockSegment) {
      lastClockSegment = key;
      paintFollow(!s);
      if (s) {
        remember();
        const active = root.querySelector(
          '[data-segment][aria-current="true"]',
        );
        if (
          active &&
          !transcript.matches(':hover') &&
          !transcript.contains(document.activeElement)
        )
          transcript.querySelector('ol').scrollTo({
            top: Math.max(
              0,
              active.offsetTop - transcript.querySelector('ol').offsetTop - 60,
            ),
            behavior: matchMedia('(prefers-reduced-motion: reduce)').matches
              ? 'instant'
              : 'smooth',
          });
      }
    }
  }
  playerRoot.addEventListener('orena:media-time', onClock);
  connectMediaPlayer(playerRoot, payload.playback);
  paintFollow();
  function closePractice() {
    practiceVersion++;
    recorder.cleanup();
    recorder = createLocalAudioRecorder();
    recording = false;
    setRecordingLock(false);
    take = null;
    practiceTarget = null;
    practiceRoot.hidden = true;
    moment.hidden = false;
    transcript.hidden = false;
    root.querySelector('.moment-actions').hidden = false;
    practice = null;
    lastClockSegment = null;
    paintFollow();
    remember();
  }
  /* A live microphone owns the segment. Rather than swallowing clicks that
     would move it, say so on the controls themselves, so the reason a control
     will not respond is visible and reaches assistive technology too. */
  function setRecordingLock(active) {
    root.querySelectorAll('[data-segment]').forEach((x) => {
      x.disabled = active;
      if (active) x.title = c.recordingInProgress;
      else x.removeAttribute('title');
    });
    const next = practiceRoot.querySelector('[data-next-moment]');
    if (next && (active || !next.dataset.exhausted)) next.disabled = active;
  }
  function basePractice() {
    stopSegmentPlayback(playerRoot, payload.playback);
    practiceTarget = { ...model.current };
    moment.hidden = true;
    transcript.hidden = practice === 'dictation';
    root.querySelector('.moment-actions').hidden = true;
    practiceRoot.hidden = false;
    // The transcript stays on screen through Shadowing and Speaking, so it has
    // to mark the line being practised rather than the one Follow left behind.
    paintFollow();
    remember();
  }
  async function openPractice(intent) {
    if (recording) return;
    practiceVersion++;
    const version = practiceVersion;
    practice = intent;
    recorder.discard();
    take = null;
    basePractice();
    const target = practiceTarget;
    practiceRoot.innerHTML = `<div class="practice-top"><small>${c[intent + 'Name']}</small><button class="quiet" data-follow>← ${c.followBack}</button></div><h2>${intent === 'dictation' ? c.hearFirst : intent === 'speaking' ? c.voiceResponse : c.shadowPrompt}</h2><div data-practice-body></div><button class="quiet" data-next-moment>${c.next} →</button>`;
    practiceRoot.querySelector('[data-follow]').onclick = closePractice;
    focusRegion(practiceRoot.querySelector('h2'));
    const body = practiceRoot.querySelector('[data-practice-body]');
    const nextIndex =
      model.segments.findIndex((x) => x.segment_id === target.segment_id) + 1;
    const nextButton = practiceRoot.querySelector('[data-next-moment]');
    const exhausted = nextIndex >= model.segments.length;
    nextButton.textContent = exhausted ? `${c.followBack} →` : `${c.next} →`;
    nextButton.onclick = () => {
      if (recording) return;
      closePractice();
      if (exhausted) return;
      model.select(model.segments[nextIndex].segment_id);
      openPractice(intent);
    };
    if (intent === 'dictation') {
      body.innerHTML = `<button class="outline" data-listen>${c.replay} ↺</button><form id="dictationForm"><label for="reconstruction">${c.dictatePrompt}</label><textarea id="reconstruction" lang="${language}" maxlength="2000" rows="3" required></textarea><div class="button-row"><button class="primary">${c.check}</button><button type="button" data-hint>${c.hint}</button><button type="button" data-reveal>${c.reveal}</button></div></form><section class="hint-line" data-hint-panel hidden></section><div class="comparison" aria-live="polite"></div><p class="meta">${c.comparisonNote}</p><p data-evidence-status role="status"></p>`;
      body.querySelector('[data-listen]').onclick = playLine;
      /* The hint is a working aid, not an outcome: it lives for this visit
         only and never becomes evidence. Revealing the answer stays the
         separate, recorded act it already was. */
      let hintLevel = 0;
      const hintPanel = body.querySelector('[data-hint-panel]');
      const hintButton = body.querySelector('[data-hint]');
      const paintHint = () => {
        if (!hintLevel) return;
        const hint = dictationHint({
          expected: target.spoken_text || target.original_text,
          answer: body.querySelector('textarea').value,
          source_language: language,
          level: hintLevel,
        });
        hintPanel.hidden = false;
        hintPanel.innerHTML = `<small>${esc(c.hintTitle)}</small><p class="hint-slots" lang="${language}">${hint.slots.map((slot) => (slot.kind === 'anchor' ? `<b>${esc(slot.text)}</b>` : slot.kind === 'slot' ? `<i>${esc(slot.text)}</i>` : esc(slot.text))).join('')}</p><p class="meta">${esc(hint.complete ? c.hintComplete : c.hintNote)}${hint.anchors ? ` · ${hint.anchors}/${hint.total} ${esc(c.hintAnchors)}` : ''}</p>`;
        hintButton.textContent =
          hintLevel >= MAX_HINT_LEVEL ? c.hintMore : c.hint;
        hintButton.disabled = hintLevel >= MAX_HINT_LEVEL;
      };
      hintButton.onclick = () => {
        hintLevel = Math.min(MAX_HINT_LEVEL, hintLevel + 1);
        paintHint();
      };
      const answer = body.querySelector('textarea'),
        key = `${payload.asset.asset_id}:${target.segment_id}`;
      answer.value = memory.value.answers[key] || '';
      answer.oninput = () => {
        memory.write(key, answer.value, 'answers');
        paintHint();
      };
      body.querySelectorAll('form button').forEach((x) => (x.disabled = true));
      let previous = {},
        priorRead = false;
      const readPrior = async () => {
        await ctx.settledWrites();
        const progress = await api.listeningProgress(payload.asset.asset_id);
        return (
          (progress.items || []).find(
            (x) => x.segment_id === target?.segment_id,
          ) || {}
        );
      };
      try {
        previous = await readPrior();
        priorRead = true;
      } catch {}
      if (!isAlive() || version !== practiceVersion) return;
      const dictation = dictationEvidence({
        asset: payload.asset.asset_id,
        segment: target,
        language,
        previous,
      });
      body.querySelectorAll('form button').forEach((x) => (x.disabled = false));
      const recover = recoverListeningEvidence(readPrior);
      const report = progressReporter(
        body.querySelector('[data-evidence-status]'),
        ctx,
        () => isAlive() && version === practiceVersion,
      );
      if (!priorRead) report.note(c.priorProgressUnread);
      const persist = async () => {
        const snapshot = dictation.value;
        body
          .querySelectorAll('form button, [data-retry-action]')
          .forEach((x) => (x.disabled = true));
        report.saving();
        try {
          // Practice that began without the stored record only knows this
          // session, so fold it into the server's copy instead of replacing it.
          const evidence = priorRead ? snapshot : await recover(snapshot);
          await ctx.mutate(() => api.saveListeningProgress(evidence));
          report.saved();
        } catch {
          report.failed(priorRead ? c.failedSave : c.priorProgressUnread, persist);
        } finally {
          if (isAlive() && version === practiceVersion)
            body
              .querySelectorAll('form button')
              .forEach((x) => (x.disabled = false));
        }
      };
      body.querySelector('form').onsubmit = async (event) => {
        event.preventDefault();
        try {
          const { result, diff } = dictation.compare(answer.value.trim());
          body.querySelector('.comparison').innerHTML =
            `<h3>${result.accuracy_percent}% ${c.match}</h3><div class="diff" lang="${language}">${diff.map((x) => `<span class="${x.status}"><span class="sr-only">${esc(x.status === 'correct' ? c.correct : x.status === 'extra' ? c.extra : c.missing)}: </span>${x.status === 'wrong' ? `<del>${esc(x.actual)}</del> → ` : x.status === 'missing' ? '+ ' : x.status === 'extra' ? '− ' : ''}${esc(x.expected || x.actual)}</span>`).join('')}</div><p lang="${language}">${esc(target.original_text)}</p><p>${esc(model.meaning(target.segment_id) || c.noMeaning)}</p><div class="button-row"><button data-again>${c.tryAgain} ↺</button><button data-understand>${c.inspect} ↗</button></div>`;
          body.querySelector('[data-understand]').onclick = () =>
            inspectPhrase(ctx, target.original_text, item.title, target.original_text);
          body.querySelector('[data-again]').onclick = () => {
            body.querySelector('.comparison').innerHTML = '';
            answer.focus();
            playLine();
          };
          await persist();
        } catch (error) {
          body.querySelector('.comparison').textContent = error.message;
        }
      };
      body.querySelector('[data-reveal]').onclick = () => {
        dictation.reveal();
        body.querySelector('.comparison').innerHTML =
          `<p lang="${language}">${esc(target.original_text)}</p><p>${esc(model.meaning(target.segment_id) || c.noMeaning)}</p>`;
        persist();
      };
      playLine();
    } else {
      body.innerHTML = `<blockquote lang="${language}">${esc(target.original_text)}</blockquote><p>${esc(model.meaning(target.segment_id) || '')}</p><p>${intent === 'shadowing' ? c.shadowGuide : c.speakingGuide}</p><div class="button-row"><button class="outline" data-listen>${c.replay} ↺</button><button class="primary" data-record>● ${c.record}</button></div><p role="status" data-record-status></p><div data-take></div><p class="meta">${c.localAudio}</p><div data-feedback></div>`;
      body.querySelector('[data-listen]').onclick = playLine;
      body.querySelector('[data-record]').onclick = async (event) => {
        const button = event.currentTarget,
          output = body.querySelector('[data-record-status]');
        button.disabled = true;
        if (recording) {
          take = await recorder.stop();
          recording = false;
          setRecordingLock(false);
          button.textContent = `● ${c.record}`;
          if (!isAlive() || version !== practiceVersion) return;
          if (take) {
            takeId = crypto.randomUUID();
            body.querySelector('[data-take]').innerHTML =
              `<h3>${c.take}</h3><audio controls src="${esc(take.url)}"></audio><div class="button-row"><button class="primary" data-feedback-action>${c.feedback}</button>${intent === 'shadowing' ? `<button class="outline" data-pronunciation>${c.pronunciation}</button>` : ''}</div>`;
            output.textContent = c.selfReport;
            // Wire the take's own actions before anything is awaited: these
            // buttons are already on screen, and a slow save must not leave
            // them looking live while nothing answers a click.
            body.querySelector('[data-feedback-action]').onclick = () =>
              voiceFeedback();
            bindPronunciation();
            if (intent === 'shadowing') {
              try {
                await ctx.settledWrites();
                if (!isAlive() || version !== practiceVersion) return;
                const records = await api.shadowingProgress(
                  payload.asset.asset_id,
                );
                const prior = (records.items || []).find(
                  (x) => x.segment_id === target.segment_id,
                );
                await ctx.mutate(() =>
                  api.saveShadowingProgress({
                    asset_id: payload.asset.asset_id,
                    segment_id: target.segment_id,
                    completed_rounds: Math.min(
                      1000,
                      (prior?.completed_rounds || 0) + 1,
                    ),
                  }),
                );
                if (isAlive())
                  output.textContent = c.persisted + ' · ' + c.selfReport;
              } catch {
                if (isAlive()) output.textContent = c.failedSave;
              }
            }
          } else output.textContent = c.microphone;
        } else {
          stopSegmentPlayback(playerRoot, payload.playback);
          // The previous take and any feedback about it stop being true the
          // moment a new recording starts.
          take = null;
          takeId = '';
          body.querySelector('[data-take]').innerHTML = '';
          body.querySelector('[data-feedback]').textContent = '';
          const activeRecorder = recorder;
          const started = await activeRecorder.start();
          if (!isAlive() || version !== practiceVersion) {
            activeRecorder.cleanup();
            return;
          }
          recording = started;
          setRecordingLock(started);
          button.textContent = started ? `■ ${c.stop}` : `● ${c.record}`;
          output.textContent = started ? c.recording : c.microphone;
        }
        button.disabled = false;
      };
      function bindPronunciation() {
        const pronunciationButton = body.querySelector('[data-pronunciation]');
        if (!pronunciationButton) return;
        pronunciationButton.onclick = async () => {
          // A recording made while this request is in flight replaces the take,
          // so the answer that comes back is about audio the learner has
          // already moved on from.
          const assessedTake = takeId,
            assessedBlob = take?.blob;
          pronunciationButton.disabled = true;
          const area = body.querySelector('[data-feedback]');
          area.textContent = c.loading;
          try {
            const result = await api.assessPronunciation(
              assessedBlob,
              language,
              target.spoken_text || target.original_text,
            );
            if (
              isAlive() &&
              version === practiceVersion &&
              assessedTake === takeId
            )
              area.innerHTML = `<h3>${c.pronunciation}</h3><p>${c.accuracy}: ${result.accuracy_score ?? c.notMeasured} · ${c.fluency}: ${result.fluency_score ?? c.notMeasured}</p><div class="pronunciation-words">${(result.words || []).map((x) => `<span lang="${language}">${esc(x.word)} <small>${x.accuracy_score ?? c.notMeasured}</small></span>`).join('')}</div><p class="meta">${result.score_kind === 'synthetic_demo' ? c.demoMeasurement : c.voiceMeasureNote}</p>`;
          } catch {
            if (isAlive() && assessedTake === takeId) {
              area.textContent = c.feedbackUnavailable;
              pronunciationButton.disabled = false;
            }
          }
        };
      }
      async function voiceFeedback() {
        const currentTake = take,
          currentTakeId = takeId;
        const area = body.querySelector('[data-feedback]');
        area.textContent = c.loading;
        body.querySelector('[data-feedback-action]').disabled = true;
        try {
          if (intent === 'shadowing') {
            const result = await ctx.mutate(() =>
              evaluateVoice({
                api,
                blob: currentTake.blob,
                language,
                reference: target.spoken_text || target.original_text,
                assetId: payload.asset.asset_id,
                segmentId: target.segment_id,
                takeId: currentTakeId,
              }),
            );
            if (
              !isAlive() ||
              version !== practiceVersion ||
              currentTakeId !== takeId
            )
              return;
            // The envelope already separates measurement from derivation; show
            // that separation rather than collapsing it into one percentage.
            area.innerHTML = `<h3>${c.heard}</h3><p lang="${language}">${esc(result.heard)}</p>${voiceEvidence(c, result.evaluation, language)}<p>${result.saved ? c.persisted : c.failedSave}</p>`;
          } else {
            const result = await api.transcribeSpeech(
              currentTake.blob,
              language,
            );
            if (
              !isAlive() ||
              version !== practiceVersion ||
              currentTakeId !== takeId
            )
              return;
            const heard = result.text || result.transcript || '';
            // What was spoken becomes the start of a draft, but never at the
            // cost of writing the learner already has. Whatever is stored is
            // what the response box shows, so the two cannot silently diverge.
            const draft = root.querySelector('#response');
            if (heard && !(draft?.value || memory.value.expressions[id])) {
              memory.write(id, heard);
              if (draft) draft.value = heard;
            }
            area.innerHTML = `<h3>${c.heard}</h3><p lang="${language}">${esc(heard)}</p><a class="outline" href="${link('expression', { id })}">${c.develop} ↗</a>`;
          }
        } catch {
          if (isAlive() && version === practiceVersion) {
            area.textContent = c.feedbackUnavailable;
            body.querySelector('[data-feedback-action]').disabled = false;
          }
        }
      }
    }
  }
  root
    .querySelectorAll('[data-intent]')
    .forEach(
      (button) => (button.onclick = () => openPractice(button.dataset.intent)),
    );
  bindComposer(root, ctx, item, () => model.current?.original_text || '');
  bindImages(root, c);
  // Follow arrives here as an intention too, and its whole point is that
  // nothing opens over the moment.
  if (deeperPractice.includes(practice)) openPractice(practice);
  return () => {
    disposed = true;
    practiceVersion++;
    recorder.cleanup();
    playerRoot.removeEventListener('orena:media-time', onClock);
    playerRoot.removeEventListener('orena:media-state', onMediaState);
    disconnectMediaPlayer(playerRoot);
  };
}
