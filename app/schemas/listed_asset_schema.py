from uuid import UUID

from pydantic import BaseModel


class ListedAssetResponse(BaseModel):
    id: UUID
    codigo: str
    nome: str
    tipo: str

    model_config = {"from_attributes": True}
