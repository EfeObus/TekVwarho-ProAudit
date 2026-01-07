"""Merge payroll and audit system migrations

Revision ID: 91492aec7b35
Revises: 20260106_1600, 20260107_1800_audit_system
Create Date: 2026-01-07 18:44:18.176162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91492aec7b35'
down_revision: Union[str, None] = ('20260106_1600', '20260107_1800_audit_system')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
