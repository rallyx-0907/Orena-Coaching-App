// Experience identity is presentation over the existing routes, never another
// capability engine. New surfaces join this map and inherit the same shell.
import { link } from '../product/intent.js';
import { esc } from './html.js';
import { scene } from './brand.js';
import { continuationEntries, continuationPlace, hint, pageIntro } from './patterns.js';
import { entryIcon } from './icons.js';
import { icon } from './phosphor.js';
import { art } from './content.js';
import { continuationExperience, continuationLink } from '../product/intent.js';

export { entryIcon } from './icons.js';

export const referenceCopy = {
  en: {
    collection: 'Collection',
    moreStories: 'More to read',
    collectionSearch: 'Find something you kept',
    collectionSearchHint: 'Search everything you have met or kept',
    collectionLenses: 'How you met it',
    lens_all: 'Everything', lens_reading: 'Read', lens_listening: 'Heard',
    lens_speaking: 'Spoken', lens_writing: 'Written', lens_language: 'Language',
    collectionResults: 'here',
    collectionThreads: 'Where you were', collectionYourContent: 'What you brought in',
    collectionYourLanguage: 'Language you kept',
    collectionViewAll: 'See all',
    collectionEmpty: 'Nothing here yet.',
    collectionEmptyNote: 'What you read, hear, keep and write will gather here.',
    threadLabel: 'A thread', contentLabel: 'Yours', languageLabel: 'Kept',
    discover: 'Discover', practice: 'Practice', reading: 'Reading', listening: 'Listening',
    writing: 'Writing', speaking: 'Speaking', vocabulary: 'Vocabulary', understanding: 'Patterns & meaning',
    language: 'My language', recall: 'Recall', continue: 'Continue', content: 'My content', admin: 'Platform Admin',
    world: 'A bigger world', make: 'Make it yours', keep: 'Your growing world',
    destinations: 'Destinations', closeDestinations: 'Close destinations',
    home: 'Home', library: 'Library', progress: 'Progress', profile: 'Profile', you: 'You',
    dictation: 'Dictation', settings: 'Settings', allPractice: 'All practice',
    allDestinations: 'Everything in Orena', mainNavigation: 'Main', practiceNavigation: 'Practice',
    languagePair: 'Learning {learning}, explained in {support}',
    searchPlaceholder: 'Search books, audio, words…', dueCount: '{n} due',
    libraryFilters: 'Filters', libraryClear: 'Clear', libraryClearFilters: 'Clear filters',
    libraryType: 'Type', libraryLevel: 'Level', libraryTopic: 'Topic',
    libraryType_books: 'Books', libraryType_audio: 'Audio', libraryType_video: 'Video', libraryType_collections: 'Collections',
    librarySearch: 'Search the library', librarySortTitle: 'Title A–Z', librarySortLevel: 'Level',
    libraryView: 'View', libraryViewGrid: 'Grid', libraryViewList: 'List',
    libraryTitles: '{n} titles', libraryShowResults: 'Show {n} results', libraryNoResults: 'Nothing matches these filters',
    libraryLoadMore: 'Load more · {n} shown',
    searchTitle: 'Search', searchResults: '{n} results', searchWord: 'Word', searchWords: 'Words',
    searchInYourTexts: 'In your texts', searchNothing: 'Nothing found for this search',
    searchBooksGap: 'Searching inside library books is not available yet',
    readerPanel: 'Word panel', readerTab_word: 'Word', readerTab_notes: 'Notes', readerTab_chapters: 'Chapters',
    readerPinyin: 'Pinyin', readerTapWord: 'Tap any word for meaning, audio and save',
    readerSavedHere: 'Saved in this chapter', readerLayerUnavailable: 'Not available for this text yet',
    speakAsk: 'Say this line your own way', speakTapRecord: 'Tap to record · hold to hear yours',
    speakAttempts: 'Your attempts', speakAttempt: 'Take {n}', speakWobble: 'Still wobbling',
    speakPlayMine: 'Hear your take', speakRetry: 'Try again', speakSkip: 'Skip this one',
    dictYouTyped: 'You typed', dictCorrect: 'Correct', dictToFix: '{n} to fix', dictCharacters: '{n} characters',
    dictReplay: 'Replay', dictHint: 'Hint', dictReveal: 'Show it',
    greetMorning: 'Good morning', greetAfternoon: 'Good afternoon', greetEvening: 'Good evening',
    greetNamed: 'Hello {name}', greetPlain: 'Welcome back', forYou: 'For you',
    reviewDue: 'Review {n} words', reviewNote: 'The ones your own reading left behind',
    reviewNothing: 'Nothing is due', reviewNothingNote: 'Everything saved is resting until its day',
    levelUnknown: 'No level recorded yet', streakUnmeasured: 'Days in a row are not counted yet',
    listenQuiz: 'Comprehension quiz', listenPrevLine: 'Previous line', listenNextLine: 'Next line',
    listenTranscript: 'Transcript', listenBack: 'Back to listening',
    vocabYourCollections: 'Your collections', vocabSavedWords: 'Saved words', vocabTier: 'Tier',
    vocabNotMastered: 'Not mastered', vocabShowAll: 'Show all {n}', vocabTapToFlip: 'Tap to flip',
    vocabKnow: 'Know', vocabHowWell: 'How well did you know it?', vocabGradeHard: 'Hard',
    vocabGradeEasy: 'Easy', vocabGradeUnavailable: 'Four-grade review is not available yet',
    vocabWordsLabel: 'Words', vocabShuffle: 'Shuffle', vocabBrowseCollections: 'Browse collections',
    chapterComplete: 'Chapter complete', chapterDoneLine: 'Chapter {n} done. {p}% of the book.',
    chapterQuiz: 'Quiz', chapterNewWords: 'New words', chapterTime: 'Time',
    chapterSavedHere: 'Saved from this chapter', chapterReviewNow: 'Review now',
    chapterUpNext: 'Up next', chapterContinue: 'Continue reading', chapterLast: 'That was the last chapter.',
    bookChapters: 'Chapters', bookUnreadOnly: 'Unread only', bookShowAll: 'Show all {n} chapters',
    bookAbout: 'About', bookWordsFrom: 'Words from this book', bookSimilar: 'Similar level',
    bookSimilarGap: 'Recommendations need level data', bookNoWordsSaved: 'No words saved from this book yet',
    bookStatWordsSaved: 'Words saved', bookStatTime: 'Time read', bookStatQuiz: 'Quiz average',
    bookStatAudio: 'Audio', bookAudioGap: 'No audio yet', bookNotMeasured: 'Not measured yet',
    bookContinueChapter: 'Continue chapter {n}', bookChapterOf: 'Ch {n} of {t}', bookNotStarted: 'Not started',
    bookNext: 'Next', bookRead: 'Read', bookBookmark: 'Save this book', bookDownload: 'Download for offline',
    bookMore: 'More', bookSoon: 'Not available yet', bookChapterWords: '{n} words',
    searchChip_all: 'All', searchChip_words: 'Words', searchChip_books: 'Books', searchChip_audio: 'Audio', searchChip_collections: 'Collections',
    savedTitle: 'Saved', saved_words: 'Words', saved_highlights: 'Highlights', saved_notes: 'Notes', saved_content: 'Content',
    savedNoWords: 'No saved words yet', savedNoWordsNote: 'Tap any word while reading or listening and it lands here for review.',
    savedOpenBook: 'Open a book', savedSearchWords: 'Search saved words', savedOneStar: '1 star', savedRecent: 'Recent',
    savedFrom: 'from', savedDue: '{n} words are due today', savedNoHighlights: 'No highlights yet',
    savedNoContent: 'Nothing brought in yet', savedNotesUnavailable: 'Notes are not available yet',
    historyTitle: 'History', historyToday: 'Today', historyEmpty: 'Nothing here yet', historyWindow: '30 days',
    historyCompleted: 'completed', historyVersion: 'version {n}', historyAnswered: '{n} of {t}',
    itemCount: '{n} items', todayWords: "Today's words", flipCard: 'Flip', flipBack: 'Front',
    progressThisWeek: 'This week', progressStudyUnavailable: 'Study time is not measured yet',
    progressStreak: 'Streak', progressWordsDue: 'Words due', progressWords: 'Words',
    progressByDomain: 'By domain', progressNotMeasured: 'Not measured yet',
    progressWordsLine: '{saved} saved · {mastered} mastered',
    progressChartUnavailable: 'Daily study time is not measured yet',
    invitation: 'A little curiosity.\nA bigger world.',
    welcome: 'Come for a story. Stay for what it opens up.',
    note: 'Listen closely. Wander through a story. Find something you want to say.',
    featured: 'Through another window', readNext: 'Between the lines',
    practiceTitle: 'A small moment.\nA little more yours.',
    practiceNote: 'Choose an intention. Work with a real voice, a passage, or a thought of your own.',
    listenTitle: 'The world has\nsomething to say.',
    listenNote: 'Follow a voice at your pace. Stay with the meaning, or step inside a single line.',
    goRead: 'Find a story', goListen: 'Follow a voice', goSpeak: 'Start an exchange',
    studio: 'Make room for your own words', studioNote: 'Something you heard can become something you say.',
    writingInvite: 'A thought worth putting into words.',
    writingDetail: 'A message, a story, a different point of view. Begin with what you mean.',
    practiceInvite: 'Stay with one small moment.',
    practiceDetail: 'Catch the words. Borrow the rhythm. Try again with a little more understanding.',
    continueTitle: 'There’s a thread\nwaiting for you.',
    continueEmpty: 'Your next visit starts here.',
    continueNote: 'The stories you enter and the words you work on leave a way back. These threads stay on this device.',
    collectionTitle: 'A world with\nyour fingerprints on it.',
    collectionNote: 'Things you brought in and chose to keep. Ready for another look.',
    browseAll: 'All the ways in', fieldNote: 'Follow your curiosity', continueLearning: 'Continue learning',
    railPrevious: 'Previous', railNext: 'Next', railEmpty: 'Nothing here yet.',
    startTitle: 'Start here', startAction: 'Start learning', continueAction: 'Continue',
    railShort: 'Around five minutes', railStories: 'Stories', railVoices: 'Everyday voices',
    railSay: 'Something to say', railWords: 'Words worth keeping', railMinutes: 'min',
    newContent: 'New content', newContentEmpty: 'Nothing new yet',
    direct: 'Choose your intention', review: 'Reference in progress · your work stays yours',
  },
  zh: {
    admin: '\u5e73\u53f0\u7ba1\u7406',
    collection: '收藏',
    moreStories: '更多可读的',
    collectionSearch: '找回你留下的东西',
    collectionSearchHint: '搜索你遇到过、留下过的一切',
    collectionLenses: '你是怎么遇到它的',
    lens_all: '全部', lens_reading: '读过', lens_listening: '听过',
    lens_speaking: '说过', lens_writing: '写过', lens_language: '语言',
    collectionResults: '项',
    collectionThreads: '上次停在哪里', collectionYourContent: '你带进来的',
    collectionYourLanguage: '你留下的语言',
    collectionViewAll: '查看全部',
    collectionEmpty: '这里还是空的。',
    collectionEmptyNote: '你读过、听过、留下和写下的，都会聚到这里。',
    threadLabel: '一条线索', contentLabel: '你的', languageLabel: '已留下',
    discover: '发现', practice: '练习', reading: '阅读', listening: '聆听', writing: '写作',
    speaking: '表达', vocabulary: '词汇', understanding: '句式与含义', language: '我的语言', recall: '回想',
    continue: '继续', content: '我的内容', world: '走进更大的世界', make: '用自己的方式表达', keep: '慢慢积累的世界',
    destinations: '去处', closeDestinations: '收起去处',
    home: '首页', library: '书库', progress: '进度', profile: '个人', you: '我',
    dictation: '听写', settings: '设置', allPractice: '全部练习',
    allDestinations: 'Orena 的全部去处', mainNavigation: '主要', practiceNavigation: '练习',
    languagePair: '正在学{learning}，用{support}讲解',
    searchPlaceholder: '搜索书、音频、词…', dueCount: '{n} 个待复习',
    libraryFilters: '筛选', libraryClear: '清除', libraryClearFilters: '清除筛选',
    libraryType: '类型', libraryLevel: '级别', libraryTopic: '主题',
    libraryType_books: '书', libraryType_audio: '音频', libraryType_video: '视频', libraryType_collections: '词集',
    librarySearch: '在书库中搜索', librarySortTitle: '按标题', librarySortLevel: '按级别',
    libraryView: '视图', libraryViewGrid: '网格', libraryViewList: '列表',
    libraryTitles: '{n} 项', libraryShowResults: '显示 {n} 个结果', libraryNoResults: '没有符合筛选的内容',
    libraryLoadMore: '加载更多 · 已显示 {n}',
    searchTitle: '搜索', searchResults: '{n} 个结果', searchWord: '词语', searchWords: '词语',
    searchInYourTexts: '在你的文本中', searchNothing: '没有找到相关内容',
    searchBooksGap: '暂不支持在书库书籍正文中搜索',
    readerPanel: '词语面板', readerTab_word: '词语', readerTab_notes: '笔记', readerTab_chapters: '章节',
    readerPinyin: '拼音', readerTapWord: '点任意词语，看释义、听发音、收藏',
    readerSavedHere: '本章已收藏', readerLayerUnavailable: '这篇文本暂不支持',
    speakAsk: '用你自己的方式说这句', speakTapRecord: '点一下录音 · 长按听自己的',
    speakAttempts: '你的尝试', speakAttempt: '第 {n} 次', speakWobble: '还不够稳的词',
    speakPlayMine: '听自己的录音', speakRetry: '再试一次', speakSkip: '跳过这句',
    dictYouTyped: '你写的', dictCorrect: '原文', dictToFix: '还差 {n} 处', dictCharacters: '{n} 个字',
    dictReplay: '再听', dictHint: '提示', dictReveal: '看原文',
    greetMorning: '早上好', greetAfternoon: '下午好', greetEvening: '晚上好',
    greetNamed: '你好，{name}', greetPlain: '欢迎回来', forYou: '为你推荐',
    reviewDue: '复习 {n} 个词', reviewNote: '都是你自己读到时留下的',
    reviewNothing: '暂时没有要复习的', reviewNothingNote: '收藏的词都在等下一个到期日',
    levelUnknown: '还没有记录级别', streakUnmeasured: '连续天数暂未统计',
    listenQuiz: '理解测验', listenPrevLine: '上一句', listenNextLine: '下一句',
    listenTranscript: '文字稿', listenBack: '返回听力',
    vocabYourCollections: '你的词表', vocabSavedWords: '已收藏的词', vocabTier: '等级',
    vocabNotMastered: '未掌握', vocabShowAll: '显示全部 {n} 个', vocabTapToFlip: '点一下翻面',
    vocabKnow: '记得', vocabHowWell: '刚才记得怎么样？', vocabGradeHard: '有点难',
    vocabGradeEasy: '很简单', vocabGradeUnavailable: '四档复习暂未开放',
    vocabWordsLabel: '词', vocabShuffle: '打乱顺序', vocabBrowseCollections: '浏览词表',
    chapterComplete: '本章读完', chapterDoneLine: '第 {n} 章读完了，全书进度 {p}%。',
    chapterQuiz: '测验', chapterNewWords: '新词', chapterTime: '时长',
    chapterSavedHere: '本章收藏的词', chapterReviewNow: '现在复习',
    chapterUpNext: '接下来', chapterContinue: '继续读', chapterLast: '这是最后一章。',
    bookChapters: '章节', bookUnreadOnly: '仅未读', bookShowAll: '显示全部 {n} 章',
    bookAbout: '简介', bookWordsFrom: '本书中的词', bookSimilar: '同级别推荐',
    bookSimilarGap: '推荐需要级别数据', bookNoWordsSaved: '本书还没有收藏的词',
    bookStatWordsSaved: '已收藏词', bookStatTime: '阅读时长', bookStatQuiz: '测验均分',
    bookStatAudio: '音频', bookAudioGap: '暂无音频', bookNotMeasured: '尚未统计',
    bookContinueChapter: '继续第 {n} 章', bookChapterOf: '第 {n} 章 / 共 {t} 章', bookNotStarted: '尚未开始',
    bookNext: '接下来', bookRead: '已读', bookBookmark: '收藏这本书', bookDownload: '离线下载',
    bookMore: '更多', bookSoon: '暂不可用', bookChapterWords: '{n} 词',
    searchChip_all: '全部', searchChip_words: '词语', searchChip_books: '书', searchChip_audio: '音频', searchChip_collections: '词集',
    savedTitle: '收藏', saved_words: '词语', saved_highlights: '划线', saved_notes: '笔记', saved_content: '内容',
    savedNoWords: '还没有收藏词语', savedNoWordsNote: '阅读或聆听时点任意一个词，它会出现在这里等你复习。',
    savedOpenBook: '打开一本书', savedSearchWords: '搜索收藏的词语', savedOneStar: '一星', savedRecent: '最近',
    savedFrom: '来自', savedDue: '今天有 {n} 个词待复习', savedNoHighlights: '还没有划线',
    savedNoContent: '还没有带入内容', savedNotesUnavailable: '暂不支持笔记',
    historyTitle: '历史', historyToday: '今天', historyEmpty: '这里还没有记录', historyWindow: '30 天',
    historyCompleted: '已完成', historyVersion: '第 {n} 版', historyAnswered: '{n} / {t}',
    itemCount: '{n} 项', todayWords: '今日词语', flipCard: '翻面', flipBack: '正面',
    progressThisWeek: '本周', progressStudyUnavailable: '学习时长暂未记录',
    progressStreak: '连续天数', progressWordsDue: '待复习', progressWords: '词语',
    progressByDomain: '各项', progressNotMeasured: '暂未记录',
    progressWordsLine: '已收藏 {saved} · 已掌握 {mastered}',
    progressChartUnavailable: '每日学习时长暂未记录',
    invitation: '一点好奇，\n一个更大的世界。', welcome: '从一个故事开始，看看它会带你去哪里。',
    note: '听见一种声音，走进一个故事，找到自己想说的话。',
    featured: '打开另一扇窗', readNext: '在字里行间',
    practiceTitle: '留住一个瞬间，\n让它成为你的语言。',
    practiceNote: '选一个练习方向。从真实的声音、文章，或自己的想法开始。',
    listenTitle: '这个世界，\n有话想对你说。', listenNote: '按自己的节奏听懂一种声音。可以一直听，也可以停下来练一句。',
    goRead: '找一个故事', goListen: '跟随一种声音', goSpeak: '开始一段对话',
    studio: '给自己的话留一点空间', studioNote: '刚刚听到的话，也可以成为你自己的表达。',
    writingInvite: '有个想法，值得写下来。', writingDetail: '一条消息，一个故事，一种不同的看法。从你真正想表达的意思开始。',
    practiceInvite: '多留一会儿，听懂这一刻。', practiceDetail: '听清文字，感受节奏。多一点理解，再试一次。',
    continueTitle: '上次的故事，\n等你接着往下走。', continueEmpty: '下次回来，从这里继续。',
    continueNote: '读过的故事、写到一半的话，都留下一条回来的路。这些记录保存在当前设备。',
    collectionTitle: '这个世界里，\n有你留下的印记。', collectionNote: '你带来的、你选择留下的内容。随时可以再看看。',
    browseAll: '每一种开始', fieldNote: '跟着好奇心走', continueLearning: '继续学习',
    railPrevious: '上一组', railNext: '下一组', railEmpty: '这里还没有内容。',
    startTitle: '从这里开始', startAction: '开始学习', continueAction: '继续',
    railShort: '五分钟左右', railStories: '故事', railVoices: '真实的声音',
    railSay: '说点什么', railWords: '值得记住的词', railMinutes: '分钟',
    newContent: '新上线', newContentEmpty: '暂无新内容',
    direct: '选择练习方向', review: '参考体验建设中 · 你的作品属于你',
  },
};
/* The rail and the room headings follow the support language too. Vietnamese
   merges over English for the same reason the main pack does: a key that has
   no Vietnamese yet still reads. */
