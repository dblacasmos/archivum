import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class Document(Base):
    """
    Modelo mínimo de documento para soportar R12.
    Más adelante podrás ampliarlo en R20, R21 y R22.
    """

    __tablename__ = "documents"

    # ID único del documento
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Título del documento
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Contenido de texto simple para poder probar permisos de acceso
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Usuario propietario del documento
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fecha de creación
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