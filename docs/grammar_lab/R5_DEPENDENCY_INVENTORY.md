# R5 dependency inventory (chuẩn bị thay thế, không phải kế hoạch thay thế)

28/09/2026 · nguồn: Explore agent đọc trực tiếp code (không suy đoán), theo yêu cầu ở
`PHASE0_DECISIONS.md` §6 (Grammar Lab thay thế R5). Đây chỉ là **kiểm kê** cho việc lập kế
hoạch giai đoạn 4 — không phải thiết kế thay thế, không đổi code nào. Mỗi mục có file:dòng
thật để không phải đọc lại từ đầu khi tới lúc thiết kế.

**Bối cảnh quan trọng phát hiện thêm**: app có **hai front-end** đang chạy song song.
`/` (production hiện tại) render R5 thật qua `renderGrammar`. `/next` (UI mới, D-088) có route
`grammar`/`grammar/:id` khai trong `routes.js` nhưng **chưa có màn hình thật** — thư mục
`static/orena/screens/` chỉ có `coming/`, nên cả hai route này hiện render "Coming soon". Nghĩa
là R5 sống thật ở `/`, còn `/next` mới chỉ có chỗ trống đã đặt tên.

Đã có sẵn trong repo (không phải bản kiểm kê phụ thuộc, nhưng liên quan, đọc trước khi lập kế
hoạch): `docs/project/grammar_audit/ORENA_GRAMMAR_SYSTEM_AUDIT.md` (chất lượng nội dung — 508
mục, 0 mục tiếng Trung "curated", chỉ 3 mục tiếng Anh "curated") và
`docs/ORENA_GRAMMAR_MIGRATION_MAP.json`.

## 1. API routes (`app.py`)

Vào qua `writing_coach/languages/runtime.py`'s `active_grammar_*` helpers, cuối cùng tới
`writing_coach/languages/grammar_registry.py:37-101` — **điểm thay thế duy nhất** nếu muốn đổi
nguồn nội dung mà không sửa từng route.

| Route | Dòng | Đọc/Ghi R5 |
| --- | --- | --- |
| `GET /api/library/grammar` | app.py:2033-2065 | Đọc course + knowledge + tiến độ người học |
| `_static_grammar_detail()` (helper) | app.py:2069-2076 | Đọc |
| `GET /api/library/grammar/{id}/reference` | app.py:2079-2092 | Đọc |
| `GET /api/library/grammar/{id}` | app.py:2095-2121 | Đọc + tiến độ |
| `POST .../complete` | app.py:2124-2135 | Đọc (chỉ để validate id) + ghi tiến độ |
| `DELETE .../complete` | app.py:2138-2144 | Đọc (chỉ để validate id) + ghi tiến độ |
| `GET /api/grammar/{id}/practice` | app.py:3167-3222 | Đọc — **không có UI nào gọi route này hiện nay** |
| `POST /api/evaluate` | app.py:2370-2499, gọi `grammar_links_for_issues` ở 2444-2448 | Đọc toàn bộ knowledge base; **ghi `grammar_links` vào bài luận đã lưu** (2486) — dữ liệu đông cứng, đọc lại sau này không truy vấn lại R5 (`row_to_dict`, app.py:1068-1086) |

## 2. UI render màn ngữ pháp

- **`/` (đang chạy thật)**: `static/orena/ui/expression.js:2640-2756` (`renderGrammar`) gọi
  `api.grammarLibrary`/`api.grammarLesson` (`static/orena/infrastructure/api.js:95-98,302-306`),
  ghép với lớp phủ thủ công `static/orena/product/grammar-shelf.js` và
  `static/orena/content/patterns.js` (254 dòng, 6 mục — 3 en/3 zh — **id là Concept ID R5 viết
  cứng**, ví dụ `'a1-complete-sentences-and-basic-word-order'`; CI kiểm bằng
  `scripts/test_orena_grammar.mjs`). **Đổi/xoá Concept ID mà không sửa 6 id này sẽ làm patterns.js
  mồ côi âm thầm.**
- **`/next` (UI mới)**: `static/orena/shell/routes.js:28,67` khai route nhưng chưa có màn hình
  thật (`static/orena/screens/` không có thư mục `grammar/`).
- **Mobile**: `mobile/src/query/useGrammar.ts` + `mobile/src/api/client.ts:135-142` +
  `mobile/src/api/contracts/learning.ts:95,114-125` — đủ API/query wiring nhưng **không màn hình
  nào import nó** (`mobile/src/features` không có thư mục grammar).

## 3. `writing_grammar_transfer`