referenceCopy.vi = {
  ...referenceCopy.en,
  discover: 'Khám phá',
  practice: 'Luyện tập',
  reading: 'Đọc',
  listening: 'Nghe',
  writing: 'Viết',
  speaking: 'Nói',
  vocabulary: 'Từ vựng',
  understanding: 'Cấu trúc & ý nghĩa',
  language: 'Ngôn ngữ của tôi',
  recall: 'Ôn lại',
  continue: 'Tiếp tục',
  content: 'Nội dung của tôi',
  admin: 'Quản trị nền tảng',
  world: 'Một thế giới rộng hơn',
  make: 'Theo cách của bạn',
  keep: 'Những gì bạn giữ lại',
  destinations: 'Các điểm đến',
  closeDestinations: 'Đóng danh sách',
  home: 'Trang chủ',
  library: 'Thư viện',
  progress: 'Tiến độ',
  profile: 'Hồ sơ',
  you: 'Bạn',
  dictation: 'Chính tả',
  settings: 'Cài đặt',
  allPractice: 'Tất cả bài luyện',
  allDestinations: 'Mọi nơi trong Orena',
  mainNavigation: 'Chính',
  practiceNavigation: 'Luyện tập',
  languagePair: 'Đang học {learning}, giải thích bằng {support}',
  searchPlaceholder: 'Tìm sách, audio, từ vựng…',
  dueCount: '{n} từ đến hạn',
  libraryFilters: 'Bộ lọc',
  libraryClear: 'Xoá',
  libraryClearFilters: 'Xoá bộ lọc',
  libraryType: 'Loại',
  libraryLevel: 'Trình độ',
  libraryTopic: 'Chủ đề',
  libraryType_books: 'Sách',
  libraryType_audio: 'Bài nghe',
  libraryType_video: 'Video clip',
  libraryType_collections: 'Bộ từ vựng',
  librarySearch: 'Tìm trong thư viện',
  librarySortTitle: 'Tên A–Z',
  librarySortLevel: 'Trình độ',
  libraryView: 'Kiểu xem',
  libraryViewGrid: 'Lưới',
  libraryViewList: 'Danh sách',
  libraryTitles: '{n} mục',
  libraryShowResults: 'Hiện {n} kết quả',
  libraryNoResults: 'Không có gì khớp bộ lọc này',
  libraryLoadMore: 'Tải thêm · đang hiện {n}',
  searchTitle: 'Tìm kiếm',
  searchResults: '{n} kết quả',
  searchWord: 'Từ',
  searchWords: 'Từ vựng',
  searchInYourTexts: 'Trong bài đọc của bạn',
  searchNothing: 'Không tìm thấy gì cho từ khoá này',
  searchBooksGap: 'Chưa hỗ trợ tìm trong nội dung sách của thư viện',
  readerPanel: 'Bảng từ',
  readerTab_word: 'Từ',
  readerTab_notes: 'Ghi chú',
  readerTab_chapters: 'Chương',
  readerPinyin: 'Phiên âm',
  readerTapWord: 'Chạm vào từ bất kỳ để xem nghĩa, nghe và lưu',
  readerSavedHere: 'Đã lưu trong chương này',
  readerLayerUnavailable: 'Bài này chưa hỗ trợ',
  speakAsk: 'Nói câu này theo cách của bạn',
  speakTapRecord: 'Nhấn để ghi âm · giữ để nghe lại bản của bạn',
  speakAttempts: 'Những lần bạn đã thử',
  speakAttempt: 'Lần {n}',
  speakWobble: 'Những từ còn ngập ngừng',
  speakPlayMine: 'Nghe bản của bạn',
  speakRetry: 'Thử lại',
  speakSkip: 'Bỏ qua câu này',
  dictYouTyped: 'Bạn đã gõ',
  dictCorrect: 'Bản gốc',
  dictToFix: 'còn {n} chỗ',
  dictCharacters: '{n} ký tự',
  dictReplay: 'Nghe lại',
  dictHint: 'Gợi ý',
  dictReveal: 'Xem bản gốc',
  greetMorning: 'Chào buổi sáng',
  greetAfternoon: 'Chào buổi chiều',
  greetEvening: 'Chào buổi tối',
  greetNamed: 'Chào {name}',
  greetPlain: 'Chào bạn',
  forYou: 'Dành cho bạn',
  reviewDue: 'Ôn {n} từ',
  reviewNote: 'Những từ chính bạn để lại khi đọc',
  reviewNothing: 'Chưa có từ đến hạn',
  reviewNothingNote: 'Các từ đã lưu đang đợi ngày của chúng',
  levelUnknown: 'Chưa ghi nhận trình độ',
  streakUnmeasured: 'Chưa đếm số ngày liên tiếp',
  listenQuiz: 'Câu hỏi hiểu bài',
  listenPrevLine: 'Câu trước',
  listenNextLine: 'Câu sau',
  listenTranscript: 'Lời thoại',
  listenBack: 'Quay lại phần nghe',
  vocabYourCollections: 'Bộ từ của bạn',
  vocabSavedWords: 'Từ đã lưu',
  vocabTier: 'Bậc',
  vocabNotMastered: 'Chưa thuộc',
  vocabShowAll: 'Xem tất cả {n} từ',
  vocabTapToFlip: 'Chạm để lật thẻ',
  vocabKnow: 'Nhớ rồi',
  vocabHowWell: 'Bạn nhớ từ này đến đâu?',
  vocabGradeHard: 'Hơi khó',
  vocabGradeEasy: 'Dễ',
  vocabGradeUnavailable: 'Ôn bốn mức chưa khả dụng',
  vocabWordsLabel: 'Từ',
  vocabShuffle: 'Đảo thứ tự',
  vocabBrowseCollections: 'Xem các bộ từ',
  chapterComplete: 'Đã đọc xong chương',
  chapterDoneLine: 'Xong chương {n}. Đã đi được {p}% cuốn sách.',
  chapterQuiz: 'Câu hỏi',
  chapterNewWords: 'Từ mới',
  chapterTime: 'Thời gian',
  chapterSavedHere: 'Đã lưu trong chương này',
  chapterReviewNow: 'Ôn ngay',
  chapterUpNext: 'Tiếp theo',
  chapterContinue: 'Đọc tiếp',
  chapterLast: 'Đây là chương cuối.',
  bookChapters: 'Chương',
  bookUnreadOnly: 'Chỉ chương chưa đọc',
  bookShowAll: 'Xem tất cả {n} chương',
  bookAbout: 'Giới thiệu',
  bookWordsFrom: 'Từ trong sách này',
  bookSimilar: 'Cùng trình độ',
  bookSimilarGap: 'Gợi ý cần dữ liệu trình độ',
  bookNoWordsSaved: 'Chưa lưu từ nào từ sách này',
  bookStatWordsSaved: 'Từ đã lưu',
  bookStatTime: 'Thời gian đọc',
  bookStatQuiz: 'Điểm trung bình',
  bookStatAudio: 'Âm thanh',
  bookAudioGap: 'Chưa có âm thanh',
  bookNotMeasured: 'Chưa được đo',
  bookContinueChapter: 'Đọc tiếp chương {n}',
  bookChapterOf: 'Chương {n} / {t}',
  bookNotStarted: 'Chưa bắt đầu',
  bookNext: 'Tiếp theo',
  bookRead: 'Đã đọc',
  bookBookmark: 'Lưu sách này',
  bookDownload: 'Tải về để đọc ngoại tuyến',
  bookMore: 'Thêm',
  bookSoon: 'Chưa khả dụng',
  bookChapterWords: '{n} từ',
  searchChip_all: 'Tất cả',
  searchChip_words: 'Từ',
  searchChip_books: 'Sách',
  searchChip_audio: 'Bài nghe',
  searchChip_collections: 'Bộ từ vựng',
  savedTitle: 'Đã lưu',
  saved_words: 'Từ',
  saved_highlights: 'Đánh dấu',
  saved_notes: 'Ghi chú',
  saved_content: 'Nội dung',
  savedNoWords: 'Chưa có từ nào được lưu',
  savedNoWordsNote: 'Chạm vào bất kỳ từ nào khi đọc hoặc nghe, nó sẽ nằm ở đây để ôn.',
  savedOpenBook: 'Mở một cuốn sách',
  savedSearchWords: 'Tìm trong từ đã lưu',
  savedOneStar: '1 sao',
  savedRecent: 'Mới nhất',
  savedFrom: 'từ',
  savedDue: 'Hôm nay có {n} từ đến hạn',
  savedNoHighlights: 'Chưa đánh dấu cụm từ nào',
  savedNoContent: 'Chưa mang nội dung nào vào',
  savedNotesUnavailable: 'Chưa hỗ trợ ghi chú',
  historyTitle: 'Lịch sử',
  historyToday: 'Hôm nay',
  historyEmpty: 'Chưa có gì ở đây',
  historyWindow: '30 ngày',
  historyCompleted: 'đã xong',
  historyVersion: 'bản {n}',
  historyAnswered: '{n}/{t}',
  itemCount: '{n} mục',
  todayWords: 'Từ hôm nay',
  flipCard: 'Lật thẻ',
  flipBack: 'Mặt trước',
  progressThisWeek: 'Tuần này',
  progressStudyUnavailable: 'Chưa đo thời gian học',
  progressStreak: 'Chuỗi ngày',
  progressWordsDue: 'Từ đến hạn',
  progressWords: 'Từ đã lưu',
  progressByDomain: 'Theo kỹ năng',
  progressNotMeasured: 'Chưa có số liệu',
  progressWordsLine: '{saved} đã lưu · {mastered} đã thuộc',
  progressChartUnavailable: 'Chưa đo thời gian học mỗi ngày',
  fieldNote: 'Đi theo tò mò của bạn',
  continueLearning: 'Tiếp tục học',
  continueAction: 'Tiếp tục',
  startTitle: 'Bắt đầu ở đây',
  startAction: 'Bắt đầu học',
  collectionViewAll: 'Xem tất cả',
  railPrevious: 'Trước',
  railNext: 'Sau',
  railEmpty: 'Chưa có gì ở đây.',
  railShort: 'Khoảng năm phút',
  railStories: 'Câu chuyện',
  railVoices: 'Những giọng nói đời thường',
  railSay: 'Điều muốn nói',
  railWords: 'Từ đáng giữ lại',
  railMinutes: 'phút',
  continueEmpty: 'Lần tới bạn sẽ bắt đầu từ đây.',
  browseAll: 'Mọi lối vào',
  direct: 'Chọn một hướng luyện tập',
  collection: 'Bộ sưu tập',
  collectionTitle: 'Một thế giới mang\ndấu tay của bạn.',
  collectionNote:
    'Những thứ bạn mang vào và chọn giữ lại. Sẵn sàng để xem lại một lần nữa.',
  collectionSearch: 'Tìm thứ bạn đã giữ',
  collectionSearchHint: 'Tìm trong mọi thứ bạn đã gặp hoặc đã giữ',
  collectionLenses: 'Bạn gặp nó theo cách nào',
  collectionResults: 'ở đây',
  collectionThreads: 'Nơi bạn đang dở',
  collectionYourContent: 'Thứ bạn mang vào',
  collectionYourLanguage: 'Ngôn ngữ bạn giữ lại',
  collectionEmpty: 'Chưa có gì ở đây.',
  collectionEmptyNote:
    'Những gì bạn đọc, nghe, giữ lại và viết ra sẽ tụ về đây.',
  lens_all: 'Tất cả',
  lens_reading: 'Đã đọc',
  lens_listening: 'Đã nghe',
  lens_speaking: 'Đã nói',
  lens_writing: 'Đã viết',
  lens_language: 'Ngôn ngữ',
  threadLabel: 'Một mạch đang dở',
  contentLabel: 'Của bạn',
  languageLabel: 'Đã giữ',
  moreStories: 'Còn nữa để đọc',
  invitation: 'Một chút tò mò.\nMột thế giới rộng hơn.',
  welcome: 'Đến vì một câu chuyện. Ở lại vì những gì nó mở ra.',
  note:
    'Lắng nghe thật kỹ. Đi lang thang trong một câu chuyện. Tìm ra điều bạn muốn nói.',
  featured: 'Qua một ô cửa khác',
  readNext: 'Giữa những dòng chữ',
  practiceTitle: 'Một khoảnh khắc nhỏ.\nThêm một chút là của bạn.',
  practiceNote:
    'Chọn một ý định. Làm việc với một giọng nói thật, một đoạn văn, hoặc một suy nghĩ của riêng bạn.',
  listenTitle: 'Thế giới có điều\nmuốn nói với bạn.',
  listenNote:
    'Đi theo một giọng nói với tốc độ của bạn. Ở lại với ý nghĩa, hoặc bước vào bên trong một câu.',
  goRead: 'Tìm một câu chuyện',
  goListen: 'Đi theo một giọng nói',
  goSpeak: 'Bắt đầu một cuộc trao đổi',
  studio: 'Dành chỗ cho lời của chính bạn',
  studioNote: 'Điều bạn nghe được có thể thành điều bạn nói ra.',
  writingInvite: 'Một suy nghĩ đáng được viết thành lời.',
  writingDetail:
    'Một tin nhắn, một câu chuyện, một góc nhìn khác. Hãy bắt đầu từ điều bạn muốn nói.',
  practiceInvite: 'Ở lại với một khoảnh khắc nhỏ.',
  practiceDetail:
    'Bắt lấy từng chữ. Mượn lấy nhịp điệu. Thử lại với một chút hiểu biết hơn.',
  continueTitle: 'Có một mạch đang\nchờ bạn quay lại.',
  continueNote:
    'Những câu chuyện bạn bước vào và những chữ bạn đang gọt giũa đều để lại một lối về. Các mạch này ở lại trên thiết bị này.',
  newContent: 'Nội dung mới',
  newContentEmpty: 'Chưa có gì mới',
  review: 'Phần tham chiếu đang hoàn thiện · bài của bạn vẫn là của bạn',
};

