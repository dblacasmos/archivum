from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.analytics.repository import AnalyticsRepository
from app.analytics.schemas import PowerBIEventsResponse
from app.analytics.service import AnalyticsService
from app.auth.security import get_current_active_user
from app.core.db import get_session

router = APIRouter(prefix="/analytics/powerbi", tags=["analytics"])


def get_analytics_service(
    session: Session = Depends(get_session),
) -> AnalyticsService:
    """
    Construye el servicio de analítica con sus dependencias.
    """

    # Crea el repositorio usando la sesión actual.
    repository = AnalyticsRepository(session)

    # Devuelve el servicio preparado para los endpoints.
    return AnalyticsService(repository)


@router.get("/events", response_model=PowerBIEventsResponse)
def list_powerbi_events(
    limit: int = Query(default=500, ge=1, le=5000),
    current_user=Depends(get_current_active_user),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Devuelve eventos en formato JSON para análisis.
    """

    # Recupera los eventos preparados para Power BI.
    events = service.list_powerbi_events(limit=limit)

    # Devuelve una respuesta clara para Swagger.
    return PowerBIEventsResponse(
        message="Eventos preparados correctamente para Power BI",
        total=len(events),
        events=events,
    )


@router.get("/events.csv")
def download_powerbi_events_csv(
    limit: int = Query(default=500, ge=1, le=5000),
    current_user=Depends(get_current_active_user),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """
    Devuelve un CSV para importarlo directamente en Power BI.
    """

    # Genera el contenido CSV desde los eventos registrados.
    csv_content = service.build_powerbi_csv(limit=limit)

    # Devuelve el CSV como archivo descargable.
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=archivum_powerbi_events.csv"
        },
    )