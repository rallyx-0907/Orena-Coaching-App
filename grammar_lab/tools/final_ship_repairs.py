from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"


def load(lang: str, point_id: str) -> tuple[Path, dict]:
    path = CONTENT / lang / f"{point_id}.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_en(obj: dict, text: str) -> None:
    obj["en"] = text


def repair_present_perfect() -> None:
    path, d = load("en", "en.present_perfect.experience")
    labels = {
        "chủ ngữ": "subject",
        "trợ động từ": "auxiliary verb",
        "quá khứ phân từ": "past participle",
        "tân ngữ": "object",
        "trạng ngữ thời gian": "time expression",
        "phủ định": "negation",
    }
    for slot in d["pattern"]["formula"]:
        add_en(slot["label"], labels[slot["label"]["vi"]])
    for variant in ("negative", "question"):
        for slot in d["pattern"]["variants"][variant]:
            add_en(slot["label"], labels[slot["label"]["vi"]])
    en_when = [
        "When you want to say you have (or have never) done something in your life, without saying when.",
        "When you ask someone about their experience, for example in an interview or when meeting for the first time.",
        "When you use words such as ever, never, before, or already to talk about experience.",
        "When you want to emphasize the result or present relevance of that experience.",
    ]
    for item, text in zip(d["when_to_use"], en_when, strict=True):
        add_en(item, text)
    anns = [
        "The experience happened in the past without a specific time.",
        "This experience has never happened up to now.",
        "Asks whether someone has ever had this experience, without asking when.",
    ]
    trans = [
        "I have visited Japan twice.",
        "She has never eaten sushi before.",
        "Have you ever been to Paris?",
    ]
    for ex, ann, tr in zip(d["examples"], anns, trans, strict=True):
        add_en(ex["annotation"], ann)
        add_en(ex["translation"], tr)
    reasons = [
        "With a specific past time expression such as last year, use the past simple, not the present perfect.",
        "In an ordinary affirmative experience statement, omit ever; at this level it is used mainly in questions.",
    ]
    for item, text in zip(d["common_mistakes"], reasons, strict=True):
        add_en(item["reason"], text)
    explains = [
        "The subject I takes have, not has or am.",
        "After has, use the past participle been, not went or go.",
        "Questions with you use Have, not Has or Do.",
    ]
    for item, text in zip(d["quick_practice"], explains, strict=True):
        add_en(item["explain"], text)
    save(path, d)


def repair_first_conditional() -> None:
    path, d = load("en", "en.conditional_first")
    labels = {
        "từ nối điều kiện": "conditional linker",
        "chủ ngữ mệnh đề if": "subject of the if-clause",
        "động từ chia hiện tại đơn": "verb in the present simple",
        "tân ngữ": "object",
        "chủ ngữ mệnh đề chính": "subject of the main clause",
        "trợ động từ will": "auxiliary will",
        "động từ nguyên thể": "base-form verb",
        "trợ động từ phủ định": "negative auxiliary",
    }
    for slot in d["pattern"]["formula"]:
        add_en(slot["label"], labels[slot["label"]["vi"]])
    for variant in ("negative", "question"):
        for slot in d["pattern"]["variants"][variant]:
            add_en(slot["label"], labels[slot["label"]["vi"]])
    en_when = [
        "When you want to say something may happen if a condition is met.",
        "When making a promise or threat based on a future action.",
        "When warning someone about a consequence if they do or do not do something.",
        "When negotiating or making an offer: if you do this, I will do that.",
    ]
    for item, text in zip(d["when_to_use"], en_when, strict=True):
        add_en(item, text)
    anns = [
        "The condition may happen; the result is in the future.",
        "Studying hard may lead to passing the exam.",
        "Negative condition: if she does not hurry, the unwanted result may happen.",
    ]
    trans = [
        "If it rains, we will stay at home.",
        "If you study hard, you will pass the exam.",
        "If she doesn't hurry, she will miss the train.",
    ]
    for ex, ann, tr in zip(d["examples"], anns, trans, strict=True):
        add_en(ex["annotation"], ann)
        add_en(ex["translation"], tr)
    add_en(
        d["common_mistakes"][0]["reason"],
        "In the if-clause of the first conditional, do not use will; use the present simple for the possible condition.",
    )
    explains = [
        "The if-clause uses the present simple, not will or the past simple.",
        "With singular she, the verb takes -es; do not use will in the if-clause.",
        "The main clause states the future result, so use will + base verb.",
    ]
    for item, text in zip(d["quick_practice"], explains, strict=True):
        add_en(item["explain"], text)
    save(path, d)


