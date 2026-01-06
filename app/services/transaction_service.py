"""
TekVwarho ProAudit - Transaction Service

Business logic for transaction (expense/income) recording.
"""

import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transaction import Transaction, TransactionType, WRENStatus
from app.models.category import Category
from app.models.vendor import Vendor


class TransactionService:
    """Service for transaction operations."""
    
    # Nigeria VAT rate (7.5% per 2026 Tax Reform)
    VAT_RATE = Decimal("0.075")
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def calculate_vat(self, amount: Decimal) -> Decimal:
        """
        Calculate VAT on an amount at 7.5% rate.
        
        Args:
            amount: Base amount to calculate VAT on
            
        Returns:
            VAT amount rounded to 2 decimal places
        """
        vat = amount * self.VAT_RATE
        return vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    async def get_transactions_for_entity(
        self,
        entity_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[str] = None,
        category_id: Optional[uuid.UUID] = None,
        vendor_id: Optional[uuid.UUID] = None,
        customer_id: Optional[uuid.UUID] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        is_paid: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Transaction], int]:
        """Get transactions for an entity with filters."""
        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.category),
                selectinload(Transaction.vendor),
            )
            .where(Transaction.entity_id == entity_id)
        )
        
        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)
        if transaction_type:
            tx_type = TransactionType(transaction_type)
            query = query.where(Transaction.transaction_type == tx_type)
        if category_id:
            query = query.where(Transaction.category_id == category_id)
        if vendor_id:
            query = query.where(Transaction.vendor_id == vendor_id)
        if min_amount is not None:
            query = query.where(Transaction.total_amount >= min_amount)
        if max_amount is not None:
            query = query.where(Transaction.total_amount <= max_amount)
        
        # Count query
        count_query = (
            select(func.count(Transaction.id))
            .where(Transaction.entity_id == entity_id)
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        query = query.order_by(Transaction.transaction_date.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        transactions = list(result.scalars().all())
        
        return transactions, total
    
    async def get_transaction_by_id(
        self,
        transaction_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> Optional[Transaction]:
        """Get transaction by ID."""
        result = await self.db.execute(
            select(Transaction)
            .options(
                selectinload(Transaction.category),
                selectinload(Transaction.vendor),
            )
            .where(Transaction.id == transaction_id)
            .where(Transaction.entity_id == entity_id)
        )
        return result.scalar_one_or_none()
    
    async def create_transaction(
        self,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        transaction_type: TransactionType,
        transaction_date: date,
        amount: float,
        description: str,
        category_id: uuid.UUID,
        vat_amount: float = 0,
        reference: Optional[str] = None,
        vendor_id: Optional[uuid.UUID] = None,
        receipt_url: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs,
    ) -> Transaction:
        """Create a new transaction."""
        total_amount = amount + vat_amount
        
        # Get WREN status from category
        wren_status = WRENStatus.REVIEW_REQUIRED
        category_result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = category_result.scalar_one_or_none()
        if category:
            if category.wren_default:
                wren_status = WRENStatus.COMPLIANT
            elif category.wren_review_required:
                wren_status = WRENStatus.REVIEW_REQUIRED
        
        transaction = Transaction(
            entity_id=entity_id,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            amount=amount,
            vat_amount=vat_amount,
            total_amount=total_amount,
            description=description,
            reference=reference,
            category_id=category_id,
            vendor_id=vendor_id,
            wren_status=wren_status,
            vat_recoverable=vat_amount > 0,
            receipt_url=receipt_url,
        )
        
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)
        
        return transaction
    
    async def update_transaction(
        self,
        transaction: Transaction,
        **kwargs,
    ) -> Transaction:
        """Update a transaction."""
        for key, value in kwargs.items():
            if value is not None and hasattr(transaction, key):
                setattr(transaction, key, value)
        
        # Recalculate total
        transaction.total_amount = transaction.amount + transaction.vat_amount
        
        await self.db.commit()
        await self.db.refresh(transaction)
        
        return transaction
    
    async def delete_transaction(self, transaction: Transaction) -> bool:
        """Delete a transaction."""
        await self.db.delete(transaction)
        await self.db.commit()
        return True
    
    async def get_transaction_summary(
        self,
        entity_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Get transaction summary for a period."""
        # Income summary
        income_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                func.coalesce(func.sum(Transaction.vat_amount), 0).label("vat"),
            )
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.INCOME)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
        )
        income = income_result.one()
        
        # Expense summary
        expense_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
                func.coalesce(func.sum(Transaction.vat_amount), 0).label("vat"),
            )
            .where(Transaction.entity_id == entity_id)
            .where(Transaction.transaction_type == TransactionType.EXPENSE)
            .where(Transaction.transaction_date >= start_date)
            .where(Transaction.transaction_date <= end_date)
        )
        expense = expense_result.one()
        
        return {
            "period_start": start_date,
            "period_end": end_date,
            "total_income": float(income.total),
            "income_count": income.count,
            "income_vat_collected": float(income.vat),
            "total_expenses": float(expense.total),
            "expense_count": expense.count,
            "expense_vat_paid": float(expense.vat),
            "net_amount": float(income.total) - float(expense.total),
            "vat_position": float(income.vat) - float(expense.vat),
            "wren_breakdown": {},
        }
    
    async def get_totals(
        self,
        entity_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[str] = None,
    ) -> Dict[str, float]:
        """Get transaction totals."""
        query = (
            select(
                func.coalesce(func.sum(Transaction.total_amount), 0).label("total"),
                func.coalesce(func.sum(Transaction.vat_amount), 0).label("vat"),
            )
            .where(Transaction.entity_id == entity_id)
        )
        
        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)
        if transaction_type:
            tx_type = TransactionType(transaction_type)
            query = query.where(Transaction.transaction_type == tx_type)
        
        result = await self.db.execute(query)
        row = result.one()
        
        return {
            "total_amount": float(row.total),
            "total_vat": float(row.vat),
            "total_wht": 0.0,
        }
    
    async def verify_wren_status(
        self,
        transaction: Transaction,
        verifier_id: uuid.UUID,
        wren_status: WRENStatus,
        notes: Optional[str] = None,
    ) -> Transaction:
        """
        Verify WREN status of a transaction (Maker-Checker SoD).
        
        NTAA 2025 Compliance:
        - Records who verified (Checker) and when
        - The service should be called after checking that Checker != Maker
        
        Args:
            transaction: The transaction to verify
            verifier_id: ID of the user verifying (Checker)
            wren_status: The WREN status to set
            notes: Optional notes for verification
            
        Returns:
            Updated transaction
        """
        from datetime import datetime, timezone
        
        transaction.wren_status = wren_status
        transaction.wren_verified_by_id = verifier_id
        transaction.wren_verified_at = datetime.now(timezone.utc)
        
        if notes:
            transaction.wren_notes = notes
        
        await self.db.commit()
        await self.db.refresh(transaction)
        
        return transaction
