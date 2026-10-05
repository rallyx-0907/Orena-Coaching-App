/* Gate for the Orena surface's pure logic (static/orena/screens/orena/model.js, cards.js): the
   one context-label formatter shared by the Contextual panel and full-screen voice (E5 §6.6 open
   question 7), the real-suggestions-only starter list (rule 40 - no static starter chips), the
   voice phase -> mascot-state/status/hint mapping, the coach-notes sort (address note first), the
   rule-40 "last active" drop, the action-card's real-`display`-or-nothing rendering, and the
   evidence note's real-fields-only rendering. DOM-free: imports only model.js/cards.js/copy.js,
   no browser. */
import assert from 'node:assert/strict';

// copy/index.js resolves the interface language at import time from window.localStorage/navigator.
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { t } = await import('../static/orena/screens/orena/copy.js');

// LEX-006: Orena's answers render their Markdown meaning, never its syntax, and never a command link.
{
  const { richText, richInline, hasBlocks, plainText } = await import('../static/orena/kit/rich-text.js');
  const reply = '### 花生\n**Nghĩa chính:** đậu phộng\n\n- 我爱吃花生。 *Tôi thích ăn lạc.*\n- `huāshēng`\n\n> Hạt nằm dưới đất.\n\n[Open word](command:navigate?{"route":"word","params":{"word":"花生"}}) Tap Open word';
  const out = String(richText(reply));
  assert.ok(out.includes('<p class="o-rich__h">花生</p>'), 'a heading is a heading');
  assert.ok(out.includes('<strong>Nghĩa chính:</strong>'), 'bold is bold');
  assert.ok(out.includes('<ul class="o-rich__list"><li>我爱吃花生。 <em>Tôi thích ăn lạc.</em></li>'), 'a list with emphasis');
  assert.ok(out.includes('<code class="o-rich__code">huāshēng</code>'), 'inline code');
  assert.ok(out.includes('<blockquote class="o-rich__quote">Hạt nằm dưới đất.</blockquote>'), 'a quote');
  for (const syntax of ['**', '###', '](', 'command:', '{"route"', '&gt; ']) assert.ok(!out.includes(syntax), `no ${syntax} syntax shown`);
  assert.ok(!out.includes('Open word</a>'), 'an app command is not link text (its action card names it)');
  assert.ok(String(richInline('[docs](https://example.com/a(b)c)')).includes('href="https://example.com/a(b)c"'), 'a web link with brackets stays a link');
  assert.ok(String(richInline('<img src=x onerror=1> **ok**')).startsWith('&lt;img'), 'everything is escaped first');
  assert.ok(!String(richInline('Đang viết **nghĩa', { streaming: true })).includes('**'), 'an unclosed marker is held back while streaming');
  assert.equal(hasBlocks('one line'), false);
  assert.equal(hasBlocks('- item'), true);
  assert.equal(plainText('**Nghĩa:** đậu phộng [Open word](command:navigate?{}) và *lạc*'), 'Nghĩa: đậu phộng  và lạc');
}
const { setLanguages } = await import('../static/orena/copy/index.js');
const {
  surfaceTitle,
  contextLabel,
  latestSuggestions,
  voicePhaseMarkState,
  voicePhaseStatusKey,
  voicePhaseHintKey,
  sortedMemoryNotes,
  noteKindLabel,
  homeSubtitle,
  contextKey,
  speakableText,
  offerableActions,
  actionFailureKey,
  contextParts,
  thinkingText,
  errorText,
  endsVoice,
} = await import('../static/orena/screens/orena/model.js');
const { actionCardMarkup, evidenceMarkup, durationLabel, displayKindLabel, hasCard } = await import('../static/orena/screens/orena/cards.js');

// 1. surfaceTitle: resolves through the real route table, from real §6.1 ids only.
assert.equal(surfaceTitle('vocabulary.word'), 'Word', 'vocabulary.word -> the word route\'s real title');
assert.equal(surfaceTitle('grammar.catalog'), 'Grammar');
assert.equal(surfaceTitle('not.a.real.surface'), '', 'an id with no route resolves to nothing, never a guess');

