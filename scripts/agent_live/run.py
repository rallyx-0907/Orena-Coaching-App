"""The controlled live run of the agent over HTTP ([PROVIDER] gate, AGENT_SPEC.md §0 R17).

Drives the throwaway sandbox of `compose.yaml` (127.0.0.1:8013) the way the new
UI would, with the provider the legacy selection names (Gemini), and records
what only a real provider can show:

- the shape of streamed tool calls and whether usage arrives on a stream
  (UI_BACKEND_GAPS I-22; a `done` with zero tokens after a model turn means the
  provider sent no usage);
- time to the first event and to the first segment, per turn, client side;
- the real cost, from the reported usage at the published rate.

Scenarios, for the learning languages English and Chinese, interface and
support Vietnamese: S1, S5, S8, S9, S13 of AGENT_CONTRACT.md §12, two identity
questions (answered without a model) and three free questions, each model turn
repeated `--repeat` times.

It will not run without `--approved` and a `--cap-usd`, and never against
another port than the live sandbox's. Before each turn it adds the turn's worst
case to what was spent (measured usage when known, the worst case when not) and
stops when that would pass the cap. Standard library only; results go to a JSON
file outside the repository.

    python scripts/agent_live/run.py --cap-usd 2.00 --approved --gemini-env <path to a .env holding GEMINI_*>
    python scripts/agent_live/run.py --plan          # the plan and its worst case, nothing sent

The script owns the sandbox: it starts compose.yaml's own project (orena-agent-live,
on :8013, or :8015 when :8013 is taken), runs, and takes it down when it ends - done,
failed, stopped at the cost cap, interrupted (Ctrl+C) or terminated - so no lane waits
on a forgotten container. Only GEMINI_* is read from the env file; nothing is printed.

Before the sandbox it takes the Gemini text quota group's lock (lock.py, README.md) and
releases it in the same unwinding, so lanes queue for the provider instead of colliding.
"""

from __future__ import annotations

import argparse
import atexit
import http.cookiejar
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lock as live_lock  # noqa: E402 - this folder's own module, next to this script

ROOT = Path(__file__).resolve().parents[2]
LOCK_NOTES: list[str] = []  # orphaned locks removed, waits: reported in the result
CONTRACT = ROOT / "docs/project/AGENT_CONTRACT.md"
SANDBOX_PORT = 8013
SANDBOX_PORTS = {8013, 8015}  # 8015 when another lane holds 8013
SHARED_PORTS = {8000, 8010, 8011, 8012}

# Published paid-tier rates, USD per 1M tokens in and out (ai.google.dev pricing, read 2026-09-28). The cap is
# counted at these even on the free tier, where nothing is billed.
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.7-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-2.5-flash": (0.30, 2.50),
}
MODEL = "gemini-3.5-flash-lite"  # the one model of the run, fixed from its start (--model / --probe-models)
PRICE_IN, PRICE_OUT = PRICES[MODEL]
# A turn's worst case under AgentLimits: 5 model rounds, each at most ~16k tokens in and 1024 out.
WORST_ROUNDS, WORST_IN, WORST_OUT = 5, 16_000, 1024
# One essay review for S9 per learning language (one model call, generous bound).
WORST_SETUP_USD = 0.02
TURN_GAP_SECONDS = 5.5  # 12 turns a minute per learner (AgentLimits)

LOCALE = {"interface": "vi", "support": "vi"}
TARGETS = {
    "en": {
        "language": "en",
        "word": "serendipity",
        "words": ["serendipity", "opportunity", "reluctant"],
        "essay": "Yesterday I go to the market with my friend. We buyed many fruits and we was very happy "
        "because the weather is good. I think markets is more interesting than supermarkets.",
    },
    "zh-CN": {
        "language": "zh",
        "word": "我",
        "words": ["机会", "学习", "朋友"],
        "essay": "昨天我和朋友去了市场。我们买了很多水果，我们很高兴因为天气很好。我觉得市场比超市更有意思的。",
    },
}
ALL_ACTIONS = [
    "navigate", "play_model", "play_user", "say_again", "compare_with_model", "save_word",
    "add_word_to_collection", "start_review", "start_targeted_drill", "unsave_word",
]  # fmt: skip
ALL_INTENTS = [
    "home", "orena.home", "vocabulary.my_language", "vocabulary.review_due", "vocabulary.word",
    "writing.review", "writing.revision", "grammar.point",
]  # fmt: skip


# What a reviewer checks by eye, flagged on every answer (human review 2026-09-28).
DONE_CLAIMS = re.compile(
    r"(?i)\b(?:mình|orena)\s+(?:vừa\s+)?đã\s+(?:lưu|thêm|xóa|mở)|\bđã\s+được\s+(?:lưu|thêm|xóa|mở)"
    r"|\b(?:has been|is now|I've|I have)\s+(?:saved|added|removed|opened)\b|已(?:经)?(?:帮你)?(?:保存|添加|删除)"
)
PRAISE = re.compile(r"(?i)rất tốt|tuyệt vời|xuất sắc|great job|well done|excellent|很好|非常好|太棒")
# Orena speaking of itself as "tôi" - not "tôi" inside a screen name ("Thư viện của tôi") or a word's gloss.
SELF_AS_TOI = re.compile(r"(?i)\btôi (không|chỉ|có thể|sẽ|đã|rất|xin|cần|muốn|hiểu|thấy)\b")
ENGLISH_SCREEN = re.compile(r"\b(Your words|My Library|My words|Practice Hub|Discover|Today)\b")


def quality_flags(text: str, has_action: bool) -> list[str]:
    flags = []
    if DONE_CLAIMS.search(text):
        flags.append("action described as done" if has_action else "claims it acted")
    if PRAISE.search(text):
        flags.append("general praise")
    if SELF_AS_TOI.search(text):
        flags.append("tôi instead of mình")
    if ENGLISH_SCREEN.search(text):
        flags.append("English screen name")
    return flags


def price(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * PRICE_IN + tokens_out * PRICE_OUT) / 1_000_000


WORST_TURN_USD = WORST_ROUNDS * price(WORST_IN, WORST_OUT)


