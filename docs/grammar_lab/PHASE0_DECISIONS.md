# Grammar Lab — Giai đoạn 0: kết quả và quyết định

26/09/2026 · branch `feature/grammar-lab` · trạng thái: chờ người duyệt, **chưa bắt đầu giai đoạn 1**.

**Claude Code (self-review, 27/09/2026): reviewed and approved to proceed.** Schema v0.2 khớp
SPEC §3; 520 dòng `validate.py` có một luật cho mỗi mục SPEC §5.2, và `test_validate_rules.py`
ép mỗi luật có cả case pass lẫn fail (`test_every_documented_rule_has_a_passing_and_a_failing_case`
canh việc này). 113 test pass, gồm cả `test_contract.py` (schema là Draft 2020-12 hợp lệ, sample
migrate round-trip, `error_tags.json` khớp `ERROR_CATEGORIES` của engine) và test hiệu năng (100
điểm dưới 5s). 10 điểm mẫu đọc tự nhiên, đúng ngữ pháp, đúng level, có pitfall thật gắn `error_tag`
hợp lệ. Ba câu hỏi ở §5 (nhãn lỗi thô, nối với R5 Concept ID, băng HSK 7-9) không chặn giai đoạn 1:
SPEC §7 giai đoạn 1 chỉ cần pipeline tiếng Anh + gold set người duyệt, không đụng engine hay R5.
Nối R5 Concept ID được SPEC §8 xếp vào giai đoạn 4; xem điều tra riêng về quan hệ với hệ thống
ngữ pháp hiện có của app trong `docs/project/CURRENT_HANDOFF.md` (mục Grammar Lab).

## 1. Đã giao

| Deliverable (SPEC §7) | File |
| --- | --- |
| Schema v0.2 | `grammar_lab/schema/grammar_set.schema.json` |
| Schema danh mục | `grammar_lab/schema/inventory.schema.json` |
| Nhãn lỗi xuất từ app | `grammar_lab/schema/error_tags.json` (sinh bằng `export-error-tags`) |
| File mẫu 10 điểm lên v0.2 | `grammar_lab/content/en/*.json`, `grammar_lab/functions/functions.yaml` |
| `validate` + test từng luật | `grammar_lab/pipeline/validate.py`, `grammar_lab/tests/` |

Kiểm tra (chạy cục bộ, không phải CI): `validate --lang en` sạch trên 10 điểm (~0,03 s);
113 test của `grammar_lab/tests` pass; 100 điểm validate dưới 5 s (có test canh).

## 2. Kết quả bước 4: nhãn lỗi của engine chấm bài

Engine **có** danh sách nhãn đóng, máy đọc được, nhưng **thô hơn nhiều** so với nhãn trong file mẫu.

- Nguồn: tuple `ERROR_CATEGORIES` trong `writing_coach/languages/english/profile.py` (13 nhãn) và
  `writing_coach/languages/chinese/profile.py` (18 nhãn). Không có tiếng Nhật.
- Tiếng Anh: `article, tense, agreement, word_choice, word_form, preposition, sentence_structure,
  punctuation, coherence, task, naturalness, spelling, other`.
- Tiếng Trung: `word_order, particle, aspect, complement, measure_word, ba_sentence, bei_sentence,
  conjunction, character_choice, word_choice, collocation, redundancy, punctuation, coherence, task,
  naturalness, register, other`.
- Engine trả mỗi lỗi dạng `{category, fragment, explanation_vi, suggestion, mini_rule_vi, confidence}`
  (`writing_coach/writing_evaluator_contract.py`, hợp đồng `writing-evaluation-v2`). `category` được ép
  bằng enum trong JSON Schema gửi cho model (Ollama ép lúc giải mã; API kiểu OpenAI chỉ nhận schema dạng
  văn bản) và được lọc lại sau khi nhận: nhãn ngoài danh sách bị bỏ (`writing_coach/writing_evaluation.py`).
  `/api/evaluate` đã trả `errors` và `issues` kèm `category`, nên giai đoạn 1 có thể không cần endpoint mới.
