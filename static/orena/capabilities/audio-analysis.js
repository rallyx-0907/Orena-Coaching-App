/* What a recording looks like and how its pitch moves, measured from the audio itself.

   The Speaking design draws the model's waveform beside the learner's and, for Chinese, the pitch
   of both as a tone contour (Orena Speaking 06 "Compare with model", 07 "Shadowing"). Nothing here
   judges anything: the bars are the signal's loudness, the contour is the fundamental frequency
   (YIN, de Cheveigné & Kawahara 2002) where the signal is voiced and nothing where it is not.
   Written verdicts ("you went flat") are not produced here or anywhere (D-076).

   The model and the learner go through the same code: the model line is fetched same-origin
   (`/api/speaking/model-audio/...`), the learner's take is this tab's own blob. */

/* Loudness per bucket, 0-1, relative to the loudest bucket. */
export function waveformBars(samples, count) {
  const n = Math.max(1, Math.floor(count));
  const bars = new Array(n).fill(0);
  if (!samples?.length) return bars;
  const size = samples.length / n;
  let peak = 0;
  for (let b = 0; b < n; b++) {
    const start = Math.floor(b * size);
    const end = Math.max(start + 1, Math.floor((b + 1) * size));
    let sum = 0;
    for (let i = start; i < end && i < samples.length; i++) sum += samples[i] * samples[i];
    bars[b] = Math.sqrt(sum / (end - start));
    peak = Math.max(peak, bars[b]);
  }
  return peak > 0 ? bars.map((value) => value / peak) : bars;
}

/* One frame's fundamental frequency by YIN, or null when the frame is unvoiced. */
function yinFrame(frame, sampleRate, minLag, maxLag, threshold) {
  const size = frame.length - maxLag;
  if (size <= 0) return null;
  let energy = 0;
  for (let i = 0; i < frame.length; i++) energy += frame[i] * frame[i];
  if (energy / frame.length < 1e-6) return null;
  const diff = new Float32Array(maxLag + 1);
  for (let lag = 1; lag <= maxLag; lag++) {
    let sum = 0;
    for (let i = 0; i < size; i++) {
      const d = frame[i] - frame[i + lag];
      sum += d * d;
    }
    diff[lag] = sum;
  }
  // Cumulative mean normalised difference.
  let running = 0;
  const cmnd = new Float32Array(maxLag + 1);
  cmnd[0] = 1;
  for (let lag = 1; lag <= maxLag; lag++) {
    running += diff[lag];
    cmnd[lag] = running > 0 ? (diff[lag] * lag) / running : 1;
  }
  for (let lag = minLag; lag <= maxLag; lag++) {
    if (cmnd[lag] < threshold) {
      while (lag + 1 <= maxLag && cmnd[lag + 1] < cmnd[lag]) lag++;
      // Parabolic interpolation around the minimum.
      const a = cmnd[lag - 1] ?? cmnd[lag];
      const b = cmnd[lag];
      const c = cmnd[lag + 1] ?? cmnd[lag];
      const shift = (a - c) / (2 * (a - 2 * b + c) || 1);
      return sampleRate / (lag + (Number.isFinite(shift) ? shift : 0));
    }
  }
  return null;
}

/* The pitch of a whole recording: one point every `hopMs`, `hz` null where unvoiced. */
export function pitchTrack(samples, sampleRate, { hopMs = 10, windowMs = 40, minHz = 70, maxHz = 450, threshold = 0.15 } = {}) {
  const track = [];
  if (!samples?.length || !sampleRate) return track;
  const hop = Math.max(1, Math.round((sampleRate * hopMs) / 1000));
  const minLag = Math.max(2, Math.floor(sampleRate / maxHz));
  const maxLag = Math.ceil(sampleRate / minHz);
  const windowSize = Math.max(Math.round((sampleRate * windowMs) / 1000), maxLag * 2);
  for (let start = 0; start + windowSize <= samples.length; start += hop) {
    const hz = yinFrame(samples.subarray(start, start + windowSize), sampleRate, minLag, maxLag, threshold);
    track.push({ t: start / sampleRate, hz: hz && hz >= minHz && hz <= maxHz ? hz : null });
  }
  return track;
}

/* Semitones relative to the recording's own median voiced pitch, so a low and a high voice
   draw comparable shapes. Isolated voiced frames (octave errors, clicks) are dropped. */
export function contour(track) {
  const voiced = track.filter((point) => point.hz);
  if (!voiced.length) return track.map((point) => ({ t: point.t, st: null }));
  const sorted = voiced.map((point) => point.hz).sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  return track.map((point, at) => {
    const neighbours = [track[at - 1], track[at + 1]].filter((item) => item?.hz).length;
    if (!point.hz || neighbours === 0) return { t: point.t, st: null };
    return { t: point.t, st: 12 * Math.log2(point.hz / median) };
  });
}

/* A contour as SVG polyline point strings in a `width` x `height` box: one string per voiced
   run, so a silence is a gap and never a line drawn across it. */
export function contourPolylines(points, { width = 1000, height = 200, span = null, range = 8, from = 0, to = null } = {}) {
  const end = to ?? (points.length ? points[points.length - 1].t : 0);
  const duration = Math.max(1e-6, (span ?? end) - from);
  const runs = [];
  let run = [];
  for (const point of points) {
    if (point.t < from || point.t > end) continue;
    if (point.st == null) {
      if (run.length > 1) runs.push(run);
      run = [];
      continue;
    }
    const x = ((point.t - from) / duration) * width;
    const y = height / 2 - (Math.max(-range, Math.min(range, point.st)) / range) * (height / 2 - 10);
    run.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  if (run.length > 1) runs.push(run);
  return runs.map((points) => points.join(' '));
}

/* Decode audio (a Blob, an ArrayBuffer or a same-origin URL) to mono samples. Browser only. */
export async function decodeAudio(input, { AudioContextCtor = globalThis.AudioContext || globalThis.webkitAudioContext, fetchImpl = globalThis.fetch } = {}) {
  if (typeof AudioContextCtor !== 'function') throw Error('audio decoding unsupported');
  const buffer =
    input instanceof ArrayBuffer
      ? input
      : typeof input === 'string'
        ? await (await fetchImpl(input, { credentials: 'same-origin' })).arrayBuffer()
        : await input.arrayBuffer();
  const context = new AudioContextCtor();
  try {
    const audio = await context.decodeAudioData(buffer.slice(0));
    const mono = new Float32Array(audio.length);
    for (let channel = 0; channel < audio.numberOfChannels; channel++) {
      const data = audio.getChannelData(channel);
      for (let i = 0; i < data.length; i++) mono[i] += data[i] / audio.numberOfChannels;
    }
    return { samples: mono, sampleRate: audio.sampleRate, duration: audio.duration };
  } finally {
    context.close?.().catch?.(() => {});
  }
}

/* Everything a view needs from one recording. */
export function analyse(decoded, { bars = 40 } = {}) {
  const track = pitchTrack(decoded.samples, decoded.sampleRate);
  return { duration: decoded.duration, bars: waveformBars(decoded.samples, bars), contour: contour(track) };
}
