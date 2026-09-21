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
import { mountReader } from './reader.js';
import { mountLexicalLayer } from './lexical.js';
import { icon } from './phosphor.js';
import { referenceCopy } from './reference.js';
import { pronunciationReportHtml } from './pronunciation-report.js';
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
  holdSegment,
  releaseSegment,
} from '../capabilities/media-player.js';
import { learningToolbar, bindLearningToolbar } from './learning-toolbar.js';
import { createLocalAudioRecorder } from '../capabilities/audio-recorder.js';
import {
  linePieces,
  activeWordIndex,
  wordSpans,
} from '../capabilities/word-timeline.js';
import { evaluateVoice } from '../capabilities/voice-feedback.js';
import {
  acquireMedia,
  translationRequest,
} from '../capabilities/media-acquisition.js';
import { origin, duration, bindImages, art } from './content.js';
import { dictationHintView, dictationResult, HINT_LEVELS, readingsFor, readingLineFor } from '../capabilities/dictation-result.js';
import { screenHtml, shapeHtml, hintLevelHtml, resultHtml } from './dictation-screen.js';
import { openLineSheet } from './line-sheet.js';
import { symbol } from './symbols.js';

/* How to read the follow panel - the words of the line being spoken, the
   meaning of every line - as two small switches on its title row. Each is a
   real checkbox named by its words; the symbol is what shows, and on a narrow
   screen the words appear on hover, focus or tap. */
const followToggle = (name, attribute, icon, label) =>
  `<label class="follow-toggle ${name}" data-tip="${esc(label)}"><input type="checkbox" ${attribute}><span class="follow-toggle__mark">${symbol(icon, 18)}</span><span class="follow-toggle__label">${esc(label)}</span></label>`;

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

/* Reading is a reader. The text is the page and nothing is interleaved with
   it; learning tools appear only for what the learner selects (`reader.js`).
   What follows reading - prepared language notes, an optional comprehension
   check, a response, and where the text came from - comes after the text. */
