import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  conversation,
  learnerTurn,
  partnerTurn,
  pendingTurn,
  conversationRequest,
  restoreConversation,
  needsOpening,
  conversationOpeningRequest,
  withOpening,
} from '../static/orena/product/conversation.js';
import { learnerMemory } from '../static/orena/product/memory.js';
import { continuationLink, route } from '../static/orena/product/intent.js';
for (const language of ['en', 'zh']) {
  const entries = new Map(),
    storage = {
      getItem: (k) => entries.get(k),
      setItem: (k, v) => entries.set(k, v),
    };
  const memory = learnerMemory(storage, 'owner', language);
  let state = conversation({
    id: 'conversation:test',
    language,
    title: 'A visit',
    situation: 'Invite a friend.',
  });
  state = learnerTurn(state, {
    id: 'one',
    text: language === 'en' ? 'Come to the park.' : '来公园吧。',
  });
  memory.conversation(state);
  const recovered = learnerMemory(storage, 'owner', language).value
    .conversations[state.id];
  assert.equal(pendingTurn(recovered).id, 'one');
  assert.deepEqual(
    conversationRequest(recovered, 'vi'),
    conversationRequest(state, 'vi'),
    'Retry preserves the exact exchange',
  );
  assert.throws(() => learnerTurn(state, { id: 'two', text: 'Oops' }));
  assert.throws(() =>
    partnerTurn(state, { reply_to: 'other', text: 'Late reply' }),
  );
  const previous = state;
  state = partnerTurn(state, {
    reply_to: 'one',
    text: 'What do you like there?',
    meaning: 'Bạn thích gì ở đó?',
    support: 'vi',
  });
  assert.equal(previous.turns.length, 1, 'The pending ledger is immutable');
  assert.throws(() =>
    partnerTurn(state, { reply_to: 'one', text: 'Duplicate' }),
  );
  state = learnerTurn(state, {
    id: 'two',
    text: 'The quiet mornings.',
    origin: 'speech_transcript',
  });
  assert.equal(
    conversationRequest(state, 'en').turns.length,
    3,
    'The partner receives cross-turn context',
  );
  memory.conversation(state);
  assert.equal(
    learnerMemory(storage, 'another', language).value.conversations[state.id],
    undefined,
  );
  assert.equal(
    learnerMemory(storage, 'owner', language === 'en' ? 'zh' : 'en').value
      .conversations[state.id],
    undefined,
  );
  assert.equal(
    restoreConversation({ ...state, turns: [state.turns[1]] }, language),
    null,
  );
  assert.throws(() =>
    partnerTurn(
      { ...state, ended: true },
      { reply_to: 'two', text: 'Too late' },
    ),
  );
  assert.equal(
    route(continuationLink({ id: state.id, intent: 'speaking' })).page,
    'conversation',
  );
}

/* The partner is instructed not to coach: a conversation where every reply
   corrects you is not a conversation. That instruction assumes a separate
   action exists, and it now does - on the learner's own turns only. */
const conversationScreen = readFileSync(
  new URL('../static/orena/screens/conversation/screen.js', import.meta.url),
  'utf8',
);
assert.ok(
  conversationScreen.includes("turn.role === 'learner' && !card ? html`<button type=\"button\" class=\"s-conv__land\""),
  'only a turn the learner produced can be coached',
);
assert.ok(
  conversationScreen.includes("if (!turn || turn.role !== 'learner' || coaching.has(index)) return;"),
  'the handler refuses a partner turn even if the markup ever offered one',
);
// What the learner was answering travels with the words: an ordinary reply to
// a question should not be read as an incomplete thought.
assert.ok(
  conversationScreen.includes('situation: turnSituation(convo.situation, convo.turns, index)'),
  'coaching is told what the turn was answering',
);
// The backend keeps its side of the same bargain.
const partner = readFileSync(
  new URL('../writing_coach/conversation.py', import.meta.url),
  'utf8',
);
assert.ok(
  partner.includes('Do not correct or coach unless asked'),
  'the partner must stay a partner',
);
assert.ok(
  partner.includes('Never claim to be a real person'),
  'a simulated partner says it is simulated',
);

/* S-24: the partner speaks first. The opening is not a turn: the alternation, the account record and the
   learner-first state machine stay as they were; the line rides along as context. */
for (const language of ['en', 'zh']) {
  let open = conversation({ id: 'conversation:open', language, title: 'Cafe', situation: 'Order a coffee.', level: 'B2' });
  assert.equal(needsOpening(open), true);
  assert.deepEqual(conversationOpeningRequest(open, 'vi'), {
    source_language: language, target_language: 'vi', situation: 'Order a coffee.', opening: true, level: 'B2',
  });
  assert.throws(() => conversationRequest(open, 'vi'), 'no learner turn yet, so no turn request');
  open = withOpening(open, { text: 'Welcome! What can I get you?', meaning: 'Chao mung!', support: 'vi' });
  assert.equal(needsOpening(open), false);
  assert.equal(open.turns.length, 0, 'the opening line is not a turn');
  assert.throws(() => conversationOpeningRequest(open, 'vi'), 'asked once');
  assert.throws(() => withOpening(conversation({ id: 'conversation:x', language, title: 't', situation: 's' }), { text: ' ' }));
  open = learnerTurn(open, { id: 'one', text: 'A latte, please.' });
  assert.equal(conversationRequest(open, 'vi').opening_line, 'Welcome! What can I get you?');
  assert.equal(conversationRequest(open, 'vi').turns[0].role, 'learner');
  const restored = restoreConversation(JSON.parse(JSON.stringify(open)), language);
  assert.equal(restored.opening.text, 'Welcome! What can I get you?');
  assert.equal(restoreConversation({ ...open, opening: { text: 'x'.repeat(2401) } }, language).opening, null);
  assert.equal(conversationRequest(conversation({ id: 'conversation:y', language, title: 't', situation: 's' }) && learnerTurn(conversation({ id: 'conversation:y', language, title: 't', situation: 's' }), { id: 'a', text: 'Hi' }), 'vi').opening_line, undefined);
}

console.log(
  'Conversation ledger, coaching on your own turns and the partner opening: PASS',
);
