from dataclasses import dataclass


@dataclass
class RagUsageMetricsResult:
    """
    Resultado interno de las métricas de uso del sistema RAG.

    Se usa para mover datos simples entre el servicio de métricas
    y el flujo RAG sin mezclar esta lógica con la generación de respuestas.
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


class RagUsageMetricsService:
    """
    Servicio de métricas de latencia y coste del flujo RAG.

    R74:
    - mide tiempos básicos del flujo RAG
    - estima tokens de entrada y salida
    - calcula un coste aproximado por consulta
    - evita depender de APIs externas para medir coste real
    """

    INPUT_COST_PER_1000_TOKENS_EUR = 0.00015
    OUTPUT_COST_PER_1000_TOKENS_EUR = 0.00060
    COST_MODEL_NAME = "estimacion_academica_basica"

    def build_metrics(
        self,
        total_latency_ms: float,
        retrieval_latency_ms: float,
        llm_latency_ms: float,
        prompt: str,
        answer: str,
    ) -> RagUsageMetricsResult:
        """
        Construye las métricas públicas de uso para una consulta RAG.

        El cálculo de tokens es aproximado: se estima 1 token por cada
        4 caracteres. No busca facturación exacta, sino una referencia
        coherente para analizar el comportamiento del sistema.
        """
        prompt_tokens = self._estimate_tokens(prompt)
        answer_tokens = self._estimate_tokens(answer)
        total_tokens = prompt_tokens + answer_tokens

        input_cost = (
            prompt_tokens / 1000
        ) * self.INPUT_COST_PER_1000_TOKENS_EUR

        output_cost = (
            answer_tokens / 1000
        ) * self.OUTPUT_COST_PER_1000_TOKENS_EUR

        estimated_cost = round(input_cost + output_cost, 6)

        return RagUsageMetricsResult(
            enabled=True,
            total_latency_ms=round(total_latency_ms, 2),
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            llm_latency_ms=round(llm_latency_ms, 2),
            prompt_tokens_estimated=prompt_tokens,
            answer_tokens_estimated=answer_tokens,
            total_tokens_estimated=total_tokens,
            estimated_cost_eur=estimated_cost,
            cost_model=self.COST_MODEL_NAME,
            explanation=(
                "Métricas RAG calculadas con latencia medida en ejecución "
                "y coste estimado mediante tokens aproximados."
            ),
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        Estima tokens de forma simple a partir del tamaño del texto.

        Se usa max(1, ...) para evitar que textos pequeños devuelvan cero
        y rompan el análisis de coste.
        """
        clean_text = text or ""
        estimated_tokens = len(clean_text) // 4

        return max(1, estimated_tokens)