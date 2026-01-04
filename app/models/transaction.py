"""
TekVwarho ProAudit - Transaction Model

Transaction model for recording income and expenses.

NTAA 2025 Compliance Features:
- Maker-Checker (SoD) for WREN expense verification
- Prevents Accountant from verifying expenses they created
- Audit trail for "before/after" category changes
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, AuditMixin

if TYPE_CHECKING:
    from app.models.entity import BusinessEntity
    from app.models.category import Category
    from app.models.vendor import Vendor


class TransactionType(str, Enum):
    """Type of transaction."""
    INCOME = "income"
    EXPENSE = "expense"


class WRENStatus(str, Enum):
    """WREN compliance status for expenses."""
    COMPLIANT = "compliant"              # Fully tax deductible
    NON_COMPLIANT = "non_compliant"      # Not tax deductible
    REVIEW_REQUIRED = "review_required"  # Needs manual review


class Transaction(BaseModel, AuditMixin):
    """
    Transaction model for recording income and expenses.
    
    Includes WREN compliance tracking for tax deductibility
    and VAT tracking for Input VAT recovery.
    """
    
    __tablename__ = "transactions"
    
    # Entity
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Type
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType),
        nullable=False,
        index=True,
    )
    
    # Date
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Amount (in Kobo for precision)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Transaction amount in Naira",
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        default=Decimal("0.00"),
        nullable=False,
        comment="VAT amount in Naira",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=False,
        comment="Total amount including VAT",
    )
    
    # Description
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="External reference number",
    )
    
    # Category
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Vendor (for expenses)
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # ===========================================
    # WREN COMPLIANCE - MAKER-CHECKER (NTAA 2025)
    # ===========================================
    
    # WREN Status (for expenses)
    wren_status: Mapped[WRENStatus] = mapped_column(
        SQLEnum(WRENStatus),
        default=WRENStatus.REVIEW_REQUIRED,
        nullable=False,
    )
    wren_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Maker-Checker Segregation of Duties
    # Maker: Person who created/uploaded the expense
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Maker: User who created this transaction",
    )
    
    # Checker: Person who verified WREN status (cannot be same as Maker)
    wren_verified_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Checker: User who verified WREN status (cannot be Maker)",
    )
    wren_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When WREN verification was performed",
    )
    
    # Original category before any changes (for audit trail)
    original_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Original category for audit trail (if changed)",
    )
    category_change_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="History of category changes with before/after snapshots",
    )
    
    # VAT
    vat_recoverable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True if Input VAT can be recovered",
    )
    
    # Attachments
    receipt_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Recurring
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurring_frequency: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="monthly, quarterly, annually",
    )
    
    # Relationships
    entity: Mapped["BusinessEntity"] = relationship(
        "BusinessEntity",
        back_populates="transactions",
    )
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="transactions",
    )
    vendor: Mapped[Optional["Vendor"]] = relationship(
        "Vendor",
        back_populates="transactions",
    )
    
    @property
    def is_expense(self) -> bool:
        return self.transaction_type == TransactionType.EXPENSE
    
    @property
    def is_income(self) -> bool:
        return self.transaction_type == TransactionType.INCOME
    
    @property
    def is_tax_deductible(self) -> bool:
        """Check if expense is tax deductible (WREN compliant)."""
        return self.wren_status == WRENStatus.COMPLIANT
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, type={self.transaction_type}, amount={self.amount})>"
