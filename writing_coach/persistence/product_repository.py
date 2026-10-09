from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from writing_coach.persistence.config import create_shadow_engine
from writing_coach.persistence.ids import stable_uuid
import uuid

from writing_coach.persistence.models import PlanRecord, Subscription, UsageEvent, User
from writing_coach.product.catalog import PLANS
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

    # --- D-154: an administrator sets an account's role and plan by hand -----------------------------------------
    @staticmethod
    def _account_uuid(user_id: str):
        try:
            return uuid.UUID(str(user_id))
        except (TypeError, ValueError):
            return None

    def account_membership(self, user_id: str) -> dict | None:
        identifier = self._account_uuid(user_id)
        if identifier is None:
            return None
        with Session(self.engine) as session:
            user = session.get(User, identifier)
            if user is None:
                return None
            row = session.scalar(select(Subscription).where(Subscription.user_id == identifier))
            return {
                "id": str(user.id),
                "user_key": user.user_key,
                "email": user.email,
                "role": user.role,
                "plan_id": row.plan_id if row else None,
                "status": row.status if row else None,
                "provider": row.provider if row else None,
                "until": row.current_period_end.isoformat() if row and row.current_period_end else None,
            }

    def apply_membership(self, user_id: str, *, role: str | None = None, plan: object = ..., until=None,
                         audit: dict | None = None) -> None:
        """Role and/or plan for one account, and its audit row, in ONE transaction (review of #112).

        The account and subscription rows are locked (`SELECT ... FOR UPDATE`) and the subscription is read again under
        the lock: a billing subscription that became active after the caller validated is refused here, never
        overwritten. Any failure - the refusal, a write, the audit row - rolls the whole change back.
        `plan`: `...` leaves the plan alone, None removes a manual subscription (Free), an id sets a manual one."""
        from writing_coach.persistence.platform_repository import _add_audit
        from writing_coach.product.membership import MANUAL_PROVIDER, MembershipConflict

        identifier = self._account_uuid(user_id)
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            user = session.scalar(select(User).where(User.id == identifier).with_for_update()) if identifier else None
            if user is None:
                raise LookupError("No account has this identifier.")
            if plan is not ...:
                row = session.scalar(select(Subscription).where(Subscription.user_id == identifier).with_for_update())
                if row is not None and row.provider and row.provider != MANUAL_PROVIDER and row.status in {"active", "trialing"}:
                    raise MembershipConflict("This account's plan is managed by billing; it cannot be set by hand.")
            if role is not None:
                user.role = role
            if plan is not ...:
                if plan is None:
                    if row is not None and row.provider == MANUAL_PROVIDER:
                        session.delete(row)
                else:
                    record = PLANS[plan]
                    if session.get(PlanRecord, plan) is None:
                        # The plans table is seeded by the importer; Plus and Pro may be newer than that seed (FK target).
                        session.add(PlanRecord(id=record.id, name=record.name, description=record.description,
                                               price_label=record.price_label, active=True))
                        session.flush()
                    if row is None:
                        session.add(Subscription(
                            id=stable_uuid("subscription", str(identifier)), user_id=identifier, plan_id=plan, status="active",
                            provider=MANUAL_PROVIDER, external_customer_id="", external_subscription_id="",
                            current_period_end=until, updated_at=now,
                        ))
                    else:
                        row.plan_id = plan
                        row.status = "active"
                        row.provider = MANUAL_PROVIDER
                        row.external_customer_id = ""
                        row.external_subscription_id = ""
                        row.current_period_end = until
                        row.updated_at = now
            if audit:
                _add_audit(session, audit, now)
