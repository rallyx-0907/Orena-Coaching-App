// Orena voice spike (Track 0): the browser side of a Gemini Live session.
// The API key never reaches this page: the local server mints a one-use ephemeral token, and the WebSocket opens
// with it (BidiGenerateContentConstrained). No audio is stored; only numbers and transcripts can be exported.

const WS = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained";
const PREFERRED = ["gemini-3.8-live", "gemini-2.5-flash-native-audio-preview-12-2025"];
// Prebuilt voices (the TTS set), with the character Google gives each: warm and friendly first.
const VOICES = [
  ["Sulafat", "ấm"], ["Achird", "thân thiện"], ["Vindemiatrix", "dịu"], ["Aoede", "nhẹ nhàng"], ["Leda", "trẻ"],
  ["Kore", "chắc"], ["Puck", "vui"], ["Zephyr", "sáng"], ["Charon", "rõ ràng"], ["Orus", "vững"], ["Fenrir", "hào hứng"],
];

const PERSONA = `You are Orena, a warm, clever friend who helps Vietnamese speakers learn English and Chinese.
Speak with a warm, natural voice, like a smart friend - never a presenter, never a salesperson.
Answer in the language the learner speaks to you. In Vietnamese call yourself "mình" and the learner "bạn"; in English
"I" and "you"; in Chinese "我" and "你". Keep turns short: one to three sentences, then let them talk. No empty praise;
say only what is true. When you say a word in the language they are learning, say it clearly, then go on at your
normal pace. Say every Chinese word in Mandarin with its tones, as its pinyin reads (学 is xué), never in its
Sino-Vietnamese (Hán-Việt) reading, even inside a Vietnamese sentence; if the Hán-Việt reading helps, say it after,
as a separate word ("học").
Voice style, sentence by sentence: before each sentence, silently choose one style and speak that sentence in it -
neutral_explain (clear, even), warm_encourage (warm, smiling), gentle_correct (soft, unhurried, never scolding),
celebrate (bright, a little faster), slow_model (slow and precise: a word or sentence for them to repeat).
Never say a style's name aloud.`;
const READ_MODE = `
Test mode: when a message holds sentences tagged like "[warm_encourage] text", read each sentence aloud exactly as
written, in its tagged style, adding nothing and saying no tag.`;

const $ = (id) => document.getElementById(id);
const state = {
  ws: null, ready: false, model: "", playCtx: null, nextTime: 0, sources: new Set(),
  micCtx: null, micStream: null, micNode: null,
  speaking: false, loudAt: 0, segmentAt: 0, speechEndAt: 0, textAt: 0, bargeAt: 0,
  turn: null, rows: [], inText: "", outText: "",
};

function status(text, kind = "") { const el = $("status"); el.textContent = text; el.className = kind; }
function log(kind, text) {
  const p = document.createElement("div"); p.className = kind; p.textContent = text; $("log").append(p);
  $("log").scrollTop = $("log").scrollHeight;
}
function language(text) {
  // Every language heard in the answer, in order of weight: a mixed answer ("it's 朋友") reads "en·zh".
  const zh = (text.match(/[一-鿿]/g) || []).length;
  const vi = /[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]/i.test(text);
  const latin = (text.match(/[a-z]/gi) || []).length;
  const found = [];
  if (latin) found.push([vi ? "vi" : "en", latin]);
  if (zh) found.push(["zh", zh * 2]);
  return found.sort((a, b) => b[1] - a[1]).map(([name]) => name).join("·");
}

async function loadModels() {
  const answer = await fetch("/api/models").then((r) => r.json()).catch(() => ({ error: "server unreachable" }));
  const select = $("model");
  select.innerHTML = "";
  const models = answer.models || [];
  const ordered = [...PREFERRED.filter((m) => models.includes(m)), ...models.filter((m) => !PREFERRED.includes(m))];
  for (const m of ordered) select.add(new Option(PREFERRED.includes(m) ? `${m}  ★` : m, m));
  const missing = PREFERRED.filter((m) => !models.includes(m));
  if (answer.error) status(`Không đọc được danh sách model: ${answer.error}`, "bad");
  else if (missing.length) status(`Key này không mở được: ${missing.join(", ")}. Còn ${models.length} model Live.`, "bad");
  else status(`${models.length} model Live dùng được.`, "ok");
  for (const [name, feel] of VOICES) $("voice").add(new Option(`${name} (${feel})`, name));
}

// --- playback: 24 kHz PCM from the server, scheduled back to back; dropped at once on an interruption -------------

