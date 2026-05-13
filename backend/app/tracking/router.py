from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import get_current_active_user
from app.core.db import get_session
from app.tracking.repository import TrackingEventRepository
from app.tracking.schemas import (
    TrackingEventCreate,
    TrackingEventListResponse,
    TrackingEventResponse,
)
from app.tracking.service import TrackingEventService

router = APIRouter(prefix="/tracking/events", tags=["tracking"])


def get_tracking_event_service(
    session: Session = Depends(get_session),
) -> TrackingEventService:
    """
    Construye el servicio de tracking con sus dependencias.
    """
    # Crea el repositorio usando la sesión de base de datos de la petición.
    repository = TrackingEventRepository(session)

    # Devuelve el servicio listo para usarse en los endpoints.
    return TrackingEventService(repository)


@router.post(
    "",
    response_model=TrackingEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tracking_event(
    body: TrackingEventCreate,
    current_user=Depends(get_current_active_user),
    service: TrackingEventService = Depends(get_tracking_event_service),
):
    """
    Registra un evento asociado al usuario autenticado.
    """
    try:
        # Registra el evento usando el usuario obtenido desde el JWT.
        return service.track_event(
            event_type=body.event_type,
            user_id=current_user.id,
            source=body.source,
            payload=body.payload,
        )

    except ValueError as exc:
        # Devuelve error 400 si los datos del evento no son válidos.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("", response_model=TrackingEventListResponse)
def list_my_tracking_events(
    limit: int = 50,
    current_user=Depends(get_current_active_user),
    service: TrackingEventService = Depends(get_tracking_event_service),
):
    """
    Lista los eventos recientes del usuario autenticado.
    """
    # Recupera solo los eventos del usuario actual.
    events = service.list_recent_events(
        limit=limit,
        user_id=current_user.id,
    )

    # Devuelve una respuesta clara para Swagger y para futuros análisis.
    return TrackingEventListResponse(
        message="Eventos recuperados correctamente",
        total=len(events),
        events=events,
    )