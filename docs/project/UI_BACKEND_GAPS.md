# Canonical UI ↔ backend tracker

## Governance

Purpose: the single tracker of what the Canonical UI Baseline needs from the
backend, API, data and business logic, and where each need stands. Authority:
D-066. The baseline (`docs/design/canonical-ui/`) decides the interface and the
data it shows; the backend adapts. A gap is worked, never a reason to remove,
move or redesign a component. Change when a requirement, a contract or a status
changes. Do not store secrets, screenshots or unverified claims. This file
replaces the D-060 backlog (GAP-001..052) and absorbs the 2026-09-21 audit; it
is the only tracker, so no audit file may run beside it.

Rules:

- **Metric rule (D-066 rule 4).** A metric the baseline draws that has no
  measured value renders `0` in its canonical component. The `0` is a UI
  fallback and is never stored, sent or counted as a measurement; the read model
  carries `measured: false`. Demo figures never ship.
- **Status.** `READY` = the slice meets every point of D-066 rule 13 (canonical
  visual on desktop and phone, real data, no production mock, state kept over a
  reload, auth, loading/empty/error/retry, fallback correct, tests pass, no
  duplicate implementation). `IN_PROGRESS` = in scope now and unfinished.
  `BLOCKED` = waits on a gate named in the row. Nothing is `READY` until it has
  been run in a browser against the real backend.
- **Gates.** `[REVIEW]` a schema or migration for learner-owned data needs a
  recorded independent architecture review before it is applied to a shared or
  sandbox runtime. `[PROVIDER]` credentials are a human gate. `[CONTENT]` the
  work is supplying content or metadata, not code. `[DEF]` a measurement or rule
  needs an official definition before it is built.
- **Slice.** S1 Word and Sentence Sheet, S2 Writing review and revision, S3
  Listening and Dictation, S4 Reading comprehension per question, S5 catalogue
  Search, L later (learner persistence, progress measurement, pronunciation).
- Every schema field must trace to a row here or to a real business need.

Baseline pin: 2026-09-21, design project
`7a5604ca-1e11-4d8e-8305-7d0cb32d552d`; files and SHA-256 in
`docs/design/canonical-ui/PINS.tsv`. Audit facts below were read from code and
schema on that date at `76e69b9`; none has been run against the baseline UI.

# CHỜ NGƯỜI QUYẾT ĐỊNH — sổ đăng ký mở (cập nhật 2026-09-22)

Đây là **danh sách duy nhất** cần anh duyệt. Mỗi mục ghi rõ đang làm gì và hai lựa chọn, để chỉ
cần chọn chứ không phải đọc lại code. Các mục bên dưới sổ này là **bằng chứng đo đạc theo từng
màn** - số liệu, cái gì đã sửa, sửa theo frame nào - không phải việc đang chờ.

Human, 2026-09-22: "phần này chưa có chức năng thì note lại và tôi sẽ review lại sau và quyết định
các hành động cho nó." Mọi việc dưới đây **đã dừng lại đúng chỗ này**, không tự quyết, không bịa dữ
liệu. Các mục ở trên là ghi chép chi tiết theo từng màn; phần này là danh sách gọn để duyệt.

## A. Nút đã vẽ nhưng chưa có hành vi

| # | Ở đâu | Tình trạng | Cần anh quyết |
| --- | --- | --- | --- |
| A1 | Reader · "Lưu bài" và "Đọc tiếp sau" | Frame cho hai nút **cùng icon bookmark** và không nói hành vi. Đang làm: "Lưu bài" bật/tắt đánh dấu; "Đọc tiếp sau" đánh dấu rồi rời bài. | Hai hành động hay một? Nếu một thì thanh còn 5 nút. |
| A2 | Reader · "Nghe" | Disabled, có title "sắp có". Văn bản chưa có audio đọc. Frame vẽ nút này bật. | Đọc bằng TTS, hay bỏ nút khỏi thanh cho tới khi có audio? |
| A3 | Reader · "Kiểm tra hiểu" | Disabled khi bài không kèm câu hỏi (sách nhập không có). | Sinh câu hỏi bằng AI, hay ẩn nút khi không có? |
| A4 | Listening · "Kiểm tra hiểu" | Cùng câu hỏi, đã treo từ trước. | Như trên. |
| A5 | Book detail · 3 nút icon (bookmark, tải về, ⋯) | Disabled, "sắp có". Frame **không vẽ** chúng. | Xoá theo frame, hay giữ và làm chức năng? |
| A6 | Profile · "Chia sẻ", "Chỉnh sửa", huy hiệu kim cương trên avatar | Frame vẽ cả ba; app chưa có hành vi nào cho chúng nên chưa dựng. | Chia sẻ cái gì và sửa được những gì? Huy hiệu kim cương là bậc, hay là thứ khác? |

## A2. Hồ sơ (Profile) — đã dựng 2026-09-22

Thiết kế **có** màn này, ở `Orena Hạn mức sử dụng.dc.html` (human chỉ chỗ; file **không nằm trong cache**
ghim, phải đọc từ nguồn). Trước đó Profile chỉ là một dialog; nay là một điểm đến `#/profile`, tab thứ năm
trỏ tới nó thay vì mở sheet.

Dựng theo số đo frame, đã verify trong app: hero padding 30 / r20 / gap 30, avatar 132, tên Nunito 34/800,
panel hạn mức rộng 560 padding 26; mobile 390: avatar 96, tên 24, hai cột xếp dọc, không tràn ngang.

**Dữ liệu thật**: gói và hạn mức đọc từ `/api/product/me` - tên gói, giới hạn tháng và số đã dùng cho từng
tính năng. Không mock, không phần trăm bịa.

**Chưa có, nên để trống và nói rõ** (rule 4): **XP** và **chuỗi ngày** - frame vẽ "15 840 XP" và "128 ngày
liên tiếp" nhưng Orena không đếm cái nào. **Khung rank** chờ `tier`. Nút **Chia sẻ / Chỉnh sửa** và huy hiệu
kim cương trên avatar: frame có vẽ, app chưa có hành vi cho chúng - xem A6 bên dưới.

**Mâu thuẫn trong chính thiết kế, cần anh chốt**: `Orena Hạn mức sử dụng` vẽ avatar bằng **vòng
conic-gradient + huy hiệu kim cương**, còn `Orena Rank Frame Master v2` vẽ **khung pha lê nhiều mặt cắt**.
Brief của anh nói rõ là pha lê, nên tôi dựng component pha lê; màn Profile hiện đang để avatar trơn cho tới
khi có `tier`. Hai file vẽ hai thứ khác nhau cho cùng một chỗ.

## B. Thành phần frame vẽ mà app chưa dựng


| # | Ở đâu | Tình trạng |
| --- | --- | --- |
| B1 | **Progress** | **Dựng lại theo frame MỚI** (2026-09-22, sau khi re-pin - frame cũ trong cache đã lệch 22 KB). Frame mới **bỏ hẳn** hàng "Bằng chứng gần nhất", thay bằng **thang cấp bậc 20 bậc** (lưới 4 cột, ô 227x56 r14, ba trạng thái: mở / hiện tại / khoá) + **thẻ CẤP BẬC** (102 cao, pad 16/18, r18). Cột phụ 600 giữ heatmap, hàng kỹ năng **có thanh**, và "Việc nên làm tiếp" là **thẻ có mũi tên** (78 cao, r17, kính tiêu điểm). Ngưỡng 20 bậc lấy từ chính frame: 50 · 150 · 300 · 500 · 700 · 950 · 1200 · 1450 · 1600 · **?** · 3000 · 4500 · 6000 · 8000 · 10000 · 13000 · 16000 · 20000 · 25000 · 30000 từ. **Bậc 10 (Virtuoso) frame không ghi số** - nó vẽ "BẬC HIỆN TẠI" đè lên - nên app hiển thị "—" và không đoán. Còn thiếu so với frame: **hàng 4 panel thứ hai** (Vừa học xong · Từ đang ôn · Kiểm tra hiểu · Nhớ lại) vì cần số liệu ôn tập/hiểu mà backend chưa có (C4). |
| B2 | **Hệ cấp bậc (rank)** | **Component đã dựng** (`ui/rank-frame.js`, port từ "Rank Frame Master v2": 20 bậc, 5 chặng, một nguồn sáng −48°, SVG sinh từ toạ độ cực, không raster; gate `test_orena_rank_frame.mjs`). **Chưa hiện ở đâu** vì `ProgressOverview.tier {name, level, current, target}` chưa ai phục vụ - cần **ngưỡng mỗi bậc**, là quyết định sản phẩm. Ngày có `tier`, khung pha lê hiện luôn, không cần sửa code. Frame: "CẤP BẬC · Virtuoso · bậc 4 · 1 994 / 3 000 từ". Anh muốn rank là **khung avatar** pha lê SVG+CSS, nhiều họ màu. |
| B3 | Book detail · dải từ đã lưu ở hero | Frame đặt "BẠN ĐÃ LƯU TỪ ĐÂY" + chip từ trong hero; app có dữ liệu nhưng để ở cột phải. |
| B5 | **Progress · tab "Xu hướng"** | **ĐÃ DỰNG** (2026-09-22): tab Tổng quan / Xu hướng ở `#/progress?tab=trends`, ba khối *Đang tốt lên · Dựa trên gì · Lỗi lặp lại*. **Mọi con số là 0 / "—"** vì chưa có mô hình xu hướng, mô hình lỗi lặp lại, hay lịch sử theo từng thước đo - `ProgressTrends.json` chưa ai phục vụ. Frame gốc: `Progress trends` (`data-screen-label="Progress trends"` + bản mobile) với các hàng xu hướng và thẻ độ khó. App **chưa có tab nào** để tới đó, và chưa dựng màn. Cần dữ liệu xu hướng theo thời gian (`ProgressTrends.json`) mà backend chưa phục vụ. |
| B6 | **Progress · hàng 4 panel thứ hai** | **ĐÃ DỰNG** (2026-09-22), 4 panel 375x147 pad 16/18 r18 gap 20. *Vừa học xong* và *Từ đang ôn* chạy bằng số thật từ kho từ của học viên; *Kiểm tra hiểu* và *Nhớ lại* render **0** vì chưa có số liệu (C4). Vị trí: **nằm giữa** hàng 3 số lớn và thang cấp bậc, chạy hết chiều ngang: *Vừa học xong* (14 từ · HSK 2 · trong 3 ngày + chip từ) · *Từ đang ôn* (42 từ · 18 chữ tới hạn hôm nay + thanh 24/42) · *Kiểm tra hiểu* (9/11 · câu đúng · 3 bài đọc + dải ô đúng/sai) · *Nhớ lại* (86% · 312 thẻ trong 7 ngày + thanh + 268 nhớ / 31 chưa chắc / 13 quên). Chưa dựng vì cần số liệu ôn tập và hiểu backend chưa có (C4). |
| B4 | Reader · panel bên | Padding 26 / gap 20 của frame chưa khớp (app 22 / 16). Chưa chỉnh vì **nội dung** panel chưa phải của frame. |

## C. Thiếu dữ liệu backend — UI không được bịa

| # | Thiếu gì | Hệ quả thấy được |
| --- | --- | --- |
| C1 | CEFR level + ước lượng **số phút đọc** cho từng mục catalogue | Thẻ thư viện thường trống dòng meta; frame luôn in `B1 · tiểu thuyết · 22 phút`. |
| C2 | Thời gian đọc theo chương | Hàng chương in **số từ**, frame in **số phút**. |
| C3 | Cấp độ theo từng kỹ năng (`profile.skill_levels`) | Rail không in được level cho Đọc/Nghe/Nói/Viết. |
| C4 | Chuỗi ngày, thời gian học 90 ngày, hoạt động 18 tuần, ngưỡng rank | Các ô Progress sẽ phải in "—" nếu dựng theo frame ngay bây giờ. |
| C5 | Câu hỏi hiểu cho sách nhập | A3 ở trên. |
| C6 | **Ngưỡng bậc 10 (Virtuoso)** | Frame vẽ "BẬC HIỆN TẠI" đè lên số của chính nó, nên 19/20 ngưỡng có số, riêng bậc 10 không. Learner ở giữa 1 600 và 3 000 từ sẽ bị tính là bậc 9. Cần anh cho **một con số**. |

