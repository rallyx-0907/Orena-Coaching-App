# PR-MON-2 Architecture Review

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-14). The fix response is at the end.

Reviewer: ChatGPT — reviewer độc lập
Branch được review: `feature/monetization-billing-v1`
HEAD được review: `31cc715972e1fc75e7a6ad01a63427809836f478`
Commit implementation chính: `490cff7bfe8e2547389d872a3f053e9d83af770e`

## Kết luận

**REQUEST CHANGES**

Không có P0.

Còn **1 P1** cần sửa trước khi merge.

## P1 — `billing_ready` hiện mới chỉ là trạng thái hiển thị, chưa chặn checkout thật sự

Hệ thống readiness mới đã kiểm tra đúng các điều kiện như:

- billing switch bật/tắt;
- runtime có phải PostgreSQL;
- account backbone có active không;
- commerce schema có tồn tại/đọc được không;
- `billing_orders` có tồn tại không;
- entitlement source có được xác minh không;
- production có public HTTPS URL hợp lệ không;
- có ít nhất một payment gateway sẵn sàng không.

Nhưng `/api/billing/offers` và `/api/billing/checkout` hiện **không bắt buộc runtime phải `billing_ready=true`**.

Điều đó tạo ra trạng thái:

`billing_ready = false`

nhưng learner vẫn có thể:

- nhìn thấy offers;
- hoặc gọi checkout.

Ví dụ hiện tại trước khi migration 0027 được áp dụng:

- `billing_orders` chưa tồn tại;
- readiness báo đúng là `false`;
- nhưng nếu `BILLING_ENABLED=1`, service Billing vẫn có thể được tạo;
- `/offers` vẫn có thể trả giá;
- `/checkout` vẫn đi tới bước tạo order và chỉ lỗi khi đụng DB.

Tương tự, production có `PUBLIC_BASE_URL` sai hoặc không phải HTTPS thì readiness sẽ false, nhưng payment boundary hiện vẫn chưa tự chặn.

### Invariant bắt buộc

> Khi runtime chưa billing-ready thì KHÔNG được phép bắt đầu checkout mới.

Việc này phải được enforce ở server, không phụ thuộc UI tự đọc `billing_ready` rồi quyết định có gọi checkout hay không.

### Yêu cầu sửa

Dùng cùng một readiness decision cho learner payment entrypoints.

Tối thiểu:

- `/api/billing/offers`
  - khi chưa ready: không quảng bá offer có thể mua;
  - trả trạng thái `ready/enabled=false` phù hợp.

- `/api/billing/checkout`
  - khi chưa ready: trả lỗi trước khi tạo order và trước khi gọi gateway;
  - dùng 503 retryable, ví dụ `billing_not_ready`.

**Không được áp readiness gate này cho webhook đã xác minh.**

Nếu runtime tạm không cho checkout mới thì webhook của tiền đã xảy ra vẫn phải được nhận và reconcile.

Admin readiness endpoint cũng phải tiếp tục hoạt động dù billing chưa ready.

### Test cần thêm

Tối thiểu cover:

1. service có cấu hình nhưng `billing_orders` chưa tồn tại
   → không có offers, checkout trả 503;

2. production có public URL sai hoặc chưa cấu hình
   → checkout trả 503;

3. runtime đầy đủ và ready
   → offers và checkout vẫn hoạt động như cũ;

4. webhook không bị vô hiệu hóa chỉ vì learner checkout readiness đang false.

Chỉ cần sửa nhỏ ở route/probe là đủ. Không cần redesign `BillingService`.

---

## P2 — Partial commerce schema

Hiện `table_state()` đang coi hai trường hợp sau giống nhau:

- không có bảng commerce nào;
- chỉ có một phần các bảng commerce.

Đều thành `absent`.

Với v1 có thể chấp nhận vì migration commerce bình thường phải atomic.

Nhưng về sau nên phân biệt:

- `absent` = commerce thật sự chưa deploy;
- `partial` = schema lỗi/không đầy đủ → fail closed.

Không block PR-MON-2 sau khi P1 trên được sửa.

---

## P2 — Giá thật bên Polar chưa được xác minh từ provider