ROUND_WORST_USD = price(WORST_IN, WORST_OUT)
# A turn whose first round the provider refused ("high demand", 503) is sent again with the same model, at most three
# times, waiting longer each time; still refused, the run stops (human direction 2026-09-28).
RETRY_DELAYS = (5, 15, 45)


def use_model(name: str) -> None:
    """The run's one model, and the rates its cap is counted at."""

    global MODEL, PRICE_IN, PRICE_OUT, WORST_TURN_USD, ROUND_WORST_USD
    if name not in PRICES:
        sys.exit(f"refusing: no published rate for {name} here (PRICES)")
    MODEL = name
    PRICE_IN, PRICE_OUT = PRICES[name]
    ROUND_WORST_USD = price(WORST_IN, WORST_OUT)
    WORST_TURN_USD = WORST_ROUNDS * ROUND_WORST_USD


def provider_refused(summary: dict) -> bool:
    """The turn ended in provider_unavailable (a 503 "high demand", a spent quota): sent again, same model."""

    return (summary.get("error") or {}).get("class") == "provider_unavailable"


class RoundLedger:
    """What each agent round cost, from the sandbox's own telemetry (GET /api/admin/ai/operations): one event per
    provider round, with its outcome and usage. A turn that failed shows the client nothing of its earlier rounds
    (a turn about a note holds its whole answer), so its cost is read here, never guessed: a round with usage at
    the model's rate, a round without it (a failure, or usage unreported) at one round's worst case. When the
    telemetry cannot be read, the whole turn's worst case is counted."""

    def __init__(self, client: Client) -> None:
        self.client = client
        self.seen: set[tuple] = set()

    def _rounds(self) -> list[dict] | None:
        status, body = self.client.call("GET", "/api/admin/ai/operations?limit=200")
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("recent"), list):
            return None
        return [e for e in body["recent"] if isinstance(e, dict) and e.get("capability") == "agent_turn_fast"]

    @staticmethod
    def _key(event: dict) -> tuple:
        return event.get("created_at"), event.get("latency_ms"), event.get("outcome")

    def mark(self) -> None:
        """Everything recorded so far is accounted for."""

        rounds = self._rounds()
        if rounds is not None:
            self.seen |= {self._key(e) for e in rounds}

    def new_cost(self) -> float | None:
        """The cost of the rounds recorded since the last look, or None when the telemetry cannot be read."""

        rounds = self._rounds()
        if rounds is None:
            return None
        fresh = [e for e in rounds if self._key(e) not in self.seen]
        self.seen |= {self._key(e) for e in fresh}
        cost = 0.0
        for event in fresh:
            usage = event.get("usage") or {}
            tokens_in, tokens_out = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if event.get("outcome") == "success" and isinstance(tokens_in, int) and isinstance(tokens_out, int):
                cost += price(tokens_in, tokens_out)
            else:
                cost += ROUND_WORST_USD
        return cost


PROBES: dict[str, int] = {}  # model -> HTTP status of its one-token probe


def probe_models(names: list[str], env: dict[str, str]) -> str | None:
    """The first of `names` that answers a one-token request (its quota is not spent), or None. The key goes in
    a header; only the status of each is kept."""

    key = env.get("GEMINI_API_KEY", "")
    body = json.dumps({"contents": [{"parts": [{"text": "ok"}]}], "generationConfig": {"maxOutputTokens": 8}}).encode()
    for name in names:
        request = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent", data=body, method="POST"
        )
        request.add_header("x-goog-api-key", key)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                PROBES[name] = response.status
        except urllib.error.HTTPError as error:
            PROBES[name] = error.code
        except (urllib.error.URLError, OSError):
            PROBES[name] = 0
        print(f"probe {name}: {PROBES[name]}")
        if PROBES[name] == 200:
            return name
    return None


@dataclass
class Scenario:
    name: str
    model: bool  # False: answered by rule, costs nothing
    message: str | None
    context: dict
    actions: list[str] = field(default_factory=list)
    intents: list[str] = field(default_factory=list)
    trigger: str = "message"
    canonical: str | None = None


def scenarios(target: str, essay_id: str | None) -> list[Scenario]:
    t = TARGETS[target]
    word = {"type": "word", "text": t["word"], "lang": target}
    return [
        Scenario("S1", True, "Màn này dùng để làm gì?", {"surface": "vocabulary.my_language", "activity_type": "app_help"},
                 canonical="S1"),
        Scenario("S5", True, "Lưu từ này.", {"surface": "vocabulary.my_language", "selected_item": word},
                 actions=["save_word"], canonical="S5"),
        Scenario("S8", True, "Cho tôi xem tiến độ của user khác.", {"surface": "home"}, canonical="S8"),
        Scenario("S9", True, "Bài này tôi hay sai chỗ nào?", {"surface": "writing.review", "essay_id": essay_id},
                 actions=["navigate"], intents=["writing.revision"], canonical="S9"),
        Scenario("S13", True, None, {"surface": "orena.home"}, actions=["start_review", "navigate"],
                 intents=["vocabulary.review_due"], trigger="open", canonical="S13"),
        Scenario("identity.who", False, "Bạn là ai?", {"surface": "home"}),
        Scenario("identity.model", False, "Bạn dùng mô hình gì?", {"surface": "home"}),
        Scenario("free.today", True, "Hôm nay tôi nên học gì?", {"surface": "home"}, ALL_ACTIONS, ALL_INTENTS),
        Scenario("free.word", True, f"Từ {t['words'][0]} nghĩa là gì và dùng thế nào?",
                 {"surface": "vocabulary.my_language"}, ALL_ACTIONS, ALL_INTENTS),
        Scenario("free.mistakes", True, "Khi viết tôi hay mắc lỗi gì nhất?", {"surface": "home"}, ALL_ACTIONS, ALL_INTENTS),
    ]  # fmt: skip


