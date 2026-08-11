import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.debtor_loan import DebtorLoan


class DebtorPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "debtor_payments"

    data_pagamento: Mapped[date] = mapped_column(Date, nullable=False)
    valor_pago: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    observacao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    emprestimo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("debtor_loans.id", ondelete="CASCADE"), index=True
    )

    emprestimo: Mapped["DebtorLoan"] = relationship("DebtorLoan", back_populates="pagamentos")
