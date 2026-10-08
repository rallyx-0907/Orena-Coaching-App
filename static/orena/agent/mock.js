/* The UI lane's mock agent (AGENT_CONTRACT §11): replays the contract's canonical streams (§12)
   with no backend, so the new UI is built and tested against the exact event sequence and payload
   shapes the intelligence lane's server must also produce. Only the wording differs; the mock
   speaks the request's support language (vi, en or zh), and labels its action buttons in the
   interface language (§7, D-094), so every language combination can be reviewed. Nothing here is
   product copy or learner data.

   §5.6: every line addressed to the learner applies `context.address`, with that language's default
   when it is absent - vi and zh-CN substitute the learner's own {self}/{user} terms into the reply
   (capitalised at the sentence's start); English never replaces "I"/"you", so a custom `user` name
   only adds a vocative ("Minh, …"), never a mid-sentence swap (§5.6 "it never replaces you"). S14
   and S15 are the two streams §5.6 adds: S14 sets the pair and already speaks in it; S15 answers
   "who are you" by rule, in the address the request carries.

   Selection: a forced stream (`?agent=S2b` in the address, for review), else the request itself -
   an opening turn is S13, a request about another learner's progress S8, a request to set the
   address S14, "who are you" S15, "save" on a selected word S5, a question on a writing review S9,
   a question on a flagged pronunciation S2, anything else S1. `?agent=H404`, `H409` or `H429` plays
   what the transport makes of that HTTP status (§2.1): Orena absent, the language changed
   elsewhere, or a short wait before the turn is sent again and answered. */
import { CONTRACT_VERSION, toContractLang, resolveAddress, capitalizeTerm, addressNoteId } from './contract.js';

const WORDS = {
  vi: {
    s1: 'Màn này là nơi {user} học và ôn lại những gì đã gặp. Chọn một mục để bắt đầu.',
    s1s: 'Ôn từ đến hạn',
    s5: 'Bấm {label} để thêm {w} vào từ vựng của {user}.',
    s5l: 'Lưu từ',
    s8: '{Self} chỉ xem được tiến độ của chính {user}.',
    s9: 'Bài này {user} hay sai thì của động từ ở câu kể lại, và hai lần dùng giới từ chưa đúng.',
    s9l: 'Sửa bài',
    s9t: 'Đang xem bài chấm gần nhất',
    s2t: 'Đang xem lần nói gần nhất',
    s2: 'Âm {w} bị đánh dấu là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:',
    s2b: 'Âm {w} được chấm thấp hơn các âm khác (71/100) nhưng không bị đánh dấu sai.',
    s2p: 'Nghe mẫu',
    s2a: 'Nói lại',
    s12: '{Self} trả lời ngắn thôi nhé.',
    s13: 'Chào {user}. Hôm nay {user} muốn ôn từ, đọc hay luyện nói?',
    s13a: 'Tôi nên học gì hôm nay?',
    s13b: 'Giải thích một từ',
    s14: 'Được rồi, từ giờ {self} gọi {user} là {user} nhé.',
    s14n: 'Xưng hô: Orena xưng "{self}", gọi người học là "{user}".',
    s15: '{Self} là Orena, trợ lý học tập AI của {user}.',
    se: 'Orena đang bận, thử lại sau nhé.',
  },
  en: {
    s1: 'This is where you study and review what you have met. Pick an item to start.',
    s1s: 'Review due words',
    s5: 'Tap {label} to add {w} to your vocabulary.',
    s5l: 'Save word',
    s8: 'I can only see your own progress.',
    s9: 'Your usual slips here are verb tense in the retelling and two prepositions.',
    s9l: 'Revise',
    s9t: 'Looking at your latest review',
    s2t: 'Looking at your latest take',
    s2: '{w} was marked as mispronounced, score 6/100. Listen to the model, then try again:',
    s2b: '{w} scored lower than the rest (71/100) but was not marked wrong.',
    s2p: 'Play model',
    s2a: 'Say again',
    s12: 'A short answer for now.',
    s13: 'Hi. Review words, read, or practise speaking today?',
    s13a: 'What should I study today?',
    s13b: 'Explain a word',
    s14: "Got it. I'll call you {user} from now on.",
    s14n: 'Address: Orena calls you "{user}".',
    s15: "I'm Orena, your AI learning assistant.",
    se: 'Orena is busy right now. Try again soon.',
  },
  zh: {
    s1: '这里是学习和复习{user}遇到过的内容的地方。选一项开始吧。',
    s1s: '复习到期词语',
    s5: '点击{label}，把 {w} 加入{user}的词汇表。',
    s5l: '保存词语',
    s8: '{self}只能查看{user}自己的进度。',
    s9: '这篇里{user}常错在复述部分的动词时态，还有两处介词用法。',
    s9l: '修改',
    s9t: '正在查看最近一次批改',
    s2t: '正在查看最近一次录音',
    s2: '{w} 被标为发音错误，得分 6/100。先听示范，再试一次：',
    s2b: '{w} 的得分比其他音节低（71/100），但没有被标为错误。',
    s2p: '听示范',
    s2a: '再说一次',
    s12: '先简短回答。',
    s13: '你好。今天想复习词语、阅读，还是练口语？',
    s13a: '我今天该学什么？',
    s13b: '解释一个词',
    s14: '好的，以后{self}用敬语称呼{user}。',
    s14n: '称呼：Orena 自称"{self}"，称呼你为"{user}"。',
    s15: '{self}是 Orena，{user}的 AI 学习助手。',
    se: 'Orena 正忙，请稍后再试。',
  },
};

