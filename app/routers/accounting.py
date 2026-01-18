"""
TekVwarho ProAudit - Accounting Router

API endpoints for Chart of Accounts and General Ledger operations.
This is the central accounting API that all financial modules integrate with.
"""

import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_entity_id
from app.models.user import User
from app.models.accounting import (
    AccountType, JournalEntryStatus, JournalEntryType, FiscalPeriodStatus
)
from app.schemas.accounting import (
    ChartOfAccountsCreate, ChartOfAccountsUpdate, ChartOfAccountsResponse,
    ChartOfAccountsTree,
    FiscalYearCreate, FiscalYearResponse,
    FiscalPeriodCreate, FiscalPeriodUpdate, FiscalPeriodResponse,
    JournalEntryCreate, JournalEntryUpdate, JournalEntryResponse,
    JournalEntryListResponse,
    TrialBalanceReport, IncomeStatementReport, BalanceSheetReport,
    AccountLedgerReport,
    GLPostingRequest, GLPostingResponse,
    PeriodCloseChecklist, PeriodCloseRequest, PeriodCloseResponse,
)
from app.services.accounting_service import AccountingService


router = APIRouter(prefix="/api/v1/entities/{entity_id}/accounting", tags=["Accounting"])


# ============================================================================
# CHART OF ACCOUNTS ENDPOINTS
# ============================================================================

