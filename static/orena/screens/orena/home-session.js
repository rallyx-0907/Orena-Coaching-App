/* Orena Home's one ambient conversation (AGENT_CONTRACT §1 "device memory for conversation"): a
   module-level singleton so the Home route (screen.js) and the rail's full-screen voice mode
   (voice.js, reachable from any route on a desk) read and write the very same thread, never two
   independent ones. The Contextual panel (panel.js) does not use this - each context it opens gets
   its own short-lived, unpersisted thread (panel.js's own module comment explains why).

   Owns: the turn lifecycle (send, stream, persist), the opening turn (§3.2, sent once per browser
   session while the device's thread is empty), coach-note upserts from `memory_update`, and the
   one dispatcher every Orena action button runs through. */
import { createSession, buildRequest } from '../../agent/session.js';
import { voiceSessionBody, voiceThread } from '../../agent/live-voice.js';
import { turn } from '../../agent/transport.js';
import { sharedMemory } from './memory-store.js';
import { supportedIntents } from '../../agent/intents.js';
import { toContractLang } from '../../agent/contract.js';
import { href } from '../../shell/routes.js';
import { languages } from '../../copy/index.js';
import { refreshLearningLanguage } from './language-sync.js';
import { builtScreens, createOrenaDispatcher, requestLanguages } from './dispatcher-setup.js';

let instance = null;

function create() {
  const memory = sharedMemory();
  const session = createSession();
  session.restore(memory.thread());
  const dispatcher = createOrenaDispatcher();
  return {
    session,
    memory,
    dispatcher,
    listeners: new Set(),
    controllers: new Set(),
    sending: false,
    openingSent: false,
    persisted: memory.thread().length,
  };
}

export function getHomeSession() {
  if (!instance) instance = create();
  return instance;
}

function notify() {
  for (const listener of instance.listeners) listener(instance.session.state());
}

/* Only fully-finished messages join device memory - a message still streaming when the learner
   navigates away is not "sent" yet from the thread's point of view, and `session.apply`'s own
   pop-on-`unsent`/`absent` already removes a learner message that never got a reply before this
   ever sees it. */
function syncPersistence() {
  const messages = instance.session.state().messages;
  while (instance.persisted < messages.length) {
    const message = messages[instance.persisted];
    const last = instance.persisted === messages.length - 1;
    if (message.role === 'orena' && !message.done) break;
    // An errored reply is not the learner's conversation: never stored, and while it is the last
    // message it holds the line so a retry (which removes it) leaves nothing behind.
    if (message.role === 'orena' && message.error) {
      if (last) break;
      instance.persisted += 1;
      continue;
    }
    instance.memory.appendMessage(message.role === 'learner' ? { role: 'learner', text: message.text } : message);
    instance.persisted += 1;
  }
}

async function runTurn(trigger, message, { retry = false } = {}) {
  const inst = getHomeSession();
  if (inst.sending) return;
  inst.sending = true;
  const support = toContractLang(languages().support);
  const address = inst.memory.addressFor(support);
  const request = buildRequest({
    trigger,
    message,
    context: { surface: 'orena.home' },
    languages: requestLanguages(),
    sessionId: inst.session.sessionId(),
    client: { supported_actions: inst.dispatcher.supported(), supported_intents: supportedIntents(builtScreens()) },
    notes: inst.memory.requestNotes(),
    address,
  });
  if (retry) inst.session.retry();
  else if (trigger === 'open') inst.session.opening();
  else inst.session.learner(message);
  notify();
  const controller = new AbortController();
  inst.controllers.add(controller);
  let cancelled = false;
  controller.signal.addEventListener('abort', () => {
    cancelled = true;
  });
  try {
    for await (const item of turn(request, { signal: controller.signal })) {
      inst.session.apply(item);
      if (item.event === 'memory_update') inst.memory.applyUpdate(item.data);
      if (item.event === 'language_mismatch') void refreshLearningLanguage();
      notify();
    }
  } finally {
    inst.controllers.delete(controller);
    inst.sending = false;
    // The learner's own stop (§2.1 429 "the learner may cancel the wait"): no closing event will
    // ever arrive for this turn, so the reducer is told it is over.
    if (cancelled) inst.session.cancel();
    syncPersistence();
    notify();
  }
  return cancelled ? null : inst.session.lastReply();
}

export function subscribeHome(listener) {
  const inst = getHomeSession();
  inst.listeners.add(listener);
  listener(inst.session.state());
  return () => inst.listeners.delete(listener);
}

export function homeState() {
  return getHomeSession().session.state();
}

export function homeDispatcher() {
  return getHomeSession().dispatcher;
}

/* AGENT_CONTRACT §3.2: sent once, while the device's thread starts empty. Safe to call from more
   than one mounted surface (Home's screen and the rail's full-screen voice can both be open) -
   the `openingSent` guard makes every call after the first a no-op. */
export function ensureOpening() {
  const inst = getHomeSession();
  if (inst.openingSent || inst.sending || inst.session.state().messages.length) return;
  inst.openingSent = true;
  runTurn('open', '');
}

export function sendHomeMessage(text) {
  const message = String(text || '').trim();
  if (!message) return;
  runTurn('message', message);
}

/* §4.1 `retry`: the last turn again, as a new request - the learner's own tap, never automatic. */
export function retryHome() {
  const messages = getHomeSession().session.state().messages;
  const before = messages.at(-2);
  if (before?.role === 'learner') runTurn('message', before.text, { retry: true });
  else runTurn('open', '', { retry: true });
}

/* Same send, awaited to its finished reply - what voice.js's engine needs to know what to speak. */
export async function sendHomeTurn(text) {
  const message = String(text || '').trim();
  if (!message) return null;
  return runTurn('message', message);
}

/* Ends the turn in flight - the learner's stop while Orena is thinking or waiting out a 429. */
export function abortHome() {
  if (!instance) return;
  for (const controller of instance.controllers) controller.abort();
}

/* "Type instead" from full-screen voice lands on Home with the cursor in the box (the source's
   `voiceType`): asked before the route mounts, taken once by the screen that has the box. */
let composerFocusWanted = false;

export function requestComposerFocus() {
  composerFocusWanted = true;
}

export function takeComposerFocus() {
  const wanted = composerFocusWanted;
  composerFocusWanted = false;
  return wanted;
}

export { href };

/* Live voice on Home (§9 mode A): the session body is this thread's turn body without a message, and the voice
   turns are written into this same thread and device memory. */
export function homeLiveVoice() {
  const inst = getHomeSession();
  const support = toContractLang(languages().support);
  const body = voiceSessionBody(buildRequest({
    trigger: 'message',
    context: { surface: 'orena.home' },
    languages: requestLanguages(),
    sessionId: inst.session.sessionId(),
    client: { supported_actions: inst.dispatcher.supported(), supported_intents: supportedIntents(builtScreens()) },
    notes: inst.memory.requestNotes(),
    address: inst.memory.addressFor(support),
  }));
  const thread = voiceThread({ session: inst.session, memory: inst.memory, notify, persist: syncPersistence, lang: () => support });
  return { body, thread };
}

