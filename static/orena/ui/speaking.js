import { esc, dialog } from './html.js';
import { voiceInvitations } from '../content/voice-invitations.js';
import { renderLibraryBrowse } from './library-browse.js';
import { mountSpeakingWorkspace, sourceFromLesson, sourceFromItem } from './speaking-workspace.js';
import { mountFreeTalk } from './speaking-free.js';
import { refCopy } from './reference.js';
import { speakCopy } from './speaking-copy.js';
import { encounter } from '../product/encounter.js';

/* The Speaking workspace: one line at a time, said and assessed. Its lines come from a Listening
   lesson (`media:<lesson>`) - the clip is the model - and, once one has content, from the Speaking
   catalogue (docs/project/UI_BACKEND_GAPS.md, SP-1). It opens on `line`, else where the learner
   last was, else the first line. */
export async function renderSpeakingWorkspace(root, ctx) {
  const { api, language, location, memory } = ctx;
  const id = String(location.id || '');
  let source = null;
  if (id.startsWith('speak:')) {
    const item = await api.speakingItem(id.slice(6));
    if (!ctx.alive()) return () => {};
    if (item?.language !== language || !item.lines?.length) throw Error(ctx.c.unavailable);
    source = sourceFromItem(item, ctx.support);
  } else if (id.startsWith('media:')) {
    const payload = await api.listeningLibraryLesson(id.slice(6), ctx.support);
    if (!ctx.alive()) return () => {};
    if (!payload?.transcript?.segments?.length || payload.asset?.source_language !== language)
      throw Error(ctx.c.unavailable);
    source = sourceFromLesson(id, payload, encounter(payload, ctx.support));
  } else if (id.startsWith('say:')) {
    // One line to say, handed over by free talk ("say the corrected line"): no model clip.
    const text = id.slice(4).trim().slice(0, 400);
    if (!text) throw Error(ctx.c.unavailable);
    source = {
      id,
      title: speakCopy(ctx.ui, ctx.support).ftSayFixed,
      level: '',
      assetId: '',
      playback: null,
      modelAudio: null,
      poster: '',
      lines: [{ id: 'say', text, original: text, reading: '', readings: [], meaning: '', startMs: 0, endMs: 0 }],
    };
  } else throw Error(ctx.c.unavailable);
  const prior = memory.value.continuation.find((item) => item.id === id)?.segment;
  const wanted = location.line || prior || '';
  const startIndex = Math.max(0, source.lines.findIndex((line) => line.id === wanted));
  return mountSpeakingWorkspace(root, ctx, source, {
    startIndex,
    // Back to where the learner came from; with no history in this tab, to the Speaking library.
    onLeave: () => (history.length > 1 ? history.back() : ctx.go('practice', { intent: 'speaking' })),
  });
}

/* The Speaking library (Orena Speaking, "Speaking library"): the shared library template scoped to
   what can be said - lines from the Speaking catalogue, Listening lessons to shadow, and the
   situations to answer freely - with the practice types as chips (ui/library-browse.js). Only real
   items appear; a type with no item has no chip. The learner's own topic is the bar's action. */
async function speakingLibrary(root, ctx, invitations) {
  const { api, language } = ctx;
  const listed = await api.speakingLibrary(language);
  if (!ctx.alive()) return () => {};
  const free = invitations.map((x) => ({
    id: `voice:${x.key}`,
    practice_type: 'free',
    title: x.title,
    language,
    level: '',
    line_count: 0,
    duration_ms: null,
    artwork: 'conversation',
  }));
  return renderLibraryBrowse(root, ctx, { speaking: [...(listed?.items || []), ...free] }, {
    only: ['speaking'],
    onImport: () => ownPrompt(ctx),
  });
}

function ownPrompt(ctx) {
  const { c, memory } = ctx;
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
}

export async function renderSpeaking(root, ctx) {
  const { c, language, location, memory } = ctx;
  const invitations = voiceInvitations(language);
  // No particular thing to say yet: the Speaking library.
  if (!location.id) return speakingLibrary(root, ctx, invitations);
  /* Free talk: an authored situation, or the learner's own topic kept in device memory. */
  const at = invitations.findIndex((x) => `voice:${x.key}` === location.id);
  const own = memory.value.continuation.find((x) => x.id === location.id);
  const picked = at >= 0 ? invitations[at] : own?.excerpt ? { title: own.title, prompt: own.excerpt, cue: '' } : null;
  if (!picked) throw Error(c.unavailable);
  const next = invitations.length ? `voice:${invitations[(at + 1) % invitations.length].key}` : '';
  return mountFreeTalk(root, ctx, {
    id: location.id,
    // The frame's bar names the practice ("Nói tự do"); the situation itself is the topic card.
    title: refCopy(ctx).libraryKind_speak_free,
    // The situation's own short name for the result's bar ("Nói tự do · <name>").
    name: picked.title,
    topic: picked.prompt,
    cue: picked.cue,
    next,
  });
}
