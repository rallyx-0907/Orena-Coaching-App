/* Orena's voice mode: the inline row the Home composer and the Contextual panel's footer both draw
   (E5 §6.4 "gradient-ring input pill... used twice"), and the full-screen immersive mode (frame 56,
   the rail's mic only - desktop, E5 §7.1). One engine drives both shapes.

   Contract §9's real-time voice session is provisional and unbuilt (no `POST /api/agent/voice/
   session` call is made); this is the cascade the Wave B brief itself names instead: the shared mic
   sheet gates the microphone, `capabilities/audio-recorder.js` records, `POST /api/speech/transcribe`
   turns it into text (no language is named - the learner may ask in their support language or the
   one they are learning, and the provider detects it), and the text becomes an ordinary turn through
   the same `send` a typed message uses - so a voice exchange and a typed one are indistinguishable
   to the agent and to device memory. The reply is read aloud with the browser's own speechSynthesis
   when "Voice reply" is on and the turn was not metered (§12 S12 "no voice"); there is no server
   audio_chunk to play (cascade, not s2s - §9's `mode` is not chosen by this build). The mock's own
   `voiceSimulate()` (a fabricated demo transcript typed out on a timer) is prototype-only and is
   not reproduced here - a browser with no microphone reads as the same `blocked` mic state
   Speaking already draws, never a fake heard line. */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { INTEL_STATES, intelChip } from '../../kit/brand.js';
import { langAttr } from '../../kit/lang.js';
import { fromContractLang } from '../../agent/contract.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { createLocalAudioRecorder } from '../../capabilities/audio-recorder.js';
import { micGate, openMicState } from '../mic/sheet.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { href } from '../../shell/routes.js';
import { t } from './copy.js';
import { voicePhaseMarkState, voicePhaseStatusKey, voicePhaseHintKey, speakableText, latestSuggestions, endsVoice, errorText } from './model.js';
import { sendHomeTurn, abortHome, ensureOpening, subscribeHome, homeState, requestComposerFocus } from './home-session.js';

const TTS_TAG = { en: 'en-US', vi: 'vi-VN', zh: 'zh-CN' };

function ttsLang() {
  const support = String(languages().support || 'en').slice(0, 2);
  return TTS_TAG[support] || 'en-US';
}

/* One engine per open voice surface (the inline row's own mount, or the full-screen overlay) -
   never shared, so closing one never touches another's recorder.
   - `send(text)` is awaited to the turn's finished reply message (or null);
   - `abort()` ends a turn still waiting for its reply (the learner's stop while Orena thinks);
   - `resume()` runs when the mic sheet - one sheet at a time, so it replaced the surface that
     started the recording - has been answered and this engine no longer exists (the Contextual
     panel reopens itself);
   - `onTextOnly()` runs when the reply says the voice session ended (§4.1 `text_only`). */
