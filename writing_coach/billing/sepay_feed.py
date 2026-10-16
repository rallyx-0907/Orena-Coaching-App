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
DEFAULT_RETRY_SECONDS = 60.0          # a 429 without a usable Retry-After still waits this long
MAX_BACKFILL_PAGES = 50
MAX_BACKFILL_RANGE = timedelta(days=31)


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
            return {"since_id": None, "backfill_from": None, "not_before": None}, None
        value = stored.get("value") if isinstance(stored.get("value"), dict) else {}
        return ({"since_id": value.get("since_id"), "backfill_from": value.get("backfill_from"),
                 "not_before": value.get("not_before")}, stored["updated_at"])  # fmt: skip

    def _first_run_from(self) -> datetime | None:
        """§6.2: the oldest open SePay order's creation; when none is open, the date SePay sales began (its first
        order of any state). Never "now", which could skip older money (review P1-3A). None while SePay has never
        sold: there is nothing of Orena's to recover yet, and the cursor is not started."""

        oldest = self._orders.oldest_open_created_at(self._gateway.name)
        if oldest is None:
            oldest = self._orders.first_order_created_at(self._gateway.name)
        return oldest

    def _write(self, value: dict[str, Any], version: Any, counts: Counter[str]) -> Any:
        """A compare-and-set write of the cursor document; None when another writer moved it (nothing written)."""

        from writing_coach.persistence.platform_repository import SettingConflict

        try:
            return self._settings.set_setting(CURSOR_KEY, value, updated_by="billing-reconciler",
                                              expected_updated_at=version)["updated_at"]
        except SettingConflict:
            counts["sepay_feed_conflict"] += 1
            return None

    def step(self, counts: Counter[str], lock: Any = None) -> None:
        if not self.enabled:
            return
        cursor, version = self._cursor()
        not_before = cursor.get("not_before")
        if not_before and datetime.fromisoformat(not_before) > self._now():
            counts["sepay_feed_waiting"] += 1   # SePay asked us to wait (Retry-After): no request before then
            return
        if cursor["since_id"] is None and cursor["backfill_from"] is None:
            start = self._first_run_from()
            if start is None:
                counts["sepay_feed_no_orders"] += 1
                return
            cursor = {"since_id": None, "backfill_from": start.isoformat(), "not_before": None}
            version = self._write(cursor, version, counts)
            if version is None:
                return
        horizon = self._now() - self._settle
        for _ in range(self._iterations):
            if lock is not None and hasattr(lock, "alive") and not lock.alive():
                counts["lock_lost"] += 1
                return
            date_from = datetime.fromisoformat(cursor["backfill_from"]) if cursor["since_id"] is None else None
            request = self._gateway.feed_request(since_id=cursor["since_id"], date_from=date_from, per_page=PER_PAGE)
            try:
                answer = self._fetch(request)  # page 1, always
            except RateLimited as limited:
                counts["sepay_feed_rate_limited"] += 1
                wait = limited.retry_after if limited.retry_after and limited.retry_after > 0 else DEFAULT_RETRY_SECONDS
                # Honoured across ticks and workers (review P2-1): the wait is part of the cursor document.
                self._write({**cursor, "not_before": (self._now() + timedelta(seconds=wait)).isoformat()}, version,
                            counts)
                return
            rows = answer.get("data") if isinstance(answer, dict) else None
            if not isinstance(rows, list) or not rows:
                return
            # In order; stops at the settle delay; a failure raises and the cursor stays where it was.
            last_handled, settled_out = self._handle_page(rows, horizon, counts)
            if last_handled is not None:
                cursor = {"since_id": last_handled, "backfill_from": None, "not_before": None}
                version = self._write(cursor, version, counts)
                if version is None:
                    return   # another writer: stop, write nothing more
            if settled_out or last_handled is None or len(rows) < PER_PAGE:
                return

    def _handle_page(self, rows: list[Any], horizon: datetime, counts: Counter[str]) -> tuple[str | None, bool]:
        """Handle one page in order under the §6.3 rules: (the last handled row's id, whether the settle delay was
        reached). A row whose handling fails raises: nothing after it is handled."""

        last_handled, settled_out = None, False
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                raise ValueError("a feed row without an id")
            transfer = self._gateway.feed_transfer(row)
            if transfer.transaction_at is None or transfer.transaction_at > horizon:
                settled_out = True
                break
            eligible = (transfer.transfer_type == "in" and transfer.account_number == self._gateway.account_number
                        and row.get("webhook_success") in (0, None))  # fmt: skip
            if eligible:
                fact = self._gateway.to_fact(transfer, payload_digest=self._gateway.feed_row_digest(row))
                outcome = self._service.handle_fact(fact)
                counts[f"sepay_feed_{outcome.status}"] += 1
            else:
                counts["sepay_feed_skipped"] += 1
            last_handled = str(row["id"])
        return last_handled, settled_out

    def backfill(self, date_from: datetime, date_to: datetime, *, resume_after: str | None = None,
                 max_pages: int = MAX_BACKFILL_PAGES) -> dict[str, Any]:
        """§6.4: an operator's recovery of one date range, through the same §6.3 rules and the same payment path. It
        needs only the API token (it is the recovery path while the feed is off), and it never reads or moves the
        authoritative cursor: it walks its own range with `page=1` and a local `since_id`.

        A partial run never reads as a finished one (review P1-1 of `851f4bb9`). The result is
        `{"complete", "reason", "resume_after", "retry_after", "counts"}`:
        - `complete` is true only when SePay returned the range's last page (fewer rows than a page, or none);
        - otherwise `reason` is `page_cap` (the safety cap was reached while more rows may remain), `rate_limited`
          (SePay answered 429; `retry_after` is its wait) or `settle_delay` (the rest of the range is still inside the
          webhook retry window), and `resume_after` is the last row handled: the operator calls again with it and the
          run continues from there. Rows already handled are not asked for again, and a repeat is a duplicate."""

        if not self._gateway.has_api_token:
            raise PermissionError("SEPAY_API_TOKEN is not configured")
        if date_to <= date_from or date_to - date_from > MAX_BACKFILL_RANGE:
            raise ValueError(f"a backfill range is positive and at most {MAX_BACKFILL_RANGE.days} days")
        counts: Counter[str] = Counter()
        horizon = min(self._now() - self._settle, date_to)
        since_id = resume_after or None

        def incomplete(reason: str, retry_after: float | None = None) -> dict[str, Any]:
            return {"complete": False, "reason": reason, "resume_after": since_id, "retry_after": retry_after,
                    "counts": dict(counts)}

        for _ in range(max(1, int(max_pages))):
            request = self._gateway.feed_request(since_id=since_id, date_from=None if since_id else date_from,
                                                 date_to=date_to, per_page=PER_PAGE)
            try:
                answer = self._fetch(request)
            except RateLimited as limited:
                counts["sepay_backfill_rate_limited"] += 1
                return incomplete("rate_limited", limited.retry_after or DEFAULT_RETRY_SECONDS)
            rows = answer.get("data") if isinstance(answer, dict) else None
            if not isinstance(rows, list) or not rows:
                return {"complete": True, "reason": None, "resume_after": None, "retry_after": None,
                        "counts": dict(counts)}
            last_handled, settled_out = self._handle_page(rows, horizon, counts)
            if last_handled is not None:
                since_id = last_handled
            if settled_out:
                return incomplete("settle_delay")
            if len(rows) < PER_PAGE:
                return {"complete": True, "reason": None, "resume_after": None, "retry_after": None,
                        "counts": dict(counts)}
        return incomplete("page_cap")   # more rows may remain: never reported as a finished recovery
