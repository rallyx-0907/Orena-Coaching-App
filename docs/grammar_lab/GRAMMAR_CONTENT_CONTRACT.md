# Grammar Lab — Grammar content contract (proposal, schema v0.4)

28/09/2026 · nhánh `feature/grammar-lab-pipeline` · nguồn: chỉ đạo trực tiếp của người,
ghi lại nguyên văn quyết định tại đây để không dựa vào lịch sử chat.

**Đây là đề xuất gửi lane UI, chưa phải bản chính thức.** Nó định nghĩa chính xác các khối
dữ liệu mà một điểm ngữ pháp Grammar Lab phải có, đủ để UI vẽ theo ảnh tham khảo (công thức
nổi bật + timeline, ví dụ tô màu theo vị trí, so sánh hai cột, sai/đúng, luyện nhanh) — không
định hình dáng UI cụ thể (màu, layout, font). `docs/project/DESIGN_CONTRACT.md`/D-067 vẫn là
nguồn UI thật khi lane UI thiết kế màn hình dùng dữ liệu này.

Thay thế mô hình `blocks: [formula, rule_table, example, pitfall, contrast, note, check]` của
schema v0.2/v0.3 cho nội dung **chính**: bảy khối cố định dưới đây, mỗi khối một trường ở cấp
điểm ngữ pháp (không phải phần tử của một mảng `blocks` trộn nhiều loại). `story` (STORY_SPEC.md,
VOICE.md) vẫn tồn tại nhưng chuyển thành **nội dung phụ, tuỳ chọn** — một mảng `blocks` chỉ còn
chứa `story`, không bắt buộc cho mọi điểm. Việc dựng prompt v3 cho story tạm dừng ở lần này.

## 1. header

Không phải trường mới — dùng lại `title` (locale map), `level` ({framework, value, rank}),
`summary` (locale map, một câu) đã có ở cấp điểm ngữ pháp từ v0.2. "header" mô tả cách UI dùng
ba trường này cùng nhau, không đổi shape của chúng.

## 2. pattern

```json
"pattern": {
  "parts": [
    {"text": "I", "role": "subject"},
    {"text": "have", "role": "aux"},
    {"text": "lived", "role": "verb"},
    {"text": "here", "role": "complement"},
    {"text": "for three days", "role": "time"}
  ],
  "variants": {
    "negative": [{"text": "I", "role": "subject"}, {"text": "haven't", "role": "aux"}, "..."],
    "question": [{"text": "Have", "role": "aux"}, {"text": "you", "role": "subject"}, "..."]
  },
  "illustration": {"kind": "timeline", "timeline": {
    "points": [
      {"id": "past", "label": {"vi": "quá khứ"}},
      {"id": "now", "label": {"vi": "hiện tại"}}
    ],
    "marks": [
      {"type": "span", "from": "past", "to": "now", "label": {"vi": "bắt đầu và kéo dài đến giờ"}}
    ]
  }}
}
```

- `parts`/`variants.negative`/`variants.question`: mảng phần công thức theo đúng thứ tự, mỗi
  phần có `text` (ngôn ngữ đích) và `role` — dùng để UI tô màu theo vai trò, nhất quán với
  `role` trong `examples[].spans` (mục 4). `variants` tuỳ chọn: chỉ khai khi có dạng phủ
  định/nghi vấn có ý nghĩa (một số điểm — hạt从 tiếng Trung chẳng hạn — có thể không có cả hai).
- `illustration.kind`: `timeline | word_order | none`.
  - `word_order` không cần dữ liệu riêng: UI vẽ chính `parts` (và `variants` nếu có) thành các ô
    theo thứ tự — đúng nhu cầu minh hoạl cho câu chữ Hán như 把 (chủ ngữ — 把 — tân ngữ — động từ
    — bổ ngữ), không cần lặp lại dữ liệu đã có ở `parts`.
  - `timeline`: cần dữ liệu riêng vì `parts` không mang quan hệ thời gian. `points` là các mốc cố
    định trên trục (2-4 điểm, ví dụ quá khứ/hiện tại/tương lai); `marks` là các điểm hoặc khoảng
    được đánh dấu, tham chiếu `points[].id`, mỗi mark có nhãn ngắn.
  - `none`: điểm không cần minh hoạ thêm (ví dụ một hạt đơn giản không có trục thời gian hay thứ
    tự đặc biệt).

`role` (dùng chung cho `pattern.parts[].role` và `examples[].spans[].role`): enum cố định —
`subject | verb | aux | object | complement | time | place | marker | particle | connector | other`.
Danh sách này đủ cho cả tiếng Anh (aux/verb tách rời cho thì hoàn thành) và tiếng Trung (`marker`
cho 把/被, `particle` cho 了/过).

## 3. when_to_use

```json
"when_to_use": [{"vi": "..."}, {"vi": "..."}]
```

2-4 ý ngắn (locale map), không phải đoạn văn — mỗi ý một tình huống hoặc điều kiện dùng cụ thể.

## 4. examples

```json
"examples": [
  {
    "text": "I have lived here for three days.",
    "spans": [{"start": 7, "end": 12, "role": "verb"}],
    "annotation": {"vi": "bắt đầu → đến giờ"},
    "translation": {"vi": "Tôi đã sống ở đây được ba ngày."},
    "pinyin": null
  }
]
```

