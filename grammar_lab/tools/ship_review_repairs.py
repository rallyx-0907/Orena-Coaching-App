from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH = ROOT / "content" / "zh"


def load(point_id: str):
    path = ZH / f"{point_id}.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# 1) A-not-A: do not present 有不有 as a normal 不-pattern.
path, d = load("zh.affirmative_negative_question")
for slot in d["pattern"]["formula"]:
    if slot.get("options") == ["是", "有", "去", "好"]:
        slot["options"] = ["是", "去", "好"]
    if slot.get("options") == ["不", "没"]:
        slot["options"] = ["不"]
save(path, d)

# 2) Pronoun practices need context so only one option can be right.
path, d = load("zh.canon.gf.hsk1.a_1_1_3.p1")
qs = d["quick_practice"]
qs[0]["q"] = "我叫小明。___是学生。"
qs[0]["q_pinyin"] = ["wǒ", "jiào", "xiǎo", "míng", "", "", "", "", "shì", "xué", "shēng", ""]
qs[0]["explain"] = {"vi": "Câu trước giới thiệu người nói là 小明, nên đại từ phù hợp là 我, không phải 我们."}
qs[1]["q"] = "王老师是女老师。___是老师。"
qs[1]["q_pinyin"] = ["wáng", "lǎo", "shī", "shì", "nǚ", "lǎo", "shī", "", "", "", "", "shì", "lǎo", "shī", ""]
qs[1]["explain"] = {"vi": "王老师 được xác định là nữ, nên dùng 她, không dùng 他."}
qs[2]["q"] = "小红和小丽来了。___是学生。"
qs[2]["q_pinyin"] = ["xiǎo", "hóng", "hé", "xiǎo", "lì", "lái", "le", "", "", "", "", "shì", "xué", "shēng", ""]
qs[2]["explain"] = {"vi": "小红 và 小丽 là hai nữ, nên dùng đại từ số nhiều 她们."}
save(path, d)

# 3) Coordination: shared subject without 也 is valid; use a real word-order error instead.
path, d = load("zh.canon.gf.hsk1.a_1_4_4.p1")
cm = d["common_mistakes"][0]
cm["wrong"] = "我喜欢喝茶，也咖啡喜欢喝。"
cm["wrong_pinyin"] = ["wǒ", "xǐ", "huan", "hē", "chá", "", "yě", "kā", "fēi", "xǐ", "huan", "hē", ""]
cm["right"] = "我喜欢喝茶，也喜欢喝咖啡。"
cm["reason"] = {"vi": "也 đặt trước vị ngữ của vế song song; không đảo tân ngữ 咖啡 lên trước động từ 喜欢喝."}
save(path, d)

# 4) Sentence-final 了: make the practice unambiguous.
path, d = load("zh.canon.r5.hsk2_3_cu_i_c_u_thay_i_tr_ng_th_i")
qp = d["quick_practice"][0]
qp["q"] = "天气变___了，多穿点衣服。"
qp["q_pinyin"] = ["tiān", "qì", "biàn", "", "", "", "le", "", "duō", "chuān", "diǎn", "yī", "fu", ""]
qp["options"] = [
    {"text": "冷", "error_tag": None, "pinyin": ["lěng"]},
    {"text": "很冷", "error_tag": "particle", "pinyin": ["hěn", "lěng"]},
]
qp["answer"] = 0
qp["explain"] = {"vi": "变冷了 diễn tả thời tiết đã chuyển sang trạng thái lạnh; 很冷 không đứng sau 变 trong mẫu này."}
save(path, d)

# 5) 的 practice: test the particle itself, not the optional 的 after an adjective.
path, d = load("zh.de_possessive")
qp = d["quick_practice"][2]
qp["q"] = "这是小王___电脑。"
qp["q_pinyin"] = ["zhè", "shì", "xiǎo", "wáng", "", "", "", "diàn", "nǎo", ""]
qp["options"] = [
    {"text": "的", "error_tag": None, "pinyin": ["de"]},
    {"text": "新", "error_tag": "particle", "pinyin": ["xīn"]},
]
qp["answer"] = 0
qp["explain"] = {"vi": "Quan hệ sở hữu giữa 小王 và 电脑 cần trợ từ 的: 小王的电脑."}
save(path, d)

# 6) Verb 了: sentence-final 了 can be valid; use a true placement error. Also remove 过 ambiguity.
path, d = load("zh.le_completion")
cm = d["common_mistakes"][0]
cm["wrong"] = "我昨天了买一本书。"
cm["right"] = "我昨天买了一本书。"
cm["reason"] = {"vi": "了 hoàn thành đứng sau động từ chính 买 trong mẫu này, không đứng trước động từ."}
cm["wrong_pinyin"] = ["wǒ", "zuó", "tiān", "le", "mǎi", "yī", "běn", "shū", ""]
qp = d["quick_practice"][2]
qp["options"] = [
    {"text": "看了", "error_tag": None, "pinyin": ["kàn", "le"]},
    {"text": "了看", "error_tag": "aspect", "pinyin": ["le", "kàn"]},
]
qp["answer"] = 0
qp["explain"] = {"vi": "Trong mẫu hoàn thành này, 了 đứng sau động từ 看: 看了; không đặt 了 trước động từ."}
save(path, d)

# 7) 吗 comparison: keep the declared 呢 contrast and use a real 呢 example.
path, d = load("zh.ma_question")
cmp = d["compare"][0]
cmp["with"] = "zh.ne_question"
cmp["other_meaning"] = {"vi": "呢 thường dùng để hỏi tiếp hoặc hỏi ngược về một chủ đề đã rõ, không phải mẫu A-not-A."}
cmp["other_example"] = "你呢？"
cmp["other_example_pinyin"] = ["nǐ", "ne", ""]
save(path, d)

# 8) 请: 我请你喝茶 is valid ('I invite/treat you to tea'), so replace with a real word-order error.
path, d = load("zh.qing_request")
cm = d["common_mistakes"][0]
cm["wrong"] = "请你茶喝。"
cm["wrong_pinyin"] = ["qǐng", "nǐ", "chá", "hē", ""]
cm["right"] = "请你喝茶。"
cm["reason"] = {"vi": "Sau 请你, động từ 喝 đứng trước tân ngữ 茶: 请你喝茶."}
save(path, d)

# 9) 去/来 serial verbs: examples allow an intervening destination, so show it in the formula.
path, d = load("zh.serial_verbs.qu_lai")
formula = d["pattern"]["formula"]
if not any(slot.get("text") == "地点" for slot in formula):
    formula.insert(2, {
        "text": "地点",
        "role": "other",
        "label": {"vi": "địa điểm"},
        "optional": True,
        "pinyin": ["dì", "diǎn"],
    })
save(path, d)

# 10) 在/正在 are both valid; use malformed duplicates as distractors.
path, d = load("zh.zai_progressive")
for idx, good, bad, good_py, bad_py in [
    (0, "正在", "正在在", ["zhèng", "zài"], ["zhèng", "zài", "zài"]),
    (1, "在", "在在", ["zài"], ["zài", "zài"]),
]:
    qp = d["quick_practice"][idx]
    qp["options"] = [
        {"text": good, "error_tag": None, "pinyin": good_py},
        {"text": bad, "error_tag": "aspect", "pinyin": bad_py},
    ]
    qp["answer"] = 0
    qp["explain"] = {"vi": f"{good} là dấu hiệu tiến hành đúng; {bad} lặp thừa 在."}
save(path, d)

print("Applied deterministic ship-review repairs to 10 HSK1 files.")