const paths = [
  ['discover', 'discover', null, 'compass'], ['continue', 'continue', null, 'return'],
  ['reading', 'practice', 'reading', 'book'], ['listening', 'practice', 'follow', 'sound'],
  ['practice', 'practice', null, 'focus'], ['writing', 'expression', null, 'pen'],
  ['speaking', 'practice', 'speaking', 'voice'], ['understanding', 'practice', 'grammar', 'spark'],
  ['content', 'content', null, 'folder'], ['language', 'language', null, 'leaf'],
  ['recall', 'practice', 'recall', 'return'],
];
export function entryPoints(ui) {
  const c = referenceCopy[ui] || referenceCopy.en;
  return paths.map(([id, page, intent, icon]) => ({ id, label: c[id], href: link(page, { intent }), icon }));
}
export function experienceFor(location) {
  const { page, intent, id = '' } = location;
  if (intent === 'recall') return 'recall';
  if (page === 'conversation' || (page === 'practice' && intent === 'speaking')) return 'speaking';
  if (page === 'expression') return 'writing';
  if (page === 'practice' && intent === 'grammar') return 'understanding';
  if (['dictation','shadowing','speaking'].includes(intent) && page === 'encounter') return 'practice';
  /* Which room an encounter belongs to.

     The id prefix is the usual answer, but it cannot be the only one: a route
     the product cannot classify used to fall to Reading, so a malformed media
     link took a learner who had asked to listen into the Reading room, rail
     highlight and error state included. The learner's stated intention decides
     when the id cannot, and only then - a `media:` id is Listening whatever
     the intent says, because the content is what it is. */
  if (page === 'encounter') {
    if (/^(media:|url:|upload:)/.test(id)) return 'listening';
    if (id) return 'reading';
    return intent === 'follow' ? 'listening' : 'reading';
  }
  if (page === 'practice' && intent === 'reading') return 'reading';
  if (page === 'practice' && intent === 'follow') return 'listening';
  return page === 'preferences' ? 'discover' : page;
}
/* The shell's destinations (D-059, D-060; Design Contract rule 38).

   Exactly the approved rail: Home, Library, Vocabulary, Progress, then a
   Practice group of Reading, Listening, Speaking, Dictation, Writing, then the
   learner's card. The design system is the visual source of truth (D-060), so
   nothing sits in the rail that the approved design does not draw. Nothing that
   existed is lost either - each has a named home one step away:
   - Continue: the Continue cards on Home, and their "See all";
   - Recall: the due chip in the top bar, and Vocabulary's review action;
   - Grammar and the whole practice map: the Practice heading itself;
   - bringing your own content: Library;
   - Platform Admin: an operator entry, rendered only for admins.

   `current` is derived from the same `experienceFor` the rooms use, so the
   rail, the tab bar and the room can never disagree about where the learner
   is. A room without its own entry lights the entry that leads to it. */
