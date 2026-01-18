"""
TekVwarho ProAudit - Transaction Service

Business logic for transaction (expense/income) recording.

GL Integration:
- When expenses are recorded, posts to GL: Dr Expense, Cr AP
- When income is recorded (if not via invoice), posts to GL: Dr AR/Bank, Cr Revenue
- Supports VAT Input tracking for expense recoveries
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


# Nigerian Standard COA Account Codes
GL_ACCOUNTS = {
    "accounts_receivable": "1130",
    "accounts_payable": "2110",
    "bank": "1120",
    "vat_output": "2130",  # VAT Payable (Output)
    "vat_input": "1180",   # VAT Receivable (Input)
    "wht_receivable": "1170",
    "wht_payable": "2140",
    "revenue": "4100",
    # Expense accounts mapped by category - use 5xxx range
    "default_expense": "5100",
}


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
        wht_amount: float = 0,
        reference: Optional[str] = None,
        vendor_id: Optional[uuid.UUID] = None,
        receipt_url: Optional[str] = None,
        notes: Optional[str] = None,
        post_to_gl: bool = True,
        gl_expense_account: Optional[str] = None,
        **kwargs,
    ) -> Transaction:
        """
        Create a new transaction with GL posting.
        
        For Expenses (Vendor Bills):
        - Dr Expense Account (from category or default)
        - Dr VAT Input (if VAT recoverable)
        - Cr Accounts Payable
        
        For Income (not via invoice):
        - Dr Accounts Receivable / Bank
        - Cr Revenue
        - Cr VAT Output (if applicable)
        
        Args:
            entity_id: Business entity ID
            user_id: User creating the transaction
            transaction_type: INCOME or EXPENSE
            transaction_date: Date of transaction
            amount: Base amount (before VAT)
            description: Transaction description
            category_id: Category ID for expense mapping
            vat_amount: VAT amount
            wht_amount: WHT amount (for expenses with WHT deducted)
            reference: External reference number
            vendor_id: Vendor ID (for expenses)
            receipt_url: Receipt/invoice URL
            notes: Additional notes
            post_to_gl: Whether to post to GL (default True)
            gl_expense_account: Override GL account for expense
        """
        total_amount = Decimal(str(amount)) + Decimal(str(vat_amount))
        
        # Get WREN status from category
        wren_status = WRENStatus.REVIEW_REQUIRED
        expense_gl_account = gl_expense_account or GL_ACCOUNTS["default_expense"]
        
        category_result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = category_result.scalar_one_or_none()
        if category:
            if category.wren_default:
                wren_status = WRENStatus.COMPLIANT
            elif category.wren_review_required:
                wren_status = WRENStatus.REVIEW_REQUIRED
            # Use category GL account if available
            if hasattr(category, 'gl_account_code') and category.gl_account_code:
                expense_gl_account = category.gl_account_code
        
        transaction = Transaction(
            entity_id=entity_id,
            transaction_type=transaction_type,
            transaction_date=transaction_date,
            amount=amount,
            vat_amount=vat_amount,
            wht_amount=wht_amount,
            total_amount=float(total_amount),
            description=description,
            reference=reference,
            category_id=category_id,
            vendor_id=vendor_id,
            wren_status=wren_status,
            vat_recoverable=vat_amount > 0 and transaction_type == TransactionType.EXPENSE,
            receipt_url=receipt_url,
            created_by_id=user_id,
        )
        
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)
        
        # Post to GL if enabled
        if post_to_gl:
            try:
                if transaction_type == TransactionType.EXPENSE:
                    await self._post_expense_to_gl(
                        entity_id=entity_id,
                        transaction=transaction,
                        expense_gl_account=expense_gl_account,
                        user_id=user_id,
                    )
                else:
                    # Income recording - only if not recorded via invoice
                    await self._post_income_to_gl(
                        entity_id=entity_id,
                        transaction=transaction,
                        user_id=user_id,
                    )
            except Exception as e:
                # Log error but don't fail transaction creation
                import logging
                logging.error(f"GL posting failed for transaction {transaction.id}: {e}")
        
        return transaction
    
    async def _get_gl_account_id(
        self,
        entity_id: uuid.UUID,
        account_code: str,
    ) -> Optional[uuid.UUID]:
        """Get GL account ID by account code."""
        from app.models.accounting import ChartOfAccounts
        
        result = await self.db.execute(
            select(ChartOfAccounts.id)
            .where(ChartOfAccounts.entity_id == entity_id)
            .where(ChartOfAccounts.account_code == account_code)
            .where(ChartOfAccounts.is_active == True)
        )
        account = result.scalar_one_or_none()
        return account
    
    async def _post_expense_to_gl(
        self,
        entity_id: uuid.UUID,
        transaction: Transaction,
        expense_gl_account: str,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Post expense transaction to General Ledger.
        
        Journal Entry:
        Dr Expense Account       [amount]
        Dr VAT Input (1180)      [vat_amount] - if recoverable
        Cr Accounts Payable      [total - wht]
        Cr WHT Payable (2140)    [wht_amount] - if applicable
        """
        from app.services.accounting_service import AccountingService
        from app.schemas.accounting import GLPostingRequest, JournalEntryLineCreate
        
        accounting_service = AccountingService(self.db)
        
        # Build journal lines
        lines = []
        
        # Debit: Expense Account
        expense_account_id = await self._get_gl_account_id(entity_id, expense_gl_account)
        if expense_account_id:
            lines.append(JournalEntryLineCreate(
                account_id=expense_account_id,
                debit_amount=Decimal(str(transaction.amount)),
                credit_amount=Decimal("0"),
                description=f"Expense: {transaction.description}",
            ))
        
        # Debit: VAT Input (if recoverable)
        if transaction.vat_recoverable and transaction.vat_amount > 0:
            vat_input_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["vat_input"])
            if vat_input_id:
                lines.append(JournalEntryLineCreate(
                    account_id=vat_input_id,
                    debit_amount=Decimal(str(transaction.vat_amount)),
                    credit_amount=Decimal("0"),
                    description=f"VAT Input recoverable: {transaction.description}",
                ))
        
        # Credit: Accounts Payable (total less WHT)
        payable_amount = Decimal(str(transaction.total_amount)) - Decimal(str(transaction.wht_amount or 0))
        ap_account_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["accounts_payable"])
        if ap_account_id and payable_amount > 0:
            lines.append(JournalEntryLineCreate(
                account_id=ap_account_id,
                debit_amount=Decimal("0"),
                credit_amount=payable_amount,
                description=f"Payable to vendor: {transaction.description}",
            ))
        
        # Credit: WHT Payable (if WHT deducted from payment)
        if transaction.wht_amount and transaction.wht_amount > 0:
            wht_payable_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["wht_payable"])
            if wht_payable_id:
                lines.append(JournalEntryLineCreate(
                    account_id=wht_payable_id,
                    debit_amount=Decimal("0"),
                    credit_amount=Decimal(str(transaction.wht_amount)),
                    description=f"WHT withheld: {transaction.description}",
                ))
        
        if not lines:
            return {"success": False, "error": "No GL accounts found for posting"}
        
        # Create GL posting request
        gl_request = GLPostingRequest(
            entry_date=transaction.transaction_date,
            reference=transaction.reference or f"EXP-{str(transaction.id)[:8]}",
            description=f"Expense: {transaction.description}",
            source_document_type="expense",
            source_document_id=str(transaction.id),
            lines=lines,
        )
        
        # Post to GL
        result = await accounting_service.post_to_gl(entity_id, gl_request, user_id)
        
        return {
            "success": result.success,
            "journal_entry_id": str(result.journal_entry_id) if result.journal_entry_id else None,
            "message": result.message,
        }
    
    async def _post_income_to_gl(
        self,
        entity_id: uuid.UUID,
        transaction: Transaction,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """
        Post income transaction to General Ledger.
        
        Note: This is for income not recorded via invoices (e.g., miscellaneous income).
        Invoice-based income should use InvoiceService which handles GL posting.
        
        Journal Entry:
        Dr Accounts Receivable   [total_amount]
        Cr Revenue               [amount]
        Cr VAT Output (2130)     [vat_amount] - if applicable
        """
        from app.services.accounting_service import AccountingService
        from app.schemas.accounting import GLPostingRequest, JournalEntryLineCreate
        
        accounting_service = AccountingService(self.db)
        
        # Build journal lines
        lines = []
        
        # Debit: Accounts Receivable
        ar_account_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["accounts_receivable"])
        if ar_account_id:
            lines.append(JournalEntryLineCreate(
                account_id=ar_account_id,
                debit_amount=Decimal(str(transaction.total_amount)),
                credit_amount=Decimal("0"),
                description=f"Income receivable: {transaction.description}",
            ))
        
        # Credit: Revenue
        revenue_account_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["revenue"])
        if revenue_account_id:
            lines.append(JournalEntryLineCreate(
                account_id=revenue_account_id,
                debit_amount=Decimal("0"),
                credit_amount=Decimal(str(transaction.amount)),
                description=f"Revenue: {transaction.description}",
            ))
        
        # Credit: VAT Output (if applicable)
        if transaction.vat_amount and transaction.vat_amount > 0:
            vat_output_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["vat_output"])
            if vat_output_id:
                lines.append(JournalEntryLineCreate(
                    account_id=vat_output_id,
                    debit_amount=Decimal("0"),
                    credit_amount=Decimal(str(transaction.vat_amount)),
                    description=f"VAT Output: {transaction.description}",
                ))
        
        if not lines:
            return {"success": False, "error": "No GL accounts found for posting"}
        
        # Create GL posting request
        gl_request = GLPostingRequest(
            entry_date=transaction.transaction_date,
            reference=transaction.reference or f"INC-{str(transaction.id)[:8]}",
            description=f"Income: {transaction.description}",
            source_document_type="income",
            source_document_id=str(transaction.id),
            lines=lines,
        )
        
        # Post to GL
        result = await accounting_service.post_to_gl(entity_id, gl_request, user_id)
        
        return {
            "success": result.success,
            "journal_entry_id": str(result.journal_entry_id) if result.journal_entry_id else None,
            "message": result.message,
        }
    
    async def record_vendor_payment(
        self,
        entity_id: uuid.UUID,
        vendor_id: uuid.UUID,
        payment_amount: Decimal,
        payment_date: date,
        bank_account_id: uuid.UUID,
        reference: str,
        user_id: uuid.UUID,
        wht_amount: Optional[Decimal] = None,
        post_to_gl: bool = True,
    ) -> Dict[str, Any]:
        """
        Record payment to vendor and post to GL.
        
        Journal Entry:
        Dr Accounts Payable (2110)   [payment_amount + wht_amount]
        Cr Bank (1120)               [payment_amount]
        Cr WHT Payable (2140)        [wht_amount] - if applicable
        
        Args:
            entity_id: Business entity ID
            vendor_id: Vendor being paid
            payment_amount: Amount paid (bank transfer amount)
            payment_date: Date of payment
            bank_account_id: Bank account GL ID
            reference: Payment reference
            user_id: User recording payment
            wht_amount: WHT deducted from payment
            post_to_gl: Whether to post to GL
        """
        from app.services.accounting_service import AccountingService
        from app.schemas.accounting import GLPostingRequest, JournalEntryLineCreate
        
        total_ap_reduction = payment_amount + (wht_amount or Decimal("0"))
        
        if not post_to_gl:
            return {"success": True, "message": "GL posting skipped"}
        
        accounting_service = AccountingService(self.db)
        
        # Build journal lines
        lines = []
        
        # Debit: Accounts Payable
        ap_account_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["accounts_payable"])
        if ap_account_id:
            lines.append(JournalEntryLineCreate(
                account_id=ap_account_id,
                debit_amount=total_ap_reduction,
                credit_amount=Decimal("0"),
                description=f"Payment to vendor: {reference}",
            ))
        
        # Credit: Bank
        if bank_account_id:
            lines.append(JournalEntryLineCreate(
                account_id=bank_account_id,
                debit_amount=Decimal("0"),
                credit_amount=payment_amount,
                description=f"Bank payment: {reference}",
            ))
        
        # Credit: WHT Payable (if WHT deducted)
        if wht_amount and wht_amount > 0:
            wht_payable_id = await self._get_gl_account_id(entity_id, GL_ACCOUNTS["wht_payable"])
            if wht_payable_id:
                lines.append(JournalEntryLineCreate(
                    account_id=wht_payable_id,
                    debit_amount=Decimal("0"),
                    credit_amount=wht_amount,
                    description=f"WHT on vendor payment: {reference}",
                ))
        
        if not lines:
            return {"success": False, "error": "No GL accounts found for posting"}
        
        # Create GL posting request
        gl_request = GLPostingRequest(
            entry_date=payment_date,
            reference=reference,
            description=f"Vendor payment: {reference}",
            source_document_type="vendor_payment",
            source_document_id=reference,
            lines=lines,
        )
        
        # Post to GL
        result = await accounting_service.post_to_gl(entity_id, gl_request, user_id)
        
        return {
            "success": result.success,
            "journal_entry_id": str(result.journal_entry_id) if result.journal_entry_id else None,
            "message": result.message,
        }
    
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
