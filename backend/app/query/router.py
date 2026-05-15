from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import get_current_active_user
from app.core.db import get_session
from app.core.logging import get_logger
from app.core.metrics import run_observed_stage
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.embeddings import OpenAIEmbeddingClient
from app.documents.repository import DocumentRepository
from app.query.schemas import QueryRequest, QueryResponse
from app.query.service import SemanticSearchService
from app.tracking.repository import TrackingEventRepository
from app.tracking.service import TrackingEventService

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


def get_semantic_search_service(
    session: Session = Depends(get_session),
) -> SemanticSearchService:
    """
    Construye el servicio de búsqueda con sus dependencias.

    Se crea aquí para mantener el endpoint limpio y dejar la lógica real
    dentro del servicio de aplicación.
    """
    document_repo = DocumentRepository(session)
    embedding_repo = DocumentEmbeddingRepository(session)
    embedding_client = OpenAIEmbeddingClient()

    return SemanticSearchService(
        document_repo=document_repo,
        embedding_repo=embedding_repo,
        embedding_client=embedding_client,
    )


@router.post("", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    current_user=Depends(get_current_active_user),
    service: SemanticSearchService = Depends(get_semantic_search_service),
    session: Session = Depends(get_session),
):
    """
    Endpoint de búsqueda documental.

    search_mode:
    - semantic: búsqueda vectorial de R50.
    - hybrid: búsqueda texto + vector de R51.

    En R52, ambos modos devuelven información de ranking explicable.
    En R53, ambos modos permiten filtrar por metadata documental.
    """
    try:
        logger.info(
            "Inicio de consulta documental",
            extra={
                "event_data": {
                    "event": "query_start",
                    "path": "/query",
                    "method": "POST",
                    "query_length": len(body.query),
                    "limit": body.limit,
                    "metric": body.metric,
                    "search_mode": body.search_mode,
                    "metadata_filters": body.metadata_filters,
                }
            },
        )

        if body.search_mode not in {"semantic", "hybrid"}:
            raise ValueError("Modo de búsqueda no soportado. Usa semantic o hybrid")

        query_embedding = run_observed_stage(
            stage="embedding",
            action=lambda: service.generate_query_embedding(body.query),
        )

        if body.search_mode == "hybrid":
            results = run_observed_stage(
                stage="retrieval",
                action=lambda: service.retrieve_hybrid_chunks(
                    current_user=current_user,
                    query=body.query,
                    query_vector=query_embedding,
                    limit=body.limit,
                    metric=body.metric,
                    metadata_filters=body.metadata_filters,
                ),
            )
            message = "Consulta híbrida procesada correctamente"
        else:
            results = run_observed_stage(
                stage="retrieval",
                action=lambda: service.retrieve_similar_chunks(
                    current_user=current_user,
                    query_vector=query_embedding,
                    limit=body.limit,
                    metric=body.metric,
                    metadata_filters=body.metadata_filters,
                ),
            )
            message = "Consulta semántica procesada correctamente"

        answer = run_observed_stage(
            stage="llm",
            action=lambda: service.build_search_answer(
                query=body.query,
                results=results,
            ),
        )

        tracking_service = TrackingEventService(
            repository=TrackingEventRepository(session)
        )

        tracking_service.track_event(
            event_type="query_executed",
            user_id=current_user.id,
            source="frontend",
            payload={
                "query": body.query,
                "search_mode": body.search_mode,
                "metric": body.metric,
                "limit": body.limit,
                "results_count": len(results),
                "metadata_filters": body.metadata_filters,
            },
        )

        logger.info(
            "Consulta documental finalizada",
            extra={
                "event_data": {
                    "event": "query_completed",
                    "path": "/query",
                    "method": "POST",
                    "retrieved_chunks": len(results),
                    "search_mode": body.search_mode,
                    "metadata_filters": body.metadata_filters,
                }
            },
        )

        return QueryResponse(
            message=message,
            query=body.query,
            user_id=str(current_user.id),
            retrieved_chunks=len(results),
            answer=answer,
            observability_ready=True,
            results=results,
            debug={
                "embedding_dimensions": len(query_embedding),
                "metric": body.metric,
                "search_mode": body.search_mode,
                "ranking": "explainable_basic",
                "metadata_filters": body.metadata_filters,
            },
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc