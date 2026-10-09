/* Plan & usage, Plans and the Billing sheet: the words of the three frames, all chrome (interface
   language, D-079). Feature names are the catalogue's feature keys (writing_coach/product/
   catalog.py) in the learner's words; plan names and descriptions come from copy/shell.js by plan
   id. Placeholders only ever receive a real positive number (the shared fill() keeps a 0 too, but
   no screen asks for one). */
import { defineCopy } from '../../copy/index.js';

const KEYS = [
  'title', 'seePlans', 'currentPlan', 'changePlan', 'upgrade', 'noCharge',
  'status_free', 'status_pending', 'status_trialing', 'status_active', 'status_past_due', 'status_paused', 'status_ended', 'status_unknown',
  'usage', 'resetsMonthly', 'usageLeft', 'limitReached', 'almostLimit', 'usageUnavailable', 'usageNotRead',
  'paymentMethod', 'noPaymentMethod', 'paymentMethodSub', 'update', 'invoices', 'noInvoices',
  'plansTitle', 'pricingHero', 'pricingSub', 'priceFree', 'freeForever',
  'billingCycle', 'cycleMonthly', 'cycleYearly', 'perMonth', 'billedMonthly', 'billedYearly', 'pricePerMonth', 'pricePerYear',
  'tagCurrent', 'ctaCurrent', 'ctaUpgrade', 'ctaSwitch', 'comparePlans',
  'monthlyLimit', 'featureIncluded', 'featureNotIncluded',
  'feature_writing_evaluate', 'feature_writing_improve', 'feature_dictionary_lookup', 'feature_vocabulary_save',
  'feature_library_grammar', 'feature_analytics_basic', 'feature_analytics_advanced', 'feature_practice_personalized', 'feature_export_report',
  'sheetUpgrade', 'sheetSwitch', 'rowPlan', 'rowPrice', 'dueToday', 'billingNote', 'sheetBack', 'sheetConfirm',
];

