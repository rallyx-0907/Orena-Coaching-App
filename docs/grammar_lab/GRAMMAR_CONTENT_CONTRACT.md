# Grammar Lab — Grammar content contract (proposal, schema v0.4)

28/09/2026 · nhánh `feature/grammar-lab-pipeline` · nguồn: chỉ đạo trực tiếp của người,
ghi lại tại đây để không dựa vào lịch sử chat.

**Đề xuất, chưa gửi lane UI.** Người duyệt nội dung qua trang preview nội bộ
(`python -m grammar_lab.pipeline.cli preview --serve`) trước; chỉ gửi lane UI sau khi người
duyệt. Tài liệu định nghĩa chính xác dữ liệu một điểm ngữ pháp mang, đủ để UI vẽ: công thức
nổi bật với ô tô màu theo vai trò, minh hoạ timeline/word_order/morphology, ví dụ tô màu cùng
bảng màu, so sánh hai cột, sai/đúng, luyện nhanh bấm được. Nó **không** định hình dáng UI (màu,
layout, font) — `docs/project/DESIGN_CONTRACT.md`/D-067 vẫn là nguồn UI thật.

Đây là **nguồn ngữ pháp chuẩn duy nhất** đi tới (`PHASE0_DECISIONS.md` §6: Grammar Lab thay thế
R5). Phần giải thích viết bằng tiếng Việt, giọng rõ ràng, cho người lớn, không văn vẻ. `story`
(STORY_SPEC.md, VOICE.md) là nội dung phụ, tuỳ chọn (`blocks: [story]`), chỉ dùng khi người học
cần giải thích thêm; prompt story v3 đang tạm dừng.

## 0. Metadata (không do model sinh)

`id`, `version`, `target_lang`, `function`, `level`, `prereqs`, `contrasts`, `error_tags`,
`source_refs` như v0.2, cộng **`point_type`**: `tense_aspect | word_order | morphology | other`
— điểm này chủ yếu nói về điều gì. Nó quyết định kiểu minh hoạ (§2).

## 1. header

```json
"header": {
  "title": {"vi": "Hiện tại hoàn thành (trải nghiệm)"},
  "native_title": "Present perfect",
  "level": {"framework": "cefr", "value": "A2", "rank": 2},
  "summary": {"vi": "Nói đã từng làm gì, không nêu thời điểm."}
}
```

