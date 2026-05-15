from time import perf_counter

from app.core.metrics import run_observed_stage
from app.query.schemas import SemanticSearchResult
from app.query.service import SemanticSearchService
from app.rag.citations import CitationService
from app.rag.evaluation import RagEvaluationService
from app.rag.hallucination_guard import HallucinationGuard
from app.rag.llm_client import OpenAIChatClient
from app.rag.usage_metrics import RagUsageMetricsService


class BasicRagService:
    """
    Servicio principal del flujo RAG.

    R70:
    - recupera contexto
    - construye prompt
    - genera respuesta

    R71:
    - limita contexto
    - valida respuesta
    - aplica fallback

    R72:
    - genera citas básicas

    R73:
    - evalúa automáticamente la respuesta

    R74:
    - mide latencia total
    - mide latencia del retrieval
    - mide latencia del LLM
    - estima tokens y coste por consulta
    """

    def __init__(
        self,
        search_service: SemanticSearchService,
        llm_client: OpenAIChatClient,
        hallucination_guard: HallucinationGuard | None = None,
        citation_service: CitationService | None = None,
        evaluation_service: RagEvaluationService | None = None,
        usage_metrics_service: RagUsageMetricsService | None = None,
    ):
        """
        Inicializa el servicio RAG con sus dependencias.

        Las dependencias auxiliares se pueden inyectar desde tests para
        controlar el comportamiento sin llamar a servicios externos.
        """
        self.search_service = search_service
        self.llm_client = llm_client
        self.hallucination_guard = hallucination_guard or HallucinationGuard()
        self.citation_service = citation_service or CitationService()
        self.evaluation_service = evaluation_service or RagEvaluationService()
        self.usage_metrics_service = (
            usage_metrics_service or RagUsageMetricsService()
        )

    def retrieve_context(
        self,
        current_user,
        query: str,
        limit: int,
        search_mode: str,
        metadata_filters: dict[str, str] | None = None,
    ) -> list[SemanticSearchResult]:
        """
        Recupera los fragmentos relevantes para la pregunta.

        Reutiliza el servicio de búsqueda para mantener seguridad,
        ranking, filtros y recuperación en un único punto.
        """
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("La consulta RAG no puede estar vacía")

        query_embedding = run_observed_stage(
            stage="embedding",
            action=lambda: self.search_service.generate_query_embedding(
                clean_query
            ),
        )

        if search_mode == "semantic":
            return run_observed_stage(
                stage="retrieval",
                action=lambda: self.search_service.retrieve_similar_chunks(
                    current_user=current_user,
                    query_vector=query_embedding,
                    limit=limit,
                    metric="cosine",
                    metadata_filters=metadata_filters,
                ),
            )

        if search_mode == "hybrid":
            return run_observed_stage(
                stage="retrieval",
                action=lambda: self.search_service.retrieve_hybrid_chunks(
                    current_user=current_user,
                    query=clean_query,
                    query_vector=query_embedding,
                    limit=limit,
                    metric="cosine",
                    metadata_filters=metadata_filters,
                ),
            )

        raise ValueError("Modo de búsqueda no soportado. Usa semantic o hybrid")

    def filter_relevant_context(
        self,
        query: str,
        context_chunks: list[SemanticSearchResult],
    ) -> list[SemanticSearchResult]:
        """
        Filtra chunks poco relevantes antes de construir el prompt RAG.

        Se prioriza la coincidencia real de términos importantes de la
        pregunta dentro del contenido del chunk, evitando usar documentos
        accesibles pero no relacionados.
        """
        clean_query = query.lower().strip()

        if not clean_query or not context_chunks:
            return []

        # Palabras vacías que no aportan intención documental.
        stopwords = {
            "como",
            "cómo",
            "que",
            "qué",
            "para",
            "sobre",
            "desde",
            "donde",
            "dónde",
            "cuando",
            "cuándo",
            "gestionan",
            "gestiona",
            "gestion",
            "gestión",
            "empleados",
            "trabajadores",
            "documento",
            "sistema",
        }

        query_terms = [
            term.strip("¿?.,;:()[]{}")
            for term in clean_query.split()
            if len(term.strip("¿?.,;:()[]{}")) >= 4
            and term.strip("¿?.,;:()[]{}") not in stopwords
        ]

        # Reglas explícitas para consultas conocidas del dominio.
        if "vacaciones" in clean_query:
            required_terms = {"vacaciones"}
        elif "despido" in clean_query:
            required_terms = {"despido", "disciplinario", "contrato"}
        elif "rag" in clean_query or "pipeline" in clean_query or "embeddings" in clean_query:
            required_terms = {"rag", "pipeline", "embeddings", "vectorial", "chunks"}
        else:
            required_terms = set(query_terms)

        filtered_chunks: list[SemanticSearchResult] = []

        for chunk in context_chunks:
            chunk_text = (chunk.chunk_content or "").lower()

            has_required_match = any(
                term in chunk_text
                for term in required_terms
            )

            if has_required_match:
                filtered_chunks.append(chunk)

        return filtered_chunks

    def build_prompt(
        self,
        query: str,
        context_chunks: list[SemanticSearchResult],
    ) -> str:
        """
        Construye el prompt enviado al LLM.

        Cada chunk se etiqueta como fuente para poder relacionar
        la respuesta con las citas generadas.
        """
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("La pregunta no puede estar vacía")

        if not context_chunks:
            return (
                "No se ha recuperado contexto documental suficiente.\n\n"
                f"Pregunta del usuario:\n{clean_query}\n\n"
                "Responde indicando que no hay información suficiente "
                "en los documentos recuperados."
            )

        context_lines: list[str] = []

        for index, chunk in enumerate(context_chunks, start=1):
            context_lines.append(
                (
                    f"[Fuente {index}]\n"
                    f"Documento: {chunk.title}\n"
                    f"Chunk: {chunk.chunk_index}\n"
                    f"Contenido:\n{chunk.chunk_content}"
                )
            )

        context_text = "\n\n".join(context_lines)

        return (
            "Usa únicamente el siguiente contexto documental para responder.\n"
            "Cuando uses información de una fuente, puedes apoyarte en su número de fuente.\n"
            "No inventes información que no aparezca en el contexto.\n"
            "Si el contexto no permite responder, indica que no hay información suficiente.\n\n"
            f"Contexto documental:\n{context_text}\n\n"
            f"Pregunta del usuario:\n{clean_query}\n\n"
            "Respuesta:"
        )

    def generate_response(
        self,
        current_user,
        query: str,
        limit: int = 5,
        search_mode: str = "hybrid",
        metadata_filters: dict[str, str] | None = None,
    ) -> dict:
        """
        Ejecuta el flujo RAG completo.

        También mide tiempos y estima coste para cumplir R74.
        """
        total_start = perf_counter()

        retrieval_start = perf_counter()
        retrieved_context_chunks = self.retrieve_context(
            current_user=current_user,
            query=query,
            limit=limit,
            search_mode=search_mode,
            metadata_filters=metadata_filters,
        )
        retrieval_latency_ms = (perf_counter() - retrieval_start) * 1000

        relevant_context_chunks = self.filter_relevant_context(
            query=query,
            context_chunks=retrieved_context_chunks,
        )

        limited_context_chunks = self.hallucination_guard.limit_context(
            context_chunks=relevant_context_chunks,
            requested_limit=limit,
        )

        context_check = self.hallucination_guard.validate_context(
            context_chunks=limited_context_chunks,
        )

        prompt = self.build_prompt(
            query=query,
            context_chunks=limited_context_chunks,
        )

        citations = self.citation_service.build_citations(
            context_chunks=limited_context_chunks,
        )

        llm_latency_ms = 0.0

        if not context_check.is_valid:
            safe_answer = self.hallucination_guard.apply_fallback_if_needed(
                answer="",
                check_result=context_check,
            )

            answer_status = "fallback"

            evaluation = self.evaluation_service.evaluate_answer(
                query=query,
                answer=safe_answer,
                context_chunks=limited_context_chunks,
                citations=citations,
                answer_status=answer_status,
                fallback_applied=True,
            )

            total_latency_ms = (perf_counter() - total_start) * 1000

            usage_metrics = self.usage_metrics_service.build_metrics(
                total_latency_ms=total_latency_ms,
                retrieval_latency_ms=retrieval_latency_ms,
                llm_latency_ms=llm_latency_ms,
                prompt=prompt,
                answer=safe_answer,
            )

            return {
                "prompt": prompt,
                "answer": safe_answer,
                "answer_status": answer_status,
                "fallback_applied": True,
                "hallucination_checks": context_check,
                "citations": citations,
                "evaluation": evaluation,
                "usage_metrics": usage_metrics,
                "context": limited_context_chunks,
                "retrieved_context_count": len(retrieved_context_chunks),
            }

        llm_start = perf_counter()
        generated_answer = run_observed_stage(
            stage="llm",
            action=lambda: self.llm_client.generate_answer(prompt),
        )
        llm_latency_ms = (perf_counter() - llm_start) * 1000

        answer_check = self.hallucination_guard.validate_answer(
            answer=generated_answer,
            context_chunks=limited_context_chunks,
            original_context_count=len(retrieved_context_chunks),
        )

        safe_answer = self.hallucination_guard.apply_fallback_if_needed(
            answer=generated_answer,
            check_result=answer_check,
        )

        answer_status = (
            "fallback" if answer_check.fallback_applied else "generated"
        )

        evaluation = self.evaluation_service.evaluate_answer(
            query=query,
            answer=safe_answer,
            context_chunks=limited_context_chunks,
            citations=citations,
            answer_status=answer_status,
            fallback_applied=answer_check.fallback_applied,
        )

        total_latency_ms = (perf_counter() - total_start) * 1000

        usage_metrics = self.usage_metrics_service.build_metrics(
            total_latency_ms=total_latency_ms,
            retrieval_latency_ms=retrieval_latency_ms,
            llm_latency_ms=llm_latency_ms,
            prompt=prompt,
            answer=safe_answer,
        )

        return {
            "prompt": prompt,
            "answer": safe_answer,
            "answer_status": answer_status,
            "fallback_applied": answer_check.fallback_applied,
            "hallucination_checks": answer_check,
            "citations": citations,
            "evaluation": evaluation,
            "usage_metrics": usage_metrics,
            "context": limited_context_chunks,
            "retrieved_context_count": len(retrieved_context_chunks),
        }