export const t = defineCopy('plan', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    title: 'Plan & usage', seePlans: 'See all plans', currentPlan: 'Current plan', changePlan: 'Change plan', upgrade: 'Upgrade', noCharge: 'No charge',
    status_free: 'Free', status_pending: 'Pending', status_trialing: 'Trial', status_active: 'Active', status_past_due: 'Past due', status_paused: 'Paused', status_ended: 'Ended', status_unknown: 'Unknown',
    usage: 'Usage', resetsMonthly: 'Resets every month', usageLeft: '{n} left', limitReached: 'Limit reached', almostLimit: 'Almost at limit',
    usageUnavailable: "Usage can't be read right now.", usageNotRead: 'Not available',
    paymentMethod: 'Payment method', noPaymentMethod: 'No payment method', paymentMethodSub: 'Payments are not available yet', update: 'Update',
    invoices: 'Invoices', noInvoices: 'No invoices yet',
    plansTitle: 'Plans', pricingHero: 'More time with Orena when you need it',
    pricingSub: 'Every plan includes all reading, listening, speaking, writing and review practice. Plans differ in how much Orena can analyse for you.',
    priceFree: 'Free', freeForever: 'Free forever',
    billingCycle: 'Billing cycle', cycleMonthly: 'Monthly', cycleYearly: 'Yearly', perMonth: '/ month', billedMonthly: 'Billed monthly', billedYearly: 'Billed {amount} yearly', pricePerMonth: '{amount} / month', pricePerYear: '{amount} / year',
    tagCurrent: 'Current', ctaCurrent: 'Current plan', ctaUpgrade: 'Upgrade to {plan}', ctaSwitch: 'Switch to {plan}', comparePlans: 'Compare plans',
    monthlyLimit: '{label} · {n} a month', featureIncluded: 'Included', featureNotIncluded: 'Not included',
    feature_writing_evaluate: 'Writing reviews', feature_writing_improve: 'Writing improvements', feature_dictionary_lookup: 'Dictionary lookups', feature_vocabulary_save: 'Saved words',
    feature_library_grammar: 'Grammar library', feature_analytics_basic: 'Progress overview', feature_analytics_advanced: 'Advanced progress', feature_practice_personalized: 'Personalised practice', feature_export_report: 'Report export',
    sheetUpgrade: 'Upgrade to {plan}', sheetSwitch: 'Switch to {plan}', rowPlan: 'Plan', rowPrice: 'Price', dueToday: 'Due today',
    billingNote: 'Paying for a plan is not available yet.', sheetBack: 'Back', sheetConfirm: 'Confirm change',
  },
  vi: {
    title: 'Gói & mức dùng', seePlans: 'Xem tất cả gói', currentPlan: 'Gói hiện tại', changePlan: 'Đổi gói', upgrade: 'Nâng cấp', noCharge: 'Không tính phí',
    status_free: 'Miễn phí', status_pending: 'Đang chờ', status_trialing: 'Dùng thử', status_active: 'Đang hoạt động', status_past_due: 'Quá hạn', status_paused: 'Tạm dừng', status_ended: 'Đã kết thúc', status_unknown: 'Chưa rõ',
    usage: 'Mức dùng', resetsMonthly: 'Đặt lại mỗi tháng', usageLeft: 'còn {n}', limitReached: 'Đã hết lượt', almostLimit: 'Sắp hết',
    usageUnavailable: 'Hiện chưa đọc được mức dùng.', usageNotRead: 'Chưa có',
    paymentMethod: 'Phương thức thanh toán', noPaymentMethod: 'Chưa có phương thức thanh toán', paymentMethodSub: 'Chưa hỗ trợ thanh toán', update: 'Cập nhật',
    invoices: 'Hoá đơn', noInvoices: 'Chưa có hoá đơn',
    plansTitle: 'Các gói', pricingHero: 'Thêm thời gian với Orena khi bạn cần',
    pricingSub: 'Mọi gói đều gồm đầy đủ luyện đọc, nghe, nói, viết và ôn tập. Các gói khác nhau ở mức Orena có thể phân tích cho bạn.',
    priceFree: 'Miễn phí', freeForever: 'Miễn phí mãi mãi',
    billingCycle: 'Chu kỳ thanh toán', cycleMonthly: 'Hằng tháng', cycleYearly: 'Hằng năm', perMonth: '/ tháng', billedMonthly: 'Thanh toán hằng tháng', billedYearly: 'Thanh toán {amount} mỗi năm', pricePerMonth: '{amount} / tháng', pricePerYear: '{amount} / năm',
    tagCurrent: 'Hiện tại', ctaCurrent: 'Gói hiện tại', ctaUpgrade: 'Nâng cấp lên {plan}', ctaSwitch: 'Chuyển sang {plan}', comparePlans: 'So sánh các gói',
    monthlyLimit: '{label} · {n} mỗi tháng', featureIncluded: 'Có', featureNotIncluded: 'Không có',
    feature_writing_evaluate: 'Lượt chữa bài viết', feature_writing_improve: 'Lượt cải thiện bài viết', feature_dictionary_lookup: 'Lượt tra từ điển', feature_vocabulary_save: 'Từ đã lưu',
    feature_library_grammar: 'Thư viện ngữ pháp', feature_analytics_basic: 'Tổng quan tiến độ', feature_analytics_advanced: 'Tiến độ nâng cao', feature_practice_personalized: 'Luyện tập cá nhân hoá', feature_export_report: 'Xuất báo cáo',
    sheetUpgrade: 'Nâng cấp lên {plan}', sheetSwitch: 'Chuyển sang {plan}', rowPlan: 'Gói', rowPrice: 'Giá', dueToday: 'Thanh toán hôm nay',
    billingNote: 'Hiện chưa hỗ trợ thanh toán cho gói.', sheetBack: 'Quay lại', sheetConfirm: 'Xác nhận đổi gói',
  },
  zh: {
    title: '套餐与用量', seePlans: '查看全部套餐', currentPlan: '当前套餐', changePlan: '更换套餐', upgrade: '升级', noCharge: '免费',
    status_free: '免费', status_pending: '待处理', status_trialing: '试用中', status_active: '生效中', status_past_due: '已逾期', status_paused: '已暂停', status_ended: '已结束', status_unknown: '未知',
    usage: '用量', resetsMonthly: '每月重置', usageLeft: '剩余 {n}', limitReached: '已达上限', almostLimit: '接近上限',
    usageUnavailable: '暂时无法读取用量。', usageNotRead: '暂无',
    paymentMethod: '付款方式', noPaymentMethod: '尚无付款方式', paymentMethodSub: '暂不支持付款', update: '更新',
    invoices: '发票', noInvoices: '暂无发票',
    plansTitle: '套餐', pricingHero: '需要时，与 Orena 共度更多时间',
    pricingSub: '每个套餐都包含全部阅读、听力、口语、写作和复习练习。套餐的区别在于 Orena 能为你分析多少。',
    priceFree: '免费', freeForever: '永久免费',
    billingCycle: '计费周期', cycleMonthly: '按月', cycleYearly: '按年', perMonth: '/ 月', billedMonthly: '按月付费', billedYearly: '每年付费 {amount}', pricePerMonth: '{amount} / 月', pricePerYear: '{amount} / 年',
    tagCurrent: '当前', ctaCurrent: '当前套餐', ctaUpgrade: '升级到{plan}', ctaSwitch: '切换到{plan}', comparePlans: '对比套餐',
    monthlyLimit: '{label} · 每月 {n}', featureIncluded: '包含', featureNotIncluded: '不包含',
    feature_writing_evaluate: '写作批改', feature_writing_improve: '写作改进', feature_dictionary_lookup: '词典查询', feature_vocabulary_save: '收藏词汇',
    feature_library_grammar: '语法库', feature_analytics_basic: '进度概览', feature_analytics_advanced: '高级进度', feature_practice_personalized: '个性化练习', feature_export_report: '导出报告',
    sheetUpgrade: '升级到{plan}', sheetSwitch: '切换到{plan}', rowPlan: '套餐', rowPrice: '价格', dueToday: '今日应付',
    billingNote: '暂不支持为套餐付款。', sheetBack: '返回', sheetConfirm: '确认更换',
  },
});
