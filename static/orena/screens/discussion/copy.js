/* Discussion's own words (design route `discussion`, frame 46). The screen title reuses
   copy/shell.js's `discussion` (already translated, already the route's crumb) - not duplicated
   here. The five starter chips are close paraphrases of the spec's own five example questions
   (ORENA_DESIGN_SPEC.md R5), real entry points into the thread - not sample content. */
import { defineCopy } from '../../copy/index.js';

const INTERFACE_KEYS = [
  'subtitleSuffix', 'placeholder', 'send', 'thinking',
  'starterMeaning', 'starterAuthor', 'starterGrammar', 'starterInterpret', 'starterTrue',
  'unavailable', 'full', 'intro',
];

export const t = defineCopy('discussion', {
  layers: Object.fromEntries(INTERFACE_KEYS.map((key) => [key, 'interface'])),
  en: {
    subtitleSuffix: 'this thread stays with the text',
    placeholder: 'Ask about this text…', send: 'Send', thinking: 'Orena is thinking…',
    starterMeaning: 'What does this mean?', starterAuthor: 'Why did the author say this?',
    starterGrammar: 'Grammar question', starterInterpret: 'How would you interpret it?',
    starterTrue: 'Is this true?',
    unavailable: 'The tutor could not answer just now. Please try again.',
    full: 'This conversation has reached its limit of {n} turns.',
    intro: 'I’m attached to “{title}”. Ask what a part means, why the author says something, or how you’d interpret it — the thread stays with this text.',
  },
  vi: {
    subtitleSuffix: 'cuộc trò chuyện này gắn với bài đọc',
    placeholder: 'Hỏi về bài này…', send: 'Gửi', thinking: 'Orena đang suy nghĩ…',
    starterMeaning: 'Câu này nghĩa là gì?', starterAuthor: 'Vì sao tác giả viết như vậy?',
    starterGrammar: 'Câu hỏi về ngữ pháp', starterInterpret: 'Bạn hiểu ý này thế nào?',
    starterTrue: 'Điều này có đúng không?',
    unavailable: 'Trợ lý chưa thể trả lời lúc này. Vui lòng thử lại.',
    full: 'Cuộc trò chuyện này đã đạt giới hạn {n} lượt.',
    intro: 'Mình đang gắn với “{title}”. Hãy hỏi một đoạn nghĩa là gì, vì sao tác giả viết như vậy, hoặc bạn hiểu ý đó thế nào — cuộc trò chuyện này gắn với bài đọc.',
  },
  zh: {
    subtitleSuffix: '此对话与这篇文章关联',
    placeholder: '问一问这篇文章…', send: '发送', thinking: 'Orena 正在思考…',
    starterMeaning: '这句是什么意思？', starterAuthor: '作者为什么这样写？',
    starterGrammar: '语法问题', starterInterpret: '你怎么理解这句话？',
    starterTrue: '这是真的吗？',
    unavailable: '助教暂时无法回答，请再试一次。',
    full: '这段对话已达到 {n} 轮的上限。',
    intro: '我已关联到《{title}》。可以问某一部分是什么意思、作者为什么这样写，或者你会怎样理解它——这段对话与这篇文章关联。',
  },
});
