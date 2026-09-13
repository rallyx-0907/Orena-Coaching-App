import { annotatedLine } from './annotated-line.js';
import {
  responseComposer,
  bindComposer,
  progressReporter,
  savedLanguageLink,
  hint,
} from './patterns.js';
import { esc, safeExternal, dialog, status, focusRegion, focusWork } from './html.js';
import { openUnderstanding, selectionWithin } from './understanding.js';
import { voiceEvidence } from './voice-evidence.js';
import { publishedReading } from '../content/reading-library.js';
import { mountVoiceResponse } from './voice-response.js';
import { link, deeperPractice } from '../product/intent.js';
import { encounter } from '../product/encounter.js';
import {
  dictationEvidence,
  recoverListeningEvidence,
} from '../product/evidence.js';
import { comprehensionSection, bindComprehension } from './comprehension.js';
import { contentFor } from '../content/texts.js';
import { readingText, readingSessionId, readable } from '../content/reading.js';
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
export function inspectPhrase(ctx, text, title, context, origin = null) {
  return openUnderstanding(ctx, {
    selection: text,
    context: context || text,
    title,
    origin,
  });
}

// Paragraph text is escaped, and the line breaks inside it are the ones the
// passage wrote.
const lines = (value) => esc(value).replace(/\n/g, '<br>');

