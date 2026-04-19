import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class DocumentVersion(Base):
    """
    Modelo que guarda una foto fija del documento en cada versión.

    La tabla documents representa el estado actual.
    La tabla document_versions representa el historial.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
    )

    # ID interno único de la versión
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Documento al que pertenece esta versión
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Número secuencial de versión: 1, 2, 3...
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Título de esa versión concreta
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Contenido textual de la versión si fue creada desde texto
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Nombre original del archivo en esa versión
    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Nombre real guardado en disco para esa versión
    stored_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Ruta física del archivo asociado a esa versión
    storage_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Tipo MIME del archivo de esa versión
    mime_type: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    # Tamaño del archivo en bytes
    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Texto extraído de la versión, persistido para reutilizarlo
    # en requisitos posteriores como chunking o embeddings.
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Estado de la extracción para saber si está pendiente,
    # completada o fallida.
    extraction_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    # Error de extracción, si existiera, para dejar trazabilidad.
    extraction_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Fecha en la que se completó correctamente la extracción.
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Usuario que creó esta versión
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fecha de creación de la versión
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relación ORM con el documento padre
    document = relationship(
        "Document",
        back_populates="versions",
        foreign_keys=[document_id],
    )

    # Relación con los chunks generados a partir de esta versión concreta
    chunks = relationship(
        "DocumentChunk",
        back_populates="version",
        cascade="all, delete-orphan",
        foreign_keys="DocumentChunk.document_version_id",
        order_by="DocumentChunk.chunk_index.asc()",
    )