# Grammar Lab — Grammar content contract (proposal, schema v0.4)

28/09/2026 · soạn ở nhánh `feature/grammar-lab-pipeline` (Grammar Lab) · nguồn: chỉ đạo trực
tiếp của người, ghi lại tại đây để không dựa vào lịch sử chat.

**Trạng thái: đề xuất gửi lane UI review.** Người đã duyệt cấu trúc và giọng văn v0.4 qua trang
preview nội bộ của Grammar Lab (28/09/2026, 11 điểm EN + 3 điểm ZH). Lane UI review tài liệu này
theo nhu cầu của hai màn Grammar, liệt kê chỗ thiếu; người duyệt và merge. Đường dẫn
`grammar_lab/...` bên dưới (schema, validate, verify, prompt) nằm ở nhánh
`feature/grammar-lab-pipeline`, chưa có trong `codex/work`. Tài liệu định nghĩa chính xác dữ liệu một điểm ngữ pháp mang, đủ để UI vẽ: công thức
nổi bật với ô tô màu theo vai trò, minh hoạ timeline/word_order/morphology, ví dụ tô màu cùng
bảng màu, so sánh hai cột, sai/đúng, luyện nhanh bấm được. Nó **không** định hình dáng UI (màu,
layout, font) — `docs/project/DESIGN_CONTRACT.md`/D-067 vẫn là nguồn UI thật.

Đây là **nguồn ngữ pháp chuẩn duy nhất** đi tới (`docs/grammar_lab/PHASE0_DECISIONS.md` §6 ở nhánh Grammar Lab: Grammar Lab thay thế
R5). Phần giải thích viết đầu bằng tiếng Việt (nay là `vi`; `en`/`zh` theo mục "Locale" bên dưới),
giọng rõ ràng, cho người lớn, không văn vẻ. `story`
(`grammar_lab/STORY_SPEC.md`, `grammar_lab/VOICE.md`) là nội dung phụ, tuỳ chọn (`blocks: [story]`), chỉ dùng khi người học
cần giải thích thêm; prompt story v3 đang tạm dừng.

## Phạm vi, khung đích, phiên bản (rev 29/09/2026, sau review PR #66)

- **Khung đích là frame 47** (Grammar Concept, `gconcept` — route thật duy nhất) và frame 44
  (Grammar Library). Những gì chỉ frame 23 vẽ (breadcrumb, timeline có nhãn sự kiện, so sánh
  nhiều lý do mỗi bên, khối "Use it" có mic) **không bắt buộc** ở hợp đồng này; frame nào là
  chuẩn vẫn là quyết định của người (`UI_BACKEND_GAPS.md` mục 4).
- **Hợp đồng chỉ mô tả nội dung tác giả.** Trạng thái học viên (đã học, đã lưu, lỗi gần đây,
  gợi ý) không nằm trong đây — app nối vào theo `id` (§9).
- **Locale.** Mọi field "locale map" là `{"vi": …, "en": …, "zh-Hans": …}` (khoá tiếng Trung là `zh-Hans`, đúng
  schema của Grammar Lab; UI ánh xạ ngôn ngữ giao diện `zh` sang khoá này). `vi` và `en` được sinh
  cùng lúc từ đầu cho mọi điểm (quyết định của người, 29/09/2026); `zh-Hans` là một đợt sau, khi nội
  dung đã ổn định. Validate `locale.missing` chạy trên **mọi** locale map của điểm với luật cố
  định, không phải cấu hình: **`vi` luôn bắt buộc** (mọi `status`); **`en` bắt buộc ở bước
  chuyển sang `approved`** (một điểm `draft_ai`/`auto_ok`/`flagged` chưa có `en` vẫn hợp lệ);
  `zh-Hans` không bao giờ bắt buộc. Ngoại lệ là nhãn `function` (mục 0), cần đủ `vi`, `en`, `zh-Hans`. Thiếu
  key thì app rơi về `en`, không bao giờ rơi âm thầm về `vi`. Mọi ví dụ bên dưới chỉ ghi `vi`
  cho gọn.
- **Chữ Hán là giản thể** (`zh-Hans`), cả nội dung lẫn locale giải thích (`docs/grammar_lab/SPEC.md`
  ở nhánh Grammar Lab); ký tự phồn thể bị validate báo (`zh.traditional_char`).
