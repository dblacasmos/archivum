import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import get_current_active_user
from app.core.db import get_session
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.embedding_schemas import (
    DocumentEmbeddingItemResponse,
    DocumentEmbeddingListResponse,
)
from app.documents.embeddings import DocumentEmbeddingService, OpenAIEmbeddingClient
from app.documents.repository import DocumentRepository

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_embedding_service(
    session: Session = Depends(get_session),
) -> DocumentEmbeddingService:
    """
    Construye el servicio de embeddings de R40.
    """
    document_repo = DocumentRepository(session)
    embedding_repo = DocumentEmbeddingRepository(session)
    embedding_client = OpenAIEmbeddingClient()

    return DocumentEmbeddingService(
        document_repo=document_repo,
        embedding_repo=embedding_repo,
        embedding_client=embedding_client,
    )


def build_embedding_list_response(
    document_id: uuid.UUID,
    version_number: int,
    embeddings,
) -> DocumentEmbeddingListResponse:
    """
    Convierte los embeddings ORM en una respuesta limpia de API.
    """
    items: list[DocumentEmbeddingItemResponse] = []

    for item in embeddings:
        items.append(
            DocumentEmbeddingItemResponse(
                chunk_id=item.chunk_id,
                chunk_index=item.chunk.chunk_index,
                provider=item.provider,
                model_name=item.model_name,
                dimensions=item.dimensions,
                generated_at=item.generated_at,
            )
        )

    return DocumentEmbeddingListResponse(
        document_id=document_id,
        version_number=version_number,
        total_embeddings=len(items),
        items=items,
    )


@router.post(
    "/{document_id}/versions/{version_number}/embeddings",
    response_model=DocumentEmbeddingListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_embeddings_for_document_version(
    document_id: uuid.UUID,
    version_number: int,
    model_name: str | None = None,
    service: DocumentEmbeddingService = Depends(get_document_embedding_service),
    current_user=Depends(get_current_active_user),
):
    """
    Genera embeddings para todos los chunks de una versión concreta.
    """
    try:
        embeddings = service.generate_embeddings_for_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
            model_name=model_name,
        )

        return build_embedding_list_response(
            document_id=document_id,
            version_number=version_number,
            embeddings=embeddings,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}/versions/{version_number}/embeddings",
    response_model=DocumentEmbeddingListResponse,
)
async def get_embeddings_for_document_version(
    document_id: uuid.UUID,
    version_number: int,
    service: DocumentEmbeddingService = Depends(get_document_embedding_service),
    current_user=Depends(get_current_active_user),
):
    """
    Recupera los embeddings ya persistidos para una versión concreta.
    """
    try:
        embeddings = service.get_embeddings_for_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
        )

        return build_embedding_list_response(
            document_id=document_id,
            version_number=version_number,
            embeddings=embeddings,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc