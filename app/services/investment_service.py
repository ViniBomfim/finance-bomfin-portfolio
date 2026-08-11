from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.investment import Investment
from app.models.listed_asset import ListedAsset
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.listed_asset_repository import ListedAssetRepository
from app.schemas.investment_schema import InvestmentCreate, InvestmentUpdate


def _asset_display_label(asset: ListedAsset) -> str:
    label = f"{asset.codigo} — {asset.nome}"
    return label[:200]


def _money2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sync_fii_totals(row: Investment) -> None:
    """Se FII com cotas e preços completos, recalcula valor aplicado e posição (valor atual)."""
    if row.tipo != "fii":
        return
    q = row.quantidade
    pm = row.preco_medio
    pu = row.preco_unitario_atual
    if q is None or pm is None or pu is None:
        return
    if q <= 0:
        return
    row.valor_aplicado = _money2(q * pm)
    row.valor_atual = _money2(q * pu)


class InvestmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = InvestmentRepository(db)
        self._listed = ListedAssetRepository(db)

    def list(self, user_id: UUID) -> list[Investment]:
        return self._repo.list_by_user(user_id)

    def total_patrimonio(self, user_id: UUID) -> float:
        return self._repo.sum_valor_atual(user_id)

    def create(self, user_id: UUID, data: InvestmentCreate) -> Investment:
        listed_asset_id: UUID | None = None
        descricao: str
        tipo: str

        if data.listed_asset_id is not None:
            asset = self._listed.get_by_id(data.listed_asset_id)
            if asset is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ativo não encontrado no cadastro")
            descricao = _asset_display_label(asset)
            tipo = asset.tipo
            listed_asset_id = asset.id
        else:
            descricao = (data.descricao or "").strip()
            if data.tipo is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo obrigatório")
            tipo = data.tipo

        qty = data.quantidade
        pm = data.preco_medio
        pu = data.preco_unitario_atual

        if tipo == "fii" and qty is not None and pm is not None and pu is not None:
            valor_aplicado = _money2(qty * pm)
            valor_atual = _money2(qty * pu)
        else:
            valor_aplicado = data.valor_aplicado
            valor_atual = data.valor_atual

        row = Investment(
            descricao=descricao,
            tipo=tipo,
            valor_aplicado=valor_aplicado,
            valor_atual=valor_atual,
            quantidade=qty if tipo == "fii" else None,
            preco_medio=pm if tipo == "fii" else None,
            preco_unitario_atual=pu if tipo == "fii" else None,
            listed_asset_id=listed_asset_id,
            user_id=user_id,
        )
        _sync_fii_totals(row)
        return self._repo.create(row)

    def update(self, user_id: UUID, investment_id: UUID, data: InvestmentUpdate) -> Investment:
        row = self._repo.get_by_id(investment_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")

        patch = data.model_dump(exclude_unset=True)

        if "listed_asset_id" in patch:
            if data.listed_asset_id is not None:
                asset = self._listed.get_by_id(data.listed_asset_id)
                if asset is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ativo não encontrado no cadastro")
                row.descricao = _asset_display_label(asset)
                row.tipo = asset.tipo
                row.listed_asset_id = data.listed_asset_id
            else:
                row.listed_asset_id = None
                if data.descricao is not None:
                    row.descricao = data.descricao.strip()
                if data.tipo is not None:
                    row.tipo = data.tipo
        else:
            if data.descricao is not None:
                row.descricao = data.descricao.strip()
            if data.tipo is not None:
                row.tipo = data.tipo

        if row.tipo != "fii":
            row.quantidade = None
            row.preco_medio = None
            row.preco_unitario_atual = None

        if row.tipo == "fii":
            if data.quantidade is not None:
                row.quantidade = data.quantidade
            if data.preco_medio is not None:
                row.preco_medio = data.preco_medio
            if data.preco_unitario_atual is not None:
                row.preco_unitario_atual = data.preco_unitario_atual

        if data.valor_aplicado is not None:
            row.valor_aplicado = data.valor_aplicado
        if data.valor_atual is not None:
            row.valor_atual = data.valor_atual

        _sync_fii_totals(row)

        return self._repo.update(row)

    def delete(self, user_id: UUID, investment_id: UUID) -> None:
        row = self._repo.get_by_id(investment_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment not found")
        self._repo.delete(row)
