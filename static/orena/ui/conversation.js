import { esc, dialog, focusRegion, focusWork } from './html.js';
import { pageIntro, progressReporter, hint } from './patterns.js';
import { openUnderstanding } from './understanding.js';
import { loadSpokenCoaching } from './spoken-coaching.js';
import { mountVoiceResponse, speechConfigured } from './voice-response.js';
import {
  conversation,
  learnerTurn,
  partnerTurn,
  pendingTurn,
  conversationRequest,
  MAX_CONVERSATION_TURNS,
} from '../product/conversation.js';
import { link } from '../product/intent.js';

/* Asking what something in a turn means sends that text and the context it sat
   in, and the server refuses a context that does not contain the selection -
   correctly, since an explanation grounded in text the learner did not select
   is not about their words.

   Budgeting from the start of the pair broke exactly that: a preceding turn may
   itself fill the whole allowance, and taking the first 2400 characters then
   kept the preceding turn and dropped the one holding the selection. The
   learner asked about their own sentence and got a 422.

   The selection's own turn is therefore never what gets trimmed. Whatever room
   is left goes to what came before it, taken from its end, because the part of
   a previous turn nearest the selection is the part that explains it. */
export const CONTEXT_LIMIT = 2400;
export const SELECTION_LIMIT = 1600;

export function turnContext(turns, index) {
  const body = String(turns[index]?.text ?? '').slice(0, CONTEXT_LIMIT);
  const preceding = index > 0 ? String(turns[index - 1]?.text ?? '') : '';
  const room = CONTEXT_LIMIT - body.length - 1; // the newline between them
  if (!preceding || room <= 0) return body;
  return `${preceding.slice(-room)}\n${body}`;
}

