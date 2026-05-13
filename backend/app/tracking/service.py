import uuid

from app.tracking.models import TrackingEvent
from app.tracking.repository import TrackingEventRepository


class TrackingEventService:
    """
    Servicio de negocio para registrar eventos.

    Aquí se centraliza la lógica del tracking para que pueda reutilizarse
    desde endpoints actuales y futuros.
    """

    def __init__(self, repository: TrackingEventRepository):
        # Guarda el repositorio que usará para persistir eventos.
        self.repository = repository

    def track_event(
        self,
        event_type: str,
        user_id: uuid.UUID | None,
        source: str = "backend",
        payload: dict | None = None,
    ) -> TrackingEvent:
        """
        Registra un evento en el sistema.
        """
        # Limpia espacios para evitar eventos con nombres mal formados.
        clean_event_type = event_type.strip()
        clean_source = source.strip()

        # Valida que el tipo de evento no esté vacío.
        if not clean_event_type:
            raise ValueError("El tipo de evento no puede estar vacío")

        # Valida que el origen no esté vacío.
        if not clean_source:
            raise ValueError("El origen del evento no puede estar vacío")

        # Crea el modelo de evento que se guardará en base de datos.
        event = TrackingEvent(
            event_type=clean_event_type,
            user_id=user_id,
            source=clean_source,
            payload=payload or {},
        )

        # Persiste el evento y lo devuelve.
        return self.repository.create(event)

    def list_recent_events(
        self,
        limit: int = 50,
        user_id: uuid.UUID | None = None,
    ) -> list[TrackingEvent]:
        """
        Obtiene eventos recientes para comprobación o análisis posterior.
        """
        # Evita límites absurdos o peligrosos.
        safe_limit = max(1, min(limit, 100))

        # Pide al repositorio los eventos recientes.
        return self.repository.list_recent(
            limit=safe_limit,
            user_id=user_id,
        )