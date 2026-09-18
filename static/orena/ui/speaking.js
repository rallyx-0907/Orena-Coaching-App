import {
  pageIntro,
  practiceReturn,
  continuationShelf,
  hint,
  workspaceFrames,
} from './patterns.js';
import { esc, dialog } from './html.js';
import { voiceInvitations } from '../content/voice-invitations.js';
import { link } from '../product/intent.js';
import { mountVoiceResponse } from './voice-response.js';
import { mountLexicalLayer } from './lexical.js';
import { startConversation } from './conversation.js';

export function renderSpeaking(root, ctx) {
  const { c, language, location, memory } = ctx;
  const invitations = voiceInvitations(language);
  const source = memory.value.continuation.find((x) => x.id === location.id);
  const picked =
    invitations.find((x) => `voice:${x.key}` === location.id) ||
    (source?.excerpt
      ? {
          key: location.id,
          title: source.title,
          prompt: source.excerpt,
          cue: c.voiceReflect,
          own: true,
        }
      : null) ||
    (!location.id ? invitations[0] : null);
  if (!picked) throw Error(c.unavailable);
  const id = picked.own ? location.id : `voice:${picked.key}`;
  /* Speaking follows the learning workspace: the situation and the take on
     one side, what was heard - evidence, then coaching - on the other, inside
     one desktop frame. Other starting points and other shapes of speaking are
     choices for afterwards, so they sit below the frame rather than in the
     column the answer needs. */
  const waiting = `<div class="result-waiting"><small>${esc(c.heard)}</small><p>${esc(c.voiceWaiting)}</p></div>`;
  root.innerHTML = `${practiceReturn(c, 'speaking')}${pageIntro({ title: c.voiceTitle, eyebrow: c.speakingName, compact: true })}<section class="learning-workspace voice-workspace" data-workspace="activity"><div class="workspace-activity voice-exchange"><header class="voice-situation"><small>${esc(c.voiceSituation)}</small><h2 lang="${language}">${esc(picked.title)}</h2></header><div data-voice></div></div><section class="workspace-result voice-result" aria-label="${esc(c.heard)}"><div class="workspace-result__bar"><button type="button" class="quiet" data-workspace-back>← ${esc(c.voiceBack)}</button></div><div class="workspace-result__scroll" data-voice-result-host aria-live="polite">${waiting}</div></section></section><div class="workspace-secondary"><aside class="voice-directions"><div class="heading-with-hint"><h2>${esc(c.voiceChoose)}</h2>${hint({ text: picked.own ? c.voiceOwnSource : c.voiceSource })}</div>${invitations.map((x) => `<a ${x.key === picked.key ? 'aria-current="true"' : ''} lang="${language}" href="${link('practice', { intent: 'speaking', id: `voice:${x.key}` })}">${esc(x.title)} ↗</a>`).join('')}<p lang="${language}">${esc(picked.cue)}</p></aside></div>${continuationShelf(ctx, 2)}`;
  const frames = workspaceFrames(root.querySelector('.voice-workspace'), {
    back: root.querySelector('[data-workspace-back]'),
    focus: () => root.querySelector('[data-record]'),
    result: root.querySelector('[data-voice-result-host]'),
  });
  // Opening a situation is continuity, never a completed speaking attempt.
  const own = document.createElement('button');
  const talk = document.createElement('button');
  talk.className = 'outline';
  talk.textContent = c.conversationStart;
  talk.onclick = () =>
    startConversation(ctx, { title: picked.title, situation: picked.prompt });
  root.querySelector('.voice-directions').append(talk);
  own.className = 'outline';
  own.textContent = c.voiceOwn;
  root.querySelector('.voice-directions').append(own);
  own.onclick = () => {
    const sheet = dialog({
      title: c.voiceOwn,
      body: `<form data-own-voice><label for="voiceOwnPrompt">${esc(c.voiceOwnNote)}</label><textarea id="voiceOwnPrompt" name="prompt" rows="4" maxlength="1200" required></textarea><button class="primary">${esc(c.voiceBegin)}</button></form>`,
    });
    sheet.querySelector('[data-own-voice]').onsubmit = (event) => {
      event.preventDefault();
      const prompt = sheet.querySelector('textarea').value.trim();
      if (!prompt) return;
      const id = `voice:own:${crypto.randomUUID()}`;
      memory.enter({
        id,
        title: prompt.slice(0, 90),
        intent: 'speaking',
        excerpt: prompt,
      });
      sheet.close();
      ctx.go('practice', { id, intent: 'speaking' });
    };
  };
  memory.enter({
    id,
    title: picked.title,
    intent: 'speaking',
    excerpt: picked.prompt,
  });
  const releaseVoice = mountVoiceResponse(root.querySelector('[data-voice]'), ctx, {
    id,
    title: picked.title,
    prompt: picked.prompt,
    resultHost: root.querySelector('[data-voice-result-host]'),
    resultIdle: waiting,
    onResult: frames.showResult,
  });
  /* The situation a learner is answering is language too, and a word in it is
     asked about the same way it is asked about anywhere else - the shared layer
     (`ui/lexical.js`), not a Speaking copy of it. */
  const lexical = mountLexicalLayer({
    surface: root,
    ctx,
    title: picked.title,
    origin: { id, where: picked.title, why: 'from_speaking' },
    alive: ctx.alive || (() => root.isConnected),
    units: {
      root: () => root,
      unitOf: (node) => node?.closest?.('[data-practice-line]') || null,
      textOf: (unit) => unit.textContent || '',
      keyOf: () => `speaking:${id}`,
    },
  });
  root.addEventListener('click', (event) => {
    if (!event.target.closest('[data-practice-line]')) return;
    lexical.tapWord(event);
  });
  return () => {
    lexical.destroy();
    releaseVoice?.();
  };
}
