"""Caption timing: re-timing provider captions and the one gate that keeps mistimed lines from learners (P0 2026-10-20).

Root cause this module exists for. A provider's automatic (speech-recognition) caption track is a *rolling* two-line
display: each cue's `start + duration` is when the cue leaves the screen, which is the start of the cue after next, not
the end of its speech. Taking that window as the speech span let the line builder push every next line's start to the
previous line's inflated end (`media_segmentation._monotonic`), so a subtitle ran up to two seconds behind the voice and
whole sentences were squeezed into 400 ms. D-020 already made the next cue's start the overlap boundary for playback;
`clip_to_next_start` applies the same boundary to the cues before they are cut into lines. It uses only the timing the
caption provider supplied (cue starts): no audio is fetched or listened to (D-244).

`caption_timing_report` is the gate. One function, run at ingest (the pipeline), at content-pack import, and before
any publish (the operator's Publish and the pipeline's own automatic publication). A transcript that fails it is held
for timing review with the stable reason `caption_timing`; it is never published. Pure: no provider, no storage, no
clock; thresholds come in as arguments (`media.caption_*` policies supply them, `thresholds()` reads them).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from writing_coach.media_segmentation import Cue, primary_language

REASON_CAPTION_TIMING = "caption_timing"
# Recorded on the processing record and on the lesson payload when the cues were re-timed to the next start (D-020).
TIMING_NEXT_START = "next_start"
TIMING_KEY = "caption_timing"

KIND_MANUAL = "manual"
KIND_AUTO = "auto"
KIND_UNKNOWN = "unknown"

DEFAULT_MAX_CPS = 25.0
DEFAULT_MAX_CPS_ZH = 10.0
DEFAULT_MAX_DEFECT_SHARE = 0.02
DEFAULT_MAX_GAP_SECONDS = 12
SHORT_LINE_MS = 800
# At most 0.8 s holding this many words is faster than ordinary speech (5 English words, ~9 Han a second): three words
# or five Han in 0.8 s is ordinary dialogue and ordinary Mandarin, and is not a defect (review of #430, 2026-10-20).
SHORT_LINE_WORDS = 4
SHORT_LINE_HAN = 7

_SPEAKER = re.compile(r">{2,}")
_SOUND_TAG = re.compile(r"\[[^\]]{1,40}\]")
_HAN = re.compile(r"[㐀-䶿一-鿿]")
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d+", re.UNICODE)
_TERMINAL = re.compile(r"[.!?…。！？；]['\"”’）)]*$")
_PUNCTUATION = re.compile(r"[.!?…,;:。！？；，、：]")
_NON_SPEECH = re.compile(r"\[[^\]]{1,40}\]|\([^)]{1,40}\)|[♪♫♬♩]")
# An English line ending on one of these words has clearly not finished its sentence.
_EN_CONTINUES = frozenset({
    "the", "a", "an", "to", "of", "and", "or", "but", "in", "on", "at", "with", "for", "from", "that", "my",
    "your", "his", "her", "their", "our", "its", "is", "are", "was", "were", "because", "if", "when", "than",
})
# A track this share of whose lines carries any punctuation is punctuated; an unpunctuated (raw automatic) track
# says nothing about where a sentence ends, so its pauses are never read as mid-sentence.
_PUNCTUATED_SHARE = 0.3
# A cue is "rolling" when it is still on screen after the next cue has started by more than this.
_ROLLING_OVERLAP_MS = 250
_ROLLING_SHARE = 0.4


def clip_to_next_start(cues: Iterable[Cue]) -> tuple[list[Cue], int]:
    """Order the cues by start and end each one no later than the next cue's start (D-020). Returns (cues, how many were
    clipped). Cues that start together (parallel tracks) are left as they are; a cue never ends before it starts."""
    ordered = sorted((cue for cue in cues), key=lambda cue: (cue.start_ms, cue.end_ms))
    clipped: list[Cue] = []
    changed = 0
    for index, cue in enumerate(ordered):
        end = cue.end_ms
        following = next((later.start_ms for later in ordered[index + 1:] if later.start_ms > cue.start_ms), None)
        if following is not None and end > following:
            end = following
            changed += 1
        clipped.append(Cue(cue.start_ms, max(end, cue.start_ms + 1), cue.text))
    return clipped, changed


def rolling_share(cues: Sequence[Cue]) -> float:
    """The share of cues still on screen well after the next cue started: the rolling-display pattern of auto captions."""
    ordered = sorted(cues, key=lambda cue: (cue.start_ms, cue.end_ms))
    pairs = [(cue, ordered[index + 1]) for index, cue in enumerate(ordered[:-1]) if ordered[index + 1].start_ms > cue.start_ms]
    if not pairs:
        return 0.0
    overlapping = sum(1 for cue, later in pairs if cue.end_ms - later.start_ms > _ROLLING_OVERLAP_MS)
    return overlapping / len(pairs)


def auto_caption_markers(texts: Iterable[str]) -> bool:
    """`>>` speaker changes or bracketed sound tags (`[music]`, `[crying]`): what YouTube's speech recognition writes."""
    return any(_SPEAKER.search(str(text or "")) or _SOUND_TAG.search(str(text or "")) for text in texts)