def canonical(name: str) -> list[str]:
    text = CONTRACT.read_text(encoding="utf-8")
    block = re.search(rf"`{name} [^`]*`[^\n]*\n\n```text\n(.*?)```", text, re.S).group(1)
    flow = " ".join(line.split("#")[0] for line in block.splitlines())
    steps = [step.strip().split("{")[0].rstrip("…").strip() for step in flow.split("→")]
    return [s for s in steps if s and s != "segment_delta"]


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 90) -> tuple[int, dict | str]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read().decode("utf-8", "replace"), exc.code
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw

    def turn(self, body: dict, timeout: float = 90) -> dict:
        """Send one turn; read its SSE stream as it arrives, timing each first."""

        request = urllib.request.Request(self.base + "/api/agent/turn", data=json.dumps(body).encode(), method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "text/event-stream")
        started = time.perf_counter()
        out: dict = {"status": None, "events": [], "t_first_event": None, "t_first_segment": None}
        try:
            response = self.opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            out["status"] = exc.code
            out["retry_after"] = exc.headers.get("Retry-After")
            out["body"] = exc.read().decode("utf-8", "replace")[:300]
            return out
        out["status"] = response.status
        name, data = None, []
        with response:
            for raw in response:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: "):
                    data.append(line[6:])
                elif not line and name:
                    now = time.perf_counter() - started
                    out["t_first_event"] = out["t_first_event"] or round(now, 3)
                    if name in ("segment_delta", "segment_end") and out["t_first_segment"] is None:
                        out["t_first_segment"] = round(now, 3)
                    out["events"].append({"name": name, "data": json.loads("\n".join(data))})
                    name, data = None, []
        out["t_done"] = round(time.perf_counter() - started, 3)
        return out


def turn_body(version: int, target: str, scenario: Scenario) -> dict:
    context = {k: v for k, v in scenario.context.items() if v is not None}
    context["locale"] = {**LOCALE, "target": target, "content": target}
    body = {
        "contract_version": version,
        "trigger": scenario.trigger,
        "client": {"ui_version": "agent-live-run", "supported_actions": scenario.actions, "supported_intents": scenario.intents},
        "context": context,
    }
    if scenario.message is not None:
        body["message"] = scenario.message
    return body


def summarize(result: dict) -> dict:
    names = [e["name"] for e in result["events"]]
    done = next((e["data"] for e in result["events"] if e["name"] == "done"), None)
    usage = (done or {}).get("usage") or {}
    tokens_in, tokens_out = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
    error = next((e["data"] for e in result["events"] if e["name"] == "error"), None)
    segments = [e["data"] for e in result["events"] if e["name"] == "segment_end"]
    # A reference segment (a target-language word to hear) is its own segment, not part of the sentence.
    text = "".join(s.get("text", "") for s in segments if s.get("voice_style") != "reference")
    return {
        "references": [s.get("text") for s in segments if s.get("voice_style") == "reference"],
        "sequence": [n for n in names if n != "segment_delta"],
        "deltas": names.count("segment_delta"),
        "tools": [e["data"].get("name") for e in result["events"] if e["name"] == "tool_call"],  # §4 { name, label }
        "actions": [e["data"] for e in result["events"] if e["name"] == "action"],
        "suggestions": [e["data"].get("intent") for e in result["events"] if e["name"] == "suggestion"],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "usage_reported": bool(tokens_in or tokens_out),
        "error": error,
        "text": text[:400],
        "flags": quality_flags(text, any(e["name"] == "action" for e in result["events"])),
    }


def plan() -> dict:
    per_target = sum(1 for s in scenarios("en", "1") if s.model)
    return {"model_turns_per_target_per_repeat": per_target, "worst_turn_usd": round(WORST_TURN_USD, 4)}


# --- multi-turn flows: a session, and the coach notes the device would keep ------------------

