import uuid
from datetime import datetime, timezone

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.documents.models import DocumentChunk, DocumentEmbedding


class DocumentEmbeddingRepository:
    """
    Repositorio específico para trabajar con chunks y embeddings.

    En R42 añadimos una consulta vectorial básica por versión.
    En R50 ampliamos esa capacidad para buscar sobre varios documentos.
    En R51 añadimos búsqueda textual básica.
    En R53 añadimos filtros por metadata documental.
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

    def _normalize_metadata_filters(
        self,
        metadata_filters: dict[str, str] | None,
    ) -> dict[str, str]:
        """
        Limpia y valida los filtros de metadata.

        No permitimos claves o valores vacíos porque una búsqueda así
        no tendría sentido y solo serviría para romper cosas, que ya bastante
        hace la humanidad sin ayuda.
        """
        if not metadata_filters:
            return {}

        normalized_filters: dict[str, str] = {}

        for key, value in metadata_filters.items():
            clean_key = str(key).strip()
            clean_value = str(value).strip()

            if not clean_key:
                raise ValueError("Las claves de metadata no pueden estar vacías")

            if not clean_value:
                raise ValueError("Los valores de metadata no pueden estar vacíos")

            normalized_filters[clean_key] = clean_value

        return normalized_filters

    def _build_metadata_filter_sql(
        self,
        document_id_expression: str,
        metadata_filters: dict[str, str] | None,
        params: dict,
    ) -> str:
        """
        Construye las condiciones SQL necesarias para filtrar por metadata.

        Se usa EXISTS para exigir que el documento tenga una fila de metadata
        con la clave y el valor indicados.
        """
        normalized_filters = self._normalize_metadata_filters(metadata_filters)

        if not normalized_filters:
            return ""

        metadata_conditions = []

        for index, (meta_key, meta_value) in enumerate(normalized_filters.items()):
            key_param = f"metadata_key_{index}"
            value_param = f"metadata_value_{index}"
            alias = f"dm_filter_{index}"

            metadata_conditions.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM document_metadata AS {alias}
                    WHERE {alias}.document_id = {document_id_expression}
                      AND LOWER({alias}.meta_key) = LOWER(:{key_param})
                      AND LOWER({alias}.meta_value) = LOWER(:{value_param})
                )
                """
            )

            params[key_param] = meta_key
            params[value_param] = meta_value

        return " AND " + " AND ".join(metadata_conditions)

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

        Esta función sigue existiendo porque la usan R42 y R43.
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

    def similarity_search_for_documents(
        self,
        document_ids: list[uuid.UUID],
        query_vector: list[float],
        limit: int = 5,
        metric: str = "cosine",
        metadata_filters: dict[str, str] | None = None,
    ) -> list[dict]:
        """
        Ejecuta la búsqueda semántica básica de R50 sobre varios documentos.

        En R53 permite aplicar filtros por metadata antes de ordenar
        los resultados por similitud vectorial.
        """
        if limit < 1:
            raise ValueError("El límite de resultados debe ser mayor que cero")

        if not document_ids:
            return []

        vector_literal = self._build_vector_literal(query_vector)
        distance_operator = self._get_distance_operator(metric)

        params = {
            "document_ids": document_ids,
            "query_vector": vector_literal,
            "limit_value": limit,
        }

        metadata_sql = self._build_metadata_filter_sql(
            document_id_expression="de.document_id",
            metadata_filters=metadata_filters,
            params=params,
        )

        stmt = text(
            f"""
            SELECT
                de.document_id AS document_id,
                de.document_version_id AS document_version_id,
                d.title AS document_title,
                de.chunk_id AS chunk_id,
                dc.chunk_index AS chunk_index,
                dc.content AS chunk_content,
                de.embedding_vector {distance_operator} CAST(:query_vector AS vector) AS distance_value
            FROM document_embeddings AS de
            INNER JOIN document_chunks AS dc
                ON dc.id = de.chunk_id
            INNER JOIN documents AS d
                ON d.id = de.document_id
            WHERE de.document_id IN :document_ids
              AND de.status = 'completed'
              {metadata_sql}
            ORDER BY de.embedding_vector {distance_operator} CAST(:query_vector AS vector)
            LIMIT :limit_value
            """
        ).bindparams(bindparam("document_ids", expanding=True))

        rows = self.db.execute(stmt, params).mappings().all()

        return [dict(row) for row in rows]

    def textual_search_for_documents(
        self,
        document_ids: list[uuid.UUID],
        query: str,
        limit: int = 5,
        metadata_filters: dict[str, str] | None = None,
    ) -> list[dict]:
        """
        Ejecuta una búsqueda textual sencilla sobre los chunks visibles.

        En R53 también permite filtrar por metadata documental.
        """
        if limit < 1:
            raise ValueError("El límite de resultados debe ser mayor que cero")

        clean_query = query.strip()
        if not clean_query:
            raise ValueError("La consulta textual no puede estar vacía")

        if not document_ids:
            return []

        query_terms = [
            term.strip().lower()
            for term in clean_query.split()
            if term.strip()
        ]

        if not query_terms:
            return []

        where_conditions = []
        params = {
            "document_ids": document_ids,
            "limit_value": limit,
        }

        for index, term in enumerate(query_terms):
            param_name = f"term_{index}"
            where_conditions.append(f"LOWER(dc.content) LIKE :{param_name}")
            params[param_name] = f"%{term}%"

        textual_filter = " OR ".join(where_conditions)

        metadata_sql = self._build_metadata_filter_sql(
            document_id_expression="dc.document_id",
            metadata_filters=metadata_filters,
            params=params,
        )

        stmt = text(
            f"""
            SELECT
                dc.document_id AS document_id,
                dc.document_version_id AS document_version_id,
                d.title AS document_title,
                dc.id AS chunk_id,
                dc.chunk_index AS chunk_index,
                dc.content AS chunk_content,
                1.0 AS textual_score
            FROM document_chunks AS dc
            INNER JOIN documents AS d
                ON d.id = dc.document_id
            WHERE dc.document_id IN :document_ids
              AND ({textual_filter})
              {metadata_sql}
            ORDER BY dc.chunk_index ASC
            LIMIT :limit_value
            """
        ).bindparams(bindparam("document_ids", expanding=True))

        rows = self.db.execute(stmt, params).mappings().all()

        return [dict(row) for row in rows]