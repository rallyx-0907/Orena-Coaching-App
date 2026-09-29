/* Frame 30 "Conversation" (pinned design, focus route 'conv'). Interface layer throughout - the
   partner's own reply text is real, generated learning-language content, not chrome. Titles
   already in copy/shell.js (shellCopy) are reused instead of repeated here: `conversation`, `back`.
   Rule 40/44: the frame's own B1/B2/C1 difficulty picker is dropped (cosmetic even in the source,
   model.js's header comment) rather than reproduced as an inert control, and so is its setup-state
   header line ("Pick a scenario · partner replies naturally, coaching is separate": an explanation
   of controls the screen already shows, rule 50). The frame draws only a fixed Scenario picker (a
   2-column grid of title + role cards) - no free-text "describe your own situation" field; real
   content (`content/voice-invitations.js`'s 3 items, each carrying the `cue` line the card's role
   line needs) stands in for the frame's 4 fixed scripted scenarios. The frame's "…" thinking
   bubble carries no word; only an accessible name (`thinking`) is written. */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'situationLabel', 'startCta',
  'thinking', 'transcribing', 'ended', 'turns', 'turnsLabel', 'howDidItLand', 'coachingWorking', 'coachingUnavailable',
  'carried', 'landed', 'anotherWay', 'nextAttempt', 'replyPlaceholder', 'send', 'mic', 'micStop', 'endConversation',
  'newScenario', 'finish', 'replyFailed', 'retryCta',
  'judge_natural', 'judge_possible_but_unnatural', 'judge_contextually_inappropriate',
  'judge_wrong_for_intended_meaning', 'judge_register_mismatch', 'judge_uncommon_but_legitimate',
  'judge_grammatically_impossible',
];

export const t = defineCopy('conversation', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    situationLabel: 'Scenario',
    startCta: 'Start conversation',
    thinking: 'Thinking…', transcribing: 'Getting what you said…', ended: 'Conversation complete', turns_one: '{n} turn', turns_other: '{n} turns', turnsLabel: 'Turns',
    howDidItLand: 'How did that land?', coachingWorking: 'Getting feedback…', coachingUnavailable: 'Feedback is not available right now.',
    carried: 'What carried', landed: 'What would land differently', anotherWay: 'Another way to say it', nextAttempt: 'Next attempt',
    replyPlaceholder: 'Your turn… type, or tap the mic', send: 'Send', mic: 'Speak', micStop: 'Tap to finish', endConversation: 'End',
    newScenario: 'New scenario', finish: 'Finish',
    replyFailed: 'The reply didn’t come through.', retryCta: 'Retry',
    judge_natural: 'Natural', judge_possible_but_unnatural: 'Possible, but unnatural', judge_contextually_inappropriate: 'Doesn’t fit here',
    judge_wrong_for_intended_meaning: 'Not what you meant', judge_register_mismatch: 'Wrong register',
    judge_uncommon_but_legitimate: 'Uncommon, but correct', judge_grammatically_impossible: 'Not grammatical',
  },
  vi: {
    situationLabel: 'Tình huống',
    startCta: 'Bắt đầu hội thoại',
    thinking: 'Đang suy nghĩ…', transcribing: 'Đang lấy nội dung bạn nói…', ended: 'Hội thoại đã hoàn tất', turns_other: '{n} lượt', turnsLabel: 'Lượt',
    howDidItLand: 'Câu đó nghe thế nào?', coachingWorking: 'Đang nhận xét…', coachingUnavailable: 'Hiện chưa thể nhận xét được.',
    carried: 'Điều đã truyền tải tốt', landed: 'Điều có thể nói khác đi', anotherWay: 'Một cách nói khác', nextAttempt: 'Lần thử tiếp theo',
    replyPlaceholder: 'Đến lượt bạn… gõ hoặc chạm micro', send: 'Gửi', mic: 'Nói', micStop: 'Chạm để kết thúc', endConversation: 'Kết thúc',
    newScenario: 'Tình huống mới', finish: 'Hoàn tất',
    replyFailed: 'Câu trả lời chưa gửi đến được.', retryCta: 'Thử lại',
    judge_natural: 'Tự nhiên', judge_possible_but_unnatural: 'Được, nhưng không tự nhiên', judge_contextually_inappropriate: 'Không hợp ngữ cảnh',
    judge_wrong_for_intended_meaning: 'Không đúng ý bạn muốn nói', judge_register_mismatch: 'Sai văn phong',
    judge_uncommon_but_legitimate: 'Hiếm dùng, nhưng đúng', judge_grammatically_impossible: 'Sai ngữ pháp',
  },
  zh: {
    situationLabel: '情境',
    startCta: '开始对话',
    thinking: '正在思考…', transcribing: '正在获取你说的内容…', ended: '对话已完成', turns_other: '{n} 轮', turnsLabel: '轮数',
    howDidItLand: '这句话听起来怎么样？', coachingWorking: '正在获取反馈…', coachingUnavailable: '暂时无法获取反馈。',
    carried: '表达清楚的部分', landed: '可以换种说法的部分', anotherWay: '另一种说法', nextAttempt: '下一次可以试试',
    replyPlaceholder: '轮到你了… 输入，或点按麦克风', send: '发送', mic: '说话', micStop: '点击结束', endConversation: '结束',
    newScenario: '换个情境', finish: '完成',
    replyFailed: '回复没有发送成功。', retryCta: '重试',
    judge_natural: '很自然', judge_possible_but_unnatural: '可以，但不自然', judge_contextually_inappropriate: '不太符合语境',
    judge_wrong_for_intended_meaning: '不是你想表达的意思', judge_register_mismatch: '语域不对',
    judge_uncommon_but_legitimate: '少见，但正确', judge_grammatically_impossible: '语法不对',
  },
});
