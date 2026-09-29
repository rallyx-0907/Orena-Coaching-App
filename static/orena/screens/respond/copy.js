/* Respond to Content copy (frame 45, D-091, Design Contract rule 50). `respondToContent`/`back`/
   `close` already live in copy/shell.js and are reused from there.

   Rule-50 review (SCRATCH/reports/listening.md): the frame's subtitle suffix ("source stays linked
   to your writing") states a real behaviour - the source is recorded with the essay (the evaluate
   request's `writing_context.journal_context`) - and E3 §4's own audit keeps it; kept here.
   The frame's "Write 60-150 words..." placeholder names a range nothing in the backend enforces,
   so the placeholder says only what to do. The frame's prompts name "this video" / "this article";
   a lesson may be audio and a source may be a book chapter or the learner's own text, so the
   media variant says "what you heard" and the reading variant "this text".

   `usesSource` labels a tile no endpoint measures (`POST /api/evaluate` grades grammar,
   vocabulary, coherence, task achievement, naturalness - nothing about the source), so it renders
   0 in its component (rule 40). */
import { defineCopy } from '../../copy/index.js';

const layers = {
  kindOpinion: 'interface', kindSummary: 'interface', kindReaction: 'interface', kindContinuation: 'interface',
  promptOpinionMedia: 'support', promptOpinionReading: 'support',
  promptSummaryMedia: 'support', promptSummaryReading: 'support',
  promptReactionMedia: 'support', promptReactionReading: 'support',
  promptContinuationMedia: 'support', promptContinuationReading: 'support',
  subtitleSuffix: 'support', sourceLabel: 'interface',
  sourceKindVideo: 'interface', sourceKindAudio: 'interface', sourceKindArticle: 'interface', sourceKindBook: 'interface', sourceKindText: 'interface',
  placeholder: 'support', wordsLabel: 'interface', getFeedback: 'interface',
  wordsTile: 'interface', usesSource: 'interface', fixesLabel: 'interface', nextStepLabel: 'interface',
  feedbackError: 'support', revise: 'interface', askOrenaWhy: 'interface', openSource: 'interface', done: 'interface',
};

export const t = defineCopy('respond', {
  layers,
  en: {
    kindOpinion: 'Opinion', kindSummary: 'Summary', kindReaction: 'Reaction', kindContinuation: 'Continuation',
    promptOpinionMedia: 'What did you think of what you heard?', promptOpinionReading: 'What did you think of this text?',
    promptSummaryMedia: 'Summarise what you heard in your own words.', promptSummaryReading: 'Summarise this text in your own words.',
    promptReactionMedia: 'React to one thing that surprised you.', promptReactionReading: 'React to one thing that surprised you in this text.',
    promptContinuationMedia: 'What do you think happens next?', promptContinuationReading: 'What do you think happens next, after this text?',
    subtitleSuffix: 'source stays linked to your writing', sourceLabel: 'Source · {kind}',
    sourceKindVideo: 'Video transcript', sourceKindAudio: 'Audio transcript', sourceKindArticle: 'Article', sourceKindBook: 'Book', sourceKindText: 'Text',
    placeholder: 'Write your response…', wordsLabel_one: 'word', wordsLabel_other: 'words', getFeedback: 'Get feedback',
    wordsTile: 'Words', usesSource: 'Uses the source', fixesLabel: 'Fixes', nextStepLabel: 'Next step',
    feedbackError: "Feedback isn't available right now.",
    revise: 'Revise', askOrenaWhy: 'Ask Orena why', openSource: 'Open source', done: 'Done',
  },
  vi: {
    kindOpinion: 'Ý kiến', kindSummary: 'Tóm tắt', kindReaction: 'Phản ứng', kindContinuation: 'Tiếp nối',
    promptOpinionMedia: 'Bạn nghĩ gì về những gì vừa nghe?', promptOpinionReading: 'Bạn nghĩ gì về văn bản này?',
    promptSummaryMedia: 'Tóm tắt những gì bạn vừa nghe bằng lời của bạn.', promptSummaryReading: 'Tóm tắt văn bản này bằng lời của bạn.',
    promptReactionMedia: 'Nêu phản ứng của bạn về một điều khiến bạn bất ngờ.', promptReactionReading: 'Nêu phản ứng của bạn về một điều khiến bạn bất ngờ trong văn bản này.',
    promptContinuationMedia: 'Theo bạn, điều gì sẽ xảy ra tiếp theo?', promptContinuationReading: 'Theo bạn, điều gì sẽ xảy ra tiếp theo, sau văn bản này?',
    subtitleSuffix: 'nguồn vẫn được liên kết với bài viết của bạn', sourceLabel: 'Nguồn · {kind}',
    sourceKindVideo: 'Bản ghi video', sourceKindAudio: 'Bản ghi âm thanh', sourceKindArticle: 'Bài viết', sourceKindBook: 'Sách', sourceKindText: 'Văn bản',
    placeholder: 'Viết phản hồi của bạn…', wordsLabel_other: 'từ', getFeedback: 'Nhận xét',
    wordsTile: 'Số từ', usesSource: 'Dùng nguồn', fixesLabel: 'Điểm cần sửa', nextStepLabel: 'Bước tiếp theo',
    feedbackError: 'Hiện chưa dùng được tính năng nhận xét.',
    revise: 'Sửa lại', askOrenaWhy: 'Hỏi Orena vì sao', openSource: 'Xem nguồn', done: 'Xong',
  },
  zh: {
    kindOpinion: '观点', kindSummary: '概括', kindReaction: '感想', kindContinuation: '续写',
    promptOpinionMedia: '你对刚才听到的内容有什么看法？', promptOpinionReading: '你对这段文字有什么看法？',
    promptSummaryMedia: '用你自己的话概括刚才听到的内容。', promptSummaryReading: '用你自己的话概括这段文字。',
    promptReactionMedia: '说说让你意外的一点。', promptReactionReading: '说说这段文字里让你意外的一点。',
    promptContinuationMedia: '你觉得接下来会发生什么？', promptContinuationReading: '这段文字之后，你觉得接下来会发生什么？',
    subtitleSuffix: '来源会一直与你的写作关联', sourceLabel: '来源 · {kind}',
    sourceKindVideo: '视频文字稿', sourceKindAudio: '音频文字稿', sourceKindArticle: '文章', sourceKindBook: '书籍', sourceKindText: '文本',
    placeholder: '写下你的回应…', wordsLabel_other: '字', getFeedback: '获取点评',
    wordsTile: '字数', usesSource: '用到来源', fixesLabel: '待修改', nextStepLabel: '下一步',
    feedbackError: '点评功能暂时不可用。',
    revise: '修改', askOrenaWhy: '问问 Orena 为什么', openSource: '查看来源', done: '完成',
  },
});
