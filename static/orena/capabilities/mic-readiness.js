/* Is the microphone actually working, and which one is it?

   Speaking and Shadowing ask a learner to talk into a device they cannot see
   the state of. "Nothing happened" then has at least four causes - no device,
   permission refused, the wrong input selected, or a level so low the take is
   silence - and the learner cannot tell them apart. This answers exactly that,
   in one line: the device by name, a live level, and whether it is ready.

   It is not a calibration wizard and adds no settings. It opens its own short
   stream, reports, and releases it; it never holds the microphone while the
   learner is not recording, and it never fabricates a level. */

const READY = 'ready';
const CHECKING = 'checking';
const DENIED = 'denied';
const NO_DEVICE = 'no_device';
const UNSUPPORTED = 'unsupported';

export const MIC_STATES = { READY, CHECKING, DENIED, NO_DEVICE, UNSUPPORTED };

/* What the capture chain actually negotiated. Reported rather than assumed,
   because a device that ignored a constraint is the difference between a clean
   take and an unusable one, and guessing here is how that goes unnoticed. */
export function trackFacts(stream) {
  const track = stream?.getAudioTracks?.()[0];
  if (!track) return null;
  const settings = track.getSettings?.() || {};
  return {
    label: track.label || '',
    sample_rate: settings.sampleRate ?? null,
    channel_count: settings.channelCount ?? null,
    echo_cancellation: settings.echoCancellation ?? null,
    noise_suppression: settings.noiseSuppression ?? null,
    auto_gain_control: settings.autoGainControl ?? null,
    device_id: settings.deviceId ? 'present' : '',
  };
}

/* A short listen, only to answer "is this working". `onLevel` receives a
   0-1 amplitude; `stop()` releases everything. */
export function watchMicrophone({
  mediaDevices = globalThis.navigator?.mediaDevices,
  AudioContextCtor = globalThis.AudioContext || globalThis.webkitAudioContext,
  onState = () => {},
  onLevel = () => {},
} = {}) {
  let stream = null;
  let context = null;
  let frame = 0;
  let stopped = false;

  const release = () => {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    for (const track of stream?.getTracks?.() || []) {
      try {
        track.stop();
      } catch {
        // A track already ended is already released.
      }
    }
    stream = null;
    if (context) {
      try {
        context.close();
      } catch {
        // Closing twice is not an error worth surfacing.
      }
      context = null;
    }
  };

  (async () => {
    if (!mediaDevices?.getUserMedia || typeof AudioContextCtor !== 'function') {
      onState({ state: UNSUPPORTED });
      return;
    }
    onState({ state: CHECKING });
    try {
      stream = await mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      const name = String(error?.name || '');
      onState({
        state: name === 'NotFoundError' || name === 'OverconstrainedError' ? NO_DEVICE : DENIED,
      });
      return;
    }
    if (stopped) return release();
    const facts = trackFacts(stream);
    onState({ state: READY, facts });
    try {
      context = new AudioContextCtor();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      const buffer = new Uint8Array(analyser.fftSize);
      const tick = () => {
        if (stopped) return;
        analyser.getByteTimeDomainData(buffer);
        let peak = 0;
        for (const value of buffer) peak = Math.max(peak, Math.abs(value - 128) / 128);
        onLevel(peak);
        frame = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // Without a level meter the state is still worth knowing.
    }
  })();

  return {
    stop() {
      stopped = true;
      release();
    },
  };
}
