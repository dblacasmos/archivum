import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class DocumentChunk(Base):
    """
    Modelo que guarda cada fragmento de texto generado a partir
    de una versión documental concreta.

    La idea es sencilla:
    - un documento puede tener muchas versiones
    - una versión puede generar muchos chunks
    - cada chunk queda numerado para reconstruir el orden
    """

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "chunk_index",
            name="uq_document_chunks_version_chunk_index",
        ),
    )

    # Identificador único del chunk
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Documento lógico al que pertenece el chunk
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Versión concreta desde la que se generó el chunk
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Posición del fragmento dentro del texto completo: 0, 1, 2...
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Texto real del fragmento
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Tamaño del fragmento medido en caracteres
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Posición inicial del fragmento dentro del texto original
    start_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Posición final del fragmento dentro del texto original
    end_char: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Fecha de creación del chunk
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relación ORM con el documento padre
    document = relationship(
        "Document",
        back_populates="chunks",
        foreign_keys=[document_id],
    )

    # Relación ORM con la versión concreta
    version = relationship(
        "DocumentVersion",
        back_populates="chunks",
        foreign_keys=[document_version_id],
    )

    # Relación uno a uno con su embedding.
    # Aquí no usamos uselist porque cada chunk tendrá como mucho
    # un único embedding asociado.
    embedding = relationship(
        "DocumentEmbedding",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="DocumentEmbedding.chunk_id",
    )