def repair_le_completion() -> None:
    path, d = load("zh", "zh.le_completion")
    labels = {
        "chủ ngữ": "subject",
        "động từ": "verb",
        "trợ từ hoàn thành": "completion particle",
        "tân ngữ": "object",
        "phủ định": "negation",
        "trợ từ nghi vấn": "question particle",
    }
    for slot in d["pattern"]["formula"]:
        add_en(slot["label"], labels[slot["label"]["vi"]])
    for variant in ("negative", "question"):
        for slot in d["pattern"]["variants"][variant]:
            add_en(slot["label"], labels[slot["label"]["vi"]])
    en_when = [
        "When you want to say an action happened and was completed, without needing to state the time.",
        "When the sentence contains a past-time marker such as 昨天, 上午, or 去年.",
        "When recounting a sequence of completed actions; each main verb may take 了.",
        "When emphasizing a completed quantity or result, for example 买了三本书.",
    ]
    for item, text in zip(d["when_to_use"], en_when, strict=True):
        add_en(item, text)
    anns = [
        "The buying action was completed in the past, with 昨天 as a time marker.",
        "A completed action is negated with 没, without 了.",
        "A 吗 question asks whether the viewing action was completed.",
    ]
    trans = ["Yesterday I bought a book.", "He didn't eat breakfast.", "Have you watched that movie?"]
    for ex, ann, tr in zip(d["examples"], anns, trans, strict=True):
        add_en(ex["annotation"], ann)
        add_en(ex["translation"], tr)
    add_en(d["compare"][0]["this_meaning"], "了 emphasizes a completed action, usually tied to a specific occurrence or concrete result.")
    add_en(d["compare"][0]["other_meaning"], "过 emphasizes having had an experience at least once, regardless of a specific time.")

    cm = d["common_mistakes"][0]
    cm["wrong"] = "我昨天了买一本书。"
    cm["right"] = "我昨天买了一本书。"
    cm["reason"] = {
        "vi": "了 chỉ sự hoàn thành đứng sau động từ chính trong mẫu này, không đứng trước động từ 买.",
        "en": "Completion 了 follows the main verb in this pattern; it does not come before 买.",
    }
    cm["wrong_pinyin"] = ["wǒ", "zuó", "tiān", "le", "mǎi", "yī", "běn", "shū", ""]
    cm["right_pinyin"] = ["wǒ", "zuó", "tiān", "mǎi", "le", "yī", "běn", "shū", ""]

    qp0, qp1, qp2 = d["quick_practice"]
    add_en(qp0["explain"], "The eating action was completed in the past, so 了 follows 吃.")
    add_en(qp1["explain"], "A completed action is negated with 没, without 了 or 不.")
    qp2["q"] = "我昨天___一本书。"
    qp2["options"] = [
        {"text": "买了", "error_tag": None, "pinyin": ["mǎi", "le"]},
        {"text": "了买", "error_tag": "aspect", "pinyin": ["le", "mǎi"]},
    ]
    qp2["answer"] = 0
    qp2["explain"] = {
        "vi": "Trong mẫu hành động hoàn thành, 了 đứng sau động từ: 买了, không phải 了买.",
        "en": "For a completed action, 了 follows the verb: 买了, not 了买.",
    }
    qp2["q_pinyin"] = ["wǒ", "zuó", "tiān", "", "", "", "yī", "běn", "shū", ""]
    save(path, d)


