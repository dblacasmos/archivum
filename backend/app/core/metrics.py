from time import perf_counter

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

# Contador total de peticiones HTTP.
# Aumenta una unidad por cada request atendida.
http_requests_total = Counter(
    "archivum_http_requests_total",
    "Número total de peticiones HTTP procesadas por la API",
    ["method", "path", "status_code"],
)

# Histograma de duración HTTP.
# Guarda tiempos de respuesta por endpoint.
http_request_duration_seconds = Histogram(
    "archivum_http_request_duration_seconds",
    "Duración de las peticiones HTTP en segundos",
    ["method", "path"],
)

# Contador de etapas del pipeline RAG.
# Cuenta cuántas veces se ejecuta cada etapa y con qué resultado.
rag_stage_total = Counter(
    "archivum_rag_stage_total",
    "Número total de ejecuciones por etapa del pipeline RAG",
    ["stage", "status"],
)

# Histograma de duración de cada etapa del pipeline RAG.
rag_stage_duration_seconds = Histogram(
    "archivum_rag_stage_duration_seconds",
    "Duración de las etapas del pipeline RAG en segundos",
    ["stage"],
)


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """
    Registra métricas HTTP de una petición completada.
    """
    http_requests_total.labels(
        method=method,
        path=path,
        status_code=str(status_code),
    ).inc()

    http_request_duration_seconds.labels(
        method=method,
        path=path,
    ).observe(duration_seconds)


def observe_rag_stage(stage: str, duration_seconds: float, status: str = "success") -> None:
    """
    Registra métricas de una etapa del pipeline RAG.
    """
    rag_stage_total.labels(stage=stage, status=status).inc()
    rag_stage_duration_seconds.labels(stage=stage).observe(duration_seconds)


def build_metrics_response() -> Response:
    """
    Devuelve el contenido de /metrics en el formato esperado por Prometheus.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


def run_observed_stage(stage: str, action):
    """
    Ejecuta una función y registra observabilidad de esa etapa.

    Sirve para etapas como:
    - retrieval
    - embedding
    - llm
    """
    start = perf_counter()

    try:
        result = action()
        duration_seconds = perf_counter() - start

        observe_rag_stage(
            stage=stage,
            duration_seconds=duration_seconds,
            status="success",
        )

        logger.info(
            f"Etapa RAG completada: {stage}",
            extra={
                "event_data": {
                    "event": "rag_stage",
                    "stage": stage,
                    "status": "success",
                    "duration_ms": round(duration_seconds * 1000, 2),
                }
            },
        )

        return result
    except Exception:
        duration_seconds = perf_counter() - start

        observe_rag_stage(
            stage=stage,
            duration_seconds=duration_seconds,
            status="error",
        )

        logger.exception(
            f"Error en la etapa RAG: {stage}",
            extra={
                "event_data": {
                    "event": "rag_stage",
                    "stage": stage,
                    "status": "error",
                    "duration_ms": round(duration_seconds * 1000, 2),
                }
            },
        )
        raise