"""Usage summed per UTC day beside per month (R5: the agent is counted, never refused)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine

from writing_coach.persistence.models import Base
from writing_coach.persistence.product_repository import PostgresProductRepository
from writing_coach.product.repository import SQLiteProductRepository, utc_day_bounds


def _exercise(repository) -> None:
    today = datetime.now(UTC).date()
    repository.record_usage(user_key="u1", feature="agent.turn", amount=1, request_id="t1:agent.turn")
    repository.record_usage(user_key="u1", feature="agent.turn", amount=1, request_id="t2:agent.turn")
    repository.record_usage(user_key="u1", feature="agent.tokens", amount=640, request_id="t1:agent.tokens")
    repository.record_usage(user_key="u2", feature="agent.turn", amount=1, request_id="t3:agent.turn")
    assert repository.daily_usage(user_key="u1", feature="agent.turn") == 2
    assert repository.daily_usage(user_key="u1", feature="agent.turn", day=today) == 2
    assert repository.daily_usage(user_key="u1", feature="agent.tokens") == 640
    assert repository.daily_usage(user_key="u1", feature="agent.turn", day=today - timedelta(days=1)) == 0
    assert repository.daily_usage(user_key="u3", feature="agent.turn") == 0
    assert repository.monthly_usage(user_key="u1", feature="agent.turn") == 2


def test_sqlite_store_counts_by_day(tmp_path):
    repository = SQLiteProductRepository(tmp_path / "product.db")
    repository.init_schema()
    _exercise(repository)


def test_postgres_store_counts_by_day_on_the_test_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    _exercise(PostgresProductRepository(engine=engine))


def test_a_day_is_a_utc_calendar_day():
    day = datetime(2026, 9, 27, tzinfo=UTC).date()
    start, end = utc_day_bounds(day)
    assert start == datetime(2026, 9, 27, tzinfo=UTC) and end - start == timedelta(days=1)
