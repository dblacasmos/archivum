from pydantic import BaseModel

from fastapi import APIRouter, Depends

from app.auth.security import get_current_active_user
from app.core.logging import get_logger
from app.core.metrics import run_observed_stage

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


class QueryRequest(BaseModel):
    """
    Cuerpo mínimo de consulta.

    En esta fase del proyecto todavía no existe el RAG completo,
    pero sí dejamos preparada la instrumentación de observabilidad
    para las etapas retrieval, embedding y llm.
    """

    query: str


def simulate_retrieval(query: str) -> list[str]:
    """
    Simula la etapa de retrieval.

    Más adelante, en R50-R51 y R70, aquí irá la recuperación real
    de documentos o chunks relevantes.
    """
    return [
        f"Fragmento relacionado con la consulta: {query}",
        "Segundo fragmento de contexto de ejemplo",
    ]


def simulate_embedding(query: str) -> list[float]:
    """
    Simula la etapa de embedding.

    En el futuro aquí se generará el embedding real de la consulta.
    """
    # El contenido es ficticio porque en R15 lo importante no es
    # el embedding real, sino dejar la observabilidad preparada.
    return [0.12, 0.48, 0.91]


def simulate_llm_answer(query: str, contexts: list[str]) -> str:
    """
    Simula la etapa de generación de respuesta.

    En R70 esta función será sustituida por la llamada real al LLM.
    """
    return (
        f"Respuesta simulada para la consulta '{query}'. "
        f"Se han usado {len(contexts)} fragmentos de contexto."
    )


@router.post("")
async def query_documents(
    body: QueryRequest,
    current_user=Depends(get_current_active_user),
):
    """
    Endpoint temporal de consulta.

    Su objetivo actual es doble:
    - mantener la protección ya usada en R14
    - dejar lista la observabilidad por etapas para R15
    """
    logger.info(
        "Inicio de consulta",
        extra={
            "event_data": {
                "event": "query_start",
                "path": "/query",
                "method": "POST",
                "query_length": len(body.query),
            }
        },
    )

    contexts = run_observed_stage(
        stage="retrieval",
        action=lambda: simulate_retrieval(body.query),
    )

    query_embedding = run_observed_stage(
        stage="embedding",
        action=lambda: simulate_embedding(body.query),
    )

    answer = run_observed_stage(
        stage="llm",
        action=lambda: simulate_llm_answer(body.query, contexts),
    )

    logger.info(
        "Consulta finalizada",
        extra={
            "event_data": {
                "event": "query_completed",
                "path": "/query",
                "method": "POST",
                "retrieved_chunks": len(contexts),
            }
        },
    )

    return {
        "message": "Consulta procesada correctamente",
        "query": body.query,
        "user_id": str(current_user.id),
        "retrieved_chunks": len(contexts),
        "answer": answer,
        "observability_ready": True,
        "debug": {
            "embedding_dimensions": len(query_embedding),
        },
    }