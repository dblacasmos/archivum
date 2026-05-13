"""create tracking events table

Revision ID: e9a7c3b2d1f4
Revises: d8f1c3a4b5e6
Create Date: 2026-05-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9a7c3b2d1f4"
down_revision: str | Sequence[str] | None = "d8f1c3a4b5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Crea la tabla de eventos de tracking.
    """
    op.create_table(
        "tracking_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(length=100),
            nullable=False,
            server_default="backend",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_tracking_events_event_type",
        "tracking_events",
        ["event_type"],
        unique=False,
    )

    op.create_index(
        "ix_tracking_events_user_id",
        "tracking_events",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_tracking_events_created_at",
        "tracking_events",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_tracking_events_type_created_at",
        "tracking_events",
        ["event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """
    Elimina la tabla de eventos de tracking.
    """
    op.drop_index(
        "ix_tracking_events_type_created_at",
        table_name="tracking_events",
    )

    op.drop_index(
        "ix_tracking_events_created_at",
        table_name="tracking_events",
    )

    op.drop_index(
        "ix_tracking_events_user_id",
        table_name="tracking_events",
    )

    op.drop_index(
        "ix_tracking_events_event_type",
        table_name="tracking_events",
    )

    op.drop_table("tracking_events")