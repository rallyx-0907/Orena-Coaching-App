# PR-MON-3 Architecture Review (design)

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-14). The design response is at the end.

# Review kiến trúc PR-MON-3

Reviewer: ChatGPT — reviewer độc lập  
Design commit: `a50aa76b`  
Base được thiết kế trên: `main d55526a2`  
Phạm vi: Billing Orders + Reconciliation Safety + proposed financial migration 0027

## Kết luận

**REQUEST CHANGES**

Không có P0.

Có **4 P1 ở mức thiết kế** cần đóng trước khi implementation.

Phần lớn hướng kiến trúc là đúng: durable anomaly, write-before-ack, idempotent replay, payOS pull, gap repair, operator API và không tự apply financial migration đều là hướng nên giữ.

---

# P1-1 — Schema reconciliation không lưu được chính `payment_unknown_order`

Thiết kế mới cho:

`billing_reconciliation_items.order_code BIGINT NULL FK billing_orders(order_code)`

Nhưng `payment_unknown_order` tồn tại chính vì **order code từ provider không tồn tại trong `billing_orders`**.

Nếu lưu order code đó vào cột có FK, INSERT reconciliation item sẽ fail.

Nếu để NULL thì lại mất một trong những dữ kiện quan trọng nhất để operator điều tra.

Điều này phá invariant:

> Verified money anomaly phải được ghi bền vững trước khi trả 2xx.

## Yêu cầu sửa

Tách:

- `reported_order_code BIGINT NULL`
  - fact do provider báo;
  - **không FK**.

và nếu cần:

- `billing_order_id UUID NULL`
  - FK tới order Orena khi đã match được.

Hoặc cấu trúc tương đương.

Không dùng một cột vừa làm provider fact vừa làm FK nội bộ.

Test bắt buộc:

- unknown payOS order code không tồn tại trong DB;
- reconciliation item vẫn INSERT được;
- giữ nguyên reported order code;
- replay cùng event chỉ tăng `occurrences`;
- webhook trả 200 sau khi item commit.

---

# P1-2 — Lost-webhook safety net vẫn có lỗ ở thời điểm order hết hạn

§4.5 step 2 chỉ pull các payOS order:

> pending, older than pull threshold, **and not yet expired**

Sau đó step 3 chuyển order quá `expires_at` thành `expired` và nói rằng payOS được pull một lần trước.

Hai rule này chưa khép kín.

Ví dụ:

1. order gần hết 30 phút;
2. khách vừa thanh toán;
3. webhook bị mất;
4. lần pull cuối cùng lỗi mạng / payOS trả 429;
5. order qua `expires_at`;
6. local chuyển thành `expired`;
7. reconciler không còn pull order đó nữa.

Tiền vẫn có thể đã đi nhưng F7 lại trở về.

`mark_paid()` chấp nhận late payment chỉ giúp khi webhook cuối cùng tới; nó không giải quyết trường hợp webhook mất hẳn.

## Yêu cầu sửa

Local expiry **không được là điểm dừng reconciliation của payOS**.

Chọn một invariant rõ ràng, ví dụ:

- expired payOS orders vẫn được poll trong một reconciliation safety horizon; hoặc
- chỉ coi provider payment state đã terminal khi đã có một successful provider lookup; hoặc
- một cơ chế tương đương chứng minh lost webhook sau expiry vẫn được tìm ra.

Không cần chọn retention horizon thương mại trong PR này, nhưng không được ngừng tìm payment chỉ vì local TTL vừa hết.

Ngoài ra không hard-code provider state `EXPIRED` như fact đã được xác minh.

Tài liệu payOS hiện tại xác nhận các state như:

`PAID / PENDING / PROCESSING / CANCELLED`

nhưng chưa đủ bằng chứng cho `EXPIRED`.

Nếu sandbox sau này trả thêm state thì PR-MON-8 cập nhật adapter.

---

# P1-3 — Safety-critical reconciliation item không được phép bị “dismiss” rồi biến mất khỏi cảnh báo

Thiết kế hiện tại cho mọi item:

`open → resolved | dismissed`

và sau khi terminal thì replay chỉ tăng `occurrences`.

Điều này nguy hiểm với các kind mang invariant tiền/quyền truy cập, đặc biệt:

- `entitlement_unsynced`;
- `provider_paid_unrecorded`;
- `paid_deleted_account`.

Ví dụ một Admin dismiss `entitlement_unsynced` nhưng account vẫn đã trả tiền mà chưa có access.

