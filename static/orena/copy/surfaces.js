/* AGENT_CONTRACT §6.2, D-096: the UI publishes each §6.1 id's name and purpose for the server, once
   - never generated at request time and never duplicated in the intelligence lane. A name is the
   title of the route the id opens, read from the shell's own copy (agent/intents.js maps an id to a
   route; shell/routes.js names each route's title key in `crumb`; copy/shell.js holds the titles). A
   purpose is one interface-layer line, en/vi/zh-CN, at most 90 characters (Design Contract rule 50);
   every §6.1 id has one (human, 2026-10-04): each describes the place as the new UI builds it.

   scripts/build_orena_surfaces.mjs calls buildSurfaces() and writes static/orena/copy/surfaces.json;
   scripts/test_orena_surfaces.mjs regenerates the same data and gates the committed file against it. */
import { defineCopy, registeredCopy } from './index.js';
import { SURFACES } from '../agent/contract.js';
import { intentRoute } from '../agent/intents.js';
import { byId } from '../shell/routes.js';
import './shell.js'; // registers the 'shell' table buildSurfaces() reads names from.

/* Purposes: interface layer, ≤ 90 characters, en/vi/zh-CN. Add a §6.1 id's key here only once its
   screen is reviewable end to end (§6.2); the generator never invents one. */
export const surfacesPurpose = defineCopy('surfaces-purpose', {
  layers: {
    'home': 'interface',
    'orena.home': 'interface',
    'library': 'interface',
    'reading.library': 'interface',
    'reading.workspace': 'interface',
    'listening.library': 'interface',
    'listening.workspace': 'interface',
    'listening.dictation': 'interface',
    'speaking.library': 'interface',
    'speaking.workspace': 'interface',
    'speaking.free_talk': 'interface',
    'speaking.word_detail': 'interface',
    'speaking.compare': 'interface',
    'writing.workspace': 'interface',
    'writing.review': 'interface',
    'writing.revision': 'interface',
    'vocabulary.my_language': 'interface',
    'vocabulary.word': 'interface',
    'vocabulary.review_due': 'interface',
    'grammar.catalog': 'interface',
    'grammar.point': 'interface',
    'progress': 'interface',
    'preferences': 'interface',
    'preferences.agent_memory': 'interface',
  },
  en: {
    'home': 'Your next step today: due words, places to continue and one suggested practice',
    'orena.home': 'Ask Orena about your learning, your mistakes and what to practise next',
    'library': 'Find texts, videos and word lists at your level to learn from',
    'reading.library': 'Choose a text at your level to read and learn words from',
    'reading.workspace': 'Read a text, tap any word for its meaning and keep the words you want',
    'listening.library': 'Choose a video or audio to listen to and practise with',
    'listening.workspace': 'Listen line by line with the transcript, meanings and replay',
    'listening.dictation': 'Write down what you hear, then check it word by word',
    'speaking.library': 'Pick a speaking or listening practice: pronunciation, dictation, free talk',
    'speaking.workspace': 'Hear a model line, record yourself and see which sounds to fix',
    'speaking.free_talk': 'Talk freely about a topic and get feedback on what you said',
    'speaking.word_detail': 'See how each word of your take compared with the model',
    'speaking.compare': 'Compare your recording with the model, line by line',
    'writing.workspace': 'Write on a task and get a review with the fixes that matter most',
    'writing.review': 'Read the review of your writing and fix the first issue',
    'writing.revision': 'Compare two versions of your writing and see what improved',
    'vocabulary.my_language': 'The words and texts you kept, with what is due for review',
    'vocabulary.word': 'One word: its meaning, pronunciation, examples and where you met it',
    'vocabulary.review_due': 'Recall the words that are due, then mark how well you knew each',
    'grammar.catalog': 'Browse grammar points by level and open one to learn it',
    'grammar.point': 'Learn one grammar point with examples, then try it yourself',
    'progress': 'See what you practised, your results over time and what to work on',
    'preferences': 'Set your languages, review limits, theme and privacy',
    'preferences.agent_memory': 'See and delete what Orena remembers about your learning',
  },
  vi: {
    'home': 'Bước tiếp theo hôm nay: từ đến hạn, bài đang dở và một gợi ý luyện tập',
    'orena.home': 'Hỏi Orena về việc học, lỗi của bạn và nên luyện gì tiếp theo',
    'library': 'Tìm bài đọc, video và bộ từ hợp trình độ để học',
    'reading.library': 'Chọn một bài đọc hợp trình độ để đọc và học từ',
    'reading.workspace': 'Đọc bài, chạm vào từ để xem nghĩa và lưu những từ bạn muốn',
    'listening.library': 'Chọn video hoặc bài nghe để nghe và luyện tập',
    'listening.workspace': 'Nghe từng câu với lời thoại, nghĩa và nghe lại',
    'listening.dictation': 'Viết lại điều bạn nghe được rồi kiểm tra từng từ',
    'speaking.library': 'Chọn bài luyện nói hoặc nghe: phát âm, chép chính tả, nói tự do',
    'speaking.workspace': 'Nghe câu mẫu, tự thu âm và xem âm nào cần sửa',
    'speaking.free_talk': 'Nói tự do về một chủ đề và nhận góp ý về điều bạn nói',
    'speaking.word_detail': 'Xem từng từ trong lần nói của bạn so với mẫu thế nào',
    'speaking.compare': 'So sánh bản thu của bạn với mẫu, từng câu',
    'writing.workspace': 'Viết theo đề và nhận nhận xét với những chỗ cần sửa nhất',
    'writing.review': 'Đọc nhận xét bài viết của bạn và sửa lỗi đầu tiên',
    'writing.revision': 'So sánh hai phiên bản bài viết và xem điều gì đã tốt hơn',
    'vocabulary.my_language': 'Các từ và bài bạn đã lưu, cùng những gì đến hạn ôn',
    'vocabulary.word': 'Một từ: nghĩa, phát âm, ví dụ và nơi bạn đã gặp nó',
    'vocabulary.review_due': 'Nhớ lại các từ đến hạn rồi đánh dấu bạn nhớ từng từ đến đâu',
    'grammar.catalog': 'Xem các điểm ngữ pháp theo trình độ và mở một điểm để học',
    'grammar.point': 'Học một điểm ngữ pháp qua ví dụ rồi tự thử dùng',
    'progress': 'Xem bạn đã luyện gì, kết quả theo thời gian và nên luyện gì thêm',
    'preferences': 'Đặt ngôn ngữ, giới hạn ôn tập, giao diện và quyền riêng tư',
    'preferences.agent_memory': 'Xem và xoá những gì Orena ghi nhớ về việc học của bạn',
  },
  zh: {
    'home': '今天的下一步：到期的词、未完成的内容和一个推荐练习',
    'orena.home': '向 Orena 询问你的学习、错误以及接下来练什么',
    'library': '按你的水平查找可以学习的文本、视频和词表',
    'reading.library': '选择一篇适合你水平的文章来阅读和学词',
    'reading.workspace': '阅读文章，点任意词看释义，保存想学的词',
    'listening.library': '选择一个视频或音频来听和练习',
    'listening.workspace': '逐句听，配有字幕、释义和重播',
    'listening.dictation': '写下你听到的内容，再逐词核对',
    'speaking.library': '选择口语或听力练习：发音、听写、自由说',
    'speaking.workspace': '听示范句，录下自己的发音，看看哪些音要改',
    'speaking.free_talk': '围绕一个话题自由说，并获得对你所说内容的反馈',
    'speaking.word_detail': '查看你这次录音里每个词与示范的对比',
    'speaking.compare': '逐句对比你的录音和示范',
    'writing.workspace': '按题目写作，并获得指出最重要修改的点评',
    'writing.review': '阅读你的作文点评，先改第一个问题',
    'writing.revision': '对比你作文的两个版本，看看哪里进步了',
    'vocabulary.my_language': '你保存的词和内容，以及到期需要复习的部分',
    'vocabulary.word': '一个词：释义、发音、例句以及你在哪里遇到它',
    'vocabulary.review_due': '回忆到期的词，再标出每个词你记得多好',
    'grammar.catalog': '按级别浏览语法点，打开一个来学习',
    'grammar.point': '通过例句学习一个语法点，然后自己试着用',
    'progress': '查看你练了什么、随时间的成绩以及需要加强的地方',
    'preferences': '设置语言、复习上限、主题和隐私',
    'preferences.agent_memory': '查看并删除 Orena 记住的有关你学习的内容',
  },
});