export function startConversation(ctx, { title, situation }) {
  const state = conversation({
    id: `conversation:${crypto.randomUUID()}`,
    language: ctx.language,
    title,
    situation,
  });
  ctx.memory.conversation(state);
  ctx.memory.enter({
    id: state.id,
    title,
    intent: 'speaking',
    excerpt: situation,
  });
  ctx.go('conversation', { id: state.id });
}
export function renderConversation(root, ctx) {
  const { c, memory, api, language } = ctx;
  let state = memory.value.conversations[ctx.location.id];
  if (!state) throw Error(c.unavailable);
  let disposed = false,
    busy = false,
    voiceCleanup = () => {},
    origin = 'typed';
  const alive = () => !disposed && ctx.alive();
  const remember = () => {
    memory.conversation(state);
    memory.enter({
      id: state.id,
      title: state.title,
      intent: 'speaking',
      excerpt: state.situation,
    });
  };
  const draw = () => {
    const pending = pendingTurn(state),
      full = state.turns.length >= MAX_CONVERSATION_TURNS;
    /* A conversation is something the learner does, so it opens like every
       other activity room: compact and without artwork, the situation kept as
       the task. Where the exchange is kept is a status symbol, as a draft's
       is; that the partner is simulated stays on screen, because it is how
       every reply below has to be read. */
    root.innerHTML = `<div class="back-row"><a href="${link('practice', { intent: 'speaking' })}">← ${esc(c.speakingName)}</a><span class="draft-status" data-state="${memory.available ? 'saved' : 'warning'}">${hint(memory.available ? { icon: 'saved', tone: 'quiet', text: c.conversationLocal } : { icon: 'warning', tone: 'warning', text: c.memoryUnavailable })}</span></div>${pageIntro({ title: state.title, note: state.situation, eyebrow: c.conversationTitle, compact: true })}<p class="notice conversation-truth">${esc(c.conversationTruth)}</p><ol class="conversation-turns">${state.turns.map((turn, index) => `<li class="conversation-turn" data-role="${turn.role}"><small>${esc(turn.role === 'partner' ? c.conversationPartner : turn.origin === 'speech_transcript' ? c.conversationSpoken : c.conversationYou)}</small><p lang="${language}">${esc(turn.text)}</p>${turn.meaning && turn.support === ctx.support ? `<details><summary>${esc(c.conversationMeaning)}</summary><p lang="${esc(turn.support)}">${esc(turn.meaning)}</p></details>` : ''}<div class="turn-actions"><button class="quiet" data-inspect-turn="${index}">${esc(c.lookCloser)} ↗</button>${turn.role === 'learner' ? `<button class="quiet" data-coach-turn="${index}">${esc(c.conversationHowItLanded)} ↗</button>` : ''}</div>${turn.role === 'learner' ? `<div data-turn-coaching="${index}"></div>` : ''}</li>`).join('')}</ol><div class="conversation-composer">${state.ended ? `<h2>${esc(c.conversationEnded)}</h2><p>${esc(c.conversationEndNote)}</p>` : full ? `<p>${esc(c.conversationFull)}</p>` : pending ? `<p>${esc(c.conversationWaiting)}</p><button class="outline" data-retry>${esc(c.retry)}</button>` : `<form data-reply><label for="conversationReply">${esc(c.conversationReply)}</label><textarea id="conversationReply" name="reply" rows="3" maxlength="2400" required lang="${language}">${esc(memory.value.expressions[state.id] || '')}</textarea><div class="button-row"><button class="primary">${esc(c.conversationSend)} →</button><button type="button" class="outline" data-voice>${esc(c.record)}</button></div></form>`}<p role="status" data-conversation-status></p><div class="button-row">${!state.ended ? `<button class="quiet" data-end>${esc(c.conversationEnd)}</button>` : ''}<button class="quiet" data-new>${esc(c.conversationNew)}</button></div></div>`;
    root.querySelectorAll('[data-inspect-turn]').forEach(
      (button) =>
        (button.onclick = () => {
          const index = Number(button.dataset.inspectTurn),
            turn = state.turns[index];
          openUnderstanding(ctx, {
            origin: { id: state.id, where: state.title, why: 'from_speaking' },
            selection: turn.text.slice(0, SELECTION_LIMIT),
            context: turnContext(state.turns, index),
            title: state.title,
          });
        }),
    );
    /* The partner is told not to coach - a conversation where every reply
       corrects you is not a conversation. This is the separate action that
       instruction assumes: asked for, about the learner's own words, and
       answered by the same coaching surface the Speaking room uses. */
    root.querySelectorAll('[data-coach-turn]').forEach(
      (button) =>
        (button.onclick = () => {
          const index = Number(button.dataset.coachTurn),
            turn = state.turns[index];
          if (turn?.role !== 'learner') return;
          button.disabled = true;
          void loadSpokenCoaching(
            root.querySelector(`[data-turn-coaching="${index}"]`),
            ctx,
            {
              transcript: turn.text,
              // What they were answering, so an ordinary reply to a question is
              // not read as an incomplete thought.
              situation: [state.situation, state.turns[index - 1]?.text]
                .filter(Boolean)
                .join('\n')
                .slice(0, 1200),
            },
          );
        }),
    );
    root.querySelector('[data-retry]')?.addEventListener('click', send);
    root.querySelector('[data-new]').onclick = () =>
      startConversation(ctx, {
        title: state.title,
        situation: state.situation,
      });
    root.querySelector('[data-end]')?.addEventListener('click', () => {
      state = { ...state, ended: true };
      remember();
      draw();
    });
    const form = root.querySelector('[data-reply]');
    if (form) {
      const input = form.querySelector('textarea');
      input.oninput = () => {
        origin = 'typed';
        memory.write(state.id, input.value);
      };
      form.onsubmit = (event) => {
        event.preventDefault();
        if (busy || !input.value.trim()) return;
        state = learnerTurn(state, {
          id: crypto.randomUUID(),
          text: input.value,
          origin,
        });
        remember();
        memory.write(state.id, '');
        draw();
        void send();
      };
      /* The same answer the take itself would give, given before the learner
         opens a recorder they cannot use. Typing a reply is unaffected. */
      const voiceButton = root.querySelector('[data-voice]');
      void speechConfigured(api).then((ready) => {
        if (!alive() || ready || !voiceButton.isConnected) return;
        voiceButton.disabled = true;
        voiceButton.title = c.voiceUnavailable;
      });
      voiceButton.onclick = () => {
        const sheet = dialog({
          title: c.record,
          body: '<div data-conversation-voice></div>',
        });
        voiceCleanup = mountVoiceResponse(
          sheet.querySelector('[data-conversation-voice]'),
          { ...ctx, alive: () => alive() && sheet.isConnected },
          {
            id: state.id,
            title: state.title,
            prompt: state.turns.at(-1)?.text || state.situation,
            segmentId: state.id,
            onUse: ({ heard }) => {
              input.value = heard.slice(0, 2400);
              origin = 'speech_transcript';
              memory.write(state.id, input.value);
              sheet.close();
              input.focus();
            },
          },
        );
        sheet.addEventListener(
          'close',
          () => {
            voiceCleanup();
            voiceCleanup = () => {};
          },
          { once: true },
        );
      };
    }
  };
  const send = async () => {
    if (busy || state.ended || !pendingTurn(state)) return;
    busy = true;
    const request = conversationRequest(state, ctx.support);
    const report = progressReporter(
      root.querySelector('[data-conversation-status]'),
      ctx,
      alive,
    );
    root.querySelector('[data-retry]')?.setAttribute('disabled', '');
    report.note(c.conversationThinking);
    try {
      const reply = await ctx.mutate(() => api.conversationTurn(request));
      if (!alive() || state.ended) return;
      state = partnerTurn(state, reply);
      remember();
      draw();
      /* The reply is the answer to what the learner just did, and the reply
         box is where they answer it. When either lands out of sight, both are
         brought into view together - as much of the exchange above them as
         fits, and never the reply's first line hidden under the header. */
      const latest = root.querySelector('.conversation-turn:last-child');
      const answer = root.querySelector('.conversation-composer .button-row');
      const box = latest?.getBoundingClientRect();
      if (
        box &&
        (box.top < 0 ||
          box.bottom > window.innerHeight ||
          (answer?.getBoundingClientRect().bottom ?? 0) > window.innerHeight)
      ) {
        focusWork();
        answer?.scrollIntoView({ block: 'end' });
        const offset =
          parseFloat(
            getComputedStyle(document.documentElement).getPropertyValue(
              '--shell-offset',
            ),
          ) || 0;
        if (latest.getBoundingClientRect().top < offset)
          latest.scrollIntoView({ block: 'start' });
      }
      focusRegion(
        root.querySelector('textarea') ||
          root.querySelector('.conversation-composer'),
      );
    } catch {
      report.failed(c.conversationUnavailable, send);
    } finally {
      busy = false;
    }
  };
  draw();
  return () => {
    disposed = true;
    voiceCleanup();
  };
}
