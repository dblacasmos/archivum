from sqlalchemy import text
from sqlalchemy.orm import Session


class AnalyticsRepository:
    """
    Repositorio de consultas analíticas.

    Aquí se hacen consultas preparadas para análisis, separadas del
    tracking transaccional usado para registrar eventos.
    """

    def __init__(self, db: Session):
        # Guarda la sesión de base de datos recibida desde FastAPI.
        self.db = db

    def get_powerbi_event_rows(self, limit: int = 500) -> list[dict]:
        """
        Devuelve eventos en formato plano para Power BI.
        """

        # Consulta SQL que transforma los eventos JSONB en columnas simples.
        stmt = text(
            """
            SELECT
                CAST(id AS TEXT) AS event_id,
                event_type,
                source,
                CAST(user_id AS TEXT) AS user_id,
                created_at,
                TO_CHAR(created_at, 'YYYY-MM-DD') AS event_date,
                EXTRACT(HOUR FROM created_at)::INT AS event_hour,
                payload ->> 'query' AS query_text,
                payload ->> 'search_mode' AS search_mode,
                NULLIF(payload ->> 'results_count', '')::INT AS results_count
            FROM tracking_events
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )

        # Ejecuta la consulta pasando el límite como parámetro seguro.
        result = self.db.execute(stmt, {"limit": limit})

        # Convierte cada fila en diccionario para que el servicio la use fácil.
        return [dict(row) for row in result.mappings().all()]