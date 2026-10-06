/* Orena Home (OA1, frame 11, D1 §6) - a browsing place (shell/routes.js `orena.focus: false`), the
   ambient assistant thread every learner can return to. Real data only: the thread and its coach
   notes are device memory (agent/memory.js), replies come from the server's agent where it is on
   (agent/transport.js, AGENT_CONTRACT §2.1; the contract mock only when the address asks), and
   every action button runs through the one dispatcher (agent/dispatcher.js) against the app's real
   APIs. The frame's "last active: Listening, 2 h ago" clause has no backing data anywhere in this
   build (model.js's `homeSubtitle` doc comment) and is dropped, not invented (rule 40). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { intelChip } from '../../kit/brand.js';
import { useStyles } from '../../kit/styles.js';
import { toast } from '../../kit/toast.js';
import { shellCopy } from '../../copy/shell.js';
import { onContext } from '../../shell/context.js';
import { orenaPresent, onOrenaPresence } from '../../agent/presence.js';
import { t } from './copy.js';
import { homeSubtitle, latestSuggestions, thinkingText } from './model.js';
import { messageMarkup } from './thread.js';
import { runOffered } from './actions.js';
import { dockVoice, undockVoice } from './voice-dock.js';
import { keepFocus } from './focus.js';
import { createVoiceEngine, voiceRowMarkup, bindVoiceRow } from './voice.js';
import { subscribeHome, homeState, homeDispatcher, ensureOpening, sendHomeMessage, sendHomeTurn, retryHome, abortHome, takeComposerFocus, homeLiveVoice } from './home-session.js';
// Side-effect only: registers the Contextual Orena panel with shell/agent-bridge.js
// (shell/agent-bridge.js's own dynamic import already does this at boot - this import exists so
// scripts/validate_browser_esm_graph.mjs, which only walks static imports from each screen.js
// entry, also parses and links panel.js and everything it imports). memory-sheet.js has the same
// need and no route or button of its own yet (no frame in this pass draws an entry point for it -
// see docs/project/UI_BACKEND_GAPS.md); kept reachable here for the same gate coverage until
// Settings' Plan & privacy tab wires a real one.
import './panel.js';
import './memory-sheet.js';

/* The shell rail's own `{{ tlLabel }}` (shell/frame.js's un-exported `learningLabel`), reproduced
   here rather than imported: frame.js draws it inline and exports no helper. */
function languageLabel(context) {
  const language = shellCopy(context.language === 'zh' ? 'lang_zh' : 'lang_en');
  return context.level ? shellCopy('learningLabel', { language, level: context.level }) : language;
}

