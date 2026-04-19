import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class DocumentMetadata(Base):
    """
    Modelo de metadata asociada a un documento.

    Cada fila representa un par clave-valor.
    Ejemplo:
    - category = manual
    - department = rrhh
    - language = es
    """

    __tablename__ = "document_metadata"
    __table_args__ = (
        UniqueConstraint("document_id", "meta_key", name="uq_document_metadata_document_key"),
    )

    # Identificador único interno de la metadata
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Documento al que pertenece esta metadata
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Clave de metadata.
    # Ejemplos: category, source, language, area
    meta_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Valor asociado a la clave.
    # Ejemplos: manual, interno, es, legal
    meta_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Fecha de creación de la fila
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Fecha de última actualización.
    # Si se hace upsert sobre una clave existente, este campo cambia.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relación ORM con el documento propietario
    document = relationship(
        "Document",
        back_populates="metadata_entries",
        foreign_keys=[document_id],
    )