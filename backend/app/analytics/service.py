import csv
import io

from app.analytics.repository import AnalyticsRepository
from app.analytics.schemas import PowerBIEventRow


class AnalyticsService:
    """
    Servicio de analítica básica.

    Su responsabilidad es preparar los datos para consumo externo,
    especialmente desde Power BI.
    """

    def __init__(self, repository: AnalyticsRepository):
        # Guarda el repositorio que accede a la base de datos.
        self.repository = repository

    def list_powerbi_events(self, limit: int = 500) -> list[PowerBIEventRow]:
        """
        Devuelve eventos normalizados como objetos Pydantic.
        """

        # Recupera filas planas desde la base de datos.
        rows = self.repository.get_powerbi_event_rows(limit=limit)

        # Convierte cada diccionario en un schema validado.
        return [PowerBIEventRow(**row) for row in rows]

    def build_powerbi_csv(self, limit: int = 500) -> str:
        """
        Genera un CSV compatible con Power BI.
        """

        # Obtiene los eventos ya preparados.
        events = self.list_powerbi_events(limit=limit)

        # Crea un buffer de texto en memoria.
        output = io.StringIO()

        # Define las columnas del CSV.
        fieldnames = [
            "event_id",
            "event_type",
            "source",
            "user_id",
            "created_at",
            "event_date",
            "event_hour",
            "query_text",
            "search_mode",
            "results_count",
        ]

        # Crea el escritor CSV.
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        # Escribe la cabecera.
        writer.writeheader()

        # Escribe cada evento como una fila.
        for event in events:
            writer.writerow(event.model_dump())

        # Devuelve el contenido completo del CSV.
        return output.getvalue()