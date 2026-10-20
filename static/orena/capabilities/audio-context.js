/* One AudioContext for the page's recording rooms, started inside the learner's tap.

   iOS Safari runs an AudioContext only when it was created or resumed during a user gesture. A context created
   after an await (the consent check, getUserMedia) stays `suspended`, so whatever it measures or processes is
   silence: the level meter read nothing and the silence auto-stop never fired (#439), and the noise-suppression
   graph recorded silence (#443). `tapAudioContext()` is called synchronously in the tap handler, before any await;
   everything after it (the recorder's processing graph, the level meter) reuses `sharedAudioContext()`. The shared
   context is never closed by a room: its users disconnect their own nodes. */

let shared = null;

function constructor() {
  return globalThis.AudioContext || globalThis.webkitAudioContext || null;
}

/* Call from the tap itself. Creates the context (48 kHz when the device allows it, which the noise suppressor
   needs) or resumes it; never awaits. Returns the context, or null where Web Audio is missing. */
export function tapAudioContext({ Ctor = constructor() } = {}) {
  try {
    if (typeof Ctor !== 'function') return null;
    if (!shared || shared.state === 'closed') {
      try {
        shared = new Ctor({ sampleRate: 48000 });
      } catch {
        shared = new Ctor();
      }
    }
    if (shared.state !== 'running') shared.resume?.()?.catch?.(() => {});
    return shared;
  } catch {
    return null;
  }
}

/* The context the last tap started, while it is usable. */
export function sharedAudioContext() {
  return shared && shared.state !== 'closed' ? shared : null;
}

/* Tests only. */
export function resetSharedAudioContext() {
  shared = null;
}
