from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class ListedAsset(UUIDPrimaryKeyMixin, Base):
    """Catálogo global de ativos negociáveis (referência para posições)."""

    __tablename__ = "listed_assets"

    codigo: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
