"""
TekVwarho ProAudit - Accounting Schemas

Pydantic schemas for Chart of Accounts and General Ledger.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator, ConfigDict


# =============================================================================
# ENUMS
# =============================================================================

class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    INCOME = "income"
    EXPENSE = "expense"


class AccountSubType(str, Enum):
    # Asset sub-types
    CASH = "cash"
    BANK = "bank"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    INVENTORY = "inventory"
    PREPAID_EXPENSE = "prepaid_expense"
    FIXED_ASSET = "fixed_asset"
    ACCUMULATED_DEPRECIATION = "accumulated_depreciation"
    OTHER_CURRENT_ASSET = "other_current_asset"
    OTHER_NON_CURRENT_ASSET = "other_non_current_asset"
    
    # Liability sub-types
    ACCOUNTS_PAYABLE = "accounts_payable"
    ACCRUED_EXPENSE = "accrued_expense"
    VAT_PAYABLE = "vat_payable"
    WHT_PAYABLE = "wht_payable"
    PAYE_PAYABLE = "paye_payable"
    PENSION_PAYABLE = "pension_payable"
    LOAN = "loan"
    OTHER_CURRENT_LIABILITY = "other_current_liability"
    OTHER_NON_CURRENT_LIABILITY = "other_non_current_liability"
    
    # Equity sub-types
    SHARE_CAPITAL = "share_capital"
    RETAINED_EARNINGS = "retained_earnings"
    DRAWINGS = "drawings"
    OTHER_EQUITY = "other_equity"
    
    # Revenue sub-types
    SALES_REVENUE = "sales_revenue"
    SERVICE_REVENUE = "service_revenue"
    INTEREST_INCOME = "interest_income"
    OTHER_INCOME = "other_income"
    
    # Expense sub-types
    COST_OF_GOODS_SOLD = "cost_of_goods_sold"
    SALARY_EXPENSE = "salary_expense"
    RENT_EXPENSE = "rent_expense"
    UTILITIES_EXPENSE = "utilities_expense"
    DEPRECIATION_EXPENSE = "depreciation_expense"
    BANK_CHARGES = "bank_charges"
    TAX_EXPENSE = "tax_expense"
    OTHER_EXPENSE = "other_expense"


class NormalBalance(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class JournalEntryStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    POSTED = "posted"
    REVERSED = "reversed"
    VOIDED = "voided"


class JournalEntryType(str, Enum):
    MANUAL = "manual"
    SALES = "sales"
    PURCHASE = "purchase"
    RECEIPT = "receipt"
    PAYMENT = "payment"
    PAYROLL = "payroll"
    DEPRECIATION = "depreciation"
    TAX_ADJUSTMENT = "tax_adjustment"
    BANK_RECONCILIATION = "bank_reconciliation"
    INVENTORY_ADJUSTMENT = "inventory_adjustment"
    OPENING_BALANCE = "opening_balance"
    CLOSING_ENTRY = "closing_entry"
    REVERSAL = "reversal"
    ACCRUAL = "accrual"
    PREPAYMENT = "prepayment"
    TRANSFER = "transfer"
    SYSTEM = "system"


class FiscalPeriodStatus(str, Enum):
    OPEN = "open"
    PENDING_CLOSE = "pending_close"
    CLOSED = "closed"
    LOCKED = "locked"
    REOPENED = "reopened"


# =============================================================================
# CHART OF ACCOUNTS SCHEMAS
# =============================================================================

class ChartOfAccountsBase(BaseModel):
    """Base schema for Chart of Accounts."""
    account_code: str = Field(..., min_length=1, max_length=20)
    account_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    account_type: AccountType
    account_sub_type: Optional[AccountSubType] = None
    normal_balance: NormalBalance
    parent_id: Optional[UUID] = None
    is_header: bool = False
    opening_balance: Decimal = Decimal("0.00")
    opening_balance_date: Optional[date] = None
    bank_account_id: Optional[UUID] = None
    is_tax_account: bool = False
    tax_type: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    is_reconcilable: bool = False
    cash_flow_category: Optional[str] = None
    sort_order: int = 0


class ChartOfAccountsCreate(ChartOfAccountsBase):
    """Schema for creating a new account."""
    pass


class ChartOfAccountsUpdate(BaseModel):
    """Schema for updating an account."""
    account_name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    account_sub_type: Optional[AccountSubType] = None
    parent_id: Optional[UUID] = None
    is_header: Optional[bool] = None
    bank_account_id: Optional[UUID] = None
    is_tax_account: Optional[bool] = None
    tax_type: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    is_reconcilable: Optional[bool] = None
    is_active: Optional[bool] = None
    cash_flow_category: Optional[str] = None
    sort_order: Optional[int] = None


class ChartOfAccountsResponse(ChartOfAccountsBase):
    """Schema for account response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    entity_id: UUID
    level: int
    current_balance: Decimal
    ytd_debit: Decimal
    ytd_credit: Decimal
    is_system_account: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ChartOfAccountsTree(ChartOfAccountsResponse):
    """Schema for hierarchical account tree."""
    children: List["ChartOfAccountsTree"] = []


