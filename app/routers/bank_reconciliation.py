"""
TekVwarho ProAudit - Bank Reconciliation Router

API endpoints for bank reconciliation operations.
Features:
- Bank account management
- Statement import
- Transaction matching (auto and manual)
- Reconciliation workflow
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_entity_id
from app.models.entity import BusinessEntity
from app.models.user import User
from app.models.bank_reconciliation import (
    BankAccountType, BankStatementSource, MatchStatus, ReconciliationStatus
)
from app.services.bank_reconciliation_service import (
    BankReconciliationService, get_bank_reconciliation_service
)

router = APIRouter(prefix="/bank-reconciliation", tags=["Bank Reconciliation"])


# ===========================================
# REQUEST/RESPONSE SCHEMAS
# ===========================================

class BankAccountCreate(BaseModel):
    """Schema for creating a bank account."""
    bank_name: str = Field(..., min_length=1, max_length=100)
    account_name: str = Field(..., min_length=1, max_length=200)
    account_number: str = Field(..., min_length=1, max_length=20)
    account_type: BankAccountType = BankAccountType.CURRENT
    currency: str = Field(default="NGN", max_length=3)
    opening_balance: float = Field(default=0.0)
    opening_balance_date: Optional[date] = None
    gl_account_code: Optional[str] = Field(None, max_length=20)
    bank_code: Optional[str] = Field(None, max_length=10)
    notes: Optional[str] = None


class BankAccountUpdate(BaseModel):
    """Schema for updating a bank account."""
    bank_name: Optional[str] = Field(None, max_length=100)
    account_name: Optional[str] = Field(None, max_length=200)
    account_type: Optional[BankAccountType] = None
    gl_account_code: Optional[str] = Field(None, max_length=20)
    bank_code: Optional[str] = Field(None, max_length=10)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class BankAccountResponse(BaseModel):
    """Response schema for bank account."""
    id: str
    bank_name: str
    account_name: str
    account_number: str
    account_type: str
    currency: str
    opening_balance: float
    current_balance: float
    last_reconciled_date: Optional[date]
    last_reconciled_balance: Optional[float]
    gl_account_code: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


class StatementTransactionInput(BaseModel):
    """Schema for a statement transaction."""
    transaction_date: date
    description: str
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    balance: float
    reference: Optional[str] = None
    value_date: Optional[date] = None


class StatementImportRequest(BaseModel):
    """Schema for importing a bank statement."""
    statement_date: date
    period_start: date
    period_end: date
    opening_balance: float
    closing_balance: float
    transactions: List[StatementTransactionInput]


class StatementTransactionResponse(BaseModel):
    """Response schema for statement transaction."""
    id: str
    transaction_date: date
    description: str
    debit_amount: float
    credit_amount: float
    balance: float
    reference: Optional[str]
    match_status: str
    matched_transaction_id: Optional[str]
    match_confidence: Optional[float]


class AutoMatchResponse(BaseModel):
    """Response for auto-matching results."""
    total_unmatched: int
    auto_matched: int
    remaining_unmatched: int
    matches: List[dict]


class MatchTransactionRequest(BaseModel):
    """Request for manual transaction matching."""
    statement_transaction_id: str
    book_transaction_id: str


class ReconciliationCreate(BaseModel):
    """Schema for creating a reconciliation."""
    reconciliation_date: date
    period_start: date
    period_end: date
    statement_opening_balance: float
    statement_closing_balance: float
    book_opening_balance: float
    book_closing_balance: float


class ReconciliationAdjustments(BaseModel):
    """Schema for reconciliation adjustments."""
    deposits_in_transit: Optional[float] = None
    outstanding_checks: Optional[float] = None
    bank_charges: Optional[float] = None
    interest_earned: Optional[float] = None
    other_adjustments: Optional[float] = None


class ReconciliationResponse(BaseModel):
    """Response schema for reconciliation."""
    id: str
    bank_account_id: str
    reconciliation_date: date
    period_start: date
    period_end: date
    statement_opening_balance: float
    statement_closing_balance: float
    book_opening_balance: float
    book_closing_balance: float
    deposits_in_transit: float
    outstanding_checks: float
    bank_charges: float
    interest_earned: float
    other_adjustments: float
    adjusted_bank_balance: float
    adjusted_book_balance: float
    difference: float
    status: str
    is_balanced: bool
    completed_at: Optional[datetime]
    approved_at: Optional[datetime]


# ===========================================
# BANK ACCOUNT ENDPOINTS
# ===========================================

@router.post(
    "/accounts",
    response_model=BankAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bank account",
)
async def create_bank_account(
    request: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """Create a new bank account for reconciliation."""
    service = get_bank_reconciliation_service(db)
    
    account = await service.create_bank_account(
        entity_id=entity_id,
        bank_name=request.bank_name,
        account_name=request.account_name,
        account_number=request.account_number,
        account_type=request.account_type,
        currency=request.currency,
        opening_balance=Decimal(str(request.opening_balance)),
        opening_balance_date=request.opening_balance_date,
        gl_account_code=request.gl_account_code,
        bank_code=request.bank_code,
        notes=request.notes,
        created_by_id=current_user.id,
    )
    
    return BankAccountResponse(
        id=str(account.id),
        bank_name=account.bank_name,
        account_name=account.account_name,
        account_number=account.account_number,
        account_type=account.account_type.value,
        currency=account.currency,
        opening_balance=float(account.opening_balance),
        current_balance=float(account.current_balance),
        last_reconciled_date=account.last_reconciled_date,
        last_reconciled_balance=float(account.last_reconciled_balance) if account.last_reconciled_balance else None,
        gl_account_code=account.gl_account_code,
        is_active=account.is_active,
    )


@router.get(
    "/accounts",
    response_model=List[BankAccountResponse],
    summary="List bank accounts",
)
async def list_bank_accounts(
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """List all bank accounts for the current entity."""
    service = get_bank_reconciliation_service(db)
    accounts = await service.get_bank_accounts(entity_id, is_active)
    
    return [
        BankAccountResponse(
            id=str(acc.id),
            bank_name=acc.bank_name,
            account_name=acc.account_name,
            account_number=acc.account_number,
            account_type=acc.account_type.value,
            currency=acc.currency,
            opening_balance=float(acc.opening_balance),
            current_balance=float(acc.current_balance),
            last_reconciled_date=acc.last_reconciled_date,
            last_reconciled_balance=float(acc.last_reconciled_balance) if acc.last_reconciled_balance else None,
            gl_account_code=acc.gl_account_code,
            is_active=acc.is_active,
        )
        for acc in accounts
    ]


@router.get(
    "/accounts/{account_id}",
    response_model=BankAccountResponse,
    summary="Get bank account details",
)
async def get_bank_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """Get a specific bank account by ID."""
    service = get_bank_reconciliation_service(db)
    account = await service.get_bank_account(account_id, entity_id)
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found",
        )
    
    return BankAccountResponse(
        id=str(account.id),
        bank_name=account.bank_name,
        account_name=account.account_name,
        account_number=account.account_number,
        account_type=account.account_type.value,
        currency=account.currency,
        opening_balance=float(account.opening_balance),
        current_balance=float(account.current_balance),
        last_reconciled_date=account.last_reconciled_date,
        last_reconciled_balance=float(account.last_reconciled_balance) if account.last_reconciled_balance else None,
        gl_account_code=account.gl_account_code,
        is_active=account.is_active,
    )


@router.patch(
    "/accounts/{account_id}",
    response_model=BankAccountResponse,
    summary="Update bank account",
)
async def update_bank_account(
    account_id: uuid.UUID,
    request: BankAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """Update a bank account."""
    service = get_bank_reconciliation_service(db)
    
    # Verify account belongs to entity
    existing = await service.get_bank_account(account_id, entity_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found",
        )
    
    updates = request.model_dump(exclude_unset=True)
    account = await service.update_bank_account(account_id, **updates)
    
    return BankAccountResponse(
        id=str(account.id),
        bank_name=account.bank_name,
        account_name=account.account_name,
        account_number=account.account_number,
        account_type=account.account_type.value,
        currency=account.currency,
        opening_balance=float(account.opening_balance),
        current_balance=float(account.current_balance),
        last_reconciled_date=account.last_reconciled_date,
        last_reconciled_balance=float(account.last_reconciled_balance) if account.last_reconciled_balance else None,
        gl_account_code=account.gl_account_code,
        is_active=account.is_active,
    )


# ===========================================
# STATEMENT IMPORT ENDPOINTS
# ===========================================

@router.post(
    "/accounts/{account_id}/statements",
    status_code=status.HTTP_201_CREATED,
    summary="Import bank statement",
)
async def import_statement(
    account_id: uuid.UUID,
    request: StatementImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """Import a bank statement with transactions."""
    service = get_bank_reconciliation_service(db)
    
    # Verify account belongs to entity
    account = await service.get_bank_account(account_id, entity_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found",
        )
    
    transactions = [t.model_dump() for t in request.transactions]
    
    statement = await service.import_statement(
        bank_account_id=account_id,
        statement_date=request.statement_date,
        period_start=request.period_start,
        period_end=request.period_end,
        opening_balance=Decimal(str(request.opening_balance)),
        closing_balance=Decimal(str(request.closing_balance)),
        transactions=transactions,
        source=BankStatementSource.MANUAL_ENTRY,
        imported_by_id=current_user.id,
    )
    
    return {
        "id": str(statement.id),
        "statement_date": statement.statement_date.isoformat(),
        "period_start": statement.period_start.isoformat(),
        "period_end": statement.period_end.isoformat(),
        "opening_balance": float(statement.opening_balance),
        "closing_balance": float(statement.closing_balance),
        "total_transactions": statement.total_transactions,
        "matched_transactions": statement.matched_transactions,
        "unmatched_transactions": statement.unmatched_transactions,
    }


@router.get(
    "/statements/{statement_id}/transactions",
    response_model=List[StatementTransactionResponse],
    summary="Get statement transactions",
)
async def get_statement_transactions(
    statement_id: uuid.UUID,
    match_status: Optional[MatchStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get transactions for a bank statement."""
    service = get_bank_reconciliation_service(db)
    transactions = await service.get_statement_transactions(statement_id, match_status)
    
    return [
        StatementTransactionResponse(
            id=str(txn.id),
            transaction_date=txn.transaction_date,
            description=txn.description,
            debit_amount=float(txn.debit_amount),
            credit_amount=float(txn.credit_amount),
            balance=float(txn.balance),
            reference=txn.reference,
            match_status=txn.match_status.value,
            matched_transaction_id=str(txn.matched_transaction_id) if txn.matched_transaction_id else None,
            match_confidence=float(txn.match_confidence) if txn.match_confidence else None,
        )
        for txn in transactions
    ]


