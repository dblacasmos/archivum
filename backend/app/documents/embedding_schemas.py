import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentEmbeddingItemResponse(BaseModel):
    """
    Respuesta pública de un embedding individual.
    """

    chunk_id: uuid.UUID
    chunk_index: int
    provider: str
    model_name: str
    dimensions: int
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentEmbeddingListResponse(BaseModel):
    """
    Respuesta pública con todos los embeddings de una versión.
    """

    document_id: uuid.UUID
    version_number: int
    total_embeddings: int
    items: list[DocumentEmbeddingItemResponse]