export function createVoiceEngine({ ctx = {}, send, onChange, abort, resume, onTextOnly } = {}) {
  let phase = 'idle'; // idle | listening | thinking | speaking
  let heard = '';
  let reply = null;
  let speakOn = true;
  let recorder = null;
  let disposed = false;

  const snapshot = () => ({ phase, heard, reply, speakOn });

  function emit() {
    if (!disposed) onChange?.(snapshot());
  }

  function setPhase(next) {
    phase = next;
    emit();
  }

  async function begin() {
    if (phase === 'listening' || phase === 'thinking') return;
    recorder = createLocalAudioRecorder();
    await micGate(ctx, async () => {
      if (disposed) {
        recorder.cleanup();
        resume?.();
        return;
      }
      const started = await recorder.start();
      if (disposed) return recorder.cleanup();
      if (!started) return void openMicState(ctx, { state: 'blocked' });
      heard = '';
      reply = null;
      setPhase('listening');
    });
  }

  /* One question through to its answer: `text` is what the learner said (or a suggestion they
     tapped). */
  async function converse(text) {
    heard = text;
    reply = null;
    setPhase('thinking');
    const answer = await send(text);
    if (disposed) return;
    reply = answer;
    if (endsVoice(answer)) {
      onTextOnly?.();
      return;
    }
    const toSpeak = speakOn ? speakableText(answer) : '';
    if (toSpeak && typeof window.speechSynthesis?.speak === 'function') speak(toSpeak);
    else setPhase('idle');
  }

  async function finish() {
    if (phase !== 'listening' || !recorder) return;
    setPhase('thinking');
    const take = await recorder.stop();
    if (disposed) return;
    if (!take?.blob) {
      setPhase('idle');
      return;
    }
    let transcript = '';
    try {
      const result = await api.transcribeSpeech(take.blob, '', 'orena-voice.webm');
      transcript = String(result?.text || '').trim();
    } catch {
      // Not the mic sheet's "assessment" state: nothing is being scored here and no recording is kept.
      setPhase('idle');
      toast(t('voiceTranscribeFailed'), { iconName: 'circle-alert' });
      return;
    }
    if (disposed) return;
    if (!transcript) {
      setPhase('idle');
      void openMicState(ctx, { state: 'notheard' });
      return;
    }
    await converse(transcript);
  }

  /* A browser with no voice installed never starts the utterance and never reports an error; the
     row would sit on "Speaking" for good. If nothing starts within a few seconds it is over. */
  const SPEECH_START_MS = 4000;

  function speak(text) {
    setPhase('speaking');
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      let started = false;
      utterance.lang = ttsLang();
      utterance.onstart = () => {
        started = true;
      };
      utterance.onend = () => {
        if (phase === 'speaking') setPhase('idle');
      };
      utterance.onerror = () => {
        if (phase === 'speaking') setPhase('idle');
      };
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
      setTimeout(() => {
        if (!started && phase === 'speaking' && !disposed) {
          stopSpeaking();
          setPhase('idle');
        }
      }, SPEECH_START_MS);
    } catch {
      setPhase('idle');
    }
  }

  function stopSpeaking() {
    try {
      window.speechSynthesis?.cancel();
    } catch {
      /* nothing to cancel */
    }
  }

  return {
    /* The main button: start listening, send what was said, or stop whatever Orena is doing. */
    main() {
      if (phase === 'idle') void begin();
      else if (phase === 'listening') void finish();
      else if (phase === 'speaking') {
        stopSpeaking();
        setPhase('idle');
      } else if (phase === 'thinking') {
        abort?.();
        setPhase('idle');
      }
    },
    /* A suggestion tapped in the idle full-screen mode: asked as if it had been said. */
    ask(text) {
      if (phase === 'idle' && String(text || '').trim()) void converse(String(text).trim());
    },
    toggleSpeak() {
      speakOn = !speakOn;
      if (!speakOn && phase === 'speaking') {
        stopSpeaking();
        setPhase('idle');
        return;
      }
      emit();
    },
    state: snapshot,
    dispose() {
      disposed = true;
      try {
        recorder?.discard?.();
        recorder?.cleanup?.();
      } catch {
        /* already released */
      }
      stopSpeaking();
    },
  };
}

/* ------------------------------------------------------------------- Inline voice row --- */

function mainLabel(phase) {
  if (phase === 'listening') return t('voiceStopSend');
  return phase === 'idle' ? t('voiceStart') : t('stop');
}

/* The row inside the gradient-ring card (Home) or pill (panel): mark, status (+ what was heard),
   speak toggle, main button, back to typing. The frame's own fixed lines ("Tap the mic and ask
   your question", "Say your question…", "Answering out loud · reply is in the chat") explain
   controls and state the screen already shows - dropped (rule 50); only what was heard is drawn. */
