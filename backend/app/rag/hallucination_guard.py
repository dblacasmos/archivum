import re
from dataclasses import dataclass

from app.query.schemas import SemanticSearchResult


FALLBACK_ANSWER = (
    "No hay información suficiente en los documentos recuperados "
    "para responder con seguridad a esta pregunta."
)


@dataclass
class HallucinationCheckResult:
    """
    Resultado interno de las comprobaciones anti-alucinación.

    Esta clase no llama a ningún modelo de IA.
    Solo guarda si la respuesta es aceptable o si hay que usar fallback.
    """

    is_valid: bool
    fallback_applied: bool
    reason: str
    used_context_chunks: int
    context_was_limited: bool
    answer_overlap_terms: list[str]


class HallucinationGuard:
    """
    Servicio sencillo para reducir respuestas no fundamentadas.

    R71:
    - limita el número de fragmentos usados como contexto
    - comprueba que exista contexto documental
    - valida que la respuesta tenga relación básica con el contexto
    - aplica fallback cuando no se puede responder con seguridad
    """

    max_context_chunks = 5
    min_relevant_terms = 1

    stopwords = {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "de",
        "del",
        "a",
        "en",
        "y",
        "o",
        "que",
        "con",
        "por",
        "para",
        "se",
        "es",
        "son",
        "al",
        "como",
        "sobre",
        "esta",
        "este",
        "estos",
        "estas",
        "documento",
        "documentos",
        "contexto",
        "información",
    }

    unsupported_markers = [
        "no aparece en el contexto",
        "no está en el contexto",
        "no se menciona en el contexto",
        "no hay información suficiente",
        "no puedo determinar",
    ]

    def limit_context(
        self,
        context_chunks: list[SemanticSearchResult],
        requested_limit: int,
    ) -> list[SemanticSearchResult]:
        """
        Limita el contexto usado por el LLM.

        Aunque el usuario pida muchos resultados, el RAG solo debe usar
        una cantidad controlada para reducir ruido e invenciones.
        """
        safe_limit = min(requested_limit, self.max_context_chunks)
        return context_chunks[:safe_limit]

    def validate_context(
        self,
        context_chunks: list[SemanticSearchResult],
    ) -> HallucinationCheckResult:
        """
        Comprueba si existe contexto documental suficiente.

        Si no hay chunks, el sistema no debe pedir al LLM que improvise.
        La improvisación es fantástica para el jazz, no para un backend.
        """
        if not context_chunks:
            return HallucinationCheckResult(
                is_valid=False,
                fallback_applied=True,
                reason="No se recuperó contexto documental suficiente",
                used_context_chunks=0,
                context_was_limited=False,
                answer_overlap_terms=[],
            )

        return HallucinationCheckResult(
            is_valid=True,
            fallback_applied=False,
            reason="Contexto documental disponible",
            used_context_chunks=len(context_chunks),
            context_was_limited=False,
            answer_overlap_terms=[],
        )

    def validate_answer(
        self,
        answer: str,
        context_chunks: list[SemanticSearchResult],
        original_context_count: int,
    ) -> HallucinationCheckResult:
        """
        Valida de forma básica si la respuesta está apoyada en el contexto.

        No intenta demostrar verdad absoluta.
        Solo evita respuestas claramente desconectadas de los fragmentos.
        """
        clean_answer = answer.strip()

        if not clean_answer:
            return HallucinationCheckResult(
                is_valid=False,
                fallback_applied=True,
                reason="El modelo devolvió una respuesta vacía",
                used_context_chunks=len(context_chunks),
                context_was_limited=original_context_count > len(context_chunks),
                answer_overlap_terms=[],
            )

        normalized_answer = clean_answer.lower()

        if any(marker in normalized_answer for marker in self.unsupported_markers):
            return HallucinationCheckResult(
                is_valid=False,
                fallback_applied=True,
                reason="El modelo indicó falta de soporte documental",
                used_context_chunks=len(context_chunks),
                context_was_limited=original_context_count > len(context_chunks),
                answer_overlap_terms=[],
            )

        context_text = " ".join(
            chunk.chunk_content for chunk in context_chunks
        )

        context_terms = self._extract_relevant_terms(context_text)
        answer_terms = self._extract_relevant_terms(clean_answer)
        overlap_terms = sorted(context_terms.intersection(answer_terms))

        if len(overlap_terms) < self.min_relevant_terms:
            return HallucinationCheckResult(
                is_valid=False,
                fallback_applied=True,
                reason="La respuesta no comparte términos relevantes con el contexto",
                used_context_chunks=len(context_chunks),
                context_was_limited=original_context_count > len(context_chunks),
                answer_overlap_terms=overlap_terms,
            )

        return HallucinationCheckResult(
            is_valid=True,
            fallback_applied=False,
            reason="La respuesta tiene soporte básico en el contexto",
            used_context_chunks=len(context_chunks),
            context_was_limited=original_context_count > len(context_chunks),
            answer_overlap_terms=overlap_terms,
        )

    def apply_fallback_if_needed(
        self,
        answer: str,
        check_result: HallucinationCheckResult,
    ) -> str:
        """
        Devuelve la respuesta original o el fallback seguro.

        Si las validaciones fallan, se evita mostrar una respuesta inventada.
        """
        if check_result.fallback_applied:
            return FALLBACK_ANSWER

        return answer

    def _extract_relevant_terms(self, text: str) -> set[str]:
        """
        Extrae palabras útiles para comparar contexto y respuesta.

        Se eliminan palabras demasiado cortas y palabras comunes.
        """
        normalized_text = text.lower()
        raw_terms = re.findall(r"[a-záéíóúüñ0-9]{4,}", normalized_text)

        return {
            term
            for term in raw_terms
            if term not in self.stopwords
        }