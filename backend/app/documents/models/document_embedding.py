import uuid
from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.config import settings
from app.core.db import Base


class DocumentEmbedding(Base):
    """
    Modelo que guarda el embedding asociado a un chunk concreto.

    En R41 dejamos de persistir el vector como JSON y
    pasamos a usar una columna real de tipo pgvector.
    """

    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            name="uq_document_embeddings_chunk_id",
        ),
    )

    # ID único interno del embedding
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Documento lógico al que pertenece el embedding
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Versión documental concreta a la que pertenece
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Chunk exacto del que se generó este embedding
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Proveedor utilizado para generar el embedding
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="openai",
        server_default=text("'openai'"),
    )

    # Nombre del modelo utilizado
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Número de dimensiones del vector generado.
    # Lo mantenemos también en una columna normal por trazabilidad.
    dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Vector persistido en una columna real de pgvector.
    # Fijamos la dimensión esperada para mantener consistencia
    # de cara a las búsquedas e índices del requisito R42.
    embedding_vector: Mapped[list[float]] = mapped_column(
        VECTOR(settings.openai_embeddings_dimensions),
        nullable=False,
    )

    # Estado simple del proceso de generación
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="completed",
        server_default=text("'completed'"),
    )

    # Error simple si hubiera fallado la generación
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Fecha real de generación
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Fecha de creación del registro
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

    # Relación con la versión documental
    version = relationship(
        "DocumentVersion",
        foreign_keys=[document_version_id],
    )

    # Relación uno a uno con el chunk
    chunk = relationship(
        "DocumentChunk",
        back_populates="embedding",
        foreign_keys=[chunk_id],
    )

    @property
    def embedding_json(self) -> list[float]:
        """
        Propiedad de compatibilidad para no romper de golpe
        parte del código y tests de R40 que aún consultaban
        el embedding como si fuera JSON.
        """
        return list(self.embedding_vector)

    @embedding_json.setter
    def embedding_json(self, value: list[float]) -> None:
        """
        Setter de compatibilidad para permitir asignaciones antiguas.
        """
        self.embedding_vector = value