- **Phiên bản.** `version` là số nguyên tăng khi nội dung một điểm đổi. Thêm field tuỳ chọn hoặc
  siết validate = đổi phiên bản schema (`v0.x`) nhưng không phá điểm đã publish; bỏ/đổi tên field
  hay đổi nghĩa = phá vỡ, cần bump schema và migrate ghi rõ. Người sửa schema: lane Grammar Lab
  đề xuất, lane UI review, người merge. Ở v0.4 đã bỏ `title`/`summary` ở cấp điểm (chuyển vào
  `header`); **các điểm preview là bản thử, không ổn định** — được sinh lại theo schema này trước
  khi có điểm nào `approved`, nên không có gì cần migrate. Bản vá 30/09/2026 (mục "Locale", nhãn
  `function`, bảng pinyin §8, `personal_production` §7b, tên field `morphology`) là thêm field và
  siết validate, không phá điểm đã publish.

## 0. Metadata (không do model sinh)

Nhắc lại tại chỗ (không cần đọc v0.2):

| Field | Kiểu | Quy tắc |
| --- | --- | --- |
| `id` | string | `<lang>.<slug>` (`en.present_perfect_experience`, `zh.ba_sentence`), bất biến sau khi publish |
| `version` | int | tăng khi nội dung đổi; tiến độ/bookmark của học viên khoá theo `id`, **không** theo `version` |
| `status` | enum | `draft_ai | auto_ok | flagged | approved | rejected`. **Chỉ `approved` được tới UI**; lọc là việc của nguồn cấp (`grammar.catalog`, `grammar.point`), UI không tự lọc |
| `target_lang` | `en | zh-Hans` | |
| `function` | string | `fn.<snake_case>`, khoá **nhóm** của Library (thay `module`/`category` của R5), kèm nhãn hiển thị bên dưới. Không phải nguồn của `header.sub` |
| `level` | object | `{framework, value, rank}` — `cefr` A1–C2 (`rank` 1–6) cho EN; `hsk3` cho ZH với bảng mức HSK 3.0 là **1–9** (`value` `"1"`…`"9"`, `rank` = số đó). Đề cương xếp chung dải 7–9: mục nào đề cương không tách riêng lấy mức thấp nhất của dải (`"7"`) |
| `sequence` | int | thứ tự đọc trong cùng `function` + `level` (tăng dần, duy nhất trong nhóm). **Điểm "tiếp theo"** = điểm có `sequence` kế tiếp cùng nhóm, hết nhóm thì điểm đầu nhóm/level kế tiếp mà mọi `prereqs` đã nằm trước nó; `prereqs` chỉ là điều kiện, không phải thứ tự |
| `prereqs` | id[] | phải là DAG, id phải tồn tại |
| `contrasts` | id[] | điểm dễ nhầm. **Đối xứng bắt buộc**: A liệt B thì B phải liệt A (validate `contrasts.asymmetric` trên cả danh mục) |
| `error_tags` | string[] | nhãn engine của điểm |
| `source_refs` | object[] | nguồn tham chiếu (khung chuẩn, sách) |
| `aliases` | string[] | **id R5 cũ** mà điểm này thay thế (cầu nối §9); rỗng cho điểm mới |
| `point_type` | enum | `tense_aspect | word_order | morphology | other` — điểm này chủ yếu nói về điều gì; quyết định kiểu minh hoạ (§2) |

**Nhãn hiển thị của `function`.** Khoá `fn.*` không bao giờ lên màn hình. Mỗi `function` được dùng
có một mục trong file `functions` đi cùng bộ xuất bản (`functions.yaml`):

```json
{"id": "fn.past_experience",
 "title": {"vi": "Nói về trải nghiệm", "en": "Talking about experience", "zh-Hans": "谈论经历"}}
```

`title` là locale map **đủ ba key `vi`, `en`, `zh-Hans`** (nhãn ngắn, ít chữ; là chỗ duy nhất `zh-Hans` bắt
buộc ngay từ đầu vì Library dùng nó cho học viên đặt giao diện tiếng Trung). Header nhóm của
Library lấy `title[ngôn ngữ giao diện]`, thiếu thì `en`. Validate `locale.missing` (theo luật
trên, với `vi`+`en`+`zh-Hans`) chạy trên mọi `function` mà có điểm đang dùng. `zh-Hans` ở đây là giản thể
(`zh.traditional_char`).