- Định danh nhãn phải khớp `^[a-z][a-z0-9_]*$`: nhãn có dấu chấm như `grammar.sva.3sg_s_missing` bị hợp
  đồng engine từ chối. Các nhãn chấm chỉ tồn tại trong `sample_v0.1.json`.
- Lab không import code app: `export-error-tags` đọc hằng số bằng `ast.literal_eval`. Test
  `test_error_tags_file_matches_engine_sources` báo lỗi nếu engine đổi danh sách mà file chưa xuất lại.

**Hệ quả cho SPEC §9 ("error_tags có đủ chi tiết không?")**: với danh sách hiện tại, câu trả lời là
**không đủ** để gắn một-một với grammar point. Ví dụ `tense` phủ cả hiện tại tiếp diễn, quá khứ đơn,
hiện tại hoàn thành và câu điều kiện loại 1; bước verify "wrong bị bắt đúng error_tag" chỉ phân biệt
được ở mức nhóm này, và `GET /api/grammar/by-error/{tag}` (giai đoạn 4) sẽ trả nhiều bài cho một nhãn.
Mở rộng nhãn là thay đổi engine, thuộc quyền người quyết; giai đoạn 0 không sửa engine.

## 3. Quyết định tự đưa ra (cần người xác nhận)

1. **Repo.** `D:\Orena-Grammar-Lab` ban đầu chỉ có `docs/grammar_lab/`, chưa phải repo git, và không có
   `PROJECT_STATE.md`/`CURRENT_HANDOFF.md`. Tôi `git init` tại chỗ, lấy `origin/main` (`7ff6985`) từ clone
   cục bộ `D:\Orena-Speaking` (remote `rallyx-0907/Orena-Coaching-App`), tạo `feature/grammar-lab` từ đó.
   Đây là một clone riêng, không phải worktree của clone kia. Hai file trạng thái nằm ở `docs/project/`.
2. **Ánh xạ nhãn lỗi.** Vì nhãn chấm không thuộc engine, mỗi pitfall được gán một nhãn engine (bảng §4);
   `error_tags` của điểm = các nhãn pitfall, không trùng. Nhãn cũ được giữ trong bảng dưới để không mất thông tin.
3. **Manifest bộ.** Một file mỗi điểm nên `meta` của v0.1 chuyển thành `content/<lang>/_set.json`
   (`explanation_locales`, `l1`). Luật locale đọc từ đây.
4. **Mã ngôn ngữ.** Thư mục, `--lang`, tiền tố ID dùng mã ngắn `en|zh|ja`; `target_lang` và khóa
   `realizations` dùng BCP-47 `en|zh-Hans|ja`. Locale giải thích `vi|en|zh-Hans|ja` (chặn `zh`, `zh-Hant`);
   L1 là ngôn ngữ `vi|zh|en|ja`.
5. **Thang level.** `level_scales` là khóa gốc trong `grammar_set.schema.json`; `if/then` theo `target_lang`
   ép `framework` và `value`; `rank` = vị trí 1-based, do `validate` kiểm. HSK 3.0 dùng `"1"`…`"9"` theo
   SPEC, dù phụ lục ngữ pháp của chuẩn gộp 7–9 thành một bậc — cần chốt trước giai đoạn 3.
6. **Function.** Realization "(planned)" của v0.1 chuyển sang trường `planned` (không kiểm tham chiếu);
   `realizations` chỉ chứa ID có thật và phải hai chiều với `function` của điểm.
7. **Luật thêm ngoài §5.2** (rẻ, bắt lỗi thật): tên file = `id`; `rank` đúng thang; prereq không cao
   level hơn điểm (SPEC §3); `contrast.with` phải có trong `contrasts`; `pitfall.error_tag` phải có trong
   `error_tags` của điểm; `wrong ≠ right`; `pitfall.l1` thuộc L1 khai báo; trùng `inv_id`.