function textEncounter(root, ctx, item) {
  const { c, language, memory } = ctx;
  let count = item.kind === 'conversation' ? 1 : item.paragraphs?.length || 1;
  const paragraphs = item.paragraphs || [item.text];
  memory.enter({ id: item.id, title: item.title, excerpt: paragraphs[0] });
  const paint = () => {
    root.innerHTML = `<div class="back-row"><a href="#/">← ${c.back}</a><button data-keep class="quiet" aria-pressed="${memory.value.kept.includes(item.id)}">${memory.value.kept.includes(item.id) ? c.saved : c.keep} ＋</button></div><header class="text-heading"><small>${origin(item, c)}</small><h1 lang="${language}">${esc(item.title)}</h1><p lang="${language}">${esc(item.subtitle || '')}</p></header><div class="text-encounter"><article class="passage ${item.kind === 'conversation' ? 'dialogue' : ''}" lang="${language}">${paragraphs
      .slice(0, count)
      .map((p) => `<p>${lines(p)}</p>`)
      .join(
        '',
      )}${count < paragraphs.length ? `<button class="outline" data-next>${c.nextLine} →</button>` : item.question ? `<h2>${esc(item.question)}</h2>` : ''}</article><aside class="language-margin"><div class="margin-art">${art(item)}</div><h2>${c.inspect}</h2>${(item.phrases || []).map((p, i) => `<details><summary lang="${language}">${esc(p.word)}</summary>${p.phonetic && ctx.profile.pinyin !== 'off' ? `<p class="pinyin">${esc(p.phonetic)}</p>` : ''}<p>${esc(preparedMeaning(p, language, ctx.support).text)}</p><blockquote lang="${language}">${esc(p.example)}</blockquote><button data-note="${i}">${c.savePhrase} ＋</button><p role="status"></p></details>`).join('')}<button class="outline" data-inspect>${c.phrase} ↗</button></aside></div>${comprehensionSection(c, item.questions, item.latest_attempt)}${responseComposer(ctx, item)}${item.rights ? `<details class="source"><summary>${esc(c.readingRights)}</summary><p>${esc(item.rights.edition)}</p><p>${esc(item.rights.changes)}</p></details>` : ''}${item.source ? `<details class="source"><summary>${c.rights}</summary>${item.source.creator ? `<p>${esc(item.source.creator)}</p>` : ''}${item.source.license ? `<p>${esc(item.source.license)}</p>` : ''}${safeExternal(item.source.provenance_url) ? `<a href="${esc(safeExternal(item.source.provenance_url))}" target="_blank" rel="noopener noreferrer">${c.original} ↗</a>` : ''}</details>` : ''}<p class="provenance">${item.origin === 'imported' ? c.ownText : item.rights ? c.publishedText : item.generation_mode ? c.readingProvenance : c.prepared}</p>`;
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
        origin: { id: item.id, where: item.title, why: 'from_reading' },
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
    const showEvidence = (fragment) => {
      const index = paragraphs.findIndex((part) => part.includes(fragment));
      if (index < 0) return '';
      passage
        .querySelectorAll('mark')
        .forEach((mark) => mark.replaceWith(mark.textContent));
      const target = passage.querySelectorAll('p')[index];
      if (target) {
        const [before, ...rest] = paragraphs[index].split(fragment);
        target.innerHTML = `${lines(before)}<mark>${esc(fragment)}</mark>${lines(rest.join(fragment))}`;
        target.scrollIntoView({ block: 'center' });
      }
      return paragraphs[index].slice(0, 2400);
    };
    bindComprehension(root, ctx, {
      sessionId: readingSessionId(item.id),
      questions: item.questions,
      onEvidence: showEvidence,
      // Evidence from a check belongs to the passage it was found in, not to
      // the check: a phrase kept here must lead back to the text.
      origin: { id: item.id, where: item.title, why: 'from_reading' },
    });
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
  if (id.startsWith('published:')) {
    const item = publishedReading(id, language);
    if (!item) throw Error(c.unavailable);
    textEncounter(root, ctx, item);
    return;
  }
  if (id.startsWith('reading:')) {
    const sessionId = readingSessionId(id);
    if (!sessionId) throw Error(c.unavailable);
    const payload = await api.readingSession(sessionId);
    const item = readingText(payload.found ? payload.session : null, language);
    if (!alive()) return;
    if (!item) throw Error(c.unavailable);
    textEncounter(root, ctx, item);
    return;
  }
  if (id.startsWith('story:') || id.startsWith('text:')) {
    const found = id.startsWith('story:')
      ? contentFor(language).find((x) => `story:${x.id}` === id)
      : memory.value.imports.find((x) => x.id === id);
    // A text the learner brought in is stored as one body of text; the
    // authored collection already has its paragraphs.
    const item =
      found &&
      readable({
        ...found,
        id,
        language,
        paragraphs:
          found.paragraphs || String(found.text || '').split(/\n\s*\n/),
      });
    if (!item) throw Error(c.unavailable);
    textEncounter(root, ctx, item);
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
  // Where this encounter actually begins and ends. A catalog excerpt is a
  // shorter thing than the asset it was cut from, and following an excerpt to
  // its end is still following something to its end.
  const startOfMedia = payload.catalog?.excerpt_start_ms || 0;
  const endOfMedia =
    payload.catalog?.excerpt_end_ms || payload.asset.duration_ms || 0;
  let reachedTheEnd = false;
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
  let voiceCleanup = () => {};
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
  root.innerHTML = `<div class="back-row"><a href="#/">← ${c.back}</a><small>${esc(origin(item, c))}</small><button class="quiet" data-keep aria-pressed="${memory.value.kept.includes(id)}">${memory.value.kept.includes(id) ? c.saved : c.keep} ＋</button></div><header class="encounter-heading"><div><div class="heading-with-hint"><small>${esc(c['topic_' + payload.catalog?.topic] || c.follow)} · ${duration((payload.catalog?.excerpt_end_ms || payload.asset.duration_ms) - (payload.catalog?.excerpt_start_ms || 0))}</small>${hint({ text: c.followNote })}</div><h1 lang="${language}">${esc(item.title)}</h1></div></header><div class="media-encounter"><section class="media-stage"><div class="player-wrap ${payload.playback.kind === 'audio' ? 'audio-player' : ''}">${payload.playback.kind === 'audio' ? audioIdentity(item, c) : ''}${mediaPlayer(payload.playback, item.title, { startMs: payload.catalog?.excerpt_start_ms || 0, endMs: payload.catalog?.excerpt_end_ms, poster: payload.catalog?.poster_url })}</div><div class="transport"><button data-play aria-label="${c.play}">▶</button><button data-replay>${c.replay} ↺</button><label><span class="sr-only">${c.speed}</span><select data-rate aria-label="${c.speed}">${[0.5, 0.75, 1, 1.25, 1.5, 2].map((v) => `<option value="${v}" ${v === 1 ? 'selected' : ''}>${v}×</option>`).join('')}</select></label></div><label class="seek-line"><span class="sr-only">${c.seek}</span><input data-seek type="range" min="${payload.catalog?.excerpt_start_ms || 0}" max="${payload.catalog?.excerpt_end_ms || payload.asset.duration_ms}" value="${model.current.start_ms}" step="100" aria-label="${c.seek}"><output data-time>0:00</output></label><div class="moment-actions"><span class="heading-with-hint">${esc(c.deeper)}${location.intent === 'follow' ? hint({ text: c.followOptional }) : ''}</span><button data-intent="dictation">${c.dictate} ↗</button><button data-intent="shadowing">${c.shadow} ↗</button><button data-intent="speaking">${c.speakingName} ↗</button><button data-inspect>${c.inspect} ＋</button></div><section class="reached-the-end" data-reached hidden><h2>${esc(c.reachedTheEnd)}</h2><p>${esc(c.reachedTheEndNote)}</p><div class="button-row"><button class="outline" data-again>${esc(c.hearItAgain)} ↺</button><button class="quiet" data-read-through>${esc(c.readItThrough)} ↗</button></div></section></section><section class="practice-space" hidden></section><aside class="transcript-panel"><div class="section-head"><h2>${c.transcript}</h2><label class="close-look"><input type="checkbox" data-close-look><span>${esc(c.closeLook)}</span></label></div><div class="follow-tools"><label class="meaning-toggle"><input type="checkbox" data-all-meaning><span>${esc(c.showAllMeaning)}</span></label></div><ol>${model.segments.map((s) => `<li><button data-segment="${esc(s.segment_id)}"><time>${duration(s.start_ms)}</time><span class="line-original" lang="${language}">${esc(s.original_text)}</span>${model.meaning(s.segment_id) ? `<span class="line-meaning" lang="${esc(ctx.support)}" hidden>${esc(model.meaning(s.segment_id))}</span>` : ''}</button></li>`).join('')}</ol><p class="meta" data-meaning-note hidden>${esc(c.allMeaningNote)}</p><section class="follow-moment" aria-label="${c.follow}"><small data-now></small><p class="spoken" lang="${language}"></p><p class="pinyin" data-pinyin></p><p class="meaning" lang="${ctx.support}"></p><button class="quiet" data-meaning hidden>${c.recoverMeaning} ↗</button><div class="close-look-guide" hidden><div class="word-legend" data-word-legend hidden><span data-role="noun">${esc(c.wordThings)}</span><span data-role="verb">${esc(c.wordActions)}</span><span data-role="detail">${esc(c.wordDetails)}</span></div><p class="meta" data-annotation-status role="status"></p><button class="quiet" data-retry-annotation hidden>${esc(c.retry)}</button></div></section></aside></div><details class="source"><summary>${c.rights}</summary><p>${esc(payload.catalog?.source?.creator || origin(item, c))}</p><p>${esc(payload.catalog?.source?.license || '')}</p><a href="${esc(safeExternal(payload.catalog?.source?.provenance_url || payload.asset.source_url))}" target="_blank" rel="noopener noreferrer">${c.original} ↗</a></details>${responseComposer(ctx, item)}`;
  const playerRoot = root.querySelector('.media-stage');
  const mediaStatus = document.createElement('p');
  mediaStatus.className = 'notice';
  mediaStatus.setAttribute('role', 'status');
  mediaStatus.hidden = true;
  playerRoot.querySelector('.player-wrap').after(mediaStatus);
  const onMediaState = (event) => {
    const state = event.detail.state;
    mediaStatus.hidden = !['blocked', 'error'].includes(state);
    if (state === 'blocked') mediaStatus.textContent = c.mediaBlocked;
    if (state === 'error') {
      mediaStatus.innerHTML = `${c.mediaFailed} <button data-retry-media>${c.retry}</button>`;
      mediaStatus.querySelector('[data-retry-media]').onclick = () =>
        ctx.go('encounter', { id, intent: practice });
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
  /* Looking closely at the line being spoken.

     The annotation endpoint has always returned per-token part of speech - and
     for Chinese a pinyin reading aid - computed locally, without a provider.
     Nothing consumed it. It runs on the current line only, when the learner
     asks: annotating six segments on arrival would spend six requests to
     colour text nobody is reading yet, and colouring every line at all times
     is a rainbow rather than a reading aid.

     Only the classes that carry meaning are tinted. Function words keep the
     ink they had, because a system a learner cannot hold in their head is
     decoration. */
  let closeLook = false;
  const annotated = new Map(), annotating = new Set();
  const annotateLine = async (segment) => {
    if (!segment || annotated.has(segment.segment_id) || annotating.has(segment.segment_id)) return;
    annotating.add(segment.segment_id);
    try {
      const result = await api.annotateMediaText({
        text: segment.original_text,
        source_language: language,
      });
      if (alive()) annotated.set(segment.segment_id, result);
    } catch {
      if (alive()) annotated.set(segment.segment_id, null);
    } finally {
      annotating.delete(segment.segment_id);
      if (alive() && closeLook && model.current?.segment_id === segment.segment_id)
        paintFollow(lastClockSegment === 'gap');
    }
  };
  /* Following and the whole conversation are one panel. The line being spoken
     is not a separate block above the list - whose height changed with every
     sentence and pushed the list up and down - but the list's own current
     entry, opened up where it sits: the line at reading size, its meaning, and
     the word guide. The panel keeps one height; only its list moves,
     and it scrolls on its own so the learner can read ahead. */
  function placeMoment(s) {
    const host = [...transcript.querySelectorAll('[data-segment]')].find(
      (x) => x.dataset.segment === s.segment_id,
    );
    const item = host?.closest('li');
    if (item && moment.parentElement !== item) item.append(moment);
    transcript
      .querySelectorAll('li')
      .forEach((li) => li.toggleAttribute('data-current', li === item));
    // The opened entry is the line; its compact row would say it twice.
    transcript
      .querySelectorAll('[data-segment]')
      .forEach((x) => (x.hidden = x === host && !moment.hidden));
  }
  function keepCurrentInView(behavior = 'smooth') {
    const list = transcript.querySelector('ol');
    const current = transcript.querySelector('li[data-current]');
    if (!current || transcript.hidden) return;
    // The line before it stays in sight as context only while the whole
    // opened entry still fits under it.
    const context = Math.max(
      0,
      Math.min(48, list.clientHeight - current.offsetHeight - 8),
    );
    list.scrollTo({
      top: Math.max(0, current.offsetTop - list.offsetTop - context),
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : behavior,
    });
  }
  function paintFollow(gap = false) {
    const s = model.current;
    if (!s) return;
    placeMoment(s);
    /* Between two spoken lines the entry stays where it was and says so; it
       does not blank the line the learner was just reading. */
    moment.dataset.gap = String(gap);
    moment.querySelector('[data-now]').textContent = gap
      ? c.pauseGap
      : `${duration(s.start_ms)} · ${c.current}`;
    followSpans = gap ? null : wordSpans(s);
    followWord = -1;
    if (gap) original.textContent = s.original_text;
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
    if (!gap && closeLook) void annotateLine(s);
    const closely = !gap && closeLook ? annotatedLine(s, annotated.get(s.segment_id), {
      pinyin: ctx.profile.pinyin !== 'off',
      labels: { noun:c.wordThings, verb:c.wordActions, detail:c.wordDetails },
    }) : null;
    if (closely) original.innerHTML = closely;
    original.dataset.closeLookState = closely ? 'on' : 'off';
    moment.querySelector('.close-look-guide').hidden = !closeLook || gap;
    moment.querySelector('[data-word-legend]').hidden = !closely;
    const pending = annotating.has(s.segment_id);
    moment.querySelector('[data-annotation-status]').textContent =
      closely ? c.closeLookHelp : pending ? c.closeLookLoading : c.closeLookUnavailable;
    moment.querySelector('[data-retry-annotation]').hidden = Boolean(closely) || pending;
    const translated = model.meaning();
    meaning.textContent =
      translated || (ctx.support === language ? c.sameLanguage : c.noMeaning);
    const pinyin = payload.catalog?.pinyin_by_segment?.[s.segment_id];
    moment.querySelector('[data-pinyin]').textContent =
      !gap && !closely?.includes('data-reading=') && ctx.profile.pinyin !== 'off'
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
  /* Understanding something should never cost the learner their place. A
     question asked while the voice runs pauses it, and says so, so the answer
     is read against a stopped moment rather than over the next three lines. */
  function holdTheVoice() {
    const playing =
      playerRoot.dataset.mediaClock === 'ready' &&
      !playButton.textContent.includes('▶');
    if (playing) togglePlayback(playerRoot, payload.playback);
    return playing;
  }
  root.querySelector('[data-inspect]').onclick = () => {
    const picked = selectionWithin(moment);
    const held = holdTheVoice();
    const sheet = inspectPhrase(
      ctx,
      picked ? picked.text : model.current.original_text,
      `${origin(item, c)} · ${item.title}`,
      model.current.original_text,
      { id, where: item.title, why: 'from_listening' },
    );
    if (held && sheet) {
      const note = document.createElement('p');
      note.className = 'meta';
      note.textContent = c.heldForYou;
      sheet.querySelector('.understanding-source')?.append(note);
    }
  };
  // Reading the whole thing is a way of understanding it. The meanings are the
  // ones the lesson already ships, each with the provenance the panel states.
  const meaningToggle = root.querySelector('[data-all-meaning]');
  const showAllMeaning = (on) => {
    meaningToggle.checked = on;
    transcript
      .querySelectorAll('.line-meaning')
      .forEach((node) => (node.hidden = !on));
    root.querySelector('[data-meaning-note]').hidden = !on;
  };
  meaningToggle.onchange = () => showAllMeaning(meaningToggle.checked);
  root.querySelector('[data-again]').onclick = () => {
    root.querySelector('[data-reached]').hidden = true;
    reachedTheEnd = false;
    seekPlayback(playerRoot, payload.playback, startOfMedia);
    togglePlayback(playerRoot, payload.playback);
  };
  root.querySelector('[data-read-through]').onclick = () => {
    showAllMeaning(true);
    focusRegion(transcript.querySelector('h2'));
  };
  const closeLookToggle = root.querySelector('input[data-close-look]');
  closeLookToggle.onchange = () => {
    closeLook = closeLookToggle.checked;
    // Pause to explore without replacing the focused word while it is read.
    const held = closeLook && holdTheVoice();
    paintFollow();
    if (held) status(c.heldForYou);
  };
  moment.querySelector('[data-retry-annotation]').onclick = () => {
    annotated.delete(model.current.segment_id);
    paintFollow();
  };
  /* A token is the smallest thing a learner can point at, so pointing at it
     opens the same explanation every other surface uses - with the line it
     came from as its context, which is what makes the answer about this
     sentence rather than a dictionary entry. */
  moment.addEventListener('click', (event) => {
    const token = event.target.closest('[data-token]');
    if (!token || !model.current) return;
    const held = holdTheVoice();
    const sheet = openUnderstanding(ctx, {
      selection: token.dataset.token,
      context: model.current.original_text,
      title: item.title,
      origin: { id, where: item.title, why: 'from_listening' },
    });
    if (held && sheet) {
      const note = document.createElement('p');
      note.className = 'meta';
      note.textContent = c.heldForYou;
      sheet.querySelector('.understanding-source')?.append(note);
    }
  });
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
        // The row that was pressed opens into the line itself; the learner's
        // place moves with it rather than falling back to the page, and the
        // opened entry is brought into the list's view.
        if (!moment.hidden) {
          focusRegion(moment);
          keepCurrentInView();
        }
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
    /* Following something to its end is the whole point of this intention, and
       until now nothing marked it: the voice simply stopped. This is not a
       score and opens no exercise - it says what happened and offers the two
       things a learner actually wants next, hearing it again or reading it
       through. It arms only once the player has genuinely settled at the end. */
    if (
      !reachedTheEnd &&
      !playing &&
      Number.isFinite(endOfMedia) &&
      endOfMedia > 0 &&
      event.detail.time_ms >= endOfMedia - 400
    ) {
      reachedTheEnd = true;
      const panel = root.querySelector('[data-reached]');
      if (panel) {
        panel.hidden = false;
        focusRegion(panel.querySelector('h2'));
      }
      remember();
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
      // A learner reading ahead in the list - pointer or focus inside it - is
      // not pulled back to the voice.
      if (s) {
        remember();
        if (
          !transcript.matches(':hover') &&
          !transcript.contains(document.activeElement)
        )
          keepCurrentInView();
      }
    }
  }
  playerRoot.addEventListener('orena:media-time', onClock);
  connectMediaPlayer(playerRoot, payload.playback);
  paintFollow();
  keepCurrentInView('instant');
  /* The follow panel and a practice panel fill the rest of the first screen,
     so they need to know where the encounter begins below its heading. */
  const encounterGrid = root.querySelector('.media-encounter');
  const placeFrame = () => {
    if (!encounterGrid.isConnected) return;
    encounterGrid.style.setProperty(
      '--encounter-top',
      `${Math.round(encounterGrid.getBoundingClientRect().top + window.scrollY)}px`,
    );
  };
  placeFrame();
  window.addEventListener('resize', placeFrame, { passive: true });
  document.fonts?.ready.then(() => isAlive() && placeFrame());
  function closePractice() {
    voiceCleanup();
    voiceCleanup = () => {};
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
    placeFrame();
    keepCurrentInView('instant');
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
    placeFrame();
    remember();
  }
  /* The answer to "compare" or "show the original" is the thing the learner
     just asked for, so it is brought into view rather than left below the
     hint. Wide, the practice panel is bounded to the frame and scrolls on its
     own: it moves only as far as the answer needs, keeping as much of the
     learner's attempt on screen as fits. Narrow, the page carries the work
     below a sticky source strip, and the answer is scrolled to. */
  function revealAnswer(answer) {
    if (!answer?.isConnected) return;
    // Wide, the answer arrives in the result region of a frame that already
    // fits; that region scrolls only if a very long line outgrows it.
    const panel = answer.closest('.dictation-result') || practiceRoot;
    // A scroll container is the wide composition; the page is never moved
    // there, only the region, and only if the answer does not already fit.
    if (getComputedStyle(panel).overflowY === 'visible') {
      answer.scrollIntoView({ block: 'nearest' });
      return;
    }
    const frame = panel.getBoundingClientRect();
    const box = answer.getBoundingClientRect();
    const below = box.bottom - frame.bottom + 16;
    if (below > 0)
      panel.scrollTop += Math.min(below, box.top - frame.top - 16);
  }
  async function openPractice(intent) {
    if (recording) return;
    voiceCleanup();
    voiceCleanup = () => {};
    practiceVersion++;
    const version = practiceVersion;
    practice = intent;
    recorder.discard();
    take = null;
    basePractice();
    const target = practiceTarget;
    /* Both ways out - back to Follow and on to the next line - sit in the
       panel's top row, so neither costs a row of the frame the work needs. */
    practiceRoot.innerHTML = `<div class="practice-top"><small>${c[intent + 'Name']}</small><div class="practice-nav"><button class="quiet" data-follow>← ${c.followBack}</button><button class="quiet" data-next-moment>${c.next} →</button></div></div><h2>${intent === 'dictation' ? c.hearFirst : intent === 'speaking' ? c.voiceResponse : c.shadowPrompt}</h2><div data-practice-body></div>`;
    practiceRoot.querySelector('[data-follow]').onclick = closePractice;
    /* Narrow screens put the work below a sticky strip of source, which is the
       right shape but starts out of sight. Opening a practice brings it to the
       learner instead of asking them to go looking for it; wide screens have it
       beside the media already and need no movement. */
    if (window.matchMedia('(max-width: 1079px)').matches) {
      focusWork();
      practiceRoot.scrollIntoView({
        block: 'start',
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
          ? 'auto'
          : 'smooth',
      });
    }
    focusRegion(practiceRoot.querySelector('h2'));
    const body = practiceRoot.querySelector('[data-practice-body]');
    const nextIndex =
      model.segments.findIndex((x) => x.segment_id === target.segment_id) + 1;
    const nextButton = practiceRoot.querySelector('[data-next-moment]');
    const exhausted = nextIndex >= model.segments.length;
    // On the last line the way on is the way back, which already sits beside
    // it; one control says it once.
    nextButton.hidden = exhausted;
    nextButton.onclick = () => {
      if (recording) return;
      closePractice();
      if (exhausted) return;
      model.select(model.segments[nextIndex].segment_id);
      openPractice(intent);
    };
    if (intent === 'dictation') {
      /* One frame, no scrolling: the shape of the line, the question with its
         replay beside it, the attempt, the actions, and a result region that
         takes the height left. The comparison replaces the shape of the line
         rather than stacking under it - both answer "what did I get right",
         and the comparison is the fuller answer. */
      body.innerHTML = `<section class="hint-line" data-hint-panel hidden></section><div class="dictation-ask"><label for="reconstruction">${c.dictatePrompt}</label><button type="button" class="quiet" data-listen>${c.replay} ↺</button></div><form id="dictationForm"><textarea id="reconstruction" lang="${language}" maxlength="2000" rows="2" required></textarea><div class="button-row dictation-actions"><button class="primary">${c.check}</button><div class="dictation-aids"><button type="button" data-hint>${c.hint}</button><button type="button" data-reveal>${c.reveal}</button></div></div></form><div class="dictation-result"><div class="comparison" aria-live="polite"></div><p data-evidence-status role="status"></p></div>`;
      body.querySelector('[data-listen]').onclick = playLine;
      /* The hint is a working aid, not an outcome: it lives for this visit
         only and never becomes evidence. Revealing the answer stays the
         separate, recorded act it already was. */
      let hintLevel = 1;
      const hintPanel = body.querySelector('[data-hint-panel]');
      const hintButton = body.querySelector('[data-hint]');
      const comparison = body.querySelector('.comparison');
      const paintHint = () => {
        const shape = dictationHint({
          expected: target.spoken_text || target.original_text,
          answer: body.querySelector('textarea').value,
          source_language: language,
          level: hintLevel,
        });
        // While a comparison is on screen it is the answer; the shape waits.
        hintPanel.hidden = comparison.childElementCount > 0;
        hintPanel.innerHTML = `<div class="hint-line__head"><small>${esc(c.hintTitle)}</small>${shape.anchors ? `<span class="meta">${shape.anchors}/${shape.total} ${esc(c.hintAnchors)}</span>` : ''}${shape.complete ? `<span class="meta">${esc(c.hintComplete)}</span>` : hint({ text: c.hintNote })}</div><p class="hint-slots" lang="${language}">${shape.slots.map((slot) => (slot.kind === 'structure' ? esc(slot.text) : `<span class="hint-word" data-kind="${slot.kind}"${slot.known ? ` data-known="${slot.known}"` : ''}>${[...slot.text].map((mark, index) => `<span class="hint-mark" data-state="${slot.kind === 'anchor' ? 'anchor' : slot.earned?.[index] ? 'known' : 'unknown'}">${esc(mark)}</span>`).join('')}</span>`)).join('')}</p>`;
        hintButton.textContent =
          hintLevel >= MAX_HINT_LEVEL ? c.hintMore : c.hint;
        hintButton.disabled = hintLevel >= MAX_HINT_LEVEL;
      };
      hintButton.onclick = () => {
        hintLevel = Math.min(MAX_HINT_LEVEL, hintLevel + 1);
        // Asking for a hint is going back to work on the line.
        comparison.innerHTML = '';
        paintHint();
      };
      const answer = body.querySelector('textarea'),
        key = `${payload.asset.asset_id}:${target.segment_id}`;
      answer.value = memory.value.answers[key] || '';
      answer.oninput = () => {
        memory.write(key, answer.value, 'answers');
        paintHint();
      };
      // The shape of the line is there from the moment the learner arrives,
      // and follows what they type. Nothing has to be asked for to begin.
      paintHint();
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
          report.failed(
            priorRead ? c.failedSave : c.priorProgressUnread,
            persist,
          );
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
            `<div class="comparison-head"><div class="heading-with-hint"><h3>${result.accuracy_percent}% ${c.match}</h3>${hint({ text: c.comparisonNote })}</div><div class="button-row"><button data-again>${c.tryAgain} ↺</button><button data-understand>${c.inspect} ↗</button></div></div><div class="diff" lang="${language}">${diff.map((x) => `<span class="${x.status}"><span class="sr-only">${esc(x.status === 'correct' ? c.correct : x.status === 'extra' ? c.extra : c.missing)}: </span>${x.status === 'wrong' ? `<del>${esc(x.actual)}</del> → ` : x.status === 'missing' ? '+ ' : x.status === 'extra' ? '− ' : ''}${esc(x.expected || x.actual)}</span>`).join('')}</div><p lang="${language}">${esc(target.original_text)}</p><p>${esc(model.meaning(target.segment_id) || c.noMeaning)}</p>`;
          hintPanel.hidden = true;
          revealAnswer(body.querySelector('.comparison'));
          body.querySelector('[data-understand]').onclick = () =>
            inspectPhrase(
              ctx,
              target.original_text,
              item.title,
              target.original_text,
              { id, where: item.title, why: 'from_listening' },
            );
          body.querySelector('[data-again]').onclick = () => {
            body.querySelector('.comparison').innerHTML = '';
            paintHint();
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
        hintPanel.hidden = true;
        revealAnswer(body.querySelector('.comparison'));
        persist();
      };
      playLine();
    } else if (intent === 'speaking') {
      voiceCleanup = mountVoiceResponse(
        body,
        { ...ctx, alive: () => isAlive() && version === practiceVersion },
        {
          id,
          title: item.title,
          prompt: target.original_text,
          assetId: payload.asset.asset_id,
          segmentId: target.segment_id,
          onRecording: (active) => {
            recording = active;
            setRecordingLock(active);
          },
        },
      );
    } else {
      // Where the recording lives sits beside the control as a hint, as it
      // does in the voice response; the guide is the instruction and stays.
      body.innerHTML = `<blockquote lang="${language}">${esc(target.original_text)}</blockquote><p class="practice-meaning">${esc(model.meaning(target.segment_id) || '')}</p><p class="practice-guide">${intent === 'shadowing' ? c.shadowGuide : c.speakingGuide}</p><div class="button-row"><button class="outline" data-listen>${c.replay} ↺</button><button class="primary" data-record>● ${c.record}</button>${hint({ text: c.localAudio })}</div><p role="status" data-record-status></p><div data-take></div><div data-feedback></div>`;
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
    voiceCleanup();
    practiceVersion++;
    recorder.cleanup();
    playerRoot.removeEventListener('orena:media-time', onClock);
    playerRoot.removeEventListener('orena:media-state', onMediaState);
    window.removeEventListener('resize', placeFrame);
    disconnectMediaPlayer(playerRoot);
  };
}
