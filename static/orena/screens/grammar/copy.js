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
  },
  en: {
    title: 'Grammar',
    topics_one: '{n} topic',
    topics_other: '{n} topics',
    empty: 'No grammar points yet.',
    levelHeading: '{code} · {name}',
    cefrA1: 'Beginner', cefrA2: 'Elementary', cefrB1: 'Intermediate', cefrB2: 'Upper-intermediate', cefrC1: 'Advanced', cefrC2: 'Proficient',
    hskBand1: 'Elementary', hskBand2: 'Intermediate', hskBand3: 'Advanced',
  },
  vi: {
    title: 'Ngữ pháp',
    topics_other: '{n} chủ điểm',
    empty: 'Chưa có điểm ngữ pháp nào.',
    levelHeading: '{code} · {name}',
    cefrA1: 'Mới bắt đầu', cefrA2: 'Sơ cấp', cefrB1: 'Trung cấp', cefrB2: 'Trung cao cấp', cefrC1: 'Cao cấp', cefrC2: 'Thành thạo',
    hskBand1: 'Sơ cấp', hskBand2: 'Trung cấp', hskBand3: 'Cao cấp',
  },
  zh: {
    title: '语法',
    topics_other: '{n} 个主题',
    empty: '还没有语法点。',
    levelHeading: '{code} · {name}',
    cefrA1: '入门', cefrA2: '基础', cefrB1: '中级', cefrB2: '中高级', cefrC1: '高级', cefrC2: '精通',
    hskBand1: '初等', hskBand2: '中等', hskBand3: '高等',
  },
});
