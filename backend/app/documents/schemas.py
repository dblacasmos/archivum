import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class DocumentMetadataUpsertRequest(BaseModel):
    """
    Cuerpo para crear o actualizar una metadata de documento.
    """

    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)


class DocumentMetadataResponse(BaseModel):
    """
    Respuesta pública de una metadata.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    meta_key: str
    meta_value: str
    created_at: datetime
    updated_at: datetime


class DocumentMetadataItemResponse(BaseModel):
    """
    Respuesta simplificada de metadata pensada para listados.
    """

    key: str
    value: str


class DocumentMetadataListResponse(BaseModel):
    """
    Respuesta agrupada con toda la metadata de un documento.
    """

    document_id: uuid.UUID
    items: list[DocumentMetadataItemResponse]


class DocumentVersionResponse(BaseModel):
    """
    Respuesta pública de una versión concreta.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    title: str
    content: str | None = None
    original_filename: str | None = None
    stored_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_by_user_id: uuid.UUID
    created_at: datetime


class DocumentVersionItemResponse(BaseModel):
    """
    Respuesta resumida para listados de versiones.
    """

    version_number: int
    title: str
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime


class DocumentVersionListResponse(BaseModel):
    """
    Respuesta agrupada con todo el historial de versiones.
    """

    document_id: uuid.UUID
    items: list[DocumentVersionItemResponse]


class DocumentTextExtractionResponse(BaseModel):
    """
    Respuesta pública del texto extraído de una versión.
    """

    document_id: uuid.UUID
    version_number: int
    extraction_status: str
    extracted_text: str
    extracted_at: datetime | None = None
    characters_count: int


class DocumentResponse(BaseModel):
    """
    Respuesta pública de documento.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "uuid",
                "title": "Manual de usuario",
                "content": None,
                "original_filename": "documento.pdf",
                "stored_filename": "uuid_documento.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 12345,
                "owner_id": "uuid",
                "created_at": "2026-04-12T18:00:00Z",
            }
        },
    )

    id: uuid.UUID
    title: str
    content: str | None = None
    original_filename: str | None = None
    stored_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    owner_id: uuid.UUID
    created_at: datetime


class ShareDocumentResponse(BaseModel):
    """
    Respuesta simple tras compartir un documento.
    """

    document_id: uuid.UUID
    shared_with_user_id: uuid.UUID
    message: str


class DocumentChunkResponse(BaseModel):
    """
    Respuesta pública de un chunk concreto.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    content: str
    char_count: int
    start_char: int
    end_char: int
    created_at: datetime


class DocumentChunkItemResponse(BaseModel):
    """
    Respuesta resumida para listados de chunks.
    """

    chunk_index: int
    content: str
    char_count: int
    start_char: int
    end_char: int


class DocumentChunkListResponse(BaseModel):
    """
    Respuesta agrupada con todos los chunks de una versión.
    """

    document_id: uuid.UUID
    version_number: int
    chunk_size: int
    chunk_overlap: int
    total_chunks: int
    items: list[DocumentChunkItemResponse]


class PipelineJobResponse(BaseModel):
    """
    Respuesta pública del estado de un job del pipeline.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_number: int
    status: str
    current_step: str
    chunk_size: int
    chunk_overlap: int
    total_chunks: int | None = None
    ready_for_vectorization: bool
    error_message: str | None = None
    created_by_user_id: uuid.UUID
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class PipelineJobStartResponse(BaseModel):
    """
    Respuesta al lanzar el pipeline.
    """

    message: str
    job: PipelineJobResponse