# Grammar Lab — danh mục bộ lõi (đề xuất, chờ người duyệt)

28/09/2026 · nhánh `feature/grammar-lab-pipeline`. Tiếng Anh A1–A2, tiếng Trung HSK 1–2.
**Không dựa vào R5.** Chưa sinh điểm nào theo danh mục này; khi duyệt, danh mục vào
`grammar_lab/inventory/{en,zh}.yaml` (SPEC §4) và sinh theo lô.

## Nguồn và độ tin cậy

| Nhóm | Nguồn | Đã kiểm được gì |
| --- | --- | --- |
| Tiếng Trung | 《国际中文教育中文水平等级标准》GF 0025-2021 (Bộ Giáo dục TQ, 2021), phụ lục A 语法等级大纲 | **Đã kiểm:** cấp 1 có 48 mục ngữ pháp, cấp 2 thêm 81 (cộng dồn 129). Nguồn thứ cấp (chưa đọc tận mắt): 了1 và 了2 đều ở cấp 1; 是……的 ở cấp 2; 把字句, 被字句 ở cấp 3 |
| Tiếng Anh | British Council/EAQUALS *Core Inventory for General English* (2nd ed., 2015), phần ngữ pháp A1, A2; *English Grammar Profile* (Cambridge) | **Đã kiểm:** tài liệu tồn tại và phủ A1–C1. Danh sách của trang LearnEnglish "A1–A2 grammar" (British Council) đọc được nhưng không tách A1/A2 |

**Giới hạn phải biết.** Bản chuẩn HSK 3.0 chính thức là PDF **ảnh quét** (không có lớp chữ);
PDF Core Inventory không đọc được bằng công cụ hiện có; EGP Online trả 404. Vì vậy cột "Cấp"
dưới đây là **đề xuất theo hiểu biết về hai khung**, đánh dấu:
`✓` khớp nguồn đã kiểm ở trên · `~` cần đối chiếu từng mục trước khi sinh. Tôi đề nghị đối
chiếu bằng một trong hai cách: người cho phép tải PDF Core Inventory (British Council, công
khai) và OCR bản quét HSK 3.0, hoặc dùng *语法学习手册* (NXB Đại học Ngôn ngữ Bắc Kinh, dựng
trên phụ lục A — sách trả phí).

Cột **Minh hoạ** là loại theo `point_type` của contract: `timeline` (thì/thể), `word_order`,
`morphology`, `none` (loại `other`). **So sánh** là các `contrasts` (phải có trong danh mục).
Điểm đã có trong repo đánh dấu **(có)**.

## Tiếng Anh — 49 điểm (A1: 27, A2: 22)

### Danh từ, mạo từ, từ hạn định

| id | Tiêu đề | Cấp | Minh hoạ | So sánh |
| --- | --- | --- | --- | --- |
| `en.plural_nouns.regular` **(có)** | Danh từ số nhiều -s/-es | A1 ~ | morphology | `.irregular` |
| `en.plural_nouns.irregular` | Số nhiều bất quy tắc (men, children) | A1 ~ | none | `.regular` |
| `en.articles.a_an` **(có)** | Mạo từ không xác định a/an | A1 ~ | none | `.the` |
| `en.articles.the` **(có)** | Mạo từ xác định the | A2 ~ | none | `.a_an`, `.zero` |
| `en.articles.zero` | Không dùng mạo từ (nói chung, số nhiều/không đếm được) | A2 ~ | none | `.the` |
| `en.demonstratives` | this/that/these/those | A1 ~ | none | `en.articles.the` |
| `en.pronouns.subject_object` | I/me, he/him… | A1 ~ | none | `en.possessive_adjectives` |
| `en.possessive_adjectives` | my/your/his… | A1 ~ | none | `en.possessive_s`, `en.pronouns.subject_object` |
| `en.possessive_s` | Sở hữu 's | A1 ~ | morphology | `en.possessive_adjectives` |
| `en.countable_uncountable.a_some` | Đếm được / không đếm được: a vs some | A1 ~ | none | `en.quantifiers.much_many` |
| `en.quantifiers.some_any` | some / any | A1 ~ | none | `.much_many` |
| `en.quantifiers.much_many` | much / many (hỏi, phủ định) | A2 ~ | none | `.a_lot_of`, `en.countable_uncountable.a_some` |
| `en.quantifiers.a_lot_of` | a lot of / lots of | A2 ~ | none | `.much_many` |

