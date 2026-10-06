/* Contextual Orena (OA2, frame 55, D1 §6 / E5 §6): the panel every "Ask Orena" opens, attached to
   whatever the learner was looking at. Registers itself with `shell/agent-bridge.js`'s
   `setAgentHandler` (imported for its side effect by shell/agent-bridge.js itself, so every screen
   that already calls `askOrena()` reaches this without importing this folder directly - D-086 "the
   agent panel ... is a later slice").

   Each context gets its own short-lived thread, never restored from device memory and never
   written to it: AGENT_CONTRACT names only Home's thread as persisted; §3.2 itself only permits
   (never requires) reusing an opening turn "within a session", and the source's own `openOrena()`
   always starts a fresh `orenaMsgs` on every call. Coach notes and the address note are still read
   from and written to the one shared agent/memory.js store (§5.4/§5.6 are learner-scoped, not
   thread-scoped).

   One sheet is open at a time (kit/overlay.js), so the microphone sheet a first recording needs
   replaces this panel. When the learner answers it the panel opens again with the very same thread
   (`carry`), in voice mode - nothing they said or were told is lost. */
import { openSheet } from '../../kit/overlay.js';
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { intelChip } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { langAttr } from '../../kit/lang.js';
import { toast } from '../../kit/toast.js';
import { shellCopy } from '../../copy/shell.js';
import { createSession, buildRequest } from '../../agent/session.js';
import { turn } from '../../agent/transport.js';
import { supportedIntents } from '../../agent/intents.js';
import { toContractLang, fromContractLang } from '../../agent/contract.js';
import { sharedMemory } from './memory-store.js';
import { orenaPresent, onOrenaPresence } from '../../agent/presence.js';
import { languages } from '../../copy/index.js';
import { context as shellContext } from '../../shell/context.js';
import { refreshLearningLanguage } from './language-sync.js';
import { setAgentHandler } from '../../shell/agent-bridge.js';
import { t } from './copy.js';
import { contextParts, latestSuggestions, thinkingText } from './model.js';
import { messageMarkup } from './thread.js';
import { runOffered } from './actions.js';
import { keepFocus } from './focus.js';
import { createVoiceEngine, voiceRowMarkup, bindVoiceRow } from './voice.js';
import { voiceSessionBody, voiceThread, chosenVoice } from '../../agent/live-voice.js';
import { builtScreens, createOrenaDispatcher, requestLanguages } from './dispatcher-setup.js';

/* The context pill's label: the selected item's own text (marked with the language it is in) and
   its kind, or the caller's label, or the place's name. */
function ctxLabelMarkup(context) {
  const { text, lang, kind } = contextParts(context, t);
  if (!text && !kind) return '';
  const language = langAttr(lang ? fromContractLang(lang) : shellContext().language);
  return html`${text ? html`<span lang="${language}">${text}</span>` : ''}${text && kind ? ' · ' : ''}${kind}`;
}

