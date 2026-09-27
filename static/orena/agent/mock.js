/* The UI lane's mock agent (AGENT_CONTRACT §11): replays the contract's canonical streams (§12)
   with no backend, so the new UI is built and tested against the exact event sequence and payload
   shapes the intelligence lane's server must also produce. Only the wording differs; the mock
   speaks the request's support language (vi, en or zh) so every interface language can be
   reviewed. Nothing here is product copy or learner data.

   Selection: a forced stream (`?agent=S2b` in the address, for review), else the request itself -
   an opening turn is S13, a request about another learner's progress S8, "save" on a selected
   word S5, a question on a writing review S9, a question on a flagged pronunciation S2, anything
   else S1. */
import { CONTRACT_VERSION } from './contract.js';

const WORDS = {
  vi: {
    s1: 'Màn này là nơi bạn học và ôn lại những gì đã gặp. Chọn một mục để bắt đầu.',
    s1s: 'Ôn từ đến hạn',
    s5: 'Mình lưu {w} cho bạn nhé.',
    s5l: 'Lưu từ',
    s8: 'Mình chỉ xem được tiến độ của chính bạn.',
    s9: 'Bài này bạn hay sai thì của động từ ở câu kể lại, và hai lần dùng giới từ chưa đúng.',
    s9l: 'Sửa bài',
    s9t: 'Đang xem bài chấm gần nhất',
    s2t: 'Đang xem lần nói gần nhất',
    s2: 'Azure đánh dấu {w} là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:',
    s2b: 'Âm {w} được chấm thấp hơn các âm khác (71/100) nhưng không bị đánh dấu sai.',
    s2p: 'Nghe mẫu',
    s2a: 'Nói lại',
    s12: 'Mình trả lời ngắn thôi nhé.',
    s13: 'Chào bạn. Hôm nay bạn muốn ôn từ, đọc hay luyện nói?',
    s13a: 'Tôi nên học gì hôm nay?',
    s13b: 'Giải thích một từ',
    se: 'Orena đang bận, thử lại sau nhé.',
  },
  en: {
    s1: 'This is where you study and review what you have met. Pick an item to start.',
    s1s: 'Review due words',
    s5: 'Saved {w} for you.',
    s5l: 'Save word',
    s8: 'I can only see your own progress.',
    s9: 'Your usual slips here are verb tense in the retelling and two prepositions.',
    s9l: 'Revise',
    s9t: 'Looking at your latest review',
    s2t: 'Looking at your latest take',
    s2: 'Azure marked {w} as mispronounced, score 6/100. Listen to the model, then try again:',
    s2b: '{w} scored lower than the rest (71/100) but was not marked wrong.',
    s2p: 'Play model',
    s2a: 'Say again',
    s12: 'A short answer for now.',
    s13: 'Hi. Review words, read, or practise speaking today?',
    s13a: 'What should I study today?',
    s13b: 'Explain a word',
    se: 'Orena is busy right now. Try again soon.',
  },
  zh: {
    s1: '这里是学习和复习你遇到过的内容的地方。选一项开始吧。',
    s1s: '复习到期词语',
    s5: '已帮你保存 {w}。',
    s5l: '保存词语',
    s8: '我只能查看你自己的进度。',
    s9: '这篇里你常错在复述部分的动词时态，还有两处介词用法。',
    s9l: '修改',
    s9t: '正在查看最近一次批改',
    s2t: '正在查看最近一次录音',
    s2: 'Azure 把 {w} 标为发音错误，得分 6/100。先听示范，再试一次：',
    s2b: '{w} 的得分比其他音节低（71/100），但没有被标为错误。',
    s2p: '听示范',
    s2a: '再说一次',
    s12: '先简短回答。',
    s13: '你好。今天想复习词语、阅读，还是练口语？',
    s13a: '我今天该学什么？',
    s13b: '解释一个词',
    se: 'Orena 正忙，请稍后再试。',
  },
};

function words(request) {
  const support = String(request?.context?.locale?.support || 'en').slice(0, 2);
  return WORDS[support] || WORDS.en;
}

function supportLang(request) {
  return String(request?.context?.locale?.support || 'en');
}

