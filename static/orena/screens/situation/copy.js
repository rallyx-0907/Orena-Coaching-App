/* Frame 31 "Situation Reaction" (pinned design, focus route 'situation'). Interface layer for
   labels/buttons/states; `subtitle` is functional, spec-required copy (E2 §4 "Copy audit": the
   header line states the mode's defining constraint, non-decorative) so it stays too - nothing here
   is a slogan or celebration line. Titles already in copy/shell.js are reused: `situationReaction`,
   `back`. Rule 40: "Try another context", the delivery-mode pill and the Intent/Clarity result
   grid are dropped (model.js's header comment) - no real content or measurement behind any of
   them. Rule 43: the frame draws no "Your answer" label and no empty-answer notice (an empty
   Submit simply does nothing), so neither is written. */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'subtitle', 'answerPlaceholder', 'submitCta', 'micIdle', 'micRecording',
  'improvement', 'naturalAlternative', 'retry', 'newScenario', 'finish',
  'transcribing', 'gettingFeedback', 'serviceError',
];

export const t = defineCopy('situation', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    subtitle: 'No model sentence · say it your way · scenario {index} of {total}',
    answerPlaceholder: 'Speak (mic) or type your reaction…', submitCta: 'Submit',
    micIdle: 'Speak', micRecording: 'Tap to finish',
    improvement: 'One useful improvement', naturalAlternative: 'Natural alternative',
    retry: 'Retry', newScenario: 'New scenario', finish: 'Finish',
    transcribing: 'Getting what you said…', gettingFeedback: 'Getting feedback…', serviceError: 'Feedback is not available right now.',
  },
  vi: {
    subtitle: 'Không có câu mẫu · nói theo cách của bạn · tình huống {index}/{total}',
    answerPlaceholder: 'Nói (micro) hoặc gõ phản ứng của bạn…', submitCta: 'Gửi',
    micIdle: 'Nói', micRecording: 'Chạm để kết thúc',
    improvement: 'Một điều nên cải thiện', naturalAlternative: 'Cách nói tự nhiên hơn',
    retry: 'Thử lại', newScenario: 'Tình huống mới', finish: 'Hoàn tất',
    transcribing: 'Đang lấy nội dung bạn nói…', gettingFeedback: 'Đang nhận xét…', serviceError: 'Hiện chưa thể nhận xét được.',
  },
  zh: {
    subtitle: '没有例句 · 用你自己的方式说 · 情境 {index}/{total}',
    answerPlaceholder: '说出（麦克风）或输入你的反应…', submitCta: '提交',
    micIdle: '说', micRecording: '点击结束',
    improvement: '一个可以改进的地方', naturalAlternative: '更自然的说法',
    retry: '重试', newScenario: '换个情境', finish: '完成',
    transcribing: '正在获取你说的内容…', gettingFeedback: '正在获取反馈…', serviceError: '暂时无法获取反馈。',
  },
});