def classify_caption_kind(kind: object, cues: Sequence[Cue] = ()) -> str:
    """The track's kind. The provider's own word (`manual`, `auto`) is kept; a track whose kind the provider did not say
    (Supadata, D-215) is `auto` when it carries the auto-caption markers or the rolling-cue pattern, else `unknown`."""
    value = str(kind or "").strip().casefold()
    if value in {KIND_MANUAL, KIND_AUTO}:
        return value
    if cues and (auto_caption_markers(cue.text for cue in cues) or rolling_share(cues) >= _ROLLING_SHARE):
        return KIND_AUTO
    return KIND_UNKNOWN if value in {"", KIND_UNKNOWN} else value


@dataclass(frozen=True)
class TimingThresholds:
    max_cps: float = DEFAULT_MAX_CPS
    max_cps_zh: float = DEFAULT_MAX_CPS_ZH
    max_defect_share: float = DEFAULT_MAX_DEFECT_SHARE
    max_gap_ms: int = DEFAULT_MAX_GAP_SECONDS * 1000


def thresholds() -> TimingThresholds:
    """The thresholds from the `media.caption_*` policies (the operator may change them); defaults when unreadable."""
    try:
        from writing_coach import policies

        return TimingThresholds(
            max_cps=float(policies.value("media.caption_max_cps")),
            max_cps_zh=float(policies.value("media.caption_max_cps_zh")),
            max_defect_share=float(policies.value("media.caption_timing_max_defect_share")),
            max_gap_ms=int(policies.value("media.caption_max_gap_seconds")) * 1000,
        )
    except Exception:  # noqa: BLE001 - a gate must still run when the policy store cannot be read
        return TimingThresholds()


@dataclass(frozen=True)
class TimingReport:
    passed: bool
    lines: int
    counts: dict[str, int] = field(default_factory=dict)
    failed: tuple[str, ...] = ()

    @property
    def reason(self) -> str:
        return "" if self.passed else REASON_CAPTION_TIMING

    def detail(self) -> str:
        """Language-neutral (ids and numbers), shown beside the translated reason without new copy."""
        parts = [f"{key} {value}" for key, value in self.counts.items() if value]
        return (", ".join(self.failed) + ": " if self.failed else "") + "; ".join(parts) + f"; {self.lines} lines"

    def as_dict(self) -> dict[str, Any]:
        return {"pass": self.passed, "lines": self.lines, "counts": dict(self.counts), "failed": list(self.failed)}


def _spoken(text: str) -> str:
    return " ".join(_SOUND_TAG.sub(" ", _SPEAKER.sub(" ", text)).split())