const DESTINATIONS = [
  { id: 'discover', page: 'discover', icon: 'house', label: 'home', owns: ['discover', 'continue'] },
  { id: 'content', page: 'content', icon: 'books', label: 'library', owns: ['content', 'book', 'search'] },
  { id: 'language', page: 'language', icon: 'cards', label: 'vocabulary', owns: ['language', 'recall', 'collection'] },
  { id: 'progress', page: 'progress', icon: 'chart-line-up', label: 'progress', owns: ['progress', 'history'] },
  /* The fifth destination the updated design draws. Until the profile screen
     is built it opens the profile and settings sheet - the same place the
     account card and the phone's own tab open - so the rail is never a link
     to nothing. */
  { id: 'profile', page: '', icon: 'user-circle', label: 'you', owns: ['profile'], sheet: true },
];
const PRACTICE = [
  { id: 'reading', page: 'practice', intent: 'reading', icon: 'book-open', domain: 'reading' },
  { id: 'listening', page: 'practice', intent: 'follow', icon: 'headphones', domain: 'listening' },
  { id: 'speaking', page: 'practice', intent: 'speaking', icon: 'microphone', domain: 'speaking' },
  { id: 'dictation', page: 'practice', intent: 'dictation', icon: 'keyboard', domain: 'dictation' },
  { id: 'writing', page: 'expression', icon: 'pencil-simple', domain: 'writing' },
];
/* The phone's tab bar. Each tab owns the rooms it leads to, so the one that
   lights up is the way back to where the learner is. */
