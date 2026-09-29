/* Speaking Summary's own words (D-079, rules 9, 26, 50). Rule 50: the design's own celebratory
   framing is kept only where it states a real fact (the task count); nothing self-congratulatory
   is added where this build has no real evidence to back it (see model.js's own header comment). */
import { defineCopy } from '../../copy/index.js';

const LAYERS = {
  eyebrow: 'interface', tasksSuffix: 'interface', recordedInProgress: 'support',
  tasksCompleted: 'interface', taskScriptedPronunciation: 'interface',
  emptyTasks: 'support', keyImprovementLabel: 'interface', keyImprovement: 'support',
  practiceMore: 'interface', backToPracticeHub: 'interface',
};

export const t = defineCopy('speak-summary', {
  layers: LAYERS,
  en: {
    eyebrow: 'Speaking session', tasksSuffix: 'tasks', recordedInProgress: 'Recorded in Progress.',
    tasksCompleted: 'Tasks completed', taskScriptedPronunciation: 'Scripted Pronunciation',
    emptyTasks: 'Nothing recorded yet this session.', keyImprovementLabel: 'Key improvement', keyImprovement: '{label} was your lowest score this session ({value}).',
    practiceMore: 'Practice more', backToPracticeHub: 'Back to Practice Hub',
  },
  vi: {
    eyebrow: 'Buổi luyện nói', tasksSuffix: 'lượt', recordedInProgress: 'Đã ghi vào Tiến độ.',
    tasksCompleted: 'Đã hoàn thành', taskScriptedPronunciation: 'Luyện phát âm theo mẫu',
    emptyTasks: 'Buổi này chưa ghi nhận gì.', keyImprovementLabel: 'Điểm cần cải thiện', keyImprovement: '{label} là điểm thấp nhất của bạn trong buổi này ({value}).',
    practiceMore: 'Luyện thêm', backToPracticeHub: 'Về Trung tâm luyện tập',
  },
  zh: {
    eyebrow: '口语练习', tasksSuffix: '项', recordedInProgress: '已记录到"进度"。',
    tasksCompleted: '已完成的任务', taskScriptedPronunciation: '跟读练习',
    emptyTasks: '本次还没有记录。', keyImprovementLabel: '重点改进', keyImprovement: '本次{label}是你最低的分数（{value}）。',
    practiceMore: '继续练习', backToPracticeHub: '返回练习中心',
  },
});
