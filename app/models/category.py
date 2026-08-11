import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.income import Income
    from app.models.expense import Expense


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    cor: Mapped[str] = mapped_column(String(32), nullable=False, default="#888888")
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # income | expense
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    user: Mapped["User"] = relationship("User", back_populates="categories")
    incomes: Mapped[list["Income"]] = relationship("Income", back_populates="categoria")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="categoria")