**Tách:** điểm có sẵn `en.countable_uncountable.much_many` ôm hai việc (phân loại danh từ và
much/many) → thành `en.countable_uncountable.a_some` + `en.quantifiers.much_many`. Điểm cũ bị
thay.

### Động từ, thì

| id | Tiêu đề | Cấp | Minh hoạ | So sánh |
| --- | --- | --- | --- | --- |
| `en.be.present` | be: am/is/are | A1 ✓ | none | `en.have_got` |
| `en.be.questions_negatives` | be: câu hỏi, phủ định | A1 ~ | word_order | `en.present_simple.do_questions` |
| `en.present_simple.habit` | Hiện tại đơn: thói quen, sự thật | A1 ✓ | timeline (habit) | `en.present_continuous.now` |
| `en.present_simple.third_person_s` **(có)** | Thêm -s/-es với he/she/it | A1 ✓ | morphology | `.habit` |
| `en.present_simple.do_questions` | do/does: câu hỏi, phủ định | A1 ~ | word_order | `en.be.questions_negatives` |
| `en.adverbs_of_frequency` | always/usually… và vị trí | A1 ~ | word_order | `en.present_simple.habit` |
| `en.present_continuous.now` **(có)** | Hiện tại tiếp diễn (đang) | A1 ~ | timeline (ongoing_now) | `en.present_simple.habit` |
| `en.have_got` | have got (sở hữu) | A1 ✓ | none | `en.there_is_are`, `en.be.present` |
| `en.there_is_are` **(có)** | There is / There are | A1 ✓ | word_order | `en.have_got` |
| `en.can.ability` | can / can't (khả năng) | A1 ~ | none | `en.could.past_ability` |
| `en.imperatives` | Câu mệnh lệnh | A1 ~ | word_order | `en.can.ability` |
| `en.would_like` | would like (lịch sự) vs want | A1 ~ | none | `en.verb_ing_or_to` |
| `en.past_simple.be` | was / were | A1 ~ | none | `en.past_simple.regular_ed` |
| `en.past_simple.regular_ed` | Quá khứ đơn: -ed | A2 ~ | morphology | `.irregular` |
| `en.past_simple.irregular` | Quá khứ đơn: động từ bất quy tắc | A2 ~ | none | `.regular_ed` |
| `en.past_simple` **(có)** | Quá khứ đơn: cách dùng (việc đã xong, có thời điểm) | A2 ✓ | timeline (point_past) | `en.present_perfect.experience`, `en.past_continuous` |
| `en.past_simple.did_questions` | did: câu hỏi, phủ định | A2 ~ | word_order | `en.present_simple.do_questions` |
| `en.past_continuous` | Quá khứ tiếp diễn | A2 ✓ | timeline (past_ongoing) | `en.past_simple` |
| `en.present_perfect.experience` **(có)** | Hiện tại hoàn thành (trải nghiệm) | A2 ~ | timeline (unspecified_past) | `en.past_simple` |
| `en.going_to.plans` | be going to (dự định) | A2 ~ | timeline (future_plan) | `en.will.decisions`, `en.present_continuous.arrangements` |
| `en.will.decisions` | will (quyết định tức thì, dự đoán) | A2 ~ | timeline (future_plan) | `en.going_to.plans` |
| `en.present_continuous.arrangements` | Hiện tại tiếp diễn cho lịch đã hẹn | A2 ~ | timeline (future_plan) | `en.going_to.plans` |
| `en.could.past_ability` | could (khả năng trong quá khứ) | A2 ~ | none | `en.can.ability` |
| `en.modals.have_to_must` | have to / must | A2 ~ | none | `en.modals.should` |
| `en.modals.should` | should (lời khuyên) | A2 ~ | none | `en.modals.have_to_must` |
| `en.verb_ing_or_to` | like doing / want to do | A2 ✓ | none | `en.would_like` |
| `en.infinitive_of_purpose` | to + V chỉ mục đích | A2 ✓ | none | `en.conjunctions.because_so` |

