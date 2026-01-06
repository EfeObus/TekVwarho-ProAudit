"""Add LGA column and email verification fields

Revision ID: 20260106_1400_add_lga_email_verification
Revises: 20260104_1500_sync_models_with_db
Create Date: 2026-01-06 14:00:00.000000

This migration adds:
1. LGA (Local Government Area) column to business_entities table
2. Email verification fields to users table:
   - email_verification_token
   - email_verification_sent_at
   - email_verified_at
   - is_invited_user
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260106_1400_add_lga_email_verification'
down_revision = '20260104_1500_sync_models_with_db'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add LGA column to business_entities
    op.add_column(
        'business_entities',
        sa.Column(
            'lga',
            sa.String(100),
            nullable=True,
            comment='Local Government Area'
        )
    )
    
    # Add email verification fields to users table
    op.add_column(
        'users',
        sa.Column(
            'email_verification_token',
            sa.String(255),
            nullable=True,
            comment='Token for email verification'
        )
    )
    
    op.add_column(
        'users',
        sa.Column(
            'email_verification_sent_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When verification email was last sent'
        )
    )
    
    op.add_column(
        'users',
        sa.Column(
            'email_verified_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When email was verified'
        )
    )
    
    op.add_column(
        'users',
        sa.Column(
            'is_invited_user',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='True if user was invited (skip email verification)'
        )
    )
    
    # Create index on email_verification_token for faster lookups
    op.create_index(
        'ix_users_email_verification_token',
        'users',
        ['email_verification_token'],
        unique=False
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_users_email_verification_token', table_name='users')
    
    # Remove email verification columns from users
    op.drop_column('users', 'is_invited_user')
    op.drop_column('users', 'email_verified_at')
    op.drop_column('users', 'email_verification_sent_at')
    op.drop_column('users', 'email_verification_token')
    
    # Remove LGA column from business_entities
    op.drop_column('business_entities', 'lga')