const TABS = [
  { id: 'discover', icon: 'house', label: 'home', owns: ['discover', 'continue', 'practice', 'speaking', 'dictation', 'writing', 'understanding'] },
  { id: 'content', icon: 'books', label: 'library', owns: ['content', 'reading', 'listening', 'book', 'search'] },
  { id: 'language', icon: 'cards', label: 'vocabulary', owns: ['language', 'recall', 'collection'] },
  { id: 'progress', icon: 'chart-line-up', label: 'progress', owns: ['progress', 'history'] },
];

/* Which navigation entry the learner is in. Practice over media - dictation,
   shadowing - is its own entry where one exists and the Practice map where
   it does not; Grammar, which has no rail entry, lights the Practice map. */
export function navigationCurrent(location) {
  const experience = experienceFor(location);
  if (experience === 'practice')
    return location.intent === 'dictation' ? 'dictation' : location.intent === 'shadowing' ? 'listening' : 'practice';
  if (experience === 'understanding') return 'practice';
  return experience;
}
export function navigationEntries(ui) {
  const c = referenceCopy[ui] || referenceCopy.en;
  const main = DESTINATIONS.map((x) => ({ ...x, label: c[x.label], href: link(x.page) }));
  const practice = PRACTICE.map((x) => ({ ...x, label: c[x.id], href: link(x.page, { intent: x.intent }) }));
  return { main, practice, practiceHref: link('practice') };
}
const current = (on) => (on ? ' aria-current="page"' : '');
export function referenceNavigation(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const here = navigationCurrent(ctx.location);
  const { main, practice, practiceHref } = navigationEntries(ctx.ui);
  const mainLinks = main
    .map((entry) => {
      const on = entry.owns.includes(here);
      const inside = `${icon(entry.icon, { filled: on, size: 20 })}<span class="nav-label">${esc(entry.label)}</span>`;
      return entry.sheet
        ? `<button type="button" class="nav-link" data-preference data-nav="${entry.id}">${inside}</button>`
        : `<a class="nav-link" href="${entry.href}"${current(on)} data-nav="${entry.id}">${inside}</a>`;
    })
    .join('');
  // A practice room's icon wears its domain hue; the row itself stays neutral.
  const practiceLinks = practice
    .map((entry) => {
      const on = here === entry.id;
      /* The design prints the learner's level beside each domain. Nothing
         stores one yet (GAP-004), so the slot reads as a dash rather than as
         a level nobody declared. */
      return `<a class="nav-link nav-link--practice" href="${entry.href}"${current(on)} data-nav="${entry.id}" data-domain="${entry.domain}">${icon(entry.icon, { filled: on, size: 18 })}<span class="nav-label">${esc(entry.label)}</span><span class="nav-level ds-data" title="${esc(c.levelUnknown)}">—</span></a>`;
    })
    .join('');
  return `<nav id="shellNav" aria-label="Orena"><div class="nav-sheet-head"><strong>${esc(c.allDestinations)}</strong><button class="nav-close" type="button" data-nav-close aria-label="${esc(c.closeDestinations)}">${icon('x', { size: 20 })}</button></div><div class="nav-group nav-group--main" role="group" aria-label="${esc(c.mainNavigation)}">${mainLinks}</div><div class="nav-group nav-group--practice" role="group" aria-labelledby="navPractice"><a class="nav-heading" id="navPractice" href="${practiceHref}"${current(here === 'practice')} data-nav="practice"><span>${esc(c.practiceNavigation)}</span><span class="sr-only">, ${esc(c.allPractice)}</span></a>${practiceLinks}</div></nav>`;
}

