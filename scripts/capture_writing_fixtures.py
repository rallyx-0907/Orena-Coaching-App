"""Capture the Writing room's real API payloads for the screen gates.

The isolated verification stack has no AI provider key, so it can never create an essay. This script
therefore drives the REAL application in-process (fastapi TestClient, throwaway sqlite repository,
exactly how tests/test_saved_reviews.py does) and replaces ONLY the model call
(`app.generate_structured`) with one structured evaluator answer per call. Everything downstream of
that - `validate_result`, `weighted_overall`, `_bounded_review`, grammar links, persistence,
`row_to_dict`, `revision_delta`, `project_writing_review`, `project_revision_compare` - is the
product's own code, so every payload below is what the routes really return for those evaluator
answers. Nothing is hand-written into a response.

Run from the repo root with the project's own Python (the one that has FastAPI and SQLAlchemy):
    python scripts/capture_writing_fixtures.py
It writes scripts/fixtures/api/writing_*.json (not the `_live` ones - see scripts/fixtures/api/README.md).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "scripts" / "fixtures" / "api"

tmp = Path(tempfile.mkdtemp(prefix="orena-writing-capture-"))
os.environ.update(
    {
        "PERSISTENCE_BACKEND": "sqlite",
        "POSTGRES_RUNTIME_URL": "",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "GOOGLE_REDIRECT_URI": "",
        "APP_ENV": "development",
        "PUBLIC_BASE_URL": "http://localhost:8000",
        "WRITING_DB": str(tmp / "w.db"),
        "AUTH_DB": str(tmp / "a.db"),
        "PLATFORM_DB": str(tmp / "p.db"),
        "PRODUCT_DB": str(tmp / "pr.db"),
    }
)

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from writing_coach.ai.base import AIResult  # noqa: E402

EN_V1 = (
    "Last weekend I go to the beach with my family. We was very happy because the weather were nice. "
    "I like swim in the sea and eat fresh seafood. In the evening, we watched the sunset together, "
    "it was a wonderful memory."
)
EN_V2 = (
    "Last weekend I went to the beach with my family. We were very happy because the weather was nice. "
    "I like swim in the sea and eat fresh seafood. In the evening, we watched the sunset together. "
    "It was a wonderful memory, and I hope to go their again."
)
ZH_V1 = "昨天我去了公园，天气很好。我和朋友们一起玩了很多游戏，我们都很开心。我把作业做完了在回家。"


def error(category, fragment, suggestion, why, rule, example="", confidence=0.9):
    return {
        "category": category,
        "fragment": fragment,
        "suggestion": suggestion,
        "explanation_vi": why,
        "mini_rule_vi": rule,
        "example": example,
        "confidence": confidence,
    }


def strength(category, fragment, why, confidence=0.9):
    return {"category": category, "fragment": fragment, "explanation_vi": why, "confidence": confidence}


ANSWERS = [
    # 1: English v1
    {
        "band_status": "sufficient_evidence",
        "cefr_estimate": "B1",
        "grammar": 48.0,
        "vocabulary": 62.0,
        "coherence": 66.0,
        "task_achievement": 64.0,
        "naturalness": 55.0,
        "summary_vi": "Bài viết kể chuyện rõ ràng và dễ theo dõi, nhưng còn vài lỗi chia động từ làm câu văn kém tự nhiên.",
        "strengths_vi": ["Bạn kể theo trình tự thời gian rất rõ ràng."],
        "strength_evidence": [
            strength("coherence", "In the evening, we watched the sunset together", "Bạn dùng mở đầu chỉ thời gian để nối các ý tự nhiên."),
            strength("vocabulary", "a wonderful memory", "Cụm danh từ này diễn tả cảm xúc chính xác và tự nhiên."),
        ],
        "priorities_vi": ["Ôn lại cách chia động từ ở thì quá khứ đơn."],
        "errors": [
            error(
                "tense",
                "I go to the beach",
                "I went to the beach",
                "Câu kể về chuyến đi cuối tuần trước nên cần dùng thì quá khứ đơn.",
                "Sự việc đã xảy ra và đã kết thúc: dùng quá khứ đơn (went, not go).",
                "Yesterday I went to school.",
                0.95,
            ),
            error(
                "agreement",
                "We was very happy",
                "We were very happy",
                "Chủ ngữ 'we' đi với 'were', không đi với 'was'.",
                "We / you / they + were; I / he / she / it + was.",
                "They were tired after the trip.",
                0.9,
            ),
            error(
                "agreement",
                "the weather were nice",
                "the weather was nice",
                "'Weather' là danh từ không đếm được, số ít nên đi với 'was'.",
                "Danh từ không đếm được dùng động từ số ít.",
                "The news was good.",
                0.85,
            ),
            error(
                "word_form",
                "I like swim in the sea",
                "I like swimming in the sea",
                "Sau 'like' để nói sở thích, dùng động từ dạng V-ing.",
                "like + V-ing (sở thích chung).",
                "She likes cooking dinner.",
                0.8,
            ),
            error(
                "punctuation",
                "together, it was",
                "together. It was",
                "Hai mệnh đề độc lập không thể nối chỉ bằng dấu phẩy; hãy tách thành hai câu.",
                "Hai mệnh đề độc lập cần dấu chấm hoặc liên từ, không chỉ dấu phẩy.",
                "",
                0.75,
            ),
        ],
    },
    # 2: English v2 (revision of 1)
    {
        "band_status": "sufficient_evidence",
        "cefr_estimate": "B1",
        "grammar": 71.0,
        "vocabulary": 64.0,
        "coherence": 72.0,
        "task_achievement": 68.0,
        "naturalness": 66.0,
        "summary_vi": "Bạn đã sửa được phần lớn lỗi chia động từ; bài viết trôi chảy hơn hẳn. Còn một lỗi dạng động từ và một lỗi chính tả mới.",
        "strengths_vi": ["Các câu đã có thì và chủ ngữ hợp lý."],
        "strength_evidence": [
            strength("coherence", "In the evening, we watched the sunset together", "Bạn dùng mở đầu chỉ thời gian để nối các ý tự nhiên."),
        ],
        "priorities_vi": ["Ôn lại cấu trúc like + V-ing."],
        "errors": [
            error(
                "word_form",
                "I like swim in the sea",
                "I like swimming in the sea",
                "Sau 'like' để nói sở thích, dùng động từ dạng V-ing.",
                "like + V-ing (sở thích chung).",
                "She likes cooking dinner.",
                0.9,
            ),
            error(
                "word_choice",
                "go their again",
                "go there again",
                "'Their' là tính từ sở hữu; chỉ nơi chốn phải dùng 'there'.",
                "there = ở đó; their = của họ.",
                "I hope to go there again.",
                0.85,
            ),
        ],
    },
    # 3: Chinese v1
    {
        "band_status": "sufficient_evidence",
        "cefr_estimate": "HSK3",
        "grammar": 58.0,
        "vocabulary": 60.0,
        "coherence": 65.0,
        "task_achievement": 62.0,
        "naturalness": 57.0,
        "summary_vi": "Bài viết rõ ràng, dùng đúng nhiều mẫu câu cơ bản; cần chú ý trật tự các hành động nối tiếp nhau.",
        "strengths_vi": ["Bạn kể được các hoạt động trong ngày một cách mạch lạc."],
        "strength_evidence": [
            strength("coherence", "我们都很开心", "Câu kết ngắn gọn, tự nhiên và nêu đúng cảm xúc."),
        ],
        "priorities_vi": ["Ôn lại cách nối hai hành động nối tiếp bằng 再."],
        "errors": [
            error(
                "conjunction",
                "做完了在回家",
                "做完了再回家",
                "Để nói làm xong việc này rồi mới làm việc kia, cần dùng liên từ chỉ trình tự, không dùng giới từ chỉ nơi chốn.",
                "Làm xong việc thứ nhất rồi mới làm việc thứ hai: dùng từ chỉ trình tự nối hai hành động.",
                "吃完饭再去看电影。",
                0.9,
            ),
        ],
    },
]


class Feeder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, **kwargs):  # noqa: ANN003
        answer = ANSWERS[self.calls]
        self.calls += 1
        return AIResult(data=dict(answer), provider="captured", model="fixed-answer", runtime={})


def dump(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", name)


def main() -> None:
    with TestClient(app_module.app) as client:
        feeder = Feeder()
        app_module.generate_structured = feeder
        app_module.ALLOW_FALLBACK = False
        app_module.get_learner_profile = lambda *a, **k: {"support_language": "vi"}
        app_module._review_in_flight.clear()
        # English series: v1, then a revision of it (v2).
        r1 = client.post("/api/evaluate", json={"prompt": "Write about your last weekend", "text": EN_V1, "target_cefr": "B1", "learning_language": "en"})
        assert r1.status_code == 200, r1.text
        first = r1.json()
        r2 = client.post(
            "/api/evaluate",
            json={"prompt": "Write about your last weekend", "text": EN_V2, "target_cefr": "B1", "parent_essay_id": first["id"], "learning_language": "en"},
        )
        assert r2.status_code == 200, r2.text
        second = r2.json()
        dump("writing_evaluate.json", second)
        dump("writing_essay_detail_v1.json", client.get(f"/api/essays/{first['id']}").json())
        dump("writing_essay_review_v1.json", client.get(f"/api/essays/{first['id']}/review").json())
        dump("writing_essay_detail.json", client.get(f"/api/essays/{second['id']}").json())
        dump("writing_essay_review.json", client.get(f"/api/essays/{second['id']}/review").json())
        dump("writing_essay_revision.json", client.get(f"/api/essays/{second['id']}/revision").json())
        kept = client.post(f"/api/essays/{second['id']}/keep")
        dump("writing_essay_keep.json", kept.json())
        client.delete(f"/api/essays/{second['id']}/keep")
        # The first version has nothing to compare with: the real 404.
        miss = client.get(f"/api/essays/{first['id']}/revision")
        dump("writing_essay_revision_first.json", {"status": miss.status_code, "body": miss.json()})

        # Chinese: the same real path with the learning language switched to zh.
        sw = client.post("/api/platform/language", json={"language": "zh"})
        print("switch zh:", sw.status_code)
        r3 = client.post("/api/evaluate", json={"prompt": "写一写你昨天做了什么", "text": ZH_V1, "learning_language": "zh"})
        assert r3.status_code == 200, r3.text
        zh = r3.json()
        dump("writing_essay_detail.zh.json", client.get(f"/api/essays/{zh['id']}").json())
        dump("writing_essay_review.zh.json", client.get(f"/api/essays/{zh['id']}/review").json())
        client.post("/api/platform/language", json={"language": "en"})
    print("calls:", feeder.calls)


if __name__ == "__main__":
    main()
