"""add upload fields to documents

Revision ID: 4c2a6f9d8e31
Revises: 9f2c4d1a7b12
Create Date: 2026-04-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4c2a6f9d8e31"
down_revision: Union[str, Sequence[str], None] = "9f2c4d1a7b12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Amplía la tabla documents para soportar la subida real de archivos.
    """
    op.add_column("documents", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("stored_filename", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("storage_path", sa.String(length=500), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.String(length=120), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """
    Revierte los campos añadidos para la subida de archivos.
    """
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "stored_filename")
    op.drop_column("documents", "original_filename")