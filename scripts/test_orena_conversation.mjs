import assert from 'node:assert/strict';
import {
  conversation,
  learnerTurn,
  partnerTurn,
  pendingTurn,
  conversationRequest,
  restoreConversation,
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
console.log(
  'Conversation ledger: cross-turn context, owner/language isolation, retries, stale replies, closing and recovery PASS',
);