Reconciler tiếp tục thấy gap, nhưng cùng dedupe row đã terminal nên không quay lại trạng thái open.

Ta đã biến một lỗi tiền thật thành một dòng “dismissed”.

## Yêu cầu sửa

Resolution policy phải theo `kind`.

Tối thiểu:

### `entitlement_unsynced`

Không được manual dismiss.

Chỉ auto-resolve khi derived invariant thật sự đã hết:

`orders prepaid version == applied commerce version`

và entitlement đã được sync thành công.

### `provider_paid_unrecorded`

Không được dismiss đơn thuần khi provider vẫn nói đã trả.

Phải có outcome thực tế như payment được record, refund/reversal được xác nhận, hoặc một resolution fact tương đương.

### `paid_deleted_account`

Không được biến mất chỉ bằng dismiss.

Resolution phải ghi lại việc nghĩa vụ đã được xử lý hoặc lý do tài chính có thể audit được.

Các informational/false-positive kinds như một số `event_undecided` có thể cho dismiss nếu reviewer/operator xác nhận không có money obligation.

## Billing readiness

PR-MON-2 định nghĩa `billing_ready` là runtime có thể:

> nhận tiền và cấp thứ mà người dùng mua.

Vì vậy nếu tồn tại một **persistent `entitlement_unsynced` sau repair attempt**, hệ thống đã có bằng chứng rằng invariant đó đang không đúng.

Không nên để `reconciliation_open` hoàn toàn “informational only”.

Thiết kế nên có một khái niệm riêng như:

`critical_reconciliation_blocker`

và ít nhất persistent paid-without-access phải đóng new checkout cho đến khi repair/resolve thật.

Không cần block toàn gateway chỉ vì mọi anomaly P2/P3.

---

# P1-4 — `pg_try_advisory_xact_lock` và network call chưa có lock scope an toàn

Thiết kế nói:

- `pg_try_advisory_xact_lock` bảo đảm chỉ một reconciler tick chạy;
- `FOR UPDATE SKIP LOCKED`;
- đồng thời tick gọi API payOS bên ngoài.

Có hai cách triển khai và cả hai đều có vấn đề nếu không định nghĩa rõ:

### Cách A — giữ cùng transaction suốt tick

Advisory xact lock có hiệu lực.

Nhưng transaction/row locks sẽ bị giữ trong lúc chờ network payOS.

Không nên giữ financial DB transaction qua external HTTP request.

### Cách B — transaction kết thúc trước network call

Row locks được thả.

Nhưng `pg_try_advisory_xact_lock` cũng được thả, nên nó không còn chứng minh “chỉ một tick chạy”.

## Yêu cầu sửa

Thiết kế lock scope rõ trước implementation.

Khuyến nghị:

- dùng **session-level advisory lock** trên một dedicated PostgreSQL connection cho toàn tick;
- luôn release trong `finally`;
- mỗi order/payment/reconciliation mutation dùng transaction ngắn riêng;
- không giữ `FOR UPDATE` hay transaction mở trong lúc gọi payOS.

Hoặc một lease/claim design tương đương.

Idempotency vẫn phải là lớp bảo vệ cuối cùng nếu webhook và pull race nhau.

---

# P2 — payOS pull response còn cần hardening

Hướng H3 là đúng.

Official payOS hiện có API lấy payment request bằng orderCode/paymentLinkId và trả `amountPaid`, `status`, `transactions`.

Nhưng implementation không được giả định trước:

- `transactions` luôn có cùng shape;
- có field `reference` ở đúng vị trí;
- có provider state `EXPIRED`.

R-MON-013 nên được thu hẹp thành:

> API lookup, `expiredAt`, `amountPaid` và các status cơ bản đã được xác minh từ official docs; exact transaction-reference shape và mọi status ngoài documented set phải được xác minh sandbox trước production activation.

Nếu event ID của poll không thể tái tạo đúng webhook event ID, phải sửa idempotency model thay vì đoán field.

---

# P2 — payOS rate limiting

Official API có thể trả `429 Too Many Requests`.

Reconciler cần:

- giới hạn số order pull mỗi tick;
- backoff khi 429;
- không tạo reconciliation anomaly tiền chỉ vì provider đang rate-limit;
- retry ở tick sau.

Không cần một scheduler phức tạp.

---

# P2 — `billing_orders` nói “never deleted” nhưng schema chưa enforce

Thiết kế đã bảo vệ `billing_reconciliation_items` bằng no-delete trigger và downgrade guard.

