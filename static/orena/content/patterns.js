// Authored presentation notes reference existing, stable Grammar Concept IDs.
// Examples and evaluation contracts continue to come from the canonical catalog.
// These generated editorial notes are explicitly labelled in the product.
const patterns = {
  en: [
    {
      id: 'a1-complete-sentences-and-basic-word-order',
      title: { en: 'Who does what?', zh: '谁做了什么？' },
      line: 'I study English every day.',
      parts: ['I', 'study', 'English'],
      note: {
        en: 'In an ordinary statement, put the subject before the verb. When the verb takes an object, it normally follows the verb.',
        zh: '在普通陈述句中，主语放在动词前。动词需要宾语时，宾语通常放在动词后。',
        vi: 'Trong câu trần thuật thông thường, chủ ngữ đứng trước động từ. Nếu động từ cần tân ngữ, tân ngữ thường đứng sau động từ.',
      },
    },
    {
      id: 'a1-be-am-is-are',
      title: { en: 'Tell someone who you are', zh: '说说你是谁' },
      line: 'I am ready.',
      parts: ['I', 'am', 'ready'],
      note: {
        en: 'Use am with I, is with he, she or it, and are with you, we or they. Be can connect the subject to an identity, a description or a place.',
        zh: 'I 搭配 am；he、she、it 搭配 is；you、we、they 搭配 are。be 可以把主语与身份、描述或地点连接起来。',
        vi: 'Dùng am với I; is với he, she, it; are với you, we, they. Be nối chủ ngữ với danh tính, đặc điểm hoặc địa điểm.',
      },
    },
    {
      id: 'a1-possessive-adjectives-pronouns-and-possessive-s',
      title: { en: 'A small thing that is yours', zh: '一件属于你的小东西' },
      line: 'This is my notebook.',
      parts: ['my notebook', 'the notebook is mine'],
      note: {
        en: 'My goes before a noun: my notebook. Mine stands on its own: the notebook is mine. The same distinction appears in your/yours and her/hers.',
        zh: 'my 放在名词前：my notebook。mine 可以单独使用：the notebook is mine。your/yours、her/hers 也有这种区别。',
        vi: 'My đứng trước danh từ: my notebook. Mine đứng độc lập: the notebook is mine. Your/yours và her/hers cũng có sự phân biệt này.',
      },
    },
  ],
  zh: [
    {
      id: 'zh-hsk1-1-svo-c-b-n',
      title: { en: 'Put a thought in motion', zh: '让一句话动起来' },
      line: '我学中文。',
      parts: ['我', '学', '中文'],
      note: {
        en: 'A basic statement often follows subject, verb, object: 我学中文. A time expression can go before the verb phrase: 我今天学中文.',
        zh: '基本陈述句常按“主语＋动词＋宾语”排列：我学中文。时间可以放在动词短语前：我今天学中文。',
        vi: 'Câu trần thuật cơ bản thường theo thứ tự chủ ngữ, động từ, tân ngữ: 我学中文. Thời gian có thể đứng trước cụm động từ: 我今天学中文.',
      },
    },
    {
      id: 'zh-hsk1-2-c-u-nh-danh',
      title: { en: 'Make an introduction', zh: '从一句介绍开始' },
      line: '我是学生。',
      parts: ['我', '是', '学生'],
      note: {
        en: '是 connects someone or something with a noun identity: 我是学生. Use 不是 to deny that identity, or add 吗 to ask a yes/no question.',
        zh: '是 把人或事物与名词性身份连接起来：我是学生。否定时用 不是；在句末加 吗 可以提出是非问句。',
        vi: '是 nối người hoặc vật với một danh tính bằng danh từ: 我是学生. Dùng 不是 để phủ định, hoặc thêm 吗 cuối câu để hỏi có/không.',
      },
    },
    {
      id: 'zh-hsk1-4-v-tr',
      title: { en: 'Where will we meet?', zh: '我们在哪里见？' },
      line: '我在学校。',
      parts: ['我', '在', '学校'],
      note: {
        en: 'To locate a known person or thing, place 在 before the location: 我在学校. The person or thing you are locating comes first.',
        zh: '说明已知的人或事物在哪里时，把 在 放在地点前：我在学校。要说明位置的人或事物放在前面。',
        vi: 'Để nói người hoặc vật đã biết ở đâu, đặt 在 trước địa điểm: 我在学校. Người hoặc vật cần xác định vị trí đứng trước.',
      },
    },
  ],
};
export const patternsFor = (language) => patterns[language] || [];