export async function openOrenaPanel(context = {}, carry = null) {
  if (!orenaPresent()) return null;
  await useStyles('screens/orena/orena.css');
  const memory = sharedMemory();
  const session = carry?.session || createSession();
  const dispatcher = createOrenaDispatcher();

  let sheetEl = null;
  let handle = null;
  let voiceMode = Boolean(context.voice) || Boolean(carry?.voice);
  let voiceEngine = null;
  let voiceShown = false;
  let draft = '';
  let consumedUnsent = '';
  let closed = false;
  const ranActions = carry?.ranActions || new Set();
  const controllers = new Set();

  function paint() {
    if (!sheetEl || closed) return;
    const state = session.state();
    const supported = dispatcher.supported();
    if (state.unsent && state.unsent !== consumedUnsent) {
      consumedUnsent = state.unsent;
      draft = state.unsent;
      voiceMode = false;
      if (state.unsentWhy === 'language') toast(t('unsentNotice'), { iconName: 'circle-alert' });
    }
    const label = ctxLabelMarkup(context);
    keepFocus(sheetEl, () =>
      mount(
        sheetEl,
        html`<div class="s-orena-panel__head">
            <div class="s-orena-panel__who">${intelChip({ size: 36, mark: 29 })}<div class="s-orena-panel__title">Orena</div></div>
            <button type="button" class="o-iconbtn o-iconbtn--close" data-sheet-close aria-label="${shellCopy('close')}">${raw(icon('x', { size: 17 }))}</button>
          </div>
          ${label ? html`<div class="s-orena-panel__ctxwrap"><div class="s-orena-panel__ctx">${raw(icon('quote', { size: 16 }))}<span class="s-orena-panel__ctxlabel">${label}</span></div></div>` : ''}
          <div class="s-orena-panel__thread" data-scroll-region>
            ${state.messages.map((message) => messageMarkup(message, { surface: 'panel', ranActions, supported }))}
            ${state.thinking ? html`<div class="s-orena-panel__thinking">${intelChip({ size: 30, mark: 24, state: 'thinking' })}${thinkingText(state.tool, t('thinkingLabel'))}</div>` : ''}
          </div>
          ${startersMarkup(state)}
          <div class="s-orena-panel__foot">${voiceMode ? html`<div class="s-orena-panel__voicepill">${voiceRowMarkup(voiceEngine ? voiceEngine.state() : { phase: 'idle', heard: '', speakOn: true }, { fresh: !voiceShown })}</div>` : typingMarkup(state)}</div>`,
      ),
    );
    voiceShown = voiceMode;
    bind();
    const thread = sheetEl.querySelector('[data-scroll-region]');
    if (thread) thread.scrollTop = thread.scrollHeight;
  }

  function startersMarkup(state) {
    const suggestions = latestSuggestions(state.messages);
    if (!suggestions.length) return '';
    return html`<div class="s-orena-panel__starters">${suggestions.map((s) => html`<button type="button" class="s-orena-panel__starter" data-starter="${s.label}">${s.label}</button>`)}</div>`;
  }

  function typingMarkup(state) {
    const busy = state.thinking;
    return html`<div class="s-orena-panel__typing">
      <input type="text" class="s-orena-panel__input" data-input placeholder="${t('askFollowUpPlaceholder')}" value="${draft}">
      <button type="button" class="s-orena-panel__voicebtn" data-to-voice aria-label="${shellCopy('talkToOrena')}" ${busy ? raw('disabled') : ''}>${raw(icon('mic', { size: 18 }))}</button>
      <button type="button" class="s-orena-panel__send" data-send aria-label="${t('sendLabel')}" ${busy ? raw('disabled') : ''}>${raw(icon('arrow-up', { size: 18 }))}</button>
    </div>`;
  }

  function bind() {
    sheetEl.querySelector('[data-sheet-close]')?.addEventListener('click', () => handle.close());
    sheetEl.querySelectorAll('[data-action-id]').forEach((button) =>
      button.addEventListener('click', () => runOffered({ dispatcher, action: findAction(button.dataset.actionId), ranActions, repaint: paint })),
    );
    sheetEl.querySelectorAll('[data-retry]').forEach((button) => button.addEventListener('click', retry));
    sheetEl.querySelectorAll('[data-starter]').forEach((button) => button.addEventListener('click', () => void runTurn('message', button.dataset.starter)));
    const input = sheetEl.querySelector('[data-input]');
    if (input) {
      input.addEventListener('input', () => {
        draft = input.value;
      });
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.isComposing) submitTyped();
      });
    }
    sheetEl.querySelector('[data-send]')?.addEventListener('click', submitTyped);
    sheetEl.querySelector('[data-to-voice]')?.addEventListener('click', () => {
      voiceMode = true;
      startVoice();
      paint();
    });
    if (voiceMode) bindVoiceRow(sheetEl, voiceEngine || startVoice(), { onClose: endVoice });
  }

  function findAction(id) {
    for (const message of session.state().messages) {
      if (message.role !== 'orena') continue;
      const found = (message.actions || []).find((a) => a.id === id);
      if (found) return found;
    }
    return null;
  }

  function submitTyped() {
    const input = sheetEl.querySelector('[data-input]');
    const text = String(input?.value || '').trim();
    if (!text || session.state().thinking) return;
    draft = '';
    void runTurn('message', text);
  }

  /* §4.1 `retry`: the last turn again as a new request, the learner's own tap. */
  function retry() {
    const messages = session.state().messages;
    const before = messages.at(-2);
    if (before?.role === 'learner') void runTurn('message', before.text, { retry: true });
    else void runTurn('open', '', { retry: true });
  }

  function endVoice() {
    voiceEngine?.dispose();
    voiceEngine = null;
    voiceMode = false;
    paint();
  }

  function abortTurn() {
    for (const controller of controllers) controller.abort();
  }

  function startVoice() {
    if (voiceEngine) return voiceEngine;
    voiceEngine = createVoiceEngine({
      ctx: { isCurrent: () => true },
      send: (text) => runTurn('message', text),
      // Live voice (§9 mode A) about this panel's context, written into this panel's thread.
      liveVoice: () => {
        const support = toContractLang(languages().support);
        const body = voiceSessionBody(buildRequest({
          trigger: 'message',
          context,
          languages: requestLanguages(),
          sessionId: session.sessionId(),
          client: { supported_actions: dispatcher.supported(), supported_intents: supportedIntents(builtScreens()) },
          notes: memory.requestNotes(),
          address: memory.addressFor(support),
        }), { voice: chosenVoice() });
        return {
          body,
          thread: voiceThread({ session, memory, notify: paint, lang: () => support }),
          // A place the learner asked for by voice opens at once (R29), through the same runner as a tap.
          open: (action) => runOffered({ dispatcher, action, ranActions, repaint: paint }),
        };
      },
      abort: abortTurn,
      // The mic sheet took this panel's place; when it has been answered, the panel comes back.
      resume: () => void openOrenaPanel(context, { session, ranActions, voice: true }),
      onTextOnly: endVoice,
      onChange: paint,
    });
    voiceEngine.main(); // tapping the mic (or opening already in voice mode) starts listening now
    return voiceEngine;
  }

  async function runTurn(trigger, message, { retry: again = false } = {}) {
    if (closed || session.state().thinking) return null;
    const support = toContractLang(languages().support);
    const address = memory.addressFor(support);
    const request = buildRequest({
      trigger,
      message: message || '',
      context,
      languages: requestLanguages(),
      sessionId: session.sessionId(),
      client: { supported_actions: dispatcher.supported(), supported_intents: supportedIntents(builtScreens()) },
      notes: memory.requestNotes(),
      address,
    });
    if (again) session.retry();
    else if (trigger === 'open') session.opening();
    else session.learner(message);
    paint();
    const controller = new AbortController();
    controllers.add(controller);
    let cancelled = false;
    controller.signal.addEventListener('abort', () => {
      cancelled = true;
    });
    try {
      for await (const item of turn(request, { signal: controller.signal })) {
        session.apply(item);
        if (item.event === 'memory_update') memory.applyUpdate(item.data);
        if (item.event === 'language_mismatch') void refreshLearningLanguage();
        paint();
        if (session.state().absent) {
          handle?.close();
          return null;
        }
      }
    } finally {
      controllers.delete(controller);
    }
    // The learner's own stop (§2.1 429 "the learner may cancel the wait").
    if (cancelled) session.cancel();
    paint();
    return cancelled ? null : session.lastReply();
  }

  const unsubscribePresence = onOrenaPresence(() => {
    if (!orenaPresent()) handle?.close();
  });

  handle = openSheet({
    label: 'Orena',
    className: 's-orena-panel',
    full: true, // E5 §6.2: 55's root sets height:var(--sheet-maxh) in addition to max-height (53/57 do not)
    render(element, sheetHandle) {
      sheetEl = element;
      handle = sheetHandle;
      paint();
      // A control that is itself a question opens on it (LEX-022); otherwise Orena opens with its greeting.
      const asked = String(context.ask || '').trim();
      if (!carry) void runTurn(asked ? 'message' : 'open', asked);
      return () => {
        closed = true;
        unsubscribePresence();
        voiceEngine?.dispose();
        abortTurn();
      };
    },
  });
  return handle;
}

setAgentHandler((context) => openOrenaPanel(context));
