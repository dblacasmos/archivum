import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.security import get_current_active_user
from app.core.db import SessionLocal, get_session
from app.documents.chunking import TextChunkingService
from app.documents.extraction import TextExtractionService
from app.documents.pipeline_repository import PipelineJobRepository
from app.documents.pipeline_service import PipelineService
from app.documents.repository import DocumentRepository
from app.documents.schemas import (
    DocumentChunkItemResponse,
    DocumentChunkListResponse,
    DocumentCreateRequest,
    DocumentMetadataItemResponse,
    DocumentMetadataListResponse,
    DocumentMetadataResponse,
    DocumentMetadataUpsertRequest,
    DocumentResponse,
    DocumentTextExtractionResponse,
    DocumentVersionItemResponse,
    DocumentVersionListResponse,
    DocumentVersionResponse,
    PipelineJobResponse,
    PipelineJobStartResponse,
    ShareDocumentRequest,
    ShareDocumentResponse,
)
from app.documents.service import DocumentService
from app.documents.storage import DocumentStorageService
from app.users.repository import UserRepository

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_service(session: Session = Depends(get_session)) -> DocumentService:
    """
    Construye el servicio de documentos con todas sus dependencias.
    """
    document_repo = DocumentRepository(session)
    user_repo = UserRepository(session)
    storage_service = DocumentStorageService()
    extraction_service = TextExtractionService()
    chunking_service = TextChunkingService()

    return DocumentService(
        document_repo=document_repo,
        user_repo=user_repo,
        storage_service=storage_service,
        extraction_service=extraction_service,
        chunking_service=chunking_service,
    )


def get_pipeline_service(session: Session = Depends(get_session)) -> PipelineService:
    """
    Construye el servicio específico del pipeline asíncrono.
    """
    document_repo = DocumentRepository(session)
    job_repo = PipelineJobRepository(session)
    extraction_service = TextExtractionService()
    chunking_service = TextChunkingService()

    return PipelineService(
        document_repo=document_repo,
        job_repo=job_repo,
        extraction_service=extraction_service,
        chunking_service=chunking_service,
        session_factory=SessionLocal,
    )


def build_text_extraction_response(version) -> DocumentTextExtractionResponse:
    """
    Convierte una versión con texto extraído en una respuesta limpia de API.
    """
    extracted_text = version.extracted_text or ""

    return DocumentTextExtractionResponse(
        document_id=version.document_id,
        version_number=version.version_number,
        extraction_status=version.extraction_status,
        extracted_text=extracted_text,
        extracted_at=version.extracted_at,
        characters_count=len(extracted_text),
    )


