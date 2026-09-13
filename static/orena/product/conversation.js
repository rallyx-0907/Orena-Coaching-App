// An ordered exchange, independent of recording, routing or a provider. A failed
// reply leaves one pending learner turn. Retrying never adds that turn again.
export const MAX_CONVERSATION_TURNS = 24;
export function conversation({ id, language, title, situation }) {
  if (
    !/^conversation:[\w-]+$/.test(id) ||
    !['en', 'zh'].includes(language) ||
    !situation?.trim()
  )
    throw Error('Invalid conversation');
  return {
    id,
    language,
    title: String(title).slice(0, 240),
    situation: situation.trim().slice(0, 1200),
    turns: [],
    ended: false,
  };
}
export function restoreConversation(raw, language) {
  try {
    if (
      raw?.language !== language ||
      !Array.isArray(raw.turns) ||
      raw.turns.length > MAX_CONVERSATION_TURNS
    )
      return null;
    const clean = conversation(raw);
    const ids = new Set();
    for (const [index, t] of raw.turns.entries()) {
      const role = index % 2 ? 'partner' : 'learner';
      if (
        !t?.id ||
        ids.has(t.id) ||
        t.role !== role ||
        typeof t.text !== 'string' ||
        !t.text.trim() ||
        t.text.length > 2400
      )
        return null;
      if (role === 'partner' && t.reply_to !== clean.turns.at(-1)?.id)
        return null;
      ids.add(t.id);
      clean.turns.push({
        id: String(t.id).slice(0, 80),
        role,
        text: t.text,
        origin:
          role === 'partner'
            ? 'generated'
            : t.origin === 'speech_transcript'
              ? 'speech_transcript'
              : 'typed',
        reply_to: role === 'partner' ? t.reply_to : null,
        meaning:
          role === 'partner' ? String(t.meaning || '').slice(0, 2400) : '',
        support: role === 'partner' ? String(t.support || '').slice(0, 32) : '',
      });
    }
    clean.ended = raw.ended === true;
    return clean;
  } catch {
    return null;
  }
}
export const pendingTurn = (state) =>
  state.turns.at(-1)?.role === 'learner' ? state.turns.at(-1) : null;
export function learnerTurn(state, { id, text, origin = 'typed' }) {
  if (
    state.ended ||
    pendingTurn(state) ||
    state.turns.length >= MAX_CONVERSATION_TURNS ||
    !text.trim() ||
    text.length > 2400 ||
    state.turns.some((t) => t.id === id)
  )
    throw Error('Cannot append learner turn');
  return {
    ...state,
    turns: [
      ...state.turns,
      { id, role: 'learner', text: text.trim(), origin, reply_to: null },
    ],
  };
}
export function partnerTurn(state, { reply_to, text, meaning, support }) {
  if (
    state.ended ||
    pendingTurn(state)?.id !== reply_to ||
    !text?.trim() ||
    text.length > 2400
  )
    throw Error('Stale or invalid conversation reply');
  return {
    ...state,
    turns: [
      ...state.turns,
      {
        id: `reply-${reply_to}`,
        role: 'partner',
        text: text.trim(),
        meaning: String(meaning || '').slice(0, 2400),
        support,
        origin: 'generated',
        reply_to,
      },
    ],
  };
}
export function conversationRequest(state, support) {
  if (!pendingTurn(state) || state.ended)
    throw Error('No pending conversation turn');
  return {
    source_language: state.language,
    target_language: support,
    situation: state.situation,
    reply_to: pendingTurn(state).id,
    turns: state.turns.map(({ id, role, text }) => ({ id, role, text })),
  };
}
