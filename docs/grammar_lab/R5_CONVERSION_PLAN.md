# Grammar Lab — chuyển đổi R5: danh mục, thay đổi, ước tính (đề xuất, chờ người duyệt)

29/09/2026 · nhánh `feature/grammar-lab-pipeline`. **Chưa sinh điểm nào, chưa gọi provider nào.**
Hướng của người: R5 là nguyên liệu thô; cấu trúc lại, sửa, bổ sung theo contract v0.4 rồi thay R5
trong app; phủ A1–C2 và HSK 1–9 (`SPEC.md` §4, §8). Chi tiết từng thay đổi: `r5_conversion_map.tsv`
(một dòng cho mỗi thay đổi; bài không có dòng là chuyển đổi 1-1).

## 1. Danh mục gốc là bao nhiêu

`grammar_curriculum.json` có 269 (EN) / 239 (ZH) **dòng**, không phải số điểm:

| | Dòng | Bài `lesson` (điểm ngữ pháp) | Không phải điểm |
| --- | --- | --- | --- |
| EN | 269 | **228** | 35 `review` + 6 `checkpoint` |
| ZH | 239 | **197** | 42 (ôn tập/kiểm tra) |

Danh mục gốc = 228 + 197 = **425 bài**. Ôn tập/kiểm tra là buổi luyện gồm các bài khác nên không
vào danh mục. Cần người xác nhận cách đếm này.

## 2. Thay đổi so với R5

Đếm từ `r5_conversion_map.tsv` (script đếm kiểm mọi id khớp R5, không id lạ):

| Hành động | EN | ZH | Ý nghĩa |
| --- | --- | --- | --- |
| Chuyển 1-1 (không dòng nào) | 184 | 140 | giữ nguyên phạm vi, chỉ cấu trúc lại |
| **Gộp** (`merge`) | 30 | 36 | bài trùng phạm vi, hoặc cùng tiêu đề ở hai cấp; bài nguồn biến mất, id R5 của nó chuyển hướng |
| **Tách** (`split`) | 5 bài → 12 điểm | 4 bài → 8 điểm | một bài ôm hai ba cách dùng; +7 EN, +4 ZH điểm |
| **Đổi cấp** (`relevel`) | 7 | 3 | đề xuất, xem §3 |
| **Thu hẹp** (`rescope`) | 5 | 1 | bài giữ nhưng bỏ phần đã có ở bài khác |
| **Loại** (`remove`) | 9 | 17 | không phải điểm ngữ pháp: kỹ năng biên tập/dịch, bài ôn tập, danh sách từ vựng, nhãn loại câu, ghi chú lỗi của người Việt (chuyển vào `common_mistakes.l1`) |
| **Thêm** (`add`) | 19 | 23 | điểm mà khung chuẩn có và R5 không có (gồm điểm bộ lõi R5 thiếu) |
| **Tổng điểm sau chuyển đổi** | **215** | **171** | 386 |

Số theo cấp (R5 → sau chuyển đổi). **Bảng EN dưới đây đã được sửa trên nhánh research sau khi thực thi `r5_conversion_map.tsv`; bảng cũ bị lệch 1 điểm ở A1/A2 và B2/C1:**

| EN | A1 | A2 | B1 | B2 | C1 | C2 | Tổng |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R5 | 25 | 32 | 50 | 51 | 38 | 32 | 228 |
| Sau | 30 | 38 | 55 | 44 | 30 | 18 | 215 |

| ZH | HSK1 | HSK2 | HSK3 | HSK4 | HSK5 | HSK6 | HSK7-9 | Tổng |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R5 | 20 | 24 | 24 | 28 | 32 | 39 | 30 | 197 |
| Sau | 28 | 36 | 26 | 23 | 25 | 16 | 17 | 171 |

Mọi cấp A1–C2 và HSK 1–9 đều có điểm; không cấp nào rỗng.

**Các chỗ đáng chú ý**
- **Tiêu đề trùng ở hai cấp** (R5 lặp cùng bài ở B1 và B2, hoặc B2 và C1): `Future continuous`,
  `Future perfect`, `Mixed conditionals`, `Negative adverbial inversion`; ZH: `以……为……`,
  `把/被 phức`, bổ ngữ thời lượng và động lượng ở HSK2 và HSK3, `关于/对于` ở ba cấp, `以便/以免`,
  `尽管/固然` ở hai cấp.
