"""Evaluate (and optionally refit) the Reading level estimate on the gold set.

The gold set is `tests/fixtures/level_gold/` - every label there is PROVISIONAL until the owner approves it
(see its README). The report is accuracy against provisional labels, not against truth.

    python scripts/eval_reading_level.py            # exact and +-1 agreement, per language, per label
    python scripts/eval_reading_level.py --fit      # grid-search TAU and the length thresholds (prints, writes nothing)

Needs jieba for Chinese (requirements.txt). Offline and deterministic.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from writing_coach import reading_level  # noqa: E402

GOLD = ROOT / "tests" / "fixtures" / "level_gold"


def load_gold() -> list[dict]:
    """Every gold item as {id, language, label, text}; real pages go through the extractor."""
    from writing_coach.reading_article_extraction import extract_article

    items: list[dict] = []
    for name in ("voa_en.json", "samples_en.json", "samples_zh.json", "real_articles.json", "zh_real.json"):
        for entry in json.loads((GOLD / name).read_text(encoding="utf-8")):
            if "path" in entry:
                text = (GOLD / entry["path"]).read_text(encoding="utf-8")
            elif "fixture" in entry:
                html = (ROOT / "tests" / "fixtures" / entry["fixture"]).read_text(encoding="utf-8")
                text = extract_article(html, "https://example.org/a/1").body
            else:
                text = entry["text"]
            items.append({"id": entry["id"], "language": entry["language"], "label": entry["label"], "text": text})
    return items


def bands(language: str) -> tuple[str, ...]:
    return reading_level.ZH_BANDS if language == "zh" else reading_level.EN_BANDS


def score(items: list[dict], predict) -> dict[str, dict]:
    """Exact and +-1 agreement on the labelled items (unlabelled ones only widen `bands_used`)."""
    out: dict[str, dict] = {}
    for language in ("en", "zh"):
        every = [i for i in items if i["language"] == language]
        rows = [i for i in every if i["label"]]
        pairs = [(bands(language).index(i["label"]), predict(i)) for i in rows]
        n = len(pairs) or 1
        out[language] = {
            "n": len(pairs),
            "exact": round(sum(a == b for a, b in pairs) / n, 3),
            "within1": round(sum(abs(a - b) <= 1 for a, b in pairs) / n, 3),
            "bands_used": sorted({bands(language)[predict(i)] for i in every}),
        }
    return out


def _memoize_counts() -> None:
    """The fit re-estimates every text per grid point; the token counts do not depend on the thresholds."""
    for name in ("_rank_counts_en", "_rank_counts_zh"):
        original = getattr(reading_level, name)
        cache: dict[str, object] = {}

        def cached(text: str, _original=original, _cache=cache):
            if text not in _cache:
                _cache[text] = _original(text)
            return _cache[text]

        setattr(reading_level, name, cached)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit", action="store_true")
    args = parser.parse_args()
    _memoize_counts()
    items = load_gold()

    def current(item):
        return reading_level.estimate(item["text"], item["language"])["index"]

    print("current:", json.dumps(score(items, current), ensure_ascii=False))
    if args.fit:
        for language in ("en", "zh"):
            rows = [i for i in items if i["language"] == language]
            best = []
            for tau, long_s, short_s in itertools.product(
                (0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.2), (14.0, 18.0, 20.0, 24.0, 28.0, 99.0), (0.0, 5.0, 7.0, 8.0)
            ):
                reading_level.TAU[language] = tau
                reading_level.LONG_SENTENCE[language] = long_s
                reading_level.SHORT_SENTENCE[language] = short_s
                s = score(rows, lambda i: reading_level.estimate(i["text"], i["language"])["index"])[language]
                best.append((s["within1"], s["exact"], tau, long_s, short_s))
            best.sort(reverse=True)
            print(language, "top fits (within1, exact, tau, long, short):", best[:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