function fill(text, word) {
  return text.replace('{w}', word || '');
}

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
    return [session(request), ...segment(0, supportLang(request), w.s1, 'neutral_explain'), ['suggestion', { label: w.s1s, intent: 'vocabulary.review_due' }], done()];
  },
  S5(request) {
    const w = words(request);
    const item = request.context?.selected_item || {};
    return [
      session(request),
      ['segment_end', { index: 0, lang: supportLang(request), text: fill(w.s5, item.text), voice_style: 'brief_ack' }],
      ['action', { id: 'a1', type: 'save_word', label: w.s5l, payload: { text: item.text || '', lang: item.lang || request.context?.locale?.target || 'en' }, risk: 'LOW' }],
      done(),
    ];
  },
  S8(request) {
    return [session(request), ['segment_end', { index: 0, lang: supportLang(request), text: words(request).s8, voice_style: 'neutral_explain' }], done()];
  },
  S9(request) {
    const w = words(request);
    return [
      session(request),
      ['tool_call', { name: 'get_current_writing_evaluation', label: w.s9t }],
      ['tool_result', { name: 'get_current_writing_evaluation', summary: 'evaluation read', evidence_ids: ['e1', 'e2'] }],
      ['evidence', { id: 'e1', source: 'writing.evaluation', ref: { essay_id: request.context?.essay_id, path: 'errors[0]' }, excerpt: { category: 'verb_tense' } }],
      ['evidence', { id: 'e2', source: 'writing.evaluation', ref: { essay_id: request.context?.essay_id, path: 'errors[2]' }, excerpt: { category: 'preposition' } }],
      ...segment(0, supportLang(request), w.s9, 'neutral_explain'),
      ['action', { id: 'a1', type: 'navigate', label: w.s9l, payload: { intent: 'writing.revision', essay_id: request.context?.essay_id }, risk: 'LOW' }],
      done(),
    ];
  },
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
      ...segment(0, supportLang(request), fill(flagged ? w.s2 : w.s2b, item.text), flagged ? 'gentle_correction' : 'neutral_explain'),
    ];
    if (flagged) {
      events.push(['segment_end', { index: 1, lang: target, text: item.text || '', voice_style: 'reference' }]);
      const line = { content_id: request.context?.content_id, item_id: item.id };
      events.push(['action', { id: 'a1', type: 'play_model', label: w.s2p, payload: line, risk: 'LOW' }]);
      events.push(['action', { id: 'a2', type: 'say_again', label: w.s2a, payload: line, risk: 'LOW' }]);
    }
    events.push(done());
    return events;
  },
  S2b(request) {
    return STREAMS.S2(request, { flagged: false });
  },
  S12(request) {
    return [session(request), ['metered', { turn_ordinal: 21, budget_state: 'soft_limited' }], ['segment_end', { index: 0, lang: supportLang(request), text: words(request).s12, voice_style: 'brief_ack' }], done()];
  },
  S13(request) {
    const w = words(request);
    return [
      session(request),
      ['segment_end', { index: 0, lang: supportLang(request), text: w.s13, voice_style: 'neutral_explain' }],
      ['suggestion', { label: w.s1s, intent: 'vocabulary.review_due' }],
      ['suggestion', { label: w.s13a, intent: 'coaching.next_step' }],
      ['suggestion', { label: w.s13b, intent: 'vocabulary.explain' }],
      done(),
    ];
  },
  SE(request) {
    return [session(request), ['error', { class: 'provider_unavailable', message: words(request).se, fallback: 'retry' }]];
  },
};

function done() {
  return ['done', { usage: { input_tokens: 0, output_tokens: 0 }, trace_id: 'mock' }];
}

const OTHER_LEARNER = /user khác|người khác|another (user|learner)|other (user|learner)|其他(用户|学员|人)|别人/i;
const SAVE = /\blưu\b|\bsave\b|保存|收藏/i;

export function chooseStream(request, forced = '') {
  if (forced && STREAMS[forced]) return forced;
  if (request.trigger === 'open') return 'S13';
  const message = String(request.message || '');
  const context = request.context || {};
  if (OTHER_LEARNER.test(message)) return 'S8';
  if (context.selected_item?.type === 'word' && SAVE.test(message)) return 'S5';
  if (context.surface === 'writing.review' && context.essay_id) return 'S9';
  if ((context.surface === 'speaking.word_detail' || context.surface === 'speaking.workspace') && context.selected_item) return 'S2';
  return 'S1';
}

/* The mock transport: an async iterable of { event, data }, paced like a stream, abortable. */
export async function* mockTurn(request, { signal, forced = '', pace = 45 } = {}) {
  const events = STREAMS[chooseStream(request, forced)](request);
  for (const [event, data] of events) {
    if (signal?.aborted) return;
    await new Promise((resolve) => setTimeout(resolve, event === 'segment_delta' ? pace : pace * 2));
    yield { event, data };
  }
}
