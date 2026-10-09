/* Feedback: the words of the frame, all chrome (interface language, D-079). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'title', 'rateTitle', 'rateSub', 'rate0', 'rate1', 'rate2', 'rate3', 'rate4', 'rate5', 'starAria',
  'aboutTitle', 'area_reading', 'area_listening', 'area_speaking', 'area_writing', 'area_vocabulary', 'area_orena', 'area_bugs',
  'placeholder', 'send', 'sendUnavailable', 'yourFeedback', 'reviewsCount',
];

export const t = defineCopy('feedback', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    title: 'Feedback', rateTitle: 'Rate your experience', rateSub: 'The Orena team reads every review.',
    rate0: 'Tap a star to rate', rate1: 'Needs a lot of work', rate2: 'Not great', rate3: 'Okay', rate4: 'Good', rate5: 'Love it', starAria: '{n} stars',
    aboutTitle: 'What is this about?',
    area_reading: 'Reading', area_listening: 'Listening', area_speaking: 'Speaking', area_writing: 'Writing', area_vocabulary: 'Vocabulary', area_orena: 'Orena Intelligence', area_bugs: 'Speed & bugs',
    placeholder: 'What did you like, and what should we improve?', send: 'Send feedback', sendUnavailable: 'Sending feedback is not available yet',
    yourFeedback: 'Your feedback', reviewsCount_one: '{n} review', reviewsCount_other: '{n} reviews',
  },
  vi: {
    title: 'Góp ý', rateTitle: 'Đánh giá trải nghiệm của bạn', rateSub: 'Đội ngũ Orena đọc mọi đánh giá.',
    rate0: 'Chạm vào sao để đánh giá', rate1: 'Cần cải thiện nhiều', rate2: 'Chưa tốt', rate3: 'Tạm được', rate4: 'Tốt', rate5: 'Rất thích', starAria: '{n} sao',
    aboutTitle: 'Bạn muốn góp ý về điều gì?',
    area_reading: 'Đọc', area_listening: 'Nghe', area_speaking: 'Nói', area_writing: 'Viết', area_vocabulary: 'Từ vựng', area_orena: 'Orena Intelligence', area_bugs: 'Tốc độ & lỗi',
    placeholder: 'Bạn thích điều gì và chúng tôi nên cải thiện điều gì?', send: 'Gửi góp ý', sendUnavailable: 'Chưa thể gửi góp ý',
    yourFeedback: 'Góp ý của bạn', reviewsCount_one: '{n} đánh giá', reviewsCount_other: '{n} đánh giá',
  },
  zh: {
    title: '反馈', rateTitle: '为你的体验打分', rateSub: 'Orena 团队会阅读每一条评价。',
    rate0: '点按星星来打分', rate1: '需要大幅改进', rate2: '不太好', rate3: '一般', rate4: '不错', rate5: '很喜欢', starAria: '{n} 星',
    aboutTitle: '你想反馈哪方面？',
    area_reading: '阅读', area_listening: '听力', area_speaking: '口语', area_writing: '写作', area_vocabulary: '词汇', area_orena: 'Orena Intelligence', area_bugs: '速度与问题',
    placeholder: '你喜欢什么？我们还应改进什么？', send: '发送反馈', sendUnavailable: '暂时无法发送反馈',
    yourFeedback: '你的反馈', reviewsCount_one: '{n} 条评价', reviewsCount_other: '{n} 条评价',
  },
});