`writing_coach/writing_grammar_transfer.py` (117 dòng) — **không** tra theo Concept ID hay
`error_tag`. Dò chuỗi con (`CATEGORY_SIGNALS`, dòng 11-30) trong title/`quick_reference.lookup_tags`
của từng bài R5 theo *category* lỗi (enum nhỏ có sẵn), chấm điểm theo độ dài chuỗi khớp và
khoảng cách level (`_level_distance`, 48-65). Gọi từ `app.py:2444-2448`, đầu ra là `grammar_links`
đông cứng trong bài luận (mục 1).

## 4. Tra theo `error_tag`

**Không tồn tại.** Grep toàn repo cho `error_tag`/`by-error`/`by_error`: chỉ có trong
`grammar_lab/`/`docs/grammar_lab/`. Cái gần nhất là `writing_grammar_transfer` (mục 3), tra theo
*category* + chuỗi con, không phải `error_tag` hay Concept ID trực tiếp. `PHASE0_DECISIONS.md`
§5 đã ghi đây là câu hỏi mở, chưa chặn giai đoạn 1.

`export_error_tags.py` (Grammar Lab, một chiều: đọc `ERROR_CATEGORIES` của app bằng
`ast.literal_eval`, ghi `error_tags.json`) không đụng R5, không có chiều ngược lại.

## 5. Tool của Orena đọc R5/Concept ID

**Không có** — không có thư mục `tools/`, không có module Python "agent" nào đọc trực tiếp
nội dung R5. Agent chỉ điều hướng qua intent (`docs/project/AGENT_CONTRACT.md:185-201`, "backend
never sees routes"): `grammar.catalog`/`grammar.point{grammar_id}` chỉ là tên intent +
`grammar_id`, client mới gọi lại các route ở mục 1. `static/orena/agent/{contract,intents}.js` là
danh sách intent phía client, không đọc nội dung.

## 6. `grammar_learning_model.py` / `grammar_knowledge.py` / `grammar_catalog.py`

Xác nhận **không đổi** so với điều tra trước (`PHASE0_DECISIONS.md` §6): cả ba chỉ validate
hình dạng, không có nội dung ngữ pháp nhúng sẵn. Không gọi từ `app.py` lúc chạy — chỉ dùng trong
test và script CI (`scripts/validate_architecture.py`, chạy trong `ci.yml`).

## 7. Việc khác cần biết khi lập kế hoạch

- **Nguồn nội dung thật**: `writing_coach/languages/{english,chinese}/grammar_curriculum.json` +
  `grammar_knowledge.json`, nạp một lần lúc import qua
  `writing_coach/languages/grammar_registry.py:37-91` (`_REGISTRY`, `GrammarProvider`) — **điểm
  thay nguồn duy nhất** nếu muốn giữ nguyên mọi route ở mục 1.
- **Khoá lưu tiến độ** nhúng cả id lẫn version R5: `f"{language}:grammar:v{content_version}:
  {lesson_id}"` (app.py:2006-2009, dùng ở `_learning_repository`) — đổi id/versioning cần giữ
  định dạng này hoặc di chuyển dữ liệu tiến độ đang có.
- **Test/script bám chặt hình dạng R5** (dễ vỡ khi thay thế): `tests/test_static_grammar_knowledge.py`
  (đọc thẳng mã nguồn `app.py` bằng chuỗi, dòng 34-49 — refactor route dù tương đương ngữ nghĩa
  vẫn có thể làm test này vỡ), `tests/test_full_grammar_curriculum.py` (đếm cứng ≥130 EN/≥175 ZH),
  `tests/test_grammar_catalog.py`, `tests/test_grammar_learning_model.py`,
  `tests/test_grammar_universal_architecture.py`, `tests/test_m4_phase3_english_representatives.py`,
  `tests/test_m4_universal_grammar_full_rollout.py`.
- **`scripts/becoming_release_gate.py`**: phần lớn đường dẫn nó kiểm (`static/becoming/...`) đã
  bị xoá từ trước khi `/next` ra đời, và **không chạy trong CI** — coi là code chết, nhưng xác
  nhận lại với người trước khi xoá vì nó vẫn đọc `grammar_knowledge.py` thật.

## Việc chưa làm (thuộc giai đoạn 4, sau review kiến trúc)

Danh sách trên chỉ để biết **cái gì sẽ vỡ** khi thay R5 — chưa đánh giá tính khả thi, chưa đề
xuất cách thay, chưa động tới `grammar_registry.py` hay bất kỳ route nào. Việc đó thuộc giai
đoạn 4, cần review kiến trúc độc lập trước (`AGENTS.md` §1, `SPEC.md` §8).