export default async function mountOrena(element, ctx) {
  if (!orenaPresent()) {
    ctx.replace(ctx.href('today'));
    return undefined;
  }
  await useStyles('screens/orena/orena.css');
  const dispatcher = homeDispatcher();
  const ranActions = new Set();
  let draft = '';
  let consumedUnsent = '';
  let voiceMode = ctx.query.get('voice') === '1';
  let voiceEngine = null;
  let voiceShown = false;
  let alive = true;

  function paint(state) {
    if (!alive) return;
    if (!orenaPresent() || state.absent) {
      ctx.replace(ctx.href('today'));
      return;
    }
    if (state.unsent && state.unsent !== consumedUnsent) {
      consumedUnsent = state.unsent;
      draft = state.unsent;
      voiceMode = false;
      // The message is back in the box either way; only a changed learning language is news.
      if (state.unsentWhy === 'language') toast(t('unsentNotice'), { iconName: 'circle-alert' });
    }
    const supported = dispatcher.supported();
    const subtitle = homeSubtitle(languageLabel(ctx.context), t);
    keepFocus(element, () =>
      mount(
        element,
        html`<div class="s-orena-home">
          <div class="s-orena-home__head">
            ${intelChip({ size: 56, mark: 45 })}
            <div class="s-orena-home__headtext">
              <h1 class="s-orena-home__h1">Orena</h1>
              ${subtitle ? html`<div class="s-orena-home__sub">${subtitle}</div>` : ''}
            </div>
          </div>
          <div class="s-orena-home__thread" data-scroll-region>
            ${!state.messages.length && !state.thinking
              ? html`<div class="s-orena-home__empty">${intelChip({ size: 32, mark: 26 })}<div class="s-orena-home__empty-body"><div class="s-orena-home__empty-title">${t('emptyTitle')}</div><div class="s-orena-home__empty-sub">${t('emptySub')}</div></div></div>`
              : ''}
            ${state.messages.map((message) => messageMarkup(message, { surface: 'home', ranActions, supported }))}
            ${state.thinking ? html`<div class="s-orena-home__thinking">${intelChip({ size: 30, mark: 24, state: 'thinking' })}${thinkingText(state.tool, t('thinkingLabel'))}</div>` : ''}
          </div>
          <div class="s-orena-home__composer">
            <div class="s-orena-home__card">
              ${voiceMode ? voiceRowMarkup(voiceEngine ? voiceEngine.state() : { phase: 'idle', heard: '', speakOn: true }, { fresh: !voiceShown }) : typingMarkup(state)}
              ${startersMarkup(state)}
            </div>
          </div>
        </div>`,
      ),
    );
    voiceShown = voiceMode;
    bind();
    const thread = element.querySelector('[data-scroll-region]');
    if (thread) thread.scrollTop = thread.scrollHeight;
    // The router moves focus to the main region once a screen has mounted, so the cursor goes in
    // the box after that (a macrotask), not during the mount.
    if (takeComposerFocus()) setTimeout(() => element.querySelector('[data-input]')?.focus({ preventScroll: true }), 0);
  }

  function typingMarkup(state) {
    const busy = state.thinking;
    return html`<div class="s-orena-home__typing">
      ${intelChip({ size: 40, mark: 32 })}
      <input type="text" class="s-orena-home__input" data-input placeholder="${t('composerPlaceholder')}" value="${draft}">
      <button type="button" class="s-orena-home__voicebtn" data-to-voice aria-label="${shellCopy('talkToOrena')}" ${busy ? raw('disabled') : ''}>${raw(icon('mic', { size: 20 }))}</button>
      <button type="button" class="s-orena-home__send" data-send aria-label="${t('sendLabel')}" ${busy ? raw('disabled') : ''}>${raw(icon('arrow-up', { size: 20 }))}</button>
    </div>`;
  }

  function startersMarkup(state) {
    const suggestions = latestSuggestions(state.messages);
    if (!suggestions.length) return '';
    return html`<div class="s-orena-home__starters" data-scroll-region>${suggestions.map((s) => html`<button type="button" class="s-orena-home__starter" data-starter="${s.label}">${s.label}</button>`)}</div>`;
  }

  function findAction(id) {
    for (const message of homeState().messages) {
      if (message.role !== 'orena') continue;
      const found = (message.actions || []).find((a) => a.id === id);
      if (found) return found;
    }
    return null;
  }

  function submitTyped() {
    const input = element.querySelector('[data-input]');
    const text = String(input?.value || '').trim();
    if (!text || homeState().thinking) return;
    draft = '';
    sendHomeMessage(text);
  }

  // Coming back to Orena takes back a conversation the dock carried.
  const carried = undockVoice();
  if (carried) {
    voiceEngine = carried;
    voiceMode = true;
    voiceShown = true;
    carried.setOnChange(() => paint(homeState()));
  }

  function endVoice() {
    voiceEngine?.dispose();
    voiceEngine = null;
    voiceMode = false;
    paint(homeState());
  }

  function startVoice() {
    if (voiceEngine) return voiceEngine;
    voiceEngine = createVoiceEngine({
      ctx,
      send: sendHomeTurn,
      // A place the learner asked for by voice opens at once (R29), through the same runner as a tap.
      liveVoice: () => ({ ...homeLiveVoice(), open: (action) => runOffered({ dispatcher, action, ranActions, repaint: () => paint(homeState()) }) }),
      abort: abortHome,
      onTextOnly: endVoice,
      onChange: () => paint(homeState()),
    });
    voiceEngine.main(); // tapping the mic (or opening already in voice mode) starts listening now
    return voiceEngine;
  }

  function bind() {
    element.querySelectorAll('[data-action-id]').forEach((button) =>
      button.addEventListener('click', () => runOffered({ dispatcher, action: findAction(button.dataset.actionId), ranActions, repaint: () => paint(homeState()) })),
    );
    element.querySelectorAll('[data-retry]').forEach((button) => button.addEventListener('click', retryHome));
    element.querySelectorAll('[data-starter]').forEach((button) => button.addEventListener('click', () => sendHomeMessage(button.dataset.starter)));
    const input = element.querySelector('[data-input]');
    if (input) {
      input.addEventListener('input', () => {
        draft = input.value;
      });
      input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.isComposing) submitTyped();
      });
    }
    element.querySelector('[data-send]')?.addEventListener('click', submitTyped);
    element.querySelector('[data-to-voice]')?.addEventListener('click', () => {
      voiceMode = true;
      startVoice();
      paint(homeState());
    });
    if (voiceMode) bindVoiceRow(element, voiceEngine || startVoice(), { onClose: endVoice });
  }

  const unsubscribe = subscribeHome((state) => paint(state));
  const unsubscribePresence = onOrenaPresence(() => paint(homeState()));
  // The subtitle names the learning language; a change of it (a 409 re-read, Settings in another
  // tab) repaints the header.
  let shownLanguage = ctx.context.language;
  const unsubscribeContext = onContext((state) => {
    if (state.language === shownLanguage) return;
    shownLanguage = state.language;
    paint(homeState());
  });
  ensureOpening();
  if (voiceMode) startVoice();

  return () => {
    alive = false;
    unsubscribe();
    unsubscribePresence();
    unsubscribeContext();
    // A live conversation goes on after Orena opens a place: the dock carries it (human request 2026-10-06).
    if (!dockVoice(voiceEngine)) voiceEngine?.dispose();
    // §2.1 429: leaving while Orena waits out a rate limit is the learner's cancel of that wait.
    if (homeState().waiting) abortHome();
  };
}
