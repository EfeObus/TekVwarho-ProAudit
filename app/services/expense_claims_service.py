"""
TekVwarho ProAudit - Expense Claims Service

Service for managing expense claims and reimbursements.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.expense_claims import (
    ExpenseClaim, ExpenseClaimItem, ExpenseCategory,
    ClaimStatus, PaymentMethod
)


class ExpenseClaimsService:
    """Service for expense claims operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_claim_number(self) -> str:
        """Generate a unique claim number."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_part = str(uuid.uuid4())[:6].upper()
        return f"EXP-{timestamp}-{random_part}"
    
    async def create_claim(
        self,
        entity_id: uuid.UUID,
        employee_id: uuid.UUID,
        title: str,
        expense_date_from: date,
        expense_date_to: date,
        description: Optional[str] = None,
        project_code: Optional[str] = None,
        cost_center: Optional[str] = None,
        department: Optional[str] = None,
        created_by_id: Optional[uuid.UUID] = None,
    ) -> ExpenseClaim:
        """Create a new expense claim."""
        claim = ExpenseClaim(
            entity_id=entity_id,
            employee_id=employee_id,
            claim_number=self._generate_claim_number(),
            title=title,
            description=description,
            expense_date_from=expense_date_from,
            expense_date_to=expense_date_to,
            project_code=project_code,
            cost_center=cost_center,
            department=department,
            status=ClaimStatus.DRAFT,
            created_by_id=created_by_id,
        )
        self.db.add(claim)
        await self.db.commit()
        await self.db.refresh(claim)
        return claim
    
    async def add_expense_item(
        self,
        claim_id: uuid.UUID,
        expense_date: date,
        category: ExpenseCategory,
        description: str,
        amount: Decimal,
        vat_amount: Decimal = Decimal("0.00"),
        vendor_name: Optional[str] = None,
        receipt_number: Optional[str] = None,
        receipt_file_url: Optional[str] = None,
        is_tax_deductible: bool = True,
        gl_account_code: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ExpenseClaimItem:
        """Add an expense item to a claim."""
        item = ExpenseClaimItem(
            claim_id=claim_id,
            expense_date=expense_date,
            category=category,
            description=description,
            amount=amount,
            vat_amount=vat_amount,
            approved_amount=amount,  # Default to claimed amount
            vendor_name=vendor_name,
            receipt_number=receipt_number,
            receipt_file_url=receipt_file_url,
            has_receipt=bool(receipt_file_url or receipt_number),
            is_tax_deductible=is_tax_deductible,
            gl_account_code=gl_account_code,
            notes=notes,
        )
        self.db.add(item)
        
        # Update claim total
        await self._update_claim_totals(claim_id)
        
        await self.db.commit()
        await self.db.refresh(item)
        return item
    
    async def _update_claim_totals(self, claim_id: uuid.UUID):
        """Recalculate claim totals from line items."""
        result = await self.db.execute(
            select(ExpenseClaim).where(ExpenseClaim.id == claim_id)
        )
        claim = result.scalar_one_or_none()
        if not claim:
            return
        
        # Sum line items
        total_result = await self.db.execute(
            select(func.sum(ExpenseClaimItem.amount)).where(
                ExpenseClaimItem.claim_id == claim_id
            )
        )
        total = total_result.scalar() or Decimal("0.00")
        
        approved_result = await self.db.execute(
            select(func.sum(ExpenseClaimItem.approved_amount)).where(
                ExpenseClaimItem.claim_id == claim_id
            )
        )
        approved = approved_result.scalar() or Decimal("0.00")
        
        claim.total_amount = total
        claim.approved_amount = approved
    
    async def get_claim(
        self,
        claim_id: uuid.UUID,
        entity_id: Optional[uuid.UUID] = None,
    ) -> Optional[ExpenseClaim]:
        """Get a claim by ID."""
        query = (
            select(ExpenseClaim)
            .options(selectinload(ExpenseClaim.line_items))
            .where(ExpenseClaim.id == claim_id)
        )
        if entity_id:
            query = query.where(ExpenseClaim.entity_id == entity_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_claims(
        self,
        entity_id: uuid.UUID,
        employee_id: Optional[uuid.UUID] = None,
        status: Optional[ClaimStatus] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ExpenseClaim]:
        """Get claims with optional filters."""
        query = (
            select(ExpenseClaim)
            .where(ExpenseClaim.entity_id == entity_id)
            .options(selectinload(ExpenseClaim.line_items))
        )
        
        if employee_id:
            query = query.where(ExpenseClaim.employee_id == employee_id)
        if status:
            query = query.where(ExpenseClaim.status == status)
        if date_from:
            query = query.where(ExpenseClaim.expense_date_from >= date_from)
        if date_to:
            query = query.where(ExpenseClaim.expense_date_to <= date_to)
        
        query = query.order_by(ExpenseClaim.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def submit_claim(
        self,
        claim_id: uuid.UUID,
    ) -> ExpenseClaim:
        """Submit a claim for approval."""
        claim = await self.get_claim(claim_id)
        if not claim:
            raise ValueError("Claim not found")
        
        if claim.status != ClaimStatus.DRAFT:
            raise ValueError("Only draft claims can be submitted")
        
        if not claim.line_items:
            raise ValueError("Cannot submit a claim with no expense items")
        
        claim.status = ClaimStatus.SUBMITTED
        claim.submitted_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(claim)
        return claim
    
    async def approve_claim(
        self,
        claim_id: uuid.UUID,
        approved_by_id: uuid.UUID,
        approval_notes: Optional[str] = None,
        item_adjustments: Optional[Dict[str, Decimal]] = None,
    ) -> ExpenseClaim:
        """
        Approve a submitted claim.
        
        Args:
            item_adjustments: Dict mapping item_id to approved_amount (for partial approvals)
        """
        claim = await self.get_claim(claim_id)
        if not claim:
            raise ValueError("Claim not found")
        
        if claim.status not in [ClaimStatus.SUBMITTED, ClaimStatus.PENDING_APPROVAL]:
            raise ValueError("Only submitted claims can be approved")
        
        # Apply item adjustments if provided
        if item_adjustments:
            for item in claim.line_items:
                if str(item.id) in item_adjustments:
                    item.approved_amount = item_adjustments[str(item.id)]
        
        # Recalculate totals
        await self._update_claim_totals(claim_id)
        
        claim.status = ClaimStatus.APPROVED
        claim.approved_by_id = approved_by_id
        claim.approved_at = datetime.utcnow()
        claim.approval_notes = approval_notes
        
        await self.db.commit()
        await self.db.refresh(claim)
        return claim
    
    async def reject_claim(
        self,
        claim_id: uuid.UUID,
        rejected_by_id: uuid.UUID,
        rejection_reason: str,
    ) -> ExpenseClaim:
        """Reject a submitted claim."""
        claim = await self.get_claim(claim_id)
        if not claim:
            raise ValueError("Claim not found")
        
        if claim.status not in [ClaimStatus.SUBMITTED, ClaimStatus.PENDING_APPROVAL]:
            raise ValueError("Only submitted claims can be rejected")
        
        claim.status = ClaimStatus.REJECTED
        claim.rejected_by_id = rejected_by_id
        claim.rejected_at = datetime.utcnow()
        claim.rejection_reason = rejection_reason
        
        await self.db.commit()
        await self.db.refresh(claim)
        return claim
    
    async def mark_as_paid(
        self,
        claim_id: uuid.UUID,
        payment_method: PaymentMethod,
        payment_reference: Optional[str] = None,
    ) -> ExpenseClaim:
        """Mark an approved claim as paid."""
        claim = await self.get_claim(claim_id)
        if not claim:
            raise ValueError("Claim not found")
        
        if claim.status != ClaimStatus.APPROVED:
            raise ValueError("Only approved claims can be marked as paid")
        
        claim.status = ClaimStatus.PAID
        claim.payment_method = payment_method
        claim.payment_reference = payment_reference
        claim.paid_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(claim)
        return claim
    
    async def get_claims_summary(
        self,
        entity_id: uuid.UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get summary statistics for expense claims."""
        base_query = select(ExpenseClaim).where(ExpenseClaim.entity_id == entity_id)
        if date_from:
            base_query = base_query.where(ExpenseClaim.expense_date_from >= date_from)
        if date_to:
            base_query = base_query.where(ExpenseClaim.expense_date_to <= date_to)
        
        # Count by status
        status_counts = {}
        for status in ClaimStatus:
            result = await self.db.execute(
                select(func.count(ExpenseClaim.id)).where(
                    and_(
                        ExpenseClaim.entity_id == entity_id,
                        ExpenseClaim.status == status,
                    )
                )
            )
            status_counts[status.value] = result.scalar() or 0
        
        # Total amounts
        total_result = await self.db.execute(
            select(func.sum(ExpenseClaim.total_amount)).where(
                ExpenseClaim.entity_id == entity_id
            )
        )
        total_claimed = total_result.scalar() or Decimal("0.00")
        
        approved_result = await self.db.execute(
            select(func.sum(ExpenseClaim.approved_amount)).where(
                and_(
                    ExpenseClaim.entity_id == entity_id,
                    ExpenseClaim.status.in_([ClaimStatus.APPROVED, ClaimStatus.PAID]),
                )
            )
        )
        total_approved = approved_result.scalar() or Decimal("0.00")
        
        paid_result = await self.db.execute(
            select(func.sum(ExpenseClaim.approved_amount)).where(
                and_(
                    ExpenseClaim.entity_id == entity_id,
                    ExpenseClaim.status == ClaimStatus.PAID,
                )
            )
        )
        total_paid = paid_result.scalar() or Decimal("0.00")
        
        # Pending approval count
        pending_count = status_counts.get("submitted", 0) + status_counts.get("pending_approval", 0)
        
        return {
            "status_counts": status_counts,
            "total_claims": sum(status_counts.values()),
            "pending_approval": pending_count,
            "total_claimed": float(total_claimed),
            "total_approved": float(total_approved),
            "total_paid": float(total_paid),
            "pending_payment": float(total_approved - total_paid),
        }
    
    async def get_expense_by_category(
        self,
        entity_id: uuid.UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Get expense breakdown by category."""
        query = (
            select(
                ExpenseClaimItem.category,
                func.sum(ExpenseClaimItem.amount).label("total_amount"),
                func.count(ExpenseClaimItem.id).label("count"),
            )
            .join(ExpenseClaim)
            .where(
                and_(
                    ExpenseClaim.entity_id == entity_id,
                    ExpenseClaim.status.in_([ClaimStatus.APPROVED, ClaimStatus.PAID]),
                )
            )
            .group_by(ExpenseClaimItem.category)
            .order_by(func.sum(ExpenseClaimItem.amount).desc())
        )
        
        if date_from:
            query = query.where(ExpenseClaimItem.expense_date >= date_from)
        if date_to:
            query = query.where(ExpenseClaimItem.expense_date <= date_to)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "category": row.category.value,
                "total_amount": float(row.total_amount or 0),
                "count": row.count or 0,
            }
            for row in rows
        ]


def get_expense_claims_service(db: AsyncSession) -> ExpenseClaimsService:
    """Get expense claims service instance."""
    return ExpenseClaimsService(db)
