import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentCreateRequest(BaseModel):
    """
    Cuerpo para crear un documento simple.
    """

    title: str
    content: str | None = None


class ShareDocumentRequest(BaseModel):
    """
    Cuerpo para compartir un documento con otro usuario.
    """

    user_id: uuid.UUID


class DocumentResponse(BaseModel):
    """
    Respuesta pública de documento.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content: str | None
    owner_id: uuid.UUID
    created_at: datetime


class ShareDocumentResponse(BaseModel):
    """
    Respuesta simple tras compartir un documento.
    """

    document_id: uuid.UUID
    shared_with_user_id: uuid.UUID
    message: str