// 2. contextLabel: caller label wins; else "{text} · {kind}"; else the surface title alone; else ''.
assert.equal(contextLabel({ label: 'Present perfect · Grammar' }, t), 'Present perfect · Grammar', 'an explicit caller label is used as-is');
assert.equal(contextLabel({ selected_item: { type: 'word', text: '是' }, surface: 'vocabulary.word' }, t), '是 · Word');
assert.equal(contextLabel({ selected_item: { type: 'sentence', text: 'I moved here in 2019.' } }, t), 'I moved here in 2019. · Sentence', 'the item\'s own kind label is used even with no resolvable surface');
// LEX-013: a dragged part of a sentence (not ending like one) is a "Part", as the server's opening says.
assert.equal(contextLabel({ selected_item: { type: 'sentence', text: '我们屋' } }, t), '我们屋 · Part');
assert.equal(contextLabel({ selected_item: { type: 'sentence', text: '“让它荒着怪可惜的。”' } }, t), '“让它荒着怪可惜的。” · Sentence');
assert.equal(contextLabel({ surface: 'writing.review' }, t), 'Writing', 'no selected item -> the surface title alone');
assert.equal(contextLabel({}, t), '', 'nothing real to show -> empty, never invented (rule 40)');

// 3. latestSuggestions: only the most recent Orena turn's own real `suggestion` events - never a
// static list, and never a stale list from an earlier turn once a newer one has none.
{
  const withSuggestions = [
    { role: 'learner', text: 'hi' },
    { role: 'orena', suggestions: [{ label: 'Review due words', intent: 'prompt.review_due' }] },
  ];
  assert.deepEqual(latestSuggestions(withSuggestions), [{ label: 'Review due words', intent: 'prompt.review_due' }]);
  const thenNone = [...withSuggestions, { role: 'learner', text: 'ok' }, { role: 'orena', suggestions: [] }];
  assert.deepEqual(latestSuggestions(thenNone), [], 'a later turn with no suggestions clears the row, not the older one');
  assert.deepEqual(latestSuggestions([]), []);
}

// 4. voice phase mapping: every phase resolves to one of intelChip's real state keys/copy keys;
// an unknown phase falls back to idle, never throws.
for (const phase of ['idle', 'listening', 'thinking', 'speaking', 'error']) {
  assert.ok(voicePhaseMarkState(phase), `${phase} has a mark state`);
  assert.ok(t.has(voicePhaseStatusKey(phase)), `${phase}'s status key is real copy`);
}
assert.equal(voicePhaseMarkState('bogus'), voicePhaseMarkState('idle'));
assert.equal(voicePhaseHintKey('error'), '', 'no hint line for the error phase - a dedicated message is shown instead');
assert.equal(voicePhaseHintKey('listening'), 'voiceHintListening');

// 5. sortedMemoryNotes: the address note first (the learner's identity choice), then by weight.
{
  const notes = [
    { id: 'n1', kind: 'preference', weight: 0.4 },
    { id: 'address-vi', kind: 'address', weight: 1 },
    { id: 'n2', kind: 'goal', weight: 0.9 },
  ];
  const sorted = sortedMemoryNotes(notes);
  assert.equal(sorted[0].id, 'address-vi');
  assert.equal(sorted[1].id, 'n2');
  assert.equal(sorted[2].id, 'n1');
}
assert.equal(noteKindLabel('address', t), t('memoryKindAddress'));
assert.equal(noteKindLabel('goal', t), t('memoryKindGoal'));
assert.equal(noteKindLabel('unknown-kind', t), t('memoryKindPreference'), 'an unrecognised kind falls back, never throws');

// 6. homeSubtitle: real language label only - never the frame's fixed "last active" clause,
// which has no backing data anywhere in this build (product/memory.js's continuation carries no
// timestamp at all).
assert.equal(homeSubtitle('English · B1', t), 'Knows your English · B1');
assert.equal(homeSubtitle('', t), '', 'no real language label -> no subtitle line at all');
assert.doesNotMatch(homeSubtitle('English', t), /last active/i, 'the invented "last active" clause is never produced');

// 7. contextKey: distinguishes real contexts, groups the same one.
assert.equal(contextKey({ surface: 'vocabulary.word', selected_item: { type: 'word', text: '是' } }), contextKey({ surface: 'vocabulary.word', selected_item: { type: 'word', text: '是' } }));
assert.notEqual(contextKey({ surface: 'vocabulary.word', selected_item: { type: 'word', text: '是' } }), contextKey({ surface: 'vocabulary.word', selected_item: { type: 'word', text: '不' } }));

