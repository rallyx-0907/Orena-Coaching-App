/* React / Reuse copy (frame 33, D-091, Design Contract rule 50). `back`/`retry`/`reactReuse` and the
   other shared labels already live in copy/shell.js and are reused from there.

   Rule-50 drops (SCRATCH/reports/listening.md): the Listen step's intro line ("Audio first. Listen
   as many times as you like, then continue.") explains an obvious play button, as E3's own copy
   audit says, and the mic's "simulated mic" note is a prototype internal - both dropped. The
   frame's "Useful phrase" note is the prototype's own gloss text; a catalogue phrase carries none,
   so only the phrase is shown, and no callout at all when the line has no catalogued phrase.

   `intentAchieved` labels a tile drawn only when the coaching returns a real verdict (S-26); without one
   the tile is not drawn (rule 40, HX-2). */
import { defineCopy } from '../../copy/index.js';

const layers = {
  stepListen: 'interface', stepUnderstand: 'interface', stepReveal: 'interface', stepContext: 'interface', stepResult: 'interface',
  segmentNo: 'interface', continueLabel: 'interface', question: 'support', reveal: 'interface', transcriptLabel: 'interface',
  usefulPhrase: 'interface', newContextChip: 'interface',
  promptWithPhrase: 'support', promptWithPhrase2: 'support', promptGeneric: 'support', promptGeneric2: 'support',
  placeholderAnswer: 'support', checkLabel: 'interface', speak: 'interface', listening: 'interface',
  intent_yes: 'interface', intent_partly: 'interface', intent_no: 'interface',
  intentAchieved: 'interface', phraseReused: 'interface', yes: 'interface', notThisTime: 'interface',
  carriedLabel: 'interface', landedLabel: 'interface', anotherWayLabel: 'interface', nextAttemptLabel: 'interface',
  notPrepared: 'interface', coachingError: 'interface',
  newContextAgain: 'interface', finishLabel: 'interface',
  playLabel: 'interface', replayLabel: 'interface', yourAnswer: 'interface', sentenceLabel: 'interface', pauseLabel: 'interface', correctLabel: 'interface', incorrectLabel: 'support',
};

