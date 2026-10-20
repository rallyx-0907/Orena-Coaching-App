"""The band estimator (Monetisation v2, Intelligence lead): an IELTS writing band, or the HSK level, estimated per
criterion with reasons and the fixes most likely to lift it. Always an estimate. Until the pilot calibration agrees with
real scores it is for administrators only, labelled experimental (MONETIZATION_V2_SPEC §3)."""

from __future__ import annotations

import pytest

from writing_coach.agent import band
from writing_coach.ai.base import AIResult

ESSAY = " ".join(["Some people believe that cities should invest more in public transport than in new roads."] * 12)
CHINESE = "我认为学习中文很有意思。" * 8


def answer(exam="ielts", score=6, quote="public transport", fixes=3, **extra):
    criteria = band.CRITERIA[exam]
    data = {
        "insufficient_evidence": False,
        "criteria": [{"criterion": key, "score": score, "reason": f"lý do {key}", "evidence": [quote]}
                     for key in criteria],
        "fixes": [{"fix": f"sửa {n}", "why": "vì", "before": quote, "after": "public transportation"}
                  for n in range(fixes)],
        **extra,
    }
    return data


class Generate:
    def __init__(self, data):
        self.data, self.calls = data, []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return AIResult(data=self.data, provider="gemini", model="gemini-3.5-flash-lite", runtime={})


def request(**overrides):
    values = {"exam": "ielts", "task": "task2", "prompt": "Roads or public transport?", "text": ESSAY,
              "support": "vi"}  # fmt: skip
    values.update(overrides)
    return band.BandRequest(**values)


@pytest.mark.parametrize(("scores", "overall"), [
    ([6, 6, 6, 7], 6.5),  # 6.25 rounds up to the half band
    ([6, 7, 7, 7], 7.0),  # 6.75 rounds up to the whole band
    ([6, 6, 6, 6], 6.0),
    ([5, 6, 6, 6], 6.0),  # 5.75 also rounds up to the whole band
    ([5, 5, 6, 6], 5.5),
    ([5, 5, 5, 6], 5.5),  # 5.25: .25 rounds up to the half band
    ([5, 5, 5, 5], 5.0),
])
def test_the_ielts_overall_follows_the_official_rounding(scores, overall):
    assert band.ielts_overall(scores) == overall


def test_the_hsk_level_is_conservative_and_groups_seven_to_nine():
    assert band.hsk_overall([3, 4, 4, 4]) == 3  # the mean 3.75 is not yet level 4
    assert band.hsk_label(4) == "HSK 4" and band.hsk_label(8) == "HSK 7-9"


def test_an_estimate_names_every_criterion_computes_the_overall_and_says_it_is_an_estimate():
    generate = Generate(answer(score=6))
    result = band.estimate(request(), generate=generate)
    assert result["estimate"] is True and result["experimental"] is True
    assert result["exam"] == "ielts" and result["overall"] == 6.0 and result["label"] == "IELTS 6.0"
    assert [c["criterion"] for c in result["criteria"]] == list(band.CRITERIA["ielts"])
    assert len(result["fixes"]) == 3
    assert generate.calls[0]["capability_key"] == "writing_evaluator"  # learner text: the writing route and its cap


def test_the_overall_is_the_servers_never_the_models():
    data = answer(score=5)
    data["overall"] = 9  # whatever the model says
    assert band.estimate(request(), generate=Generate(data))["overall"] == 5.0


def test_a_quote_that_is_not_in_the_learners_text_is_dropped():
    result = band.estimate(request(), generate=Generate(answer(quote="a sentence the learner never wrote")))
    assert all(c["evidence"] == [] for c in result["criteria"])
    assert result["fixes"] == []  # a fix about words the learner did not write is not shown


def test_a_sample_too_short_is_refused_without_a_model_call():
    generate = Generate(answer())
    result = band.estimate(request(text="Public transport is good."), generate=generate)
    assert result["insufficient_evidence"] is True and result["overall"] is None
    assert generate.calls == []  # nothing spent


def test_the_model_may_say_the_evidence_is_insufficient():
    result = band.estimate(request(), generate=Generate(answer(insufficient_evidence=True)))
    assert result["insufficient_evidence"] is True and result["overall"] is None and result["criteria"] == []


def test_a_score_out_of_range_is_refused():
    with pytest.raises(band.BandUnavailable):
        band.estimate(request(), generate=Generate(answer(score=12)))


