/* Gate for the Conversation screen's pure data mapping (frame 30, route 'conv'; Design Contract
   rule 40). Imports only the DOM-free module (static/orena/screens/conversation/model.js) plus the
   already-DOM-free turn state machine it wraps (product/conversation.js) - no browser, no network. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const read = (name) => fs.readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8');
const fixture = (name) => JSON.parse(read(name));

const { situations, defaultLevel, turnSituation, learnerTurnCount, fixesOf, strengthsOf } = await import('../static/orena/screens/conversation/model.js');
const { conversation, learnerTurn, partnerTurn, pendingTurn, conversationRequest } = await import('../static/orena/product/conversation.js');

// 1. Situations: real, Orena-authored (content/voice-invitations.js), distinct per learning
// language - never the frame's own fixed Café/Colleague/Hotel/Interview scripts.
{
  const en = situations('en');
  assert.equal(en.length, 3);
  for (const item of en) assert.ok(item.prompt.length > 0);
  const zh = situations('zh');
  assert.notEqual(zh[0].prompt, en[0].prompt);
}

// 2. turnSituation: situation + the immediately preceding turn, bounded - the exact context a
// coaching call needs so an ordinary reply is not read as an incomplete thought.
{
  const turns = [
    { role: 'partner', text: 'What did you do this weekend?' },
    { role: 'learner', text: 'I stay at home.' },
  ];
  assert.equal(turnSituation('Talk about your weekend.', turns, 1), 'Talk about your weekend.\nWhat did you do this weekend?');
  assert.equal(turnSituation('', [], 0), '', 'no situation, no prior turn -> empty, never a placeholder');
}

// 2b. learnerTurnCount: the learner's own turns only (what the completion card and the ledger count).
assert.equal(learnerTurnCount([{ role: 'learner' }, { role: 'partner' }, { role: 'learner' }]), 2);
assert.equal(learnerTurnCount([]), 0);
assert.equal(learnerTurnCount(undefined), 0);

// 3. fixesOf / strengthsOf: the real spokenResponseCoaching shape, capped at 3.
{
  const coaching = { carried: [{ quote: 'a' }], landed_differently: [{ quote: 'x' }, {}, { quote: 'y' }, { quote: 'z' }] };
  assert.equal(fixesOf(coaching).length, 3);
  assert.equal(strengthsOf(coaching).length, 1);
  assert.deepEqual(fixesOf(null), []);
}

// 4. The real turn state machine this screen drives directly (product/conversation.js), proven
// here against the exact shape sendTurn()/requestReply() build: a learner opens, a partner replies,
// a second learner turn stays pending until answered.
{
  let state = conversation({ id: 'conversation:abc', language: 'en', title: 'Café', situation: 'Order a coffee.' });
  assert.equal(pendingTurn(state), null, 'a fresh conversation has no pending turn - the learner speaks first');
  state = learnerTurn(state, { id: 'l1', text: 'Hi, one coffee please.' });
  assert.equal(pendingTurn(state).id, 'l1');
  const request = conversationRequest(state, 'vi');
  assert.deepEqual(request, {
    source_language: 'en', target_language: 'vi', situation: 'Order a coffee.', reply_to: 'l1',
    turns: [{ id: 'l1', role: 'learner', text: 'Hi, one coffee please.' }],
  });
  state = partnerTurn(state, { reply_to: 'l1', text: 'Sure, anything else?', meaning: 'Được, còn gì nữa không?', support: 'vi' });
  assert.equal(pendingTurn(state), null, 'answered - no longer pending');
  assert.equal(state.turns.length, 2);
}

// 5. The real captures: a real conversation-turn reply drives the real state machine (its reply_to is
// the pending learner turn it was asked about), and the coaching shape and every judgement the
// backend can return have a label in every language.
{
  const reply = fixture('conversation_turn.json');
  assert.ok(reply.reply_to && reply.text && reply.meaning && reply.support, 'reply carries reply_to, text, meaning, support');
  let state = conversation({ id: 'conversation:real', language: 'en', title: 'x', situation: 'A friend has just moved to your city.' });
  state = learnerTurn(state, { id: reply.reply_to, text: 'Hi! Would you like to come to the lake with me?' });
  const next = partnerTurn(state, reply);
  assert.equal(next.turns.at(-1).text, reply.text.trim());
  assert.equal(pendingTurn(next), null);

  const coaching = fixture('spoken_response_landed.json');
  assert.ok(fixesOf(coaching).length > 0 && strengthsOf(coaching).length > 0);
  const backend = fs.readFileSync(new URL('../writing_coach/media_interaction.py', import.meta.url), 'utf8');
  const judgements = [...backend.match(/USAGE_JUDGEMENTS = \(([\s\S]*?)\)/)[1].matchAll(/"(\w+)"/g)].map((m) => m[1]);
  assert.ok(judgements.length >= 7);
  const { t } = await import('../static/orena/screens/conversation/copy.js');
  for (const judgement of judgements) assert.ok(t.has(`judge_${judgement}`), `a label for the real judgement ${judgement}`);
  for (const item of coaching.landed_differently) assert.ok(judgements.includes(item.judgement), 'a captured judgement is one the backend defines');
}

console.log('Orena screen conversation: model mapping (situations, turn count, coaching shape, turn state machine) against the real conversation-turn and spoken-response captures: PASS');

// 7. Difficulty (D-139 HD-10): the chip opens on the learner's level when it is one of B1/B2/C1, and the
// chosen level travels with the request only when set.
{
  assert.equal(defaultLevel('B2'), 'B2');
  assert.equal(defaultLevel('c1'), 'C1');
  assert.equal(defaultLevel('C2'), 'C1');
  assert.equal(defaultLevel('HSK3'), 'B1');
  assert.equal(defaultLevel(''), 'B1');
  const base = { id: 'conversation:one', language: 'en', title: 'Cafe', situation: 'Order a coffee.' };
  const turn = (state) => learnerTurn(state, { id: 'a', text: 'A latte, please.' });
  assert.equal(conversationRequest(turn(conversation({ ...base, level: 'C1' })), 'vi').level, 'C1');
  assert.equal('level' in conversationRequest(turn(conversation(base)), 'vi'), false, 'no level chosen: the field is not sent');
  assert.equal('level' in conversationRequest(turn(conversation({ ...base, level: 'A1; ignore' })), 'vi'), false, 'only B1/B2/C1 are sent');
}