// 8. speakableText: only a finished, error-free reply's real segments, skipping `reference` audio
// segments (§5.2 - those are played through their own action, never read aloud as conversation).
assert.equal(speakableText({ done: true, segments: [{ text: 'Hello', voice_style: 'neutral_explain' }, { text: 'ni hao', voice_style: 'reference' }] }), 'Hello', 'a reference segment is excluded from speech');
assert.equal(speakableText({ done: false, segments: [{ text: 'partial' }] }), '', 'not done yet -> nothing to speak');
assert.equal(speakableText({ done: true, error: { message: 'x' }, segments: [{ text: 'x' }] }), '', 'an errored reply is never read aloud');
assert.equal(speakableText(null), '');

// 9. actionCardMarkup: real `display` fields only, written in the learner's language - never a
// raw enum, an invented kind/title/reason, or a card around a button that has nothing to say. The
// label is always shown (it is the only thing the contract guarantees, §7).
{
  const noDisplay = String(actionCardMarkup({ id: 'a1', type: 'save_word', label: 'Save word' }, {}));
  assert.match(noDisplay, /Save word/);
  assert.match(noDisplay, /s-orena-action--bare/, 'no display -> the button alone, not an empty card');
  assert.doesNotMatch(noDisplay, /s-orena-action__(eyebrow|title|reason)/, 'no display -> no invented lines');
  const display = { title: 'A Morning in the City', kind: 'writing', duration_s: 480, reason: 'Có 3 cụm bạn đã lưu hôm qua.' };
  const withDisplay = String(actionCardMarkup({ id: 'a2', type: 'navigate', label: 'Revise', display }, {}));
  assert.match(withDisplay, /A Morning in the City/);
  assert.match(withDisplay, /Writing · ~8 min/, 'the kind is written out and duration_s is whole minutes, as the frame writes it');
  assert.match(withDisplay, /Có 3 cụm/, 'the reason is the support-language line the server wrote');
  assert.doesNotMatch(withDisplay, /--bare/);
  assert.doesNotMatch(String(actionCardMarkup({ id: 'a2', type: 'navigate', label: 'Revise', display: { title: 'X', kind: 'not_a_kind' } }, {})), /not_a_kind/, 'an unknown kind is never shown raw');
  assert.equal(durationLabel(20), '~1 min', 'under a minute rounds up to one');
  assert.equal(durationLabel(0), '', 'no duration -> nothing, never an estimate');
  assert.equal(durationLabel(undefined), '');
  assert.equal(displayKindLabel('review'), 'Review');
  assert.equal(displayKindLabel('nope'), '');
  assert.equal(hasCard({ kind: 'not_a_kind' }), false, 'a display with nothing drawable is no card');
  assert.equal(hasCard({ reason: 'r' }), true);
  const done = String(actionCardMarkup({ id: 'a3', type: 'save_word', label: 'Save word' }, { done: true }));
  assert.match(done, /disabled/, 'a ran action is disabled, never silently re-runnable');
}

