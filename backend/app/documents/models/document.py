import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Document(Base):
    """
    Modelo de documento.

    Esta tabla representa el estado actual del documento.
    El historial completo se guarda en document_versions.
    """

    __tablename__ = "documents"

    # ID único del documento
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Título lógico del documento dentro del sistema
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Contenido textual simple si el documento se creó desde texto
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Nombre original del archivo actual
    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Nombre final del archivo actual guardado en disco
    stored_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Ruta física actual del archivo
    storage_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Tipo MIME actual del archivo
    mime_type: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    # Tamaño actual del archivo en bytes
    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # Usuario propietario del documento
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fecha de creación del documento
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relación con el propietario
    owner = relationship(
        "User",
        back_populates="owned_documents",
        foreign_keys=[owner_id],
    )

    # Relación con los accesos explícitos
    accesses = relationship(
        "DocumentAccess",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentAccess.document_id",
    )

    # Relación con la metadata del documento
    metadata_entries = relationship(
        "DocumentMetadata",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentMetadata.document_id",
    )

    # Relación con el historial de versiones
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version_number.asc()",
    )

    # Relación con los chunks generados para cualquiera de sus versiones
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentChunk.document_id",
        order_by="DocumentChunk.chunk_index.asc()",
    )