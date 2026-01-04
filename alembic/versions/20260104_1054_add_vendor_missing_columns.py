"""Add missing vendor columns (contact_person, country, default_wht_rate)

Revision ID: 20260104_1054
Revises: 20260104_0930
Create Date: 2026-01-04 10:54:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260104_1054"
down_revision: Union[str, None] = "20260104_0930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to vendors table."""
    # Add contact_person column
    op.add_column(
        "vendors",
        sa.Column("contact_person", sa.String(100), nullable=True),
    )
    
    # Add country column with default value
    op.add_column(
        "vendors",
        sa.Column("country", sa.String(100), nullable=False, server_default="Nigeria"),
    )
    
    # Add default_wht_rate column
    op.add_column(
        "vendors",
        sa.Column("default_wht_rate", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Remove added columns from vendors table."""
    op.drop_column("vendors", "default_wht_rate")
    op.drop_column("vendors", "country")
    op.drop_column("vendors", "contact_person")
