import { esc, dialog, focusRegion } from './html.js';
import { pageIntro, progressReporter } from './patterns.js';
import { openUnderstanding } from './understanding.js';
import { mountVoiceResponse } from './voice-response.js';
import {
  conversation,
  learnerTurn,
  partnerTurn,
  pendingTurn,
  conversationRequest,
  MAX_CONVERSATION_TURNS,
} from '../product/conversation.js';
import { link } from '../product/intent.js';

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
    root.innerHTML = `<div class="back-row"><a href="${link('practice', { intent: 'speaking' })}">← ${esc(c.speakingName)}</a><span class="meta">${esc(memory.available ? c.conversationLocal : c.memoryUnavailable)}</span></div>${pageIntro({ title: state.title, note: state.situation, eyebrow: c.conversationTitle })}<p class="notice">${esc(c.conversationTruth)}</p><ol class="conversation-turns">${state.turns.map((turn, index) => `<li class="conversation-turn" data-role="${turn.role}"><small>${esc(turn.role === 'partner' ? c.conversationPartner : turn.origin === 'speech_transcript' ? c.conversationSpoken : c.conversationYou)}</small><p lang="${language}">${esc(turn.text)}</p>${turn.meaning && turn.support === ctx.support ? `<details><summary>${esc(c.conversationMeaning)}</summary><p lang="${esc(turn.support)}">${esc(turn.meaning)}</p></details>` : ''}<button class="quiet" data-inspect-turn="${index}">${esc(c.lookCloser)} ↗</button></li>`).join('')}</ol><div class="conversation-composer">${state.ended ? `<h2>${esc(c.conversationEnded)}</h2><p>${esc(c.conversationEndNote)}</p>` : full ? `<p>${esc(c.conversationFull)}</p>` : pending ? `<p>${esc(c.conversationWaiting)}</p><button class="outline" data-retry>${esc(c.retry)}</button>` : `<form data-reply><label for="conversationReply">${esc(c.conversationReply)}</label><textarea id="conversationReply" name="reply" rows="3" maxlength="2400" required lang="${language}">${esc(memory.value.expressions[state.id] || '')}</textarea><div class="button-row"><button class="primary">${esc(c.conversationSend)} →</button><button type="button" class="outline" data-voice>${esc(c.record)}</button></div></form>`}<p role="status" data-conversation-status></p><div class="button-row">${!state.ended ? `<button class="quiet" data-end>${esc(c.conversationEnd)}</button>` : ''}<button class="quiet" data-new>${esc(c.conversationNew)}</button></div></div>`;
    root.querySelectorAll('[data-inspect-turn]').forEach(
      (button) =>
        (button.onclick = () => {
          const index = Number(button.dataset.inspectTurn),
            turn = state.turns[index];
          openUnderstanding(ctx, {
            selection: turn.text.slice(0, 1600),
            context: state.turns
              .slice(Math.max(0, index - 1), index + 1)
              .map((t) => t.text)
              .join('\n')
              .slice(0, 2400),
            title: state.title,
          });
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
      root.querySelector('[data-voice]').onclick = () => {
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