function textEncounter(root, ctx, item, book = null) {
  const { c, language, memory } = ctx;
  const paragraphs = item.paragraphs || [item.text];
  /* A chapter is a chapter of a book. Which book, and which chapter of how
     many, is what makes Continue continuity rather than a list of rows - and
     it is known right here, where the book was loaded, and nowhere later. */
  const chapterIndex = book?.chapterId
    ? (book.chapters || []).findIndex((chapter) => chapter.id === book.chapterId)
    : -1;
  memory.enter({
    id: item.id,
    title: item.title,
    excerpt: paragraphs[0],
    context: book?.title || '',
    place: chapterIndex >= 0
      ? { index: chapterIndex + 1, total: book.chapters.length }
      : null,
  });
  const title = `${origin(item, c)} · ${item.title}`;
  const from = { id: item.id, where: item.title, why: 'from_reading' };
  const notes = (item.phrases || []).length
    ? `<details class="reader-notes"><summary>${esc(c.readerNotes)}</summary>${item.phrases.map((p, i) => `<div class="reader-note"><p class="reader-note__word" lang="${language}">${esc(p.word)}</p>${p.phonetic && ctx.profile.pinyin !== 'off' ? `<p class="pinyin">${esc(p.phonetic)}</p>` : ''}<p lang="${esc(ctx.support)}">${esc(preparedMeaning(p, language, ctx.support).text)}</p><blockquote lang="${language}">${esc(p.example)}</blockquote><button class="quiet" data-note="${i}">${c.savePhrase} ＋</button><p role="status"></p></div>`).join('')}</details>`
    : '';
  root.innerHTML = `<div data-reader-host></div><div class="reader-after">${notes}${comprehensionSection(c, item.questions, item.latest_attempt)}${responseComposer(ctx, item)}${item.rights ? `<details class="source"><summary>${esc(c.readingRights)}</summary><p>${esc(item.rights.edition)}</p><p>${esc(item.rights.changes)}</p></details>` : ''}${item.source ? `<details class="source"><summary>${c.rights}</summary>${item.source.creator ? `<p>${esc(item.source.creator)}</p>` : ''}${item.source.license ? `<p>${esc(item.source.license)}</p>` : ''}${safeExternal(item.source.provenance_url) ? `<a href="${esc(safeExternal(item.source.provenance_url))}" target="_blank" rel="noopener noreferrer">${c.original} ↗</a>` : ''}</details>` : ''}<p class="provenance">${item.origin === 'imported' ? c.ownText : item.rights ? c.publishedText : item.generation_mode ? c.readingProvenance : c.prepared}</p></div>`;

  const reader = mountReader(root.querySelector('[data-reader-host]'), ctx, {
    item,
    blocks: item.blocks,
    book,
    progressive: item.kind === 'conversation',
    title,
    origin: from,
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
                focus_note: title,
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
  bindComprehension(root, ctx, {
    sessionId: readingSessionId(item.id),
    questions: item.questions,
    onEvidence: (fragment) => reader.showEvidence(fragment),
    /* Which paragraph settles the question, counted in the text the learner
       just read - the approved answer panel names it. Unfound evidence says
       "from the text" rather than a number nobody can check. */
    placeOfEvidence: (fragment) => {
      const needle = String(fragment || '').trim();
      if (!needle) return null;
      const paragraphs = (item.blocks || []).length
        ? (item.blocks || [])
            .filter((block) => block.type === 'paragraph')
            .map((block) => String(block.text || ''))
        : (item.paragraphs || []).map((part) => String(part || ''));
      const found = paragraphs.findIndex((text) => text.includes(needle));
      return found >= 0 ? found : null;
    },
    // Evidence from a check belongs to the passage it was found in, not to
    // the check: a phrase kept here must lead back to the text.
    origin: from,
  });
  bindComposer(root, ctx, item);
  bindImages(root, c);
  return () => reader.destroy();
}
function waitingMedia(root, ctx, payload) {
  const { c, language, memory } = ctx;
  const id = ctx.location.id,
    title = payload.asset.title || c.pendingMedia;
  // A catalog lesson whose transcript is still missing reaches this same
  // waiting room, and it must not be described as something the learner
  // brought in. addMedia already ignores anything that is not an import.
  const imported = id.startsWith('url:') || id.startsWith('upload:');
  memory.enter({ id, title, source_url: payload.asset.source_url });
  memory.addMedia({
    id,
    title,
    kind: payload.playback.kind,
    duration_ms: payload.asset.duration_ms,
    thumbnail_url: payload.asset.thumbnail_url,
    provider: payload.playback.provider,
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
    return textEncounter(root, ctx, item);
  }
  if (id.startsWith('reading:')) {
    const sessionId = readingSessionId(id);
    if (!sessionId) throw Error(c.unavailable);
    const payload = await api.readingSession(sessionId);
    const item = readingText(payload.found ? payload.session : null, language);
    if (!alive()) return;
    if (!item) throw Error(c.unavailable);
    return textEncounter(root, ctx, item);
  }
  if (id.startsWith('book:')) {
    // `book:<bookId>/<chapterId>` - a Shared Reading Library chapter. Same
    // gate every other source ends at: the API's paragraphs go through
    // readable() and the same textEncounter() every reading source uses,
    // never a second reader.
    const [bookId, chapterId] = id.slice(5).split('/');
    // The book is what gives a chapter its place: contents, previous and next,
    // and where the book came from. A chapter still reads without it.
    const [chapter, bookDetail] =
      bookId && chapterId
        ? await Promise.all([
            api.libraryBookChapter(bookId, chapterId),
            api.libraryBook(bookId).catch(() => null),
          ])
        : [null, null];
    if (!alive()) return;
    const item =
      chapter &&
      readable({
        id,
        title: chapter.title,
        language: chapter.language,
        paragraphs: chapter.paragraphs,
        source: chapter.author ? { creator: chapter.author } : undefined,
      });
    if (!item) throw Error(c.unavailable);
    return textEncounter(
      root,
      ctx,
      { ...item, blocks: chapter.blocks },
      {
        id: bookId,
        title: chapter.book_title || bookDetail?.title || '',
        chapterId,
        chapters: bookDetail?.chapters || [],
        provenance: bookDetail?.provenance || null,
      },
    );
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
    return textEncounter(root, ctx, item);
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
        : id.startsWith('upload:')
          ? // A file the learner uploaded is Orena's own stored content, so it
            // is resolved by identity instead of being re-acquired from a
            // provider: there is no provider, and there may be no transcript.
            await api.mediaMy(id.slice(7))
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
      origin: /^(url|upload):/.test(id) ? 'imported' : 'curated',
      kind: payload.playback.kind,
    };
  if (/^(url|upload):/.test(id))
    memory.addMedia({
      id,
      title: item.title,
      kind: item.kind,
      duration_ms: payload.asset.duration_ms,
      thumbnail_url: payload.asset.thumbnail_url,
      provider: payload.playback.provider,
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
  /* Where the learner got to, in the one shared continuation shape.

     A voice has a place inside a whole exactly as a chapter does: the line
     being followed, of how many. That is what Continue, Book detail and
     Discover already read (`continuationPlace`), so Listening feeds the same
     field rather than keeping a progress store of its own. The segment id it
     already stored stays, because resuming needs the line and not the count. */
  const remember = () => {
    const index = model.segments.findIndex(
      (segment) => segment.segment_id === model.current?.segment_id,
    );
    memory.enter({
      id,
      title: item.title,
      segment: model.current?.segment_id,
      intent: practice,
      source_url: payload.asset.source_url,
      excerpt: model.current?.original_text,
      context: payload.catalog?.source_label || payload.catalog?.source?.creator || '',
      place: index >= 0 ? { index: index + 1, total: model.segments.length } : null,
    });
  };
  remember();
  /* One shape for every line, and the same shape when it is the line being
     spoken.

     The row used to be a compact button that was hidden the instant the voice
     reached it, and replaced in place by a block carrying the sentence again,
     its meaning, its reading, a status line and three controls. Playback then
     rewrote the list's geometry every few seconds: it grew where the voice
     was and collapsed behind it, the lines a learner was reading slid, and on
     a phone the whole panel jumped. The information was right; the structural
     change was the defect (DESIGN_CONTRACT: active state before structural
     expansion).

     So every row carries every slot it will ever need - when it was said, the
     line, its reading, its meaning - and becoming the current line changes
     only what those slots say and how the row is drawn. Which slots are shown
     at all is a panel-wide display preference, so it is true of every row at
     once and a change of line never changes a height. */
  const transcriptRow = (s) => {
    const reading = payload.catalog?.pinyin_by_segment?.[s.segment_id];
    return `<li><button data-segment="${esc(s.segment_id)}"><span class="line-when"><time>${duration(s.start_ms)}</time><span class="line-state" data-line-state></span></span><span class="line-original" lang="${language}">${esc(s.original_text)}</span><span class="line-pinyin" data-line-pinyin lang="${language}">${esc(typeof reading === 'string' ? reading : '')}</span><span class="line-meaning" lang="${esc(ctx.support)}">${esc(model.meaning(s.segment_id) || '')}</span></button><div class="line-pick" data-line-pick><button type="button" class="line-pick__go" data-seek-here="${esc(s.segment_id)}">${icon('play', { size: 15, filled: true })}<span>${esc((referenceCopy[ctx.ui] || referenceCopy.en).listenSeekHere)}</span></button><button type="button" class="line-pick__loop" data-loop-line="${esc(s.segment_id)}">${icon('arrow-counter-clockwise', { size: 15 })}<span>${esc((referenceCopy[ctx.ui] || referenceCopy.en).listenLoopLine)}</span></button></div></li>`;
  };
  /* The bar that owns the actions of the current line (`ui/learning-toolbar.js`).
     Icon-first, because these are the reusable learner actions - hear it
     again, work on it, show what it means, show how it reads, colour the word
     classes - and the support language names each one in its tooltip and to
     assistive technology. Pinyin is not a quiet control here; it is absent
     when the learning language has no reading to show. */
  const lineActions = [
    { name: 'autoscroll', kind: 'toggle', label: (referenceCopy[ctx.ui] || referenceCopy.en).listenAutoScroll, chip: (referenceCopy[ctx.ui] || referenceCopy.en).listenAutoScroll },
    language === 'zh'
      ? { name: 'pinyin', icon: 'reading', kind: 'toggle', label: c.stagePinyin, chip: (referenceCopy[ctx.ui] || referenceCopy.en).readerPinyin }
      : null,
    { name: 'meaning', icon: 'meaning', kind: 'toggle', label: c.stageMeaning, chip: String(ctx.support || '').toUpperCase() },
    { name: 'deep', icon: 'more', label: (referenceCopy[ctx.ui] || referenceCopy.en).listenMore },
  ];
  /* The approved listening workspace (D-059 Phase 7, Screens part 1 section
     04): one card, two panes. The artwork, what this is, the rail and the
     controls on the left; the synced transcript on the right, with the reading
     and support layers the design draws as chips. Comprehension for listening
     has no items yet, so its control keeps its place and says so (GAP-025). */
  const r = referenceCopy[ctx.ui] || referenceCopy.en;
  const totalMs = (payload.catalog?.excerpt_end_ms || payload.asset.duration_ms) - (payload.catalog?.excerpt_start_ms || 0);
  // What the baseline's identity line says: how hard, what kind, how long.
  const meta = [
    esc(payload.catalog?.level || ''),
    esc(r['libraryKind_' + payload.catalog?.content_type] || c['topic_' + payload.catalog?.topic] || ''),
    esc(duration(totalMs)),
  ].filter(Boolean).join(' · ');
  const kept = memory.value.kept.includes(id);
  const rateChip = (value) =>
    `<button type="button" class="listen-rate" role="radio" aria-checked="${value === 1}" data-rate-value="${value}">${value}×</button>`;
  root.innerHTML = `<button type="button" class="icon-button listen-back" data-listen-back aria-label="${esc(r.listenBack)}">${icon('caret-right', { size: 20, className: 'is-flipped' })}</button><div class="listen-workspace" data-mode="${esc(location.intent || 'follow')}"><section class="listen-stage media-stage"><div class="listen-art player-wrap ${payload.playback.kind === 'audio' ? 'audio-player' : ''}">${payload.playback.kind === 'audio' ? `<div class="listen-poster">${art(item)}</div>` : ''}${mediaPlayer(payload.playback, item.title, { startMs: payload.catalog?.excerpt_start_ms || 0, endMs: payload.catalog?.excerpt_end_ms, poster: payload.catalog?.poster_url, controls: false })}</div><div class="listen-identity"><h1 lang="${language}">${esc(item.title)}</h1><p class="ds-data listen-meta">${meta}</p></div><div class="listen-transport"><label class="seek-line listen-seek"><span class="sr-only">${esc(c.seek)}</span><output class="ds-data" data-time>0:00</output><input data-seek type="range" min="${payload.catalog?.excerpt_start_ms || 0}" max="${payload.catalog?.excerpt_end_ms || payload.asset.duration_ms}" value="${model.current.start_ms}" step="100" aria-label="${esc(c.seek)}"><span class="ds-data listen-seek__total">${esc(duration(totalMs))}</span></label><div class="listen-controls"><button type="button" class="icon-button" data-step="prev" aria-label="${esc(r.listenPrevLine)}">${icon('skip-back', { size: 19 })}</button><button type="button" class="listen-play" data-play aria-label="${esc(c.play)}">${icon('play', { size: 24, filled: true })}</button><button type="button" class="icon-button" data-step="next" aria-label="${esc(r.listenNextLine)}">${icon('skip-forward', { size: 19 })}</button><button type="button" class="icon-button" data-replay aria-label="${esc(c.replay)}">${icon('arrow-counter-clockwise', { size: 19 })}</button><div class="listen-rates" role="radiogroup" aria-label="${esc(c.speed)}">${[0.75, 1, 1.25].map(rateChip).join('')}</div></div></div><div class="listen-actions"><button type="button" class="outline listen-quiz" disabled title="${esc(r.bookSoon)}" aria-label="${esc(`${r.listenQuiz} — ${r.bookSoon}`)}">${icon('info', { size: 17 })}<span>${esc(r.listenQuiz)}</span></button><button type="button" class="icon-button" data-keep aria-pressed="${kept}" aria-label="${esc(kept ? c.saved : c.keep)}">${icon('bookmark-simple', { size: 19, filled: kept })}</button></div><div class="state-panel reached-the-end" data-reached hidden>${icon('check-circle', { size: 20, filled: true })}<div><strong>${esc(c.reachedTheEnd)}</strong><p>${esc(c.reachedTheEndNote)}</p></div><div class="button-row"><button type="button" class="outline" data-again>${esc(c.hearItAgain)}</button><button type="button" class="quiet" data-read-through>${esc(c.readItThrough)} ↗</button></div></div></section><section class="practice-space" hidden></section><aside class="transcript-panel" data-show-meaning="off" data-show-reading="off"><div class="transcript-panel__head"><span class="ds-label">${esc(r.listenTranscript)}</span><span class="section-head__tools">${learningToolbar(lineActions, { label: c.lineActionsLabel })}</span></div><p class="transcript-note" data-line-note hidden><span role="status" data-line-note-text></span><button class="quiet" data-retry-annotation hidden>${esc(c.retry)}</button><button class="quiet" data-meaning hidden>${esc(c.recoverMeaning)} ↗</button></p><button class="quiet" data-back-to-current hidden>${esc(c.stageBackToCurrent)}</button><ol>${model.segments.map(transcriptRow).join('')}</ol><p class="transcript-hint">${icon('hand-tap', { size: 16 })}<span>${esc(r.readerTapWord)}</span></p></aside></div><details class="source"><summary>${c.rights}</summary><p>${esc(payload.catalog?.source?.creator || origin(item, c))}</p><p>${esc(payload.catalog?.source?.license || '')}</p><a href="${esc(safeExternal(payload.catalog?.source?.provenance_url || payload.asset.source_url))}" target="_blank" rel="noopener noreferrer">${c.original} ↗</a></details><div data-response-host>${responseComposer(ctx, item)}</div>`;
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
  const transcript = root.querySelector('.transcript-panel');
  /* There is no separate "current line" element any more: the current line is
     a row of the transcript, and everything that used to live in a panel of
     its own is either a slot that row already has or a note that belongs to
     the workspace rather than to a sentence. */
  const lineNote = root.querySelector('[data-line-note]');
  const lineNoteText = root.querySelector('[data-line-note-text]');
  const rowFor = (segmentId) =>
    [...transcript.querySelectorAll('[data-segment]')].find(
      (x) => x.dataset.segment === segmentId,
    ) || null;
  const currentRow = () => rowFor(model.current?.segment_id);
  const slot = (name) => currentRow()?.querySelector(name) || null;
  /* The same lexical layer Reading uses (`ui/lexical.js`), over the transcript.
     A tapped word in a spoken line answers exactly as a tapped word in a
     chapter does - one lookup, one panel, one save, one explanation - because
     it is the same implementation. The transcript only says where its text is:
     a line carrying `data-segment`, and the canonical text that line was
     rendered from. */
  /* Which line a tap belongs to. A transcript row is a seek control, so the
     compact rows keep meaning "take me there"; the line being followed is
     opened up in place, outside that button, at reading size - and that is the
     line a learner taps a word in. One tap, one meaning, no ambiguity: tap a
     row to go there, tap a word in the line you are on to ask about it. */
  const segmentIdOf = (unit) =>
    unit?.closest?.('li')?.querySelector('[data-segment]')?.dataset.segment || '';
  /* The line a learner is working on is askable wherever it is on screen: in
     the transcript, and in the practice panel, where it is the phrase being
     shadowed or spoken. Same layer, same answers - a word in a line the learner
     is repeating is the word they are most likely to ask about. */
  const lineOf = (unit) =>
    unit?.dataset?.practiceSegment || segmentIdOf(unit) || '';
  let heldByTheSheet = false;
  const lexical = mountLexicalLayer({
    surface: root,
    ctx,
    title: item.title,
    origin: { id, where: item.title, why: 'from_listening' },
    alive: isAlive,
    /* Asking about a word stops the voice where it is, and closing the sheet
       carries on from there (the baseline's Quick Sheet, D-066). */
    onPanel: (open) => {
      if (open) heldByTheSheet = holdTheVoice() || heldByTheSheet;
      else if (heldByTheSheet) {
        heldByTheSheet = false;
        togglePlayback(playerRoot, payload.playback);
      }
    },
    units: {
      root: () => root.querySelector('.listen-workspace'),
      unitOf: (node) => node?.closest?.('.line-original, [data-practice-line]') || null,
      textOf: (unit) =>
        model.segments.find((segment) => segment.segment_id === lineOf(unit))?.original_text ||
        unit.textContent ||
        '',
      keyOf: (unit) => `segment:${lineOf(unit)}`,
    },
  });
  /* Tap a row to go there; tap a word in the line you are already on to ask
     about it. The row is a seek control, so the two can share it without
     ambiguity: on the current line seeking is a no-op, and the word is what
     the learner meant. A line the voice has not reached keeps the plain
     meaning of its row. */
  root.addEventListener('click', (event) => {
    const practised = event.target.closest('[data-practice-line]');
    if (practised) return lexical.tapWord(event);
    const line = event.target.closest('.line-original');
    if (!line || line.closest('li')?.hasAttribute('data-current') !== true) return;
    lexical.tapWord(event);
  });
  const original = () => slot('.line-original');
  const meaning = () => slot('.line-meaning');
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
  // Mirrors the stage's word-colour toggle, read by paintFollow.
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
      if (
        alive() &&
        (closeLook || showPinyin()) &&
        model.current?.segment_id === segment.segment_id
      )
        paintFollow(lastClockSegment === 'gap');
    }
  };
  /* Following and the whole conversation are one panel, and the line being
     spoken is one of its rows. Not a block above the list, whose height
     changed with every sentence; and no longer a row that swaps its compact
     form for a taller opened one either. The panel keeps one height, every
     row keeps its own, and only the list scrolls - so a learner can read
     ahead, and the geometry under their eyes holds still while the voice
     moves (DESIGN_CONTRACT: active state before structural expansion). */
  function markCurrent(s) {
    const row = rowFor(s.segment_id);
    const item = row?.closest('li') || null;
    transcript
      .querySelectorAll('li')
      .forEach((li) => li.toggleAttribute('data-current', li === item));
    // The line the voice reached is no longer one the learner picked; the row's own actions
    // are shown by the attribute alone, so nothing here moves or hides a node.
    item?.removeAttribute('data-picked');
    return row;
  }
  /* A row that stops being the current line gives back exactly what being the
     current line added: word spans, colours, a lazily fetched reading, the
     state it was in. Its slots stay; only their contents return to plain. */
  function plainRow(row) {
    if (!row) return;
    const segment = model.segments.find((x) => x.segment_id === row.dataset.segment);
    const line = row.querySelector('.line-original');
    if (segment && line) line.textContent = segment.original_text;
    line?.removeAttribute('data-close-look-state');
    const state = row.querySelector('[data-line-state]');
    if (state) state.textContent = '';
  }
  /* A learner reading ahead in the list is not pulled back to the voice - but
     only while they are actually moving through it. Hover and focus used to
     count, and a tap on a switch or a line left both behind on a phone, so the
     list stopped following for good and the line being spoken scrolled out of
     sight. A swipe, a wheel, a drag of the scrollbar or a key in the list
     holds it for a few seconds; tabbing along the lines holds it while there. */
  let readingAheadUntil = 0;
  const holdList = () => {
    readingAheadUntil = performance.now() + 4000;
  };
  {
    const list = transcript.querySelector('ol');
    list.addEventListener('wheel', holdList, { passive: true });
    list.addEventListener('touchmove', holdList, { passive: true });
    list.addEventListener('keydown', holdList);
    list.addEventListener('pointerdown', (event) => {
      if (event.target === list) holdList();
    });
  }
  const readingAhead = () =>
    performance.now() < readingAheadUntil ||
    Boolean(document.activeElement?.matches?.('[data-segment]:focus-visible'));
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
  /* Only one row is ever the painted one, so the row the voice has left is
     handed back its plain text before the new one is dressed. */
  let paintedRow = null;
  function paintFollow(gap = false) {
    const s = model.current;
    if (!s) return;
    const row = markCurrent(s);
    if (paintedRow && paintedRow !== row) plainRow(paintedRow);
    paintedRow = row;
    if (!row) return;
    const line = row.querySelector('.line-original');
    /* Between two spoken lines the current line stays where it is and says so;
       it does not blank the line the learner was just reading. */
    transcript.dataset.gap = String(gap);
    row.querySelector('[data-line-state]').textContent = gap
      ? ` · ${c.pauseGap}`
      : ` · ${c.lineNow}`;
    followSpans = gap ? null : wordSpans(s);
    followWord = -1;
    if (gap) line.textContent = s.original_text;
    else if (followSpans) {
      const pieces = linePieces(s);
      line.innerHTML = pieces
        .map((piece) =>
          piece.index < 0
            ? esc(piece.text)
            : `<span class="word" data-word="${piece.index}">${esc(piece.text)}</span>`,
        )
        .join('');
    } else line.textContent = s.original_text;
    if (!gap && closeLook) void annotateLine(s);
    /* Word classes as colour, and nothing else: the reading stays in the row's
       own slot rather than being stacked above each character inside the line.
       Set over the characters it grew the line by about fourteen pixels the
       moment the voice arrived, on rows whose height is the one thing this
       panel promises not to change - and it said the reading twice, once in
       the line and once in the slot that was already reserving room for it. */
    const closely = !gap && closeLook ? annotatedLine(s, annotated.get(s.segment_id), {
      pinyin: false,
      labels: { noun:c.wordThings, verb:c.wordActions, detail:c.wordDetails },
    }) : null;
    if (closely) line.innerHTML = closely;
    line.dataset.closeLookState = closely ? 'on' : 'off';
    /* The legend is a key, not content: it is shown once, from its own control,
       and never repeated under the line it explains. Only a real failure is
       worth a note, and the note belongs to the workspace rather than to the
       sentence - a row that grows a status line is a row that moves the list. */
    const pending = annotating.has(s.segment_id);
    const trouble = closeLook && !gap && !closely;
    const translated = model.meaning();
    const lostMeaning = !gap && !translated && ctx.support !== language;
    lineNoteText.textContent = trouble
      ? pending
        ? c.closeLookLoading
        : c.closeLookUnavailable
      : lostMeaning
        ? c.noMeaning
        : '';
    lineNote.querySelector('[data-retry-annotation]').hidden = !trouble || pending;
    lineNote.querySelector('[data-meaning]').hidden = !lostMeaning;
    lineNote.hidden = !trouble && !lostMeaning;
    const meaningSlot = row.querySelector('.line-meaning');
    if (meaningSlot && translated) meaningSlot.textContent = translated;
    /* Pinyin for the line. The lesson's own reading is used when it ships one;
       otherwise the shared tagger already knows how these words are read - the
       same local, non-AI annotation the word colours use - so the reading is
       composed from it rather than left blank. Nothing is invented: a line the
       tagger cannot read shows no pinyin at all. The row's slot is there in
       every case, and the panel reserves its height while readings are shown,
       so a reading arriving late never moves the list. */
    const readingSlot = row.querySelector('[data-line-pinyin]');
    const catalogPinyin = payload.catalog?.pinyin_by_segment?.[s.segment_id];
    let reading = typeof catalogPinyin === 'string' ? catalogPinyin : '';
    if (!gap && showPinyin() && !reading) {
      void annotateLine(s);
      reading = (annotated.get(s.segment_id)?.annotations || [])
        .map((token) => token?.pronunciation || '')
        .filter(Boolean)
        .join(' ');
    }
    if (readingSlot) readingSlot.textContent = reading;
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
  /* On a narrow screen, starting the voice brings the follow view together:
     the voice under the header and the panel filling the rest of the screen,
     rather than the panel starting below the fold. */
  function bringFollowIntoView() {
    if (practice || !window.matchMedia('(max-width: 800px)').matches) return;
    const box = transcript.getBoundingClientRect();
    if (box.top >= 0 && box.bottom <= window.innerHeight + 1) return;
    focusWork();
    root.querySelector('.listen-workspace').scrollIntoView({
      block: 'start',
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'auto'
        : 'smooth',
    });
  }
  root.querySelector('[data-play]').onclick = () => {
    togglePlayback(playerRoot, payload.playback);
    bringFollowIntoView();
  };
  root.querySelector('[data-replay]').onclick = playLine;
  /* Speed is the design's row of chips: one is chosen, the others are not. */
  const rateChips = [...root.querySelectorAll('[data-rate-value]')];
  const chooseRate = (chip) => {
    rate = Number(chip.dataset.rateValue);
    setPlaybackRate(playerRoot, payload.playback, rate);
    rateChips.forEach((other) => other.setAttribute('aria-checked', String(other === chip)));
  };
  rateChips.forEach((chip, index) => {
    chip.onclick = () => {
      /* A phone shows the chosen speed alone, so tapping it takes the next one;
         a desk shows all three and a tap chooses. */
      const alone = chip.getAttribute('aria-checked') === 'true' && chip.offsetParent !== null
        && rateChips.filter((other) => other.offsetParent !== null).length === 1;
      chooseRate(alone ? rateChips[(index + 1) % rateChips.length] : chip);
    };
  });
  /* Skip is a line, not a number of seconds: a synced transcript moves by what
     was said. */
  root.querySelectorAll('[data-step]').forEach((button) => {
    button.onclick = () => {
      const segments = model.segments;
      const at = segments.findIndex((segment) => segment.segment_id === model.current?.segment_id);
      const next = segments[Math.max(0, Math.min(segments.length - 1, (at < 0 ? 0 : at) + (button.dataset.step === 'next' ? 1 : -1)))];
      if (!next) return;
      model.select(next.segment_id);
      replaySegment(playerRoot, payload.playback, next.start_ms, null, rate);
    };
  });
  root.querySelector('[data-listen-back]').onclick = () => {
    if (history.length > 1) history.back();
    else location.hash = link('practice', { intent: 'follow' });
  };
  root.querySelector('[data-keep]').onclick = (event) => {
    memory.keep(id);
    const nowKept = memory.value.kept.includes(id);
    event.currentTarget.setAttribute('aria-pressed', String(nowKept));
    event.currentTarget.setAttribute('aria-label', nowKept ? c.saved : c.keep);
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
  function inspectCurrentLine() {
    const picked = selectionWithin(transcript);
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
  }
  /* Three small controls, and nothing more: what the line means, how it is
     said, and whether the words carry their class as colour. They are learner
     preferences, kept the way the reader keeps its own (one key, try/catch),
     rather than a new place to store three booleans. */
  const STAGE_KEY = 'orena.stage';
  const readStage = () => {
    try {
      const raw = JSON.parse(localStorage.getItem(STAGE_KEY) || 'null');
      return raw && typeof raw === 'object' ? raw : {};
    } catch {
      return {};
    }
  };
  const savedStage = readStage();
  const stage = {
    meaning: savedStage.meaning !== false,
    pinyin: savedStage.pinyin !== false,
    // Word-class colours have no switch on the baseline's transcript, so a stored "on" would be one nobody can turn off.
    colors: false,
    autoscroll: savedStage.autoscroll !== false,
  };
  const showPinyin = () => language === 'zh' && stage.pinyin && ctx.profile.pinyin !== 'off';
  const keepStage = () => {
    try {
      localStorage.setItem(STAGE_KEY, JSON.stringify(stage));
    } catch {
      // A device that cannot keep the preference still honours it this visit.
    }
  };
  /* Whether a line's meaning and its reading are shown is a property of the
     panel, not of a row: every row has both slots, and the panel says which of
     them count. That is what makes a change of current line free of geometry -
     the alternative, showing them on whichever row the voice is on, is the
     expand-and-collapse this batch removed. */
  const showAllMeaning = (on) => {
    stage.meaning = on;
    transcript.dataset.showMeaning = on ? 'on' : 'off';
    bar?.setToggle('meaning', on);
    // Meanings that are shown say where they came from - once, beside the
    // control that shows them, never under every line (D-051 rule 6).
    const note = transcript.querySelector('[data-meaning-note]');
    if (note) note.hidden = !on;
  };
  const showAllReadings = () => {
    transcript.dataset.showReading = showPinyin() ? 'on' : 'off';
    bar?.setToggle('pinyin', stage.pinyin);
  };
  closeLook = stage.colors;
  /* Replay, Practice, and the display preferences, in one bar with a fixed
     place above the list - never inside the row the voice happens to be on
     (DESIGN_CONTRACT: shared action toolbar, icon-first shared actions). */
  const bar = bindLearningToolbar(transcript.querySelector('.learning-toolbar'), {
    onAction: (name) => {
      if (name === 'deep') openDeep();
    },
    onToggle: (name, on) => {
      if (name === 'meaning') showAllMeaning(on);
      else if (name === 'pinyin') {
        stage.pinyin = on;
        showAllReadings();
      } else if (name === 'autoscroll') {
        stage.autoscroll = on;
        readingAheadUntil = 0;
      } else {
        stage.colors = on;
        closeLook = on;
      }
      keepStage();
      paintFollow();
      if (stage.autoscroll) keepCurrentInView('instant');
    },
  });
  bar.setToggle('autoscroll', stage.autoscroll);
  showAllMeaning(stage.meaning);
  showAllReadings();
  /* Everything deeper than hearing and asking, behind one button (ui/line-sheet.js). */
  function openDeep() {
    const line = model.current;
    if (!line) return;
    openLineSheet({
      r,
      c,
      when: duration(line.start_ms),
      text: line.original_text,
      language,
      onPick: (way) => {
        if (way === 'keep') return saveCurrentSentence();
        if (way === 'inspect') return inspectCurrentLine();
        if (deeperPractice.includes(way)) openPractice(way);
      },
    });
  }
  function saveCurrentSentence() {
    const line = model.current;
    if (!line) return;
    memory.rememberLanguage({
      term: line.original_text,
      origin: id,
      where: item.title,
      why: 'from_listening',
      context: line.original_text,
    });
    status(c.persisted);
  }
  /* A learner who has read ahead gets one way back to the voice, and it only
     exists while they are actually away from it. */
  {
    const back = root.querySelector('[data-back-to-current]');
    const list = transcript.querySelector('ol');
    const refresh = () => {
      const current = transcript.querySelector('li[data-current]');
      if (!current) return;
      const above = current.offsetTop - list.offsetTop < list.scrollTop - 8;
      const below =
        current.offsetTop - list.offsetTop + current.offsetHeight >
        list.scrollTop + list.clientHeight + 8;
      back.hidden = !(above || below);
    };
    list.addEventListener('scroll', refresh, { passive: true });
    back.onclick = () => {
      readingAheadUntil = 0;
      keepCurrentInView('smooth');
      back.hidden = true;
    };
    setTimeout(refresh, 400);
  }
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

  lineNote.querySelector('[data-retry-annotation]').onclick = () => {
    annotated.delete(model.current.segment_id);
    paintFollow();
  };
  /* A token is the smallest thing a learner can point at, so pointing at it
     opens the same explanation every other surface uses - with the line it
     came from as its context, which is what makes the answer about this
     sentence rather than a dictionary entry. */
  transcript.addEventListener('click', (event) => {
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
      if (isAlive()) lineNoteText.textContent = c.meaningUnavailable;
    } finally {
      button.disabled = false;
    }
  };
  /* A tapped line is picked, not jumped to (Orena Listening frame 03 A): the voice stays where
     it is until the learner says "jump here", and "replay line" hears just that line. A line the
     voice is already on has nothing to pick; a tap in it is a tap on a word. */
  const picked = () => transcript.querySelector('li[data-picked]');
  const unpick = () => {
    const was = picked();
    if (!was) return;
    was.removeAttribute('data-picked');
  };
  root.querySelectorAll('[data-segment]').forEach(
    (button) =>
      (button.onclick = () => {
        if (recording) return;
        const li = button.closest('li');
        if (li.hasAttribute('data-current')) return unpick();
        const same = li.hasAttribute('data-picked');
        unpick();
        if (same) return;
        li.setAttribute('data-picked', '');
      }),
  );
  root.querySelectorAll('[data-seek-here]').forEach(
    (button) =>
      (button.onclick = () => {
        if (recording) return;
        unpick();
        model.select(button.dataset.seekHere);
        practice = null;
        closePractice();
        const s = model.current;
        replaySegment(playerRoot, payload.playback, s.start_ms, null, rate);
        paintFollow();
        // The line becomes the current one in place; the learner's place moves with it.
        keepCurrentInView();
        remember();
      }),
  );
  root.querySelectorAll('[data-loop-line]').forEach(
    (button) =>
      (button.onclick = () => {
        if (recording) return;
        const s = model.segments.find((x) => x.segment_id === button.dataset.loopLine);
        if (s) replaySegment(playerRoot, payload.playback, s.start_ms, s.end_ms, rate);
      }),
  );
  const seekInput = root.querySelector('[data-seek]');
  // The played part of the scrubber is drawn from its position, the way the baseline has it.
  const paintFill = () => {
    const span = Number(seekInput.max) - Number(seekInput.min);
    seekInput.style.setProperty('--fill', `${span > 0 ? Math.max(0, Math.min(100, ((Number(seekInput.value) - Number(seekInput.min)) / span) * 100)) : 0}%`);
  };
  paintFill();
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
    paintFill();
    seekPlayback(playerRoot, payload.playback, Number(event.target.value));
  };
  function onClock(event) {
    const playing = event.detail.player_state === 1;
    if (!scrubbing) {
      timeOutput.textContent = duration(event.detail.time_ms);
      seekInput.value = String(event.detail.time_ms);
      paintFill();
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
    if (practice) {
      // Re-assert the boundary against a player that connected late.
      if (practice === 'dictation') holdPractisedLine();
      return;
    }
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
        if (stage.autoscroll && !readingAhead()) keepCurrentInView();
      }
    }
  }
  playerRoot.addEventListener('orena:media-time', onClock);
  connectMediaPlayer(playerRoot, payload.playback);
  paintFollow();
  keepCurrentInView('instant');
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
    root.removeAttribute('data-dictation');
    root.querySelector('.listen-workspace')?.removeAttribute('data-dictation');
    const responseHost = root.querySelector('[data-response-host]');
    if (responseHost) responseHost.hidden = false;
    transcript.hidden = false;
    // Following is the whole source again.
    releaseSegment(playerRoot);
    practice = null;
    lastClockSegment = null;
    paintFollow();
    keepCurrentInView('instant');
    remember();
  }
  /* Writing down a line means hearing that line, and not the five after it.

     Dictation binds the player to the segment being written (`holdSegment`),
     so every way of starting playback - Replay, the transport's play button,
     the video element's own controls - stops at the end of that line. Before
     this, only Replay was bounded and everything else ran the source on
     through the rest of the lesson, which is what a learner met first.

     The player may not have its metadata yet when a practice opens straight
     from a link, so the hold is also re-applied from the clock: asking twice
     costs nothing, and the boundary is never missed. */
  function holdPractisedLine() {
    if (practice !== 'dictation' || !practiceTarget) return releaseSegment(playerRoot);
    return holdSegment(playerRoot, practiceTarget.start_ms, practiceTarget.end_ms);
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
    /* A live microphone owns the line, so moving off it waits - but a control
       that is off for a different reason (the first line, the last line) must
       not be switched back on when the recording ends. */
    practiceRoot
      .querySelectorAll('[data-prev-moment], [data-next-moment], [data-menu-toggle]')
      .forEach((x) => {
        if (active) {
          x.dataset.wasDisabled = String(x.disabled);
          x.disabled = true;
          x.title = c.recordingInProgress;
        } else {
          x.disabled = x.dataset.wasDisabled === 'true';
          x.removeAttribute('title');
        }
      });
  }
  function basePractice() {
    stopSegmentPlayback(playerRoot, payload.playback);
    practiceTarget = { ...model.current };
    transcript.hidden = practice === 'dictation';
    holdPractisedLine();
    // The stage hands the room over to the practice panel: the line being
    // worked on is shown there, so showing it twice would only compete.
    practiceRoot.hidden = false;
    // The transcript stays on screen through Shadowing and Speaking, so it has
    // to mark the line being practised rather than the one Follow left behind.
    paintFollow();
    remember();
  }
  async function openPractice(intent) {
    if (recording) return;
    voiceCleanup();
    voiceCleanup = () => {};
    practiceVersion++;
    const version = practiceVersion;
    practice = intent;
    /* A practice mode is its own task. The writing response belongs to Follow -
       "what stayed with you" under a Dictation is a different module wearing
       this one's page (D-057: one task, one frame). */
    const responseHost = root.querySelector('[data-response-host]');
    if (responseHost) responseHost.hidden = true;
    lexical.forget();
    recorder.discard();
    take = null;
    basePractice();
    const target = practiceTarget;
    const at = model.segments.findIndex((x) => x.segment_id === target.segment_id);
    /* Leaving the task and moving through it are different acts, and used to
       be told the same way: an arrow back beside an arrow on. A learner who
       wanted the line before ended up out of Dictation altogether. So leaving
       is chrome - a cross, in the panel's top row, next to the name of the
       task - and moving is task navigation, with the line's place in the
       lesson between its two directions. */
    const dictating = intent === 'dictation';
    root.toggleAttribute('data-dictation', dictating);
    root.querySelector('.listen-workspace')?.toggleAttribute('data-dictation', dictating);
    practiceRoot.innerHTML = dictating
      ? screenHtml({
          title: item.title,
          level: payload.catalog?.level || '',
          index: at + 1,
          total: model.segments.length,
          kind: payload.playback?.kind === 'video' ? 'video' : 'audio',
          range: `${duration(target.start_ms)} – ${duration(target.end_ms)}`,
          poster: art(item),
          rate,
          r,
          c,
          ask: r.dictAsk,
        })
      : `<div class="practice-top"><small>${c[intent + 'Name']}</small><button type="button" class="quiet practice-exit" data-exit-practice>${symbol('close', 18)}<span>${esc(c.exitPractice)}</span></button></div><h2>${intent === 'dictation' ? c.hearFirst : intent === 'speaking' ? c.voiceResponse : c.shadowPrompt}</h2><nav class="practice-steps" aria-label="${esc(c.lineNavigation)}"><button type="button" class="quiet" data-prev-moment aria-label="${esc(c.previousLine)}" data-tip="${esc(c.previousLine)}">${symbol('back', 18)}</button><span class="practice-place">${at + 1} / ${model.segments.length}</span><button type="button" class="quiet" data-next-moment aria-label="${esc(c.nextLine)}" data-tip="${esc(c.nextLine)}">${symbol('forward', 18)}</button></nav><div data-practice-body></div>`;
    practiceRoot.querySelector('[data-exit-practice]').onclick = closePractice;
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
    const body = dictating ? practiceRoot : practiceRoot.querySelector('[data-practice-body]');
    const nextIndex = at + 1;
    const nextButton = practiceRoot.querySelector('[data-next-moment]');
    const previousButton = practiceRoot.querySelector('[data-prev-moment]');
    const exhausted = nextIndex >= model.segments.length;
    if (nextButton) nextButton.disabled = exhausted;
    if (previousButton) previousButton.disabled = at <= 0;
    /* Moving to another line stays inside the task: the same intention, a
       different segment. openPractice() already discards the take, the
       recorder and the previous version, so this is a move rather than a
       leave-and-re-enter. */
    const moveTo = (index) => {
      if (recording || index < 0 || index >= model.segments.length) return;
      model.select(model.segments[index].segment_id);
      openPractice(intent);
    };
    if (nextButton) nextButton.onclick = () => moveTo(nextIndex);
    if (previousButton) previousButton.onclick = () => moveTo(at - 1);
    /* Previous, where you are, Next - and nothing else.

       Two attempts at arbitrary segment selection have now been removed. A
       strip of numbered pills said nothing a learner could recognise; a
       popover of real sentences read better but overlapped its own text,
       overflowed its pane, and covered the task it was meant to serve. Both
       were a second way to do what the two arrows already do, and both spent
       room that Dictation needs for the line being written.

       The position between the arrows is a state, not a control. Leaving is
       its own act, in the chrome. */
    if (intent === 'dictation') {
      /* The baseline's Dictation screen (D-066, ui/dictation-screen.js): the task on the
         left - the line's clip, the shape of the line with a reading under each
         character, the field - and the result on the right. The comparison, the hint
         and the evidence are the ones that were here before; what changed is how they
         are drawn and that a hint has three levels and never shows the whole line. */
      const spoken = target.spoken_text || target.original_text;
      const readings = readingsFor(spoken, target.original_text, payload.catalog?.pinyin_chars_by_segment?.[target.segment_id]);
      const readingLine = readingLineFor(spoken, target.original_text, payload.catalog?.pinyin_by_segment?.[target.segment_id]);
      const answer = body.querySelector('#reconstruction');
      const shapeHost = body.querySelector('[data-hint-panel]');
      const hintPill = body.querySelector('[data-dz-hint-pill]');
      const hintButton = body.querySelector('[data-hint]');
      const resultHost = body.querySelector('[data-dz-result]');
      const clip = body.querySelector('[data-dz-clip]');
      const rateButton = body.querySelector('[data-dz-rate]');
      const emptyResult = resultHost.innerHTML;
      const key = `${payload.asset.asset_id}:${target.segment_id}`;
      const keepTerm = (payload.catalog?.vocabulary || []).find((term) => term && target.original_text.includes(term)) || '';
      /* The hint is a working aid, not an outcome: it lives for this visit only and
         never becomes evidence. */
      let hintLevel = 0;
      answer.value = memory.value.answers[key] || '';
      const paintHint = () => {
        const view = dictationHintView({ expected: spoken, answer: answer.value, language, level: hintLevel, readings });
        shapeHost.innerHTML = shapeHtml(view, language, r);
        hintPill.hidden = view.level === 0;
        hintPill.innerHTML = hintLevelHtml(view, r);
        hintButton.disabled = view.level >= HINT_LEVELS;
      };
      body.querySelectorAll('[data-listen]').forEach((x) => (x.onclick = playLine));
      rateButton.onclick = () => {
        const order = rateChips.map((chip) => Number(chip.dataset.rateValue));
        const next = order[(order.indexOf(rate) + 1) % order.length];
        chooseRate(rateChips.find((chip) => Number(chip.dataset.rateValue) === next) || rateChips[0]);
        rateButton.textContent = `${rate}×`;
      };
      hintButton.onclick = () => {
        hintLevel = Math.min(HINT_LEVELS, hintLevel + 1);
        // Asking for a hint is going back to work on the line.
        resultHost.innerHTML = emptyResult;
        paintHint();
      };
      answer.oninput = () => {
        memory.write(key, answer.value, 'answers');
        paintHint();
      };
      paintHint();
      /* The clip's own bar: where in the line the voice is, from the player itself. */
      const media = playerRoot.querySelector('audio, video');
      const clipTimer = setInterval(() => {
        if (!isAlive() || version !== practiceVersion) return clearInterval(clipTimer);
        if (!media || !clip) return;
        const span = Math.max(1, target.end_ms - target.start_ms);
        clip.style.width = `${Math.max(0, Math.min(100, ((media.currentTime * 1000 - target.start_ms) / span) * 100))}%`;
      }, 120);
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
          const typed = answer.value.trim();
          // The evidence and the score are the evaluator's, as before; the screen only reads them.
          dictation.compare(typed);
          const result = dictationResult({
            lineIndex: at + 1,
            lineTotal: model.segments.length,
            expected: spoken,
            answer: typed,
            language,
            reading: readingLine,
            readings,
            level: hintLevel,
            note: (mark) =>
              mark.kind === 'wrong' ? `${mark.from} → ${mark.to}` : mark.kind === 'missing' ? `${r.dictMissing} ${mark.to}` : `${r.dictExtra} ${mark.from}`,
          });
          resultHost.innerHTML = resultHtml({
            result,
            language,
            r,
            meaning: model.meaning(target.segment_id) || '',
            keep: keepTerm,
            last: nextIndex >= model.segments.length,
          });
          /* Each mark opens the explanation of the right word, in this line. */
          resultHost.querySelectorAll('[data-mark]').forEach((button) => {
            button.onclick = () => {
              const mark = result.marks[Number(button.dataset.mark)];
              inspectPhrase(ctx, mark.to || mark.from, item.title, spoken, { id, where: item.title, why: 'from_listening' });
            };
          });
          resultHost.querySelector('[data-listen-again]').onclick = playLine;
          resultHost.querySelector('[data-again]').onclick = () => {
            resultHost.innerHTML = emptyResult;
            answer.focus();
            playLine();
          };
          resultHost.querySelector('[data-next-line]').onclick = () => moveTo(nextIndex);
          resultHost.querySelector('[data-keep-line]').onclick = (click) => {
            memory.rememberLanguage({
              term: keepTerm || target.original_text,
              origin: id,
              where: item.title,
              why: 'from_listening',
              context: target.original_text,
            });
            click.currentTarget.disabled = true;
            status(c.persisted);
          };
          resultHost.scrollIntoView({ block: 'nearest', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
          await persist();
        } catch (error) {
          resultHost.textContent = error.message;
        }
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
      body.innerHTML = `<blockquote class="practice-line" data-practice-line data-practice-segment="${esc(target.segment_id)}" lang="${language}">${esc(target.original_text)}</blockquote><p class="practice-meaning">${esc(model.meaning(target.segment_id) || '')}</p><p class="practice-guide">${intent === 'shadowing' ? c.shadowGuide : c.speakingGuide}</p><div class="button-row"><button class="outline" data-listen>${c.replay} ↺</button><button class="primary" data-record>● ${c.record}</button>${hint({ text: c.localAudio })}</div><p role="status" data-record-status></p><div data-take></div><div data-feedback></div>`;
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
              area.innerHTML = pronunciationReportHtml(c, result, language);
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
  bindComposer(root, ctx, item, () => model.current?.original_text || '');
  bindImages(root, c);
  // Follow arrives here as an intention too, and its whole point is that
  // nothing opens over the moment.
  if (deeperPractice.includes(practice)) openPractice(practice);
  return () => {
    disposed = true;
    bar.dispose();
    lexical.destroy();
    voiceCleanup();
    practiceVersion++;
    recorder.cleanup();
    playerRoot.removeEventListener('orena:media-time', onClock);
    playerRoot.removeEventListener('orena:media-state', onMediaState);
    disconnectMediaPlayer(playerRoot);
  };
}
