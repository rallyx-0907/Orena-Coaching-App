"""Media import minutes against the plan (`media.import`, D-16S): the part of the quota that outlives the request.

A learner's import is a background job: the request stores the source and queues it, a worker makes the transcript
and the meanings, and the learner's room polls. The meter is the minutes of SOURCE media the learner imports in
their month (the product unit is source minutes, whatever the work was: an import that found free captions still
costs the learner the video's minutes), stored in seconds.

    request   duration read on the server (YouTube's own metadata, ffprobe of the stored bytes; never the client's)
              -> same source already imported by this learner? answer it, charge nothing
              -> reserve ceil(seconds) (all or nothing; 429 before any work, 503 when it cannot be checked)
              -> the reservation's operation id is kept on the library entry (`source`, not shown to the learner)
    worker    dispatch by id before the first paid step -> captions or speech recognition -> meanings
              -> settle by id: the source seconds on success, 0 when nothing usable was made
    restart   the entry still holds the id: the pipeline re-queues the job, and a settlement that could not be
              written is retried from the intent recorded on the entry

The reconciler only backstops: `ASYNC_METERS` are swept after `ASYNC_RECONCILE_AFTER`, not after minutes
(product/quota.py). Nothing here decides a limit, a window or a plan: that is the quota core's.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from writing_coach.core.errors import orena_http_error
from writing_coach.media_library_store import OWNER_FIELD, MediaLibraryEntry, owner_token
from writing_coach.product import quota

_log = logging.getLogger(__name__)

METER = "media.import"

# Where the reservation is kept: the entry's provenance (`source`, strings only), which no learner payload carries.
SOURCE_OP = "quota_op"
SOURCE_UNITS = "quota_units"
SOURCE_SETTLE = "quota_settle"     # "<actual>|<outcome_ref>" once decided; "done" once the store holds it
SOURCE_KEY = "source_key"          # "youtube:<id>" or "file:<sha256>": what "the same source" means
SETTLED = "done"

DISPATCH_REF = "media-import"
# A decoded length may exceed a container's declared length by a little (encoder padding); more than this is not
# the source that was reserved for.
TOLERANCE_SECONDS = 2
SETTLE_ATTEMPTS = 3
LIVE_STATES = frozenset({"queued", "running", "ready", "held"})


class ImportQuotaUnavailable(Exception):
    """The worker may not start paid work for this import: `code` is the pipeline's stop reason."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --- the switch ---------------------------------------------------------------------------------------------

def ready() -> bool:
    """True when `media.import` is enforced and can be checked; False when it is not enforced (the unmetered path,
    exactly as before); 503 `quota_unavailable` when it is enforced but cannot be checked. Asked before the learner's
    file is downloaded or read, so a refusal does none of that work."""
    return quota.require_ready(METER)


def max_import_seconds() -> int:
    """The longest source the pipeline will transcribe (`MEDIA_ASR_MAX_SECONDS`): the cap of one reservation."""
    from writing_coach.media_transcript_pipeline import max_asr_seconds

    return max_asr_seconds()


def duration_unavailable() -> Exception:
    return orena_http_error(503, "media_duration_unavailable",
                            "The length of this media could not be read right now. Please try again.",
                            retryable=True)


def units_for(seconds: object, *, cap: bool = True) -> int:
    """`ceil(seconds)`, at least 1, at most the pipeline's longest source. Unreadable or non-positive: 503."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise duration_unavailable()
    units = max(1, math.ceil(round(float(seconds), 3)))
    return min(units, max_import_seconds()) if cap else units


# --- admission ----------------------------------------------------------------------------------------------

@dataclass
class Hold:
    """One admitted import's reservation, until its entry owns it."""

    ticket: Any
    source_key: str

    @property
    def operation_id(self) -> str:
        return self.ticket.operation_id

    @property
    def units(self) -> int:
        return self.ticket.units

    def fields(self) -> dict[str, str]:
        return {SOURCE_OP: self.operation_id, SOURCE_UNITS: str(self.units), SOURCE_KEY: self.source_key}

    def release(self) -> None:
        self.ticket.release()


def admit(seconds: float, source_key: str, *, cap: bool = True, idempotency_key: str | None = None) -> Hold | None:
    """Reserve this source's minutes, or refuse before any work: 429 `quota_exhausted` (all or nothing), 503, 409.

    None when the meter is not enforced. The operation is (account, meter, key, source): a retry of the same
    request under one `Idempotency-Key` is never charged twice."""
    units = units_for(seconds, cap=cap)
    ticket = quota.begin(METER, units=units, request_digest=quota.request_digest(source_key),
                         idempotency_key=idempotency_key)
    if not getattr(ticket, "enforced", False):
        return None
    return Hold(ticket, source_key)


_LOCKS: dict[str, list[Any]] = {}
_LOCKS_GUARD = threading.Lock()


@contextmanager
def source_lock(owner_key: str, source_key: str) -> Iterator[None]:
    """Serialise the 'already imported? -> reserve -> store the entry' step for one learner and one source, so two
    requests for the same source cannot both be charged. The library index is a single-process store (its own
    contract), so a process-local lock is the same scope."""
    key = f"{owner_token(owner_key)}|{source_key}"
    with _LOCKS_GUARD:
        slot = _LOCKS.setdefault(key, [threading.Lock(), 0])
        slot[1] += 1
    try:
        with slot[0]:
            yield
    finally:
        with _LOCKS_GUARD:
            slot[1] -= 1
            if slot[1] == 0:
                _LOCKS.pop(key, None)