VI = {"interface": "vi", "support": "vi"}
SAVE = {"actions": ["navigate", "save_word"]}  # a client that can run save_word
ARTICLE_EN = (
    "Automation is often described as a threat to jobs, but the evidence is more complicated than the headlines "
    "suggest, and the debate has been conducted mostly in slogans. Economists have long noticed that new machines destroy some tasks while creating others, and the net "
    "effect depends on how quickly workers can move from the old tasks to the new ones. Every earlier wave of "
    "technology, from the loom to the spreadsheet, was feared in the same way before its benefits were understood. "
    "The author argues that the loudest warnings come from people who confuse tasks with occupations. A bank "
    "teller's job changed when cash machines arrived, yet the number of tellers grew for two decades because "
    "branches became cheaper to open and banks opened more of them. The machine took over the counting; the people "
    "took over the advice. The same pattern, the author says, appears in warehouses, in accounting firms and in "
    "radiology departments, where software reads the scan and the doctor spends the time saved with the patient. "
    "The strongest claim in the essay is that retraining programmes are a waste of public money. The author offers "
    "a single study of one factory closure in Ohio and concludes from it that no retraining scheme anywhere has "
    "ever worked. Nothing else is cited, and the essay does not say how the workers in that study were chosen. "
    "Finally, the author proposes wage insurance instead: a payment that tops up the earnings of workers who "
    "accept a lower-paid job after being laid off, so that they keep working while they learn new skills."
)
FLOWS: dict[str, list[tuple[str, str, dict, str | None, dict]]] = {
    # name: [(target, step, locale, message, context extras)]
    "address": [
        ("zh-CN", "default", VI, "Giải thích giúp mình từ 学习 nhé.", {}),
        ("zh-CN", "request", VI, "Từ giờ Orena xưng chị, gọi mình là em nhé.", {}),
        ("zh-CN", "after", VI, "Chị giải thích từ 机会 cho em với.", {}),
    ],
    # "ask once" for a pair that is not kinship: used over several turns, asked once, declined, not asked again
    "decline": [
        ("zh-CN", "pair-1", VI, "Tớ hỏi cậu: 朋友 nghĩa là gì?", {}),
        ("zh-CN", "pair-2", VI, "Cậu ơi, tớ hỏi tiếp: 学生 là gì?", {}),
        ("zh-CN", "pair-3", VI, "Cảm ơn cậu. Tớ hỏi thêm: 老师 nghĩa là gì?", {}),
        ("zh-CN", "says-no", VI, "Thôi, cứ xưng mình và gọi bạn như cũ là được.", {}),
        ("zh-CN", "later", VI, "Tớ hỏi cậu tiếp: 学习 là gì?", {"new_session": True}),
    ],
    # Vietnamese kinship answered in kind at once, a change of it, and someone else ("anh tôi") changing nothing
    "kinship": [
        ("zh-CN", "anh", VI, "Anh muốn hỏi từ 学习 nghĩa là gì?", {}),
        ("zh-CN", "chi-em", VI, "Em hỏi chị: 朋友 là gì ạ?", {}),
        ("zh-CN", "someone-else", VI, "Anh tôi hỏi từ 老师 nghĩa là gì?", {}),
        ("zh-CN", "a-language", VI, "Tiếng Anh khó quá", {}),
    ],
    # a pair already kept, changed again: back to the default
    "rechange": [
        ("zh-CN", "set", VI, "Từ giờ Orena xưng chị, gọi mình là em nhé.", {}),
        ("zh-CN", "back", VI, "Thôi, quay về xưng mình và gọi bạn nhé.", {}),
        ("zh-CN", "after", VI, "Giải thích từ 朋友 giúp mình.", {}),
    ],
    "claims": [
        ("zh-CN", "vi", VI, "Lưu từ này giúp mình.", {"word": "我"}),
        ("en", "en", {"interface": "en", "support": "en"}, "Save this word for me.", {"word": "meticulous"}),
        ("en", "zh", {"interface": "zh-CN", "support": "zh-CN"}, "帮我保存这个词。", {"word": "meticulous"}),
    ],
    "history": [("zh-CN", "zh-writing", VI, "Khi viết tôi hay mắc lỗi gì nhất?", {})],
    # Slice 3: the opening on the snapshot, weaknesses and next steps from the backend, SRS in the learner's words
    "coaching": [
        ("zh-CN", "opening", VI, None, {"trigger": "open", "surface": "orena.home"}),
        ("zh-CN", "weak", VI, "Mình đang yếu ở đâu nhất?", {"surface": "home"}),
        ("zh-CN", "next", VI, "Giờ mình nên học gì tiếp?", {"surface": "home"}),
        ("zh-CN", "srs", VI, "Từ 朋友 của mình đang ở trạng thái nào?", {}),
    ],
    # coach notes, layer 3: kept, corrected (replaced), forgotten (removed), each by the learner's own words
    "notes": [
        ("zh-CN", "remember", VI, "Nhớ giúp mình: mình thích ví dụ thật ngắn.", {}),
        ("zh-CN", "correct", VI, "À không, ví dụ dài hơn một chút thì mình dễ hiểu hơn.", {}),
        ("zh-CN", "forget", VI, "Quên ghi chú về ví dụ đó đi.", {}),
        ("zh-CN", "after", VI, "Cho mình một ví dụ với 朋友.", {}),
    ],
    # Conversation kernel slice 2 (agent/pending.py): an offer survives a question in between, is run once on the
    # learner's yes, dropped on a no, and not run twice. Each flow is one session; judged by `pending_verdict`.
    "pending-save": [
        ("en", "ask", VI, "abate nghĩa là gì? Mình có nên lưu từ này không?", SAVE),
        ("en", "example", VI, "cho ví dụ nữa", SAVE),
        ("en", "save", VI, "ừ lưu đi", SAVE),
        ("en", "again", VI, "ok lưu", SAVE),
    ],
    "pending-cancel": [
        ("en", "ask", VI, "abate nghĩa là gì? Mình có nên lưu từ này không?", SAVE),
        ("en", "no", VI, "không", SAVE),
        ("en", "after", VI, "từ đó có formal không?", SAVE),
    ],
    "pending-between": [
        ("en", "ask", VI, "abate nghĩa là gì? Mình có nên lưu từ này không?", SAVE),
        ("en", "between", VI, "từ đó có formal không?", SAVE),
        ("en", "save", VI, "thôi lưu đi", SAVE),
    ],
    # Conversation kernel slices 3-4: references resolve from the conversation, a pasted text is asked about
    # again without pasting it, and a change of learning language keeps the conversation. `conversation_verdict`.
    "convo-refs": [
        ("en", "ask", VI, "mitigate nghĩa là gì?", SAVE),
        ("en", "example", VI, "cho ví dụ kiểu điện tử", SAVE),
        ("en", "formal", VI, "formal không?", SAVE),
        ("en", "save", VI, "từ đó lưu đi", SAVE),
    ],
    "convo-paste": [
        ("en", "ask", VI, ARTICLE_EN + "\n\nTóm lại tác giả phản đối điều gì?", {}),
        ("en", "third", VI, "đoạn thứ 3 lập luận có yếu không?", {}),
        ("en", "first", VI, "còn đoạn đầu thì nói gì?", {}),
    ],
    "convo-lang": [
        ("en", "ask", VI, "mitigate nghĩa là gì?", {}),
        ("zh-CN", "switch", VI, "từ đó dịch sang tiếng Trung là gì?", {}),
    ],
    "screens": [
        ("zh-CN", "vi", VI, "Màn này dùng để làm gì?", {"surface": "vocabulary.my_language"}),
        ("en", "zh", {"interface": "zh-CN", "support": "zh-CN"}, "这个页面是做什么的？", {"surface": "vocabulary.my_language"}),
    ],
}


ESSAY_FLOWS = frozenset({"history"})  # the flows that read the essay review; the rest skip that provider call


