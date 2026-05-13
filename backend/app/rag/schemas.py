from pydantic import BaseModel, Field

from app.query.schemas import SemanticSearchResult


class RagRequest(BaseModel):
    """
    Entrada del endpoint /rag.

    El usuario envía una pregunta y el sistema usa documentos
    recuperados para generar una respuesta.
    """

    query: str = Field(
        min_length=1,
        description="Pregunta que se responderá usando contexto documental",
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Número máximo de chunks solicitados para recuperar contexto",
    )

    search_mode: str = Field(
        default="hybrid",
        description="Modo de recuperación: semantic o hybrid",
    )

    metadata_filters: dict[str, str] | None = Field(
        default=None,
        description="Filtros opcionales por metadata documental",
    )


class HallucinationChecks(BaseModel):
    """
    Información pública sobre las comprobaciones de R71.
    """

    enabled: bool
    is_valid: bool
    fallback_applied: bool
    reason: str
    used_context_chunks: int
    context_was_limited: bool
    answer_overlap_terms: list[str]


class RagCitation(BaseModel):
    """
    Cita básica generada para una respuesta RAG.
    """

    citation_id: str
    document_id: str
    document_version_id: str
    document_title: str
    chunk_id: str
    chunk_index: int
    ranking_position: int | None = None
    relevance_label: str | None = None
    source_excerpt: str


class RagEvaluation(BaseModel):
    """
    Resultado público de la evaluación automática R73.
    """

    enabled: bool
    coherence_score: float
    relevance_score: float
    context_overlap_score: float
    citation_coverage_score: float
    overall_score: float
    verdict: str
    metrics: dict
    explanation: str


class RagUsageMetrics(BaseModel):
    """
    Métricas públicas de latencia y coste del flujo RAG.

    R74 añade este bloque para poder analizar cuánto tarda una consulta
    y qué coste aproximado tendría según los tokens estimados.
    """

    enabled: bool
    total_latency_ms: float
    retrieval_latency_ms: float
    llm_latency_ms: float
    prompt_tokens_estimated: int
    answer_tokens_estimated: int
    total_tokens_estimated: int
    estimated_cost_eur: float
    cost_model: str
    explanation: str


class RagResponse(BaseModel):
    """
    Respuesta del flujo RAG.

    R72 añade citas básicas.
    R73 añade evaluación automática.
    R74 añade métricas de latencia y coste.
    """

    message: str
    query: str
    user_id: str
    retrieved_chunks: int
    used_context_chunks: int
    prompt: str
    answer: str
    answer_status: str
    fallback_applied: bool
    hallucination_checks: HallucinationChecks
    citations: list[RagCitation]
    evaluation: RagEvaluation
    usage_metrics: RagUsageMetrics
    context: list[SemanticSearchResult]
    debug: dict