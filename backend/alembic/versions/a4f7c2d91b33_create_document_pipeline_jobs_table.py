"""create document pipeline jobs table

Revision ID: a4f7c2d91b33
Revises: ab12cd34ef56
Create Date: 2026-04-15 18:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a4f7c2d91b33"
down_revision: Union[str, Sequence[str], None] = "ab12cd34ef56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crea la tabla que almacenará los jobs del pipeline asíncrono.
    """
    op.create_table(
        "document_pipeline_jobs",
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
            "version_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "current_step",
            sa.String(length=50),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "chunk_size",
            sa.Integer(),
            nullable=False,
            server_default="500",
        ),
        sa.Column(
            "chunk_overlap",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
        sa.Column(
            "total_chunks",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "ready_for_vectorization",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_document_pipeline_jobs_document_id",
        "document_pipeline_jobs",
        ["document_id"],
    )
    op.create_index(
        "ix_document_pipeline_jobs_document_version_id",
        "document_pipeline_jobs",
        ["document_version_id"],
    )
    op.create_index(
        "ix_document_pipeline_jobs_created_by_user_id",
        "document_pipeline_jobs",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_document_pipeline_jobs_status",
        "document_pipeline_jobs",
        ["status"],
    )


def downgrade() -> None:
    """
    Revierte la creación de la tabla del pipeline.
    """
    op.drop_index("ix_document_pipeline_jobs_status", table_name="document_pipeline_jobs")
    op.drop_index("ix_document_pipeline_jobs_created_by_user_id", table_name="document_pipeline_jobs")
    op.drop_index("ix_document_pipeline_jobs_document_version_id", table_name="document_pipeline_jobs")
    op.drop_index("ix_document_pipeline_jobs_document_id", table_name="document_pipeline_jobs")
    op.drop_table("document_pipeline_jobs")