def test_hsk_counts_characters_and_labels_the_level():
    data = answer(exam="hsk", score=4, quote="学习中文")
    result = band.estimate(request(exam="hsk", task="free", text=CHINESE), generate=Generate(data))
    assert result["overall"] == 4 and result["label"] == "HSK 4"
    assert [c["criterion"] for c in result["criteria"]] == list(band.CRITERIA["hsk"])


def test_the_exam_must_match_the_language_learned():
    assert band.exam_for_language("en") == "ielts" and band.exam_for_language("zh") == "hsk"
    assert band.exam_for_language("ja") is None  # no exam: the route refuses with 409, never a 500


def test_calibration_agreement_reports_the_pilot_measures():
    pairs = [(6.0, 6.0), (6.5, 6.0), (7.0, 6.0), (5.5, 5.5)]
    report = band.agreement(pairs)
    assert report == {"n": 4, "mean_absolute_error": 0.375, "within_half_band": 0.75, "exact": 0.5}


# --- the route: administrators only until the pilot calibration agrees (spec §3) ----------------------------------

from tests.test_agent_api import client  # noqa: E402,F401 - the agent router's test client fixture


@pytest.fixture()
def admin_route(monkeypatch):
    from tests.test_agent_api import enable
    from writing_coach.agent import api as agent_api

    enable([])
    seen = {"admin": True, "generate": Generate(answer(score=7))}

    def guard(request):
        if not seen["admin"]:
            from fastapi import HTTPException

            raise HTTPException(403, "Platform administrator access required")
        return {"role": "admin"}

    monkeypatch.setattr(agent_api, "_band_admin", guard)
    from writing_coach.agent.tools import LearnerScope

    # an English learner: IELTS is their exam (the request context's default language is not assumed)
    monkeypatch.setattr(agent_api.LearnerScope, "from_request_context", classmethod(lambda cls: LearnerScope("u1", "en")))
    monkeypatch.setattr(band, "_generate", seen["generate"])
    monkeypatch.setattr(band, "_mode", "admin")
    return seen


BODY = {"exam": "ielts", "task": "task2", "prompt": "Roads or public transport?", "text": ESSAY, "support": "vi"}


def test_an_administrator_gets_an_experimental_estimate(client, admin_route):  # noqa: F811
    answered = client.post("/api/agent/band/writing", json=BODY)
    assert answered.status_code == 200
    assert answered.json()["overall"] == 7.0 and answered.json()["experimental"] is True
    assert answered.headers["Cache-Control"] == "no-store"


def test_a_learner_is_refused_before_any_model_call(client, admin_route):  # noqa: F811
    admin_route["admin"] = False
    assert client.post("/api/agent/band/writing", json=BODY).status_code == 403
    assert admin_route["generate"].calls == []


def test_switched_off_the_route_is_not_there(client, admin_route, monkeypatch):  # noqa: F811
    monkeypatch.setattr(band, "_mode", band.mode_from_env({band.MODE_ENV: "off"}))
    assert client.post("/api/agent/band/writing", json=BODY).status_code == 404


def test_the_exam_must_be_the_one_for_the_language_learned(client, admin_route):  # noqa: F811
    refused = client.post("/api/agent/band/writing", json={**BODY, "exam": "hsk"})
    assert refused.status_code == 409 and refused.json()["detail"] == "exam_language_mismatch"
    assert admin_route["generate"].calls == []


def test_an_unusable_model_answer_is_a_502_never_a_patched_band(client, admin_route, monkeypatch):  # noqa: F811
    monkeypatch.setattr(band, "_generate", Generate(answer(score=12)))
    refused = client.post("/api/agent/band/writing", json=BODY)
    assert refused.status_code == 502 and refused.json()["detail"] == "band_unavailable"


def test_a_provider_that_cannot_answer_is_a_503(client, admin_route, monkeypatch):  # noqa: F811
    from writing_coach.ai.base import AIProviderUnavailable

    def down(**kwargs):
        raise AIProviderUnavailable("no provider")

    monkeypatch.setattr(band, "_generate", down)
    refused = client.post("/api/agent/band/writing", json=BODY)
    assert refused.status_code == 503 and refused.json()["detail"] == "ai_unavailable"


def test_the_switch_reads_off_and_defaults_to_administrators():
    assert band.mode_from_env({}) == "admin" and band.mode_from_env({"BAND_ESTIMATOR": " OFF "}) == "off"
    assert band.mode_from_env({"BAND_ESTIMATOR": "learners"}) == "admin"  # no learner opening through a switch