def repair_guo_experience() -> None:
    path, d = load("zh", "zh.guo_experience")
    labels = {
        "chủ ngữ": "subject",
        "động từ": "verb",
        "trợ từ trải nghiệm": "experiential particle",
        "tân ngữ": "object",
        "phủ định": "negation",
        "trợ từ nghi vấn": "question particle",
    }
    for slot in d["pattern"]["formula"]:
        add_en(slot["label"], labels[slot["label"]["vi"]])
    for variant in ("negative", "question"):
        for slot in d["pattern"]["variants"][variant]:
            add_en(slot["label"], labels[slot["label"]["vi"]])
    en_when = [
        "When you want to talk about an experience that happened before, without caring about the specific time.",
        "When answering questions like 你...过...吗？ to say whether you have ever done something.",
        "When negating an experience with 没(有) + verb + 过, not 不.",
        "When emphasizing how many times the experience occurred, place the frequency phrase after 过.",
    ]
    for item, text in zip(d["when_to_use"], en_when, strict=True):
        add_en(item, text)
    anns = [
        "Describes an experience that happened before without specifying when.",
        "Negate an experience with 没, not 不.",
        "Asks whether the other person has ever studied it, using 过...吗.",
    ]
    trans = ["I have eaten Beijing roast duck before.", "He has never been to the Great Wall.", "Have you ever studied Chinese?"]
    for ex, ann, tr in zip(d["examples"], anns, trans, strict=True):
        add_en(ex["annotation"], ann)
        add_en(ex["translation"], tr)
    add_en(d["compare"][0]["this_meaning"], "过 emphasizes having had an experience, regardless of a specific time or present result.")
    add_en(d["compare"][0]["other_meaning"], "了 emphasizes a completed action, often tied to a specific time or concrete result.")
    add_en(d["common_mistakes"][0]["reason"], "Vietnamese learners may translate ‘không’ directly as 不, but experiential 过 is negated with 没(有), not 不.")
    explains = [
        "An affirmative experience uses verb + 过, so the blank is the verb 去.",
        "Negate experience with 过 using 没, not 不 or 了.",
        "Questions about experience use 过 after the verb, not 了 or 不.",
    ]
    for item, text in zip(d["quick_practice"], explains, strict=True):
        add_en(item["explain"], text)
    save(path, d)


def repair_pronoun_practice() -> None:
    path, d = load("zh", "zh.canon.gf.hsk1.a_1_1_3.p1")
    qps = d["quick_practice"]
    qps[0].update({
        "q": "我叫李明。___是学生。",
        "options": [
            {"text": "我", "error_tag": None, "pinyin": ["wǒ"]},
            {"text": "我们", "error_tag": "other", "pinyin": ["wǒ", "men"]},
        ],
        "answer": 0,
        "explain": {"vi": "Người nói đang tự giới thiệu mình, nên dùng 我.", "en": "The speaker is introducing himself, so 我 is the correct pronoun."},
        "q_pinyin": ["wǒ", "jiào", "lǐ", "míng", "", "", "", "", "shì", "xué", "shēng", ""],
    })
    qps[1].update({
        "q": "王老师是女老师。___是老师。",
        "options": [
            {"text": "她", "error_tag": None, "pinyin": ["tā"]},
            {"text": "他", "error_tag": "other", "pinyin": ["tā"]},
        ],
        "answer": 0,
        "explain": {"vi": "Đã nói rõ 王老师 là nữ, nên dùng 她.", "en": "王老师 is explicitly identified as female, so 她 is correct."},
        "q_pinyin": ["wáng", "lǎo", "shī", "shì", "nǚ", "lǎo", "shī", "", "", "", "", "shì", "lǎo", "shī", ""],
    })
    qps[2].update({
        "q": "小王和小李都是女生。___是学生。",
        "options": [
            {"text": "她们", "error_tag": None, "pinyin": ["tā", "men"]},
            {"text": "她", "error_tag": "other", "pinyin": ["tā"]},
        ],
        "answer": 0,
        "explain": {"vi": "Câu nói về hai bạn nữ, nên dùng đại từ số nhiều 她们.", "en": "The sentence refers to two female students, so the plural pronoun 她们 is correct."},
        "q_pinyin": ["xiǎo", "wáng", "hé", "xiǎo", "lǐ", "dōu", "shì", "nǚ", "shēng", "", "", "", "", "shì", "xué", "shēng", ""],
    })
    save(path, d)