## C. Dữ liệu backend cần cho UI đã dựng sẵn (2026-09-22)

Human: *"Backend chưa có thì note lại làm sau. UI phải có hoàn chỉnh đã."* Các màn dưới đây **đã dựng đủ
component**, đang render 0 / "—" đúng rule 4, và sẽ tự có số khi backend phục vụ:

| Ô đang trống | Cần gì |
| --- | --- |
| Progress · Kiểm tra hiểu | số câu đúng / tổng, theo 7 ngày |
| Progress · Nhớ lại | số thẻ đã chấm 7 ngày + tách nhớ / chưa chắc / quên |
| Progress · Chuỗi ngày, Thời gian học | đếm ngày liên tiếp, thời gian học 90 ngày |
| Progress · heatmap 18 tuần | hoạt động theo từng ngày |
| Progress · thời gian 7 ngày theo kỹ năng | thời gian theo kỹ năng (chép chính tả tính vào Nghe) |
| Xu hướng · Đang tốt lên | 4 thước đo so với 4 tuần trước |
| Xu hướng · Dựa trên gì | đếm thẻ / bản viết / câu hỏi / phiên nói / bài đọc |
| Xu hướng · Lỗi lặp lại | mô hình lỗi lặp: tên lỗi, số lần, ví dụ, nguồn |
| Hồ sơ · XP và chuỗi ngày | điểm kinh nghiệm và chuỗi ngày |
| Hồ sơ · khung rank trên avatar | `ProgressOverview.tier` + ngưỡng bậc 10 (C6) |

## D. Quyết định quy tắc, không phải quyết định code

| # | Việc | Hai lựa chọn |
| --- | --- | --- |
| D1 | Chip lọc thư viện | Frame liệt kê **11** loại; app chỉ hiện chip cho loại **thực sự có nội dung** (nay là 4). Hiện đủ 11 thì có chip bấm vào không ra gì. |
| D2 | Ghi công nguồn & bản quyền | Frame **không vẽ ở đâu cả**. Nút đã bỏ theo yêu cầu; khối ghi công hiện nằm dưới bài đọc vì văn bản đã xuất bản buộc phải có. Đặt ở đâu là của anh. |
| D3 | Màu chữ | Frame dùng `rgba(255,255,255,0.72 / 0.55)`; app đọc token `--text-secondary` / `--text-muted`. Component chỉ được đọc token, nên nếu phải khớp tuyệt đối thì sửa ở `theme.css`, không sửa trong component. |
| D4 | DM Mono → Roboto Mono cho tiếng Việt | Đã treo từ trước; mọi nhãn mono tiếng Việt đang rơi về Roboto Mono. |
| D5 | Ink / Paper | Anh nhắc trong yêu cầu, nhưng D-066 đã khai tử và code đã gỡ theme picker. Đang làm **một** hệ Dark Glass. Muốn hai theme trở lại thì là quyết định sản phẩm mới. |

## E. Cổng kích hoạt (không phải việc của lane này)

| # | Việc |
| --- | --- |
| E1 | `reading.discussion_turn` hiện **đếm usage, không chặn ai**. Bật enforcement Free/Premium là cổng kích hoạt thương mại, cần anh mở, và khi mở thì phải đi qua quota ledger chứ không phải `usage_events`. |
| E2 | Tầng fallback thứ ba cho AI router: chỉ cần thêm một trường config, không cần code. |

## F. Nợ kỹ thuật thấy được trong phiên

| # | Việc |
| --- | --- |
| F1 | `scripts/test_orena_vocabulary_theme_tokens.mjs` và `scripts/test_orena_writing_workspace.mjs` **fail sẵn từ `3deab1e`**, kiểm chứng trên cây sạch. Chưa sửa vì ngoài phạm vi. |
| F4 | **Sandbox `:8011` mất sạch dữ liệu học viên sau khi Docker engine treo và được khởi động lại (2026-09-22 05:51).** Bảng còn nguyên, schema vẫn ở `20260922_0012`, nhưng `essays`, `reading_sessions`, `text_discussions`, `usage_events` đều **0 dòng**; sáng cùng ngày có 10 bài viết, một luồng thảo luận và các dòng usage. Nguyên nhân **không xác định được** từ đây. Điều xác minh được: container `orena-foundation-postgres` có `Mounts: []` - **không gắn volume nào**, dữ liệu nằm trong lớp ghi của container, nên runtime này chưa bao giờ bền vững. Volume của production và preview (`ai-writing-coach-data`, `ai-writing-coach-postgres-data`) vẫn còn nguyên, không bị đụng tới. |
| F2 | Sandbox `:8011` đang có 1 EPUB thử ("Kafka pa stranden", 5 chương, id `ce71a298…`) tôi nhập để đo màn Book detail. Giữ để anh xem, hay archive? |
| F3 | Chưa đo lại Reader và Library ở **390 mobile** sau các thay đổi hôm nay; đã đo desktop 1920. |


---

## Summary by canonical screen

| Canonical UI | Required contract | Backend implementation | Data source / DB | Tests | Status |
| --- | --- | --- | --- | --- | --- |
| Quick Sheet, word | `WordDetail` | `/api/dictionary/word-detail` (projection in `word_detail.py`) over `reading_lookup` and the contextual explanation; `ui/quick-sheet.js` | vocabulary catalog, tagger, AI capability | `tests/test_word_detail.py` (held to the pinned contract), `test_orena_reading_room.mjs`, `test_media_interaction` | IN_PROGRESS (S1 built; see log) |
| Sentence sheet | `SentenceSheet` | `/api/dictionary/sentence-sheet`; parts and vocabulary in `ui/quick-sheet.js` | as above | as above | IN_PROGRESS (S1 built; see log) |
| Writing review | `WritingReview` | `GET /api/essays/{id}/review` (`writing_contract.py`); `example` in the evaluator contract (v2.5), English `register` category; `ui/writing-feedback.js` | `essays` | `tests/test_writing_contract.py` (held to the pinned contract), `test_writing_evaluation`, `test_orena_writing_review.mjs` | IN_PROGRESS (S2 built; see log) |
| Writing revision | `RevisionCompare` | `GET /api/essays/{id}/revision`; `revision_delta` judged by the words | `essays` chain | `test_writing_revision_contract`, `test_writing_contract` | IN_PROGRESS (S2 built; see log) |
| Writing entry, workspace | `ContentCard`, draft | `/api/drafts`, `/api/tasks/generate`; prompt library | account backbone, catalogue | `test_work_api`, `test_orena_writing_workspace.mjs` | BLOCKED (`[CONTENT]` prompts; drafts past sandbox) |
| Listening library, workspace | `ContentCard`, `AudioPlayer`, `Transcript` | `listening_api`, `media_*`; `content_type` derived; library `ui/library-browse.js`; workspace details open (see log) | catalogue JSON, `listening_progress`, device memory | `test_listening_*`, `test_orena_library.mjs`, `test_orena_pure_listening.mjs` | IN_PROGRESS (S3a built, S3b open) |
| Dictation | `DictationResult` | `capabilities/dictation-result.js`, `ui/dictation-screen.js`; `pinyin_alignment.py`; the evaluator and evidence save unchanged | outcomes, catalogue JSON | `test_orena_dictation_screen.mjs`, `test_pinyin_alignment.py`, `test_dictation_evaluator.mjs` | IN_PROGRESS (S3b built; DC-5 needs a decision) |
| Reading library, book detail | `ContentCard`, `Chapter` | `reading_library_api`; add kind, level, duration | `reading_books`, `reading_book_chapters` | `test_reading_library_api`, `test_orena_reading_library.mjs` | BLOCKED (`[REVIEW]` catalogue schema) |
| Reading workspace | `ReadingChapter` | `libraryBookChapter`, `readingTranslate`; whole-chapter translation | book assets, translation cache | `test_reading_translation`, `test_orena_reading_room.mjs` | IN_PROGRESS (S4) |
| Reading comprehension | comprehension | per-question check endpoint; per-chapter generation | `reading_sessions`, `reading_attempts` | none for the routes yet: add before changing | IN_PROGRESS (S4) |
| Search (all libraries) | `ContentCard[]` | catalogue search API, read-only | books, listening, vocabulary, collections | add | IN_PROGRESS (S5) |
| Speaking library | `ContentCard` | Speaking catalogue | catalogue | add | BLOCKED (`[CONTENT]`) |
| Speaking workspace | `PronunciationResult` | provider abstraction, normalized contract, Azure and SpeechSuper adapters, tone contour | `speaking_attempts` (no raw audio) | `test_speech_pronunciation`, `test_speaking_evaluator`, `test_m3_pronunciation_contract.mjs` | IN_PROGRESS (L); E2E `[PROVIDER]` |
| Vocabulary library, card, strokes | `VocabularyCollection`, `WordDetail` | `vocabulary_library`, stroke order | `vocabulary_*` | `test_vocabulary_library*`, `test_chinese_stroke_order`, `test_orena_vocabulary_library.mjs` | IN_PROGRESS (L) |
| Vocabulary context clips | `ContextClip` | word to clip index over listening transcripts | new index | add | BLOCKED (`[REVIEW]`/index design) |
| Vocabulary review | `VocabularyCard` | three-grade scheduler and interval preview | `saved_words` | `test_vocabulary_cards`, `test_orena_vocabulary_card.mjs`; add SRS tests | BLOCKED (`[REVIEW]` rule change) |
| Progress overview, trends | `ProgressOverview`, `ProgressTrends` | read model over the domain owners; every metric carries `measured` | LearnerSummary, events (new) | `test_learner_summary`, `test_orena_growth_summary.mjs` | BLOCKED (`[DEF]`, `[REVIEW]`) |
| Home / Discover | `AppShell`, `ContentCard` | shared card serializer; Continue read model | catalogues, device continuation | `test_orena_discover_layout.mjs` | IN_PROGRESS (L) |
| App shell | `AppShell` | profile fields; metric fallback | profile, LearnerSummary | `test_orena_foundation.mjs` | IN_PROGRESS (foundation with S1) |

## Requirements

Legend for each table: **Have** is what the backend does today; **Need** is the
change. Group headers name the contract, data source and tests once.

### Shell — `AppShell` · profile, LearnerSummary · `test_orena_foundation.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| SH-1 | Display name and avatar | `/api/me` gives email and mode → profile fields | L | BLOCKED `[REVIEW]` |
| SH-2 | Level next to the language ("B1", "HSK 2") | CEFR `declared_level`, not stored, no HSK → stored level per language framework | L | BLOCKED `[REVIEW]` |
| SH-3 | Language ("NORSK" in the mock) | `/api/platform/languages` is en and zh → none; Norwegian is demo data | - | IN_PROGRESS |
| SH-4 | Rank label ("Virtuoso · bậc 4") | none → rank definition and ladder; shows `0` until measured | L | BLOCKED `[DEF]` |
| SH-5 | Streak in the top bar and headers | none → streak definition and measurement; shows `0` | L | BLOCKED `[DEF]` |
| SH-6 | Level per skill in the rail | none → stored level per skill | L | BLOCKED `[REVIEW]` |
| SH-7 | Search field, desktop and phone | none server-side → S5 | S5 | IN_PROGRESS |
| SH-8 | Active nav and skill, five-item phone bar | client routing → none | - | IN_PROGRESS |
| SH-9 | Loading, empty, error | baseline draws none → keep the existing skeleton and degraded panel | - | IN_PROGRESS |
| SH-10 | Auth | Google OAuth, session guard, admin guard → none | - | IN_PROGRESS |

