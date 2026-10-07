from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fix_sentence_final_le(data: dict) -> None:
    data["quick_practice"][0]["q_pinyin"] = [
        "tiān", "", "", "", "", "duō", "chuān", "diǎn", "yī", "fú", ""
    ]


def fix_serial_place_role(data: dict) -> None:
    for slot in data["pattern"]["formula"]:
        if slot.get("text") == "地点":
            slot["role"] = "place"


patch(ROOT / "content" / "zh" / "zh.canon.r5.hsk2_3_cu_i_c_u_thay_i_tr_ng_th_i.json", fix_sentence_final_le)
patch(ROOT / "content" / "zh" / "zh.serial_verbs.qu_lai.json", fix_serial_place_role)
print("Applied ship-repair schema hotfixes.")
