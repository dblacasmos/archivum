import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """
    Cuerpo de entrada para el endpoint /query.

    En R50 se usaba para búsqueda semántica.
    En R51 se añadió search_mode para pedir búsqueda híbrida.
    En R52 se mantiene el ranking explicable automático.
    En R53 se añade metadata_filters para filtrar por metadata documental.
    """

    query: str = Field(
        min_length=1,
        description="Texto que el usuario quiere buscar",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número máximo de resultados a devolver",
    )
    metric: str = Field(
        default="cosine",
        description="Métrica vectorial a usar: cosine, l2 o inner_product",
    )
    search_mode: str = Field(
        default="semantic",
        description="Modo de búsqueda: semantic o hybrid",
    )
    metadata_filters: dict[str, str] | None = Field(
        default=None,
        description=(
            "Filtros por metadata documental en formato clave-valor. "
            "Ejemplo: {'category': 'legal', 'language': 'es'}"
        ),
    )


class SemanticSearchResult(BaseModel):
    """
    Representa un resultado individual devuelto por la búsqueda.

    En R52 se añaden campos explicables de ranking:
    - ranking_score: puntuación final usada para ordenar.
    - ranking_position: posición final del resultado.
    - relevance_label: etiqueta sencilla de relevancia.
    - relevance_explanation: explicación legible para el usuario.
    - ranking_factors: señales usadas para calcular el ranking.
    """

    document_id: uuid.UUID
    document_version_id: uuid.UUID
    title: str
    chunk_id: uuid.UUID
    chunk_index: int
    chunk_content: str

    distance_value: float | None = None
    similarity_score: float | None = None
    textual_score: float | None = None
    hybrid_score: float | None = None
    match_source: str = "semantic"

    ranking_score: float | None = None
    ranking_position: int | None = None
    relevance_label: str | None = None
    relevance_explanation: str | None = None
    ranking_factors: dict | None = None


class QueryResponse(BaseModel):
    """
    Respuesta pública del endpoint /query.

    La estructura mantiene los campos anteriores y devuelve dentro de results
    la información explicable del ranking.
    """

    message: str
    query: str
    user_id: str
    retrieved_chunks: int
    answer: str
    observability_ready: bool
    results: list[SemanticSearchResult]
    debug: dict