# Self-reference for nested tree
ChartOfAccountsTree.model_rebuild()


class AccountBalanceSummary(BaseModel):
    """Summary of account balance."""
    account_id: UUID
    account_code: str
    account_name: str
    account_type: AccountType
    current_balance: Decimal
    ytd_debit: Decimal
    ytd_credit: Decimal


# =============================================================================
# FISCAL PERIOD SCHEMAS
# =============================================================================

class FiscalYearBase(BaseModel):
    """Base schema for Fiscal Year."""
    year_name: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date


class FiscalYearCreate(FiscalYearBase):
    """Schema for creating fiscal year."""
    auto_create_periods: bool = True


class FiscalYearResponse(FiscalYearBase):
    """Schema for fiscal year response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    entity_id: UUID
    is_current: bool
    is_closed: bool
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[UUID] = None


class FiscalPeriodBase(BaseModel):
    """Base schema for Fiscal Period."""
    period_name: str = Field(..., min_length=1, max_length=50)
    period_number: int = Field(..., ge=1, le=13)
    start_date: date
    end_date: date


class FiscalPeriodCreate(FiscalPeriodBase):
    """Schema for creating fiscal period."""
    fiscal_year_id: UUID


class FiscalPeriodUpdate(BaseModel):
    """Schema for updating fiscal period."""
    status: Optional[FiscalPeriodStatus] = None
    closing_notes: Optional[str] = None


class FiscalPeriodResponse(FiscalPeriodBase):
    """Schema for fiscal period response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    entity_id: UUID
    fiscal_year_id: UUID
    status: FiscalPeriodStatus
    bank_reconciled: bool
    closed_at: Optional[datetime] = None
    closed_by_id: Optional[UUID] = None


# =============================================================================
# JOURNAL ENTRY SCHEMAS
# =============================================================================

class JournalEntryLineBase(BaseModel):
    """Base schema for journal entry line."""
    account_id: UUID
    description: Optional[str] = None
    debit_amount: Decimal = Decimal("0.00")
    credit_amount: Decimal = Decimal("0.00")
    department_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    tax_code: Optional[str] = None
    tax_amount: Decimal = Decimal("0.00")
    customer_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    bank_transaction_id: Optional[UUID] = None
    
    @validator('debit_amount', 'credit_amount')
    def validate_amounts(cls, v):
        if v < 0:
            raise ValueError('Amount cannot be negative')
        return v


class JournalEntryLineCreate(JournalEntryLineBase):
    """Schema for creating journal entry line."""
    pass


class JournalEntryLineResponse(JournalEntryLineBase):
    """Schema for journal entry line response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    journal_entry_id: UUID
    line_number: int
    account_code: Optional[str] = None
    account_name: Optional[str] = None


class JournalEntryBase(BaseModel):
    """Base schema for journal entry."""
    entry_date: date
    description: str = Field(..., min_length=1, max_length=500)
    memo: Optional[str] = None
    entry_type: JournalEntryType = JournalEntryType.MANUAL
    source_module: Optional[str] = None
    source_document_type: Optional[str] = None
    source_document_id: Optional[UUID] = None
    source_reference: Optional[str] = None
    currency: str = "NGN"
    exchange_rate: Decimal = Decimal("1.000000")
    requires_approval: bool = False
    reconciliation_id: Optional[UUID] = None


class JournalEntryCreate(JournalEntryBase):
    """Schema for creating a journal entry."""
    lines: List[JournalEntryLineCreate] = Field(..., min_length=2)
    auto_post: bool = False
    
    @validator('lines')
    def validate_balanced(cls, v):
        total_debit = sum(line.debit_amount for line in v)
        total_credit = sum(line.credit_amount for line in v)
        if total_debit != total_credit:
            raise ValueError(f'Entry must be balanced. Debit: {total_debit}, Credit: {total_credit}')
        if total_debit == 0:
            raise ValueError('Entry must have a non-zero amount')
        return v


class JournalEntryUpdate(BaseModel):
    """Schema for updating a journal entry (draft only)."""
    entry_date: Optional[date] = None
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    memo: Optional[str] = None
    lines: Optional[List[JournalEntryLineCreate]] = None
    
    @validator('lines')
    def validate_balanced(cls, v):
        if v is None:
            return v
        total_debit = sum(line.debit_amount for line in v)
        total_credit = sum(line.credit_amount for line in v)
        if total_debit != total_credit:
            raise ValueError(f'Entry must be balanced. Debit: {total_debit}, Credit: {total_credit}')
        return v


class JournalEntryResponse(JournalEntryBase):
    """Schema for journal entry response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    entity_id: UUID
    fiscal_period_id: Optional[UUID] = None
    entry_number: str
    total_debit: Decimal
    total_credit: Decimal
    status: JournalEntryStatus
    posted_at: Optional[datetime] = None
    posted_by_id: Optional[UUID] = None
    is_reversed: bool
    reversed_at: Optional[datetime] = None
    reversal_entry_id: Optional[UUID] = None
    original_entry_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approved_by_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    lines: List[JournalEntryLineResponse] = []


class JournalEntryListResponse(BaseModel):
    """Schema for paginated journal entries list."""
    items: List[JournalEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class JournalEntryPost(BaseModel):
    """Schema for posting a journal entry."""
    post_date: Optional[date] = None


class JournalEntryReverse(BaseModel):
    """Schema for reversing a journal entry."""
    reversal_date: date
    reason: str = Field(..., min_length=1, max_length=500)


# =============================================================================
# REPORTING SCHEMAS
# =============================================================================

class TrialBalanceItem(BaseModel):
    """Item in trial balance report."""
    account_id: UUID
    account_code: str
    account_name: str
    account_type: AccountType
    debit_balance: Decimal
    credit_balance: Decimal


class TrialBalanceReport(BaseModel):
    """Trial balance report."""
    entity_id: UUID
    as_of_date: date
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool
    items: List[TrialBalanceItem]


class IncomeStatementItem(BaseModel):
    """Item in income statement."""
    account_id: UUID
    account_code: str
    account_name: str
    account_sub_type: Optional[AccountSubType]
    amount: Decimal


class IncomeStatementReport(BaseModel):
    """Income statement (P&L) report."""
    entity_id: UUID
    start_date: date
    end_date: date
    revenue_items: List[IncomeStatementItem]
    expense_items: List[IncomeStatementItem]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class BalanceSheetItem(BaseModel):
    """Item in balance sheet."""
    account_id: UUID
    account_code: str
    account_name: str
    account_sub_type: Optional[AccountSubType]
    balance: Decimal


class BalanceSheetReport(BaseModel):
    """Balance sheet report."""
    entity_id: UUID
    as_of_date: date
    assets: List[BalanceSheetItem]
    liabilities: List[BalanceSheetItem]
    equity: List[BalanceSheetItem]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool


class AccountLedgerEntry(BaseModel):
    """Single entry in account ledger."""
    date: date
    entry_number: str
    description: str
    reference: Optional[str]
    debit: Decimal
    credit: Decimal
    balance: Decimal


class AccountLedgerReport(BaseModel):
    """Account ledger (T-account) report."""
    account_id: UUID
    account_code: str
    account_name: str
    account_type: AccountType
    start_date: date
    end_date: date
    opening_balance: Decimal
    entries: List[AccountLedgerEntry]
    total_debits: Decimal
    total_credits: Decimal
    closing_balance: Decimal


# =============================================================================
# GL INTEGRATION SCHEMAS
# =============================================================================

class GLPostingRequest(BaseModel):
    """Request to post a document to GL."""
    source_module: str
    source_document_type: str
    source_document_id: UUID
    source_reference: Optional[str] = None
    entry_date: date
    description: str
    lines: List[JournalEntryLineCreate]
    auto_post: bool = True


class GLPostingResponse(BaseModel):
    """Response from GL posting."""
    success: bool
    journal_entry_id: Optional[UUID] = None
    entry_number: Optional[str] = None
    message: str


# =============================================================================
# PERIOD CLOSE SCHEMAS
# =============================================================================

class PeriodCloseChecklist(BaseModel):
    """Checklist for closing a period."""
    period_id: UUID
    period_name: str
    
    # Checks
    all_entries_posted: bool
    bank_reconciliations_complete: bool
    outstanding_items_reviewed: bool
    adjusting_entries_made: bool
    trial_balance_balanced: bool
    
    # Details
    unposted_entries_count: int
    unreconciled_bank_accounts: List[str]
    outstanding_items_count: int
    
    can_close: bool
    blocking_issues: List[str]


class PeriodCloseRequest(BaseModel):
    """Request to close a fiscal period."""
    period_id: UUID
    closing_notes: Optional[str] = None
    force_close: bool = False


class PeriodCloseResponse(BaseModel):
    """Response from period close."""
    success: bool
    period_id: UUID
    status: FiscalPeriodStatus
    message: str
    closed_at: Optional[datetime] = None
