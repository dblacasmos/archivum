import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class PipelineJob(Base):
    """
    Modelo que representa una ejecución del pipeline asíncrono
    sobre una versión concreta de un documento.

    La idea es sencilla:
    - un documento puede tener varias versiones
    - una versión puede lanzar varios jobs a lo largo del tiempo
    - cada job guarda su estado, el paso actual y posibles errores
    """

    __tablename__ = "document_pipeline_jobs"

    # ID único del job
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Documento lógico asociado al job
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Versión concreta que se va a procesar
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Número de versión solo para exponerlo fácil en API
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Estado global del pipeline:
    # pending | running | completed | failed
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    # Paso actual dentro del pipeline:
    # queued | extracting_text | chunking_text | ready_for_vectorization
    current_step: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )

    # Parámetros usados para el chunking
    chunk_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=500,
        server_default=text("500"),
    )

    chunk_overlap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default=text("100"),
    )

    # Número total de chunks generados al terminar
    total_chunks: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Indica si la versión queda lista para la fase siguiente
    ready_for_vectorization: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # Mensaje de error simple si algo falla
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Usuario que lanzó el job
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fechas de control del proceso
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relación con el documento lógico
    document = relationship(
        "Document",
        foreign_keys=[document_id],
    )

    # Relación con la versión concreta
    version = relationship(
        "DocumentVersion",
        foreign_keys=[document_version_id],
    )