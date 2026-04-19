import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.documents.chunking import TextChunkingService
from app.documents.extraction import TextExtractionService
from app.documents.models import Document, PipelineJob
from app.documents.pipeline_repository import PipelineJobRepository
from app.documents.repository import DocumentRepository


class PipelineService:
    """
    Servicio que coordina el pipeline asíncrono de R32.

    Flujo:
    1. Crear job pendiente
    2. Ejecutar extracción de texto
    3. Ejecutar chunking
    4. Marcar la versión como lista para vectorización
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        job_repo: PipelineJobRepository,
        extraction_service: TextExtractionService,
        chunking_service: TextChunkingService,
        session_factory: Callable[[], Session] = SessionLocal,
    ):
        self.document_repo = document_repo
        self.job_repo = job_repo
        self.extraction_service = extraction_service
        self.chunking_service = chunking_service
        self.session_factory = session_factory

    def _get_role_names(self, user) -> set[str]:
        """
        Devuelve los roles del usuario como conjunto.
        """
        return {role.name for role in user.roles}

    def _is_admin(self, user) -> bool:
        """
        Comprueba si el usuario es administrador.
        """
        return "admin" in self._get_role_names(user)

    def _can_manage_pipeline(self, user, document: Document) -> bool:
        """
        Solo admin y owner pueden lanzar el pipeline porque
        modifica información persistida del sistema.
        """
        if self._is_admin(user):
            return True

        return document.owner_id == user.id

    def _can_read_pipeline_job(self, user, document: Document) -> bool:
        """
        Reglas de lectura del estado del pipeline:
        - admin puede ver todo
        - owner puede ver sus jobs
        - usuario con acceso explícito puede consultar el estado
        """
        if self._is_admin(user):
            return True

        if document.owner_id == user.id:
            return True

        access = self.document_repo.get_explicit_access(document.id, user.id)
        return access is not None

    def start_pipeline_for_version(
        self,
        current_user,
        document_id: uuid.UUID,
        version_number: int,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> PipelineJob:
        """
        Crea un job pendiente para una versión concreta.

        La ejecución real se lanzará en segundo plano
        desde el router usando BackgroundTasks.
        """
        if chunk_size <= 0:
            raise ValueError("El tamaño del chunk debe ser mayor que cero")

        if chunk_overlap < 0:
            raise ValueError("El solapamiento no puede ser negativo")

        if chunk_overlap >= chunk_size:
            raise ValueError("El solapamiento debe ser menor que el tamaño del chunk")

        document = self.document_repo.get_document_by_id(document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_manage_pipeline(current_user, document):
            raise PermissionError("No tienes permisos para lanzar el pipeline de este documento")

        version = self.document_repo.get_document_version(
            document_id=document.id,
            version_number=version_number,
        )
        if version is None:
            raise ValueError("Versión no encontrada")

        job = PipelineJob(
            document_id=document.id,
            document_version_id=version.id,
            version_number=version.version_number,
            status="pending",
            current_step="queued",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            total_chunks=None,
            ready_for_vectorization=False,
            error_message=None,
            created_by_user_id=current_user.id,
        )

        return self.job_repo.create_pipeline_job(job)

    def get_pipeline_job_for_read(
        self,
        current_user,
        job_id: uuid.UUID,
    ) -> PipelineJob:
        """
        Devuelve un job si el usuario tiene permiso para consultarlo.
        """
        job = self.job_repo.get_pipeline_job_by_id(job_id)
        if job is None:
            raise ValueError("Job de pipeline no encontrado")

        document = self.document_repo.get_document_by_id(job.document_id)
        if document is None:
            raise ValueError("Documento no encontrado")

        if not self._can_read_pipeline_job(current_user, document):
            raise PermissionError("No tienes permisos para consultar este job de pipeline")

        return job

    def run_pipeline_job(self, job_id: uuid.UUID) -> None:
        """
        Ejecuta un job completo en una sesión nueva de base de datos.

        Esto es importante porque el background task se ejecuta
        fuera del ciclo normal de la petición HTTP.
        """
        db = self.session_factory()

        try:
            document_repo = DocumentRepository(db)
            job_repo = PipelineJobRepository(db)
            extraction_service = TextExtractionService()
            chunking_service = TextChunkingService()

            job = job_repo.get_pipeline_job_by_id(job_id)
            if job is None:
                return

            version = document_repo.get_document_version(
                document_id=job.document_id,
                version_number=job.version_number,
            )
            if version is None:
                job_repo.mark_job_as_failed(
                    job=job,
                    error_message="La versión asociada al pipeline ya no existe",
                    failed_step="extracting_text",
                )
                return

            # Paso 1: extracción
            job = job_repo.mark_job_as_running(
                job=job,
                current_step="extracting_text",
            )

            extraction_result = extraction_service.extract_from_version(version)

            version = document_repo.save_extracted_text_for_version(
                version=version,
                extracted_text=extraction_result.extracted_text,
            )

            # Paso 2: chunking
            job = job_repo.update_current_step(
                job=job,
                current_step="chunking_text",
            )

            chunk_pieces = chunking_service.chunk_text(
                text=version.extracted_text or "",
                chunk_size=job.chunk_size,
                chunk_overlap=job.chunk_overlap,
            )

            chunks_data = [
                {
                    "chunk_index": item.chunk_index,
                    "content": item.content,
                    "char_count": item.char_count,
                    "start_char": item.start_char,
                    "end_char": item.end_char,
                }
                for item in chunk_pieces
            ]

            chunks = document_repo.save_chunks_for_version(
                document=version.document,
                version=version,
                chunks_data=chunks_data,
            )

            # Paso 3: dejar listo para vectorización
            job_repo.mark_job_as_completed(
                job=job,
                total_chunks=len(chunks),
            )

        except ValueError as exc:
            # Error funcional controlado: formato no soportado,
            # falta de texto, parámetros inválidos, etc.
            if "job" in locals() and job is not None:
                failed_step = getattr(job, "current_step", None) or "unknown"
                job_repo.mark_job_as_failed(
                    job=job,
                    error_message=str(exc),
                    failed_step=failed_step,
                )
        except Exception as exc:
            # Error inesperado del sistema.
            if "job" in locals() and job is not None:
                failed_step = getattr(job, "current_step", None) or "unknown"
                job_repo.mark_job_as_failed(
                    job=job,
                    error_message=f"Error interno del pipeline: {str(exc)}",
                    failed_step=failed_step,
                )
        finally:
            db.close()