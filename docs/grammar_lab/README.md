# Grammar Lab — bộ tài liệu khởi động

Chép nguyên thư mục `docs/grammar_lab/` này vào gốc repo Orena (giữ đúng đường dẫn).

| File | Dùng để |
| --- | --- |
| `SPEC.md` | Đặc tả Grammar Lab v0.1 (bản đồng bộ với Claude Doc ngày 26/09/2026) |
| `sample_v0.1.json` | 10 điểm ngữ pháp tiếng Anh mẫu (A1–B1, giải thích tiếng Việt), bản nháp AI |
| `prompts/phase0_contract.md` | Prompt giao Claude Code làm Giai đoạn 0 |
| `prompts/phase1_pipeline.md` | Prompt giao Claude Code làm Giai đoạn 1 — chỉ chạy sau khi Giai đoạn 0 đã được duyệt |

Thứ tự:
1. Commit thư mục này (có thể commit thẳng lên branch feature/grammar-lab).
2. Dán nội dung `phase0_contract.md` vào Claude Code.
3. Xem báo cáo, đặc biệt kết quả về error_tags. Duyệt xong mới dán `phase1_pipeline.md`.

Nếu sửa spec trên Claude Doc, nhớ cập nhật lại `SPEC.md` trong repo — Claude Code chỉ đọc bản trong repo.
