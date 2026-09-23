import {
  pageIntro,
  practiceReturn,
  continuationEntries,
  continuationPlace,
  continuationShelf,
  hint,
  workspaceFrames,
} from './patterns.js';
import { esc, dialog } from './html.js';
import { voiceInvitations } from '../content/voice-invitations.js';
import { link, continuationExperience } from '../product/intent.js';
import { art } from './content.js';
import { mountVoiceResponse } from './voice-response.js';
import { mountLexicalLayer } from './lexical.js';
import { startConversation } from './conversation.js';
import { mountSpeakingWorkspace, sourceFromLesson } from './speaking-workspace.js';
import { encounter } from '../product/encounter.js';

/* The Speaking workspace: one line at a time, said and assessed. Its lines come from a Listening
   lesson (`media:<lesson>`) - the clip is the model - and, once one has content, from the Speaking
   catalogue (docs/project/UI_BACKEND_GAPS.md, SP-1). It opens on `line`, else where the learner
   last was, else the first line. */
export async function renderSpeakingWorkspace(root, ctx) {
  const { api, language, location, memory } = ctx;
  const id = String(location.id || '');
  if (!id.startsWith('media:')) throw Error(ctx.c.unavailable);
  const payload = await api.listeningLibraryLesson(id.slice(6), ctx.support);
  if (!ctx.alive()) return () => {};
  if (!payload?.transcript?.segments?.length || payload.asset?.source_language !== language)
    throw Error(ctx.c.unavailable);
  const source = sourceFromLesson(id, payload, encounter(payload, ctx.support));
  const prior = memory.value.continuation.find((item) => item.id === id)?.segment;
  const wanted = location.line || prior || '';
  const startIndex = Math.max(0, source.lines.findIndex((line) => line.id === wanted));
  return mountSpeakingWorkspace(root, ctx, source, {
    startIndex,
    // Back to where the learner came from; with no history in this tab, to the Speaking library.
    onLeave: () => (history.length > 1 ? history.back() : ctx.go('practice', { intent: 'speaking' })),
  });
}

/* Speaking is a module, not a branch of Listening.

   Arriving with no particular thing to say used to drop the learner straight
   into the first situation in the list. A learner who opened Speaking on
   purpose should be offered the ways into it that actually exist here, built
   from real state: work they left unfinished, a line they have been listening
   to and could repeat, the authored situations, and their own prompt. Nothing
   on this landing is invented - a path with nothing real behind it is absent. */
function speakingLanding(root, ctx, invitations) {
  const { c, language, memory } = ctx;
  const entries = continuationEntries(memory);
  const resuming = entries.find((x) => continuationExperience(x) === 'speaking') || null;
  const repeatable = entries
    .filter((x) => continuationExperience(x) === 'listening' && String(x.excerpt || '').trim())
    .slice(0, 6);

  /* One continuation, not a history dump: the thing the learner was last
     saying, with the artwork of where it came from. */
  const place = resuming ? continuationPlace(resuming) : null;
  const continueRow = resuming
    ? `<a class="speak-resume" href="${esc(link('practice', { id: resuming.id, intent: 'speaking' }))}"><span class="speak-resume__visual" aria-hidden="true">${art(resuming)}</span><span class="speak-resume__body"><strong lang="${esc(language)}">${esc(resuming.title)}</strong>${resuming.excerpt ? `<span lang="${esc(language)}">${esc(String(resuming.excerpt).slice(0, 110))}</span>` : ''}${place ? `<span class="speak-resume__place">${place.index}/${place.total}</span>` : ''}</span><span class="speak-resume__go">${esc(c.continue)} <span aria-hidden="true">→</span></span></a>`
    : '';

  /* A line worth repeating leads with the content it came from, on a rail. */
  const repeatRail = repeatable.length
    ? `<div class="speak-rail">${repeatable
        .map(
          (x) =>
            `<a class="speak-rail__item" href="${esc(link('practice', { id: x.id, intent: 'speaking' }))}"><span class="speak-rail__visual" aria-hidden="true">${art(x)}</span><span lang="${esc(language)}">${esc(String(x.excerpt).slice(0, 80))}</span></a>`,
        )
        .join('')}</div>`
    : '';

  /* Situations are text, and text does not need a rectangle each. */
  const respondList = invitations.length
    ? `<ul class="speak-situations">${invitations
        .map(
          (x) =>
            `<li><a href="${esc(link('practice', { intent: 'speaking', id: `voice:${x.key}` }))}" lang="${esc(language)}">${esc(x.title)}</a>${x.cue ? `<span lang="${esc(language)}">${esc(x.cue)}</span>` : ''}</li>`,
        )
        .join('')}</ul>`
    : '';

  const section = (title, body) =>
    body ? `<section class="speak-section"><h2>${esc(title)}</h2>${body}</section>` : '';

  root.innerHTML = `${practiceReturn(c, 'speaking')}${pageIntro({ title: c.speakingName, compact: true })}${section(
    c.speakContinue,
    continueRow,
  )}${section(c.speakRepeat, repeatRail)}${section(c.speakRespond, respondList)}<section class="speak-section speak-section--prompt"><h2>${esc(c.speakPrompt)}</h2><button class="outline" data-own-prompt>${esc(c.voiceOwn)} <span aria-hidden="true">→</span></button></section>`;
  bindOwnPrompt(root, ctx);
  return () => {};
}