def run_flows(client: Client, version: int, names: list[str], cap: float, gap: float, spent: float) -> tuple[list[dict], float]:
    rows: list[dict] = []
    ledger = RoundLedger(client)
    ledger.mark()  # the setup's calls are counted by their own bound
    for name in names:
        session_id, notes = None, {}
        for target, step, locale, message, extra in FLOWS[name]:
            if spent + WORST_TURN_USD > cap:
                print(f"cap ${cap:.2f} would be passed; stopping at ${spent:.4f}")
                return rows, spent
            client.call("POST", "/api/platform/language", {"language": TARGETS[target]["language"]})
            if extra.get("new_session"):
                session_id = None
            context: dict = {"surface": extra.get("surface", "vocabulary.my_language"),
                             "locale": {**locale, "target": target, "content": target}}  # fmt: skip
            actions, intents = ["navigate"], ["vocabulary.review_due", "writing.revision"]
            if extra.get("word"):
                context["selected_item"] = {"type": "word", "text": extra["word"], "lang": target}
                actions = ["save_word", "add_word_to_collection"]
            actions = extra.get("actions", actions)
            if context["surface"] in {"home", "orena.home"}:
                actions, intents = ALL_ACTIONS, ALL_INTENTS
            body = {
                "contract_version": version,
                "trigger": extra.get("trigger", "message"),
                "client": {"ui_version": "agent-live-run", "supported_actions": actions, "supported_intents": intents},
                "context": context,
                # §5.6 (v5): the address note travels as context.address, never in coach_notes
                "coach_notes": [n for n in notes.values() if n.get("kind") != "address"],
            }
            kept_address = next((n["address"] for n in notes.values() if n.get("kind") == "address"), None)
            if kept_address is not None:
                context["address"] = kept_address
            if message is not None:
                body["message"] = message
            if session_id:
                body["session_id"] = session_id
            refused = 0
            result: dict = {}
            summary: dict = {}
            while True:
                if spent + WORST_TURN_USD > cap:  # every send, a retry too, fits the cap at its worst
                    print(f"cap ${cap:.2f} would be passed; stopping at ${spent:.4f}")
                    if refused:  # the refused attempt is kept in the result, not lost
                        rows.append(_row(name, step, target, locale, message, result, summary, [], refused))
                    return rows, spent
                result = client.turn(body)
                while result["status"] == 429:  # this server's own per-learner limit (§2.1): wait, send again
                    time.sleep(int(result.get("retry_after") or 1))
                    result = client.turn(body)
                summary = summarize(result) if result["status"] == 200 else {"body": result.get("body")}
                spent += turn_cost(summary, ledger)
                if not provider_refused(summary):
                    break
                if refused == len(RETRY_DELAYS):
                    print(f"stopping: the provider refused {name}/{step} {refused + 1} times with {MODEL} "
                          f"(see provider_errors)")  # fmt: skip
                    rows.append(_row(name, step, target, locale, message, result, summary, [], refused + 1))
                    return rows, spent
                delay = RETRY_DELAYS[refused]
                refused += 1
                print(f"{name:8} {step:12} the provider refused the first round; retry {refused}/{len(RETRY_DELAYS)} "
                      f"in {delay} s, same model ({MODEL})")  # fmt: skip
                time.sleep(delay)
            for event in result.get("events", []):
                if event["name"] == "session":
                    session_id = event["data"]["session_id"]
                if event["name"] == "memory_update" and event["data"]["op"] == "upsert":
                    notes[event["data"]["note"]["id"]] = event["data"]["note"]
                if event["name"] == "memory_update" and event["data"]["op"] == "remove":
                    notes.pop(event["data"]["note"]["id"], None)  # the device drops it, as it would
            memory = [e["data"] for e in result.get("events", []) if e["name"] == "memory_update"]
            rows.append(_row(name, step, target, locale, message, result, summary, memory, refused + 1))
            print(f"{name:8} {step:12} {target:6} {result['status']} tools={summary.get('tools')} "
                  f"memory={[(m['op'], m['note'].get('text') or m['note'].get('id')) for m in memory]} "
                  f"flags={summary.get('flags')} segment={result.get('t_first_segment')}s "
                  f"spent=${spent:.4f}")  # fmt: skip
            time.sleep(gap)
    return rows, spent


def turn_cost(summary: dict, ledger: RoundLedger) -> float:
    """A turn's cost, always from its rounds as the sandbox's telemetry recorded them - never from `done.usage`,
    which sums only the rounds that reported usage (a round that reported none adds nothing there; review
    2026-09-28) -, or its whole worst case when the telemetry cannot be read."""

    measured = ledger.new_cost()
    return WORST_TURN_USD if measured is None else measured


def _row(name, step, target, locale, message, result, summary, memory, attempts) -> dict:  # noqa: ANN001
    return {"flow": name, "step": step, "target": target, "locale": locale, "message": message,
            "status": result["status"], "memory_update": memory, "attempts": attempts,
            "t_first_event": result.get("t_first_event"), "t_first_segment": result.get("t_first_segment"),
            "t_done": result.get("t_done"), **summary}  # fmt: skip


def notes_verdict(rows: list[dict]) -> dict:
    """The notes flow, judged from what the device received: a note kept, the same note replaced, then removed, and
    a plain turn after. `pass` only when all four hold."""

    steps = {row["step"]: row for row in rows if row.get("flow") == "notes"}
    verdict: dict = {"complete": all(s in steps for s in ("remember", "correct", "forget", "after"))}

    def ops(step: str) -> list[tuple[str, str]]:
        return [(m["op"], m["note"].get("id", "")) for m in (steps.get(step) or {}).get("memory_update", [])
                if not str(m["note"].get("id", "")).startswith("address-")]  # fmt: skip

    kept = [note_id for op, note_id in ops("remember") if op == "upsert"]
    note_id = kept[0] if len(kept) == 1 else None
    verdict["remember"] = note_id is not None
    corrected = ops("correct")
    verdict["correct"] = note_id is not None and corrected == [("upsert", note_id)]
    verdict["correct_detail"] = "replaced" if verdict["correct"] else ("new note" if corrected else "unchanged")
    verdict["forget"] = note_id is not None and ops("forget") == [("remove", note_id)]
    after = steps.get("after") or {}
    verdict["after"] = bool(after) and not after.get("error") and not ops("after")
    verdict["pass"] = all(verdict[k] for k in ("complete", "remember", "correct", "forget", "after"))
    return verdict


def pending_verdict(rows: list[dict]) -> dict:
    """The pending-interaction flows, judged from the actions the device received: `pass` per flow only when the
    save was offered, an interjected question ran nothing, a yes ran save_word(abate) exactly once and with `open`,
    a second yes ran nothing, and a no ran nothing."""

    def acts(flow: str, step: str) -> list[dict]:
        row = next((r for r in rows if r.get("flow") == flow and r.get("step") == step), None)
        return [a for a in (row or {}).get("actions", [])]

    def saves(items: list[dict]) -> list[dict]:
        return [a for a in items if a.get("type") == "save_word" and a.get("payload", {}).get("text", "").lower() == "abate"]

    def ran(items: list[dict]) -> list[dict]:
        return [a for a in saves(items) if a.get("open") is True]

    verdict: dict = {}
    if any(r.get("flow") == "pending-save" for r in rows):
        verdict["pending-save"] = {
            "offered": bool(saves(acts("pending-save", "ask"))) and not ran(acts("pending-save", "ask")),
            "interjection_ran_nothing": not ran(acts("pending-save", "example")),
            "save_ran_once": len(ran(acts("pending-save", "save"))) == 1,
            "repeat_ran_nothing": not ran(acts("pending-save", "again")),
        }
    if any(r.get("flow") == "pending-cancel" for r in rows):
        verdict["pending-cancel"] = {
            "offered": bool(saves(acts("pending-cancel", "ask"))),
            "no_ran_nothing": not ran(acts("pending-cancel", "no")) and not ran(acts("pending-cancel", "after")),
        }
    if any(r.get("flow") == "pending-between" for r in rows):
        verdict["pending-between"] = {
            "offered": bool(saves(acts("pending-between", "ask"))),
            "question_ran_nothing": not ran(acts("pending-between", "between")),
            "late_yes_ran_once": len(ran(acts("pending-between", "save"))) == 1,
        }
    for checks in verdict.values():
        checks["pass"] = all(checks.values())
    return verdict


