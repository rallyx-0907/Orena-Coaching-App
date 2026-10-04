/* Attempt History's own words (D-079, rules 9, 26, 50). All copy here is a field label or the
   spec-required privacy note - D5's own copy audit for this frame found nothing decorative to
   drop. */
import { defineCopy } from '../../copy/index.js';

const LAYERS = {
  title: 'interface', statAttempts: 'interface', statBest: 'interface', statChange: 'interface',
  attemptLabel: 'interface', bestBadge: 'interface', currentBadge: 'interface', metaLine: 'support',
  privacyNoteSession: 'support', privacyNoteKept: 'support', historyScope: 'support',
};

export const t = defineCopy('attempts', {
  layers: LAYERS,
  en: {
    title: 'Attempt history', statAttempts: 'Attempts', statBest: 'Best', statChange: 'Change',
    attemptLabel: 'Attempt {n}', bestBadge: 'Best', currentBadge: 'Current', metaLine: '{when} · accuracy {acc} · fluency {flu}',
    privacyNoteSession: 'Recordings stay in this browser tab and are gone when you close it; scores are saved without audio.',
    historyScope: 'Up to 50 recent server attempts. Best and change use the verified attempts shown here.',
    privacyNoteKept: 'The last five recordings of each line stay on this device, never uploaded; scores are saved without audio.',
  },
  vi: {
    title: 'Các lần thử', statAttempts: 'Số lần', statBest: 'Tốt nhất', statChange: 'Thay đổi',
    attemptLabel: 'Lần {n}', bestBadge: 'Tốt nhất', currentBadge: 'Hiện tại', metaLine: '{when} · độ chính xác {acc} · độ trôi chảy {flu}',
    privacyNoteSession: 'Bản ghi âm chỉ nằm trong thẻ trình duyệt này và mất khi bạn đóng thẻ; điểm số được lưu mà không có âm thanh.',
    historyScope: 'Tối đa 50 lần thử gần đây từ máy chủ. Điểm tốt nhất và thay đổi chỉ tính các lần thử được xác minh đang hiển thị.',
    privacyNoteKept: 'Năm bản ghi gần nhất của mỗi câu được giữ trên thiết bị này, không tải lên đâu cả; điểm số được lưu mà không có âm thanh.',
  },
  zh: {
    title: '尝试记录', statAttempts: '次数', statBest: '最佳', statChange: '变化',
    attemptLabel: '第 {n} 次', bestBadge: '最佳', currentBadge: '当前', metaLine: '{when} · 准确度 {acc} · 流利度 {flu}',
    privacyNoteSession: '录音只保存在这个浏览器标签页中，关闭后即消失；分数保存时不含音频。',
    historyScope: '最多显示服务器上的最近 50 次尝试。最佳分数和变化仅依据这里显示的已验证尝试。',
    privacyNoteKept: '每句话最近的五段录音保存在本设备上，不会上传；分数保存时不含音频。',
  },
});
