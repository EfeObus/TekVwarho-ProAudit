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
# SKU (Commercial Tier) Models
from app.models.sku import (
    SKUTier,
    IntelligenceAddon,
    Feature,
    UsageMetricType,
    BillingCycle,
    SKUPricing,
    TenantSKU,
    UsageRecord,
    UsageEvent,
    FeatureAccessLog,
    TIER_LIMITS,
    INTELLIGENCE_LIMITS,
    # Billing features #30-36
    PaymentTransaction,
    ServiceCredit,
    DiscountCode,
    DiscountCodeUsage,
    VolumeDiscountRule,
    ExchangeRate,
    ScheduledUsageReport,
    UsageReportHistory,
)
from app.models.entity import BusinessEntity
from app.models.category import Category, CategoryType
from app.models.vendor import Vendor
from app.models.customer import Customer
from app.models.transaction import Transaction, TransactionType
from app.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus
from app.models.inventory import InventoryItem, StockMovement, StockWriteOff
from app.models.tax import VATRecord, PAYERecord, TaxPeriod
# Consolidated Audit System - all audit models in one file
from app.models.audit_consolidated import (
    # Basic Audit
    AuditLog,
    AuditAction,
    # Advanced Audit System
    AuditRun,
    AuditRunStatus,
    AuditRunType,
    AuditFinding,
    FindingRiskLevel,
    FindingCategory,
    AuditEvidence,
    EvidenceType,
    AuditorSession,
    AuditorActionLog,
    AuditorActionType,
)
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
    # Loan Management
    EmployeeLoan,
    LoanRepayment,
    LoanType,
    LoanStatus,
    # Leave Management
    EmployeeLeave,
    LeaveType,
    LeaveStatus,
    # Settings
    PayrollSettings,
)
from app.models.bank_reconciliation import (
    BankAccount,
    BankStatement,
    BankStatementTransaction,
    BankReconciliation,
    ReconciliationAdjustment,
    UnmatchedItem,
    BankChargeRule,
    MatchingRule,
    BankStatementImport,
    # Enums
    BankAccountCurrency,
    BankStatementSource,
    ReconciliationStatus,
    MatchType,
    MatchConfidenceLevel,
    AdjustmentType,
    UnmatchedItemType,
    ChargeDetectionMethod,
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
# Expense Claims
from app.models.expense_claims import (
    ExpenseClaim,
    ExpenseClaimItem,
    ExpenseCategory,
    ClaimStatus,
    PaymentMethod,
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
    # Payroll - Loan Management
    "EmployeeLoan",
    "LoanRepayment",
    "LoanType",
    "LoanStatus",
    # Payroll - Leave Management
    "EmployeeLeave",
    "LeaveType",
    "LeaveStatus",
    # Payroll - Settings
    "PayrollSettings",
    # Audit
    "AuditLog",
    # Advanced Audit System
    "AuditRun",
    "AuditRunStatus",
    "AuditRunType",
    "AuditFinding",
    "FindingRiskLevel",
    "FindingCategory",
    "AuditEvidence",
    "EvidenceType",
    "AuditorSession",
    "AuditorActionLog",
    "AuditorActionType",
    "AuditAction",
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
    # Bank Reconciliation
    "BankAccount",
    "BankStatement",
    "BankStatementTransaction",
    "BankReconciliation",
    "ReconciliationAdjustment",
    "UnmatchedItem",
    "BankChargeRule",
    "MatchingRule",
    "BankStatementImport",
    "BankAccountCurrency",
    "BankStatementSource",
    "ReconciliationStatus",
    "MatchType",
    "MatchConfidenceLevel",
    "AdjustmentType",
    "UnmatchedItemType",
    "ChargeDetectionMethod",
    # Billing Features #30-36
    "PaymentTransaction",
    "ServiceCredit",
    "DiscountCode",
    "DiscountCodeUsage",
    "VolumeDiscountRule",
    "ExchangeRate",
    "ScheduledUsageReport",
    "UsageReportHistory",
    # Expense Claims
    "ExpenseClaim",
    "ExpenseClaimItem",
    "ExpenseCategory",
    "ClaimStatus",
    "PaymentMethod",
]
