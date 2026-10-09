/* The shell's and the kit's own words: navigation, the top bar, system states and every place's
   title (the breadcrumb). Interface layer throughout - chrome, not explanation (D-079). */
import { defineCopy } from './index.js';

const KEYS = [
  'mainNavigation', 'skipToContent',
  'today', 'discover', 'orena', 'practiceHub', 'practiceShort', 'myLibrary', 'libraryShort', 'progress', 'profile',
  'askOrena', 'askOrenaSub', 'askAnything', 'talkToOrena', 'search', 'notifications', 'back', 'retry', 'close', 'undo', 'dismiss',
  'loadingLesson', 'errorLesson', 'errorStory', 'errorPlace', 'errorOffline', 'errorServer', 'comingSoon',
  'cantOpen', 'offlineTitle', 'stillOffline',
  'lang_en', 'lang_zh', 'learningLabel', 'plan_free', 'plan_premium', 'planDesc_free', 'planDesc_premium',
  'content', 'listening', 'dictation', 'reader', 'pronunciation', 'compareWithModel', 'review', 'writing',
  'listeningComprehension',
  'compareVersions', 'checkUnderstanding', 'collection', 'word', 'grammar', 'settings', 'shadowing', 'freeTalk',
  'conversation', 'situationReaction', 'retell', 'reactReuse', 'timedRecall', 'contextTransfer', 'dailyFeed',
  'contextRewrite', 'timedWriting', 'readingTransfer', 'readingComplete', 'attemptHistory', 'speakingSummary',
  'timedReaction', 'respondToContent', 'discussion', 'mockInterview', 'soundTone', 'fromYourErrors',
  'welcome', 'admin',
];

