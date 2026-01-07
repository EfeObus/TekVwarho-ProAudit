"""
TekVwarho ProAudit - SQLAlchemy Models Package

This package contains all database models for the application.
"""

from app.models.base import BaseModel, TimestampMixin, AuditMixin
from app.models.user import User, UserRole, PlatformRole, UserEntityAccess
from app.models.organization import (
    Organization, 
    SubscriptionTier, 
    OrganizationType, 
    VerificationStatus
)
from app.models.entity import BusinessEntity
from app.models.category import Category, CategoryType
from app.models.vendor import Vendor
from app.models.customer import Customer
from app.models.transaction import Transaction, TransactionType
from app.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus
from app.models.inventory import InventoryItem, StockMovement, StockWriteOff
from app.models.tax import VATRecord, PAYERecord, TaxPeriod
from app.models.audit import AuditLog
from app.models.tax_2026 import (
    VATRecoveryRecord,
    VATRecoveryType,
    DevelopmentLevyRecord,
    PITReliefDocument,
    ReliefType,
    ReliefStatus,
    CreditNote,
    CreditNoteStatus,
)
from app.models.entity import BusinessType
from app.models.fixed_asset import (
    FixedAsset,
    DepreciationEntry,
    AssetCategory,
    AssetStatus,
    DepreciationMethod,
    DisposalType,
)
from app.models.notification import (
    Notification,
    NotificationType,
    NotificationPriority,
    NotificationChannel,
)
from app.models.payroll import (
    Employee,
    EmployeeBankAccount,
    PayrollRun,
    Payslip,
    PayslipItem,
    StatutoryRemittance,
    EmploymentType,
    EmploymentStatus,
    PayrollStatus,
    PayrollFrequency,
    PayItemType,
    PayItemCategory,
    BankName,
    PensionFundAdministrator,
)
from app.models.advanced_accounting import (
    AccountingDimension,
    TransactionDimension,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceivedNote,
    GoodsReceivedNoteItem,
    ThreeWayMatch,
    WHTCreditNote,
    Budget,
    BudgetLineItem,
    ApprovalWorkflow,
    ApprovalWorkflowApprover,
    ApprovalRequest,
    ApprovalDecision,
    LedgerEntry,
    EntityGroup,
    EntityGroupMember,
    IntercompanyTransaction,
    DimensionType,
    MatchingStatus,
    WHTCreditStatus,
    ApprovalStatus,
    BudgetPeriodType,
)

__all__ = [
    # Base
    "BaseModel",
    "TimestampMixin",
    "AuditMixin",
    # User & RBAC
    "User",
    "UserRole",
    "PlatformRole",
    "UserEntityAccess",
    # Organization
    "Organization",
    "SubscriptionTier",
    "OrganizationType",
    "VerificationStatus",
    # Entity
    "BusinessEntity",
    # Category
    "Category",
    "CategoryType",
    # Vendor
    "Vendor",
    # Customer
    "Customer",
    # Transaction
    "Transaction",
    "TransactionType",
    # Invoice
    "Invoice",
    "InvoiceLineItem",
    "InvoiceStatus",
    # Inventory
    "InventoryItem",
    "StockMovement",
    "StockWriteOff",
    # Tax
    "VATRecord",
    "PAYERecord",
    "TaxPeriod",
    # 2026 Tax Reform
    "VATRecoveryRecord",
    "VATRecoveryType",
    "DevelopmentLevyRecord",
    "PITReliefDocument",
    "ReliefType",
    "ReliefStatus",
    "CreditNote",
    "CreditNoteStatus",
    "BusinessType",
    # Fixed Assets (2026)
    "FixedAsset",
    "DepreciationEntry",
    "AssetCategory",
    "AssetStatus",
    "DepreciationMethod",
    "DisposalType",
    # Notifications
    "Notification",
    "NotificationType",
    "NotificationPriority",
    "NotificationChannel",
    # Payroll
    "Employee",
    "EmployeeBankAccount",
    "PayrollRun",
    "Payslip",
    "PayslipItem",
    "StatutoryRemittance",
    "EmploymentType",
    "EmploymentStatus",
    "PayrollStatus",
    "PayrollFrequency",
    "PayItemType",
    "PayItemCategory",
    "BankName",
    "PensionFundAdministrator",
    # Audit
    "AuditLog",
    # Advanced Accounting (2026 Tax Reform)
    "AccountingDimension",
    "TransactionDimension",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "GoodsReceivedNote",
    "GoodsReceivedNoteItem",
    "ThreeWayMatch",
    "WHTCreditNote",
    "Budget",
    "BudgetLineItem",
    "ApprovalWorkflow",
    "ApprovalWorkflowApprover",
    "ApprovalRequest",
    "ApprovalDecision",
    "LedgerEntry",
    "EntityGroup",
    "EntityGroupMember",
    "IntercompanyTransaction",
    "DimensionType",
    "MatchingStatus",
    "WHTCreditStatus",
    "ApprovalStatus",
    "BudgetPeriodType",
]
