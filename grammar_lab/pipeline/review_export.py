"""``review-export`` (human, 2026-09-29, item 4): one Markdown file per level for review by an
external model the human runs on a free tool.

``grammar_lab/review/<lang>/<level>.md`` holds, in this order: a header (point count, size
estimate), the reviewer instructions (two passes), the engine error labels of the language, a
level overview table (pass 1) and the points cut into numbered sections of about ten
(pass 2). Feedback comes back as JSONL, one object per line::

    {"id": "en.past_simple", "block": "examples[1]", "issue": "[knowledge] ...", "severity": "major", "fix": "..."}

``apply_feedback.py`` reads those files. The four issue tags (``[knowledge]`` wrong knowledge,
``[scope]`` wrong scope or level, ``[wording]`` expression, ``[format]`` format) are what the
post-A1 statistics group by.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import load_functions, load_points
from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.pipeline.validate import ERROR_TAGS_PATH, LAB_ROOT, LANGS

SECTION_SIZE = 10
DEFAULT_OUT = LAB_ROOT / "review"
ISSUE_TAGS = ("knowledge", "scope", "wording", "format")
SEVERITIES = ("blocker", "major", "minor")
NO_ISSUE_BLOCK = "none"
BLOCKS = (
    "metadata", "header", "pattern", "illustration", "when_to_use", "examples", "compare",
    "common_mistakes", "quick_practice", "personal_production",
)


def level_label(lang: str, value: str) -> str:
    return f"HSK{value}" if lang == "zh" else value


def review_path(lang: str, level: str, out_dir: Path = DEFAULT_OUT) -> Path:
    return out_dir / lang / f"{level}.md"


def _pair_pinyin(text: str, pinyin: list[str] | None) -> str:
    if not pinyin or len(pinyin) != len(text):
        return text
    return "".join(f"{char}({syllable})" if syllable else char for char, syllable in zip(text, pinyin, strict=True))


def _loc(mapping: dict[str, str] | None, *order: str) -> str:
    if not mapping:
        return ""
    parts = [f"{key}: {mapping[key]}" for key in (order or tuple(mapping)) if key in mapping]
    return " | ".join(parts)


def _slots(slots: list[dict[str, Any]], zh: bool) -> str:
    out = []
    for slot in slots:
        text = _pair_pinyin(slot["text"], slot.get("pinyin")) if zh else slot["text"]
        label = slot["label"].get("vi", "")
        piece = f"[{text} <{slot['role']}> {label}" + (", optional" if slot.get("optional") else "") + "]"
        if slot.get("options"):
            piece += " options: " + " / ".join(o["text"] for o in slot["options"])
        out.append(piece)
    return " + ".join(out)


def render_point(point: dict[str, Any], functions: dict[str, dict[str, Any]]) -> str:
    """One point as reviewer-facing Markdown. Block keys (``examples[1]``...) are the ``block``
    values a reviewer cites."""
    zh = point["target_lang"] == "zh-Hans"
    header = point["header"]
    function = functions.get(point["function"], {})
    lines = [
        f"### {point['id']}",
        f"- **metadata**: level {point['level']['value']} · point_type {point['point_type']} · function "
        f"{point['function']} ({function.get('title', {}).get('en', '?')}) · sequence {point.get('sequence', '?')} · "
        f"status {point['status']}",
        f"  - prereqs: {', '.join(point['prereqs']) or '-'}; contrasts: {', '.join(point['contrasts']) or '-'}; "
        f"error_tags: {', '.join(point['error_tags']) or '-'}",
        f"- **header**: {_pair_pinyin(header['native_title'], header.get('native_title_pinyin')) if zh else header['native_title']}"
        f" · title {_loc(header['title'])} · sub {_loc(header.get('sub'))}",
        f"  - summary {_loc(header['summary'])}",
        f"- **pattern** formula: {_slots(point['pattern']['formula'], zh)}",
    ]
    for name, slots in point["pattern"].get("variants", {}).items():
        lines.append(f"  - {name}: {_slots(slots, zh)}")
    illustration = point["pattern"]["illustration"]
    detail = illustration["kind"]
    if illustration.get("timeline"):
        detail += f" shape={illustration['timeline']['shape']}"
    for row in illustration.get("morphology", []):
        detail += f" [{row['base']} + {row['affix']} -> {row['result']}]"
    lines.append(f"- **illustration**: {detail}")
    lines.append("- **when_to_use**:")
    for index, item in enumerate(point.get("when_to_use", [])):
        lines.append(f"  - when_to_use[{index}]: {_loc(item)}")
    lines.append("- **examples**:")
    for index, example in enumerate(point["examples"]):
        text = _pair_pinyin(example["text"], example.get("pinyin")) if zh else example["text"]
        spans = ", ".join(f"{example['text'][s['start']:s['end']]}={s['role']}" for s in example["spans"])
        lines.append(f"  - examples[{index}] ({example['form']}): {text}  ‹{spans}›")
        lines.append(f"    - {_loc(example['translation'])} · {_loc(example['annotation'])}")
    if point.get("compare"):
        lines.append("- **compare**:")
        for index, item in enumerate(point["compare"]):
            lines.append(f"  - compare[{index}] with {item['with']}: this «{item['this_example']}» ({_loc(item['this_meaning'])}) "
                         f"vs other «{item['other_example']}» ({_loc(item['other_meaning'])})")
    lines.append("- **common_mistakes**:")
    for index, item in enumerate(point["common_mistakes"]):
        lines.append(f"  - common_mistakes[{index}] [{item['error_tag']}, l1 {','.join(item['l1'])}]: ✗ {item['wrong']} → ✓ {item['right']}")
        lines.append(f"    - {_loc(item['reason'])}")
    lines.append("- **quick_practice**:")
    for index, item in enumerate(point["quick_practice"]):
        options = " | ".join(
            f"{'✓' if i == item['answer'] else '✗'} {o['text']}" + (f" [{o['error_tag']}]" if o["error_tag"] else "")
            for i, o in enumerate(item["options"])
        )
        lines.append(f"  - quick_practice[{index}]: {item['q']}  ⟨{options}⟩")
        lines.append(f"    - {_loc(item['explain'])}")
    production = point.get("personal_production")
    if production:
        rule = " → ".join(
            f"{slot['role']}:{'/'.join(slot['any_of']) if 'any_of' in slot else '/' + slot['regex'] + '/'}"
            for slot in production["pattern_rule"]["slots"]
        )
        lines.append(f"- **personal_production**: prompt {_loc(production['prompt'])} · placeholder «{production['placeholder']}» · "
                     f"target_form {production['target_form']} · rule {rule} · sample «{production['sample']['text']}»")
    lines.append("")
    return "\n".join(lines)


def _overview(points: list[dict[str, Any]]) -> str:
    rows = ["| # | id | title | type | function | prereqs | contrasts | tags |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for index, point in enumerate(points, 1):
        header = point["header"]
        rows.append(
            f"| {index} | {point['id']} | {header['native_title']} — {header['title'].get('vi', '')} | {point['point_type']} | "
            f"{point['function']} | {', '.join(point['prereqs']) or '-'} | {', '.join(point['contrasts']) or '-'} | "
            f"{', '.join(point['error_tags'])} |"
        )
    return "\n".join(rows)


INSTRUCTIONS = """\
## Hướng dẫn cho người review (đọc kỹ trước khi làm)