- **Nhãn loại thay cho điểm** (ZH HSK5 "并列/递进/转折/因果/条件/假设复句 nâng cao", HSK6 "discourse
  connectors by relation"): nội dung đã nằm ở các điểm liên từ cụ thể, nên loại nhãn.
- **Kỹ năng biên tập, không phải điểm** (EN C2 "Precision editing" 8 bài; ZH `Long sentence parsing`,
  `Compression and expansion`, `Ambiguity diagnosis`, `Style transformation`, …): đề xuất chuyển sang
  Writing, không giữ ở ngữ pháp. Quyết định của người.
- **Bài ôm nhiều hình thức** được tách: mạo từ `a/an/the` (thành `a_an`, `the`, `zero`), số nhiều,
  sở hữu (`possessive adjectives / pronouns / 's`), `and/but/or` với `because/so`, `can/could`, `不`
  với `没`, `吗` với `呢`, `会` với `能/可以`, lặp động từ với lặp tính từ. Các chỗ tách bộ lõi đã
  đề xuất được giữ.
- **HSK 7-9** (30 bài R5, phần lớn trừu tượng): chỉ thay đổi ở chỗ trùng rõ. Đề cương HSK 3.0 có danh
  sách mục riêng cho cấp 7-9 mà tôi chưa đọc; số điểm cuối cùng ở cấp này **chưa biết** và có thể lớn
  hơn 17 nhiều.

## 3. Độ tin cậy của các thay đổi — phải nói rõ

Việc đối chiếu với khung chuẩn **chưa làm** (cần đọc nguồn, mục 4). Các thay đổi dựa trên gì:

- **Chắc, từ chính R5** (không cần khung): gộp bài trùng hệt tiêu đề, loại bài không phải điểm, tách
  bài ôm nhiều hình thức. 107 trên 159 dòng của map (khoảng hai phần ba) thuộc nhóm này.
- **Đề xuất theo hiểu biết, chưa đối chiếu nguồn**: `relevel` (10 dòng) và `add` (42 dòng) — 52 dòng, khoảng một phần ba map — cùng một số
  `merge` mà hai bài khác cấp (ví dụ đảo ngữ về C1). Đây là các dòng cần đối chiếu Core Inventory /
  đề cương HSK 3.0 trước khi coi là đúng. Những chỗ dựa vào nguồn thứ cấp đã ghi trong `note` của map.
- **Chưa thể đánh giá** mà không đọc nguồn: bài R5 "sai cấp" ở B1–C2 (EN) và HSK3–6 (ZH), và điểm
  thiếu ở các cấp cao. Con số 42 điểm thêm gần như chắc chắn **thiếu** ở B2 trở lên và HSK4 trở lên,
  vì bản thân tôi chỉ liệt được những điểm cơ bản từ trí nhớ.

## 4. Nguồn và cách đối chiếu (sau khi người duyệt, trước khi sinh)

1. **HSK 3.0**: chỉ các trang ngữ pháp của đề cương (bản quét ảnh) → Gemini đọc ảnh, một model khác
   model của engine, giữ khoá `gemini-text`, không OCR trên máy. Đầu ra là danh sách mục theo cấp,
   người đối chiếu với map. Số trang chưa biết (ước một vài chục); mỗi trang một lượt đọc.
2. **Core Inventory tiếng Anh**: tải bản công khai miễn phí của British Council/EAQUALS; EGP theo điều
   khoản sử dụng. Không mua sách.
3. Kết quả: cập nhật `r5_conversion_map.tsv` (điền lại `relevel`/`add`, thêm bài thiếu ở cấp cao), rồi
   người duyệt danh mục **một lần**, sau đó mới `inventory/{en,zh}.yaml` và sinh.

## 5. Ước tính cho toàn bộ danh mục (386 điểm)

Đơn vị đo từ các lượt chạy 28/09 (`CORE_CATALOG_PROPOSAL.md`); phần chưa đo ghi rõ.

**Giả định:** mỗi điểm 1,5 lượt sinh; sinh `vi` + `en` cùng lúc (output ≈ ×1,6) và nạp bài R5 làm
đầu vào (≈ +25% token vào): DeepSeek ≈ **×2** so với lượt vi-only đã đo. Engine không phụ thuộc số
locale (chỉ chấm câu tiếng đích). `zh` locale để đợt sau, không tính ở đây.

| | EN (215) | ZH (171) | Tổng (386) |
| --- | --- | --- | --- |
| DeepSeek sinh | ≈ $2.0 | ≈ $2.3 | **≈ $4.3** (trần đề xuất $8) |
| Lượt engine (Gemini, ≈ 24/điểm) | ≈ 5 200 | ≈ 4 100 | ≈ 9 300 |
| Lượt Groq (≈ 9/điểm, gồm xác nhận chỗ sửa R5) | ≈ 1 900 | ≈ 1 500 | ≈ 3 400 |
| Đọc HSK 3.0 bằng Gemini ảnh | — | ≤ vài chục lượt (chưa biết số trang) | — |

**Thời gian**
- **Gói miễn phí:** nút cổ chai là engine, 500 lượt/model/ngày, dùng chung nhóm `gemini-text` với
  lane khác → khoảng **20 điểm/ngày → 19–20 ngày**. Nếu lane khác dùng quota, lâu hơn. Việc đọc HSK
  bằng model khác không ăn quota của model engine.
- **Có billing:** sinh + verify xong trong **1–2 ngày**, giới hạn bởi tốc độ DeepSeek (30–60 giây/điểm,
  dài hơn ở C1/C2 và HSK5+ vì bài R5 dài hơn khoảng 15–25%) và tốc độ engine.

**Chi phí engine khi có billing:** *chưa đo được* (telemetry `admin/ai/operations` của sandbox trống).
Ước thô ≈ $0.0005/lượt chấm theo giá niêm yết flash-lite → **≈ $4–5** cho 9 300 lượt; con số này cần
đo trước khi dựa vào. Tổng có billing ≈ **$9** (gồm DeepSeek), sai số lớn ở phần engine.

**Người phải duyệt** (mọi điểm cần duyệt; phút/điểm là **giả định của tôi**, không phải số đo):

| Nhóm cấp | Số điểm | Phút/điểm | Giờ |
| --- | --- | --- | --- |
| EN A1–A2 | 68 | 4 | 4,5 |
| EN B1–B2 | 98 | 6 | 9,8 |
| EN C1–C2 | 49 | 9 | 7,4 |
| ZH HSK1–3 | 90 | 4 | 6,0 |
| ZH HSK4–5 | 48 | 6 | 4,8 |
| ZH HSK6, 7–9 | 33 | 9 | 5,0 |
| **Tổng** | **386** | | **≈ 37 giờ** |

Duyệt tiếng Trung cần người đọc được tiếng Trung; tôi không có thông tin về người đó. Mỗi thêm 10
điểm HSK 7-9 (khi đọc xong đề cương) ≈ +$0.13 DeepSeek, +240 lượt engine, +1,5 giờ duyệt.

**Chặn còn lại cho ZH:** engine đã đổi giới hạn độ dài tối thiểu theo ngôn ngữ (`codex/work`, đã
merge vào nhánh này, chưa build lại image hay verify). Câu ZH ngắn vẫn ở trạng thái "chưa verify được
bằng engine" cho tới lần verify sau; không đổi số ước tính.

## 6. Cần người quyết trước khi sinh

1. Cách đếm danh mục gốc (425 bài, bỏ ôn tập/kiểm tra) và danh sách gộp/tách/loại trong map.
2. Kỹ năng biên tập (EN C2 "Precision editing", ZH tương ứng): chuyển sang Writing (đề xuất) hay giữ ở
   ngữ pháp.
3. Cho phép đọc HSK 3.0 bằng Gemini ảnh và tải Core Inventory để đối chiếu cấp và điểm thiếu, rồi cập
   nhật map (mục 4), trước khi khoá danh mục.
4. Gói miễn phí (≈ 20 ngày) hay billing (1–2 ngày, ≈ $9, engine chưa đo).
5. Ai duyệt ZH, và bao nhiêu điểm mỗi ngày.

## 7. Cập nhật 30/09/2026 (sau quyết định của người ngày 29/09)

- **Đợt "chắc" đã có seed**: `inventory/seeds_en.yaml` (56 điểm EN A1–A2) và `seeds_zh.yaml` (43 điểm ZH HSK 1–2), tức
  99 điểm là các dòng R5 giữ nguyên, gộp, tách, thu hẹp. Dòng đổi cấp (`relevel`) và dòng thêm (`add`) chờ khoá danh mục,
  nên `en.past_simple`, `en.can.ability`, `zh.le_change`, `zh.modal.hui`... chưa nằm trong seed.
- **Quy trình mới bỏ verify bằng engine lúc sinh** (blind-solve tắt mặc định). Engine chỉ chấm `common_mistakes` và
  `quick_practice` sau review (`engine-grade`): khoảng **11 lượt/điểm** (mẫu A1: 54 lượt cho 5 điểm), không phải 24.
- **Đính chính đơn giá engine.** Bản trên ghi ≈ $0.0005/lượt; với bảng giá trong `llm_client.py` (Gemini flash-lite
  $0.30 vào / $2.50 ra mỗi triệu token, ~2 000 vào + 500 ra mỗi lượt) là **≈ $0.0019/lượt**. Chấm engine cho cả 386 điểm
  ≈ 4 200 lượt ≈ **$8** (chưa đo thực), không phải $4–5.
- **Sinh** (DeepSeek, `vi` + `en`, có `sub` và `personal_production`): ≈ $0.015/điểm → đợt 99 điểm ≈ $1.5, cả 386 điểm ≈ $6.
  Ước tính, chưa đo; lệnh `generate` báo chi phí thực và dừng ở `--cost-ceiling-usd`.
- **Đọc đề cương HSK 3.0**: phụ lục ngữ pháp là **trang 176–260 (85 trang)** của file quét 260 trang (gov.cn, không có lớp chữ),
  nhiều hơn "vài chục" nên chờ người cho phép trước khi gọi Gemini ảnh. Core Inventory (bản 2011, công khai) đã trích
  xong: `inventory/raw/core_inventory_en.csv`, 277 dòng mã + bậc, dùng làm `source_anchors` cho điểm EN.
