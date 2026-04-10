"""improve refresh_tokens constraints

Revision ID: d3693b76fc55
Revises: bd3fa179a21d
Create Date: 2026-03-30 19:28:10.395988

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3693b76fc55'
down_revision: Union[str, Sequence[str], None] = 'bd3fa179a21d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