/* Wire locale code (as §6.2's JSON shape names it) → this copy layer's own pack key. */
const WIRE_LOCALES = Object.freeze({ en: 'en', vi: 'vi', 'zh-CN': 'zh' });

/* Every §6.1 id's `{ name, purpose? }`, read from the raw copy packs - never the live language
   state (copy/index.js's `current`), so this is the same regardless of what the UI happens to be
   showing when it runs. Throws if a §6.1 id has no route, or a route's title is missing a
   language - both are a copy or intents.js defect to fix, never a reason to publish a gap. */
export function buildSurfaces() {
  const tables = registeredCopy();
  const shell = tables.get('shell');
  const purpose = tables.get('surfaces-purpose');
  if (!shell) throw new Error('copy/surfaces.js: copy/shell.js has not registered its table');
  const surfaces = {};
  for (const id of Object.keys(SURFACES)) {
    const route = byId(intentRoute(id));
    if (!route) throw new Error(`copy/surfaces.js: §6.1 id "${id}" has no route (agent/intents.js)`);
    const name = {};
    for (const [wire, packKey] of Object.entries(WIRE_LOCALES)) {
      const text = shell.packs[packKey]?.[route.crumb];
      if (!text) throw new Error(`copy/surfaces.js: no ${wire} title for "${id}" (copy/shell.js "${route.crumb}")`);
      name[wire] = text;
    }
    const entry = { name };
    if (purpose) {
      const line = {};
      for (const [wire, packKey] of Object.entries(WIRE_LOCALES)) {
        const text = purpose.packs[packKey]?.[id];
        if (text) line[wire] = text;
      }
      if (Object.keys(line).length) entry.purpose = line;
    }
    surfaces[id] = entry;
  }
  return surfaces;
}
