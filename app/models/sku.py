"""
TekVwarho ProAudit - SKU (Stock Keeping Unit) Models

Commercial product tier definitions for:
- ProAudit Core (SME)
- ProAudit Professional (Mid-Market)
- ProAudit Enterprise (Large Organizations)
- ProAudit Intelligence (Add-on for ML/AI features)

Nigerian Market Pricing (Naira)
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime, Date,
    Numeric, Enum as SQLEnum, ForeignKey, JSON, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

# Import enums from separate file to avoid circular imports
from app.models.sku_enums import (
    SKUTier,
    IntelligenceAddon,
    Feature,
    UsageMetricType,
    BillingCycle,
)

# Re-export for backwards compatibility
__all__ = [
    'SKUTier',
    'IntelligenceAddon', 
    'Feature',
    'UsageMetricType',
    'BillingCycle',
    'SKUPricing',
    'TenantSKU',
    'UsageRecord',
    'UsageEvent',
    'FeatureAccessLog',
    'PaymentTransaction',
    'TIER_LIMITS',
    'INTELLIGENCE_LIMITS',
]

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.organization import Organization


# =============================================================================
# MODELS
# =============================================================================

class SKUPricing(BaseModel):
    """
    Pricing configuration for each SKU tier.
    Prices in Nigerian Naira (₦).
    """
    __tablename__ = "sku_pricing"
    
    sku_tier: Mapped[SKUTier] = mapped_column(
        SQLEnum(SKUTier),
        nullable=False,
        index=True,
    )
    
    # Base pricing (Naira)
    base_price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Base monthly price in Naira"
    )
    base_price_annual: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Annual price in Naira (typically 15% discount)"
    )
    
    # Per-user pricing for additional users
    price_per_user: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Price per additional user in Naira"
    )
    
    # Intelligence add-on pricing
    intelligence_standard_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Standard Intelligence add-on price in Naira"
    )
    intelligence_advanced_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="Advanced Intelligence add-on price in Naira"
    )
    
    # Effective dates
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    currency: Mapped[str] = mapped_column(
        String(3),
        default="NGN",
        comment="ISO currency code"
    )


class TenantSKU(BaseModel):
    """
    SKU assignment for a tenant (organization).
    Tracks what tier they're on and any custom overrides.
    """
    __tablename__ = "tenant_skus"
    
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Relationship back to organization
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="tenant_sku",
    )
    
    # Current SKU tier (CORE, PROFESSIONAL, ENTERPRISE)
    tier: Mapped[SKUTier] = mapped_column(
        SQLEnum(SKUTier),
        default=SKUTier.CORE,
        nullable=False,
    )
    
    # Intelligence add-on (NONE, STANDARD, ADVANCED)
    intelligence_addon: Mapped[Optional[IntelligenceAddon]] = mapped_column(
        SQLEnum(IntelligenceAddon),
        default=IntelligenceAddon.NONE,
        nullable=True,
    )
    
    # Billing cycle (monthly, quarterly, annual)
    billing_cycle: Mapped[str] = mapped_column(
        String(20),
        default="monthly",
        nullable=False,
    )
    
    # Current billing period
    current_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Trial period
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the trial period ends (null if not on trial)"
    )
    
    # Feature overrides (JSON: {"feature_name": true/false})
    # Allows enabling/disabling specific features outside normal tier
    feature_overrides: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Override specific features for this tenant"
    )
    
    # Custom limits (JSON: {"metric": limit_value})
    # Allows custom limits outside normal tier limits
    custom_limits: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Custom usage limits for this tenant"
    )
    
    # Pricing overrides (for negotiated enterprise deals) in Naira
    custom_price_naira: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Custom negotiated monthly price in Nigerian Naira"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    suspension_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Audit trail
    upgraded_from: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Previous tier before upgrade"
    )
    upgraded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    upgraded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    
    # Custom limit overrides (for enterprise deals)
    custom_user_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Override default user limit for this tenant"
    )
    custom_entity_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Override default entity limit for this tenant"
    )
    custom_transaction_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Override default transaction limit (-1 for unlimited)"
    )
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class UsageRecord(BaseModel):
    """
    Track usage metrics for billing and limit enforcement.
    Records are created per organization per billing period.
    """
    __tablename__ = "usage_records"
    
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationship back to organization
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="usage_records",
    )
    
    # Period
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Usage counts
    transactions_count: Mapped[int] = mapped_column(BigInteger, default=0)
    users_count: Mapped[int] = mapped_column(Integer, default=0)
    entities_count: Mapped[int] = mapped_column(Integer, default=0)
    invoices_count: Mapped[int] = mapped_column(Integer, default=0)
    api_calls_count: Mapped[int] = mapped_column(BigInteger, default=0)
    ocr_pages_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_used_mb: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    ml_inferences_count: Mapped[int] = mapped_column(BigInteger, default=0)
    employees_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Limit breach tracking
    limit_breaches: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Record of any limit breaches this period"
    )
    
    # Billing
    is_billed: Mapped[bool] = mapped_column(Boolean, default=False)
    billed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    invoice_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class UsageEvent(BaseModel):
    """
    Individual usage events for real-time metering.
    Aggregated into UsageRecord periodically.
    """
    __tablename__ = "usage_events"
    
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    metric_type: Mapped[UsageMetricType] = mapped_column(
        SQLEnum(UsageMetricType),
        nullable=False,
        index=True,
    )
    
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    
    # For tracking specific resources
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Event metadata (named event_metadata to avoid conflict with SQLAlchemy's metadata)
    event_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Timestamp is inherited from BaseModel (created_at)


class FeatureAccessLog(BaseModel):
    """
    Log feature access attempts for auditing and analytics.
    Tracks both successful access and denials.
    """
    __tablename__ = "feature_access_logs"
    
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    
    feature: Mapped[Feature] = mapped_column(
        SQLEnum(Feature),
        nullable=False,
        index=True,
    )
    
    was_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    # If denied, why?
    denial_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Request context
    endpoint: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class PaymentTransaction(BaseModel):
    """
    Record of all payment transactions processed through Paystack.
    
    Stores payment intents, completions, refunds, and subscription events.
    Essential for:
    - Financial reconciliation
    - Audit trail
    - Subscription management
    - Refund processing
    """
    __tablename__ = "payment_transactions"
    
    # Organization context
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # User who initiated payment (if known)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Paystack references
    reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="TekVwarho payment reference (TVP-XXXXX)"
    )
    paystack_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Paystack transaction reference"
    )
    paystack_access_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Paystack checkout access code"
    )
    authorization_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Paystack checkout URL"
    )
    
    # Transaction type
    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="subscription",
        comment="subscription, one_time, refund, etc."
    )
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="pending, success, failed, refunded, cancelled"
    )
    
    # Amount details (stored in kobo for Paystack compatibility)
    amount_kobo: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Amount in kobo (100 kobo = 1 Naira)"
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="NGN",
    )
    
    # Fee tracking
    paystack_fee_kobo: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Paystack transaction fee in kobo"
    )
    
    # SKU context
    tier: Mapped[Optional[SKUTier]] = mapped_column(
        SQLEnum(SKUTier),
        nullable=True,
    )
    billing_cycle: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="monthly, annual"
    )
    intelligence_addon: Mapped[Optional[IntelligenceAddon]] = mapped_column(
        SQLEnum(IntelligenceAddon),
        nullable=True,
    )
    additional_users: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # Payment method details (from Paystack response)
    payment_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="card, bank_transfer, ussd, etc."
    )
    card_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="visa, mastercard, verve, etc."
    )
    card_last4: Mapped[Optional[str]] = mapped_column(
        String(4),
        nullable=True,
    )
    bank_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Timestamps
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="When payment was confirmed"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="When payment intent expires"
    )
    
    # Webhook tracking
    webhook_received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    webhook_event_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Paystack webhook event ID for idempotency"
    )
    
    # Error tracking
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    gateway_response: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Raw gateway response message"
    )
    
    # Full response storage (for debugging/audit)
    paystack_response: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Full Paystack API response"
    )
    
    # Custom metadata
    custom_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Custom metadata for the transaction"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    @property
    def amount_naira(self) -> int:
        """Get amount in Naira (integer)."""
        return self.amount_kobo // 100
    
    @property
    def amount_naira_formatted(self) -> str:
        """Get formatted amount in Naira."""
        return f"₦{self.amount_naira:,}"
    
    @property
    def fee_naira(self) -> Optional[int]:
        """Get Paystack fee in Naira."""
        if self.paystack_fee_kobo:
            return self.paystack_fee_kobo // 100
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "reference": self.reference,
            "paystack_reference": self.paystack_reference,
            "status": self.status,
            "amount_naira": self.amount_naira,
            "amount_formatted": self.amount_naira_formatted,
            "currency": self.currency,
            "tier": self.tier.value if self.tier else None,
            "billing_cycle": self.billing_cycle,
            "payment_method": self.payment_method,
            "card_last4": self.card_last4,
            "initiated_at": self.initiated_at.isoformat() if self.initiated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "failure_reason": self.failure_reason,
        }


# =============================================================================
# TIER LIMITS CONFIGURATION (Default limits per tier)
# =============================================================================

# These are the default limits - can be overridden per tenant in TenantSKU.custom_limits
TIER_LIMITS = {
    SKUTier.CORE: {
        UsageMetricType.USERS: 5,
        UsageMetricType.ENTITIES: 1,
        UsageMetricType.TRANSACTIONS: 10_000,  # per month
        UsageMetricType.INVOICES: 100,  # per month
        UsageMetricType.API_CALLS: 0,  # No API access
        UsageMetricType.OCR_PAGES: 0,  # No OCR
        UsageMetricType.STORAGE_MB: 5_000,  # 5 GB
        UsageMetricType.ML_INFERENCES: 0,  # No ML
        UsageMetricType.EMPLOYEES: 10,  # Basic payroll limit
    },
    SKUTier.PROFESSIONAL: {
        UsageMetricType.USERS: 25,
        UsageMetricType.ENTITIES: 1,
        UsageMetricType.TRANSACTIONS: 100_000,  # per month
        UsageMetricType.INVOICES: 1_000,  # per month
        UsageMetricType.API_CALLS: 1_000,  # per hour (read-only)
        UsageMetricType.OCR_PAGES: 0,  # Requires Intelligence add-on
        UsageMetricType.STORAGE_MB: 50_000,  # 50 GB
        UsageMetricType.ML_INFERENCES: 0,  # Requires Intelligence add-on
        UsageMetricType.EMPLOYEES: 500,
    },
    SKUTier.ENTERPRISE: {
        UsageMetricType.USERS: -1,  # Unlimited
        UsageMetricType.ENTITIES: -1,  # Unlimited
        UsageMetricType.TRANSACTIONS: 1_000_000,  # per month (soft limit)
        UsageMetricType.INVOICES: -1,  # Unlimited
        UsageMetricType.API_CALLS: 10_000,  # per hour
        UsageMetricType.OCR_PAGES: 0,  # Requires Intelligence add-on
        UsageMetricType.STORAGE_MB: 500_000,  # 500 GB
        UsageMetricType.ML_INFERENCES: 0,  # Requires Intelligence add-on
        UsageMetricType.EMPLOYEES: -1,  # Unlimited
    },
}

# Intelligence add-on limits (added to base tier limits)
INTELLIGENCE_LIMITS = {
    IntelligenceAddon.NONE: {
        UsageMetricType.OCR_PAGES: 0,
        UsageMetricType.ML_INFERENCES: 0,
    },
    IntelligenceAddon.STANDARD: {
        UsageMetricType.OCR_PAGES: 1_000,  # per month
        UsageMetricType.ML_INFERENCES: 10_000,  # per day
    },
    IntelligenceAddon.ADVANCED: {
        UsageMetricType.OCR_PAGES: 5_000,  # per month
        UsageMetricType.ML_INFERENCES: 50_000,  # per day
    },
}