/* The phone's destinations: four tabs and the learner's own. "You" opens the
   profile and settings sheet, so it is a button, not a link. */
export function navigationTabs(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const here = navigationCurrent(ctx.location);
  const tabs = TABS.map((tab) => {
    const on = tab.owns.includes(here);
    const href = tab.id === 'discover' ? link() : link(tab.id);
    return `<a class="shell-tab" href="${href}"${current(on)}>${icon(tab.icon, { filled: on, size: 22 })}<span>${esc(c[tab.label])}</span></a>`;
  }).join('');
  return `<nav class="shell-tabs" aria-label="${esc(c.mainNavigation)}">${tabs}<button class="shell-tab" type="button" data-preference>${icon('user-circle', { size: 22 })}<span>${esc(c.you)}</span></button></nav>`;
}

/* The practice map on a phone. The approved phone composition draws five tabs
   and no practice list; until the Library phase gives Practice its phone home,
   this one control keeps every practice room reachable (tracked as parity
   drift in DESIGN_SYSTEM_MIGRATION.md, not a design of its own). */
export function navigationToggle(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  return `<button class="nav-toggle" data-nav-toggle type="button" aria-expanded="false" aria-controls="shellNav" aria-label="${esc(c.allDestinations)}">${icon('squares-four', { size: 20 })}</button>`;
}


