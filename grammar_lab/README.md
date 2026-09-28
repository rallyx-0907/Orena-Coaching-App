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

# Giai đoạn 1 (SPEC §5.1-§5.5) -- cần key managed API riêng của lab (không phải key trong sandbox app)
# và evaluator sandbox: grammar_lab/sandbox/ (docker compose, xem sandbox/README.md).
python -m grammar_lab.pipeline.cli generate --lang en --ids en.past_simple,en.there_is_are   # provider mặc định: anthropic
python -m grammar_lab.pipeline.cli generate --lang en --ids en.past_simple --with-story \
  --provider deepseek --model deepseek-flash --deepseek-thinking off   # thêm block story (schema v0.3)
# --deepseek-thinking off|low|high (mặc định off) -- xem docstring llm_client.py: thinking chia sẻ
# max_tokens với câu trả lời, low/high tự thêm khoảng đệm (+4096/+8192); ghi vào reports/<run_id>/generate.json
python -m grammar_lab.pipeline.cli verify --lang en --evaluator-url http://localhost:8020    # blind-solve mặc định: gemini
python -m grammar_lab.pipeline.cli route --lang en --gold-set-passed   # bỏ cờ này -> mọi mục bị flagged (SPEC §5.4)
python -m grammar_lab.pipeline.cli report --lang en                    # reports/<run_id>/report.{json,html}

python -m pytest grammar_lab/tests                              # toàn bộ test
```

Mã lỗi của `validate` được liệt kê ở đầu [`pipeline/validate.py`](pipeline/validate.py); mỗi mã có ít
nhất một ca đúng và một ca sai trong `tests/test_validate_rules.py`.

**So hai model cho `generate`** (SPEC §9, "managed API nào và ngân sách"): chạy `generate` hai lần cho
cùng 10 điểm với `--model` khác nhau (`claude-haiku-4-5-20251001` rồi `claude-sonnet-5`), mỗi lần ra
một `run_id` riêng trong `reports/`; `verify` + `route` + `report` cho từng run_id rồi so
`report.json`'s `route_status_counts`/`verify_flag_rate`/`api_cost_usd` giữa hai lần chạy.

`generate`/`verify` gọi API thật (`llm_client.py` có cache theo hash input ở `.cache/llm/`, không
tính phí lần chạy lại). Bốn provider: `anthropic | openai | gemini | groq`, cộng `deepseek` (chỉ
`json_object`, không ép schema -- xem docstring `llm_client.py`). Gemini và DeepSeek đọc key từ
`GEMINI_API_KEY`/`DEEPSEEK_API_KEY`, không bao giờ giá trị literal trong code hay compose. Gemini đi
qua `rate_limit.py` (chia sẻ một bucket với engine chấm bài trong sandbox nếu engine cũng dùng Gemini
-- xem `sandbox/README.md`); DeepSeek có bucket riêng nếu cần, không dùng chung với Gemini.

Trước một lần chạy live bất kỳ (kể cả smoke test): giữ
`sandbox/live_provider_lock.py` (khóa file dùng chung
`%USERPROFILE%\.orena\live-provider.lock` giữa các lane, giải phóng trong cùng
trap gỡ sandbox) -- xem `sandbox/README.md`.

`evaluator_client.py` chỉ có chế độ staging (HTTP); **không có `base_url` mặc định** -- endpoint công
khai duy nhất, `orena.chillpickle.org`, chui thẳng vào container production (`writing-coach:8000`),
một "human gate" theo `AGENTS.md` phần Safety. Trỏ `--evaluator-url` vào một sandbox được phép thao
tác (vd. `grammar_lab/sandbox/` ở `:8020`).

## Bố cục

| Đường dẫn | Nội dung |
| --- | --- |
| `schema/grammar_set.schema.json` | Schema v0.2 + v0.3 (`block_story`): grammar point (gốc), `$defs.set_manifest`, `$defs.functions_file`, `$defs.cast_file`, `level_scales` |
| `schema/inventory.schema.json` | Danh mục chính `inventory/<lang>.yaml` |
| `schema/error_tags.json` | Nhãn lỗi của engine chấm bài, **sinh tự động**, không sửa tay |
| `content/<lang>/_set.json` | Manifest của bộ: locale giải thích và L1 bắt buộc |
| `content/<lang>/<id>.json` | Mỗi grammar point một file, tên file = `id` |
| `functions/functions.yaml` | Lớp chức năng giao tiếp dùng chung |
| `cast/cast.yaml` | Cast nhân vật cố định cho block `story` (schema v0.3, `STORY_SPEC.md` §3) |
| `inventory/<lang>.yaml` | Danh mục chính (giai đoạn 3; hiện là `[]`) |
| `pipeline/` | CLI và các bước. `coverage.py` còn là stub (cần inventory, giai đoạn 3); `preview/` là stub giai đoạn 2 |
| `rules/en_morphology.py` | Bảng biến đổi tất định (SPEC §5.1 bước 1): third person -s, số nhiều, quá khứ, -ing, so sánh |
| `pipeline/content_store.py` | Đọc/ghi `content/<lang>/` + `cast/cast.yaml` dùng chung giữa generate/verify/route |
| `pipeline/llm_client.py` | Managed API (Anthropic, OpenAI, Gemini, Groq, DeepSeek), cache theo hash input ở `.cache/llm/` |
| `pipeline/rate_limit.py`, `secrets_redact.py` | Rate limiter theo bucket dùng chung (Gemini) + che giá trị key khỏi mọi thông báo lỗi |
| `pipeline/evaluator_client.py` | Client HTTP chế độ staging cho engine chấm bài (không có `base_url` mặc định) |
| `pipeline/run_context.py`, `report_step.py` | `reports/<run_id>/*.json` + `reports/latest.txt` nối các bước; `report` gộp thành JSON/HTML |
| `prompts/generate_story.md`, `verify_story.md` | Prompt sinh và verify block `story` (schema v0.3) |
| `reports/<run_id>/` | Kết quả chạy (không commit) |
| `sandbox/` | Evaluator sandbox rời (compose project, image, port riêng) cho `verify`; xem `sandbox/README.md` |
| `sandbox/live_provider_lock.py` | Khóa file dùng chung giữa các lane trước một lần chạy live (không đụng Docker) |

## Quy ước

- `--lang` và thư mục dùng mã ngắn `en | zh | ja`; tiền tố ID cũng vậy (`zh.le_completion`).
  `target_lang` và khóa `realizations` dùng BCP-47: `en | zh-Hans | ja`.
- Locale giải thích: `vi | en | zh-Hans | ja` (tiếng Trung chỉ giản thể). L1 là ngôn ngữ: `vi | zh | en | ja`.
- Mọi file JSON được ghi qua `pipeline/jsonio.py` (định dạng cố định) để diff gọn.