`billing_orders` cũng là financial record nhưng hiện invariant “never deleted” chủ yếu dựa vào application discipline.

Nên cân nhắc no-delete DB trigger cho `billing_orders` sau promotion.

Không block design nếu repository hoàn toàn không có delete path và downgrade guard đã có, nhưng database-level protection sẽ phù hợp hơn với H7.

---

# Quyết định H1–H7

## H1 — Promotion order 0027 / 0028

**APPROVE, với rule chặt hơn.**

Không lấy số revision làm thứ tự.

Tại thời điểm promote:

1. đọc lại Alembic head thật;
2. revision được promote phải parent vào **current head**;
3. chỉ một financial/content migration được đưa vào chain tại một thời điểm;
4. revision promote sau tự re-parent revision của chính lane đó.

Nếu Billing đi trước:

`... → 0026 → 0027`

và Reading sau đó nối 0028 lên 0027.

Nếu Reading đi trước:

Reading tự re-parent 0028 lên current head; khi Billing promote, Billing re-parent 0027 lên head mới.

Billing không sửa file thuộc Reading.

**H1 = CHỐT.**

---

## H2 — sửa trực tiếp never-applied 0027

**APPROVE CÓ ĐIỀU KIỆN.**

Về source-control đây là lựa chọn đúng vì 0027 vẫn nằm trong `migrations/proposed/`.

Nhưng trước khi sửa revision này in-place phải có operator confirmation rằng:

- không shared/runtime DB nào có `alembic_version = 20261005_0027`;
- không có `billing_orders` được tạo thủ công từ revision này;
- không có sandbox lâu dài nào cần giữ migration history cũ.

Nếu không xác minh được, không mutate revision cũ; tạo revision mới.

Billing lane không tự truy vấn :8000/:8010/:8021 để chứng minh việc này.

**H2 = CONDITIONAL APPROVE.**

---

## H3 — cho phép payOS pull

**APPROVE.**

Đây là safety net cần thiết.

Webhook delivery retry của payOS không được tài liệu hiện tại bảo đảm đủ để dùng làm nguồn recovery duy nhất.

API lookup payment request là API chính thức.

Điều kiện:

- billing phải bật;
- keys hợp lệ;
- outbound call qua gateway abstraction;
- timeout;
- rate-limit/backoff;
- sandbox verification trước production.

**H3 = CHỐT.**

---

## H4 — Polar refund có revoke access ngay không?

**APPROVE đề xuất của lane: KHÔNG.**

Refund order subscription không tự kết thúc subscription relationship.

Access tiếp tục theo subscription lifecycle event của Polar.

Nếu muốn ngắt access thì subscription phải được revoke/cancel theo lifecycle tương ứng.

Mọi refund vẫn phải được ghi durable.

**H4 = CHỐT.**

---

## H5 — TTL order 30 phút

**APPROVE.**

30 phút là operational TTL, không phải commercial entitlement policy.

Gửi cùng `expiredAt` cho payOS là hợp lý.

Nhưng:

> TTL không được trở thành thời điểm Orena ngừng tìm payment bị mất webhook.

Late verified payment vẫn thắng local expiry.

**H5 = CHỐT với P1-2 ở trên.**

---

## H6 — Admin resolve, có audit, resolve không tự dịch chuyển tiền

**APPROVE CÓ RÀNG BUỘC.**

- Admin only.
- Audit note bắt buộc.
- Resolve action không charge/refund/grant/revoke tiền hoặc access một cách ngầm.
- Financial action là operation riêng.

Nhưng `dismissed` không được áp tự do cho safety-critical kinds như đã nêu ở P1-3.

**H6 = CHỐT SAU KHI thêm per-kind resolution rules.**

---

## H7 — retention

**APPROVE theo cách diễn đạt:**

> Không có automated deletion trong PR-MON-3 cho tới khi có retention/legal policy chính thức.

Không cần cam kết “giữ vĩnh viễn” như một chính sách pháp lý.

Dữ liệu vẫn phải tối thiểu hóa:

- không raw webhook payload;
- không email;
- không card data;
- chỉ financial/reconciliation facts cần audit.

**H7 = CHỐT.**

---

# Provider delivery policy

Giữ nguyên nguyên tắc:

> money event đã verify chỉ được 2xx sau khi có durable representation.

Business anomaly:
- durable reconciliation row;
- sau đó 2xx.

Infrastructure/DB failure khiến không ghi durable được:
- 5xx/503.

