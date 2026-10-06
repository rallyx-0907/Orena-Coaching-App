/* Orena's live voice, mode A (AGENT_CONTRACT §9, R28, Intelligence lane PR #81): the client half of a
   speech-to-speech session. No DOM and no copy: the voice surfaces (screens/orena/voice.js) draw it.

   1. `openVoiceSession(body)` asks the server for a session (`POST /api/agent/voice/session`, a turn body without
      `message`). The server answers with a one-use token for the vendor's websocket; the provider key never
      reaches the client.
   2. `connectLiveVoice(session, …)` opens that socket, sends the server's locked `setup` first and waits for
      `setupComplete`. Then:
      - the microphone streams as 16 kHz PCM16;
      - Orena's audio plays as it arrives (24 kHz PCM16);
      - both transcripts are reported;
      - an `interrupted` stops playback at once (barge-in);
      - a tool call is run by the server (`POST /api/agent/voice/tool`), its §4 events handed to the caller and
        its responses sent back on the socket.
   3. `end()` closes everything and tells the server (`POST /api/agent/voice/end`), which bills the time. A
      session never ended is billed at its cap, so leaving the page ends it too (sendBeacon).

   Failure is never a switch to another vendor (§9): the caller falls back to its own cascade. */
import { CONTRACT_VERSION } from './contract.js';

const WORKLET_URL = new URL('../capabilities/pcm-capture-worklet.js', import.meta.url).href;

export class VoiceSessionError extends Error {
  constructor(status, category = '', retryAfter = 0) {
    super(category || `voice_session_${status}`);
    this.status = status;
    this.category = category;
    this.retryAfter = retryAfter;
  }
}

async function post(path, body, fetchImpl) {
  const response = await fetchImpl(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const category = String(data?.detail?.category || data?.category || '');
    throw new VoiceSessionError(response.status, category, Number(response.headers?.get?.('Retry-After')) || 0);
  }
  return data;
}

/* Orena's voice, the learner's choice (§9, R29): kept on this device, sent with each session; the server locks it
   into the session and uses its default for an unknown or missing id. */
const VOICE_KEY = 'orena.voice.v1';
export function chosenVoice(storage = globalThis.localStorage) {
  try {
    return String(storage?.getItem(VOICE_KEY) || '');
  } catch {
    return '';
  }
}
export function chooseVoice(id, storage = globalThis.localStorage) {
  try {
    storage?.setItem(VOICE_KEY, String(id || ''));
  } catch {
    /* kept for this visit only */
  }
}

