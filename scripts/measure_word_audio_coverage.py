"""How much of a word list Wikimedia Commons can actually pronounce.

Not a test and not part of CI: it crosses the network, so it is a measurement
an operator runs when they want a number, and the number it prints is the only
honest source of "coverage" for this feature.

    python scripts/measure_word_audio_coverage.py            # both lists
    python scripts/measure_word_audio_coverage.py --limit 10

It asks Commons the same question the app asks, through the same code, so what
it reports is what a learner would get - including the refusals: a Chinese word
is counted as covered only when a clip binds to the *reading*, which is the
rule the whole feature rests on.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from writing_coach.word_audio import CommonsVoice  # noqa: E402

# Ordinary words a learner meets early, not ones chosen because they have
# recordings: a list picked for its hit rate would measure nothing.
ENGLISH = [
    "harbour", "lantern", "quay", "promise", "gather", "narrow", "gentle", "heavy",
    "gate", "river", "market", "window", "letter", "morning", "winter", "listen",
    "borrow", "lucky", "sudden", "quiet", "bridge", "kitchen", "silence", "journey",
    "shoulder", "weather", "distant", "painter", "ancient", "bright",
]
# Words with more than one reading, which is the case this feature exists for.
CHINESE = [
    ("行", "xíng"), ("行", "háng"), ("重", "zhòng"), ("重", "chóng"),
    ("长", "cháng"), ("长", "zhǎng"), ("乐", "lè"), ("乐", "yuè"),
    ("还", "hái"), ("还", "huán"), ("差", "chà"), ("差", "chāi"),
    ("觉", "jué"), ("觉", "jiào"), ("地", "de"),
]
# Commons is a volunteer service. One request at a time, with a pause.
PAUSE_SECONDS = 0.4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="only the first N of each list")
    parser.add_argument("--language", choices=("en", "zh", "both"), default="both")
    arguments = parser.parse_args()

    voice = CommonsVoice()
    english = ENGLISH[: arguments.limit] if arguments.limit else ENGLISH
    chinese = CHINESE[: arguments.limit] if arguments.limit else CHINESE

    if arguments.language in ("en", "both"):
        found = []
        for word in english:
            spoken = voice.speak(term=word, language="en", reading="", single_reading=True)
            print(f"  en {word:<10} {'yes' if spoken else 'no ':<4} {spoken.licence if spoken else ''}")
            if spoken:
                found.append(word)
            time.sleep(PAUSE_SECONDS)
        print(f"English: {len(found)}/{len(english)} covered")

    if arguments.language in ("zh", "both"):
        found = []
        for term, reading in chinese:
            spoken = voice.speak(term=term, language="zh", reading=reading, single_reading=False)
            print(f"  zh {term} {reading:<8} {'yes' if spoken else 'no ':<4} {spoken.licence if spoken else ''}")
            if spoken:
                found.append((term, reading))
            time.sleep(PAUSE_SECONDS)
        print(f"Chinese, bound to a reading: {len(found)}/{len(chinese)} covered")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