- `spans[].start`/`end`: vị trí ký tự (0-based, `end` không bao gồm) trong `text` — không phải
  chuỗi con lặp lại. Đây là thay đổi so với `seg` của v0.2/v0.3 (mảng `[text, label?]` ghép lại
  phải khớp `text`): span theo vị trí loại bỏ hẳn lớp lỗi "ghép lại không khớp" mà DeepSeek từng
  gặp (seg dùng `[text, null]` thay vì `[text]`) — `text` là nguồn duy nhất, span chỉ là toạ độ
  tham chiếu vào đó, `validate.py` chỉ cần kiểm `0 <= start < end <= len(text)`.
- `annotation`: chú thích ngắn, locale map (ví dụ minh hoạ "finished → started" là kiểu chú thích,
  không bắt buộc viết bằng tiếng Anh — viết ở locale giải thích như mọi trường khác).
- `translation`: chỉ `vi` (giữ quy ước cũ của `example.tr`).
- `pinyin`: bắt buộc khi `target_lang` là `zh-Hans`, `null`/vắng mặt cho ngôn ngữ khác. Mảng cùng
  độ dài với số ký tự trong `text` (theo từng chữ Hán; dấu câu/khoảng trắng nhận chuỗi rỗng
  `""`), ví dụ `["wǒ", "bǎ", "shū", "kàn", "wán", "le"]` cho `"我把书看完了"`.

## 5. compare

```json
"compare": [
  {
    "with": "en.present_perfect.experience",
    "this_meaning": {"vi": "..."},
    "this_example": "I have lived here for three days.",
    "other_meaning": {"vi": "..."},
    "other_example": "I lived there for three years."
  }
]
```

Thay `contrast` block (v0.2/v0.3: cặp câu thô) bằng hai cột có ý nghĩa: `this_*` là điểm đang
xem, `other_*` là điểm bị nhầm (`with`, một grammar point id). `with` phải nằm trong `contrasts[]`
ở cấp điểm ngữ pháp (giữ nguyên luật đối chiếu hai chiều của v0.2, chỉ đổi hình dạng nội dung).

## 6. common_mistakes

```json
"common_mistakes": [
  {
    "wrong": "I have three brother.",
    "right": "I have three brothers.",
    "reason": {"vi": "..."},
    "error_tag": "agreement",
    "l1": ["vi"]
  }
]
```

Thay `pitfall` block — cùng shape (`wrong`/`right`/`error_tag`/`l1`, giữ nguyên luật cũ: `wrong ≠
right`, `error_tag` phải trong `error_tags` của điểm và trong danh sách nhãn engine, `l1` phải
khai trong manifest), chỉ đổi tên trường `why` → `reason` cho khớp thuật ngữ mới.

## 7. quick_practice

```json
"quick_practice": [
  {"q": "I have two ___.", "options": ["cat", "cats", "cates"], "answer": 1, "explain": {"vi": "..."}}
]
```

Đúng 3 câu (`minItems: 3, maxItems: 3` — khác `check` cũ vốn không giới hạn số câu). Giữ quy ước
cloze cũ (`q` chứa `___`, `options` là các phương án điền, `answer` là chỉ số 0-based) vì đây là
quy ước đã kiểm chứng (`blind_solve.md`, verify qua model khác họ). Không còn suy ra tất định từ
`examples`/`common_mistakes` như `check` cũ (`_build_check_items`) — model sinh trực tiếp, verify
đảm bảo đúng một đáp án đúng (mục "Verify" dưới).

## 8. story (phụ, tuỳ chọn)

`blocks: [{"type": "story", ...}]` — giữ nguyên shape của STORY_SPEC.md/VOICE.md, nhưng **không
bắt buộc** cho schema v0.4 (khác v0.3, nơi story bắt buộc cho theme `daily`). Dùng khi người học
cần giải thích thêm, không phải giải thích mặc định. Không sửa gì thêm ở `prompts/generate_story.md`
lần này theo yêu cầu tạm dừng.

## Verify (khối mới, ngoài các kiểm tra đã có ở SPEC §5.3)

| Kiểm tra | Cách làm | Gắn cờ khi |
| --- | --- | --- |
| Span hợp lệ | Tất định, `validate.py` | `start`/`end` ngoài phạm vi `text` hoặc `start >= end` |
| Câu ví dụ sạch | Gửi `examples[].text` qua engine | Engine bắt bất kỳ lỗi nào |
| `common_mistakes.wrong` bắt đúng nhãn | Gửi qua engine | Engine không bắt đúng `error_tag` đã khai |
| `quick_practice` đúng một đáp án | Hỏi model blind-solve (khác họ model sinh) | Model chọn khác `answer`, hoặc thấy nhiều phương án đều đúng |
| `compare.with` tồn tại và có trong `contrasts` | Tất định, `validate.py` | Không khớp |

## Ví dụ đầy đủ (rút gọn, tiếng Anh)

```json
{
  "id": "en.plural_nouns.regular",
  "when_to_use": [{"vi": "Khi đếm được và có từ hai trở lên."}],
  "pattern": {
    "parts": [{"text": "two", "role": "marker"}, {"text": "cats", "role": "object"}],
    "illustration": {"kind": "none"}
  },
  "examples": [{
    "text": "I have two cats.",
    "spans": [{"start": 12, "end": 16, "role": "object"}],
    "annotation": {"vi": "số nhiều: +s"},
    "translation": {"vi": "Tôi có hai con mèo."}
  }],
  "compare": [],
  "common_mistakes": [{
    "wrong": "I have two cat.", "right": "I have two cats.",
    "reason": {"vi": "Đếm được, từ hai trở lên phải thêm -s."},
    "error_tag": "agreement", "l1": ["vi"]
  }],
  "quick_practice": [
    {"q": "I have two ___.", "options": ["cat", "cats", "cates"], "answer": 1, "explain": {"vi": "..."}}
  ]
}
```
