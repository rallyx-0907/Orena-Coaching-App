/* Today (T1). Interface layer: section headings, controls, card-kind labels, the zero-state
   labels rule 40 requires for the goal ring/streak/level card. Support layer: the one sentence
   that explains the goal ring when there is real evidence for it (learner-summary), and the
   activity-count phrases it is built from. */
import { defineCopy } from '../../copy/index.js';

const INTERFACE_KEYS = [
  'recommendedTitle', 'anotherAction', 'forYouTitle', 'seeAllAction', 'startAction', 'continueAction', 'placePercent',
  'goalLabel', 'ofGoalLabel', 'notTrackedYet', 'dayStreak', 'levelLabel', 'levelXp',
  'kindRead', 'kindListen', 'kindSpeak', 'kindWord', 'kindContinue', 'kindReview', 'kindGrammar',
  'skillReading', 'skillListening', 'skillSpeaking',
  'weekday_mon', 'weekday_tue', 'weekday_wed', 'weekday_thu', 'weekday_fri', 'weekday_sat', 'weekday_sun',
  /* The header's time-of-day greeting (buildGreeting, model.js) - the page's own heading text,
     chrome like every other title on this screen, never the learner's own explanation of anything. */
  'greetingMorning', 'greetingAfternoon', 'greetingEvening',
  /* The skippable level prompt (D-105 H-19): a Banner (the design's frame) for a profile with no level. */
  'levelPromptTitle', 'levelPromptText', 'levelPromptAction',
  /* System copy follows the interface language (HP-1 A, as D-139 HD-14): the due-review reason and the header
     subtitle say what the page holds; only the learning content stays in the content language. */
  'reviewReason', 'subtitleBoth', 'subtitleOnly',
];

const SUPPORT_KEYS = [
  'evidenceThisWeek', 'evidenceSeparator',
  'activity_submitted_versions', 'activity_checks_answered', 'activity_lines_reconstructed',
  'activity_takes', 'activity_patterns_marked_complete', 'activity_phrases_kept',
  /* The due-review recommendation's "why this" line (buildRecommendationPool, model.js) - an
     explanation of the suggestion, not a control label, so it is support-layer like the goal
     ring's own evidence sentence above. */
  /* The header subtitle (buildHeadSubtitle, model.js) - it explains what the real state of the
     page below actually holds, exactly like the evidence sentence above; never a control label. */
];