export function voiceRowMarkup({ phase, heard, speakOn }, { fresh = false } = {}) {
  const showStop = phase !== 'idle';
  // The source fades the row in when voice mode opens; a repaint of the same row must not replay it.
  return html`<div class="s-orena-vrow${fresh ? ' s-orena-vrow--in' : ''}">
    ${intelChip({ size: 44, mark: 36, state: voicePhaseMarkState(phase) })}
    <div class="s-orena-vrow__body">
      <div class="s-orena-vrow__status"><span class="s-orena-dot s-orena-dot--${phase}"></span>${t(voicePhaseStatusKey(phase))}</div>
      ${heard ? html`<div class="s-orena-vrow__line">“${heard}”</div>` : ''}
    </div>
    <button type="button" class="s-orena-vrow__speak${speakOn ? '' : ' s-orena-vrow__speak--off'}" data-voice-speak aria-label="${speakOn ? t('voiceReplyOn') : t('voiceReplyOff')}" title="${speakOn ? t('voiceReplyOn') : t('voiceReplyOff')}">${raw(icon('volume-2', { size: 17 }))}</button>
    <button type="button" class="s-orena-vrow__main s-orena-voice-main s-orena-voice-main--${phase}" data-voice-main aria-label="${mainLabel(phase)}">${showStop ? raw(icon('square', { size: 12 })) : raw(icon('mic', { size: 19 }))}</button>
    <button type="button" class="s-orena-vrow__close" data-voice-close aria-label="${t('backToTyping')}" title="${t('backToTyping')}">${raw(icon('x', { size: 18 }))}</button>
  </div>`;
}

export function bindVoiceRow(root, engine, { onClose } = {}) {
  root.querySelector('[data-voice-main]')?.addEventListener('click', () => engine.main());
  root.querySelector('[data-voice-speak]')?.addEventListener('click', () => engine.toggleSpeak());
  root.querySelector('[data-voice-close]')?.addEventListener('click', () => {
    engine.dispose();
    onClose?.();
  });
}

/* ---------------------------------------------------------------- Full-screen voice (frame 56) */

let fullHandle = null;

function replyMarkup(reply) {
  if (!reply) return '';
  if (reply.error) return html`<div class="s-orena-voicefull__reply">${errorText(reply.error, t('transportError'))}</div>`;
  const segments = reply.segments || [];
  if (!segments.length) return '';
  return html`<div class="s-orena-voicefull__reply">${segments.map((segment) => html`<span lang="${langAttr(fromContractLang(segment.lang))}">${segment.text}</span>`)}</div>`;
}

function fullMarkup({ phase, heard, reply, speakOn }, suggestions, { fresh = false } = {}) {
  const showStop = phase !== 'idle';
  const hintKey = voicePhaseHintKey(phase);
  return html`<div class="s-orena-voicefull${fresh ? ' s-orena-voicefull--in' : ''}">
    <div class="s-orena-voicefull__head">
      <div class="s-orena-voicefull__title">${t('fullVoiceTitle')}</div>
      <button type="button" class="s-orena-voicefull__close" data-voice-full-close aria-label="${t('closeVoice')}">${raw(icon('x', { size: 18 }))}</button>
    </div>
    <div class="s-orena-voicefull__spacer"></div>
    <div class="s-orena-voicefull__orb"><svg viewBox="0 0 100 100" aria-hidden="true"><use href="#${INTEL_STATES[voicePhaseMarkState(phase)]}"></use></svg></div>
    <div class="s-orena-voicefull__status"><span class="s-orena-dot s-orena-dot--${phase}"></span>${t(voicePhaseStatusKey(phase))}</div>
    <div class="s-orena-voicefull__talk" data-scroll-region>
      ${heard ? html`<div class="s-orena-voicefull__heard">“${heard}”</div>` : ''}
      ${phase !== 'listening' ? replyMarkup(reply) : ''}
    </div>
    <div class="s-orena-voicefull__spacer"></div>
    ${phase === 'idle' && suggestions.length ? html`<div class="s-orena-voicefull__chips">${suggestions.map((s) => html`<button type="button" class="s-orena-voicefull__chip" data-voice-full-suggest="${s.label}">“${s.label}”</button>`)}</div>` : ''}
    <div class="s-orena-voicefull__controls">
      <button type="button" class="s-orena-voicefull__ghost" data-voice-full-type>${t('typeInstead')}</button>
      <button type="button" class="s-orena-voicefull__main s-orena-voice-main s-orena-voice-main--${phase}" data-voice-full-main aria-label="${mainLabel(phase)}">${showStop ? raw(icon('square', { size: 20 })) : raw(icon('mic', { size: 30 }))}</button>
      <button type="button" class="s-orena-voicefull__ghost${speakOn ? ' s-orena-voicefull__ghost--on' : ''}" data-voice-full-speak>${speakOn ? t('voiceReplyOn') : t('voiceReplyOff')}</button>
    </div>
    ${hintKey ? html`<div class="s-orena-voicefull__hint">${t(hintKey)}</div>` : ''}
  </div>`;
}

