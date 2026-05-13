import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.db import Base


class TrackingEvent(Base):
    """
    Modelo que representa un evento registrado en el sistema.

    Un evento puede ser una acción de usuario, como una búsqueda,
    o un comportamiento interno del sistema, como una consulta RAG.
    """

    __tablename__ = "tracking_events"

    # Identificador único del evento.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tipo de evento registrado.
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Usuario asociado al evento.
    # Puede ser nulo para eventos técnicos del sistema sin usuario.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Módulo funcional donde se produjo el evento.
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="backend",
    )

    # Información adicional flexible del evento.
    # JSONB permite guardar datos distintos según el tipo de evento.
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Fecha y hora en la que se registró el evento.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relación opcional con el usuario propietario del evento.
    user = relationship(
        "User",
        back_populates="tracking_events",
        foreign_keys=[user_id],
    )


Index(
    "ix_tracking_events_type_created_at",
    TrackingEvent.event_type,
    TrackingEvent.created_at,
)