Price integrity hiện chỉ chứng minh:

- giá catalogue của Orena;
- amount trong file billing;
- `external_price_id` mapping.

Nó chưa chứng minh `external_price_id` bên Polar hiện thật sự đang charge đúng số tiền đó.

R-MON-011 giữ nguyên.

Chấp nhận defer sang PR-MON-8 sandbox/provider verification.

Không được coi `billing_ready=true` là đồng nghĩa với “đã xác minh giá thật bên Polar” trước PR-MON-8.

---

## Trả lời 5 câu hỏi trong review request

### 1. Một giá lệch thì block cả gateway hay chỉ key đó?

**Giữ block cả gateway.**

Đây là fail-safe hợp lý cho Billing v1.

Một gateway đang có config lệch thì tốt hơn hết dừng toàn bộ việc bán trên gateway đó cho tới khi operator sửa xong, thay vì bán một phần catalogue trong trạng thái config không nhất quán.

### 2. Confirmed amount/currency optional trong schema nhưng required khi checkout thật?

**Chấp nhận.**

Hiện chưa có learner client nào phụ thuộc contract checkout cũ.

Server price vẫn là nguồn charge thật.

Giá learner gửi lên chỉ dùng để phát hiện stale UI / giá vừa đổi.

### 3. Commerce unreadable → fail closed và retry 5 giây?

**Đúng.**

Không được để paid entitlement silently fallback sang legacy chỉ vì một lần schema discovery lỗi.

### 4. Bỏ điều kiện `backbone.is_active` khỏi entitlement discovery?

**Đúng.**

Nếu PostgreSQL commerce được kỳ vọng tồn tại thì entitlement phải tự xác định `installed / absent / unverified`.

Một lỗi discovery của backbone không được che mất paid entitlement.

### 5. Polar-side price verification để PR-MON-8?

**Chấp nhận như residual risk.**

Không block PR-MON-2.

Nhưng production activation vẫn phải chờ provider validation thật.

---

## Re-review

Chỉ cần sửa P1 về readiness enforcement và thêm focused tests.

Sau đó gửi lại:

- SHA commit sửa;
- diff liên quan;
- kết quả test targeted.

Không cần review kiến trúc lại toàn bộ trừ khi bản sửa làm thay đổi đáng kể price-integrity hoặc entitlement semantics.

---

## Fix response (implementer, 2026-10-14)

**P1 — fixed** in the commit that records this file (D-MON-017). Route/probe only; `BillingService`, the price gate and
the entitlement semantics are unchanged.

- `writing_coach/billing_api.py`: the learner entrypoints read the same decision as every surface,
  `billing.readiness.billing_ready()` (cached 5 s, never raises).
  - `GET /api/billing/offers`: `{"enabled", "ready", "offers"}`; `offers` is empty unless `ready`.
  - `POST /api/billing/checkout`: not ready → **503 `billing_not_ready`, retryable**, checked right after
    `billing_off` and before sign-in, the incarnation, any order write or any gateway call.
  - Not gated: `POST /api/billing/webhooks/{gateway}` (money already taken is received and reconciled), the admin
    refund and `GET /api/admin/billing/readiness`.
- Tests (`tests/test_billing_price_integrity.py`, through the real readiness report and the real router):
  1. configured, `billing_orders` absent → no offers, checkout 503, no order, no gateway call;
  2. production with `http://` or an unset public URL → the same;
  3. a fully ready runtime → one offer, checkout 200 with the gateway's redirect, one order, one gateway call;
  4. readiness false → a webhook still reaches the service and answers 200.
- Mutations: removing the checkout gate fails 3 tests; removing the offers gate fails 3 tests.
- Local targeted SQLite run (not CI): 264 passed, 1 skipped (billing, price integrity, effective entitlement, account
  state, commerce, membership, admin console routes, language limit, public-route inventory).

**P2 partial commerce schema** — recorded as R-MON-012 (`absent` vs `partial`), not changed here.
**P2 Polar price** — R-MON-011 unchanged; `billing_ready=true` does not mean the Polar price was verified, and
production activation waits for PR-MON-8.
