/* Check Understanding's own words (design route `checku`, frame 20). The screen title itself
   reuses copy/shell.js's `checkUnderstanding` (already translated, already the route's crumb) -
   not duplicated here. Every key below is chrome (labels, states) or the 8 real backend question
   types (reading_evidence_repository.py QUESTION_TYPES) - never the frame's own sample
   "factual/inference/meaning/intent" wording (D-068). */
import { defineCopy } from '../../copy/index.js';

const INTERFACE_KEYS = [
  'progress', 'progressDone', 'evidenceLabel', 'showInText', 'nextQuestion', 'seeResult',
  'resultLabel', 'resultHeadline', 'continueLabel', 'deeperHeading', 'discussThisText',
  'retryQuestions', 'practiceVocabulary', 'writeResponse', 'newWordsLabel', 'minutesLabel',
  'nextReading', 'exitPractice', 'upNext', 'minutes',
  'noPracticeTitle', 'practiceOffTitle', 'backToReading',
  'correctLabel', 'missedLabel',
  'qtype_main_idea', 'qtype_detail', 'qtype_inference', 'qtype_vocabulary_in_context',
  'qtype_cause_effect', 'qtype_sequence', 'qtype_authors_purpose', 'qtype_reference',
];
const SUPPORT_KEYS = ['verdictCorrect', 'verdictIncorrect'];

export const t = defineCopy('check', {
  layers: {
    ...Object.fromEntries(INTERFACE_KEYS.map((key) => [key, 'interface'])),
    ...Object.fromEntries(SUPPORT_KEYS.map((key) => [key, 'support'])),
  },
  en: {
    progress: 'question {n} of {total}', progressDone: 'done',
    evidenceLabel: 'Evidence from the text', showInText: 'Show in text',
    nextQuestion: 'Next question', seeResult: 'See result',
    resultLabel: 'Result', resultHeadline: 'You understood {correct} / {total}', continueLabel: 'Continue',
    deeperHeading: 'Go deeper · optional', discussThisText: 'Discuss this text',
    retryQuestions: 'Retry questions', practiceVocabulary: 'Practice vocabulary', writeResponse: 'Write a response',
    newWordsLabel: 'new words', minutesLabel: 'min',
    nextReading: 'Next reading', exitPractice: 'Exit practice', upNext: 'Up next · {title}', minutes: '{n} min',
    noPracticeTitle: 'No comprehension check for this text yet.',
    practiceOffTitle: 'Practice answers aren’t being saved yet.', backToReading: 'Back to reading',
    correctLabel: 'Correct', missedLabel: 'Missed',
    verdictCorrect: 'Correct', verdictIncorrect: 'Not quite',
    qtype_main_idea: 'Main idea', qtype_detail: 'Detail', qtype_inference: 'Inference',
    qtype_vocabulary_in_context: 'Vocabulary in context', qtype_cause_effect: 'Cause and effect',
    qtype_sequence: 'Sequence', qtype_authors_purpose: 'Author’s purpose', qtype_reference: 'Reference',
  },
  vi: {
    progress: 'câu {n}/{total}', progressDone: 'xong',
    evidenceLabel: 'Bằng chứng trong bài', showInText: 'Xem trong bài',
    nextQuestion: 'Câu tiếp theo', seeResult: 'Xem kết quả',
    resultLabel: 'Kết quả', resultHeadline: 'Bạn hiểu đúng {correct} / {total} câu', continueLabel: 'Tiếp tục',
    deeperHeading: 'Tìm hiểu thêm · không bắt buộc', discussThisText: 'Thảo luận về bài này',
    retryQuestions: 'Làm lại câu hỏi', practiceVocabulary: 'Luyện từ vựng', writeResponse: 'Viết phản hồi',
    newWordsLabel: 'từ mới', minutesLabel: 'phút',
    nextReading: 'Bài đọc tiếp theo', exitPractice: 'Thoát luyện tập', upNext: 'Tiếp theo · {title}', minutes: '{n} phút',
    noPracticeTitle: 'Bài này chưa có phần kiểm tra hiểu.',
    practiceOffTitle: 'Câu trả lời luyện tập chưa được lưu.', backToReading: 'Quay lại bài đọc',
    correctLabel: 'Đúng', missedLabel: 'Sai',
    verdictCorrect: 'Chính xác', verdictIncorrect: 'Chưa đúng',
    qtype_main_idea: 'Ý chính', qtype_detail: 'Chi tiết', qtype_inference: 'Suy luận',
    qtype_vocabulary_in_context: 'Từ vựng theo ngữ cảnh', qtype_cause_effect: 'Nguyên nhân - kết quả',
    qtype_sequence: 'Trình tự', qtype_authors_purpose: 'Mục đích của tác giả', qtype_reference: 'Tham chiếu',
  },
  zh: {
    progress: '第 {n}/{total} 题', progressDone: '已完成',
    evidenceLabel: '文中依据', showInText: '在原文中查看',
    nextQuestion: '下一题', seeResult: '查看结果',
    resultLabel: '结果', resultHeadline: '你答对了 {correct} / {total} 题', continueLabel: '继续',
    deeperHeading: '深入了解 · 可选', discussThisText: '讨论这篇文章',
    retryQuestions: '重新答题', practiceVocabulary: '练习词汇', writeResponse: '写一段回应',
    newWordsLabel: '个新词', minutesLabel: '分钟',
    nextReading: '下一篇', exitPractice: '退出练习', upNext: '接下来 · {title}', minutes: '{n} 分钟',
    noPracticeTitle: '这篇文章暂时没有理解检查。',
    practiceOffTitle: '练习答案暂时不会被保存。', backToReading: '返回阅读',
    correctLabel: '正确', missedLabel: '答错',
    verdictCorrect: '回答正确', verdictIncorrect: '还不太对',
    qtype_main_idea: '主旨大意', qtype_detail: '细节', qtype_inference: '推理',
    qtype_vocabulary_in_context: '上下文词汇', qtype_cause_effect: '因果关系',
    qtype_sequence: '顺序', qtype_authors_purpose: '作者意图', qtype_reference: '指代',
  },
});