def conversation_verdict(rows: list[dict]) -> dict:
    """The conversation flows, judged from the answers the device received: references resolved to the word named
    earlier (an action or its text names it), a pasted text answered about without being pasted again, and a
    language change that kept the topic. Keyword checks only; the answers are in the result for reading."""

    def row(flow: str, step: str) -> dict:
        return next((r for r in rows if r.get("flow") == flow and r.get("step") == step), {})

    def says(r: dict, *words: str) -> bool:
        text = (r.get("text") or "").casefold()
        return any(w.casefold() in text for w in words)

    asks_again = ("dán", "paste", "gửi lại", "cung cấp", "nội dung", "bạn muốn hỏi về", "đoạn nào")
    verdict: dict = {}
    if any(r.get("flow") == "convo-refs" for r in rows):
        saved = [a for a in row("convo-refs", "save").get("actions", []) if a.get("type") == "save_word"]
        verdict["convo-refs"] = {
            "example_about_the_word": says(row("convo-refs", "example"), "mitigate"),
            "formal_about_the_word": says(row("convo-refs", "formal"), "mitigate"),
            "saved_mitigate_once": len(saved) == 1 and saved[0]["payload"].get("text", "").lower() == "mitigate"
            and saved[0].get("open") is True,
        }
    if any(r.get("flow") == "convo-paste" for r in rows):
        third, first = row("convo-paste", "third"), row("convo-paste", "first")
        verdict["convo-paste"] = {
            "third_answered_from_the_text": says(third, "Ohio", "một nhà máy", "một nghiên cứu", "đào tạo lại")
            and not says(third, *asks_again[:4]),
            "first_answered_from_the_text": says(first, "tự động hóa", "automation", "công việc", "nhiệm vụ")
            and not says(first, *asks_again[:4]),
        }
    if any(r.get("flow") == "convo-lang" for r in rows):
        verdict["convo-lang"] = {"kept_the_word_after_the_switch": says(row("convo-lang", "switch"), "缓解", "减轻", "减缓", "mitigate")}
    for checks in verdict.values():
        checks["pass"] = all(checks.values())
    return verdict


def notes_log(lines: list[str]) -> list[dict]:
    """The server's "agent notes:" lines, one entry per turn that changed or cancelled a note: whether the model
    was asked again, and the outcome (turn.py logs counts only)."""

    turns: list[dict] = []
    asked = False
    for line in lines:
        if "asked again" in line and "unchanged" not in line:
            asked = True
        elif "agent notes: changed" in line or "unchanged after asking again" in line:
            turns.append({"asked_again": asked, "changed": "unchanged" not in line})
            asked = False
        elif "failed before a verdict" in line:  # the attempt failed (it is sent again): its own entry, no carry-over
            turns.append({"asked_again": asked, "changed": None, "failed": True})
            asked = False
    return turns


# --- the sandbox this script owns -------------------------------------------------------------

COMPOSE_FILE = ROOT / "scripts/agent_live/compose.yaml"
PROJECT = "orena-agent-live"
GEMINI_KEYS = ("GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_MODELS")


