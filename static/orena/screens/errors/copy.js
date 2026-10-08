/* From Your Errors' own words (frame 50, D-091; Design Contract rules 9, 26, 50). `instruction` is
   'support' (real, necessary guidance for an interaction with no other affordance explaining it -
   D7 §1.7's own judgment call on the sibling Review Session screen's "Tap to reveal", kept for the
   same reason); everything else is chrome. */
import { defineCopy } from '../../copy/index.js';

const LAYERS = {
  instruction: 'support', sourceLabel: 'interface',
  showAnswer: 'interface', check: 'interface',
  resultCorrect: 'interface', resultIncorrect: 'interface', resultRevealed: 'interface',
  tryAgain: 'interface', nextSentence: 'interface', seeResults: 'interface',
  progress: 'interface', done: 'interface',
  stateCleared: 'interface', stateLater: 'interface', stateKeep: 'interface',
  drillComplete: 'interface', scoreLine: 'interface',
  runAgain: 'interface', finish: 'interface',
  emptyTitle: 'interface',
};

export const t = defineCopy('errors', {
  layers: LAYERS,
  en: {
    instruction: 'This sentence has one error. Edit it so it’s correct.',
    sourceLabel: 'from your Writing',
    showAnswer: 'Show answer', check: 'Check',
    resultCorrect: 'Correct', resultIncorrect: 'Not quite yet', resultRevealed: 'Here’s the correction',
    tryAgain: 'Try again', nextSentence: 'Next sentence', seeResults: 'See results',
    progress: '{n} of {total}', done: 'done',
    stateCleared: 'cleared', stateLater: 'fixed after a retry', stateKeep: 'keep practising',
    drillComplete: 'Drill complete',
    scoreLine: '{firstTry} of {total} fixed on the first try',
    runAgain: 'Run again', finish: 'Finish',
    emptyTitle: 'No recent writing errors to review yet',
  },
  vi: {
    instruction: 'Câu này có một lỗi. Hãy sửa lại cho đúng.',
    sourceLabel: 'từ bài Viết của bạn',
    showAnswer: 'Xem đáp án', check: 'Kiểm tra',
    resultCorrect: 'Chính xác', resultIncorrect: 'Chưa đúng', resultRevealed: 'Đây là câu đã sửa',
    tryAgain: 'Thử lại', nextSentence: 'Câu tiếp theo', seeResults: 'Xem kết quả',
    progress: '{n} trên {total}', done: 'xong',
    stateCleared: 'đã sửa đúng ngay', stateLater: 'sửa đúng sau khi thử lại', stateKeep: 'cần luyện thêm',
    drillComplete: 'Đã hoàn thành',
    scoreLine: 'Sửa đúng ngay lần đầu {firstTry}/{total} câu',
    runAgain: 'Luyện lại', finish: 'Hoàn tất',
    emptyTitle: 'Chưa có lỗi viết gần đây để ôn lại',
  },
  zh: {
    instruction: '这句话有一处错误，请修改使其正确。',
    sourceLabel: '来自你的写作',
    showAnswer: '查看答案', check: '检查',
    resultCorrect: '正确', resultIncorrect: '还不太对', resultRevealed: '这是正确的说法',
    tryAgain: '再试一次', nextSentence: '下一句', seeResults: '查看结果',
    progress: '第 {n} 句 / 共 {total} 句', done: '已完成',
    stateCleared: '一次改对', stateLater: '重试后改对', stateKeep: '继续练习',
    drillComplete: '练习完成',
    scoreLine: '一次改对 {firstTry}/{total} 句',
    runAgain: '再练一次', finish: '完成',
    emptyTitle: '目前还没有可复习的写作错误',
  },
});
