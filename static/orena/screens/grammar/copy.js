import { defineCopy } from '../../copy/index.js';

export const t = defineCopy('grammar', {
  layers: {
    title: 'interface',
    topics: 'interface',
    empty: 'interface',
    // Level group headings (model.js levelHeading): "{code} · {name}". CEFR by level, HSK 3.0
    // (levels 1-9, contract §0) by its three bands 初等 / 中等 / 高等.
    levelHeading: 'interface',
    cefrA1: 'interface', cefrA2: 'interface', cefrB1: 'interface', cefrB2: 'interface', cefrC1: 'interface', cefrC2: 'interface',
    hskBand1: 'interface', hskBand2: 'interface', hskBand3: 'interface',
    // The Library's sections (model.js buildLibrary, 2026-10-08).
    levelLabel: 'interface',
    levelPoints: 'interface',
    continueTitle: 'interface',
    continueHint: 'interface',
    levelComplete: 'interface',
    topicsTitle: 'interface',
    topicsHint: 'interface',
    topicMeta: 'interface',
    showAllTopics: 'interface',
    showFewerTopics: 'interface',
    allTitle: 'interface',
    allHint: 'interface',
    clearTopic: 'interface',
    tagNew: 'interface',
    tagDone: 'interface',
    tagScore: 'interface',
    otherTopic: 'interface',
  },
  en: {
    title: 'Grammar',
    topics_one: '{n} topic',
    topics_other: '{n} topics',
    empty: 'No grammar points yet.',
    levelHeading: '{code} · {name}',
    cefrA1: 'Beginner', cefrA2: 'Elementary', cefrB1: 'Intermediate', cefrB2: 'Upper-intermediate', cefrC1: 'Advanced', cefrC2: 'Proficient',
    hskBand1: 'Elementary', hskBand2: 'Intermediate', hskBand3: 'Advanced',

    levelLabel: 'Level', levelPoints: '{n} points',
    continueTitle: 'Continue learning', continueHint: 'Next at {level}', levelComplete: 'You have completed every point at this level.',
    topicsTitle: 'Explore by topic', topicsHint: '{n} topics at {level}', topicMeta: '{n} points · {done} done', showAllTopics: 'Show all {n} topics', showFewerTopics: 'Show fewer',
    allTitle: 'All grammar', allHint: '{level} · {n} points', clearTopic: 'All topics', tagNew: 'New', tagDone: 'Done', tagScore: '{correct}/{total}', otherTopic: 'Other',
  },
  vi: {
    title: 'Ngữ pháp',
    topics_other: '{n} chủ điểm',
    empty: 'Chưa có điểm ngữ pháp nào.',
    levelHeading: '{code} · {name}',
    cefrA1: 'Mới bắt đầu', cefrA2: 'Sơ cấp', cefrB1: 'Trung cấp', cefrB2: 'Trung cao cấp', cefrC1: 'Cao cấp', cefrC2: 'Thành thạo',
    hskBand1: 'Sơ cấp', hskBand2: 'Trung cấp', hskBand3: 'Cao cấp',

    levelLabel: 'Trình độ', levelPoints: '{n} điểm',
    continueTitle: 'Học tiếp', continueHint: 'Tiếp theo ở {level}', levelComplete: 'Bạn đã hoàn thành mọi điểm ở trình độ này.',
    topicsTitle: 'Khám phá theo chủ đề', topicsHint: '{n} chủ đề ở {level}', topicMeta: '{n} điểm · đã xong {done}', showAllTopics: 'Xem cả {n} chủ đề', showFewerTopics: 'Thu gọn',
    allTitle: 'Toàn bộ ngữ pháp', allHint: '{level} · {n} điểm', clearTopic: 'Mọi chủ đề', tagNew: 'Mới', tagDone: 'Đã xong', tagScore: '{correct}/{total}', otherTopic: 'Khác',
  },
  zh: {
    title: '语法',
    topics_other: '{n} 个主题',
    empty: '还没有语法点。',
    levelHeading: '{code} · {name}',
    cefrA1: '入门', cefrA2: '基础', cefrB1: '中级', cefrB2: '中高级', cefrC1: '高级', cefrC2: '精通',
    hskBand1: '初等', hskBand2: '中等', hskBand3: '高等',

    levelLabel: '级别', levelPoints: '{n} 个语法点',
    continueTitle: '继续学习', continueHint: '{level} 的下一步', levelComplete: '你已完成这个级别的所有语法点。',
    topicsTitle: '按主题浏览', topicsHint: '{level} 共 {n} 个主题', topicMeta: '{n} 个语法点 · 已完成 {done}', showAllTopics: '显示全部 {n} 个主题', showFewerTopics: '收起',
    allTitle: '全部语法', allHint: '{level} · {n} 个语法点', clearTopic: '全部主题', tagNew: '新', tagDone: '已完成', tagScore: '{correct}/{total}', otherTopic: '其他',
  },
});
