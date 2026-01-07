"""
Three-Way Matching Service
Purchase Order <-> Goods Received Note <-> Vendor Invoice

Auto-matches and flags discrepancies for review before payment approval
"""

from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from enum import Enum
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.orm import selectinload

from app.models.advanced_accounting import (
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceivedNote,
    GoodsReceivedNoteItem,
    ThreeWayMatch,
    MatchingStatus
)

logger = logging.getLogger(__name__)


class MatchingTolerance:
    """Configurable matching tolerances"""
    
    QUANTITY_TOLERANCE_PCT = Decimal("2")  # 2% quantity variance allowed
    PRICE_TOLERANCE_PCT = Decimal("1")     # 1% price variance allowed
    AMOUNT_TOLERANCE_NGN = Decimal("100")  # NGN 100 absolute tolerance


class ThreeWayMatchingService:
    """
    Service for 3-way matching of Purchase Orders, GRNs, and Invoices
    """
    
    async def create_purchase_order(
        self,
        db: AsyncSession,
        entity_id: UUID,
        vendor_id: UUID,
        po_data: Dict[str, Any],
        items: List[Dict[str, Any]],
        created_by: UUID
    ) -> PurchaseOrder:
        """Create a new Purchase Order"""
        
        # Generate PO number
        po_number = await self._generate_po_number(db, entity_id)
        
        # Create PO
        po = PurchaseOrder(
            entity_id=entity_id,
            vendor_id=vendor_id,
            po_number=po_number,
            po_date=po_data.get("po_date", date.today()),
            expected_delivery_date=po_data.get("expected_delivery_date"),
            delivery_address=po_data.get("delivery_address"),
            payment_terms=po_data.get("payment_terms"),
            notes=po_data.get("notes"),
            status="draft",
            created_by_id=created_by
        )
        
        # Calculate totals
        subtotal = Decimal("0")
        total_vat = Decimal("0")
        
        for item_data in items:
            qty = Decimal(str(item_data["quantity"]))
            unit_price = Decimal(str(item_data["unit_price"]))
            line_total = qty * unit_price
            
            # Calculate VAT (7.5%)
            vat_amount = Decimal("0")
            if item_data.get("is_vatable", True):
                vat_amount = line_total * Decimal("0.075")
            
            po_item = PurchaseOrderItem(
                item_description=item_data["description"],
                quantity=qty,
                unit_of_measure=item_data.get("uom", "UNIT"),
                unit_price=unit_price,
                vat_amount=vat_amount,
                line_total=line_total + vat_amount,
                inventory_item_id=item_data.get("inventory_item_id"),
                gl_account_code=item_data.get("gl_account_code")
            )
            po.items.append(po_item)
            
            subtotal += line_total
            total_vat += vat_amount
        
        po.subtotal = subtotal
        po.vat_amount = total_vat
        po.total_amount = subtotal + total_vat
        
        db.add(po)
        await db.commit()
        await db.refresh(po)
        
        logger.info(f"Created PO {po_number} for entity {entity_id}")
        
        return po
    
    async def approve_purchase_order(
        self,
        db: AsyncSession,
        po_id: UUID,
        approved_by: UUID
    ) -> PurchaseOrder:
        """Approve a purchase order"""
        
        po = await db.get(PurchaseOrder, po_id)
        if not po:
            raise ValueError(f"Purchase Order {po_id} not found")
        
        if po.status != "draft":
            raise ValueError(f"Cannot approve PO in status {po.status}")
        
        po.status = "approved"
        po.approved_by_id = approved_by
        po.approved_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(po)
        
        return po
    
    async def create_goods_received_note(
        self,
        db: AsyncSession,
        entity_id: UUID,
        po_id: UUID,
        grn_data: Dict[str, Any],
        items: List[Dict[str, Any]],
        created_by: UUID
    ) -> GoodsReceivedNote:
        """Create a Goods Received Note against a PO"""
        
        # Get PO
        po = await db.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.items)])
        if not po:
            raise ValueError(f"Purchase Order {po_id} not found")
        
        if po.status not in ["approved", "partially_received"]:
            raise ValueError(f"Cannot receive goods for PO in status {po.status}")
        
        # Generate GRN number
        grn_number = await self._generate_grn_number(db, entity_id)
        
        # Create GRN
        grn = GoodsReceivedNote(
            entity_id=entity_id,
            purchase_order_id=po_id,
            grn_number=grn_number,
            received_date=grn_data.get("received_date", date.today()),
            received_by=grn_data.get("received_by"),
            delivery_note_number=grn_data.get("delivery_note_number"),
            notes=grn_data.get("notes"),
            status="pending_inspection",
            created_by_id=created_by
        )
        
        # Map PO items for lookup
        po_items_map = {str(item.id): item for item in po.items}
        
        for item_data in items:
            po_item_id = item_data.get("po_item_id")
            po_item = po_items_map.get(str(po_item_id)) if po_item_id else None
            
            grn_item = GoodsReceivedNoteItem(
                po_item_id=po_item_id,
                item_description=item_data.get("description") or (po_item.item_description if po_item else ""),
                quantity_received=Decimal(str(item_data["quantity_received"])),
                quantity_accepted=Decimal(str(item_data.get("quantity_accepted", item_data["quantity_received"]))),
                quantity_rejected=Decimal(str(item_data.get("quantity_rejected", 0))),
                rejection_reason=item_data.get("rejection_reason"),
                inspection_notes=item_data.get("inspection_notes"),
                storage_location=item_data.get("storage_location")
            )
            grn.items.append(grn_item)
        
        db.add(grn)
        
        # Update PO status
        total_ordered = sum(item.quantity for item in po.items)
        total_received = await self._get_total_received(db, po_id)
        total_received += sum(Decimal(str(item_data["quantity_received"])) for item_data in items)
        
        if total_received >= total_ordered:
            po.status = "fully_received"
        else:
            po.status = "partially_received"
        
        await db.commit()
        await db.refresh(grn)
        
        logger.info(f"Created GRN {grn_number} for PO {po.po_number}")
        
        return grn
    
    async def match_invoice_to_po_grn(
        self,
        db: AsyncSession,
        entity_id: UUID,
        invoice_id: UUID,
        po_id: UUID,
        grn_id: Optional[UUID] = None
    ) -> ThreeWayMatch:
        """
        Perform 3-way matching between Invoice, PO, and GRN
        """
        from app.models.invoice import Invoice
        
        # Get Invoice
        invoice = await db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # Get PO with items
        po = await db.get(PurchaseOrder, po_id, options=[selectinload(PurchaseOrder.items)])
        if not po:
            raise ValueError(f"Purchase Order {po_id} not found")
        
        # Get GRN with items
        grn = None
        if grn_id:
            grn = await db.get(GoodsReceivedNote, grn_id, options=[selectinload(GoodsReceivedNote.items)])
            if not grn:
                raise ValueError(f"GRN {grn_id} not found")
        else:
            # Find most recent GRN for this PO
            grn_query = select(GoodsReceivedNote).where(
                GoodsReceivedNote.purchase_order_id == po_id
            ).order_by(GoodsReceivedNote.received_date.desc())
            result = await db.execute(grn_query)
            grn = result.scalar_one_or_none()
        
        # Perform matching
        discrepancies = []
        status = MatchingStatus.MATCHED
        
        # 1. Match totals
        po_total = po.total_amount or Decimal("0")
        invoice_total = invoice.total_amount or Decimal("0")
        
        amount_diff = abs(invoice_total - po_total)
        amount_diff_pct = (amount_diff / po_total * 100) if po_total else Decimal("0")
        
        if amount_diff > MatchingTolerance.AMOUNT_TOLERANCE_NGN:
            if amount_diff_pct > MatchingTolerance.PRICE_TOLERANCE_PCT:
                discrepancies.append({
                    "type": "amount_mismatch",
                    "field": "total_amount",
                    "po_value": str(po_total),
                    "invoice_value": str(invoice_total),
                    "difference": str(amount_diff),
                    "severity": "high" if amount_diff_pct > 5 else "medium"
                })
                status = MatchingStatus.DISCREPANCY
        
        # 2. Match quantities (if GRN exists)
        if grn:
            grn_total_qty = sum(item.quantity_accepted or Decimal("0") for item in grn.items)
            po_total_qty = sum(item.quantity for item in po.items)
            
            qty_diff = abs(grn_total_qty - po_total_qty)
            qty_diff_pct = (qty_diff / po_total_qty * 100) if po_total_qty else Decimal("0")
            
            if qty_diff_pct > MatchingTolerance.QUANTITY_TOLERANCE_PCT:
                discrepancies.append({
                    "type": "quantity_mismatch",
                    "field": "total_quantity",
                    "po_value": str(po_total_qty),
                    "grn_value": str(grn_total_qty),
                    "difference": str(qty_diff),
                    "severity": "medium"
                })
                if status == MatchingStatus.MATCHED:
                    status = MatchingStatus.DISCREPANCY
        
        # 3. Check vendor match
        if invoice.vendor_id and po.vendor_id:
            if str(invoice.vendor_id) != str(po.vendor_id):
                discrepancies.append({
                    "type": "vendor_mismatch",
                    "field": "vendor_id",
                    "po_vendor": str(po.vendor_id),
                    "invoice_vendor": str(invoice.vendor_id),
                    "severity": "high"
                })
                status = MatchingStatus.DISCREPANCY
        
        # Create match record
        match_record = ThreeWayMatch(
            entity_id=entity_id,
            purchase_order_id=po_id,
            grn_id=grn.id if grn else None,
            invoice_id=invoice_id,
            status=status,
            po_amount=po_total,
            grn_quantity=grn_total_qty if grn else None,
            invoice_amount=invoice_total,
            discrepancies=discrepancies if discrepancies else None,
            matched_at=datetime.utcnow() if status == MatchingStatus.MATCHED else None
        )
        
        db.add(match_record)
        await db.commit()
        await db.refresh(match_record)
        
        logger.info(f"3-way match created: {status.value} for invoice {invoice.invoice_number}")
        
        return match_record
    
    async def resolve_discrepancy(
        self,
        db: AsyncSession,
        match_id: UUID,
        resolution: str,
        resolved_by: UUID,
        notes: Optional[str] = None
    ) -> ThreeWayMatch:
        """Resolve a matching discrepancy"""
        
        match_record = await db.get(ThreeWayMatch, match_id)
        if not match_record:
            raise ValueError(f"Match record {match_id} not found")
        
        if match_record.status not in [MatchingStatus.DISCREPANCY, MatchingStatus.PENDING_REVIEW]:
            raise ValueError(f"Cannot resolve match in status {match_record.status}")
        
        valid_resolutions = ["accept", "reject", "adjust"]
        if resolution not in valid_resolutions:
            raise ValueError(f"Invalid resolution. Must be one of: {valid_resolutions}")
        
        if resolution == "accept":
            match_record.status = MatchingStatus.MATCHED
            match_record.matched_at = datetime.utcnow()
        elif resolution == "reject":
            match_record.status = MatchingStatus.REJECTED
        elif resolution == "adjust":
            match_record.status = MatchingStatus.PENDING_REVIEW
        
        match_record.resolved_by_id = resolved_by
        match_record.resolution_notes = notes
        match_record.resolved_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(match_record)
        
        return match_record
    
    async def get_unmatched_invoices(
        self,
        db: AsyncSession,
        entity_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get invoices that haven't been matched to a PO/GRN"""
        from app.models.invoice import Invoice
        
        # Find invoices without a match record
        matched_invoice_ids = select(ThreeWayMatch.invoice_id).where(
            ThreeWayMatch.entity_id == entity_id
        )
        
        query = select(Invoice).where(
            and_(
                Invoice.entity_id == entity_id,
                Invoice.invoice_type == "bill",  # Vendor invoices
                Invoice.id.not_in(matched_invoice_ids)
            )
        )
        
        result = await db.execute(query)
        invoices = result.scalars().all()
        
        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                "vendor_name": inv.vendor_name if hasattr(inv, "vendor_name") else None,
                "total_amount": str(inv.total_amount or 0),
                "status": inv.status
            }
            for inv in invoices
        ]
    
    async def get_matching_summary(
        self,
        db: AsyncSession,
        entity_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get summary of matching status"""
        
        query = select(
            ThreeWayMatch.status,
            func.count(ThreeWayMatch.id).label("count"),
            func.sum(ThreeWayMatch.invoice_amount).label("total_amount")
        ).where(
            and_(
                ThreeWayMatch.entity_id == entity_id,
                ThreeWayMatch.created_at >= datetime.combine(start_date, datetime.min.time()),
                ThreeWayMatch.created_at <= datetime.combine(end_date, datetime.max.time())
            )
        ).group_by(ThreeWayMatch.status)
        
        result = await db.execute(query)
        rows = result.all()
        
        summary = {
            "matched": {"count": 0, "amount": Decimal("0")},
            "discrepancy": {"count": 0, "amount": Decimal("0")},
            "pending_review": {"count": 0, "amount": Decimal("0")},
            "rejected": {"count": 0, "amount": Decimal("0")}
        }
        
        for row in rows:
            status_key = row[0].value if hasattr(row[0], 'value') else str(row[0])
            summary[status_key] = {
                "count": row[1],
                "amount": str(row[2] or Decimal("0"))
            }
        
        total_count = sum(s["count"] for s in summary.values())
        matched_count = summary["matched"]["count"]
        match_rate = (matched_count / total_count * 100) if total_count else Decimal("0")
        
        return {
            "entity_id": str(entity_id),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "by_status": summary,
            "totals": {
                "total_matches": total_count,
                "successful_matches": matched_count,
                "match_rate": f"{match_rate:.1f}%"
            },
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def auto_match_invoices(
        self,
        db: AsyncSession,
        entity_id: UUID
    ) -> Dict[str, Any]:
        """
        Automatically match unmatched invoices to POs based on reference numbers
        """
        from app.models.invoice import Invoice
        
        unmatched = await self.get_unmatched_invoices(db, entity_id)
        
        matched = []
        failed = []
        
        for inv_data in unmatched:
            invoice = await db.get(Invoice, UUID(inv_data["id"]))
            if not invoice:
                continue
            
            # Try to find matching PO by reference
            po_ref = None
            if hasattr(invoice, 'po_reference') and invoice.po_reference:
                po_ref = invoice.po_reference
            elif hasattr(invoice, 'reference') and invoice.reference:
                # Extract PO number from reference
                if "PO" in invoice.reference.upper():
                    po_ref = invoice.reference
            
            if po_ref:
                po_query = select(PurchaseOrder).where(
                    and_(
                        PurchaseOrder.entity_id == entity_id,
                        PurchaseOrder.po_number == po_ref
                    )
                )
                result = await db.execute(po_query)
                po = result.scalar_one_or_none()
                
                if po:
                    try:
                        match_record = await self.match_invoice_to_po_grn(
                            db, entity_id, invoice.id, po.id
                        )
                        matched.append({
                            "invoice_id": str(invoice.id),
                            "invoice_number": invoice.invoice_number,
                            "po_number": po.po_number,
                            "status": match_record.status.value
                        })
                    except Exception as e:
                        failed.append({
                            "invoice_id": str(invoice.id),
                            "invoice_number": invoice.invoice_number,
                            "error": str(e)
                        })
        
        return {
            "entity_id": str(entity_id),
            "matched": matched,
            "failed": failed,
            "summary": {
                "total_processed": len(unmatched),
                "matched_count": len(matched),
                "failed_count": len(failed)
            }
        }
    
    async def _generate_po_number(self, db: AsyncSession, entity_id: UUID) -> str:
        """Generate unique PO number"""
        
        today = date.today()
        prefix = f"PO-{today.strftime('%Y%m')}"
        
        # Get last PO number
        query = select(func.max(PurchaseOrder.po_number)).where(
            and_(
                PurchaseOrder.entity_id == entity_id,
                PurchaseOrder.po_number.like(f"{prefix}%")
            )
        )
        result = await db.execute(query)
        last_po = result.scalar_one_or_none()
        
        if last_po:
            # Extract sequence and increment
            seq = int(last_po.split("-")[-1]) + 1
        else:
            seq = 1
        
        return f"{prefix}-{seq:04d}"
    
    async def _generate_grn_number(self, db: AsyncSession, entity_id: UUID) -> str:
        """Generate unique GRN number"""
        
        today = date.today()
        prefix = f"GRN-{today.strftime('%Y%m')}"
        
        query = select(func.max(GoodsReceivedNote.grn_number)).where(
            and_(
                GoodsReceivedNote.entity_id == entity_id,
                GoodsReceivedNote.grn_number.like(f"{prefix}%")
            )
        )
        result = await db.execute(query)
        last_grn = result.scalar_one_or_none()
        
        if last_grn:
            seq = int(last_grn.split("-")[-1]) + 1
        else:
            seq = 1
        
        return f"{prefix}-{seq:04d}"
    
    async def _get_total_received(self, db: AsyncSession, po_id: UUID) -> Decimal:
        """Get total quantity received for a PO"""
        
        query = select(func.sum(GoodsReceivedNoteItem.quantity_accepted)).join(
            GoodsReceivedNote
        ).where(
            GoodsReceivedNote.purchase_order_id == po_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() or Decimal("0")


# Singleton instance
three_way_matching_service = ThreeWayMatchingService()
