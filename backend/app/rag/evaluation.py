import re
from dataclasses import dataclass

from app.query.schemas import SemanticSearchResult


@dataclass
class EvaluationResult:
    """
    Resultado interno de la evaluación automática R73.

    Se usa dataclass porque solo necesitamos mover datos simples
    entre el servicio de evaluación y el flujo RAG.
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


class RagEvaluationService:
    """
    Servicio de evaluación automática de respuestas RAG.

    R73:
    - calcula métricas básicas de coherencia y relevancia
    - compara pregunta, respuesta y contexto documental
    - registra un resultado simple y entendible
    - evita métricas avanzadas de NLP porque quedan fuera del alcance
    """

    def evaluate_answer(
        self,
        query: str,
        answer: str,
        context_chunks: list[SemanticSearchResult],
        citations: list[dict],
        answer_status: str,
        fallback_applied: bool,
    ) -> EvaluationResult:
        """
        Evalúa una respuesta generada por el flujo RAG.

        La evaluación es básica y determinista:
        - no llama a ningún modelo externo
        - no necesita APIs adicionales
        - sirve para comprobar si la respuesta está apoyada en el contexto
        """
        query_terms = self._extract_terms(query)
        answer_terms = self._extract_terms(answer)
        context_terms = self._extract_context_terms(context_chunks)

        context_overlap_score = self._calculate_context_overlap_score(
            answer_terms=answer_terms,
            context_terms=context_terms,
        )

        relevance_score = self._calculate_relevance_score(
            query_terms=query_terms,
            answer_terms=answer_terms,
            context_terms=context_terms,
        )

        citation_coverage_score = self._calculate_citation_coverage_score(
            context_chunks=context_chunks,
            citations=citations,
        )

        coherence_score = self._calculate_coherence_score(
            answer=answer,
            answer_status=answer_status,
            fallback_applied=fallback_applied,
            context_overlap_score=context_overlap_score,
        )

        overall_score = round(
            (
                coherence_score * 0.35
                + relevance_score * 0.35
                + context_overlap_score * 0.20
                + citation_coverage_score * 0.10
            ),
            3,
        )

        verdict = self._build_verdict(overall_score=overall_score)

        metrics = {
            "query_terms_count": len(query_terms),
            "answer_terms_count": len(answer_terms),
            "context_terms_count": len(context_terms),
            "context_chunks_count": len(context_chunks),
            "citations_count": len(citations),
            "fallback_applied": fallback_applied,
            "answer_status": answer_status,
        }

        explanation = self._build_explanation(
            verdict=verdict,
            coherence_score=coherence_score,
            relevance_score=relevance_score,
            context_overlap_score=context_overlap_score,
            citation_coverage_score=citation_coverage_score,
        )

        return EvaluationResult(
            enabled=True,
            coherence_score=coherence_score,
            relevance_score=relevance_score,
            context_overlap_score=context_overlap_score,
            citation_coverage_score=citation_coverage_score,
            overall_score=overall_score,
            verdict=verdict,
            metrics=metrics,
            explanation=explanation,
        )

    def _extract_terms(self, text: str) -> set[str]:
        """
        Extrae palabras útiles de un texto.

        Se eliminan palabras demasiado cortas para evitar que artículos
        como "el", "la" o "de" distorsionen la métrica.
        """
        normalized_text = text.lower()
        raw_terms = re.findall(r"[a-záéíóúñü0-9]+", normalized_text)

        return {
            term
            for term in raw_terms
            if len(term) >= 4
        }

    def _extract_context_terms(
        self,
        context_chunks: list[SemanticSearchResult],
    ) -> set[str]:
        """
        Une los términos de todos los chunks usados como contexto.

        Así se puede comparar la respuesta contra el contexto documental
        completo que recibió el modelo.
        """
        context_terms: set[str] = set()

        for chunk in context_chunks:
            context_terms.update(self._extract_terms(chunk.chunk_content))

        return context_terms

    def _calculate_context_overlap_score(
        self,
        answer_terms: set[str],
        context_terms: set[str],
    ) -> float:
        """
        Calcula cuánto vocabulario de la respuesta aparece en el contexto.

        Si la respuesta usa términos presentes en los documentos, sube.
        Si responde con cosas externas, baja. La humanidad lo llama sentido común.
        """
        if not answer_terms or not context_terms:
            return 0.0

        overlap_terms = answer_terms.intersection(context_terms)

        return round(len(overlap_terms) / len(answer_terms), 3)

    def _calculate_relevance_score(
        self,
        query_terms: set[str],
        answer_terms: set[str],
        context_terms: set[str],
    ) -> float:
        """
        Calcula una relevancia básica entre pregunta, respuesta y contexto.

        La respuesta puntúa mejor si comparte términos con la pregunta
        o si esos términos aparecen en el contexto recuperado.
        """
        if not query_terms:
            return 0.0

        supported_terms = answer_terms.union(context_terms)
        matched_terms = query_terms.intersection(supported_terms)

        return round(len(matched_terms) / len(query_terms), 3)

    def _calculate_citation_coverage_score(
        self,
        context_chunks: list[SemanticSearchResult],
        citations: list[dict],
    ) -> float:
        """
        Calcula si los chunks usados tienen citas asociadas.

        En R72 ya se generan citas, aquí solo comprobamos que la cobertura
        sea coherente con el contexto utilizado.
        """
        if not context_chunks:
            return 0.0

        return round(min(len(citations) / len(context_chunks), 1.0), 3)

    def _calculate_coherence_score(
        self,
        answer: str,
        answer_status: str,
        fallback_applied: bool,
        context_overlap_score: float,
    ) -> float:
        """
        Calcula una coherencia básica de la respuesta.

        Si hay fallback, la coherencia no es cero porque el sistema ha evitado
        inventar, pero tampoco se considera una respuesta completa generada.
        """
        clean_answer = answer.strip()

        if not clean_answer:
            return 0.0

        if fallback_applied or answer_status == "fallback":
            return 0.5

        if context_overlap_score >= 0.45:
            return 1.0

        if context_overlap_score >= 0.25:
            return 0.7

        return 0.3

    def _build_verdict(self, overall_score: float) -> str:
        """
        Convierte la puntuación global en una etiqueta sencilla.

        Esto permite leer el resultado sin interpretar decimales como si
        fueran una profecía matemática.
        """
        if overall_score >= 0.75:
            return "good"

        if overall_score >= 0.45:
            return "acceptable"

        return "weak"

    def _build_explanation(
        self,
        verdict: str,
        coherence_score: float,
        relevance_score: float,
        context_overlap_score: float,
        citation_coverage_score: float,
    ) -> str:
        """
        Genera una explicación legible de la evaluación.

        La explicación está pensada para aparecer en la respuesta JSON
        y poder usarse como evidencia en Swagger o en tests.
        """
        return (
            f"Evaluación {verdict}: "
            f"coherencia={coherence_score}, "
            f"relevancia={relevance_score}, "
            f"solapamiento_contexto={context_overlap_score}, "
            f"cobertura_citas={citation_coverage_score}."
        )