import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class RefreshToken(Base):
    """Tabla que almacena refresh tokens activos o revocados."""

    __tablename__ = "refresh_tokens"

    # ------------------
    # Campos de la tabla
    # ------------------

    # ID interno del registro
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Usuario propietario del token
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ID único del token (JWT ID)
    jti: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # Hash del refresh token (no guardar token real)
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Indica si fue revocado
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Fecha de expiración
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Fecha de creación
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ----------
    # Relaciones
    # ----------

    # Acceso directo al usuario propietario del token
    user = relationship(
        "User",
        back_populates="refresh_tokens",
    )