"""merge_audit_run_and_coa

Revision ID: dcc3fe505b58
Revises: 20260103_1700_chart_of_accounts, 20260119_1200
Create Date: 2026-01-19 18:04:06.981684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcc3fe505b58'
down_revision: Union[str, None] = ('20260103_1700_chart_of_accounts', '20260119_1200')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
