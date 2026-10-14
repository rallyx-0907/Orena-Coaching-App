/* Credit top-up: the keys product/credit-topup.js points at (refusals, waiting states, history labels).
   KEYS ONLY, NOT DESIGN COPY: no frame draws these yet (UI_BACKEND_GAPS "Credit top-up client", CT-6), so every
   string below is a PLACEHOLDER the design will confirm or replace. The four history words are the billing lane's:
   "Buy credits / Use credits / Refund credits / Adjust credits" and their Vietnamese "Mua Credits", "Dùng Credits",
   "Hoàn Credits", "Điều chỉnh Credits". The Chinese strings are placeholders awaiting a native review.
   Nothing here names a ledger, hold, settlement, reversal, reconciliation or shortfall: those are backend terms. */
import { defineCopy } from './index.js';

const KEYS = [
  'errUnavailable', 'errTryLater', 'errPriceChanged', 'errNotOffered', 'errAlreadyStarted', 'errOrderClosed',
  'errGatewayUnavailable', 'errSignIn', 'errAccountClosed', 'errGeneric',
  'statusWaiting', 'statusStillWaiting', 'statusConfirmed', 'statusExpired', 'statusCancelled', 'statusFailed', 'statusRefunded',
  'historyBuy', 'historyUse', 'historyRefund', 'historyAdjust',
];

export const t = defineCopy('creditTopup', {
  layers: Object.fromEntries(KEYS.map((key) => [key, 'interface'])),
  en: {
    errUnavailable: 'Credits are not available right now.', errTryLater: 'Credits cannot be bought right now. Try again later.',
    errPriceChanged: 'The price changed. Check it and confirm again.', errNotOffered: 'This pack is no longer available.',
    errAlreadyStarted: 'This purchase is already waiting for payment.', errOrderClosed: 'This purchase is closed. Start a new one.',
    errGatewayUnavailable: 'The payment page could not be opened. Try again.', errSignIn: 'Sign in to buy credits.',
    errAccountClosed: 'This account cannot buy credits.', errGeneric: 'Something went wrong. Try again later.',
    statusWaiting: 'Waiting for payment confirmation', statusStillWaiting: 'Still waiting. Credits are added once the payment is confirmed.',
    statusConfirmed: 'Credits added', statusExpired: 'The payment time ran out', statusCancelled: 'The payment was cancelled',
    statusFailed: 'The payment did not go through', statusRefunded: 'This payment was refunded',
    historyBuy: 'Buy credits', historyUse: 'Use credits', historyRefund: 'Refund credits', historyAdjust: 'Adjust credits',
  },
  vi: {
    errUnavailable: 'Hiện chưa thể dùng Credits.', errTryLater: 'Hiện chưa thể mua Credits. Hãy thử lại sau.',
    errPriceChanged: 'Giá đã thay đổi. Hãy kiểm tra và xác nhận lại.', errNotOffered: 'Gói này không còn nữa.',
    errAlreadyStarted: 'Giao dịch này đang chờ thanh toán.', errOrderClosed: 'Giao dịch này đã đóng. Hãy bắt đầu giao dịch mới.',
    errGatewayUnavailable: 'Không mở được trang thanh toán. Hãy thử lại.', errSignIn: 'Đăng nhập để mua Credits.',
    errAccountClosed: 'Tài khoản này không thể mua Credits.', errGeneric: 'Đã có lỗi xảy ra. Hãy thử lại sau.',
    statusWaiting: 'Đang chờ xác nhận thanh toán', statusStillWaiting: 'Vẫn đang chờ. Credits sẽ được cộng khi thanh toán được xác nhận.',
    statusConfirmed: 'Đã cộng Credits', statusExpired: 'Đã hết thời gian thanh toán', statusCancelled: 'Thanh toán đã bị hủy',
    statusFailed: 'Thanh toán không thành công', statusRefunded: 'Khoản thanh toán này đã được hoàn',
    historyBuy: 'Mua Credits', historyUse: 'Dùng Credits', historyRefund: 'Hoàn Credits', historyAdjust: 'Điều chỉnh Credits',
  },
  zh: {
    errUnavailable: '暂时无法使用 Credits。', errTryLater: '暂时无法购买 Credits，请稍后再试。',
    errPriceChanged: '价格已变化，请核对后重新确认。', errNotOffered: '此套餐已不再提供。',
    errAlreadyStarted: '此次购买正在等待付款。', errOrderClosed: '此次购买已关闭，请重新开始。',
    errGatewayUnavailable: '无法打开付款页面，请重试。', errSignIn: '请登录后购买 Credits。',
    errAccountClosed: '此账号无法购买 Credits。', errGeneric: '出了点问题，请稍后再试。',
    statusWaiting: '正在等待付款确认', statusStillWaiting: '仍在等待。付款确认后会自动添加 Credits。',
    statusConfirmed: 'Credits 已到账', statusExpired: '付款已超时', statusCancelled: '付款已取消',
    statusFailed: '付款未成功', statusRefunded: '此笔付款已退款',
    historyBuy: '购买 Credits', historyUse: '使用 Credits', historyRefund: '退还 Credits', historyAdjust: '调整 Credits',
  },
});
