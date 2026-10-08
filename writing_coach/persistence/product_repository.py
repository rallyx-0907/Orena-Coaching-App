from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from writing_coach.persistence.config import create_shadow_engine
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import Subscription, UsageEvent, User
from writing_coach.product.repository import ProductRepository, SubscriptionRecord, utc_day_bounds


class PostgresProductRepository(ProductRepository):
    """SQLAlchemy/PostgreSQL implementation of the authoritative product contract."""

    def __init__(self, engine: Engine | None = None, *, url: str | None = None) -> None:
        self.engine = engine or create_shadow_engine(url)

    def _user_id(self, user_key: str):
        return stable_uuid("user", user_key)

    def _ensure_user(self, session: Session, user_key: str) -> User:
        uid = self._user_id(user_key)
        item = session.get(User, uid)
        if item is None:
            now = datetime.now(timezone.utc)
            item = User(
                id=uid,
                user_key=user_key,
                email="",
                name="",
                picture="",
                role="user",
                created_at=now,
                last_login=None,
            )
            session.add(item)
            session.flush()
        return item

    def get_subscription(self, user_key: str) -> SubscriptionRecord | None:
        if not user_key:
            return None
        uid = self._user_id(user_key)
        with Session(self.engine) as session:
            row = session.scalar(select(Subscription).where(Subscription.user_id == uid))
            if row is None:
                return None
            return SubscriptionRecord(
                user_key=user_key,
                plan_id=row.plan_id,
                status=row.status,
                provider=row.provider,
                external_customer_id=row.external_customer_id,
                external_subscription_id=row.external_subscription_id,
                current_period_end=(row.current_period_end.isoformat() if row.current_period_end else ""),
                updated_at=row.updated_at.isoformat(),
            )

    def record_usage(
        self,
        *,
        user_key: str,
        feature: str,
        amount: int,
        request_id: str = "",
    ) -> None:
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            user = self._ensure_user(session, user_key)
            session.add(
                UsageEvent(
                    id=stable_uuid("usage", user_key, feature, request_id, now.isoformat()),
                    user_id=user.id,
                    feature=feature,
                    amount=max(0, int(amount)),
                    request_id=request_id,
                    occurred_at=now,
                )
            )

    def monthly_usage(self, *, user_key: str, feature: str) -> int:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        uid = self._user_id(user_key)
        with Session(self.engine) as session:
            total = session.scalar(
                select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(
                    UsageEvent.user_id == uid,
                    UsageEvent.feature == feature,
                    UsageEvent.occurred_at >= month_start,
                )
            )
        return int(total or 0)

    def daily_usage(self, *, user_key: str, feature: str, day: date | None = None) -> int:
        """The feature's usage on one UTC calendar day (today by default)."""

        start, end = utc_day_bounds(day)
        uid = self._user_id(user_key)
        with Session(self.engine) as session:
            total = session.scalar(
                select(func.coalesce(func.sum(UsageEvent.amount), 0)).where(
                    UsageEvent.user_id == uid,
                    UsageEvent.feature == feature,
                    UsageEvent.occurred_at >= start,
                    UsageEvent.occurred_at < end,
                )
            )
        return int(total or 0)