Đây vẫn là phía an toàn mặc dù Polar retry tối đa 10 lần và có thể disable endpoint sau 10 consecutive non-2xx.

Không được đổi thành “luôn trả 200” chỉ để tránh endpoint disable — như vậy có thể mất money event.

Sau này Ops cần alert nếu webhook 5xx liên tục.

---

# Sau khi sửa design

Chưa code.

Agent chỉ cần cập nhật `PR-MON-3_DESIGN.md` để đóng bốn P1:

1. schema unknown-order;
2. pull/reconciliation sau local expiry;
3. per-kind resolution + critical reconciliation readiness;
4. reconciler advisory-lock / transaction scope.

Sau đó trả lại:

- commit SHA của design revision;
- diff của design;
- bảng H1–H7 đã chốt;
- không implementation;
- không sửa/promote/apply 0027.

Tôi sẽ focused re-review bốn thay đổi này.

Nếu pass thì **APPROVE design**, sau đó mới được implement slices 1–6.

---

## Design response (implementer, 2026-10-14)

Design revision 2 is in `docs/billing/PR-MON-3_DESIGN.md`, in the commit that records this file. There is no code,
and 0027 is unchanged, not promoted and not applied.

- **P1-1.** Provider facts and Orena links are separate columns.
  - Provider facts, with no foreign key: `reported_order_code`, `reported_amount_minor`, `reported_currency`,
    `external_event_id`.
  - Orena links, set only when matched: `billing_order_id` (foreign key to `billing_orders.id`) and
    `incarnation_id`.
  - The required tests are listed (§4.2, §5, §8).
- **P1-2.** Local expiry does not stop the pull.
  - `expired` payOS orders stay in the pull set until a **successful** lookup returns a documented terminal answer:
    PAID with the matching amount, or CANCELLED with nothing paid.
  - Everything else, `EXPIRED` and any unknown status included, is non-terminal and backs off up to 6 h.
  - A 14-day operational horizon opens `provider_state_unresolved` and keeps a daily lookup, so the search never
    stops.
  - Idempotency no longer reconstructs the webhook id. The pull's id is `payos:order:<code>`, there is one payment
    per payOS order, a `paid_reference` column is added, and a confirming lookup catches an overpayment (§4.5).
- **P1-3.** The resolution rules are per kind and enforced by CHECKs and a trigger.
  - `entitlement_unsynced` is resolved only by the reconciler, with `entitlement_synced`.
  - `provider_paid_unrecorded`, `paid_deleted_account` and the other money kinds need an outcome with a reference
    or an audited reason, and are never dismissed.
  - A critical item reopens when its condition is detected again.
  - An open critical item blocks its gateway's readiness (`reconciliation_critical`), so the D-MON-017 gate closes
    checkout while webhooks and the reconciler keep running (§4.2, §4.7, §5).
- **P1-4.** A session-level `pg_try_advisory_lock` on a dedicated connection with no transaction, released in
  `finally`.
  - Each mutation runs in its own short transaction.
  - No transaction or row lock is open during the payOS call, and a test asserts this through `pg_locks`.
  - If the lock connection is lost, the tick stops (§4.5).
- **P2s.**
  - The pull is limited per tick, gets a 5 s timeout, and backs off on a 429 (honouring `Retry-After`) without
    opening a money item.
  - `billing_orders` gets a no-delete trigger.
  - R-MON-013 is narrowed as asked.
- **H1–H7** are recorded as decided in §9. H2 waits for the operator's confirmation.

---

# PR-MON-3 — Focused Design Re-verification

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-14).

Reviewer: ChatGPT — reviewer độc lập  
Reviewed design commit: `5b44517502e46ce15f27860830245f8af62ba587`

## Verdict

**APPROVE DESIGN**

Bốn P1 của review trước đã được đóng.

### P1-1 — Unknown provider order

**VERIFIED FIXED.**

Provider facts và Orena internal links đã được tách riêng.

`reported_order_code` và các provider facts không có foreign key, nên một payment cho order code chưa từng tồn tại trong Orena vẫn có thể được ghi durable trước khi webhook trả 2xx.

`billing_order_id` và `incarnation_id` chỉ được điền khi Orena thực sự match được record.

### P1-2 — Payment lookup sau local expiry

**VERIFIED FIXED.**

Local `expires_at` không còn là điểm dừng reconciliation.

Expired payOS orders vẫn nằm trong pull set cho tới khi có một provider answer được phép coi là settled.

