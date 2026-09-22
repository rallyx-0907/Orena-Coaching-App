"""Give the sandbox learner enough real data to review Hồ sơ and Tiến độ.

Both screens show what the learner has actually done - the rank comes from
mastered words, the panels from saved and due words, the usage bars from the
plan's own counters - so an empty sandbox shows an empty page and nothing can
be reviewed. This fills it **through the app's own endpoints**: every word is
saved with POST /api/library/vocabulary and carried to "mastered" by three
POST .../review calls, exactly as a learner would. Nothing is written into a
database behind the app's back, so what appears on the screen is what the
product really produced.

Sandbox only, by construction. `AGENTS.md` ("Safety") reserves production on
8000 and preview on 8010 for the human; this refuses any host but the sandbox
unless --i-know-what-im-doing is passed, and it never deletes anything it did
not create.

    python scripts/seed_sandbox_learner.py --rank 5
    python scripts/seed_sandbox_learner.py --words 120 --reset

--rank seeds just past that rank's threshold. The thresholds are the design's,
read from static/orena/product/rank.js so this script and the interface cannot
drift apart.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SANDBOX = "http://127.0.0.1:8011"
RESERVED_PORTS = {"8000", "8010"}
ROOT = Path(__file__).resolve().parent.parent
RANK_SOURCE = ROOT / "static" / "orena" / "product" / "rank.js"

# Plain English words a learner could plausibly have met. Kept boring on
# purpose: this is test data, not content, and it is never shown to anyone but
# whoever is reviewing the screens.
STEMS = [
    "morning", "harbour", "letter", "window", "silence", "market", "journey", "garden",
    "weather", "kitchen", "machine", "picture", "evening", "village", "bottle", "candle",
    "river", "forest", "island", "bridge", "mountain", "valley", "meadow", "desert",
    "teacher", "student", "doctor", "farmer", "builder", "painter", "singer", "writer",
    "gentle", "sudden", "quiet", "bright", "heavy", "narrow", "distant", "ancient",
    "gather", "wander", "remember", "promise", "arrive", "return", "believe", "imagine",
    "kindness", "patience", "courage", "wonder", "comfort", "freedom", "shadow", "memory",
]
SUFFIXES = ["", "s", "-note", "-again", "-more", "-still", "-yet", "-anew"]


def rank_thresholds() -> list[tuple[str, int]]:
    """The design's own thresholds, read from the module the app renders from."""
    text = RANK_SOURCE.read_text(encoding="utf-8")
    block = text[text.index("export const RANK_THRESHOLDS = {"):]
    block = block[: block.index("};")]
    pairs = re.findall(r"(\w+):\s*(\d+)", block)
    return [(name, int(value)) for name, value in pairs]


def words_for(count: int) -> list[str]:
    out: list[str] = []
    for i in range(count):
        stem = STEMS[i % len(STEMS)]
        suffix = SUFFIXES[(i // len(STEMS)) % len(SUFFIXES)]
        round_no = i // (len(STEMS) * len(SUFFIXES))
        out.append(f"{stem}{suffix}" + (f"-{round_no + 2}" if round_no else ""))
    return out


def call(base: str, method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=SANDBOX, help="the sandbox base URL")
    parser.add_argument("--rank", type=int, default=None, help="seed just past this rank's threshold")
    parser.add_argument("--words", type=int, default=None, help="seed this many mastered words instead")
    parser.add_argument("--learning", type=int, default=12, help="extra words left mid-review, so the panels are not all the same")
    parser.add_argument("--reset", action="store_true", help="delete every word this sandbox holds first")
    parser.add_argument("--i-know-what-im-doing", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    base = args.base.rstrip("/")
    port = base.rsplit(":", 1)[-1]
    if port in RESERVED_PORTS and not args.i_know_what_im_doing:
        print(f"Refusing {base}: {port} is a runtime the human operates, not the sandbox.", file=sys.stderr)
        return 2

    thresholds = rank_thresholds()
    if args.words is not None:
        target = max(0, args.words)
        label = f"{target} mastered words"
    else:
        rank = args.rank if args.rank is not None else 5
        reachable = [(name, words) for name, words in thresholds]
        if rank < 1 or rank > len(reachable):
            print(f"--rank must be between 1 and {len(reachable)} (the ranks the design gives a number).", file=sys.stderr)
            return 2
        name, words = reachable[rank - 1]
        target = words
        label = f"{name} ({words} words)"

    try:
        before = call(base, "GET", "/api/library/vocabulary")
    except urllib.error.URLError as error:
        print(f"Cannot reach {base}: {error}", file=sys.stderr)
        return 1
    held = [item["word"] for item in before.get("items", [])]
    print(f"sandbox {base}: {len(held)} words held, seeding {label}")

    if args.reset and held:
        for word in held:
            call(base, "DELETE", f"/api/library/vocabulary/{urllib.parse.quote(word)}")
        print(f"  removed {len(held)} words")
        held = []

    started = time.time()
    plan = words_for(target + args.learning)
    for index, word in enumerate(plan):
        call(base, "POST", "/api/library/vocabulary", {
            "word": word,
            "definition": "seeded for review",
            "source_kind": "manual",
        })
        # Three "got it" answers carry a word to review stage three, which is
        # what both screens count as mastered. The learning tail stops at one,
        # so "đang ôn" and "tới hạn" are not empty either.
        rounds = 3 if index < target else 1
        for _ in range(rounds):
            call(base, "POST", f"/api/library/vocabulary/{urllib.parse.quote(word)}/review", {"result": "got_it"})
        if index and index % 100 == 0:
            print(f"  {index}/{len(plan)} …")

    after = call(base, "GET", "/api/library/vocabulary")
    summary = after.get("summary", {})
    print(f"done in {time.time() - started:.0f}s: "
          f"saved {summary.get('saved')}, mastered {summary.get('mastered')}, "
          f"learning {summary.get('learning')}, due {summary.get('due')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
