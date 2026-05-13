from app.query.schemas import SemanticSearchResult


class ExplainableRankingService:
    """
    Servicio encargado de ordenar resultados y explicar por qué son relevantes.

    No usa modelos complejos ni explicabilidad avanzada.
    Solo convierte las señales ya disponibles en una puntuación clara:
    - similitud semántica
    - coincidencia textual
    - origen del resultado
    """

    def rank_results(
        self,
        results: list[SemanticSearchResult],
        limit: int,
    ) -> list[SemanticSearchResult]:
        """
        Ordena los resultados por relevancia explicable.

        Primero calcula la información de ranking de cada resultado.
        Después los ordena de mayor a menor puntuación.
        """
        ranked_results: list[SemanticSearchResult] = []

        for result in results:
            ranked_result = self._add_ranking_information(result)
            ranked_results.append(ranked_result)

        ordered_results = sorted(
            ranked_results,
            key=lambda item: (
                item.ranking_score or 0.0,
                item.hybrid_score or 0.0,
                item.similarity_score or 0.0,
                item.textual_score or 0.0,
            ),
            reverse=True,
        )

        for index, result in enumerate(ordered_results, start=1):
            result.ranking_position = index

        return ordered_results[:limit]

    def _add_ranking_information(
        self,
        result: SemanticSearchResult,
    ) -> SemanticSearchResult:
        """
        Añade score, etiqueta y explicación al resultado.

        La idea es que el usuario pueda ver por qué un chunk aparece arriba.
        """
        semantic_score = result.similarity_score or 0.0
        textual_score = result.textual_score or 0.0

        if result.match_source == "semantic_textual":
            base_score = ((semantic_score + textual_score) / 2.0)
            source_bonus = 0.15
        elif result.match_source == "semantic":
            base_score = semantic_score
            source_bonus = 0.05
        elif result.match_source == "textual":
            base_score = textual_score
            source_bonus = 0.0
        else:
            base_score = result.hybrid_score or semantic_score or textual_score
            source_bonus = 0.0

        ranking_score = min(base_score + source_bonus, 1.0)

        result.ranking_score = round(ranking_score, 6)
        result.relevance_label = self._build_relevance_label(result.ranking_score)
        result.ranking_factors = {
            "semantic_score": semantic_score,
            "textual_score": textual_score,
            "source_bonus": source_bonus,
            "match_source": result.match_source,
        }
        result.relevance_explanation = self._build_explanation(result)

        return result

    def _build_relevance_label(self, ranking_score: float) -> str:
        """
        Traduce una puntuación numérica a una etiqueta sencilla.
        """
        if ranking_score >= 0.85:
            return "alta"

        if ranking_score >= 0.50:
            return "media"

        return "baja"

    def _build_explanation(self, result: SemanticSearchResult) -> str:
        """
        Genera una explicación corta en español para el resultado.
        """
        if result.match_source == "semantic_textual":
            return (
                "Resultado muy relevante porque combina similitud semántica "
                "con coincidencia textual directa en el contenido."
            )

        if result.match_source == "semantic":
            return (
                "Resultado relevante porque su embedding es cercano al embedding "
                "de la consulta realizada."
            )

        if result.match_source == "textual":
            return (
                "Resultado relevante porque contiene términos que coinciden "
                "literalmente con la consulta."
            )

        return (
            "Resultado incluido por las señales básicas disponibles durante "
            "el proceso de búsqueda."
        )