### Home — `AppShell`, `ContentCard` · catalogues, device continuation · `test_orena_discover_layout.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| HM-1 | Continue strip: kind, title, 68%, "còn 4 phút", resume | device `continuation`; progress only where a place is recorded → a `ContinueLearning` read model; cross-device is gated | L | BLOCKED `[REVIEW]` |
| HM-2 | "Mới cho bạn · phù hợp trình độ" | nothing ranks content → level-based ordering (needs SH-2) | L | BLOCKED `[REVIEW]` |
| HM-3 | Reading, Listening, Vocabulary rails | separate shapes per domain → the shared `ContentCard` serializer | L | IN_PROGRESS |
| HM-4 | Speaking rail | no Speaking library → SP-1 | L | BLOCKED `[CONTENT]` |
| HM-5 | Writing rail "Gợi ý viết mỗi ngày" | only AI task generation → WR-2 | L | BLOCKED `[CONTENT]` |
| HM-6 | Card: 17 types, skill, hue, badge (ĐANG LUYỆN, ĐÃ LƯU, TẠO RIÊNG, ĐÃ NHẬP) | per-domain fields; hue is artwork → one serializer | L | IN_PROGRESS |
| HM-7 | Populated rails | 7 listening lessons, books only after admin import → supply content | L | BLOCKED `[CONTENT]` |

### Reading — `ReadingChapter`, `Chapter`, `ContentCard` · `reading_books`, `reading_book_chapters`, assets · `test_reading_library_api`, `test_reading_translation`, `test_orena_reading_library.mjs`, `test_orena_reading_room.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| RD-1 | 11 type chips (books, excerpts, articles, news, essays, stories, dialogues, quotes, own, imported) | books carry no kind, level or topic → catalogue metadata | L | BLOCKED `[REVIEW]` |
| RD-2 | Card: author, level, kind, minutes | author and word count only → level, kind, and an owned reading-speed rule for minutes | L | BLOCKED `[REVIEW]` |
| RD-3 | Search inside the library | none → S5 | S5 | IN_PROGRESS |
| RD-4 | "Nhập văn bản", TẠO RIÊNG / ĐÃ NHẬP | import exists, device memory → wire the badge | L | IN_PROGRESS |
| RD-5 | Paged cover grid | cursor and `/cover` exist → none (real art is supply) | - | IN_PROGRESS |
| RD-6 | Book hero: continue chapter, 34%, time left | `libraryBook`; percent from continuation → `Chapter.progress` | L | IN_PROGRESS |
| RD-7 | Chapter state read / reading / unread | only the current chapter (device) → durable chapter state | L | BLOCKED `[REVIEW]` |
| RD-8 | "Bạn đã lưu từ đây … + 83 từ" | saved words carry no book link → word-to-book link | L | BLOCKED `[REVIEW]` |
| RD-9 | Book bookmark, menu, listen | none; device speech for words → saved items, audio | L | BLOCKED `[REVIEW]` `[PROVIDER]` |
| RD-10 | Position inside a chapter | chapter only → exact position | L | BLOCKED `[REVIEW]` |
| RD-11 | Bilingual layer | `readingTranslate`, first 12 paragraphs → whole chapter, batched and cached | S4 | IN_PROGRESS |
| RD-12 | Panel tabs Word, Grammar, Notes | Word only → grammar notes and notes | L | BLOCKED `[REVIEW]` |
| RD-13 | Action bar: save, listen, check, discuss, write a response, read later | check, discuss (`conversation-turn`) and response (`practice_context`) partly exist; save and read-later do not → wire and add saved items | L | IN_PROGRESS |
| RD-14 | Comprehension: one question, verdict and "đoạn giúp bạn trả lời", skippable | generated sessions hold answer, explanation and evidence, but `/answer` grades the whole set → per-question check; sessions for library chapters | S4 | IN_PROGRESS |
| RD-15 | "Bỏ qua vẫn tính đã đọc" | no completion record → part of RD-7 | L | BLOCKED `[REVIEW]` |

### Quick Sheet — `WordDetail`, `SentenceSheet` · vocabulary catalog, tagger, AI capability · `test_media_interaction`, `test_reading_lookup`, `test_orena_understanding.mjs`, `test_r16_contextual_dictionary.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| QS-1 | Layer 1: headword, IPA or pinyin, part of speech, speaker, save | lookup returns all of it → serializer | S1 | IN_PROGRESS |
| QS-2 | "Nghĩa ở câu này" in layer 1 | dictionary meaning only; contextual meaning is an AI explain → a contextual-meaning request through the provider abstraction, distinct from lookup | S1 | IN_PROGRESS |
| QS-3 | Seven usage levels | `USAGE_JUDGEMENTS` are the same seven → rename to the contract values | S1 | IN_PROGRESS |
| QS-4 | "Vì sao ở đây?": verdict, reason, examples, common mistake, grammar note, related | `judgement`, `judgement_reason`, `examples`, `counter_examples`, `grammar_notes`, `vocabulary` → map | S1 | IN_PROGRESS |
| QS-5 | Core idea, mental model, contrast | not in the schema → extend the explanation schema | S1 | IN_PROGRESS |
| QS-6 | "Hỏi tiếp" chips and free question | `follow_ups`, `question` → none | S1 | IN_PROGRESS |
| QS-7 | Where you met it; your own sentences | provenance is device memory; essays not indexed by word → `learnerSentences` read model; sources gated | S1 / L | IN_PROGRESS / BLOCKED `[REVIEW]` |
| QS-8 | "Lưu giải thích" | no saved explanation → saved explanations | L | BLOCKED `[REVIEW]` |
| QS-9 | Chinese variant with pinyin | annotate and explain cover it → none | S1 | IN_PROGRESS |
| QS-10 | Writing-feedback variant | same contract plus `errors[].suggestion` → S2 | S2 | IN_PROGRESS |
| QS-11 | Sentence sheet: translation, short explanation, structure, vocabulary with saved state | all but structure → `structure[{chunk, role}]`, language-neutral roles | S1 | IN_PROGRESS |
| QS-12 | Audio pauses and resumes | client → none | - | IN_PROGRESS |

### Listening, Dictation — `ContentCard`, `AudioPlayer`, `Transcript`, `DictationResult` · catalogue JSON, `listening_progress`, `shadowing_progress`, outcomes · `test_listening_*`, `test_orena_pure_listening.mjs`, `test_dictation_evaluator.mjs`, `test_orena_dictation_*.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| LS-1 | Nine type chips | `content_type` derived from playback, topic and tags (`listening_catalog.content_type`, served in `lesson_metadata`); chips only for types some item has; a lesson that says nothing gets none; imported = the learner's own media | S3a | IN_PROGRESS (built; see log) |
| LS-2 | Card: duration, level, time left, video badge | duration on the cover, level, "time left" and a progress bar from the place in device memory, video and provenance badges | S3a | IN_PROGRESS (built; see log) |
| LS-3 | Library search | the bar's search filters the room's own items (title, level, type); catalogue-wide search stays S5 | S5 | IN_PROGRESS |
| LS-4 | Player: scrubber, transport, speed, loop | scrubber violet with a white knob and a played part that follows the position; transport, speeds and "replay line" as before | S3b | IN_PROGRESS (built; see log) |
| LS-5 | Transcript with pinyin, translation, active word, autoscroll | header chips (auto-scroll, the reading, the support language); auto-scroll is a kept preference that really stops the list following; a tapped line is picked ("Tua tới đây", "Nghe lại dòng") and the voice does not move | S3b | IN_PROGRESS (built; see log) |
| LS-6 | Listening comprehension | none → items and scoring | L | BLOCKED `[CONTENT]` |
| LS-7 | Bookmark | none → saved items | L | BLOCKED `[REVIEW]` |
| LS-8 | Deep actions: dictation, shadow, read line, keep phrase, inspect | one "⋯" button and a sheet (`ui/line-sheet.js`); the five ways run the practices that already existed | S3b | IN_PROGRESS (built; see log) |
| DC-1 | Line 2 of 5, clip range, replay | its own screen: segmented progress, the clip with its range and a bar of where the voice is, replay | S3b | IN_PROGRESS (built; see log) |
| DC-2 | Hint level 1-3, "5 / 11 ký tự" | three levels, leading units, never the whole line (held by a gate); typed-earned units also shown | S3b | IN_PROGRESS (built; see log) |
| DC-3 | Pinyin per revealed character | `pinyin_alignment.py` cuts the reviewed reading into one syllable per character; served as `pinyin_chars_by_segment`; a line that does not agree draws none | S3b | IN_PROGRESS (built; see log) |
| DC-4 | Result: score, count, wrong / missing / extra | `capabilities/dictation-result.js` maps the evaluator to `DictationResult`; a substitution is one wrong place; the count under the ring is the count the score is made of | S3b | IN_PROGRESS (built; see log) |
| DC-5 | "Đã dùng gợi ý — không tính vào chuỗi" | `used_hint` + hint level stored with the attempt (D-068); no score effect | L | BLOCKED (migration chain awaiting authorization + architecture review) |
| DC-6 | Keep a word from the result | "Lưu <term>": the lesson's own vocabulary term found in the line, else the whole line, into device memory | S3b | IN_PROGRESS (built; see log) |

### Speaking — `PronunciationResult` · `speaking_attempts` (no raw audio, D-066 rule 7) · `test_speech_pronunciation`, `test_speaking_evaluator`, `test_m3_pronunciation_contract.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| SP-1 | Six practice types, "2/5 câu" | no Speaking library → catalogue of clip, sentences, type, level | L | BLOCKED `[CONTENT]` |
| SP-2 | "Ghi âm của tôi" library | no durable audio by policy → show `0` saved; durable audio needs its own review | L | BLOCKED `[REVIEW]` |
| SP-3 | Clip, sentence, waveform, mic controls | clip, transcript, recorder, mic readiness → none | L | IN_PROGRESS |
| SP-4 | Transcribe | `/api/speech/transcribe`, unconfigured → credentials | L | BLOCKED `[PROVIDER]` |
| SP-5 | Score panel: overall, accuracy, fluency, passed | Azure adapter, unconfigured → normalized contract, provider abstraction, SpeechSuper adapter; metrics `0` with no attempt; canonical unavailable state without a provider | L | IN_PROGRESS (E2E `[PROVIDER]`) |
| SP-6 | Timing note | offsets available → compare with the model clip | L | IN_PROGRESS |
| SP-7 | Per-word note in words | phoneme accuracy only → tone and phoneme rules, or coaching | L | IN_PROGRESS |
| SP-8 | Tone curve, target and actual | none → pitch contour service | L | IN_PROGRESS |
| SP-9 | Compare, hear your take | client blob → none | L | IN_PROGRESS |
| SP-10 | Free talk: topic, phrases, what you said, comment | `evaluateSpeaking` needs ASR → topic and phrase content | L | BLOCKED `[CONTENT]` `[PROVIDER]` |
| SP-11 | Recording state | client → none | L | IN_PROGRESS |

