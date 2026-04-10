import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.security import get_current_active_user
from app.core.db import get_session
from app.documents.repository import DocumentRepository
from app.documents.schemas import (
    DocumentCreateRequest,
    DocumentResponse,
    ShareDocumentRequest,
    ShareDocumentResponse,
)
from app.documents.service import DocumentService
from app.users.repository import UserRepository

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(session: Session = Depends(get_session)) -> DocumentService:
    """
    Construye el servicio de documentos con sus dependencias.
    """
    document_repo = DocumentRepository(session)
    user_repo = UserRepository(session)
    return DocumentService(document_repo=document_repo, user_repo=user_repo)


async def read_upload_content_as_text(upload_file: UploadFile | None) -> str | None:
    """
    Lee el contenido del archivo subido como texto simple.

    Este endpoint se plantea como apoyo a R14 para proteger /documents/upload.
    No pretende sustituir todavía al flujo completo de R20/R30.
    """
    if upload_file is None:
        return None

    raw_bytes = await upload_file.read()
    if not raw_bytes:
        return None

    return raw_bytes.decode("utf-8", errors="ignore")


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreateRequest,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Crea un documento.
    Solo admin o editor pueden hacerlo.
    """
    try:
        return service.create_document(
            current_user=current_user,
            title=body.title,
            content=body.content,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str = Form(...),
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Endpoint puente para R14 y R20.

    Permite subir un documento por multipart/form-data.
    Si llega un archivo, se intenta leer como texto.
    Si además llega el campo content, ese texto tiene prioridad.
    """
    try:
        file_text = await read_upload_content_as_text(file)
        final_content = content if content is not None else file_text

        return service.create_document(
            current_user=current_user,
            title=title,
            content=final_content,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Lista únicamente los documentos visibles para el usuario autenticado.
    """
    return service.list_visible_documents(current_user=current_user)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Devuelve un documento solo si el usuario tiene permiso para leerlo.
    """
    try:
        return service.get_document_for_read(
            current_user=current_user,
            document_id=document_id,
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


@router.post("/{document_id}/share", response_model=ShareDocumentResponse)
async def share_document(
    document_id: uuid.UUID,
    body: ShareDocumentRequest,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Comparte un documento con otro usuario.
    Solo owner o admin pueden hacerlo.
    """
    try:
        access = service.share_document(
            current_user=current_user,
            document_id=document_id,
            target_user_id=body.user_id,
        )

        return ShareDocumentResponse(
            document_id=access.document_id,
            shared_with_user_id=access.user_id,
            message="Documento compartido correctamente",
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