Bạn đang review nội dung ngữ pháp do một mô hình AI viết cho ứng dụng học ngôn ngữ, người học là
**người Việt trưởng thành**. Giải thích viết bằng tiếng Việt (`vi`) và tiếng Anh (`en`). Bạn KHÔNG
sửa file; bạn chỉ trả về danh sách góp ý theo định dạng bên dưới.

### Định dạng trả lời (bắt buộc, mọi lượt)

Chỉ trả về **JSONL**: mỗi dòng một đối tượng JSON, đúng năm khoá, **không kèm chữ nào khác** (không
lời chào, không markdown, không ```):

`{"id": "...", "block": "...", "issue": "[loại] mô tả lỗi", "severity": "blocker|major|minor", "fix": "..."}`

- `id`: id điểm (ví dụ `en.past_simple`); góp ý về cả bậc (thiếu điểm, thứ tự, trùng lặp giữa
  các điểm) dùng `"id": "LEVEL"`.
- `block`: một trong `metadata`, `header`, `pattern`, `illustration`, `when_to_use[i]`, `examples[i]`,
  `compare[i]`, `common_mistakes[i]`, `quick_practice[i]`, `personal_production`; với `id` là
  `LEVEL` dùng `catalogue`. Dùng đúng khoá như trong nội dung (có chỉ số `[i]`).
- `issue`: bắt đầu bằng đúng một nhãn loại trong ngoặc vuông: `[knowledge]` sai kiến thức ngữ pháp,
  `[scope]` sai phạm vi hoặc sai bậc, `[wording]` diễn đạt (giải thích, ví dụ chưa tự nhiên), `[format]`
  sai định dạng/cấu trúc (công thức, span, nhãn, pinyin).
- `severity`: `blocker` (sai, không thể đưa cho người học), `major` (cần sửa), `minor` (nên sửa).
- `fix`: câu/khối đúng bạn đề nghị, cụ thể đến mức người khác chép được. Không có đề xuất thì để `""`.
- Nếu một phần/lượt **không có góp ý**, trả đúng một dòng:
  `{"id": "<id cuối cùng của phần>", "block": "none", "issue": "ok", "severity": "none", "fix": ""}`
  (dòng này cũng là dấu mốc để biết bạn đã xử lý đến đâu).

### Hai lượt

**Lượt 1 — tổng quan cả bậc** (chỉ dùng bảng "Tổng quan bậc" bên dưới): điểm trùng lặp, điểm sai bậc,
điểm còn thiếu so với khung chuẩn của bậc này, thứ tự và điều kiện tiên quyết (`prereqs`) hợp lý chưa,
mâu thuẫn giữa các điểm (hai điểm dạy hai quy tắc khác nhau cho cùng một hiện tượng). Trả JSONL rồi
**dừng**.

**Lượt 2 — chi tiết từng phần.** Khi người dùng gõ "bắt đầu lượt 2", chỉ review **Phần 1**, trả JSONL
rồi **dừng**; người dùng gõ "tiếp tục" thì sang phần kế. Nếu câu trả lời của bạn bị cắt giữa chừng,
người dùng sẽ nhắc và bạn **tiếp tục từ điểm ngay sau id cuối cùng đã trả**, không lặp lại phần đã trả.
Với mỗi điểm kiểm tra:

1. Đúng ngữ pháp và đúng phạm vi bậc; không dạy quá bậc.
2. Công thức (`pattern`) đủ mọi dạng mà tiêu đề nêu; ô có `role` hợp lý; ví dụ có span đúng ô.
3. Ví dụ tự nhiên, người bản ngữ sẽ nói; không gượng ép chỉ để minh hoạ.
4. Giải thích tiếng Việt rõ, giọng người lớn, không văn vẻ, không trẻ con; bản `en` (nếu có) khớp `vi`.
5. `common_mistakes` đúng là lỗi **người Việt** hay mắc với điểm này (không phải lỗi chung chung).
6. `quick_practice`: đúng **một** đáp án đúng; mỗi đáp án sai là lỗi người học thật (không phải
   dạng bịa vô nghĩa); `explain` khớp đáp án.
7. Nhãn lỗi (`error_tag`) gắn đúng loại lỗi; chỉ dùng nhãn trong danh sách nhãn của engine bên dưới.
8. `personal_production`: `prompt` dẫn tới đúng mẫu; `pattern_rule` nhận đúng câu dùng mẫu và không
   nhận câu không dùng; `sample` đúng.
{zh_extra}"""

ZH_EXTRA = """\
9. **Tiếng Trung**: pinyin từng chữ đúng (trong ngoặc sau chữ Hán), thanh điệu đúng, **chữ đa âm**
   (了, 长, 还, 数, 重, 得, 着, 行...) đọc đúng theo ngữ cảnh, biến điệu không bị ghi thành thanh gốc
   một cách sai lệch, câu tự nhiên, dùng chữ giản thể, không có khoảng trắng trong câu.
"""


def build_review(lang: str, level: str, root: Path = LAB_ROOT) -> str:
    points_by_id = load_points(lang, root)
    wanted = level.removeprefix("HSK") if lang == "zh" else level
    points = sorted(
        (p for p in points_by_id.values() if p["level"]["value"] == wanted and p.get("schema_version") == "0.4"),
        key=lambda p: (p["function"], p.get("sequence", 0), p["id"]),
    )
    if not points:
        raise ValueError(f"no schema 0.4 points at level {level} for {lang}")
    functions = {f["id"]: f for f in load_functions(root)["functions"]}
    sections = [points[i:i + SECTION_SIZE] for i in range(0, len(points), SECTION_SIZE)]
    tags = read_json(root / ERROR_TAGS_PATH)["languages"][points[0]["target_lang"]]["tags"]

    body = [render_point(p, functions) for p in points]
    section_texts = []
    cursor = 0
    for number, section in enumerate(sections, 1):
        chunk = "\n".join(body[cursor:cursor + len(section)])
        cursor += len(section)
        section_texts.append(f"## Phần {number} / {len(sections)} ({len(section)} điểm: {section[0]['id']} … {section[-1]['id']})\n\n{chunk}")
    overview = _overview(points)
    instructions = INSTRUCTIONS.replace("{zh_extra}", ZH_EXTRA if lang == "zh" else "")
    body_text = (
        f"{instructions}\n### Nhãn lỗi của engine ({points[0]['target_lang']})\n\n`{'`, `'.join(tags)}`\n\n"
        f"## Tổng quan bậc {level} (lượt 1)\n\n{overview}\n\n" + "\n\n".join(section_texts) + "\n"
    )
    chars = len(body_text)
    head = (
        f"# Review nội dung ngữ pháp — {lang} · bậc {level}\n\n"
        f"- Số điểm: **{len(points)}**, chia thành **{len(sections)} phần** (~{SECTION_SIZE} điểm mỗi phần).\n"
        f"- Độ dài file: ~{chars:,} ký tự (ước ~{chars // 3:,} token; mỗi phần ~{chars // 3 // max(len(sections), 1):,} token). "
        "Nếu công cụ của bạn không nhận nổi cả file, dán hướng dẫn + bảng tổng quan cho lượt 1, rồi dán từng phần cho lượt 2.\n"
        f"- Nguồn: `grammar_lab/content/{lang}/`, trạng thái các điểm là bản nháp AI (`draft_ai`), chưa duyệt.\n"
        f"- Xuất bởi `grammar_lab review-export` — đừng sửa tay file này, sửa nội dung rồi xuất lại.\n\n"
    )
    return head + body_text


def write_review(lang: str, level: str, root: Path = LAB_ROOT, out_dir: Path = DEFAULT_OUT) -> Path:
    if lang not in LANGS:
        raise ValueError(f"unknown lang {lang!r}")
    text = build_review(lang, level, root)
    path = review_path(lang, level, out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def levels_present(lang: str, root: Path = LAB_ROOT) -> list[str]:
    seen = {p["level"]["value"] for p in load_points(lang, root).values() if p.get("schema_version") == "0.4"}
    return [level_label(lang, value) for value in sorted(seen, key=lambda v: (len(v), v))]