export const shellCopy = defineCopy('shell', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    listeningComprehension: 'Listening comprehension',
    mainNavigation: 'Main', skipToContent: 'Skip to content',
    today: 'Today', discover: 'Discover', orena: 'Orena', practiceHub: 'Practice Hub', practiceShort: 'Practice',
    myLibrary: 'My Library', libraryShort: 'Library', progress: 'Progress', profile: 'Profile',
    askOrena: 'Ask Orena', askOrenaSub: 'Your study companion', askAnything: 'Ask anything…', talkToOrena: 'Talk to Orena', search: 'Search',
    notifications: 'Notifications', back: 'Back', retry: 'Retry', close: 'Close', undo: 'Undo', dismiss: 'Dismiss',
    loadingLesson: 'Preparing your lesson', errorLesson: 'Couldn’t load this lesson', errorStory: 'Couldn’t load this story', errorPlace: 'Couldn’t load {place}',
    errorOffline: 'Check your connection and try again.', errorServer: 'The server didn’t respond. Nothing was lost.',
    comingSoon: 'Coming soon',
    cantOpen: 'Can’t open this yet', offlineTitle: 'You’re offline.', stillOffline: 'Still offline',
    lang_en: 'English', lang_zh: 'Chinese', learningLabel: '{language} · {level}',
    plan_free: 'Free', plan_premium: 'Premium', planDesc_free: 'Core writing practice for everyday learning.', planDesc_premium: 'Deeper feedback, personalized practice and advanced progress tools.',
    content: 'Content', listening: 'Listening', dictation: 'Dictation', reader: 'Reader', pronunciation: 'Pronunciation',
    compareWithModel: 'Compare with model', review: 'Review', writing: 'Writing', compareVersions: 'Compare versions',
    checkUnderstanding: 'Check understanding', collection: 'Collection', word: 'Word', grammar: 'Grammar',
    settings: 'Settings', shadowing: 'Shadowing', freeTalk: 'Free Talk', conversation: 'Conversation',
    situationReaction: 'Situation Reaction', retell: 'Retell', reactReuse: 'React / Reuse', timedRecall: 'Timed Recall',
    contextTransfer: 'Context Transfer', dailyFeed: 'Daily feed', contextRewrite: 'Context Rewrite',
    timedWriting: 'Timed Writing', readingTransfer: 'Reading Transfer', readingComplete: 'Reading complete',
    attemptHistory: 'Attempt history', speakingSummary: 'Speaking summary', timedReaction: 'Timed Reaction',
    respondToContent: 'Respond to content', discussion: 'Discussion', mockInterview: 'Mock Interview',
    soundTone: 'Sound / Tone', fromYourErrors: 'From your errors', welcome: 'Welcome', admin: 'Platform admin',
  },
  vi: {
    listeningComprehension: 'Nghe hiểu',
    mainNavigation: 'Điều hướng chính', skipToContent: 'Đến nội dung',
    today: 'Hôm nay', discover: 'Khám phá', orena: 'Orena', practiceHub: 'Luyện tập', practiceShort: 'Luyện tập',
    myLibrary: 'Thư viện của tôi', libraryShort: 'Thư viện', progress: 'Tiến độ', profile: 'Hồ sơ',
    askOrena: 'Hỏi Orena', askOrenaSub: 'Bạn đồng hành học tập', askAnything: 'Hỏi bất cứ điều gì…', talkToOrena: 'Nói với Orena', search: 'Tìm kiếm',
    notifications: 'Thông báo', back: 'Quay lại', retry: 'Thử lại', close: 'Đóng', undo: 'Hoàn tác', dismiss: 'Bỏ qua',
    loadingLesson: 'Đang chuẩn bị bài học', errorLesson: 'Không tải được bài học này', errorStory: 'Không tải được bài đọc này', errorPlace: 'Không tải được {place}',
    errorOffline: 'Kiểm tra kết nối rồi thử lại.', errorServer: 'Máy chủ không phản hồi. Không có gì bị mất.',
    comingSoon: 'Sắp có',
    cantOpen: 'Chưa mở được', offlineTitle: 'Bạn đang ngoại tuyến.', stillOffline: 'Vẫn đang ngoại tuyến',
    lang_en: 'Tiếng Anh', lang_zh: 'Tiếng Trung', learningLabel: '{language} · {level}',
    plan_free: 'Miễn phí', plan_premium: 'Premium', planDesc_free: 'Luyện viết cốt lõi cho việc học hằng ngày.', planDesc_premium: 'Phản hồi sâu hơn, luyện tập cá nhân hóa và công cụ theo dõi tiến độ nâng cao.',
    content: 'Nội dung', listening: 'Nghe', dictation: 'Chép chính tả', reader: 'Đọc', pronunciation: 'Phát âm',
    compareWithModel: 'So với mẫu', review: 'Ôn tập', writing: 'Viết', compareVersions: 'So sánh phiên bản',
    checkUnderstanding: 'Kiểm tra hiểu', collection: 'Bộ sưu tập', word: 'Từ', grammar: 'Ngữ pháp',
    settings: 'Cài đặt', shadowing: 'Đọc theo', freeTalk: 'Nói tự do', conversation: 'Hội thoại',
    situationReaction: 'Phản xạ tình huống', retell: 'Kể lại', reactReuse: 'Phản hồi và dùng lại', timedRecall: 'Nhớ nhanh',
    contextTransfer: 'Chuyển ngữ cảnh', dailyFeed: 'Từ mỗi ngày', contextRewrite: 'Viết lại theo ngữ cảnh',
    timedWriting: 'Viết có giờ', readingTransfer: 'Vận dụng bài đọc', readingComplete: 'Đọc xong',
    attemptHistory: 'Các lần thử', speakingSummary: 'Tổng kết buổi nói', timedReaction: 'Phản xạ có giờ',
    respondToContent: 'Phản hồi nội dung', discussion: 'Thảo luận', mockInterview: 'Phỏng vấn thử',
    soundTone: 'Âm và thanh điệu', fromYourErrors: 'Từ lỗi của bạn', welcome: 'Chào mừng', admin: 'Quản trị nền tảng',
  },
  zh: {
    listeningComprehension: '听力理解',
    mainNavigation: '主导航', skipToContent: '跳至内容',
    today: '今天', discover: '发现', orena: 'Orena', practiceHub: '练习中心', practiceShort: '练习',
    myLibrary: '我的书库', libraryShort: '书库', progress: '进度', profile: '个人',
    askOrena: '问 Orena', askOrenaSub: '你的学习伙伴', askAnything: '随便问…', talkToOrena: '和 Orena 说话', search: '搜索',
    notifications: '通知', back: '返回', retry: '重试', close: '关闭', undo: '撤销', dismiss: '忽略',
    loadingLesson: '正在准备课程', errorLesson: '无法加载这节课', errorStory: '无法加载这篇文章', errorPlace: '无法加载{place}',
    errorOffline: '请检查网络后重试。', errorServer: '服务器没有响应。内容没有丢失。',
    comingSoon: '即将推出',
    cantOpen: '暂时打不开', offlineTitle: '你已离线。', stillOffline: '仍处于离线状态',
    lang_en: '英语', lang_zh: '中文', learningLabel: '{language} · {level}',
    plan_free: '免费版', plan_premium: '高级版', planDesc_free: '满足日常学习的核心写作练习。', planDesc_premium: '更深入的反馈、个性化练习和高级进度工具。',
    content: '内容', listening: '听力', dictation: '听写', reader: '阅读', pronunciation: '发音',
    compareWithModel: '与示范对比', review: '复习', writing: '写作', compareVersions: '版本对比',
    checkUnderstanding: '理解检查', collection: '合集', word: '词语', grammar: '语法',
    settings: '设置', shadowing: '跟读', freeTalk: '自由说', conversation: '对话',
    situationReaction: '情景反应', retell: '复述', reactReuse: '反应与复用', timedRecall: '限时回忆',
    contextTransfer: '语境迁移', dailyFeed: '每日词汇', contextRewrite: '语境改写',
    timedWriting: '限时写作', readingTransfer: '阅读迁移', readingComplete: '读完了',
    attemptHistory: '尝试记录', speakingSummary: '口语总结', timedReaction: '限时反应',
    respondToContent: '回应内容', discussion: '讨论', mockInterview: '模拟面试',
    soundTone: '音与声调', fromYourErrors: '从错误中练', welcome: '欢迎', admin: '平台管理',
  },
});

/* A plan's name and description follow the interface language by the plan's id (the catalogue's own
   English strings are the fallback for a plan this build has no words for). */
export function planName(plan) {
  const key = `plan_${plan?.id}`;
  return plan && shellCopy.has(key) ? shellCopy(key) : String(plan?.name || '');
}

export function planDescription(plan) {
  const key = `planDesc_${plan?.id}`;
  return plan && shellCopy.has(key) ? shellCopy(key) : String(plan?.description || '');
}
