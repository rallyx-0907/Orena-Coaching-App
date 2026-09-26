# Orena Grammar Lab

Môi trường độc lập để sinh, kiểm tra và duyệt nội dung ngữ pháp trước khi gộp vào app.
Đặc tả: [`docs/grammar_lab/SPEC.md`](../docs/grammar_lab/SPEC.md). Quyết định giai đoạn 0:
[`docs/grammar_lab/PHASE0_DECISIONS.md`](../docs/grammar_lab/PHASE0_DECISIONS.md).

Lab không import code app, app không import code lab; hợp đồng duy nhất là JSON Schema trong `schema/`.
Phụ thuộc nằm ở `pyproject.toml` của lab, không thêm vào `requirements.txt` của app.

## Cài đặt (một lần)

Chạy từ gốc repo:

```bash
python -m venv grammar_lab/.venv
grammar_lab/.venv/Scripts/python -m pip install -e "grammar_lab[dev]"
```

(Linux/macOS: `grammar_lab/.venv/bin/python`.) Các lệnh dưới đây giả định `python` là python của venv này.

## Lệnh

```bash
python -m grammar_lab.pipeline.cli validate --lang en          # SPEC §5.2, exit 1 nếu có lỗi
python -m grammar_lab.pipeline.cli validate --lang en --json   # báo cáo dạng JSON
python -m grammar_lab.pipeline.cli validate --lang en --mark   # ghi status=flagged + flags validate:<mã> vào file lỗi
python -m grammar_lab.pipeline.cli export-error-tags           # xuất lại schema/error_tags.json từ engine chấm bài
python -m pytest grammar_lab/tests                              # toàn bộ test
```

Mã lỗi của `validate` được liệt kê ở đầu [`pipeline/validate.py`](pipeline/validate.py); mỗi mã có ít
nhất một ca đúng và một ca sai trong `tests/test_validate_rules.py`.

## Bố cục

| Đường dẫn | Nội dung |
| --- | --- |
| `schema/grammar_set.schema.json` | Schema v0.2: grammar point (gốc), `$defs.set_manifest`, `$defs.functions_file`, `level_scales` |
| `schema/inventory.schema.json` | Danh mục chính `inventory/<lang>.yaml` |
| `schema/error_tags.json` | Nhãn lỗi của engine chấm bài, **sinh tự động**, không sửa tay |
| `content/<lang>/_set.json` | Manifest của bộ: locale giải thích và L1 bắt buộc |
| `content/<lang>/<id>.json` | Mỗi grammar point một file, tên file = `id` |
| `functions/functions.yaml` | Lớp chức năng giao tiếp dùng chung |
| `inventory/<lang>.yaml` | Danh mục chính (giai đoạn 3; hiện là `[]`) |
| `pipeline/` | CLI và các bước; `generate`, `verify`, `route`, `coverage`, `*_client` là stub của giai đoạn 1 |
| `rules/`, `prompts/`, `preview/` | Stub của giai đoạn 1–2 |
| `reports/<run_id>/` | Kết quả chạy (không commit) |

## Quy ước

- `--lang` và thư mục dùng mã ngắn `en | zh | ja`; tiền tố ID cũng vậy (`zh.le_completion`).
  `target_lang` và khóa `realizations` dùng BCP-47: `en | zh-Hans | ja`.
- Locale giải thích: `vi | en | zh-Hans | ja` (tiếng Trung chỉ giản thể). L1 là ngôn ngữ: `vi | zh | en | ja`.
- Mọi file JSON được ghi qua `pipeline/jsonio.py` (định dạng cố định) để diff gọn.
