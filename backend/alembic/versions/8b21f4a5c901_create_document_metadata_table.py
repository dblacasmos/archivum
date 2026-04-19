"""create document metadata table

Revision ID: 8b21f4a5c901
Revises: 4c2a6f9d8e31
Create Date: 2026-04-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b21f4a5c901"
down_revision: Union[str, Sequence[str], None] = "4c2a6f9d8e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crea la tabla de metadata básica asociada a documentos.
    """
    op.create_table(
        "document_metadata",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("meta_key", sa.String(length=100), nullable=False),
        sa.Column("meta_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "meta_key", name="uq_document_metadata_document_key"),
    )

    op.create_index(op.f("ix_document_metadata_document_id"), "document_metadata", ["document_id"], unique=False)


def downgrade() -> None:
    """
    Elimina la tabla de metadata de documentos.
    """
    op.drop_index(op.f("ix_document_metadata_document_id"), table_name="document_metadata")
    op.drop_table("document_metadata")