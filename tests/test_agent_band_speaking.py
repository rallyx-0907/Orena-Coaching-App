"""The speaking band estimator (Monetisation v2, MONETIZATION_V2_SPEC §3): an IELTS Speaking band, or the HSK level the
speech shows, from what the learner said (the transcript) and how it sounded (the pronunciation assessment's scores).
Like writing, always an estimate, administrators only until the pilot calibration agrees (D-249 order: after the daily
voice cap)."""

from __future__ import annotations

import pytest

from writing_coach.agent import band, band_speaking
from writing_coach.ai.base import AIResult

TRANSCRIPT = " ".join(["I usually take the bus to work because it is cheaper and I can read on the way."] * 6)
CHINESE = "我每天早上坐地铁去上班，因为地铁很方便。" * 4
PRONUNCIATION = {"pron_score": 78.0, "accuracy_score": 80.0, "fluency_score": 74.0, "prosody_score": 70.0,
                 "completeness_score": 95.0}  # fmt: skip


def answer(exam="ielts", score=6, quote="take the bus", **extra):
    return {
        "insufficient_evidence": False,
        "criteria": [{"criterion": key, "score": score, "reason": f"lý do {key}", "evidence": [quote]}
                     for key in band_speaking.CRITERIA[exam]],
        "fixes": [{"fix": "sửa", "why": "vì", "before": quote, "after": "catch the bus"}],
        **extra,
    }


class Generate:
    def __init__(self, data):
        self.data, self.calls = data, []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return AIResult(data=self.data, provider="gemini", model="gemini-3.5-flash-lite", runtime={})


def request(**overrides):
    values = {"exam": "ielts", "part": "part1", "prompt": "How do you get to work?", "transcript": TRANSCRIPT,
              "duration_seconds": 60, "pronunciation": PRONUNCIATION, "support": "vi"}  # fmt: skip
    values.update(overrides)
    return band_speaking.SpeakingBandRequest(**values)


def test_ielts_speaking_names_its_four_criteria_and_the_server_computes_the_overall():
    data = answer(score=6)
    data["criteria"][3]["score"] = 7  # pronunciation one band higher: 6.25 rounds up to 6.5
    result = band_speaking.estimate(request(), generate=Generate(data))
    assert [c["criterion"] for c in result["criteria"]] == ["fluency_coherence", "lexical_resource",
                                                            "grammatical_range_accuracy", "pronunciation"]
    assert result["overall"] == 6.5 and result["label"] == "IELTS 6.5"
    assert result["estimate"] is True and result["experimental"] is True and result["skill"] == "speaking"


def test_the_speech_rate_is_measured_by_the_server_and_handed_to_the_model():
    generate = Generate(answer())
    result = band_speaking.estimate(request(duration_seconds=60), generate=generate)
    words = band.sample_size("ielts", TRANSCRIPT)
    assert result["measures"]["rate_per_minute"] == words and result["measures"]["unit"] == "word"
    prompt = generate.calls[0]["messages"][1]["content"]
    assert f"{words} words per minute" in prompt and "pron_score 78" in prompt
    assert generate.calls[0]["capability_key"] == band.CAPABILITY  # learner text: the same route, guard and cap


def test_without_a_pronunciation_assessment_pronunciation_is_not_guessed_and_there_is_no_overall():
    generate = Generate(answer())
    result = band_speaking.estimate(request(pronunciation=None), generate=generate)
    assert [c["criterion"] for c in result["criteria"]] == ["fluency_coherence", "lexical_resource",
                                                            "grammatical_range_accuracy"]
    assert result["overall"] is None and result["label"] is None and result["missing"] == ["pronunciation"]
    criteria = generate.calls[0]["schema"]["properties"]["criteria"]["items"]["properties"]["criterion"]["enum"]
    assert "pronunciation" not in criteria  # the model is not asked for it