### Writing — `WritingReview`, `RevisionCompare`, draft · `essays`, `essay_revisions`, account drafts · `test_writing_evaluation`, `test_writing_review_completeness`, `test_writing_review_reuse`, `test_writing_revision_contract`, `test_writing_evaluator_contract`, `test_work_api`, `test_orena_writing_review.mjs`, `test_orena_writing_workspace.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| WR-1 | Entry: continue draft, "lưu 6 phút trước" | account drafts (sandbox) and device → `updated_at` | L | BLOCKED `[REVIEW]` |
| WR-2 | "Theo gợi ý": prompt list by kind, level, target words | AI task generation only → curated prompt library | L | BLOCKED `[CONTENT]` |
| WR-3 | Four modes | free, own prompt, `practice_context` exist → wire | L | IN_PROGRESS |
| WR-4 | Workspace: autosave, word count, target | limits, count, `saveDraft` → none | S2 | IN_PROGRESS |
| WR-5 | Review: summary, strengths, three issues, rule, related grammar, ask more | `summary_vi`, `strengths_vi`, `errors[]`, `grammar_links` → serializer | S2 | IN_PROGRESS (built) |
| WR-6 | Example sentence per issue | no such field → add to the evaluator contract, versioned | S2 | IN_PROGRESS (built) |
| WR-7 | Issue kind: register, grammar, punctuation, vocabulary, naturalness | categories are rubric keys → extend the taxonomy, EN and ZH together | S2 | IN_PROGRESS (built) |
| WR-8 | Four dimensions, 0-100 | five rubric keys → serialize the four drawn; keep `task_achievement` | S2 | IN_PROGRESS (built) |
| WR-9 | "Lưu nhận xét" | every review is stored as an essay → none | S2 | IN_PROGRESS (built) |
| WR-10 | "Lưu khái niệm" | no saved concept from a review → saved concept | L | BLOCKED `[REVIEW]` |
| WR-11 | Apply a fix | client, uses `anchored` → none | S2 | IN_PROGRESS (built) |
| WR-12 | Revision: v1 and v2, fixed / remaining / new, headline | `revision_delta` → titles, details and headline from the data | S2 | IN_PROGRESS (built) |
| WR-13 | Dimension change "72 → 88" | delta is a difference → return `from` and `to` | S2 | IN_PROGRESS (built) |
| WR-14 | Done, edit again | client → none | S2 | IN_PROGRESS (built) |

### Vocabulary — `VocabularyCollection`, `VocabularyCard`, `WordDetail`, `ContextClip` · `vocabulary_collections`, `vocabulary_entries`, memberships, `saved_words` · `test_vocabulary_library*`, `test_vocabulary_cards`, `test_chinese_stroke_order`, `test_orena_vocabulary_*.mjs`

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| VC-1 | Collections with language, size, percent | `vocabularyLibraryCollections` → shared card | L | IN_PROGRESS |
| VC-2 | Real packs | catalog gated until a pack is published → supply | L | BLOCKED `[CONTENT]` |
| VC-3 | Search words or collections | inside one collection only → S5 | S5 | IN_PROGRESS |
| VC-4 | Card front and back, mastery 0-3 | entries, `review_stage` → define mastery mapping once | L | IN_PROGRESS |
| VC-5 | Deep card: senses, collocations, contrast, mistake, mental model, related | free-text fields → structured entry or on-demand explain | L | IN_PROGRESS |
| VC-6 | "Lấy từ đâu" | device provenance → durable source link | L | BLOCKED `[REVIEW]` |
| VC-7 | "Câu của bạn" | essays not indexed by word → read model (as QS-7) | L | IN_PROGRESS |
| VC-8 | Han strokes: radical, components, order, animation | offline stroke pack → check the pack for decomposition | L | IN_PROGRESS |
| VC-9 | Trace along, free write | no canvas → client capability | L | IN_PROGRESS |
| VC-10 | Context clips for a word | no word-to-clip index → inverted index over listening transcripts | L | BLOCKED `[REVIEW]` |
| VC-11 | Review: three grades with intervals, 3 / 24 | `again` / `got_it` → three-grade scheduler, interval preview, server-chosen queue; map old states, add tests, keep history | L | BLOCKED `[REVIEW]` |
| VC-12 | Tier, 87/150, "chưa thuộc", show all | progress and filters exist; tier does not → tier definition | L | BLOCKED `[DEF]` |
| VC-13 | Han or Latin script | `orthography` → none | L | IN_PROGRESS |

### Progress — `ProgressOverview`, `ProgressTrends` · LearnerSummary, `saved_words`, `reading_attempts`, `essays` · `test_learner_summary`, `test_orena_growth_summary.mjs`, `test_writing_analytics`

Every value below renders `0` (a chart, its zero state) until measured.

| ID | Canonical UI | Have → Need | Slice | Status |
| --- | --- | --- | --- | --- |
| PG-1 | Streak | none → definition and measurement | L | BLOCKED `[DEF]` |
| PG-2 | Study time and per-skill time | no duration is recorded → official rule (time of completed work, never app-open time) and telemetry | L | BLOCKED `[DEF]` `[REVIEW]` |
| PG-3 | Words mastered | `review_stage` → one threshold | L | IN_PROGRESS |
| PG-4 | Just learned, with samples | `saved_words.added_at` → none | L | IN_PROGRESS |
| PG-5 | Reviewing, due, done today | due from `next_review_at`; no event → review events | L | BLOCKED `[REVIEW]` |
| PG-6 | Comprehension 9/11 and sequence | `reading_attempts` for generated passages → chapter quizzes (S4) | L | IN_PROGRESS |
| PG-7 | Recall accuracy, cards, got / unsure / forgot | cumulative counters only → review event table; needs VC-11 | L | BLOCKED `[REVIEW]` |
| PG-8 | Recent evidence per skill | LearnerSummary latest observations → `EvidenceItem` projection | L | IN_PROGRESS |
| PG-9 | Rank panel | none → SH-4 | L | BLOCKED `[DEF]` |
| PG-10 | 18-week heatmap | none → per-day activity | L | BLOCKED `[DEF]` `[REVIEW]` |
| PG-11 | Next action | `practiceRecommendation`, `crossSkillCue`, `reviewCue` → one contract | L | IN_PROGRESS |
| PG-12 | Improving over four weeks | only comparable measures may show a trend → series where comparable, `0` otherwise | L | BLOCKED `[DEF]` |
| PG-13 | Recurring errors | `error-memory` covers Writing → cross-domain read model | L | IN_PROGRESS |
| PG-14 | "Dựa trên gì" counts | derivable → after PG-7 | L | IN_PROGRESS |

## Progress log

**S1 Quick Sheet** (2026-09-21, `codex/work`). Built: `word_detail.py` and two endpoints
(QS-1..6, 11); `context_meaning`, `core_idea`, `mental_model`, `contrast`,
`common_mistake`, `structure` in the explanation schema; `ui/quick-sheet.js` and
`quick-sheet.css` (layer one, ask, deeper, sentence and its parts) called from
Reading and the Listening transcript through `ui/lexical.js`; the old lookup panel,
selection toolbar and reader panel styles removed. Checked in a browser on the
sandbox (:8011), vi interface, English text: docked in the reader, popover in
Listening, phone sheet with scrim. Local: pytest 1148 passed / 118 skipped, all CI
`.mjs` gates pass except `test_m3_pronunciation_contract.mjs`, which has failed
since D-065 removed the score from the report (it is a Speaking-slice item).

Not READY yet - what is left before S1 can be called READY:

- Chinese in a browser (hanzi, pinyin, the grammar-word label) and the zh interface.
- Phone: the ask, deeper and sentence views, not only layer one.
- Save from the sheet end to end with a reload, and the provider-down and retry states.
- Speaking still mounts the layer (`ui/speaking.js`): check it.
- The explanation and summary come back in English when the support language is
  Vietnamese on the sandbox's provider; the request names Vietnamese, so this is the
  provider's output (handoff: local model quality), to be checked with the live one.
- `QS-7` `sources` / `learnerSentences` are empty until their read models exist;
  `QS-8` "Lưu giải thích" keeps its place, disabled and saying so.
- Writing feedback, Vocabulary and Practice still open the older Understanding
  surface (`ui/understanding.js`); it is retired when S2 and the Vocabulary work
  move onto the sheet.
- Found on the way, fixed: the Listening transcript's words could not be tapped
  (a stale `.media-encounter` root); `.media-encounter` selectors remain as dead
  CSS to remove in S3.

**S3a Library** (2026-09-21, `f75991f`). Built: the baseline's library for Reading and
Listening as one surface (`ui/library-browse.js`): a bar with the room's name, a search and
the import action; one row of single-choice type chips offered only for types some item
really has; a grid of ContentCards with the length on the cover, a progress bar and "time
left" from the place the learner reached (device memory), a video badge and a provenance
badge (said once, not repeated in the line), and an authored "3 min" shown in the interface
language. Backend: `content_type` for listening lessons, derived and tested
(`test_every_lesson_carries_a_type_the_baseline_names_or_none`). The D-060 facet layout and its
CSS are deleted; a new gate `scripts/test_orena_library.mjs` (in CI) holds the contract and the
copy for every catalogue type in en, zh and vi. Checked in a browser on the sandbox (vi):
desktop Reading and Listening, phone Listening with touch (chip tap filters, no horizontal
overflow, chips scroll). Local: pytest 1160 passed / 118 skipped; every CI `.mjs` gate passes
except `test_m3_pronunciation_contract.mjs`.

Not READY yet - S3 as a whole:

- The Listening workspace has the baseline's structure (player, scrubber, transport, speeds,
  comprehension button, bookmark, transcript with VI) but not its details: the transcript
  header is the shared learning toolbar's row of icon buttons where the baseline draws
  "Tự cuộn", PINYIN and VI chips and puts the deep actions (dictation, shadow, read the
  line, keep, inspect) behind one "⋯"; the scrubber is amber where the baseline's is violet
  with a white knob. `learning-toolbar.js` is shared with Reading, so it changes in one pass.
- The catalogue's lesson `en-travel-rainy-day-taxi` is a single 71 s segment (one very long
  transcript line): a content-segmentation gap `[CONTENT]`, not code.
- Dictation is a panel beside the player; the baseline draws its own screen (segmented
  progress, the player inside a centred card with the hint-level pill, hint shape with pinyin,
  a result column with the score ring, marks and actions). The evaluator, hint levels, score,
  wrong/missing/extra and save already exist and are reused. DC-3 (pinyin per character) and
  DC-5 (assisted flag kept) are still open.
- Search (S5) and the catalogue-wide result page are untouched; the Library page
  (`#/content`, all kinds) uses the same component with type chips only.
- Browser checks of the zh interface and of imported items in the library.

**S3b Listening workspace and Dictation** (2026-09-21, `8bdb649`, `3c70516`, `3df3aee`). Built from
the pinned frames (Orena Listening 02, 03, 04), not from the previous implementation:

- Workspace: header chips (Tự cuộn, the reading, the support language) and one "⋯"; a tapped
  line is picked and offers "Tua tới đây" and "Nghe lại dòng", the voice stays where it is; the
  deep ways (dictation, shadow, read the line, keep, look closer) are a sheet over the workspace
  (popover on a desk, bottom sheet on a phone, closes on navigation); an audio lesson has a poster;
  the identity line is level · type · length; the scrubber is violet with a white knob. Word-class
  colours have no switch on the baseline, so they are off and their legend is gone.
- Dictation: its own screen - segmented progress, the clip, the pills (hear again, speed, hint
  level), the shape of the line with a reading under each character, the field, and a result
  column (ring, what was typed with each wrong, missing and extra place marked and tappable, the
  right line with the missed characters lit, the reading and the meaning, next line / try again /
  replay / keep). The comparison, score, hint module and evidence save are the ones that existed;
  `capabilities/dictation-result.js` only puts them in the baseline's shapes. The streak pill
  shows 0 (not measured). A used hint says "Đã dùng gợi ý." and nothing more.
- Backend/data: `pinyin_alignment.py` and `pinyin_chars_by_segment` in the lesson payloads;
  the aligner is verifiable (pypinyin only says where a syllable ends), left a line unaligned
  rather than wrong, and caught two real typos in the reviewed readings (`zhǎodào`, `Bǎikē`),
  corrected in the catalogue. Every Chinese line the catalogue ships aligns (a test holds it).
- Chinese and localization: keys are in parity across en, zh and vi in both copy packs; the
  library, the workspace, the deep sheet, Dictation, the Quick Sheet (word, deeper, typed
  question) and the Writing review with its finding sheet were run in a browser in a Chinese
  interface with Chinese text and real answers (Gemini): second person, Chinese throughout.
- Checked in a browser on the sandbox with real touch: Dictation and the workspace on a phone (no
  horizontal overflow, the deep sheet is a bottom sheet with a scrim, the result follows the task),
  the library on a phone (two columns, the item in progress leads). Local: pytest 1171 passed /
  118 skipped; every CI `.mjs` gate passes except `test_m3_pronunciation_contract.mjs`; new gates
  `test_orena_library.mjs`, `test_orena_dictation_screen.mjs`, `test_orena_listening_workspace.mjs`.
