import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    """Modelo que representa la tabla 'users'."""

    __tablename__ = "users"

    # ID único del usuario
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Email único del usuario
    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
        index=True,
    )

    # Hash de la contraseña
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Nombre visible del usuario
    display_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    # Indica si el usuario está activo
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Fecha de creación
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Un usuario puede tener muchos refresh tokens
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Relación muchos a muchos con roles
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
    )

    # Un usuario puede ser propietario de muchos documentos
    owned_documents = relationship(
        "Document",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="Document.owner_id",
    )

    # Un usuario puede tener muchos permisos explícitos sobre documentos
    document_accesses = relationship(
        "DocumentAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="DocumentAccess.user_id",
    )