function play(base64, mimeType) {
  const rate = Number((/rate=(\d+)/.exec(mimeType || "") || [])[1] || 24000);
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const pcm = new Int16Array(bytes.buffer, 0, bytes.byteLength >> 1);
  const buffer = state.playCtx.createBuffer(1, pcm.length, rate);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;
  const source = state.playCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(state.playCtx.destination);
  const at = Math.max(state.nextTime, state.playCtx.currentTime + 0.03);
  source.start(at);
  state.nextTime = at + buffer.duration;
  state.sources.add(source);
  source.onended = () => state.sources.delete(source);
}

function stopPlayback() {
  for (const s of state.sources) { try { s.stop(); } catch { /* already ended */ } }
  state.sources.clear();
  state.nextTime = 0;
}

const playing = () => state.sources.size > 0;

// --- one row per model turn ---------------------------------------------------------------------------------------

function openTurn() {
  // From the last loud moment of what was said (the page's own measure), or from Send for a typed line.
  const spoken = state.speaking && state.loudAt - state.segmentAt >= SPEECH_MS ? state.loudAt : state.speechEndAt;
  const trigger = state.textAt && state.textAt > spoken ? "gõ" : "nói";
  const from = trigger === "gõ" ? state.textAt : spoken;
  state.turn = { n: state.rows.length + 1, model: state.model, trigger, first_audio_ms: from ? Math.round(performance.now() - from) : null,
                 interrupted: false, barge_to_stop_ms: null, lang: "", said: "", heard: trigger === "gõ" ? state.typed : state.inText.trim(),
                 quality: "", note: "" };  // prettier-ignore
  if (state.turn.first_audio_ms !== null && state.turn.first_audio_ms < 150) {
    state.turn.first_audio_ms = null; // the mic still heard something (noise, or Orena through speakers): not a measure
  }
  state.inText = "";
}

function closeTurn() {
  if (!state.turn) return;
  state.turn.said = state.outText.trim();
  state.turn.lang = language(state.turn.said);
  if (state.turn.said) log("orena", `Orena: ${state.turn.said}`);
  state.rows.push(state.turn);
  renderRow(state.turn);
  state.turn = null; state.outText = ""; state.bargeAt = 0;
}

function renderRow(row) {
  const tr = document.createElement("tr");
  const quality = document.createElement("select");
  for (const v of ["", "1", "2", "3", "4", "5"]) quality.add(new Option(v ? `${v}/5` : "—", v));
  quality.onchange = () => { row.quality = quality.value; };
  const note = document.createElement("input");
  note.type = "text"; note.placeholder = "phát âm, ngữ điệu, giọng…"; note.oninput = () => { row.note = note.value; };
  const cells = [row.n, row.model, row.trigger, row.first_audio_ms ?? "—", row.interrupted ? "có" : "", row.barge_to_stop_ms ?? "", row.lang];
  for (const c of cells) { const td = document.createElement("td"); td.textContent = c; tr.append(td); }
  for (const el of [quality, note]) { const td = document.createElement("td"); td.append(el); tr.append(td); }
  $("rows").append(tr);
}

// --- the session --------------------------------------------------------------------------------------------------

async function connect() {
  $("connect").disabled = true;
  status("Xin token…");
  const token = await fetch("/api/token", { method: "POST" }).then((r) => r.json()).catch(() => ({ error: "server unreachable" }));
  if (!token.token) { status(`Không lấy được token: ${token.error}`, "bad"); $("connect").disabled = false; return; }
  state.model = $("model").value;
  state.playCtx = state.playCtx || new AudioContext({ sampleRate: 24000 });
  await state.playCtx.resume();
  const ws = new WebSocket(`${WS}?access_token=${encodeURIComponent(token.token)}`);
  state.ws = ws;
  ws.onopen = () => {
    const generationConfig = {
      responseModalities: ["AUDIO"],
      speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: $("voice").value } } },
    };
    if ($("affective").checked) generationConfig.enableAffectiveDialog = true;
    ws.send(JSON.stringify({ setup: {
      model: `models/${state.model}`,
      generationConfig,
      systemInstruction: { parts: [{ text: PERSONA + ($("mode").value === "read" ? READ_MODE : "") }] },
      inputAudioTranscription: {},
      outputAudioTranscription: {},
    } }));
    status("Đang thiết lập phiên…");
  };
  ws.onmessage = async (event) => {
    const text = typeof event.data === "string" ? event.data : await event.data.text();
    handle(JSON.parse(text));
  };
  ws.onclose = (event) => {
    state.ready = false;
    status(`Phiên đóng${event.code !== 1000 ? ` (${event.code}${event.reason ? `: ${event.reason}` : ""})` : ""}.`, event.code === 1000 ? "" : "bad");
    stopMic(); closeTurn();
    $("connect").disabled = false; $("mic").disabled = true; $("send").disabled = true; $("disconnect").disabled = true;
  };
}