- Deleted: the old Dictation panel's CSS and code (`revealAnswer`, `.dictate-*`, `.hint-line`,
  `data-mode='dictation'`), the audio identity block, the D-060 library layout.

Decisions the human closed (D-068, 2026-09-21):

- **DC-5.** Approved: the used-hint state is stored with the attempt, and no scoring effect is
  inferred without a scoring rule. Storing it means two columns on `listening_progress` (the last
  attempt's `used_hint` and hint level), a schema change for learner-owned data: it is authored as a
  migration after the chain still awaiting human authorization (`20260916_0008` and
  `20260916_0009`, sandbox at `20260912_0007`) and needs a recorded independent architecture review
  before it is applied. Until then nothing about it is built and the screen says nothing about
  hints used.
- **The lesson `en-travel-rainy-day-taxi` is removed** from the catalogue (six lessons remain); its
  source `commons-taxi-dialogue-1` goes with it.
- **Reveal in Dictation.** The baseline draws no "show the answer", and a hint never shows the whole
  line, so the screen has none; the recorded `revealed` evidence path is now unreachable from the UI.

Not READY yet - what is left of S3:

- LS-6 (comprehension) and LS-7 (bookmark as a saved item) stay `BLOCKED` as before; the bookmark
  is device memory.
- The workspace on a phone stacks the poster, the transport and the transcript; the baseline's
  phone puts a top bar (back, the reading and support chips, bookmark) over a longer transcript with
  the transport at the bottom. Functional and touch-checked, not yet the same composition.
- Word-class colouring code (`closeLook`, annotation of the current line) has no UI; delete it.
- The two `verify_writing_*_browser.mjs` scripts still wait for the deleted `.review-headline`.
- The library's chips show only types that exist; the baseline draws the full fixed set.

**S2 Writing review and revision** (2026-09-21). Built: `writing_contract.py` and two
endpoints (WR-5..9, 11..14); `example` per finding and the English `register`
category (evaluator contract `writing-evaluation-v2.5`); one table maps every
category of both languages to the baseline's five kinds; `ui/writing-feedback.js` and
`writing-feedback.css` (overview, findings, dimensions, the finding sheet with apply,
the version comparison) replace the old report renderer, the revision workbench and
the locate helper. Checked in a browser on the sandbox with the real provider
(vi interface, English text, desktop): review, opening a finding, applying it (draft
changed, count fell), a second version and its comparison. Two root causes found and
fixed on the way: the comparison was handed an unparsed earlier review and saw none of
its findings; and it matched findings by identical wording, so it called a reworded
finding fixed and new at once - it now asks the words. Local: pytest and every CI
`.mjs` gate pass except `test_m3_pronunciation_contract.mjs`.

Not READY yet:

- Chinese (zh text, zh interface) and the phone in a browser; the provider-down state.
- WR-1..4 (entry with four modes, prompt library, workspace top bar) and WR-10 (save a
  concept) are untouched; the room's frame is still the earlier composition.
- Dead styles from the old review (`.review-*` overview/issue/dimension rules,
  `.correction*`) and now-unused copy keys (`reviewFocus`, `reviewDeeper`,
  `reviewLocate`, ...) remain to be removed; they share names with the Vocabulary review
  session's classes, so they need a careful pass.
- `ui/understanding.js` is still used by comprehension, conversation, the encounter,
  voice response and grammar; it goes when those move onto the Quick Sheet.
- The comparison shows the two drafts side by side only when the frame is 820px or
  wider; in the room's result column it shows the banner and the changes, as the
  baseline's phone does.

## Old tracker (GAP-001..052) mapped

Carried into a row above: GAP-001 SH-5 PG-1 · 002/003/008 PG-2 · 004 SH-2 SH-6 ·
006 HM-1 · 011/026 SH-7 · 012 HM-6 RD-5 · 013 SH-1 · 014 PG-5 · 019 superseded
by VC-11 (three grades) · 020 VC-12 · 021 SP-5..8 · 022/027/029 RD-1 RD-2 LS-1 ·
025 LS-6 · 028 (per-word only) DC-3 · 032/034 RD-9 RD-13 · 035 RD-7 RD-15 · 036/039
RD-12 · 040 RD-10 · 043 VC-11 · 044 RD-1 · 045 RD-11 · 047 VC-12 · 048 SH-4 PG-9 ·
049 PG-10 · 051 DC-3 · 052 HM-2.

Not drawn by the baseline, so no longer tracked (git history keeps them): GAP-005,
007, 009, 010, 015, 016, 017, 018, 023, 024, 028 (whole-text pinyin), 030, 031,
033, 037, 038, 041, 042, 046, 050. Profile, My Content, Admin, Onboarding, states,
Modal/Drawer and tablet have no canonical design; their current implementation
stays until the human supplies one (D-066).

**Bug pass on S1/S2** (2026-09-21, commits `fb9a9ec`, `3651ed0`). Six reported defects,
each with its root cause:

- The ask-more input looked dead: a repaint on every state change rebuilt the sheet and
  erased the question being typed. The draft and its focus now survive a repaint, and the
  newest answer scrolls into view. Checked: a 52 s repaint kept text and focus.
- A sheet outlived the screen it was opened from. Every sheet (word, sentence, finding) now
  closes on a route change. Checked with `history.back()` and a hash change, for the word
  sheet and the Writing finding sheet.
- Feedback spoke about "the learner". `VOICE_POLICY` in the writing evaluator and the tutor
  prompts sets second person (bạn / you / 你); the evaluator contract is `writing-evaluation-v2.6`,
  so stored reviews in the old voice are retired. The answer language is now named in the last
  line of the tutor prompt, naming `judgement_reason` and `follow_ups`, which a model otherwise
  leaves in the text's language. Checked live in vi: gloss, verdict, follow-ups and a typed
  question all in Vietnamese; zh word (`终于`) gives pinyin, no IPA, Vietnamese explanations.
- Rails could not be swiped on a phone: `touch-action: pan-y` blocked horizontal panning.
  Checked with a real touch swipe (touch-enabled mobile context, CDP touch events): the
  For-you rail moved from 0 to 217 px. Not a resized mouse viewport.
- The reader's back link went to a route that answered `{"detail":"Not Found"}`; it now
  returns to the book, or to Practice when there is none.
- The For-you cards were unequal (a legacy `align-items:start` in `rooms.css`): now one height (183 px).

Also: the first-layer gloss is no longer replaced when the full explanation loads (for Chinese
the full answer can be a sentence translation). Deleted the old Writing review layout's CSS
(`.review-*`, `.correction*`, ~250 lines across four files), including a legacy
`.review-bar` box that also clipped the vocabulary session's header. Phone sheet checked with
touch (bottom sheet, scrim, no horizontal overflow, closes on navigation).

Still open from S1/S2: the zh *interface* on the sheets and the phone views of ask/deeper
for zh; provider-down states are covered by unit tests, not a browser pass; the two
`verify_*_browser.mjs` scripts (cited in docs) wait for the deleted `.review-headline` and
must be rewritten for the new markup; unused copy keys (`reviewFocus`, `reviewDeeper`,
`reviewLocate`, ...); WR-1..4, WR-10, QS-7, QS-8; `ui/understanding.js` stays for its other
callers. The provider's 15-50 s latency for the full explanation and about 40 s for a review
is provider speed, shown by the loading states, not fixed here.

## Writing workspace, measured against "Writing workspace" and "Writing review" (D-067)

Built to the frame: a 76px top bar (back, title, saved, word count, one "Nhận xét" pill), a 920px column
with the prompt card (the intention field lives in it) and the piece as a 24px serif document; a review
makes two panes (994 : 820, radius 20, padding 28/30). Removed because the frame draws nothing for
them - decisions for the human, not guesses:

- **The level control.** Decided (D-068 follow-up): no selector; the review aims at the level the learner
  declared in their profile (`declared_level`), else the level of the text answered, else nothing.
- **Register exploration and the revision history** are kept and now sit behind the top bar's menu (three
  lines), the design's pattern for "everything deeper behind one button".
- **The "Cần một điểm bắt đầu?" starters** are legacy of the old entry and stay below the room until the
  Writing entry frame (ContentCard / SectionRail of prompts) is built.
- The prompt card's second line ("B1 · ≈150 từ · giọng thân mật") and the "/ ≈150 từ" target in the count
  need a task with a level, a length and a tone; the free-writing room has none, so the card is one line
  and the count is the words written.
- Still not the frame: the review pane's own content (overview, "làm tốt", "ba chỗ cần sửa" cards with
  three chips each, "các mặt" bars), the top bar's "Lưu nhận xét" / "Sửa lại" pair, the revision
  compare frame, the error sheet, and the entry.

## Bugs 7-13 (2026-09-21) - what changed and where

| # | Result | Where |
| --- | --- | --- |
| 7 | PASS: a replaced or closed sheet is cancelled; only the latest tap is answered; the last tap's own selection no longer reads as a drag; words in any visible line are askable (the line becomes current, paused) | `ui/lexical.js`, `ui/quick-sheet.js`, `ui/encounter.js`, `scripts/test_orena_lookup_race.mjs` |
| 8 | PASS: follow-ups go to a contextual tutor (answer first, never restated, short by default, earlier turns carried) | `media_interaction.answer_learner_question`, `word_detail.py`, `tests/test_word_detail.py` |
| 9 | PASS: Previous / Next on the Dictation rail, in step with the progress | `ui/dictation-screen.js`, `dictation.css` |
| 10 | PASS: hear, line, field and check fit 390x844 (check at y 572-622); a long line scrolls in its own pane | `dictation.css` |
| 11 | PASS as built in S3b (ring, count, marks, right line; no invented number); no new deviation found | `ui/dictation-screen.js` |
| 12 | PASS: a tap on a line goes to it and plays it; the half-way picked state is deleted | `ui/encounter.js`, `listening.css` |
| 13 | PASS: the overflow is the menu icon (three lines) | `ui/encounter.js`, `ui/symbols.js`, `ui/expression.js` |

"Ink + Paper": the Paper theme was retired by D-066; there is one theme, so the check is desktop and phone
in one theme.

## Bugs 14-15 and the design sync (2026-09-22)

| # | Result | Where |
| --- | --- | --- |
| 14 | PASS: a word typed with an extra letter ("breack") is still wrong and the hint never shows it whole - the place where it parts from the target stays masked; the old test that expected the word revealed is re-expressed | `capabilities/dictation-hints.js`, `scripts/test_orena_dictation_hints.mjs` |
| 15 | PASS: on a desk the task is one screen (check button at 979/1080, 720/768, 686/720; with or without a result); the picture takes what the height allows, the line scrolls in its own pane | `dictation.css`, `scripts/test_orena_dictation_screen.mjs` |

Design sync: tokens and the contracts checked are unchanged; the rules documents were read for the first time and
are recorded in `docs/design/canonical-ui/SYNC_2026-09-22.md`. From them: the Writing review is a Draft / Review tab
pair on a phone and the revision is three columns with a banner - both built now. Still to build from the templates:
the Writing entry, Home (top bar with search, level and streak, the Continue strip, section rails at 300x170 / 232x132),
Reading (library, book detail, workspace) - each read from the source when it is worked on.

## Writing entry and the ground (2026-09-22)

Built to "Writing entry": `ui/writing-entry.js`, `writing-entry.css`, route `#/writing`. The draft card is drawn only when
the device holds a continuation for Writing; the prompt rail is the texts' own prompts (badge = the text's kind, meta =
its level and length); "search" filters the prompts; "See all" opens the rail into a grid. Not drawn because the
app holds no such data: "saved N minutes ago" on the draft card, a category badge for prompts that have no kind,
a target length. The error sheet is the finding sheet (`issueSheetHtml`), already the frame's: fragment struck,
correction, kind, why, rule well, example, ask / save concept / apply.

## Writing review and revision, second pass (2026-09-22)

