import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
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

/* The partner is instructed not to coach: a conversation where every reply
   corrects you is not a conversation. That instruction assumes a separate
   action exists, and it now does - on the learner's own turns only. */
const conversationUi = readFileSync(
  new URL('../static/orena/ui/conversation.js', import.meta.url),
  'utf8',
);
assert.ok(
  conversationUi.includes("turn.role === 'learner' ? `<button class=\"quiet\" data-coach-turn="),
  'only a turn the learner produced can be coached',
);
assert.ok(
  conversationUi.includes("if (turn?.role !== 'learner') return;"),
  'the handler refuses a partner turn even if the markup ever offered one',
);
assert.ok(
  conversationUi.includes('loadSpokenCoaching('),
  'coaching reuses the shared surface rather than a second one',
);
// What the learner was answering travels with the words: an ordinary reply to
// a question should not be read as an incomplete thought.
assert.ok(
  conversationUi.includes('[state.situation, state.turns[index - 1]?.text]'),
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
for (const ui of ['en', 'zh'])
  assert.ok(copy[ui].conversationHowItLanded, `${ui}: no label for the coaching action`);

/* The shelf must tell two threads apart. A conversation and a single take are
   both Speaking about the same situation, and used to render identically -
   the only way to tell them apart was to open one. */
const patterns = readFileSync(
  new URL('../static/orena/ui/patterns.js', import.meta.url),
  'utf8',
);
assert.ok(
  patterns.includes("item.id.startsWith('conversation:')"),
  'the shelf names a thread by its shape, not only its intention',
);
assert.ok(
  patterns.includes('memory.value.conversations?.[item.id]'),
  'a conversation on the shelf reports its own state',
);
assert.ok(
  patterns.includes('state.turns.length'),
  'how far a conversation got is worth more than "there is more"',
);
for (const ui of ['en', 'zh']) {
  assert.ok(copy[ui].conversationTurnsSoFar, `${ui}: no label for turns so far`);
  // The shape label and the plain intention must not read the same, or the
  // two threads collapse again.
  assert.notEqual(
    copy[ui].conversationTitle,
    copy[ui].speakingName,
    `${ui}: a conversation reads the same as a single take`,
  );
}

/* --- Asking about a turn must send the turn the learner selected ---

   The server refuses a context that does not contain the selection, so a
   context budgeted from the start of the pair fails outright when the
   preceding turn is long enough to fill the allowance on its own. The turn
   holding the selection is never the part that gets trimmed. */
const { turnContext, CONTEXT_LIMIT, SELECTION_LIMIT } = await import(
  '../static/orena/ui/conversation.js'
);

const contains = (turns, index) => {
  const selection = turns[index].text.slice(0, SELECTION_LIMIT);
  const context = turnContext(turns, index);
  assert.ok(context.length <= CONTEXT_LIMIT, `context over budget: ${context.length}`);
  assert.ok(
    context.toLowerCase().includes(selection.toLowerCase()),
    'the server would reject this: the selection is not in its own context',
  );
  return context;
};

// The ordinary case still carries what came before.
const short = [{ text: 'Where did you go?' }, { text: 'I went to the market.' }];
assert.equal(turnContext(short, 1), ['Where did you go?', 'I went to the market.'].join('\n'));
contains(short, 1);
assert.equal(turnContext(short, 0), 'Where did you go?', 'the first turn has nothing before it');

/* The finding's case: a preceding turn permitted to fill the entire budget.
   Taking the first 2400 characters kept it and dropped the learner's own
   sentence entirely. */
const longPair = [{ text: 'x'.repeat(CONTEXT_LIMIT) }, { text: 'I meant it kindly.' }];
const budgeted = contains(longPair, 1);
assert.ok(budgeted.endsWith('I meant it kindly.'), 'the selected turn survives, whole');
assert.ok(budgeted.startsWith('x'), 'the room that remains still goes to what came before');

// A turn longer than the whole budget still yields a context holding its
// selection, because the selection is capped below the context.
const huge = [{ text: 'y'.repeat(50) }, { text: 'z'.repeat(CONTEXT_LIMIT * 2) }];
contains(huge, 1);

// Chinese counts the same way: characters, not bytes.
const zh = [{ text: '很'.repeat(CONTEXT_LIMIT) }, { text: '我昨天去了商店。' }];
const zhContext = contains(zh, 1);
assert.ok(zhContext.endsWith('我昨天去了商店。'));

console.log(
  'Conversation ledger, coaching on your own turns, distinguishable threads, and context that keeps its selection: PASS',
);