**Tách:** `en.past_simple` (có) chỉ còn cách dùng; hình thức tách thành `.regular_ed`,
`.irregular`, `.did_questions`, `en.past_simple.be`. Nội dung của điểm cũ sẽ được sinh lại theo
phạm vi hẹp hơn.

### Tính từ, trạng từ, giới từ, câu

| id | Tiêu đề | Cấp | Minh hoạ | So sánh |
| --- | --- | --- | --- | --- |
| `en.adjectives.position` | Tính từ đứng trước danh từ (ngược tiếng Việt) | A1 ~ | word_order | `en.adverbs.manner_ly` |
| `en.comparatives` **(có)** | So sánh hơn | A2 ✓ | morphology | `en.superlatives` |
| `en.superlatives` | So sánh nhất | A2 ~ | morphology | `en.comparatives` |
| `en.adverbs.manner_ly` | Trạng từ chỉ cách thức -ly | A2 ~ | morphology | `en.adjectives.position` |
| `en.prepositions.time` | at / on / in (thời gian) | A1 ✓ | none | `.place` |
| `en.prepositions.place` | in / on / at (nơi chốn) | A1 ✓ | none | `.time` |
| `en.questions.wh` | Câu hỏi Wh- | A1 ✓ | word_order | `en.present_simple.do_questions` |
| `en.conjunctions.and_but_or` | and / but / or | A1 ~ | none | `.because_so` |
| `en.conjunctions.because_so` | because / so | A2 ~ | none | `.and_but_or`, `en.infinitive_of_purpose` |

Ngoài bộ lõi, giữ nguyên trong repo: `en.conditional_first` (**B1**).

## Tiếng Trung — 50 điểm (HSK 1: 26, HSK 2: 24)

HSK 3.0 đếm cả mục từ loại (ví dụ từng nhóm đại từ) — 129 mục của cấp 1–2 gộp lại thành các
điểm dạy được dưới đây. Mục từ vựng thuần (danh sách đại từ, số đếm) không thành điểm riêng.

### HSK 1

| id | Tiêu đề | Cấp | Minh hoạ | So sánh |
| --- | --- | --- | --- | --- |
| `zh.shi_sentence` | Câu chữ 是 | 1 ~ | word_order | `zh.adjective_predicate` |
| `zh.adjective_predicate` | Tính từ làm vị ngữ (很 + tính từ, không 是) | 1 ~ | word_order | `zh.shi_sentence` |
| `zh.you_sentence` | 有: có, sở hữu, tồn tại | 1 ~ | word_order | `zh.zai_location` |
| `zh.zai_location` | 在 làm động từ: ở đâu | 1 ~ | word_order | `zh.you_sentence`, `zh.zai_place_before_verb` |
| `zh.zai_place_before_verb` | 在 + nơi chốn đứng trước động từ | 1 ~ | word_order | `zh.zai_location` |
| `zh.time_before_verb` | Thời gian đứng trước động từ | 1 ~ | word_order | `zh.zai_place_before_verb` |
| `zh.dates_times` | Thứ tự năm-tháng-ngày, giờ | 1 ~ | word_order | `zh.time_before_verb` |
| `zh.bu_negation` | Phủ định với 不 | 1 ~ | none | `zh.mei_negation` |
| `zh.mei_negation` | Phủ định với 没(有) | 1 ~ | none | `zh.bu_negation` |
| `zh.ma_question` | Câu hỏi 吗 | 1 ~ | word_order | `zh.question_words` |
| `zh.question_words` | Từ để hỏi tại chỗ (什么, 谁, 哪儿, 几, 多少) | 1 ~ | word_order | `zh.ma_question` |
| `zh.ne_question` | 呢: hỏi lại (你呢？) | 1 ~ | none | `zh.ma_question` |
| `zh.ba_suggestion` | 吧: đề nghị, phỏng đoán | 1 ~ | none | `zh.ma_question` |
| `zh.de_possessive` | 的 sở hữu / bổ nghĩa | 1 ~ | word_order | `zh.de_di_de` |
| `zh.measure_words.basic` | Lượng từ cơ bản (个, 本, 口…) | 1 ~ | word_order | `zh.liang_er` |
| `zh.liang_er` | 两 vs 二 | 1 ~ | none | `zh.measure_words.basic` |
| `zh.demonstratives` | 这/那 + lượng từ | 1 ~ | word_order | `zh.measure_words.basic` |
| `zh.modal.hui` | 会 (biết làm, do học) | 1 ~ | none | `zh.modal.neng` |
| `zh.modal.xiang_yao` | 想 / 要 (muốn) | 1 ~ | none | `zh.modal.hui` |
| `zh.le_completion` **(có)** | 了 sau động từ: hoàn thành (了1) | 1 ✓ | timeline (point_past) | `zh.guo_experience`, `zh.le_change` |
| `zh.le_change` | 了 cuối câu: thay đổi, tình huống mới (了2) | 1 ✓ | none | `zh.le_completion` |
| `zh.zai_progressive` | 在/正在 + động từ (呢): đang | 1 ~ | timeline (ongoing_now) | `zh.zhe_state` |
| `zh.tai_le` | 太……了 | 1 ~ | none | `zh.adjective_predicate` |
| `zh.ye_dou` | 也 / 都 đứng trước động từ | 1 ~ | word_order | `zh.he_conjunction` |
| `zh.he_conjunction` | 和 chỉ nối danh từ, không nối câu | 1 ~ | none | `zh.ye_dou` |
| `zh.serial_verbs.qu_lai` | 去/来 + nơi + làm gì | 1 ~ | word_order | `zh.zai_place_before_verb` |

