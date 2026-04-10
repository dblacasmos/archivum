import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class DocumentAccess(Base):
    """
    ACL simple por documento.
    Si existe una fila para (documento, usuario), ese usuario puede leer el documento.
    """

    __tablename__ = "document_accesses"
    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_document_access_document_user"),
    )

    # ID interno del permiso
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Documento sobre el que se concede acceso
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Usuario que recibe acceso
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Usuario que concedió el acceso
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Fecha de creación del permiso
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relación con el documento
    document = relationship(
        "Document",
        back_populates="accesses",
        foreign_keys=[document_id],
    )

    # Relación con el usuario que recibe el permiso
    user = relationship(
        "User",
        back_populates="document_accesses",
        foreign_keys=[user_id],
    )