function words(request) {
  const support = String(request?.context?.locale?.support || 'en').slice(0, 2);
  return WORDS[support] || WORDS.en;
}

/* Action labels are buttons: interface language (AGENT_CONTRACT §7, D-094). */
function labels(request) {
  const ui = String(request?.context?.locale?.interface || 'en').slice(0, 2);
  return WORDS[ui] || WORDS.en;
}

function supportLang(request) {
  return String(request?.context?.locale?.support || 'en');
}

/* Fills every {token} a template names from `params`; a token with no value is left as-is (never
   used with an incomplete params object). */
function render(text, params) {
  return String(text).replace(/\{(\w+)\}/g, (whole, name) => (params[name] != null ? String(params[name]) : whole));
}

/* §5.6 "Applied": every support-layer line is filled from the request's own `context.address`, with
   that language's default when absent - never invented, never read from anywhere else. English
   never lets a custom term replace "I"/"you" mid-sentence; a name adds a vocative instead.

   "Applied only when address.lang equals context.locale.support; otherwise that language's
   default" (§5.6) is the server's own rule, not only the client's: `buildRequest` already enforces
   it on the way out, but this mock stands in for the receiving side too (§11), so it re-checks
   before use rather than trusting whatever `context.address` a hand-built request happens to
   carry. */