def repair_coordinate_mistake() -> None:
    path, d = load("zh", "zh.canon.gf.hsk1.a_1_4_4.p1")
    cm = d["common_mistakes"][0]
    cm.update({
        "wrong": "我喜欢喝茶，也我喜欢喝咖啡。",
        "right": "我喜欢喝茶，我也喜欢喝咖啡。",
        "reason": {
            "vi": "Khi vế thứ hai nêu lại chủ ngữ, 也 đứng sau chủ ngữ: 我也喜欢..., không đứng trước 我.",
            "en": "When the second clause repeats the subject, 也 comes after that subject: 我也喜欢..., not before 我.",
        },
        "wrong_pinyin": ["wǒ", "xǐ", "huān", "hē", "chá", "", "yě", "wǒ", "xǐ", "huān", "hē", "kā", "fēi", ""],
        "right_pinyin": ["wǒ", "xǐ", "huān", "hē", "chá", "", "wǒ", "yě", "xǐ", "huān", "hē", "kā", "fēi", ""],
    })
    save(path, d)


def repair_sentence_final_le() -> None:
    path, d = load("zh", "zh.canon.r5.hsk2_3_cu_i_c_u_thay_i_tr_ng_th_i")
    neg = d["pattern"]["variants"]["negative"]
    neg[1]["label"] = {"vi": "không còn / phủ định trạng thái trước", "en": "no longer / negates the previous state"}
    neg[2]["label"] = {"vi": "trạng thái nay không còn", "en": "state that no longer holds"}
    qp = d["quick_practice"][0]
    qp.update({
        "q": "天___，多穿点衣服。",
        "options": [
            {"text": "冷了", "error_tag": None, "pinyin": ["lěng", "le"]},
            {"text": "了冷", "error_tag": "particle", "pinyin": ["le", "lěng"]},
        ],
        "answer": 0,
        "explain": {
            "vi": "了 đứng sau tính từ để báo trạng thái mới: 冷了, không đặt trước thành 了冷.",
            "en": "Sentence-final 了 follows the adjective to mark a new state: 冷了, not 了冷.",
        },
        "q_pinyin": ["tiān", "", "", "", "duō", "chuān", "diǎn", "yī", "fú", ""],
    })
    save(path, d)


def repair_de_possessive() -> None:
    path, d = load("zh", "zh.de_possessive")
    qp = d["quick_practice"][2]
    qp.update({
        "q": "我喜欢___电脑。",
        "options": [
            {"text": "很新的", "error_tag": None, "pinyin": ["hěn", "xīn", "de"]},
            {"text": "很新", "error_tag": "particle", "pinyin": ["hěn", "xīn"]},
        ],
        "answer": 0,
        "explain": {
            "vi": "Cụm tính từ 很新 đứng trước danh từ cần 的: 很新的电脑.",
            "en": "The adjective phrase 很新 needs 的 before the noun: 很新的电脑.",
        },
        "q_pinyin": ["wǒ", "xǐ", "huān", "", "", "", "diàn", "nǎo", ""],
    })
    save(path, d)


def repair_ma_compare() -> None:
    path, d = load("zh", "zh.ma_question")
    cmp = d["compare"][0]
    cmp.update({
        "with": "zh.ne_question",
        "this_example": "你是老师吗？",
        "other_example": "我是老师，你呢？",
        "this_meaning": {"vi": "吗 đặt cuối một câu đầy đủ để hỏi có/không.", "en": "吗 goes at the end of a complete statement to make a yes/no question."},
        "other_meaning": {"vi": "呢 dùng để hỏi lại hoặc tiếp nối một chủ đề đã rõ, như ‘còn bạn thì sao?’. ", "en": "呢 continues an established topic or asks a return question, like ‘and you?’."},
        "this_example_pinyin": ["nǐ", "shì", "lǎo", "shī", "ma", ""],
        "other_example_pinyin": ["wǒ", "shì", "lǎo", "shī", "", "nǐ", "ne", ""],
    })
    save(path, d)


def repair_qing_request() -> None:
    path, d = load("zh", "zh.qing_request")
    cm = d["common_mistakes"][0]
    cm.update({
        "wrong": "请喝茶你。",
        "right": "请你喝茶。",
        "reason": {
            "vi": "Khi nêu người được mời/yêu cầu, người đó đứng sau 请 và trước động từ: 请你喝茶.",
            "en": "When the person being invited or asked is stated, that person comes after 请 and before the verb: 请你喝茶.",
        },
        "wrong_pinyin": ["qǐng", "hē", "chá", "nǐ", ""],
        "right_pinyin": ["qǐng", "nǐ", "hē", "chá", ""],
    })
    save(path, d)


