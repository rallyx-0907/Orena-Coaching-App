"""The M0/M1 benchmark script's live mode, with the provider replaced by the scripted model (no network, no key):
answers are kept per turn, the pack can be compared on and off, unservable tools can be left out, the side-by-side
Markdown is written, and nothing is written inside the repository (A2, issue #256)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from writing_coach.agent.memory_pack import PACK_OPEN

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("agent_prompt_cache_benchmark",
                                                  ROOT / "scripts" / "agent_prompt_cache_benchmark.py")  # fmt: skip
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def scripted(bench, monkeypatch):
    """LiveProvider answers as the offline scripted model, and every request it was sent is kept."""

    sent = []

    class Scripted:
        def __init__(self, provider_id, model):
            self.models = {}

        def stream(self, req, *, should_stop=bench.never_stop):
            sent.append(req)
            language = "zh" if any("zh-CN" in m.content for m in req.messages if m.role == "system") else "en"
            model = self.models.setdefault(language, bench.OfflineModel(language))
            return model.stream(req, should_stop=should_stop)

    monkeypatch.setattr(bench, "LiveProvider", Scripted)
    return sent


def live_args(bench, tmp_path, *extra):
    return ["--live", "--approved", "--cap-usd", "5", "--price-in", "0.3", "--price-cached", "0.03",
            "--price-out", "2.5", "--layouts", "legacy", "--turns", "2", "--out", str(tmp_path / "r.json"), *extra]


def test_answers_are_kept_per_turn_and_written_side_by_side(bench, scripted, tmp_path):
    md = tmp_path / "answers.md"
    assert bench.main(live_args(bench, tmp_path, "--pack", "both", "--answers-md", str(md))) == 0
    result = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert set(result["results"]) == {"legacy/en", "legacy+pack/en", "legacy/zh", "legacy+pack/zh"}
    (run,) = result["results"]["legacy/zh"]
    assert [a["learner"] for a in run["answers"]] == bench.SCRIPTS["zh"][:2]
    assert all(a["orena"] for a in run["answers"]) and all(isinstance(a["tools"], list) for a in run["answers"])
    text = md.read_text(encoding="utf-8")
    assert "## zh, repeat 0" in text and "**legacy+pack**" in text and bench.SCRIPTS["en"][0] in text


def test_the_pack_reaches_only_the_pack_runs(bench, scripted, tmp_path):
    bench.main(live_args(bench, tmp_path, "--pack", "both"))
    with_pack = [r for r in scripted if any(m.content.startswith(PACK_OPEN) for m in r.messages)]
    without = [r for r in scripted if not any(m.content.startswith(PACK_OPEN) for m in r.messages)]
    assert with_pack and without
    zh_pack = next(m.content for r in with_pack for m in r.messages
                   if m.content.startswith(PACK_OPEN) and "加班" in m.content)  # the Chinese fixture learner
    assert '"declared_level":"HSK3"' in zh_pack


def test_left_out_tools_are_not_offered(bench, scripted, tmp_path):
    bench.main(live_args(bench, tmp_path, "--exclude-tools", "get_word_detail,search_grammar_points"))
    assert scripted and all({t.name for t in r.tools}.isdisjoint({"get_word_detail", "search_grammar_points"})
                            for r in scripted)  # fmt: skip
    assert json.loads((tmp_path / "r.json").read_text())["excluded_tools"] == ["get_word_detail", "search_grammar_points"]


def test_nothing_is_written_inside_the_repository(bench, scripted):
    with pytest.raises(SystemExit, match="outside the repository"):
        bench.main(["--answers-md", str(ROOT / "answers.md")])