8. **Chữ phồn thể.** Dùng bảng `TSCharacters.txt` của OpenCC (gói `opencc-python-reimplemented`,
   Apache-2.0); chỉ báo ký tự mà mọi dạng giản thể tương ứng đều khác nó, nên 乾/於/瞭 không bị báo nhầm.
   Phạm vi: mọi chuỗi ngôn ngữ đích của điểm zh-Hans, `source_refs` của điểm zh, mọi giá trị locale
   `zh-Hans` ở bất kỳ ngôn ngữ nào, và tiêu đề `zh-Hans` của function.
9. **`check.answer`** giữ là chỉ số (như v0.1); "answer nằm trong options" = chỉ số hợp lệ.
   Trùng phương án so sánh sau khi bỏ khoảng trắng thừa và không phân biệt hoa thường.
10. **`validate --mark`** (tùy chọn) ghi `status: flagged` và `flags: ["validate:<mã>"]`; chạy lại sau khi
    sửa sẽ xóa cờ `validate:*` nhưng không tự đổi status về (việc của `route`). Mặc định chỉ đọc.
11. **Điểm lỗi schema** không chạy luật ngữ nghĩa (tránh lỗi dây chuyền); functions.yaml lỗi thì bỏ kiểm
    tham chiếu function.
12. **`provenance`** của 10 điểm: `model: "unknown"`, `prompt_version: "sample_v0.1"`, `migrated_from`
    trỏ về file mẫu; `generated_at` đặt là ngày SPEC (26/09/2026) vì thời điểm sinh thật không được ghi.
    `source_refs` để rỗng: file mẫu không có mã nguồn.
13. **Schema thêm** `review.reject_reason` (danh sách cố định ở SPEC §6), `flags`, và bắt buộc `review`
    khi `approved`/`rejected` — để giai đoạn 2 không phải nâng schema.

## 4. Ánh xạ nhãn lỗi v0.1 → engine (tiếng Anh)

| Grammar point | Pitfall (câu sai) | Nhãn v0.1 gần nhất | Nhãn engine |
| --- | --- | --- | --- |
| present_simple.third_person_s | He go to school by bus. | grammar.sva.3sg_s_missing | agreement |
| | My mother have two sisters. | grammar.sva.have_has | agreement |
| there_is_are | In my room have a big bed. | grammar.existential.have_for_there_is | sentence_structure |
| | There is many people in the park. | grammar.existential.is_are_agreement | agreement |
| plural_nouns.regular | I have three brother. | grammar.noun.plural_s_missing | agreement |
| | Many student like this teacher. | grammar.noun.plural_s_missing | agreement |
| articles.a_an_the | I am student. | grammar.article.missing | article |
| | Sun rises in east. | grammar.article.missing | article |
| present_continuous.now | She reading a book. | grammar.tense.be_missing | tense |
| | I am go to school now. | grammar.tense.ing_missing | tense |
| past_simple | Yesterday I go to the market. | grammar.tense.past_unmarked | tense |
| | I didn't went there. | grammar.tense.did_plus_past | tense |
| present_perfect.experience | I have visited Da Lat last year. | grammar.tense.pp_with_finished_time | tense |
| | I have ever been to Japan. | grammar.tense.ever_in_positive | word_choice |
| countable_uncountable.much_many | I need many informations. | grammar.noun.uncountable_plural | word_form |
| | We have too many homeworks. | grammar.quantifier.much_many | word_choice |
| comparatives | This phone is more cheaper. | grammar.comparative.double | word_form |
| | She is taller me. | grammar.comparative.than_missing | sentence_structure |
| conditional_first | If it will rain, we will stay at home. | grammar.conditional.will_in_if_clause | tense |
| | If I have time, I visit you. | grammar.conditional.result_tense | tense |

Trong v0.1, pitfall không có nhãn riêng; cột "nhãn v0.1 gần nhất" là suy luận. Các nhãn v0.1 không
ứng với pitfall nào: `grammar.noun.irregular_plural`, `grammar.article.a_vs_the`, `grammar.article.a_vs_an`.
Engine không định nghĩa nghĩa từng nhãn, nên ranh giới `agreement` / `word_form` / `word_choice` là phán đoán;
verify ở giai đoạn 1 sẽ cho biết engine thực tế gán nhãn nào.