function bindOwnPrompt(root, ctx) {
  const { c, memory } = ctx;
  const button = root.querySelector('[data-own-prompt]');
  if (!button) return;
  button.onclick = () => {
    const sheet = dialog({
      title: c.voiceOwn,
      body: `<form data-own-voice><label for="voiceOwnPrompt">${esc(c.voiceOwnNote)}</label><textarea id="voiceOwnPrompt" name="prompt" rows="4" maxlength="1200" required></textarea><button class="primary">${esc(c.voiceBegin)}</button></form>`,
    });
    sheet.querySelector('[data-own-voice]').onsubmit = (event) => {
      event.preventDefault();
      const prompt = sheet.querySelector('textarea').value.trim();
      if (!prompt) return;
      const id = `voice:own:${crypto.randomUUID()}`;
      memory.enter({ id, title: prompt.slice(0, 90), intent: 'speaking', excerpt: prompt });
      sheet.close();
      ctx.go('practice', { id, intent: 'speaking' });
    };
  };
}

export function renderSpeaking(root, ctx) {
  const { c, language, location, memory } = ctx;
  const invitations = voiceInvitations(language);
  // No particular thing to say yet: offer the ways in that really exist.
  if (!location.id) return speakingLanding(root, ctx, invitations);
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
  /* Title first, data after (design update 2026-09-20): the screen opens on
     the line to say, not on a room heading over a situation label. */
  root.innerHTML = `${practiceReturn(c, 'speaking')}<section class="learning-workspace voice-workspace" data-workspace="activity"><div class="workspace-activity voice-exchange"><h1 class="sr-only">${esc(c.voiceTitle)}</h1><div data-voice></div></div><section class="workspace-result voice-result" aria-label="${esc(c.heard)}"><div class="workspace-result__bar"><button type="button" class="quiet" data-workspace-back>← ${esc(c.voiceBack)}</button></div><div class="workspace-result__scroll" data-voice-result-host aria-live="polite">${waiting}</div></section></section><div class="workspace-secondary"><aside class="voice-directions"><div class="heading-with-hint"><h2>${esc(c.voiceChoose)}</h2>${hint({ text: picked.own ? c.voiceOwnSource : c.voiceSource })}</div>${invitations.map((x) => `<a ${x.key === picked.key ? 'aria-current="true"' : ''} lang="${language}" href="${link('practice', { intent: 'speaking', id: `voice:${x.key}` })}">${esc(x.title)} ↗</a>`).join('')}<p lang="${language}">${esc(picked.cue)}</p></aside></div>${continuationShelf(ctx, 2)}`;
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
