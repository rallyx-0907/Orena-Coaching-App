// Authored presentation notes reference existing, stable Grammar Concept IDs.
// Examples and evaluation contracts continue to come from the canonical catalog.
// These generated editorial notes are explicitly labelled in the product.
const patterns = {
  en: [
    {
      id: 'a1-complete-sentences-and-basic-word-order',
      contrast: {
        instead: 'Every day I English study.',
        judgement: 'grammatically_impossible',
        why: {
          en: 'The object cannot sit before the verb. English keeps subject, verb, object in that order even when a time expression starts the sentence: Every day I study English.',
          zh: '宾语不能放在动词前。即使句首有时间词，英语仍保持“主语＋动词＋宾语”：Every day I study English。',
          vi: 'Tân ngữ không thể đứng trước động từ. Ngay cả khi câu bắt đầu bằng cụm thời gian, tiếng Anh vẫn giữ chủ ngữ, động từ, tân ngữ: Every day I study English.',
        },
      },
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
      contrast: {
        instead: 'I ready.',
        judgement: 'grammatically_impossible',
        why: {
          en: 'English needs the verb even when the meaning is obvious: I am ready. Many languages leave it out, which is why this one is easy to drop.',
          zh: '即使意思很清楚，英语也需要这个动词：I am ready。很多语言可以省略，所以这里容易漏掉。',
          vi: 'Tiếng Anh vẫn cần động từ dù nghĩa đã rõ: I am ready. Nhiều ngôn ngữ lược bỏ nó, nên chỗ này rất dễ quên.',
        },
      },
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
      contrast: {
        instead: 'This is mine notebook.',
        judgement: 'grammatically_impossible',
        why: {
          en: 'Mine never takes a noun after it. Before a noun the form is my: this is my notebook. Mine stands alone: the notebook is mine.',
          zh: 'mine 后面不能再接名词。名词前用 my：this is my notebook。mine 单独使用：the notebook is mine。',
          vi: 'Mine không bao giờ đi kèm danh từ phía sau. Trước danh từ dùng my: this is my notebook. Mine đứng một mình: the notebook is mine.',
        },
      },
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
      contrast: {
        instead: '我中文学。',
        judgement: 'grammatically_impossible',
        why: {
          en: 'The object follows the verb: 我学中文. Putting 中文 before 学 breaks the basic order - unlike the time expression, which does go before the verb.',
          zh: '宾语在动词后面：我学中文。把“中文”放到“学”前面就破坏了基本语序；时间词才可以放在动词前。',
          vi: 'Tân ngữ đứng sau động từ: 我学中文. Đặt 中文 trước 学 làm hỏng trật tự cơ bản; chỉ cụm thời gian mới đứng trước động từ.',
        },
      },
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
      contrast: {
        instead: '我很是学生。',
        judgement: 'grammatically_impossible',
        why: {
          en: '是 does not take 很. 很 goes with adjectives - 我很高 - while 是 links to a noun on its own: 我是学生.',
          zh: '“是”前面不用“很”。“很”与形容词搭配（我很高），而“是”直接连接名词：我是学生。',
          vi: '“是” không đi với “很”. “很” dùng với tính từ (我很高), còn “是” nối trực tiếp với danh từ: 我是学生.',
        },
      },
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
      contrast: {
        instead: '我学校在。',
        judgement: 'grammatically_impossible',
        why: {
          en: '在 comes before the place, not after it: 我在学校. Chinese puts the location phrase ahead of what happens there, which is the opposite of the English order.',
          zh: '“在”放在地点前，不放在地点后：我在学校。汉语把处所短语放在动作前面，这与英语的顺序相反。',
          vi: '“在” đứng trước địa điểm, không đứng sau: 我在学校. Tiếng Trung đặt cụm chỉ nơi chốn trước hành động, ngược với trật tự tiếng Anh.',
        },
      },
      note: {
        en: 'To locate a known person or thing, place 在 before the location: 我在学校. The person or thing you are locating comes first.',
        zh: '说明已知的人或事物在哪里时，把 在 放在地点前：我在学校。要说明位置的人或事物放在前面。',
        vi: 'Để nói người hoặc vật đã biết ở đâu, đặt 在 trước địa điểm: 我在学校. Người hoặc vật cần xác định vị trí đứng trước.',
      },
    },
  ],
};
patterns.en.push(
  {
    id: 'a2-past-simple-regular-verbs',
    title: { en: 'Then, or usually?', zh: '那一次，还是平时？' },
    line: 'Yesterday I walked home.',
    parts: ['Yesterday', 'walked'],
    note: {
      en: 'A completed event at a finished past time uses the past simple. A present routine answers a different question: I walk home every day.',
      zh: '已经结束的过去时间里发生的事情用一般过去时。现在的习惯是另一回事：I walk home every day。',
      vi: 'Một sự việc đã kết thúc ở thời điểm quá khứ dùng quá khứ đơn. Thói quen hiện tại là chuyện khác: I walk home every day.',
    },
    contrast: {
      instead: 'Yesterday I walk home.',
      judgement: 'wrong_for_intended_meaning',
      why: {
        en: 'For an ordinary account of yesterday, walked places the event in the past. Narrative present can be a deliberate storytelling choice; it is not the neutral account intended here.',
        zh: '普通地讲昨天的事，用 walked 表明事情发生在过去。故事中有时刻意使用现在时，但不是这里想表达的普通叙述。',
        vi: 'Khi kể thông thường về hôm qua, walked đặt sự việc vào quá khứ. Hiện tại kể chuyện là một lựa chọn có chủ ý, không phải cách kể trung tính ở đây.',
      },
    },
  },
  {
    id: 'a2-present-perfect-vs-past-simple',
    title: { en: 'An experience, or a date?', zh: '一次经历，还是一个日期？' },
    line: 'I visited London last year.',
    parts: ['visited', 'last year'],
    note: {
      en: 'Name a finished past time with the past simple. I have visited London presents the experience without saying when.',
      zh: '说出已经结束的过去时间时，用一般过去时。I have visited London 表达有过这种经历，不说明是什么时候。',
      vi: 'Khi nêu thời gian quá khứ đã kết thúc, dùng quá khứ đơn. I have visited London nói về trải nghiệm, không nói khi nào.',
    },
    contrast: {
      instead: 'I have visited London last year.',
      judgement: 'grammatically_impossible',
      why: {
        en: 'In standard English, last year fixes a finished past period, which conflicts with this present-perfect construction. Use visited here.',
        zh: '标准英语中，last year 指定了已经结束的过去时间，与这里的现在完成时结构冲突。此处用 visited。',
        vi: 'Trong tiếng Anh chuẩn, last year là thời gian quá khứ đã kết thúc, không đi với cấu trúc hiện tại hoàn thành này. Dùng visited.',
      },
    },
  },
  {
    id: 'a2-first-conditional',
    title: { en: 'Make a plan with room for change', zh: '给计划留一点余地' },
    line: 'If it rains tomorrow, I will stay home.',
    parts: ['If it rains', 'I will stay home'],
    note: {
      en: 'For a possible future condition, use the present form after if and put the prediction in the main clause.',
      zh: '表达未来可能出现的条件时，if 从句用现在时，主句表达预测。',
      vi: 'Với điều kiện có thể xảy ra trong tương lai, dùng hiện tại sau if và đặt dự đoán ở mệnh đề chính.',
    },
    contrast: {
      instead: 'If it will rain tomorrow, I will stay home.',
      judgement: 'contextually_inappropriate',
      why: {
        en: 'This is an ordinary weather condition, not willingness or insistence. Here rains supplies the condition; will belongs in the prediction.',
        zh: '这里说普通的天气条件，不是意愿或坚持。用 rains 提供条件，用 will 表达主句的预测。',
        vi: 'Đây là điều kiện thời tiết thông thường, không phải ý muốn hay sự khăng khăng. Rains nêu điều kiện; will nằm trong dự đoán.',
      },
    },
  },
);
patterns.zh.push(
  {
    id: 'zh-hsk2-1-kinh-nghi-m',
    title: { en: 'Something you have experienced', zh: '你有过这样的经历吗？' },
    line: '我没去过北京。',
    parts: ['没', '去过', '北京'],
    note: {
      en: '过 after a verb presents an experience. To say that experience has not happened, use 没 before the verb.',
      zh: '动词后的“过”表示经历。说没有这种经历时，在动词前用“没”。',
      vi: '过 sau động từ nói về trải nghiệm. Để nói chưa có trải nghiệm đó, dùng 没 trước động từ.',
    },
    contrast: {
      instead: '我不去过北京。',
      judgement: 'grammatically_impossible',
      why: {
        en: '不 does not negate this experiential 过 construction. 没去过 means you have not been; 不去 means you do not or will not go.',
        zh: '这里的经历结构“过”不用“不”来否定。“没去过”表示没有经历；“不去”表示不去做或不愿去。',
        vi: '不 không phủ định cấu trúc trải nghiệm 过 này. 没去过 là chưa từng đi; 不去 là không đi hoặc sẽ không đi.',
      },
    },
  },
  {
    id: 'zh-hsk2-4-so-s-nh',
    title: { en: 'Notice a difference', zh: '说说哪里不一样' },
    line: '今天比昨天冷。',
    parts: ['今天', '比昨天', '冷'],
    note: {
      en: '比 introduces what you compare against. The adjective follows the comparison: today is colder than yesterday.',
      zh: '“比”引出比较对象，形容词放在比较结构后面：今天比昨天冷。',
      vi: '比 đưa ra đối tượng so sánh. Tính từ đứng sau phần so sánh: hôm nay lạnh hơn hôm qua.',
    },
    contrast: {
      instead: '今天比昨天很冷。',
      judgement: 'grammatically_impossible',
      why: {
        en: 'Standard 比 comparisons do not put 很 before this adjective. You can say 冷多了 to express a much larger difference.',
        zh: '标准的“比”字句这里不在形容词前加“很”。“比昨天冷”已经表达了比较，差别很大时可以说“比昨天冷多了”。',
        vi: 'Trong câu so sánh 比 chuẩn, không thêm 很 trước tính từ ở đây. Có thể nói 冷多了 để nhấn mạnh chênh lệch lớn.',
      },
    },
  },
  {
    id: 'zh-hsk3-1-n-n-t-ng',
    title: { en: 'Where did you put it?', zh: '你把它放在哪儿了？' },
    line: '我把钥匙放在桌上了。',
    parts: ['把钥匙', '放在桌上'],
    note: {
      en: '把 brings a known object forward, then tells what happened to it. The rest of the sentence must actually say what you did with the keys.',
      zh: '“把”把已知的对象提前，后面说清楚这个对象发生了什么变化或去了哪里。',
      vi: '把 đưa tân ngữ đã xác định lên trước, rồi nói điều gì xảy ra với nó. Phần sau phải cho biết bạn đã làm gì với chìa khóa.',
    },
    contrast: {
      instead: '我把钥匙。',
      judgement: 'grammatically_impossible',
      why: {
        en: 'This stops after naming the object. Add the action and its outcome or destination, such as 放在桌上了.',
        zh: '这句话只说出了对象，还没有说做了什么。“把”字句需要补上动作和结果或位置，例如“放在桌上了”，让对方知道钥匙去了哪里。',
        vi: 'Câu này dừng ở việc nêu tân ngữ. Cần thêm hành động và kết quả hoặc vị trí, như 放在桌上了.',
      },
    },
  },
);
export const patternsFor = (language) => patterns[language] || [];
