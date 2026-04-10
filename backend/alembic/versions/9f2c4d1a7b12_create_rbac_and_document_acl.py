"""create rbac and document acl tables

Revision ID: 9f2c4d1a7b12
Revises: d3693b76fc55
Create Date: 2026-03-31 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f2c4d1a7b12"
down_revision: Union[str, Sequence[str], None] = "d3693b76fc55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------
    # Tabla de roles del sistema
    # -------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    # ---------------------------------------
    # Tabla intermedia usuario <-> rol (RBAC)
    # ---------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # ---------------------------
    # Tabla mínima de documentos
    # ---------------------------
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_owner_id"), "documents", ["owner_id"], unique=False)

    # --------------------------------------------
    # ACL simple: permisos explícitos por documento
    # --------------------------------------------
    op.create_table(
        "document_accesses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "user_id", name="uq_document_access_document_user"),
    )
    op.create_index(op.f("ix_document_accesses_document_id"), "document_accesses", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_accesses_user_id"), "document_accesses", ["user_id"], unique=False)

    # ---------------------
    # Seed inicial de roles
    # ---------------------
    op.execute(
        """
        INSERT INTO roles (id, name, description) VALUES
        (gen_random_uuid(), 'admin', 'Administrador del sistema'),
        (gen_random_uuid(), 'editor', 'Puede crear y gestionar sus documentos'),
        (gen_random_uuid(), 'viewer', 'Puede consultar documentos autorizados');
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_accesses_user_id"), table_name="document_accesses")
    op.drop_index(op.f("ix_document_accesses_document_id"), table_name="document_accesses")
    op.drop_table("document_accesses")

    op.drop_index(op.f("ix_documents_owner_id"), table_name="documents")
    op.drop_table("documents")

    op.drop_table("user_roles")

    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_table("roles")