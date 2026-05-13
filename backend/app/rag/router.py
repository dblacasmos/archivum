from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import get_current_active_user
from app.core.db import get_session
from app.core.logging import get_logger
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.embeddings import OpenAIEmbeddingClient
from app.documents.repository import DocumentRepository
from app.query.service import SemanticSearchService
from app.rag.citations import CitationService
from app.rag.evaluation import RagEvaluationService
from app.rag.hallucination_guard import HallucinationGuard
from app.rag.llm_client import OpenAIChatClient
from app.rag.schemas import (
    HallucinationChecks,
    RagCitation,
    RagEvaluation,
    RagRequest,
    RagResponse,
    RagUsageMetrics,
)
from app.rag.service import BasicRagService
from app.rag.usage_metrics import RagUsageMetricsService

router = APIRouter(prefix="/rag", tags=["rag"])
logger = get_logger(__name__)


@router.post("", response_model=RagResponse)
def generate_rag_answer(
    body: RagRequest,
    db: Session = Depends(get_session),
    current_user=Depends(get_current_active_user),
):
    """
    Endpoint principal del flujo RAG.

    R70:
    - recupera contexto
    - construye prompt
    - genera respuesta

    R71:
    - controla alucinaciones

    R72:
    - devuelve citas

    R73:
    - devuelve evaluación automática

    R74:
    - devuelve métricas de latencia y coste
    """
    try:
        document_repo = DocumentRepository(db)
        embedding_repo = DocumentEmbeddingRepository(db)
        embedding_client = OpenAIEmbeddingClient()

        search_service = SemanticSearchService(
            document_repo=document_repo,
            embedding_repo=embedding_repo,
            embedding_client=embedding_client,
        )

        llm_client = OpenAIChatClient()
        hallucination_guard = HallucinationGuard()
        citation_service = CitationService()
        evaluation_service = RagEvaluationService()
        usage_metrics_service = RagUsageMetricsService()

        rag_service = BasicRagService(
            search_service=search_service,
            llm_client=llm_client,
            hallucination_guard=hallucination_guard,
            citation_service=citation_service,
            evaluation_service=evaluation_service,
            usage_metrics_service=usage_metrics_service,
        )

        result = rag_service.generate_response(
            current_user=current_user,
            query=body.query,
            limit=body.limit,
            search_mode=body.search_mode,
            metadata_filters=body.metadata_filters,
        )

        context_chunks = result["context"]
        checks = result["hallucination_checks"]
        evaluation = result["evaluation"]
        usage_metrics = result["usage_metrics"]

        logger.info(
            "Flujo RAG finalizado con métricas de latencia y coste",
            extra={
                "event_data": {
                    "event": "rag_completed",
                    "path": "/rag",
                    "method": "POST",
                    "retrieved_chunks": result["retrieved_context_count"],
                    "used_context_chunks": len(context_chunks),
                    "citations_count": len(result["citations"]),
                    "search_mode": body.search_mode,
                    "metadata_filters": body.metadata_filters,
                    "fallback_applied": result["fallback_applied"],
                    "hallucination_reason": checks.reason,
                    "evaluation_enabled": evaluation.enabled,
                    "evaluation_verdict": evaluation.verdict,
                    "evaluation_overall_score": evaluation.overall_score,
                    "usage_metrics_enabled": usage_metrics.enabled,
                    "total_latency_ms": usage_metrics.total_latency_ms,
                    "retrieval_latency_ms": usage_metrics.retrieval_latency_ms,
                    "llm_latency_ms": usage_metrics.llm_latency_ms,
                    "total_tokens_estimated": usage_metrics.total_tokens_estimated,
                    "estimated_cost_eur": usage_metrics.estimated_cost_eur,
                }
            },
        )

        return RagResponse(
            message="Flujo RAG procesado correctamente",
            query=body.query,
            user_id=str(current_user.id),
            retrieved_chunks=result["retrieved_context_count"],
            used_context_chunks=len(context_chunks),
            prompt=result["prompt"],
            answer=result["answer"],
            answer_status=result["answer_status"],
            fallback_applied=result["fallback_applied"],
            hallucination_checks=HallucinationChecks(
                enabled=True,
                is_valid=checks.is_valid,
                fallback_applied=checks.fallback_applied,
                reason=checks.reason,
                used_context_chunks=checks.used_context_chunks,
                context_was_limited=checks.context_was_limited,
                answer_overlap_terms=checks.answer_overlap_terms,
            ),
            citations=[
                RagCitation(**citation)
                for citation in result["citations"]
            ],
            evaluation=RagEvaluation(
                enabled=evaluation.enabled,
                coherence_score=evaluation.coherence_score,
                relevance_score=evaluation.relevance_score,
                context_overlap_score=evaluation.context_overlap_score,
                citation_coverage_score=evaluation.citation_coverage_score,
                overall_score=evaluation.overall_score,
                verdict=evaluation.verdict,
                metrics=evaluation.metrics,
                explanation=evaluation.explanation,
            ),
            usage_metrics=RagUsageMetrics(
                enabled=usage_metrics.enabled,
                total_latency_ms=usage_metrics.total_latency_ms,
                retrieval_latency_ms=usage_metrics.retrieval_latency_ms,
                llm_latency_ms=usage_metrics.llm_latency_ms,
                prompt_tokens_estimated=usage_metrics.prompt_tokens_estimated,
                answer_tokens_estimated=usage_metrics.answer_tokens_estimated,
                total_tokens_estimated=usage_metrics.total_tokens_estimated,
                estimated_cost_eur=usage_metrics.estimated_cost_eur,
                cost_model=usage_metrics.cost_model,
                explanation=usage_metrics.explanation,
            ),
            context=context_chunks,
            debug={
                "search_mode": body.search_mode,
                "metadata_filters": body.metadata_filters,
                "rag_version": "basic_r74_latency_cost_metrics",
                "citations_enabled": True,
                "hallucination_control_enabled": True,
                "evaluation_enabled": True,
                "usage_metrics_enabled": True,
                "max_context_chunks": hallucination_guard.max_context_chunks,
            },
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc