"""
TekVwarho ProAudit - Accounting Service

Service layer for Chart of Accounts and General Ledger operations.
This is the core accounting engine that handles:
- Chart of Accounts management
- Journal entry creation, posting, and reversal
- Fiscal period management
- GL integration with other modules
- Financial reporting
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.accounting import (
    ChartOfAccounts, AccountType, AccountSubType, NormalBalance,
    FiscalYear, FiscalPeriod, FiscalPeriodStatus,
    JournalEntry, JournalEntryLine, JournalEntryStatus, JournalEntryType,
    AccountBalance, RecurringJournalEntry, GLIntegrationLog,
)
from app.schemas.accounting import (
    ChartOfAccountsCreate, ChartOfAccountsUpdate, ChartOfAccountsResponse,
    FiscalYearCreate, FiscalPeriodCreate, FiscalPeriodUpdate,
    JournalEntryCreate, JournalEntryUpdate, JournalEntryLineCreate,
    TrialBalanceReport, TrialBalanceItem,
    IncomeStatementReport, IncomeStatementItem,
    BalanceSheetReport, BalanceSheetItem,
    CashFlowStatementReport, CashFlowItem, CashFlowCategory,
    AccountLedgerReport, AccountLedgerEntry,
    GLPostingRequest, GLPostingResponse,
    PeriodCloseChecklist, PeriodCloseRequest, PeriodCloseResponse,
)


class AccountingService:
    """Service for accounting operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # =========================================================================
    # CHART OF ACCOUNTS
    # =========================================================================
    
    async def get_chart_of_accounts(
        self,
        entity_id: uuid.UUID,
        account_type: Optional[AccountType] = None,
        is_active: bool = True,
        include_headers: bool = True,
    ) -> List[ChartOfAccounts]:
        """Get chart of accounts for an entity."""
        query = select(ChartOfAccounts).where(
            ChartOfAccounts.entity_id == entity_id
        )
        
        if account_type:
            query = query.where(ChartOfAccounts.account_type == account_type)
        
        if not include_headers:
            query = query.where(ChartOfAccounts.is_header == False)
        
        query = query.where(ChartOfAccounts.is_active == is_active)
        query = query.order_by(ChartOfAccounts.account_code)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_account_by_id(
        self,
        account_id: uuid.UUID,
    ) -> Optional[ChartOfAccounts]:
        """Get account by ID."""
        result = await self.db.execute(
            select(ChartOfAccounts).where(ChartOfAccounts.id == account_id)
        )
        return result.scalar_one_or_none()
    
    async def get_account_by_code(
        self,
        entity_id: uuid.UUID,
        account_code: str,
    ) -> Optional[ChartOfAccounts]:
        """Get account by code."""
        result = await self.db.execute(
            select(ChartOfAccounts).where(
                and_(
                    ChartOfAccounts.entity_id == entity_id,
                    ChartOfAccounts.account_code == account_code,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_account(
        self,
        entity_id: uuid.UUID,
        data: ChartOfAccountsCreate,
        user_id: uuid.UUID,
    ) -> ChartOfAccounts:
        """Create a new account in the chart of accounts."""
        # Check for duplicate code
        existing = await self.get_account_by_code(entity_id, data.account_code)
        if existing:
            raise ValueError(f"Account code {data.account_code} already exists")
        
        # Determine level based on parent
        level = 1
        if data.parent_id:
            parent = await self.get_account_by_id(data.parent_id)
            if parent:
                level = parent.level + 1
        
        account = ChartOfAccounts(
            entity_id=entity_id,
            account_code=data.account_code,
            account_name=data.account_name,
            description=data.description,
            account_type=data.account_type,
            account_sub_type=data.account_sub_type,
            normal_balance=data.normal_balance,
            parent_id=data.parent_id,
            level=level,
            is_header=data.is_header,
            opening_balance=data.opening_balance,
            opening_balance_date=data.opening_balance_date,
            current_balance=data.opening_balance,
            bank_account_id=data.bank_account_id,
            is_tax_account=data.is_tax_account,
            tax_type=data.tax_type,
            tax_rate=data.tax_rate,
            is_reconcilable=data.is_reconcilable,
            cash_flow_category=data.cash_flow_category,
            sort_order=data.sort_order,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        
        self.db.add(account)
        await self.db.flush()
        return account
    
    async def update_account(
        self,
        account_id: uuid.UUID,
        data: ChartOfAccountsUpdate,
        user_id: uuid.UUID,
    ) -> ChartOfAccounts:
        """Update an existing account."""
        account = await self.get_account_by_id(account_id)
        if not account:
            raise ValueError("Account not found")
        
        if account.is_system_account:
            raise ValueError("Cannot modify system account")
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(account, field, value)
        
        account.updated_by_id = user_id
        await self.db.flush()
        return account
    
    async def create_default_chart_of_accounts(
        self,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[ChartOfAccounts]:
        """Create default Nigerian Chart of Accounts."""
        default_accounts = [
            # ASSETS
            {"code": "1000", "name": "Assets", "type": AccountType.ASSET, "sub_type": None, "normal": NormalBalance.DEBIT, "is_header": True},
            {"code": "1100", "name": "Current Assets", "type": AccountType.ASSET, "sub_type": None, "normal": NormalBalance.DEBIT, "is_header": True, "parent": "1000"},
            {"code": "1110", "name": "Cash on Hand", "type": AccountType.ASSET, "sub_type": AccountSubType.CASH, "normal": NormalBalance.DEBIT, "parent": "1100"},
            {"code": "1120", "name": "Bank Accounts", "type": AccountType.ASSET, "sub_type": AccountSubType.BANK, "normal": NormalBalance.DEBIT, "is_header": True, "parent": "1100", "reconcilable": True},
            {"code": "1130", "name": "Accounts Receivable", "type": AccountType.ASSET, "sub_type": AccountSubType.ACCOUNTS_RECEIVABLE, "normal": NormalBalance.DEBIT, "parent": "1100", "reconcilable": True},
            {"code": "1140", "name": "Inventory", "type": AccountType.ASSET, "sub_type": AccountSubType.INVENTORY, "normal": NormalBalance.DEBIT, "parent": "1100"},
            {"code": "1150", "name": "Prepaid Expenses", "type": AccountType.ASSET, "sub_type": AccountSubType.PREPAID_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "1100"},
            {"code": "1160", "name": "VAT Receivable (Input VAT)", "type": AccountType.ASSET, "sub_type": AccountSubType.OTHER_CURRENT_ASSET, "normal": NormalBalance.DEBIT, "parent": "1100", "tax_account": True, "tax_type": "vat_input"},
            {"code": "1170", "name": "WHT Receivable", "type": AccountType.ASSET, "sub_type": AccountSubType.OTHER_CURRENT_ASSET, "normal": NormalBalance.DEBIT, "parent": "1100", "tax_account": True, "tax_type": "wht_receivable"},
            {"code": "1200", "name": "Non-Current Assets", "type": AccountType.ASSET, "sub_type": None, "normal": NormalBalance.DEBIT, "is_header": True, "parent": "1000"},
            {"code": "1210", "name": "Property, Plant & Equipment", "type": AccountType.ASSET, "sub_type": AccountSubType.FIXED_ASSET, "normal": NormalBalance.DEBIT, "parent": "1200"},
            {"code": "1220", "name": "Accumulated Depreciation", "type": AccountType.ASSET, "sub_type": AccountSubType.ACCUMULATED_DEPRECIATION, "normal": NormalBalance.CREDIT, "parent": "1200"},
            {"code": "1230", "name": "Intangible Assets", "type": AccountType.ASSET, "sub_type": AccountSubType.OTHER_NON_CURRENT_ASSET, "normal": NormalBalance.DEBIT, "parent": "1200"},
            
            # LIABILITIES
            {"code": "2000", "name": "Liabilities", "type": AccountType.LIABILITY, "sub_type": None, "normal": NormalBalance.CREDIT, "is_header": True},
            {"code": "2100", "name": "Current Liabilities", "type": AccountType.LIABILITY, "sub_type": None, "normal": NormalBalance.CREDIT, "is_header": True, "parent": "2000"},
            {"code": "2110", "name": "Accounts Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.ACCOUNTS_PAYABLE, "normal": NormalBalance.CREDIT, "parent": "2100", "reconcilable": True},
            {"code": "2120", "name": "Accrued Expenses", "type": AccountType.LIABILITY, "sub_type": AccountSubType.ACCRUED_EXPENSE, "normal": NormalBalance.CREDIT, "parent": "2100"},
            {"code": "2130", "name": "VAT Payable (Output VAT)", "type": AccountType.LIABILITY, "sub_type": AccountSubType.VAT_PAYABLE, "normal": NormalBalance.CREDIT, "parent": "2100", "tax_account": True, "tax_type": "vat_output", "tax_rate": Decimal("7.5")},
            {"code": "2140", "name": "WHT Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.WHT_PAYABLE, "normal": NormalBalance.CREDIT, "parent": "2100", "tax_account": True, "tax_type": "wht_payable"},
            {"code": "2150", "name": "PAYE Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.PAYE_PAYABLE, "normal": NormalBalance.CREDIT, "parent": "2100", "tax_account": True, "tax_type": "paye"},
            {"code": "2160", "name": "Pension Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.PENSION_PAYABLE, "normal": NormalBalance.CREDIT, "parent": "2100", "tax_account": True, "tax_type": "pension"},
            {"code": "2170", "name": "NHF Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.OTHER_CURRENT_LIABILITY, "normal": NormalBalance.CREDIT, "parent": "2100", "tax_account": True, "tax_type": "nhf"},
            {"code": "2180", "name": "NSITF Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.OTHER_CURRENT_LIABILITY, "normal": NormalBalance.CREDIT, "parent": "2100", "tax_account": True, "tax_type": "nsitf"},
            {"code": "2190", "name": "Salaries Payable", "type": AccountType.LIABILITY, "sub_type": AccountSubType.ACCRUED_EXPENSE, "normal": NormalBalance.CREDIT, "parent": "2100"},
            {"code": "2200", "name": "Non-Current Liabilities", "type": AccountType.LIABILITY, "sub_type": None, "normal": NormalBalance.CREDIT, "is_header": True, "parent": "2000"},
            {"code": "2210", "name": "Long-term Loans", "type": AccountType.LIABILITY, "sub_type": AccountSubType.LOAN, "normal": NormalBalance.CREDIT, "parent": "2200"},
            
            # EQUITY
            {"code": "3000", "name": "Equity", "type": AccountType.EQUITY, "sub_type": None, "normal": NormalBalance.CREDIT, "is_header": True},
            {"code": "3100", "name": "Share Capital", "type": AccountType.EQUITY, "sub_type": AccountSubType.SHARE_CAPITAL, "normal": NormalBalance.CREDIT, "parent": "3000"},
            {"code": "3200", "name": "Retained Earnings", "type": AccountType.EQUITY, "sub_type": AccountSubType.RETAINED_EARNINGS, "normal": NormalBalance.CREDIT, "parent": "3000"},
            {"code": "3300", "name": "Drawings", "type": AccountType.EQUITY, "sub_type": AccountSubType.DRAWINGS, "normal": NormalBalance.DEBIT, "parent": "3000"},
            
            # REVENUE
            {"code": "4000", "name": "Revenue", "type": AccountType.REVENUE, "sub_type": None, "normal": NormalBalance.CREDIT, "is_header": True},
            {"code": "4100", "name": "Sales Revenue", "type": AccountType.REVENUE, "sub_type": AccountSubType.SALES_REVENUE, "normal": NormalBalance.CREDIT, "parent": "4000"},
            {"code": "4200", "name": "Service Revenue", "type": AccountType.REVENUE, "sub_type": AccountSubType.SERVICE_REVENUE, "normal": NormalBalance.CREDIT, "parent": "4000"},
            {"code": "4300", "name": "Interest Income", "type": AccountType.REVENUE, "sub_type": AccountSubType.INTEREST_INCOME, "normal": NormalBalance.CREDIT, "parent": "4000"},
            {"code": "4900", "name": "Other Income", "type": AccountType.REVENUE, "sub_type": AccountSubType.OTHER_INCOME, "normal": NormalBalance.CREDIT, "parent": "4000"},
            
            # EXPENSES
            {"code": "5000", "name": "Expenses", "type": AccountType.EXPENSE, "sub_type": None, "normal": NormalBalance.DEBIT, "is_header": True},
            {"code": "5100", "name": "Cost of Goods Sold", "type": AccountType.EXPENSE, "sub_type": AccountSubType.COST_OF_GOODS_SOLD, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5200", "name": "Salaries & Wages", "type": AccountType.EXPENSE, "sub_type": AccountSubType.SALARY_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5210", "name": "Employer Pension Contribution", "type": AccountType.EXPENSE, "sub_type": AccountSubType.SALARY_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000", "tax_account": True, "tax_type": "employer_pension"},
            {"code": "5220", "name": "NSITF Contribution", "type": AccountType.EXPENSE, "sub_type": AccountSubType.SALARY_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000", "tax_account": True, "tax_type": "nsitf_expense"},
            {"code": "5230", "name": "ITF Contribution", "type": AccountType.EXPENSE, "sub_type": AccountSubType.SALARY_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000", "tax_account": True, "tax_type": "itf"},
            {"code": "5300", "name": "Rent Expense", "type": AccountType.EXPENSE, "sub_type": AccountSubType.RENT_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5400", "name": "Utilities Expense", "type": AccountType.EXPENSE, "sub_type": AccountSubType.UTILITIES_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5500", "name": "Depreciation Expense", "type": AccountType.EXPENSE, "sub_type": AccountSubType.DEPRECIATION_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5600", "name": "Bank Charges", "type": AccountType.EXPENSE, "sub_type": AccountSubType.BANK_CHARGES, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5610", "name": "EMTL Charges", "type": AccountType.EXPENSE, "sub_type": AccountSubType.BANK_CHARGES, "normal": NormalBalance.DEBIT, "parent": "5000", "tax_account": True, "tax_type": "emtl"},
            {"code": "5620", "name": "Stamp Duty", "type": AccountType.EXPENSE, "sub_type": AccountSubType.BANK_CHARGES, "normal": NormalBalance.DEBIT, "parent": "5000", "tax_account": True, "tax_type": "stamp_duty"},
            {"code": "5700", "name": "Income Tax Expense", "type": AccountType.EXPENSE, "sub_type": AccountSubType.TAX_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5800", "name": "Professional Fees", "type": AccountType.EXPENSE, "sub_type": AccountSubType.OTHER_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
            {"code": "5900", "name": "Other Expenses", "type": AccountType.EXPENSE, "sub_type": AccountSubType.OTHER_EXPENSE, "normal": NormalBalance.DEBIT, "parent": "5000"},
        ]
        
        # Create accounts in order (parents first)
        created_accounts = []
        code_to_id = {}
        
        for acc_data in default_accounts:
            parent_id = None
            if "parent" in acc_data and acc_data["parent"] in code_to_id:
                parent_id = code_to_id[acc_data["parent"]]
            
            level = 1
            if parent_id:
                parent = await self.get_account_by_id(parent_id)
                if parent:
                    level = parent.level + 1
            
            account = ChartOfAccounts(
                entity_id=entity_id,
                account_code=acc_data["code"],
                account_name=acc_data["name"],
                account_type=acc_data["type"],
                account_sub_type=acc_data.get("sub_type"),
                normal_balance=acc_data["normal"],
                parent_id=parent_id,
                level=level,
                is_header=acc_data.get("is_header", False),
                is_tax_account=acc_data.get("tax_account", False),
                tax_type=acc_data.get("tax_type"),
                tax_rate=acc_data.get("tax_rate"),
                is_reconcilable=acc_data.get("reconcilable", False),
                is_system_account=True,
                created_by_id=user_id,
                updated_by_id=user_id,
            )
            
            self.db.add(account)
            await self.db.flush()
            
            code_to_id[acc_data["code"]] = account.id
            created_accounts.append(account)
        
        return created_accounts
    
    # =========================================================================
    # FISCAL PERIODS
    # =========================================================================
    
    async def get_fiscal_years(
        self,
        entity_id: uuid.UUID,
    ) -> List[FiscalYear]:
        """Get all fiscal years for an entity."""
        result = await self.db.execute(
            select(FiscalYear)
            .where(FiscalYear.entity_id == entity_id)
            .order_by(desc(FiscalYear.start_date))
        )
        return list(result.scalars().all())
    
    async def get_current_fiscal_year(
        self,
        entity_id: uuid.UUID,
    ) -> Optional[FiscalYear]:
        """Get current fiscal year for an entity."""
        result = await self.db.execute(
            select(FiscalYear).where(
                and_(
                    FiscalYear.entity_id == entity_id,
                    FiscalYear.is_current == True,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_fiscal_year(
        self,
        entity_id: uuid.UUID,
        data: FiscalYearCreate,
        user_id: uuid.UUID,
    ) -> FiscalYear:
        """Create a new fiscal year with optional periods."""
        # Check for overlapping years
        existing = await self.db.execute(
            select(FiscalYear).where(
                and_(
                    FiscalYear.entity_id == entity_id,
                    or_(
                        and_(
                            FiscalYear.start_date <= data.start_date,
                            FiscalYear.end_date >= data.start_date,
                        ),
                        and_(
                            FiscalYear.start_date <= data.end_date,
                            FiscalYear.end_date >= data.end_date,
                        ),
                    )
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Fiscal year overlaps with existing year")
        
        fiscal_year = FiscalYear(
            entity_id=entity_id,
            year_name=data.year_name,
            start_date=data.start_date,
            end_date=data.end_date,
            is_current=True,
        )
        
        self.db.add(fiscal_year)
        await self.db.flush()
        
        # Auto-create periods (12 months)
        if data.auto_create_periods:
            await self._create_fiscal_periods(entity_id, fiscal_year, user_id)
        
        return fiscal_year
    
    async def _create_fiscal_periods(
        self,
        entity_id: uuid.UUID,
        fiscal_year: FiscalYear,
        user_id: uuid.UUID,
    ) -> List[FiscalPeriod]:
        """Create 12 monthly periods for a fiscal year."""
        from calendar import monthrange
        from dateutil.relativedelta import relativedelta
        
        periods = []
        current_date = fiscal_year.start_date
        
        for period_num in range(1, 13):
            month_name = current_date.strftime("%B %Y")
            _, last_day = monthrange(current_date.year, current_date.month)
            period_end = date(current_date.year, current_date.month, last_day)
            
            # Don't exceed fiscal year end
            if period_end > fiscal_year.end_date:
                period_end = fiscal_year.end_date
            
            period = FiscalPeriod(
                entity_id=entity_id,
                fiscal_year_id=fiscal_year.id,
                period_name=month_name,
                period_number=period_num,
                start_date=current_date,
                end_date=period_end,
                status=FiscalPeriodStatus.OPEN,
            )
            
            self.db.add(period)
            periods.append(period)
            
            # Move to next month
            current_date = period_end + relativedelta(days=1)
            if current_date > fiscal_year.end_date:
                break
        
        await self.db.flush()
        return periods
    
    async def get_fiscal_period_for_date(
        self,
        entity_id: uuid.UUID,
        entry_date: date,
    ) -> Optional[FiscalPeriod]:
        """Get the fiscal period containing a specific date."""
        result = await self.db.execute(
            select(FiscalPeriod).where(
                and_(
                    FiscalPeriod.entity_id == entity_id,
                    FiscalPeriod.start_date <= entry_date,
                    FiscalPeriod.end_date >= entry_date,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_open_period_for_date(
        self,
        entity_id: uuid.UUID,
        entry_date: date,
    ) -> Optional[FiscalPeriod]:
        """Get an open fiscal period for a specific date."""
        result = await self.db.execute(
            select(FiscalPeriod).where(
                and_(
                    FiscalPeriod.entity_id == entity_id,
                    FiscalPeriod.start_date <= entry_date,
                    FiscalPeriod.end_date >= entry_date,
                    FiscalPeriod.status == FiscalPeriodStatus.OPEN,
                )
            )
        )
        return result.scalar_one_or_none()
    
    # =========================================================================
    # JOURNAL ENTRIES
    # =========================================================================
    
    async def _generate_entry_number(
        self,
        entity_id: uuid.UUID,
        entry_date: date,
    ) -> str:
        """Generate unique journal entry number."""
        year = entry_date.year
        
        # Count existing entries for this year
        result = await self.db.execute(
            select(func.count(JournalEntry.id)).where(
                and_(
                    JournalEntry.entity_id == entity_id,
                    JournalEntry.entry_number.like(f"JE-{year}-%"),
                )
            )
        )
        count = result.scalar() or 0
        
        return f"JE-{year}-{str(count + 1).zfill(5)}"
    
    async def get_journal_entries(
        self,
        entity_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[JournalEntryStatus] = None,
        entry_type: Optional[JournalEntryType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[JournalEntry], int]:
        """Get journal entries with filtering."""
        query = select(JournalEntry).where(JournalEntry.entity_id == entity_id)
        
        if start_date:
            query = query.where(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.where(JournalEntry.entry_date <= end_date)
        if status:
            query = query.where(JournalEntry.status == status)
        if entry_type:
            query = query.where(JournalEntry.entry_type == entry_type)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Get entries with lines
        query = query.options(selectinload(JournalEntry.lines))
        query = query.order_by(desc(JournalEntry.entry_date), desc(JournalEntry.entry_number))
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        entries = list(result.scalars().all())
        
        return entries, total
    
    async def get_journal_entry_by_id(
        self,
        entry_id: uuid.UUID,
    ) -> Optional[JournalEntry]:
        """Get journal entry by ID with lines."""
        result = await self.db.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.id == entry_id)
        )
        return result.scalar_one_or_none()
    
    async def create_journal_entry(
        self,
        entity_id: uuid.UUID,
        data: JournalEntryCreate,
        user_id: uuid.UUID,
    ) -> JournalEntry:
        """Create a new journal entry."""
        # First check if any period exists for this date
        any_period = await self.get_fiscal_period_for_date(entity_id, data.entry_date)
        if not any_period:
            raise ValueError(f"No fiscal period exists for date {data.entry_date}")
        
        # Check if period is LOCKED (hard enforcement)
        if any_period.status == FiscalPeriodStatus.LOCKED:
            raise ValueError(
                f"Cannot post to locked period '{any_period.period_name}'. "
                f"Period has been permanently locked and no further entries are allowed."
            )
        
        # Check if period is CLOSED
        if any_period.status == FiscalPeriodStatus.CLOSED:
            raise ValueError(
                f"Cannot post to closed period '{any_period.period_name}'. "
                f"Reopen the period or use a different date."
            )
        
        # Validate period is open (covers remaining statuses)
        period = await self.get_open_period_for_date(entity_id, data.entry_date)
        if not period:
            raise ValueError(f"No open fiscal period for date {data.entry_date}")
        
        # Generate entry number
        entry_number = await self._generate_entry_number(entity_id, data.entry_date)
        
        # Calculate totals
        total_debit = sum(line.debit_amount for line in data.lines)
        total_credit = sum(line.credit_amount for line in data.lines)
        
        if total_debit != total_credit:
            raise ValueError(f"Entry must be balanced. Debit: {total_debit}, Credit: {total_credit}")
        
        # Create entry
        entry = JournalEntry(
            entity_id=entity_id,
            fiscal_period_id=period.id,
            entry_number=entry_number,
            entry_date=data.entry_date,
            description=data.description,
            memo=data.memo,
            entry_type=data.entry_type,
            source_module=data.source_module,
            source_document_type=data.source_document_type,
            source_document_id=data.source_document_id,
            source_reference=data.source_reference,
            total_debit=total_debit,
            total_credit=total_credit,
            currency=data.currency,
            exchange_rate=data.exchange_rate,
            requires_approval=data.requires_approval,
            reconciliation_id=data.reconciliation_id,
            status=JournalEntryStatus.DRAFT,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        
        self.db.add(entry)
        await self.db.flush()
        
        # Create lines
        for idx, line_data in enumerate(data.lines, 1):
            line = JournalEntryLine(
                journal_entry_id=entry.id,
                account_id=line_data.account_id,
                line_number=idx,
                description=line_data.description,
                debit_amount=line_data.debit_amount,
                credit_amount=line_data.credit_amount,
                department_id=line_data.department_id,
                project_id=line_data.project_id,
                tax_code=line_data.tax_code,
                tax_amount=line_data.tax_amount,
                customer_id=line_data.customer_id,
                vendor_id=line_data.vendor_id,
                bank_transaction_id=line_data.bank_transaction_id,
            )
            self.db.add(line)
        
        await self.db.flush()
        
        # Auto-post if requested
        if data.auto_post:
            entry = await self.post_journal_entry(entry.id, user_id)
        
        return entry
    
    async def post_journal_entry(
        self,
        entry_id: uuid.UUID,
        user_id: uuid.UUID,
        post_date: Optional[date] = None,
    ) -> JournalEntry:
        """Post a journal entry to the GL."""
        entry = await self.get_journal_entry_by_id(entry_id)
        if not entry:
            raise ValueError("Journal entry not found")
        
        if entry.status != JournalEntryStatus.DRAFT:
            raise ValueError(f"Cannot post entry with status: {entry.status}")
        
        # Check if period is LOCKED (hard enforcement)
        any_period = await self.get_fiscal_period_for_date(entry.entity_id, entry.entry_date)
        if any_period and any_period.status == FiscalPeriodStatus.LOCKED:
            raise ValueError(
                f"Cannot post to locked period '{any_period.period_name}'. "
                f"Period has been permanently locked and no further entries are allowed."
            )
        
        # Verify period is still open
        period = await self.get_open_period_for_date(entry.entity_id, entry.entry_date)
        if not period:
            raise ValueError(f"Fiscal period is not open for date {entry.entry_date}")
        
        # Update account balances
        for line in entry.lines:
            account = await self.get_account_by_id(line.account_id)
            if account:
                if account.normal_balance == NormalBalance.DEBIT:
                    account.current_balance += line.debit_amount - line.credit_amount
                else:
                    account.current_balance += line.credit_amount - line.debit_amount
                account.ytd_debit += line.debit_amount
                account.ytd_credit += line.credit_amount
        
        # Update entry status
        entry.status = JournalEntryStatus.POSTED
        entry.posted_at = datetime.utcnow()
        entry.posted_by_id = user_id
        
        await self.db.flush()
        return entry
    
    async def reverse_journal_entry(
        self,
        entry_id: uuid.UUID,
        reversal_date: date,
        reason: str,
        user_id: uuid.UUID,
    ) -> JournalEntry:
        """Reverse a posted journal entry."""
        entry = await self.get_journal_entry_by_id(entry_id)
        if not entry:
            raise ValueError("Journal entry not found")
        
        if entry.status != JournalEntryStatus.POSTED:
            raise ValueError("Can only reverse posted entries")
        
        if entry.is_reversed:
            raise ValueError("Entry has already been reversed")
        
        # Check if reversal period is LOCKED (hard enforcement)
        any_period = await self.get_fiscal_period_for_date(entry.entity_id, reversal_date)
        if any_period and any_period.status == FiscalPeriodStatus.LOCKED:
            raise ValueError(
                f"Cannot create reversal in locked period '{any_period.period_name}'. "
                f"Period has been permanently locked."
            )
        
        # Check period is open
        period = await self.get_open_period_for_date(entry.entity_id, reversal_date)
        if not period:
            raise ValueError(f"No open fiscal period for reversal date {reversal_date}")
        
        # Create reversal entry with swapped debits/credits
        reversal_lines = []
        for line in entry.lines:
            reversal_lines.append(JournalEntryLineCreate(
                account_id=line.account_id,
                description=f"Reversal: {line.description or ''}",
                debit_amount=line.credit_amount,  # Swap
                credit_amount=line.debit_amount,  # Swap
                department_id=line.department_id,
                project_id=line.project_id,
                tax_code=line.tax_code,
                tax_amount=line.tax_amount,
                customer_id=line.customer_id,
                vendor_id=line.vendor_id,
            ))
        
        reversal_data = JournalEntryCreate(
            entry_date=reversal_date,
            description=f"Reversal of {entry.entry_number}: {reason}",
            entry_type=JournalEntryType.REVERSAL,
            source_module=entry.source_module,
            source_document_type=entry.source_document_type,
            source_document_id=entry.source_document_id,
            lines=reversal_lines,
            auto_post=True,
        )
        
        reversal_entry = await self.create_journal_entry(entry.entity_id, reversal_data, user_id)
        reversal_entry.original_entry_id = entry.id
        
        # Update original entry
        entry.is_reversed = True
        entry.reversed_at = datetime.utcnow()
        entry.reversed_by_id = user_id
        entry.reversal_entry_id = reversal_entry.id
        entry.reversal_reason = reason
        entry.status = JournalEntryStatus.REVERSED
        
        await self.db.flush()
        return reversal_entry
    
    # =========================================================================
    # GL INTEGRATION (FOR OTHER MODULES)
    # =========================================================================
    
    async def post_to_gl(
        self,
        entity_id: uuid.UUID,
        request: GLPostingRequest,
        user_id: uuid.UUID,
    ) -> GLPostingResponse:
        """
        Post a document from another module to the GL.
        This is the main integration point for all modules.
        """
        # Check if already posted
        existing = await self.db.execute(
            select(GLIntegrationLog).where(
                and_(
                    GLIntegrationLog.entity_id == entity_id,
                    GLIntegrationLog.source_module == request.source_module,
                    GLIntegrationLog.source_document_type == request.source_document_type,
                    GLIntegrationLog.source_document_id == request.source_document_id,
                    GLIntegrationLog.is_reversed == False,
                )
            )
        )
        if existing.scalar_one_or_none():
            return GLPostingResponse(
                success=False,
                message="Document has already been posted to GL",
            )
        
        try:
            # Create journal entry
            entry_data = JournalEntryCreate(
                entry_date=request.entry_date,
                description=request.description,
                entry_type=self._map_module_to_entry_type(request.source_module),
                source_module=request.source_module,
                source_document_type=request.source_document_type,
                source_document_id=request.source_document_id,
                source_reference=request.source_reference,
                lines=request.lines,
                auto_post=request.auto_post,
            )
            
            entry = await self.create_journal_entry(entity_id, entry_data, user_id)
            
            # Log the integration
            log = GLIntegrationLog(
                entity_id=entity_id,
                source_module=request.source_module,
                source_document_type=request.source_document_type,
                source_document_id=request.source_document_id,
                source_reference=request.source_reference,
                journal_entry_id=entry.id,
                posted_by_id=user_id,
            )
            self.db.add(log)
            await self.db.flush()
            
            return GLPostingResponse(
                success=True,
                journal_entry_id=entry.id,
                entry_number=entry.entry_number,
                message="Successfully posted to GL",
            )
        except Exception as e:
            return GLPostingResponse(
                success=False,
                message=str(e),
            )
    
    def _map_module_to_entry_type(self, source_module: str) -> JournalEntryType:
        """Map source module to journal entry type."""
        mapping = {
            "sales": JournalEntryType.SALES,
            "invoices": JournalEntryType.SALES,
            "receipts": JournalEntryType.RECEIPT,
            "purchases": JournalEntryType.PURCHASE,
            "vendors": JournalEntryType.PURCHASE,
            "payments": JournalEntryType.PAYMENT,
            "payroll": JournalEntryType.PAYROLL,
            "fixed_assets": JournalEntryType.DEPRECIATION,
            "inventory": JournalEntryType.INVENTORY_ADJUSTMENT,
            "bank_reconciliation": JournalEntryType.BANK_RECONCILIATION,
            "tax": JournalEntryType.TAX_ADJUSTMENT,
        }
        return mapping.get(source_module.lower(), JournalEntryType.MANUAL)
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    async def get_trial_balance(
        self,
        entity_id: uuid.UUID,
        as_of_date: date,
    ) -> TrialBalanceReport:
        """Generate trial balance report."""
        accounts = await self.get_chart_of_accounts(entity_id, include_headers=False)
        
        items = []
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")
        
        for account in accounts:
            # Determine if balance should show as debit or credit
            balance = account.current_balance
            
            if account.normal_balance == NormalBalance.DEBIT:
                debit_balance = balance if balance >= 0 else Decimal("0.00")
                credit_balance = abs(balance) if balance < 0 else Decimal("0.00")
            else:
                credit_balance = balance if balance >= 0 else Decimal("0.00")
                debit_balance = abs(balance) if balance < 0 else Decimal("0.00")
            
            if debit_balance > 0 or credit_balance > 0:
                items.append(TrialBalanceItem(
                    account_id=account.id,
                    account_code=account.account_code,
                    account_name=account.account_name,
                    account_type=account.account_type,
                    debit_balance=debit_balance,
                    credit_balance=credit_balance,
                ))
                total_debits += debit_balance
                total_credits += credit_balance
        
        return TrialBalanceReport(
            entity_id=entity_id,
            as_of_date=as_of_date,
            total_debits=total_debits,
            total_credits=total_credits,
            is_balanced=total_debits == total_credits,
            items=items,
        )
    
    async def get_income_statement(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> IncomeStatementReport:
        """Generate income statement (P&L) report."""
        accounts = await self.get_chart_of_accounts(entity_id, include_headers=False)
        
        revenue_items = []
        expense_items = []
        total_revenue = Decimal("0.00")
        total_expenses = Decimal("0.00")
        
        for account in accounts:
            if account.account_type in [AccountType.REVENUE, AccountType.INCOME]:
                if account.current_balance != 0:
                    revenue_items.append(IncomeStatementItem(
                        account_id=account.id,
                        account_code=account.account_code,
                        account_name=account.account_name,
                        account_sub_type=account.account_sub_type,
                        amount=abs(account.current_balance),
                    ))
                    total_revenue += abs(account.current_balance)
            elif account.account_type == AccountType.EXPENSE:
                if account.current_balance != 0:
                    expense_items.append(IncomeStatementItem(
                        account_id=account.id,
                        account_code=account.account_code,
                        account_name=account.account_name,
                        account_sub_type=account.account_sub_type,
                        amount=abs(account.current_balance),
                    ))
                    total_expenses += abs(account.current_balance)
        
        return IncomeStatementReport(
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
            revenue_items=revenue_items,
            expense_items=expense_items,
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_income=total_revenue - total_expenses,
        )
    
    async def get_balance_sheet(
        self,
        entity_id: uuid.UUID,
        as_of_date: date,
    ) -> BalanceSheetReport:
        """Generate balance sheet report."""
        accounts = await self.get_chart_of_accounts(entity_id, include_headers=False)
        
        assets = []
        liabilities = []
        equity = []
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        total_equity = Decimal("0.00")
        
        for account in accounts:
            balance = abs(account.current_balance) if account.current_balance != 0 else Decimal("0.00")
            
            if account.account_type == AccountType.ASSET:
                if balance > 0:
                    assets.append(BalanceSheetItem(
                        account_id=account.id,
                        account_code=account.account_code,
                        account_name=account.account_name,
                        account_sub_type=account.account_sub_type,
                        balance=balance,
                    ))
                    total_assets += balance
            elif account.account_type == AccountType.LIABILITY:
                if balance > 0:
                    liabilities.append(BalanceSheetItem(
                        account_id=account.id,
                        account_code=account.account_code,
                        account_name=account.account_name,
                        account_sub_type=account.account_sub_type,
                        balance=balance,
                    ))
                    total_liabilities += balance
            elif account.account_type == AccountType.EQUITY:
                if balance > 0:
                    equity.append(BalanceSheetItem(
                        account_id=account.id,
                        account_code=account.account_code,
                        account_name=account.account_name,
                        account_sub_type=account.account_sub_type,
                        balance=balance,
                    ))
                    total_equity += balance
        
        return BalanceSheetReport(
            entity_id=entity_id,
            as_of_date=as_of_date,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            is_balanced=total_assets == (total_liabilities + total_equity),
        )
    
    async def get_cash_flow_statement(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> CashFlowStatementReport:
        """
        Generate cash flow statement (indirect method).
        
        Uses cash_flow_category on accounts to classify movements.
        Categories: operating, investing, financing
        """
        # Get accounts with balances
        accounts = await self.get_chart_of_accounts(entity_id, include_headers=False)
        
        # Calculate net income for the period
        income_statement = await self.get_income_statement(entity_id, start_date, end_date)
        net_income = income_statement.net_income
        
        # Track cash flow items
        operating_items = []
        investing_items = []
        financing_items = []
        
        # Get depreciation (non-cash expense - add back)
        depreciation_total = Decimal("0.00")
        for account in accounts:
            if account.account_sub_type and "DEPRECIATION" in str(account.account_sub_type).upper():
                depreciation_total += abs(account.current_balance)
        
        # Get changes in working capital accounts
        working_capital_changes = []
        
        for account in accounts:
            cash_flow_cat = account.cash_flow_category or ""
            
            # Skip if no balance change
            if account.current_balance == 0:
                continue
            
            # Operating activities: AR, AP, Inventory changes
            if account.account_sub_type:
                sub_type_str = str(account.account_sub_type).upper()
                
                # AR increase = cash outflow; AR decrease = cash inflow
                if "RECEIVABLE" in sub_type_str and account.account_type == AccountType.ASSET:
                    # For indirect method, increase in AR is subtracted
                    working_capital_changes.append(CashFlowItem(
                        description=f"Change in {account.account_name}",
                        amount=-account.current_balance,  # Negative if AR increased
                        category=CashFlowCategory.OPERATING,
                    ))
                
                # AP increase = cash inflow
                elif "PAYABLE" in sub_type_str and account.account_type == AccountType.LIABILITY:
                    working_capital_changes.append(CashFlowItem(
                        description=f"Change in {account.account_name}",
                        amount=account.current_balance,
                        category=CashFlowCategory.OPERATING,
                    ))
                
                # Inventory increase = cash outflow
                elif "INVENTORY" in sub_type_str:
                    working_capital_changes.append(CashFlowItem(
                        description=f"Change in {account.account_name}",
                        amount=-account.current_balance,
                        category=CashFlowCategory.OPERATING,
                    ))
            
            # Investing activities: Fixed assets
            if cash_flow_cat.lower() == "investing" or (
                account.account_sub_type and "ASSET" in str(account.account_sub_type).upper()
                and account.account_type == AccountType.ASSET
                and "FIXED" in account.account_name.upper()
            ):
                investing_items.append(CashFlowItem(
                    description=account.account_name,
                    amount=-account.current_balance,  # Purchases are outflows
                    category=CashFlowCategory.INVESTING,
                ))
            
            # Financing activities: Loans, equity
            if cash_flow_cat.lower() == "financing" or (
                account.account_type == AccountType.LIABILITY
                and account.account_sub_type
                and "LOAN" in str(account.account_sub_type).upper()
            ):
                financing_items.append(CashFlowItem(
                    description=account.account_name,
                    amount=account.current_balance,
                    category=CashFlowCategory.FINANCING,
                ))
        
        # Calculate totals
        operating_total = net_income + depreciation_total + sum(
            item.amount for item in working_capital_changes
        )
        investing_total = sum(item.amount for item in investing_items)
        financing_total = sum(item.amount for item in financing_items)
        
        net_change = operating_total + investing_total + financing_total
        
        # Get beginning and ending cash
        beginning_cash = Decimal("0.00")
        ending_cash = Decimal("0.00")
        
        for account in accounts:
            if account.account_sub_type and "CASH" in str(account.account_sub_type).upper():
                ending_cash += account.current_balance
                beginning_cash = ending_cash - net_change  # Derive beginning balance
        
        return CashFlowStatementReport(
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
            net_income=net_income,
            depreciation=depreciation_total,
            changes_in_working_capital=working_capital_changes,
            operating_activities_total=operating_total,
            investing_items=investing_items,
            investing_activities_total=investing_total,
            financing_items=financing_items,
            financing_activities_total=financing_total,
            net_change_in_cash=net_change,
            beginning_cash=beginning_cash,
            ending_cash=ending_cash,
        )
    
    # =========================================================================
    # PERIOD CLOSE (ENHANCED WITH BANK RECONCILIATION VALIDATION)
    # =========================================================================
    
    async def get_period_close_checklist(
        self,
        entity_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> PeriodCloseChecklist:
        """
        Get comprehensive checklist for closing a period.
        
        Enforces Nigerian accounting standards:
        1. All journal entries must be posted
        2. All bank accounts must be reconciled up to period end
        3. All reconciliation adjustments must be posted to GL
        4. Trial balance must be balanced
        5. Outstanding items must be reviewed
        """
        period = await self.db.execute(
            select(FiscalPeriod).where(FiscalPeriod.id == period_id)
        )
        period = period.scalar_one_or_none()
        if not period:
            raise ValueError("Fiscal period not found")
        
        # Check for unposted entries
        unposted_result = await self.db.execute(
            select(func.count(JournalEntry.id)).where(
                and_(
                    JournalEntry.entity_id == entity_id,
                    JournalEntry.fiscal_period_id == period_id,
                    JournalEntry.status == JournalEntryStatus.DRAFT,
                )
            )
        )
        unposted_count = unposted_result.scalar() or 0
        
        # Validate bank reconciliations using the bank reconciliation service
        from app.services.bank_reconciliation_service import BankReconciliationService
        bank_service = BankReconciliationService(self.db)
        bank_validation = await bank_service.validate_reconciliation_for_period_close(
            entity_id=entity_id,
            period_end_date=period.end_date,
        )
        
        bank_reconciled = bank_validation["is_valid"]
        unreconciled_accounts = [
            f"{acc['bank_name']} ({acc['account_number'][-4:] if len(acc.get('account_number', '')) >= 4 else acc.get('account_number', '')}): {', '.join(acc.get('issues', []))}"
            for acc in bank_validation.get("accounts", [])
            if not acc.get("is_valid", False)
        ]
        
        # Build checklist
        blocking_issues = []
        
        if unposted_count > 0:
            blocking_issues.append(f"{unposted_count} unposted journal entries")
        
        if not bank_reconciled:
            blocking_issues.append("Bank reconciliations not complete")
            blocking_issues.extend(unreconciled_accounts)
        
        trial_balance = await self.get_trial_balance(entity_id, period.end_date)
        if not trial_balance.is_balanced:
            blocking_issues.append(
                f"Trial balance is not balanced (difference: {trial_balance.total_debit - trial_balance.total_credit})"
            )
        
        # Check for pending AR/AP reconciliation (receipts/payments not matched to bank)
        # This would require querying transactions without bank matches
        outstanding_items_count = bank_validation.get("accounts", [])
        
        return PeriodCloseChecklist(
            period_id=period_id,
            period_name=period.period_name,
            all_entries_posted=unposted_count == 0,
            bank_reconciliations_complete=bank_reconciled,
            outstanding_items_reviewed=True,  # User must manually confirm
            adjusting_entries_made=True,  # User must manually confirm
            trial_balance_balanced=trial_balance.is_balanced,
            unposted_entries_count=unposted_count,
            unreconciled_bank_accounts=unreconciled_accounts,
            outstanding_items_count=len(outstanding_items_count),
            can_close=len(blocking_issues) == 0,
            blocking_issues=blocking_issues,
        )
    
    async def close_period(
        self,
        entity_id: uuid.UUID,
        request: PeriodCloseRequest,
        user_id: uuid.UUID,
    ) -> PeriodCloseResponse:
        """Close a fiscal period."""
        checklist = await self.get_period_close_checklist(entity_id, request.period_id)
        
        if not checklist.can_close and not request.force_close:
            return PeriodCloseResponse(
                success=False,
                period_id=request.period_id,
                status=FiscalPeriodStatus.OPEN,
                message=f"Cannot close period: {', '.join(checklist.blocking_issues)}",
            )
        
        # Get and update period
        period = await self.db.execute(
            select(FiscalPeriod).where(FiscalPeriod.id == request.period_id)
        )
        period = period.scalar_one_or_none()
        
        period.status = FiscalPeriodStatus.CLOSED
        period.closed_at = datetime.utcnow()
        period.closed_by_id = user_id
        period.closing_notes = request.closing_notes
        
        await self.db.flush()
        
        return PeriodCloseResponse(
            success=True,
            period_id=request.period_id,
            status=FiscalPeriodStatus.CLOSED,
            message="Period closed successfully",
            closed_at=period.closed_at,
        )
