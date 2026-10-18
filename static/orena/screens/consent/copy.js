/* Words of the two consent sheets (D-229 clause 5, D-233): the one-time "I agree" for an account with no consent record,
   and the just-in-time voice question at the first use of the microphone. Both are chrome and a system note, so every
   key follows the interface language (the mic sheet's own rule, D-139 HD-14). Short by rule 50; no design sample copy. */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'consentTitle', 'consentBody', 'consentTerms', 'consentPrivacy', 'consentAgree',
  'voiceTitle', 'voiceBody', 'voiceAllow', 'voiceLater', 'voiceSaveError',
];

export const t = defineCopy('consent', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    consentTitle: 'Before you continue',
    consentBody: 'By continuing, you agree to the Terms of Service and the Privacy Policy.',
    consentTerms: 'Terms of Service', consentPrivacy: 'Privacy Policy', consentAgree: 'I agree',
    voiceTitle: 'Let Orena hear your voice?',
    voiceBody: 'To practise speaking, your voice is recorded and sent to an AI service for feedback. You can turn this off any time in Settings.',
    voiceAllow: 'Allow', voiceLater: 'Not now', voiceSaveError: 'Couldn’t save that — try again',
  },
  vi: {
    consentTitle: 'Trước khi tiếp tục',
    consentBody: 'Bằng việc tiếp tục, bạn đồng ý với Điều khoản sử dụng và Chính sách quyền riêng tư.',
    consentTerms: 'Điều khoản sử dụng', consentPrivacy: 'Chính sách quyền riêng tư', consentAgree: 'Đồng ý',
    voiceTitle: 'Cho phép Orena nghe giọng bạn?',
    voiceBody: 'Để luyện nói, giọng của bạn được ghi lại và gửi tới dịch vụ AI để nhận xét. Bạn có thể tắt bất cứ lúc nào trong Cài đặt.',
    voiceAllow: 'Cho phép', voiceLater: 'Để sau', voiceSaveError: 'Chưa lưu được — hãy thử lại',
  },
  zh: {
    consentTitle: '继续之前',
    consentBody: '继续即表示你同意服务条款和隐私政策。',
    consentTerms: '服务条款', consentPrivacy: '隐私政策', consentAgree: '我同意',
    voiceTitle: '允许 Orena 听你的声音吗？',
    voiceBody: '为了练习口语，你的声音会被录下并发送到 AI 服务以获取点评。你可以随时在设置中关闭。',
    voiceAllow: '允许', voiceLater: '暂不', voiceSaveError: '没能保存 — 请重试',
  },
});
