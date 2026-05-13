import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TrackingEventCreate(BaseModel):
    """
    Datos necesarios para registrar un evento nuevo.

    El usuario no se envía desde el cliente porque se obtiene
    automáticamente desde el token JWT.
    """

    event_type: str = Field(
        min_length=1,
        max_length=100,
        description="Tipo de evento que se quiere registrar",
    )

    source: str = Field(
        default="backend",
        min_length=1,
        max_length=100,
        description="Módulo o parte del sistema que genera el evento",
    )

    payload: dict = Field(
        default_factory=dict,
        description="Información adicional del evento",
    )


class TrackingEventResponse(BaseModel):
    """
    Respuesta pública de un evento registrado.
    """

    id: uuid.UUID
    event_type: str
    user_id: uuid.UUID | None
    source: str
    payload: dict
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class TrackingEventListResponse(BaseModel):
    """
    Respuesta para listar eventos registrados.
    """

    message: str
    total: int
    events: list[TrackingEventResponse]