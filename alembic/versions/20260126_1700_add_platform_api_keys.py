"""Add platform API keys table

Revision ID: 20260126_1700
Revises: 20260125_1800
Create Date: 2026-01-26 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260126_1700'
down_revision: Union[str, None] = '20260125_1800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    api_key_type = postgresql.ENUM(
        'nrs_gateway', 'jtb_gateway', 'paystack', 'flutterwave', 'sendgrid', 'custom',
        name='apikeytype',
        create_type=False
    )
    api_key_environment = postgresql.ENUM(
        'sandbox', 'production',
        name='apikeyenvironment',
        create_type=False
    )
    
    # Create enum types if they don't exist
    api_key_type.create(op.get_bind(), checkfirst=True)
    api_key_environment.create(op.get_bind(), checkfirst=True)
    
    # Create platform_api_keys table
    op.create_table(
        'platform_api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('key_type', api_key_type, nullable=False, server_default='custom'),
        sa.Column('environment', api_key_environment, nullable=False, server_default='sandbox'),
        
        # API credentials
        sa.Column('api_key', sa.String(512), nullable=False),
        sa.Column('api_secret', sa.String(512), nullable=True),
        sa.Column('client_id', sa.String(255), nullable=True),
        sa.Column('masked_key', sa.String(100), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        
        # Endpoint configuration
        sa.Column('api_endpoint', sa.String(500), nullable=True),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        
        # Status
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('is_verified', sa.Boolean, nullable=False, server_default=sa.text('false')),
        
        # Usage tracking
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_count', sa.Integer, nullable=False, server_default=sa.text('0')),
        
        # Expiration
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        
        # Audit
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('revoked_by_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text, nullable=True),
        
        # Notes
        sa.Column('notes', sa.Text, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Create indexes
    op.create_index('ix_platform_api_keys_key_type', 'platform_api_keys', ['key_type'])
    op.create_index('ix_platform_api_keys_environment', 'platform_api_keys', ['environment'])
    op.create_index('ix_platform_api_keys_is_active', 'platform_api_keys', ['is_active'])
    op.create_index('ix_platform_api_keys_created_by_id', 'platform_api_keys', ['created_by_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_platform_api_keys_created_by_id', table_name='platform_api_keys')
    op.drop_index('ix_platform_api_keys_is_active', table_name='platform_api_keys')
    op.drop_index('ix_platform_api_keys_environment', table_name='platform_api_keys')
    op.drop_index('ix_platform_api_keys_key_type', table_name='platform_api_keys')
    
    # Drop table
    op.drop_table('platform_api_keys')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS apikeyenvironment")
    op.execute("DROP TYPE IF EXISTS apikeytype")
