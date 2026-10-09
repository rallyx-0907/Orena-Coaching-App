/* Profile's own words (frames 24-25). Every key is interface layer: labels, states and CTAs, not
   explanation - Profile draws no hint/feedback copy (D-079). Titles Profile shares with the rest
   of the shell (Settings, Progress, back...) come from copy/shell.js and are not repeated here.

   No `{n}` placeholder here is ever filled with a literal `0` through `t()` - `copy/index.js`'s
   `fill()` (`params[name] ?? params[name] === 0 ? ... : match`) never substitutes a placeholder
   whose value is exactly `0`, because `??` only short-circuits on null/undefined, not on `0`, so
   the ternary's condition becomes the *number* `0` - falsy - and the original `{n}` is left in the
   text. This is confirmed still live in `copy/index.js` today (reproduced against this screen).
   Profile has more always-zero measures than most screens under rule 40, so due/streak-days/
   weekly-minutes all give their headline/tile pairs as plain `*None`/`*One`/`*Many` keys the
   screen selects between in JS (never asking `fill()` to substitute a literal `0`) - `due === 1`
   is the only place English grammatical number matters for `dueValue*`; day-streak's "day"/"days"
   is the same split. vi/zh do not inflect, so their `*One`/`*Many` forms read identically - kept
   duplicated rather than shared via `.plural()`, so the lookup needs no special case either way.
   The `*None` keys (`dueValueNone`, `streakDaysValueNone`, `weekMinutesValueNone`) carry no
   placeholder at all, since model.js's own rule-40 fallback for all three is permanently 0 today -
   but `streakDaysTileValue`/`weekMinutesTileValue` (screen.js) read `model.dayStreak`/
   `model.weekMinutes` themselves rather than assuming the zero case, so the day either measure
   gains a real backend source, the `*One`/`*Many` keys already exist and pick up the real count
   with no further change. (`product/layered-copy.js`'s separate, now-fixed bug - a suffixed
   `_other` key not falling back to its bare key's declared layer - no longer applies to this table
   either way, since nothing here uses `.plural()`.) The placeholders Profile does carry
   (`rankLevelLabel`, `dueValueOne`/`dueValueMany`, `streakDaysValueOne`/`*Many`,
   `weekMinutesValueOne`/`*Many`) only ever receive a real positive number or
   a non-empty string when they are selected, never `0`, so none of them meet the `fill()` bug
   above. `dailyGoalLabel`/`dailyGoalNotTracked` (the 4th hero tile, screen.js) carry no
   placeholder either - the ring's own honest "0" is drawn as a plain digit, matching every other
   raw stat number on this screen (`model.dayStreak`, `model.savedCount`), never routed through
   `t()`. */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'heroEyebrow', 'heroHeadlineDueOne', 'heroHeadlineDueMany', 'heroHeadlineNone', 'ctaOpenProgress',
  'dailyGoalLabel', 'dailyGoalNotTracked',
  'streakLabel', 'streakDaysValueNone', 'streakDaysValueOne', 'streakDaysValueMany',
  'dueLabel', 'dueValueNone', 'dueValueOne', 'dueValueMany',
  'startReview', 'weekLabel', 'weekMinutesValueNone', 'weekMinutesValueOne', 'weekMinutesValueMany',
  'weeklyGoalTitle', 'dayStreakStatLabel', 'savedItemsStatLabel',
  'goalPrefix', 'goalEveryday', 'goalWork', 'goalExam', 'goalVoice', 'goalNotSet',
  'actionHistory', 'actionPlan', 'actionPrivacy', 'actionFeedback', 'actionAdmin', 'actionSignOut',
  'actionAdminSub', 'actionSettingsSub', 'actionHistorySub', 'actionProgressSub',
  'actionPlanSub', 'actionPrivacySub', 'actionFeedbackSub',
  'weekdays', 'rankLevelLabel',
];