Built to "Writing review" and "Writing revision" (desktop and phone): the findings are marked in the draft itself
(`ui/draft-marks.js`), the pane labels are drawn, the top bar's one primary action follows the room (Review / Revise /
Done), and a revision is the banner, the legend, the two versions marked and the changes with the dimension deltas at
their foot. The phone's revision bar is "Revise more" beside "Done".

- **A mark is earned.** The contracts carry the words of a finding (`fragment`; a change's `title`), not where they
  are. A mark is drawn only where the words occur exactly once in the text, the rule apply-fix uses; otherwise the
  finding stays guidance and marks nothing. The revision marks what was fixed and what is still there in the earlier
  version, what is still there and what is new in the later one; it cannot mark the words that replaced a fix
  (`detail` carries the evaluator's suggestion, not the learner's words). Positions in the contract would end both limits.
- **"Lưu nhận xét" (save the review) is not drawn.** A review is already kept with the piece; saving it as something
  else needs a place in learner data that is held for the account architecture (AGENTS.md, holds). Decision needed:
  what "saved" means here (a kept set of rules in My Language?), then it is one button.
- **Where the findings of a revision went.** The revision frame draws no findings, so a version with a version before
  it opens on the comparison and its findings are one menu item away ("Review of this version"), and back. The frame
  gives no button to revise again from the desktop comparison; it is behind the same menu (the phone has it in the bar).
- **The design's Vietnamese sentences are sample text.** The changes list shows the evaluator's own words (the
  fragment, its kind, the correction and reason), not the frame's "Giọng văn đã thân mật".

## Home, built to its frames (2026-09-22)

`ui/home.js` + `home.css` replace `discoverySpread`: the baseline's top bar (the one search, the level, the
streak), the Continue strip, then the rails the frames draw - what is new for you, Reading, Listening,
Speaking, Writing, Vocabulary - and what the learner kept. Every card is a real item; a rail with nothing
in it is not drawn. The old composition (greeting, hero pair, "for you"/"saved" only) and its stylesheet
are deleted (rule 44).

- **The frames' sidebar draws an account card and per-skill levels; the app's rail does not.** The shell is
  already built to `AppShell` (D-066) and the human kept the current logo; the account lives in the profile
  sheet. Per-skill levels have no source (`skillLevels` in `AppShell.json` is unserved). Decision needed
  before the rail grows a card.
- **The streak is still unmeasured (GAP-001).** The chip keeps its place and shows "—", as everywhere else.
- **"For you" is the catalogue's own order (GAP-052).** There is no recommender; the rail alternates
  listening and reading so the phone's first two cards show both, and says nothing about why.
- **The frame's phone tab bar holds Home / Library / Vocab / Progress / Profile**, which the shell already
  draws; Home draws no navigation of its own.
- **Not drawn because nothing supplies them:** a per-card "ĐANG LUYỆN / ĐÃ LƯU" badge (`badge` in
  `ContentCard.json` is unserved), the frame's "còn 4 phút" (a thread records a place, not a remaining time).

## Reading workspace, to its frame (2026-09-22)

"Reading · bilingual + panel" is one screen, and now so is the room: a 4px hairline of the learner's place
across the top, a 72px bar, the text at its 780px measure beside the 440px panel, each scrolling on its own,
and the frame's floating bar under the text. What used to sit under the text - the prepared notes, the
optional check, the response, the rights - is reached from that bar and opens as a sheet (D-068: a function
is not deleted because the mockup omits it; it goes where the design's patterns put it).

- **The frame's bar has six pills; the app draws what exists.** Lưu bài (keep), Nghe (unavailable, as
  before), Kiểm tra hiểu (disabled with no questions, D-068), Viết phản hồi (the response composer, primary),
  the prepared notes when the text has them, and the rights. **"Thảo luận" is not drawn**: there is no
  discussion over a whole text, only the per-selection understanding surface. Decision needed: either a
  thread against a text (learner data, so the account architecture holds it) or the pill leaves the design.
- **"Đọc tiếp sau" is not drawn either.** The frame draws both "Lưu bài" and a primary "Đọc tiếp sau"; the app
  has one bookmark and remembers the place by itself, so a second one would be the same action twice.
- **The sheet is the app's existing dialog, not the design's sheet pattern.** The Quick Sheet's glass is not
  yet a shared primitive; restyling every sheet is its own slice.

## The rail's learner card and per-skill levels (2026-09-22, human decision)

The human asked for both (answer (c) to the five points). Built: the card at the foot of the rail - who this
is, the level they declared and the language they are learning - opening the profile and settings sheet, as
the frames draw it; hidden on a phone, where the Profile tab is that door.

**Per-skill levels are drawn only when the profile carries one** (`profile.skill_levels[skill]`). Nothing
serves that field today (`skillLevels` in `AppShell.json` is unserved), so no level prints. Repeating the one
declared level on all four skills would be a figure nobody measured. **Backend needed:** a per-skill level on
the learner profile, derived from real evidence, before those slots can fill.

## Reviews read back (2026-09-22, D-072.1, no schema)

The Writing room lists the pieces that were reviewed (`GET /api/essays`, this learner and this language,
eight most recent) with the version, the level the evaluator estimated and the date the row states. A row
opens the review stored with that piece (`GET /api/essays/{id}/review`) in a sheet: nothing is copied and
nothing new is written. **The bookmark ("Lưu nhận xét", `essays.review_kept_at`) is approved but not built:**
it waits on the independent architecture review, so the list is every reviewed piece, not a curated set.

## Book detail, measured against the source (2026-09-22, D-067)

Measured `[data-screen-label="Book detail · chapters"]` in `Orena Reading.dc.html` against
`#/book?id=…` at 1920x1080. **Corrected to the frame** (each verified in the running app):
book title 40→38, the chapters heading from a mono `ds-label` to the frame's Nunito 24/800 section
heading, the cover 176→220 wide with radius 14→18, chapter rows padding 12/14→16/20 and radius
13→15, list gap 7→9, chapter title 14→18, chapter number →15, chapter meta →13.5.

Reading Library needed nothing: at 1920 it already measures the frame exactly (bar 84 / padding
0 40, title Nunito 26/800, cover 236x315 radius 16 with the glass ring, grid gap 28, cover-to-text
13, card title Nunito 18/700). The per-skill CSS (`.lib[data-skill='reading']`) is what carries it.

**Not resolved here, because the design and the implementation differ in composition and rules 43-44
make that a decision, not a fix:**

- **The frame draws neither the chip row nor the stat tiles.** The app's hero carries
  `Đọc · EN · 5 chương · 1,200 từ` as chips and four `book-stat` tiles (words saved, reading time,
  average score, audio) that mostly render an honest dash. The frame carries one DM Mono line -
  `B1 · tiểu thuyết · 12 chương · 22 phút còn lại` - and no tiles at all.
- **The frame draws one action.** The app draws a primary plus three disabled icon buttons
  (bookmark, download, more). The disabled-placeholder question is already open for
  "Kiểm tra hiểu"; this is the same question on this screen.
- **The frame puts the saved words in the hero**, under `BẠN ĐÃ LƯU TỪ ĐÂY`, as word pills with a
  `+ 83 từ` overflow. The app has the same data but in a right-hand aside, beside an "About" section
  and a "Similar" note the frame does not draw.
- **The frame has no "chỉ chương chưa đọc" filter.**
- **A chapter row is one line in the frame** (number · title · `18 phút`), 56px tall. The app stacks
  the meta under the title, so the row is ~90px, and the meta is a **word count**, not minutes -
  minutes would need a per-chapter reading-time estimate the catalogue does not carry.
- **Cover proportion.** The frame's cover is 220x300; the app's artwork keeps its own ratio and
  renders 220x322.
- **Colour.** The frame's chapter text is `rgba(255,255,255,0.72)` and its number/meta
  `rgba(255,255,255,0.55)`; the app reads `--text-secondary` / `--text-muted`. Components may only
  read semantic tokens (`AGENTS.md`, Theme), so if these must match exactly it is a token question
  for `theme.css`, not a component override.

## Reading library, re-checked against the source (2026-09-22, D-067)

Re-read `Orena Reading.dc.html` from the design project itself. It is **byte-identical to the
pinned cache** (94 122 bytes, sha256 `fc7f7640…`, the hash `PINS.tsv` records), so the cache was
not stale - the earlier "Reading library matches its frame" claim was simply too broad: it covered
the bar, the grid and the card box, not the whole composition.

**Corrected to the frame:** the cover badge ("ĐÃ NHẬP", "TẠO RIÊNG") was 10.5px / 0.1em tracking in
plain white with no ring; the frame draws 11px / 0.08em in the accent ink `#D5C0FF` with the glass
ring and 6/12 padding. The badge now reads from `--accent-ink` and `--glass-ring`, so no literal
colour entered a component. Verified in the running app after a cache-busted stylesheet reload.

Also confirmed, against an earlier misreading of mine: `TẠO RIÊNG` / `ĐÃ NHẬP` are **cover badges on
cards**, not section headings - the frame has one grid of twelve. The app's per-card badge is the
right shape.

**Still different, and each needs a decision or a backend fact rather than a CSS change:**

- **Card meta is often absent.** The frame prints `B1 · tiểu thuyết · 22 phút` on every card -
  level, type, minutes. The app prints that only where the catalogue carries it: an imported book
  shows nothing, `Kafka pa stranden` shows `sách` alone. **Backend needed:** a CEFR level and a
  reading-time estimate per catalogue item; the app refuses to invent either.
- **Four filter chips where the frame draws eleven.** The frame offers Tất cả, Sách, Chương trích,
  Bài báo, Tin tức, Tiểu luận, Truyện, Hội thoại, Trích dẫn, Tạo riêng, Đã nhập. The app offers a
  chip only for a type some item in the room actually has (`library-browse.js`), so today it shows
  four. Offering a filter that can only ever return nothing is the opposite trade; **which rule
  wins is the human's call**, and nothing here changes until it is made.

## Reading workspace, measured against the source (2026-09-22, D-067)

The human reported the layout is wrong when a source is opened to read. Measured
`[data-screen-label="Reading · bilingual + panel"]` against `#/encounter?…&intent=reading` at
1920x1080.

**The skeleton was already the frame's**: the 4px hairline across the top, the 72px bar with
`0 40px` padding, the 780 reading measure, the 440 aside with its Từ / Ngữ pháp / Ghi chú tabs, and
the floating action bar (radius 999, 12 padding, 10 gap, six 48px pills, the last one primary and
ringless).

**Corrected:** the app drew a **second progress bar** in a band across the whole window
(`.reader-foot`, 1905 wide, with its own `.reader-progress`). The source draws the place **once as a
bar** - the top hairline - and repeats the figure only as text (`34% · còn 9 phút`, DM Mono 13) at
the **foot of the 780 column**, beside the way on to the next chapter. The second bar is deleted and
the row now sits exactly on the column (measured x=343 w=780, identical to `.reader-page`). A code
comment claiming the frame "draws the same figure twice" as two rails is corrected in place.

**Still different, and each is a decision rather than a value:**

- **The bar's controls.** The frame draws a "Song ngữ" pill (121x40) and one 40x40 icon button
  (radius 13, ringed). The app draws a back arrow (32), the support-language chip (`VI`, 35x32) and
  `Aa` (34x34, radius 10). Same purpose, different controls.
- **The six actions are named differently.** Frame: Lưu bài · Nghe · Kiểm tra hiểu · Thảo luận ·
  Viết phản hồi · **Đọc tiếp sau** (primary). App: Giữ lại để sau · Nghe · Điều bạn thu được ·
  **Câu trả lời của bạn** (primary) · Những từ đáng chú ý · Nguồn & bản quyền. The count, the sizes
  and the shape match; which six, and which one is primary, is product wording.
- **Spacing:** bar gap 20 in the frame against 14; aside padding 26 / gap 20 against 22 / 16. Left
  alone in this pass because the aside's contents are not yet the frame's, so matching its padding
  alone would not make it the frame.

## Reading workspace, three faults the human found (2026-09-22)