Đối với tiếng Trung, `point_type` chọn theo hiện tượng: 了/过/着 → `tense_aspect`; 把/被 →
`word_order` (cùng loại); bổ ngữ, lượng từ → `other`; lặp AA/AABB, 儿化 → `morphology`. Không
thêm `timeline.shape` riêng cho tiếng Trung cho đến khi UI vẽ được (thêm giá trị = thêm cách vẽ);
tạm ánh xạ 了 hoàn thành → `point_past`, 过 trải nghiệm → `unspecified_past`, 着 tiếp diễn →
`ongoing_now`.

## 1. header

```json
"header": {
  "title": {"vi": "Hiện tại hoàn thành (trải nghiệm)"},
  "native_title": "Present perfect",
  "sub": {"vi": "trải nghiệm"},
  "level": {"framework": "cefr", "value": "A2", "rank": 2},
  "summary": {"vi": "Nói đã từng làm gì, không nêu thời điểm."}
}
```

Ánh xạ lên màn hình:

- **Tiêu đề màn hình / thẻ Library = `native_title`** (chuỗi phẳng, ngôn ngữ đích; UI đánh dấu
  `lang` theo `target_lang`; tiếng Trung kèm `native_title_pinyin`). Không bao giờ bind `title`
  vào ô tiêu đề — đó là lỗi hiển thị chữ Việt cho học viên hỗ trợ Anh/Trung mà `model.js` đã sửa
  một lần (D-079).
- **`title`** (locale map, giải thích) là tên gọi trong ngôn ngữ hỗ trợ của học viên; dùng ở nơi
  cần gloss (dòng phụ, tìm kiếm, sheet), không phải ô tiêu đề.
- **`sub`** (locale map, ngắn, ≤ 24 ký tự, khác `summary`) đổ vào ô thứ ba của dòng
  `Grammar · {level} · {sub}` ở đầu frame 47; `summary` (một câu) hiển thị riêng bên dưới.
- `level` (CEFR cho tiếng Anh, HSK 3.0 cho tiếng Trung) phải bằng `level` của điểm (validate
  `header.level_mismatch`). Ở v0.4 không còn `title`/`summary` ở cấp điểm.

## 2. pattern — công thức, tách khỏi câu ví dụ

```json
"pattern": {
  "formula": [
    {"text": "S", "role": "subject", "label": {"vi": "chủ ngữ"}},
    {"text": "have/has", "role": "aux", "label": {"vi": "trợ động từ"}},
    {"text": "V3", "role": "verb", "label": {"vi": "quá khứ phân từ"}},
    {"text": "for/since …", "role": "time", "label": {"vi": "mốc thời gian"}, "optional": true}
  ],
  "variants": {
    "negative": [{"text": "S", "role": "subject", "label": {"vi": "chủ ngữ"}},
                 {"text": "haven't/hasn't", "role": "aux", "label": {"vi": "trợ động từ phủ định"}},
                 {"text": "V3", "role": "verb", "label": {"vi": "quá khứ phân từ"}}],
    "question": ["..."]
  },
  "illustration": {"kind": "timeline", "timeline": {"shape": "unspecified_past"}}
}
```

- `formula` là **ô trừu tượng**, không bao giờ là một câu cụ thể — câu cụ thể chỉ nằm trong
  `examples`. Mỗi ô: `text` (ô như trên thẻ ngữ pháp: `S`, `V3`, `把`, `主语`), `role` (để tô
  màu), `label` (tên ô bằng tiếng Việt), `optional` (ô có thể vắng trong câu đúng).
- `text` của ô **không chứa `+`** — UI tự vẽ dấu nối giữa các ô (`N + -s` là hai ô `N` và
  `-s/-es`; validate: `formula.slot_has_joiner`).
- Ô là một lựa chọn giữa nhiều dạng → `options`: `text` gọi tên lựa chọn, mỗi phần tử là một
  dạng (`{"text": "be", "options": [{"text": "is"}, {"text": "are"}]}`, `much | many`, `a | an`).
  Tối thiểu 2, không trùng (`formula.option_duplicate`); tiếng Trung mỗi lựa chọn có `pinyin`.
- Công thức phải phủ **mọi dạng tiêu đề nêu**. Verify kiểm bằng model khác họ với model sinh
  (blind-solve, hiện là Groq): đưa tiêu đề + tóm tắt + công thức (kèm các lựa chọn), hỏi còn
  thiếu dạng nào; thiếu → cờ `formula_incomplete` (điểm bị flagged). Prompt: `grammar_lab/prompts/verify_formula.md`.
