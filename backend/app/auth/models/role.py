import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Role(Base):
    """
    Modelo que representa un rol del sistema.
    Ejemplos: admin, editor, viewer.
    """

    __tablename__ = "roles"

    # ID único del rol
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Nombre único del rol
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Descripción opcional del rol
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relación muchos a muchos con usuarios
    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
    )