- **The end-of-chapter sheet is deleted.** `chapter-complete` (a D-059 composition) rendered the
  moment any book chapter opened - not when one was finished - and took about half the desktop
  viewport, more on a phone. The source draws no such sheet, so it is deleted with its markup, its
  repaint and its CSS (rule 44), not restyled. What it reported lives on where the source puts it:
  the words kept here in the side panel, the way on in the foot row.
- **"Nguồn & bản quyền" has left the action bar.** The source draws no such action (human,
  2026-09-22). Attribution itself is not a design choice - a published text owes its credit - so the
  block now sits quietly under the text instead of behind a bar action. **Open for the human:** the
  frame draws no attribution anywhere; where it should live is still the call recorded in the
  fidelity notes.
- **The way out of a book was a loop.** The book page's back was `history.back()` while the reader's
  back *navigates* to `#/book`, so back from the reader pushed the book page, and back from there
  returned to the reader: a learner could not leave the book. The book page's back is now a link to
  the reading library, so library → book → reader unwinds one step at a time. Verified:
  `#/encounter…` → `#/book?id=…` → `#/practice?intent=reading`.

## Reading workspace, matched to the frame's bar and actions (2026-09-22)

The human asked for the layout, the button count, their wording and their places to match the source
exactly. Measured `[data-screen-label="Reading · bilingual + panel"]` and built to those numbers.

**The six actions, in the source's order, with its icons and sizes** - each width verified in the
running app against the frame: Lưu bài 120 (`bookmark-simple`) · Nghe 107 (`speaker-high`) ·
Kiểm tra hiểu 162 (`check-square-offset`) · Thảo luận 139/140 (`chats-circle`) · Viết phản hồi 163
(`pen-nib`) · **Đọc tiếp sau 166, the primary** (`bookmark-simple`, the violet gradient, Nunito 800).
All 48 tall, Nunito Sans 16/400 on the ringed glass. The prepared-notes action left the bar: the
frame draws no seventh pill and the side panel's third tab is where notes belong.

**The bar**: the way back and the title are one link with an arrow (Nunito Sans 16), the place line
is 13px sentence case rather than a 10.5px uppercase tag, and the right cluster is the "Song ngữ"
pill (40 tall, radius 999, translate glyph) with the 40x40 radius-13 type-size button. Bar gap 20.

**"Thảo luận" is now real.** It opens the thread this lane built for D-072.2 and talks to
`/api/texts/discussion`: the learner's questions and the tutor's answers are kept with the account,
one `request_id` per submission so a retry cannot double-answer, and when no provider can answer the
question stays in the box with a retry - no invented reply. Verified end to end in the sandbox
against Gemini.

**Two inferences, recorded for the human rather than decided:**

- The frame gives "Lưu bài" and "Đọc tiếp sau" the same bookmark glyph and no behaviour. Built as:
  "Lưu bài" toggles the bookmark; "Đọc tiếp sau" keeps it *and leaves the text*, which is what its
  words say. If they are meant to be one action, the bar drops to five.
- "Nghe" stays unavailable with its "coming" title: a text has no audio to read aloud yet. The frame
  draws it enabled. Same open question as the disabled "Kiểm tra hiểu".

## Progress: the bar, the two screens, and what no backend can fill (2026-09-22)

Measured against the re-pinned `Orena-Progress.dc.html`, all four frames: `Progress overview`,
`Progress overview mobile`, `Progress trends`, `Progress trends mobile`.

**The bar.** Progress draws no search. Its bar is the destination name (26/800), the window its
numbers cover in mono 13 - "bảy ngày gần đây" on Tổng quan, "so với 4 tuần trước" on Xu hướng - and
the streak chip, which the overview bar carries and the trends bar does not. The search form the app
used to draw there is deleted (rule 44), and with it the screen fits one viewport at 1920x1080:
nothing on Tổng quan or Xu hướng needs scrolling any more.

**The two tabs.** The frame draws the tab pair only on its *trends* frames - `Tổng quan` inactive,
`Xu hướng` solid - and the overview frames draw none. Taken literally that leaves Xu hướng
unreachable, so the pair is drawn on both screens: it is one component with two states, and the
inactive `Tổng quan` pill the trends frame draws is that component's other half. **Open for the
human:** if the overview really is meant to carry no tabs, the way into Xu hướng needs to be drawn
somewhere.

**Xu hướng has no data at all.** Every figure on it renders 0 or a dash in its canonical component
(D-066 rule 4), because nothing serves it:

- **GAP-P1 · no trend model.** The frame draws each measure as the move it made ("72 → 88") against
  four weeks ago. Orena stores no per-measure history, so neither end of that move exists. The rows
  keep their place and say nothing. The frame draws no bar on these rows, so the app draws none
  either - and no trend arrow, which would be a direction nobody measured.
- **GAP-P2 · no repeated-error model.** "Lỗi lặp lại" lists a mistake, how many times it came back,
  why, and where. Nothing counts a mistake across sessions, so the block carries its empty line.
- **GAP-P3 · no comprehension or recall figures.** Row two's third and fourth panels - "Kiểm tra
  hiểu" and "Nhớ lại" - have no source; they render 0 and say what they would count.
- **GAP-P4 · no time on task.** "Thời gian học" and every per-skill row measure time. Orena records
  none, so those tracks are the unavailable hatch and every value is a dash.
- **GAP-P5 · the tier-10 threshold.** The ladder's own tiles state every threshold except tier 10,
  where the frame draws "BẬC HIỆN TẠI" over the number. That tile shows a dash rather than a guess.
  The number is the product's to state.

**The phone.** The desktop bar is not drawn below 600px, so the page draws the frame's own head
there instead - the name at 24/800 (22 on Xu hướng), the window beside it, and the two tabs as a
full-width row of 38 at radius 13 - and both stat rows stay rows, three tiles then four, at the
frame's 8px gap and 11/10 padding. Without that head the phone could reach Tổng quan and never
Xu hướng.

## Hồ sơ, measured against "Orena Hạn mức sử dụng" (2026-09-22)

Read at the source with `DesignSync` - the screen is **not** in
`docs/design/canonical-ui/`, so it has no pin and must be read there each time.

**What now matches the frame.** Hồ sơ is a destination in the rail rather than a
sheet, and it carries the bar the frame draws - "Hồ sơ" at 26/800, the global
search at 46 tall, the streak chip. The hero is the frame's: the ring at 168
(126 on the phone), the name at 34/800 with the rank and plan pills beside it,
the XP line, and **Chia sẻ then Chỉnh sửa at the hero's far right**, in that
order, at 46 tall. The settings card is "Cài đặt" with the frame's six rows, in
its order and with its glyphs - Ngôn ngữ đang học, Mục tiêu mỗi ngày, Nhắc học,
Gói, Nội dung riêng tư, Giao diện. Five Phosphor 2.1.1 icons the app lacked
(`target`, `credit-card`, `moon-stars`, `lock-key`, `share-network`) were
fetched from the package and inlined; none was typed from memory.

**What no backend can fill:**

- **GAP-H1 · XP and the rank.** The frame draws "15 840 XP", "Virtuoso · bậc
  10 / 32" and "CÒN 6 160 → LUMINARY". Nothing counts XP and nothing serves a
  tier, so the XP line says it is not counted, its bar is the unavailable one,
  and the ring stays the plain well until a tier arrives.
- **GAP-H2 · Nhắc học.** There is no study reminder: no schedule, no store, no
  notification. The row keeps its place and says so, and does not open.
- **GAP-H3 · Nội dung riêng tư.** Nothing counts a learner's imported texts for
  this row. Same treatment.
- **GAP-H4 · the reset date.** The frame's quota head reads "PLUS · ĐẶT LẠI
  12/10". `account_state()` carries the plan and each feature's limit and use,
  but no period or reset date, so the head carries the plan alone.
- **GAP-H5 · the joined date and the streak in the hero's meta line.** Neither
  is served; the line carries the language pair it does know.
- **GAP-H6 · the rail's foot.** The frame draws the rank crystal, the day's
  goal (18/30′) and the streak there. Orena measures none of the three, so the
  rail keeps the learner card it has.

**One conflict, for the human rather than for this lane (rule 7).** The frame
closes the quota card with a **"Lên Pro"** button.
`docs/product/ORENA_COMMERCE_ARCHITECTURE.md` §2 and §4 say the opposite:
`billing_ready` is false everywhere upstream and "read-only UI badges are not
access enforcement" - no price, upgrade action or provider identifier belongs
in the interface yet. The button is therefore **not drawn**, and the decision is
recorded here rather than made: either commerce opens, or the frame's button
waits for it.

## The rank system, re-read at the source (2026-09-22, later)

`Orena Rank Frame Master v2` is the current master and the app is now a
faithful port of it: **thirty-two ranks in eight bands of four** - Amethyst,
Sapphire, Orchid, Amber, Aquamarine, Carnelian, Moonstone, Prismatic - one
generator, one light at −48°, no raster anywhere. What the earlier port was
missing and now has: the two-hue split from Amber up (so a high band reads
multi-coloured rather than pale), the band's three extra rings, the second
star from rank 17, the orbit's glow dots, the master's own aura pair, and its
**three** levels of detail rather than two (`min` at 96px and under, `mid` up
to 170, the full crystal above).

**The conflict, recorded rather than decided (rule 7).** Two design sources
count ranks differently:

| Source | Ranks | States thresholds? |
| --- | ---: | --- |
| `Orena Rank Frame Master v2` (and `Orena Hạn mức sử dụng`: "bậc 10 / 32") | **32** | no - it is a material spec |
| The Progress frame's ladder ("THANG CẤP BẬC · 20 BẬC") | **20** | yes, a word count per tile |

Taken as newest-wins the master is current, and the app follows it: the ladder
draws thirty-two. The Progress frame's numbers are kept **by name**, not by
position - its first sixteen names are the master's first sixteen, and
Archivist, Aurora, Celestial and Paragon are the master's 25th, 28th, 29th and
32nd - so a number the design states for a rank stays with that rank.

- **GAP-R1 · fourteen ranks have no threshold.** Virtuoso (which the frame drew
  "BẬC HIỆN TẠI" over), Navigator, Cartographer, Wayfinder, Chronicler,
  Rhapsode, Orator, Vesper, Ember, Curator, Lumen, Empyrean and Zenith have no
  stated word count, so their tiles show a dash and no one can be counted into
  them. Fourteen numbers are the product's to state.
- **GAP-R2 · is the ladder twenty or thirty-two?** If the Progress frame is the
  current one, the ladder is twenty and the master's other twelve ranks are not
  yet in play. One line from the human settles it; nothing else in the code
  needs to change, because both read `static/orena/product/rank.js`.

**Where the rank comes from.** Not from a backend - `tier` is still unserved.
It is derived from the one thing Orena really counts, the learner's mastered
words (past review stage three), against the thresholds above, in
`static/orena/product/rank.js`. Progress and Hồ sơ both read it, so they cannot
disagree. At zero words nobody holds a rank: Hồ sơ draws the plain well and the
Progress card says "Chưa có bậc", and the crystal appears at the first fifty
words rather than being shown for a rank nobody earned.

**One layout consequence.** Thirty-two tiles do not fit the Progress screen at
1920x1080, and that screen must stay inside one viewport. The page now takes
exactly the room the bar leaves and the **ladder scrolls inside its own panel**
(the side column too, if it ever runs longer). Nothing is clipped away and the
screen itself never scrolls.

## GAP-H7 · the usage bars can only ever read zero (2026-09-22)

Found while seeding a learner to review Hồ sơ. The plan's limits are real -
`account_state()` answers with each feature's `monthly_limit` - but **nothing
records a use**. `record_usage` has exactly one caller in the whole codebase,
`writing_coach/text_discussion.py`, and `reading.discussion_turn` is not one of
the features a plan lists. So after 1 600 saved words and a dictionary lookup,
`/api/product/me` still reports `used: 0` for `vocabulary.save` and
`dictionary.lookup`, and the panel draws six bars at zero.