- Hai cách dùng khác nhau thì tách thành hai điểm, không gộp một công thức: mạo từ là
  `en.articles.a_an` (không xác định) và `en.articles.the` (xác định), `compare` lẫn nhau.
- `variants.negative`/`variants.question`: cũng là ô, chỉ khai khi điểm có dạng phủ định/nghi
  vấn riêng.
- `role` dùng chung cho ô công thức và span trong ví dụ, để UI tô cùng màu: `subject | verb |
  aux | object | complement | classifier | time | place | marker | particle | connector | other`
  (`classifier` = lượng từ tiếng Trung; tên role là của hợp đồng — renderer tự ánh xạ sang bucket màu
  của nó, vd. `aux` ↔ `auxiliary`, `time`/`place` ↔ bucket riêng):
- `illustration.kind` do `point_type` quyết định (validate: `illustration.kind_mismatch`):

  | point_type | kind | Dữ liệu |
  | --- | --- | --- |
  | `tense_aspect` (thì/thể) | `timeline` | `timeline.shape`, enum đóng: `point_past`, `ongoing_now`, `unspecified_past`, `habit`, `future_condition`, `future_plan`, `past_ongoing` (thêm giá trị = thêm cách vẽ ở app); `relevance` (locale map, tuỳ chọn); nhãn điểm trên trục do UI tự sinh từ `shape` (nhãn/chú thích do tác giả từng điểm như "moved"/"now" của frame 23 là ngoài phạm vi, chưa có `events[]`) |
  | `word_order` (trật tự câu, vd. 把) | `word_order` | không có — UI vẽ chính các ô `formula` thành hộp theo thứ tự |
  | `morphology` (biến đổi từ) | `morphology` | Mảng `pattern.illustration.morphology` (cạnh `kind`), 1-4 mục `{base, affix, result, affix_note?, note?}`, vd. `{"base": "book", "affix": "-s", "result": "books"}`. **Chữ ngôn ngữ đích và chú thích tiếng Việt là hai field riêng**: `base`, `affix`, `result` chỉ chứa chữ đích (không ngoặc, không "(lặp)"); chú thích về phụ tố là `affix_note` (locale map, vd. `{"vi": "lặp lại động từ"}`), chú thích cả hàng là `note` (locale map). Tiếng Trung: lặp `{base: 看, affix: 看, result: 看看, affix_note: {vi: lặp lại}}`, 儿化 `{base: 花, affix: 儿, result: 花儿}`; bảng 了/过/着 không hợp mô hình gốc+phụ tố nên là `tense_aspect` hoặc `other`. Chữ Hán có `base_pinyin`, `affix_pinyin`, `result_pinyin` |
  | `other` | `none` | không có |

## 3. when_to_use

2-4 ý ngắn (locale map), mỗi ý một tình huống cụ thể. Frame 47 **không vẽ** khối này; nội dung
được giữ, chỗ hiển thị (sau "⋯" hay trong sheet) do lane UI quyết, không thì ghi vào
`UI_BACKEND_GAPS.md`.

## 4. examples — tô mọi phần thuộc công thức

```json
{
  "text": "I have lived here since 2020.",
  "form": "affirmative",
  "spans": [
    {"start": 0, "end": 1, "role": "subject"},
    {"start": 2, "end": 6, "role": "aux"},
    {"start": 7, "end": 12, "role": "verb"},
    {"start": 18, "end": 28, "role": "time"}
  ],
  "annotation": {"vi": "bắt đầu 2020 → vẫn đúng bây giờ"},
  "translation": {"vi": "Tôi sống ở đây từ năm 2020."}
}
```

- `form`: câu theo công thức nào (`affirmative` = `formula`, `negative`/`question` =
  `variants.<form>`).
- `spans` tô **mọi** phần của câu ứng với một ô của công thức đó (cả `aux` lẫn `verb`), với
  đúng `role` của ô → UI tô cùng màu. Validate: mỗi role của ô **không optional** phải có ít
  nhất một span (`example.formula_role_missing`); không span nào có role ngoài công thức
  (`example.span_role_not_in_formula`); `form` phủ định/nghi vấn phải có công thức tương ứng
  (`example.form_without_variant`).
- `start`/`end` là vị trí ký tự (0-based, `end` không gồm). Model đưa chuỗi con, code tự tính
  vị trí — model không phải đếm ký tự.

## 5. compare