export const t = defineCopy('today', {
  layers: Object.fromEntries([...INTERFACE_KEYS.map((k) => [k, 'interface']), ...SUPPORT_KEYS.map((k) => [k, 'support'])]),
  en: {
    recommendedTitle: 'Recommended for today', anotherAction: 'Another', forYouTitle: 'For you',
    seeAllAction: 'See all', startAction: 'Start', continueAction: 'Continue', placePercent: '{pct}% done',
    goalLabel: "Today's goal", ofGoalLabel: "of today's goal", notTrackedYet: 'Not tracked yet',
    dayStreak: '{n} day streak', levelLabel: 'Level', levelXp: '{n} XP',
    kindRead: 'Read', kindListen: 'Listen', kindSpeak: 'Speak', kindWord: 'Word', kindContinue: 'Continue', kindReview: 'Review', kindGrammar: 'Grammar',
    skillReading: 'Reading', skillListening: 'Listening', skillSpeaking: 'Speaking',
    weekday_mon: 'M', weekday_tue: 'T', weekday_wed: 'W', weekday_thu: 'T', weekday_fri: 'F', weekday_sat: 'S', weekday_sun: 'S',
    evidenceThisWeek: 'This week: {list}', evidenceSeparator: ' · ',
    activity_submitted_versions_one: '{n} draft submitted', activity_submitted_versions_other: '{n} drafts submitted',
    activity_checks_answered_one: '{n} reading check answered', activity_checks_answered_other: '{n} reading checks answered',
    activity_lines_reconstructed_one: '{n} line reconstructed', activity_lines_reconstructed_other: '{n} lines reconstructed',
    activity_takes_one: '{n} speaking take', activity_takes_other: '{n} speaking takes',
    activity_patterns_marked_complete_one: '{n} grammar point completed', activity_patterns_marked_complete_other: '{n} grammar points completed',
    activity_phrases_kept_one: '{n} phrase kept', activity_phrases_kept_other: '{n} phrases kept',
    reviewReason_one: '{n} word due for review', reviewReason_other: '{n} words due for review',
    greetingMorning: 'Good morning', greetingAfternoon: 'Good afternoon', greetingEvening: 'Good evening',
    levelPromptTitle: 'What is your level?', levelPromptText: 'Tell Orena where you are, or skip it for now.', levelPromptAction: 'Choose level',
    subtitleBoth_one: '{n} thing worth doing today, then something to enjoy.',
    subtitleBoth_other: '{n} things worth doing today, then something to enjoy.',
    subtitleOnly_one: '{n} thing worth doing today.',
    subtitleOnly_other: '{n} things worth doing today.',
  },
  vi: {
    recommendedTitle: 'Đề xuất cho hôm nay', anotherAction: 'Đề xuất khác', forYouTitle: 'Dành cho bạn',
    seeAllAction: 'Xem tất cả', startAction: 'Bắt đầu', continueAction: 'Tiếp tục', placePercent: 'Đã xong {pct}%',
    goalLabel: 'Mục tiêu hôm nay', ofGoalLabel: 'trong mục tiêu hôm nay', notTrackedYet: 'Chưa được theo dõi',
    dayStreak: 'Chuỗi {n} ngày', levelLabel: 'Cấp độ', levelXp: '{n} XP',
    kindRead: 'Đọc', kindListen: 'Nghe', kindSpeak: 'Nói', kindWord: 'Từ vựng', kindContinue: 'Tiếp tục', kindReview: 'Ôn tập', kindGrammar: 'Ngữ pháp',
    skillReading: 'Đọc', skillListening: 'Nghe', skillSpeaking: 'Nói',
    weekday_mon: 'T2', weekday_tue: 'T3', weekday_wed: 'T4', weekday_thu: 'T5', weekday_fri: 'T6', weekday_sat: 'T7', weekday_sun: 'CN',
    evidenceThisWeek: 'Tuần này: {list}', evidenceSeparator: ' · ',
    activity_submitted_versions_other: '{n} bản viết đã nộp',
    activity_checks_answered_other: '{n} câu kiểm tra đọc hiểu đã làm',
    activity_lines_reconstructed_other: '{n} câu nghe đã phục dựng',
    activity_takes_other: '{n} lượt nói',
    activity_patterns_marked_complete_other: '{n} điểm ngữ pháp đã hoàn thành',
    activity_phrases_kept_other: '{n} cụm từ đã lưu',
    reviewReason_other: '{n} từ cần ôn tập',
    greetingMorning: 'Chào buổi sáng', greetingAfternoon: 'Chào buổi chiều', greetingEvening: 'Chào buổi tối',
    levelPromptTitle: 'Trình độ của bạn là gì?', levelPromptText: 'Cho Orena biết bạn đang ở đâu, hoặc bỏ qua lúc này.', levelPromptAction: 'Chọn trình độ',
    subtitleBoth_other: 'Có {n} việc đáng làm hôm nay, rồi đến điều gì đó để thư giãn.',
    subtitleOnly_other: 'Có {n} việc đáng làm hôm nay.',
  },
  zh: {
    recommendedTitle: '今天推荐', anotherAction: '换一个', forYouTitle: '为你推荐',
    seeAllAction: '查看全部', startAction: '开始', continueAction: '继续', placePercent: '已完成 {pct}%',
    goalLabel: '今天的目标', ofGoalLabel: '达成今天的目标', notTrackedYet: '暂未记录',
    dayStreak: '连续 {n} 天', levelLabel: '等级', levelXp: '{n} XP',
    kindRead: '阅读', kindListen: '听力', kindSpeak: '口语', kindWord: '词语', kindContinue: '继续', kindReview: '复习', kindGrammar: '语法',
    skillReading: '阅读', skillListening: '听力', skillSpeaking: '口语',
    weekday_mon: '一', weekday_tue: '二', weekday_wed: '三', weekday_thu: '四', weekday_fri: '五', weekday_sat: '六', weekday_sun: '日',
    evidenceThisWeek: '本周：{list}', evidenceSeparator: '、',
    activity_submitted_versions_other: '{n} 篇提交的作文',
    activity_checks_answered_other: '{n} 次阅读理解检测',
    activity_lines_reconstructed_other: '{n} 句听力还原',
    activity_takes_other: '{n} 次口语录音',
    activity_patterns_marked_complete_other: '{n} 个已完成的语法点',
    activity_phrases_kept_other: '{n} 个已保存的短语',
    reviewReason_other: '{n} 个词需要复习',
    greetingMorning: '早上好', greetingAfternoon: '下午好', greetingEvening: '晚上好',
    levelPromptTitle: '你的水平是？', levelPromptText: '告诉 Orena 你现在的水平，或者先跳过。', levelPromptAction: '选择水平',
    subtitleBoth_other: '今天有 {n} 件值得做的事，之后还有内容可以放松享受。',
    subtitleOnly_other: '今天有 {n} 件值得做的事。',
  },
});
