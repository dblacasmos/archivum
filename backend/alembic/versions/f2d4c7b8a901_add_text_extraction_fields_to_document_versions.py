"""add text extraction fields to document_versions

Revision ID: f2d4c7b8a901
Revises: c1a9f6d4e2b7
Create Date: 2026-04-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2d4c7b8a901"
down_revision: Union[str, Sequence[str], None] = "c1a9f6d4e2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade a las versiones de documento los campos necesarios
    para persistir el resultado de la extracción de texto.
    """
    op.add_column(
        "document_versions",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column(
            "extraction_status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
    )

    op.add_column(
        "document_versions",
        sa.Column("extraction_error", sa.Text(), nullable=True),
    )

    op.add_column(
        "document_versions",
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """
    Revierte los campos añadidos para extracción de texto.
    """
    op.drop_column("document_versions", "extracted_at")
    op.drop_column("document_versions", "extraction_error")
    op.drop_column("document_versions", "extraction_status")
    op.drop_column("document_versions", "extracted_text")