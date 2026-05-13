from app.query.schemas import SemanticSearchResult


class CitationService:
    """
    Servicio encargado de crear citas básicas para el flujo RAG.

    R72:
    - recibe los chunks usados como contexto
    - genera referencias simples y trazables
    - evita formateos académicos complejos
    """

    def build_citations(
        self,
        context_chunks: list[SemanticSearchResult],
    ) -> list[dict]:
        """
        Construye una lista de citas a partir de los chunks usados.

        Cada cita apunta al documento y al chunk concreto que participó
        en la generación de la respuesta. Así el usuario puede saber de
        dónde sale la información.
        """
        citations: list[dict] = []

        for citation_number, chunk in enumerate(context_chunks, start=1):
            citations.append(
                {
                    "citation_id": f"[{citation_number}]",
                    "document_id": str(chunk.document_id),
                    "document_version_id": str(chunk.document_version_id),
                    "document_title": chunk.title,
                    "chunk_id": str(chunk.chunk_id),
                    "chunk_index": chunk.chunk_index,
                    "ranking_position": chunk.ranking_position,
                    "relevance_label": chunk.relevance_label,
                    "source_excerpt": self._build_excerpt(chunk.chunk_content),
                }
            )

        return citations

    def _build_excerpt(self, text: str, max_length: int = 180) -> str:
        """
        Recorta el contenido del chunk para mostrar una referencia legible.

        No se devuelve el chunk completo para evitar respuestas enormes.
        """
        clean_text = " ".join(text.split())

        if len(clean_text) <= max_length:
            return clean_text

        return f"{clean_text[:max_length].rstrip()}..."