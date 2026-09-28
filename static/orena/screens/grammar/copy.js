import { defineCopy } from '../../copy/index.js';

export const t = defineCopy('grammar', {
  layers: {
    title: 'interface',
    topics: 'interface',
    open: 'interface',
    done: 'interface',
    empty: 'support',
    // languages-4 (2) / finding B.2: level-group headings. The value space is closed - exactly
    // nine labels across both providers' `level_names` (writing_coach/languages/grammar_registry.py:
    // English A1-C2 uses six of them, Chinese HSK1-7-9 uses all nine, reusing the same English word
    // for the levels that mean the same standing) - so these are mapped to real interface copy
    // rather than shown as the backend's own English string, per model.js#levelName's own comment.
    levelFoundation: 'interface', levelCore: 'interface', levelBasic: 'interface',
    levelIntermediate: 'interface', levelLowerIntermediate: 'interface', levelUpperIntermediate: 'interface',
    levelAdvanced: 'interface', levelMastery: 'interface', levelAdvancedMastery: 'interface',
  },
  en: {
    title: 'Grammar',
    topics_one: '{n} topic · {done}/{total} done',
    topics_other: '{n} topics · {done}/{total} done',
    open: 'Not done',
    done: 'Done',
    empty: 'No grammar concepts yet.',
    levelFoundation: 'Foundation', levelCore: 'Core', levelBasic: 'Basic',
    levelIntermediate: 'Intermediate', levelLowerIntermediate: 'Lower-intermediate', levelUpperIntermediate: 'Upper-intermediate',
    levelAdvanced: 'Advanced', levelMastery: 'Mastery', levelAdvancedMastery: 'Advanced mastery',
  },
  vi: {
    title: 'Ngữ pháp',
    topics_other: '{n} chủ điểm · {done}/{total} đã học',
    open: 'Chưa học',
    done: 'Đã học',
    empty: 'Chưa có điểm ngữ pháp nào.',
    levelFoundation: 'Nền tảng', levelCore: 'Cốt lõi', levelBasic: 'Cơ bản',
    levelIntermediate: 'Trung cấp', levelLowerIntermediate: 'Trung cấp thấp', levelUpperIntermediate: 'Trung cấp cao',
    levelAdvanced: 'Nâng cao', levelMastery: 'Thành thạo', levelAdvancedMastery: 'Thành thạo nâng cao',
  },
  zh: {
    title: '语法',
    topics_other: '{n} 个主题 · 已完成 {done}/{total}',
    open: '未学',
    done: '已完成',
    empty: '暂时还没有语法要点。',
    levelFoundation: '基础', levelCore: '核心', levelBasic: '初级',
    levelIntermediate: '中级', levelLowerIntermediate: '中低级', levelUpperIntermediate: '中高级',
    levelAdvanced: '高级', levelMastery: '精通', levelAdvancedMastery: '高级精通',
  },
});