**Tách:** 了 thành hai điểm theo đúng hai mục của HSK 3.0 (了1, 了2).

### HSK 2

| id | Tiêu đề | Cấp | Minh hoạ | So sánh |
| --- | --- | --- | --- | --- |
| `zh.guo_experience` **(có)** | 过: đã từng | 2 ~ | timeline (unspecified_past) | `zh.le_completion` |
| `zh.zhe_state` | 着: trạng thái kéo dài | 2 ~ | timeline (ongoing_now) | `zh.zai_progressive` |
| `zh.shi_de` | 是……的: nhấn thời gian, nơi, cách của việc đã xảy ra | 2 ✓ | word_order | `zh.le_completion` |
| `zh.yao_le` | 要……了 / 快要……了: sắp | 2 ~ | timeline (future_plan) | `zh.le_change` |
| `zh.bi_comparison` | So sánh với 比 | 2 ~ | word_order | `zh.meiyou_comparison`, `zh.gen_yiyang` |
| `zh.meiyou_comparison` | 没有 + ……: không bằng | 2 ~ | word_order | `zh.bi_comparison` |
| `zh.gen_yiyang` | 跟……一样 | 2 ~ | word_order | `zh.bi_comparison` |
| `zh.complement.degree_de` | Bổ ngữ trình độ: V 得 + tính từ | 2 ~ | word_order | `zh.de_di_de` |
| `zh.complement.result` | Bổ ngữ kết quả (完, 好, 到, 懂) | 2 ~ | none | `zh.le_completion` |
| `zh.complement.direction_simple` | Bổ ngữ xu hướng đơn (来/去) | 2 ~ | none | `zh.serial_verbs.qu_lai` |
| `zh.complement.duration` | Thời lượng: 学了两年 | 2 ~ | word_order | `zh.complement.frequency` |
| `zh.complement.frequency` | Số lần: 去过两次 | 2 ~ | word_order | `zh.complement.duration` |
| `zh.de_di_de` | 的 / 地 / 得 | 2 ~ | none | `zh.de_possessive`, `zh.complement.degree_de` |
| `zh.modal.neng` | 能 / 可以 (có thể, được phép) | 2 ~ | none | `zh.modal.hui` |
| `zh.youdian_yidian` | 有点儿 vs 一点儿 | 2 ~ | word_order | `zh.tai_le` |
| `zh.verb_reduplication` | Lặp động từ (看看, 休息休息) | 2 ~ | morphology | `zh.youdian_yidian` |
| `zh.haishi_huozhe` | 还是 (hỏi lựa chọn) vs 或者 | 2 ~ | none | `zh.ma_question` |
| `zh.yinwei_suoyi` | 因为……所以…… | 2 ~ | none | `zh.suiran_danshi` |
| `zh.suiran_danshi` | 虽然……但是…… | 2 ~ | none | `zh.yinwei_suoyi` |
| `zh.cong_dao` | 从……到…… | 2 ~ | word_order | `zh.zai_place_before_verb` |
| `zh.gei_dui` | 给 / 对 + người + động từ | 2 ~ | word_order | `zh.zai_place_before_verb` |
| `zh.bie_imperative` | 别 / 不要 (đừng) | 2 ~ | none | `zh.bu_negation` |
| `zh.jiu_cai` | 就 vs 才 (sớm/muộn so với dự kiến) | 2 ~ | none | `zh.yao_le` |
| `zh.yibian` | 一边……一边…… | 2 ~ | none | `zh.zai_progressive` |