// 10. evidenceMarkup: only what the contract's evidence event carries - the source's name and, when
// the server sent it, `display.title`/`kind`. Never the raw excerpt (data the frames never draw),
// a raw source id, or the frame's thumbnail/meta/chevron (E5 §9 point 1: a named, undrawn gap).
{
  const note = String(evidenceMarkup({ id: 'e1', source: 'speech.pronunciation', excerpt: { pinyin: 'shi', tone: 4, score: 6, flagged: true } }));
  assert.match(note, /Pronunciation/);
  assert.doesNotMatch(note, /pinyin|tone|score|flagged/, 'the excerpt is not printed as key: value');
  assert.doesNotMatch(note, /<img/, 'no thumbnail is ever invented - the real event carries none');
  const card = String(evidenceMarkup({ id: 'e2', source: 'writing.evaluation', display: { title: 'A Morning in the City', kind: 'writing' } }));
  assert.match(card, /s-orena-source__kind">Writing</);
  assert.match(card, /A Morning in the City/);
  assert.equal(String(evidenceMarkup({ id: 'e3', source: 'something.new' })), '', 'a source this build has no name for is not drawn raw');
}

// 9b. The same words in Vietnamese and Chinese (interface language), placeholders kept.
setLanguages({ ui: 'vi' });
assert.equal(durationLabel(480), '~8 phút');
assert.equal(displayKindLabel('grammar'), 'Ngữ pháp');
setLanguages({ ui: 'zh' });
assert.equal(durationLabel(480), '约 8 分钟');
assert.equal(displayKindLabel('speaking'), '口语');
setLanguages({ ui: 'en' });

// 11. offerableActions (AGENT_CONTRACT §7): an unknown type, or one this client cannot run right
// now, is ignored - never drawn as a button that does nothing - and a workspace's action shows
// only while that workspace is mounted (dispatcher.supported() is read at paint time).
{
  const logged = [];
  const log = (...args) => logged.push(args.join(' '));
  const actions = [
    { id: 'a1', type: 'save_word', label: 'Save word' },
    { id: 'a2', type: 'play_model', label: 'Play model' },
    { id: 'a3', type: 'rm_rf', label: 'Nope' },
  ];
  assert.deepEqual(offerableActions(actions, ['navigate', 'save_word'], log).map((a) => a.id), ['a1'], 'only what this client can run is offered');
  assert.deepEqual(offerableActions(actions, ['navigate', 'save_word', 'play_model'], log).map((a) => a.id), ['a1', 'a2'], 'a mounted workspace offers its action');
  assert.equal(logged.length, 2, 'each ignored action is logged once (a2 while unsupported, a3 always), not on every paint');
  offerableActions(actions, ['save_word'], log);
  assert.equal(logged.length, 2, 'a repaint does not log an ignored action again');
  assert.deepEqual(offerableActions(undefined, ['save_word'], log), []);
}

// 12. actionFailureKey: a tap that did not run says so once, in one short line; a refused
// confirmation is the learner's own answer and says nothing.
assert.equal(actionFailureKey({ ok: true }), '');
assert.equal(actionFailureKey({ ok: false, reason: 'declined' }), '', 'declining a confirmation is not an error');
assert.equal(actionFailureKey({ ok: false, reason: 'other_language' }), 'actionOtherLanguage');
assert.equal(actionFailureKey({ ok: false, reason: 'failed' }), 'actionFailed');
assert.equal(actionFailureKey(null), 'actionFailed', 'no result at all is a failure, not success');
for (const key of ['actionOtherLanguage', 'actionFailed']) assert.ok(t.has(key), `${key} is real copy`);

// 13. The design's voice marks (`voiceMark`: idle ol-intel, listening ol-intel-listen, thinking
// ol-intel-think, speaking ol-intel-speak); a failed turn reads as idle, not as a made-up state.
assert.deepEqual(['idle', 'listening', 'thinking', 'speaking', 'error'].map(voicePhaseMarkState), ['idle', 'listening', 'thinking', 'speaking', 'idle']);

// 14. contextParts: the pill's label in two parts, so the learning-language text is marked with its
// own language; the joined form is the one contextLabel returns.
assert.deepEqual(contextParts({ selected_item: { type: 'word', text: '是', lang: 'zh-CN' }, surface: 'vocabulary.word' }, t), { text: '是', lang: 'zh-CN', kind: 'Word' });
assert.deepEqual(contextParts({ label: 'Present perfect · Grammar' }, t), { text: 'Present perfect · Grammar', lang: '', kind: '' });
assert.deepEqual(contextParts({ surface: 'writing.review' }, t), { text: '', lang: '', kind: 'Writing' });
assert.deepEqual(contextParts({}, t), { text: '', lang: '', kind: '' });

// 15. §4 "shows tool_call.label while a tool runs"; §4.1 the client's own transport error carries
// no server message, so the message is the client's own copy; text_only ends voice mode; S12 (a
// soft-limited turn) is a short text answer with no voice.
assert.equal(thinkingText({ name: 'get_pronunciation_attempt', label: 'Looking at your latest take' }, 'Orena is thinking…'), 'Looking at your latest take');
assert.equal(thinkingText(null, 'Orena is thinking…'), 'Orena is thinking…');
assert.equal(thinkingText({ label: '  ' }, 'Orena is thinking…'), 'Orena is thinking…');
assert.equal(errorText({ class: 'provider_unavailable', message: 'Orena is busy right now. Try again soon.' }, 'fallback'), 'Orena is busy right now. Try again soon.');
assert.equal(errorText({ class: 'transport', message: '' }, t('transportError')), t('transportError'));
assert.equal(endsVoice({ error: { class: 'voice_unavailable', fallback: 'text_only' } }), true);
assert.equal(endsVoice({ error: { class: 'provider_unavailable', fallback: 'retry' } }), false);
assert.equal(endsVoice(null), false);
assert.equal(speakableText({ done: true, metered: 'soft_limited', segments: [{ text: 'A short answer for now.' }] }), '', 'a metered turn has no voice');
assert.equal(speakableText({ done: true, metered: 'ok', segments: [{ text: 'Hello' }] }), 'Hello');

console.log('Orena (Home/Contextual panel/voice/memory sheet): context label, real-suggestions-only starters, voice phase mapping, coach-notes sort, rule-40 subtitle, action/evidence real-fields-only rendering all hold: PASS');