Unknown/undocumented states không bị tự suy diễn thành terminal.

Sau pull horizon, anomaly được mở nhưng lookup vẫn tiếp tục với cadence thấp hơn.

Thiết kế cũng không còn phụ thuộc vào việc tái tạo webhook event ID từ dữ liệu poll.

### P1-3 — Per-kind resolution và critical readiness

**VERIFIED FIXED.**

Safety-critical reconciliation kinds không thể bị Admin dismiss tùy ý.

`entitlement_unsynced` chỉ được reconciler tự resolve sau khi invariant entitlement thật sự được phục hồi.

Các money obligations yêu cầu outcome/reference/reason phù hợp.

Critical condition tái diễn sẽ reopen item.

Open critical reconciliation item làm gateway tương ứng `not ready`, trong khi webhook, reconciler và Admin recovery routes vẫn hoạt động.

### P1-4 — Reconciler lock scope

**VERIFIED FIXED.**

Thiết kế dùng session-level advisory lock trên dedicated PostgreSQL connection cho toàn tick.

Các mutation dùng transaction ngắn riêng.

Không giữ DB transaction hoặc row lock trong lúc gọi payOS.

Webhook/pull concurrency vẫn dựa vào idempotency như lớp bảo vệ cuối cùng.

Implementation note:

Sau khi gọi `pg_try_advisory_lock`, nếu driver/SQLAlchemy mở implicit transaction chỉ để thực hiện câu SELECT lấy lock, transaction đó phải được kết thúc trước external HTTP call; session advisory lock vẫn được giữ trên connection.

## P2

Các P2 của review trước đã được xử lý đủ ở design level:

- pull batch limit;
- timeout;
- 429/backoff;
- không tạo money anomaly vì rate-limit;
- no-delete protection cho `billing_orders`;
- R-MON-013 đã thu hẹp đúng phạm vi provider facts chưa được sandbox xác minh.

Không có P2 nào block implementation.

## H1–H7

H1, H3, H4, H5, H6 và H7: **APPROVED / DECIDED** theo design revision 2.

H2: **CONDITIONAL APPROVE** giữ nguyên.

Trước khi implementation sửa trực tiếp proposed revision 0027, operator phải xác nhận:

1. không runtime/shared DB nào có `alembic_version = 20261005_0027`;
2. không có `billing_orders` được tạo thủ công từ revision đó;
3. không có long-lived sandbox cần giữ migration history cũ.

Nếu không thể xác nhận đủ ba điều, **không sửa 0027 in-place**. Dùng phương án follow-up revision đã mô tả trong design.

Việc chọn một trong hai nhánh H2 này không cần architecture review mới, miễn implementation giữ đúng schema/invariants đã được duyệt.

## Authorization to implement

PR-MON-3 design được phép chuyển sang implementation slices 1–6 sau khi H2 được operator quyết định theo rule trên.

Vẫn giữ các gate:

- chỉ test migration trên PostgreSQL tạm;
- không promote migration;
- không apply lên `:8000`, `:8010`, `:8021` hoặc shared runtime;
- không bật production Billing;
- financial migration vẫn cần human authorization riêng trước promotion/application.

Implementation hoàn tất vẫn cần independent review trước merge vì đây là payment + financial schema code.

---

## H2 branch taken (implementer, 2026-10-14)

No operator confirmation was given, so 0027 is **not** changed in place. The approved schema change is a new
proposed revision, `migrations/proposed/20261014_0031_billing_reconciliation.py` (`down_revision = "20261005_0027"`),
as design §5 provides. If the operator later confirms all three conditions, folding it into 0027 is a
source-control change only and needs no new architecture review.

---

# PR-MON-3 implementation review

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-14).

PR-MON-3 implementation review on frozen HEAD 49505ca0:

VERDICT: REQUEST CHANGES
No P0. Three P1s.

P1-1 paid_deleted_account retry durability:
mark_paid can commit paid_deleted_account, item write fails -> 503; retry sees paid/same event as duplicate and never recreates the refund-obligation item. Add focused regression and make the anomaly recoverable/stable across retry.

P1-2 provider_paid_unrecorded resolution:
- Admin must not close it as payment_recorded without the order actually becoming paid.
- payment_recorded must be system/reconciler-only and DB-backed.
- refund_confirmed/reversal_confirmed must leave a durable disposition so subsequent payOS PAID lookups do not reopen the same resolved obligation forever.
Add focused tests.