def caption_timing_report(
    lines: Sequence[Cue],
    *,
    language: str,
    caption_kind: str = "",
    retimed: bool = True,
    limits: TimingThresholds | None = None,
) -> TimingReport:
    """Whether provider-caption lines follow the speech. Criteria:

    * `order`: any line that ends at or before its start, starts before the previous one, or overlaps it fails at once;
    * `fast`: a line read faster than `max_cps` characters a second (`max_cps_zh` Han characters for Chinese);
    * `short_dense`: a line of at most 0.8 s holding four or more words (seven Han characters);
    * `gap_mid_sentence`: a silence longer than `max_gap_ms` where the text clearly continues - a punctuated track,
      the line before ending on a comma or a word that cannot end an English sentence (`the`, `to`, `and`...) and the
      next starting in lower case (Chinese: the line before ending on `，` or `、`), and neither line marking
      non-speech (`[music]`, `♪`), since a music break or a pause after a finished thought is not a defect; never on an automatic track;
    * `not_retimed`: an automatic track whose cues were not re-timed to the next start.

    `fast`, `short_dense` and `gap_mid_sentence` together may touch at most `max_defect_share` of the lines (and at least
    one line is always tolerated, so a single borderline line in a short clip does not hold it).
    """
    limits = limits or TimingThresholds()
    zh = primary_language(language) == "zh"
    max_cps = limits.max_cps_zh if zh else limits.max_cps
    order = fast = short_dense = gap = 0
    defective: set[int] = set()
    previous: Cue | None = None
    # The gap rule reads punctuation, which an automatic track does not have reliably: it is skipped for one.
    automatic = str(caption_kind or "").casefold() == KIND_AUTO
    punctuated = bool(lines) and sum(1 for line in lines if _PUNCTUATION.search(line.text)) / len(lines) >= _PUNCTUATED_SHARE
    for index, line in enumerate(lines):
        duration = line.end_ms - line.start_ms
        if duration <= 0 or (previous is not None and (line.start_ms < previous.start_ms or line.start_ms < previous.end_ms)):
            order += 1
        spoken = _spoken(line.text)
        units = len(_HAN.findall(spoken)) if zh else len(spoken)
        if duration > 0 and units / (duration / 1000.0) > max_cps:
            fast += 1
            defective.add(index)
        words = len(_HAN.findall(spoken)) if zh else len(_WORD.findall(spoken))
        if 0 < duration <= SHORT_LINE_MS and words >= (SHORT_LINE_HAN if zh else SHORT_LINE_WORDS):
            short_dense += 1
            defective.add(index)
        if previous is not None and line.start_ms - previous.end_ms > limits.max_gap_ms:
            if not automatic and punctuated and _clearly_continues(previous.text, line.text, zh):
                gap += 1
                defective.add(index)
        previous = line
    kind = str(caption_kind or "").casefold()
    not_retimed = int(kind == KIND_AUTO and not retimed)
    allowed = max(1, int(len(lines) * max(0.0, limits.max_defect_share)))
    failed: list[str] = []
    if order:
        failed.append("order")
    if len(defective) > allowed:
        failed.append("defects")
    if not_retimed:
        failed.append("not_retimed")
    counts = {"order": order, "fast": fast, "short_dense": short_dense, "gap_mid_sentence": gap, "not_retimed": not_retimed}
    return TimingReport(passed=not failed, lines=len(lines), counts=counts, failed=tuple(failed))


def _clearly_continues(before_raw: str, after_raw: str, zh: bool) -> bool:
    if _NON_SPEECH.search(before_raw) or _NON_SPEECH.search(after_raw):
        return False
    before, after = _spoken(before_raw), _spoken(after_raw)
    if not before or not after or _TERMINAL.search(before):
        return False
    if zh:
        return before.endswith(("，", "、"))
    words = _WORD.findall(before.casefold())
    ends_open = before.endswith((",", ";", ":")) or bool(words and words[-1] in _EN_CONTINUES)
    return ends_open and after[:1].islower()


def lesson_caption_facts(entry: Any) -> tuple[bool, str, bool]:
    """(applies, kind, retimed) for a stored entry: the gate applies to a transcript made from provider captions."""
    lesson = getattr(entry, "lesson", None) or {}
    payload = lesson.get("payload") if isinstance(lesson, Mapping) else None
    payload = payload if isinstance(payload, Mapping) else {}
    processing = getattr(entry, "processing", None) or {}
    source = getattr(entry, "source", None) or {}
    origin = str(payload.get("transcript_origin") or processing.get("origin") or "")
    if origin != "provider_caption":
        return False, "", True
    retimed = (payload.get(TIMING_KEY) or processing.get(TIMING_KEY)) == TIMING_NEXT_START
    kind = str(payload.get("caption_kind") or processing.get("caption_kind") or source.get("caption_kind") or "")
    return True, kind, retimed
