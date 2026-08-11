import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class AccountStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"


if TYPE_CHECKING:
    from app.models.period import Period
    from app.models.category import Category
    from app.models.debtor_loan import DebtorLoan
    from app.models.investment import Investment
    from app.models.spender import Spender
    from app.models.trip import Trip


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    account_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=AccountStatus.ACTIVE.value,
        server_default=AccountStatus.ACTIVE.value,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    notifications_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    me_spender_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("spenders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    goal_pool_withdrawn_to_income: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    avatar_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)

    @property
    def has_avatar(self) -> bool:
        return bool(self.avatar_bytes)

    periods: Mapped[list["Period"]] = relationship("Period", back_populates="user", cascade="all, delete-orphan")
    categories: Mapped[list["Category"]] = relationship(
        "Category", back_populates="user", cascade="all, delete-orphan"
    )
    investments: Mapped[list["Investment"]] = relationship(
        "Investment", back_populates="user", cascade="all, delete-orphan"
    )
    debtor_loans: Mapped[list["DebtorLoan"]] = relationship(
        "DebtorLoan", back_populates="user", cascade="all, delete-orphan"
    )
    spenders: Mapped[list["Spender"]] = relationship(
        "Spender",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Spender.user_id",
    )
    me_spender: Mapped["Spender | None"] = relationship(
        "Spender",
        foreign_keys=[me_spender_id],
        post_update=True,
    )
    trips: Mapped[list["Trip"]] = relationship(
        "Trip", back_populates="user", cascade="all, delete-orphan"
    )
