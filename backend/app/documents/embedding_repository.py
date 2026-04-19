import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.documents.models import DocumentChunk, DocumentEmbedding


class DocumentEmbeddingRepository:
    """
    Repositorio específico para trabajar con chunks y embeddings.

    En R42 añadimos también una consulta vectorial básica
    para demostrar que los embeddings almacenados en pgvector
    pueden recuperarse por similitud.
    """

    def __init__(self, db: Session):
        self.db = db

    def list_chunks_for_version(self, document_version_id: uuid.UUID) -> list[DocumentChunk]:
        """
        Devuelve todos los chunks de una versión concreta ordenados
        por su índice natural.
        """
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_version_id == document_version_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_embeddings_for_version(self, document_version_id: uuid.UUID) -> list[DocumentEmbedding]:
        """
        Devuelve los embeddings ya persistidos para una versión concreta.
        """
        stmt = (
            select(DocumentEmbedding)
            .where(DocumentEmbedding.document_version_id == document_version_id)
            .order_by(DocumentEmbedding.generated_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_embedding_by_chunk_id(self, chunk_id: uuid.UUID) -> DocumentEmbedding | None:
        """
        Busca el embedding asociado a un chunk concreto.
        """
        stmt = select(DocumentEmbedding).where(DocumentEmbedding.chunk_id == chunk_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def replace_embeddings_for_chunks(
        self,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        model_name: str,
        provider: str = "openai",
    ) -> list[DocumentEmbedding]:
        """
        Crea o actualiza los embeddings de todos los chunks de una versión.

        Si ya existían embeddings previos para esos chunks, se sustituyen.
        """
        if len(chunks) != len(vectors):
            raise ValueError(
                "El número de chunks no coincide con el número de embeddings generados"
            )

        saved_embeddings: list[DocumentEmbedding] = []

        for chunk, vector in zip(chunks, vectors, strict=True):
            existing_embedding = self.get_embedding_by_chunk_id(chunk.id)

            if existing_embedding is None:
                embedding = DocumentEmbedding(
                    document_id=document_id,
                    document_version_id=document_version_id,
                    chunk_id=chunk.id,
                    provider=provider,
                    model_name=model_name,
                    dimensions=len(vector),
                    embedding_vector=vector,
                    status="completed",
                    error_message=None,
                    generated_at=datetime.now(timezone.utc),
                )
            else:
                existing_embedding.provider = provider
                existing_embedding.model_name = model_name
                existing_embedding.dimensions = len(vector)
                existing_embedding.embedding_vector = vector
                existing_embedding.status = "completed"
                existing_embedding.error_message = None
                existing_embedding.generated_at = datetime.now(timezone.utc)
                embedding = existing_embedding

            self.db.add(embedding)
            saved_embeddings.append(embedding)

        self.db.commit()

        for item in saved_embeddings:
            self.db.refresh(item)

        return saved_embeddings

    def _build_vector_literal(self, vector: list[float]) -> str:
        """
        Convierte una lista Python a la sintaxis textual que entiende pgvector.

        Ejemplo:
        [1.0, 2.0, 3.0] -> "[1.0,2.0,3.0]"
        """
        if not vector:
            raise ValueError("La consulta vectorial necesita un vector no vacío")

        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def _get_distance_operator(self, metric: str) -> str:
        """
        Devuelve el operador SQL de pgvector según la métrica solicitada.

        Métricas soportadas en esta fase:
        - cosine: distancia por coseno
        - l2: distancia euclídea
        - inner_product: producto interno negativo

        No abrimos la puerta a cualquier texto para evitar SQL inseguro.
        """
        supported_metrics = {
            "cosine": "<=>",
            "l2": "<->",
            "inner_product": "<#>",
        }

        operator = supported_metrics.get(metric)
        if operator is None:
            raise ValueError(
                "Métrica no soportada. Usa una de estas: cosine, l2, inner_product"
            )

        return operator

    def similarity_search_by_vector(
        self,
        document_version_id: uuid.UUID,
        query_vector: list[float],
        limit: int = 5,
        metric: str = "cosine",
    ) -> list[dict]:
        """
        Ejecuta una consulta vectorial básica contra los embeddings
        de una versión documental concreta.

        Esta función NO implementa aún la búsqueda semántica completa de R50.
        Aquí solo demostramos la parte de infraestructura:
        - ya existe el vector guardado
        - ya existe el índice
        - ya podemos ordenar por similitud

        Devuelve una lista simple de resultados con distancia calculada.
        """
        if limit < 1:
            raise ValueError("El límite de resultados debe ser mayor que cero")

        vector_literal = self._build_vector_literal(query_vector)
        distance_operator = self._get_distance_operator(metric)

        stmt = text(
            f"""
            SELECT
                de.id AS embedding_id,
                de.chunk_id AS chunk_id,
                dc.chunk_index AS chunk_index,
                dc.content AS chunk_content,
                de.model_name AS model_name,
                de.dimensions AS dimensions,
                de.embedding_vector {distance_operator} CAST(:query_vector AS vector) AS distance_value
            FROM document_embeddings AS de
            INNER JOIN document_chunks AS dc
                ON dc.id = de.chunk_id
            WHERE de.document_version_id = :document_version_id
            ORDER BY de.embedding_vector {distance_operator} CAST(:query_vector AS vector)
            LIMIT :limit_value
            """
        )

        rows = self.db.execute(
            stmt,
            {
                "document_version_id": document_version_id,
                "query_vector": vector_literal,
                "limit_value": limit,
            },
        ).mappings().all()

        return [dict(row) for row in rows]