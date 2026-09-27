import { defineCopy } from '../../copy/index.js';

export const t = defineCopy('grammar', {
  layers: {
    title: 'interface',
    topics: 'interface',
    open: 'interface',
    done: 'interface',
    empty: 'support',
  },
  en: {
    title: 'Grammar',
    topics_one: '{n} topic · {done}/{total} done',
    topics_other: '{n} topics · {done}/{total} done',
    open: 'Open',
    done: 'Done',
    empty: 'No grammar concepts yet.',
  },
  vi: {
    title: 'Ngữ pháp',
    topics_other: '{n} chủ điểm · {done}/{total} đã học',
    open: 'Chưa học',
    done: 'Đã học',
    empty: 'Chưa có điểm ngữ pháp nào.',
  },
  zh: {
    title: '语法',
    topics_other: '{n} 个主题 · 已完成 {done}/{total}',
    open: '未学',
    done: '已完成',
    empty: '暂时还没有语法要点。',
  },
});
