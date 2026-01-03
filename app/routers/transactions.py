"""
TekVwarho ProAudit - Transactions Router

API endpoints for transaction (expense/income) recording.
"""

from datetime import date
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

from app.database import get_async_session
from app.dependencies import get_current_active_user
from app.models.user import User
from app.models.transaction import TransactionType
from app.schemas.auth import MessageResponse
from app.services.transaction_service import TransactionService
from app.services.entity_service import EntityService


router = APIRouter()


class TransactionTypeEnum(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCreateRequest(BaseModel):
    """Schema for creating a transaction."""
    transaction_type: TransactionTypeEnum
    transaction_date: date
    amount: float = Field(..., gt=0)
    vat_amount: float = Field(0, ge=0)
    description: str = Field(..., min_length=1, max_length=500)
    reference: Optional[str] = Field(None, max_length=100)
    category_id: UUID
    vendor_id: Optional[UUID] = None
    receipt_url: Optional[str] = None


class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: UUID
    entity_id: UUID
    transaction_type: str
    transaction_date: date
    amount: float
    vat_amount: float
    total_amount: float
    description: str
    reference: Optional[str] = None
    category_id: Optional[UUID] = None
    category_name: Optional[str] = None
    vendor_id: Optional[UUID] = None
    vendor_name: Optional[str] = None
    wren_status: str
    vat_recoverable: bool
    receipt_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    """List of transactions response."""
    transactions: List[TransactionResponse]
    total: int
    total_amount: float
    total_vat: float


class TransactionSummaryResponse(BaseModel):
    """Transaction summary for a period."""
    period_start: date
    period_end: date
    total_income: float
    income_count: int
    income_vat_collected: float
    total_expenses: float
    expense_count: int
    expense_vat_paid: float
    net_amount: float
    vat_position: float
    wren_breakdown: dict


@router.get(
    "/{entity_id}/transactions",
    response_model=TransactionListResponse,
    summary="List transactions",
)
async def list_transactions(
    entity_id: UUID,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    transaction_type: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all transactions for an entity."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    transaction_service = TransactionService(db)
    transactions, total = await transaction_service.get_transactions_for_entity(
        entity_id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    
    totals = await transaction_service.get_totals(
        entity_id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
    )
    
    transaction_responses = [
        TransactionResponse(
            id=t.id,
            entity_id=t.entity_id,
            transaction_type=t.transaction_type.value,
            transaction_date=t.transaction_date,
            amount=float(t.amount),
            vat_amount=float(t.vat_amount),
            total_amount=float(t.total_amount),
            description=t.description,
            reference=t.reference,
            category_id=t.category_id,
            category_name=t.category.name if t.category else None,
            vendor_id=t.vendor_id,
            vendor_name=t.vendor.name if t.vendor else None,
            wren_status=t.wren_status.value,
            vat_recoverable=t.vat_recoverable,
            receipt_url=t.receipt_url,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in transactions
    ]
    
    return TransactionListResponse(
        transactions=transaction_responses,
        total=total,
        total_amount=totals["total_amount"],
        total_vat=totals["total_vat"],
    )


@router.post(
    "/{entity_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create transaction",
)
async def create_transaction(
    entity_id: UUID,
    request: TransactionCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new transaction."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    transaction_service = TransactionService(db)
    
    try:
        tx_type = TransactionType(request.transaction_type.value)
        
        transaction = await transaction_service.create_transaction(
            entity_id=entity_id,
            user_id=current_user.id,
            transaction_type=tx_type,
            transaction_date=request.transaction_date,
            amount=request.amount,
            vat_amount=request.vat_amount,
            description=request.description,
            reference=request.reference,
            category_id=request.category_id,
            vendor_id=request.vendor_id,
            receipt_url=request.receipt_url,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    transaction = await transaction_service.get_transaction_by_id(transaction.id, entity_id)
    
    return TransactionResponse(
        id=transaction.id,
        entity_id=transaction.entity_id,
        transaction_type=transaction.transaction_type.value,
        transaction_date=transaction.transaction_date,
        amount=float(transaction.amount),
        vat_amount=float(transaction.vat_amount),
        total_amount=float(transaction.total_amount),
        description=transaction.description,
        reference=transaction.reference,
        category_id=transaction.category_id,
        category_name=transaction.category.name if transaction.category else None,
        vendor_id=transaction.vendor_id,
        vendor_name=transaction.vendor.name if transaction.vendor else None,
        wren_status=transaction.wren_status.value,
        vat_recoverable=transaction.vat_recoverable,
        receipt_url=transaction.receipt_url,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


@router.get(
    "/{entity_id}/transactions/summary",
    response_model=TransactionSummaryResponse,
    summary="Get transaction summary",
)
async def get_transaction_summary(
    entity_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get transaction summary for a period."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    transaction_service = TransactionService(db)
    summary = await transaction_service.get_transaction_summary(
        entity_id,
        start_date,
        end_date,
    )
    
    return TransactionSummaryResponse(**summary)


@router.get(
    "/{entity_id}/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction",
)
async def get_transaction(
    entity_id: UUID,
    transaction_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific transaction."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    transaction_service = TransactionService(db)
    transaction = await transaction_service.get_transaction_by_id(transaction_id, entity_id)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    return TransactionResponse(
        id=transaction.id,
        entity_id=transaction.entity_id,
        transaction_type=transaction.transaction_type.value,
        transaction_date=transaction.transaction_date,
        amount=float(transaction.amount),
        vat_amount=float(transaction.vat_amount),
        total_amount=float(transaction.total_amount),
        description=transaction.description,
        reference=transaction.reference,
        category_id=transaction.category_id,
        category_name=transaction.category.name if transaction.category else None,
        vendor_id=transaction.vendor_id,
        vendor_name=transaction.vendor.name if transaction.vendor else None,
        wren_status=transaction.wren_status.value,
        vat_recoverable=transaction.vat_recoverable,
        receipt_url=transaction.receipt_url,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


@router.delete(
    "/{entity_id}/transactions/{transaction_id}",
    response_model=MessageResponse,
    summary="Delete transaction",
)
async def delete_transaction(
    entity_id: UUID,
    transaction_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a transaction."""
    entity_service = EntityService(db)
    entity = await entity_service.get_entity_by_id(entity_id, current_user)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found or access denied",
        )
    
    can_write = await entity_service.check_user_can_write(current_user, entity_id)
    if not can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access denied for this entity",
        )
    
    transaction_service = TransactionService(db)
    transaction = await transaction_service.get_transaction_by_id(transaction_id, entity_id)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    
    await transaction_service.delete_transaction(transaction)
    
    return MessageResponse(
        message="Transaction deleted successfully",
        success=True,
    )
