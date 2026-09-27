Đọc PROJECT_STATE.md, CURRENT_HANDOFF.md và docs/grammar_lab/SPEC.md trước khi làm.

Nhiệm vụ: thực hiện Giai đoạn 0 của Grammar Lab theo SPEC.md (mục 2, 3, 7).

Ràng buộc:
- Tạo và làm việc trên branch feature/grammar-lab. Không commit vào main.
- Chỉ tạo/sửa file trong grammar_lab/ và docs/grammar_lab/. Không sửa code app, không sửa engine chấm bài, không thêm migration.
- grammar_lab có pyproject.toml riêng, không thêm phụ thuộc vào app.

Việc cần làm:
1. Tạo khung thư mục grammar_lab/ đúng như SPEC mục 2 (file rỗng/stub được phép).
2. Viết schema/grammar_set.schema.json (v0.2) theo SPEC mục 3, gồm:
   level {framework, value, rank} với framework cố định theo ngôn ngữ (en: cefr, zh-Hans: hsk3, ja: jlpt) và level_scales khai báo thứ tự cấp;
   pitfall.l1 là mảng và bắt buộc error_tag; version, source_refs, provenance, review;
   timeline.kind là enum đóng như SPEC.
3. Viết schema/inventory.schema.json theo SPEC mục 4.
4. Tìm nơi engine chấm bài định nghĩa nhãn lỗi. Nếu có danh sách máy đọc được, xuất ra schema/error_tags.json. Nếu KHÔNG có, dừng bước này, ghi rõ vào báo cáo engine đang trả lỗi ở dạng nào, không tự sửa engine.
5. Nâng docs/grammar_lab/sample_v0.1.json lên v0.2, lưu thành grammar_lab/content/en/<id>.json (mỗi điểm một file) và grammar_lab/functions/functions.yaml.
6. Viết pipeline/validate.py và CLI lệnh `validate` với đủ các luật ở SPEC mục 5.2 (bao gồm luật: nội dung zh-Hans không được chứa ký tự phồn thể).
7. Viết test cho từng luật validate (mỗi luật ít nhất một ca đúng và một ca sai).

Tiêu chí xong: `python -m grammar_lab.pipeline.cli validate --lang en` chạy sạch trên 10 file mẫu; toàn bộ test pass.

Kết thúc: cập nhật PROJECT_STATE.md và CURRENT_HANDOFF.md, rồi báo cáo ngắn: đã làm gì, quyết định nào tự đưa ra, và kết quả bước 4 về error_tags. Không bắt đầu Giai đoạn 1.