This is a backend gap, not a surface one: the panel is the component the source
draws and the numbers it shows are the ones the product reports. Metering the
endpoints that a plan charges for - writing evaluation and rewriting, lookups,
saved words - is what makes the panel say anything. Until then the bars are
honest and uninformative.

`scripts/seed_sandbox_learner.py` fills the sandbox learner through the app's
own endpoints so the rank, the ladder and the vocabulary panels can be
reviewed with real data; it cannot fill these bars, for the reason above.

## Vocabulary is read by the page, and counted in the database (2026-09-22)

The three-minute listing was one symptom; the architecture was the disease.
`GET /api/library/vocabulary` answered with **every** word a learner had ever
saved, and Vocabulary, Tiến độ, Hồ sơ, Home, Search, the recall queue and the
book page all read it - to show a count, three words, a due queue or a filtered
list. Every one of those screens cost what the whole library cost, and one slow
vocabulary request made all of them wait.

**What each screen asks for now**

| Surface | Before | Now |
| --- | --- | --- |
| Hồ sơ | whole library, counted in the browser | `/api/library/vocabulary/summary` |
| Tiến độ | whole library | the summary, plus `?limit=3&order=recent` |
| Home ("what is due") | whole library, `.filter(due)` | the summary's `due` |
| Recall queue | whole library, `.filter(due)` | `?status=due&order=due&limit=60` |
| My Language | whole library | `?limit=50`, then `?cursor=…`; search, status and order go to the server |
| Saved panel | whole library, searched and sorted in the browser | the same paged query |
| Search | whole library, filtered per keystroke | `?query=…&limit=40`, debounced |
| Book page | whole library, matched on the note | `?focus=<title>&focus=<chapter>…` |

`summary` (and the learner's rank) travels with every page, counted by
aggregate queries, so no screen adds items up and Hồ sơ and Tiến độ cannot
disagree. The rank ladder moved to `writing_coach/product/rank_ladder.py`: the
product states the thirty-two ranks and their thresholds, the browser reads the
answer, and `static/orena/product/rank.js` holds no thresholds any more.

**Indexes, measured rather than guessed.** At ten thousand saved words the
counts took fourteen seconds, because `saved_words` joins `vocabulary_learning`
on `lower(word)` and a function over a column cannot use the primary key - so
every row met every row. `SQLiteSpecializedLearningRepository.initialize()` now
creates expression indexes on `lower(word)` for both tables, plus
`saved_words(added_at DESC, word)`, `vocabulary_learning(next_review_at)` and
`vocabulary_learning(review_stage)` for the orders and filters the screens ask
for. Nothing else was added.

**Measured, on the schema the runtime creates** (best of five, in the app
image; the learner has that many saved words):

| | 0 | 12 | 1 600 | 10 000 |
| --- | ---: | ---: | ---: | ---: |
| summary (counts + rank) | 0.2 ms | 0.3 ms | 0.8 ms | 3.9 ms |
| first page (50) | 0.3 ms | 0.6 ms | 1.5 ms | 7.6 ms |
| recent three | 0.5 ms | 0.3 ms | 1.3 ms | 7.4 ms |
| due queue (25) | 0.3 ms | 0.3 ms | 2.9 ms | 13.5 ms |
| search one page | 0.3 ms | 0.3 ms | 1.9 ms | 7.9 ms |

Over HTTP in the sandbox, with the seeded 1 612-word learner: the summary is
6 ms and 2.4 KB, a 50-word page 20 ms and 23 KB, the due queue 24 ms, three
recent words 20 ms. The old full listing was **185 s** and would have been
~1.5 MB.

**What this does not change.** The endpoint keeps its name, its payload's
`items` and `summary`, and its save/review/delete siblings; it gained `limit`,
`cursor`, `query`, `status`, `order` and `focus`, and `next_cursor`,
`has_more` and `total`. A caller that passes nothing now gets the first fifty
words instead of all of them - which is the point, and is why every caller in
this repository was changed in the same commit.

## Four decisions closing the vocabulary paging work (2026-09-22)

**1. Sorting by level is not a global sort, and no longer pretends to be.** A
level is not in the learner's database - it comes from the curated catalogue
and is attached when a word is read - so the server cannot order by it, and a
cross-store sort would mean denormalising level onto every saved word, which is
a schema decision, not a UI one. The option is therefore offered only when the
list in front of the learner is the whole set it claims to cover (`has_more` is
false); while there is more to load it is disabled, and the order falls back to
the one the server actually applied. The level **filter** on a collection is
unaffected: that one has always been the server's, through the collection
endpoint's own `level` parameter.

**2. What a search matches is now stated, not left open.** The server matches
the word, its definition and the translation kept with it - every field the
learner's own database holds. It does not match the catalogue's
`support_translations`, which are attached at read time. This is not a loss in
practice: every way of keeping a word writes the meaning the learner was
looking at into `definition` or `translation_vi` (`vocabularyKeepPayload`, the
reader's keep, Quick Sheet's keep, Understanding's keep), so the words a
learner can search by meaning are the words whose meaning is stored. The
contract is written in `library_page`'s docstring, in the route, in the browser
client, and pinned by
`tests/test_vocabulary_paging.py::test_search_matches_the_fields_the_learner_database_holds`.
Searching the shared catalogue and intersecting would put a second store in the
search path for a case the keep paths already cover; if that ever becomes real,
it is a bounded change - the catalogue can be asked for matching terms and the
page filtered by them.

**3. The cursor belongs to the question it came from.** Every ordering ends in
a unique tie-breaker (`word`, which is unique per learner and language), so
`(added_at, word)`, `(next_review_at, word)` and `(lower(word), word)` are
total orders and no two rows share a key. The cursor carries the order and a
fingerprint of the filters (`query`, `status`, `focus`) alongside the key:
change any of them and the cursor is ignored rather than read against a
different ordering, so the caller gets that question's first page. A damaged
cursor is a first page too, never an error a learner has to read. What this
promises, and what the tests hold: a word whose sort key does not change is
seen exactly once; a word saved, rescheduled or graded mid-walk moves to where
its new key belongs and is met there.

**4. TRACKED · mobile `listLibraryVocabulary` owes pagination.** `mobile/` is
frozen (`AGENTS.md` §5), so it was not touched, and this is the item to pick up
when it thaws:

- `mobile/src/api/client.ts` → `listLibraryVocabulary()` calls
  `GET /api/library/vocabulary` with no parameters. The endpoint no longer
  answers with the whole library: it returns the first fifty words, plus
  `total`, `has_more` and `next_cursor`.
- `mobile/src/query/useReadingLibrary.ts` → `useLibraryVocabulary` holds that
  one response as a whole list.
- What it needs: `limit`/`cursor` in the client, an infinite query (or an
  explicit page) in the hook, and `summary` read for counts instead of the
  items being counted. `librarySchema` should gain the three new fields.
- Nothing is broken today - mobile is not shipped - and the mobile contract
  test mocks its own response, so it still passes.

**No other caller relies on the old behaviour.** Every browser caller asks for
a bounded page (held by `scripts/test_orena_vocabulary_paging.mjs`), and the
four server-side callers that used to read the listing to answer "is this word
saved?" - the word sheet, the collections list, a collection's cards and the
daily feed - now ask about the words they are drawing, through
`saved_vocabulary_words` and `saved_vocabulary_state`.

## GAP-H7, checked: the meter works, nothing a plan sells is wired to it (2026-09-22)

Asked to verify before closing, rather than assume. What is there:

- **The machinery is real and tested.** `record_usage` writes a `usage_events`
  row; `monthly_usage` sums this calendar month's rows; `account_state` reads
  that for each feature a plan lists. Six tests cover it end to end - an
  accepted turn is metered exactly once, nothing is metered when no provider
  answers, nothing when the cap refuses, and a repeated `request_id` is not
  metered again (`tests/test_text_discussion.py`, `tests/test_product_account_state.py`).
- **One caller.** `writing_coach/text_discussion.py` meters
  `reading.discussion_turn`, and that feature is in no plan's entitlements
  (`writing_coach/product/catalog.py`), so it can never appear on Hồ sơ.
- **Live sandbox, 2026-09-22**: `/api/product/me` reports `used: 0` for all
  nine features with `usage_state: "known"` - the meter was read and it is
  genuinely zero, not unreadable.

**Deferred, and left at zero.** The features a plan charges for - writing
evaluation, rewriting, lookups, saved words - do not call `record_usage` yet.
That is backend work with a human gate on it (commerce is not open;
`billing_ready` is false), not something a surface can fix, and nothing here
will be seeded or faked to make the bars look alive: a bar that reads zero
because nothing has been metered is telling the truth. The panel is the
component the source draws, and it will start saying something the day those
endpoints meter.

## Viewport check: 1920 is the reference, and what breaks below it (2026-09-22)

The source draws these screens at **1920x1080** and at **390x844**, and nothing
in between. 1920 is the reference and was not touched. The other widths were
tested for defects only - things that disappear, get crushed or run off the
edge - not treated as a brief to invent a layout.

**What was wrong, and is fixed** (neither changes 1920, both verified there):

- **Progress collapsed below its own width.** Holding the page to one screen is
  right at 1920, where the composition fits. Narrower, row two's four panels no
  longer fit across, the rows above grow, and the clamp crushed what was under
  them: at 1440 the rank ladder came out 40px tall, at 1024 the ladder and the
  rank card had **no height at all** - thirty-two rungs and the learner's own
  rank, invisible. The clamp now applies at 1600 and up, which is the
  composition it came from; below that the page scrolls like any page and
  everything is present (1440: all 32 rungs, ladder 1046px; 1024: all 32,
  ladder 1292px).
- **The Profile hero crushed its own copy.** The hero may wrap, but without a
  floor the copy simply got thinner instead: at 1024 the name, the rank pill,
  the plan pill and the XP line shared **94px** while the two actions kept
  their 267. The copy now has a floor of 320px, so the actions wrap under it
  instead (1024: copy 391px, actions on their own line). At 1920 the copy is
  990px and nothing moves.

**Verified clean**: Progress overview and Xu hướng, and Hồ sơ, at 1920, 1440,
1024 and 390 - no horizontal page scroll, nothing clipped outside the viewport,
the phone head and tabs intact at 390. Vocabulary, Library and Search were
swept at 1024 with nothing clipped; Home's card rail is `overflow-x: auto` by
design and is not a defect.

**For human review - the design does not define these, so nothing was
invented:**

- **What Progress is between 390 and 1920.** At 1440 and 1024 row two wraps
  from four panels to three and the screen becomes a scrolling page rather than
  one screen. That is the honest fallback, not a decision: whether the panels
  should shrink to stay four across, whether the ladder should stay a scrolling
  panel, and whether "one screen" is a rule at those widths, are design calls.
- **What Hồ sơ is at those widths.** The hero wraps its actions below the copy
  and the two panels stack. The source draws neither state.
- **Between 601px and about 900px** the phone composition has already been left
  behind (the phone rules stop at 600) while the desktop one has no room. No
  frame covers it; it is not currently drawn for any device Orena targets, so
  it was left as it falls out.

## One of the two "inherited failures" was the CRLF checkout, not the code (2026-09-22)

`scripts/test_orena_writing_workspace.mjs` has been failing on this machine for
weeks and passing in CI. It asserts `/showActivity\(\);
\s+const retry/`
against `ui/expression.js`. Git stores that file with LF and checks it out with
CRLF here, so the `` sits where the pattern expects `
` and the match
fails - the source is identical either way. It now passes locally only because
this lane rewrote that file with LF endings.

So the local expectation is **one** inherited failure, not two:
`scripts/test_m3_pronunciation_contract.mjs`, which is a real content
mismatch (a pronunciation projection that no longer carries the score the test
expects) and fails on a clean HEAD tree as well. Same family as the CRLF note
already recorded for `test_orena_grammar.mjs`: an environment failure, not an
application regression - and the gates that are written against source text
would be steadier matching `?
`.