def test_partial_scores_without_the_overall_pronunciation_score_are_not_a_pronunciation_band():
    partial = {"accuracy_score": 80.0, "fluency_score": 74.0}  # no pron_score: not a pronunciation assessment
    result = band_speaking.estimate(request(pronunciation=partial), generate=Generate(answer()))
    assert result["missing"] == ["pronunciation"] and result["overall"] is None


def test_too_little_speech_is_not_scored_and_costs_nothing():
    generate = Generate(answer())
    for short in (request(transcript="I take the bus."), request(duration_seconds=10)):
        result = band_speaking.estimate(short, generate=generate)
        assert result["insufficient_evidence"] is True and result["overall"] is None
    assert generate.calls == []


def test_a_quote_the_learner_did_not_say_is_dropped():
    result = band_speaking.estimate(request(), generate=Generate(answer(quote="words never said")))
    assert all(c["evidence"] == [] for c in result["criteria"]) and result["fixes"] == []


def test_a_score_out_of_range_is_refused():
    with pytest.raises(band.BandUnavailable):
        band_speaking.estimate(request(), generate=Generate(answer(score=10)))


def test_hsk_speaking_labels_the_level():
    data = answer(exam="hsk", score=3, quote="坐地铁")
    result = band_speaking.estimate(request(exam="hsk", part="free", transcript=CHINESE), generate=Generate(data))
    assert result["overall"] == 3 and result["label"] == "HSK 3"
    assert [c["criterion"] for c in result["criteria"]] == list(band_speaking.CRITERIA["hsk"])


def test_the_prompt_warns_that_the_transcript_is_machine_heard():
    generate = Generate(answer())
    band_speaking.estimate(request(), generate=generate)
    assert "speech recognition" in generate.calls[0]["messages"][0]["content"]


# --- the route ----------------------------------------------------------------------------------------------------

from tests.test_agent_api import client  # noqa: E402,F401 - the agent router's test client fixture


@pytest.fixture()
def admin_route(monkeypatch):
    from tests.test_agent_api import enable
    from writing_coach.agent import api as agent_api
    from writing_coach.agent.tools import LearnerScope

    enable([])
    seen = {"admin": True, "generate": Generate(answer(score=7))}

    def guard(request):
        if not seen["admin"]:
            from fastapi import HTTPException

            raise HTTPException(403, "Platform administrator access required")
        return {"role": "admin"}

    monkeypatch.setattr(agent_api, "_band_admin", guard)
    monkeypatch.setattr(band, "_generate", seen["generate"])
    monkeypatch.setattr(band, "_mode", "admin")
    monkeypatch.setattr(agent_api.LearnerScope, "from_request_context", classmethod(lambda cls: LearnerScope("u1", "en")))
    return seen


BODY = {"exam": "ielts", "part": "part1", "prompt": "How do you get to work?", "transcript": TRANSCRIPT,
        "duration_seconds": 60, "pronunciation": PRONUNCIATION, "support": "vi"}  # fmt: skip


def test_an_administrator_gets_a_speaking_estimate(client, admin_route):  # noqa: F811
    answered = client.post("/api/agent/band/speaking", json=BODY)
    assert answered.status_code == 200 and answered.json()["overall"] == 7.0
    assert answered.headers["Cache-Control"] == "no-store"


def test_a_learner_is_refused_before_any_model_call(client, admin_route):  # noqa: F811
    admin_route["admin"] = False
    assert client.post("/api/agent/band/speaking", json=BODY).status_code == 403
    assert admin_route["generate"].calls == []


def test_switched_off_and_wrong_exam(client, admin_route, monkeypatch):  # noqa: F811
    assert client.post("/api/agent/band/speaking", json={**BODY, "exam": "hsk"}).status_code == 409
    monkeypatch.setattr(band, "_mode", "off")
    assert client.post("/api/agent/band/speaking", json=BODY).status_code == 404
    assert admin_route["generate"].calls == []


def test_a_pronunciation_score_out_of_range_is_a_422(client, admin_route):  # noqa: F811
    bad = {**BODY, "pronunciation": {**PRONUNCIATION, "pron_score": 140}}
    assert client.post("/api/agent/band/speaking", json=bad).status_code == 422