Ngoài bộ lõi, giữ nguyên trong repo: `zh.ba_construction` (**HSK 3**, khớp nguồn thứ cấp đặt
把字句 ở cấp 3). 被字句 cũng ở cấp 3 → không vào bộ lõi.

## Ước tính

**Số điểm.** EN 49 (9 đã có; `en.past_simple` sinh lại theo phạm vi hẹp; `en.countable_uncountable.much_many`
bị thay bằng hai điểm mới), ZH 50 (2 đã có). Cần sinh mới **88** điểm, sinh lại 1 → **89** lượt
chạy.

**Mỗi điểm cần** (đo từ các lượt chạy 28/09):
- DeepSeek sinh: trung bình **$0.0031** (EN) / **$0.0044** (ZH) một lượt; tính 1,5 lượt/điểm
  cho các lần sinh lại có ghi chú.
- Engine (Gemini `gemini-3.5-flash-lite` trong sandbox): **14–17 lượt chấm** một lần verify
  (ví dụ 3–5, common_mistakes 2–4, quick_practice ~8); tính 1,5 lần verify/điểm → **~24 lượt**.
- Groq (blind-solve + công thức + đáp án sai): **5 lượt** một lần verify → ~8/điểm.

| | EN (41 điểm cần chạy) | ZH (48) | Tổng (89) |
| --- | --- | --- | --- |
| DeepSeek | ≈ $0.19 | ≈ $0.32 | **≈ $0.51** (trần đề xuất $1) |
| Lượt engine | ≈ 980 | ≈ 1 150 | ≈ 2 130 |
| Lượt Groq | ≈ 330 | ≈ 380 | ≈ 710 |

**Thời gian theo quota hiện tại.** Nút cổ chai là engine: quota miễn phí Gemini **500 lượt/
model/ngày** (reset 07:00 UTC), dùng chung nhóm `gemini-text` với lane khác. 2 130 lượt ≈
**4–5 ngày quota** nếu Grammar Lab dùng hết phần quota; thực tế **~20 điểm/ngày → 4–5 ngày** cho
bộ lõi. DeepSeek sinh cả 89 điểm mất khoảng 1–1,5 giờ (30–60 giây/điểm); Groq nằm trong free
tier nếu giới hạn ngày của nó như tôi hiểu (chưa đo). Thời gian người duyệt từng điểm không tính.

**Chi phí engine.** Ở free tier: $0, bị giới hạn bởi quota như trên. Nếu chuyển sang trả phí để
chạy trong một ngày: chưa đo được (telemetry `admin/ai/operations` của sandbox trống); ước
thô ~2 000 token vào / ~500 ra một lượt chấm → cỡ **$1** cho cả bộ theo giá niêm yết của
flash-lite — con số này cần đo trước khi dựa vào.

**Chặn trước khi chạy ZH.** Engine từ chối văn bản dưới 10 ký tự (422): ở lượt verify ZH vừa
rồi 31/43 cờ là lỗi này, nên verify ZH chưa có nghĩa. Cần quyết: prompt yêu cầu câu ZH ≥ 10 ký
tự, hoặc sửa giới hạn phía engine của app. Nếu không, verify ZH chủ yếu cho ra cờ
`evaluator_error`.

## Cần người quyết khi duyệt

1. Danh sách và các chỗ tách (mạo từ, much/many, past simple, 了).
2. Có cho đối chiếu từng mục với nguồn (tải PDF Core Inventory, OCR bản HSK 3.0) trước khi sinh
   không — hiện phần lớn cột "Cấp" là `~`.
3. Cách xử lý câu ZH ngắn với engine (mục trên).
4. Chạy theo lô bao nhiêu điểm một ngày (mặc định ~20, trong quota).
