from datetime import datetime
from pydantic import BaseModel


class PowerBIEventRow(BaseModel):
    """
    Fila analítica preparada para Power BI.

    No representa la tabla original completa, sino una versión plana
    y cómoda para crear visualizaciones.
    """

    event_id: str
    event_type: str
    source: str
    user_id: str | None
    created_at: datetime
    event_date: str
    event_hour: int
    query_text: str | None
    search_mode: str | None
    results_count: int | None


class PowerBIEventsResponse(BaseModel):
    """
    Respuesta JSON con eventos preparados para análisis.
    """

    message: str
    total: int
    events: list[PowerBIEventRow]