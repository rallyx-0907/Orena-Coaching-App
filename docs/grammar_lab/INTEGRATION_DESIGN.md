# Grammar Lab — thiết kế tích hợp vào app (đề xuất, chưa code)

28/09/2026 · nhánh `feature/grammar-lab-pipeline` · **để review kiến trúc độc lập** (`AGENTS.md`
§1 "Architecture review authority"; `SPEC.md` §8). Chưa có dòng code nào theo tài liệu này.

Tài liệu trả lời bốn câu: nội dung Grammar Lab được **lưu** thế nào trong app, được **phục vụ**
qua API nào, **thay R5** ở từng chỗ phụ thuộc ra sao, và **thứ tự cắt chuyển** nào an toàn. Dữ
liệu một điểm là `GRAMMAR_CONTENT_CONTRACT.md` v0.4 (PR vào `codex/work`:
rallyx-0907/Orena-Coaching-App#66); tài liệu này không đổi contract đó.

## 0. Hiện trạng (đọc từ `origin/codex/work` @ `b55e9d5`, không từ nhánh này)

`R5_DEPENDENCY_INVENTORY.md` được viết trên base cũ; các dòng dưới đây là bản làm lại trên
`codex/work`, chỉ về **dữ liệu** (không đọc code giao diện của lane UI ngoài chỗ nó gọi API và
đọc trường nào — `AGENTS.md` §3).

| Chỗ phụ thuộc | Vị trí trên `codex/work` | Phụ thuộc gì |
| --- | --- | --- |
| Nguồn R5 | `writing_coach/languages/{english,chinese}/grammar_curriculum.json` + `grammar_knowledge.json` (en 269 / zh 239), nạp lúc import | — |
| Registry | `grammar_registry.py:26-108` (`GrammarProvider`, `_REGISTRY`), `runtime.py:78-102` (`active_grammar_*`) | điểm thay nguồn duy nhất |
| Route thư viện | `app.py:2057-2168`: `GET /api/library/grammar`, `…/{id}`, `…/{id}/reference`, `POST/DELETE …/{id}/complete` | hình dạng R5 (curriculum row + `knowledge.lesson` + `learning_model`) |
| Route luyện | `app.py:3191-3242` `GET /api/grammar/{id}/practice` | `practice_blueprint`; chỉ `api.js:95-98` gọi, không màn nào |
| Khoá tiến độ | `app.py:2030-2033` `"{lang}:grammar:v{content_version}:{lesson_id}"` | id + version R5 |
| `/api/evaluate` | `app.py:2468-2472` → `grammar_links_for_issues(...)` → lưu `module_data["grammar_links"]` (`learning_repository.py:51-55`), đọc lại `row_to_dict` 1105-1109, `writing_contract.py:81-85` `_grammar_ref`, `writing-feedback.js:56` link `#/grammar?id=` | đông cứng id R5 trong bài đã lưu |
| `writing_grammar_transfer.py` | `CATEGORY_SIGNALS` 11-30, `_haystack` 38-45 (dò chuỗi con trong `lookup_tags`/`aliases`/`title`), output 100-115 | *category* lỗi + chuỗi con, `source: "static-grammar-kb"` |
| Nhãn lỗi engine | `english/profile.py:26-41`, `chinese/profile.py:26-45`, `runtime.active_error_categories()` | Grammar Lab `error_tags` **chính là** danh sách này (`export_error_tags.py`) |
| `/next` Grammar | `screens/grammar` gọi `api.grammarLibrary()`; `screens/grammar-concept` gọi `api.grammarLesson(id)`, `api.completeGrammar(id)`, đọc `learning_model.blocks[]` | hình dạng R5 |
| `/` (UI cũ) | `ui/expression.js:2643,2735` + `content/patterns.js` (6 en + 6 zh, id Concept R5) | hình dạng + id R5 |
| Orena (agent) | `AGENT_CONTRACT.md` §3 (`selected_item.type = grammar_point`), §6.1 `grammar.point{grammar_id}`, §7 (id đến từ tool read); client `grammar-concept/screen.js:178-231` `askOrena(... content_id: lesson.id)`. **Không có** code agent phía server đọc ngữ pháp | id R5 |
| Test/CI bám R5 | đếm cứng 269/239 (`test_m4_grammar_concept_specific_content.py`, `test_m4_universal_grammar_full_rollout.py`), tối thiểu (`test_full_grammar_curriculum.py`, `test_chinese_library.py`), hình dạng (`test_static_grammar_knowledge.py`, `test_grammar_storage_namespace.py`, `test_writing_grammar_transfer.py`, `test_writing_evaluation.py` 653/680/836…); `.mjs`: `test_orena_grammar`, `test_orena_extension_patterns` (đọc JSON R5, kiểm id patterns.js), `test_orena_screen_grammar` (fixture R5) — ci.yml 58, 74, 120, 128 | |

## 1. Lưu trữ: bộ nội dung đã xuất bản, chỉ đọc, đi cùng mã nguồn

**Đề xuất:** nội dung ngữ pháp là **nội dung chương trình**, không phải dữ liệu người học — nó
đi cùng mã nguồn như R5 hôm nay, không vào cơ sở dữ liệu. Nhờ vậy việc này không chạm tới hold
"learner-data persistence" (`AGENTS.md` §7), trừ tiến độ (§4).

```
writing_coach/languages/grammar_lab/
  en/index.json            # manifest + danh sách điểm (nhẹ, cho màn thư viện)
  en/points/<id>.json      # một điểm, đúng GRAMMAR_CONTENT_CONTRACT v0.4
  zh/index.json
  zh/points/<id>.json
  r5_redirects.json        # id R5 -> id Grammar Lab | null (xem §5)
```

- **Chỉ xuất bản điểm đã duyệt.** Grammar Lab thêm lệnh `cli publish --lang <l>`: chép điểm
  từ `grammar_lab/content/` sang thư mục trên, **chỉ** điểm có `status: approved` (người duyệt;
  `draft_ai`/`flagged` không bao giờ ra app), validate sạch và verify không còn cờ chưa xử lý.
  Pipeline không bao giờ tự đặt `approved`.
- `index.json`: `{schema_version, set_version, language, published_at, source_commit,
  points: [{id, title, native_title, level, point_type, function, prereqs, contrasts,
  error_tags, content_hash}]}`. `content_hash` = sha256 của file điểm — để client cache và để
  biết một điểm đã đổi.
- **Nạp lúc khởi động, lỗi thì dừng.** Provider đọc và validate toàn bộ bộ đã xuất bản với
  `grammar_set.schema.json` (bản copy đi cùng bộ) lúc import. Sai schema → app không khởi động
  (không fallback âm thầm về R5 — cùng tinh thần `AGENTS.md` §10).
- Không đưa `grammar_lab/pipeline` vào runtime của app: app chỉ đọc JSON đã xuất bản. Pipeline
  vẫn là công cụ offline.

## 2. Provider

`writing_coach/languages/grammar_lab_registry.py` (mới), **song song** với `grammar_registry.py`
chứ không nhồi vào `GrammarProvider` (hình dạng khác hẳn, trộn hai hình dạng là nguồn lỗi):

```python
@dataclass(frozen=True)
class GrammarLabSet:
    language: str                     # "en" | "zh"
    schema_version: str               # "0.4"
    set_version: str
    index: tuple[dict, ...]           # index.json points, theo thứ tự cấp độ rồi id
    by_id: Mapping[str, dict]         # điểm đầy đủ
    by_error_tag: Mapping[str, tuple[str, ...]]   # nhãn engine -> id điểm

def grammar_lab_set(language: str) -> GrammarLabSet: ...    # lỗi rõ ràng nếu ngôn ngữ chưa có bộ
def points_for_error(language, error_tag, *, target_level=None, limit=2) -> list[dict]: ...
```

`runtime.py` thêm `active_grammar_lab_set()` theo ngôn ngữ phiên như các `active_grammar_*`
hiện có.

## 3. API đọc mới (thêm vào, không sửa route R5)

Tiền tố mới để hai nguồn không lẫn trong giai đoạn chạy song song: `/api/grammar/v1/...`.

| Route | Trả về |
| --- | --- |
| `GET /api/grammar/v1/points?level=` | `{language, schema_version, set_version, levels: [...], points: [index item + completed]}` — `levels` do server trả (bỏ việc UI viết cứng `LEVEL_NAME_KEY`) |
| `GET /api/grammar/v1/points/{id}` | `{language, point: <contract v0.4>, completed, content_hash}`; 404 nếu id không có trong bộ của ngôn ngữ phiên |
| `GET /api/grammar/v1/by-error?error_tag=&level=&limit=` | `{language, error_tag, points: [{grammar_id, title, level, reason}]}` — tra theo nhãn engine (§5) |
| `POST /api/grammar/v1/points/{id}/complete`, `DELETE …` | như route R5 tương ứng, trên khoá tiến độ mới (§4) |

- Ngôn ngữ = ngôn ngữ phiên (như route R5), id phải mang tiền tố ngôn ngữ đó (`en.`/`zh.`).
- Response giữ **nguyên** contract v0.4 trong `point` — server không dịch sang hình dạng khác; UI
  vẽ thẳng contract (đúng lộ trình `CURRENT_HANDOFF`: màn Grammar vẽ `GRAMMAR_CONTENT_CONTRACT.md`).
- `GET /api/grammar/{id}/practice` (R5, không màn nào gọi) **không** có bản v1: `quick_practice`
  thay phần luyện có trong điểm; luyện viết tự do sau điểm là tính năng riêng, cần quyết định
  sản phẩm (§8).

## 4. Tiến độ người học — cần review kiến trúc

Khoá R5: `"{lang}:grammar:v{content_version}:{lesson_id}"`. Đề xuất cho Grammar Lab:
`"{lang}:grammar-lab:v1:{point_id}"` trong **cùng kho tiến độ hiện có** (`_learning_repository`),
không bảng mới, không cột mới. Hoàn thành vẫn không phải thành thạo (giữ
`completion_is_mastery: false`).

**Không tự di chuyển tiến độ R5.** Id R5 và id Grammar Lab không tương ứng 1-1 (R5 có 508 mục
tới C2/HSK7-9; bộ lõi mới là A1–A2/HSK1–2 và tách/gộp khác). Hai lựa chọn cho người review:

1. Không mang sang: tiến độ R5 ở lại dưới khoá cũ, không hiển thị ở màn mới. Đơn giản, người
   học thấy mất dấu "đã học".
2. Mang sang khi đọc: dùng `r5_redirects.json` (§5), một điểm mới coi là đã hoàn thành nếu mọi
   mục R5 trỏ tới nó đã hoàn thành. Không ghi lại dữ liệu cũ, không import lúc khởi động.

Đây là quyết định về dữ liệu người học → thuộc hold của `AGENTS.md` §7 và cần **review kiến
trúc độc lập** trước khi code; tài liệu này không chọn.

## 5. Thay R5 ở từng chỗ phụ thuộc

### 5.1 `writing_grammar_transfer` → tra theo `error_tag`

Hôm nay: dò chuỗi con của *category* trong `lookup_tags`/`aliases`/`title` R5. Với Grammar Lab
không cần đoán: `error_tags` của mỗi điểm **là** nhãn của engine (`export_error_tags.py` sinh từ
`ERROR_CATEGORIES`), và `issue.category` của `/api/evaluate` cũng là nhãn đó.

`points_for_error(language, category, target_level, limit=2)`:

1. Ứng viên: điểm có `category` trong `error_tags`.
2. Xếp: khoảng cách cấp độ tới `target_level` (rank trong `level`, thay `_LEVEL_ORDERS` viết
   cứng), rồi điểm có `common_mistakes` mang đúng nhãn đó, rồi id.
3. Mỗi điểm chỉ link một lần trong một bài (giữ quy tắc hiện tại).

Output giữ **nguyên** hình dạng link hiện có để `_grammar_ref` và `writing-feedback.js` không
đổi: `{issue_id, category, grammar_id, title, level, reason, evidence, source: "grammar-lab"}`.
Nhãn không phải ngữ pháp (`spelling`, `naturalness`, `task`, `register`, `coherence`…) không có
điểm nào mang → không link, không đoán.

Thay đổi tối thiểu tại `app.py:2468-2472`: gọi `points_for_error` thay cho
`grammar_links_for_issues` (một chỗ gọi). `writing_grammar_transfer.py` và test của nó bị xoá ở
bước R5 ra đi (§6 bước 6), không trước.

### 5.2 Link đông cứng trong bài đã lưu

Bài đã chấm trước khi chuyển giữ `grammar_links` với id R5 và `source: "static-grammar-kb"` —
**không sửa dữ liệu đã lưu**. Khi mở link id R5, client gọi redirect: `r5_redirects.json` cho id
Grammar Lab tương ứng hoặc `null` (mở thư viện). Bảng này sinh từ `source_refs`/`functions.yaml`
khi danh mục được duyệt, commit cùng bộ xuất bản; nó là cách duy nhất id R5 còn được đọc sau
khi R5 bị xoá.

### 5.3 `patterns.js`

Chỉ UI cũ `/` (`ui/expression.js`) và hai gate CI dùng nó; nội dung của nó (dòng công thức,
`parts`, ghi chú, so sánh) nay nằm trong `pattern`/`compare` của contract. **Không port**: nó ra
đi cùng UI cũ ở cutover D-091. Cho tới lúc đó R5 còn, nên `test_orena_extension_patterns.mjs`
vẫn đúng. `patterns.js`, `grammar-shelf.js` (nếu UI mới không còn dùng) và hai gate `.mjs` bị
xoá trong cùng thay đổi xoá R5.

### 5.4 Orena (agent)

- `AGENT_CONTRACT.md` bump: `grammar.point{grammar_id}` và `selected_item {type: grammar_point,
  id}` dùng id Grammar Lab (`CURRENT_HANDOFF` đã ghi việc này). Contract do lane `codex/work`
  sửa, không phải lane Grammar Lab hay lane Intelligence (D-086).
- Tool đọc ngữ pháp của Orena (khi lane Intelligence viết) đọc qua **provider/API v1** (`points/{id}`,
  `by-error`), không đọc file — đúng §7 "id đến từ tool read, không từ generation".
- `evidence.source = grammar.catalog` giữ nguyên tên.

### 5.5 Màn `/next`

Lane UI dựng lại hai màn Grammar trên `/api/grammar/v1/*` sau khi contract được merge (lộ trình
`CURRENT_HANDOFF`). Fixture `scripts/fixtures/api/library_grammar*.json` được thay bằng fixture
sinh từ bộ xuất bản thật.

## 6. Thứ tự cắt chuyển

Mọi bước trước bước 6 **chỉ thêm**; R5 và UI cũ chạy nguyên. Mỗi bước có đường lùi riêng.

| # | Bước | Ai | Điều kiện vào | Đường lùi |
| --- | --- | --- | --- | --- |
| 0 | Contract merge (#66) + DECISION_LOG "R5 được thay bằng Grammar Lab" | người | review của lane UI | — |
| 1 | Danh mục bộ lõi duyệt; sinh + verify; người duyệt từng điểm (`approved`) | Grammar Lab + người | bước 0 | không đụng app |
| 2 | `cli publish`, `grammar_lab_registry.py`, route `/api/grammar/v1/*`, test; CI chạy validate trên bộ xuất bản | lane được giao | **review kiến trúc độc lập** tài liệu này (đặc biệt §4) | gỡ route mới; R5 không đổi |
| 3 | Màn Grammar `/next` vẽ contract qua v1 | lane UI | bước 2 trên nhánh | `/next` chưa là `/` |
| 4 | `/api/evaluate` link bằng `points_for_error` cho bài mới; redirect cho id R5; bump `AGENT_CONTRACT` | lane được giao | bước 2; bộ lõi phủ đủ nhãn ngữ pháp của cả hai ngôn ngữ | đổi lại một chỗ gọi (`app.py:2468-2472`) |
| 5 | Cutover D-091: `/` thành UI mới; `renderGrammar`, `patterns.js` ra đi cùng UI cũ | theo D-091 | bước 3 | theo kế hoạch D-091 |
| 6 | Xoá R5: route `/api/library/grammar*`, `/api/grammar/{id}/practice`, `grammar_registry` R5, JSON R5, `writing_grammar_transfer.py`, các test/gate bám R5 (§0) | lane được giao, **người cho phép** | bước 4 + 5; **quyết định về độ phủ** (§7) | `git revert` một commit; dữ liệu người học không bị đụng |

Bước 6 là bước duy nhất xoá; nó không đụng dữ liệu người học đã lưu (link đông cứng đọc qua
redirect, tiến độ theo lựa chọn ở §4).

## 7. Rủi ro và điều người cần quyết

1. **Độ phủ.** R5 có 508 mục tới C2 / HSK7-9; bộ lõi đề xuất chỉ A1–A2 / HSK1–2. Sau bước 6
   người học B1+ không có bài ngữ pháp và `by-error` ít kết quả hơn. Bước 6 phải chờ bộ phủ các
   cấp mà người học thật đang ở, hoặc người chấp nhận khoảng trống — quyết định sản phẩm.
2. **Ngôn ngữ giải thích.** Contract hiện chỉ có `vi` (R5 cũng chỉ có `*_vi`). Nhãn UI theo
   ngôn ngữ người học (D-068), nhưng phần giải thích cho người học L1 khác `vi` là việc sinh
   thêm locale — không chặn tích hợp, cần quyết khi mở L1 mới.
3. **Tiến độ R5** (§4): chọn 1 hoặc 2, qua review kiến trúc.
4. **Engine không chấm được câu Trung ngắn** (422 dưới 10 ký tự) và bỏ sót nhiều lỗi rõ ràng —
   đây là giới hạn chất lượng của verify, không phải của tích hợp, nhưng quyết định bao nhiêu
   điểm đạt `approved`.
5. **Luyện viết tự do** sau điểm (thay `/api/grammar/{id}/practice`): giữ, bỏ, hay làm lại —
   quyết định sản phẩm.

## 8. Ngoài phạm vi

Code; sửa `AGENT_CONTRACT.md` (lane `codex/work`); UI (lane UI); schema/migration cơ sở dữ liệu
(không cần, trừ lựa chọn tiến độ ở §4); `mobile/` (đóng băng, `AGENTS.md` §5 — wiring
`useGrammar.ts` được cập nhật khi mobile mở lại).
