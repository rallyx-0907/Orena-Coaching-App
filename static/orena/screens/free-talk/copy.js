/* Frame 29 "Free Talk" (pinned design, focus route 'freetalk'). Interface layer for every label,
   button and state line; `support` for the two lines that explain an empty result. Titles already in
   copy/shell.js (shellCopy) are reused instead of repeated here: `freeTalk`, `back`. Rule 50: the
   frame's own "Demo ASR · edit to what you'd actually say" pill and "simulated" on the mic line are
   prototype self-disclosure and are not carried, nor is the trailing "Nice." on the empty-fixes
   line (E2 §2 "Copy audit"). The frame's four step labels (its header subtitle) name the learner's
   real position, so they stay. */
import { defineCopy } from '../../copy/index.js';

const INTERFACE_KEYS = [
  'stepSetup', 'stepRecording', 'stepTranscript', 'stepResult',
  'topicLabel', 'topicPlaceholder', 'durationLabel', 'phrasesLabel', 'startCta', 'pickTopicFirst',
  'micOn', 'tapToFinish', 'transcriptTitle', 'transcriptPlain', 'recordAgain', 'getFeedback',
  'statWords', 'statPace', 'statPaceUnit', 'statLinking',
  'strengthsTitle', 'fixesTitle', 'retryTitle', 'talkAgain', 'askAboutThis', 'finish',
  'transcribing', 'gettingFeedback', 'serviceError',
  'minutes', 'headlineNone', 'headlineOne', 'headlineMany',
];
const SUPPORT_KEYS = ['strengthsEmpty', 'fixesEmpty'];

export const t = defineCopy('free-talk', {
  layers: {
    ...Object.fromEntries(INTERFACE_KEYS.map((key) => [key, 'interface'])),
    ...Object.fromEntries(SUPPORT_KEYS.map((key) => [key, 'support'])),
  },
  en: {
    stepSetup: 'Set up · topic and duration', stepRecording: 'Recording', stepTranscript: 'Check the transcript', stepResult: 'Feedback',
    topicLabel: 'Topic', topicPlaceholder: 'What do you want to talk about?', durationLabel: 'Duration',
    phrasesLabel: 'Useful phrases · from your library',
    startCta: 'Start speaking', pickTopicFirst: 'Pick a topic first',
    micOn: 'Mic on', tapToFinish: 'Tap to finish',
    transcriptTitle: 'Transcript · {time} spoken', transcriptPlain: 'Transcript', recordAgain: 'Record again', getFeedback: 'Get feedback',
    statWords: 'Words', statPace: 'Pace', statPaceUnit: 'wpm', statLinking: 'Linking',
    strengthsTitle: 'Strengths', strengthsEmpty: 'Say a little more next time so there is more to point out.',
    fixesTitle: 'Fixes · max 3', fixesEmpty: 'Nothing here needs fixing.',
    retryTitle: 'Retry this sentence', talkAgain: 'Talk again', askAboutThis: 'Ask about this', finish: 'Finish',
    transcribing: 'Getting what you said…', gettingFeedback: 'Getting feedback…',
    serviceError: 'Feedback is not available right now.',
    minutes_one: '{n} min', minutes_other: '{n} min',
    headlineNone: 'Nothing flagged - nice and clear.', headlineOne: '1 thing worth fixing.',
    headlineMany_one: '{n} thing worth fixing.', headlineMany_other: '{n} things worth fixing.',
  },
  vi: {
    stepSetup: 'Thiết lập · chủ đề và thời lượng', stepRecording: 'Đang ghi âm', stepTranscript: 'Kiểm tra bản ghi lời nói', stepResult: 'Nhận xét',
    topicLabel: 'Chủ đề', topicPlaceholder: 'Bạn muốn nói về điều gì?', durationLabel: 'Thời lượng',
    phrasesLabel: 'Cụm từ hữu ích · từ thư viện của bạn',
    startCta: 'Bắt đầu nói', pickTopicFirst: 'Hãy chọn một chủ đề trước',
    micOn: 'Đang bật micro', tapToFinish: 'Chạm để kết thúc',
    transcriptTitle: 'Bản ghi · đã nói {time}', transcriptPlain: 'Bản ghi', recordAgain: 'Ghi âm lại', getFeedback: 'Nhận xét',
    statWords: 'Số từ', statPace: 'Tốc độ', statPaceUnit: 'từ/phút', statLinking: 'Liên kết câu',
    strengthsTitle: 'Điểm mạnh', strengthsEmpty: 'Lần sau hãy nói thêm một chút để có thêm điều để nhận xét.',
    fixesTitle: 'Cần sửa · tối đa 3', fixesEmpty: 'Không có gì cần sửa ở đây.',
    retryTitle: 'Thử nói lại câu này', talkAgain: 'Nói lại', askAboutThis: 'Hỏi về điều này', finish: 'Hoàn tất',
    transcribing: 'Đang lấy nội dung bạn nói…', gettingFeedback: 'Đang nhận xét…',
    serviceError: 'Hiện chưa thể nhận xét được.',
    minutes_other: '{n} phút',
    headlineNone: 'Không có gì cần sửa - rất rõ ràng.', headlineOne: 'Có 1 điều đáng sửa.',
    headlineMany_other: 'Có {n} điều đáng sửa.',
  },
  zh: {
    stepSetup: '设置 · 主题和时长', stepRecording: '录音中', stepTranscript: '检查文字稿', stepResult: '反馈',
    topicLabel: '主题', topicPlaceholder: '你想聊些什么？', durationLabel: '时长',
    phrasesLabel: '常用表达 · 来自你的词库',
    startCta: '开始说', pickTopicFirst: '先选一个主题',
    micOn: '麦克风已开启', tapToFinish: '点击结束',
    transcriptTitle: '文字稿 · 已说 {time}', transcriptPlain: '文字稿', recordAgain: '重新录音', getFeedback: '获取反馈',
    statWords: '字数', statPace: '语速', statPaceUnit: '字/分钟', statLinking: '衔接',
    strengthsTitle: '优点', strengthsEmpty: '下次多说一点，就有更多可以点评的内容。',
    fixesTitle: '待改进 · 最多 3 条', fixesEmpty: '这里没有需要修改的地方。',
    retryTitle: '再说一遍这句话', talkAgain: '再说一次', askAboutThis: '问问这个', finish: '完成',
    transcribing: '正在获取你说的内容…', gettingFeedback: '正在获取反馈…',
    serviceError: '暂时无法获取反馈。',
    minutes_other: '{n} 分钟',
    headlineNone: '没有需要改进的地方 - 很清楚。', headlineOne: '有 1 处值得改进。',
    headlineMany_other: '有 {n} 处值得改进。',
  },
});
