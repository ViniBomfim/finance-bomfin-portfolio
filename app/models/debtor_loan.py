import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.debtor_payment import DebtorPayment
    from app.models.spender import Spender
    from app.models.user import User


class DebtorLoan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "debtor_loans"

    devedor_nome: Mapped[str] = mapped_column(String(200), nullable=False)
    valor_emprestado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data_emprestimo: Mapped[date] = mapped_column(Date, nullable=False)
    destino_dinheiro: Mapped[str] = mapped_column(String(500), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    spender_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spenders.id", ondelete="SET NULL"), nullable=True, index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="debtor_loans")
    spender: Mapped["Spender | None"] = relationship("Spender")
    pagamentos: Mapped[list["DebtorPayment"]] = relationship(
        "DebtorPayment",
        back_populates="emprestimo",
        cascade="all, delete-orphan",
        order_by="DebtorPayment.data_pagamento.desc()",
    )
