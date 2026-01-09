"""
TekVwarho ProAudit - Bank Reconciliation Model

Bank reconciliation models for Nigerian businesses.
Supports:
- Bank statement import and matching
- Transaction matching (auto and manual)
- Reconciliation statements
- Outstanding items tracking
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    Enum as SQLEnum, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, AuditMixin

if TYPE_CHECKING:
    from app.models.entity import BusinessEntity
    from app.models.transaction import Transaction
    from app.models.user import User


class BankAccountType(str, Enum):
    """Bank account type."""
    CURRENT = "current"
    SAVINGS = "savings"
    DOMICILIARY = "domiciliary"
    FIXED_DEPOSIT = "fixed_deposit"
    ESCROW = "escrow"


class BankStatementSource(str, Enum):
    """Source of bank statement."""
    MANUAL_UPLOAD = "manual_upload"
    API_IMPORT = "api_import"
    MANUAL_ENTRY = "manual_entry"


class MatchStatus(str, Enum):
    """Transaction matching status."""
    UNMATCHED = "unmatched"
    AUTO_MATCHED = "auto_matched"
    MANUAL_MATCHED = "manual_matched"
    RECONCILED = "reconciled"
    DISPUTED = "disputed"


class ReconciliationStatus(str, Enum):
    """Bank reconciliation status."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"


# ===========================================
# BANK ACCOUNT (FOR RECONCILIATION)
# ===========================================

class BankAccount(BaseModel, AuditMixin):
    """
    Bank account for reconciliation purposes.
    
    Links to the Chart of Accounts (GL) for proper accounting integration.
    """
    
    __tablename__ = "bank_accounts"
    
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Bank Details
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_type: Mapped[BankAccountType] = mapped_column(
        SQLEnum(BankAccountType),
        default=BankAccountType.CURRENT,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    bank_code: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True,
        comment="CBN bank code for electronic transfers",
    )
    
    # GL Integration
    gl_account_code: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="General Ledger account code for this bank account",
    )
    
    # Opening Balance
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
    )
    opening_balance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Current Balance (updated from reconciliations)
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
    )
    last_reconciled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_reconciled_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=18, scale=2), nullable=True,
    )
    
    # API Integration (for banks with API access)
    api_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_credentials: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="Encrypted API credentials for bank integration",
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    entity: Mapped["BusinessEntity"] = relationship("BusinessEntity")
    statements: Mapped[List["BankStatement"]] = relationship(
        "BankStatement",
        back_populates="bank_account",
        cascade="all, delete-orphan",
    )
    reconciliations: Mapped[List["BankReconciliation"]] = relationship(
        "BankReconciliation",
        back_populates="bank_account",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        UniqueConstraint('entity_id', 'account_number', 'bank_name', name='uq_bank_account'),
    )
    
    def __repr__(self) -> str:
        return f"<BankAccount(id={self.id}, bank={self.bank_name}, account={self.account_number})>"


# ===========================================
# BANK STATEMENT
# ===========================================

class BankStatement(BaseModel):
    """
    Imported bank statement containing transactions from the bank.
    """
    
    __tablename__ = "bank_statements"
    
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bank_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Statement Period
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Balances from Statement
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    
    # Import Details
    source: Mapped[BankStatementSource] = mapped_column(
        SQLEnum(BankStatementSource),
        default=BankStatementSource.MANUAL_UPLOAD,
        nullable=False,
    )
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    imported_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Transaction Count
    total_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unmatched_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Relationships
    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount", back_populates="statements",
    )
    transactions: Mapped[List["BankStatementTransaction"]] = relationship(
        "BankStatementTransaction",
        back_populates="statement",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<BankStatement(id={self.id}, date={self.statement_date})>"


# ===========================================
# BANK STATEMENT TRANSACTION
# ===========================================

class BankStatementTransaction(BaseModel):
    """
    Individual transaction from a bank statement.
    """
    
    __tablename__ = "bank_statement_transactions"
    
    statement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bank_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Transaction Details
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Amounts
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    
    # Matching
    match_status: Mapped[MatchStatus] = mapped_column(
        SQLEnum(MatchStatus),
        default=MatchStatus.UNMATCHED,
        nullable=False,
        index=True,
    )
    matched_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    match_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=5, scale=2), nullable=True,
        comment="Auto-match confidence score (0-100)",
    )
    matched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    matched_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    statement: Mapped["BankStatement"] = relationship(
        "BankStatement", back_populates="transactions",
    )
    matched_transaction: Mapped[Optional["Transaction"]] = relationship(
        "Transaction", foreign_keys=[matched_transaction_id],
    )
    
    @property
    def amount(self) -> Decimal:
        """Get net amount (positive for credits, negative for debits)."""
        return self.credit_amount - self.debit_amount
    
    def __repr__(self) -> str:
        return f"<BankStatementTransaction(id={self.id}, date={self.transaction_date}, amount={self.amount})>"


# ===========================================
# BANK RECONCILIATION
# ===========================================

class BankReconciliation(BaseModel, AuditMixin):
    """
    Bank reconciliation record for a specific period.
    
    Tracks the reconciliation process and results.
    """
    
    __tablename__ = "bank_reconciliations"
    
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bank_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Reconciliation Period
    reconciliation_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Bank Statement Balances
    statement_opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    statement_closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    
    # Book Balances (from GL)
    book_opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    book_closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    
    # Reconciliation Adjustments
    deposits_in_transit: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Deposits recorded in books but not yet in bank",
    )
    outstanding_checks: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Checks issued but not yet cleared",
    )
    bank_charges: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Bank charges not yet recorded in books",
    )
    interest_earned: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Interest not yet recorded in books",
    )
    other_adjustments: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
    )
    
    # Reconciled Balance
    adjusted_bank_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    adjusted_book_balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        nullable=False,
    )
    difference: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Difference after adjustments (should be 0 when reconciled)",
    )
    
    # Status
    status: Mapped[ReconciliationStatus] = mapped_column(
        SQLEnum(ReconciliationStatus),
        default=ReconciliationStatus.DRAFT,
        nullable=False,
    )
    
    # Approval
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Outstanding Items (JSON for flexibility)
    outstanding_items: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="List of outstanding/unreconciled items",
    )
    
    # Relationships
    bank_account: Mapped["BankAccount"] = relationship(
        "BankAccount", back_populates="reconciliations",
    )
    
    @property
    def is_balanced(self) -> bool:
        """Check if reconciliation is balanced (difference is zero)."""
        return self.difference == Decimal("0.00")
    
    def __repr__(self) -> str:
        return f"<BankReconciliation(id={self.id}, date={self.reconciliation_date}, status={self.status})>"