/* The top bar of a destination (Home, Library, Vocabulary, Progress): the
   global search, the language pair and the due chip. Rooms where the learner
   works do not carry it - the content comes forward (rule 11). */
/* The bar the updated design draws: where the learner is, the one search, and
   the streak. The language pair moved to the account card and the profile
   sheet, which is where the design keeps language settings; what is due is a
   counter on Vocabulary, where the design counts it. */
export function topBar(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const here = navigationCurrent(ctx.location);
  /* The bar names the destination with the same word the rail uses. */
  const title = (here === 'discover' ? c.home : c[here]) || c.home;
  return `<h1 class="topbar-title">${esc(title)}</h1><form class="topbar-search" role="search" data-global-search><label class="sr-only" for="globalSearch">${esc(c.searchPlaceholder)}</label>${icon('magnifying-glass', { size: 18 })}<input id="globalSearch" type="search" name="q" autocomplete="off" placeholder="${esc(c.searchPlaceholder)}"></form><div class="topbar-chips">${streakChip(ctx)}</div>`;
}

/* Days in a row. Nothing counts them yet (GAP-001), so the chip keeps its
   place and says so rather than showing a number nobody measured. */
export function streakChip(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  return `<span class="streak-chip" title="${esc(c.streakUnmeasured)}">${icon('fire', { size: 14 })}<span class="ds-data">—</span><span class="sr-only">${esc(c.streakUnmeasured)}</span></span>`;
}

