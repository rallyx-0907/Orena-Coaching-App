/* Frame 30 "Conversation" (pinned design, focus route 'conv'; E2 §3). A real AI partner
   (`POST /api/dictionary/conversation-turn`) through the existing, already-DOM-free turn state
   machine (`product/conversation.js`) and the existing device-memory persistence
   (`ctx.context.memory.conversation`/`.enter`) - reused whole, not duplicated.

   Real deviations from the frame, recorded rather than silently resolved (UI_BACKEND_GAPS "Speak
   more"):
   - The frame's `cvStart` seeds a fixed opening line from a scripted partner. The real contract
     cannot do that: `ConversationIn` (`writing_coach/conversation.py`) requires at least one turn
     and that the last turn be the learner's pending one. The chat therefore opens with the
     situation the learner is answering (drawn as the frame's partner bubble, never sent as a turn)
     and the learner speaks first.
   - The frame ends a chat only when its 4-line script runs out. An open-ended AI partner needs a
     learner-driven end, so the header carries one "End" text button (where a page's own action
     sits in the design); it and the 24-turn cap both lead to the frame's "Conversation complete".
   - "How did that land?" opens the Orena panel in the frame, with a regex analysis from the
     prototype. No Conversation surface id exists in AGENT_CONTRACT §6.1, so the real per-turn
     coaching (`POST /api/dictionary/spoken-response`) shows inline, in the Free Talk result's own
     drawn patterns.

   Rule 49: this route is a learning workspace; the message list is the one region that grows long
   and is the only thing that scrolls (`data-scroll-region`) - the frame's own already-correct
   inner-scroll region (E2 §3: "the one frame in this set that already satisfies rule 49's
   'workspace is the viewport' pattern by construction"). */
import { html, mount, raw } from '../../kit/html.js';
import { icon } from '../../kit/icons.js';
import { langAttr } from '../../kit/lang.js';
import { useStyles } from '../../kit/styles.js';
import { api } from '../../infrastructure/api.js';
import { languages } from '../../copy/index.js';
import { shellCopy as ts } from '../../copy/shell.js';
import { createLocalAudioRecorder } from '../../capabilities/audio-recorder.js';
import { logSpeakingTask } from '../../product/speaking-session.js';
import { appendConversationTurn, loadConversation } from '../../product/account-records.js';
import { micGate, openMicState } from '../mic/sheet.js';
import {
  conversation, learnerTurn, partnerTurn, pendingTurn, conversationRequest, restoreConversation, MAX_CONVERSATION_TURNS,
} from '../../product/conversation.js';
import { t } from './copy.js';
import { situations, turnSituation, learnerTurnCount, fixesOf, strengthsOf } from './model.js';

function judgementLabel(judgement) {
  return t.has(`judge_${judgement}`) ? t(`judge_${judgement}`) : '';
}