def _port_free(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _compose_env(gemini_env: str | None, port: int) -> dict[str, str]:
    """This process's environment, with GEMINI_* only from the named file (never printed)."""

    env = {k: v for k, v in os.environ.items() if not k.startswith(("COMPOSE_", "GEMINI_") if gemini_env else "COMPOSE_")}
    if gemini_env:
        for line in Path(gemini_env).read_text(encoding="utf-8", errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in GEMINI_KEYS and value.strip().strip("'\""):
                env[key.strip()] = value.strip().strip("'\"")
    env["AGENT_LIVE_PORT"] = str(port)
    env["GEMINI_MODELS"] = MODEL  # the sandbox offers only the run's one model: nothing to switch to on a failure
    return env


class Sandbox:
    """compose.yaml's own project, up for the run and down at its end, whatever the end is."""

    def __init__(self, env: dict[str, str]) -> None:
        self.env = env
        self.started = False
        self.removed = False

    def _compose(self, *args: str, check: bool = True) -> int:
        command = ["docker", "compose", "-p", PROJECT, "-f", str(COMPOSE_FILE), *args]
        return subprocess.run(command, env=self.env, check=check).returncode

    def up(self, base_url: str, wait_seconds: float = 120) -> None:
        self.started = True  # from here on, down() must run, even if up fails halfway
        atexit.register(self.down)
        self._compose("up", "-d")
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(base_url + "/api/readiness", timeout=3) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(1)
        raise RuntimeError("the sandbox did not become ready")

    def provider_errors(self) -> list[str]:
        """What the provider answered when a round failed, from the web log (the learner only sees
        provider_unavailable). Only those lines, anything key-like redacted; read before the sandbox goes."""

        if not self.started or self.removed:
            return []
        command = ["docker", "compose", "-p", PROJECT, "-f", str(COMPOSE_FILE), "logs", "--no-color", "web"]
        try:
            log = subprocess.run(command, env=self.env, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", check=False, timeout=60).stdout  # fmt: skip
        except (OSError, subprocess.TimeoutExpired):
            return ["the web log could not be read"]
        lines = [line for line in log.splitlines()
                 if "agent provider round" in line or "agent turn failed" in line or "agent notes:" in line]  # fmt: skip
        return [re.sub(r"(?i)(key=|bearer\s+|AIza)[\w\-.]+", r"\1<redacted>", line)[-600:] for line in lines]

    def down(self) -> None:
        if self.started and not self.removed:
            self.removed = True
            print("taking the sandbox down")
            self._compose("down", "--remove-orphans", check=False)


def _stop_on_signal(signum, frame):  # noqa: ANN001 - signal handler
    raise SystemExit(128 + signum)  # unwinds through finally: the sandbox comes down


def main() -> int:
    args = _arguments()
    use_model(args.model)
    turns = plan()["model_turns_per_target_per_repeat"] * args.repeat * len([t for t in args.targets.split(",") if t])
    print(f"plan: {turns} model turns (scenarios); worst case ${turns * WORST_TURN_USD + 2 * WORST_SETUP_USD:.2f}")
    if args.plan:
        return 0
    if not args.approved or args.cap_usd is None or args.cap_usd <= 0:
        sys.exit("refusing: needs --approved and the approved --cap-usd")
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _stop_on_signal)
    # Lanes using the same quota queue on its lock before any sandbox or provider call (lock.py, README.md).
    try:
        lock = live_lock.acquire(_lane(), args.cap_usd, group="gemini-text").start_heartbeat()  # its one group
    except live_lock.LockTimeout as error:
        print(f"stopping: {error}")
        return 3
    LOCK_NOTES.extend(lock.notes)
    atexit.register(lock.release)
    try:
        # Chosen under the lock: a lane that held it may have just freed :8013.
        port = next((p for p in sorted(SANDBOX_PORTS) if _port_free(p)), None)
        if port is None:
            print(f"refusing: {sorted(SANDBOX_PORTS)} are all taken")
            return 1
        if args.probe_models:
            chosen = probe_models([m for m in args.probe_models.split(",") if m], _compose_env(args.gemini_env, port))
            if chosen is None:
                print(f"stopping: no model answered ({PROBES})")
                return 1
            use_model(chosen)
        print(f"model: {MODEL} (fixed for the whole run)")
        sandbox = Sandbox(_compose_env(args.gemini_env, port))
        # A run killed outright (TerminateProcess, kill -9) runs no finally: its leftovers of this project go first.
        sandbox._compose("down", "--remove-orphans", check=False)
        try:
            base_url = f"http://127.0.0.1:{port}"
            sandbox.up(base_url)
            return drive(args, base_url)
        except subprocess.CalledProcessError:
            print("the sandbox did not start (is GEMINI_API_KEY set?)")
            return 1
        finally:
            _add_provider_errors(args.out, sandbox.provider_errors())
            sandbox.down()
    finally:
        lock.release()  # after the sandbox is down, in the same unwinding


def _add_provider_errors(out: str, lines: list[str]) -> None:
    """The provider's own error lines and the note nudges, from the web log, into the result."""

    errors = [line for line in lines if "agent notes:" not in line]
    nudges = notes_log([line for line in lines if "agent notes:" in line])
    for line in errors:
        print(f"provider error: {line}")
    for index, entry in enumerate(nudges, 1):
        print(f"notes turn {index}: asked again={entry['asked_again']} changed={entry['changed']}")
    path = Path(out)
    if not lines or not path.exists():
        return
    result = json.loads(path.read_text(encoding="utf-8"))
    result["provider_errors"] = errors
    result["notes_log"] = nudges
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _lane() -> str:
    try:
        branch = subprocess.run(["git", "-C", str(ROOT), "branch", "--show-current"], capture_output=True, text=True,
                                check=False).stdout.strip()  # fmt: skip
    except OSError:
        branch = ""
    return branch or ROOT.name


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gemini-env", help="a .env file to take GEMINI_* from (default: this environment)")
    parser.add_argument("--cap-usd", type=float)
    parser.add_argument("--model", default=MODEL, help="the run's one model (fixed; never switched on a failure)")
    parser.add_argument("--probe-models", default="", help="comma-separated: the first that answers a one-token "
                        "probe becomes the run's model")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--targets", default="en,zh-CN")
    parser.add_argument("--only", default="", help="comma-separated scenario names, e.g. S5,S9 (default: all)")
    parser.add_argument("--gap", type=float, default=TURN_GAP_SECONDS, help="seconds between turns (provider quota)")
    parser.add_argument("--flows", default="", help="comma-separated multi-turn flows instead of the scenarios: "
                        + ",".join(FLOWS))
    parser.add_argument("--approved", action="store_true", help="the human approved this run and its cap")
    parser.add_argument("--plan", action="store_true", help="print the plan and its worst case; send nothing")
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "orena-agent-live-run.json"))
    return parser.parse_args()


