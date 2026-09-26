Đọc PROJECT_STATE.md, CURRENT_HANDOFF.md và docs/grammar_lab/SPEC.md (mục 5 và 7).

Nhiệm vụ: thực hiện Giai đoạn 1 trên branch feature/grammar-lab, theo danh sách việc "Thứ tự việc trong giai đoạn 1" ở SPEC mục 7.

Ràng buộc: như Giai đoạn 0. API key đọc từ biến môi trường, không ghi vào code. evaluator_client làm chế độ staging trước. Mọi lời gọi LLM có cache theo hash input và ghi chi phí vào report.

Việc cần làm theo thứ tự: llm_client.py → evaluator_client.py → rules/en_morphology.py → generate.py + prompts/generate_point.md v1 → verify.py (engine khớp pitfall, ví dụ sạch, giải mù; bỏ qua level và dịch ngược) → route.py theo công thức và luật ở SPEC mục 5.4 (ngưỡng khởi đầu 0,8) → report (JSON + HTML).

Tiêu chí xong: một chuỗi lệnh generate → validate → verify → route → report chạy trọn cho 10 điểm tiếng Anh; report có tỉ lệ gắn cờ theo từng kiểm tra, độ khớp engine và chi phí.

Kết thúc: cập nhật PROJECT_STATE.md và CURRENT_HANDOFF.md, báo cáo ngắn kèm đường dẫn report. Không làm preview (Giai đoạn 2).