function addressed(request, template, extra = {}) {
  const contractLang = toContractLang(request?.context?.locale?.support || 'en');
  const rawAddress = request?.context?.address;
  const address = rawAddress && rawAddress.lang === contractLang ? rawAddress : null;
  const resolved = resolveAddress(address, contractLang) || { lang: contractLang, user: 'you' };
  const text = render(template, {
    ...extra,
    self: resolved.self,
    Self: capitalizeTerm(resolved.self),
    user: resolved.user,
    User: capitalizeTerm(resolved.user),
  });
  if (contractLang !== 'en') return text;
  if (!resolved.user || resolved.user === 'you') return text;
  // The vocative leads the sentence, so its own first word drops to lower case - except the pronoun "I".
  const rest = /^I(?=[\s'’])/.test(text) ? text : `${text.charAt(0).toLowerCase()}${text.slice(1)}`;
  return `${capitalizeTerm(resolved.user)}, ${rest}`;
}

/* A canonical pair to demonstrate setting the address (S14), one per support language - what a real
   server would read out of the learner's own request; the mock has no message to parse. */
const ADDRESS_DEMO = { vi: { self: 'chị', user: 'em' }, en: { user: 'Minh' }, zh: { register: 'polite' } };

/* A segment's text arrives in a few deltas, then its end. */
function segment(index, lang, text, voiceStyle) {
  const events = [];
  const parts = text.match(/.{1,18}(\s|$)|.{1,18}/gu) || [text];
  for (const part of parts) {
    events.push(['segment_delta', { index, lang, text_delta: part }]);
  }
  events.push(['segment_end', { index, lang, text, voice_style: voiceStyle }]);
  return events;
}

let sessionCounter = 0;
function session(request) {
  return ['session', { session_id: request.session_id || `mock-${(sessionCounter += 1)}`, contract_version: CONTRACT_VERSION }];
}

export const STREAMS = {
  S1(request) {
    const w = words(request);
    return [session(request), ...segment(0, supportLang(request), addressed(request, w.s1), 'neutral_explain'), ['suggestion', { label: w.s1s, intent: 'prompt.review_due' }], done()];
  },
  /* §7, §10, D-096: an offer, never a completion claim - the learner still has to tap the button.
     The reply names the button by its interface-language label (§7) and does not describe it. */
  S5(request) {
    const w = words(request);
    const item = request.context?.selected_item || {};
    const label = labels(request).s5l;
    return [
      session(request),
      ['segment_end', { index: 0, lang: supportLang(request), text: addressed(request, w.s5, { w: item.text, label }), voice_style: 'brief_ack' }],
      ['action', { id: 'a1', type: 'save_word', label, payload: { text: item.text || '', lang: item.lang || request.context?.locale?.target || 'en' }, risk: 'LOW' }],
      done(),
    ];
  },
  S8(request) {
    return [session(request), ['segment_end', { index: 0, lang: supportLang(request), text: addressed(request, words(request).s8), voice_style: 'neutral_explain' }], done()];
  },
  S9(request) {
    const w = words(request);
    return [
      session(request),
      ['tool_call', { name: 'get_current_writing_evaluation', label: w.s9t }],
      ['tool_result', { name: 'get_current_writing_evaluation', summary: 'evaluation read', evidence_ids: ['e1', 'e2'] }],
      ['evidence', { id: 'e1', source: 'writing.evaluation', ref: { essay_id: request.context?.essay_id, path: 'errors[0]' }, excerpt: { category: 'verb_tense' } }],
      ['evidence', { id: 'e2', source: 'writing.evaluation', ref: { essay_id: request.context?.essay_id, path: 'errors[2]' }, excerpt: { category: 'preposition' } }],
      ...segment(0, supportLang(request), addressed(request, w.s9), 'neutral_explain'),
      ['action', { id: 'a1', type: 'navigate', label: labels(request).s9l, payload: { intent: 'writing.revision', essay_id: request.context?.essay_id }, risk: 'LOW' }],
      done(),
    ];
  },
  /* §10, D-096: no provider name (the old text named the ASR vendor). */
  S2(request, { flagged = true } = {}) {
    const w = words(request);
    const item = request.context?.selected_item || {};
    const target = item.lang || request.context?.locale?.target || 'zh-CN';
    const excerpt = flagged ? { pinyin: 'shi', tone: 4, score: 6, flagged: true } : { pinyin: 'shi', tone: 3, score: 71, flagged: false };
    const events = [
      session(request),
      ['tool_call', { name: 'get_pronunciation_attempt', label: w.s2t }],
      ['tool_result', { name: 'get_pronunciation_attempt', summary: 'attempt read', evidence_ids: ['e1'] }],
      ['evidence', { id: 'e1', source: 'speech.pronunciation', ref: { attempt_id: request.context?.attempt_id, path: 'words[0].phonemes[0]' }, excerpt }],
      ...segment(0, supportLang(request), addressed(request, flagged ? w.s2 : w.s2b, { w: item.text }), flagged ? 'gentle_correction' : 'neutral_explain'),
    ];
    if (flagged) {
      events.push(['segment_end', { index: 1, lang: target, text: item.text || '', voice_style: 'reference' }]);
      const line = { content_id: request.context?.content_id, item_id: item.id };
      events.push(['action', { id: 'a1', type: 'play_model', label: labels(request).s2p, payload: line, risk: 'LOW' }]);
      events.push(['action', { id: 'a2', type: 'say_again', label: labels(request).s2a, payload: line, risk: 'LOW' }]);
    }
    events.push(done());
    return events;
  },
  S2b(request) {
    return STREAMS.S2(request, { flagged: false });
  },
  S12(request) {
    return [session(request), ['metered', { turn_ordinal: 21, budget_state: 'soft_limited' }], ['segment_end', { index: 0, lang: supportLang(request), text: addressed(request, words(request).s12), voice_style: 'brief_ack' }], done()];
  },
  S13(request) {
    const w = words(request);
    return [
      session(request),
      ['segment_end', { index: 0, lang: supportLang(request), text: addressed(request, w.s13), voice_style: 'neutral_explain' }],
      ['suggestion', { label: w.s1s, intent: 'prompt.review_due' }],
      ['suggestion', { label: w.s13a, intent: 'prompt.next_step' }],
      ['suggestion', { label: w.s13b, intent: 'prompt.explain_word' }],
      done(),
    ];
  },
  /* §5.6, D-096: sets the address the learner just asked for and already speaks in it - a
     memory_update applies without a tap, so unlike every other reply this one may say it is done
     (§7 "A memory_update is different"). The mock has no message to parse, so it demonstrates one
     canonical pair per support language (ADDRESS_DEMO); a real server reads the learner's own words. */
  S14(request) {
    const w = words(request);
    const contractLang = toContractLang(request?.context?.locale?.support || 'en');
    const demo = ADDRESS_DEMO[String(request?.context?.locale?.support || 'en').slice(0, 2)] || ADDRESS_DEMO.en;
    const address = { ...demo, lang: contractLang };
    const resolved = resolveAddress(address, contractLang) || { lang: contractLang, user: 'you' };
    const note = {
      id: addressNoteId(contractLang),
      kind: 'address',
      address,
      // §5.6: "the line the learner reads in preferences.agent_memory", in the support language.
      text: render(w.s14n, { self: resolved.self, user: resolved.user }),
      weight: 1,
      last_reinforced: new Date().toISOString(),
      expires_at: null,
    };
    const text = render(w.s14, { self: resolved.self, Self: capitalizeTerm(resolved.self), user: resolved.user, User: capitalizeTerm(resolved.user) });
    return [
      session(request),
      ['memory_update', { op: 'upsert', note }],
      ['segment_end', { index: 0, lang: supportLang(request), text, voice_style: 'brief_ack' }],
      done(),
    ];
  },
  /* §5.6, D-096: fixed copy, answered by rule in whatever address the request carries - never the
     model, never a claim about how it decided. */
  S15(request) {
    const w = words(request);
    return [session(request), ...segment(0, supportLang(request), addressed(request, w.s15), 'neutral_explain'), done()];
  },
  SE(request) {
    return [session(request), ['error', { class: 'provider_unavailable', message: addressed(request, words(request).se), fallback: 'retry' }]];
  },
};

function done() {
  return ['done', { usage: { input_tokens: 0, output_tokens: 0 }, trace_id: 'mock' }];
}

const OTHER_LEARNER = /user khác|người khác|another (user|learner)|other (user|learner)|其他(用户|学员|人)|别人/i;
const SAVE = /\blưu\b|\bsave\b|保存|收藏/i;
/* §5.6: a request to set the address (vi "gọi … là", "xưng là"; en "call me"; zh "叫我"/"称呼我").
   No trailing \b after a Vietnamese diacritic: JS's \b is ASCII-only, so a boundary right after
   "là" (ends in à) never matches - the leading \b before the ASCII "gọi"/"xưng" still does. */
const ADDRESS_REQUEST = /\bgọi\s+(tôi|mình|em)\s+là|\bxưng\s+là|\bcall me\b|请?叫我|请?称呼我/i;
/* "Who are you", vi/en/zh. */
const WHO_ARE_YOU = /\bbạn là ai\b|\bwho are you\b|你是谁|你是誰/i;

export function chooseStream(request, forced = '') {
  if (forced && STREAMS[forced]) return forced;
  if (request.trigger === 'open') return 'S13';
  const message = String(request.message || '');
  const context = request.context || {};
  if (OTHER_LEARNER.test(message)) return 'S8';
  if (ADDRESS_REQUEST.test(message)) return 'S14';
  if (WHO_ARE_YOU.test(message)) return 'S15';
  if (context.selected_item?.type === 'word' && SAVE.test(message)) return 'S5';
  if (context.surface === 'writing.review' && context.essay_id) return 'S9';
  if ((context.surface === 'speaking.word_detail' || context.surface === 'speaking.workspace') && context.selected_item) return 'S2';
  return 'S1';
}

/* §2.1 statuses, as the transport reports them. */
export const STATUSES = Object.freeze({ H404: 'absent', H409: 'language_mismatch', H429: 'wait' });
const RETRY_AFTER = 2;

/* The mock transport: an async iterable of { event, data }, paced like a stream, abortable. */
export async function* mockTurn(request, { signal, forced = '', pace = 45 } = {}) {
  if (STATUSES[forced] && forced !== 'H429') {
    yield { event: STATUSES[forced], data: {} };
    return;
  }
  if (forced === 'H429') {
    yield { event: 'wait', data: { seconds: RETRY_AFTER } };
    await new Promise((resolve) => setTimeout(resolve, pace ? RETRY_AFTER * 1000 : 0));
    if (signal?.aborted) return;
  }
  const events = STREAMS[chooseStream(request, forced)](request);
  for (const [event, data] of events) {
    if (signal?.aborted) return;
    await new Promise((resolve) => setTimeout(resolve, event === 'segment_delta' ? pace : pace * 2));
    yield { event, data };
  }
}