# ===========================================
# MATCHING ENDPOINTS
# ===========================================

@router.post(
    "/statements/{statement_id}/auto-match",
    response_model=AutoMatchResponse,
    summary="Auto-match statement transactions",
)
async def auto_match_transactions(
    statement_id: uuid.UUID,
    min_confidence: float = Query(80.0, ge=0, le=100, description="Minimum match confidence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """
    Automatically match statement transactions with book transactions.
    
    Uses fuzzy matching on amount, date, and description.
    """
    service = get_bank_reconciliation_service(db)
    
    result = await service.auto_match_transactions(
        statement_id=statement_id,
        entity_id=entity_id,
        min_confidence=min_confidence,
    )
    
    return AutoMatchResponse(**result)


@router.post(
    "/match",
    summary="Manually match transactions",
)
async def match_transaction(
    request: MatchTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually match a statement transaction with a book transaction."""
    service = get_bank_reconciliation_service(db)
    
    try:
        stmt_txn = await service.match_transactions(
            statement_transaction_id=uuid.UUID(request.statement_transaction_id),
            book_transaction_id=uuid.UUID(request.book_transaction_id),
            matched_by_id=current_user.id,
        )
        return {
            "success": True,
            "message": "Transaction matched successfully",
            "match_status": stmt_txn.match_status.value,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/unmatch/{statement_transaction_id}",
    summary="Unmatch a transaction",
)
async def unmatch_transaction(
    statement_transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unmatch a previously matched transaction."""
    service = get_bank_reconciliation_service(db)
    
    try:
        await service.unmatch_transaction(statement_transaction_id)
        return {"success": True, "message": "Transaction unmatched"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ===========================================
# RECONCILIATION ENDPOINTS
# ===========================================

@router.post(
    "/accounts/{account_id}/reconciliations",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create reconciliation",
)
async def create_reconciliation(
    account_id: uuid.UUID,
    request: ReconciliationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """Create a new bank reconciliation."""
    service = get_bank_reconciliation_service(db)
    
    # Verify account belongs to entity
    account = await service.get_bank_account(account_id, entity_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found",
        )
    
    recon = await service.create_reconciliation(
        bank_account_id=account_id,
        reconciliation_date=request.reconciliation_date,
        period_start=request.period_start,
        period_end=request.period_end,
        statement_opening_balance=Decimal(str(request.statement_opening_balance)),
        statement_closing_balance=Decimal(str(request.statement_closing_balance)),
        book_opening_balance=Decimal(str(request.book_opening_balance)),
        book_closing_balance=Decimal(str(request.book_closing_balance)),
        created_by_id=current_user.id,
    )
    
    return ReconciliationResponse(
        id=str(recon.id),
        bank_account_id=str(recon.bank_account_id),
        reconciliation_date=recon.reconciliation_date,
        period_start=recon.period_start,
        period_end=recon.period_end,
        statement_opening_balance=float(recon.statement_opening_balance),
        statement_closing_balance=float(recon.statement_closing_balance),
        book_opening_balance=float(recon.book_opening_balance),
        book_closing_balance=float(recon.book_closing_balance),
        deposits_in_transit=float(recon.deposits_in_transit),
        outstanding_checks=float(recon.outstanding_checks),
        bank_charges=float(recon.bank_charges),
        interest_earned=float(recon.interest_earned),
        other_adjustments=float(recon.other_adjustments),
        adjusted_bank_balance=float(recon.adjusted_bank_balance),
        adjusted_book_balance=float(recon.adjusted_book_balance),
        difference=float(recon.difference),
        status=recon.status.value,
        is_balanced=recon.is_balanced,
        completed_at=recon.completed_at,
        approved_at=recon.approved_at,
    )


@router.patch(
    "/reconciliations/{reconciliation_id}/adjustments",
    response_model=ReconciliationResponse,
    summary="Update reconciliation adjustments",
)
async def update_reconciliation_adjustments(
    reconciliation_id: uuid.UUID,
    request: ReconciliationAdjustments,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update reconciliation adjustments and recalculate difference."""
    service = get_bank_reconciliation_service(db)
    
    try:
        adjustments = {}
        if request.deposits_in_transit is not None:
            adjustments["deposits_in_transit"] = Decimal(str(request.deposits_in_transit))
        if request.outstanding_checks is not None:
            adjustments["outstanding_checks"] = Decimal(str(request.outstanding_checks))
        if request.bank_charges is not None:
            adjustments["bank_charges"] = Decimal(str(request.bank_charges))
        if request.interest_earned is not None:
            adjustments["interest_earned"] = Decimal(str(request.interest_earned))
        if request.other_adjustments is not None:
            adjustments["other_adjustments"] = Decimal(str(request.other_adjustments))
        
        recon = await service.update_reconciliation_adjustments(
            reconciliation_id=reconciliation_id,
            **adjustments,
        )
        
        return ReconciliationResponse(
            id=str(recon.id),
            bank_account_id=str(recon.bank_account_id),
            reconciliation_date=recon.reconciliation_date,
            period_start=recon.period_start,
            period_end=recon.period_end,
            statement_opening_balance=float(recon.statement_opening_balance),
            statement_closing_balance=float(recon.statement_closing_balance),
            book_opening_balance=float(recon.book_opening_balance),
            book_closing_balance=float(recon.book_closing_balance),
            deposits_in_transit=float(recon.deposits_in_transit),
            outstanding_checks=float(recon.outstanding_checks),
            bank_charges=float(recon.bank_charges),
            interest_earned=float(recon.interest_earned),
            other_adjustments=float(recon.other_adjustments),
            adjusted_bank_balance=float(recon.adjusted_bank_balance),
            adjusted_book_balance=float(recon.adjusted_book_balance),
            difference=float(recon.difference),
            status=recon.status.value,
            is_balanced=recon.is_balanced,
            completed_at=recon.completed_at,
            approved_at=recon.approved_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/reconciliations/{reconciliation_id}/complete",
    response_model=ReconciliationResponse,
    summary="Complete reconciliation",
)
async def complete_reconciliation(
    reconciliation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a reconciliation as completed."""
    service = get_bank_reconciliation_service(db)
    
    try:
        recon = await service.complete_reconciliation(
            reconciliation_id=reconciliation_id,
            completed_by_id=current_user.id,
        )
        
        return ReconciliationResponse(
            id=str(recon.id),
            bank_account_id=str(recon.bank_account_id),
            reconciliation_date=recon.reconciliation_date,
            period_start=recon.period_start,
            period_end=recon.period_end,
            statement_opening_balance=float(recon.statement_opening_balance),
            statement_closing_balance=float(recon.statement_closing_balance),
            book_opening_balance=float(recon.book_opening_balance),
            book_closing_balance=float(recon.book_closing_balance),
            deposits_in_transit=float(recon.deposits_in_transit),
            outstanding_checks=float(recon.outstanding_checks),
            bank_charges=float(recon.bank_charges),
            interest_earned=float(recon.interest_earned),
            other_adjustments=float(recon.other_adjustments),
            adjusted_bank_balance=float(recon.adjusted_bank_balance),
            adjusted_book_balance=float(recon.adjusted_book_balance),
            difference=float(recon.difference),
            status=recon.status.value,
            is_balanced=recon.is_balanced,
            completed_at=recon.completed_at,
            approved_at=recon.approved_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/reconciliations/{reconciliation_id}/approve",
    response_model=ReconciliationResponse,
    summary="Approve reconciliation",
)
async def approve_reconciliation(
    reconciliation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a completed reconciliation."""
    service = get_bank_reconciliation_service(db)
    
    try:
        recon = await service.approve_reconciliation(
            reconciliation_id=reconciliation_id,
            approved_by_id=current_user.id,
        )
        
        return ReconciliationResponse(
            id=str(recon.id),
            bank_account_id=str(recon.bank_account_id),
            reconciliation_date=recon.reconciliation_date,
            period_start=recon.period_start,
            period_end=recon.period_end,
            statement_opening_balance=float(recon.statement_opening_balance),
            statement_closing_balance=float(recon.statement_closing_balance),
            book_opening_balance=float(recon.book_opening_balance),
            book_closing_balance=float(recon.book_closing_balance),
            deposits_in_transit=float(recon.deposits_in_transit),
            outstanding_checks=float(recon.outstanding_checks),
            bank_charges=float(recon.bank_charges),
            interest_earned=float(recon.interest_earned),
            other_adjustments=float(recon.other_adjustments),
            adjusted_bank_balance=float(recon.adjusted_bank_balance),
            adjusted_book_balance=float(recon.adjusted_book_balance),
            difference=float(recon.difference),
            status=recon.status.value,
            is_balanced=recon.is_balanced,
            completed_at=recon.completed_at,
            approved_at=recon.approved_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/accounts/{account_id}/reconciliations",
    response_model=List[ReconciliationResponse],
    summary="List reconciliations for account",
)
async def list_reconciliations(
    account_id: uuid.UUID,
    status_filter: Optional[ReconciliationStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """List all reconciliations for a bank account."""
    service = get_bank_reconciliation_service(db)
    
    # Verify account belongs to entity
    account = await service.get_bank_account(account_id, entity_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found",
        )
    
    reconciliations = await service.get_reconciliations(account_id, status_filter)
    
    return [
        ReconciliationResponse(
            id=str(r.id),
            bank_account_id=str(r.bank_account_id),
            reconciliation_date=r.reconciliation_date,
            period_start=r.period_start,
            period_end=r.period_end,
            statement_opening_balance=float(r.statement_opening_balance),
            statement_closing_balance=float(r.statement_closing_balance),
            book_opening_balance=float(r.book_opening_balance),
            book_closing_balance=float(r.book_closing_balance),
            deposits_in_transit=float(r.deposits_in_transit),
            outstanding_checks=float(r.outstanding_checks),
            bank_charges=float(r.bank_charges),
            interest_earned=float(r.interest_earned),
            other_adjustments=float(r.other_adjustments),
            adjusted_bank_balance=float(r.adjusted_bank_balance),
            adjusted_book_balance=float(r.adjusted_book_balance),
            difference=float(r.difference),
            status=r.status.value,
            is_balanced=r.is_balanced,
            completed_at=r.completed_at,
            approved_at=r.approved_at,
        )
        for r in reconciliations
    ]


@router.get(
    "/summary",
    summary="Get reconciliation summary",
)
async def get_reconciliation_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_id: uuid.UUID = Depends(get_current_entity_id),
):
    """Get reconciliation summary for all accounts in the entity."""
    service = get_bank_reconciliation_service(db)
    summary = await service.get_reconciliation_summary(entity_id)
    return summary