export const t = defineCopy('react', {
  layers,
  en: {
    stepListen: 'Listen', stepUnderstand: 'Understand', stepReveal: 'Reveal', stepContext: 'New context', stepResult: 'Result',
    segmentNo: 'segment {n}', continueLabel: "I've listened", question: 'What does this line mean?', reveal: 'Reveal', transcriptLabel: 'Transcript',
    usefulPhrase: 'Useful phrase',
    newContextChip: 'New context',
    promptWithPhrase: 'Use "{phrase}" in a new sentence of your own.',
    promptWithPhrase2: 'Say "{phrase}" again, this time about something that happened to you.',
    promptGeneric: 'Use something from this line in a new sentence of your own.',
    promptGeneric2: 'Say what this line says again, this time about something that happened to you.',
    placeholderAnswer: 'One sentence…', checkLabel: 'Check', speak: 'Speak', listening: 'Listening…',
    intent_yes: 'Yes', intent_partly: 'Partly', intent_no: 'No',
    intentAchieved: 'Intent achieved?', phraseReused: 'Phrase reused?', yes: 'Yes', notThisTime: 'Not this time',
    carriedLabel: 'What carried', landedLabel: 'What would land differently', anotherWayLabel: 'One natural alternative', nextAttemptLabel: 'Try next time',
    notPrepared: 'Coaching is not prepared for this response yet.',
    coachingError: "Coaching isn't available right now.",
    newContextAgain: 'New context', finishLabel: 'Finish',
    playLabel: 'Play', replayLabel: 'Play the line again', yourAnswer: 'Your answer', sentenceLabel: 'The line', pauseLabel: 'Pause', correctLabel: 'Correct', incorrectLabel: 'Not quite - the correct meaning is highlighted',
  },
  vi: {
    stepListen: 'Nghe', stepUnderstand: 'Hiểu', stepReveal: 'Xem lại', stepContext: 'Ngữ cảnh mới', stepResult: 'Kết quả',
    segmentNo: 'câu {n}', continueLabel: 'Mình đã nghe', question: 'Câu này nghĩa là gì?', reveal: 'Xem bản ghi', transcriptLabel: 'Bản ghi',
    usefulPhrase: 'Cụm hữu ích',
    newContextChip: 'Ngữ cảnh mới',
    promptWithPhrase: 'Dùng "{phrase}" trong một câu mới của riêng bạn.',
    promptWithPhrase2: 'Nói lại "{phrase}", lần này về một chuyện đã xảy ra với bạn.',
    promptGeneric: 'Dùng một phần của câu này trong một câu mới của riêng bạn.',
    promptGeneric2: 'Nói lại ý của câu này, lần này về một chuyện đã xảy ra với bạn.',
    placeholderAnswer: 'Một câu…', checkLabel: 'Kiểm tra', speak: 'Nói', listening: 'Đang nghe…',
    intent_yes: 'Có', intent_partly: 'Một phần', intent_no: 'Chưa',
    intentAchieved: 'Đã đạt ý định?', phraseReused: 'Đã dùng lại cụm?', yes: 'Có', notThisTime: 'Lần này chưa',
    carriedLabel: 'Điều đã truyền tải được', landedLabel: 'Điều sẽ được hiểu khác đi', anotherWayLabel: 'Một cách nói tự nhiên khác', nextAttemptLabel: 'Lần sau hãy thử',
    notPrepared: 'Chưa có nhận xét cho câu trả lời này.',
    coachingError: 'Hiện chưa dùng được tính năng nhận xét.',
    newContextAgain: 'Ngữ cảnh mới', finishLabel: 'Hoàn tất',
    playLabel: 'Phát', replayLabel: 'Nghe lại câu này', yourAnswer: 'Câu bạn chọn', sentenceLabel: 'Câu gốc', pauseLabel: 'Tạm dừng', correctLabel: 'Đúng rồi', incorrectLabel: 'Chưa đúng - nghĩa đúng được tô sáng',
  },
  zh: {
    stepListen: '听', stepUnderstand: '理解', stepReveal: '查看', stepContext: '新语境', stepResult: '结果',
    segmentNo: '第 {n} 句', continueLabel: '我听完了', question: '这句话是什么意思？', reveal: '查看文字稿', transcriptLabel: '文字稿',
    usefulPhrase: '实用短语',
    newContextChip: '新语境',
    promptWithPhrase: '在一个新句子里用一下"{phrase}"。',
    promptWithPhrase2: '再说一次"{phrase}"，这次说说发生在你身上的一件事。',
    promptGeneric: '在一个新句子里用一下这句话中的内容。',
    promptGeneric2: '再说一次这句话的意思，这次说说发生在你身上的一件事。',
    placeholderAnswer: '一句话…', checkLabel: '检查', speak: '说话', listening: '正在听…',
    intent_yes: '是', intent_partly: '部分达到', intent_no: '没有',
    intentAchieved: '达成意图了吗？', phraseReused: '用上短语了吗？', yes: '是', notThisTime: '这次没有',
    carriedLabel: '传达到的部分', landedLabel: '可能被理解不同的部分', anotherWayLabel: '另一种自然的说法', nextAttemptLabel: '下次可以试试',
    notPrepared: '这次回答还没有准备好点评。',
    coachingError: '点评功能暂时不可用。',
    newContextAgain: '新语境', finishLabel: '完成',
    playLabel: '播放', replayLabel: '再听一遍这句话', yourAnswer: '你的选择', sentenceLabel: '原句', pauseLabel: '暂停', correctLabel: '答对了', incorrectLabel: '还不太对 - 正确的意思已高亮',
  },
});