Một cặp so sánh cho mỗi điểm dễ nhầm (không phải nhiều lý do mỗi bên — đó là dạng frame 23, chưa
bắt buộc): `with` (id điểm dễ nhầm, phải có trong `contrasts`, và vì `contrasts` đối xứng nên
điểm kia cũng so sánh ngược lại), `this_meaning`/`other_meaning` (**locale map**),
`this_example`/`other_example` (chuỗi ngôn ngữ đích; tiếng Trung kèm `this_example_pinyin`/
`other_example_pinyin`). Ví dụ:

```json
"compare": [{
  "with": "en.past_simple",
  "this_meaning": {"vi": "Đã từng, không nêu lúc nào"},
  "this_example": "I have been to Japan.",
  "other_meaning": {"vi": "Xong ở một thời điểm đã nêu"},
  "other_example": "I went to Japan in 2019."
}]
```

## 6. common_mistakes

`wrong`, `right`, `reason` (lý do ngắn, locale map), `error_tag` (nhãn engine, phải nằm trong
`error_tags` của điểm; tiếng Trung dùng nhãn thật như `ba_sentence`), `l1` (ngôn ngữ mẹ đẻ mà lỗi
này điển hình). Verify: engine phải bắt `wrong` đúng `error_tag`, `right` phải sạch.

Là **mảng có thứ tự**, tác giả xếp theo mức phổ biến. Frame 47 vẽ **một** khối "Common mistake":
renderer chọn phần tử đầu tiên có `l1` khớp ngôn ngữ mẹ đẻ của học viên, không có thì phần tử
`[0]`; các phần tử còn lại dành cho sheet/`⋯`.

## 7. quick_practice

```json
{
  "q": "She ___ to Japan twice.",
  "options": [
    {"text": "has been", "error_tag": null},
    {"text": "was", "error_tag": "tense"},
    {"text": "has went", "error_tag": "word_form"}
  ],
  "answer": 0,
  "explain": {"vi": "Trải nghiệm, không nêu thời điểm → has + V3."}
}
```

`answer` là **chỉ số 0-based** vào `options` (không phải chuỗi văn bản — mapper cũ so sánh giá trị
chữ phải đổi thành so sánh chỉ số); `explain` (locale map) thay `explanation` của R5. Đúng 3 câu,
`q` có đúng một chỗ `___`; tiếng Trung `q` và mỗi `options[].text` có `_pinyin`. Số đáp án là 2
hoặc 3 (frame 47 vẽ 4; component `gcqOptions` phải xử lý được 2–3 trước khi nội dung thật lên). Đáp án đúng `error_tag: null`; **mỗi đáp án sai là một
lỗi ngữ pháp người học thật sự hay mắc với điểm này, gắn `error_tag`** (nhãn engine) — không
có đáp án vô nghĩa kiểu "cates". Kiểm tra:

- Mỗi câu có **2 hoặc 3** đáp án: nếu câu chỉ có một lỗi thật (`cat` thay cho `cats`) thì hai
  đáp án — không độn thêm dạng bịa cho đủ ba (bắt buộc đúng ba từng ép model bịa `cates`,
  `boxs`, `floweres` dù đã được dặn không).
- Validate: đáp án sai gắn `error_tag: spelling` bị cờ `quick_practice.distractor_misspelling`.
- Verify: model khác họ đọc từng đáp án sai và phán đó là lỗi người học thật hay dạng bịa/sai
  chính tả — cờ `quick_practice_distractor_implausible` (`grammar_lab/prompts/verify_distractors.md`). Cần bước
  này vì luật theo nhãn không đủ: khi bị cấm nhãn `spelling`, model sinh chỉ đổi nhãn dạng bịa
  thành `word_form`; và engine cũng không phân biệt được (nó vẫn báo `cates` là lỗi).
- Verify điền từng đáp án vào chỗ trống và chấm qua engine: đáp án đúng phải sạch
  (`quick_practice_answer_not_clean`), mỗi đáp án sai phải bị bắt đúng nhãn đã khai
  (`quick_practice_distractor_not_caught`); cộng thêm model khác họ giải thử (đúng một đáp án).

## 7b. personal_production (tuỳ chọn)

Khối "Try it yourself" của frame 47: một câu viết tự do.