@router.get("/chart-of-accounts", response_model=List[ChartOfAccountsResponse])
async def list_chart_of_accounts(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    account_type: Optional[AccountType] = Query(None, description="Filter by account type"),
    is_active: bool = Query(True, description="Filter by active status"),
    include_headers: bool = Query(True, description="Include header accounts"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chart of accounts for entity."""
    service = AccountingService(db)
    accounts = await service.get_chart_of_accounts(
        entity_id=entity_id,
        account_type=account_type,
        is_active=is_active,
        include_headers=include_headers,
    )
    return accounts


@router.get("/chart-of-accounts/tree", response_model=ChartOfAccountsTree)
async def get_chart_of_accounts_tree(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chart of accounts as hierarchical tree."""
    service = AccountingService(db)
    accounts = await service.get_chart_of_accounts(entity_id=entity_id)
    
    # Build tree structure
    accounts_by_id = {acc.id: acc for acc in accounts}
    root_accounts = [acc for acc in accounts if acc.parent_id is None]
    
    def build_children(account):
        children = [acc for acc in accounts if acc.parent_id == account.id]
        return [
            ChartOfAccountsTree(
                id=child.id,
                account_code=child.account_code,
                account_name=child.account_name,
                account_type=child.account_type,
                account_sub_type=child.account_sub_type,
                normal_balance=child.normal_balance,
                current_balance=child.current_balance,
                level=child.level,
                is_header=child.is_header,
                is_active=child.is_active,
                children=build_children(child),
            )
            for child in sorted(children, key=lambda x: x.account_code)
        ]
    
    # Create top-level tree
    tree = ChartOfAccountsTree(
        id=uuid.UUID('00000000-0000-0000-0000-000000000000'),
        account_code="ROOT",
        account_name="Chart of Accounts",
        account_type=AccountType.ASSET,
        normal_balance=None,
        current_balance=None,
        level=0,
        is_header=True,
        is_active=True,
        children=[
            ChartOfAccountsTree(
                id=acc.id,
                account_code=acc.account_code,
                account_name=acc.account_name,
                account_type=acc.account_type,
                account_sub_type=acc.account_sub_type,
                normal_balance=acc.normal_balance,
                current_balance=acc.current_balance,
                level=acc.level,
                is_header=acc.is_header,
                is_active=acc.is_active,
                children=build_children(acc),
            )
            for acc in sorted(root_accounts, key=lambda x: x.account_code)
        ],
    )
    
    return tree


@router.post("/chart-of-accounts", response_model=ChartOfAccountsResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    data: ChartOfAccountsCreate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new account in the chart of accounts."""
    service = AccountingService(db)
    try:
        account = await service.create_account(
            entity_id=entity_id,
            data=data,
            user_id=current_user.id,
        )
        await db.commit()
        return account
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/chart-of-accounts/{account_id}", response_model=ChartOfAccountsResponse)
async def get_account(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    account_id: uuid.UUID = Path(..., description="Account ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get account by ID."""
    service = AccountingService(db)
    account = await service.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.put("/chart-of-accounts/{account_id}", response_model=ChartOfAccountsResponse)
async def update_account(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    account_id: uuid.UUID = Path(..., description="Account ID"),
    data: ChartOfAccountsUpdate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an account."""
    service = AccountingService(db)
    try:
        account = await service.update_account(
            account_id=account_id,
            data=data,
            user_id=current_user.id,
        )
        await db.commit()
        return account
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/chart-of-accounts/initialize", response_model=List[ChartOfAccountsResponse])
async def initialize_chart_of_accounts(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initialize default Nigerian Chart of Accounts for the entity."""
    service = AccountingService(db)
    
    # Check if accounts already exist
    existing = await service.get_chart_of_accounts(entity_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chart of Accounts already exists. Cannot reinitialize.",
        )
    
    accounts = await service.create_default_chart_of_accounts(
        entity_id=entity_id,
        user_id=current_user.id,
    )
    await db.commit()
    return accounts


# ============================================================================
# FISCAL YEAR & PERIOD ENDPOINTS
# ============================================================================

@router.get("/fiscal-years", response_model=List[FiscalYearResponse])
async def list_fiscal_years(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all fiscal years for entity."""
    service = AccountingService(db)
    return await service.get_fiscal_years(entity_id)


@router.post("/fiscal-years", response_model=FiscalYearResponse, status_code=status.HTTP_201_CREATED)
async def create_fiscal_year(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    data: FiscalYearCreate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new fiscal year with monthly periods."""
    service = AccountingService(db)
    try:
        fiscal_year = await service.create_fiscal_year(
            entity_id=entity_id,
            data=data,
            user_id=current_user.id,
        )
        await db.commit()
        return fiscal_year
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/fiscal-years/current", response_model=FiscalYearResponse)
async def get_current_fiscal_year(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current fiscal year for entity."""
    service = AccountingService(db)
    fiscal_year = await service.get_current_fiscal_year(entity_id)
    if not fiscal_year:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current fiscal year found. Please create a fiscal year first.",
        )
    return fiscal_year


@router.get("/fiscal-periods/for-date", response_model=FiscalPeriodResponse)
async def get_period_for_date(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    entry_date: date = Query(..., description="Date to find period for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get fiscal period for a specific date."""
    service = AccountingService(db)
    period = await service.get_fiscal_period_for_date(entity_id, entry_date)
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No fiscal period found for date {entry_date}",
        )
    return period


# ============================================================================
# JOURNAL ENTRY ENDPOINTS
# ============================================================================

@router.get("/journal-entries", response_model=JournalEntryListResponse)
async def list_journal_entries(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    status: Optional[JournalEntryStatus] = Query(None, description="Filter by status"),
    entry_type: Optional[JournalEntryType] = Query(None, description="Filter by type"),
    limit: int = Query(100, ge=1, le=500, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get journal entries with filtering and pagination."""
    service = AccountingService(db)
    entries, total = await service.get_journal_entries(
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        entry_type=entry_type,
        limit=limit,
        offset=offset,
    )
    return JournalEntryListResponse(
        items=entries,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    data: JournalEntryCreate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new journal entry."""
    service = AccountingService(db)
    try:
        entry = await service.create_journal_entry(
            entity_id=entity_id,
            data=data,
            user_id=current_user.id,
        )
        await db.commit()
        return entry
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    entry_id: uuid.UUID = Path(..., description="Journal Entry ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get journal entry by ID."""
    service = AccountingService(db)
    entry = await service.get_journal_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return entry


@router.post("/journal-entries/{entry_id}/post", response_model=JournalEntryResponse)
async def post_journal_entry(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    entry_id: uuid.UUID = Path(..., description="Journal Entry ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post a draft journal entry to the GL."""
    service = AccountingService(db)
    try:
        entry = await service.post_journal_entry(
            entry_id=entry_id,
            user_id=current_user.id,
        )
        await db.commit()
        return entry
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/journal-entries/{entry_id}/reverse", response_model=JournalEntryResponse)
async def reverse_journal_entry(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    entry_id: uuid.UUID = Path(..., description="Journal Entry ID"),
    reversal_date: date = Query(..., description="Date for reversal entry"),
    reason: str = Query(..., min_length=5, description="Reason for reversal"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reverse a posted journal entry."""
    service = AccountingService(db)
    try:
        entry = await service.reverse_journal_entry(
            entry_id=entry_id,
            reversal_date=reversal_date,
            reason=reason,
            user_id=current_user.id,
        )
        await db.commit()
        return entry
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# GL INTEGRATION ENDPOINT (FOR OTHER MODULES)
# ============================================================================

@router.post("/gl/post", response_model=GLPostingResponse)
async def post_to_general_ledger(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    request: GLPostingRequest = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Post a document from another module to the General Ledger.
    This is the main integration point for all financial modules.
    
    Used by:
    - Sales/Invoices module
    - Purchases/Vendors module
    - Receipts module
    - Payments module
    - Payroll module
    - Fixed Assets module
    - Inventory module
    - Bank Reconciliation module
    """
    service = AccountingService(db)
    response = await service.post_to_gl(
        entity_id=entity_id,
        request=request,
        user_id=current_user.id,
    )
    
    if response.success:
        await db.commit()
    else:
        await db.rollback()
    
    return response


# ============================================================================
# FINANCIAL REPORTS ENDPOINTS
# ============================================================================

@router.get("/reports/trial-balance", response_model=TrialBalanceReport)
async def get_trial_balance(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    as_of_date: date = Query(..., description="Report date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate Trial Balance report."""
    service = AccountingService(db)
    return await service.get_trial_balance(entity_id, as_of_date)


@router.get("/reports/income-statement", response_model=IncomeStatementReport)
async def get_income_statement(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    start_date: date = Query(..., description="Period start date"),
    end_date: date = Query(..., description="Period end date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate Income Statement (P&L) report."""
    service = AccountingService(db)
    return await service.get_income_statement(entity_id, start_date, end_date)


@router.get("/reports/balance-sheet", response_model=BalanceSheetReport)
async def get_balance_sheet(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    as_of_date: date = Query(..., description="Report date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate Balance Sheet report."""
    service = AccountingService(db)
    return await service.get_balance_sheet(entity_id, as_of_date)


# ============================================================================
# PERIOD CLOSE ENDPOINTS
# ============================================================================

@router.get("/periods/{period_id}/close-checklist", response_model=PeriodCloseChecklist)
async def get_period_close_checklist(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    period_id: uuid.UUID = Path(..., description="Fiscal Period ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get checklist for closing a fiscal period."""
    service = AccountingService(db)
    try:
        return await service.get_period_close_checklist(entity_id, period_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/periods/close", response_model=PeriodCloseResponse)
async def close_fiscal_period(
    entity_id: uuid.UUID = Path(..., description="Entity ID"),
    request: PeriodCloseRequest = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a fiscal period."""
    service = AccountingService(db)
    response = await service.close_period(
        entity_id=entity_id,
        request=request,
        user_id=current_user.id,
    )
    
    if response.success:
        await db.commit()
    else:
        await db.rollback()
    
    return response