def build_pipeline_job_response(job) -> PipelineJobResponse:
    """
    Convierte un job ORM en una respuesta pública de API.
    """
    return PipelineJobResponse(
        id=job.id,
        document_id=job.document_id,
        document_version_id=job.document_version_id,
        version_number=job.version_number,
        status=job.status,
        current_step=job.current_step,
        chunk_size=job.chunk_size,
        chunk_overlap=job.chunk_overlap,
        total_chunks=job.total_chunks,
        ready_for_vectorization=job.ready_for_vectorization,
        error_message=job.error_message,
        created_by_user_id=job.created_by_user_id,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    body: DocumentCreateRequest,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Crea un documento lógico simple.
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
    title: str | None = Form(None),
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Endpoint de subida de documentos.
    Permite subir un archivo real o crear un documento a partir de texto.
    """
    try:
        if file is not None and file.filename:
            return await service.upload_document(
                current_user=current_user,
                upload_file=file,
                title=title,
            )

        if content is not None and title is not None:
            return service.create_document(
                current_user=current_user,
                title=title,
                content=content,
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes enviar un archivo o, como mínimo, título y contenido",
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


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Lista únicamente los documentos visibles para el usuario autenticado.
    """
    return service.list_visible_documents(current_user=current_user)


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


@router.post(
    "/{document_id}/metadata",
    response_model=DocumentMetadataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_document_metadata(
    document_id: uuid.UUID,
    body: DocumentMetadataUpsertRequest,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Crea o actualiza una metadata básica de un documento.
    """
    try:
        return service.upsert_document_metadata(
            current_user=current_user,
            document_id=document_id,
            meta_key=body.key,
            meta_value=body.value,
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
    "/{document_id}/metadata",
    response_model=DocumentMetadataListResponse,
)
async def list_document_metadata(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Devuelve toda la metadata asociada a un documento.
    """
    try:
        metadata_entries = service.list_document_metadata(
            current_user=current_user,
            document_id=document_id,
        )

        return DocumentMetadataListResponse(
            document_id=document_id,
            items=[
                DocumentMetadataItemResponse(
                    key=item.meta_key,
                    value=item.meta_value,
                )
                for item in metadata_entries
            ],
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


@router.get(
    "/{document_id}/metadata/{meta_key}",
    response_model=DocumentMetadataResponse,
)
async def get_document_metadata_by_key(
    document_id: uuid.UUID,
    meta_key: str,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Devuelve una metadata concreta de un documento según su clave.
    """
    try:
        return service.get_document_metadata_by_key(
            current_user=current_user,
            document_id=document_id,
            meta_key=meta_key,
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


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_version(
    document_id: uuid.UUID,
    title: str | None = Form(None),
    content: str | None = Form(None),
    file: UploadFile | None = File(None),
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Crea una nueva versión de un documento existente.
    """
    try:
        return await service.create_document_version(
            current_user=current_user,
            document_id=document_id,
            title=title,
            content=content,
            upload_file=file,
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
    "/{document_id}/versions",
    response_model=DocumentVersionListResponse,
)
async def list_document_versions(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Devuelve el historial de versiones de un documento.
    """
    try:
        versions = service.list_document_versions(
            current_user=current_user,
            document_id=document_id,
        )

        return DocumentVersionListResponse(
            document_id=document_id,
            items=[
                DocumentVersionItemResponse(
                    version_number=item.version_number,
                    title=item.title,
                    original_filename=item.original_filename,
                    mime_type=item.mime_type,
                    size_bytes=item.size_bytes,
                    created_at=item.created_at,
                )
                for item in versions
            ],
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


@router.get(
    "/{document_id}/versions/{version_number}",
    response_model=DocumentVersionResponse,
)
async def get_document_version(
    document_id: uuid.UUID,
    version_number: int,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Devuelve una versión concreta de un documento.
    """
    try:
        return service.get_document_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
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


@router.post(
    "/{document_id}/versions/{version_number}/extract-text",
    response_model=DocumentTextExtractionResponse,
)
async def extract_text_from_document_version(
    document_id: uuid.UUID,
    version_number: int,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Ejecuta la extracción de texto sobre una versión concreta
    y persiste el resultado.
    """
    try:
        version = service.extract_text_from_document_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
        )
        return build_text_extraction_response(version)
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
    "/{document_id}/versions/{version_number}/extract-text",
    response_model=DocumentTextExtractionResponse,
)
async def get_extracted_text_from_document_version(
    document_id: uuid.UUID,
    version_number: int,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Recupera el texto extraído ya persistido para una versión concreta.
    """
    try:
        version = service.get_extracted_text_for_document_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
        )
        return build_text_extraction_response(version)
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


@router.post(
    "/{document_id}/versions/{version_number}/chunk-text",
    response_model=DocumentChunkListResponse,
)
async def chunk_text_from_document_version(
    document_id: uuid.UUID,
    version_number: int,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Divide el texto extraído de una versión en chunks y los persiste.
    """
    try:
        chunks = service.chunk_document_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        return DocumentChunkListResponse(
            document_id=document_id,
            version_number=version_number,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            total_chunks=len(chunks),
            items=[
                DocumentChunkItemResponse(
                    chunk_index=item.chunk_index,
                    content=item.content,
                    char_count=item.char_count,
                    start_char=item.start_char,
                    end_char=item.end_char,
                )
                for item in chunks
            ],
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
    "/{document_id}/versions/{version_number}/chunk-text",
    response_model=DocumentChunkListResponse,
)
async def get_chunks_from_document_version(
    document_id: uuid.UUID,
    version_number: int,
    service: DocumentService = Depends(get_document_service),
    current_user=Depends(get_current_active_user),
):
    """
    Recupera los chunks ya persistidos de una versión concreta.
    """
    try:
        chunks = service.get_chunks_for_document_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
        )

        if len(chunks) >= 2:
            inferred_chunk_size = max(chunks[0].char_count, chunks[1].char_count)
            inferred_overlap = max(0, chunks[0].end_char - chunks[1].start_char)
        elif len(chunks) == 1:
            inferred_chunk_size = chunks[0].char_count
            inferred_overlap = 0
        else:
            inferred_chunk_size = 0
            inferred_overlap = 0

        return DocumentChunkListResponse(
            document_id=document_id,
            version_number=version_number,
            chunk_size=inferred_chunk_size,
            chunk_overlap=inferred_overlap,
            total_chunks=len(chunks),
            items=[
                DocumentChunkItemResponse(
                    chunk_index=item.chunk_index,
                    content=item.content,
                    char_count=item.char_count,
                    start_char=item.start_char,
                    end_char=item.end_char,
                )
                for item in chunks
            ],
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


@router.post(
    "/{document_id}/versions/{version_number}/pipeline",
    response_model=PipelineJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_pipeline_for_document_version(
    document_id: uuid.UUID,
    version_number: int,
    background_tasks: BackgroundTasks,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    service: PipelineService = Depends(get_pipeline_service),
    current_user=Depends(get_current_active_user),
):
    """
    Lanza el pipeline en segundo plano para una versión concreta.

    La respuesta devuelve un job en estado pendiente
    para que el cliente pueda consultar su evolución.
    """
    try:
        job = service.start_pipeline_for_version(
            current_user=current_user,
            document_id=document_id,
            version_number=version_number,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        background_tasks.add_task(service.run_pipeline_job, job.id)

        return PipelineJobStartResponse(
            message="Pipeline lanzado correctamente en segundo plano",
            job=build_pipeline_job_response(job),
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
    "/pipeline-jobs/{job_id}",
    response_model=PipelineJobResponse,
)
async def get_pipeline_job_status(
    job_id: uuid.UUID,
    service: PipelineService = Depends(get_pipeline_service),
    current_user=Depends(get_current_active_user),
):
    """
    Devuelve el estado actual de un job del pipeline.
    """
    try:
        job = service.get_pipeline_job_for_read(
            current_user=current_user,
            job_id=job_id,
        )
        return build_pipeline_job_response(job)
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