function handle(msg) {
  if (msg.setupComplete) {
    state.ready = true;
    status(`Đã kết nối: ${state.model}, giọng ${$("voice").value}. Bật mic hoặc gõ câu.`, "ok");
    $("mic").disabled = false; $("send").disabled = false; $("disconnect").disabled = false;
    log("sys", `— phiên mới: ${state.model} · ${$("voice").value} · ${$("mode").value}`);
    return;
  }
  if (msg.goAway) log("sys", `server sắp đóng phiên (${msg.goAway.timeLeft || "?"})`);
  const content = msg.serverContent;
  if (!content) return;
  if (content.inputTranscription?.text) state.inText += content.inputTranscription.text;
  if (content.outputTranscription?.text) state.outText += content.outputTranscription.text;
  if (content.interrupted) {
    stopPlayback();
    if (state.turn) {
      state.turn.interrupted = true;
      if (state.bargeAt) state.turn.barge_to_stop_ms = Math.round(performance.now() - state.bargeAt);
    }
    state.bargeAt = 0;
    closeTurn();
  }
  for (const part of content.modelTurn?.parts || []) {
    if (part.inlineData?.data) {
      if (!state.turn) {
        if (state.inText.trim()) log("you", `Bạn: ${state.inText.trim()}`);
        openTurn();
      }
      play(part.inlineData.data, part.inlineData.mimeType);
    }
  }
  if (content.turnComplete) closeTurn();
}

// --- the microphone -----------------------------------------------------------------------------------------------

const LOUD = 0.02; // the page's own speech threshold (timing only; the server's VAD decides the turn)
const SILENCE_MS = 500;
const SPEECH_MS = 250;

async function startMic() {
  state.micStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
  });
  state.micCtx = new AudioContext();
  await state.micCtx.audioWorklet.addModule("/capture.js");
  const source = state.micCtx.createMediaStreamSource(state.micStream);
  state.micNode = new AudioWorkletNode(state.micCtx, "orena-capture");
  state.micNode.port.onmessage = ({ data }) => {
    const now = performance.now();
    $("level").firstElementChild.style.width = `${Math.min(100, data.level * 600)}%`;
    if (data.level > LOUD) {
      if (!state.speaking) state.segmentAt = now;
      state.speaking = true; state.loudAt = now;
      // Speaking over Orena for 250 ms: a barge-in, timed from when it began.
      if (playing() && !state.bargeAt && now - state.segmentAt >= SPEECH_MS) state.bargeAt = state.segmentAt;
    } else if (state.speaking && now - state.loudAt > SILENCE_MS) {
      state.speaking = false;
      if (state.loudAt - state.segmentAt >= SPEECH_MS) state.speechEndAt = state.loudAt; // the end of what was said
    }
    if (state.ready) {
      const bytes = new Uint8Array(data.pcm);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      state.ws.send(JSON.stringify({ realtimeInput: { audio: { mimeType: "audio/pcm;rate=16000", data: btoa(binary) } } }));
    }
  };
  source.connect(state.micNode);
  $("mic").textContent = "Tắt mic";
}

function stopMic() {
  state.micStream?.getTracks().forEach((t) => t.stop());
  state.micCtx?.close();
  state.micStream = state.micCtx = state.micNode = null;
  $("mic").textContent = "Bật mic";
  $("level").firstElementChild.style.width = "0";
}

function sendText() {
  const text = $("text").value.trim();
  if (!text || !state.ready) return;
  if (playing()) { state.bargeAt = performance.now(); } // typing over Orena counts as a barge-in too
  state.textAt = performance.now();
  state.inText = "";
  state.typed = text;
  log("you", `Bạn (gõ): ${text}`);
  state.ws.send(JSON.stringify({ realtimeInput: { text } }));
  $("text").value = "";
}

function exportRows() {
  const data = { exported_at: new Date().toISOString(), note: "Track 0 voice spike - test data only, no audio", rows: state.rows };
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: "orena-voice-spike.json" });
  a.click();
  URL.revokeObjectURL(url);
}

$("connect").onclick = connect;
$("disconnect").onclick = () => state.ws?.close(1000);
$("mic").onclick = () => (state.micStream ? stopMic() : startMic().catch((e) => status(`Mic: ${e.message}`, "bad")));
$("send").onclick = sendText;
$("text").onkeydown = (e) => { if (e.key === "Enter") sendText(); };
$("export").onclick = exportRows;
loadModels();