def repair_serial_verbs() -> None:
    path, d = load("zh", "zh.serial_verbs.qu_lai")
    formula = d["pattern"]["formula"]
    place_slot = {
        "text": "地点",
        "role": "location",
        "label": {"vi": "địa điểm", "en": "place"},
        "optional": True,
        "pinyin": ["dì", "diǎn"],
    }
    if not any(slot.get("role") == "location" for slot in formula):
        formula.insert(2, place_slot)
    save(path, d)


def repair_zai_practice() -> None:
    path, d = load("zh", "zh.zai_progressive")
    qps = d["quick_practice"]
    qps[0].update({
        "q": "他___吃饭呢。",
        "options": [
            {"text": "正在", "error_tag": None, "pinyin": ["zhèng", "zài"]},
            {"text": "是", "error_tag": "aspect", "pinyin": ["shì"]},
        ],
        "answer": 0,
        "explain": {"vi": "正在 đứng trước động từ 吃 để nhấn hành động đang diễn ra; 是 không phải dấu hiệu tiếp diễn.", "en": "正在 goes before 吃 to mark an action in progress; 是 is not a progressive marker."},
    })
    qps[1].update({
        "q": "我们___学习中文。",
        "options": [
            {"text": "在", "error_tag": None, "pinyin": ["zài"]},
            {"text": "有", "error_tag": "aspect", "pinyin": ["yǒu"]},
        ],
        "answer": 0,
        "explain": {"vi": "在 đứng trước 学习 để nói hành động đang diễn ra; 有 không tạo thể tiếp diễn.", "en": "在 before 学习 marks an action in progress; 有 does not form the progressive."},
    })
    save(path, d)


def repair_affirmative_negative_pattern() -> None:
    path, d = load("zh", "zh.affirmative_negative_question")
    subject = {
        "text": "主语", "role": "subject", "label": {"vi": "chủ ngữ", "en": "subject"}, "pinyin": ["zhǔ", "yǔ"]
    }
    regular = {
        "text": "V/Adj", "role": "verb", "label": {"vi": "động từ hoặc tính từ", "en": "verb or adjective"},
        "options": [
            {"text": "是", "pinyin": ["shì"]},
            {"text": "去", "pinyin": ["qù"]},
            {"text": "好", "pinyin": ["hǎo"]},
        ],
        "pinyin": ["", "", "", "", ""],
    }
    repeated = dict(regular)
    repeated["label"] = {"vi": "lặp lại cùng động từ hoặc tính từ", "en": "repeat the same verb or adjective"}
    obj = {"text": "宾语", "role": "object", "label": {"vi": "tân ngữ", "en": "object"}, "optional": True, "pinyin": ["bīn", "yǔ"]}
    d["pattern"]["formula"] = [subject, regular, {"text": "不", "role": "marker", "label": {"vi": "phủ định 不", "en": "negator 不"}, "pinyin": ["bù"]}, repeated, obj]
    d["pattern"]["variants"]["question"] = [
        subject,
        {"text": "有", "role": "verb", "label": {"vi": "động từ 有", "en": "verb 有"}, "pinyin": ["yǒu"]},
        {"text": "没", "role": "marker", "label": {"vi": "phủ định của 有", "en": "negator used with 有"}, "pinyin": ["méi"]},
        {"text": "有", "role": "verb", "label": {"vi": "lặp lại 有", "en": "repeated 有"}, "pinyin": ["yǒu"]},
        obj,
    ]
    save(path, d)


def main() -> None:
    repair_present_perfect()
    repair_first_conditional()
    repair_le_completion()
    repair_guo_experience()
    repair_pronoun_practice()
    repair_coordinate_mistake()
    repair_sentence_final_le()
    repair_de_possessive()
    repair_ma_compare()
    repair_qing_request()
    repair_serial_verbs()
    repair_zai_practice()
    repair_affirmative_negative_pattern()
    print("Applied deterministic ship repairs: 4 approval-locale debts + reviewed HSK1 feedback batch.")


if __name__ == "__main__":
    main()