```json
"personal_production": {
  "prompt": {"vi": "Viết một câu về nơi bạn đã từng đến."},
  "placeholder": "I have been to …",
  "placeholder_note": {"vi": "gợi ý mở đầu câu"},
  "target_form": "affirmative",
  "pattern_rule": {
    "ordered": true,
    "slots": [
      {"role": "aux", "any_of": ["have", "has", "haven't", "hasn't", "'ve"]},
      {"role": "verb", "regex": "\\b(been|gone|seen|done|eaten|visited|tried|\\w+ed)\\b"}
    ]
  },
  "sample": {"text": "I have been to Da Nang twice."}
}
```

- Mỗi điểm 0 hoặc 1 khối; thiếu khối thì UI không vẽ thẻ (ghi lại như một quyết định, không tự
  bịa prompt). `target_form` trỏ tới `formula`/`variants` nào; `sample` là câu mẫu để UI hiện
  sau khi học viên nộp (tiếng Trung kèm `sample.pinyin`); nó phải sạch qua engine.
- **`placeholder` chỉ là chữ ngôn ngữ đích** (chuỗi phẳng, tiếng Trung kèm `placeholder_pinyin`);
  lời chú thích tiếng Việt/Anh nếu có là `placeholder_note` (locale map). Hai thứ không bao giờ
  cùng một field.
- **Luật nhận diện mẫu (`pattern_rule`, bắt buộc khi có khối)**: xác định được, không dùng model.
  `slots` (≥ 1) là các role của công thức `target_form` mà việc có mặt của chúng chứng tỏ câu dùng
  mẫu (tác giả bỏ qua role không phân biệt được, như `subject` là "I"/"she"); mỗi slot có `role`
  và **đúng một** trong `any_of` (danh sách chuỗi đích) hoặc `regex`. Chuẩn hoá câu học viên
  trước khi so (`casefold`, `’` → `'`); `any_of` khớp nguyên từ (EN) hoặc chuỗi con (ZH); `regex`
  là `re.search` không phân biệt hoa thường. `ordered: true` thì các slot phải khớp theo thứ tự
  xuất hiện, không chồng lên nhau.
- **Câu đúng ngữ pháp mà không chứa mẫu không tính là đã dùng được mẫu.** Kết quả một câu học
  viên là tích của hai phép đo độc lập, engine (đúng/sai ngữ pháp) và `pattern_rule` (có dùng mẫu):

  | Engine | `pattern_rule` | Kết quả | UI có gì để hiển thị |
  | --- | --- | --- | --- |
  | không lỗi | khớp | `used` — đã dùng được mẫu | câu của học viên, `sample` |
  | không lỗi | không khớp | `not_used` — **không tính**, câu đúng nhưng chưa dùng mẫu | nhắc `formula` của `target_form`, cho viết lại |
  | có lỗi có nhãn `error_tag` thuộc `error_tags` của điểm | (không xét) | `error` | gợi ý theo bảng ánh xạ dưới đây |
  | có lỗi, nhãn không thuộc `error_tags` của điểm | (không xét) | `error` | chỉ thông điệp của engine, hợp đồng không cấp gợi ý |
  | câu ngắn hơn ngưỡng của engine | (không xét) | `unverifiable` — không có phán quyết | không hiện đúng/sai |

- **Gợi ý khi sai = ánh xạ nhãn của engine sang `common_mistakes` của chính điểm đó.** Với lỗi
  đầu tiên (thứ tự engine trả) mà `category` ∈ `error_tags`: tìm mục `common_mistakes` có
  `error_tag` = `category`; hai mục trở lên cùng nhãn thì lấy mục đầu có `l1` khớp ngôn ngữ mẹ
  đẻ của học viên (như §6), không có thì mục đầu. Gợi ý = `reason` của mục đó (locale map) và
  `right` làm dạng đúng. Không có mục nào cùng nhãn thì không có gợi ý từ hợp đồng — không sinh
  thêm gợi ý ngoài `common_mistakes`.
- Validate (tất định): `personal_production.rule_invalid` (thiếu `slots`, slot có cả `any_of` lẫn
  `regex` hoặc không có cái nào, `regex` không biên dịch được), `personal_production.rule_role_not_in_formula`
  (role không có trong công thức `target_form`), `personal_production.rule_rejects_sample` (luật
  không khớp `sample.text`), `personal_production.rule_rejects_example` (luật không khớp một ví
  dụ cùng `form` — luật quá chặt).
- **Chấm và bằng chứng không nằm trong nội dung**: câu học viên viết được chấm bởi engine viết
  hiện có (cùng đường Writing), và kết quả đi theo đường bằng chứng có sẵn của app. Hợp đồng
  này không định nghĩa nơi lưu bài viết của học viên (thuộc phần giữ chỗ persistence của
  `AGENTS.md` §7).
