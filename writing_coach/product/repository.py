from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DB_PATH = Path(os.getenv("PRODUCT_DB", ROOT / "data" / "product.db"))


@dataclass(frozen=True)
class SubscriptionRecord:
    user_key: str
    plan_id: str
    status: str
    provider: str
    external_customer_id: str
    external_subscription_id: str
    current_period_end: str
    updated_at: str


class ProductRepository(Protocol):
    def get_subscription(self, user_key: str) -> SubscriptionRecord | None: ...
    def record_usage(
        self,
        *,
        user_key: str,
        feature: str,
        amount: int,
        request_id: str = "",
    ) -> None: ...
    def monthly_usage(self, *, user_key: str, feature: str) -> int: ...
    def daily_usage(self, *, user_key: str, feature: str, day: date | None = None) -> int: ...


class SQLiteProductRepository:
    """Transitional centralized product store.

    Product/business logic depends on this repository interface, not on SQLite.
    A PostgreSQL implementation can replace it without changing callers.
    """

    def __init__(self, path: Path = PRODUCT_DB_PATH) -> None:
        self.path = path
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_key TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    provider TEXT NOT NULL DEFAULT '',
                    external_customer_id TEXT NOT NULL DEFAULT '',
                    external_subscription_id TEXT NOT NULL DEFAULT '',
                    current_period_end TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    amount INTEGER NOT NULL DEFAULT 1,
                    request_id TEXT NOT NULL DEFAULT '',
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_usage_user_feature_time
                ON usage_events(user_key, feature, occurred_at);
                """
            )
            conn.commit()

    def get_subscription(self, user_key: str) -> SubscriptionRecord | None:
        if not user_key:
            return None
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE user_key = ?",
                (user_key,),
            ).fetchone()
        return SubscriptionRecord(**dict(row)) if row else None

    def record_usage(
        self,
        *,
        user_key: str,
        feature: str,
        amount: int,
        request_id: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO usage_events(user_key, feature, amount, request_id, occurred_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_key, feature, max(0, int(amount)), request_id, now),
            )
            conn.commit()

    def monthly_usage(self, *, user_key: str, feature: str) -> int:
        now = datetime.now(timezone.utc)
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM usage_events
                WHERE user_key = ? AND feature = ? AND occurred_at >= ?
                """,
                (user_key, feature, month_start),
            ).fetchone()
        return int(row["total"] if row else 0)

    def daily_usage(self, *, user_key: str, feature: str, day: date | None = None) -> int:
        """The feature's usage on one UTC calendar day (today by default)."""

        start, end = utc_day_bounds(day)
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM usage_events
                WHERE user_key = ? AND feature = ? AND occurred_at >= ? AND occurred_at < ?
                """,
                (user_key, feature, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")),
            ).fetchone()
        return int(row["total"] if row else 0)


def utc_day_bounds(day: date | None = None) -> tuple[datetime, datetime]:
    """[start, end) of a UTC calendar day, the boundary both usage stores count by."""

    chosen = day or datetime.now(UTC).date()
    start = datetime(chosen.year, chosen.month, chosen.day, tzinfo=UTC)
    return start, start + timedelta(days=1)