export const t = defineCopy('profile', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    heroEyebrow: 'Your progress · today',
    heroHeadlineDueOne: '{n} review due today',
    heroHeadlineDueMany: '{n} reviews due today',
    heroHeadlineNone: 'No reviews due today',
    ctaOpenProgress: 'Open Progress',
    dailyGoalLabel: 'Daily goal',
    dailyGoalNotTracked: 'Not tracked yet',
    streakLabel: 'Streak',
    streakDaysValueNone: '0 days',
    streakDaysValueOne: '{n} day',
    streakDaysValueMany: '{n} days',
    dueLabel: 'Due review',
    dueValueNone: 'All caught up',
    dueValueOne: '{n} item',
    dueValueMany: '{n} items',
    startReview: 'Start review',
    weekLabel: 'This week',
    weekMinutesValueNone: '0 min',
    weekMinutesValueOne: '{n} min',
    weekMinutesValueMany: '{n} min',
    weeklyGoalTitle: 'Weekly goal · {n} days',
    dayStreakStatLabel: 'Day streak',
    savedItemsStatLabel: 'Saved items',
    goalPrefix: 'Goal',
    goalEveryday: 'Everyday life',
    goalWork: 'Work',
    goalExam: 'Exam preparation',
    goalVoice: 'Speaking confidence',
    goalNotSet: 'Not set',
    actionHistory: 'History',
    actionPlan: 'Plan & usage',
    actionPrivacy: 'Privacy',
    actionFeedback: 'Feedback',
    actionAdmin: 'Platform admin',
    actionSignOut: 'Sign out',
    actionAdminSub: 'Admin accounts only',
    actionSettingsSub: 'languages, learning, review, notifications',
    actionHistorySub: 'everything recorded, by day',
    actionProgressSub: 'skills, evidence, rank',
    actionPlanSub: 'plan, limits, invoices, pricing',
    actionPrivacySub: 'microphone · learner audio',
    actionFeedbackSub: 'rate Orena, suggest improvements',
    weekdays: 'M,T,W,T,F,S,S',
    rankLevelLabel: 'Level {n}',
  },
  vi: {
    heroEyebrow: 'Tiến độ của bạn · hôm nay',
    heroHeadlineDueOne: 'Có {n} nội dung cần ôn hôm nay',
    heroHeadlineDueMany: 'Có {n} nội dung cần ôn hôm nay',
    heroHeadlineNone: 'Hôm nay không có nội dung cần ôn',
    ctaOpenProgress: 'Mở Tiến độ',
    dailyGoalLabel: 'Mục tiêu hằng ngày',
    dailyGoalNotTracked: 'Chưa được theo dõi',
    streakLabel: 'Chuỗi ngày',
    streakDaysValueNone: '0 ngày',
    streakDaysValueOne: '{n} ngày',
    streakDaysValueMany: '{n} ngày',
    dueLabel: 'Cần ôn tập',
    dueValueNone: 'Đã hoàn thành hết',
    dueValueOne: '{n} mục',
    dueValueMany: '{n} mục',
    startReview: 'Bắt đầu ôn tập',
    weekLabel: 'Tuần này',
    weekMinutesValueNone: '0 phút',
    weekMinutesValueOne: '{n} phút',
    weekMinutesValueMany: '{n} phút',
    weeklyGoalTitle: 'Mục tiêu hàng tuần · {n} ngày',
    dayStreakStatLabel: 'Chuỗi ngày',
    savedItemsStatLabel: 'Mục đã lưu',
    goalPrefix: 'Mục tiêu',
    goalEveryday: 'Giao tiếp hằng ngày',
    goalWork: 'Công việc',
    goalExam: 'Ôn thi',
    goalVoice: 'Tự tin khi nói',
    goalNotSet: 'Chưa đặt',
    actionHistory: 'Lịch sử',
    actionPlan: 'Gói & mức dùng',
    actionPrivacy: 'Quyền riêng tư',
    actionFeedback: 'Góp ý',
    actionAdmin: 'Quản trị hệ thống',
    actionSignOut: 'Đăng xuất',
    actionAdminSub: 'Chỉ dành cho tài khoản quản trị',
    actionSettingsSub: 'ngôn ngữ, học tập, ôn tập, thông báo',
    actionHistorySub: 'mọi hoạt động đã ghi, theo ngày',
    actionProgressSub: 'kỹ năng, minh chứng, thứ hạng',
    actionPlanSub: 'gói, giới hạn, hoá đơn, bảng giá',
    actionPrivacySub: 'micrô · âm thanh học viên',
    actionFeedbackSub: 'đánh giá Orena, đề xuất cải thiện',
    weekdays: 'T2,T3,T4,T5,T6,T7,CN',
    rankLevelLabel: 'Cấp {n}',
  },
  zh: {
    heroEyebrow: '你的进度 · 今天',
    heroHeadlineDueOne: '今天有 {n} 项内容待复习',
    heroHeadlineDueMany: '今天有 {n} 项内容待复习',
    heroHeadlineNone: '今天没有待复习内容',
    ctaOpenProgress: '打开进度',
    dailyGoalLabel: '每日目标',
    dailyGoalNotTracked: '暂未记录',
    streakLabel: '连续天数',
    streakDaysValueNone: '0 天',
    streakDaysValueOne: '{n} 天',
    streakDaysValueMany: '{n} 天',
    dueLabel: '待复习',
    dueValueNone: '全部完成',
    dueValueOne: '{n} 项',
    dueValueMany: '{n} 项',
    startReview: '开始复习',
    weekLabel: '本周',
    weekMinutesValueNone: '0 分钟',
    weekMinutesValueOne: '{n} 分钟',
    weekMinutesValueMany: '{n} 分钟',
    weeklyGoalTitle: '每周目标 · {n} 天',
    dayStreakStatLabel: '连续天数',
    savedItemsStatLabel: '已保存内容',
    goalPrefix: '目标',
    goalEveryday: '日常生活',
    goalWork: '工作',
    goalExam: '备考',
    goalVoice: '口语自信',
    goalNotSet: '未设置',
    actionHistory: '历史记录',
    actionPlan: '套餐与用量',
    actionPrivacy: '隐私',
    actionFeedback: '反馈',
    actionAdmin: '平台管理',
    actionSignOut: '退出登录',
    actionAdminSub: '仅限管理员账号',
    actionSettingsSub: '语言、学习、复习、通知',
    actionHistorySub: '按天记录的全部活动',
    actionProgressSub: '技能、证据、等级',
    actionPlanSub: '套餐、限额、发票、价格',
    actionPrivacySub: '麦克风 · 学员录音',
    actionFeedbackSub: '为 Orena 打分，提出改进建议',
    weekdays: '一,二,三,四,五,六,日',
    rankLevelLabel: '等级 {n}',
  },
});
