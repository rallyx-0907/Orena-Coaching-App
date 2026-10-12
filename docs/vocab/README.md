# Orena — Cấu trúc dữ liệu thẻ từ vựng (EN / ZH)

Gồm:
- `vocab_entry.schema.json`: JSON Schema (2020-12) cho một thẻ từ.
- `samples/en_resilient.json`, `samples/zh_senlin.json`: 2 bản ghi mẫu, đúng nội dung 2 thẻ thiết kế chuẩn.

Thiết kế chuẩn để dựng giao diện là canvas "Flashcard từ vựng Anh – Trung" (bản đầu: EN tối giản, ZH cổ điển phương Đông).

## Nguyên tắc
- Một khung chung cho mọi ngôn ngữ. Phần riêng của từng ngôn ngữ nằm trong `en` hoặc `zh`, mỗi thẻ có đúng một trong hai, theo `lang`.
- Mỗi ngôn ngữ dùng thang cấp riêng: EN `CEFR` A1–C2, ZH `HSK3` 1–6 và 7-9. Không quy đổi chéo.
- Tiếng Trung chỉ dùng giản thể (`zh-Hans`).
- Tô nổi bật trong câu ví dụ theo **chuỗi khớp** (`highlight.match`, kèm `occurrence` nếu từ xuất hiện nhiều lần), không dùng vị trí ký tự. Như vậy nhập liệu dễ hơn, và UI tự cắt câu để tô. ZH tô cả câu chữ Hán (`highlight`) lẫn dòng pinyin (`reading_highlight`).
- Không có `illustration` hoặc `kind: "none"` thì ẩn khung hình. `library` trỏ tới thư viện hình nét SVG dùng chung, `upload` là ảnh tải lên qua Admin.
- `status`: `draft` → `reviewed` → `published`. Learner chỉ thấy thẻ `published`.

## Trường → vị trí trên thẻ

| Mặt | EN | ZH |
|---|---|---|
| Trước | `level`, `pos`, `headword`, `en.ipa.uk/us`, `illustration`, `meanings[0]`, `related` (family, synonym, antonym) | `level`, `pos`, `zh.chars[]` (ruby pinyin), `zh.han_viet`, `illustration`, `meanings[0]`, bộ thủ từ `zh.chars[].radical/components/strokes`, `zh.measure_words`, `related` |
| Sau | `examples[]` (label, text + highlight, translation, explanation), `collocations`, `memory_tip_vi` | `examples[]` (text + highlight, reading + reading_highlight, translation, explanation), `memory_tip_vi` |

Bộ thủ: nếu các chữ dùng chung một bộ (như 森林 → 木), UI chỉ hiện một ô bộ thủ và liệt kê cấu tạo từng chữ.

## Admin: kiểm tra khi lưu/nhập
1. Validate theo schema. Bản ghi sai thì từ chối và báo rõ trường nào lỗi.
2. `highlight.match` phải có trong `text`, và `reading_highlight.match` phải có trong `reading`. Nếu không thì cảnh báo, không tô.
3. ZH: các `zh.chars[].hanzi` ghép lại phải đúng bằng `headword`.
4. `id` là duy nhất. Nhập trùng thì hỏi ghi đè hay bỏ qua.
5. Nhập hàng loạt bằng JSON (mảng các bản ghi) hoặc JSONL. Có màn xem trước thẻ trước khi lưu.

## Ghi chú
- Cấp HSK của 森林 trong bản mẫu đang để `4` theo HSK 2.0. Cần đối chiếu với danh sách HSK 3.0 trước khi publish.
- Nội dung thật do người dùng nhập qua Admin. Coding agent chỉ dùng 2 bản ghi mẫu này để seed và test.
