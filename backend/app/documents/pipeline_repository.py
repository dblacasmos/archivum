import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.documents.models import PipelineJob


class PipelineJobRepository:
    """
    Repositorio centrado únicamente en la tabla de jobs del pipeline.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_pipeline_job(self, job: PipelineJob) -> PipelineJob:
        """
        Guarda un job nuevo en base de datos.
        """
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_pipeline_job_by_id(self, job_id: uuid.UUID) -> PipelineJob | None:
        """
        Recupera un job concreto por su ID.
        """
        return self.db.get(PipelineJob, job_id)

    def get_latest_pipeline_job_for_version(
        self,
        document_version_id: uuid.UUID,
    ) -> PipelineJob | None:
        """
        Devuelve el último job lanzado sobre una versión concreta.
        """
        stmt = (
            select(PipelineJob)
            .where(PipelineJob.document_version_id == document_version_id)
            .order_by(desc(PipelineJob.created_at))
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def mark_job_as_running(
        self,
        job: PipelineJob,
        current_step: str,
    ) -> PipelineJob:
        """
        Marca el job como ejecutándose.
        """
        job.status = "running"
        job.current_step = current_step
        job.started_at = datetime.now(timezone.utc)
        job.finished_at = None
        job.error_message = None
        job.ready_for_vectorization = False

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_current_step(
        self,
        job: PipelineJob,
        current_step: str,
    ) -> PipelineJob:
        """
        Actualiza el paso actual del pipeline sin cambiar el estado global.
        """
        job.current_step = current_step

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_job_as_completed(
        self,
        job: PipelineJob,
        total_chunks: int,
    ) -> PipelineJob:
        """
        Marca el job como completado y deja la versión lista
        para la fase de vectorización.
        """
        job.status = "completed"
        job.current_step = "ready_for_vectorization"
        job.total_chunks = total_chunks
        job.ready_for_vectorization = True
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_job_as_failed(
        self,
        job: PipelineJob,
        error_message: str,
        failed_step: str,
    ) -> PipelineJob:
        """
        Marca el job como fallido y guarda un mensaje de error simple.
        """
        job.status = "failed"
        job.current_step = failed_step
        job.error_message = error_message
        job.ready_for_vectorization = False
        job.finished_at = datetime.now(timezone.utc)

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job