export default async function conversationScreen(element, ctx) {
  await useStyles('screens/conversation/conversation.css');
  const language = ctx.context.language;
  const support = languages().support;
  const memory = ctx.context.memory;
  const recorder = createLocalAudioRecorder();
  const lang = langAttr(language);
  const supportLang = langAttr(support);

  let disposed = false;
  const alive = () => !disposed && ctx.isCurrent();

  const bank = situations(language);
  let pickedKey = bank[0]?.key || ''; // the frame opens with its first scenario chosen
  let convo = null; // the product/conversation.js state, once started
  let busy = false;
  let recording = false;
  let transcribing = false; // a take is being turned into text
  let lastBlob = null; // the recording awaiting a transcript, kept so a Retry sends the same take again
  let draft = ''; // what is typed (or transcribed) in the composer, kept across repaints
  let recordedThisTurn = false; // the composer's text came from the microphone rather than the keyboard
  let refocus = false; // the learner just sent a turn: the composer takes focus back once the reply is in
  const coaching = new Map(); // turn index -> { loading, result }

  element.classList.add('s-conv');

  function remember() {
    if (!convo) return;
    memory.conversation(convo);
    memory.enter({ id: convo.id, title: convo.title, intent: 'speaking', excerpt: convo.situation });
  }

  /* Each turn is also written to the account as it happens, in order (D4 I6): a failed write changes
     nothing the learner sees, because the device already holds the conversation. */
  function keepTurn(turn) {
    if (!convo || !turn) return;
    void appendConversationTurn(convo.id, turn, { title: convo.title, situation: convo.situation });
  }

  /* `?id=conversation:...` opens a conversation the learner left, from this device or from the account
     (a new device), and carries on where it stopped. Anything that does not restore cleanly opens the
     scenario picker, as before. */
  async function resume(id) {
    const local = memory.value.conversations?.[id];
    const raw = local || (await loadConversation(id, language));
    if (!alive()) return null;
    const restored = raw ? restoreConversation(raw, language) : null;
    if (restored && !local) memory.conversation(restored);
    return restored;
  }

  const isOver = () => Boolean(convo) && (convo.ended || convo.turns.length >= MAX_CONVERSATION_TURNS);

  function headMarkup() {
    const item = convo ? bank.find((entry) => entry.title === convo.title) : null;
    const sub = convo ? (item ? `${item.title} · ${item.cue}` : convo.title) : '';
    const subline = convo ? (sub ? html`<div class="s-conv__sub" lang="${lang}">${sub}</div>` : '') : html`<div class="s-conv__sub">${t('setupSubtitle')}</div>`;
    return html`<div class="s-conv__head">
      <button type="button" class="o-iconbtn o-iconbtn--back" data-back aria-label="${ts('back')}">${raw(icon('arrow-left', { size: 21 }))}</button>
      <div class="s-conv__headcol"><h1 class="s-conv__title">${ts('conversation')}</h1>${subline}</div>
      ${convo && !isOver() ? html`<button type="button" class="o-btn o-btn--text s-conv__end" data-end>${t('endConversation')}</button>` : ''}
    </div>`;
  }

  function scenarioMarkup(item) {
    return html`<button type="button" class="s-conv__scenario" aria-pressed="${item.key === pickedKey ? 'true' : 'false'}" data-situation="${item.key}">
      <div class="s-conv__scenario-title" lang="${lang}">${item.title}</div>
      <div class="s-conv__scenario-cue" lang="${lang}">${item.cue}</div>
    </button>`;
  }

  function setupMarkup() {
    return html`<div class="s-conv__body" data-scroll-region><section class="o-card o-card--24 s-conv__setup">
      <div>
        <div class="s-conv__label">${t('situationLabel')}</div>
        <div class="s-conv__scenarios">${bank.map(scenarioMarkup)}</div>
      </div>
      <button type="button" class="o-btn o-btn--primary o-btn--block s-conv__start" data-start>${t('startCta')}</button>
    </section></div>`;
  }

  function quotedStrength(item) {
    return html`<p class="s-conv__coach-strength"><b lang="${lang}">${item.quote}</b> · <span lang="${supportLang}">${item.why}</span></p>`;
  }

  function quotedFix(item) {
    const judge = item.judgement ? judgementLabel(item.judgement) : '';
    return html`<div class="s-conv__coach-fix">
      <div class="s-conv__coach-fix-change"><s lang="${lang}">${item.quote}</s>${item.instead ? html` → <b lang="${lang}">${item.instead}</b>` : ''}${judge ? html`<span class="s-conv__coach-judge">${judge}</span>` : ''}</div>
      ${item.why ? html`<div class="s-conv__coach-fix-why" lang="${supportLang}">${item.why}</div>` : ''}
    </div>`;
  }

  function coachingMarkup(card) {
    if (card.loading) return html`<div class="s-conv__coach"><p class="s-conv__muted" role="status">${t('coachingWorking')}</p></div>`;
    const result = card.result;
    const carriedItems = strengthsOf(result);
    const landedItems = fixesOf(result);
    if (!result?.available || (!carriedItems.length && !landedItems.length)) return html`<div class="s-conv__coach"><p class="s-conv__muted">${t('coachingUnavailable')}</p></div>`;
    return html`<div class="s-conv__coach">
      ${carriedItems.length ? html`<div><span class="s-conv__coach-title s-conv__coach-title--good">${t('carried')}</span>${carriedItems.map(quotedStrength)}</div>` : ''}
      ${landedItems.length ? html`<div><span class="s-conv__coach-title s-conv__coach-title--bad">${t('landed')}</span>${landedItems.map(quotedFix)}</div>` : ''}
      ${result.another_way ? html`<p class="s-conv__coach-note"><b>${t('anotherWay')}</b> · <span lang="${lang}">${result.another_way}</span></p>` : ''}
      ${result.next_attempt ? html`<p class="s-conv__coach-note"><b>${t('nextAttempt')}</b> · <span lang="${supportLang}">${result.next_attempt}</span></p>` : ''}
    </div>`;
  }

  function messageMarkup(turn, index) {
    const card = coaching.get(index);
    return html`<div class="s-conv__msg s-conv__msg--${turn.role}">
      <div class="s-conv__bubble" lang="${lang}">${turn.text}</div>
      ${turn.role === 'learner' && !card ? html`<button type="button" class="s-conv__land" data-land="${index}">${t('howDidItLand')}</button>` : ''}
      ${card ? coachingMarkup(card) : ''}
    </div>`;
  }

  function endedMarkup() {
    const spoken = learnerTurnCount(convo.turns);
    return html`<div class="s-conv__ended">
      <span class="s-conv__deco s-conv__deco--a"></span><span class="s-conv__deco s-conv__deco--b"></span>
      <div class="s-conv__ended-title">${t('ended')}</div>
      <div class="s-conv__ended-note">${t.plural('turns', spoken)}</div>
      <div class="s-conv__ended-actions">
        <button type="button" class="o-btn o-btn--secondary" data-new>${t('newScenario')}</button>
        <button type="button" class="o-btn o-btn--primary" data-finish>${t('finish')}</button>
      </div>
    </div>`;
  }

  function listMarkup() {
    return html`<div class="s-conv__list" data-scroll-region data-list>
      <div class="s-conv__msg s-conv__msg--partner"><div class="s-conv__bubble" lang="${lang}">${convo.situation}</div></div>
      ${convo.turns.map(messageMarkup)}
      ${busy ? html`<div class="s-conv__thinking" role="status" aria-label="${t('thinking')}">…</div>` : ''}
      ${isOver() ? endedMarkup() : ''}
    </div>`;
  }

  function composerMarkup() {
    if (isOver()) return '';
    const failed = Boolean(pendingTurn(convo)) && !busy; // the reply was requested and the request itself failed
    if (failed) {
      return html`<div class="s-conv__composer"><span class="s-conv__retry-text" role="alert">${t('replyFailed')}</span><button type="button" class="o-btn o-btn--secondary s-conv__retry-btn" data-retry>${t('retryCta')}</button></div>`;
    }
    const locked = busy || transcribing;
    return html`<form class="s-conv__composer" data-reply>
      <input type="text" class="s-conv__input" data-input placeholder="${transcribing ? t('transcribing') : t('replyPlaceholder')}" value="${draft}" lang="${lang}" autocomplete="off" ${locked ? 'disabled' : ''}>
      <button type="button" class="s-conv__mic" data-mic aria-pressed="${recording ? 'true' : 'false'}" aria-label="${recording ? t('micStop') : t('mic')}" ${locked ? 'disabled' : ''}>${raw(icon('mic', { size: 18 }))}</button>
      <button type="submit" class="s-conv__send" aria-label="${t('send')}" ${locked ? 'disabled' : ''}>${raw(icon('arrow-right', { size: 18 }))}</button>
    </form>`;
  }

  /* `scroll`: 'bottom' after the exchange grows, otherwise the list keeps where the learner was. */
  function paint({ scroll = 'keep' } = {}) {
    const before = element.querySelector('[data-list]')?.scrollTop ?? 0;
    mount(element, html`${headMarkup()}${convo ? html`${listMarkup()}${composerMarkup()}` : setupMarkup()}`);
    element.querySelector('[data-back]').addEventListener('click', () => ctx.back());
    bind();
    const list = element.querySelector('[data-list]');
    if (list) list.scrollTop = scroll === 'bottom' ? list.scrollHeight : before;
    const input = element.querySelector('[data-input]');
    if (refocus && input && !input.disabled) {
      refocus = false;
      input.focus({ preventScroll: true });
    }
  }

  function bind() {
    if (!convo) {
      element.querySelectorAll('[data-situation]').forEach((button) => {
        button.onclick = () => { pickedKey = button.dataset.situation; paint(); };
      });
      element.querySelector('[data-start]').onclick = () => startConversation();
      return;
    }
    element.querySelectorAll('[data-land]').forEach((button) => {
      button.onclick = () => void howDidItLand(Number(button.dataset.land));
    });
    const input = element.querySelector('[data-input]');
    if (input) input.oninput = () => { draft = input.value; recordedThisTurn = false; };
    const form = element.querySelector('[data-reply]');
    if (form) {
      form.onsubmit = (event) => {
        event.preventDefault();
        const text = draft.trim();
        if (!text || busy) return;
        draft = '';
        refocus = true;
        void sendTurn(text, recordedThisTurn ? 'speech_transcript' : 'typed');
      };
      element.querySelector('[data-mic]').onclick = () => (recording ? void stopMic() : void toggleMic());
    }
    element.querySelector('[data-new]')?.addEventListener('click', () => { convo = null; draft = ''; coaching.clear(); paint(); });
    element.querySelector('[data-finish]')?.addEventListener('click', finish);
    element.querySelector('[data-end]')?.addEventListener('click', () => { convo = { ...convo, ended: true }; remember(); paint({ scroll: 'bottom' }); });
    element.querySelector('[data-retry]')?.addEventListener('click', () => void requestReply());
  }

  function finish() {
    const spoken = learnerTurnCount(convo.turns);
    logSpeakingTask({ kind: 'conversation', contentId: convo.id, facts: [{ label: t('turnsLabel'), value: String(spoken) }] });
    ctx.go(ctx.href('spsummary'));
  }

  function startConversation() {
    const picked = bank.find((item) => item.key === pickedKey);
    if (!picked) return;
    convo = conversation({ id: `conversation:${crypto.randomUUID()}`, language, title: picked.title, situation: picked.prompt });
    coaching.clear();
    draft = '';
    remember();
    paint();
  }

  async function sendTurn(text, origin) {
    convo = learnerTurn(convo, { id: crypto.randomUUID(), text, origin });
    recordedThisTurn = false;
    remember();
    keepTurn(convo.turns.at(-1));
    await requestReply();
  }

  /* Asks the real AI partner for the next line. A failure leaves the learner's turn pending
     (never removed - their words are not lost) and the composer is replaced with Retry, which
     resends the exact same request for the same still-pending turn. */
  async function requestReply() {
    if (!pendingTurn(convo)) return;
    busy = true;
    paint({ scroll: 'bottom' });
    try {
      const reply = await api.conversationTurn(conversationRequest(convo, support));
      if (!alive()) return;
      convo = partnerTurn(convo, reply);
      remember();
      keepTurn(convo.turns.at(-1));
    } catch {
      // still pending; the retry control resends it.
    } finally {
      busy = false;
      if (alive()) paint({ scroll: 'bottom' });
    }
  }

  async function toggleMic() {
    if (recording) return;
    await micGate(ctx, async () => {
      const started = await recorder.start();
      if (!alive()) return recorder.cleanup();
      if (!started) return void problem('blocked');
      recording = true;
      paint();
    });
  }

  async function stopMic() {
    recording = false;
    const take = await recorder.stop();
    if (!alive() || !take?.blob) return paint();
    lastBlob = take.blob;
    await transcribe();
  }

  async function transcribe() {
    transcribing = true;
    paint();
    try {
      const result = await api.transcribeSpeech(lastBlob, language);
      if (!alive()) return;
      const text = String(result?.text || result?.transcript || '').trim();
      transcribing = false;
      paint();
      if (!text) return void problem('notheard');
      draft = text;
      recordedThisTurn = true;
      paint();
    } catch {
      if (!alive()) return;
      transcribing = false;
      paint();
      void problem(navigator.onLine === false ? 'offline' : 'provider');
    }
  }

  /* The Mic state sheet's own buttons, wired: Retry sends the same take again (or asks for the
     microphone again), Try again records again, and typing instead / continuing without the
     transcript leaves the learner in the composer. */
  function problem(kind) {
    return openMicState(ctx, {
      state: kind,
      onAction: (key) => {
        if (key === 'retry' && kind === 'provider' && lastBlob) return void transcribe();
        if (key === 'retry' || key === 'tryagain') return void toggleMic();
        if (key === 'continue' || key === 'typeInstead') element.querySelector('[data-input]')?.focus();
        return undefined;
      },
    });
  }

  async function howDidItLand(index) {
    const turn = convo.turns[index];
    if (!turn || turn.role !== 'learner' || coaching.has(index)) return;
    coaching.set(index, { loading: true, result: null });
    paint();
    try {
      const result = await api.spokenResponseCoaching({
        transcript: turn.text.slice(0, 2400),
        source_language: language,
        target_language: support,
        situation: turnSituation(convo.situation, convo.turns, index),
      });
      if (!alive()) return;
      coaching.set(index, { loading: false, result });
    } catch {
      if (!alive()) return;
      coaching.set(index, { loading: false, result: null });
    }
    paint();
  }

  const wanted = ctx.query?.get?.('id') || '';
  if (wanted) convo = await resume(wanted);
  paint({ scroll: 'bottom' });

  return () => {
    disposed = true;
    recorder.cleanup();
  };
}
