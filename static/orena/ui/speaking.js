import { pageIntro, practiceReturn, continuationShelf } from './patterns.js';
import { esc, dialog } from './html.js';
import { voiceInvitations } from '../content/voice-invitations.js';
import { link } from '../product/intent.js';
import { mountVoiceResponse } from './voice-response.js';
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
  root.innerHTML = `${pageIntro({ title: c.voiceTitle, note: c.voiceIntro, eyebrow: c.speakingName, scene: 'speaking' })}${practiceReturn(c, 'speaking')}<div class="voice-room"><section class="voice-exchange"><header class="voice-situation"><small>${esc(c.voiceSituation)}</small><h2 lang="${language}">${esc(picked.title)}</h2></header><div data-voice></div></section><aside class="voice-directions"><h2>${esc(c.voiceChoose)}</h2>${invitations.map((x) => `<a ${x.key === picked.key ? 'aria-current="true"' : ''} lang="${language}" href="${link('practice', { intent: 'speaking', id: `voice:${x.key}` })}">${esc(x.title)} ↗</a>`).join('')}<p lang="${language}">${esc(picked.cue)}</p><p class="meta">${esc(c.voiceSource)}</p></aside></div>${continuationShelf(ctx, 2)}`;
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
  if (picked.own)
    root.querySelector('.voice-directions > .meta').textContent =
      c.voiceOwnSource;
  memory.enter({
    id,
    title: picked.title,
    intent: 'speaking',
    excerpt: picked.prompt,
  });
  return mountVoiceResponse(root.querySelector('[data-voice]'), ctx, {
    id,
    title: picked.title,
    prompt: picked.prompt,
  });
}