/* The voices the server offers, labelled in the interface language. Null while voice is off (404). */
export async function listVoices(interfaceLang, { fetchImpl = globalThis.fetch } = {}) {
  try {
    const response = await fetchImpl(`/api/agent/voice/voices?interface=${encodeURIComponent(interfaceLang || 'en')}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!response.ok) return null;
    const data = await response.json();
    return Array.isArray(data?.voices) && data.voices.length ? { default: String(data.default || ''), voices: data.voices } : null;
  } catch {
    return null;
  }
}

/* The session body is a turn body without a message (§9), with the learner's voice when they chose one. */
export function voiceSessionBody(turnRequest, { voice = '' } = {}) {
  const { trigger, message, ...rest } = turnRequest || {};
  return { contract_version: CONTRACT_VERSION, ...rest, ...(voice ? { voice } : {}) };
}

export function openVoiceSession(body, { fetchImpl = globalThis.fetch } = {}) {
  return post('/api/agent/voice/session', body, fetchImpl);
}

/* Bytes <-> base64 without a stack overflow on long frames. */
export function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}

export function pcm16ToFloat(base64) {
  const raw = atob(base64);
  const samples = new Float32Array(raw.length >> 1);
  for (let i = 0; i < samples.length; i += 1) {
    let value = raw.charCodeAt(2 * i) | (raw.charCodeAt(2 * i + 1) << 8);
    if (value >= 0x8000) value -= 0x10000;
    samples[i] = value / 0x8000;
  }
  return samples;
}

/* `audio` holds the two AudioContexts the caller created inside the learner's tap (mobile Safari only starts
   audio from a gesture): `{ input, output }`. */
export function connectLiveVoice(session, { audio, mediaDevices = globalThis.navigator?.mediaDevices, fetchImpl = globalThis.fetch, WebSocketCtor = globalThis.WebSocket, onState = () => {}, onLearner = () => {}, onOrena = () => {}, onTurnComplete = () => {}, onEvents = () => {}, onClosed = () => {} } = {}) {
  const id = session.voice_session_id;
  const connect = session.connect || {};
  const url = `${connect.url}${String(connect.url).includes('?') ? '&' : '?'}access_token=${encodeURIComponent(connect.ephemeral_token)}`;
  const socket = new WebSocketCtor(url);
  let ready = false;
  let closed = false;
  let stream = null;
  let worklet = null;
  let source = null;
  let heard = ''; // what the learner has said in the current turn
  let lastHeard = ''; // the learner's latest words, kept past the turn's end
  let said = ''; // what Orena has said in the current turn
  let playAt = 0;
  const playing = new Set();
  const capTimer = setTimeout(() => end('cap'), Math.max(30, Number(session.max_seconds) || 900) * 1000);

  function send(message) {
    if (socket.readyState === 1) socket.send(JSON.stringify(message));
  }

  async function startMic() {
    stream = await mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
    if (closed) return stopMic();
    try {
      source = audio.input.createMediaStreamSource(stream);
    } catch {
      // A browser that cannot feed a 16 kHz context from its microphone gets one at its own rate; the worklet
      // averages it down instead.
      try { await audio.input.close(); } catch { /* closed */ }
      audio.input = new (globalThis.AudioContext || globalThis.webkitAudioContext)();
      await audio.input.resume?.();
      source = audio.input.createMediaStreamSource(stream);
    }
    await audio.input.audioWorklet.addModule(WORKLET_URL);
    if (closed) return stopMic();
    worklet = new AudioWorkletNode(audio.input, 'orena-pcm16-capture');
    worklet.port.onmessage = (event) => {
      if (ready && !closed) send({ realtimeInput: { audio: { data: toBase64(echoGate(event.data)), mimeType: 'audio/pcm;rate=16000' } } });
    };
    source.connect(worklet);
    onState('listening');
  }

  function stopMic() {
    try { source?.disconnect(); } catch { /* gone */ }
    try { worklet?.disconnect(); } catch { /* gone */ }
    for (const track of stream?.getTracks?.() || []) track.stop();
    source = null;
    worklet = null;
    stream = null;
  }

  /* While Orena is speaking (and a moment after), a phone's speaker leaks into its own microphone and mobile
     Safari does not cancel the echo of Web Audio output: Orena heard itself and answered itself, over and over.
     During that window only a clearly louder voice - the learner talking over Orena, which is barge-in - is sent;
     quieter frames go as silence, so the stream stays continuous and the vendor's VAD sees no speech. */
  const ECHO_TAIL_S = 0.45;
  // How loud the learner must be to talk over Orena. A fixed 0.12 sat above a phone microphone's normal speech
  // level, so a learner speaking over Orena or a playing lesson was cut into fragments the recognizer turned into
  // nonsense. It now follows the echo: a frame passes when it is clearly louder than what the microphone has been
  // picking up of Orena's or the lesson's audio.
  let echoLevel = 0.02;
  const BARGE_IN_RATIO = 2.5;
  // The lesson's own media is the same problem: a video playing on the page reaches the microphone, and Orena
  // would take it for the learner. Every player in the app reports its clock on the document (media-player.js).
  let mediaUntil = 0;
  const onMediaClock = (event) => {
    mediaUntil = event.detail?.player_state === 1 ? Date.now() + 700 : 0;
  };
  document.addEventListener('orena:media-time', onMediaClock);

  function echoGate(buffer) {
    if (!playing.size && audio.output.currentTime > playAt + ECHO_TAIL_S && Date.now() > mediaUntil) return buffer;
    const frame = new Int16Array(buffer);
    let sum = 0;
    for (let i = 0; i < frame.length; i += 1) sum += (frame[i] / 0x8000) ** 2;
    const rms = Math.sqrt(sum / frame.length);
    if (rms >= Math.max(0.03, echoLevel * BARGE_IN_RATIO)) return buffer; // the learner, over the echo
    echoLevel = echoLevel * 0.8 + rms * 0.2; // what the echo sounds like right now
    return new Int16Array(frame.length).buffer;
  }

  function play(base64) {
    const samples = pcm16ToFloat(base64);
    if (!samples.length) return;
    const ctx = audio.output;
    const buffer = ctx.createBuffer(1, samples.length, 24000);
    buffer.copyToChannel(samples, 0);
    const node = ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(ctx.destination);
    playAt = Math.max(playAt, ctx.currentTime + 0.03);
    node.start(playAt);
    playAt += buffer.duration;
    playing.add(node);
    node.onended = () => {
      playing.delete(node);
      if (!playing.size && !closed) onState('listening');
    };
    onState('speaking');
  }

  /* Barge-in: the learner spoke over Orena; what is queued never plays. */
  function silence() {
    for (const node of playing) {
      try { node.stop(); } catch { /* already stopped */ }
    }
    playing.clear();
    playAt = 0;
  }

  async function runTools(calls) {
    let answer = null;
    try {
      // The vendor's input transcript can arrive after its tool call: the learner's latest words go instead of an
      // empty string, which the server would read as "they said nothing" and lose the open-on-request (R29).
      const words = heard.trim() || lastHeard;
      answer = await post('/api/agent/voice/tool', { voice_session_id: id, calls, ...(words ? { heard: words } : {}) }, fetchImpl);
    } catch (error) {
      if (error?.status === 404) return end('server');
      answer = { responses: calls.map((call) => ({ id: call.id, name: call.name, response: { error: 'unavailable' } })), events: [] };
    }
    if (closed) return;
    // `open`: the learner asked in their own words to open this place - its action runs now, without a tap (R29).
    if (Array.isArray(answer?.events) && answer.events.length) onEvents(answer.events, String(answer.open || ''));
    send({ toolResponse: { functionResponses: answer?.responses || [] } });
  }

  socket.onopen = () => send(connect.setup || {});
  socket.onmessage = async (event) => {
    let message;
    try {
      message = JSON.parse(typeof event.data === 'string' ? event.data : await event.data.text());
    } catch {
      return;
    }
    // `setupComplete` is an empty object: its presence is the signal, not its value.
    if (!ready && Object.prototype.hasOwnProperty.call(message, 'setupComplete')) {
      ready = true;
      try {
        await startMic();
      } catch {
        end('mic');
      }
      return;
    }
    if (message.toolCall?.functionCalls?.length) {
      void runTools(message.toolCall.functionCalls.map(({ id: callId, name, args }) => ({ id: callId, name, args })));
      return;
    }
    const content = message.serverContent;
    if (!content) return;
    if (content.interrupted) {
      silence();
      onState('listening');
    }
    if (content.inputTranscription?.text) {
      heard += content.inputTranscription.text;
      if (heard.trim()) lastHeard = heard.trim();
      onLearner(heard);
    }
    if (content.outputTranscription?.text) {
      said += content.outputTranscription.text;
      onOrena(said);
    }
    for (const part of content.modelTurn?.parts || []) {
      if (part.inlineData?.data) play(part.inlineData.data);
    }
    if (content.turnComplete) {
      onTurnComplete({ heard: heard.trim(), said: said.trim(), interrupted: Boolean(content.interrupted) });
      heard = '';
      said = '';
    }
  };
  socket.onerror = () => end('socket');
  socket.onclose = () => end('socket');

  const beacon = () => {
    try {
      navigator.sendBeacon?.('/api/agent/voice/end', new Blob([JSON.stringify({ voice_session_id: id })], { type: 'application/json' }));
    } catch { /* the cap bills it */ }
  };
  window.addEventListener('pagehide', beacon);

  function end(reason = 'learner') {
    if (closed) return;
    closed = true;
    clearTimeout(capTimer);
    window.removeEventListener('pagehide', beacon);
    document.removeEventListener('orena:media-time', onMediaClock);
    silence();
    stopMic();
    try { socket.close(); } catch { /* closed */ }
    post('/api/agent/voice/end', { voice_session_id: id }, fetchImpl).catch(() => {});
    onClosed(reason);
  }

  /* The learner's view changed (R30): the server learns it and returns a "[context] …" note, which the model is
     given without answering it (turnComplete false). */
  async function sendContext(context) {
    if (closed || !context || typeof context !== 'object') return;
    let answer;
    try {
      answer = await post('/api/agent/voice/context', { voice_session_id: id, context }, fetchImpl);
    } catch (error) {
      if (error?.status === 404) end('server');
      return;
    }
    const note = String(answer?.note || '').trim();
    if (note && ready && !closed) send({ clientContent: { turns: [{ role: 'user', parts: [{ text: note }] }], turnComplete: false } });
  }

  return { end, interrupt: silence, sendContext };
}

/* A live voice turn written into a conversation thread (the Home thread or a Contextual panel's), through the
   same reducer a typed turn uses: the learner's words, Orena's words and the server's §4 events. A turn joins the
   thread when Orena answers - a cough the model let pass leaves nothing behind. */
export function voiceThread({ session, memory = null, notify = () => {}, persist = () => {}, lang = () => 'en' }) {
  let open = false;
  function ensure(heard) {
    if (open) return;
    open = true;
    if (String(heard || '').trim()) session.learner(String(heard).trim());
    else session.opening();
  }
  return {
    events(heard, list) {
      ensure(heard);
      for (const item of list || []) {
        if (!item?.event) continue;
        session.apply({ event: item.event, data: item.data || {} });
        if (item.event === 'memory_update') memory?.applyUpdate?.(item.data);
      }
      notify();
    },
    text(heard, said) {
      if (!String(said || '').trim()) return;
      ensure(heard);
      session.apply({ event: 'segment_end', data: { index: 0, lang: lang(), text: String(said).trim(), voice_style: 'neutral_explain' } });
      notify();
    },
    done() {
      if (!open) return;
      open = false;
      session.apply({ event: 'done', data: {} });
      persist();
      notify();
    },
  };
}
