import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Investment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investments"

    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # renda_fixa | stock | fii | crypto
    valor_aplicado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    valor_atual: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    quantidade: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    preco_medio: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    preco_unitario_atual: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    listed_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("listed_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    user: Mapped["User"] = relationship("User", back_populates="investments")
    listed_asset: Mapped["ListedAsset | None"] = relationship("ListedAsset")
