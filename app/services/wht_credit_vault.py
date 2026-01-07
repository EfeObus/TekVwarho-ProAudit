"""
WHT Credit Note Vault Service
Tracks and manages WHT credit notes for tax offset

Features:
- Auto-match credit notes to receivables
- Track deduction rates and types
- Status management (pending, received, applied)
- Tax year tracking
- TIN validation
- Credit expiry alerts (6-year validity)
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
import re
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.orm import selectinload

from app.models.advanced_accounting import WHTCreditNote, WHTCreditStatus

logger = logging.getLogger(__name__)


# WHT Rates for different income types (2026 Tax Reform)
WHT_RATES = {
    "dividend": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Dividends"
    },
    "interest": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Interest"
    },
    "royalty": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Royalties"
    },
    "rent": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Rent on Property"
    },
    "professional_fees": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Professional/Consultancy Fees"
    },
    "technical_fees": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Technical Service Fees"
    },
    "management_fees": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Management Fees"
    },
    "contract": {
        "resident": Decimal("5"),
        "non_resident": Decimal("10"),
        "description": "Contract/Supply of Goods"
    },
    "director_fees": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Director Fees"
    },
    "commission": {
        "resident": Decimal("10"),
        "non_resident": Decimal("10"),
        "description": "Commission"
    }
}


class WHTCreditVaultService:
    """
    Service for managing WHT credit notes
    """
    
    def __init__(self):
        self.wht_rates = WHT_RATES
    
    async def record_credit_note(
        self,
        db: AsyncSession,
        entity_id: UUID,
        credit_note_data: Dict[str, Any],
        created_by: UUID
    ) -> WHTCreditNote:
        """Record a new WHT credit note"""
        
        # Validate TIN format
        issuer_tin = credit_note_data.get("issuer_tin", "")
        if not self._validate_tin(issuer_tin):
            raise ValueError(f"Invalid TIN format: {issuer_tin}")
        
        # Validate WHT type
        wht_type = credit_note_data.get("wht_type", "").lower()
        if wht_type not in self.wht_rates:
            raise ValueError(f"Invalid WHT type: {wht_type}")
        
        # Calculate WHT amount if not provided
        gross_amount = Decimal(str(credit_note_data["gross_amount"]))
        wht_rate = Decimal(str(credit_note_data.get("wht_rate", self.wht_rates[wht_type]["resident"])))
        wht_amount = credit_note_data.get("wht_amount")
        
        if not wht_amount:
            wht_amount = (gross_amount * wht_rate / 100).quantize(Decimal("0.01"))
        else:
            wht_amount = Decimal(str(wht_amount))
        
        # Determine tax year
        issue_date = credit_note_data.get("issue_date")
        if isinstance(issue_date, str):
            issue_date = date.fromisoformat(issue_date)
        if not issue_date:
            issue_date = date.today()
        
        tax_year = credit_note_data.get("tax_year", issue_date.year)
        
        # Calculate expiry (6 years from issue)
        expires_at = datetime.combine(
            date(issue_date.year + 6, 12, 31),
            datetime.max.time()
        )
        
        credit_note = WHTCreditNote(
            entity_id=entity_id,
            credit_note_number=credit_note_data["credit_note_number"],
            issue_date=issue_date,
            issuer_name=credit_note_data["issuer_name"],
            issuer_tin=issuer_tin,
            issuer_address=credit_note_data.get("issuer_address"),
            gross_amount=gross_amount,
            wht_rate=wht_rate,
            wht_amount=wht_amount,
            wht_type=wht_type,
            tax_year=tax_year,
            status=WHTCreditStatus.PENDING,
            description=credit_note_data.get("description"),
            expires_at=expires_at,
            created_by_id=created_by
        )
        
        db.add(credit_note)
        await db.commit()
        await db.refresh(credit_note)
        
        logger.info(f"Recorded WHT credit note {credit_note.credit_note_number} for NGN {wht_amount}")
        
        return credit_note
    
    async def auto_match_to_receivables(
        self,
        db: AsyncSession,
        entity_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Auto-match pending credit notes to receivables
        Matches based on issuer TIN and amount
        """
        from app.models.invoice import Invoice
        
        # Get pending credit notes
        cn_query = select(WHTCreditNote).where(
            and_(
                WHTCreditNote.entity_id == entity_id,
                WHTCreditNote.status == WHTCreditStatus.PENDING,
                WHTCreditNote.matched_invoice_id == None
            )
        )
        result = await db.execute(cn_query)
        credit_notes = result.scalars().all()
        
        matches = []
        
        for cn in credit_notes:
            # Find matching invoice
            # Match criteria:
            # 1. Same customer TIN
            # 2. Invoice amount matches gross amount
            # 3. Invoice is marked as having WHT deduction
            
            inv_query = select(Invoice).where(
                and_(
                    Invoice.entity_id == entity_id,
                    Invoice.customer_tin == cn.issuer_tin,
                    Invoice.status.in_(["sent", "paid", "partial"])
                )
            )
            
            inv_result = await db.execute(inv_query)
            potential_invoices = inv_result.scalars().all()
            
            for inv in potential_invoices:
                # Check amount match (within tolerance)
                inv_total = inv.total_amount or Decimal("0")
                amount_diff = abs(inv_total - cn.gross_amount)
                tolerance = inv_total * Decimal("0.05")  # 5% tolerance
                
                if amount_diff <= tolerance:
                    # Match found
                    cn.matched_invoice_id = inv.id
                    cn.status = WHTCreditStatus.MATCHED
                    cn.matched_at = datetime.utcnow()
                    
                    matches.append({
                        "credit_note_id": str(cn.id),
                        "credit_note_number": cn.credit_note_number,
                        "invoice_id": str(inv.id),
                        "invoice_number": inv.invoice_number,
                        "issuer_name": cn.issuer_name,
                        "wht_amount": str(cn.wht_amount)
                    })
                    break
        
        if matches:
            await db.commit()
            logger.info(f"Auto-matched {len(matches)} credit notes to invoices")
        
        return matches
    
    async def apply_credit_to_tax(
        self,
        db: AsyncSession,
        credit_note_id: UUID,
        tax_payment_reference: str,
        applied_by: UUID
    ) -> WHTCreditNote:
        """Apply a credit note against tax liability"""
        
        cn = await db.get(WHTCreditNote, credit_note_id)
        if not cn:
            raise ValueError(f"Credit note {credit_note_id} not found")
        
        if cn.status not in [WHTCreditStatus.RECEIVED, WHTCreditStatus.MATCHED]:
            raise ValueError(f"Cannot apply credit note in status {cn.status}")
        
        # Check if not expired
        if cn.expires_at and cn.expires_at < datetime.utcnow():
            raise ValueError(f"Credit note has expired on {cn.expires_at}")
        
        cn.status = WHTCreditStatus.APPLIED
        cn.applied_tax_reference = tax_payment_reference
        cn.applied_at = datetime.utcnow()
        cn.applied_by_id = applied_by
        
        await db.commit()
        await db.refresh(cn)
        
        logger.info(f"Applied credit note {cn.credit_note_number} to tax payment {tax_payment_reference}")
        
        return cn
    
    async def get_vault_summary(
        self,
        db: AsyncSession,
        entity_id: UUID,
        tax_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get summary of WHT credit vault"""
        
        query = select(WHTCreditNote).where(WHTCreditNote.entity_id == entity_id)
        
        if tax_year:
            query = query.where(WHTCreditNote.tax_year == tax_year)
        
        result = await db.execute(query)
        credit_notes = result.scalars().all()
        
        # Group by status
        by_status = {
            "pending": {"count": 0, "amount": Decimal("0")},
            "received": {"count": 0, "amount": Decimal("0")},
            "matched": {"count": 0, "amount": Decimal("0")},
            "applied": {"count": 0, "amount": Decimal("0")},
            "expired": {"count": 0, "amount": Decimal("0")},
            "rejected": {"count": 0, "amount": Decimal("0")}
        }
        
        by_type = {}
        by_issuer = {}
        expiring_soon = []
        
        now = datetime.utcnow()
        soon = now + timedelta(days=180)  # 6 months
        
        for cn in credit_notes:
            status = cn.status.value if hasattr(cn.status, 'value') else cn.status
            amount = cn.wht_amount or Decimal("0")
            
            if status in by_status:
                by_status[status]["count"] += 1
                by_status[status]["amount"] += amount
            
            # By type
            wht_type = cn.wht_type or "other"
            if wht_type not in by_type:
                by_type[wht_type] = {"count": 0, "amount": Decimal("0")}
            by_type[wht_type]["count"] += 1
            by_type[wht_type]["amount"] += amount
            
            # By issuer
            issuer = cn.issuer_name or "Unknown"
            if issuer not in by_issuer:
                by_issuer[issuer] = {"count": 0, "amount": Decimal("0")}
            by_issuer[issuer]["count"] += 1
            by_issuer[issuer]["amount"] += amount
            
            # Check expiry
            if cn.expires_at and status in ["pending", "received", "matched"]:
                if cn.expires_at <= soon:
                    expiring_soon.append({
                        "id": str(cn.id),
                        "credit_note_number": cn.credit_note_number,
                        "issuer_name": cn.issuer_name,
                        "wht_amount": str(amount),
                        "expires_at": cn.expires_at.isoformat(),
                        "days_until_expiry": (cn.expires_at - now).days
                    })
        
        # Calculate totals
        total_available = (
            by_status["received"]["amount"] + 
            by_status["matched"]["amount"]
        )
        total_applied = by_status["applied"]["amount"]
        total_pending = by_status["pending"]["amount"]
        
        return {
            "entity_id": str(entity_id),
            "tax_year": tax_year,
            "summary": {
                "total_credit_notes": len(credit_notes),
                "total_available": str(total_available),
                "total_applied": str(total_applied),
                "total_pending": str(total_pending),
                "total_expired": str(by_status["expired"]["amount"])
            },
            "by_status": {
                k: {"count": v["count"], "amount": str(v["amount"])}
                for k, v in by_status.items()
            },
            "by_type": {
                k: {"count": v["count"], "amount": str(v["amount"])}
                for k, v in by_type.items()
            },
            "top_issuers": sorted(
                [
                    {"name": k, "count": v["count"], "amount": str(v["amount"])}
                    for k, v in by_issuer.items()
                ],
                key=lambda x: Decimal(x["amount"]),
                reverse=True
            )[:10],
            "expiring_soon": expiring_soon,
            "wht_rates": {
                k: {
                    "rate": str(v["resident"]),
                    "description": v["description"]
                }
                for k, v in self.wht_rates.items()
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def get_credit_notes(
        self,
        db: AsyncSession,
        entity_id: UUID,
        status: Optional[str] = None,
        tax_year: Optional[int] = None,
        issuer_tin: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get credit notes with filters"""
        
        query = select(WHTCreditNote).where(
            WHTCreditNote.entity_id == entity_id
        ).order_by(WHTCreditNote.issue_date.desc())
        
        if status:
            query = query.where(WHTCreditNote.status == WHTCreditStatus(status))
        
        if tax_year:
            query = query.where(WHTCreditNote.tax_year == tax_year)
        
        if issuer_tin:
            query = query.where(WHTCreditNote.issuer_tin == issuer_tin)
        
        result = await db.execute(query)
        credit_notes = result.scalars().all()
        
        return [
            {
                "id": str(cn.id),
                "credit_note_number": cn.credit_note_number,
                "issue_date": cn.issue_date.isoformat() if cn.issue_date else None,
                "issuer_name": cn.issuer_name,
                "issuer_tin": cn.issuer_tin,
                "gross_amount": str(cn.gross_amount),
                "wht_rate": str(cn.wht_rate),
                "wht_amount": str(cn.wht_amount),
                "wht_type": cn.wht_type,
                "tax_year": cn.tax_year,
                "status": cn.status.value if hasattr(cn.status, 'value') else cn.status,
                "matched_invoice_id": str(cn.matched_invoice_id) if cn.matched_invoice_id else None,
                "applied_tax_reference": cn.applied_tax_reference,
                "expires_at": cn.expires_at.isoformat() if cn.expires_at else None,
                "description": cn.description
            }
            for cn in credit_notes
        ]
    
    async def update_status(
        self,
        db: AsyncSession,
        credit_note_id: UUID,
        new_status: str,
        updated_by: UUID,
        notes: Optional[str] = None
    ) -> WHTCreditNote:
        """Update credit note status"""
        
        cn = await db.get(WHTCreditNote, credit_note_id)
        if not cn:
            raise ValueError(f"Credit note {credit_note_id} not found")
        
        # Validate status transition
        valid_transitions = {
            "pending": ["received", "rejected"],
            "received": ["matched", "applied", "expired"],
            "matched": ["applied", "received"],
            "applied": [],  # Final state
            "rejected": ["pending"],  # Can be corrected
            "expired": []  # Final state
        }
        
        current = cn.status.value if hasattr(cn.status, 'value') else cn.status
        if new_status not in valid_transitions.get(current, []):
            raise ValueError(f"Cannot transition from {current} to {new_status}")
        
        cn.status = WHTCreditStatus(new_status)
        
        if new_status == "received":
            cn.received_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(cn)
        
        logger.info(f"Updated credit note {cn.credit_note_number} status to {new_status}")
        
        return cn
    
    async def check_expired_credits(self, db: AsyncSession) -> int:
        """Check and mark expired credit notes"""
        
        query = update(WHTCreditNote).where(
            and_(
                WHTCreditNote.status.in_([
                    WHTCreditStatus.PENDING,
                    WHTCreditStatus.RECEIVED,
                    WHTCreditStatus.MATCHED
                ]),
                WHTCreditNote.expires_at < datetime.utcnow()
            )
        ).values(status=WHTCreditStatus.EXPIRED)
        
        result = await db.execute(query)
        await db.commit()
        
        expired_count = result.rowcount
        if expired_count > 0:
            logger.warning(f"Marked {expired_count} credit notes as expired")
        
        return expired_count
    
    async def generate_tax_offset_report(
        self,
        db: AsyncSession,
        entity_id: UUID,
        tax_year: int
    ) -> Dict[str, Any]:
        """Generate report for tax offset claims"""
        
        query = select(WHTCreditNote).where(
            and_(
                WHTCreditNote.entity_id == entity_id,
                WHTCreditNote.tax_year == tax_year,
                WHTCreditNote.status.in_([
                    WHTCreditStatus.RECEIVED,
                    WHTCreditStatus.MATCHED,
                    WHTCreditStatus.APPLIED
                ])
            )
        ).order_by(WHTCreditNote.issue_date)
        
        result = await db.execute(query)
        credit_notes = result.scalars().all()
        
        # Build report
        total_available = Decimal("0")
        total_applied = Decimal("0")
        
        by_quarter = {
            "Q1": {"count": 0, "amount": Decimal("0")},
            "Q2": {"count": 0, "amount": Decimal("0")},
            "Q3": {"count": 0, "amount": Decimal("0")},
            "Q4": {"count": 0, "amount": Decimal("0")}
        }
        
        entries = []
        
        for cn in credit_notes:
            amount = cn.wht_amount or Decimal("0")
            
            if cn.status == WHTCreditStatus.APPLIED:
                total_applied += amount
            else:
                total_available += amount
            
            # Determine quarter
            if cn.issue_date:
                month = cn.issue_date.month
                quarter = f"Q{(month - 1) // 3 + 1}"
                by_quarter[quarter]["count"] += 1
                by_quarter[quarter]["amount"] += amount
            
            entries.append({
                "credit_note_number": cn.credit_note_number,
                "issue_date": cn.issue_date.isoformat() if cn.issue_date else None,
                "issuer_name": cn.issuer_name,
                "issuer_tin": cn.issuer_tin,
                "gross_amount": str(cn.gross_amount),
                "wht_rate": str(cn.wht_rate),
                "wht_amount": str(amount),
                "wht_type": cn.wht_type,
                "status": cn.status.value
            })
        
        return {
            "entity_id": str(entity_id),
            "tax_year": tax_year,
            "report_title": f"WHT Credit Note Schedule - {tax_year}",
            "summary": {
                "total_credit_notes": len(credit_notes),
                "total_available_for_offset": str(total_available),
                "total_already_applied": str(total_applied),
                "net_available": str(total_available)
            },
            "by_quarter": {
                k: {"count": v["count"], "amount": str(v["amount"])}
                for k, v in by_quarter.items()
            },
            "entries": entries,
            "notes": [
                "This schedule should be attached to the Company Income Tax return",
                "All credit notes are valid for 6 years from the date of issue",
                "Ensure all issuer TINs are verified against FIRS database"
            ],
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _validate_tin(self, tin: str) -> bool:
        """Validate Nigerian TIN format"""
        if not tin:
            return False
        
        # Nigerian TIN is typically 10-14 digits
        # Remove any dashes or spaces
        clean_tin = re.sub(r'[\s\-]', '', tin)
        
        # Check format
        if not clean_tin.isdigit():
            return False
        
        if len(clean_tin) < 10 or len(clean_tin) > 14:
            return False
        
        return True
    
    def get_wht_rate(
        self,
        wht_type: str,
        is_resident: bool = True
    ) -> Decimal:
        """Get WHT rate for a given type"""
        
        if wht_type.lower() not in self.wht_rates:
            return Decimal("10")  # Default rate
        
        rate_key = "resident" if is_resident else "non_resident"
        return self.wht_rates[wht_type.lower()][rate_key]


# Singleton instance
wht_credit_vault_service = WHTCreditVaultService()
