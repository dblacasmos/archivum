"""create vector index for document embeddings

Revision ID: d8f1c3a4b5e6
Revises: c4e8f1a2b3d6
Create Date: 2026-04-19 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


# ID único de esta migración.
revision: str = "d8f1c3a4b5e6"

# Indica que esta migración depende de la de R41,
# donde ya existe la columna embedding_vector de tipo vector.
down_revision: Union[str, None] = "c4e8f1a2b3d6"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Número básico de listas del índice ivfflat.
# No es tuning avanzado, solo una configuración mínima y razonable
# para dejar el índice operativo en el proyecto.
IVFFLAT_LISTS = 100


def upgrade() -> None:
    """
    Crea un índice vectorial ivfflat sobre la columna embedding_vector
    usando la métrica de similitud por coseno.

    Esto deja preparada la base para búsquedas semánticas posteriores
    sin entrar todavía en optimizaciones avanzadas.
    """
    # Aseguramos que la extensión vector existe antes de crear el índice.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Creamos un índice ivfflat orientado a cosine distance.
    # vector_cosine_ops indica a PostgreSQL cómo comparar vectores
    # cuando se utilice la distancia por coseno.
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS ix_document_embeddings_embedding_vector_cosine
        ON document_embeddings
        USING ivfflat (embedding_vector vector_cosine_ops)
        WITH (lists = {IVFFLAT_LISTS})
        """
    )

    # Actualizamos estadísticas para que PostgreSQL conozca mejor
    # la tabla y tenga más información al planificar consultas.
    op.execute("ANALYZE document_embeddings")


def downgrade() -> None:
    """
    Revierte la creación del índice vectorial.
    """
    op.execute(
        """
        DROP INDEX IF EXISTS ix_document_embeddings_embedding_vector_cosine
        """
    )