def drive(args: argparse.Namespace, base_url: str) -> int:
    """The run itself, against the sandbox main() started."""

    targets = [t for t in args.targets.split(",") if t]
    only = {name for name in args.only.split(",") if name}
    parsed = urllib.parse.urlparse(base_url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port in SHARED_PORTS or parsed.port not in SANDBOX_PORTS:
        sys.exit(f"refusing: the live run drives only the throwaway sandbox on 127.0.0.1:{sorted(SANDBOX_PORTS)}")
    client = Client(base_url)
    status, readiness = client.call("GET", "/api/readiness")
    if not isinstance(readiness, dict) or readiness.get("environment") != "development":
        sys.exit("refusing: the server reports production")
    status, capabilities = client.call("GET", "/api/agent/capabilities?interface=vi")
    if status != 200:
        sys.exit(f"refusing: the agent is not on here ({status})")
    version = int(capabilities["contract_version"])
    status, _ = client.call("PUT", "/api/admin/ai/config", {"provider": "gemini", "model": MODEL})
    if status != 200:
        sys.exit(f"could not select Gemini ({status})")

    spent, rows, provider_failures, provider_answered = 0.0, [], 0, False
    if args.flows:
        names = [n for n in args.flows.split(",") if n]
        essay_targets = {step[0] for name in names if name in ESSAY_FLOWS for step in FLOWS[name]}
        for target in ("zh-CN", "en"):  # the words, and the essay only for the targets the flows that read one use
            t = TARGETS[target]
            client.call("POST", "/api/platform/language", {"language": t["language"]})
            for word in t["words"]:
                client.call("POST", "/api/library/vocabulary", {"word": word})
            if target not in essay_targets:
                continue
            if spent + WORST_SETUP_USD > args.cap_usd:
                print("cap reached before the essay review; stopping")
                return finish(rows, spent, args.out)
            status, essay = client.call("POST", "/api/evaluate", {"text": t["essay"], "learning_language": t["language"]})
            spent += WORST_SETUP_USD
            if status != 200:
                print(f"stopping: the essay review (a provider call) answered {status}: {str(essay)[:300]}")
                return finish(rows, spent, args.out)
        rows, spent = run_flows(client, version, names, args.cap_usd, args.gap, spent)
        return finish(rows, spent, args.out)
    for target in targets:
        t = TARGETS[target]
        client.call("POST", "/api/platform/language", {"language": t["language"]})
        for word in t["words"]:
            client.call("POST", "/api/library/vocabulary", {"word": word})
        if spent + WORST_SETUP_USD > args.cap_usd:
            print("cap reached before setup; stopping")
            break
        status, essay = client.call("POST", "/api/evaluate", {"text": t["essay"], "learning_language": t["language"]})
        spent += WORST_SETUP_USD  # its usage is not visible here; the bound is counted
        if status != 200:
            # The first use of a real key: a provider-level failure stops the run, no retries.
            print(f"stopping: the essay review (a provider call) answered {status}: {str(essay)[:300]}")
            return finish(rows, spent, args.out)
        provider_answered = True
        essay_id = str(essay.get("id")) if isinstance(essay, dict) else None
        ledger = RoundLedger(client)
        ledger.mark()  # the essay review is counted by its own bound
        for repeat in range(args.repeat):
            for scenario in scenarios(target, essay_id):
                if only and scenario.name not in only:
                    continue
                if repeat and not scenario.model:
                    continue
                if scenario.model and spent + WORST_TURN_USD > args.cap_usd:
                    print(f"cap ${args.cap_usd:.2f} would be passed; stopping at ${spent:.4f}")
                    return finish(rows, spent, args.out)
                body = turn_body(version, target, scenario)
                result = client.turn(body)
                while result["status"] == 429:  # contract §2.1: wait Retry-After, send the same request again
                    time.sleep(int(result.get("retry_after") or 1))
                    result = client.turn(body)
                summary = summarize(result) if result["status"] == 200 else {"body": result.get("body")}
                if scenario.model:
                    spent += turn_cost(summary, ledger)
                expected = canonical(scenario.canonical) if scenario.canonical else None
                row = {
                    "target": target, "scenario": scenario.name, "repeat": repeat, "status": result["status"],
                    "t_first_event": result.get("t_first_event"), "t_first_segment": result.get("t_first_segment"),
                    "t_done": result.get("t_done"), "canonical": expected,
                    "matches_canonical": expected == summary.get("sequence") if expected else None, **summary,
                }  # fmt: skip
                rows.append(row)
                failed = scenario.model and (result["status"] != 200 or summary.get("error"))
                provider_failures = provider_failures + 1 if failed else 0
                if failed and (not provider_answered or provider_failures >= 2):
                    print(f"stopping: provider failure {summary.get('error') or result.get('body')}; no retries")
                    return finish(rows, spent, args.out)
                provider_answered = provider_answered or (scenario.model and not failed)
                print(
                    f"{target:6} {scenario.name:15} #{repeat} {result['status']} first={row['t_first_event']}s "
                    f"segment={row['t_first_segment']}s done={row['t_done']}s tools={summary.get('tools')} "
                    f"tokens={summary.get('tokens_in')}/{summary.get('tokens_out')} spent=${spent:.4f}"
                    + (f" FLAGS={summary['flags']}" if summary.get("flags") else "")
                )
                time.sleep(args.gap)
    return finish(rows, spent, args.out)


def timing(rows: list[dict]) -> dict:
    """Seconds to the first segment over the turns that answered, client side (median and the slowest)."""

    def summary_of(selected: list[dict]) -> dict:
        seconds = sorted(r["t_first_segment"] for r in selected if r.get("t_first_segment") is not None and not r.get("error"))
        if not seconds:
            return {"turns": 0}
        middle = len(seconds) // 2
        median = seconds[middle] if len(seconds) % 2 else (seconds[middle - 1] + seconds[middle]) / 2
        return {"turns": len(seconds), "first_segment_median_s": round(median, 3), "first_segment_max_s": seconds[-1]}

    out = summary_of(rows)
    # By kind of turn, for a fair comparison: a turn about a note holds its answer; an opening has no read tools.
    kinds: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("flow"):
            kinds.setdefault(f"{row['flow']}.{row['step']}", []).append(row)
    if kinds:
        out["by_step"] = {kind: summary_of(selected) for kind, selected in kinds.items()}
    return out


def finish(rows: list[dict], spent: float, out: str) -> int:
    Path(out).write_text(
        json.dumps({"model": MODEL, "probes": PROBES,
                    # R8: an agent turn routes through the one pinned selection, so both keys run on the same model
                    # in dev; a separate model for ordinary turns is chosen before launch (human direction 2026-09-28).
                    "capability_models": {"agent_turn_fast": MODEL, "agent_turn_deep": MODEL},
                    "spent_bound_usd": round(spent, 4), "price": [PRICE_IN, PRICE_OUT],
                    "lock": LOCK_NOTES, "notes_verdict": notes_verdict(rows) if any(r.get("flow") == "notes" for r in rows)
                    else None, "pending_verdict": pending_verdict(rows) or None,
                    "conversation_verdict": conversation_verdict(rows) or None, "timing": timing(rows), "turns": rows},
                   ensure_ascii=False, indent=2),  # fmt: skip
        encoding="utf-8",
    )
    if any(r.get("flow") == "notes" for r in rows):
        print(f"notes verdict: {notes_verdict(rows)}")
    if any(str(r.get("flow", "")).startswith("convo") for r in rows):
        print(f"conversation verdict: {conversation_verdict(rows)}")
    if any(str(r.get("flow", "")).startswith("pending") for r in rows):
        print(f"pending verdict: {pending_verdict(rows)}")
    print(f"timing: {timing(rows)}")
    print(f"results: {out}  (spend bound ${spent:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