- Verify: `sample` sạch qua engine (`personal_production_sample_not_clean`); `prompt` không
  yêu cầu dạng ngoài `target_form` (đọc chéo model, `personal_production_off_target`).

## 8. Tiếng Trung: pinyin theo từng chữ

Mọi field **mang chữ ngôn ngữ đích** có pinyin: mảng cùng độ dài với số ký tự của field đó. Danh
sách field và tên field pinyin (đóng, không có tên nào khác):

| Field chữ đích | Field pinyin (cạnh nó) |
| --- | --- |
| `header.native_title` | `header.native_title_pinyin` |
| `pattern.formula[].text` và `pattern.variants.*[].text` | `pinyin` trong cùng ô |
| `…formula[].options[].text` | `options[].pinyin` |
| `examples[].text` | `examples[].pinyin` |
| `compare[].this_example` / `other_example` | `this_example_pinyin` / `other_example_pinyin` |
| `common_mistakes[].wrong` / `right` | `wrong_pinyin` / `right_pinyin` |
| `quick_practice[].q` | `q_pinyin` |
| `quick_practice[].options[].text` | `options[].pinyin` |
| `pattern.illustration.morphology[].base` / `affix` / `result` | `base_pinyin` / `affix_pinyin` / `result_pinyin` |
| `personal_production.placeholder` | `placeholder_pinyin` |
| `personal_production.sample.text` | `sample.pinyin` |

**Chỉ những field trong bảng này được quét.** Bộ so khớp `personal_production.pattern_rule` (`any_of`,
`regex`) chứa chữ Hán để so khớp, không hiển thị cho học viên, nên không cần pinyin và không bị quét. Locale map — phần giải thích (`title`, `summary`,
`label`, `annotation`, `translation`, `reason`, `explain`, `*_note`, …) — không bao giờ bị
quét, kể cả khi lời giải thích trích chữ Hán để dạy (vd. `"reason": {"vi": "bổ ngữ như 完, 好"}`
không cần pinyin và không bị cờ). `zh.pinyin_field_unlisted` chỉ bắt một **field chuỗi phẳng
ngoài bảng** (không phải locale map, không phải id/nhãn) mang chữ Hán — tức là một field chữ đích
mới bị quên đăng ký ở bảng. Chữ Hán → âm tiết **có dấu thanh** (thanh nhẹ không
dấu: `le`, `men`); ký tự không phải chữ Hán (dấu câu, chữ Latin, khoảng trắng) → `""`. Không
dùng số thanh (`wo3`). Validate: `zh.pinyin_invalid` (thiếu, sai độ dài, sai định dạng). Chữ đa âm (了 le/liǎo, 长,
还, 数, 重…): âm đúng theo ngữ cảnh là rủi ro thật mà kiểm cấu trúc không bắt được; Verify có một
lượt đọc chéo model (`zh.pinyin_polyphone_suspect`, `grammar_lab/prompts/verify_pinyin.md`) đối
chiếu từng chữ đa âm với câu, điểm bị cờ vào hàng người duyệt.
Chuỗi tiếng Trung không có khoảng trắng — cả hai bên chỗ trống `___` (`他___吃过越南菜。`, không
`他 ___ 吃过越南菜。`). Validate: `zh.whitespace`; generate tự bỏ khoảng trắng quanh chỗ trống
của câu luyện nhanh.

## 9. Nối vào app: danh mục Library, R5, trạng thái học viên

**Chiếu danh mục** (`grammar.catalog`, một dòng cho mỗi điểm `approved` của `target_lang` đang học,
sắp theo `level.rank`, `function`, `sequence`): `id`, `header.native_title` (+pinyin), `header.title`,
`header.sub`, `level`, `function`, `sequence`, `point_type`, `error_tags`, `aliases`. Đếm và nhóm
theo `function` trong mỗi level là việc của UI/nguồn cấp từ các field này. **Không** có trong nội
dung: trạng thái từng điểm, "lỗi gần đây", "đã lưu", "gợi ý" — app nối các nhóm đó từ trạng thái
học viên vào `id` (lỗi gần đây = giao `error_tags` với lỗi engine ghi nhận của học viên; gợi ý =
điểm `sequence` kế tiếp trong §0; đã lưu = danh sách lưu của học viên). Hợp đồng này không định
nghĩa nơi lưu các trạng thái đó. Thiết kế chưa vẽ Library tiếng Trung (`UI_BACKEND_GAPS.md` mục
6(b)) — chiếu danh mục theo `target_lang` sẵn sàng cho ZH, còn màn là quyết định thiết kế của người.

