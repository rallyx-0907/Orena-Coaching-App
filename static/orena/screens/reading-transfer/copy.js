/* Reading Transfer copy (frame 39, D-091, Design Contract rule 50). Titles of places, `back` and
   `retry` already live in copy/shell.js and are reused from there.

   Rule-50 drop: the header's own "· active use of what you read" suffix restates what the place is
   called and what its chips already say; only the text's title is kept as the subtitle.

   Layers (D-079): a control's label, the chip names and the result's headings are chrome
   ('interface'); the task prompt each mode gives, and the states that explain what happened, are
   explanation ('support'). What the coach itself writes (the "why" of each point and the thing to
   try) arrives from the endpoint already in the learner's support language. */
import { defineCopy } from '../../copy/index.js';

const layers = {
  modeParaphrase: 'interface', modeInference: 'interface', modeContextShift: 'interface',
  promptParaphrase: 'support', promptInference: 'support', promptContextShift: 'support',
  sourceLabel: 'interface', placeholder: 'interface', answerLabel: 'interface',
  speak: 'interface', listening: 'interface', transcribing: 'interface',
  checkLabel: 'interface', checking: 'interface',
  carriedLabel: 'interface', landedLabel: 'interface', improvementLabel: 'interface', insteadLabel: 'interface',
  anotherSentence: 'interface', finishLabel: 'interface', backToReading: 'interface',
  notPrepared: 'support', coachingError: 'support', noSentence: 'support',
};

export const t = defineCopy('reading-transfer', {
  layers,
  en: {
    modeParaphrase: 'Paraphrase', modeInference: 'Inference', modeContextShift: 'Context Shift',
    promptParaphrase: 'Say this idea in your own words.',
    promptInference: 'What is the writer implying here, beyond the literal words?',
    promptContextShift: 'If this were said to your manager instead of a close friend, how would it change? Say the new version.',
    sourceLabel: 'Source sentence', placeholder: 'Type, or use the mic…', answerLabel: 'Your answer',
    speak: 'Speak', listening: 'Listening…', transcribing: 'Transcribing…',
    checkLabel: 'Check', checking: 'Checking…',
    carriedLabel: 'What carried', landedLabel: 'What would land differently',
    improvementLabel: 'One useful improvement', insteadLabel: 'Instead',
    anotherSentence: 'Another sentence', finishLabel: 'Finish', backToReading: 'Back to reading',
    notPrepared: 'Nothing stood out in this answer.',
    coachingError: "Coaching isn't available right now.",
    noSentence: 'This text has no sentence to work with yet.',
  },
  vi: {
    modeParaphrase: 'Diễn đạt lại', modeInference: 'Suy luận', modeContextShift: 'Đổi ngữ cảnh',
    promptParaphrase: 'Hãy nói lại ý này bằng lời của bạn.',
    promptInference: 'Ngoài nghĩa đen, tác giả đang ngầm ý điều gì ở đây?',
    promptContextShift: 'Nếu câu này được nói với quản lý thay vì một người bạn thân, nó sẽ thay đổi thế nào? Hãy nói phiên bản mới.',
    sourceLabel: 'Câu nguồn', placeholder: 'Gõ chữ, hoặc dùng micro…', answerLabel: 'Câu trả lời của bạn',
    speak: 'Nói', listening: 'Đang nghe…', transcribing: 'Đang chuyển thành văn bản…',
    checkLabel: 'Kiểm tra', checking: 'Đang kiểm tra…',
    carriedLabel: 'Điều đã truyền tải được', landedLabel: 'Điều sẽ được hiểu khác đi',
    improvementLabel: 'Một điểm nên cải thiện', insteadLabel: 'Thay vào đó',
    anotherSentence: 'Câu khác', finishLabel: 'Hoàn tất', backToReading: 'Quay lại bài đọc',
    notPrepared: 'Không có điều gì nổi bật trong câu trả lời này.',
    coachingError: 'Hiện chưa dùng được tính năng nhận xét.',
    noSentence: 'Bài này chưa có câu nào để luyện.',
  },
  zh: {
    modeParaphrase: '转述', modeInference: '推断', modeContextShift: '语境转换',
    promptParaphrase: '用你自己的话说出这个意思。',
    promptInference: '除了字面意思，作者在这里暗示了什么？',
    promptContextShift: '如果这句话是对你的经理说，而不是对亲近的朋友说，会有什么不同？请说出新的版本。',
    sourceLabel: '原句', placeholder: '打字，或使用麦克风…', answerLabel: '你的回答',
    speak: '说话', listening: '正在听…', transcribing: '正在转换为文字…',
    checkLabel: '检查', checking: '正在检查…',
    carriedLabel: '传达到的部分', landedLabel: '可能被理解不同的部分',
    improvementLabel: '一个有用的改进', insteadLabel: '换成',
    anotherSentence: '换一句', finishLabel: '完成', backToReading: '返回阅读',
    notPrepared: '这次回答里没有需要特别指出的地方。',
    coachingError: '点评功能暂时不可用。',
    noSentence: '这篇文章暂时没有可练习的句子。',
  },
});