/* Opened only from the desk rail's mic (`shell/frame.js`, desktop-only per the source - E5 §7.1
   found no mobile trigger anywhere in the export, so none is invented here, rule 43). Shares Home's
   one ambient thread and session (home-session.js): the rail is not "about" any particular screen,
   so there is nothing for it to attach a context to, unlike every other voice entry point. It sits
   in the shell's overlay layer, under sheets: the mic sheet a first recording needs opens above it. */
export async function openVoiceFull() {
  if (fullHandle) return fullHandle;
  await useStyles('screens/orena/orena.css');
  const layer = document.querySelector('[data-part="layer"]');
  if (!layer) return null;
  ensureOpening();
  const opener = document.activeElement;
  const root = document.createElement('div');
  root.className = 's-orena-voicefull-root';
  root.setAttribute('role', 'dialog');
  root.setAttribute('aria-modal', 'true');
  root.setAttribute('aria-label', t('fullVoiceTitle'));

  const engine = createVoiceEngine({
    send: (text) => sendHomeTurn(text),
    abort: abortHome,
    onTextOnly: () => {
      close();
      requestComposerFocus();
      location.hash = href('orena');
    },
    onChange: paint,
  });

  function close() {
    document.removeEventListener('keydown', onKey);
    engine.dispose();
    unsubscribe();
    root.remove();
    fullHandle = null;
    if (opener?.isConnected) opener.focus({ preventScroll: true });
  }

  function onKey(event) {
    if (event.key === 'Escape' && !document.querySelector('.o-sheet')) close();
  }

  let painted = false;

  function paint() {
    mount(root, fullMarkup(engine.state(), latestSuggestions(homeState().messages), { fresh: !painted }));
    painted = true;
    root.querySelector('[data-voice-full-close]')?.addEventListener('click', close);
    root.querySelector('[data-voice-full-main]')?.addEventListener('click', () => engine.main());
    root.querySelector('[data-voice-full-speak]')?.addEventListener('click', () => engine.toggleSpeak());
    root.querySelectorAll('[data-voice-full-suggest]').forEach((button) => button.addEventListener('click', () => engine.ask(button.dataset.voiceFullSuggest)));
    root.querySelector('[data-voice-full-type]')?.addEventListener('click', () => {
      close();
      // "Type instead" lands on the chat with the cursor in the box (source `voiceType`).
      if (location.hash.startsWith('#/orena')) document.querySelector('[data-input]')?.focus();
      else {
        requestComposerFocus();
        location.hash = href('orena');
      }
    });
  }

  const unsubscribe = subscribeHome(() => paint());
  paint();
  layer.append(root);
  document.addEventListener('keydown', onKey);
  root.querySelector('[data-voice-full-main]')?.focus({ preventScroll: true });
  fullHandle = { close };
  // The source starts listening the moment voice mode opens (`voiceOpen` -> `voiceListen`).
  engine.main();
  return fullHandle;
}
