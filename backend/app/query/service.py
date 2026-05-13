import hashlib
import math

from app.core.config import settings
from app.documents.embedding_repository import DocumentEmbeddingRepository
from app.documents.embeddings import OpenAIEmbeddingClient
from app.documents.repository import DocumentRepository
from app.query.ranking import ExplainableRankingService
from app.query.schemas import SemanticSearchResult


class SemanticSearchService:
    """
    Servicio de negocio para búsqueda documental.

    R50:
    - búsqueda semántica por embeddings.

    R51:
    - búsqueda híbrida combinando semántica + texto.

    R52:
    - ranking explicable sobre los resultados recuperados.

    R53:
    - filtros por metadata documental.

    R54:
    - seguridad por documento en retrieval aplicando filtro owner/ACL.
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        embedding_repo: DocumentEmbeddingRepository,
        embedding_client: OpenAIEmbeddingClient,
    ):
        self.document_repo = document_repo
        self.embedding_repo = embedding_repo
        self.embedding_client = embedding_client
        self.ranking_service = ExplainableRankingService()

    def _build_local_query_vector(self, query: str) -> list[float]:
        """
        Genera un vector local determinista si no hay API key.

        Sirve para desarrollo y tests sin depender de OpenAI.
        """
        normalized_query = query.strip().lower()

        if not normalized_query:
            raise ValueError("La consulta no puede estar vacía")

        vector = [0.0] * settings.openai_embeddings_dimensions
        digest = hashlib.sha256(normalized_query.encode("utf-8")).digest()

        for index, byte_value in enumerate(digest[:16]):
            position = (
                (index * 97 + byte_value)
                % settings.openai_embeddings_dimensions
            )

            vector[position] = (byte_value / 255.0) + 0.01

        norm = math.sqrt(sum(value * value for value in vector))

        if norm == 0:
            vector[0] = 1.0
            return vector

        return [value / norm for value in vector]

    def generate_query_embedding(self, query: str) -> list[float]:
        """
        Genera el embedding de la consulta del usuario.

        Primero intenta usar el cliente configurado.
        Si falla, usa un vector local para no romper el entorno
        de desarrollo.
        """
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("La consulta no puede estar vacía")

        try:
            provider_result = self.embedding_client.generate_embeddings(
                [clean_query]
            )

            return provider_result.vectors[0]

        except Exception:
            return self._build_local_query_vector(clean_query)

    def _build_similarity_score(
        self,
        metric: str,
        distance_value: float,
    ) -> float | None:
        """
        Convierte distancia vectorial en score entendible.

        Para coseno:
        - distancia 0 significa muy parecido.
        - score 1 significa muy relevante.
        """
        if metric != "cosine":
            return None

        similarity_score = 1.0 - float(distance_value)

        if similarity_score < 0.0:
            return 0.0

        if similarity_score > 1.0:
            return 1.0

        return round(similarity_score, 6)

    def _get_authorized_document_ids(self, current_user) -> list:
        """
        R54 - Devuelve solo los documentos autorizados para el usuario.

        Esta función es el filtro de seguridad del retrieval:
        - admin puede recuperar todos los documentos.
        - owner puede recuperar sus documentos.
        - un usuario con permiso explícito puede recuperar
          documentos compartidos.

        Importante:
        este filtro se aplica antes de llamar al repositorio
        de embeddings, así ningún chunk no autorizado llega
        al ranking.
        """
        visible_documents = self.document_repo.list_visible_documents(
            current_user
        )

        return [document.id for document in visible_documents]

    def _normalize_metadata_filters(
        self,
        metadata_filters: dict[str, str] | None,
    ) -> dict[str, str] | None:
        """
        Limpia filtros de metadata antes de enviarlos al repositorio.

        Si no hay filtros, devuelve None para que la búsqueda
        funcione igual que antes.
        """
        if not metadata_filters:
            return None

        normalized_filters: dict[str, str] = {}

        for key, value in metadata_filters.items():
            clean_key = str(key).strip()
            clean_value = str(value).strip()

            if not clean_key:
                raise ValueError(
                    "Las claves de metadata no pueden estar vacías"
                )

            if not clean_value:
                raise ValueError(
                    "Los valores de metadata no pueden estar vacíos"
                )

            normalized_filters[clean_key] = clean_value

        return normalized_filters

    def retrieve_similar_chunks(
        self,
        current_user,
        query_vector: list[float],
        limit: int = 5,
        metric: str = "cosine",
        metadata_filters: dict[str, str] | None = None,
    ) -> list[SemanticSearchResult]:
        """
        Recupera chunks usando solo búsqueda vectorial.

        En R53, antes de ordenar por similitud, se restringen
        los documentos usando metadata si el usuario ha indicado
        filtros.

        En R54, además se aplican restricciones de seguridad
        por ownership/permisos antes del retrieval.
        """
        visible_document_ids = self._get_authorized_document_ids(
            current_user
        )

        if not visible_document_ids:
            return []

        normalized_filters = self._normalize_metadata_filters(
            metadata_filters
        )

        raw_results = (
            self.embedding_repo.similarity_search_for_documents(
                document_ids=visible_document_ids,
                query_vector=query_vector,
                limit=limit,
                metric=metric,
                metadata_filters=normalized_filters,
            )
        )

        results: list[SemanticSearchResult] = []

        for item in raw_results:
            distance_value = float(item["distance_value"])

            similarity_score = self._build_similarity_score(
                metric=metric,
                distance_value=distance_value,
            )

            results.append(
                SemanticSearchResult(
                    document_id=item["document_id"],
                    document_version_id=item["document_version_id"],
                    title=item["document_title"],
                    chunk_id=item["chunk_id"],
                    chunk_index=item["chunk_index"],
                    chunk_content=item["chunk_content"],
                    distance_value=distance_value,
                    similarity_score=similarity_score,
                    textual_score=0.0,
                    hybrid_score=similarity_score,
                    match_source="semantic",
                )
            )

        return self.ranking_service.rank_results(
            results=results,
            limit=limit,
        )

    def retrieve_hybrid_chunks(
        self,
        current_user,
        query: str,
        query_vector: list[float],
        limit: int = 5,
        metric: str = "cosine",
        metadata_filters: dict[str, str] | None = None,
    ) -> list[SemanticSearchResult]:
        """
        Recupera chunks combinando búsqueda semántica y textual.

        En R53 se aplican los mismos filtros de metadata tanto
        en la parte semántica como en la textual.

        En R54 también se aplican restricciones de seguridad
        antes de ejecutar el retrieval.
        """
        visible_document_ids = self._get_authorized_document_ids(
            current_user
        )

        if not visible_document_ids:
            return []

        normalized_filters = self._normalize_metadata_filters(
            metadata_filters
        )

        semantic_rows = (
            self.embedding_repo.similarity_search_for_documents(
                document_ids=visible_document_ids,
                query_vector=query_vector,
                limit=limit,
                metric=metric,
                metadata_filters=normalized_filters,
            )
        )

        textual_rows = (
            self.embedding_repo.textual_search_for_documents(
                document_ids=visible_document_ids,
                query=query,
                limit=limit,
                metadata_filters=normalized_filters,
            )
        )

        combined_results: dict[str, SemanticSearchResult] = {}

        for item in semantic_rows:
            distance_value = float(item["distance_value"])

            similarity_score = self._build_similarity_score(
                metric=metric,
                distance_value=distance_value,
            )

            chunk_id = str(item["chunk_id"])

            combined_results[chunk_id] = SemanticSearchResult(
                document_id=item["document_id"],
                document_version_id=item["document_version_id"],
                title=item["document_title"],
                chunk_id=item["chunk_id"],
                chunk_index=item["chunk_index"],
                chunk_content=item["chunk_content"],
                distance_value=distance_value,
                similarity_score=similarity_score,
                textual_score=0.0,
                hybrid_score=similarity_score or 0.0,
                match_source="semantic",
            )

        for item in textual_rows:
            chunk_id = str(item["chunk_id"])
            textual_score = float(item["textual_score"])

            if chunk_id in combined_results:
                existing_result = combined_results[chunk_id]

                existing_result.textual_score = textual_score

                existing_result.hybrid_score = round(
                    (
                        (existing_result.similarity_score or 0.0)
                        + textual_score
                    ),
                    6,
                )

                existing_result.match_source = "semantic_textual"

            else:
                combined_results[chunk_id] = SemanticSearchResult(
                    document_id=item["document_id"],
                    document_version_id=item["document_version_id"],
                    title=item["document_title"],
                    chunk_id=item["chunk_id"],
                    chunk_index=item["chunk_index"],
                    chunk_content=item["chunk_content"],
                    distance_value=None,
                    similarity_score=0.0,
                    textual_score=textual_score,
                    hybrid_score=textual_score,
                    match_source="textual",
                )

        return self.ranking_service.rank_results(
            results=list(combined_results.values()),
            limit=limit,
        )

    def build_search_answer(
        self,
        query: str,
        results: list[SemanticSearchResult],
    ) -> str:
        """
        Genera un resumen sencillo de la búsqueda.
        """
        if not results:
            return (
                f"No se han encontrado fragmentos relevantes "
                f"para la consulta '{query}'."
            )

        best_result = results[0]

        return (
            f"Se han recuperado {len(results)} fragmentos relevantes. "
            f"El resultado principal pertenece al documento "
            f"'{best_result.title}', "
            f"corresponde al chunk {best_result.chunk_index} "
            f"y tiene una relevancia "
            f"{best_result.relevance_label}."
        )