Tiêu đề (ngôn ngữ giải thích + tên gốc bằng ngôn ngữ đích), trình độ (CEFR cho tiếng Anh, HSK
3.0 cho tiếng Trung), một câu tóm tắt. `header.level` phải bằng `level` của điểm (validate:
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
  thiếu dạng nào; thiếu → cờ `formula_incomplete` (điểm bị flagged). Prompt: `prompts/verify_formula.md`.
- Hai cách dùng khác nhau thì tách thành hai điểm, không gộp một công thức: mạo từ là
  `en.articles.a_an` (không xác định) và `en.articles.the` (xác định), `compare` lẫn nhau.
- `variants.negative`/`variants.question`: cũng là ô, chỉ khai khi điểm có dạng phủ định/nghi
  vấn riêng.
- `role` dùng chung cho ô công thức và span trong ví dụ, để UI tô cùng màu: `subject | verb |
  aux | object | complement | time | place | marker | particle | connector | other`.
- `illustration.kind` do `point_type` quyết định (validate: `illustration.kind_mismatch`):

  | point_type | kind | Dữ liệu |
  | --- | --- | --- |
  | `tense_aspect` (thì/thể) | `timeline` | `timeline.shape` (enum đóng, xem schema) + `relevance` tuỳ chọn |
  | `word_order` (trật tự câu, vd. 把) | `word_order` | không có — UI vẽ chính các ô `formula` thành hộp theo thứ tự |
  | `morphology` (biến đổi từ) | `morphology` | 1-4 mục `{base, affix, result}`, vd. `book + -s → books` |
  | `other` | `none` | không có |

## 3. when_to_use

2-4 ý ngắn (locale map), mỗi ý một tình huống cụ thể.

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

Hai cột: `with` (id điểm dễ nhầm, phải có trong `contrasts`), `this_meaning`/`this_example`,
`other_meaning`/`other_example`.

## 6. common_mistakes

`wrong`, `right`, `reason` (lý do ngắn), `error_tag` (nhãn engine, phải nằm trong `error_tags`
của điểm), `l1`. Verify: engine phải bắt `wrong` đúng `error_tag`, `right` phải sạch.

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

Đúng 3 câu, `q` có đúng một chỗ `___`. Đáp án đúng `error_tag: null`; **mỗi đáp án sai là một
lỗi ngữ pháp người học thật sự hay mắc với điểm này, gắn `error_tag`** (nhãn engine) — không
có đáp án vô nghĩa kiểu "cates". Kiểm tra:

- Mỗi câu có **2 hoặc 3** đáp án: nếu câu chỉ có một lỗi thật (`cat` thay cho `cats`) thì hai
  đáp án — không độn thêm dạng bịa cho đủ ba (bắt buộc đúng ba từng ép model bịa `cates`,
  `boxs`, `floweres` dù đã được dặn không).
- Validate: đáp án sai gắn `error_tag: spelling` bị cờ `quick_practice.distractor_misspelling`.
- Verify: model khác họ đọc từng đáp án sai và phán đó là lỗi người học thật hay dạng bịa/sai
  chính tả — cờ `quick_practice_distractor_implausible` (`prompts/verify_distractors.md`). Cần bước
  này vì luật theo nhãn không đủ: khi bị cấm nhãn `spelling`, model sinh chỉ đổi nhãn dạng bịa
  thành `word_form`; và engine cũng không phân biệt được (nó vẫn báo `cates` là lỗi).
- Verify điền từng đáp án vào chỗ trống và chấm qua engine: đáp án đúng phải sạch
  (`quick_practice_answer_not_clean`), mỗi đáp án sai phải bị bắt đúng nhãn đã khai
  (`quick_practice_distractor_not_caught`); cộng thêm model khác họ giải thử (đúng một đáp án).

## 8. Tiếng Trung: pinyin theo từng chữ

Mọi chuỗi tiếng Trung — `formula[].text` (và variants), `examples[].text`,
`common_mistakes[].wrong`/`right` — có pinyin: mảng cùng độ dài với số ký tự
(`pinyin`, `wrong_pinyin`, `right_pinyin`). Chữ Hán → âm tiết **có dấu thanh** (thanh nhẹ không
dấu: `le`, `men`); ký tự không phải chữ Hán (dấu câu, chữ Latin, khoảng trắng) → `""`. Không
dùng số thanh (`wo3`). Validate: `zh.pinyin_invalid` (thiếu, sai độ dài, sai định dạng).
Chuỗi tiếng Trung không có khoảng trắng — cả hai bên chỗ trống `___` (`他___吃过越南菜。`, không
`他 ___ 吃过越南菜。`). Validate: `zh.whitespace`; generate tự bỏ khoảng trắng quanh chỗ trống
của câu luyện nhanh.

## Verify (tổng hợp)

| Kiểm tra | Cách làm | Mã cờ |
| --- | --- | --- |
| Span hợp lệ, phủ đủ công thức | Tất định (`validate.py`) | `example.span_invalid`, `example.formula_role_missing`, `example.span_role_not_in_formula` |
| Ô công thức không mang `+` | Tất định | `formula.slot_has_joiner` |
| Đáp án sai không chỉ là lỗi chính tả | Tất định | `quick_practice.distractor_misspelling` |
| Minh hoạ hợp `point_type` | Tất định | `illustration.kind_mismatch` |
| Pinyin | Tất định | `zh.pinyin_invalid` |
| Tiếng Trung không có khoảng trắng | Tất định | `zh.whitespace` |
| Câu ví dụ, câu so sánh sạch | Engine | `example_not_clean` |
| Sai/đúng | Engine | `common_mistake_not_caught`, `common_mistake_right_flagged` |
| Luyện nhanh: đáp án đúng sạch, đáp án sai bị bắt đúng nhãn | Engine | `quick_practice_answer_not_clean`, `quick_practice_distractor_not_caught` |
| Luyện nhanh: đúng một đáp án | Model khác họ giải thử | `blind_solve_wrong`, `blind_solve_ambiguous` |
| Công thức phủ mọi dạng tiêu đề nêu | Model khác họ đọc tiêu đề + tóm tắt + công thức | `formula_incomplete` |
| Đáp án sai là lỗi người học thật, không phải dạng bịa | Model khác họ đọc từng đáp án | `quick_practice_distractor_implausible` |

Tiếng Trung được chấm bằng engine ở phiên ngôn ngữ `zh` (evaluator chọn ngôn ngữ phiên qua
`POST /api/platform/language` của sandbox — thay đổi theo phiên, không đổi hồ sơ lưu trữ).