/* Platform Admin is an operator entry, not a learner destination: the updated
   design's rail draws five learner destinations and no operations. It is
   rendered for an administrator inside the profile and settings sheet, which
   is where operating the platform belongs. */
export function operatorEntry(ctx) {
  if (ctx.user?.is_admin !== true) return '';
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  return `<nav class="sheet-links sheet-links--operator" aria-label="${esc(c.admin)}"><a href="${link('admin')}">${esc(c.admin)}</a></nav>`;
}

/* "中文 → VI": what is being learned, and the language Orena explains it in.
   The learning language keeps its own writing system where it has one. */
const LEARNING_MARK = { zh: '中文', en: 'EN' };
export function languagePair(ctx) {
  const learning = LEARNING_MARK[ctx.language] || String(ctx.language || '').toUpperCase();
  const support = String(ctx.support || ctx.ui || '').toUpperCase();
  return { learning, support, text: `${learning} → ${support}` };
}

/* The learner, at the foot of the rail: who they are, what they are learning,
   and the way into settings. Only what the account actually says is shown -
   the design's level ("HSK 2") has no source yet and is tracked as GAP-004. */
export function accountCard(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  const user = ctx.user || {};
  const name = String(user.name || user.display_name || (user.email ? user.email.split('@')[0] : '') || c.you);
  return `<button class="account-card" type="button" data-preference aria-label="${esc(`${c.profile} · ${c.settings}`)}"><span class="account-avatar" aria-hidden="true"></span><span class="account-text"><strong>${esc(name)}</strong><small>${esc(languagePair(ctx).text)}</small></span>${icon('gear-six', { size: 16, className: 'account-gear' })}</button>`;
}
export function accountAvatarButton(ctx) {
  const c = referenceCopy[ctx.ui] || referenceCopy.en;
  return `<button class="account-avatar account-avatar--button" type="button" data-preference aria-label="${esc(`${c.profile} · ${c.settings}`)}"></button>`;
}
export function editorialIntro(ctx, {title, note, state, eyebrow}) {
  return `<header class="editorial-intro"><div><small>${esc(eyebrow || referenceCopy[ctx.ui].fieldNote)}</small><h1>${esc(title).replaceAll('\n','<br>')}</h1><p>${esc(note)}</p></div>${scene(state,{size:'hero'})}</header>`;
}
/* The room whose whole subject is coming back.

   It used to be the same shelf Discover carries, rendered longer: a row of
   white cards each holding a word and a title, which is a list of unfinished
   database rows rather than continuity. What a learner needs here is where
   they are - the thing itself, what it belongs to, how far through they got,
   and one way back in.

   Nothing here is invented. The cover is drawn from the item's own identity,
   the place is printed only when the entry actually carries one, and the shelf
   still decides what can be resumed: a thread whose work is gone is not
   offered, and a device that cannot remember says so.
   `continuationEntries` is that decision; this room asks it. */
const continuationIcons = {
  listening: 'sound',
  reading: 'book',
  speaking: 'voice',
  writing: 'pen',
  understanding: 'spark',
  practice: 'focus',
  recall: 'return',
};

function continueLabel(item, ctx) {
  const experience = continuationExperience(item);
  return experience === 'listening'
    ? ctx.c.followName
    : ctx.c[`${experience}Name`] || ctx.c.resume;
}

function progressBar(place, label) {
  if (!place) return '';
  return `<span class="continue-progress" role="img" aria-label="${esc(label)}"><span class="continue-progress__bar"><span style="width:${place.percent}%"></span></span><small>${place.percent}%</small></span>`;
}

/* The one the learner was last in, given the room to be recognised. */
function continueLead(item, ctx) {
  const c = referenceCopy[ctx.ui];
  const place = continuationPlace(item);
  const progressLabel = place ? `${place.percent}% · ${item.context || item.title}` : '';
  return `<section class="continue-lead"><span class="continue-lead__visual" aria-hidden="true">${art(item)}</span><div class="continue-lead__body"><small>${entryIcon(continuationIcons[continuationExperience(item)] || 'return')}${esc(continueLabel(item, ctx))}</small><h2 lang="${esc(ctx.language)}">${esc(item.title)}</h2>${item.context ? `<p class="continue-lead__context" lang="${esc(ctx.language)}">${esc(item.context)}${place ? ` · ${place.index}/${place.total}` : ''}</p>` : ''}${progressBar(place, progressLabel)}<a class="primary" href="${esc(continuationLink(item))}">${esc(c.continueAction)} <span aria-hidden="true">→</span></a></div></section>`;
}

function continueCard(item, ctx) {
  const place = continuationPlace(item);
  const where = item.context || '';
  return `<a class="continue-card" href="${esc(continuationLink(item))}"><span class="continue-card__visual" aria-hidden="true">${art(item)}</span><span class="continue-card__body"><small>${entryIcon(continuationIcons[continuationExperience(item)] || 'return')}${esc(continueLabel(item, ctx))}</small><strong lang="${esc(ctx.language)}">${esc(item.title)}</strong>${where ? `<span class="continue-card__context" lang="${esc(ctx.language)}">${esc(where)}${place ? ` · ${place.index}/${place.total}` : ''}</span>` : ''}${progressBar(place, place ? `${place.percent}%` : '')}</span></a>`;
}

export function renderContinue(root, ctx) {
  const c = referenceCopy[ctx.ui];
  const threads = continuationEntries(ctx.memory);
  const [lead, ...rest] = threads;
  const body = lead
    ? `${continueLead(lead, ctx)}${rest.length ? `<section class="continue-more" aria-label="${esc(c.continueLearning)}"><div class="section-head"><h2>${esc(c.continueLearning)}</h2>${hint({ text: ctx.c.deviceThreads })}</div><div class="continue-grid">${rest.map((item) => continueCard(item, ctx)).join('')}</div></section>` : ''}`
    : `<section class="continue-empty">${scene('empty', { size: 'medium' })}<div><h2>${esc(c.continueEmpty)}</h2><a class="primary" href="${link()}">${esc(c.startAction)} <span aria-hidden="true">→</span></a></div></section>`;
  root.innerHTML = `${pageIntro({ title: c.continue, compact: true })}${ctx.memory.available ? '' : `<p class="notice">${esc(ctx.c.memoryUnavailable)}</p>`}${body}`;
}
