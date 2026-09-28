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

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/project/AGENT_CONTRACT.md"
SANDBOX_PORT = 8013
SANDBOX_PORTS = {8013, 8015}  # 8015 when another lane holds 8013
SHARED_PORTS = {8000, 8010, 8011, 8012}

# Published paid-tier rate of gemini-3.5-flash-lite (ai.google.dev pricing, read 2026-09-27), USD per 1M tokens.
PRICE_IN, PRICE_OUT = 0.30, 2.50
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
    text = "".join(e["data"].get("text", "") for e in result["events"] if e["name"] == "segment_end")
    return {
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
FLOWS: dict[str, list[tuple[str, str, dict, str | None, dict]]] = {
    # name: [(target, step, locale, message, context extras)]
    "address": [
        ("zh-CN", "default", VI, "Giải thích giúp mình từ 学习 nhé.", {}),
        ("zh-CN", "request", VI, "Từ giờ Orena xưng chị, gọi mình là em nhé.", {}),
        ("zh-CN", "after", VI, "Chị giải thích từ 机会 cho em với.", {}),
    ],
    "decline": [
        ("zh-CN", "uses-a-pair", VI, "Em hỏi chị: 朋友 nghĩa là gì ạ?", {}),
        ("zh-CN", "says-no", VI, "Thôi, cứ xưng mình và gọi bạn như cũ là được.", {}),
        ("zh-CN", "later", VI, "Em hỏi chị tiếp: 学生 là gì ạ?", {"new_session": True}),
    ],
    "claims": [
        ("zh-CN", "vi", VI, "Lưu từ này giúp mình.", {"word": "我"}),
        ("en", "en", {"interface": "en", "support": "en"}, "Save this word for me.", {"word": "meticulous"}),
        ("en", "zh", {"interface": "zh-CN", "support": "zh-CN"}, "帮我保存这个词。", {"word": "meticulous"}),
    ],
    "history": [("zh-CN", "zh-writing", VI, "Khi viết tôi hay mắc lỗi gì nhất?", {})],
    "screens": [
        ("zh-CN", "vi", VI, "Màn này dùng để làm gì?", {"surface": "vocabulary.my_language"}),
        ("en", "zh", {"interface": "zh-CN", "support": "zh-CN"}, "这个页面是做什么的？", {"surface": "vocabulary.my_language"}),
    ],
}


def run_flows(client: Client, version: int, names: list[str], cap: float, gap: float, spent: float) -> tuple[list[dict], float]:
    rows: list[dict] = []
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
            actions = ["navigate"]
            if extra.get("word"):
                context["selected_item"] = {"type": "word", "text": extra["word"], "lang": target}
                actions = ["save_word", "add_word_to_collection"]
            body = {
                "contract_version": version,
                "trigger": "message",
                "message": message,
                "client": {"ui_version": "agent-live-run", "supported_actions": actions,
                           "supported_intents": ["vocabulary.review_due", "writing.revision"]},  # fmt: skip
                "context": context,
                "coach_notes": list(notes.values()),
            }
            if session_id:
                body["session_id"] = session_id
            result = client.turn(body)
            while result["status"] == 429:
                time.sleep(int(result.get("retry_after") or 1))
                result = client.turn(body)
            summary = summarize(result) if result["status"] == 200 else {"body": result.get("body")}
            for event in result.get("events", []):
                if event["name"] == "session":
                    session_id = event["data"]["session_id"]
                if event["name"] == "memory_update" and event["data"]["op"] == "upsert":
                    notes[event["data"]["note"]["id"]] = event["data"]["note"]
            memory = [e["data"] for e in result.get("events", []) if e["name"] == "memory_update"]
            if result["status"] == 200:
                spent += price(summary["tokens_in"], summary["tokens_out"]) if summary["usage_reported"] else WORST_TURN_USD
            row = {"flow": name, "step": step, "target": target, "locale": locale, "message": message,
                   "status": result["status"], "memory_update": memory, **summary}  # fmt: skip
            rows.append(row)
            print(f"{name:8} {step:12} {target:6} {result['status']} tools={summary.get('tools')} "
                  f"memory={[m['note'].get('text') for m in memory if 'note' in m]} flags={summary.get('flags')} "
                  f"spent=${spent:.4f}")  # fmt: skip
            time.sleep(gap)
    return rows, spent


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

    def down(self) -> None:
        if self.started and not self.removed:
            self.removed = True
            print("taking the sandbox down")
            self._compose("down", "--remove-orphans", check=False)


def _stop_on_signal(signum, frame):  # noqa: ANN001 - signal handler
    raise SystemExit(128 + signum)  # unwinds through finally: the sandbox comes down


def main() -> int:
    args = _arguments()
    turns = plan()["model_turns_per_target_per_repeat"] * args.repeat * len([t for t in args.targets.split(",") if t])
    print(f"plan: {turns} model turns (scenarios); worst case ${turns * WORST_TURN_USD + 2 * WORST_SETUP_USD:.2f}")
    if args.plan:
        return 0
    if not args.approved or args.cap_usd is None or args.cap_usd <= 0:
        sys.exit("refusing: needs --approved and the approved --cap-usd")
    port = next((p for p in sorted(SANDBOX_PORTS) if _port_free(p)), None)
    if port is None:
        sys.exit(f"refusing: {sorted(SANDBOX_PORTS)} are all taken")
    sandbox = Sandbox(_compose_env(args.gemini_env, port))
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _stop_on_signal)
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
        sandbox.down()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gemini-env", help="a .env file to take GEMINI_* from (default: this environment)")
    parser.add_argument("--cap-usd", type=float)
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
    status, _ = client.call("PUT", "/api/admin/ai/config", {"provider": "gemini", "model": "gemini-3.5-flash-lite"})
    if status != 200:
        sys.exit(f"could not select Gemini ({status})")

    spent, rows, provider_failures, provider_answered = 0.0, [], 0, False
    if args.flows:
        for target in ("zh-CN", "en"):  # the words and the essay the flows read
            t = TARGETS[target]
            client.call("POST", "/api/platform/language", {"language": t["language"]})
            for word in t["words"]:
                client.call("POST", "/api/library/vocabulary", {"word": word})
            status, essay = client.call("POST", "/api/evaluate", {"text": t["essay"], "learning_language": t["language"]})
            spent += WORST_SETUP_USD
            if status != 200:
                print(f"stopping: the essay review (a provider call) answered {status}: {str(essay)[:300]}")
                return finish(rows, spent, args.out)
        rows, spent = run_flows(client, version, [n for n in args.flows.split(",") if n], args.cap_usd, args.gap, spent)
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
                if scenario.model and result["status"] == 200:
                    measured = price(summary["tokens_in"], summary["tokens_out"])
                    spent += measured if summary["usage_reported"] else WORST_TURN_USD
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


def finish(rows: list[dict], spent: float, out: str) -> int:
    Path(out).write_text(
        json.dumps({"spent_bound_usd": round(spent, 4), "price": [PRICE_IN, PRICE_OUT], "turns": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"results: {out}  (spend bound ${spent:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
