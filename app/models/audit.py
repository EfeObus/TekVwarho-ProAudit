"""
TekVwarho ProAudit - Audit Log Model

Immutable audit log for tracking all data changes.

NTAA 2025 Compliance Features:
- IP Address & Device Fingerprint (mandatory for proving tax return submission)
- Before/After snapshots (for category changes like Personal → Business)
- NRS Server Response storage (IRN and Cryptographic Stamp)
- 5-year retention per NTAA requirements
- Session tracking for impersonation audit trail
"""

import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditAction(str, enum.Enum):
    """Audit action types."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    VIEW = "view"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    NRS_SUBMIT = "nrs_submit"
    NRS_CANCEL = "nrs_cancel"
    NRS_CREDIT_NOTE = "nrs_credit_note"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    # WREN Maker-Checker actions
    WREN_VERIFY = "wren_verify"
    WREN_REJECT = "wren_reject"
    CATEGORY_CHANGE = "category_change"
    # Impersonation actions
    IMPERSONATION_START = "impersonation_start"
    IMPERSONATION_END = "impersonation_end"
    IMPERSONATION_GRANT = "impersonation_grant"
    IMPERSONATION_REVOKE = "impersonation_revoke"


class AuditLog(Base):
    """
    Immutable audit log for tracking all data changes.
    
    NTAA 2025 Compliant:
    - IP & Device Fingerprint for proving submission source
    - Before/After snapshots for category changes
    - NRS response storage for IRN and cryptographic stamps
    - 5-year retention per NTAA requirements
    
    This table should have no UPDATE or DELETE permissions.
    """
    
    __tablename__ = "audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Entity Context (business entity)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # Allow NULL for platform-level actions
        index=True,
    )
    
    # Organization Context (for multi-tenant queries)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    
    # User Context
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,  # System actions may not have a user
        index=True,
    )
    
    # Impersonation Context (if CSR is impersonating)
    impersonated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="If action was performed by CSR impersonating user",
    )
    
    # Action
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction),
        nullable=False,
        index=True,
    )
    
    # Target Entity
    target_entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of entity (transaction, invoice, etc.)",
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="ID of the affected entity",
    )
    
    # ===========================================
    # BEFORE/AFTER SNAPSHOTS (NTAA 2025 Requirement)
    # ===========================================
    
    old_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Previous values (for UPDATE/DELETE) - MANDATORY for audit",
    )
    new_values: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="New values (for CREATE/UPDATE)",
    )
    changes: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Calculated changes for UPDATEs - shows exact field diffs",
    )
    
    # ===========================================
    # DEVICE FINGERPRINT (NTAA 2025 Requirement)
    # Mandatory for proving who submitted tax returns
    # ===========================================
    
    # Request Context
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Browser/device fingerprint for submission verification",
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Session ID for tracking related actions",
    )
    
    # Geolocation (optional but helpful for fraud detection)
    geo_location: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Approximate location from IP (country, city)",
    )
    
    # ===========================================
    # NRS RESPONSE STORAGE (NTAA 2025 Requirement)
    # Store IRN and Cryptographic Stamp directly
    # ===========================================
    
    nrs_irn: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="NRS Invoice Reference Number (if NRS action)",
    )
    nrs_response: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full NRS server response including cryptographic stamp",
    )
    
    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    
    # Description for human-readable logging
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable description of the action",
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action.value}, type={self.target_entity_type})>"