## 5. Việc cần người quyết trước giai đoạn 1

- Chấp nhận nhãn thô của engine, hay mở rộng danh sách nhãn (thay đổi engine, ngoài phạm vi lab)?
- Quan hệ với R5 Grammar KB đã có trong app (508 concept, Concept ID ổn định, "không phải syllabus thứ
  hai" theo CURRENT_HANDOFF): ID của Grammar Lab (`en.past_simple`…) hiện độc lập với Concept ID R5.
  Cần quyết cách nối trước giai đoạn 4. **Điều tra và khuyến nghị ở mục 6.**
- HSK 3.0: 9 bậc riêng hay bậc gộp 7–9 như phụ lục ngữ pháp.

## 6. Điều tra: quan hệ với R5 Grammar KB (27/09/2026, Claude Code)

**Bằng chứng** (đọc trực tiếp code, không suy đoán):

- `grammar_learning_model.py`, `grammar_knowledge.py`, `grammar_catalog.py` **không chứa nội dung** —
  cả ba chỉ validate hình dạng (luồng 8 giai đoạn `notice→...→transfer`; catalog phẳng), nhận nội dung
  làm tham số, không neo vào tiếng Anh/Trung cụ thể. Không có xung đột trực tiếp với schema
  `grammar_point` của lab.
- Nội dung thật nằm ở nơi khác và **đang chạy thật**: `writing_coach/languages/{english,chinese}/
  grammar_curriculum.json` (269 + 239 = 508 mục, khớp con số "508 concept") và `grammar_knowledge.json`
  (schema_version 2, đầy đủ cho cả 508). App expose qua `GET/POST /api/library/grammar*` trong `app.py`
  (dòng ~2033-2124), có route trong UI mới ở `/next` (`static/orena/shell/routes.js`: `grammar`,
  `grammar/:id`). Đây là **con đường học ngữ pháp thật của người học hôm nay**, không phải dữ liệu chết.
- R5 được khai là **protected area**: `AGENTS.md` §6 liệt "R5 Grammar contracts and Concept IDs";
  `ARCHITECTURE_INVARIANTS.md` ("Closed-stage protection") khóa ở baseline PR #44, giữ Concept ID ổn
  định, cấm "recreate superseded broad structural Grammar migration write paths".
- `ORENA_CONTENT_ARCHITECTURE.md` §11 nói thẳng hướng sản phẩm: nội dung Grammar luôn "neo vào R5 stable
  Grammar Concept ID"; Understanding Engine "có thể dùng Concept ID để làm căn cứ giải thích, không
  nhân đôi hay thay thế curriculum". Tức là vai trò "tra cứu cho Agent trích dẫn" **R5 đã làm rồi** —
  giả thuyết "curriculum vs tra cứu" trong đề bài không đứng được: cả hai vai trò đó đều đã là R5.

**Kết luận**: đây không phải trường hợp "một bên rỗng, tự quyết được" — validator rỗng, nhưng nội dung
mà nó validate (R5) rất sống và đang phục vụ người học. Grammar Lab, nếu đến giai đoạn 4, sẽ tạo ra
`grammar_point` cho **cùng một mục đích** (dạy ngữ pháp có thứ tự, có level) mà R5 đã đang làm — khác
với giả thuyết ban đầu là hai hệ phục vụ hai mục đích tách biệt. Đây đúng là quyết định sản phẩm, không
phải kỹ thuật.

**3 phương án cho giai đoạn 4** (không chặn giai đoạn 1 — SPEC giai đoạn 0-3 không đụng app):

1. **Thay thế R5** bằng nội dung Grammar Lab (schema đa khối, có pitfall gắn `error_tag`, đã verify qua
   engine chấm bài, đối chiếu EGP/HSK/JLPT). Giá trị cao nhất nhưng đụng thẳng "protected area" và
   "đóng ở baseline PR #44" — cần review kiến trúc riêng, rủi ro lớn nhất.
2. **Nối vào R5**: Grammar Lab sinh nội dung nhưng xuất bản dưới **Concept ID của R5** (không dùng
   `en.past_simple` song song); dùng để nâng cấp các mục "foundation" yếu (đặc biệt tiếng Trung, audit
   cũ ghi "239 generic/placeholder") và bổ sung năng lực R5 chưa có (pitfall ↔ `error_tag` ↔ nút "Học
   điểm này" mà SPEC §8 vẽ ra). Khớp đúng câu "neo vào Concept ID ổn định" trong Content Architecture.
   Việc kỹ thuật: ánh xạ ID lab → Concept ID hiện có, hoặc để R5 cấp Concept ID mới rồi lab gán ngược.
3. **Giữ tách biệt, không tích hợp**: Grammar Lab dừng ở vai trò thử nghiệm/R&D, không import vào app;
   R5 tiếp tục là con đường Grammar duy nhất. Rẻ nhất nhưng bỏ phí phần verify/pitfall đã đầu tư, và
   không có lý do rõ để tiếp tục sinh nội dung Anh/Trung song song R5 quá lâu.

**Khuyến nghị của Claude Code**: phương án 2. Nó tôn trọng "R5 không bị đụng, Concept ID ổn định" (đã
đóng băng), tận dụng năng lực pitfall/error_tag/verify mà R5 hiện không có, và không tạo ra "syllabus
thứ hai" mà app đã cam kết tránh. Không cần quyết ngay — chỉ cần trước giai đoạn 4; giai đoạn 1 (mục
này) chạy hoàn toàn offline, không đụng R5.

**Quyết định của người (28/09/2026): SỬA LẠI.** Bản ghi "chọn phương án 2" ngay trên là do Claude Code
hiểu sai; đây không phải điều người quyết. Người đã đính chính trực tiếp (28/09/2026): **phương án 1 —
Grammar Lab thay thế R5**. R5 bị đánh giá là không đáng tin và sẽ bị loại bỏ; Grammar Lab là nguồn ngữ
pháp chuẩn duy nhất đi tới. SPEC §8 đã viết lại theo hướng này (không còn "làm giàu concept R5 hiện có").

Giữ nguyên đoạn "chọn phương án 2" phía trên trong lịch sử tài liệu (không xóa) để không mất dấu vết
diễn biến quyết định — nhưng nó **không còn hiệu lực**, chỉ đoạn này mới là quyết định thật.

Phạm vi của lần sửa này: chỉ định hướng sản phẩm (Grammar Lab là nguồn ngữ pháp chuẩn) và tiếp tục xây
Grammar Lab theo hướng đó — không phải lệnh xóa/di chuyển code R5 ngay. R5 vẫn là **protected area**
(`AGENTS.md` §6) và đóng ở baseline PR #44 (`ARCHITECTURE_INVARIANTS.md`, "Closed-stage protection");
việc thay thế thật sự trong app (rút API `/api/library/grammar*`, các route UI, `writing_grammar_transfer`,
tra cứu theo `error_tag`, v.v. — xem kiểm kê phụ thuộc R5 đang được lập) là **schema/migration thay đổi
trạng thái sản phẩm hiện có**, thuộc diện `AGENTS.md` §1 "cần review kiến trúc độc lập" khi tới lúc thực
hiện — không tự phê duyệt. Việc này chưa xảy ra ở đây; đây chỉ là bước chuẩn bị (kiểm kê + tiếp tục xây
Grammar Lab), không đụng code app hay R5.

Số quyết định chính thức (D-xxx) sẽ cấp khi nhánh này tích hợp về `codex/work` — `D-xxx` chỉ được cấp
trên `codex/work` theo quy ước của repo; nội dung quyết định đã ghi đầy đủ ở đây và không chờ số mới có
hiệu lực. Không chặn giai đoạn 1–3.
