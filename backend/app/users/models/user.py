import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

class User(Base):
    ''' Modelo que representa la tabla 'users' en la base de datos'''
    
    __tablename__ = 'users'

    # ID único del usuario (clave primaria)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Email del usuario (único y obligatorio)
    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
        index=True
    )

    # Hash de la contraseña (nunca guardar contraseña en texto plano)
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # Nombre visible del usuario (opcional)
    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=True
    )

    # Indica si el usuario está activo
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # Fecha de creación (la asigna automáticamente la base de datos)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )