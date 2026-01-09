"""
TekVwarho ProAudit - Bank Reconciliation Service

Service for managing bank reconciliation operations.
Features:
- Bank account CRUD
- Statement import and parsing
- Auto-matching using fuzzy logic
- Manual matching
- Reconciliation statement generation
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from difflib import SequenceMatcher

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bank_reconciliation import (
    BankAccount, BankAccountType, BankStatement, BankStatementSource,
    BankStatementTransaction, BankReconciliation,
    MatchStatus, ReconciliationStatus,
)
from app.models.transaction import Transaction


class BankReconciliationService:
    """Service for bank reconciliation operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ===========================================
    # BANK ACCOUNT OPERATIONS
    # ===========================================
    
    async def create_bank_account(
        self,
        entity_id: uuid.UUID,
        bank_name: str,
        account_name: str,
        account_number: str,
        account_type: BankAccountType = BankAccountType.CURRENT,
        currency: str = "NGN",
        opening_balance: Decimal = Decimal("0.00"),
        opening_balance_date: Optional[date] = None,
        gl_account_code: Optional[str] = None,
        bank_code: Optional[str] = None,
        notes: Optional[str] = None,
        created_by_id: Optional[uuid.UUID] = None,
    ) -> BankAccount:
        """Create a new bank account for reconciliation."""
        account = BankAccount(
            entity_id=entity_id,
            bank_name=bank_name,
            account_name=account_name,
            account_number=account_number,
            account_type=account_type,
            currency=currency,
            opening_balance=opening_balance,
            opening_balance_date=opening_balance_date or date.today(),
            current_balance=opening_balance,
            gl_account_code=gl_account_code,
            bank_code=bank_code,
            notes=notes,
            created_by_id=created_by_id,
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        return account
    
    async def get_bank_accounts(
        self,
        entity_id: uuid.UUID,
        is_active: Optional[bool] = True,
    ) -> List[BankAccount]:
        """Get all bank accounts for an entity."""
        query = select(BankAccount).where(BankAccount.entity_id == entity_id)
        if is_active is not None:
            query = query.where(BankAccount.is_active == is_active)
        query = query.order_by(BankAccount.bank_name, BankAccount.account_name)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_bank_account(
        self,
        account_id: uuid.UUID,
        entity_id: Optional[uuid.UUID] = None,
    ) -> Optional[BankAccount]:
        """Get a specific bank account by ID."""
        query = select(BankAccount).where(BankAccount.id == account_id)
        if entity_id:
            query = query.where(BankAccount.entity_id == entity_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_bank_account(
        self,
        account_id: uuid.UUID,
        **updates,
    ) -> Optional[BankAccount]:
        """Update a bank account."""
        account = await self.get_bank_account(account_id)
        if not account:
            return None
        
        for key, value in updates.items():
            if hasattr(account, key):
                setattr(account, key, value)
        
        await self.db.commit()
        await self.db.refresh(account)
        return account
    
    # ===========================================
    # STATEMENT IMPORT
    # ===========================================
    
    async def import_statement(
        self,
        bank_account_id: uuid.UUID,
        statement_date: date,
        period_start: date,
        period_end: date,
        opening_balance: Decimal,
        closing_balance: Decimal,
        transactions: List[Dict[str, Any]],
        source: BankStatementSource = BankStatementSource.MANUAL_UPLOAD,
        file_name: Optional[str] = None,
        imported_by_id: Optional[uuid.UUID] = None,
    ) -> BankStatement:
        """
        Import a bank statement with transactions.
        
        Args:
            transactions: List of dicts with keys:
                - transaction_date: date
                - description: str
                - debit_amount: Decimal (optional, default 0)
                - credit_amount: Decimal (optional, default 0)
                - balance: Decimal
                - reference: str (optional)
                - value_date: date (optional)
        """
        # Create statement
        statement = BankStatement(
            bank_account_id=bank_account_id,
            statement_date=statement_date,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            source=source,
            file_name=file_name,
            imported_by_id=imported_by_id,
            total_transactions=len(transactions),
            unmatched_transactions=len(transactions),
        )
        self.db.add(statement)
        await self.db.flush()
        
        # Create transactions
        for txn_data in transactions:
            txn = BankStatementTransaction(
                statement_id=statement.id,
                transaction_date=txn_data["transaction_date"],
                value_date=txn_data.get("value_date"),
                description=txn_data["description"],
                reference=txn_data.get("reference"),
                debit_amount=Decimal(str(txn_data.get("debit_amount", 0))),
                credit_amount=Decimal(str(txn_data.get("credit_amount", 0))),
                balance=Decimal(str(txn_data["balance"])),
                match_status=MatchStatus.UNMATCHED,
            )
            self.db.add(txn)
        
        await self.db.commit()
        await self.db.refresh(statement)
        return statement
    
    async def get_statement_transactions(
        self,
        statement_id: uuid.UUID,
        match_status: Optional[MatchStatus] = None,
    ) -> List[BankStatementTransaction]:
        """Get transactions for a statement."""
        query = select(BankStatementTransaction).where(
            BankStatementTransaction.statement_id == statement_id
        )
        if match_status:
            query = query.where(BankStatementTransaction.match_status == match_status)
        query = query.order_by(BankStatementTransaction.transaction_date)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    # ===========================================
    # AUTO-MATCHING
    # ===========================================
    
    async def auto_match_transactions(
        self,
        statement_id: uuid.UUID,
        entity_id: uuid.UUID,
        min_confidence: float = 80.0,
    ) -> Dict[str, Any]:
        """
        Automatically match statement transactions with book transactions.
        
        Uses fuzzy matching on:
        - Amount (exact match required)
        - Date (within 3 days)
        - Description (fuzzy similarity)
        
        Returns:
            Dict with match statistics
        """
        # Get unmatched statement transactions
        stmt_txns = await self.get_statement_transactions(
            statement_id, 
            match_status=MatchStatus.UNMATCHED
        )
        
        matches = []
        for stmt_txn in stmt_txns:
            # Find potential matches in book
            amount = stmt_txn.amount
            potential_matches = await self._find_potential_matches(
                entity_id=entity_id,
                amount=amount,
                transaction_date=stmt_txn.transaction_date,
                days_tolerance=3,
            )
            
            if potential_matches:
                # Score and rank matches
                scored_matches = []
                for book_txn in potential_matches:
                    score = self._calculate_match_score(stmt_txn, book_txn)
                    if score >= min_confidence:
                        scored_matches.append((book_txn, score))
                
                if scored_matches:
                    # Take best match
                    scored_matches.sort(key=lambda x: x[1], reverse=True)
                    best_match, confidence = scored_matches[0]
                    
                    # Mark as auto-matched
                    stmt_txn.match_status = MatchStatus.AUTO_MATCHED
                    stmt_txn.matched_transaction_id = best_match.id
                    stmt_txn.match_confidence = Decimal(str(confidence))
                    stmt_txn.matched_at = datetime.utcnow()
                    
                    matches.append({
                        "statement_transaction_id": str(stmt_txn.id),
                        "book_transaction_id": str(best_match.id),
                        "confidence": confidence,
                    })
        
        await self.db.commit()
        
        # Update statement match counts
        await self._update_statement_match_counts(statement_id)
        
        return {
            "total_unmatched": len(stmt_txns),
            "auto_matched": len(matches),
            "remaining_unmatched": len(stmt_txns) - len(matches),
            "matches": matches,
        }
    
    async def _find_potential_matches(
        self,
        entity_id: uuid.UUID,
        amount: Decimal,
        transaction_date: date,
        days_tolerance: int = 3,
    ) -> List[Transaction]:
        """Find potential matching transactions from the book."""
        from datetime import timedelta
        
        date_start = transaction_date - timedelta(days=days_tolerance)
        date_end = transaction_date + timedelta(days=days_tolerance)
        
        # Match on amount (debits are negative, credits are positive)
        query = select(Transaction).where(
            and_(
                Transaction.entity_id == entity_id,
                Transaction.transaction_date >= date_start,
                Transaction.transaction_date <= date_end,
                or_(
                    Transaction.amount == abs(amount),
                    Transaction.amount == -abs(amount),
                ),
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    def _calculate_match_score(
        self,
        stmt_txn: BankStatementTransaction,
        book_txn: Transaction,
    ) -> float:
        """
        Calculate match score between statement and book transaction.
        
        Scoring:
        - Amount match: 40 points
        - Date match: 30 points (decreasing with distance)
        - Description similarity: 30 points
        """
        score = 0.0
        
        # Amount match (exact = 40 points)
        stmt_amount = abs(stmt_txn.amount)
        book_amount = abs(book_txn.amount)
        if stmt_amount == book_amount:
            score += 40.0
        
        # Date match (same day = 30, decreasing by 10 per day difference)
        date_diff = abs((stmt_txn.transaction_date - book_txn.transaction_date).days)
        date_score = max(0, 30 - (date_diff * 10))
        score += date_score
        
        # Description similarity (fuzzy match)
        stmt_desc = stmt_txn.description.lower()
        book_desc = (book_txn.description or "").lower()
        if stmt_desc and book_desc:
            similarity = SequenceMatcher(None, stmt_desc, book_desc).ratio()
            score += similarity * 30
        
        return score
    
    # ===========================================
    # MANUAL MATCHING
    # ===========================================
    
    async def match_transactions(
        self,
        statement_transaction_id: uuid.UUID,
        book_transaction_id: uuid.UUID,
        matched_by_id: uuid.UUID,
    ) -> BankStatementTransaction:
        """Manually match a statement transaction with a book transaction."""
        result = await self.db.execute(
            select(BankStatementTransaction).where(
                BankStatementTransaction.id == statement_transaction_id
            )
        )
        stmt_txn = result.scalar_one_or_none()
        if not stmt_txn:
            raise ValueError("Statement transaction not found")
        
        stmt_txn.match_status = MatchStatus.MANUAL_MATCHED
        stmt_txn.matched_transaction_id = book_transaction_id
        stmt_txn.match_confidence = Decimal("100.00")
        stmt_txn.matched_at = datetime.utcnow()
        stmt_txn.matched_by_id = matched_by_id
        
        await self.db.commit()
        await self.db.refresh(stmt_txn)
        
        # Update statement match counts
        await self._update_statement_match_counts(stmt_txn.statement_id)
        
        return stmt_txn
    
    async def unmatch_transaction(
        self,
        statement_transaction_id: uuid.UUID,
    ) -> BankStatementTransaction:
        """Unmatch a previously matched transaction."""
        result = await self.db.execute(
            select(BankStatementTransaction).where(
                BankStatementTransaction.id == statement_transaction_id
            )
        )
        stmt_txn = result.scalar_one_or_none()
        if not stmt_txn:
            raise ValueError("Statement transaction not found")
        
        stmt_txn.match_status = MatchStatus.UNMATCHED
        stmt_txn.matched_transaction_id = None
        stmt_txn.match_confidence = None
        stmt_txn.matched_at = None
        stmt_txn.matched_by_id = None
        
        await self.db.commit()
        await self.db.refresh(stmt_txn)
        
        # Update statement match counts
        await self._update_statement_match_counts(stmt_txn.statement_id)
        
        return stmt_txn
    
    async def _update_statement_match_counts(self, statement_id: uuid.UUID):
        """Update match counts on a statement."""
        result = await self.db.execute(
            select(BankStatement).where(BankStatement.id == statement_id)
        )
        statement = result.scalar_one_or_none()
        if not statement:
            return
        
        # Count matched vs unmatched
        matched_result = await self.db.execute(
            select(func.count(BankStatementTransaction.id)).where(
                and_(
                    BankStatementTransaction.statement_id == statement_id,
                    BankStatementTransaction.match_status.in_([
                        MatchStatus.AUTO_MATCHED,
                        MatchStatus.MANUAL_MATCHED,
                        MatchStatus.RECONCILED,
                    ])
                )
            )
        )
        matched_count = matched_result.scalar() or 0
        
        statement.matched_transactions = matched_count
        statement.unmatched_transactions = statement.total_transactions - matched_count
        
        await self.db.commit()
    
    # ===========================================
    # RECONCILIATION
    # ===========================================
    
    async def create_reconciliation(
        self,
        bank_account_id: uuid.UUID,
        reconciliation_date: date,
        period_start: date,
        period_end: date,
        statement_opening_balance: Decimal,
        statement_closing_balance: Decimal,
        book_opening_balance: Decimal,
        book_closing_balance: Decimal,
        created_by_id: Optional[uuid.UUID] = None,
    ) -> BankReconciliation:
        """Create a new bank reconciliation."""
        # Calculate adjusted balances (initially same as closing)
        adjusted_bank = statement_closing_balance
        adjusted_book = book_closing_balance
        difference = adjusted_bank - adjusted_book
        
        recon = BankReconciliation(
            bank_account_id=bank_account_id,
            reconciliation_date=reconciliation_date,
            period_start=period_start,
            period_end=period_end,
            statement_opening_balance=statement_opening_balance,
            statement_closing_balance=statement_closing_balance,
            book_opening_balance=book_opening_balance,
            book_closing_balance=book_closing_balance,
            adjusted_bank_balance=adjusted_bank,
            adjusted_book_balance=adjusted_book,
            difference=difference,
            status=ReconciliationStatus.DRAFT,
            created_by_id=created_by_id,
        )
        self.db.add(recon)
        await self.db.commit()
        await self.db.refresh(recon)
        return recon
    
    async def update_reconciliation_adjustments(
        self,
        reconciliation_id: uuid.UUID,
        deposits_in_transit: Optional[Decimal] = None,
        outstanding_checks: Optional[Decimal] = None,
        bank_charges: Optional[Decimal] = None,
        interest_earned: Optional[Decimal] = None,
        other_adjustments: Optional[Decimal] = None,
    ) -> BankReconciliation:
        """Update reconciliation adjustments and recalculate difference."""
        result = await self.db.execute(
            select(BankReconciliation).where(BankReconciliation.id == reconciliation_id)
        )
        recon = result.scalar_one_or_none()
        if not recon:
            raise ValueError("Reconciliation not found")
        
        # Update adjustments
        if deposits_in_transit is not None:
            recon.deposits_in_transit = deposits_in_transit
        if outstanding_checks is not None:
            recon.outstanding_checks = outstanding_checks
        if bank_charges is not None:
            recon.bank_charges = bank_charges
        if interest_earned is not None:
            recon.interest_earned = interest_earned
        if other_adjustments is not None:
            recon.other_adjustments = other_adjustments
        
        # Recalculate adjusted balances
        # Bank: closing - outstanding checks + deposits in transit
        recon.adjusted_bank_balance = (
            recon.statement_closing_balance
            - recon.outstanding_checks
            + recon.deposits_in_transit
        )
        
        # Book: closing + interest - bank charges + other
        recon.adjusted_book_balance = (
            recon.book_closing_balance
            + recon.interest_earned
            - recon.bank_charges
            + recon.other_adjustments
        )
        
        # Calculate difference
        recon.difference = recon.adjusted_bank_balance - recon.adjusted_book_balance
        
        # Update status
        if recon.difference == Decimal("0.00"):
            recon.status = ReconciliationStatus.IN_PROGRESS
        
        await self.db.commit()
        await self.db.refresh(recon)
        return recon
    
    async def complete_reconciliation(
        self,
        reconciliation_id: uuid.UUID,
        completed_by_id: uuid.UUID,
    ) -> BankReconciliation:
        """Mark reconciliation as completed."""
        result = await self.db.execute(
            select(BankReconciliation).where(BankReconciliation.id == reconciliation_id)
        )
        recon = result.scalar_one_or_none()
        if not recon:
            raise ValueError("Reconciliation not found")
        
        if recon.difference != Decimal("0.00"):
            raise ValueError(
                f"Cannot complete reconciliation with difference of {recon.difference}. "
                "Difference must be zero."
            )
        
        recon.status = ReconciliationStatus.COMPLETED
        recon.completed_at = datetime.utcnow()
        recon.completed_by_id = completed_by_id
        
        # Update bank account
        account_result = await self.db.execute(
            select(BankAccount).where(BankAccount.id == recon.bank_account_id)
        )
        account = account_result.scalar_one_or_none()
        if account:
            account.last_reconciled_date = recon.reconciliation_date
            account.last_reconciled_balance = recon.statement_closing_balance
            account.current_balance = recon.statement_closing_balance
        
        await self.db.commit()
        await self.db.refresh(recon)
        return recon
    
    async def approve_reconciliation(
        self,
        reconciliation_id: uuid.UUID,
        approved_by_id: uuid.UUID,
    ) -> BankReconciliation:
        """Approve a completed reconciliation."""
        result = await self.db.execute(
            select(BankReconciliation).where(BankReconciliation.id == reconciliation_id)
        )
        recon = result.scalar_one_or_none()
        if not recon:
            raise ValueError("Reconciliation not found")
        
        if recon.status != ReconciliationStatus.COMPLETED:
            raise ValueError("Reconciliation must be completed before approval")
        
        recon.status = ReconciliationStatus.APPROVED
        recon.approved_at = datetime.utcnow()
        recon.approved_by_id = approved_by_id
        
        await self.db.commit()
        await self.db.refresh(recon)
        return recon
    
    async def get_reconciliations(
        self,
        bank_account_id: uuid.UUID,
        status: Optional[ReconciliationStatus] = None,
    ) -> List[BankReconciliation]:
        """Get reconciliations for a bank account."""
        query = select(BankReconciliation).where(
            BankReconciliation.bank_account_id == bank_account_id
        )
        if status:
            query = query.where(BankReconciliation.status == status)
        query = query.order_by(BankReconciliation.reconciliation_date.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_reconciliation_summary(
        self,
        entity_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get reconciliation summary for all accounts in an entity."""
        accounts = await self.get_bank_accounts(entity_id)
        
        summary = {
            "total_accounts": len(accounts),
            "accounts": [],
        }
        
        for account in accounts:
            last_recon = await self.db.execute(
                select(BankReconciliation)
                .where(BankReconciliation.bank_account_id == account.id)
                .order_by(BankReconciliation.reconciliation_date.desc())
                .limit(1)
            )
            last_recon = last_recon.scalar_one_or_none()
            
            summary["accounts"].append({
                "account_id": str(account.id),
                "bank_name": account.bank_name,
                "account_number": account.account_number,
                "current_balance": float(account.current_balance),
                "last_reconciled_date": (
                    account.last_reconciled_date.isoformat() 
                    if account.last_reconciled_date else None
                ),
                "last_reconciled_balance": (
                    float(account.last_reconciled_balance) 
                    if account.last_reconciled_balance else None
                ),
                "last_reconciliation_status": (
                    last_recon.status.value if last_recon else None
                ),
            })
        
        return summary


# Factory function
def get_bank_reconciliation_service(db: AsyncSession) -> BankReconciliationService:
    """Get bank reconciliation service instance."""
    return BankReconciliationService(db)
