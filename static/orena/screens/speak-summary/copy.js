/* Speaking Summary's own words (D-079, rules 9, 26, 50). Rule 50: the design's own celebratory
   framing is kept only where it states a real fact (the task count); nothing self-congratulatory
   is added where this build has no real evidence to back it (see model.js's own header comment). */
import { defineCopy } from '../../copy/index.js';

const LAYERS = {
  eyebrow: 'interface', tasksSuffix: 'interface', recordedInProgress: 'support',
  tasksCompleted: 'interface', taskScriptedPronunciation: 'interface',
  emptyTasks: 'support', keyImprovementLabel: 'interface', keyImprovement: 'support',
  practiceMore: 'interface', backToPracticeHub: 'interface', metricAccuracy: 'interface', metricFluency: 'interface',
};

export const t = defineCopy('speak-summary', {
  layers: LAYERS,
  en: {
    eyebrow: 'Speaking · last 7 days', tasksSuffix: 'tasks', recordedInProgress: 'Recent speaking activity.',
    tasksCompleted: 'Tasks completed', taskScriptedPronunciation: 'Scripted Pronunciation',
    emptyTasks: 'Nothing recorded in the last 7 days.', keyImprovementLabel: 'Key improvement', keyImprovement: '{label} was your lowest available score ({value}).',
    practiceMore: 'Practice more', backToPracticeHub: 'Back to Practice Hub', metricAccuracy: 'Accuracy', metricFluency: 'Fluency',
  },
  vi: {
    eyebrow: 'Luyện nói · 7 ngày qua', tasksSuffix: 'lượt', recordedInProgress: 'Hoạt động nói gần đây.',
    tasksCompleted: 'Đã hoàn thành', taskScriptedPronunciation: 'Luyện phát âm theo mẫu',
    emptyTasks: 'Chưa ghi nhận gì trong 7 ngày qua.', keyImprovementLabel: 'Điểm cần cải thiện', keyImprovement: '{label} là điểm thấp nhất hiện có ({value}).',
    practiceMore: 'Luyện thêm', backToPracticeHub: 'Về Trung tâm luyện tập', metricAccuracy: 'Độ chính xác', metricFluency: 'Trôi chảy',
  },
  zh: {
    eyebrow: '口语 · 最近 7 天', tasksSuffix: '项', recordedInProgress: '最近的口语活动。',
    tasksCompleted: '已完成的任务', taskScriptedPronunciation: '跟读练习',
    emptyTasks: '最近 7 天没有记录。', keyImprovementLabel: '重点改进', keyImprovement: '{label}是现有记录中的最低分数（{value}）。',
    practiceMore: '继续练习', backToPracticeHub: '返回练习中心', metricAccuracy: '准确度', metricFluency: '流利度',
  },
});
