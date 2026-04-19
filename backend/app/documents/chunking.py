from dataclasses import dataclass


@dataclass
class ChunkPiece:
    """
    Representa un fragmento de texto ya calculado.
    """

    chunk_index: int
    content: str
    char_count: int
    start_char: int
    end_char: int


class TextChunkingService:
    """
    Servicio sencillo de chunking por caracteres con solapamiento.

    Se ha optado por una estrategia básica y fácil de justificar:
    - tamaño máximo configurable en caracteres
    - solapamiento configurable entre chunks
    - intento de cortar por espacio para no partir palabras cuando sea posible

    No es una técnica avanzada, pero encaja con el alcance de R31.
    """

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[ChunkPiece]:
        """
        Divide un texto grande en fragmentos más pequeños.
        """
        clean_text = self._normalize_text(text)

        if not clean_text:
            raise ValueError("No hay texto disponible para fragmentar")

        if chunk_size <= 0:
            raise ValueError("El tamaño del chunk debe ser mayor que cero")

        if chunk_overlap < 0:
            raise ValueError("El solapamiento no puede ser negativo")

        if chunk_overlap >= chunk_size:
            raise ValueError("El solapamiento debe ser menor que el tamaño del chunk")

        chunks: list[ChunkPiece] = []
        start = 0
        text_length = len(clean_text)
        chunk_index = 0

        while start < text_length:
            raw_end = min(start + chunk_size, text_length)
            end = self._adjust_end_to_word_boundary(clean_text, start, raw_end)

            # Si por alguna razón no hemos avanzado, usamos el final bruto
            # para evitar bucles infinitos.
            if end <= start:
                end = raw_end

            content = clean_text[start:end].strip()

            if content:
                real_start = clean_text.find(content, start, end)
                real_end = real_start + len(content)

                chunks.append(
                    ChunkPiece(
                        chunk_index=chunk_index,
                        content=content,
                        char_count=len(content),
                        start_char=real_start,
                        end_char=real_end,
                    )
                )
                chunk_index += 1

            if end >= text_length:
                break

            start = max(end - chunk_overlap, start + 1)

        return chunks

    def _normalize_text(self, text: str) -> str:
        """
        Limpia espacios extra manteniendo saltos de línea razonables.
        """
        lines = [line.strip() for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]
        return "\n".join(non_empty_lines).strip()

    def _adjust_end_to_word_boundary(self, text: str, start: int, raw_end: int) -> int:
        """
        Intenta cortar en el último espacio cercano al final del chunk
        para no romper palabras de forma innecesaria.
        """
        if raw_end >= len(text):
            return raw_end

        minimum_acceptable_end = start + max(1, int((raw_end - start) * 0.6))
        candidate = raw_end

        while candidate > minimum_acceptable_end and not text[candidate - 1].isspace():
            candidate -= 1

        return candidate if candidate > minimum_acceptable_end else raw_end