"""migrate document embeddings to pgvector

Revision ID: c4e8f1a2b3d6
Revises: b7c9a1d2e4f5
Create Date: 2026-04-19 13:00:00.000000
"""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR


# ID de revisión de Alembic
revision: str = "c4e8f1a2b3d6"
down_revision: Union[str, None] = "b7c9a1d2e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Dimensión fija del modelo que usa el proyecto.
# La dejamos explícita en migración para que sea estable.
EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    """
    Convierte el almacenamiento de embeddings desde JSON normal
    a una columna real de tipo pgvector.
    """
    # Activamos la extensión vector en la base de datos actual.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Añadimos la nueva columna vectorial primero como nullable
    # para poder migrar los datos existentes sin romper la tabla.
    op.add_column(
        "document_embeddings",
        sa.Column(
            "embedding_vector",
            VECTOR(EMBEDDING_DIMENSIONS),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    # Leemos los embeddings antiguos guardados como JSON.
    rows = connection.execute(
        sa.text(
            """
            SELECT id, embedding_json
            FROM document_embeddings
            """
        )
    ).mappings().all()

    for row in rows:
        embedding_id = row["id"]
        raw_embedding = row["embedding_json"]

        # Validamos que el valor leído sea una lista real.
        if not isinstance(raw_embedding, list):
            raise ValueError(
                f"El embedding {embedding_id} no tiene un JSON válido en formato lista"
            )

        # Validamos la dimensión esperada para mantener
        # coherencia con el modelo configurado.
        if len(raw_embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"El embedding {embedding_id} tiene {len(raw_embedding)} dimensiones y se esperaban {EMBEDDING_DIMENSIONS}. "
                "Limpia los embeddings antiguos de pruebas y vuelve a lanzar la migración."
            )

        # Convertimos la lista a la representación textual
        # que PostgreSQL entiende para el tipo vector.
        vector_literal = "[" + ",".join(str(float(value)) for value in raw_embedding) + "]"

        connection.execute(
            sa.text(
                """
                UPDATE document_embeddings
                SET embedding_vector = CAST(:vector_literal AS vector)
                WHERE id = :embedding_id
                """
            ),
            {
                "vector_literal": vector_literal,
                "embedding_id": embedding_id,
            },
        )

    # Una vez migrados los datos, exigimos que la columna ya no admita nulos.
    op.alter_column(
        "document_embeddings",
        "embedding_vector",
        nullable=False,
    )

    # Eliminamos la columna JSON antigua porque R41 ya usa pgvector real.
    op.drop_column("document_embeddings", "embedding_json")


def downgrade() -> None:
    """
    Revierte la migración y vuelve a guardar los embeddings como JSON.
    """
    op.add_column(
        "document_embeddings",
        sa.Column(
            "embedding_json",
            sa.JSON(),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            """
            SELECT id, embedding_vector::text AS embedding_vector_text
            FROM document_embeddings
            """
        )
    ).mappings().all()

    for row in rows:
        embedding_id = row["id"]
        vector_text = row["embedding_vector_text"] or "[]"

        cleaned_text = vector_text.strip().strip("[]")

        if cleaned_text:
            values = [float(value.strip()) for value in cleaned_text.split(",")]
        else:
            values = []

        connection.execute(
            sa.text(
                """
                UPDATE document_embeddings
                SET embedding_json = CAST(:embedding_json AS json)
                WHERE id = :embedding_id
                """
            ),
            {
                "embedding_json": json.dumps(values),
                "embedding_id": embedding_id,
            },
        )

    op.alter_column(
        "document_embeddings",
        "embedding_json",
        nullable=False,
    )

    op.drop_column("document_embeddings", "embedding_vector")