**Cầu nối R5.** Grammar Lab thay R5 (`PHASE0_DECISIONS.md` §6), nhưng tiến độ đã lưu, `grammar_links`
của Writing, `/api/library/grammar/{lesson_id}` và deep link `grammar.point` mang id R5.
`aliases` (§0) liệt id R5 mà điểm mới thay thế: một id R5 → một id mới (gộp: nhiều id R5 cùng
trỏ một id mới; tách: mỗi mảnh giữ id R5 gốc trong `aliases` cùng bảng chọn mảnh chính ở
`source_refs`). Quy tắc khi cắt chuyển: (1) id R5 phân giải thành id mới qua `aliases`, deep link
không 404 mà chuyển hướng sang id mới; (2) tiến độ khoá theo id R5 đọc như tiến độ của id mới —
việc ghi lại ở hồ sơ học viên do phần persistence quyết (`AGENTS.md` §7), hợp đồng chỉ bảo đảm
bảng ánh xạ tất định; (3) id R5 không có điểm thay thế không được xoá âm thầm: nó nằm trong danh
sách "bị bỏ" của báo cáo chuyển đổi để người duyệt. Validate: mỗi id R5 xuất hiện ở `aliases` của
tối đa một điểm (`aliases.duplicate`).

## Verify (tổng hợp)

| Kiểm tra | Cách làm | Mã cờ |
| --- | --- | --- |
| Span hợp lệ, phủ đủ công thức | Tất định (`grammar_lab/pipeline/validate.py`) | `example.span_invalid`, `example.formula_role_missing`, `example.span_role_not_in_formula` |
| Ô công thức không mang `+` | Tất định | `formula.slot_has_joiner` |
| Đáp án sai không chỉ là lỗi chính tả | Tất định | `quick_practice.distractor_misspelling` |
| Minh hoạ hợp `point_type` | Tất định | `illustration.kind_mismatch` |
| Pinyin | Tất định (chỉ các field trong bảng §8; locale map không quét) | `zh.pinyin_invalid`, `zh.pinyin_field_unlisted` |
| Chữ đa âm đọc đúng âm | Model khác họ đọc | `zh.pinyin_polyphone_suspect` |
| Locale map: `vi` luôn, `en` khi `approved`; nhãn `function` đủ `vi`+`en`+`zh-Hans` | Tất định | `locale.missing` |
| Giản thể | Tất định | `zh.traditional_char` |
| `contrasts` đối xứng, `aliases` không trùng | Tất định trên cả danh mục | `contrasts.asymmetric`, `aliases.duplicate` |
| Luật nhận diện mẫu của `personal_production` hợp lệ, khớp `sample` và ví dụ cùng dạng | Tất định | `personal_production.rule_invalid`, `personal_production.rule_role_not_in_formula`, `personal_production.rule_rejects_sample`, `personal_production.rule_rejects_example` |
| Câu mẫu của `personal_production` | Engine + model khác họ | `personal_production_sample_not_clean`, `personal_production_off_target` |
| Tiếng Trung không có khoảng trắng | Tất định | `zh.whitespace` |
| Câu ví dụ, câu so sánh sạch | Engine | `example_not_clean` |
| Sai/đúng | Engine | `common_mistake_not_caught`, `common_mistake_right_flagged` |
| Luyện nhanh: đáp án đúng sạch, đáp án sai bị bắt đúng nhãn | Engine | `quick_practice_answer_not_clean`, `quick_practice_distractor_not_caught` |
| Luyện nhanh: đúng một đáp án | Model khác họ giải thử | `blind_solve_wrong`, `blind_solve_ambiguous` |
| Công thức phủ mọi dạng tiêu đề nêu | Model khác họ đọc tiêu đề + tóm tắt + công thức | `formula_incomplete` |
| Đáp án sai là lỗi người học thật, không phải dạng bịa | Model khác họ đọc từng đáp án | `quick_practice_distractor_implausible` |

Tiếng Trung được chấm bằng engine ở phiên ngôn ngữ `zh` (evaluator chọn ngôn ngữ phiên qua
`POST /api/platform/language` của sandbox — thay đổi theo phiên, không đổi hồ sơ lưu trữ).
