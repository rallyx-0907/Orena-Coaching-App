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

/* The session body is a turn body without a message (§9). */
export function voiceSessionBody(turnRequest) {
  const { trigger, message, ...rest } = turnRequest || {};
  return { contract_version: CONTRACT_VERSION, ...rest };
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
    await audio.input.audioWorklet.addModule(WORKLET_URL);
    if (closed) return stopMic();
    source = audio.input.createMediaStreamSource(stream);
    worklet = new AudioWorkletNode(audio.input, 'orena-pcm16-capture');
    worklet.port.onmessage = (event) => {
      if (ready && !closed) send({ realtimeInput: { audio: { data: toBase64(event.data), mimeType: 'audio/pcm;rate=16000' } } });
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
      answer = await post('/api/agent/voice/tool', { voice_session_id: id, calls, heard }, fetchImpl);
    } catch (error) {
      if (error?.status === 404) return end('server');
      answer = { responses: calls.map((call) => ({ id: call.id, name: call.name, response: { error: 'unavailable' } })), events: [] };
    }
    if (closed) return;
    if (Array.isArray(answer?.events) && answer.events.length) onEvents(answer.events);
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
    silence();
    stopMic();
    try { socket.close(); } catch { /* closed */ }
    post('/api/agent/voice/end', { voice_session_id: id }, fetchImpl).catch(() => {});
    onClosed(reason);
  }

  return { end, interrupt: silence };
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