P1-3 payOS confirmation state race:
- _settle uses a pre-HTTP order snapshot for state-sensitive decisions.
- Race: pending -> HTTP -> webhook makes paid -> lookup says CANCELLED; mark_cancelled returns false but code still settles CANCELLED.
- Also a webhook-paid order refunded before its required confirming lookup drops out of pull_candidates because refunded is excluded, so overpayment confirmation is lost.
Use a fresh/conditional state decision after the HTTP call and keep the required confirmation across refund.
Add both race regressions.

Approved:
- same-version gap escalation;
- per-gateway critical blocking;
- one-payment-per-order model in principle;
- implementation deviations 1,2,3,4,6,7,8.
Deviation 5 policy approved after P1-3 implementation is fixed.

Do not redesign PR-MON-3.
Do not promote/apply 0027/0031.
Return fixing SHA + focused diffs + focused PG tests.
No full architecture re-review after these three P1s unless semantics materially change.

---

## Fix response to the implementation review (implementer, 2026-10-14)

The code fixes are in `52923cf6`; `1f73d4fa` adds one more P1-3 regression test. The design is unchanged, and
0027/0031 are not promoted or applied anywhere.

- **P1-1.**
  - `mark_paid` reads the account's `deleted_at` under the lock it already takes.
  - A repeat of a payment recorded at or after the deletion is `paid_deleted_account`. This holds for the same
    event and for the same payment seen from its other source. `record_payment` therefore records the refund owed
    again, idempotently: the same item, with `occurrences` + 1.
  - A payment made before the deletion is still a `duplicate`, so no false obligation is created.
  - A redelivery of the recorded payment to a refunded order is also a duplicate, not `not_payable`.
  - Tests:
    - `test_p1_1_a_refund_owed_for_a_deleted_account_survives_a_failed_first_record`: the first item write fails,
      so the answer is 503. The retry answers 200 `paid_deleted_account` and creates one item. A third delivery
      gives `occurrences = 2`.
    - `test_p1_1_a_payment_made_before_the_account_was_deleted_owes_no_refund_on_redelivery`.
- **P1-2.**
  - `payment_recorded` is removed from every administrator rule.
  - The CHECK `ck_billing_item_payment_recorded` allows it only with `resolved_by = 'reconciler'`.
  - The guard trigger refuses it unless the named order is `paid` or `refunded`.
  - An administrator's `refund_confirmed` or `reversal_confirmed` of `provider_paid_unrecorded` settles that
    order's provider lookup in the same transaction (`provider_settled_at`, `next_lookup_at = NULL`).
  - The durable disposition is the resolved item plus the settled order. The order is not asked again, so the
    obligation is never reopened.
  - The resolution still moves no money and changes no access.
  - Tests:
    - `test_p1_2_payment_recorded_is_the_reconcilers_statement_and_needs_the_paid_order`. The write is refused by
      the repository, by the CHECK when it is made directly, and by the trigger when the reconciler makes it while
      the order is unpaid.
    - `test_p1_2_a_confirmed_refund_settles_the_order_so_the_next_paid_lookup_does_not_reopen_it`.
- **P1-3.**
  - `_settle` re-reads the order after the provider call and decides on that fresh state.
  - CANCELLED settles only when the conditional `mark_cancelled` actually cancelled. Otherwise it records
    `provider_state_unresolved` and keeps asking.
  - "Recorded" means `paid` or `refunded`.
  - `pull_candidates` and the partial index `ix_billing_orders_pull` keep a `refunded` order whose confirming
    lookup is still due.
  - Deviation 5 behaves as approved.
  - Tests:
    - `test_p1_3_a_webhook_during_the_lookup_is_never_overwritten_by_cancelled`.
    - `test_p1_3_a_refund_before_the_confirming_lookup_keeps_that_lookup`: the overpayment is still found after
      the refund.
    - `test_p1_3_a_refunded_order_confirmed_paid_is_settled_without_a_false_anomaly`.
    - `test_p1_3_a_payment_and_refund_during_the_lookup_are_decided_on_the_order_as_it_is_now`. This test catches
      the stale-snapshot mutant. The CANCELLED race alone is already held by the conditional update.
- **Evidence** (local execution, not CI):
  - SQLite targeted: 598 passed, 1 skipped.
  - Throwaway PostgreSQL 16: 491 run, 490 passed, 1 failed (INHERITED #160).
  - Mutations: 17/17 caught on `1f73d4fa`; the table is in `docs/billing/PR-MON-3_REVIEW_REQUEST.md`.

