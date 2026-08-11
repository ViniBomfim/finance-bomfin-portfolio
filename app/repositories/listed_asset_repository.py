from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.listed_asset import ListedAsset


class ListedAssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, asset_id: UUID) -> ListedAsset | None:
        return self.db.get(ListedAsset, asset_id)

    def list_all_ordered(self) -> list[ListedAsset]:
        stmt = select(ListedAsset).order_by(ListedAsset.tipo, ListedAsset.codigo)
        return list(self.db.scalars(stmt).all())
