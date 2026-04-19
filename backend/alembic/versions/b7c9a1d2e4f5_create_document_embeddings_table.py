"""create document embeddings table

Revision ID: b7c9a1d2e4f5
Revises: a4f7c2d91b33
Create Date: 2026-04-18 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ID de revisión de Alembic
revision: str = "b7c9a1d2e4f5"
down_revision: Union[str, None] = "a4f7c2d91b33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crea la tabla que guarda los embeddings asociados a chunks.
    En R40 el vector se guarda como JSON normal, no como pgvector.
    """
    op.create_table(
        "document_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'openai'"),
        ),
        sa.Column(
            "model_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "dimensions",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "embedding_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'completed'"),
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "chunk_id",
            name="uq_document_embeddings_chunk_id",
        ),
    )

    op.create_index(
        "ix_document_embeddings_document_id",
        "document_embeddings",
        ["document_id"],
    )
    op.create_index(
        "ix_document_embeddings_document_version_id",
        "document_embeddings",
        ["document_version_id"],
    )
    op.create_index(
        "ix_document_embeddings_chunk_id",
        "document_embeddings",
        ["chunk_id"],
    )


def downgrade() -> None:
    """
    Revierte la creación de la tabla de embeddings.
    """
    op.drop_index("ix_document_embeddings_chunk_id", table_name="document_embeddings")
    op.drop_index("ix_document_embeddings_document_version_id", table_name="document_embeddings")
    op.drop_index("ix_document_embeddings_document_id", table_name="document_embeddings")
    op.drop_table("document_embeddings")