def existing_import(store: Any, *, owner_key: str, language: str, source_key: str) -> MediaLibraryEntry | None:
    """This learner's live import of this source in this learning language, or None.

    Live is queued, running, ready or held: the learner already paid for it (or is paying), so asking again returns
    it. A failed or cancelled one settled 0, so the learner may import the source again as a new, charged import."""
    token = owner_token(owner_key)
    for entry in store.list(library="personal", status=None, language=language):
        if entry.source.get(OWNER_FIELD) != token or entry.status == "archived":
            continue
        key = entry.source.get(SOURCE_KEY) or (f"youtube:{entry.provider_media_id}" if entry.provider == "youtube" else "")
        if key != source_key:
            continue
        state = (entry.processing or {}).get("state")
        if state is None or state in LIVE_STATES:
            return entry
    return None


# --- the worker's side --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class EntryHold:
    operation_id: str
    units: int


def hold_of(entry: MediaLibraryEntry | None) -> EntryHold | None:
    """The reservation this entry owns and has not settled, or None (not metered, or already settled)."""
    if entry is None:
        return None
    source = entry.source
    operation = source.get(SOURCE_OP, "")
    if not operation or source.get(SOURCE_SETTLE) == SETTLED:
        return None
    try:
        units = int(source.get(SOURCE_UNITS, ""))
    except ValueError:
        return None
    return EntryHold(operation, units) if units > 0 else None


def reserved_seconds(entry: MediaLibraryEntry | None) -> int | None:
    hold = hold_of(entry)
    return hold.units if hold is not None else None


def dispatch(hold: EntryHold) -> None:
    """Right before the job's first paid step. Refuses (raises) when the reservation is not live: no paid work
    without a reservation, and none when the store cannot be asked."""
    try:
        status = quota.dispatch_operation(hold.operation_id, DISPATCH_REF)
    except Exception:  # noqa: BLE001 - the store is unreadable: fail closed
        _log.warning("media import dispatch: quota store unavailable for %s", hold.operation_id, exc_info=True)
        raise ImportQuotaUnavailable("quota_unavailable") from None
    if status in ("dispatch", "duplicate"):
        return
    if status == "denied":
        raise ImportQuotaUnavailable("account_deleted")
    _log.warning("media import dispatch refused for %s: %s", hold.operation_id, status)
    raise ImportQuotaUnavailable("quota_unavailable")


def settlement_for(entry: MediaLibraryEntry | None, hold: EntryHold) -> tuple[int, str]:
    """(units to charge, outcome reference) from where the entry ended.

    A usable transcript (ready, or held for a person's rights decision) costs the source's seconds - the whole
    reservation for captions, the seconds speech recognition actually decoded (never more than reserved) when it had
    to listen. Anything else - failed, unusable, cancelled, deleted - costs 0; what the providers charged stays in
    the AI cost ledger."""
    if entry is None:
        return 0, "cancelled"
    processing = entry.processing or {}
    state = processing.get("state")
    if state in ("ready", "held"):
        origin = str(processing.get("origin") or "unknown")
        decoded = processing.get("asr_seconds")
        if origin == "generated_asr" and isinstance(decoded, (int, float)) and not isinstance(decoded, bool) and decoded > 0:
            return min(hold.units, math.ceil(decoded)), f"completed:{origin}"
        return hold.units, f"completed:{origin}"
    reason = str(processing.get("reason") or state or "unfinished")
    return 0, f"failed:{reason}"[:200]


def encode_intent(actual: int, ref: str) -> str:
    return f"{actual}|{ref}"[:300]


def decode_intent(value: str) -> tuple[int, str] | None:
    head, _, ref = value.partition("|")
    try:
        return int(head), ref
    except ValueError:
        return None


def settle(hold: EntryHold, actual: int, ref: str, *, attempts: int | None = None) -> str:
    """Settle by operation id. Any verdict the store returns is final (settled, or already so); only a failure to
    reach the store is retried, with a short back-off, and then raised: the caller keeps its intent and the next
    restart retries."""
    attempts = max(1, SETTLE_ATTEMPTS if attempts is None else attempts)
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            status = quota.settle_operation(hold.operation_id, actual, ref)
        except Exception as error:  # noqa: BLE001
            last = error
            if attempt + 1 < attempts:
                time.sleep(0.5 * (2 ** attempt))
            continue
        if status not in ("settle", "duplicate"):
            _log.warning("media import settle %s: %s", hold.operation_id, status)
        return status
    raise ImportQuotaUnavailable("quota_unavailable") from last


def cancel_entry(entry: MediaLibraryEntry) -> None:
    """A learner removed an import that has not settled: it produced nothing for them, so it costs 0. Best effort
    (the worker, finding the entry gone, settles the same way; the store treats the repeat as a duplicate)."""
    hold = hold_of(entry)
    if hold is None:
        return
    # A settlement already decided (the import finished and only its write is pending) is written as decided.
    actual, ref = decode_intent(entry.source.get(SOURCE_SETTLE, "")) or (0, "cancelled")
    try:
        settle(hold, actual, ref)
    except Exception:  # noqa: BLE001 - the delete must not fail on accounting; the reconciler is the backstop
        _log.warning("media import cancel could not settle %s", hold.operation_id, exc_info=True)
