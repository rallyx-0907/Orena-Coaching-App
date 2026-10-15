"""The SePay recovery feed (PR-MON-8 §6, design revisions 5 + 6): missed webhooks, recovered from the Transactions
API v2. A recovery path only, never a parallel payment source.

- **Off by default.** It runs only when the gateway has `SEPAY_API_TOKEN` **and** `SEPAY_FEED_ENABLED`; a token alone
  never starts it. It is turned on only after SePay test mode has proven the cursor and `webhook_success` behaviour.
- **The cursor loop (§6.2).** Always `page=1&since_id=<committed cursor>`, never `page=2`: the set after `since_id`
  changes as the cursor moves. Each iteration handles one page in order and stops at the first row still inside the
  settle delay, which is longer than SePay's webhook retry window. It commits the cursor (a compare-and-set on the
  setting's `updated_at`, under the reconciler's advisory lock) to the last handled row, then asks again. A row that
  fails stops the step without advancing; the next tick retries, and idempotency absorbs the repeat.
- **Which rows are applied (§6.3):** incoming, to the configured account, past the settle delay, with
  `webhook_success` 0 or null. Each goes through the same normalization and the same locked payment decision as a
  webhook (`BillingService.handle_fact`).
- **Secrets (§3.2):** errors carry the HTTP status only; the token never reaches a log or an exception.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from writing_coach.billing.reconciler import RateLimited

_log = logging.getLogger(__name__)

CURSOR_KEY = "billing.sepay.feed_cursor"
SETTLE_DELAY = timedelta(minutes=45)
MAX_ITERATIONS = 5
PER_PAGE = 100
FEED_TIMEOUT_SECONDS = 10.0


class FeedHTTPError(Exception):
    """A failed feed request, by status code only (never its headers, URL or body)."""

    def __init__(self, status: int | None) -> None:
        super().__init__(f"sepay feed answered {status}")
        self.status = status


def fetch_page(request: Mapping[str, Any], *, timeout: float = FEED_TIMEOUT_SECONDS) -> dict:
    """One GET of the feed. A 429 is `RateLimited`; anything else that fails is `FeedHTTPError(status)`."""

    url = f"{request['url']}?{urllib.parse.urlencode(request['params'])}"
    call = urllib.request.Request(url, method="GET", headers=dict(request["headers"]))
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:  # noqa: S310 - the configured SePay host
            return json.loads(response.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 429:
            try:
                wait = float(error.headers.get("Retry-After") or "")
            except ValueError:
                wait = None
            raise RateLimited(wait) from None
        raise FeedHTTPError(error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise FeedHTTPError(None) from None


class SePayFeed:
    def __init__(self, *, service: Any, gateway: Any, settings: Any, orders: Any,
                 fetch: Callable[[Mapping[str, Any]], dict] = fetch_page,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 settle_delay: timedelta = SETTLE_DELAY, max_iterations: int = MAX_ITERATIONS) -> None:
        self._service = service
        self._gateway = gateway
        self._settings = settings      # platform_settings: get_setting / set_setting(expected_updated_at=...)
        self._orders = orders
        self._fetch = fetch
        self._now = now
        self._settle = settle_delay
        self._iterations = max(1, int(max_iterations))

    @property
    def enabled(self) -> bool:
        return bool(getattr(self._gateway, "feed_enabled", False))

    def _cursor(self) -> tuple[dict[str, Any], Any]:
        stored = self._settings.get_setting(CURSOR_KEY)
        if stored is None:
            return {"since_id": None, "backfill_from": None}, None
        value = stored.get("value") if isinstance(stored.get("value"), dict) else {}
        return {"since_id": value.get("since_id"), "backfill_from": value.get("backfill_from")}, stored["updated_at"]

    def _first_run_from(self) -> datetime:
        """The oldest open SePay order's creation, or now when none is open (nothing earlier can be owed)."""

        oldest = self._orders.oldest_open_created_at(self._gateway.name)
        return oldest if oldest is not None else self._now()

    def step(self, counts: Counter[str], lock: Any = None) -> None:
        if not self.enabled:
            return
        from writing_coach.persistence.platform_repository import SettingConflict

        cursor, version = self._cursor()
        if cursor["since_id"] is None and cursor["backfill_from"] is None:
            start = self._first_run_from()
            try:
                written = self._settings.set_setting(CURSOR_KEY, {"since_id": None, "backfill_from": start.isoformat()},
                                                     updated_by="billing-reconciler", expected_updated_at=version)
            except SettingConflict:
                counts["sepay_feed_conflict"] += 1
                return
            cursor, version = {"since_id": None, "backfill_from": start.isoformat()}, written["updated_at"]
        horizon = self._now() - self._settle
        for _ in range(self._iterations):
            if lock is not None and hasattr(lock, "alive") and not lock.alive():
                counts["lock_lost"] += 1
                return
            date_from = datetime.fromisoformat(cursor["backfill_from"]) if cursor["since_id"] is None else None
            request = self._gateway.feed_request(since_id=cursor["since_id"], date_from=date_from, per_page=PER_PAGE)
            try:
                answer = self._fetch(request)  # page 1, always
            except RateLimited:
                counts["sepay_feed_rate_limited"] += 1
                return
            rows = answer.get("data") if isinstance(answer, dict) else None
            if not isinstance(rows, list) or not rows:
                return
            last_handled, settled_out = None, False
            for row in rows:
                if not isinstance(row, dict) or not row.get("id"):
                    raise ValueError("a feed row without an id")   # an unreadable page never moves the cursor
                transfer = self._gateway.feed_transfer(row)
                if transfer.transaction_at is None or transfer.transaction_at > horizon:
                    settled_out = True   # still inside the settle delay (or unreadable): not past this row
                    break
                eligible = (transfer.transfer_type == "in" and transfer.account_number == self._gateway.account_number
                            and row.get("webhook_success") in (0, None))  # fmt: skip
                if eligible:
                    fact = self._gateway.to_fact(transfer, payload_digest=self._gateway.feed_row_digest(row))
                    outcome = self._service.handle_fact(fact)   # raises on a write failure: the cursor stays
                    counts[f"sepay_feed_{outcome.status}"] += 1
                else:
                    counts["sepay_feed_skipped"] += 1
                last_handled = str(row["id"])
            if last_handled is not None:
                try:
                    written = self._settings.set_setting(CURSOR_KEY, {"since_id": last_handled, "backfill_from": None},
                                                         updated_by="billing-reconciler", expected_updated_at=version)
                except SettingConflict:
                    counts["sepay_feed_conflict"] += 1   # another writer: stop, write nothing more
                    return
                cursor, version = {"since_id": last_handled, "backfill_from": None}, written["updated_at"]
            if settled_out or last_handled is None or len(rows) < PER_PAGE:
                return
